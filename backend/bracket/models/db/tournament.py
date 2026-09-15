import re
from enum import auto
from typing import Annotated

from heliclockter import datetime_utc
from pydantic import AfterValidator, Field

from bracket.models.db.shared import BaseModelORM
from bracket.utils.id_types import ClubId, TournamentId
from bracket.utils.pydantic import EmptyStrToNone
from bracket.utils.types import EnumAutoStr


class TournamentStatus(EnumAutoStr):
    OPEN = auto()
    ARCHIVED = auto()


class HockeyMode(EnumAutoStr):
    COMPETITION = auto()
    GAME_SHOOTOUT = auto()
    STANDARD = auto()


class HockeyRuleset(EnumAutoStr):
    DEB = auto()
    IIHF = auto()


class HockeyAgeCategory(EnumAutoStr):
    U9 = auto()
    U11 = auto()
    U13 = auto()
    U15 = auto()
    U17 = auto()
    U20 = auto()
    SENIOR = auto()


def validate_ruleset_season(value: str) -> str:
    match = re.fullmatch(r"(\d{4})/(\d{2})", value)
    if match is None or int(match.group(2)) != (int(match.group(1)) + 1) % 100:
        raise ValueError("ruleset_season must be a sequential season in YYYY/YY format")
    return value


RulesetSeason = Annotated[str, AfterValidator(validate_ruleset_season)]


class TournamentInsertable(BaseModelORM):
    club_id: ClubId
    name: str
    created: datetime_utc
    start_time: datetime_utc
    duration_minutes: int = Field(..., ge=1)
    margin_minutes: int = Field(..., ge=0)
    dashboard_public: bool
    dashboard_endpoint: str | None = None
    logo_path: str | None = None
    players_can_be_in_multiple_teams: bool
    auto_assign_courts: bool
    status: TournamentStatus = TournamentStatus.OPEN
    hockey_mode: HockeyMode = HockeyMode.COMPETITION
    ruleset: HockeyRuleset = HockeyRuleset.DEB
    age_category: HockeyAgeCategory = HockeyAgeCategory.U15
    ruleset_season: RulesetSeason = "2026/27"


class Tournament(TournamentInsertable):
    id: TournamentId


class TournamentUpdateBody(BaseModelORM):
    start_time: datetime_utc
    name: str
    dashboard_public: bool
    dashboard_endpoint: EmptyStrToNone | str = None
    players_can_be_in_multiple_teams: bool
    auto_assign_courts: bool
    duration_minutes: int = Field(..., ge=1)
    margin_minutes: int = Field(..., ge=0)
    hockey_mode: HockeyMode | None = None
    ruleset: HockeyRuleset | None = None
    age_category: HockeyAgeCategory | None = None
    ruleset_season: RulesetSeason | None = None


class TournamentChangeStatusBody(BaseModelORM):
    status: TournamentStatus


class TournamentBody(TournamentUpdateBody):
    club_id: ClubId
    hockey_mode: HockeyMode = HockeyMode.COMPETITION
    ruleset: HockeyRuleset = HockeyRuleset.DEB
    age_category: HockeyAgeCategory = HockeyAgeCategory.U15
    ruleset_season: RulesetSeason = "2026/27"
