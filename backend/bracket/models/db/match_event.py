from enum import auto

from heliclockter import datetime_utc
from pydantic import Field, model_validator

from bracket.models.db.shared import BaseModelORM
from bracket.utils.id_types import MatchEventId, MatchId, PlayerId, TeamId
from bracket.utils.types import EnumAutoStr


class MatchEventType(EnumAutoStr):
    GOAL = auto()
    PENALTY = auto()


class MatchEventPeriod(EnumAutoStr):
    GAME = auto()
    HALF1 = auto()
    HALF2 = auto()
    SHOOTOUT = auto()
    PERIOD1 = auto()
    PERIOD2 = auto()
    PERIOD3 = auto()
    OVERTIME = auto()


class MatchEventBody(BaseModelORM):
    team_id: TeamId
    event_type: MatchEventType
    period: MatchEventPeriod
    game_time_seconds: int | None = Field(default=None, ge=0)
    player_id: PlayerId | None = None
    player_number: int | None = Field(default=None, ge=0)
    player_name: str | None = None
    assist1_player_id: PlayerId | None = None
    assist1_number: int | None = Field(default=None, ge=0)
    assist1_name: str | None = None
    assist2_player_id: PlayerId | None = None
    assist2_number: int | None = Field(default=None, ge=0)
    assist2_name: str | None = None
    penalty_code: str | None = None
    penalty_rule: str | None = None
    penalty_type: str | None = None
    penalty_minutes: int | None = Field(default=None, ge=0)
    infraction: str | None = None
    game_misconduct: bool | None = None
    sort_order: int = 0

    @model_validator(mode="after")
    def validate_event_specific_fields(self) -> "MatchEventBody":
        assist_values = (
            self.assist1_player_id,
            self.assist1_number,
            self.assist1_name,
            self.assist2_player_id,
            self.assist2_number,
            self.assist2_name,
        )
        penalty_values = (
            self.penalty_code,
            self.penalty_rule,
            self.penalty_type,
            self.penalty_minutes,
            self.infraction,
            self.game_misconduct,
        )
        if self.event_type is MatchEventType.GOAL and any(
            value is not None for value in penalty_values
        ):
            raise ValueError("GOAL events cannot contain penalty fields")
        if self.event_type is MatchEventType.PENALTY and any(
            value is not None for value in assist_values
        ):
            raise ValueError("PENALTY events cannot contain assist fields")

        if self.event_type is MatchEventType.GOAL:
            player_ids = [
                player_id
                for player_id in (
                    self.player_id,
                    self.assist1_player_id,
                    self.assist2_player_id,
                )
                if player_id is not None
            ]
            if len(player_ids) != len(set(player_ids)):
                raise ValueError("A player cannot have multiple roles in one GOAL event")
        return self


class MatchEventInsertable(MatchEventBody):
    match_id: MatchId
    created: datetime_utc


class MatchEvent(MatchEventInsertable):
    id: MatchEventId
