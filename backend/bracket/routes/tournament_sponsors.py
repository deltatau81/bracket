import os
from uuid import uuid4

import aiofiles
import aiofiles.os
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from starlette import status

from bracket.models.db.tournament import Tournament
from bracket.models.db.tournament_sponsor import (
    TournamentSponsorCreateBody,
    TournamentSponsorUpdateBody,
)
from bracket.models.db.user import UserPublic
from bracket.database import database
from bracket.routes.auth import (
    user_authenticated_for_tournament_admin,
    user_authenticated_or_public_dashboard,
)
from bracket.routes.models import (
    SuccessResponse,
    TournamentSponsorResponse,
    TournamentSponsorsResponse,
)
from bracket.routes.util import disallow_archived_tournament
from bracket.schema import tournament_sponsors
from bracket.sql.tournament_sponsors import (
    create_tournament_sponsor,
    delete_tournament_sponsor,
    get_tournament_sponsor,
    get_tournament_sponsors,
    update_tournament_sponsor,
)
from bracket.utils.id_types import TournamentId, TournamentSponsorId
from bracket.utils.logging import logger

router = APIRouter()
MAX_SPONSOR_LOGO_SIZE = 5 * 1024 * 1024
SPONSOR_LOGO_CONTENT_TYPES = {"image/jpeg", "image/png"}


def sponsor_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Tournament sponsor not found",
    )


async def remove_sponsor_logo(logo_path: str) -> None:
    if not logo_path.startswith("static/sponsor-logos/"):
        return
    try:
        await aiofiles.os.remove(logo_path)
    except FileNotFoundError:
        pass
    except Exception as exc:
        logger.error(f"Could not remove sponsor logo {logo_path}: {exc}")


@router.get(
    "/tournaments/{tournament_id}/sponsors",
    response_model=TournamentSponsorsResponse,
)
async def list_tournament_sponsors(
    tournament_id: TournamentId,
    _: UserPublic | None = Depends(user_authenticated_or_public_dashboard),
) -> TournamentSponsorsResponse:
    return TournamentSponsorsResponse(data=await get_tournament_sponsors(tournament_id))


@router.post(
    "/tournaments/{tournament_id}/sponsors",
    response_model=TournamentSponsorResponse,
)
async def create_tournament_sponsor_route(
    tournament_id: TournamentId,
    body: TournamentSponsorCreateBody,
    _: UserPublic = Depends(user_authenticated_for_tournament_admin),
    __: Tournament = Depends(disallow_archived_tournament),
) -> TournamentSponsorResponse:
    sponsor_id = await create_tournament_sponsor(tournament_id, body)
    sponsor = await get_tournament_sponsor(tournament_id, sponsor_id)
    assert sponsor is not None
    return TournamentSponsorResponse(data=sponsor)


@router.put(
    "/tournaments/{tournament_id}/sponsors/{sponsor_id}",
    response_model=TournamentSponsorResponse,
)
async def update_tournament_sponsor_route(
    tournament_id: TournamentId,
    sponsor_id: TournamentSponsorId,
    body: TournamentSponsorUpdateBody,
    _: UserPublic = Depends(user_authenticated_for_tournament_admin),
    __: Tournament = Depends(disallow_archived_tournament),
) -> TournamentSponsorResponse:
    if await get_tournament_sponsor(tournament_id, sponsor_id) is None:
        raise sponsor_not_found()
    await update_tournament_sponsor(tournament_id, sponsor_id, body)
    sponsor = await get_tournament_sponsor(tournament_id, sponsor_id)
    assert sponsor is not None
    return TournamentSponsorResponse(data=sponsor)


@router.post(
    "/tournaments/{tournament_id}/sponsors/{sponsor_id}/logo",
    response_model=TournamentSponsorResponse,
)
async def upload_tournament_sponsor_logo(
    tournament_id: TournamentId,
    sponsor_id: TournamentSponsorId,
    file: UploadFile,
    _: UserPublic = Depends(user_authenticated_for_tournament_admin),
    __: Tournament = Depends(disallow_archived_tournament),
) -> TournamentSponsorResponse:
    sponsor = await get_tournament_sponsor(tournament_id, sponsor_id)
    if sponsor is None:
        raise sponsor_not_found()

    if file.content_type not in SPONSOR_LOGO_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only PNG and JPEG sponsor logos are supported",
        )

    assert file.filename is not None
    extension = os.path.splitext(file.filename)[1].lower()
    if extension not in (".png", ".jpg", ".jpeg"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only PNG and JPEG sponsor logos are supported",
        )

    content = await file.read(MAX_SPONSOR_LOGO_SIZE + 1)
    if len(content) > MAX_SPONSOR_LOGO_SIZE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Sponsor logos may not exceed 5 MB",
        )

    logo_path = f"static/sponsor-logos/{uuid4()}{extension}"
    await aiofiles.os.makedirs("static/sponsor-logos", exist_ok=True)
    async with aiofiles.open(logo_path, "wb") as logo_file:
        await logo_file.write(content)

    await database.execute(
        tournament_sponsors.update()
        .where(
            (tournament_sponsors.c.id == sponsor_id)
            & (tournament_sponsors.c.tournament_id == tournament_id)
        )
        .values(logo_path=logo_path)
    )
    await remove_sponsor_logo(sponsor.logo_path)

    updated = await get_tournament_sponsor(tournament_id, sponsor_id)
    assert updated is not None
    return TournamentSponsorResponse(data=updated)


@router.delete(
    "/tournaments/{tournament_id}/sponsors/{sponsor_id}",
    response_model=SuccessResponse,
)
async def delete_tournament_sponsor_route(
    tournament_id: TournamentId,
    sponsor_id: TournamentSponsorId,
    _: UserPublic = Depends(user_authenticated_for_tournament_admin),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    sponsor = await get_tournament_sponsor(tournament_id, sponsor_id)
    if sponsor is None:
        raise sponsor_not_found()
    await delete_tournament_sponsor(tournament_id, sponsor_id)
    await remove_sponsor_logo(sponsor.logo_path)
    return SuccessResponse()
