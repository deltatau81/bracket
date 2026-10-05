from datetime import timedelta

from bracket.logic.planning.conflicts import get_conflicting_matches
from bracket.models.db.stage_item_inputs import StageItemInputFinal
from bracket.models.db.team import Team
from bracket.models.db.util import StageWithStageItems
from bracket.utils.dummy_records import DUMMY_MOCK_TIME
from bracket.utils.id_types import MatchId, StageId, StageItemInputId, TeamId, TournamentId
from tests.integration_tests.mocks import MOCK_NOW
from tests.unit_tests.mocks import (
    get_2_definitive_and_2_tentative_matches_mock,
    get_2_definitive_matches_mock,
    get_one_round_with_two_definitive_matches,
    get_stage_item_inputs_mock,
    get_stage_item_mock,
)


def test_get_conflicting_matches_conflicts_to_set() -> None:
    """
    Test `get_conflicting_matches` returns the right conflicts to set
    """
    tournament_id = TournamentId(-1)
    stage_item_inputs = get_stage_item_inputs_mock(tournament_id)
    match1, match2 = get_2_definitive_matches_mock(stage_item_inputs)
    rounds = get_one_round_with_two_definitive_matches(match1, match2)
    stage_item = StageWithStageItems(
        id=StageId(-1),
        tournament_id=tournament_id,
        name="",
        created=MOCK_NOW,
        is_active=False,
        stage_items=[get_stage_item_mock(stage_item_inputs, [rounds])],
    )

    assert get_conflicting_matches([stage_item]) == ({-1: [True, False], -2: [True, False]}, set())


def test_get_conflicting_matches_conflicts_to_clear() -> None:
    """
    Test `get_conflicting_matches` returns the right conflicts to clear
    """
    tournament_id = TournamentId(-1)
    stage_item_inputs = get_stage_item_inputs_mock(tournament_id)
    match1, match2 = get_2_definitive_matches_mock(
        stage_item_inputs, DUMMY_MOCK_TIME + timedelta(hours=1)
    )
    rounds = get_one_round_with_two_definitive_matches(match1, match2)
    stage_item = StageWithStageItems(
        id=StageId(-1),
        tournament_id=tournament_id,
        name="",
        created=MOCK_NOW,
        is_active=False,
        stage_items=[get_stage_item_mock(stage_item_inputs, [rounds])],
    )

    assert get_conflicting_matches([stage_item]) == ({}, {-1, -2})


def test_get_conflicting_matches_same_team_different_input_ids() -> None:
    tournament_id = TournamentId(-1)
    stage_item_inputs = get_stage_item_inputs_mock(tournament_id)
    shared_input = StageItemInputFinal(
        id=StageItemInputId(-5),
        team_id=TeamId(-1),
        slot=5,
        tournament_id=tournament_id,
        team=Team(**stage_item_inputs[0].team.model_dump(exclude={"id"}), id=TeamId(-1)),
    )
    match1, match2 = get_2_definitive_matches_mock(stage_item_inputs)
    match2 = match2.model_copy(
        update={
            "stage_item_input1_id": shared_input.id,
            "stage_item_input1": shared_input,
        }
    )
    rounds = get_one_round_with_two_definitive_matches(match1, match2)
    stage_item = StageWithStageItems(
        id=StageId(-1),
        tournament_id=tournament_id,
        name="",
        created=MOCK_NOW,
        is_active=False,
        stage_items=[get_stage_item_mock(stage_item_inputs, [rounds])],
    )

    conflicts, _ = get_conflicting_matches([stage_item])
    assert conflicts[-1] == [True, False]
    assert conflicts[-2] == [True, False]


def test_get_conflicting_matches_different_teams_same_club() -> None:
    tournament_id = TournamentId(-1)
    stage_item_inputs = get_stage_item_inputs_mock(tournament_id)
    team1 = stage_item_inputs[0].team.model_copy(update={"participant_club_id": 5})
    team2 = stage_item_inputs[2].team.model_copy(update={"participant_club_id": 5})
    match1, match2 = get_2_definitive_matches_mock(stage_item_inputs)
    match1 = match1.model_copy(update={"stage_item_input1": stage_item_inputs[0].model_copy(update={"team": team1})})
    match2 = match2.model_copy(
        update={
            "stage_item_input1": stage_item_inputs[2].model_copy(
                update={"team_id": TeamId(-3), "team": team2}
            )
        }
    )
    rounds = get_one_round_with_two_definitive_matches(match1, match2)
    stage_item = StageWithStageItems(
        id=StageId(-1),
        tournament_id=tournament_id,
        name="",
        created=MOCK_NOW,
        is_active=False,
        stage_items=[get_stage_item_mock(stage_item_inputs, [rounds])],
    )

    assert get_conflicting_matches([stage_item]) == ({}, {-1, -2})


def test_get_conflicting_matches_same_team_across_stage_items() -> None:
    tournament_id = TournamentId(-1)
    stage_item_inputs = get_stage_item_inputs_mock(tournament_id)
    match1, match2 = get_2_definitive_matches_mock(stage_item_inputs)
    match2 = match2.model_copy(
        update={
            "stage_item_input1_id": StageItemInputId(-5),
            "stage_item_input1": stage_item_inputs[2].model_copy(
                update={"id": StageItemInputId(-5), "team_id": TeamId(-3)}
            ),
        }
    )
    match3 = match2.model_copy(
        update={
            "id": MatchId(-3),
            "stage_item_input1_id": StageItemInputId(-6),
            "stage_item_input1": stage_item_inputs[0].model_copy(
                update={"id": StageItemInputId(-6)}
            ),
            "stage_item_input2_id": StageItemInputId(-7),
            "stage_item_input2": StageItemInputFinal(
                id=StageItemInputId(-7),
                team_id=TeamId(-6),
                slot=6,
                tournament_id=tournament_id,
                team=Team(**stage_item_inputs[3].team.model_dump(exclude={"id"}), id=TeamId(-6)),
            ),
        }
    )
    stage_item = StageWithStageItems(
        id=StageId(-1),
        tournament_id=tournament_id,
        name="",
        created=MOCK_NOW,
        is_active=False,
        stage_items=[
            get_stage_item_mock(
                stage_item_inputs,
                [get_one_round_with_two_definitive_matches(match1, match2)],
            ),
            get_stage_item_mock(
                stage_item_inputs,
                [get_one_round_with_two_definitive_matches(match3, match2)],
            ),
        ],
    )

    conflicts, _ = get_conflicting_matches([stage_item])
    assert conflicts[-1] == [True, False]
    assert conflicts[-3] == [True, False]


def test_get_conflicting_matches_preserves_unresolved_match_behavior() -> None:
    tournament_id = TournamentId(-1)
    stage_item_inputs = get_stage_item_inputs_mock(tournament_id)
    match1, match2, tentative1, tentative2 = get_2_definitive_and_2_tentative_matches_mock(
        stage_item_inputs
    )
    stage_item = StageWithStageItems(
        id=StageId(-1),
        tournament_id=tournament_id,
        name="",
        created=MOCK_NOW,
        is_active=False,
        stage_items=[
            get_stage_item_mock(
                stage_item_inputs,
                [
                    get_one_round_with_two_definitive_matches(match1, match2),
                    get_one_round_with_two_definitive_matches(match1, match2),
                ],
            )
        ],
    )
    stage_item.stage_items[0].rounds[1].matches = [tentative1, tentative2]

    conflicts, cleared = get_conflicting_matches([stage_item])
    assert conflicts[-1] == [True, False]
    assert conflicts[-2] == [True, False]
    assert -3 not in conflicts
    assert -4 not in conflicts
    assert cleared == set()
