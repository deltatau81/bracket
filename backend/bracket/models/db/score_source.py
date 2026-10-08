from pydantic import ConfigDict, Field

from bracket.models.db.match import Match, MatchPeriod, MatchScoreEntrySource
from bracket.models.db.shared import BaseModelORM


class ScoreSourcePreviewBody(BaseModelORM):
    model_config = ConfigDict(extra="forbid")
    target_source: MatchScoreEntrySource


class ScoreSourceConfirmBody(ScoreSourcePreviewBody):
    conflict_token: str = Field(min_length=64, max_length=64, pattern="^[0-9a-f]{64}$")


class SectionScores(BaseModelORM):
    period: MatchPeriod
    team1_score: int
    team2_score: int


class SectionScoreDifference(BaseModelORM):
    period: MatchPeriod
    team1_difference: int
    team2_difference: int


class ScoreSourcePreview(BaseModelORM):
    match_id: int
    current_source: MatchScoreEntrySource | None
    target_source: MatchScoreEntrySource
    current_scores: list[SectionScores]
    resulting_scores: list[SectionScores]
    differences: list[SectionScoreDifference]
    relevant_goal_count: int
    scores_changed: bool
    rankings_may_change: bool
    conflict_token: str


class ScoreSourceConfirmation(BaseModelORM):
    match: Match
    active_source: MatchScoreEntrySource
    current_scores: list[SectionScores]
