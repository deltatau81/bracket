from decimal import Decimal
from enum import auto

from heliclockter import datetime_utc, timedelta
from pydantic import BaseModel, ConfigDict

from bracket.models.db.court import Court
from bracket.models.db.shared import BaseModelORM
from bracket.models.db.stage_item_inputs import StageItemInput
from bracket.models.db.tournament import HockeyAgeCategory, HockeyRuleset, RulesetSeason
from bracket.utils.id_types import CourtId, MatchId, RoundId, StageItemInputId
from bracket.utils.types import EnumAutoStr, assert_some


class MatchStatus(EnumAutoStr):
    PLANNED = auto()
    RUNNING = auto()
    FINISHED = auto()


class MatchPeriod(EnumAutoStr):
    GAME = auto()
    HALF1 = auto()
    HALF2 = auto()
    SHOOTOUT = auto()
    PERIOD1 = auto()
    PERIOD2 = auto()
    PERIOD3 = auto()
    OVERTIME = auto()


class MatchPhaseState(EnumAutoStr):
    ACTIVE = auto()
    BREAK = auto()


class MatchPhaseAction(EnumAutoStr):
    START_MATCH = auto()
    END_PERIOD = auto()
    START_NEXT_PERIOD = auto()
    START_OVERTIME = auto()
    FINISH_MATCH = auto()
    REOPEN_MATCH = auto()
    RESUME_PERIOD = auto()


class MatchScoreEntrySource(EnumAutoStr):
    MANUAL = auto()
    EVENTS = auto()


class MatchPhaseBody(BaseModelORM):
    action: MatchPhaseAction


class MatchBaseInsertable(BaseModelORM):
    created: datetime_utc
    start_time: datetime_utc | None = None
    duration_minutes: int
    margin_minutes: int
    custom_duration_minutes: int | None = None
    custom_margin_minutes: int | None = None
    position_in_schedule: int | None = None
    round_id: RoundId
    stage_item_input1_score: int
    stage_item_input2_score: int
    stage_item_input1_half1_score: int = 0
    stage_item_input2_half1_score: int = 0
    stage_item_input1_half2_score: int = 0
    stage_item_input2_half2_score: int = 0
    stage_item_input1_penalty_score: int = 0
    stage_item_input2_penalty_score: int = 0
    court_id: CourtId | None = None
    stage_item_input1_conflict: bool
    stage_item_input2_conflict: bool
    status: MatchStatus = MatchStatus.PLANNED
    active_period: MatchPeriod | None = None
    phase_state: MatchPhaseState | None = None
    ruleset_override: HockeyRuleset | None = None
    age_category_override: HockeyAgeCategory | None = None
    ruleset_season_override: RulesetSeason | None = None
    score_entry_source: MatchScoreEntrySource | None = None

    @property
    def end_time(self) -> datetime_utc:
        assert self.start_time
        return self.start_time + timedelta(minutes=self.duration_minutes + self.margin_minutes)


class MatchInsertable(MatchBaseInsertable):
    stage_item_input1_id: StageItemInputId | None = None
    stage_item_input2_id: StageItemInputId | None = None
    stage_item_input1_winner_from_match_id: MatchId | None = None
    stage_item_input2_winner_from_match_id: MatchId | None = None


class Match(MatchInsertable):
    id: MatchId
    stage_item_input1: StageItemInput | None = None
    stage_item_input2: StageItemInput | None = None

    def get_winner(self) -> StageItemInput | None:
        if self.status != MatchStatus.FINISHED:
            return None

        if self.stage_item_input1_score > self.stage_item_input2_score:
            return self.stage_item_input1
        if self.stage_item_input1_score < self.stage_item_input2_score:
            return self.stage_item_input2

        return None


class MatchWithDetails(Match):
    """
    MatchWithDetails has zero or one defined stage item inputs, but not both.
    """

    court: Court | None = None


def get_match_hash(
    stage_item_input1_id: StageItemInputId | None, stage_item_input2_id: StageItemInputId | None
) -> str:
    return f"{stage_item_input1_id}-{stage_item_input2_id}"


class MatchWithDetailsDefinitive(Match):
    stage_item_input1: StageItemInput  # pyrefly: ignore [bad-override]
    stage_item_input2: StageItemInput  # pyrefly: ignore [bad-override]
    court: Court | None = None

    @property
    def stage_item_inputs(self) -> list[StageItemInput]:
        return [self.stage_item_input1, self.stage_item_input2]

    @property
    def stage_item_input_ids(self) -> list[StageItemInputId]:
        return [assert_some(self.stage_item_input1_id), assert_some(self.stage_item_input2_id)]

    def get_input_ids_hashes(self) -> list[str]:
        return [
            get_match_hash(self.stage_item_input1_id, self.stage_item_input2_id),
            get_match_hash(self.stage_item_input2_id, self.stage_item_input1_id),
        ]


class MatchBody(BaseModelORM):
    round_id: RoundId
    stage_item_input1_score: int | None = None
    stage_item_input2_score: int | None = None
    stage_item_input1_half1_score: int = 0
    stage_item_input2_half1_score: int = 0
    stage_item_input1_half2_score: int = 0
    stage_item_input2_half2_score: int = 0
    stage_item_input1_penalty_score: int = 0
    stage_item_input2_penalty_score: int = 0
    court_id: CourtId | None = None
    start_time: datetime_utc | None = None
    custom_duration_minutes: int | None = None
    custom_margin_minutes: int | None = None
    status: MatchStatus | None = None
    ruleset_override: HockeyRuleset | None = None
    age_category_override: HockeyAgeCategory | None = None
    ruleset_season_override: RulesetSeason | None = None


class MatchUpdateBody(MatchBody):
    model_config = ConfigDict(extra="forbid")

    id: MatchId | None = None

class MatchCreateBodyFrontend(BaseModelORM):

    round_id: RoundId
    court_id: CourtId | None = None
    stage_item_input1_id: StageItemInputId | None = None
    stage_item_input2_id: StageItemInputId | None = None
    stage_item_input1_winner_from_match_id: MatchId | None = None
    stage_item_input2_winner_from_match_id: MatchId | None = None


class MatchCreateBody(MatchCreateBodyFrontend):
    duration_minutes: int
    margin_minutes: int
    custom_duration_minutes: int | None = None
    custom_margin_minutes: int | None = None


class MatchRescheduleBody(BaseModelORM):
    old_court_id: CourtId
    old_position: int
    new_court_id: CourtId
    new_position: int


class MatchFilter(BaseModel):
    elo_diff_threshold: int
    only_recommended: bool
    limit: int
    iterations: int


class SuggestedMatch(BaseModel):
    stage_item_input1: StageItemInput
    stage_item_input2: StageItemInput
    elo_diff: Decimal
    swiss_diff: Decimal
    is_recommended: bool
    times_played_sum: int
    player_behind_schedule_count: int

    @property
    def stage_item_input_ids(self) -> list[int]:
        return [self.stage_item_input1.id, self.stage_item_input2.id]
