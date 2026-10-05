import pytest

from bracket.logic.match_phase import (
    MatchPhaseTransition,
    MatchPhaseTransitionError,
    transition_match_phase,
)
from bracket.models.db.match import (
    MatchPeriod,
    MatchPhaseAction,
    MatchPhaseState,
    MatchStatus,
)
from bracket.models.db.match_event import MatchEventPeriod, MatchEventType
from bracket.models.db.tournament import HockeyMode


State = tuple[MatchStatus, MatchPeriod | None, MatchPhaseState | None]


def apply(state: State, mode: HockeyMode, action: MatchPhaseAction) -> State:
    result = transition_match_phase(*state, mode, action)
    assert isinstance(result, MatchPhaseTransition)
    return result.status, result.active_period, result.phase_state


def test_complete_competition_sequence() -> None:
    state: State = (MatchStatus.PLANNED, None, None)
    expected = (
        (MatchPhaseAction.START_MATCH, (MatchStatus.RUNNING, MatchPeriod.HALF1, MatchPhaseState.ACTIVE)),
        (MatchPhaseAction.END_PERIOD, (MatchStatus.RUNNING, MatchPeriod.HALF1, MatchPhaseState.BREAK)),
        (MatchPhaseAction.START_NEXT_PERIOD, (MatchStatus.RUNNING, MatchPeriod.HALF2, MatchPhaseState.ACTIVE)),
        (MatchPhaseAction.END_PERIOD, (MatchStatus.RUNNING, MatchPeriod.HALF2, MatchPhaseState.BREAK)),
        (MatchPhaseAction.START_NEXT_PERIOD, (MatchStatus.RUNNING, MatchPeriod.SHOOTOUT, MatchPhaseState.ACTIVE)),
        (MatchPhaseAction.FINISH_MATCH, (MatchStatus.FINISHED, MatchPeriod.SHOOTOUT, MatchPhaseState.BREAK)),
    )
    for action, next_state in expected:
        state = apply(state, HockeyMode.COMPETITION, action)
        assert state == next_state


def test_complete_game_shootout_sequence() -> None:
    state: State = (MatchStatus.PLANNED, None, None)
    expected = (
        (MatchPhaseAction.START_MATCH, (MatchStatus.RUNNING, MatchPeriod.GAME, MatchPhaseState.ACTIVE)),
        (MatchPhaseAction.END_PERIOD, (MatchStatus.RUNNING, MatchPeriod.GAME, MatchPhaseState.BREAK)),
        (MatchPhaseAction.START_NEXT_PERIOD, (MatchStatus.RUNNING, MatchPeriod.SHOOTOUT, MatchPhaseState.ACTIVE)),
        (MatchPhaseAction.FINISH_MATCH, (MatchStatus.FINISHED, MatchPeriod.SHOOTOUT, MatchPhaseState.BREAK)),
    )
    for action, next_state in expected:
        state = apply(state, HockeyMode.GAME_SHOOTOUT, action)
        assert state == next_state


def test_game_shootout_enums_are_available() -> None:
    assert HockeyMode.GAME_SHOOTOUT.value == "GAME_SHOOTOUT"
    assert MatchPeriod.GAME.value == "GAME"
    assert MatchEventPeriod.GAME.value == "GAME"


def test_complete_standard_sequence_without_overtime() -> None:
    state: State = (MatchStatus.PLANNED, None, None)
    for action in (
        MatchPhaseAction.START_MATCH,
        MatchPhaseAction.END_PERIOD,
        MatchPhaseAction.START_NEXT_PERIOD,
        MatchPhaseAction.END_PERIOD,
        MatchPhaseAction.START_NEXT_PERIOD,
        MatchPhaseAction.FINISH_MATCH,
    ):
        state = apply(state, HockeyMode.STANDARD, action)
    assert state == (MatchStatus.FINISHED, MatchPeriod.PERIOD3, MatchPhaseState.BREAK)


def test_explicit_standard_overtime_sequence() -> None:
    state: State = (MatchStatus.PLANNED, None, None)
    for action in (
        MatchPhaseAction.START_MATCH,
        MatchPhaseAction.END_PERIOD,
        MatchPhaseAction.START_NEXT_PERIOD,
        MatchPhaseAction.END_PERIOD,
        MatchPhaseAction.START_NEXT_PERIOD,
        MatchPhaseAction.END_PERIOD,
    ):
        state = apply(state, HockeyMode.STANDARD, action)
    assert state == (MatchStatus.RUNNING, MatchPeriod.PERIOD3, MatchPhaseState.BREAK)
    state = apply(state, HockeyMode.STANDARD, MatchPhaseAction.START_OVERTIME)
    assert state == (MatchStatus.RUNNING, MatchPeriod.OVERTIME, MatchPhaseState.ACTIVE)
    state = apply(state, HockeyMode.STANDARD, MatchPhaseAction.END_PERIOD)
    assert state == (MatchStatus.RUNNING, MatchPeriod.OVERTIME, MatchPhaseState.BREAK)
    state = apply(state, HockeyMode.STANDARD, MatchPhaseAction.FINISH_MATCH)
    assert state == (MatchStatus.FINISHED, MatchPeriod.OVERTIME, MatchPhaseState.BREAK)


@pytest.mark.parametrize("period", [MatchPeriod.PERIOD3, MatchPeriod.OVERTIME])
@pytest.mark.parametrize("phase", [MatchPhaseState.ACTIVE, MatchPhaseState.BREAK])
def test_standard_can_finish_from_final_period_states(
    period: MatchPeriod, phase: MatchPhaseState
) -> None:
    assert apply(
        (MatchStatus.RUNNING, period, phase), HockeyMode.STANDARD, MatchPhaseAction.FINISH_MATCH
    ) == (MatchStatus.FINISHED, period, MatchPhaseState.BREAK)


def test_overtime_never_starts_automatically() -> None:
    state = (MatchStatus.RUNNING, MatchPeriod.PERIOD3, MatchPhaseState.ACTIVE)
    assert apply(state, HockeyMode.STANDARD, MatchPhaseAction.END_PERIOD) == (
        MatchStatus.RUNNING,
        MatchPeriod.PERIOD3,
        MatchPhaseState.BREAK,
    )


def test_reopen_and_resume_preserve_period() -> None:
    reopened = apply(
        (MatchStatus.FINISHED, MatchPeriod.SHOOTOUT, MatchPhaseState.BREAK),
        HockeyMode.COMPETITION,
        MatchPhaseAction.REOPEN_MATCH,
    )
    assert reopened == (MatchStatus.RUNNING, MatchPeriod.SHOOTOUT, MatchPhaseState.BREAK)
    assert apply(reopened, HockeyMode.COMPETITION, MatchPhaseAction.RESUME_PERIOD) == (
        MatchStatus.RUNNING,
        MatchPeriod.SHOOTOUT,
        MatchPhaseState.ACTIVE,
    )


@pytest.mark.parametrize(
    ("state", "mode", "action"),
    [
        ((MatchStatus.RUNNING, MatchPeriod.HALF1, MatchPhaseState.ACTIVE), HockeyMode.COMPETITION, MatchPhaseAction.START_NEXT_PERIOD),
        ((MatchStatus.RUNNING, MatchPeriod.HALF1, MatchPhaseState.BREAK), HockeyMode.COMPETITION, MatchPhaseAction.END_PERIOD),
        ((MatchStatus.RUNNING, MatchPeriod.HALF2, MatchPhaseState.BREAK), HockeyMode.COMPETITION, MatchPhaseAction.START_OVERTIME),
        ((MatchStatus.RUNNING, MatchPeriod.PERIOD1, MatchPhaseState.BREAK), HockeyMode.STANDARD, MatchPhaseAction.START_OVERTIME),
        ((MatchStatus.RUNNING, MatchPeriod.HALF1, MatchPhaseState.ACTIVE), HockeyMode.COMPETITION, MatchPhaseAction.FINISH_MATCH),
        ((MatchStatus.RUNNING, MatchPeriod.HALF2, MatchPhaseState.ACTIVE), HockeyMode.COMPETITION, MatchPhaseAction.FINISH_MATCH),
        ((MatchStatus.RUNNING, MatchPeriod.PERIOD1, MatchPhaseState.ACTIVE), HockeyMode.STANDARD, MatchPhaseAction.FINISH_MATCH),
        ((MatchStatus.RUNNING, MatchPeriod.PERIOD2, MatchPhaseState.BREAK), HockeyMode.STANDARD, MatchPhaseAction.FINISH_MATCH),
        ((MatchStatus.RUNNING, MatchPeriod.HALF1, MatchPhaseState.BREAK), HockeyMode.COMPETITION, MatchPhaseAction.FINISH_MATCH),
        ((MatchStatus.RUNNING, MatchPeriod.HALF1, MatchPhaseState.ACTIVE), HockeyMode.COMPETITION, MatchPhaseAction.REOPEN_MATCH),
        ((MatchStatus.RUNNING, MatchPeriod.HALF1, MatchPhaseState.ACTIVE), HockeyMode.COMPETITION, MatchPhaseAction.RESUME_PERIOD),
        ((MatchStatus.PLANNED, None, None), HockeyMode.COMPETITION, MatchPhaseAction.RESUME_PERIOD),
    ],
)
def test_invalid_and_skipped_transitions(
    state: State, mode: HockeyMode, action: MatchPhaseAction
) -> None:
    with pytest.raises(MatchPhaseTransitionError, match="Invalid match phase transition"):
        apply(state, mode, action)


@pytest.mark.parametrize(
    ("mode", "period"),
    [
        (HockeyMode.STANDARD, MatchPeriod.HALF1),
        (HockeyMode.STANDARD, MatchPeriod.HALF2),
        (HockeyMode.STANDARD, MatchPeriod.SHOOTOUT),
        (HockeyMode.COMPETITION, MatchPeriod.PERIOD1),
        (HockeyMode.COMPETITION, MatchPeriod.PERIOD2),
        (HockeyMode.COMPETITION, MatchPeriod.PERIOD3),
        (HockeyMode.COMPETITION, MatchPeriod.OVERTIME),
    ],
)
def test_wrong_mode_periods_are_rejected(mode: HockeyMode, period: MatchPeriod) -> None:
    with pytest.raises(MatchPhaseTransitionError, match="is not valid"):
        apply(
            (MatchStatus.RUNNING, period, MatchPhaseState.BREAK),
            mode,
            MatchPhaseAction.RESUME_PERIOD,
        )


@pytest.mark.parametrize("status", [MatchStatus.RUNNING, MatchStatus.FINISHED])
def test_legacy_state_without_period_is_rejected(status: MatchStatus) -> None:
    with pytest.raises(MatchPhaseTransitionError, match="requires an active period"):
        apply(
            (status, None, None),
            HockeyMode.COMPETITION,
            MatchPhaseAction.REOPEN_MATCH,
        )


def test_event_period_and_penalty_terminology_are_separate() -> None:
    assert MatchEventPeriod.SHOOTOUT.value == "SHOOTOUT"
    assert "BREAK" not in MatchEventPeriod.__members__
    assert MatchEventType.PENALTY.value == "PENALTY"
    assert MatchEventPeriod.SHOOTOUT.value != MatchEventType.PENALTY.value
