import aiofiles.os

from bracket.database import database
from bracket.sql.tournaments import (
    sql_delete_tournament_owned_data,
    sql_get_tournament,
)
from bracket.utils.id_types import TournamentId
from bracket.utils.logging import logger


async def get_tournament_logo_path(tournament_id: TournamentId) -> str | None:
    tournament = await sql_get_tournament(tournament_id)
    logo_path = f"static/tournament-logos/{tournament.logo_path}" if tournament.logo_path else None
    return logo_path if logo_path is not None and await aiofiles.os.path.exists(logo_path) else None


async def delete_tournament_logo(tournament_id: TournamentId) -> None:
    logo_path = await get_tournament_logo_path(tournament_id)
    if logo_path is not None:
        await aiofiles.os.remove(logo_path)


async def sql_delete_tournament_completely(tournament_id: TournamentId) -> None:
    logo_path = await get_tournament_logo_path(tournament_id)
    async with database.transaction():
        await sql_delete_tournament_owned_data(tournament_id)

    if logo_path is not None:
        try:
            await aiofiles.os.remove(logo_path)
        except OSError as exc:
            logger.error("Could not remove deleted tournament logo %s: %s", logo_path, exc)
