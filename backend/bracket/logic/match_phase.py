from dataclasses import dataclass

from bracket.models.db.match import (
    MatchPeriod,
    MatchPhaseAction,
    MatchPhaseState,
    MatchStatus,
)
from bracket.models.db.tournament import HockeyMode


class MatchPhaseTransitionError(ValueError):
    """Raised when a match phase state or requested transition is invalid."""


@dataclass(frozen=True)
class MatchPhaseTransition:
    status: MatchStatus
    active_period: MatchPeriod | None
    phase_state: MatchPhaseState | None


_VALID_PERIODS = {
    HockeyMode.COMPETITION: {
        MatchPeriod.HALF1,
        MatchPeriod.HALF2,
        MatchPeriod.SHOOTOUT,
    },
    HockeyMode.STANDARD: {
        MatchPeriod.PERIOD1,
        MatchPeriod.PERIOD2,
        MatchPeriod.PERIOD3,
        MatchPeriod.OVERTIME,
    },
    HockeyMode.GAME_SHOOTOUT: {
        MatchPeriod.GAME,
        MatchPeriod.SHOOTOUT,
    },
}

_TRANSITIONS = {
    (HockeyMode.GAME_SHOOTOUT, MatchPeriod.GAME, MatchPhaseState.ACTIVE, MatchPhaseAction.END_PERIOD):
        (MatchStatus.RUNNING, MatchPeriod.GAME, MatchPhaseState.BREAK),
    (HockeyMode.GAME_SHOOTOUT, MatchPeriod.GAME, MatchPhaseState.BREAK, MatchPhaseAction.START_NEXT_PERIOD):
        (MatchStatus.RUNNING, MatchPeriod.SHOOTOUT, MatchPhaseState.ACTIVE),
    (HockeyMode.GAME_SHOOTOUT, MatchPeriod.SHOOTOUT, MatchPhaseState.ACTIVE, MatchPhaseAction.FINISH_MATCH):
        (MatchStatus.FINISHED, MatchPeriod.SHOOTOUT, MatchPhaseState.BREAK),
    (HockeyMode.COMPETITION, MatchPeriod.HALF1, MatchPhaseState.ACTIVE, MatchPhaseAction.END_PERIOD):
        (MatchStatus.RUNNING, MatchPeriod.HALF1, MatchPhaseState.BREAK),
    (HockeyMode.COMPETITION, MatchPeriod.HALF1, MatchPhaseState.BREAK, MatchPhaseAction.START_NEXT_PERIOD):
        (MatchStatus.RUNNING, MatchPeriod.HALF2, MatchPhaseState.ACTIVE),
    (HockeyMode.COMPETITION, MatchPeriod.HALF2, MatchPhaseState.ACTIVE, MatchPhaseAction.END_PERIOD):
        (MatchStatus.RUNNING, MatchPeriod.HALF2, MatchPhaseState.BREAK),
    (HockeyMode.COMPETITION, MatchPeriod.HALF2, MatchPhaseState.BREAK, MatchPhaseAction.START_NEXT_PERIOD):
        (MatchStatus.RUNNING, MatchPeriod.SHOOTOUT, MatchPhaseState.ACTIVE),
    (HockeyMode.COMPETITION, MatchPeriod.SHOOTOUT, MatchPhaseState.ACTIVE, MatchPhaseAction.FINISH_MATCH):
        (MatchStatus.FINISHED, MatchPeriod.SHOOTOUT, MatchPhaseState.BREAK),
    (HockeyMode.STANDARD, MatchPeriod.PERIOD1, MatchPhaseState.ACTIVE, MatchPhaseAction.END_PERIOD):
        (MatchStatus.RUNNING, MatchPeriod.PERIOD1, MatchPhaseState.BREAK),
    (HockeyMode.STANDARD, MatchPeriod.PERIOD1, MatchPhaseState.BREAK, MatchPhaseAction.START_NEXT_PERIOD):
        (MatchStatus.RUNNING, MatchPeriod.PERIOD2, MatchPhaseState.ACTIVE),
    (HockeyMode.STANDARD, MatchPeriod.PERIOD2, MatchPhaseState.ACTIVE, MatchPhaseAction.END_PERIOD):
        (MatchStatus.RUNNING, MatchPeriod.PERIOD2, MatchPhaseState.BREAK),
    (HockeyMode.STANDARD, MatchPeriod.PERIOD2, MatchPhaseState.BREAK, MatchPhaseAction.START_NEXT_PERIOD):
        (MatchStatus.RUNNING, MatchPeriod.PERIOD3, MatchPhaseState.ACTIVE),
    (HockeyMode.STANDARD, MatchPeriod.PERIOD3, MatchPhaseState.ACTIVE, MatchPhaseAction.END_PERIOD):
        (MatchStatus.RUNNING, MatchPeriod.PERIOD3, MatchPhaseState.BREAK),
    (HockeyMode.STANDARD, MatchPeriod.PERIOD3, MatchPhaseState.BREAK, MatchPhaseAction.START_OVERTIME):
        (MatchStatus.RUNNING, MatchPeriod.OVERTIME, MatchPhaseState.ACTIVE),
    (HockeyMode.STANDARD, MatchPeriod.OVERTIME, MatchPhaseState.ACTIVE, MatchPhaseAction.END_PERIOD):
        (MatchStatus.RUNNING, MatchPeriod.OVERTIME, MatchPhaseState.BREAK),
}


def _validate_current_state(
    status: MatchStatus,
    active_period: MatchPeriod | None,
    phase_state: MatchPhaseState | None,
    hockey_mode: HockeyMode,
) -> None:
    if status is MatchStatus.PLANNED:
        if active_period is None and phase_state is None:
            return
        raise MatchPhaseTransitionError("A planned match cannot have a period or phase state")

    if active_period is None or phase_state is None:
        raise MatchPhaseTransitionError(
            f"A {status.value.lower()} match requires an active period and phase state"
        )
    if active_period not in _VALID_PERIODS[hockey_mode]:
        raise MatchPhaseTransitionError(
            f"Period {active_period.value} is not valid for {hockey_mode.value} mode"
        )
    if status is MatchStatus.FINISHED and phase_state is not MatchPhaseState.BREAK:
        raise MatchPhaseTransitionError("A finished match must be in BREAK")


def transition_match_phase(
    status: MatchStatus,
    active_period: MatchPeriod | None,
    phase_state: MatchPhaseState | None,
    hockey_mode: HockeyMode,
    action: MatchPhaseAction,
) -> MatchPhaseTransition:
    """Return the complete next phase state without performing side effects."""
    _validate_current_state(status, active_period, phase_state, hockey_mode)

    if status is MatchStatus.PLANNED and action is MatchPhaseAction.START_MATCH:
        initial_period = {
            HockeyMode.COMPETITION: MatchPeriod.HALF1,
            HockeyMode.GAME_SHOOTOUT: MatchPeriod.GAME,
            HockeyMode.STANDARD: MatchPeriod.PERIOD1,
        }[hockey_mode]
        return MatchPhaseTransition(MatchStatus.RUNNING, initial_period, MatchPhaseState.ACTIVE)

    if status is MatchStatus.FINISHED and action is MatchPhaseAction.REOPEN_MATCH:
        return MatchPhaseTransition(MatchStatus.RUNNING, active_period, MatchPhaseState.BREAK)

    if (
        status is MatchStatus.RUNNING
        and phase_state is MatchPhaseState.BREAK
        and action is MatchPhaseAction.RESUME_PERIOD
    ):
        return MatchPhaseTransition(MatchStatus.RUNNING, active_period, MatchPhaseState.ACTIVE)

    if (
        hockey_mode is HockeyMode.STANDARD
        and active_period in {MatchPeriod.PERIOD3, MatchPeriod.OVERTIME}
        and phase_state in {MatchPhaseState.ACTIVE, MatchPhaseState.BREAK}
        and action is MatchPhaseAction.FINISH_MATCH
    ):
        return MatchPhaseTransition(MatchStatus.FINISHED, active_period, MatchPhaseState.BREAK)

    next_state = _TRANSITIONS.get((hockey_mode, active_period, phase_state, action))
    if next_state is not None:
        return MatchPhaseTransition(*next_state)

    period = active_period.value if active_period is not None else "None"
    phase = phase_state.value if phase_state is not None else "None"
    raise MatchPhaseTransitionError(
        f"Invalid match phase transition: {status.value}/{period}/{phase} + {action.value}"
    )
