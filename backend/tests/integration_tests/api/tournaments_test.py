from contextlib import AsyncExitStack

import aiofiles
import aiofiles.os
import aiohttp
import pytest

from bracket.database import database
from bracket.logic.tournaments import sql_delete_tournament_completely
from bracket.models.db.tournament import (
    HockeyAgeCategory,
    HockeyMode,
    HockeyRuleset,
    Tournament,
    TournamentCompetitionFormat,
    TournamentStatus,
)
from bracket.models.db.stage_item_inputs import StageItemInputInsertable
from bracket.schema import (
    competition_disciplines,
    competition_pairings,
    competition_results,
    competition_scoring,
    competitions,
    courts,
    match_events,
    matches,
    players,
    players_x_teams,
    rankings,
    rounds,
    stage_item_inputs,
    stage_items,
    stages,
    teams,
    tournaments,
)
from bracket.sql.tournaments import sql_delete_tournament, sql_get_tournament_by_endpoint_name
from bracket.utils.db import fetch_one_parsed_certain
from bracket.utils.dummy_records import (
    DUMMY_MATCH1,
    DUMMY_MOCK_TIME,
    DUMMY_COURT1,
    DUMMY_PLAYER1,
    DUMMY_RANKING1,
    DUMMY_ROUND1,
    DUMMY_STAGE1,
    DUMMY_STAGE_ITEM1,
    DUMMY_TEAM1,
    DUMMY_TOURNAMENT,
)
from bracket.utils.http import HTTPMethod
from bracket.utils.types import assert_some
from tests.integration_tests.api.shared import (
    SUCCESS_RESPONSE,
    send_auth_request,
    send_request,
    send_tournament_request,
)
from tests.integration_tests.models import AuthContext
from tests.integration_tests.sql import (
    inserted_court,
    inserted_match,
    inserted_player_in_team,
    inserted_ranking,
    inserted_round,
    inserted_stage,
    inserted_stage_item,
    inserted_stage_item_input,
    inserted_team,
    inserted_tournament,
)


@pytest.mark.asyncio(loop_scope="session")
async def test_tournaments_endpoint(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    assert await send_auth_request(HTTPMethod.GET, "tournaments", auth_context, {}) == {
        "data": [
            {
                "id": auth_context.tournament.id,
                "club_id": auth_context.club.id,
                "created": DUMMY_MOCK_TIME.isoformat().replace("+00:00", "Z"),
                "start_time": DUMMY_MOCK_TIME.isoformat().replace("+00:00", "Z"),
                "name": "Some Cool Tournament",
                "logo_path": None,
                "dashboard_public": True,
                "dashboard_endpoint": "endpoint-test",
                "players_can_be_in_multiple_teams": True,
                "auto_assign_courts": True,
                "duration_minutes": 10,
                "margin_minutes": 5,
                "status": "OPEN",
                "hockey_mode": "COMPETITION",
                "competition_format": "STANDARD",
                "ruleset": "DEB",
                "age_category": "U15",
                "ruleset_season": "2026/27",
                "game_win_points": "2.00",
                "game_draw_points": "1.00",
                "game_loss_points": "0.00",
                "shootout_win_points": "1.00",
                "shootout_draw_points": "0.50",
                "shootout_loss_points": "0.00",
            }
        ],
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_tournament_endpoint(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    assert await send_auth_request(
        HTTPMethod.GET, f"tournaments/{auth_context.tournament.id}", auth_context, {}
    ) == {
        "data": {
            "id": auth_context.tournament.id,
            "club_id": auth_context.club.id,
            "created": DUMMY_MOCK_TIME.isoformat().replace("+00:00", "Z"),
            "start_time": DUMMY_MOCK_TIME.isoformat().replace("+00:00", "Z"),
            "logo_path": None,
            "name": "Some Cool Tournament",
            "dashboard_public": True,
            "dashboard_endpoint": "endpoint-test",
            "players_can_be_in_multiple_teams": True,
            "auto_assign_courts": True,
            "duration_minutes": 10,
            "margin_minutes": 5,
            "status": "OPEN",
            "hockey_mode": "COMPETITION",
            "competition_format": "STANDARD",
            "ruleset": "DEB",
            "age_category": "U15",
            "ruleset_season": "2026/27",
            "game_win_points": "2.00",
            "game_draw_points": "1.00",
            "game_loss_points": "0.00",
            "shootout_win_points": "1.00",
            "shootout_draw_points": "0.50",
            "shootout_loss_points": "0.00",
        },
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_create_tournament(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    dashboard_endpoint = "some-new-endpoint"
    body = {
        "name": "Some new name",
        "start_time": DUMMY_MOCK_TIME.isoformat().replace("+00:00", "Z"),
        "club_id": auth_context.club.id,
        "dashboard_public": True,
        "dashboard_endpoint": dashboard_endpoint,
        "players_can_be_in_multiple_teams": True,
        "auto_assign_courts": True,
        "duration_minutes": 12,
        "margin_minutes": 3,
    }
    assert (
        await send_auth_request(HTTPMethod.POST, "tournaments", auth_context, json=body)
        == SUCCESS_RESPONSE
    )

    # Cleanup
    tournament = assert_some(await sql_get_tournament_by_endpoint_name(dashboard_endpoint))
    assert tournament.hockey_mode is HockeyMode.COMPETITION
    assert tournament.competition_format is TournamentCompetitionFormat.STANDARD
    assert tournament.ruleset is HockeyRuleset.DEB
    assert tournament.age_category is HockeyAgeCategory.U15
    assert tournament.ruleset_season == "2026/27"
    await sql_delete_tournament_completely(tournament.id)


@pytest.mark.asyncio(loop_scope="session")
async def test_create_standard_tournament(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    dashboard_endpoint = "standard-hockey-test"
    body = {
        "name": "Standard Hockey",
        "start_time": DUMMY_MOCK_TIME.isoformat().replace("+00:00", "Z"),
        "club_id": auth_context.club.id,
        "dashboard_public": True,
        "dashboard_endpoint": dashboard_endpoint,
        "players_can_be_in_multiple_teams": True,
        "auto_assign_courts": True,
        "duration_minutes": 12,
        "margin_minutes": 3,
        "hockey_mode": "STANDARD",
        "competition_format": "YOUTH_CLUB",
        "ruleset": "IIHF",
        "age_category": "SENIOR",
        "ruleset_season": "2026/27",
    }
    assert (
        await send_auth_request(HTTPMethod.POST, "tournaments", auth_context, json=body)
        == SUCCESS_RESPONSE
    )

    tournament = assert_some(await sql_get_tournament_by_endpoint_name(dashboard_endpoint))
    assert tournament.hockey_mode is HockeyMode.STANDARD
    assert tournament.competition_format is TournamentCompetitionFormat.YOUTH_CLUB
    assert tournament.ruleset is HockeyRuleset.IIHF
    assert tournament.age_category is HockeyAgeCategory.SENIOR
    response = await send_auth_request(
        HTTPMethod.GET, f"tournaments/{tournament.id}", auth_context, {}
    )
    assert response["data"]["hockey_mode"] == "STANDARD"
    assert response["data"]["competition_format"] == "YOUTH_CLUB"
    assert response["data"]["ruleset"] == "IIHF"
    assert response["data"]["age_category"] == "SENIOR"
    assert response["data"]["ruleset_season"] == "2026/27"
    await sql_delete_tournament_completely(tournament.id)


@pytest.mark.parametrize("ruleset_season", ["2026/27", "2029/30", "2099/00"])
@pytest.mark.asyncio(loop_scope="session")
async def test_create_tournament_with_valid_ruleset_season(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
    ruleset_season: str,
) -> None:
    dashboard_endpoint = f"rules-season-{ruleset_season.replace('/', '-')}"
    body = {
        "name": "Configured Hockey",
        "start_time": DUMMY_MOCK_TIME.isoformat().replace("+00:00", "Z"),
        "club_id": auth_context.club.id,
        "dashboard_public": True,
        "dashboard_endpoint": dashboard_endpoint,
        "players_can_be_in_multiple_teams": True,
        "auto_assign_courts": True,
        "duration_minutes": 12,
        "margin_minutes": 3,
        "ruleset": "DEB",
        "age_category": "U15",
        "ruleset_season": ruleset_season,
    }
    assert (
        await send_auth_request(HTTPMethod.POST, "tournaments", auth_context, json=body)
        == SUCCESS_RESPONSE
    )
    tournament = assert_some(await sql_get_tournament_by_endpoint_name(dashboard_endpoint))
    assert tournament.ruleset_season == ruleset_season
    await sql_delete_tournament_completely(tournament.id)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ruleset", "UNKNOWN"),
        ("age_category", "U99"),
        ("ruleset_season", "2026/99"),
        ("ruleset_season", "26/27"),
        ("ruleset_season", "2026-27"),
    ],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_create_tournament_rejects_invalid_rules_configuration(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
    field: str,
    value: str,
) -> None:
    body = {
        "name": "Invalid Hockey",
        "start_time": DUMMY_MOCK_TIME.isoformat().replace("+00:00", "Z"),
        "club_id": auth_context.club.id,
        "dashboard_public": True,
        "players_can_be_in_multiple_teams": True,
        "auto_assign_courts": True,
        "duration_minutes": 12,
        "margin_minutes": 3,
        field: value,
    }
    response = await send_auth_request(HTTPMethod.POST, "tournaments", auth_context, json=body)
    assert "detail" in response


@pytest.mark.asyncio(loop_scope="session")
async def test_create_tournament_duplicate_dashboard_endpoint(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    body = {
        "name": "Some new name",
        "start_time": DUMMY_MOCK_TIME.isoformat().replace("+00:00", "Z"),
        "club_id": auth_context.club.id,
        "dashboard_public": True,
        "dashboard_endpoint": "endpoint-test",
        "players_can_be_in_multiple_teams": True,
        "auto_assign_courts": True,
        "duration_minutes": 12,
        "margin_minutes": 3,
    }
    assert await send_auth_request(HTTPMethod.POST, "tournaments", auth_context, json=body) == {
        "detail": "This dashboard link is already taken"
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_update_tournament(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    body = {
        "name": "Some new name",
        "start_time": DUMMY_MOCK_TIME.isoformat().replace("+00:00", "Z"),
        "dashboard_public": False,
        "players_can_be_in_multiple_teams": True,
        "auto_assign_courts": True,
        "duration_minutes": 12,
        "margin_minutes": 3,
        "competition_format": "YOUTH_CLUB",
    }
    assert (
        await send_tournament_request(HTTPMethod.PUT, "", auth_context, json=body)
        == SUCCESS_RESPONSE
    )
    updated_tournament = await fetch_one_parsed_certain(
        database,
        Tournament,
        query=tournaments.select().where(tournaments.c.id == auth_context.tournament.id),
    )
    assert updated_tournament.name == body["name"]
    assert updated_tournament.dashboard_public == body["dashboard_public"]
    assert updated_tournament.competition_format is TournamentCompetitionFormat.YOUTH_CLUB


@pytest.mark.asyncio(loop_scope="session")
async def test_hockey_mode_cannot_be_changed_after_creation(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    update_body = {
        "name": "Updated standard tournament",
        "start_time": DUMMY_MOCK_TIME.isoformat().replace("+00:00", "Z"),
        "dashboard_public": False,
        "players_can_be_in_multiple_teams": True,
        "auto_assign_courts": True,
        "duration_minutes": 12,
        "margin_minutes": 3,
    }
    async with inserted_tournament(
        DUMMY_TOURNAMENT.model_copy(
            update={
                "club_id": auth_context.club.id,
                "dashboard_endpoint": None,
                "hockey_mode": HockeyMode.STANDARD,
                "ruleset": HockeyRuleset.IIHF,
                "age_category": HockeyAgeCategory.SENIOR,
                "ruleset_season": "2029/30",
            }
        )
    ) as standard_tournament:
        standard_context = auth_context.model_copy(update={"tournament": standard_tournament})

        assert (
            await send_tournament_request(
                HTTPMethod.PUT, "", standard_context, json=update_body
            )
            == SUCCESS_RESPONSE
        )
        stored = await fetch_one_parsed_certain(
            database,
            Tournament,
            tournaments.select().where(tournaments.c.id == standard_tournament.id),
        )
        assert stored.hockey_mode is HockeyMode.STANDARD
        assert stored.ruleset is HockeyRuleset.IIHF
        assert stored.age_category is HockeyAgeCategory.SENIOR
        assert stored.ruleset_season == "2029/30"

        assert (
            await send_tournament_request(
                HTTPMethod.PUT,
                "",
                standard_context,
                json=update_body | {"hockey_mode": "STANDARD"},
            )
            == SUCCESS_RESPONSE
        )

        assert (
            await send_tournament_request(
                HTTPMethod.PUT,
                "",
                standard_context,
                json=update_body
                | {
                    "ruleset": "IIHF",
                    "age_category": "SENIOR",
                    "ruleset_season": "2029/30",
                },
            )
            == SUCCESS_RESPONSE
        )

        response = await send_tournament_request(
            HTTPMethod.PUT,
            "",
            standard_context,
            json=update_body | {"hockey_mode": "COMPETITION"},
        )
        assert "cannot be changed" in response["detail"]
        stored = await fetch_one_parsed_certain(
            database,
            Tournament,
            tournaments.select().where(tournaments.c.id == standard_tournament.id),
        )
        assert stored.hockey_mode is HockeyMode.STANDARD

    response = await send_tournament_request(
        HTTPMethod.PUT,
        "",
        auth_context,
        json=update_body | {"hockey_mode": "STANDARD"},
    )
    assert "cannot be changed" in response["detail"]
    stored = await fetch_one_parsed_certain(
        database,
        Tournament,
        tournaments.select().where(tournaments.c.id == auth_context.tournament.id),
    )
    assert stored.hockey_mode is HockeyMode.COMPETITION


@pytest.mark.parametrize(
    ("field", "changed_value"),
    [
        ("ruleset", "IIHF"),
        ("age_category", "SENIOR"),
        ("ruleset_season", "2029/30"),
    ],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_rules_configuration_cannot_be_changed_after_creation(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
    field: str,
    changed_value: str,
) -> None:
    async with inserted_tournament(
        DUMMY_TOURNAMENT.model_copy(
            update={"club_id": auth_context.club.id, "dashboard_endpoint": None}
        )
    ) as tournament:
        tournament_context = auth_context.model_copy(update={"tournament": tournament})
        body = {
            "name": "This name must not be stored",
            "start_time": DUMMY_MOCK_TIME.isoformat().replace("+00:00", "Z"),
            "dashboard_public": False,
            "players_can_be_in_multiple_teams": True,
            "auto_assign_courts": True,
            "duration_minutes": 12,
            "margin_minutes": 3,
            field: changed_value,
        }
        response = await send_tournament_request(
            HTTPMethod.PUT, "", tournament_context, json=body
        )
        assert "cannot be changed" in response["detail"]
        stored = await fetch_one_parsed_certain(
            database,
            Tournament,
            tournaments.select().where(tournaments.c.id == tournament.id),
        )
        assert stored.name == tournament.name
        assert stored.ruleset is HockeyRuleset.DEB
        assert stored.age_category is HockeyAgeCategory.U15
        assert stored.ruleset_season == "2026/27"


@pytest.mark.asyncio(loop_scope="session")
async def test_archive_and_unarchive_tournament(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    query = tournaments.select().where(tournaments.c.id == auth_context.tournament.id)
    body = {"status": "ARCHIVED"}
    assert (
        await send_tournament_request(HTTPMethod.POST, "change-status", auth_context, json=body)
        == SUCCESS_RESPONSE
    )
    updated_tournament = await fetch_one_parsed_certain(database, Tournament, query)
    assert updated_tournament.status is TournamentStatus.ARCHIVED
    assert updated_tournament.dashboard_public is False

    # Archiving twice is not allowed
    assert await send_tournament_request(
        HTTPMethod.POST, "change-status", auth_context, json=body
    ) == {"detail": "Tournament already has the requested status"}

    # Unarchive the tournament
    body = {"status": "OPEN"}
    assert (
        await send_tournament_request(HTTPMethod.POST, "change-status", auth_context, json=body)
        == SUCCESS_RESPONSE
    )
    updated_tournament = await fetch_one_parsed_certain(database, Tournament, query)
    assert updated_tournament.status is TournamentStatus.OPEN
    assert updated_tournament.dashboard_public is False


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_tournament(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with inserted_tournament(
        DUMMY_TOURNAMENT.model_copy(
            update={"club_id": auth_context.club.id, "dashboard_endpoint": None}
        )
    ) as tournament_inserted:
        assert (
            await send_tournament_request(
                HTTPMethod.DELETE,
                "",
                auth_context.model_copy(update={"tournament": tournament_inserted}),
            )
            == SUCCESS_RESPONSE
        )

    await sql_delete_tournament(tournament_inserted.id)


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_api_created_tournament_with_automatic_ranking(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    endpoint = "delete-fresh-tournament"
    body = {
        "name": "Delete fresh tournament",
        "start_time": DUMMY_MOCK_TIME.isoformat().replace("+00:00", "Z"),
        "club_id": auth_context.club.id,
        "dashboard_public": True,
        "dashboard_endpoint": endpoint,
        "players_can_be_in_multiple_teams": True,
        "auto_assign_courts": True,
        "duration_minutes": 10,
        "margin_minutes": 5,
    }
    assert (
        await send_auth_request(HTTPMethod.POST, "tournaments", auth_context, json=body)
        == SUCCESS_RESPONSE
    )
    tournament = assert_some(await sql_get_tournament_by_endpoint_name(endpoint))
    ranking_rows = await database.fetch_all(
        rankings.select().where(rankings.c.tournament_id == tournament.id)
    )
    assert len(ranking_rows) == 1

    assert (
        await send_tournament_request(
            HTTPMethod.DELETE,
            "",
            auth_context.model_copy(update={"tournament": tournament}),
        )
        == SUCCESS_RESPONSE
    )
    assert await database.fetch_one(
        tournaments.select().where(tournaments.c.id == tournament.id)
    ) is None
    assert await database.fetch_all(
        rankings.select().where(rankings.c.tournament_id == tournament.id)
    ) == []


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_complete_tournament_preserves_other_tournament(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_data = DUMMY_TOURNAMENT.model_copy(
        update={"club_id": auth_context.club.id, "dashboard_endpoint": None}
    )
    async with AsyncExitStack() as stack:
        tournament = await stack.enter_async_context(inserted_tournament(tournament_data))
        ranking = await stack.enter_async_context(
            inserted_ranking(DUMMY_RANKING1.model_copy(update={"tournament_id": tournament.id}))
        )
        stage = await stack.enter_async_context(
            inserted_stage(DUMMY_STAGE1.model_copy(update={"tournament_id": tournament.id}))
        )
        stage_item = await stack.enter_async_context(
            inserted_stage_item(
                DUMMY_STAGE_ITEM1.model_copy(
                    update={"stage_id": stage.id, "ranking_id": ranking.id}
                )
            )
        )
        round_ = await stack.enter_async_context(
            inserted_round(DUMMY_ROUND1.model_copy(update={"stage_item_id": stage_item.id}))
        )
        team = await stack.enter_async_context(
            inserted_team(DUMMY_TEAM1.model_copy(update={"tournament_id": tournament.id}))
        )
        player = await stack.enter_async_context(
            inserted_player_in_team(
                DUMMY_PLAYER1.model_copy(update={"tournament_id": tournament.id}), team.id
            )
        )
        court = await stack.enter_async_context(
            inserted_court(DUMMY_COURT1.model_copy(update={"tournament_id": tournament.id}))
        )
        stage_input = await stack.enter_async_context(
            inserted_stage_item_input(
                StageItemInputInsertable(
                    slot=0,
                    tournament_id=tournament.id,
                    stage_item_id=stage_item.id,
                    team_id=team.id,
                )
            )
        )
        match = await stack.enter_async_context(
            inserted_match(
                DUMMY_MATCH1.model_copy(
                    update={
                        "round_id": round_.id,
                        "stage_item_input1_id": stage_input.id,
                        "stage_item_input2_id": None,
                        "court_id": court.id,
                    }
                )
            )
        )
        dependent_match = await stack.enter_async_context(
            inserted_match(
                DUMMY_MATCH1.model_copy(
                    update={
                        "round_id": round_.id,
                        "stage_item_input1_id": stage_input.id,
                        "stage_item_input2_id": None,
                        "stage_item_input1_winner_from_match_id": match.id,
                        "court_id": court.id,
                        "position_in_schedule": 2,
                    }
                )
            )
        )
        other_tournament = await stack.enter_async_context(
            inserted_tournament(tournament_data.model_copy(update={"name": "Preserved tournament"}))
        )
        other_ranking = await stack.enter_async_context(
            inserted_ranking(
                DUMMY_RANKING1.model_copy(update={"tournament_id": other_tournament.id})
            )
        )
        other_stage = await stack.enter_async_context(
            inserted_stage(
                DUMMY_STAGE1.model_copy(update={"tournament_id": other_tournament.id})
            )
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
        other_team = await stack.enter_async_context(
            inserted_team(
                DUMMY_TEAM1.model_copy(update={"tournament_id": other_tournament.id})
            )
        )
        other_player = await stack.enter_async_context(
            inserted_player_in_team(
                DUMMY_PLAYER1.model_copy(update={"tournament_id": other_tournament.id}),
                other_team.id,
            )
        )
        other_court = await stack.enter_async_context(
            inserted_court(DUMMY_COURT1.model_copy(update={"tournament_id": other_tournament.id}))
        )
        other_stage_input = await stack.enter_async_context(
            inserted_stage_item_input(
                StageItemInputInsertable(
                    slot=0,
                    tournament_id=other_tournament.id,
                    stage_item_id=other_stage_item.id,
                    team_id=other_team.id,
                )
            )
        )
        other_source_match = await stack.enter_async_context(
            inserted_match(
                DUMMY_MATCH1.model_copy(
                    update={
                        "round_id": other_round.id,
                        "stage_item_input1_id": other_stage_input.id,
                        "stage_item_input2_id": None,
                        "court_id": other_court.id,
                    }
                )
            )
        )
        other_cross_reference_match = await stack.enter_async_context(
            inserted_match(
                DUMMY_MATCH1.model_copy(
                    update={
                        "round_id": other_round.id,
                        "stage_item_input1_id": other_stage_input.id,
                        "stage_item_input2_id": None,
                        "stage_item_input1_winner_from_match_id": match.id,
                        "stage_item_input2_winner_from_match_id": other_source_match.id,
                        "court_id": other_court.id,
                        "position_in_schedule": 2,
                    }
                )
            )
        )
        event_id = await database.execute(
            match_events.insert(),
            values={
                "match_id": match.id,
                "team_id": team.id,
                "event_type": "GOAL",
                "period": "HALF1",
                "game_time_seconds": 10,
                "player_id": player.id,
                "player_name": player.name,
            },
        )
        competition_id = await database.execute(
            competitions.insert(),
            values={
                "tournament_id": tournament.id,
                "name": "Delete competition",
                "start_time": DUMMY_MOCK_TIME,
                "duration_minutes": 30,
                "court_id": court.id,
            },
        )
        discipline_id = await database.execute(
            competition_disciplines.insert(),
            values={
                "competition_id": competition_id,
                "name": "Delete discipline",
                "metric_type": "MANUAL",
            },
        )
        scoring_id = await database.execute(
            competition_scoring.insert(),
            values={"competition_id": competition_id, "place": 1, "points": 3},
        )
        result_id = await database.execute(
            competition_results.insert(),
            values={"discipline_id": discipline_id, "team_id": team.id, "place": 1},
        )
        pairing_id = await database.execute(
            competition_pairings.insert(),
            values={
                "discipline_id": discipline_id,
                "shooter_team_id": team.id,
                "goalkeeper_name": "Goalkeeper",
            },
        )

        assert (
            await send_tournament_request(
                HTTPMethod.DELETE,
                "",
                auth_context.model_copy(update={"tournament": tournament}),
            )
            == SUCCESS_RESPONSE
        )

        deleted_rows = (
            (tournaments, tournament.id),
            (rankings, ranking.id),
            (stages, stage.id),
            (stage_items, stage_item.id),
            (rounds, round_.id),
            (stage_item_inputs, stage_input.id),
            (matches, match.id),
            (matches, dependent_match.id),
            (match_events, event_id),
            (players, player.id),
            (teams, team.id),
            (courts, court.id),
            (competitions, competition_id),
            (competition_disciplines, discipline_id),
            (competition_scoring, scoring_id),
            (competition_results, result_id),
            (competition_pairings, pairing_id),
        )
        for table, row_id in deleted_rows:
            assert await database.fetch_one(table.select().where(table.c.id == row_id)) is None
        assert await database.fetch_all(
            players_x_teams.select().where(players_x_teams.c.player_id == player.id)
        ) == []

        preserved_rows = (
            (tournaments, other_tournament.id),
            (rankings, other_ranking.id),
            (stages, other_stage.id),
            (stage_items, other_stage_item.id),
            (rounds, other_round.id),
            (stage_item_inputs, other_stage_input.id),
            (matches, other_source_match.id),
            (matches, other_cross_reference_match.id),
            (players, other_player.id),
            (teams, other_team.id),
            (courts, other_court.id),
        )
        for table, row_id in preserved_rows:
            assert await database.fetch_one(table.select().where(table.c.id == row_id)) is not None
        assert await database.fetch_one(
            players_x_teams.select().where(
                (players_x_teams.c.player_id == other_player.id)
                & (players_x_teams.c.team_id == other_team.id)
            )
        ) is not None

        preserved_match = await database.fetch_one(
            matches.select().where(matches.c.id == other_cross_reference_match.id)
        )
        assert preserved_match is not None
        assert preserved_match["stage_item_input1_winner_from_match_id"] is None
        assert (
            preserved_match["stage_item_input2_winner_from_match_id"]
            == other_source_match.id
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_tournament_upload_and_remove_logo(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    test_file_path = "tests/integration_tests/assets/test_logo.png"
    data = aiohttp.FormData()
    data.add_field(
        "file",
        open(test_file_path, "rb"),  # pylint: disable=consider-using-with
        filename="test_logo.png",
        content_type="image/png",
    )

    response = await send_tournament_request(
        method=HTTPMethod.POST,
        endpoint="logo",
        auth_context=auth_context,
        body=data,
    )

    assert response.get("data", {}).get("logo_path"), f"Response: {response}"
    assert await aiofiles.os.path.exists(f"static/tournament-logos/{response['data']['logo_path']}")

    response = await send_tournament_request(
        method=HTTPMethod.POST, endpoint="logo", auth_context=auth_context, body=aiohttp.FormData()
    )

    assert response["data"]["logo_path"] is None, f"Response: {response}"
    assert not await aiofiles.os.path.exists(
        f"static/tournament-logos/{response['data']['logo_path']}"
    )


UNAUTHORIZED_RESPONSE = {
    "detail": "Could not validate credentials or page is not publicly available"
}


@pytest.mark.asyncio(loop_scope="session")
async def test_non_public_tournament_endpoints_blocked_for_unauthenticated_users(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    """
    Unauthenticated requests to a tournament with dashboard_public=False must be rejected.
    This tests the fix for GHSA-9mjc-6fp2-hm9v.
    """
    async with inserted_tournament(
        DUMMY_TOURNAMENT.model_copy(
            update={
                "club_id": auth_context.club.id,
                "dashboard_public": False,
                "dashboard_endpoint": "non-public-endpoint",
            }
        )
    ) as private_tournament:
        tournament_id = private_tournament.id
        for endpoint in (
            f"tournaments/{tournament_id}",
            f"tournaments/{tournament_id}/courts",
            f"tournaments/{tournament_id}/teams",
            f"tournaments/{tournament_id}/rankings",
            f"tournaments/{tournament_id}/stages?no_draft_rounds=true",
        ):
            response = await send_request(HTTPMethod.GET, endpoint)
            assert response == UNAUTHORIZED_RESPONSE, (
                f"Expected 401 for unauthenticated access to non-public endpoint {endpoint!r}, "
                f"got: {response}"
            )
