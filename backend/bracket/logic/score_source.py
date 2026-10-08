import hashlib
import hmac
import json
from collections import Counter

from fastapi import HTTPException

from bracket.config import config
from bracket.database import database
from bracket.models.db.match import Match, MatchPeriod, MatchScoreEntrySource, MatchStatus
from bracket.models.db.match_event import MatchEvent, MatchEventType
from bracket.models.db.score_source import (
    ScoreSourcePreview,
    SectionScoreDifference,
    SectionScores,
)
from bracket.models.db.tournament import HockeyMode, Tournament
from bracket.utils.id_types import MatchId, TeamId

SCORE_COLUMNS = {
    MatchPeriod.GAME: ("stage_item_input1_score", "stage_item_input2_score"),
    MatchPeriod.HALF1: ("stage_item_input1_half1_score", "stage_item_input2_half1_score"),
    MatchPeriod.HALF2: ("stage_item_input1_half2_score", "stage_item_input2_half2_score"),
    MatchPeriod.SHOOTOUT: ("stage_item_input1_penalty_score", "stage_item_input2_penalty_score"),
}
ALL_SCORE_FIELDS = tuple(field for pair in SCORE_COLUMNS.values() for field in pair)


def source_periods(mode: HockeyMode) -> tuple[MatchPeriod, ...]:
    if mode is HockeyMode.GAME_SHOOTOUT:
        return MatchPeriod.GAME, MatchPeriod.SHOOTOUT
    if mode is HockeyMode.COMPETITION:
        return MatchPeriod.HALF1, MatchPeriod.HALF2, MatchPeriod.SHOOTOUT
    raise HTTPException(422, "Score source switching is only supported for hockey matches")


def section_scores(values: dict[str, int], mode: HockeyMode) -> list[SectionScores]:
    return [
        SectionScores(
            period=period,
            team1_score=values[SCORE_COLUMNS[period][0]],
            team2_score=values[SCORE_COLUMNS[period][1]],
        )
        for period in source_periods(mode)
    ]


def build_source_preview(
    match: Match,
    tournament: Tournament,
    events: list[MatchEvent],
    participants: tuple[TeamId | None, TeamId | None],
    target: MatchScoreEntrySource,
) -> tuple[ScoreSourcePreview, dict[str, int]]:
    periods = source_periods(tournament.hockey_mode)
    current = {field: getattr(match, field) for field in ALL_SCORE_FIELDS}
    resulting = current.copy()
    goals = sorted(
        (
            event
            for event in events
            if event.match_id == match.id
            and event.event_type is MatchEventType.GOAL
            and MatchPeriod(event.period.value) in periods
            and event.team_id in participants
        ),
        key=lambda event: event.id,
    )
    # An already active target is a strict no-op, even if legacy scores disagree.
    if target is MatchScoreEntrySource.EVENTS and match.score_entry_source is not target:
        counts = Counter((event.team_id, event.period.value) for event in goals)
        for period in periods:
            for side, team_id in enumerate(participants):
                resulting[SCORE_COLUMNS[period][side]] = (
                    counts[(team_id, period.value)] if team_id is not None else 0
                )
        if tournament.hockey_mode is HockeyMode.COMPETITION:
            for side in (1, 2):
                resulting[f"stage_item_input{side}_score"] = (
                    resulting[f"stage_item_input{side}_half1_score"]
                    + resulting[f"stage_item_input{side}_half2_score"]
                )
    current_sections = section_scores(current, tournament.hockey_mode)
    resulting_sections = section_scores(resulting, tournament.hockey_mode)
    differences = [
        SectionScoreDifference(
            period=before.period,
            team1_difference=after.team1_score - before.team1_score,
            team2_difference=after.team2_score - before.team2_score,
        )
        for before, after in zip(current_sections, resulting_sections, strict=True)
    ]
    snapshot = {
        "contract": 1,
        "target": target.value,
        "match": match.model_dump(mode="json"),
        "participants": participants,
        "tournament": tournament.model_dump(mode="json"),
        "goals": [event.model_dump(mode="json") for event in goals],
    }
    token = hmac.new(
        config.jwt_secret.encode(),
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode(),
        hashlib.sha256,
    ).hexdigest()
    changed = current != resulting
    return ScoreSourcePreview(
        match_id=match.id,
        current_source=match.score_entry_source,
        target_source=target,
        current_scores=current_sections,
        resulting_scores=resulting_sections,
        differences=differences,
        relevant_goal_count=len(goals),
        scores_changed=changed,
        rankings_may_change=changed and match.status is MatchStatus.FINISHED,
        conflict_token=token,
    ), resulting


async def match_participants(match_id: MatchId) -> tuple[TeamId | None, TeamId | None]:
    row = await database.fetch_one(
        """
            SELECT input1.team_id AS team1_id, input2.team_id AS team2_id FROM matches
            LEFT JOIN stage_item_inputs input1 ON input1.id = matches.stage_item_input1_id
            LEFT JOIN stage_item_inputs input2 ON input2.id = matches.stage_item_input2_id
            WHERE matches.id = :id
        """,
        {"id": match_id},
    )
    assert row is not None
    return (
        TeamId(row["team1_id"]) if row["team1_id"] is not None else None,
        TeamId(row["team2_id"]) if row["team2_id"] is not None else None,
    )


async def save_score_source(
    match_id: MatchId, target: MatchScoreEntrySource, scores: dict[str, int]
) -> None:
    assignments = ", ".join(f"{field} = :{field}" for field in ALL_SCORE_FIELDS)
    await database.execute(
        f"UPDATE matches SET score_entry_source = :source, {assignments} WHERE id = :id",
        {"id": match_id, "source": target.value, **scores},
    )
