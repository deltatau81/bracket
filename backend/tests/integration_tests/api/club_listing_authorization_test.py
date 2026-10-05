from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Any

import aiohttp
import pytest
import pytest_asyncio

from bracket.models.db.account import UserAccountType
from bracket.models.db.user_x_club import UserXClubInsertable, UserXClubRelation
from bracket.utils.dummy_records import DUMMY_CLUB
from tests.integration_tests.api.shared import get_root_uvicorn_url
from tests.integration_tests.mocks import get_mock_token, get_mock_user
from tests.integration_tests.sql import inserted_club, inserted_user, inserted_user_x_club


@pytest_asyncio.fixture(loop_scope="session", scope="module")
async def club_listing_context() -> AsyncIterator[dict[str, Any]]:
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
            users[account_type.value] = user

        regular_without_club = await stack.enter_async_context(
            inserted_user(
                get_mock_user().model_copy(update={"account_type": UserAccountType.REGULAR})
            )
        )

        for account_type in UserAccountType:
            await stack.enter_async_context(
                inserted_user_x_club(
                    UserXClubInsertable(
                        user_id=users[account_type.value].id,
                        club_id=assigned_club.id,
                        relation=UserXClubRelation.COLLABORATOR,
                    )
                )
            )

        yield {
            "assigned_club": assigned_club,
            "unrelated_club": unrelated_club,
            "users": users,
            "regular_without_club": regular_without_club,
        }


@pytest.mark.parametrize(
    ("user_key", "expected_club_keys"),
    [
        (UserAccountType.REGULAR.value, {"assigned_club", "unrelated_club"}),
        (UserAccountType.ADMIN.value, {"assigned_club"}),
        (UserAccountType.SCORER.value, {"assigned_club"}),
        (UserAccountType.DEMO.value, {"assigned_club"}),
        ("regular_without_club", {"assigned_club", "unrelated_club"}),
    ],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_club_listing_role_matrix(
    startup_and_shutdown_uvicorn_server: None,
    club_listing_context: dict[str, Any],
    user_key: str,
    expected_club_keys: set[str],
) -> None:
    user = (
        club_listing_context["users"].get(user_key)
        or club_listing_context[user_key]
    )
    headers = {"Authorization": f"Bearer {get_mock_token(user.email)}"}

    async with aiohttp.ClientSession() as session:
        async with session.get(get_root_uvicorn_url() + "clubs", headers=headers) as response:
            body = await response.json()
            assert response.status == 200, body

    returned_club_ids = {club["id"] for club in body["data"]}
    expected_club_ids = {
        club_listing_context[club_key].id for club_key in expected_club_keys
    }
    if user.account_type == UserAccountType.REGULAR:
        assert expected_club_ids <= returned_club_ids
    else:
        assert returned_club_ids == expected_club_ids
