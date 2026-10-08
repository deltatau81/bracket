import hmac

from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from bracket.config import config
from bracket.logic.match_phase import (
    MatchPhaseTransitionError,
    transition_match_phase,
)
from bracket.logic.permissions import validate_match_update_permissions
from bracket.logic.planning.conflicts import handle_conflicts
from bracket.logic.planning.matches import (
    get_scheduled_matches,
    handle_match_reschedule,
    reorder_matches_for_court,
    schedule_all_unscheduled_matches,
)
from bracket.logic.ranking.calculation import (
    recalculate_ranking_for_stage_item,
)
from bracket.logic.ranking.elimination import update_inputs_in_subsequent_elimination_rounds
from bracket.logic.scheduling.upcoming_matches import (
    get_draft_round_in_stage_item,
    get_upcoming_matches_for_swiss,
)
from bracket.logic.score_source import (
    ALL_SCORE_FIELDS,
    build_source_preview,
    match_participants,
    save_score_source,
    section_scores,
)
from bracket.models.db.account import UserAccountType
from bracket.models.db.match import (
    Match,
    MatchCreateBody,
    MatchCreateBodyFrontend,
    MatchFilter,
    MatchPhaseAction,
    MatchPhaseBody,
    MatchRescheduleBody,
    MatchStatus,
    MatchUpdateBody,
)
from bracket.models.db.score_source import (
    ScoreSourceConfirmation,
    ScoreSourceConfirmBody,
    ScoreSourcePreview,
    ScoreSourcePreviewBody,
)
from bracket.models.db.stage_item import StageType
from bracket.models.db.tournament import Tournament
from bracket.models.db.user import UserPublic
from bracket.routes.auth import (
    oauth2_scheme,
    user_authenticated_for_tournament,
    user_authenticated_for_tournament_admin,
)
from bracket.routes.models import (
    DataResponse,
    SingleMatchResponse,
    SuccessResponse,
    UpcomingMatchesResponse,
)
from bracket.routes.util import disallow_archived_tournament, match_dependency
from bracket.sql.courts import get_all_courts_in_tournament
from bracket.sql.match_events import get_match_events
from bracket.sql.match_write import match_write_context
from bracket.sql.matches import (
    ScoreEntrySourceConflictError,
    sql_create_match,
    sql_delete_match,
    sql_get_match,
    sql_transition_match_phase,
    sql_update_match,
    sql_update_match_results,
)
from bracket.sql.rounds import get_round_by_id
from bracket.sql.stage_items import get_stage_item
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.tournaments import sql_get_tournament
from bracket.sql.validation import check_foreign_keys_belong_to_tournament
from bracket.utils.id_types import MatchId, StageItemId, TournamentId
from bracket.utils.types import assert_some

router = APIRouter(prefix=config.api_prefix)


@router.get(
    "/tournaments/{tournament_id}/stage_items/{stage_item_id}/upcoming_matches",
    response_model=UpcomingMatchesResponse,
)
async def get_matches_to_schedule(
    tournament_id: TournamentId,
    stage_item_id: StageItemId,
    elo_diff_threshold: int = 200,
    iterations: int = 2_000,
    only_recommended: bool = False,
    limit: int = 50,
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> UpcomingMatchesResponse:
    match_filter = MatchFilter(
        elo_diff_threshold=elo_diff_threshold,
        only_recommended=only_recommended,
        limit=limit,
        iterations=iterations,
    )

    draft_round, stage_item = await get_draft_round_in_stage_item(tournament_id, stage_item_id)
    courts = await get_all_courts_in_tournament(tournament_id)
    if len(courts) <= len(draft_round.matches):
        return UpcomingMatchesResponse(data=[])

    return UpcomingMatchesResponse(
        data=get_upcoming_matches_for_swiss(match_filter, stage_item, draft_round)
    )


@router.delete("/tournaments/{tournament_id}/matches/{match_id}", response_model=SuccessResponse)
async def delete_match(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament_admin),
    __: Tournament = Depends(disallow_archived_tournament),
    match: Match = Depends(match_dependency),
) -> SuccessResponse:
    round_ = await get_round_by_id(tournament_id, match.round_id)
    stage_item = await get_stage_item(tournament_id, round_.stage_item_id)

    if not round_.is_draft or stage_item.type != StageType.SWISS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only delete matches from draft rounds in Swiss stage items",
        )

    await sql_delete_match(match.id)

    stage_item = await get_stage_item(tournament_id, round_.stage_item_id)

    await recalculate_ranking_for_stage_item(tournament_id, stage_item)
    return SuccessResponse()


@router.post("/tournaments/{tournament_id}/matches", response_model=SingleMatchResponse)
async def create_match(
    tournament_id: TournamentId,
    match_body: MatchCreateBodyFrontend,
    _: UserPublic = Depends(user_authenticated_for_tournament_admin),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SingleMatchResponse:
    await check_foreign_keys_belong_to_tournament(match_body, tournament_id)

    round_ = await get_round_by_id(tournament_id, match_body.round_id)
    stage_item = await get_stage_item(tournament_id, round_.stage_item_id)

    if not round_.is_draft or stage_item.type != StageType.SWISS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only create matches in draft rounds of Swiss stage items",
        )

    tournament = await sql_get_tournament(tournament_id)
    body_with_durations = MatchCreateBody(
        **match_body.model_dump(),
        duration_minutes=tournament.duration_minutes,
        margin_minutes=tournament.margin_minutes,
    )

    return SingleMatchResponse(
        data=await sql_create_match(body_with_durations, tournament.hockey_mode)
    )


@router.post("/tournaments/{tournament_id}/schedule_matches", response_model=SuccessResponse)
async def schedule_matches(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament_admin),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    stages = await get_full_tournament_details(tournament_id)
    await schedule_all_unscheduled_matches(tournament_id, stages)
    return SuccessResponse()


@router.post(
    "/tournaments/{tournament_id}/matches/{match_id}/reschedule", response_model=SuccessResponse
)
async def reschedule_match(
    tournament_id: TournamentId,
    match_id: MatchId,
    body: MatchRescheduleBody,
    tournament: Tournament = Depends(disallow_archived_tournament),
    _: UserPublic = Depends(user_authenticated_for_tournament_admin),
) -> SuccessResponse:
    await check_foreign_keys_belong_to_tournament(body, tournament_id)
    await handle_match_reschedule(tournament, body, match_id)
    await handle_conflicts(await get_full_tournament_details(tournament_id))
    return SuccessResponse()


@router.post(
    "/tournaments/{tournament_id}/matches/{match_id}/phase",
    response_model=SingleMatchResponse,
)
async def transition_match_phase_by_id(
    tournament_id: TournamentId,
    match_id: MatchId,
    body: MatchPhaseBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    tournament: Tournament = Depends(disallow_archived_tournament),
    match: Match = Depends(match_dependency),
) -> SingleMatchResponse:
    async with match_write_context(tournament_id, match_id) as (locked_tournament, locked_match):
        tournament = locked_tournament
        match = locked_match
        try:
            next_state = transition_match_phase(
                match.status,
                match.active_period,
                match.phase_state,
                tournament.hockey_mode,
                body.action,
            )
        except MatchPhaseTransitionError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error

        updated_match = await sql_transition_match_phase(
            match.id,
            match.status,
            match.active_period,
            match.phase_state,
            next_state,
        )
        if updated_match is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Match phase changed concurrently; reload the match and try again",
            )

        if body.action in {MatchPhaseAction.FINISH_MATCH, MatchPhaseAction.REOPEN_MATCH}:
            round_ = await get_round_by_id(tournament_id, match.round_id)
            stage_item = await get_stage_item(tournament_id, round_.stage_item_id)
            await recalculate_ranking_for_stage_item(tournament_id, stage_item)
            if stage_item.type == StageType.SINGLE_ELIMINATION:
                await update_inputs_in_subsequent_elimination_rounds(
                    round_.id,
                    stage_item,
                    {match_id},
                )

        return SingleMatchResponse(data=updated_match)


@router.put("/tournaments/{tournament_id}/matches/{match_id}", response_model=SuccessResponse)
async def update_match_by_id(
    tournament_id: TournamentId,
    match_id: MatchId,
    match_body: MatchUpdateBody,
    user: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
    match: Match = Depends(match_dependency),
) -> SuccessResponse:
    async with match_write_context(tournament_id, match_id) as (locked_tournament, locked_match):
        tournament = locked_tournament
        match = locked_match
        tournament = await sql_get_tournament(tournament_id)
        validate_match_update_permissions(user, match, match_body, tournament.hockey_mode)
        await check_foreign_keys_belong_to_tournament(match_body, tournament_id)

        if match_body.status is not None:
            allowed_transitions = {
                MatchStatus.PLANNED: {MatchStatus.PLANNED, MatchStatus.RUNNING},
                MatchStatus.RUNNING: {MatchStatus.RUNNING, MatchStatus.FINISHED},
                MatchStatus.FINISHED: {MatchStatus.FINISHED, MatchStatus.RUNNING},
            }
            if match_body.status not in allowed_transitions[match.status]:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"Invalid match status transition: {match.status} -> {match_body.status}"
                    ),
                )

        try:
            if user.account_type is UserAccountType.SCORER:
                await sql_update_match_results(match_id, match, match_body, tournament.hockey_mode)
            else:
                await sql_update_match(match_id, match_body, tournament)
        except ScoreEntrySourceConflictError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error),
            ) from error
        await handle_conflicts(await get_full_tournament_details(tournament_id))

        round_ = await get_round_by_id(tournament_id, match.round_id)
        stage_item = await get_stage_item(tournament_id, round_.stage_item_id)
        await recalculate_ranking_for_stage_item(tournament_id, stage_item)

        # Only reorder matches that do not have a fixed start_time.
        # Once a start_time exists, matches are scheduled independently.
        if (
            user.account_type is not UserAccountType.SCORER
            and match.start_time is None
            and match_body.start_time is None
            and (
                match_body.custom_duration_minutes != match.custom_duration_minutes
                or match_body.custom_margin_minutes != match.custom_margin_minutes
            )
        ):
            tournament = await sql_get_tournament(tournament_id)
            scheduled_matches = get_scheduled_matches(
                await get_full_tournament_details(tournament_id)
            )
            await reorder_matches_for_court(
                tournament, scheduled_matches, assert_some(match.court_id)
            )

        if stage_item.type == StageType.SINGLE_ELIMINATION:
            await update_inputs_in_subsequent_elimination_rounds(round_.id, stage_item, {match_id})

        return SuccessResponse()


SCORE_SOURCE_ERRORS = {
    400: {"description": "Tournament is archived"},
    401: {"description": "Authentication required"},
    403: {"description": "Administrative permission required; SCORER is forbidden"},
    404: {"description": "Match does not belong to the specified tournament"},
    409: {"description": "Preview is stale; request a new preview"},
    422: {"description": "Invalid target/token or STANDARD tournament"},
}


@router.post(
    "/tournaments/{tournament_id}/matches/{match_id}/score-source/preview",
    response_model=DataResponse[ScoreSourcePreview],
    responses=SCORE_SOURCE_ERRORS,
)
async def preview_match_score_source(
    tournament_id: TournamentId,
    match_id: MatchId,
    body: ScoreSourcePreviewBody,
    _: UserPublic = Depends(user_authenticated_for_tournament_admin),
    token: str = Depends(oauth2_scheme),
) -> DataResponse[ScoreSourcePreview]:
    """Read-only preview; locks are released before responding.

    EVENTS fully recounts GOALs in GAME/HALF1/HALF2/SHOOTOUT as appropriate.
    MANUAL preserves scores. Existing events are never modified. An already
    active target is a no-op. Null is allowed only as an existing source.
    """
    async with match_write_context(tournament_id, match_id) as (tournament, match):
        await user_authenticated_for_tournament_admin(tournament_id, token)
        preview, _scores = build_source_preview(
            match,
            tournament,
            await get_match_events(match_id),
            await match_participants(match_id),
            body.target_source,
        )
        return DataResponse(data=preview)


@router.post(
    "/tournaments/{tournament_id}/matches/{match_id}/score-source/confirm",
    response_model=DataResponse[ScoreSourceConfirmation],
    responses=SCORE_SOURCE_ERRORS,
)
async def confirm_match_score_source(
    tournament_id: TournamentId,
    match_id: MatchId,
    body: ScoreSourceConfirmBody,
    _: UserPublic = Depends(user_authenticated_for_tournament_admin),
    token: str = Depends(oauth2_scheme),
) -> DataResponse[ScoreSourceConfirmation]:
    """Confirm exactly the previewed state; no automatic retry.

    Source, scores and existing stage-ranking updates commit together.
    A changed source, score, GOAL, phase or tournament configuration invalidates
    the token (409). Same-source confirmations validate the token but never
    recount scores. A token cannot be used for another match or target.
    Database failures roll back the entire operation.
    """
    async with match_write_context(tournament_id, match_id) as (tournament, match):
        await user_authenticated_for_tournament_admin(tournament_id, token)
        preview, scores = build_source_preview(
            match,
            tournament,
            await get_match_events(match_id),
            await match_participants(match_id),
            body.target_source,
        )
        if not hmac.compare_digest(preview.conflict_token, body.conflict_token):
            raise HTTPException(409, "Score source preview is stale; request a new preview")
        if match.score_entry_source is not body.target_source:
            await save_score_source(match_id, body.target_source, scores)
            round_ = await get_round_by_id(tournament_id, match.round_id)
            stage_item = await get_stage_item(tournament_id, round_.stage_item_id)
            await recalculate_ranking_for_stage_item(tournament_id, stage_item)
            if stage_item.type == StageType.SINGLE_ELIMINATION:
                await update_inputs_in_subsequent_elimination_rounds(
                    round_.id,
                    stage_item,
                    {match_id},
                )
        updated = await sql_get_match(match_id)
        return DataResponse(
            data=ScoreSourceConfirmation(
                match=updated,
                active_source=body.target_source,
                current_scores=section_scores(
                    {field: getattr(updated, field) for field in ALL_SCORE_FIELDS},
                    tournament.hockey_mode,
                ),
            )
        )
