from __future__ import annotations

import json
from decimal import Decimal
from typing import Annotated

from heliclockter import datetime_utc
from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from bracket.logic.ranking.statistics import START_ELO
from bracket.models.db.player import Player
from bracket.models.db.player_x_team import PlayerPosition, PlayerTeamAssignmentBody
from bracket.models.db.shared import BaseModelORM
from bracket.utils.id_types import ClubId, PlayerId, TeamId, TournamentId


class TeamInsertable(BaseModelORM):
    created: datetime_utc
    name: str
    tournament_id: TournamentId
    participant_club_id: ClubId | None = None
    pairing_group: Annotated[str | None, StringConstraints(max_length=32)] = None
    active: bool
    elo_score: Decimal = START_ELO
    swiss_score: Decimal = Decimal("0.0")
    wins: int = 0
    draws: int = 0
    losses: int = 0
    logo_path: str | None = None


class Team(TeamInsertable):
    id: TeamId


class TeamPlayer(Player):
    number: int | None = None
    position: PlayerPosition | None = None


class TeamWithPlayers(BaseModel):
    id: TeamId
    players: list[TeamPlayer]
    elo_score: Decimal = START_ELO
    swiss_score: Decimal = Decimal("0.0")
    wins: int = 0
    draws: int = 0
    losses: int = 0
    name: str
    logo_path: str | None = None

    @property
    def player_ids(self) -> list[PlayerId]:
        return [player.id for player in self.players]

    @field_validator("players", mode="before")
    @staticmethod
    def handle_players(values: list[TeamPlayer] | None) -> list[TeamPlayer]:
        if values is None:
            return []
        if isinstance(values, str):
            values_json = json.loads(values)
            if values_json == [None]:
                return []
            return values_json

        return values


class FullTeamWithPlayers(TeamWithPlayers, Team):
    pass


class TeamBody(BaseModelORM):
    name: Annotated[str, StringConstraints(min_length=1, max_length=30)]
    active: bool
    participant_club_id: ClubId | None = None
    pairing_group: Annotated[str | None, StringConstraints(max_length=32)] = None
    player_ids: set[PlayerId]
    player_assignments: list[PlayerTeamAssignmentBody] | None = None

    @model_validator(mode="after")
    def assignments_belong_to_members(self) -> "TeamBody":
        assignment_ids = {assignment.player_id for assignment in self.player_assignments or []}
        if not assignment_ids.issubset(self.player_ids):
            raise ValueError("player_assignments must refer to player_ids")
        return self


class TeamMultiBody(BaseModelORM):
    names: str = Field(..., min_length=1)
    active: bool
    participant_club_id: ClubId | None = None
    pairing_group: Annotated[str | None, StringConstraints(max_length=32)] = None
