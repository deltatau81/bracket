from io import BytesIO

import aiofiles.os
import aiohttp
import pytest

from bracket.schema import tournament_sponsors
from bracket.utils.http import HTTPMethod
from tests.integration_tests.api.shared import (
    SUCCESS_RESPONSE,
    get_root_uvicorn_url,
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


@pytest.mark.asyncio(loop_scope="session")
async def test_tournament_sponsor_url_updates_preserve_logo_path(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    logo_path = "static/sponsors/original.png"
    created = await send_tournament_request(
        HTTPMethod.POST,
        "sponsors",
        auth_context,
        json={
            "name": "URL sponsor",
            "logo_path": logo_path,
            "url": "https://example.com/original",
            "position": "LEFT",
        },
    )
    sponsor_id = created["data"]["id"]
    body = {
        "name": "Renamed sponsor",
        "logo_path": logo_path,
        "url": "https://example.com/updated",
        "position": "RIGHT",
        "sort_order": 3,
    }

    updated = await send_tournament_request(
        HTTPMethod.PUT, f"sponsors/{sponsor_id}", auth_context, json=body
    )
    assert updated["data"]["url"] == body["url"]
    assert updated["data"]["logo_path"] == logo_path

    body["url"] = None
    updated = await send_tournament_request(
        HTTPMethod.PUT, f"sponsors/{sponsor_id}", auth_context, json=body
    )
    assert updated["data"]["url"] is None
    assert updated["data"]["logo_path"] == logo_path

    assert await send_tournament_request(
        HTTPMethod.DELETE, f"sponsors/{sponsor_id}", auth_context
    ) == SUCCESS_RESPONSE


@pytest.mark.asyncio(loop_scope="session")
async def test_tournament_sponsor_logo_upload_and_delete(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    created = await send_tournament_request(
        HTTPMethod.POST,
        "sponsors",
        auth_context,
        json={"name": "Upload", "logo_path": "", "position": "LEFT"},
    )
    sponsor_id = created["data"]["id"]
    data = aiohttp.FormData()
    data.add_field(
        "file",
        open(  # pylint: disable=consider-using-with
            "tests/integration_tests/assets/test_logo.png", "rb"
        ),
        filename="test_logo.png",
        content_type="image/png",
    )

    uploaded = await send_tournament_request(
        HTTPMethod.POST,
        f"sponsors/{sponsor_id}/logo",
        auth_context,
        body=data,
    )
    logo_path = uploaded["data"]["logo_path"]
    assert logo_path.startswith("static/sponsor-logos/")
    assert await aiofiles.os.path.exists(logo_path)

    assert await send_tournament_request(
        HTTPMethod.DELETE, f"sponsors/{sponsor_id}", auth_context
    ) == SUCCESS_RESPONSE
    assert not await aiofiles.os.path.exists(logo_path)


async def rejected_logo_upload(
    auth_context: AuthContext,
    sponsor_id: int,
    content: bytes,
    content_type: str,
) -> None:
    data = aiohttp.FormData()
    data.add_field(
        "file",
        BytesIO(content),
        filename="test.png",
        content_type=content_type,
    )
    url = (
        get_root_uvicorn_url()
        + f"tournaments/{auth_context.tournament.id}/sponsors/{sponsor_id}/logo"
    )
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=auth_context.headers, data=data) as response:
            assert response.status == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_tournament_sponsor_logo_rejects_invalid_content_type(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    created = await send_tournament_request(
        HTTPMethod.POST,
        "sponsors",
        auth_context,
        json={"name": "Invalid type", "logo_path": "", "position": "LEFT"},
    )
    sponsor_id = created["data"]["id"]
    await rejected_logo_upload(auth_context, sponsor_id, b"not an image", "text/plain")
    assert await send_tournament_request(
        HTTPMethod.DELETE, f"sponsors/{sponsor_id}", auth_context
    ) == SUCCESS_RESPONSE


@pytest.mark.asyncio(loop_scope="session")
async def test_tournament_sponsor_logo_rejects_files_over_five_mb(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    created = await send_tournament_request(
        HTTPMethod.POST,
        "sponsors",
        auth_context,
        json={"name": "Too large", "logo_path": "", "position": "LEFT"},
    )
    sponsor_id = created["data"]["id"]
    await rejected_logo_upload(
        auth_context,
        sponsor_id,
        b"x" * (5 * 1024 * 1024 + 1),
        "image/png",
    )
    assert await send_tournament_request(
        HTTPMethod.DELETE, f"sponsors/{sponsor_id}", auth_context
    ) == SUCCESS_RESPONSE
