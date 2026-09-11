import pytest

from bracket.schema import tournament_sponsors
from bracket.utils.http import HTTPMethod
from tests.integration_tests.api.shared import (
    SUCCESS_RESPONSE,
    send_request,
    send_tournament_request,
)
from tests.integration_tests.models import AuthContext
from tests.integration_tests.sql import assert_row_count_and_clear


@pytest.mark.asyncio(loop_scope="session")
async def test_tournament_sponsor_crud_sorting_and_public_read(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    sponsors = [
        {"name": "Right", "logo_path": "right.png", "position": "RIGHT"},
        {
            "name": "Left second",
            "logo_path": "left-2.png",
            "url": "https://example.com",
            "position": "LEFT",
            "sort_order": 2,
        },
        {
            "name": "Left first",
            "logo_path": "left-1.png",
            "position": "LEFT",
            "sort_order": 1,
        },
    ]
    created = []
    for sponsor in sponsors:
        response = await send_tournament_request(
            HTTPMethod.POST, "sponsors", auth_context, json=sponsor
        )
        created.append(response["data"])

    public_response = await send_request(
        HTTPMethod.GET, f"tournaments/{auth_context.tournament.id}/sponsors"
    )
    assert [sponsor["name"] for sponsor in public_response["data"]] == [
        "Left first",
        "Left second",
        "Right",
    ]

    update = {
        "name": "Updated",
        "logo_path": "updated.png",
        "url": None,
        "position": "RIGHT",
        "sort_order": 5,
    }
    updated = await send_tournament_request(
        HTTPMethod.PUT,
        f"sponsors/{created[1]['id']}",
        auth_context,
        json=update,
    )
    assert updated["data"] == {
        **update,
        "id": created[1]["id"],
        "tournament_id": auth_context.tournament.id,
    }

    assert await send_tournament_request(
        HTTPMethod.DELETE, f"sponsors/{created[0]['id']}", auth_context
    ) == SUCCESS_RESPONSE
    await assert_row_count_and_clear(tournament_sponsors, 2)


@pytest.mark.asyncio(loop_scope="session")
async def test_tournament_sponsor_position_validation(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    response = await send_tournament_request(
        HTTPMethod.POST,
        "sponsors",
        auth_context,
        json={"name": "Invalid", "logo_path": "invalid.png", "position": "CENTER"},
    )
    assert response["detail"][0]["loc"] == ["body", "position"]
