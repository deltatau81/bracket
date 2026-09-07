from fastapi import APIRouter, Depends, HTTPException
from heliclockter import datetime_utc
from starlette import status

from bracket.models.db.competition import (
    CompetitionBody,
    CompetitionDisciplineBody,
    CompetitionDisciplineInsertable,
    CompetitionInsertable,
    CompetitionScoringBody,
    CompetitionRankedResult,
    CompetitionResultBody,
    CompetitionResultInsertable,
)
from bracket.models.db.tournament import Tournament
from bracket.models.db.user import UserPublic
from bracket.routes.auth import (
    user_authenticated_for_tournament,
    user_authenticated_for_tournament_admin,
    user_authenticated_or_public_dashboard,
)
from bracket.routes.models import (
    CompetitionDisciplineResponse,
    CompetitionDisciplinesResponse,
    CompetitionResponse,
    CompetitionScoringResponse,
    CompetitionsResponse,
    SuccessResponse,
    CompetitionRankedResultsResponse,
    CompetitionResultsResponse,
    TournamentOverallStandingsResponse,
)
from bracket.routes.util import disallow_archived_tournament
from bracket.sql.competitions import (
    create_competition,
    create_discipline,
    delete_competition,
    delete_discipline,
    get_competition,
    get_competitions_in_tournament,
    get_discipline,
    get_disciplines,
    get_scoring,
    replace_scoring,
    update_competition,
    update_discipline,
    get_results,
    get_result,
    upsert_result,
    update_result_place,
    get_tournament_overall_standings,
)
from bracket.utils.id_types import (
     CompetitionDisciplineId,
     CompetitionId,
     TournamentId,
)
from bracket.competition_logic import rank_results
router = APIRouter()


@router.get(
    "/tournaments/{tournament_id}/overall_standings",
    response_model=TournamentOverallStandingsResponse,
)
async def get_overall_standings(
    tournament_id: TournamentId,
    _: UserPublic | None = Depends(user_authenticated_or_public_dashboard),
) -> TournamentOverallStandingsResponse:
    return TournamentOverallStandingsResponse(
        data=await get_tournament_overall_standings(tournament_id)
    )


def competition_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Competition not found",
    )


@router.get(
    "/tournaments/{tournament_id}/competitions",
    response_model=CompetitionsResponse,
)
async def get_competitions(
    tournament_id: TournamentId,
    _: UserPublic | None = Depends(user_authenticated_or_public_dashboard),
) -> CompetitionsResponse:
    return CompetitionsResponse(
        data=await get_competitions_in_tournament(tournament_id)
    )


@router.get(
    "/tournaments/{tournament_id}/competitions/{competition_id}",
    response_model=CompetitionResponse,
)
async def get_competition_by_id(
    tournament_id: TournamentId,
    competition_id: CompetitionId,
    _: UserPublic | None = Depends(user_authenticated_or_public_dashboard),
) -> CompetitionResponse:
    competition = await get_competition(
        tournament_id,
        competition_id,
    )

    if competition is None:
        raise competition_not_found()

    return CompetitionResponse(data=competition)


@router.post(
    "/tournaments/{tournament_id}/competitions",
    response_model=CompetitionResponse,
)
async def create_competition_route(
    tournament_id: TournamentId,
    body: CompetitionBody,
    _: UserPublic = Depends(user_authenticated_for_tournament_admin),
    __: Tournament = Depends(disallow_archived_tournament),
) -> CompetitionResponse:
    competition_id = await create_competition(
        CompetitionInsertable(
            **body.model_dump(),
            tournament_id=tournament_id,
            created=datetime_utc.now(),
        )
    )

    competition = await get_competition(
        tournament_id,
        competition_id,
    )

    assert competition is not None
    return CompetitionResponse(data=competition)


@router.put(
    "/tournaments/{tournament_id}/competitions/{competition_id}",
    response_model=CompetitionResponse,
)
async def update_competition_route(
    tournament_id: TournamentId,
    competition_id: CompetitionId,
    body: CompetitionBody,
    _: UserPublic = Depends(user_authenticated_for_tournament_admin),
    __: Tournament = Depends(disallow_archived_tournament),
) -> CompetitionResponse:
    existing = await get_competition(
        tournament_id,
        competition_id,
    )

    if existing is None:
        raise competition_not_found()

    await update_competition(
        tournament_id,
        competition_id,
        body,
    )

    competition = await get_competition(
        tournament_id,
        competition_id,
    )

    assert competition is not None
    return CompetitionResponse(data=competition)


@router.delete(
    "/tournaments/{tournament_id}/competitions/{competition_id}",
    response_model=SuccessResponse,
)
async def delete_competition_route(
    tournament_id: TournamentId,
    competition_id: CompetitionId,
    _: UserPublic = Depends(user_authenticated_for_tournament_admin),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    existing = await get_competition(
        tournament_id,
        competition_id,
    )

    if existing is None:
        raise competition_not_found()

    await delete_competition(
        tournament_id,
        competition_id,
    )

    return SuccessResponse()

# ---------------------------------------------------------------------------
# Disciplines
# ---------------------------------------------------------------------------

def discipline_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Competition discipline not found",
    )


@router.get(
    "/tournaments/{tournament_id}/competitions/{competition_id}/disciplines",
    response_model=CompetitionDisciplinesResponse,
)
async def get_competition_disciplines(
    tournament_id: TournamentId,
    competition_id: CompetitionId,
    _: UserPublic | None = Depends(
        user_authenticated_or_public_dashboard
    ),
) -> CompetitionDisciplinesResponse:
    competition = await get_competition(
        tournament_id,
        competition_id,
    )

    if competition is None:
        raise competition_not_found()

    return CompetitionDisciplinesResponse(
        data=await get_disciplines(competition_id)
    )


@router.post(
    "/tournaments/{tournament_id}/competitions/{competition_id}/disciplines",
    response_model=CompetitionDisciplineResponse,
)
async def create_competition_discipline(
    tournament_id: TournamentId,
    competition_id: CompetitionId,
    body: CompetitionDisciplineBody,
    _: UserPublic = Depends(user_authenticated_for_tournament_admin),
    __: Tournament = Depends(disallow_archived_tournament),
) -> CompetitionDisciplineResponse:
    competition = await get_competition(
        tournament_id,
        competition_id,
    )

    if competition is None:
        raise competition_not_found()

    discipline_id = await create_discipline(
        CompetitionDisciplineInsertable(
            **body.model_dump(),
            competition_id=competition_id,
            created=datetime_utc.now(),
        )
    )

    discipline = await get_discipline(
        competition_id,
        discipline_id,
    )

    assert discipline is not None

    return CompetitionDisciplineResponse(
        data=discipline
    )


@router.put(
    "/tournaments/{tournament_id}/competitions/{competition_id}/disciplines/{discipline_id}",
    response_model=CompetitionDisciplineResponse,
)
async def update_competition_discipline(
    tournament_id: TournamentId,
    competition_id: CompetitionId,
    discipline_id: CompetitionDisciplineId,
    body: CompetitionDisciplineBody,
    _: UserPublic = Depends(user_authenticated_for_tournament_admin),
    __: Tournament = Depends(disallow_archived_tournament),
) -> CompetitionDisciplineResponse:
    competition = await get_competition(
        tournament_id,
        competition_id,
    )

    if competition is None:
        raise competition_not_found()

    existing = await get_discipline(
        competition_id,
        discipline_id,
    )

    if existing is None:
        raise discipline_not_found()

    await update_discipline(
        competition_id,
        discipline_id,
        body,
    )

    discipline = await get_discipline(
        competition_id,
        discipline_id,
    )

    assert discipline is not None

    return CompetitionDisciplineResponse(
        data=discipline
    )


@router.delete(
    "/tournaments/{tournament_id}/competitions/{competition_id}/disciplines/{discipline_id}",
    response_model=SuccessResponse,
)
async def delete_competition_discipline(
    tournament_id: TournamentId,
    competition_id: CompetitionId,
    discipline_id: CompetitionDisciplineId,
    _: UserPublic = Depends(user_authenticated_for_tournament_admin),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    competition = await get_competition(
        tournament_id,
        competition_id,
    )

    if competition is None:
        raise competition_not_found()

    existing = await get_discipline(
        competition_id,
        discipline_id,
    )

    if existing is None:
        raise discipline_not_found()

    await delete_discipline(
        competition_id,
        discipline_id,
    )

    return SuccessResponse()


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

@router.get(
    "/tournaments/{tournament_id}/competitions/{competition_id}/scoring",
    response_model=CompetitionScoringResponse,
)
async def get_competition_scoring(
    tournament_id: TournamentId,
    competition_id: CompetitionId,
    _: UserPublic | None = Depends(
        user_authenticated_or_public_dashboard
    ),
) -> CompetitionScoringResponse:
    competition = await get_competition(
        tournament_id,
        competition_id,
    )

    if competition is None:
        raise competition_not_found()

    return CompetitionScoringResponse(
        data=await get_scoring(competition_id)
    )


@router.put(
    "/tournaments/{tournament_id}/competitions/{competition_id}/scoring",
    response_model=CompetitionScoringResponse,
)
async def set_competition_scoring(
    tournament_id: TournamentId,
    competition_id: CompetitionId,
    body: list[CompetitionScoringBody],
    _: UserPublic = Depends(user_authenticated_for_tournament_admin),
    __: Tournament = Depends(disallow_archived_tournament),
) -> CompetitionScoringResponse:
    competition = await get_competition(
        tournament_id,
        competition_id,
    )

    if competition is None:
        raise competition_not_found()

    places = [item.place for item in body]

    if len(places) != len(set(places)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Each place may only occur once",
        )

    await replace_scoring(
        competition_id,
        body,
    )

    return CompetitionScoringResponse(
        data=await get_scoring(competition_id)
    )

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@router.get(
    "/tournaments/{tournament_id}/competitions/{competition_id}/disciplines/{discipline_id}/results",
    response_model=CompetitionResultsResponse,
)
async def get_competition_results(
    tournament_id: TournamentId,
    competition_id: CompetitionId,
    discipline_id: CompetitionDisciplineId,
    _: UserPublic | None = Depends(
        user_authenticated_or_public_dashboard
    ),
) -> CompetitionResultsResponse:

    competition = await get_competition(
        tournament_id,
        competition_id,
    )

    if competition is None:
        raise competition_not_found()

    discipline = await get_discipline(
        competition_id,
        discipline_id,
    )

    if discipline is None:
        raise discipline_not_found()

    return CompetitionResultsResponse(
        data=await get_results(discipline_id)
    )


@router.put(
    "/tournaments/{tournament_id}/competitions/{competition_id}/disciplines/{discipline_id}/results",
    response_model=CompetitionResultsResponse,
)
async def set_competition_result(
    tournament_id: TournamentId,
    competition_id: CompetitionId,
    discipline_id: CompetitionDisciplineId,
    body: CompetitionResultBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> CompetitionResultsResponse:

    competition = await get_competition(
        tournament_id,
        competition_id,
    )

    if competition is None:
        raise competition_not_found()

    discipline = await get_discipline(
        competition_id,
        discipline_id,
    )

    if discipline is None:
        raise discipline_not_found()

    if (
        body.attempts is not None
        and body.successes is not None
        and body.successes > body.attempts
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Successes cannot be greater than attempts",
        )

    await upsert_result(
        CompetitionResultInsertable(
            **body.model_dump(),
            discipline_id=discipline_id,
            updated=datetime_utc.now(),
        )
    )

    return CompetitionResultsResponse(
        data=await get_results(discipline_id)
    )


@router.post(
    "/tournaments/{tournament_id}/competitions/{competition_id}/disciplines/{discipline_id}/calculate",
    response_model=CompetitionRankedResultsResponse,
)
async def calculate_competition_results(
    tournament_id: TournamentId,
    competition_id: CompetitionId,
    discipline_id: CompetitionDisciplineId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> CompetitionRankedResultsResponse:

    competition = await get_competition(
        tournament_id,
        competition_id,
    )

    if competition is None:
        raise competition_not_found()

    discipline = await get_discipline(
        competition_id,
        discipline_id,
    )

    if discipline is None:
        raise discipline_not_found()

    results = await get_results(
        discipline_id
    )

    scoring = await get_scoring(
        competition_id
    )

    ranked = rank_results(
        discipline,
        results,
        scoring,
    )

    for item in ranked:
        await update_result_place(
            item.result.id,
            item.place,
        )

    return CompetitionRankedResultsResponse(
        data=[
            CompetitionRankedResult(
                result=item.result,
                place=item.place,
                points=item.points,
                tied=item.tied,
            )
            for item in ranked
        ]
    )
