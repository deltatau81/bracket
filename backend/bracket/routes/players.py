from fastapi import APIRouter, Depends

from bracket.config import config
from bracket.database import database
from bracket.logic.subscriptions import check_requirement
from bracket.models.db.player import Player, PlayerBody, PlayerMultiBody
from bracket.models.db.player_x_team import PlayerTeamUpdateBody
from bracket.models.db.tournament import Tournament
from bracket.models.db.user import UserPublic
from bracket.routes.auth import (
    user_authenticated_for_tournament,
    user_authenticated_or_public_dashboard,
)
from bracket.routes.models import (
    CreatedPlayerResponse,
    PaginatedPlayers,
    PlayerStatisticsResponse,
    PlayersResponse,
    SinglePlayerResponse,
    SuccessResponse,
)
from bracket.routes.util import disallow_archived_tournament
from bracket.schema import players, players_x_teams, teams
from bracket.sql.players import (
    get_all_players_in_tournament,
    get_player_count,
    insert_player,
    sql_delete_player,
)
from bracket.sql.player_statistics import get_player_statistics
from bracket.utils.db import fetch_one_parsed
from bracket.utils.id_types import PlayerId, TournamentId
from bracket.utils.pagination import PaginationPlayers
from bracket.utils.types import assert_some

router = APIRouter(prefix=config.api_prefix)


@router.get(
    "/tournaments/{tournament_id}/player_statistics",
    response_model=PlayerStatisticsResponse,
)
async def player_statistics(
    tournament_id: TournamentId,
    _: UserPublic | None = Depends(user_authenticated_or_public_dashboard),
) -> PlayerStatisticsResponse:
    return PlayerStatisticsResponse(data=await get_player_statistics(tournament_id))


@router.get("/tournaments/{tournament_id}/players", response_model=PlayersResponse)
async def get_players(
    tournament_id: TournamentId,
    not_in_team: bool = False,
    pagination: PaginationPlayers = Depends(),
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> PlayersResponse:
    return PlayersResponse(
        data=PaginatedPlayers(
            players=await get_all_players_in_tournament(
                tournament_id, not_in_team=not_in_team, pagination=pagination
            ),
            count=await get_player_count(tournament_id, not_in_team=not_in_team),
        )
    )


@router.put("/tournaments/{tournament_id}/players/{player_id}", response_model=SinglePlayerResponse)
async def update_player_by_id(
    tournament_id: TournamentId,
    player_id: PlayerId,
    player_body: PlayerBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SinglePlayerResponse:
    player_values = player_body.model_dump()
    for name_field in ("first_name", "last_name"):
        if name_field in player_body.model_fields_set:
            player_values[name_field] = getattr(player_body, name_field)
    await database.execute(
        query=players.update().where(
            (players.c.id == player_id) & (players.c.tournament_id == tournament_id)
        ),
        values=player_values,
    )
    return SinglePlayerResponse(
        data=assert_some(
            await fetch_one_parsed(
                database,
                Player,
                players.select().where(
                    (players.c.id == player_id) & (players.c.tournament_id == tournament_id)
                ),
            )
        )
    )


@router.put(
    "/tournaments/{tournament_id}/players/{player_id}/team",
    response_model=SuccessResponse,
)
async def update_player_team(
    tournament_id: TournamentId,
    player_id: PlayerId,
    body: PlayerTeamUpdateBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    player_exists = await database.fetch_one(
        players.select().where(
            (players.c.id == player_id)
            & (players.c.tournament_id == tournament_id)
        )
    )
    if player_exists is None:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found",
        )

    if body.team_id is not None:
        team_exists = await database.fetch_one(
            teams.select().where(
                (teams.c.id == body.team_id)
                & (teams.c.tournament_id == tournament_id)
            )
        )
        if team_exists is None:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found",
            )

    async with database.transaction():
        await database.execute(
            players_x_teams.delete().where(
                players_x_teams.c.player_id == player_id
            )
        )

        if body.team_id is not None:
            await database.execute(
                players_x_teams.insert(),
                values={
                    "player_id": player_id,
                    "team_id": body.team_id,
                    "number": body.number,
                    "position": body.position,
                },
            )

    return SuccessResponse()


@router.delete("/tournaments/{tournament_id}/players/{player_id}", response_model=SuccessResponse)
async def delete_player(
    tournament_id: TournamentId,
    player_id: PlayerId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    await sql_delete_player(tournament_id, player_id)
    return SuccessResponse()


@router.post("/tournaments/{tournament_id}/players", response_model=CreatedPlayerResponse)
async def create_single_player(
    player_body: PlayerBody,
    tournament_id: TournamentId,
    user: UserPublic = Depends(user_authenticated_for_tournament),
    _: Tournament = Depends(disallow_archived_tournament),
) -> CreatedPlayerResponse:
    existing_players = await get_all_players_in_tournament(tournament_id)
    check_requirement(existing_players, user, "max_players")
    return CreatedPlayerResponse(data=await insert_player(player_body, tournament_id))


@router.post("/tournaments/{tournament_id}/players_multi", response_model=SuccessResponse)
async def create_multiple_players(
    player_body: PlayerMultiBody,
    tournament_id: TournamentId,
    user: UserPublic = Depends(user_authenticated_for_tournament),
    _: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    player_names = [player.strip() for player in player_body.names.split("\n") if len(player) > 0]
    existing_players = await get_all_players_in_tournament(tournament_id)
    check_requirement(existing_players, user, "max_players", additions=len(player_names))

    for player_name in player_names:
        await insert_player(PlayerBody(name=player_name, active=player_body.active), tournament_id)

    return SuccessResponse()
