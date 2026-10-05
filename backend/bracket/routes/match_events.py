from fastapi import APIRouter, Depends, HTTPException
from heliclockter import datetime_utc
from starlette import status

from bracket.database import database
from bracket.logic.match_rules import get_effective_match_rules
from bracket.logic.penalty_catalog import (
    PenaltyCatalog,
    PenaltyType,
    UnsupportedPenaltyCatalogError,
    get_penalty_catalog,
)
from bracket.models.db.match import Match, MatchPhaseState, MatchStatus
from bracket.models.db.match_event import (
    MatchEvent,
    MatchEventBody,
    MatchEventInsertable,
    MatchEventPeriod,
    MatchEventType,
)
from bracket.models.db.tournament import HockeyMode, Tournament
from bracket.models.db.user import UserPublic
from bracket.routes.auth import (
    user_authenticated_for_tournament,
    user_authenticated_or_public_dashboard,
)
from bracket.routes.models import (
    MatchEventsResponse,
    PenaltyCatalogResponse,
    SingleMatchEventResponse,
    SuccessResponse,
)
from bracket.routes.util import disallow_archived_tournament
from bracket.sql.match_events import (
    adjust_goal_score,
    create_match_event,
    delete_match_event,
    get_match_event,
    get_match_events,
    get_match_team_ids,
    get_player_snapshot,
    get_tournament_match_events,
    recalculate_youth_club_game_score,
    update_match_event,
    youth_club_game_score_uses_events,
)
from bracket.sql.matches import sql_get_match
from bracket.sql.tournaments import sql_get_tournament
from bracket.utils.id_types import MatchEventId, MatchId, PlayerId, TournamentId

router = APIRouter()

ALLOWED_EVENT_PERIODS = {
    HockeyMode.COMPETITION: {
        MatchEventPeriod.HALF1,
        MatchEventPeriod.HALF2,
        MatchEventPeriod.SHOOTOUT,
    },
    HockeyMode.STANDARD: {
        MatchEventPeriod.PERIOD1,
        MatchEventPeriod.PERIOD2,
        MatchEventPeriod.PERIOD3,
        MatchEventPeriod.OVERTIME,
    },
    HockeyMode.GAME_SHOOTOUT: {
        MatchEventPeriod.GAME,
        MatchEventPeriod.SHOOTOUT,
    },
}


async def validate_match_and_team(
    tournament_id: TournamentId,
    match_id: MatchId,
    event_body: MatchEventBody | None = None,
    *,
    validate_period: bool = True,
) -> None:
    team_ids = await get_match_team_ids(tournament_id, match_id)
    if team_ids is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not find match with id {match_id}",
        )
    if event_body is not None and event_body.team_id not in team_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Event team is not a resolved participant of this match",
        )
    if event_body is not None and validate_period:
        tournament = await sql_get_tournament(tournament_id)
        if event_body.period not in ALLOWED_EVENT_PERIODS[tournament.hockey_mode]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Period {event_body.period.value} is not allowed for "
                    f"{tournament.hockey_mode.value} tournaments"
                ),
            )


async def apply_player_snapshots(event_body: MatchEventBody) -> MatchEventBody:
    snapshot_updates: dict[str, object] = {}
    player_fields: tuple[tuple[str, PlayerId | None], ...] = (
        ("player", event_body.player_id),
        ("assist1", event_body.assist1_player_id),
        ("assist2", event_body.assist2_player_id),
    )
    for prefix, player_id in player_fields:
        if player_id is None:
            continue
        snapshot = await get_player_snapshot(player_id, event_body.team_id)
        if snapshot is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Player {player_id} does not belong to event team {event_body.team_id}",
            )
        player_name, player_number = snapshot
        snapshot_updates[f"{prefix}_name"] = player_name
        snapshot_updates[f"{prefix}_number"] = player_number
    return event_body.model_copy(update=snapshot_updates)


def effective_penalty_catalog(match: Match, tournament: Tournament) -> PenaltyCatalog:
    effective_rules = get_effective_match_rules(match, tournament)
    try:
        return get_penalty_catalog(
            effective_rules.ruleset,
            effective_rules.ruleset_season,
            effective_rules.age_category,
        )
    except UnsupportedPenaltyCatalogError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error


def apply_penalty_snapshot(
    event_body: MatchEventBody,
    catalog: PenaltyCatalog,
) -> MatchEventBody:
    if event_body.event_type is not MatchEventType.PENALTY or event_body.penalty_code is None:
        return event_body

    definition = next(
        (
            candidate
            for candidate in catalog.penalties
            if candidate.code == event_body.penalty_code
        ),
        None,
    )
    if definition is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown penalty code {event_body.penalty_code}",
        )

    try:
        selected_type = (
            PenaltyType(event_body.penalty_type)
            if event_body.penalty_type is not None
            else definition.default_penalty_type
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown penalty type {event_body.penalty_type}",
        ) from error

    if selected_type not in definition.allowed_penalty_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Penalty type {selected_type.value} is not allowed for "
                f"{definition.code}"
            ),
        )

    if definition.code == "OTHER":
        if not event_body.infraction:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="OTHER/CUSTOM penalties require a manual infraction",
            )
        return event_body.model_copy(
            update={
                "penalty_rule": None,
                "penalty_type": selected_type.value,
                "game_misconduct": event_body.game_misconduct or False,
            }
        )

    if selected_type is PenaltyType.CUSTOM:
        return event_body.model_copy(
            update={
                "penalty_code": definition.code,
                "penalty_rule": definition.rule,
                "penalty_type": selected_type.value,
                "infraction": definition.label,
                "game_misconduct": event_body.game_misconduct or False,
            }
        )

    type_definition = next(
        definition
        for definition in catalog.penalty_types
        if definition.type is selected_type
    )
    return event_body.model_copy(
        update={
            "penalty_code": definition.code,
            "penalty_rule": definition.rule,
            "penalty_type": selected_type.value,
            "penalty_minutes": type_definition.minutes,
            "infraction": definition.label,
            "game_misconduct": type_definition.game_misconduct,
        }
    )


def validate_game_time(event_body: MatchEventBody, tournament: Tournament) -> None:
    if event_body.game_time_seconds is not None:
        return
    if (
        event_body.event_type is MatchEventType.GOAL
        and tournament.hockey_mode in {HockeyMode.COMPETITION, HockeyMode.GAME_SHOOTOUT}
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="Game time is required for this event",
    )


async def event_or_404(match_id: MatchId, event_id: MatchEventId) -> MatchEvent:
    event = await get_match_event(match_id, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not find match event with id {event_id}",
        )

    return event


async def apply_goal_contribution(event: MatchEventBody, match_id: MatchId, delta: int) -> None:
    if event.event_type is not MatchEventType.GOAL:
        return
    if not await adjust_goal_score(match_id, event.team_id, event.period, delta):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Could not adjust goal score; verify the participant and that the score "
                "cannot become negative"
            ),
        )


@router.get(
    "/tournaments/{tournament_id}/events",
    response_model=MatchEventsResponse,
)
async def list_tournament_match_events(
    tournament_id: TournamentId,
    _: UserPublic | None = Depends(user_authenticated_or_public_dashboard),
) -> MatchEventsResponse:
    return MatchEventsResponse(data=await get_tournament_match_events(tournament_id))


@router.get(
    "/tournaments/{tournament_id}/matches/{match_id}/penalties/catalog",
    response_model=PenaltyCatalogResponse,
)
async def get_match_penalty_catalog(
    tournament_id: TournamentId,
    match_id: MatchId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> PenaltyCatalogResponse:
    await validate_match_and_team(tournament_id, match_id)
    match = await sql_get_match(match_id)
    tournament = await sql_get_tournament(tournament_id)
    return PenaltyCatalogResponse(data=effective_penalty_catalog(match, tournament))


@router.get(
    "/tournaments/{tournament_id}/matches/{match_id}/events",
    response_model=MatchEventsResponse,
)
async def list_match_events(
    tournament_id: TournamentId,
    match_id: MatchId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> MatchEventsResponse:
    await validate_match_and_team(tournament_id, match_id)
    return MatchEventsResponse(data=await get_match_events(match_id))


@router.post(
    "/tournaments/{tournament_id}/matches/{match_id}/events",
    response_model=SingleMatchEventResponse,
)
async def create_event(
    tournament_id: TournamentId,
    match_id: MatchId,
    event_body: MatchEventBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SingleMatchEventResponse:
    await validate_match_and_team(
        tournament_id, match_id, event_body, validate_period=False
    )
    match = await sql_get_match(match_id)
    if (
        match.status is not MatchStatus.RUNNING
        or match.phase_state is not MatchPhaseState.ACTIVE
        or match.active_period is None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="New match events require a running match with an active period",
        )

    tournament = await sql_get_tournament(tournament_id)
    active_period = MatchEventPeriod(match.active_period.value)
    if active_period not in ALLOWED_EVENT_PERIODS[tournament.hockey_mode]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Period {active_period.value} is not allowed for "
                f"{tournament.hockey_mode.value} tournaments"
            ),
        )

    event_body = event_body.model_copy(update={"period": active_period})
    validate_game_time(event_body, tournament)
    event_body = await apply_player_snapshots(event_body)
    if event_body.event_type is MatchEventType.PENALTY and event_body.penalty_code is not None:
        event_body = apply_penalty_snapshot(
            event_body,
            effective_penalty_catalog(match, tournament),
        )
    event = MatchEventInsertable(
        **event_body.model_dump(), match_id=match_id, created=datetime_utc.now()
    )
    async with database.transaction():
        created_event = await create_match_event(event)
        if not (
            created_event.event_type is MatchEventType.GOAL
            and created_event.period is MatchEventPeriod.GAME
            and await recalculate_youth_club_game_score(match_id)
        ):
            await apply_goal_contribution(created_event, match_id, 1)

    return SingleMatchEventResponse(data=created_event)


@router.put(
    "/tournaments/{tournament_id}/matches/{match_id}/events/{event_id}",
    response_model=SingleMatchEventResponse,
)
async def update_event(
    tournament_id: TournamentId,
    match_id: MatchId,
    event_id: MatchEventId,
    event_body: MatchEventBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SingleMatchEventResponse:
    await validate_match_and_team(tournament_id, match_id, event_body)
    old_event = await event_or_404(match_id, event_id)
    event_body = await apply_player_snapshots(event_body)
    match = await sql_get_match(match_id)
    tournament = await sql_get_tournament(tournament_id)
    validate_game_time(event_body, tournament)
    if event_body.event_type is MatchEventType.PENALTY and event_body.penalty_code is not None:
        event_body = apply_penalty_snapshot(
            event_body,
            effective_penalty_catalog(match, tournament),
        )
    old_contribution = (old_event.event_type, old_event.team_id, old_event.period)
    new_contribution = (event_body.event_type, event_body.team_id, event_body.period)
    async with database.transaction():
        youth_game_event_changed = (
            old_contribution != new_contribution
            and await youth_club_game_score_uses_events(match_id)
            and (
                (
                    old_event.event_type is MatchEventType.GOAL
                    and old_event.period is MatchEventPeriod.GAME
                )
                or (
                    event_body.event_type is MatchEventType.GOAL
                    and event_body.period is MatchEventPeriod.GAME
                )
            )
        )
        if old_contribution != new_contribution and not youth_game_event_changed:
            await apply_goal_contribution(old_event, match_id, -1)
        event = await update_match_event(match_id, event_id, event_body)
        if youth_game_event_changed:
            await recalculate_youth_club_game_score(match_id)
        elif old_contribution != new_contribution:
            await apply_goal_contribution(event_body, match_id, 1)

    assert event is not None
    return SingleMatchEventResponse(data=event)


@router.delete(
    "/tournaments/{tournament_id}/matches/{match_id}/events/{event_id}",
    response_model=SuccessResponse,
)
async def delete_event(
    tournament_id: TournamentId,
    match_id: MatchId,
    event_id: MatchEventId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    await validate_match_and_team(tournament_id, match_id)
    event = await event_or_404(match_id, event_id)
    async with database.transaction():
        youth_game_goal = (
            event.event_type is MatchEventType.GOAL
            and event.period is MatchEventPeriod.GAME
            and await youth_club_game_score_uses_events(match_id)
        )
        if not youth_game_goal:
            await apply_goal_contribution(event, match_id, -1)
        deleted = await delete_match_event(match_id, event_id)
        if youth_game_goal:
            await recalculate_youth_club_game_score(match_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not find match event with id {event_id}",
        )
    return SuccessResponse()
