from decimal import Decimal
from enum import auto

from heliclockter import datetime_utc
from pydantic import Field

from bracket.models.db.shared import BaseModelORM
from bracket.utils.id_types import (
    CompetitionDisciplineId,
    CompetitionId,
    CompetitionPairingId,
    CompetitionResultId,
    CompetitionScoringId,
    CourtId,
    TeamId,
    TournamentId,
)
from bracket.utils.types import EnumAutoStr


class CompetitionMetricType(EnumAutoStr):
    TIME = auto()
    COUNT = auto()
    RATIO = auto()
    MANUAL = auto()


class CompetitionBody(BaseModelORM):
    name: str
    description: str | None = None
    start_time: datetime_utc
    duration_minutes: int = Field(..., ge=1)
    court_id: CourtId | None = None


class CompetitionInsertable(CompetitionBody):
    tournament_id: TournamentId
    created: datetime_utc


class Competition(CompetitionInsertable):
    id: CompetitionId


class CompetitionDisciplineBody(BaseModelORM):
    name: str
    description: str | None = None
    metric_type: CompetitionMetricType = CompetitionMetricType.MANUAL
    sort_order: int = 0


class CompetitionDisciplineInsertable(CompetitionDisciplineBody):
    competition_id: CompetitionId
    created: datetime_utc


class CompetitionDiscipline(CompetitionDisciplineInsertable):
    id: CompetitionDisciplineId


class CompetitionScoringBody(BaseModelORM):
    place: int = Field(..., ge=1)
    points: Decimal = Field(..., ge=0)


class CompetitionScoringInsertable(CompetitionScoringBody):
    competition_id: CompetitionId


class CompetitionScoring(CompetitionScoringInsertable):
    id: CompetitionScoringId


class CompetitionResultBody(BaseModelORM):
    team_id: TeamId
    place: int | None = Field(default=None, ge=1)
    time_ms: int | None = Field(default=None, ge=0)
    attempts: int | None = Field(default=None, ge=0)
    successes: int | None = Field(default=None, ge=0)
    notes: str | None = None


class CompetitionResultInsertable(CompetitionResultBody):
    discipline_id: CompetitionDisciplineId
    updated: datetime_utc


class CompetitionResult(CompetitionResultInsertable):
    id: CompetitionResultId

class CompetitionRankedResult(BaseModelORM):
    result: CompetitionResult
    place: int
    points: Decimal
    tied: bool

class CompetitionPairingBody(BaseModelORM):
    shooter_team_id: TeamId | None = None
    goalkeeper_team_id: TeamId | None = None
    shooter_name: str | None = None
    goalkeeper_name: str | None = None
    sort_order: int = 0
    notes: str | None = None


class CompetitionPairingInsertable(CompetitionPairingBody):
    discipline_id: CompetitionDisciplineId


class CompetitionPairing(CompetitionPairingInsertable):
    id: CompetitionPairingId


class CompetitionStanding(BaseModelORM):
    team_id: TeamId
    points: Decimal


class TournamentOverallStanding(BaseModelORM):
    team_id: TeamId
    team_name: str
    game_points: Decimal
    competition_points: Decimal
    total_points: Decimal
