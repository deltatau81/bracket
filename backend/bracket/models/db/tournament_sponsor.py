from typing import Literal

from bracket.models.db.shared import BaseModelORM
from bracket.utils.id_types import TournamentId, TournamentSponsorId

SponsorPosition = Literal["LEFT", "RIGHT"]


class TournamentSponsorCreateBody(BaseModelORM):
    name: str
    logo_path: str
    url: str | None = None
    position: SponsorPosition
    sort_order: int = 0


class TournamentSponsorUpdateBody(TournamentSponsorCreateBody):
    pass


class TournamentSponsor(TournamentSponsorCreateBody):
    id: TournamentSponsorId
    tournament_id: TournamentId
