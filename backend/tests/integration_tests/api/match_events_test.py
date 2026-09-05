from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest

from bracket.database import database
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
from tests.integration_tests.api.shared import SUCCESS_RESPONSE, send_tournament_request
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
async def event_match_context(auth_context: AuthContext) -> AsyncIterator[dict[str, Any]]:
    tournament_id = auth_context.tournament.id
    async with (
        inserted_stage(DUMMY_STAGE1.model_copy(update={"tournament_id": tournament_id})) as stage,
        inserted_stage_item(
            DUMMY_STAGE_ITEM1.model_copy(
                update={"stage_id": stage.id, "ranking_id": auth_context.ranking.id}
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


@pytest.mark.asyncio(loop_scope="session")
async def test_match_event_workflow(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with event_match_context(auth_context) as context:
        match_before = await sql_get_match(context["match"].id)
        goal_body = {
            "team_id": context["team1"].id,
            "event_type": "GOAL",
            "period": "HALF1",
            "game_time_seconds": 462,
            "player_id": context["player1"].id,
            "player_name": "forged",
            "player_number": 999,
        }
        goal = (await event_request(HTTPMethod.POST, context, auth_context, body=goal_body))["data"]
        assert goal["player_name"] == context["player1"].name
        assert goal["player_number"] == 21

        manual_body = {
            "team_id": context["team2"].id,
            "event_type": "GOAL",
            "period": "HALF2",
            "game_time_seconds": 20,
            "player_number": 8,
            "player_name": "Manual Player",
        }
        manual = (
            await event_request(HTTPMethod.POST, context, auth_context, body=manual_body)
        )["data"]
        assert manual["player_id"] is None
        assert manual["player_name"] == "Manual Player"

        assisted_body = goal_body | {
            "game_time_seconds": 100,
            "assist1_player_id": context["player2"].id,
            "assist2_player_id": context["player4"].id,
        }
        assisted = (
            await event_request(HTTPMethod.POST, context, auth_context, body=assisted_body)
        )["data"]
        assert assisted["assist1_name"] == context["player2"].name
        assert assisted["assist2_name"] == context["player4"].name

        foreign_player = goal_body | {"player_id": context["player3"].id}
        response = await event_request(HTTPMethod.POST, context, auth_context, body=foreign_player)
        assert "does not belong" in response["detail"]

        foreign_team = goal_body | {"team_id": context["team3"].id}
        response = await event_request(HTTPMethod.POST, context, auth_context, body=foreign_team)
        assert "not a resolved participant" in response["detail"]

        for invalid_period in ("PERIOD1", "OVERTIME"):
            response = await event_request(
                HTTPMethod.POST,
                context,
                auth_context,
                body=goal_body | {"period": invalid_period},
            )
            assert "not allowed for COMPETITION" in response["detail"]

        duplicate_player = goal_body | {"assist1_player_id": context["player1"].id}
        response = await event_request(
            HTTPMethod.POST, context, auth_context, body=duplicate_player
        )
        assert "multiple roles" in str(response["detail"])

        duplicate_assists = goal_body | {
            "assist1_player_id": context["player2"].id,
            "assist2_player_id": context["player2"].id,
        }
        response = await event_request(
            HTTPMethod.POST, context, auth_context, body=duplicate_assists
        )
        assert "multiple roles" in str(response["detail"])

        penalty_body = {
            "team_id": context["team2"].id,
            "event_type": "PENALTY",
            "period": "HALF1",
            "game_time_seconds": 50,
            "penalty_type": "Team penalty",
            "penalty_minutes": 2,
            "infraction": "Too many players",
        }
        penalty = (
            await event_request(HTTPMethod.POST, context, auth_context, body=penalty_body)
        )["data"]
        assert penalty["player_id"] is None

        penalty_with_assist = penalty_body | {"assist1_name": "Not allowed"}
        response = await event_request(
            HTTPMethod.POST, context, auth_context, body=penalty_with_assist
        )
        assert "cannot contain assist" in str(response["detail"])

        response = await event_request(
            HTTPMethod.PUT,
            context,
            auth_context,
            suffix=f"/{manual['id']}",
            body=manual_body | {"team_id": context["team3"].id},
        )
        assert "not a resolved participant" in response["detail"]
        events = (await event_request(HTTPMethod.GET, context, auth_context))["data"]
        stored_manual = next(event for event in events if event["id"] == manual["id"])
        assert stored_manual == manual

        updated = (
            await event_request(
                HTTPMethod.PUT,
                context,
                auth_context,
                suffix=f"/{manual['id']}",
                body=manual_body | {"game_time_seconds": 30, "sort_order": 2},
            )
        )["data"]
        assert updated["game_time_seconds"] == 30
        assert updated["sort_order"] == 2

        events = (await event_request(HTTPMethod.GET, context, auth_context))["data"]
        assert [event["period"] for event in events] == ["HALF1", "HALF1", "HALF1", "HALF2"]
        assert [event["game_time_seconds"] for event in events[:3]] == [50, 100, 462]

        assert (
            await event_request(
                HTTPMethod.DELETE, context, auth_context, suffix=f"/{goal['id']}"
            )
            == SUCCESS_RESPONSE
        )
        assert all(
            event["id"] != goal["id"]
            for event in (await event_request(HTTPMethod.GET, context, auth_context))["data"]
        )

        match_after = await sql_get_match(context["match"].id)
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
            getattr(match_after, field) == getattr(match_before, field) for field in score_fields
        )

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
        async with event_match_context(auth_context) as context:
            base_body = {
                "team_id": context["team1"].id,
                "event_type": "GOAL",
                "game_time_seconds": 10,
                "player_id": context["player1"].id,
            }
            for period in ("PERIOD1", "PERIOD2", "PERIOD3", "OVERTIME"):
                response = await event_request(
                    HTTPMethod.POST,
                    context,
                    auth_context,
                    body=base_body | {"period": period},
                )
                assert response["data"]["period"] == period

            for period in ("HALF1", "HALF2"):
                response = await event_request(
                    HTTPMethod.POST,
                    context,
                    auth_context,
                    body=base_body | {"period": period},
                )
                assert "not allowed for STANDARD" in response["detail"]
    finally:
        await database.execute(
            query=tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
            values={"hockey_mode": "COMPETITION"},
        )
