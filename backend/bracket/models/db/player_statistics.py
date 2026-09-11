from bracket.models.db.player_x_team import PlayerPosition
from bracket.models.db.shared import BaseModelORM
from bracket.utils.id_types import PlayerId, TeamId


class PlayerStatistics(BaseModelORM):
    player_id: PlayerId
    player_name: str
    team_id: TeamId | None = None
    team_name: str | None = None
    jersey_number: int | None = None
    position: PlayerPosition | None = None
    goals: int
    assists: int
    points: int
    penalty_minutes: int
