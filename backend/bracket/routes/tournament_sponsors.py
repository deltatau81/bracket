from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from bracket.models.db.tournament import Tournament
from bracket.models.db.tournament_sponsor import (
    TournamentSponsorCreateBody,
    TournamentSponsorUpdateBody,
)
from bracket.models.db.user import UserPublic
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
from bracket.sql.tournament_sponsors import (
    create_tournament_sponsor,
    delete_tournament_sponsor,
    get_tournament_sponsor,
    get_tournament_sponsors,
    update_tournament_sponsor,
)
from bracket.utils.id_types import TournamentId, TournamentSponsorId

router = APIRouter()


def sponsor_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Tournament sponsor not found",
    )


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
    if await get_tournament_sponsor(tournament_id, sponsor_id) is None:
        raise sponsor_not_found()
    await delete_tournament_sponsor(tournament_id, sponsor_id)
    return SuccessResponse()
