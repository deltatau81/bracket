from fastapi import APIRouter, Depends, HTTPException
from heliclockter import datetime_utc
from starlette import status

from bracket.models.db.match_event import MatchEventBody, MatchEventInsertable, MatchEventPeriod
from bracket.models.db.tournament import HockeyMode, Tournament
from bracket.models.db.user import UserPublic
from bracket.routes.auth import user_authenticated_for_tournament
from bracket.routes.models import MatchEventsResponse, SingleMatchEventResponse, SuccessResponse
from bracket.routes.util import disallow_archived_tournament
from bracket.sql.match_events import (
    create_match_event,
    delete_match_event,
    get_match_event,
    get_match_events,
    get_match_team_ids,
    get_player_snapshot,
    update_match_event,
)
from bracket.sql.tournaments import sql_get_tournament
from bracket.utils.id_types import MatchEventId, MatchId, PlayerId, TournamentId

router = APIRouter()


async def validate_match_and_team(
    tournament_id: TournamentId, match_id: MatchId, event_body: MatchEventBody | None = None
) -> None:
    team_ids = await get_match_team_ids(tournament_id, match_id)
    if team_ids is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not find match with id {match_id}",
        )
    if event_body is not None and event_body.team_id not in team_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Event team is not a resolved participant of this match",
        )
    if event_body is not None:
        tournament = await sql_get_tournament(tournament_id)
        allowed_periods = {
            HockeyMode.COMPETITION: {MatchEventPeriod.HALF1, MatchEventPeriod.HALF2},
            HockeyMode.STANDARD: {
                MatchEventPeriod.PERIOD1,
                MatchEventPeriod.PERIOD2,
                MatchEventPeriod.PERIOD3,
                MatchEventPeriod.OVERTIME,
            },
        }
        if event_body.period not in allowed_periods[tournament.hockey_mode]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Player {player_id} does not belong to event team {event_body.team_id}",
            )
        player_name, player_number = snapshot
        snapshot_updates[f"{prefix}_name"] = player_name
        snapshot_updates[f"{prefix}_number"] = player_number
    return event_body.model_copy(update=snapshot_updates)


async def event_or_404(match_id: MatchId, event_id: MatchEventId) -> None:
    if await get_match_event(match_id, event_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not find match event with id {event_id}",
        )


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
    await validate_match_and_team(tournament_id, match_id, event_body)
    event_body = await apply_player_snapshots(event_body)
    event = MatchEventInsertable(
        **event_body.model_dump(), match_id=match_id, created=datetime_utc.now()
    )
    return SingleMatchEventResponse(data=await create_match_event(event))


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
    await event_or_404(match_id, event_id)
    event_body = await apply_player_snapshots(event_body)
    event = await update_match_event(match_id, event_id, event_body)
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
    if not await delete_match_event(match_id, event_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not find match event with id {event_id}",
        )
    return SuccessResponse()
