"""SQL/HTTP regressions, runnable without additional test dependencies.

Standalone execution requires a disposable database and explicit opt-in.
"""
import os
import unittest
from contextlib import AsyncExitStack
from decimal import Decimal

import aiohttp

from bracket.database import database, engine
from bracket.models.db.account import UserAccountType
from bracket.models.db.user_x_club import UserXClubInsertable, UserXClubRelation
from tests.integration_tests.mocks import get_mock_token, get_mock_user
from bracket.models.db.match import MatchPeriod, MatchPhaseState, MatchStatus
from bracket.models.db.stage_item import StageType
from bracket.models.db.stage_item_inputs import StageItemInputInsertable
from bracket.schema import metadata, matches, tournaments
from bracket.sql.matches import sql_get_match
from bracket.utils.dummy_records import (
    DUMMY_MATCH1, DUMMY_ROUND1, DUMMY_STAGE1, DUMMY_STAGE_ITEM1, DUMMY_TEAM1, DUMMY_TEAM2,
)
from tests.integration_tests.api.shared import UvicornTestServer, get_root_uvicorn_url
from tests.integration_tests.sql import (
    inserted_auth_context, inserted_match, inserted_round, inserted_stage,
    inserted_stage_item, inserted_stage_item_input, inserted_team, inserted_user, inserted_user_x_club,
)


@unittest.skipUnless(os.environ.get("BRACKET_ISOLATED_CONSISTENCY_TESTS") == "1",
                     "Requires an explicitly isolated disposable database")
class MatchConsistencyHttpTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        metadata.create_all(engine)
        await database.connect()
        self.stack = AsyncExitStack()
        self.auth = await self.stack.enter_async_context(inserted_auth_context())
        self.server = UvicornTestServer()
        await self.server.up()

    async def asyncTearDown(self):
        await self.stack.aclose()
        await self.server.down()
        if database.is_connected:
            await database.disconnect()
        metadata.drop_all(engine)

    async def context(self, mode, source="MANUAL", youth=False):
        await database.execute(tournaments.update().where(tournaments.c.id == self.auth.tournament.id),
                               values={"hockey_mode": mode, "competition_format": "YOUTH_CLUB" if youth else "STANDARD"})
        stage = await self.stack.enter_async_context(inserted_stage(
            DUMMY_STAGE1.model_copy(update={"tournament_id": self.auth.tournament.id})))
        item = await self.stack.enter_async_context(inserted_stage_item(
            DUMMY_STAGE_ITEM1.model_copy(update={"stage_id": stage.id, "ranking_id": self.auth.ranking.id,
                                               "type": StageType.ROUND_ROBIN, "is_youth_club_group": youth})))
        round_ = await self.stack.enter_async_context(inserted_round(
            DUMMY_ROUND1.model_copy(update={"stage_item_id": item.id, "is_draft": False})))
        teams = []
        inputs = []
        for slot, dummy in enumerate((DUMMY_TEAM1, DUMMY_TEAM2)):
            team = await self.stack.enter_async_context(inserted_team(
                dummy.model_copy(update={"tournament_id": self.auth.tournament.id})))
            teams.append(team)
            inputs.append(await self.stack.enter_async_context(inserted_stage_item_input(
                StageItemInputInsertable(slot=slot, team_id=team.id,
                    tournament_id=self.auth.tournament.id, stage_item_id=item.id))))
        match = await self.stack.enter_async_context(inserted_match(DUMMY_MATCH1.model_copy(update={
            "round_id": round_.id, "stage_item_input1_id": inputs[0].id, "stage_item_input2_id": inputs[1].id,
            "court_id": None, "status": MatchStatus.RUNNING,
            "active_period": MatchPeriod.GAME if mode == "GAME_SHOOTOUT" else MatchPeriod.HALF1,
            "phase_state": MatchPhaseState.ACTIVE,
            "stage_item_input1_score": 3, "stage_item_input2_score": 1,
            "stage_item_input1_half1_score": 2, "stage_item_input2_half1_score": 1,
            "stage_item_input1_half2_score": 1, "stage_item_input2_half2_score": 0,
            "stage_item_input1_penalty_score": 1, "stage_item_input2_penalty_score": 0,
        })))
        await database.execute(matches.update().where(matches.c.id == match.id),
                               values={"score_entry_source": source})
        return match, teams

    async def request(self, method, endpoint, body=None, status=200):
        url = get_root_uvicorn_url() + f"tournaments/{self.auth.tournament.id}/" + endpoint
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=body, headers=self.auth.headers) as response:
                result = await response.json()
                self.assertEqual(response.status, status, result)
                return result

    async def test_manual_partial_full_zero_and_standard_http(self):
        for mode in ("STANDARD", "COMPETITION", "GAME_SHOOTOUT"):
            with self.subTest(mode=mode):
                match, _ = await self.context(mode)
                endpoint = f"matches/{match.id}"
                body = {"round_id": match.round_id, "stage_item_input1_penalty_score": 0}
                await self.request("PUT", endpoint, body)
                first = await sql_get_match(match.id)
                self.assertEqual(first.stage_item_input1_half1_score, 2)
                self.assertEqual(first.stage_item_input1_score, 3)
                self.assertEqual(first.stage_item_input1_penalty_score, 0)
                await self.request("PUT", endpoint, body)
                self.assertEqual((await sql_get_match(match.id)).model_dump(), first.model_dump())
                await self.request("PUT", endpoint, {"round_id": match.round_id,
                    "stage_item_input1_half1_score": None}, status=422)
                full = {"round_id": match.round_id,
                    "stage_item_input1_score": 9, "stage_item_input2_score": 8,
                    "stage_item_input1_half1_score": 0, "stage_item_input2_half1_score": 0,
                    "stage_item_input1_half2_score": 0, "stage_item_input2_half2_score": 0,
                    "stage_item_input1_penalty_score": 0, "stage_item_input2_penalty_score": 0}
                await self.request("PUT", endpoint, full)
                updated = await sql_get_match(match.id)
                self.assertEqual(updated.stage_item_input1_score, 0 if mode == "COMPETITION" else 9)

    async def test_youth_sources_and_finished_event_ranking_http(self):
        for source in ("MANUAL", "EVENTS", None):
            with self.subTest(source=source):
                match, teams = await self.context("GAME_SHOOTOUT", source, youth=True)
                endpoint = f"matches/{match.id}/events"
                goal = {"team_id": teams[0].id, "event_type": "GOAL", "period": "GAME"}
                event = (await self.request("POST", endpoint, goal))["data"]
                current = await sql_get_match(match.id)
                self.assertEqual(current.stage_item_input1_score, 3 if source == "MANUAL" else 1)
                await database.execute(matches.update().where(matches.c.id == match.id),
                    values={"status": "FINISHED", "active_period": "SHOOTOUT", "phase_state": "BREAK"})
                await self.request("PUT", endpoint + f"/{event['id']}", {**goal, "team_id": teams[1].id})
                totals = (await self.request("GET", "overall_standings"))["data"]
                own = next(row for row in totals if row["team_id"] == teams[0].id)
                self.assertEqual(Decimal(own["game_points"]), Decimal("3") if source == "MANUAL" else Decimal("1"))
                await self.request("DELETE", endpoint + f"/{event['id']}")
                totals = (await self.request("GET", "overall_standings"))["data"]
                own = next(row for row in totals if row["team_id"] == teams[0].id)
                self.assertEqual(Decimal(own["game_points"]), Decimal("3") if source == "MANUAL" else Decimal("2"))
                after = await sql_get_match(match.id)
                self.assertEqual(after.score_entry_source.value if after.score_entry_source else None, source)

    async def test_scorer_mode_access_and_admin_protection_http(self):
        original_auth = self.auth
        user = await self.stack.enter_async_context(inserted_user(
            get_mock_user().model_copy(update={"account_type": UserAccountType.SCORER})))
        relation = await self.stack.enter_async_context(inserted_user_x_club(
            UserXClubInsertable(user_id=user.id, club_id=self.auth.club.id,
                                relation=UserXClubRelation.COLLABORATOR)))
        self.auth = self.auth.model_copy(update={
            "user": user, "user_x_club": relation,
            "headers": {"Authorization": f"Bearer {get_mock_token(user.email)}"},
        })
        for mode in ("GAME_SHOOTOUT", "STANDARD", "COMPETITION"):
            with self.subTest(mode=mode):
                match, _ = await self.context(mode)
                body = {"round_id": match.round_id, "stage_item_input1_score": 0,
                        "stage_item_input2_penalty_score": 2}
                await self.request("PUT", f"matches/{match.id}", body,
                                   status=200 if mode == "GAME_SHOOTOUT" else 403)
                current = await sql_get_match(match.id)
                self.assertEqual(current.stage_item_input1_score,
                                 0 if mode == "GAME_SHOOTOUT" else 3)
                await self.request("PUT", f"matches/{match.id}",
                    {"round_id": match.round_id, "court_id": None}, status=403)
        match, _ = await self.context("GAME_SHOOTOUT")
        await database.execute(tournaments.update().where(tournaments.c.id == self.auth.tournament.id),
                               values={"status": "ARCHIVED"})
        await self.request("PUT", f"matches/{match.id}",
            {"round_id": match.round_id, "stage_item_input1_score": 0}, status=400)
        await database.execute(tournaments.update().where(tournaments.c.id == self.auth.tournament.id),
                               values={"status": "OPEN"})
        self.auth = original_auth

    async def test_competition_finished_goal_corrections_recalculate_points(self):
        match, teams = await self.context("COMPETITION", "EVENTS")
        goal = {"team_id": teams[0].id, "event_type": "GOAL", "period": "HALF1"}
        event = (await self.request("POST", f"matches/{match.id}/events", goal))["data"]
        await database.execute(matches.update().where(matches.c.id == match.id),
            values={"status": "FINISHED", "active_period": "SHOOTOUT", "phase_state": "BREAK"})
        endpoint = f"matches/{match.id}/events/{event['id']}"
        await self.request("PUT", endpoint, {**goal, "team_id": teams[1].id})
        totals = (await self.request("GET", "overall_standings"))["data"]
        own = next(row for row in totals if row["team_id"] == teams[0].id)
        self.assertEqual(Decimal(own["game_points"]), Decimal("4"))
        await self.request("DELETE", endpoint)
        totals = (await self.request("GET", "overall_standings"))["data"]
        own = next(row for row in totals if row["team_id"] == teams[0].id)
        self.assertEqual(Decimal(own["game_points"]), Decimal("5"))


# The regular project suite uses its existing database/server fixtures.
# Standalone unittest is only a fallback when pytest is unavailable.
try:
    import pytest
except ImportError:
    pytest = None

if pytest is not None:
    @pytest.mark.parametrize("scenario", [
        "test_manual_partial_full_zero_and_standard_http",
        "test_youth_sources_and_finished_event_ranking_http",
        "test_scorer_mode_access_and_admin_protection_http",
        "test_competition_finished_goal_corrections_recalculate_points",
    ])
    @pytest.mark.asyncio(loop_scope="session")
    async def test_match_consistency_http(
        startup_and_shutdown_uvicorn_server, auth_context, scenario
    ):
        case = MatchConsistencyHttpTest()
        case.auth = auth_context
        try:
            async with AsyncExitStack() as stack:
                case.stack = stack
                await getattr(case, scenario)()
        finally:
            await database.execute(
                tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
                values={
                    "hockey_mode": auth_context.tournament.hockey_mode.value,
                    "competition_format": auth_context.tournament.competition_format.value,
                    "status": auth_context.tournament.status.value,
                },
            )
