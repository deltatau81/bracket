from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Any

import aiohttp
import pytest
import pytest_asyncio

from bracket.database import database
from bracket.models.db.account import UserAccountType
from bracket.models.db.user_x_club import UserXClubInsertable, UserXClubRelation
from bracket.sql.users import check_whether_email_is_in_use, delete_user
from bracket.utils.dummy_records import DUMMY_CLUB
from tests.integration_tests.api.shared import get_root_uvicorn_url
from tests.integration_tests.mocks import get_mock_token, get_mock_user
from tests.integration_tests.sql import inserted_club, inserted_user, inserted_user_x_club


@pytest_asyncio.fixture(loop_scope="session", scope="module")
async def user_creation_context() -> AsyncIterator[dict[str, Any]]:
    async with AsyncExitStack() as stack:
        assigned_club = await stack.enter_async_context(inserted_club(DUMMY_CLUB))
        unrelated_club = await stack.enter_async_context(
            inserted_club(DUMMY_CLUB.model_copy(update={"name": "Unrelated Club"}))
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

        await stack.enter_async_context(
            inserted_user_x_club(
                UserXClubInsertable(
                    user_id=users[UserAccountType.ADMIN]["user"].id,
                    club_id=assigned_club.id,
                    relation=UserXClubRelation.COLLABORATOR,
                )
            )
        )

        yield {
            "assigned_club": assigned_club,
            "unrelated_club": unrelated_club,
            "users": users,
        }


@pytest.mark.parametrize(
    ("caller_type", "requested_type", "club_key", "expected_status"),
    [
        (UserAccountType.REGULAR, UserAccountType.ADMIN, "assigned_club", 200),
        (UserAccountType.REGULAR, UserAccountType.SCORER, "assigned_club", 200),
        (UserAccountType.REGULAR, UserAccountType.REGULAR, "assigned_club", 422),
        (UserAccountType.REGULAR, UserAccountType.DEMO, "assigned_club", 422),
        (UserAccountType.ADMIN, UserAccountType.SCORER, "assigned_club", 200),
        (UserAccountType.ADMIN, UserAccountType.ADMIN, "assigned_club", 422),
        (UserAccountType.ADMIN, UserAccountType.REGULAR, "assigned_club", 422),
        (UserAccountType.ADMIN, UserAccountType.DEMO, "assigned_club", 422),
        (UserAccountType.ADMIN, UserAccountType.SCORER, "unrelated_club", 403),
        (UserAccountType.SCORER, UserAccountType.SCORER, "assigned_club", 403),
        (UserAccountType.DEMO, UserAccountType.SCORER, "assigned_club", 403),
    ],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_club_user_creation_matrix(
    startup_and_shutdown_uvicorn_server: None,
    user_creation_context: dict[str, Any],
    caller_type: UserAccountType,
    requested_type: UserAccountType,
    club_key: str,
    expected_status: int,
) -> None:
    club = user_creation_context[club_key]
    email = f"{caller_type.value}-{requested_type.value}-{club_key}@creation.test".lower()
    payload = {
        "email": email,
        "name": "Created User",
        "password": "test-password-123",
        "account_type": requested_type.value,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            get_root_uvicorn_url() + f"clubs/{club.id}/users",
            headers=user_creation_context["users"][caller_type]["headers"],
            json=payload,
        ) as response:
            body = await response.json()
            assert response.status == expected_status, body

    if expected_status == 200:
        created_user = body["data"]
        assert created_user["account_type"] == requested_type.value
        relation = await database.fetch_one(
            """
            SELECT relation
            FROM users_x_clubs
            WHERE user_id = :user_id AND club_id = :club_id
            """,
            values={"user_id": created_user["id"], "club_id": club.id},
        )
        assert relation is not None
        assert relation["relation"] == UserXClubRelation.COLLABORATOR.value
        await delete_user(created_user["id"])
    else:
        assert not await check_whether_email_is_in_use(email)


@pytest.mark.asyncio(loop_scope="session")
async def test_public_registration_creates_no_admin_account(
    startup_and_shutdown_uvicorn_server: None,
) -> None:
    email = "public-registration@creation.test"
    async with aiohttp.ClientSession() as session:
        async with session.post(
            get_root_uvicorn_url() + "users/register",
            json={
                "email": email,
                "name": "Public User",
                "password": "test-password-123",
                "captcha_token": "test-token",
            },
        ) as response:
            body = await response.json()
            assert response.status == 403, body
            assert body == {
                "detail": "Public registration cannot create administrative accounts"
            }

    assert not await check_whether_email_is_in_use(email)
