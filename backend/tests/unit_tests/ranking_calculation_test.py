from decimal import Decimal

import pytest
from heliclockter import datetime_utc

from bracket.logic.ranking import calculation as ranking_calculation
from bracket.logic.ranking.calculation import determine_ranking_for_stage_item
from bracket.logic.ranking.statistics import TeamStatistics
from bracket.models.db.match import MatchStatus, MatchWithDetails, MatchWithDetailsDefinitive
from bracket.models.db.ranking import Ranking
from bracket.models.db.stage_item import StageType
from bracket.models.db.stage_item_inputs import StageItemInputFinal
from bracket.models.db.team import Team
from bracket.models.db.util import RoundWithMatches, StageItemWithRounds
from bracket.utils.dummy_records import DUMMY_TEAM1, DUMMY_TEAM2
from bracket.utils.id_types import (
    MatchId,
    RankingId,
    RoundId,
    StageId,
    StageItemId,
    StageItemInputId,
    TeamId,
    TournamentId,
)


def test_determine_ranking_for_stage_item_elimination() -> None:
    tournament_id = TournamentId(-1)
    now = datetime_utc.now()
    stage_item_input1 = StageItemInputFinal(
        id=StageItemInputId(-1),
        team_id=TeamId(-1),
        slot=1,
        tournament_id=tournament_id,
        team=Team(**DUMMY_TEAM1.model_dump(), id=TeamId(-1)),
    )
    stage_item_input2 = StageItemInputFinal(
        id=StageItemInputId(-2),
        team_id=TeamId(-2),
        slot=1,
        tournament_id=tournament_id,
        team=Team(**DUMMY_TEAM2.model_dump(), id=TeamId(-2)),
    )

    ranking = determine_ranking_for_stage_item(
        StageItemWithRounds(
            rounds=[
                RoundWithMatches(
                    id=RoundId(-1),
                    matches=[
                        MatchWithDetailsDefinitive(
                            id=MatchId(-1),
                            stage_item_input1=stage_item_input1,
                            stage_item_input2=stage_item_input2,
                            created=now,
                            duration_minutes=90,
                            margin_minutes=15,
                            round_id=RoundId(-1),
                            stage_item_input1_score=2,
                            stage_item_input2_score=0,
                            stage_item_input1_conflict=False,
                            stage_item_input2_conflict=False,
                            status=MatchStatus.FINISHED,
                        ),
                        MatchWithDetailsDefinitive(
                            id=MatchId(-2),
                            stage_item_input1=stage_item_input1,
                            stage_item_input2=stage_item_input2,
                            created=now,
                            duration_minutes=90,
                            margin_minutes=15,
                            round_id=RoundId(-1),
                            stage_item_input1_score=2,
                            stage_item_input2_score=2,
                            stage_item_input1_conflict=False,
                            stage_item_input2_conflict=False,
                            status=MatchStatus.FINISHED,
                        ),
                        MatchWithDetails(  # This gets ignored in ranking calculation
                            id=MatchId(-3),
                            created=now,
                            duration_minutes=90,
                            margin_minutes=15,
                            round_id=RoundId(-1),
                            stage_item_input1_score=3,
                            stage_item_input2_score=2,
                            stage_item_input1_conflict=False,
                            stage_item_input2_conflict=False,
                            status=MatchStatus.FINISHED,
                        ),
                    ],
                    stage_item_id=StageItemId(-1),
                    created=now,
                    is_draft=False,
                    name="",
                )
            ],
            inputs=[stage_item_input1, stage_item_input2],
            type_name="Single Elimination",
            team_count=4,
            ranking_id=None,
            id=StageItemId(-1),
            stage_id=StageId(-1),
            name="",
            created=now,
            type=StageType.SINGLE_ELIMINATION,
        ),
        Ranking(
            id=RankingId(-1),
            tournament_id=tournament_id,
            created=now,
            win_points=Decimal("3.5"),
            draw_points=Decimal("1.25"),
            loss_points=Decimal("0.0"),
            add_score_points=False,
            position=0,
        ),
    )

    assert ranking == {
        -2: TeamStatistics(wins=0, draws=1, losses=1, points=Decimal("1.25")),
        -1: TeamStatistics(wins=1, draws=1, losses=0, points=Decimal("4.75")),
    }


def test_determine_ranking_for_stage_item_swiss() -> None:
    tournament_id = TournamentId(-1)
    now = datetime_utc.now()
    stage_item_input1 = StageItemInputFinal(
        id=StageItemInputId(-1),
        team_id=TeamId(-1),
        slot=1,
        tournament_id=tournament_id,
        team=Team(**DUMMY_TEAM1.model_dump(), id=TeamId(-1)),
    )
    stage_item_input2 = StageItemInputFinal(
        id=StageItemInputId(-2),
        team_id=TeamId(-2),
        slot=1,
        tournament_id=tournament_id,
        team=Team(**DUMMY_TEAM2.model_dump(), id=TeamId(-2)),
    )

    ranking = determine_ranking_for_stage_item(
        StageItemWithRounds(
            rounds=[
                RoundWithMatches(
                    id=RoundId(-1),
                    matches=[
                        MatchWithDetailsDefinitive(
                            id=MatchId(-1),
                            stage_item_input1=stage_item_input1,
                            stage_item_input2=stage_item_input2,
                            created=now,
                            duration_minutes=90,
                            margin_minutes=15,
                            round_id=RoundId(-1),
                            stage_item_input1_score=2,
                            stage_item_input2_score=0,
                            stage_item_input1_conflict=False,
                            stage_item_input2_conflict=False,
                            status=MatchStatus.FINISHED,
                        ),
                        MatchWithDetailsDefinitive(
                            id=MatchId(-2),
                            stage_item_input1=stage_item_input1,
                            stage_item_input2=stage_item_input2,
                            created=now,
                            duration_minutes=90,
                            margin_minutes=15,
                            round_id=RoundId(-1),
                            stage_item_input1_score=2,
                            stage_item_input2_score=2,
                            stage_item_input1_conflict=False,
                            stage_item_input2_conflict=False,
                            status=MatchStatus.FINISHED,
                        ),
                        MatchWithDetails(  # This gets ignored in ranking calculation
                            id=MatchId(-3),
                            created=now,
                            duration_minutes=90,
                            margin_minutes=15,
                            round_id=RoundId(-1),
                            stage_item_input1_score=3,
                            stage_item_input2_score=2,
                            stage_item_input1_conflict=False,
                            stage_item_input2_conflict=False,
                            status=MatchStatus.FINISHED,
                        ),
                    ],
                    stage_item_id=StageItemId(-1),
                    created=now,
                    is_draft=False,
                    name="",
                )
            ],
            inputs=[stage_item_input1, stage_item_input2],
            type_name="Swiss",
            team_count=4,
            ranking_id=None,
            id=StageItemId(-1),
            stage_id=StageId(-1),
            name="",
            created=now,
            type=StageType.SWISS,
        ),
        Ranking(
            id=RankingId(-1),
            tournament_id=tournament_id,
            created=now,
            win_points=Decimal("3.5"),
            draw_points=Decimal("1.25"),
            loss_points=Decimal("0.0"),
            add_score_points=False,
            position=0,
        ),
    )

    assert ranking == {
        -2: TeamStatistics(wins=0, draws=1, losses=1, points=Decimal("1208")),
        -1: TeamStatistics(wins=1, draws=1, losses=0, points=Decimal("1320")),
    }


def test_determine_ranking_for_stage_item_swiss_no_matches() -> None:
    tournament_id = TournamentId(-1)
    now = datetime_utc.now()
    stage_item_input1 = StageItemInputFinal(
        id=StageItemInputId(-1),
        team_id=TeamId(-1),
        slot=1,
        tournament_id=tournament_id,
        team=Team(**DUMMY_TEAM1.model_dump(), id=TeamId(-1)),
    )
    stage_item_input2 = StageItemInputFinal(
        id=StageItemInputId(-2),
        team_id=TeamId(-2),
        slot=1,
        tournament_id=tournament_id,
        team=Team(**DUMMY_TEAM2.model_dump(), id=TeamId(-2)),
    )

    ranking = determine_ranking_for_stage_item(
        StageItemWithRounds(
            rounds=[
                RoundWithMatches(
                    id=RoundId(-1),
                    matches=[],
                    stage_item_id=StageItemId(-1),
                    created=now,
                    is_draft=False,
                    name="",
                )
            ],
            inputs=[stage_item_input1, stage_item_input2],
            type_name="Swiss",
            team_count=2,
            ranking_id=None,
            id=StageItemId(-1),
            stage_id=StageId(-1),
            name="",
            created=now,
            type=StageType.SWISS,
        ),
        Ranking(
            id=RankingId(-1),
            tournament_id=tournament_id,
            created=now,
            win_points=Decimal("3.5"),
            draw_points=Decimal("1.25"),
            loss_points=Decimal("0.0"),
            add_score_points=False,
            position=0,
        ),
    )

    assert ranking == {
        -2: TeamStatistics(wins=0, draws=0, losses=0, points=Decimal("1200")),
        -1: TeamStatistics(wins=0, draws=0, losses=0, points=Decimal("1200")),
    }


@pytest.mark.parametrize(
    ("match_status", "score1", "score2", "expected"),
    [
        (MatchStatus.PLANNED, 0, 0, {}),
        (MatchStatus.RUNNING, 0, 0, {}),
        (MatchStatus.RUNNING, 2, 1, {}),
        (
            MatchStatus.FINISHED,
            0,
            0,
            {
                StageItemInputId(-1): TeamStatistics(draws=1, points=Decimal("1")),
                StageItemInputId(-2): TeamStatistics(draws=1, points=Decimal("1")),
            },
        ),
        (
            MatchStatus.FINISHED,
            2,
            1,
            {
                StageItemInputId(-1): TeamStatistics(wins=1, points=Decimal("3")),
                StageItemInputId(-2): TeamStatistics(losses=1, points=Decimal("0")),
            },
        ),
    ],
)
def test_only_finished_matches_are_ranked(
    match_status: MatchStatus,
    score1: int,
    score2: int,
    expected: dict[StageItemInputId, TeamStatistics],
) -> None:
    tournament_id = TournamentId(-1)
    now = datetime_utc.now()
    input1 = StageItemInputFinal(
        id=StageItemInputId(-1),
        team_id=TeamId(-1),
        slot=1,
        tournament_id=tournament_id,
        team=Team(**DUMMY_TEAM1.model_dump(), id=TeamId(-1)),
    )
    input2 = StageItemInputFinal(
        id=StageItemInputId(-2),
        team_id=TeamId(-2),
        slot=2,
        tournament_id=tournament_id,
        team=Team(**DUMMY_TEAM2.model_dump(), id=TeamId(-2)),
    )
    match = MatchWithDetailsDefinitive(
        id=MatchId(-1),
        stage_item_input1=input1,
        stage_item_input2=input2,
        stage_item_input1_id=input1.id,
        stage_item_input2_id=input2.id,
        created=now,
        duration_minutes=10,
        margin_minutes=5,
        round_id=RoundId(-1),
        stage_item_input1_score=score1,
        stage_item_input2_score=score2,
        stage_item_input1_conflict=False,
        stage_item_input2_conflict=False,
        status=match_status,
    )
    stage_item = StageItemWithRounds(
        rounds=[
            RoundWithMatches(
                id=RoundId(-1),
                matches=[match],
                stage_item_id=StageItemId(-1),
                created=now,
                is_draft=False,
                name="",
            )
        ],
        inputs=[input1, input2],
        type_name="Round Robin",
        team_count=2,
        ranking_id=None,
        id=StageItemId(-1),
        stage_id=StageId(-1),
        name="",
        created=now,
        type=StageType.ROUND_ROBIN,
    )
    ranking = Ranking(
        id=RankingId(-1),
        tournament_id=tournament_id,
        created=now,
        win_points=Decimal("3"),
        draw_points=Decimal("1"),
        loss_points=Decimal("0"),
        add_score_points=False,
        position=0,
    )

    assert determine_ranking_for_stage_item(stage_item, ranking) == expected


@pytest.mark.asyncio
async def test_recalculate_clears_stale_values_across_match_status_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tournament_id = TournamentId(-1)
    now = datetime_utc.now()
    input1 = StageItemInputFinal(
        id=StageItemInputId(-1),
        team_id=TeamId(-1),
        slot=1,
        tournament_id=tournament_id,
        team=Team(**DUMMY_TEAM1.model_dump(), id=TeamId(-1)),
    )
    input2 = StageItemInputFinal(
        id=StageItemInputId(-2),
        team_id=TeamId(-2),
        slot=2,
        tournament_id=tournament_id,
        team=Team(**DUMMY_TEAM2.model_dump(), id=TeamId(-2)),
    )
    ranking = Ranking(
        id=RankingId(-1),
        tournament_id=tournament_id,
        created=now,
        win_points=Decimal("3"),
        draw_points=Decimal("1"),
        loss_points=Decimal("0"),
        add_score_points=False,
        position=0,
    )
    stored = {
        input1.id: TeamStatistics(draws=3, points=Decimal("3")),
        input2.id: TeamStatistics(draws=3, points=Decimal("3")),
    }

    async def get_ranking(*_: object) -> Ranking:
        return ranking

    async def persist_stats(
        _: TournamentId,
        stage_item_input_id: StageItemInputId,
        statistics: TeamStatistics,
    ) -> None:
        stored[stage_item_input_id] = statistics

    monkeypatch.setattr(ranking_calculation, "get_ranking_for_stage_item", get_ranking)
    monkeypatch.setattr(ranking_calculation, "update_team_stats", persist_stats)

    def make_stage_item(
        first_status: MatchStatus,
        first_score1: int = 0,
        first_score2: int = 0,
    ) -> StageItemWithRounds:
        matches = [
            MatchWithDetailsDefinitive(
                id=MatchId(match_id),
                stage_item_input1=input1,
                stage_item_input2=input2,
                stage_item_input1_id=input1.id,
                stage_item_input2_id=input2.id,
                created=now,
                duration_minutes=10,
                margin_minutes=5,
                round_id=RoundId(-1),
                stage_item_input1_score=first_score1 if match_id == -1 else 0,
                stage_item_input2_score=first_score2 if match_id == -1 else 0,
                stage_item_input1_conflict=False,
                stage_item_input2_conflict=False,
                status=first_status if match_id == -1 else MatchStatus.PLANNED,
            )
            for match_id in (-1, -2, -3)
        ]
        return StageItemWithRounds(
            rounds=[
                RoundWithMatches(
                    id=RoundId(-1),
                    matches=matches,
                    stage_item_id=StageItemId(-1),
                    created=now,
                    is_draft=False,
                    name="",
                )
            ],
            inputs=[input1, input2],
            type_name="Round Robin",
            team_count=2,
            ranking_id=ranking.id,
            id=StageItemId(-1),
            stage_id=StageId(-1),
            name="",
            created=now,
            type=StageType.ROUND_ROBIN,
        )

    zero = TeamStatistics(points=Decimal("0"))
    transitions = [
        (MatchStatus.PLANNED, 0, 0, zero, zero),
        (MatchStatus.RUNNING, 0, 0, zero, zero),
        (MatchStatus.RUNNING, 2, 1, zero, zero),
        (
            MatchStatus.FINISHED,
            2,
            1,
            TeamStatistics(wins=1, points=Decimal("3")),
            TeamStatistics(losses=1, points=Decimal("0")),
        ),
        (MatchStatus.RUNNING, 2, 1, zero, zero),
    ]

    for status_, score1, score2, expected1, expected2 in transitions:
        await ranking_calculation.recalculate_ranking_for_stage_item(
            tournament_id, make_stage_item(status_, score1, score2)
        )
        assert stored == {input1.id: expected1, input2.id: expected2}
