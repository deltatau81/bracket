from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import aiohttp
import pytest

from bracket.database import database
from bracket.models.db.match import (
    MatchPeriod,
    MatchPhaseState,
    MatchScoreEntrySource,
    MatchStatus,
)
from bracket.models.db.stage_item_inputs import StageItemInputInsertable
from bracket.schema import match_events, matches, players_x_teams, tournaments
from bracket.sql.matches import sql_get_match
from bracket.utils.dummy_records import (
    DUMMY_MATCH1,
    DUMMY_PLAYER1,
    DUMMY_PLAYER2,
    DUMMY_PLAYER3,
    DUMMY_PLAYER4,
    DUMMY_ROUND1,
    DUMMY_STAGE1,
    DUMMY_STAGE_ITEM1,
    DUMMY_TEAM1,
    DUMMY_TEAM2,
    DUMMY_TEAM3,
)
from bracket.utils.http import HTTPMethod
from tests.integration_tests.api.shared import (
    SUCCESS_RESPONSE,
    get_root_uvicorn_url,
    send_tournament_request,
)
from tests.integration_tests.models import AuthContext
from tests.integration_tests.sql import (
    inserted_match,
    inserted_player_in_team,
    inserted_round,
    inserted_stage,
    inserted_stage_item,
    inserted_stage_item_input,
    inserted_team,
)


@asynccontextmanager
async def event_match_context(
    auth_context: AuthContext,
    *,
    status: MatchStatus = MatchStatus.RUNNING,
    active_period: MatchPeriod | None = MatchPeriod.HALF1,
    phase_state: MatchPhaseState | None = MatchPhaseState.ACTIVE,
    is_youth_club_group: bool = False,
) -> AsyncIterator[dict[str, Any]]:
    tournament_id = auth_context.tournament.id
    async with (
        inserted_stage(DUMMY_STAGE1.model_copy(update={"tournament_id": tournament_id})) as stage,
        inserted_stage_item(
            DUMMY_STAGE_ITEM1.model_copy(
                update={
                    "stage_id": stage.id,
                    "ranking_id": auth_context.ranking.id,
                    "is_youth_club_group": is_youth_club_group,
                }
            )
        ) as stage_item,
        inserted_round(DUMMY_ROUND1.model_copy(update={"stage_item_id": stage_item.id})) as round_,
        inserted_team(DUMMY_TEAM1.model_copy(update={"tournament_id": tournament_id})) as team1,
        inserted_team(DUMMY_TEAM2.model_copy(update={"tournament_id": tournament_id})) as team2,
        inserted_team(DUMMY_TEAM3.model_copy(update={"tournament_id": tournament_id})) as team3,
        inserted_player_in_team(
            DUMMY_PLAYER1.model_copy(update={"tournament_id": tournament_id}), team1.id
        ) as player1,
        inserted_player_in_team(
            DUMMY_PLAYER2.model_copy(update={"tournament_id": tournament_id}), team1.id
        ) as player2,
        inserted_player_in_team(
            DUMMY_PLAYER3.model_copy(update={"tournament_id": tournament_id}), team2.id
        ) as player3,
        inserted_player_in_team(
            DUMMY_PLAYER4.model_copy(update={"tournament_id": tournament_id}), team1.id
        ) as player4,
        inserted_stage_item_input(
            StageItemInputInsertable(
                slot=0,
                team_id=team1.id,
                tournament_id=tournament_id,
                stage_item_id=stage_item.id,
            )
        ) as input1,
        inserted_stage_item_input(
            StageItemInputInsertable(
                slot=1,
                team_id=team2.id,
                tournament_id=tournament_id,
                stage_item_id=stage_item.id,
            )
        ) as input2,
        inserted_match(
            DUMMY_MATCH1.model_copy(
                update={
                    "round_id": round_.id,
                    "stage_item_input1_id": input1.id,
                    "stage_item_input2_id": input2.id,
                    "court_id": None,
                    "status": status,
                    "active_period": active_period,
                    "phase_state": phase_state,
                    "stage_item_input1_score": 0,
                    "stage_item_input2_score": 0,
                    "stage_item_input1_half1_score": 0,
                    "stage_item_input2_half1_score": 0,
                    "stage_item_input1_half2_score": 0,
                    "stage_item_input2_half2_score": 0,
                    "stage_item_input1_penalty_score": 0,
                    "stage_item_input2_penalty_score": 0,
                }
            )
        ) as match,
    ):
        await database.execute(
            query=players_x_teams.update().where(
                (players_x_teams.c.player_id == player1.id)
                & (players_x_teams.c.team_id == team1.id)
            ),
            values={"number": 21},
        )
        yield {
            "match": match,
            "round": round_,
            "stage_item": stage_item,
            "team1": team1,
            "team2": team2,
            "team3": team3,
            "player1": player1,
            "player2": player2,
            "player3": player3,
            "player4": player4,
        }


async def event_request(
    method: HTTPMethod,
    context: dict[str, Any],
    auth_context: AuthContext,
    suffix: str = "",
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    endpoint = f"matches/{context['match'].id}/events{suffix}"
    return await send_tournament_request(method, endpoint, auth_context, json=body)


async def event_request_with_status(
    method: HTTPMethod,
    context: dict[str, Any],
    auth_context: AuthContext,
    suffix: str = "",
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    url = (
        get_root_uvicorn_url()
        + f"tournaments/{auth_context.tournament.id}/matches/"
        + f"{context['match'].id}/events{suffix}"
    )
    async with aiohttp.ClientSession() as session:
        async with session.request(
            method=method.value,
            url=url,
            json=body,
            headers=auth_context.headers,
        ) as response:
            return response.status, await response.json()


async def phase_request(
    context: dict[str, Any], auth_context: AuthContext, action: str
) -> dict[str, Any]:
    return await send_tournament_request(
        HTTPMethod.POST,
        f"matches/{context['match'].id}/phase",
        auth_context,
        json={"action": action},
    )


def goal_body(context: dict[str, Any], team_key: str = "team1") -> dict[str, Any]:
    return {
        "team_id": context[team_key].id,
        "event_type": "GOAL",
        "period": "HALF2",
        "game_time_seconds": 10,
        "player_number": 17,
    }


async def set_match_state(
    context: dict[str, Any],
    *,
    status: MatchStatus,
    active_period: MatchPeriod | None,
    phase_state: MatchPhaseState | None,
) -> None:
    await database.execute(
        query=matches.update().where(matches.c.id == context["match"].id),
        values={
            "status": status.value,
            "active_period": active_period.value if active_period is not None else None,
            "phase_state": phase_state.value if phase_state is not None else None,
        },
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_manual_goal_crud_does_not_change_match_score(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with event_match_context(auth_context) as context:
        await database.execute(
            query=matches.update().where(matches.c.id == context["match"].id),
            values={
                "score_entry_source": MatchScoreEntrySource.MANUAL.value,
                "stage_item_input1_half1_score": 5,
                "stage_item_input2_half1_score": 3,
                "stage_item_input1_score": 5,
                "stage_item_input2_score": 3,
            },
        )
        body = goal_body(context)
        goal = (await event_request(HTTPMethod.POST, context, auth_context, body=body))["data"]
        match = await sql_get_match(context["match"].id)
        assert (match.stage_item_input1_score, match.stage_item_input2_score) == (5, 3)

        await event_request(
            HTTPMethod.PUT,
            context,
            auth_context,
            suffix=f"/{goal['id']}",
            body=body | {"team_id": context["team2"].id},
        )
        await event_request(
            HTTPMethod.DELETE,
            context,
            auth_context,
            suffix=f"/{goal['id']}",
        )
        match = await sql_get_match(context["match"].id)
        assert (match.stage_item_input1_score, match.stage_item_input2_score) == (5, 3)


@pytest.mark.asyncio(loop_scope="session")
async def test_competition_event_creation_follows_active_phase(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with event_match_context(
        auth_context,
        status=MatchStatus.PLANNED,
        active_period=None,
        phase_state=None,
    ) as context:
        body = goal_body(context)

        status_code, _ = await event_request_with_status(
            HTTPMethod.POST, context, auth_context, body=body
        )
        assert status_code == 422

        started = (await phase_request(context, auth_context, "START_MATCH"))["data"]
        assert (started["status"], started["active_period"], started["phase_state"]) == (
            "RUNNING",
            "HALF1",
            "ACTIVE",
        )

        status_code, response = await event_request_with_status(
            HTTPMethod.POST, context, auth_context, body=body
        )
        assert status_code == 200, response
        half1_event = response["data"]
        assert half1_event["period"] == "HALF1"

        ended = (await phase_request(context, auth_context, "END_PERIOD"))["data"]
        assert (ended["active_period"], ended["phase_state"]) == ("HALF1", "BREAK")

        status_code, _ = await event_request_with_status(
            HTTPMethod.POST, context, auth_context, body=body
        )
        assert status_code == 422

        status_code, response = await event_request_with_status(
            HTTPMethod.PUT,
            context,
            auth_context,
            suffix=f"/{half1_event['id']}",
            body=body | {"team_id": context["team2"].id, "period": "HALF1"},
        )
        assert status_code == 200, response

        half2 = (await phase_request(context, auth_context, "START_NEXT_PERIOD"))["data"]
        assert (half2["active_period"], half2["phase_state"]) == ("HALF2", "ACTIVE")

        status_code, response = await event_request_with_status(
            HTTPMethod.POST,
            context,
            auth_context,
            body=body | {"period": "PERIOD3"},
        )
        assert status_code == 200, response
        half2_event = response["data"]
        assert half2_event["period"] == "HALF2"

        await phase_request(context, auth_context, "END_PERIOD")
        status_code, response = await event_request_with_status(
            HTTPMethod.DELETE,
            context,
            auth_context,
            suffix=f"/{half2_event['id']}",
        )
        assert status_code == 200, response

        shootout = (
            await phase_request(context, auth_context, "START_NEXT_PERIOD")
        )["data"]
        assert (shootout["active_period"], shootout["phase_state"]) == (
            "SHOOTOUT",
            "ACTIVE",
        )

        shootout_event = (
            await event_request(
                HTTPMethod.POST,
                context,
                auth_context,
                body=body | {"period": "HALF1"},
            )
        )["data"]
        assert shootout_event["period"] == "SHOOTOUT"

        finished = (await phase_request(context, auth_context, "FINISH_MATCH"))["data"]
        assert finished["status"] == "FINISHED"

        status_code, _ = await event_request_with_status(
            HTTPMethod.POST, context, auth_context, body=body
        )
        assert status_code == 422

        status_code, response = await event_request_with_status(
            HTTPMethod.PUT,
            context,
            auth_context,
            suffix=f"/{shootout_event['id']}",
            body=body | {"team_id": context["team2"].id, "period": "SHOOTOUT"},
        )
        assert status_code == 200, response

        status_code, response = await event_request_with_status(
            HTTPMethod.DELETE,
            context,
            auth_context,
            suffix=f"/{shootout_event['id']}",
        )
        assert status_code == 200, response

        match = await sql_get_match(context["match"].id)
        assert match.stage_item_input1_half1_score == 0
        assert match.stage_item_input2_half1_score == 1
        assert match.stage_item_input1_half2_score == 0
        assert match.stage_item_input2_half2_score == 0
        assert match.stage_item_input1_score == 0
        assert match.stage_item_input2_score == 1
        assert match.stage_item_input1_penalty_score == 0
        assert match.stage_item_input2_penalty_score == 0

    for active_period, phase_state in (
        (None, None),
        (MatchPeriod.HALF1, None),
    ):
        async with event_match_context(
            auth_context,
            status=MatchStatus.RUNNING,
            active_period=active_period,
            phase_state=phase_state,
        ) as context:
            status_code, _ = await event_request_with_status(
                HTTPMethod.POST,
                context,
                auth_context,
                body=goal_body(context),
            )
            assert status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_goal_score_delta_reconciliation(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with event_match_context(auth_context) as context:
        await database.execute(
            query=matches.update().where(matches.c.id == context["match"].id),
            values={
                "stage_item_input1_half1_score": 3,
                "stage_item_input1_half2_score": 2,
                "stage_item_input1_score": 5,
            },
        )

        body = goal_body(context)
        goal = (await event_request(HTTPMethod.POST, context, auth_context, body=body))["data"]
        assert goal["period"] == "HALF1"
        assert goal["player_id"] is None
        assert goal["player_number"] == 17

        match = await sql_get_match(context["match"].id)
        assert match.stage_item_input1_half1_score == 4
        assert match.stage_item_input1_half2_score == 2
        assert match.stage_item_input1_score == 6

        before_invalid = match
        status_code, _ = await event_request_with_status(
            HTTPMethod.POST,
            context,
            auth_context,
            body=body | {"team_id": context["team3"].id},
        )
        assert status_code == 422
        after_invalid = await sql_get_match(context["match"].id)
        assert after_invalid.stage_item_input1_half1_score == before_invalid.stage_item_input1_half1_score
        assert after_invalid.stage_item_input1_score == before_invalid.stage_item_input1_score

        penalty_body = {
            "team_id": context["team2"].id,
            "event_type": "PENALTY",
            "period": "HALF2",
            "game_time_seconds": 20,
            "player_number": 8,
            "penalty_minutes": 2,
            "infraction": "Hooking",
        }
        penalty = (
            await event_request(HTTPMethod.POST, context, auth_context, body=penalty_body)
        )["data"]
        match_after_penalty = await sql_get_match(context["match"].id)
        assert match_after_penalty.stage_item_input1_score == 6
        assert match_after_penalty.stage_item_input2_score == 0

        moved_team = (
            await event_request(
                HTTPMethod.PUT,
                context,
                auth_context,
                suffix=f"/{goal['id']}",
                body=body | {"team_id": context["team2"].id, "period": "HALF1"},
            )
        )["data"]
        match = await sql_get_match(context["match"].id)
        assert match.stage_item_input1_half1_score == 3
        assert match.stage_item_input1_score == 5
        assert match.stage_item_input2_half1_score == 1
        assert match.stage_item_input2_score == 1

        moved_period = (
            await event_request(
                HTTPMethod.PUT,
                context,
                auth_context,
                suffix=f"/{moved_team['id']}",
                body=body | {"team_id": context["team2"].id, "period": "HALF2"},
            )
        )["data"]
        match = await sql_get_match(context["match"].id)
        assert match.stage_item_input2_half1_score == 0
        assert match.stage_item_input2_half2_score == 1
        assert match.stage_item_input2_score == 1

        converted_penalty = (
            await event_request(
                HTTPMethod.PUT,
                context,
                auth_context,
                suffix=f"/{moved_period['id']}",
                body=penalty_body | {"period": "HALF2"},
            )
        )["data"]
        match = await sql_get_match(context["match"].id)
        assert match.stage_item_input2_half2_score == 0
        assert match.stage_item_input2_score == 0

        converted_goal = (
            await event_request(
                HTTPMethod.PUT,
                context,
                auth_context,
                suffix=f"/{penalty['id']}",
                body=body | {"period": "HALF2"},
            )
        )["data"]
        match = await sql_get_match(context["match"].id)
        assert match.stage_item_input1_half1_score == 3
        assert match.stage_item_input1_half2_score == 3
        assert match.stage_item_input1_score == 6

        assert (
            await event_request(
                HTTPMethod.DELETE,
                context,
                auth_context,
                suffix=f"/{converted_goal['id']}",
            )
            == SUCCESS_RESPONSE
        )
        match = await sql_get_match(context["match"].id)
        assert match.stage_item_input1_half1_score == 3
        assert match.stage_item_input1_half2_score == 2
        assert match.stage_item_input1_score == 5

        await set_match_state(
            context,
            status=MatchStatus.RUNNING,
            active_period=MatchPeriod.SHOOTOUT,
            phase_state=MatchPhaseState.ACTIVE,
        )
        shootout = (
            await event_request(HTTPMethod.POST, context, auth_context, body=body)
        )["data"]
        match = await sql_get_match(context["match"].id)
        assert match.stage_item_input1_penalty_score == 1
        assert match.stage_item_input1_score == 5

        assert (
            await event_request(
                HTTPMethod.DELETE,
                context,
                auth_context,
                suffix=f"/{shootout['id']}",
            )
            == SUCCESS_RESPONSE
        )
        match = await sql_get_match(context["match"].id)
        assert match.stage_item_input1_penalty_score == 0
        assert match.stage_item_input1_score == 5

        await set_match_state(
            context,
            status=MatchStatus.RUNNING,
            active_period=MatchPeriod.HALF1,
            phase_state=MatchPhaseState.ACTIVE,
        )
        guarded = (
            await event_request(
                HTTPMethod.POST,
                context,
                auth_context,
                body=body | {"team_id": context["team2"].id},
            )
        )["data"]
        await database.execute(
            query=matches.update().where(matches.c.id == context["match"].id),
            values={
                "stage_item_input2_half1_score": 0,
                "stage_item_input2_score": 0,
            },
        )
        status_code, response = await event_request_with_status(
            HTTPMethod.DELETE,
            context,
            auth_context,
            suffix=f"/{guarded['id']}",
        )
        assert status_code == 422, response
        stored_ids = {
            event["id"]
            for event in (await event_request(HTTPMethod.GET, context, auth_context))["data"]
        }
        assert guarded["id"] in stored_ids

        assert converted_penalty["event_type"] == "PENALTY"


@pytest.mark.asyncio(loop_scope="session")
async def test_game_shootout_goal_score_reconciliation(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    await database.execute(
        tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
        values={"hockey_mode": "GAME_SHOOTOUT"},
    )
    try:
        async with event_match_context(
            auth_context, active_period=MatchPeriod.GAME
        ) as context:
            await send_tournament_request(
                HTTPMethod.PUT,
                f"matches/{context['match'].id}",
                auth_context,
                json={
                    "round_id": context["round"].id,
                    "stage_item_input1_score": 5,
                    "stage_item_input2_score": 3,
                    "stage_item_input1_penalty_score": 1,
                    "stage_item_input2_penalty_score": 2,
                },
            )
            match = await sql_get_match(context["match"].id)
            assert (match.stage_item_input1_score, match.stage_item_input2_score) == (5, 3)
            assert (
                match.stage_item_input1_penalty_score,
                match.stage_item_input2_penalty_score,
            ) == (1, 2)
            assert match.stage_item_input1_half1_score == 0
            assert match.stage_item_input1_half2_score == 0

            body = goal_body(context) | {"period": "GAME"}
            goal = (
                await event_request(HTTPMethod.POST, context, auth_context, body=body)
            )["data"]
            match = await sql_get_match(context["match"].id)
            assert (match.stage_item_input1_score, match.stage_item_input2_score) == (6, 3)
            assert match.stage_item_input1_half1_score == 0
            assert match.stage_item_input1_half2_score == 0

            updated = await event_request(
                HTTPMethod.PUT,
                context,
                auth_context,
                suffix=f"/{goal['id']}",
                body=body | {"team_id": context["team2"].id},
            )
            assert updated["data"]["period"] == "GAME"
            match = await sql_get_match(context["match"].id)
            assert (match.stage_item_input1_score, match.stage_item_input2_score) == (5, 4)

            await event_request(
                HTTPMethod.DELETE, context, auth_context, suffix=f"/{goal['id']}"
            )
            match = await sql_get_match(context["match"].id)
            assert (match.stage_item_input1_score, match.stage_item_input2_score) == (5, 3)

            await set_match_state(
                context,
                status=MatchStatus.RUNNING,
                active_period=MatchPeriod.SHOOTOUT,
                phase_state=MatchPhaseState.ACTIVE,
            )
            shootout_goal = (
                await event_request(HTTPMethod.POST, context, auth_context, body=body)
            )["data"]
            assert shootout_goal["period"] == "SHOOTOUT"
            match = await sql_get_match(context["match"].id)
            assert (match.stage_item_input1_score, match.stage_item_input2_score) == (5, 3)
            assert match.stage_item_input1_penalty_score == 2
    finally:
        await database.execute(
            tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
            values={"hockey_mode": "COMPETITION"},
        )


@pytest.mark.parametrize("source", [MatchScoreEntrySource.EVENTS, None])
@pytest.mark.asyncio(loop_scope="session")
async def test_youth_club_game_score_is_recalculated_from_goal_events(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext,
    source: MatchScoreEntrySource | None,
) -> None:
    await database.execute(
        tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
        values={
            "hockey_mode": "GAME_SHOOTOUT",
            "competition_format": "YOUTH_CLUB",
        },
    )
    try:
        async with event_match_context(
            auth_context,
            active_period=MatchPeriod.GAME,
            is_youth_club_group=True,
        ) as context:
            await database.execute(
                matches.update().where(matches.c.id == context["match"].id),
                values={"score_entry_source": source.value if source is not None else None},
            )
            body = goal_body(context) | {
                "period": "GAME",
                "game_time_seconds": None,
                "player_number": None,
            }

            match = await sql_get_match(context["match"].id)
            assert (match.stage_item_input1_score, match.stage_item_input2_score) == (0, 0)

            goals = [
                (
                    await event_request(
                        HTTPMethod.POST,
                        context,
                        auth_context,
                        body=body,
                    )
                )["data"]
            ]
            match = await sql_get_match(context["match"].id)
            assert (match.stage_item_input1_score, match.stage_item_input2_score) == (1, 0)

            for team_key, count in (("team1", 1), ("team2", 3)):
                for _ in range(count):
                    goals.append(
                        (
                            await event_request(
                                HTTPMethod.POST,
                                context,
                                auth_context,
                                body=body | {"team_id": context[team_key].id},
                            )
                        )["data"]
                    )

            match = await sql_get_match(context["match"].id)
            assert (match.stage_item_input1_score, match.stage_item_input2_score) == (2, 3)

            team2_goal = next(
                goal for goal in goals if goal["team_id"] == context["team2"].id
            )
            await event_request(
                HTTPMethod.DELETE,
                context,
                auth_context,
                suffix=f"/{team2_goal['id']}",
            )
            match = await sql_get_match(context["match"].id)
            assert (match.stage_item_input1_score, match.stage_item_input2_score) == (2, 2)

            team1_goal = next(
                goal for goal in goals if goal["team_id"] == context["team1"].id
            )
            await event_request(
                HTTPMethod.PUT,
                context,
                auth_context,
                suffix=f"/{team1_goal['id']}",
                body=body | {"team_id": context["team2"].id},
            )
            match = await sql_get_match(context["match"].id)
            assert (match.stage_item_input1_score, match.stage_item_input2_score) == (1, 3)

            await database.execute(
                matches.update().where(matches.c.id == context["match"].id),
                values={
                    "stage_item_input1_penalty_score": 3,
                    "stage_item_input2_penalty_score": 1,
                },
            )
            await set_match_state(
                context,
                status=MatchStatus.RUNNING,
                active_period=MatchPeriod.SHOOTOUT,
                phase_state=MatchPhaseState.ACTIVE,
            )
            shootout_goal = (
                await event_request(HTTPMethod.POST, context, auth_context, body=body)
            )["data"]
            assert shootout_goal["period"] == "SHOOTOUT"
            match = await sql_get_match(context["match"].id)
            assert (match.stage_item_input1_score, match.stage_item_input2_score) == (1, 3)
            assert (
                match.stage_item_input1_penalty_score,
                match.stage_item_input2_penalty_score,
            ) == (4, 1)

            await set_match_state(
                context,
                status=MatchStatus.FINISHED,
                active_period=MatchPeriod.GAME,
                phase_state=MatchPhaseState.BREAK,
            )
            reopened = await phase_request(context, auth_context, "REOPEN_MATCH")
            assert reopened["data"]["status"] == "RUNNING"
            await phase_request(context, auth_context, "RESUME_PERIOD")
            await event_request(HTTPMethod.POST, context, auth_context, body=body)
            match = await sql_get_match(context["match"].id)
            assert (match.stage_item_input1_score, match.stage_item_input2_score) == (2, 3)
    finally:
        await database.execute(
            tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
            values={
                "hockey_mode": "COMPETITION",
                "competition_format": "STANDARD",
            },
        )


@pytest.mark.parametrize(
    ("hockey_mode", "active_period"),
    [
        ("COMPETITION", MatchPeriod.HALF1),
        ("GAME_SHOOTOUT", MatchPeriod.GAME),
    ],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_youth_goal_time_is_optional(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
    hockey_mode: str,
    active_period: MatchPeriod,
) -> None:
    await database.execute(
        tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
        values={"hockey_mode": hockey_mode},
    )
    try:
        async with event_match_context(
            auth_context, active_period=active_period
        ) as context:
            body = goal_body(context) | {"period": active_period.value}
            body.pop("game_time_seconds")

            created = (
                await event_request(HTTPMethod.POST, context, auth_context, body=body)
            )["data"]
            assert created["game_time_seconds"] is None

            match = await sql_get_match(context["match"].id)
            assert match.stage_item_input1_score == 1

            listed = (await event_request(HTTPMethod.GET, context, auth_context))["data"]
            stored = next(event for event in listed if event["id"] == created["id"])
            assert stored["game_time_seconds"] is None

            edited = (
                await event_request(
                    HTTPMethod.PUT,
                    context,
                    auth_context,
                    suffix=f"/{created['id']}",
                    body=body | {"player_number": 18},
                )
            )["data"]
            assert edited["game_time_seconds"] is None

            timed = (
                await event_request(
                    HTTPMethod.PUT,
                    context,
                    auth_context,
                    suffix=f"/{created['id']}",
                    body=body | {"game_time_seconds": 342},
                )
            )["data"]
            assert timed["game_time_seconds"] == 342

            cleared = (
                await event_request(
                    HTTPMethod.PUT,
                    context,
                    auth_context,
                    suffix=f"/{created['id']}",
                    body=body | {"game_time_seconds": None},
                )
            )["data"]
            assert cleared["game_time_seconds"] is None

            assert (
                await event_request(
                    HTTPMethod.DELETE,
                    context,
                    auth_context,
                    suffix=f"/{created['id']}",
                )
                == SUCCESS_RESPONSE
            )
            match = await sql_get_match(context["match"].id)
            assert match.stage_item_input1_score == 0
    finally:
        await database.execute(
            tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
            values={"hockey_mode": "COMPETITION"},
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_standard_goal_still_requires_game_time(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    await database.execute(
        tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
        values={"hockey_mode": "STANDARD"},
    )
    try:
        async with event_match_context(
            auth_context, active_period=MatchPeriod.PERIOD1
        ) as context:
            body = goal_body(context) | {"period": "PERIOD1"}
            body.pop("game_time_seconds")
            status_code, _ = await event_request_with_status(
                HTTPMethod.POST, context, auth_context, body=body
            )
            assert status_code == 422

            timed = (
                await event_request(
                    HTTPMethod.POST,
                    context,
                    auth_context,
                    body=body | {"game_time_seconds": 42},
                )
            )["data"]
            assert timed["game_time_seconds"] == 42
            await event_request(
                HTTPMethod.DELETE,
                context,
                auth_context,
                suffix=f"/{timed['id']}",
            )
    finally:
        await database.execute(
            tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
            values={"hockey_mode": "COMPETITION"},
        )
@pytest.mark.asyncio(loop_scope="session")
async def test_match_event_player_snapshots_and_validation(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with event_match_context(auth_context) as context:
        body = goal_body(context) | {
            "player_id": context["player1"].id,
            "player_name": "forged",
            "player_number": 999,
        }
        goal = (await event_request(HTTPMethod.POST, context, auth_context, body=body))["data"]
        assert goal["player_name"] == context["player1"].name
        assert goal["player_number"] == 21

        foreign_player = body | {"player_id": context["player3"].id}
        response = await event_request(HTTPMethod.POST, context, auth_context, body=foreign_player)
        assert "does not belong" in response["detail"]

        duplicate_player = body | {"assist1_player_id": context["player1"].id}
        response = await event_request(
            HTTPMethod.POST, context, auth_context, body=duplicate_player
        )
        assert "multiple roles" in str(response["detail"])

        penalty_with_assist = {
            "team_id": context["team1"].id,
            "event_type": "PENALTY",
            "period": "HALF1",
            "game_time_seconds": 20,
            "assist1_name": "Not allowed",
        }
        response = await event_request(
            HTTPMethod.POST, context, auth_context, body=penalty_with_assist
        )
        assert "cannot contain assist" in str(response["detail"])

        await database.execute(query=matches.delete().where(matches.c.id == context["match"].id))
        remaining_events = await database.fetch_all(
            query=match_events.select().where(match_events.c.match_id == context["match"].id)
        )
        assert remaining_events == []


@pytest.mark.asyncio(loop_scope="session")
async def test_standard_match_event_periods(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    await database.execute(
        query=tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
        values={"hockey_mode": "STANDARD"},
    )
    try:
        async with event_match_context(
            auth_context,
            active_period=MatchPeriod.PERIOD1,
        ) as context:
            body = goal_body(context)
            for period in (
                MatchPeriod.PERIOD1,
                MatchPeriod.PERIOD2,
                MatchPeriod.PERIOD3,
                MatchPeriod.OVERTIME,
            ):
                await set_match_state(
                    context,
                    status=MatchStatus.RUNNING,
                    active_period=period,
                    phase_state=MatchPhaseState.ACTIVE,
                )
                response = await event_request(
                    HTTPMethod.POST,
                    context,
                    auth_context,
                    body=body | {"period": "HALF1"},
                )
                assert response["data"]["period"] == period.value

            stored_match = await sql_get_match(context["match"].id)
            assert stored_match.stage_item_input1_score == 0
            assert stored_match.stage_item_input1_half1_score == 0
            assert stored_match.stage_item_input1_half2_score == 0

            status_code, response = await event_request_with_status(
                HTTPMethod.PUT,
                context,
                auth_context,
                suffix=f"/{response['data']['id']}",
                body=body | {"period": "HALF1"},
            )
            assert status_code == 422, response
            assert "not allowed for STANDARD" in response["detail"]

            await set_match_state(
                context,
                status=MatchStatus.RUNNING,
                active_period=MatchPeriod.HALF1,
                phase_state=MatchPhaseState.ACTIVE,
            )
            status_code, response = await event_request_with_status(
                HTTPMethod.POST, context, auth_context, body=body
            )
            assert status_code == 422, response
            assert "not allowed for STANDARD" in response["detail"]
    finally:
        await database.execute(
            query=tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
            values={"hockey_mode": "COMPETITION"},
        )

@pytest.mark.asyncio(loop_scope="session")
async def test_penalty_catalog_endpoint_uses_effective_rules(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with event_match_context(auth_context) as context:
        endpoint = f"matches/{context['match'].id}/penalties/catalog"

        await database.execute(
            query=tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
            values={"ruleset": "IIHF", "ruleset_season": "2026/27"},
        )
        iihf = (
            await send_tournament_request(HTTPMethod.GET, endpoint, auth_context)
        )["data"]
        assert iihf["ruleset"] == "IIHF"
        assert iihf["season"] == "2026/27"
        assert iihf["age_category"] == auth_context.tournament.age_category.value
        assert iihf["catalog_source"] == "IIHF_2026_27"
        tripping = next(
            penalty for penalty in iihf["penalties"] if penalty["code"] == "TRIPPING"
        )
        assert tripping["rule"] == "57"
        assert tripping["label"] == "Beinstellen"
        assert tripping["default_penalty_type"] == "MINOR"

        await database.execute(
            query=tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
            values={"ruleset": "DEB"},
        )
        deb = (
            await send_tournament_request(HTTPMethod.GET, endpoint, auth_context)
        )["data"]
        assert deb["ruleset"] == "DEB"
        assert deb["catalog_source"] == "IIHF_BASE"


@pytest.mark.asyncio(loop_scope="session")
async def test_structured_penalty_snapshots_and_historical_corrections(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with event_match_context(auth_context) as context:
        score_before = await sql_get_match(context["match"].id)
        base = {
            "team_id": context["team1"].id,
            "event_type": "PENALTY",
            "period": "HALF2",
            "game_time_seconds": 32,
            "player_id": None,
            "player_number": 17,
        }
        tripping = (
            await event_request(
                HTTPMethod.POST,
                context,
                auth_context,
                body=base
                | {
                    "penalty_code": "TRIPPING",
                    "penalty_rule": "999",
                    "penalty_type": "MINOR",
                    "penalty_minutes": 99,
                    "infraction": "spoofed",
                    "game_misconduct": True,
                },
            )
        )["data"]
        assert tripping["period"] == "HALF1"
        assert tripping["player_id"] is None
        assert tripping["player_number"] == 17
        assert tripping["penalty_code"] == "TRIPPING"
        assert tripping["penalty_rule"] == "57"
        assert tripping["penalty_type"] == "MINOR"
        assert tripping["penalty_minutes"] == 2
        assert tripping["infraction"] == "Beinstellen"
        assert tripping["game_misconduct"] is False

        status_code, response = await event_request_with_status(
            HTTPMethod.POST,
            context,
            auth_context,
            body=base
            | {
                "penalty_code": "FIGHTING",
                "penalty_type": "AWARDED_GOAL",
            },
        )
        assert status_code == 422, response
        assert "not allowed" in response["detail"]

        major = (
            await event_request(
                HTTPMethod.POST,
                context,
                auth_context,
                body=base
                | {
                    "game_time_seconds": 40,
                    "penalty_code": "BOARDING",
                    "penalty_type": "MAJOR_GAME_MISCONDUCT",
                },
            )
        )["data"]
        assert major["penalty_minutes"] == 5
        assert major["game_misconduct"] is True

        penalty_shot = (
            await event_request(
                HTTPMethod.POST,
                context,
                auth_context,
                body=base
                | {
                    "game_time_seconds": 50,
                    "penalty_code": "TRIPPING",
                    "penalty_type": "PENALTY_SHOT",
                    "penalty_minutes": 2,
                },
            )
        )["data"]
        assert penalty_shot["penalty_minutes"] is None
        assert penalty_shot["game_misconduct"] is False

        custom = (
            await event_request(
                HTTPMethod.POST,
                context,
                auth_context,
                body=base
                | {
                    "game_time_seconds": 60,
                    "penalty_code": "OTHER",
                    "penalty_type": "CUSTOM",
                    "penalty_minutes": 3,
                    "infraction": "Manuelle Strafe",
                },
            )
        )["data"]
        assert custom["penalty_rule"] is None
        assert custom["penalty_minutes"] == 3
        assert custom["infraction"] == "Manuelle Strafe"

        legacy = (
            await event_request(
                HTTPMethod.POST,
                context,
                auth_context,
                body=base
                | {
                    "game_time_seconds": 70,
                    "penalty_type": "Legacy penalty",
                    "penalty_minutes": 6,
                    "infraction": "Legacy text",
                },
            )
        )["data"]
        listed = (await event_request(HTTPMethod.GET, context, auth_context))["data"]
        stored_legacy = next(event for event in listed if event["id"] == legacy["id"])
        assert stored_legacy["penalty_code"] is None
        assert stored_legacy["penalty_type"] == "Legacy penalty"
        assert stored_legacy["infraction"] == "Legacy text"

        await set_match_state(
            context,
            status=MatchStatus.RUNNING,
            active_period=MatchPeriod.HALF1,
            phase_state=MatchPhaseState.BREAK,
        )
        corrected = (
            await event_request(
                HTTPMethod.PUT,
                context,
                auth_context,
                suffix=f"/{tripping['id']}",
                body=base
                | {
                    "penalty_code": "HOOKING",
                    "penalty_type": "MINOR",
                },
            )
        )["data"]
        assert corrected["penalty_code"] == "HOOKING"
        assert corrected["penalty_rule"] == "55"
        assert corrected["infraction"] == "Haken"

        await set_match_state(
            context,
            status=MatchStatus.FINISHED,
            active_period=MatchPeriod.HALF1,
            phase_state=MatchPhaseState.BREAK,
        )
        corrected = (
            await event_request(
                HTTPMethod.PUT,
                context,
                auth_context,
                suffix=f"/{corrected['id']}",
                body=base
                | {
                    "penalty_code": "BOARDING",
                    "penalty_type": "MAJOR_GAME_MISCONDUCT",
                },
            )
        )["data"]
        assert corrected["penalty_rule"] == "41"
        assert corrected["game_misconduct"] is True

        score_after = await sql_get_match(context["match"].id)
        score_fields = (
            "stage_item_input1_score",
            "stage_item_input2_score",
            "stage_item_input1_half1_score",
            "stage_item_input2_half1_score",
            "stage_item_input1_half2_score",
            "stage_item_input2_half2_score",
            "stage_item_input1_penalty_score",
            "stage_item_input2_penalty_score",
        )
        assert all(
            getattr(score_after, field) == getattr(score_before, field)
            for field in score_fields
        )
