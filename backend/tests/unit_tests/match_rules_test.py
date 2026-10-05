from bracket.logic.match_rules import get_effective_match_rules
from bracket.models.db.match import Match
from bracket.models.db.tournament import HockeyAgeCategory, HockeyRuleset, Tournament
from bracket.utils.dummy_records import DUMMY_MATCH1, DUMMY_TOURNAMENT
from bracket.utils.id_types import MatchId, TournamentId


def test_effective_match_rules_inherit_tournament_values() -> None:
    match = Match(**DUMMY_MATCH1.model_dump(), id=MatchId(-1))
    tournament = Tournament(**DUMMY_TOURNAMENT.model_dump(), id=TournamentId(-1))

    effective = get_effective_match_rules(match, tournament)

    assert effective.ruleset == tournament.ruleset
    assert effective.age_category == tournament.age_category
    assert effective.ruleset_season == tournament.ruleset_season


def test_effective_match_rules_resolve_each_override_independently() -> None:
    match_data = DUMMY_MATCH1.model_copy(
        update={
            "ruleset_override": HockeyRuleset.IIHF,
            "ruleset_season_override": "2029/30",
        }
    )
    tournament_data = DUMMY_TOURNAMENT.model_copy(
        update={"age_category": HockeyAgeCategory.U17}
    )
    match = Match(**match_data.model_dump(), id=MatchId(-1))
    tournament = Tournament(**tournament_data.model_dump(), id=TournamentId(-1))

    effective = get_effective_match_rules(match, tournament)

    assert effective.ruleset == HockeyRuleset.IIHF
    assert effective.age_category == HockeyAgeCategory.U17
    assert effective.ruleset_season == "2029/30"
