import aiofiles.os
import aiohttp
import pytest

from bracket.database import database
from bracket.models.db.team import Team
from bracket.schema import players, teams, users_x_clubs
from bracket.utils.db import fetch_one_parsed_certain
from bracket.utils.dummy_records import (
    DUMMY_CLUB,
    DUMMY_MOCK_TIME,
    DUMMY_TEAM1,
    DUMMY_TOURNAMENT,
)
from bracket.utils.http import HTTPMethod
from tests.integration_tests.api.shared import (
    SUCCESS_RESPONSE,
    send_auth_request,
    send_tournament_request,
)
from tests.integration_tests.models import AuthContext
from tests.integration_tests.sql import (
    assert_row_count_and_clear,
    inserted_club,
    inserted_team,
    inserted_tournament,
)


@pytest.mark.asyncio(loop_scope="session")
async def test_teams_endpoint(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with inserted_team(
        DUMMY_TEAM1.model_copy(update={"tournament_id": auth_context.tournament.id})
    ) as team_inserted:
        assert await send_tournament_request(HTTPMethod.GET, "teams", auth_context, {}) == {
            "data": {
                "teams": [
                    {
                        "active": True,
                        "created": DUMMY_MOCK_TIME.isoformat().replace("+00:00", "Z"),
                        "id": team_inserted.id,
                        "name": "Team 1",
                        "players": [],
                        "tournament_id": team_inserted.tournament_id,
                        "participant_club_id": None,
                        "pairing_group": None,
                        "elo_score": "1200.0",
                        "swiss_score": "0.0",
                        "wins": 0,
                        "draws": 0,
                        "losses": 0,
                        "logo_path": None,
                    }
                ],
                "count": 1,
            },
        }


@pytest.mark.asyncio(loop_scope="session")
async def test_create_team(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    body = {"name": "Some new name", "active": True, "player_ids": []}
    response = await send_tournament_request(HTTPMethod.POST, "teams", auth_context, None, body)
    assert response["data"]["name"] == body["name"]
    await assert_row_count_and_clear(teams, 1)


@pytest.mark.asyncio(loop_scope="session")
async def test_team_pairing_group_create_update_clear_and_length_validation(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    body = {"name": "Pairing Team", "active": True, "player_ids": []}

    created = await send_tournament_request(
        HTTPMethod.POST,
        "teams",
        auth_context,
        None,
        body | {"pairing_group": "A"},
    )
    team_id = created["data"]["id"]
    assert created["data"]["pairing_group"] == "A"

    updated = await send_tournament_request(
        HTTPMethod.PUT,
        f"teams/{team_id}",
        auth_context,
        None,
        body | {"pairing_group": "C"},
    )
    assert updated["data"]["pairing_group"] == "C"

    cleared = await send_tournament_request(
        HTTPMethod.PUT,
        f"teams/{team_id}",
        auth_context,
        None,
        body | {"pairing_group": None},
    )
    assert cleared["data"]["pairing_group"] is None

    omitted = await send_tournament_request(
        HTTPMethod.POST, "teams", auth_context, None, body | {"name": "Omitted Group"}
    )
    assert omitted["data"]["pairing_group"] is None

    too_long = await send_tournament_request(
        HTTPMethod.POST,
        "teams",
        auth_context,
        None,
        body | {"name": "Too Long Group", "pairing_group": "X" * 33},
    )
    assert too_long["detail"][0]["loc"][-1] == "pairing_group"

    await assert_row_count_and_clear(teams, 2)


@pytest.mark.asyncio(loop_scope="session")
async def test_create_teams(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    body = {"names": "Team -1,Player 42,Player 43\nTeam -2,", "active": True}
    response = await send_tournament_request(
        HTTPMethod.POST, "teams_multi", auth_context, None, body
    )
    assert response["success"] is True
    await assert_row_count_and_clear(teams, 2)
    await assert_row_count_and_clear(players, 3)


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_team(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with inserted_team(
        DUMMY_TEAM1.model_copy(update={"tournament_id": auth_context.tournament.id})
    ) as team_inserted:
        assert (
            await send_tournament_request(
                HTTPMethod.DELETE, f"teams/{team_inserted.id}", auth_context, {}
            )
            == SUCCESS_RESPONSE
        )
        await assert_row_count_and_clear(teams, 0)


@pytest.mark.asyncio(loop_scope="session")
async def test_update_team(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    body = {"name": "Some new name", "active": True, "player_ids": []}
    async with inserted_team(
        DUMMY_TEAM1.model_copy(update={"tournament_id": auth_context.tournament.id})
    ) as team_inserted:
        response = await send_tournament_request(
            HTTPMethod.PUT, f"teams/{team_inserted.id}", auth_context, None, body
        )
        updated_team = await fetch_one_parsed_certain(
            database, Team, query=teams.select().where(teams.c.id == team_inserted.id)
        )
        assert updated_team.name == body["name"]
        assert response["data"]["name"] == body["name"]

        await assert_row_count_and_clear(teams, 1)


@pytest.mark.asyncio(loop_scope="session")
async def test_update_team_invalid_players(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    body = {"name": "Some new name", "active": True, "player_ids": [-1]}
    async with inserted_team(
        DUMMY_TEAM1.model_copy(update={"tournament_id": auth_context.tournament.id})
    ) as team_inserted:
        response = await send_tournament_request(
            HTTPMethod.PUT, f"teams/{team_inserted.id}", auth_context, None, body
        )
        assert response == {"detail": "Could not find Player(s) with ID {-1}"}


@pytest.mark.asyncio(loop_scope="session")
async def test_team_participant_club_create_read_and_update(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with (
        inserted_club(DUMMY_CLUB.model_copy(update={"name": "Participant Club One"})) as club1,
        inserted_club(DUMMY_CLUB.model_copy(update={"name": "Participant Club Two"})) as club2,
    ):
        body = {"name": "Participant Team", "active": True, "player_ids": []}
        created = await send_tournament_request(
            HTTPMethod.POST,
            "teams",
            auth_context,
            None,
            body | {"participant_club_id": club1.id},
        )
        team_id = created["data"]["id"]
        assert created["data"]["participant_club_id"] == club1.id

        listed = await send_tournament_request(HTTPMethod.GET, "teams", auth_context, {})
        listed_team = next(team for team in listed["data"]["teams"] if team["id"] == team_id)
        assert listed_team["participant_club_id"] == club1.id

        for participant_club_id in (None, club2.id, None):
            updated = await send_tournament_request(
                HTTPMethod.PUT,
                f"teams/{team_id}",
                auth_context,
                None,
                body | {"participant_club_id": participant_club_id},
            )
            assert updated["data"]["participant_club_id"] == participant_club_id

        await assert_row_count_and_clear(teams, 1)


@pytest.mark.asyncio(loop_scope="session")
async def test_team_batch_pairing_group_and_participant_club(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with inserted_club(DUMMY_CLUB.model_copy(update={"name": "Batch Club"})) as club:
        response = await send_tournament_request(
            HTTPMethod.POST,
            "teams_multi",
            auth_context,
            None,
            {
                "names": "Batch Team 1\nBatch Team 2",
                "active": True,
                "participant_club_id": club.id,
                "pairing_group": "B",
            },
        )
        assert response["success"] is True
        created_teams = await database.fetch_all(
            teams.select().where(teams.c.tournament_id == auth_context.tournament.id)
        )
        assert {row["participant_club_id"] for row in created_teams} == {club.id}
        assert {row["pairing_group"] for row in created_teams} == {"B"}
        await assert_row_count_and_clear(teams, 2)


@pytest.mark.asyncio(loop_scope="session")
async def test_team_participant_club_cardinality_and_authorization_isolation(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with (
        inserted_club(DUMMY_CLUB.model_copy(update={"name": "Participant Club Alpha"})) as club1,
        inserted_club(DUMMY_CLUB.model_copy(update={"name": "Participant Club Beta"})) as club2,
        inserted_club(DUMMY_CLUB.model_copy(update={"name": "Participant Club Without Team"})),
    ):
        memberships_before = await database.fetch_all(
            users_x_clubs.select().where(users_x_clubs.c.user_id == auth_context.user.id)
        )

        participant_club_ids = [club1.id, club1.id, club1.id, club2.id]
        for index, participant_club_id in enumerate(participant_club_ids):
            response = await send_tournament_request(
                HTTPMethod.POST,
                "teams",
                auth_context,
                None,
                {
                    "name": f"Participant Team {index}",
                    "active": True,
                    "player_ids": [],
                    "participant_club_id": participant_club_id,
                },
            )
            assert response["data"]["participant_club_id"] == participant_club_id

        memberships_after = await database.fetch_all(
            users_x_clubs.select().where(users_x_clubs.c.user_id == auth_context.user.id)
        )
        assert [dict(row._mapping) for row in memberships_after] == [
            dict(row._mapping) for row in memberships_before
        ]
        await assert_row_count_and_clear(teams, 4)


@pytest.mark.asyncio(loop_scope="session")
async def test_team_participant_club_validation(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    response = await send_tournament_request(
        HTTPMethod.POST,
        "teams",
        auth_context,
        None,
        {
            "name": "Invalid Participant Club",
            "active": True,
            "player_ids": [],
            "participant_club_id": -1,
        },
    )
    assert response == {"detail": "Could not find Club(s) with ID -1"}
    await assert_row_count_and_clear(teams, 0)


@pytest.mark.asyncio(loop_scope="session")
async def test_team_upload_and_remove_logo(
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

    async with inserted_team(
        DUMMY_TEAM1.model_copy(update={"tournament_id": auth_context.tournament.id})
    ) as team_inserted:
        response = await send_tournament_request(
            method=HTTPMethod.POST,
            endpoint=f"teams/{team_inserted.id}/logo",
            auth_context=auth_context,
            body=data,
        )

        assert response["data"]["logo_path"], f"Response: {response}"
        assert await aiofiles.os.path.exists(f"static/team-logos/{response['data']['logo_path']}")

        response = await send_tournament_request(
            method=HTTPMethod.POST,
            endpoint="logo",
            auth_context=auth_context,
            body=aiohttp.FormData(),
        )

        assert response["data"]["logo_path"] is None, f"Response: {response}"
        assert not await aiofiles.os.path.exists(
            f"static/team-logos/{response['data']['logo_path']}"
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_cross_tournament_team_access_denied(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    """Regression test: a team from tournament B cannot be accessed via tournament A's URL."""
    async with inserted_tournament(
        DUMMY_TOURNAMENT.model_copy(
            update={"club_id": auth_context.club.id, "dashboard_endpoint": None}
        )
    ) as other_tournament:
        async with inserted_team(
            DUMMY_TEAM1.model_copy(update={"tournament_id": other_tournament.id})
        ) as other_team:
            response = await send_auth_request(
                HTTPMethod.PUT,
                f"tournaments/{auth_context.tournament.id}/teams/{other_team.id}",
                auth_context,
                json={"name": "Hacked", "active": True, "player_ids": []},
            )
            assert response.get("detail") == f"Could not find team with id {other_team.id}"
