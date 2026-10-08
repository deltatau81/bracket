from contextlib import AsyncExitStack
from decimal import Decimal

import aiohttp
import pytest

from bracket.database import database
from bracket.logic.ranking.calculation import recalculate_ranking_for_stage_item
from bracket.models.db.stage_item_inputs import StageItemInputInsertable
from bracket.models.db.tournament import HockeyMode, TournamentCompetitionFormat
from bracket.schema import (
    competition_disciplines,
    competition_results,
    competition_scoring,
    competitions,
    matches,
    rankings,
    rounds,
    stage_item_inputs,
    stage_items,
    stages,
    teams,
    tournaments,
)
from bracket.sql.competitions import get_tournament_overall_standings
from bracket.sql.stage_items import get_stage_item
from bracket.utils.dummy_records import (
    DUMMY_CLUB,
    DUMMY_MATCH1,
    DUMMY_MOCK_TIME,
    DUMMY_RANKING1,
    DUMMY_ROUND1,
    DUMMY_STAGE1,
    DUMMY_STAGE_ITEM1,
    DUMMY_TEAM1,
    DUMMY_TOURNAMENT,
)
from tests.integration_tests.api.shared import get_root_uvicorn_url
from tests.integration_tests.models import AuthContext
from tests.integration_tests.sql import (
    inserted_club,
    inserted_match,
    inserted_ranking,
    inserted_round,
    inserted_stage,
    inserted_stage_item,
    inserted_stage_item_input,
    inserted_team,
    inserted_tournament,
)


@pytest.mark.parametrize("format_", list(TournamentCompetitionFormat))
@pytest.mark.parametrize("mode", [HockeyMode.COMPETITION, HockeyMode.GAME_SHOOTOUT])
@pytest.mark.asyncio(loop_scope="session")
async def test_real_sql_and_http_combined_standings(
    auth_context: AuthContext, format_: TournamentCompetitionFormat, mode: HockeyMode
) -> None:
    async with AsyncExitStack() as stack:
        clubs = []
        for name in ("Participant Alpha", "Participant Beta", "Participant Zero"):
            clubs.append(
                await stack.enter_async_context(
                    inserted_club(DUMMY_CLUB.model_copy(update={"name": name}))
                )
            )
        assert all(club.id != auth_context.club.id for club in clubs)
        tournament = await stack.enter_async_context(
            inserted_tournament(
                DUMMY_TOURNAMENT.model_copy(
                    update={
                        "club_id": auth_context.club.id,
                        "dashboard_endpoint": None,
                        "competition_format": format_,
                        "hockey_mode": mode,
                        "game_win_points": Decimal("2.25"),
                        "game_draw_points": Decimal("0.35"),
                        "game_loss_points": Decimal("0.10"),
                        "shootout_win_points": Decimal("1.50"),
                        "shootout_draw_points": Decimal("0.25"),
                        "shootout_loss_points": Decimal("0.05"),
                    }
                )
            )
        )
        tid = tournament.id
        participants = []
        for name, club in (
            ("Alpha A", clubs[0]),
            ("Alpha B", clubs[0]),
            ("Beta", clubs[1]),
            ("No club 1", None),
            ("No club 2", None),
            ("Zero", clubs[2]),
        ):
            participants.append(
                await stack.enter_async_context(
                    inserted_team(
                        DUMMY_TEAM1.model_copy(
                            update={
                                "name": name,
                                "tournament_id": tid,
                                "participant_club_id": club.id if club else None,
                            }
                        )
                    )
                )
            )
        stage = await stack.enter_async_context(
            inserted_stage(DUMMY_STAGE1.model_copy(update={"tournament_id": tid}))
        )
        for index in range(2):
            ranking = await stack.enter_async_context(
                inserted_ranking(
                    DUMMY_RANKING1.model_copy(
                        update={
                            "tournament_id": tid,
                            "position": index,
                            "win_points": Decimal(7 + index),
                            "add_score_points": True,
                        }
                    )
                )
            )
            group = await stack.enter_async_context(
                inserted_stage_item(
                    DUMMY_STAGE_ITEM1.model_copy(
                        update={
                            "stage_id": stage.id,
                            "ranking_id": ranking.id,
                        }
                    )
                )
            )
            inputs = []
            for slot, team in enumerate(participants[:4], 1):
                inputs.append(
                    await stack.enter_async_context(
                        inserted_stage_item_input(
                            StageItemInputInsertable(
                                tournament_id=tid,
                                stage_item_id=group.id,
                                slot=slot,
                                team_id=team.id,
                            )
                        )
                    )
                )
            round_ = await stack.enter_async_context(
                inserted_round(DUMMY_ROUND1.model_copy(update={"stage_item_id": group.id}))
            )
            for first, second in ((0, 2), (1, 3)):
                await stack.enter_async_context(
                    inserted_match(
                        DUMMY_MATCH1.model_copy(
                            update={
                                "round_id": round_.id,
                                "court_id": None,
                                "position_in_schedule": index * 2 + first + 1,
                                "stage_item_input1_id": inputs[first].id,
                                "stage_item_input2_id": inputs[second].id,
                                "stage_item_input1_score": 2,
                                "stage_item_input2_score": 0,
                                "stage_item_input1_half1_score": 1,
                                "stage_item_input2_half1_score": 0,
                                "stage_item_input1_half2_score": 1,
                                "stage_item_input2_half2_score": 0,
                                "stage_item_input1_penalty_score": 1,
                                "stage_item_input2_penalty_score": 0,
                            }
                        )
                    )
                )
            await recalculate_ranking_for_stage_item(tid, await get_stage_item(tid, group.id))

        competition_ids = []
        try:
            for count in (2, 1):
                cid = await database.execute(
                    competitions.insert().values(
                        tournament_id=tid,
                        name=f"Technique {count}",
                        start_time=DUMMY_MOCK_TIME,
                    )
                )
                competition_ids.append(cid)
                for place, points in ((1, "1.25"), (2, "0.35"), (3, "0.10")):
                    await database.execute(
                        competition_scoring.insert().values(
                            competition_id=cid,
                            place=place,
                            points=Decimal(points),
                        )
                    )
                for index in range(count):
                    did = await database.execute(
                        competition_disciplines.insert().values(
                            competition_id=cid,
                            name=f"Discipline {index}",
                        )
                    )
                    for team, place in (
                        (participants[0], 1),
                        (participants[1], 2),
                        (participants[2], 3),
                        (participants[3], None),
                        (participants[4], 2),
                    ):
                        await database.execute(
                            competition_results.insert().values(
                                discipline_id=did,
                                team_id=team.id,
                                place=place,
                            )
                        )

            source_tables = (
                tournaments,
                teams,
                matches,
                stage_item_inputs,
                stages,
                stage_items,
                rounds,
                rankings,
                competitions,
                competition_disciplines,
                competition_results,
                competition_scoring,
            )

            async def snapshot():
                return [
                    [
                        dict(row)
                        for row in await database.fetch_all(table.select().order_by(table.c.id))
                    ]
                    for table in source_tables
                ]

            before = await snapshot()
            rows = await get_tournament_overall_standings(tid)
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    get_root_uvicorn_url() + f"tournaments/{tid}/overall_standings",
                    headers=auth_context.headers,
                ) as response:
                    assert response.status == 200
                    payload = await response.json()
            assert await snapshot() == before
            assert len(payload["data"]) == len(rows)

            win = Decimal("12.00" if mode is HockeyMode.COMPETITION else "7.50")
            loss = Decimal("0.50" if mode is HockeyMode.COMPETITION else "0.30")
            expected = []

            def expected_row(team, club, game, technique):
                return {
                    "team_id": team.id if team else None,
                    "team_name": team.name if team else None,
                    "club_id": club.id if club else None,
                    "club_name": club.name if club else None,
                    "game_points": f"{game:.2f}",
                    "competition_points": f"{technique:.2f}",
                    "total_points": f"{game + technique:.2f}",
                }

            if format_ is TournamentCompetitionFormat.STANDARD:
                for team, club, game, technique in (
                    (participants[0], clubs[0], win, Decimal("3.75")),
                    (participants[1], clubs[0], win, Decimal("1.05")),
                    (participants[2], clubs[1], loss, Decimal("0.30")),
                    (participants[3], None, loss, Decimal("0.00")),
                    (participants[4], None, Decimal("0.00"), Decimal("1.05")),
                    (participants[5], clubs[2], Decimal("0.00"), Decimal("0.00")),
                ):
                    expected.append(expected_row(team, club, game, technique))
            else:
                for team, club, game, technique in (
                    (None, clubs[0], win * 2, Decimal("4.80")),
                    (None, clubs[1], loss, Decimal("0.30")),
                    (None, clubs[2], Decimal("0.00"), Decimal("0.00")),
                    (participants[3], None, loss, Decimal("0.00")),
                    (participants[4], None, Decimal("0.00"), Decimal("1.05")),
                ):
                    expected.append(expected_row(team, club, game, technique))
            expected.sort(
                key=lambda item: (-Decimal(item["total_points"]), -Decimal(item["game_points"]))
            )
            assert payload == {"data": expected}
            assert all(item["club_id"] != auth_context.club.id for item in payload["data"])
            for field in ("game_points", "competition_points", "total_points"):
                assert sum(Decimal(item[field]) for item in payload["data"]) == sum(
                    getattr(item, field) for item in rows
                )
            assert sum(Decimal(item["competition_points"]) for item in payload["data"]) == Decimal(
                "6.15"
            )
            assert (
                sum(Decimal(item["game_points"]) for item in payload["data"]) == 2 * win + 2 * loss
            )
        finally:
            for cid in competition_ids:
                await database.execute(competitions.delete().where(competitions.c.id == cid))
