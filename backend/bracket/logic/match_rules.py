from bracket.models.db.match import Match
from bracket.models.db.shared import BaseModelORM
from bracket.models.db.tournament import (
    HockeyAgeCategory,
    HockeyRuleset,
    RulesetSeason,
    Tournament,
)


class EffectiveMatchRules(BaseModelORM):
    ruleset: HockeyRuleset
    age_category: HockeyAgeCategory
    ruleset_season: RulesetSeason


def get_effective_match_rules(match: Match, tournament: Tournament) -> EffectiveMatchRules:
    return EffectiveMatchRules(
        ruleset=(
            match.ruleset_override
            if match.ruleset_override is not None
            else tournament.ruleset
        ),
        age_category=(
            match.age_category_override
            if match.age_category_override is not None
            else tournament.age_category
        ),
        ruleset_season=(
            match.ruleset_season_override
            if match.ruleset_season_override is not None
            else tournament.ruleset_season
        ),
    )
