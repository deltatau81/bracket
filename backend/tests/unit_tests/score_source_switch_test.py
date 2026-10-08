from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from bracket.logic.score_source import ALL_SCORE_FIELDS, build_source_preview
from bracket.models.db.match import Match, MatchPeriod, MatchScoreEntrySource, MatchStatus
from bracket.models.db.match_event import MatchEvent, MatchEventPeriod, MatchEventType
from bracket.models.db.score_source import ScoreSourceConfirmBody, ScoreSourcePreviewBody
from bracket.models.db.tournament import HockeyMode, TournamentStatus
from bracket.utils.dummy_records import DUMMY_MATCH1, DUMMY_MOCK_TIME, DUMMY_TOURNAMENT
from bracket.utils.id_types import TeamId


def records(mode=HockeyMode.COMPETITION, source=MatchScoreEntrySource.MANUAL):
    match = Match.model_validate(
        {
            **DUMMY_MATCH1.model_dump(),
            "id": 1,
            "score_entry_source": source,
            "stage_item_input1_score": 8,
            "stage_item_input1_half1_score": 5,
            "stage_item_input1_half2_score": 3,
            "stage_item_input1_penalty_score": 4,
        }
    )
    tournament = DUMMY_TOURNAMENT.model_copy(update={"id": 7, "hockey_mode": mode})
    return match, tournament


def event(period, team=11, event_id=1, type_=MatchEventType.GOAL):
    return MatchEvent(
        id=event_id,
        match_id=1,
        team_id=team,
        event_type=type_,
        period=MatchEventPeriod(period),
        created=DUMMY_MOCK_TIME,
    )


@pytest.mark.parametrize("mode", [HockeyMode.COMPETITION, HockeyMode.GAME_SHOOTOUT])
@pytest.mark.parametrize("source", [MatchScoreEntrySource.MANUAL, None])
@pytest.mark.parametrize("with_events", [False, True])
def test_switch_to_events_recounts_every_section(mode, source, with_events):
    match, tournament = records(mode, source)
    periods = (
        ["GAME", "SHOOTOUT"] if mode is HockeyMode.GAME_SHOOTOUT else ["HALF1", "HALF2", "SHOOTOUT"]
    )
    events = (
        [event(period, event_id=i) for i, period in enumerate(periods, 1)] if with_events else []
    )
    events += [event(periods[0], 99, 90), event(periods[0], 11, 91, MatchEventType.PENALTY)]
    preview, scores = build_source_preview(
        match, tournament, events, (TeamId(11), TeamId(12)), MatchScoreEntrySource.EVENTS
    )
    assert preview.relevant_goal_count == (len(periods) if with_events else 0)
    assert all(
        section.team1_score == int(with_events) and section.team2_score == 0
        for section in preview.resulting_scores
    )
    assert scores["stage_item_input1_score"] == (
        int(with_events) if mode is HockeyMode.GAME_SHOOTOUT else 2 * int(with_events)
    )
    assert match.stage_item_input1_score == 8
    assert preview.scores_changed
    assert preview.differences[0].team1_difference == int(with_events) - (
        8 if mode is HockeyMode.GAME_SHOOTOUT else 5
    )


@pytest.mark.parametrize(
    "source", [MatchScoreEntrySource.EVENTS, None, MatchScoreEntrySource.MANUAL]
)
@pytest.mark.parametrize("with_events", [False, True])
def test_switch_to_manual_preserves_all_scores_and_events(source, with_events):
    match, tournament = records(source=source)
    events = [event("HALF1")] if with_events else []
    before = [entry.model_dump() for entry in events]
    preview, scores = build_source_preview(
        match, tournament, events, (TeamId(11), TeamId(12)), MatchScoreEntrySource.MANUAL
    )
    assert scores == {field: getattr(match, field) for field in ALL_SCORE_FIELDS}
    assert not preview.scores_changed
    assert [entry.model_dump() for entry in events] == before


@pytest.mark.parametrize("source", list(MatchScoreEntrySource))
def test_same_source_is_noop_even_when_event_counts_disagree(source):
    match, tournament = records(source=source)
    preview, scores = build_source_preview(
        match, tournament, [event("HALF1")], (TeamId(11), TeamId(12)), source
    )
    assert not preview.scores_changed
    assert scores["stage_item_input1_half1_score"] == 5


@pytest.mark.parametrize(
    "change",
    [
        "source",
        "scores",
        "phase",
        "status",
        "event_team",
        "event_period",
        "event_added",
        "event_deleted",
        "archive",
        "rules",
        "participant",
        "target",
    ],
)
def test_token_covers_relevant_state(change):
    match, tournament = records()
    events = [event("HALF1")]
    participants = (TeamId(11), TeamId(12))
    target = MatchScoreEntrySource.EVENTS
    original = build_source_preview(match, tournament, events, participants, target)[
        0
    ].conflict_token
    if change == "source":
        match = match.model_copy(update={"score_entry_source": None})
    if change == "scores":
        match = match.model_copy(update={"stage_item_input1_half2_score": 4})
    if change == "phase":
        match = match.model_copy(update={"active_period": MatchPeriod.HALF2})
    if change == "status":
        match = match.model_copy(update={"status": MatchStatus.RUNNING})
    if change == "event_team":
        events = [event("HALF1", 12)]
    if change == "event_period":
        events = [event("HALF2")]
    if change == "event_added":
        events.append(event("SHOOTOUT", event_id=2))
    if change == "event_deleted":
        events = []
    if change == "archive":
        tournament = tournament.model_copy(update={"status": TournamentStatus.ARCHIVED})
    if change == "rules":
        tournament = tournament.model_copy(update={"game_win_points": Decimal("3.5")})
    if change == "participant":
        participants = (TeamId(12), TeamId(11))
    if change == "target":
        target = MatchScoreEntrySource.MANUAL
    assert (
        build_source_preview(match, tournament, events, participants, target)[0].conflict_token
        != original
    )


def test_token_is_stable_for_event_order_and_bound_to_match():
    match, tournament = records()
    events = [event("HALF1"), event("HALF2", event_id=2)]
    token = build_source_preview(
        match, tournament, events, (TeamId(11), TeamId(12)), MatchScoreEntrySource.EVENTS
    )[0].conflict_token
    assert (
        build_source_preview(
            match,
            tournament,
            list(reversed(events)),
            (TeamId(11), TeamId(12)),
            MatchScoreEntrySource.EVENTS,
        )[0].conflict_token
        == token
    )
    other = match.model_copy(update={"id": 2})
    assert (
        build_source_preview(
            other, tournament, [], (TeamId(11), TeamId(12)), MatchScoreEntrySource.EVENTS
        )[0].conflict_token
        != token
    )


@pytest.mark.parametrize("target", [None, "null", "LEGACY", "invalid"])
def test_only_explicit_valid_targets(target):
    with pytest.raises(ValidationError):
        ScoreSourcePreviewBody(target_source=target)


@pytest.mark.parametrize("token", [None, "", "old", "z" * 64])
def test_confirmation_requires_valid_token(token):
    with pytest.raises(ValidationError):
        ScoreSourceConfirmBody(target_source="EVENTS", conflict_token=token)


def test_standard_is_rejected():
    match, tournament = records(HockeyMode.STANDARD)
    with pytest.raises(HTTPException) as error:
        build_source_preview(match, tournament, [], (None, None), MatchScoreEntrySource.EVENTS)
    assert error.value.status_code == 422


@pytest.mark.parametrize("status", list(MatchStatus))
def test_rankings_warning_only_for_finished_score_changes(status):
    match, tournament = records()
    match = match.model_copy(update={"status": status})
    preview, _ = build_source_preview(
        match, tournament, [], (None, None), MatchScoreEntrySource.EVENTS
    )
    assert preview.rankings_may_change == (status is MatchStatus.FINISHED)
