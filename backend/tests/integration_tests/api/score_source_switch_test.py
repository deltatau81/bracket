import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import patch

import aiohttp
import pytest

from bracket.database import database
from bracket.logic.ranking.calculation import recalculate_ranking_for_stage_item
from bracket.logic.score_source import ALL_SCORE_FIELDS
from bracket.models.db.account import UserAccountType
from bracket.models.db.match import MatchPeriod, MatchPhaseState, MatchStatus
from bracket.models.db.match_event import MatchEventInsertable, MatchEventPeriod, MatchEventType
from bracket.models.db.user_x_club import UserXClubInsertable, UserXClubRelation
from bracket.schema import (
    competition_disciplines,
    competition_results,
    competition_scoring,
    competitions,
    matches,
    stage_item_inputs,
    teams,
    tournaments,
)
from bracket.sql.competitions import get_tournament_overall_standings
from bracket.sql.match_events import create_match_event, get_match_events
from bracket.sql.match_write import match_write_context
from bracket.sql.matches import sql_get_match
from bracket.utils.dummy_records import DUMMY_CLUB, DUMMY_MOCK_TIME, DUMMY_TOURNAMENT
from tests.integration_tests.api.match_events_test import event_match_context
from tests.integration_tests.api.shared import get_root_uvicorn_url
from tests.integration_tests.mocks import get_mock_token, get_mock_user
from tests.integration_tests.sql import (
    inserted_club,
    inserted_tournament,
    inserted_user,
    inserted_user_x_club,
)


@asynccontextmanager
async def context(auth, mode="COMPETITION", source="MANUAL", with_events=False, status="RUNNING"):
    tid = auth.tournament.id
    keys = (
        "hockey_mode",
        "competition_format",
        "status",
        "game_win_points",
        "game_draw_points",
        "game_loss_points",
        "shootout_win_points",
        "shootout_draw_points",
        "shootout_loss_points",
    )
    row = await database.fetch_one(tournaments.select().where(tournaments.c.id == tid))
    original = {key: row[key] for key in keys}
    await database.execute(
        tournaments.update().where(tournaments.c.id == tid), {"hockey_mode": mode, "status": "OPEN"}
    )
    try:
        async with event_match_context(
            auth,
            active_period=MatchPeriod.GAME if mode == "GAME_SHOOTOUT" else MatchPeriod.HALF1,
            status=MatchStatus(status),
            phase_state=MatchPhaseState.ACTIVE,
        ) as ctx:
            mid = ctx["match"].id
            await database.execute(
                matches.update().where(matches.c.id == mid),
                {
                    "score_entry_source": source,
                    "stage_item_input1_score": 7,
                    "stage_item_input2_score": 4,
                    "stage_item_input1_half1_score": 5,
                    "stage_item_input2_half1_score": 3,
                    "stage_item_input1_half2_score": 2,
                    "stage_item_input2_half2_score": 1,
                    "stage_item_input1_penalty_score": 4,
                    "stage_item_input2_penalty_score": 2,
                },
            )
            if with_events:
                periods = (
                    ["GAME", "SHOOTOUT"]
                    if mode == "GAME_SHOOTOUT"
                    else ["HALF1", "HALF2", "SHOOTOUT"]
                )
                for period in periods:
                    for team in (ctx["team1"], ctx["team1"], ctx["team2"]):
                        await create_match_event(
                            MatchEventInsertable(
                                match_id=mid,
                                team_id=team.id,
                                event_type=MatchEventType.GOAL,
                                period=MatchEventPeriod(period),
                                created=DUMMY_MOCK_TIME,
                            )
                        )
                await create_match_event(
                    MatchEventInsertable(
                        match_id=mid,
                        team_id=ctx["team1"].id,
                        event_type=MatchEventType.PENALTY,
                        period=MatchEventPeriod(periods[0]),
                        game_time_seconds=20,
                        created=DUMMY_MOCK_TIME,
                    )
                )
            yield ctx
    finally:
        await database.execute(tournaments.update().where(tournaments.c.id == tid), original)


async def request(auth, ctx, action, body=None, method="POST", headers=None, tid=None):
    url = (
        get_root_uvicorn_url() + f"tournaments/{tid or auth.tournament.id}/matches/"
        f"{ctx['match'].id}/{action}"
    )
    async with aiohttp.ClientSession() as session:
        async with session.request(
            method, url.rstrip("/"), json=body, headers=auth.headers if headers is None else headers
        ) as response:
            return response.status, (
                await response.json()
                if response.content_type == "application/json"
                else {"detail": await response.text()}
            )


async def preview(auth, ctx, target):
    code, data = await request(auth, ctx, "score-source/preview", {"target_source": target})
    assert code == 200, data
    return data["data"]


async def confirm(auth, ctx, target, token):
    return await request(
        auth, ctx, "score-source/confirm", {"target_source": target, "conflict_token": token}
    )


@pytest.mark.parametrize("mode", ["COMPETITION", "GAME_SHOOTOUT"])
@pytest.mark.parametrize(
    "source,target",
    [("MANUAL", "EVENTS"), ("EVENTS", "MANUAL"), (None, "MANUAL"), (None, "EVENTS")],
)
@pytest.mark.parametrize("with_events", [False, True])
@pytest.mark.asyncio(loop_scope="session")
async def test_http_switch_matrix_and_readonly_preview(
    auth_context, mode, source, target, with_events
):
    async with context(auth_context, mode, source, with_events) as ctx:
        before = (await sql_get_match(ctx["match"].id)).model_dump()
        events = [event.model_dump() for event in await get_match_events(ctx["match"].id)]
        p = await preview(auth_context, ctx, target)
        assert p["current_source"] == source
        assert (await sql_get_match(ctx["match"].id)).model_dump() == before
        code, response = await confirm(auth_context, ctx, target, p["conflict_token"])
        assert code == 200, response
        result = response["data"]
        assert result["active_source"] == target
        assert result["match"]["score_entry_source"] == target
        assert result["current_scores"] == p["resulting_scores"]
        assert [event.model_dump() for event in await get_match_events(ctx["match"].id)] == events
        if target == "EVENTS":
            assert all(
                section["team1_score"] == (2 if with_events else 0)
                and section["team2_score"] == int(with_events)
                for section in result["current_scores"]
            )
            assert result["match"]["stage_item_input1_score"] == (
                (2 if with_events else 0) * (2 if mode == "COMPETITION" else 1)
            )
        else:
            assert all(result["match"][field] == before[field] for field in ALL_SCORE_FIELDS)
        if target == "MANUAL":
            code, _ = await request(
                auth_context,
                ctx,
                "events",
                {"team_id": ctx["team1"].id, "event_type": "GOAL", "period": "HALF1"},
            )
            assert code == 200
            after = await sql_get_match(ctx["match"].id)
            assert all(getattr(after, field) == before[field] for field in ALL_SCORE_FIELDS)


@pytest.mark.parametrize("source", ["MANUAL", "EVENTS"])
@pytest.mark.asyncio(loop_scope="session")
async def test_same_source_noop_and_old_confirmation_not_replayed(auth_context, source):
    async with context(auth_context, source=source, with_events=True) as ctx:
        before = (await sql_get_match(ctx["match"].id)).model_dump()
        p = await preview(auth_context, ctx, source)
        assert not p["scores_changed"]
        code, _ = await confirm(auth_context, ctx, source, p["conflict_token"])
        assert code == 200
        assert (await sql_get_match(ctx["match"].id)).model_dump() == before
        other = "MANUAL" if source == "EVENTS" else "EVENTS"
        p = await preview(auth_context, ctx, other)
        assert (await confirm(auth_context, ctx, other, p["conflict_token"]))[0] == 200
        assert (await confirm(auth_context, ctx, other, p["conflict_token"]))[0] == 409


@pytest.mark.parametrize(
    "change", ["event_create", "event_update", "event_delete", "score", "phase", "source", "rule"]
)
@pytest.mark.asyncio(loop_scope="session")
async def test_changed_state_invalidates_confirmation(auth_context, change):
    async with context(auth_context, with_events=True) as ctx:
        p = await preview(auth_context, ctx, "EVENTS")
        if change.startswith("event_"):
            saved = next(
                event
                for event in await get_match_events(ctx["match"].id)
                if event.event_type is MatchEventType.GOAL
            )
            body = {"team_id": ctx["team2"].id, "event_type": "GOAL", "period": "HALF1"}
            endpoint = "events" if change == "event_create" else f"events/{saved.id}"
            method = {"event_create": "POST", "event_update": "PUT", "event_delete": "DELETE"}[
                change
            ]
            assert (
                await request(
                    auth_context, ctx, endpoint, body if method != "DELETE" else None, method
                )
            )[0] == 200
        elif change == "score":
            assert (
                await request(
                    auth_context,
                    ctx,
                    "",
                    {"round_id": ctx["match"].round_id, "stage_item_input1_half1_score": 9},
                    "PUT",
                )
            )[0] == 200
        elif change == "phase":
            assert (await request(auth_context, ctx, "phase", {"action": "END_PERIOD"}))[0] == 200
        elif change == "source":
            await database.execute(
                matches.update().where(matches.c.id == ctx["match"].id),
                {"score_entry_source": None},
            )
        else:
            await database.execute(
                tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
                {"game_win_points": Decimal("4.25")},
            )
        current = (await sql_get_match(ctx["match"].id)).model_dump()
        assert (await confirm(auth_context, ctx, "EVENTS", p["conflict_token"]))[0] == 409
        assert (await sql_get_match(ctx["match"].id)).model_dump() == current


@pytest.mark.parametrize("action", ["preview", "confirm"])
@pytest.mark.asyncio(loop_scope="session")
async def test_access_validation_and_archive(auth_context, action):
    async with context(auth_context) as ctx:
        body = {"target_source": "EVENTS"}
        if action == "confirm":
            body["conflict_token"] = (await preview(auth_context, ctx, "EVENTS"))["conflict_token"]
        endpoint = "score-source/" + action
        assert (await request(auth_context, ctx, endpoint, body, headers={}))[0] == 401
        assert (await request(auth_context, ctx, endpoint, body, tid=999999))[0] == 404
        other = {**ctx, "match": ctx["match"].model_copy(update={"id": 999999})}
        assert (await request(auth_context, other, endpoint, body))[0] == 404
        async with inserted_user(
            get_mock_user().model_copy(update={"account_type": UserAccountType.SCORER})
        ) as user:
            async with inserted_user_x_club(
                UserXClubInsertable(
                    user_id=user.id,
                    club_id=auth_context.club.id,
                    relation=UserXClubRelation.COLLABORATOR,
                )
            ):
                headers = {"Authorization": f"Bearer {get_mock_token(user.email)}"}
                assert (await request(auth_context, ctx, endpoint, body, headers=headers))[0] == 403
        await database.execute(
            tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
            {"hockey_mode": "STANDARD"},
        )
        assert (await request(auth_context, ctx, endpoint, body))[0] == 422
        await database.execute(
            tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
            {"hockey_mode": "COMPETITION", "status": "ARCHIVED"},
        )
        assert (await request(auth_context, ctx, endpoint, body))[0] == 400


@pytest.mark.parametrize(
    "action,body",
    [
        ("preview", {"target_source": None}),
        ("preview", {"target_source": "LEGACY"}),
        ("confirm", {"target_source": "EVENTS"}),
        ("confirm", {"target_source": "EVENTS", "conflict_token": "invalid"}),
    ],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_invalid_request_contract(auth_context, action, body):
    async with context(auth_context) as ctx:
        assert (await request(auth_context, ctx, "score-source/" + action, body))[0] == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_real_foreign_tournament_match_is_not_accessible(auth_context):
    async with context(auth_context) as ctx:
        await database.execute(
            tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
            {"hockey_mode": "COMPETITION"},
        )
        async with inserted_tournament(
            DUMMY_TOURNAMENT.model_copy(
                update={
                    "club_id": auth_context.club.id,
                    "dashboard_endpoint": None,
                }
            )
        ) as other:
            body = {"target_source": "EVENTS"}
            assert (await request(auth_context, ctx, "score-source/preview", body, tid=other.id))[
                0
            ] == 404
            body["conflict_token"] = (await preview(auth_context, ctx, "EVENTS"))["conflict_token"]
            assert (await request(auth_context, ctx, "score-source/confirm", body, tid=other.id))[
                0
            ] == 404


async def wait_for_database_waiter():
    for _ in range(100):
        await database.execute("SELECT pg_stat_clear_snapshot()")
        waiting = await database.fetch_val("""
            SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()
            AND wait_event_type = 'Lock' AND query LIKE '%FOR UPDATE%'
        """)
        if waiting:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("HTTP writer did not wait for the actual PostgreSQL lock")


@pytest.mark.parametrize("writer", ["event", "event_update", "event_delete", "score", "phase"])
@pytest.mark.parametrize("confirmation_first", [False, True])
@pytest.mark.asyncio(loop_scope="session")
async def test_real_concurrent_writes_are_serialized(auth_context, writer, confirmation_first):
    async with context(auth_context, with_events=writer in {"event_update", "event_delete"}) as ctx:
        p = await preview(auth_context, ctx, "EVENTS")
        saved = next(
            (
                event
                for event in await get_match_events(ctx["match"].id)
                if event.event_type is MatchEventType.GOAL
            ),
            None,
        )

        async def write():
            if writer in {"event_update", "event_delete"}:
                assert saved is not None
                return await request(
                    auth_context,
                    ctx,
                    f"events/{saved.id}",
                    {"team_id": ctx["team2"].id, "event_type": "GOAL", "period": "HALF1"}
                    if writer == "event_update"
                    else None,
                    "PUT" if writer == "event_update" else "DELETE",
                )
            if writer == "event":
                return await request(
                    auth_context,
                    ctx,
                    "events",
                    {"team_id": ctx["team1"].id, "event_type": "GOAL", "period": "HALF1"},
                )
            if writer == "score":
                return await request(
                    auth_context,
                    ctx,
                    "",
                    {"round_id": ctx["match"].round_id, "stage_item_input1_half1_score": 9},
                    "PUT",
                )
            return await request(auth_context, ctx, "phase", {"action": "END_PERIOD"})

        async def switch():
            return await confirm(auth_context, ctx, "EVENTS", p["conflict_token"])

        tasks = []
        try:
            async with match_write_context(auth_context.tournament.id, ctx["match"].id):
                tasks.append(asyncio.create_task(switch() if confirmation_first else write()))
                await wait_for_database_waiter()
                tasks.append(asyncio.create_task(write() if confirmation_first else switch()))
                await asyncio.sleep(0.05)
                assert not any(task.done() for task in tasks)
            results = await asyncio.wait_for(asyncio.gather(*tasks), 10)
            confirmation, mutation = results if confirmation_first else list(reversed(results))
            assert confirmation[0] == (200 if confirmation_first else 409), results
            assert mutation[0] == (409 if confirmation_first and writer == "score" else 200), (
                results
            )
            current = await sql_get_match(ctx["match"].id)
            assert current.score_entry_source.value == (
                "EVENTS" if confirmation_first else "MANUAL"
            )
            if confirmation_first:
                assert current.stage_item_input1_half1_score == (
                    1 if writer.startswith("event") else 0
                )
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio(loop_scope="session")
async def test_ranking_failure_rolls_back_scores_source_and_ranking(auth_context):
    async with context(auth_context, with_events=True, status="FINISHED") as ctx:
        before = (await sql_get_match(ctx["match"].id)).model_dump()
        before_inputs = [
            dict(row)
            for row in await database.fetch_all(
                stage_item_inputs.select().where(
                    stage_item_inputs.c.stage_item_id == ctx["stage_item"].id
                )
            )
        ]
        p = await preview(auth_context, ctx, "EVENTS")

        async def fail_after_ranking(tid, item):
            await recalculate_ranking_for_stage_item(tid, item)
            raise RuntimeError("Injected transaction failure after ranking writes")

        with patch("bracket.routes.matches.recalculate_ranking_for_stage_item", fail_after_ranking):
            assert (await confirm(auth_context, ctx, "EVENTS", p["conflict_token"]))[0] == 500
        assert (await sql_get_match(ctx["match"].id)).model_dump() == before
        assert [
            dict(row)
            for row in await database.fetch_all(
                stage_item_inputs.select().where(
                    stage_item_inputs.c.stage_item_id == ctx["stage_item"].id
                )
            )
        ] == before_inputs


@pytest.mark.parametrize("mode", ["COMPETITION", "GAME_SHOOTOUT"])
@pytest.mark.parametrize("status", ["RUNNING", "FINISHED"])
@pytest.mark.asyncio(loop_scope="session")
async def test_configured_ranking_club_total_and_competition_unchanged(auth_context, mode, status):
    async with context(auth_context, mode, with_events=True, status=status) as ctx:
        tid = auth_context.tournament.id
        await database.execute(
            tournaments.update().where(tournaments.c.id == tid),
            {
                "competition_format": "YOUTH_CLUB",
                "game_win_points": Decimal("3.25"),
                "game_draw_points": Decimal("0.35"),
                "game_loss_points": Decimal("0.10"),
                "shootout_win_points": Decimal("1.50"),
                "shootout_draw_points": Decimal("0.25"),
                "shootout_loss_points": Decimal("0.05"),
            },
        )
        async with inserted_club(
            DUMMY_CLUB.model_copy(update={"name": "Participating Club"})
        ) as club:
            await database.execute(
                teams.update().where(teams.c.id.in_([ctx["team1"].id, ctx["team2"].id])),
                {"participant_club_id": club.id},
            )
            cid = await database.execute(
                competitions.insert().values(
                    tournament_id=tid, name="Unchanged Technique", start_time=DUMMY_MOCK_TIME
                )
            )
            try:
                did = await database.execute(
                    competition_disciplines.insert().values(competition_id=cid, name="Technique")
                )
                await database.execute(
                    competition_scoring.insert().values(
                        competition_id=cid, place=1, points=Decimal("1.25")
                    )
                )
                await database.execute(
                    competition_results.insert().values(
                        discipline_id=did, team_id=ctx["team1"].id, place=1
                    )
                )
                p = await preview(auth_context, ctx, "EVENTS")
                assert p["rankings_may_change"] == (status == "FINISHED")
                assert (await confirm(auth_context, ctx, "EVENTS", p["conflict_token"]))[0] == 200
                standings = await get_tournament_overall_standings(tid)
                own = next(row for row in standings if row.club_id == club.id)
                expected = (
                    (Decimal("8.25") if mode == "COMPETITION" else Decimal("4.90"))
                    if status == "FINISHED"
                    else Decimal("0")
                )
                assert own.game_points == expected
                assert own.competition_points == Decimal("1.25")
                assert own.total_points == expected + Decimal("1.25")
                assert own.team_id is None and own.team_name is None
                assert club.id != auth_context.club.id
            finally:
                await database.execute(competitions.delete().where(competitions.c.id == cid))
                await database.execute(
                    teams.update().where(teams.c.id.in_([ctx["team1"].id, ctx["team2"].id])),
                    {"participant_club_id": None},
                )


@pytest.mark.parametrize("action", ["preview", "confirm"])
@pytest.mark.asyncio(loop_scope="session")
async def test_existing_admin_role_requires_tournament_access(auth_context, action):
    async with context(auth_context) as ctx:
        p = await preview(auth_context, ctx, "EVENTS")
        body = {"target_source": "EVENTS"}
        if action == "confirm":
            body["conflict_token"] = p["conflict_token"]
        async with inserted_user(
            get_mock_user().model_copy(update={"account_type": UserAccountType.ADMIN})
        ) as user:
            headers = {"Authorization": f"Bearer {get_mock_token(user.email)}"}
            assert (
                await request(auth_context, ctx, "score-source/" + action, body, headers=headers)
            )[0] == 403
            async with inserted_user_x_club(
                UserXClubInsertable(
                    user_id=user.id,
                    club_id=auth_context.club.id,
                    relation=UserXClubRelation.COLLABORATOR,
                )
            ):
                assert (
                    await request(
                        auth_context, ctx, "score-source/" + action, body, headers=headers
                    )
                )[0] == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_archive_between_preview_and_confirmation_rejects_without_changes(auth_context):
    async with context(auth_context, with_events=True) as ctx:
        p = await preview(auth_context, ctx, "EVENTS")
        before = (await sql_get_match(ctx["match"].id)).model_dump()
        await database.execute(
            tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
            {"status": "ARCHIVED"},
        )
        assert (await confirm(auth_context, ctx, "EVENTS", p["conflict_token"]))[0] == 400
        assert (await sql_get_match(ctx["match"].id)).model_dump() == before
