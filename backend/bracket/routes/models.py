from typing import Generic, TypeVar

from pydantic import BaseModel

from bracket.logic.penalty_catalog import PenaltyCatalog
from bracket.logic.scheduling.handle_stage_activation import StageItemInputUpdate
from bracket.models.db.club import Club
from bracket.models.db.court import Court
from bracket.models.db.match import Match, SuggestedMatch
from bracket.models.db.match_event import MatchEvent
from bracket.models.db.player import Player
from bracket.models.db.ranking import Ranking
from bracket.models.db.stage_item_inputs import (
    StageItemInputOptionFinal,
    StageItemInputOptionTentative,
)
from bracket.models.db.team import FullTeamWithPlayers, Team
from bracket.models.db.tournament import Tournament
from bracket.models.db.tournament_sponsor import TournamentSponsor
from bracket.models.db.user import UserPublic
from bracket.models.db.util import StageWithStageItems
from bracket.routes.auth import Token
from bracket.utils.id_types import StageId, StageItemId
from bracket.models.db.competition import (
    Competition,
    CompetitionDiscipline,
    CompetitionScoring,
    CompetitionResult,
    CompetitionRankedResult,
    TournamentOverallStanding,
)

DataT = TypeVar("DataT")


class SuccessResponse(BaseModel):
    success: bool = True


class DataResponse(BaseModel, Generic[DataT]):
    data: DataT


class ClubsResponse(DataResponse[list[Club]]):
    pass


class ClubResponse(DataResponse[Club | None]):
    pass


class TournamentResponse(DataResponse[Tournament]):
    pass


class TournamentsResponse(DataResponse[list[Tournament]]):
    pass


class TournamentSponsorResponse(DataResponse[TournamentSponsor]):
    pass


class TournamentSponsorsResponse(DataResponse[list[TournamentSponsor]]):
    pass


class PaginatedPlayers(BaseModel):
    count: int
    players: list[Player]


class PlayersResponse(DataResponse[PaginatedPlayers]):
    pass


class SinglePlayerResponse(DataResponse[Player]):
    pass


class CreatedPlayerResponse(SinglePlayerResponse):
    success: bool = True


class StagesWithStageItemsResponse(DataResponse[list[StageWithStageItems]]):
    pass


class UpcomingMatchesResponse(DataResponse[list[SuggestedMatch]]):
    pass


class SingleMatchResponse(DataResponse[Match]):
    pass


class MatchEventsResponse(DataResponse[list[MatchEvent]]):
    pass


class PenaltyCatalogResponse(DataResponse[PenaltyCatalog]):
    pass


class SingleMatchEventResponse(DataResponse[MatchEvent]):
    pass


class PaginatedTeams(BaseModel):
    count: int
    teams: list[FullTeamWithPlayers]


class TeamsWithPlayersResponse(DataResponse[PaginatedTeams]):
    pass


class SingleTeamResponse(DataResponse[Team]):
    pass


class UserPublicResponse(DataResponse[UserPublic]):
    pass



class UsersResponse(DataResponse[list[UserPublic]]):
    pass


class TokenResponse(DataResponse[Token]):
    pass


class CourtsResponse(DataResponse[list[Court]]):
    pass


class SingleCourtResponse(DataResponse[Court]):
    pass


class RankingsResponse(DataResponse[list[Ranking]]):
    pass


class StageItemInputOptionsResponse(
    DataResponse[dict[StageId, list[StageItemInputOptionTentative | StageItemInputOptionFinal]]]
):
    pass


class StageRankingResponse(DataResponse[dict[StageItemId, list[StageItemInputUpdate]]]):
    pass

class CompetitionsResponse(DataResponse[list[Competition]]):
    pass


class CompetitionResponse(DataResponse[Competition]):
    pass

class CompetitionDisciplinesResponse(
    DataResponse[list[CompetitionDiscipline]]
):
    pass


class CompetitionDisciplineResponse(
    DataResponse[CompetitionDiscipline]
):
    pass


class CompetitionScoringResponse(
    DataResponse[list[CompetitionScoring]]
):
    pass
class CompetitionResultsResponse(
    DataResponse[list[CompetitionResult]]
):
    pass


class CompetitionRankedResultsResponse(
    DataResponse[list[CompetitionRankedResult]]
):
    pass


class TournamentOverallStandingsResponse(
    DataResponse[list[TournamentOverallStanding]]
):
    pass
