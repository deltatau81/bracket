from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import HTTPException

from bracket.database import database
from bracket.models.db.match import Match
from bracket.models.db.tournament import Tournament, TournamentStatus
from bracket.utils.id_types import MatchId, TournamentId


@asynccontextmanager
async def match_write_context(
    tournament_id: TournamentId, match_id: MatchId
) -> AsyncIterator[tuple[Tournament, Match]]:
    """Serialize score, event and phase writes and their stage ranking updates.

    Lock order: tournament, match, events, ranking rows. The tournament lock also
    prevents archive/rule updates during a confirmation and serializes rankings
    for different matches of the same tournament. Locks last for this transaction
    only, including for a read-only preview; never across preview/confirmation.
    """
    async with database.transaction():
        tournament_row = await database.fetch_one(
            "SELECT * FROM tournaments WHERE id = :id FOR UPDATE",
            {"id": tournament_id},
        )
        if tournament_row is None:
            raise HTTPException(404, "Tournament not found")
        tournament = Tournament.model_validate(tournament_row)
        if tournament.status is TournamentStatus.ARCHIVED:
            raise HTTPException(400, "Can't update archived tournament")
        match_row = await database.fetch_one(
            """
                SELECT matches.* FROM matches
                JOIN rounds ON rounds.id = matches.round_id
                JOIN stage_items ON stage_items.id = rounds.stage_item_id
                JOIN stages ON stages.id = stage_items.stage_id
                WHERE matches.id = :match_id AND stages.tournament_id = :tournament_id
                FOR UPDATE OF matches
            """,
            {"match_id": match_id, "tournament_id": tournament_id},
        )
        if match_row is None:
            raise HTTPException(404, "Match not found in this tournament")
        yield tournament, Match.model_validate(match_row)
