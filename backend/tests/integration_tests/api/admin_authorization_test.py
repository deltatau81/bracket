from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Any

import aiohttp
import pytest
import pytest_asyncio

from bracket.database import database
from bracket.logic.tournaments import sql_delete_tournament_completely
from bracket.models.db.account import UserAccountType
from bracket.models.db.user_x_club import UserXClubInsertable, UserXClubRelation
from bracket.schema import tournament_sponsors
from bracket.sql.clubs import sql_delete_club
from bracket.sql.tournaments import sql_get_tournament_by_endpoint_name
from bracket.utils.dummy_records import DUMMY_CLUB, DUMMY_MOCK_TIME, DUMMY_TOURNAMENT
from bracket.utils.http import HTTPMethod
from tests.integration_tests.api.shared import get_root_uvicorn_url
from tests.integration_tests.mocks import get_mock_token, get_mock_user
from tests.integration_tests.sql import (
    inserted_club,
    inserted_tournament,
    inserted_user,
    inserted_user_x_club,
)


@pytest_asyncio.fixture(loop_scope="session", scope="module")
async def authorization_context() -> AsyncIterator[dict[str, Any]]:
    async with AsyncExitStack() as stack:
        club1 = await stack.enter_async_context(inserted_club(DUMMY_CLUB))
        club2 = await stack.enter_async_context(
            inserted_club(DUMMY_CLUB.model_copy(update={"name": "Other Club"}))
        )
        tournament1 = await stack.enter_async_context(
            inserted_tournament(
                DUMMY_TOURNAMENT.model_copy(
                    update={
                        "club_id": club1.id,
                        "dashboard_endpoint": "authorization-club-one",
                    }
                )
            )
        )
        tournament2 = await stack.enter_async_context(
            inserted_tournament(
                DUMMY_TOURNAMENT.model_copy(
                    update={
                        "club_id": club2.id,
                        "dashboard_endpoint": "authorization-club-two",
                    }
                )
            )
        )

        users = {}
        for account_type in UserAccountType:
            user = await stack.enter_async_context(
                inserted_user(
                    get_mock_user().model_copy(update={"account_type": account_type})
                )
            )
            users[account_type] = {
                "user": user,
                "headers": {"Authorization": f"Bearer {get_mock_token(user)}"},
            }

        for account_type in (
            UserAccountType.ADMIN,
            UserAccountType.SCORER,
            UserAccountType.DEMO,
        ):
            await stack.enter_async_context(
                inserted_user_x_club(
                    UserXClubInsertable(
                        user_id=users[account_type]["user"].id,
                        club_id=club1.id,
                        relation=UserXClubRelation.COLLABORATOR,
                    )
                )
            )

        yield {
            "club1": club1,
            "club2": club2,
            "tournament1": tournament1,
            "tournament2": tournament2,
            "users": users,
        }


async def request_status(
    method: HTTPMethod,
    path: str,
    headers: dict[str, str],
    json: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    async with aiohttp.ClientSession() as session:
        async with session.request(
            method.value,
            get_root_uvicorn_url() + path,
            headers=headers,
            json=json,
        ) as response:
            return response.status, await response.json()


@pytest.mark.parametrize(
    ("account_type", "expected_status"),
    [
        (UserAccountType.REGULAR, 200),
        (UserAccountType.ADMIN, 403),
        (UserAccountType.SCORER, 403),
        (UserAccountType.DEMO, 403),
    ],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_global_admin_role_matrix(
    startup_and_shutdown_uvicorn_server: None,
    authorization_context: dict[str, Any],
    account_type: UserAccountType,
    expected_status: int,
) -> None:
    status_code, body = await request_status(
        HTTPMethod.POST,
        "clubs",
        authorization_context["users"][account_type]["headers"],
        {"name": f"Created by {account_type.value}"},
    )
    assert status_code == expected_status, body
    if status_code == 200:
        await sql_delete_club(body["data"]["id"])


@pytest.mark.parametrize(
    ("account_type", "club_key", "expected_status"),
    [
        (UserAccountType.REGULAR, "club2", 200),
        (UserAccountType.ADMIN, "club1", 200),
        (UserAccountType.ADMIN, "club2", 403),
        (UserAccountType.SCORER, "club1", 403),
        (UserAccountType.DEMO, "club1", 403),
    ],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_club_admin_role_and_assignment_matrix(
    startup_and_shutdown_uvicorn_server: None,
    authorization_context: dict[str, Any],
    account_type: UserAccountType,
    club_key: str,
    expected_status: int,
) -> None:
    club = authorization_context[club_key]
    status_code, body = await request_status(
        HTTPMethod.GET,
        f"clubs/{club.id}/users",
        authorization_context["users"][account_type]["headers"],
    )
    assert status_code == expected_status, body


@pytest.mark.parametrize(
    ("account_type", "tournament_key", "expected_status"),
    [
        (UserAccountType.REGULAR, "tournament2", 200),
        (UserAccountType.ADMIN, "tournament1", 200),
        (UserAccountType.ADMIN, "tournament2", 403),
        (UserAccountType.DEMO, "tournament1", 403),
    ],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_tournament_admin_role_and_assignment_matrix(
    startup_and_shutdown_uvicorn_server: None,
    authorization_context: dict[str, Any],
    account_type: UserAccountType,
    tournament_key: str,
    expected_status: int,
) -> None:
    tournament = authorization_context[tournament_key]
    status_code, body = await request_status(
        HTTPMethod.POST,
        f"tournaments/{tournament.id}/sponsors",
        authorization_context["users"][account_type]["headers"],
        {"name": "Authorization test", "logo_path": "test.png", "position": "LEFT"},
    )
    assert status_code == expected_status, body
    if status_code == 200:
        await database.execute(
            tournament_sponsors.delete().where(
                tournament_sponsors.c.tournament_id == tournament.id
            )
        )


def tournament_body(club_id: int, endpoint: str) -> dict[str, Any]:
    return {
        "name": "Authorization tournament",
        "start_time": DUMMY_MOCK_TIME.isoformat(),
        "club_id": club_id,
        "dashboard_public": True,
        "dashboard_endpoint": endpoint,
        "players_can_be_in_multiple_teams": True,
        "auto_assign_courts": True,
        "duration_minutes": 10,
        "margin_minutes": 5,
    }


@pytest.mark.parametrize(
    ("account_type", "club_key", "endpoint", "expected_status"),
    [
        (UserAccountType.REGULAR, "club2", "regular-any-club", 200),
        (UserAccountType.ADMIN, "club1", "admin-assigned-club", 200),
        (UserAccountType.ADMIN, "club2", "admin-other-club", 403),
    ],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_tournament_creation_uses_club_scope(
    startup_and_shutdown_uvicorn_server: None,
    authorization_context: dict[str, Any],
    account_type: UserAccountType,
    club_key: str,
    endpoint: str,
    expected_status: int,
) -> None:
    club = authorization_context[club_key]
    status_code, response = await request_status(
        HTTPMethod.POST,
        "tournaments",
        authorization_context["users"][account_type]["headers"],
        tournament_body(club.id, endpoint),
    )
    assert status_code == expected_status, response
    created = await sql_get_tournament_by_endpoint_name(endpoint)
    if expected_status == 200:
        assert created is not None
        await sql_delete_tournament_completely(created.id)
    else:
        assert created is None
