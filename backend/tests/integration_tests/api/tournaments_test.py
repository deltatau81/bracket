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
    TournamentStatus,
)
from bracket.schema import tournaments
from bracket.sql.tournaments import sql_delete_tournament, sql_get_tournament_by_endpoint_name
from bracket.utils.db import fetch_one_parsed_certain
from bracket.utils.dummy_records import DUMMY_MOCK_TIME, DUMMY_TOURNAMENT
from bracket.utils.http import HTTPMethod
from bracket.utils.types import assert_some
from tests.integration_tests.api.shared import (
    SUCCESS_RESPONSE,
    send_auth_request,
    send_tournament_request,
)
from tests.integration_tests.models import AuthContext
from tests.integration_tests.sql import inserted_tournament


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
                "ruleset": "DEB",
                "age_category": "U15",
                "ruleset_season": "2026/27",
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
            "ruleset": "DEB",
            "age_category": "U15",
            "ruleset_season": "2026/27",
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
    assert tournament.ruleset is HockeyRuleset.IIHF
    assert tournament.age_category is HockeyAgeCategory.SENIOR
    response = await send_auth_request(
        HTTPMethod.GET, f"tournaments/{tournament.id}", auth_context, {}
    )
    assert response["data"]["hockey_mode"] == "STANDARD"
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
