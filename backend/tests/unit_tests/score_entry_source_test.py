from types import SimpleNamespace

import pytest

from bracket.models.db.match import MatchScoreEntrySource
from bracket.models.db.tournament import HockeyMode
from bracket.sql.matches import (
    ScoreEntrySourceConflictError,
    _ensure_score_update_allowed,
    default_score_entry_source,
)


SCORE_FIELDS = {
    "stage_item_input1_score": 5,
    "stage_item_input2_score": 3,
    "stage_item_input1_half1_score": 0,
    "stage_item_input2_half1_score": 0,
    "stage_item_input1_half2_score": 0,
    "stage_item_input2_half2_score": 0,
    "stage_item_input1_penalty_score": 1,
    "stage_item_input2_penalty_score": 2,
}


def match_with_source(source: MatchScoreEntrySource | None) -> SimpleNamespace:
    return SimpleNamespace(score_entry_source=source, **SCORE_FIELDS)


def test_score_entry_source_values_are_explicit() -> None:
    assert MatchScoreEntrySource.MANUAL.value == "MANUAL"
    assert MatchScoreEntrySource.EVENTS.value == "EVENTS"


@pytest.mark.parametrize(
    ("hockey_mode", "expected"),
    [
        (HockeyMode.COMPETITION, MatchScoreEntrySource.MANUAL),
        (HockeyMode.GAME_SHOOTOUT, MatchScoreEntrySource.MANUAL),
        (HockeyMode.STANDARD, None),
    ],
)
def test_new_match_default_is_mode_aware(
    hockey_mode: HockeyMode, expected: MatchScoreEntrySource | None
) -> None:
    assert default_score_entry_source(hockey_mode) is expected


def test_events_source_rejects_changed_scores() -> None:
    with pytest.raises(ScoreEntrySourceConflictError):
        _ensure_score_update_allowed(
            match_with_source(MatchScoreEntrySource.EVENTS),
            SCORE_FIELDS | {"stage_item_input1_score": 6},
        )


def test_events_source_allows_unchanged_scores() -> None:
    _ensure_score_update_allowed(match_with_source(MatchScoreEntrySource.EVENTS), SCORE_FIELDS)


def test_manual_and_legacy_sources_allow_score_updates() -> None:
    _ensure_score_update_allowed(match_with_source(MatchScoreEntrySource.MANUAL), SCORE_FIELDS)
    _ensure_score_update_allowed(match_with_source(None), SCORE_FIELDS | {"stage_item_input1_score": 6})
