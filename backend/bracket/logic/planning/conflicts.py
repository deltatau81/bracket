from collections import defaultdict

from bracket.database import database
from bracket.models.db.match import Match, MatchWithDetailsDefinitive
from bracket.models.db.util import StageWithStageItems
from bracket.utils.id_types import MatchId


def matches_overlap(match1: Match, match2: Match) -> bool:
    if (
        match1.start_time is None
        or match1.end_time is None
        or match2.start_time is None
        or match2.end_time is None
    ):
        return False

    return not (
        (match1.end_time < match2.end_time and match1.start_time < match2.start_time)
        or (match1.start_time > match2.start_time or match1.end_time > match2.end_time)
    )


def _match_input_identity(match: MatchWithDetailsDefinitive, side: int) -> tuple[str, int]:
    stage_item_input = getattr(match, f"stage_item_input{side}")
    if stage_item_input.team_id is not None:
        return "team", stage_item_input.team_id
    return "input", getattr(match, f"stage_item_input{side}_id")


def get_conflicting_matches(
    stages: list[StageWithStageItems],
) -> tuple[
    defaultdict[MatchId, list[bool]],
    set[MatchId],
]:
    matches = [
        match
        for stage in stages
        for stage_item in stage.stage_items
        for round_ in stage_item.rounds
        for match in round_.matches
        if isinstance(match, MatchWithDetailsDefinitive)
    ]

    conflicts_to_set: defaultdict[MatchId, list[bool]] = defaultdict(lambda: [False, False])
    matches_with_conflicts = set()
    conflicts_to_clear = set()

    for i, match1 in enumerate(matches):
        for match2 in matches[i + 1 :]:
            if match1.id == match2.id:
                continue

            match1_inputs = [_match_input_identity(match1, side) for side in (1, 2)]
            match2_inputs = [_match_input_identity(match2, side) for side in (1, 2)]
            conflicting_sides = [
                side2
                for side2, input2 in enumerate(match2_inputs)
                if input2 in match1_inputs
            ]

            if len(conflicting_sides) < 1:
                continue

            if matches_overlap(match1, match2):
                for side2 in conflicting_sides:
                    conflicts_to_set[match2.id][side2] = True
                    for side1, input1 in enumerate(match1_inputs):
                        if input1 == match2_inputs[side2]:
                            conflicts_to_set[match1.id][side1] = True

                matches_with_conflicts.add(match1.id)
                matches_with_conflicts.add(match2.id)

    for match in matches:
        if match.id not in matches_with_conflicts:
            conflicts_to_clear.add(match.id)

    assert set(conflicts_to_set.keys()).intersection(conflicts_to_clear) == set()
    return conflicts_to_set, conflicts_to_clear


async def set_conflicts(
    conflicts_to_set: dict[MatchId, list[bool]],
    conflicts_to_clear: set[MatchId],
) -> None:
    for match_id, conflict in conflicts_to_set.items():
        await database.execute(
            """
            UPDATE matches
            SET
                stage_item_input1_conflict = :conflict1_id,
                stage_item_input2_conflict = :conflict2_id
            WHERE id = :match_id
            """,
            values={
                "match_id": match_id,
                "conflict1_id": conflict[0],
                "conflict2_id": conflict[1],
            },
        )

    for match_id in conflicts_to_clear:
        await database.execute(
            """
            UPDATE matches
            SET
                stage_item_input1_conflict = false,
                stage_item_input2_conflict = false
            WHERE id = :match_id
            """,
            values={"match_id": match_id},
        )


async def handle_conflicts(stages: list[StageWithStageItems]) -> None:
    conflicts_to_set, conflicts_to_clear = get_conflicting_matches(stages)
    await set_conflicts(conflicts_to_set, conflicts_to_clear)
