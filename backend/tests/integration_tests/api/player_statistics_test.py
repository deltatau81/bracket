from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Any

import pytest
import pytest_asyncio

from bracket.database import database
from bracket.models.db.match import MatchPeriod, MatchStatus
from bracket.models.db.player_x_team import PlayerXTeamInsertable
from bracket.models.db.stage_item_inputs import StageItemInputInsertable
from bracket.schema import match_events, players_x_teams
from bracket.utils.dummy_records import (
    DUMMY_MATCH1,
    DUMMY_PLAYER1,
    DUMMY_PLAYER2,
    DUMMY_PLAYER3,
    DUMMY_PLAYER4,
    DUMMY_RANKING1,
    DUMMY_ROUND1,
    DUMMY_STAGE1,
    DUMMY_STAGE_ITEM1,
    DUMMY_TEAM1,
    DUMMY_TEAM2,
    DUMMY_TEAM3,
    DUMMY_TOURNAMENT,
)
from bracket.utils.http import HTTPMethod
from tests.integration_tests.api.shared import send_request
from tests.integration_tests.models import AuthContext
from tests.integration_tests.sql import (
    inserted_generic,
    inserted_match,
    inserted_player,
    inserted_ranking,
    inserted_round,
    inserted_stage,
    inserted_stage_item,
    inserted_stage_item_input,
    inserted_team,
    inserted_tournament,
)


async def insert_event(match_id: int, team_id: int, **values: object) -> None:
    await database.execute(
        match_events.insert(),
        values={
            "match_id": match_id,
            "team_id": team_id,
            "game_time_seconds": 10,
            "sort_order": 0,
            **values,
        },
    )


@pytest_asyncio.fixture(loop_scope="session", scope="module")
async def statistics_context(auth_context: AuthContext) -> AsyncIterator[dict[str, Any]]:
    tournament_id = auth_context.tournament.id
    async with AsyncExitStack() as stack:
        stage = await stack.enter_async_context(
            inserted_stage(DUMMY_STAGE1.model_copy(update={"tournament_id": tournament_id}))
        )
        stage_item = await stack.enter_async_context(
            inserted_stage_item(
                DUMMY_STAGE_ITEM1.model_copy(
                    update={"stage_id": stage.id, "ranking_id": auth_context.ranking.id}
                )
            )
        )
        round_ = await stack.enter_async_context(
            inserted_round(DUMMY_ROUND1.model_copy(update={"stage_item_id": stage_item.id}))
        )
        team1 = await stack.enter_async_context(
            inserted_team(DUMMY_TEAM1.model_copy(update={"tournament_id": tournament_id}))
        )
        team2 = await stack.enter_async_context(
            inserted_team(DUMMY_TEAM2.model_copy(update={"tournament_id": tournament_id}))
        )

        player_models = [
            DUMMY_PLAYER1.model_copy(update={"name": "Alpha", "tournament_id": tournament_id}),
            DUMMY_PLAYER2.model_copy(update={"name": "Beta", "tournament_id": tournament_id}),
            DUMMY_PLAYER3.model_copy(update={"name": "Charlie", "tournament_id": tournament_id}),
            DUMMY_PLAYER4.model_copy(update={"name": "Zero", "tournament_id": tournament_id}),
        ]
        roster = []
        for index, player_model in enumerate(player_models):
            player = await stack.enter_async_context(inserted_player(player_model))
            await stack.enter_async_context(
                inserted_generic(
                    PlayerXTeamInsertable(
                        player_id=player.id,
                        team_id=team1.id,
                        number=index + 10,
                        position="F",
                    ),
                    players_x_teams,
                    PlayerXTeamInsertable,
                )
            )
            roster.append(player)

        input1 = await stack.enter_async_context(
            inserted_stage_item_input(
                StageItemInputInsertable(
                    slot=0,
                    team_id=team1.id,
                    tournament_id=tournament_id,
                    stage_item_id=stage_item.id,
                )
            )
        )
        input2 = await stack.enter_async_context(
            inserted_stage_item_input(
                StageItemInputInsertable(
                    slot=1,
                    team_id=team2.id,
                    tournament_id=tournament_id,
                    stage_item_id=stage_item.id,
                )
            )
        )
        match_values = {
            "round_id": round_.id,
            "stage_item_input1_id": input1.id,
            "stage_item_input2_id": input2.id,
            "court_id": None,
        }
        finished_match = await stack.enter_async_context(
            inserted_match(
                DUMMY_MATCH1.model_copy(update=match_values | {"status": MatchStatus.FINISHED})
            )
        )
        running_match = await stack.enter_async_context(
            inserted_match(
                DUMMY_MATCH1.model_copy(update=match_values | {"status": MatchStatus.RUNNING})
            )
        )

        alpha, beta, charlie, _ = roster
        await insert_event(
            finished_match.id,
            team1.id,
            event_type="GOAL",
            period="HALF1",
            player_id=alpha.id,
            assist1_player_id=beta.id,
            assist2_player_id=charlie.id,
        )
        await insert_event(
            finished_match.id,
            team1.id,
            event_type="GOAL",
            period="HALF2",
            player_id=beta.id,
            assist1_player_id=alpha.id,
        )
        await insert_event(
            finished_match.id,
            team1.id,
            event_type="GOAL",
            period="SHOOTOUT",
            player_id=beta.id,
            assist1_player_id=alpha.id,
            assist2_player_id=charlie.id,
        )
        await insert_event(
            running_match.id,
            team1.id,
            event_type="GOAL",
            period="HALF1",
            player_id=charlie.id,
        )
        await insert_event(
            finished_match.id,
            team1.id,
            event_type="GOAL",
            period="HALF1",
            player_id=None,
            player_number=99,
        )
        for minutes in (2, 4, None):
            await insert_event(
                finished_match.id,
                team1.id,
                event_type="PENALTY",
                period="HALF1",
                player_id=alpha.id,
                penalty_minutes=minutes,
            )

        other_tournament = await stack.enter_async_context(
            inserted_tournament(
                DUMMY_TOURNAMENT.model_copy(
                    update={
                        "club_id": auth_context.club.id,
                        "dashboard_endpoint": "player-statistics-other",
                    }
                )
            )
        )
        other_player = await stack.enter_async_context(
            inserted_player(
                DUMMY_PLAYER1.model_copy(
                    update={"name": "Other Tournament", "tournament_id": other_tournament.id}
                )
            )
        )
        other_ranking = await stack.enter_async_context(
            inserted_ranking(DUMMY_RANKING1.model_copy(update={"tournament_id": other_tournament.id}))
        )
        other_stage = await stack.enter_async_context(
            inserted_stage(DUMMY_STAGE1.model_copy(update={"tournament_id": other_tournament.id}))
        )
        other_stage_item = await stack.enter_async_context(
            inserted_stage_item(
                DUMMY_STAGE_ITEM1.model_copy(
                    update={"stage_id": other_stage.id, "ranking_id": other_ranking.id}
                )
            )
        )
        other_round = await stack.enter_async_context(
            inserted_round(
                DUMMY_ROUND1.model_copy(update={"stage_item_id": other_stage_item.id})
            )
        )
        other_team1 = await stack.enter_async_context(
            inserted_team(
                DUMMY_TEAM1.model_copy(update={"tournament_id": other_tournament.id})
            )
        )
        other_team2 = await stack.enter_async_context(
            inserted_team(
                DUMMY_TEAM3.model_copy(update={"tournament_id": other_tournament.id})
            )
        )
        other_input1 = await stack.enter_async_context(
            inserted_stage_item_input(
                StageItemInputInsertable(
                    slot=0,
                    team_id=other_team1.id,
                    tournament_id=other_tournament.id,
                    stage_item_id=other_stage_item.id,
                )
            )
        )
        other_input2 = await stack.enter_async_context(
            inserted_stage_item_input(
                StageItemInputInsertable(
                    slot=1,
                    team_id=other_team2.id,
                    tournament_id=other_tournament.id,
                    stage_item_id=other_stage_item.id,
                )
            )
        )
        other_match = await stack.enter_async_context(
            inserted_match(
                DUMMY_MATCH1.model_copy(
                    update={
                        "round_id": other_round.id,
                        "stage_item_input1_id": other_input1.id,
                        "stage_item_input2_id": other_input2.id,
                        "court_id": None,
                        "status": MatchStatus.FINISHED,
                    }
                )
            )
        )
        await insert_event(
            other_match.id,
            other_team1.id,
            event_type="GOAL",
            period="HALF1",
            player_id=other_player.id,
        )

        yield {
            "tournament_id": tournament_id,
            "team": team1,
            "players": roster,
            "other_player": other_player,
        }


@pytest.mark.asyncio(loop_scope="session")
async def test_player_statistics_aggregation_and_ordering(
    startup_and_shutdown_uvicorn_server: None,
    statistics_context: dict[str, Any],
) -> None:
    response = await send_request(
        HTTPMethod.GET,
        f"tournaments/{statistics_context['tournament_id']}/player_statistics",
    )
    rows = response["data"]

    assert [row["player_name"] for row in rows] == ["Alpha", "Beta", "Charlie", "Zero"]
    assert [row["player_id"] for row in rows] == [
        player.id for player in statistics_context["players"]
    ]
    assert rows[0] == {
        "player_id": statistics_context["players"][0].id,
        "player_name": "Alpha",
        "team_id": statistics_context["team"].id,
        "team_name": statistics_context["team"].name,
        "jersey_number": 10,
        "position": "F",
        "goals": 1,
        "assists": 1,
        "points": 2,
        "penalty_minutes": 6,
    }
    assert (rows[1]["goals"], rows[1]["assists"], rows[1]["points"]) == (1, 1, 2)
    assert (rows[2]["goals"], rows[2]["assists"], rows[2]["points"]) == (0, 1, 1)
    assert (rows[3]["goals"], rows[3]["assists"], rows[3]["points"]) == (0, 0, 0)
    assert all(row["player_id"] != statistics_context["other_player"].id for row in rows)
