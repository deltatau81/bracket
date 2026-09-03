from typing import Literal

from pydantic import Field

from bracket.models.db.shared import BaseModelORM
from bracket.utils.id_types import PlayerId, TeamId

PlayerPosition = Literal["GK", "D", "F"]


class PlayerXTeamInsertable(BaseModelORM):
    player_id: PlayerId
    team_id: TeamId
    number: int | None = Field(default=None, ge=0)
    position: PlayerPosition | None = None


class PlayerTeamAssignmentBody(BaseModelORM):
    player_id: PlayerId
    number: int | None = Field(default=None, ge=0)
    position: PlayerPosition | None = None
