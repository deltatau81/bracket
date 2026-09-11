from bracket.database import database
from bracket.models.db.tournament_sponsor import (
    TournamentSponsor,
    TournamentSponsorCreateBody,
    TournamentSponsorUpdateBody,
)
from bracket.schema import tournament_sponsors
from bracket.utils.db import fetch_all_parsed, fetch_one_parsed
from bracket.utils.id_types import TournamentId, TournamentSponsorId


async def get_tournament_sponsors(tournament_id: TournamentId) -> list[TournamentSponsor]:
    return await fetch_all_parsed(
        database,
        TournamentSponsor,
        tournament_sponsors.select()
        .where(tournament_sponsors.c.tournament_id == tournament_id)
        .order_by(
            tournament_sponsors.c.position,
            tournament_sponsors.c.sort_order,
            tournament_sponsors.c.id,
        ),
    )


async def get_tournament_sponsor(
    tournament_id: TournamentId, sponsor_id: TournamentSponsorId
) -> TournamentSponsor | None:
    return await fetch_one_parsed(
        database,
        TournamentSponsor,
        tournament_sponsors.select().where(
            (tournament_sponsors.c.id == sponsor_id)
            & (tournament_sponsors.c.tournament_id == tournament_id)
        ),
    )


async def create_tournament_sponsor(
    tournament_id: TournamentId, body: TournamentSponsorCreateBody
) -> TournamentSponsorId:
    sponsor_id = await database.execute(
        tournament_sponsors.insert(),
        values={**body.model_dump(), "tournament_id": tournament_id},
    )
    return TournamentSponsorId(sponsor_id)


async def update_tournament_sponsor(
    tournament_id: TournamentId,
    sponsor_id: TournamentSponsorId,
    body: TournamentSponsorUpdateBody,
) -> None:
    await database.execute(
        tournament_sponsors.update()
        .where(
            (tournament_sponsors.c.id == sponsor_id)
            & (tournament_sponsors.c.tournament_id == tournament_id)
        )
        .values(**body.model_dump(), url=body.url)
    )


async def delete_tournament_sponsor(
    tournament_id: TournamentId, sponsor_id: TournamentSponsorId
) -> None:
    await database.execute(
        tournament_sponsors.delete().where(
            (tournament_sponsors.c.id == sponsor_id)
            & (tournament_sponsors.c.tournament_id == tournament_id)
        )
    )
