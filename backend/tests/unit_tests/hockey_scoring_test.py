from decimal import Decimal

import pytest
from pydantic import ValidationError

from bracket.logic.ranking.calculation import (
    determine_ranking_for_stage_item,
    determine_team_ranking_for_stage_item,
    get_part_points,
)
from bracket.models.db.stage_item import StageType
from bracket.models.db.tournament import HockeyMode, HockeyScoring, TournamentCompetitionFormat
from bracket.utils.dummy_records import DUMMY_TOURNAMENT
from tests.unit_tests.ranking_calculation_test import make_round_robin_stage_item


@pytest.mark.parametrize(
    "mode,expected",
    [
        (HockeyMode.COMPETITION, ("5", "0")),
        (HockeyMode.GAME_SHOOTOUT, ("3", "0")),
    ],
)
@pytest.mark.parametrize("format_", list(TournamentCompetitionFormat))
@pytest.mark.parametrize("bonus", [False, True])
def test_hockey_defaults_ignore_goal_bonus(mode, expected, format_, bonus):
    stage, ranking = make_round_robin_stage_item()
    tournament = DUMMY_TOURNAMENT.model_copy(update={"competition_format": format_})
    result = determine_ranking_for_stage_item(
        stage, ranking.model_copy(update={"add_score_points": bonus}), mode, tournament
    )
    assert [stat.points for stat in result.values()] == list(map(Decimal, expected))


@pytest.mark.parametrize(
    "mode,expected",
    [
        (HockeyMode.COMPETITION, ("8", "0")),
        (HockeyMode.GAME_SHOOTOUT, ("5", "0")),
    ],
)
def test_custom_hockey_points_are_independent_of_ranking(mode, expected):
    stage, ranking = make_round_robin_stage_item()
    scoring = HockeyScoring(game_win_points="3", shootout_win_points="2", shootout_draw_points="1")
    for win in ("7", "12"):
        result = determine_team_ranking_for_stage_item(
            stage, ranking.model_copy(update={"win_points": Decimal(win)}), mode, scoring
        )
        assert [stat.points for _, stat in result] == list(map(Decimal, expected))


@pytest.mark.parametrize(
    "mode,expected",
    [
        (HockeyMode.COMPETITION, ("5", "1.00")),
        (HockeyMode.GAME_SHOOTOUT, ("3", "0.75")),
    ],
)
def test_positive_loss_points_and_hundredths(mode, expected):
    stage, ranking = make_round_robin_stage_item()
    scoring = HockeyScoring(game_loss_points="0.25", shootout_loss_points="0.50")
    result = determine_ranking_for_stage_item(stage, ranking, mode, scoring)
    assert [stat.points for stat in result.values()] == list(map(Decimal, expected))


def test_game_win_with_drawn_shootout():
    stage, ranking = make_round_robin_stage_item()
    match = stage.rounds[0].matches[0]
    stage.rounds[0].matches[0] = match.model_copy(
        update={
            "stage_item_input1_score": 1,
            "stage_item_input2_score": 0,
            "stage_item_input1_penalty_score": 0,
            "stage_item_input2_penalty_score": 0,
        }
    )
    result = determine_ranking_for_stage_item(stage, ranking, HockeyMode.GAME_SHOOTOUT)
    assert [stat.points for stat in result.values()] == [Decimal("2.5"), Decimal("0.5")]


@pytest.mark.parametrize("team,opponent,expected", [(1, 0, "3"), (0, 0, "1"), (0, 1, "0.25")])
def test_configured_segment_results(team, opponent, expected):
    assert get_part_points(team, opponent, Decimal("3"), Decimal("1"), Decimal("0.25")) == Decimal(
        expected
    )


@pytest.mark.parametrize("value", [None, "-0.01", "0.001", "1000000", "NaN", "Infinity", "invalid"])
@pytest.mark.parametrize("field", list(HockeyScoring.model_fields))
def test_invalid_scoring_values(field, value):
    with pytest.raises(ValidationError):
        HockeyScoring.model_validate({field: value})


def test_numeric_boundary_and_defaults():
    scoring = HockeyScoring(game_win_points="999999.99")
    assert scoring.game_win_points == Decimal("999999.99")
    assert HockeyScoring().model_dump() == {
        "game_win_points": Decimal("2"),
        "game_draw_points": Decimal("1"),
        "game_loss_points": Decimal("0"),
        "shootout_win_points": Decimal("1"),
        "shootout_draw_points": Decimal("0.5"),
        "shootout_loss_points": Decimal("0"),
    }


@pytest.mark.parametrize("mode", [HockeyMode.COMPETITION, HockeyMode.GAME_SHOOTOUT])
def test_draft_round_is_excluded(mode):
    stage, ranking = make_round_robin_stage_item()
    stage.rounds[0].is_draft = True
    assert (
        determine_ranking_for_stage_item(stage, ranking, mode, HockeyScoring(game_win_points="3"))
        == {}
    )


@pytest.mark.parametrize(
    "type_", [StageType.ROUND_ROBIN, StageType.SINGLE_ELIMINATION, StageType.SWISS]
)
def test_standard_stage_types_ignore_hockey_points(type_):
    stage, ranking = make_round_robin_stage_item()
    stage.type = type_
    baseline = determine_ranking_for_stage_item(stage, ranking, HockeyMode.STANDARD)
    custom = determine_ranking_for_stage_item(
        stage, ranking, HockeyMode.STANDARD, HockeyScoring(game_win_points="99")
    )
    assert custom == baseline


def test_openapi_scoring_inputs_are_optional_and_responses_are_complete():
    from bracket.app import app
    from openapi import openapi  # noqa: F401

    schemas = app.openapi()["components"]["schemas"]
    fields = set(HockeyScoring.model_fields)
    for name in ("TournamentBody", "TournamentUpdateBody"):
        assert fields <= set(schemas[name]["properties"])
        assert not fields & set(schemas[name]["required"])
    assert fields <= set(schemas["Tournament"]["required"])


@pytest.mark.parametrize("mode", [HockeyMode.COMPETITION, HockeyMode.GAME_SHOOTOUT])
@pytest.mark.parametrize("type_", [StageType.SINGLE_ELIMINATION, StageType.SWISS])
def test_non_round_robin_hockey_stages_keep_ranking_rules(mode, type_):
    stage, ranking = make_round_robin_stage_item()
    stage.type = type_
    ranking = ranking.model_copy(update={"add_score_points": True})
    baseline = determine_ranking_for_stage_item(stage, ranking, mode)
    assert (
        determine_ranking_for_stage_item(
            stage, ranking, mode, HockeyScoring(game_win_points=Decimal("99"))
        )
        == baseline
    )
