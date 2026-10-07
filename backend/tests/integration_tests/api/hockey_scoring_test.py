from contextlib import AsyncExitStack
from decimal import Decimal

import aiohttp
import pytest
import pytest_asyncio

from bracket.database import database
from bracket.logic.ranking.calculation import recalculate_ranking_for_stage_item
from bracket.logic.scheduling.handle_stage_activation import get_team_rankings_lookup_for_tournament
from bracket.logic.tournaments import sql_delete_tournament_completely
from bracket.models.db.stage_item_inputs import StageItemInputInsertable
from bracket.models.db.tournament import (
    HockeyMode,
    HockeyScoring,
    TournamentCompetitionFormat,
    TournamentStatus,
    TournamentUpdateBody,
)
from bracket.routes import tournaments as tournament_routes
from bracket.schema import (
    competition_disciplines,
    competition_results,
    competition_scoring,
    competitions,
    stage_item_inputs,
    tournaments,
)
from bracket.sql.stage_items import get_stage_item
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.tournaments import sql_get_tournament, sql_get_tournament_by_endpoint_name
from bracket.utils.dummy_records import (
    DUMMY_MATCH1,
    DUMMY_MOCK_TIME,
    DUMMY_RANKING1,
    DUMMY_ROUND1,
    DUMMY_STAGE1,
    DUMMY_STAGE_ITEM1,
    DUMMY_TEAM1,
    DUMMY_TOURNAMENT,
)
from bracket.utils.http import HTTPMethod
from tests.integration_tests.api.shared import (
    SUCCESS_RESPONSE,
    get_root_uvicorn_url,
    send_auth_request,
    send_request,
)
from tests.integration_tests.sql import (
    inserted_match,
    inserted_ranking,
    inserted_round,
    inserted_stage,
    inserted_stage_item,
    inserted_stage_item_input,
    inserted_team,
    inserted_tournament,
)


def update_body(tournament):
    return {
        "name": tournament.name,
        "start_time": tournament.start_time.isoformat(),
        "dashboard_public": tournament.dashboard_public,
        "players_can_be_in_multiple_teams": tournament.players_can_be_in_multiple_teams,
        "auto_assign_courts": tournament.auto_assign_courts,
        "duration_minutes": tournament.duration_minutes,
        "margin_minutes": tournament.margin_minutes,
    }


@pytest_asyncio.fixture(loop_scope="session")
async def scoring_context(auth_context):
    async with inserted_tournament(
        DUMMY_TOURNAMENT.model_copy(
            update={
                "club_id": auth_context.club.id,
                "dashboard_endpoint": None,
            }
        )
    ) as tournament:
        yield auth_context.model_copy(update={"tournament": tournament})


@pytest.mark.asyncio(loop_scope="session")
async def test_scoring_create_read_update_and_omission(scoring_context):
    context = scoring_context
    defaults = HockeyScoring().model_dump()
    endpoint = f"tournaments/{context.tournament.id}"
    response = await send_auth_request(HTTPMethod.GET, endpoint, context)
    assert {key: Decimal(response["data"][key]) for key in defaults} == defaults
    custom = {
        "game_win_points": "3.25",
        "game_draw_points": "1.25",
        "game_loss_points": "0.25",
        "shootout_win_points": "2.5",
        "shootout_draw_points": "0.75",
        "shootout_loss_points": "0.50",
    }
    assert (
        await send_auth_request(
            HTTPMethod.PUT, endpoint, context, json=update_body(context.tournament) | custom
        )
        == SUCCESS_RESPONSE
    )
    assert (
        await send_auth_request(
            HTTPMethod.PUT,
            endpoint,
            context,
            json=update_body(context.tournament) | {"game_win_points": "4.25"},
        )
        == SUCCESS_RESPONSE
    )
    assert (
        await send_auth_request(
            HTTPMethod.PUT, endpoint, context, json=update_body(context.tournament)
        )
        == SUCCESS_RESPONSE
    )
    stored = await sql_get_tournament(context.tournament.id)
    expected = custom | {"game_win_points": "4.25"}
    assert {key: getattr(stored, key) for key in expected} == {
        key: Decimal(value) for key, value in expected.items()
    }
    public = await send_request(HTTPMethod.GET, endpoint)
    assert Decimal(public["data"]["game_win_points"]) == Decimal("4.25")

    for configured in (False, True):
        name = f"slice5a-create-{configured}"
        body = update_body(context.tournament) | {
            "club_id": context.club.id,
            "dashboard_endpoint": name,
        }
        if configured:
            body |= custom
        assert (
            await send_auth_request(HTTPMethod.POST, "tournaments", context, json=body)
            == SUCCESS_RESPONSE
        )
        created = await sql_get_tournament_by_endpoint_name(name)
        try:
            expected_values = (
                {key: Decimal(value) for key, value in custom.items()} if configured else defaults
            )
            assert {key: getattr(created, key) for key in defaults} == expected_values
        finally:
            await sql_delete_tournament_completely(created.id)


@pytest.mark.parametrize("method", [HTTPMethod.POST, HTTPMethod.PUT])
@pytest.mark.parametrize("value", [None, "-0.01", "0.001", "1000000", "NaN", "Infinity", "invalid"])
@pytest.mark.asyncio(loop_scope="session")
async def test_scoring_api_rejects_invalid_values(scoring_context, method, value):
    context = scoring_context
    body = update_body(context.tournament) | {"game_win_points": value}
    endpoint = f"tournaments/{context.tournament.id}"
    if method is HTTPMethod.POST:
        endpoint = "tournaments"
        body["club_id"] = context.club.id
    async with aiohttp.ClientSession() as session:
        async with session.request(
            method.value, get_root_uvicorn_url() + endpoint, headers=context.headers, json=body
        ) as response:
            assert response.status == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_scoring_api_boundary_permissions_and_archiving(scoring_context):
    context = scoring_context
    endpoint = f"tournaments/{context.tournament.id}"
    body = update_body(context.tournament) | {"game_win_points": "999999.99"}
    assert await send_auth_request(HTTPMethod.PUT, endpoint, context, json=body) == SUCCESS_RESPONSE
    assert (await sql_get_tournament(context.tournament.id)).game_win_points == Decimal("999999.99")
    response = await send_request(HTTPMethod.PUT, endpoint, json=body | {"game_win_points": "2"})
    assert "detail" in response
    assert (await sql_get_tournament(context.tournament.id)).game_win_points == Decimal("999999.99")
    await database.execute(
        tournaments.update()
        .where(tournaments.c.id == context.tournament.id)
        .values(status=TournamentStatus.ARCHIVED.value)
    )
    response = await send_auth_request(
        HTTPMethod.PUT, endpoint, context, json=body | {"game_win_points": "2"}
    )
    assert "detail" in response
    assert (await sql_get_tournament(context.tournament.id)).game_win_points == Decimal("999999.99")


@pytest.mark.parametrize("mode", [HockeyMode.COMPETITION, HockeyMode.GAME_SHOOTOUT])
@pytest.mark.parametrize("format_", list(TournamentCompetitionFormat))
@pytest.mark.asyncio(loop_scope="session")
async def test_rule_update_recalculates_all_groups_and_overall(
    scoring_context, mode, format_, monkeypatch
):
    context = scoring_context
    tid = context.tournament.id
    await database.execute(
        tournaments.update()
        .where(tournaments.c.id == tid)
        .values(hockey_mode=mode.value, competition_format=format_.value)
    )
    async with AsyncExitStack() as stack:
        team1 = await stack.enter_async_context(
            inserted_team(DUMMY_TEAM1.model_copy(update={"tournament_id": tid}))
        )
        team2 = await stack.enter_async_context(
            inserted_team(DUMMY_TEAM1.model_copy(update={"tournament_id": tid, "name": "Team 2"}))
        )
        stage = await stack.enter_async_context(
            inserted_stage(DUMMY_STAGE1.model_copy(update={"tournament_id": tid}))
        )
        group_ids = []
        for index in range(2):
            ranking = await stack.enter_async_context(
                inserted_ranking(
                    DUMMY_RANKING1.model_copy(
                        update={
                            "tournament_id": tid,
                            "win_points": Decimal(7 + index),
                            "position": index,
                        }
                    )
                )
            )
            group = await stack.enter_async_context(
                inserted_stage_item(
                    DUMMY_STAGE_ITEM1.model_copy(
                        update={"stage_id": stage.id, "ranking_id": ranking.id}
                    )
                )
            )
            group_ids.append(group.id)
            inputs = []
            for slot, team in enumerate((team1, team2), 1):
                inputs.append(
                    await stack.enter_async_context(
                        inserted_stage_item_input(
                            StageItemInputInsertable(
                                tournament_id=tid,
                                stage_item_id=group.id,
                                slot=slot,
                                team_id=team.id,
                            )
                        )
                    )
                )
            round_ = await stack.enter_async_context(
                inserted_round(DUMMY_ROUND1.model_copy(update={"stage_item_id": group.id}))
            )
            await stack.enter_async_context(
                inserted_match(
                    DUMMY_MATCH1.model_copy(
                        update={
                            "round_id": round_.id,
                            "court_id": None,
                            "stage_item_input1_id": inputs[0].id,
                            "stage_item_input2_id": inputs[1].id,
                            "stage_item_input1_score": 2,
                            "stage_item_input2_score": 0,
                            "stage_item_input1_half1_score": 1,
                            "stage_item_input2_half1_score": 0,
                            "stage_item_input1_half2_score": 1,
                            "stage_item_input2_half2_score": 0,
                            "stage_item_input1_penalty_score": 1,
                            "stage_item_input2_penalty_score": 0,
                        }
                    )
                )
            )
            await recalculate_ranking_for_stage_item(tid, await get_stage_item(tid, group.id))
        cid = await database.execute(
            competitions.insert().values(
                tournament_id=tid, name="Technique", start_time=DUMMY_MOCK_TIME
            )
        )
        try:
            did = await database.execute(
                competition_disciplines.insert().values(competition_id=cid, name="Manual")
            )
            await database.execute(
                competition_scoring.insert().values(
                    competition_id=cid, place=1, points=Decimal("2.50")
                )
            )
            await database.execute(
                competition_results.insert().values(discipline_id=did, team_id=team1.id, place=1)
            )
            endpoint = f"tournaments/{tid}"

            async def overall():
                response = await send_auth_request(
                    HTTPMethod.GET, endpoint + "/overall_standings", context
                )
                return {row["team_id"]: row for row in response["data"]}

            before = await overall()
            assert Decimal(before[team1.id]["game_points"]) == Decimal(
                "10" if mode is HockeyMode.COMPETITION else "6"
            )
            body = update_body(context.tournament) | {
                "game_win_points": "3",
                "shootout_win_points": "2",
                "game_loss_points": "0.35",
                "shootout_loss_points": "0.50",
            }
            assert (
                await send_auth_request(HTTPMethod.PUT, endpoint, context, json=body)
                == SUCCESS_RESPONSE
            )
            after = await overall()
            assert Decimal(after[team1.id]["game_points"]) == Decimal(
                "16" if mode is HockeyMode.COMPETITION else "10"
            )
            assert Decimal(after[team2.id]["game_points"]) == Decimal(
                "2.4" if mode is HockeyMode.COMPETITION else "1.7"
            )
            assert (
                Decimal(after[team1.id]["competition_points"])
                == Decimal(before[team1.id]["competition_points"])
                == Decimal("2.50")
            )
            assert Decimal(after[team1.id]["total_points"]) == Decimal(
                after[team1.id]["game_points"]
            ) + Decimal("2.50")

            lookup = await get_team_rankings_lookup_for_tournament(
                tid, await get_full_tournament_details(tid)
            )
            for group_id in group_ids:
                assert [stats.points for _, stats in lookup[group_id]] == [
                    Decimal("8" if mode is HockeyMode.COMPETITION else "5"),
                    Decimal("1.2" if mode is HockeyMode.COMPETITION else "0.85"),
                ]

            original = tournament_routes.recalculate_ranking_for_stage_item
            calls = []

            async def fail_after_first(tournament_id, stage_item):
                calls.append(stage_item.id)
                if len(calls) == 2:
                    raise RuntimeError("Injected recalculation failure")
                await original(tournament_id, stage_item)

            monkeypatch.setattr(
                tournament_routes, "recalculate_ranking_for_stage_item", fail_after_first
            )
            current = await sql_get_tournament(tid)
            with pytest.raises(RuntimeError, match="Injected"):
                await tournament_routes.update_tournament_by_id(
                    tid,
                    TournamentUpdateBody.model_validate(body | {"game_win_points": "4"}),
                    context.user,
                    current,
                )
            assert len(calls) == 2
            assert (await sql_get_tournament(tid)).game_win_points == Decimal("3")
            assert await overall() == after
            # Identical and omitted rules must not call recalculation.
            calls.clear()
            assert (
                await send_auth_request(HTTPMethod.PUT, endpoint, context, json=body)
                == SUCCESS_RESPONSE
            )
            assert (
                await send_auth_request(
                    HTTPMethod.PUT, endpoint, context, json=update_body(context.tournament)
                )
                == SUCCESS_RESPONSE
            )
            assert calls == []
            rows = await database.fetch_all(
                stage_item_inputs.select().where(stage_item_inputs.c.tournament_id == tid)
            )
            assert len(rows) == 4
            assert sorted(Decimal(str(row["points"])) for row in rows) == sorted(
                [
                    Decimal("8" if mode is HockeyMode.COMPETITION else "5"),
                    Decimal("1.2" if mode is HockeyMode.COMPETITION else "0.85"),
                ]
                * 2
            )
        finally:
            await database.execute(competitions.delete().where(competitions.c.id == cid))
