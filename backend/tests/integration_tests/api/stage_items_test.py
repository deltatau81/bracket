import pytest

from bracket.database import database
from bracket.models.db.match import MatchScoreEntrySource
from bracket.models.db.stage_item import StageType
from bracket.models.db.stage_item_inputs import StageItemInputCreateBodyFinal
from bracket.schema import matches, rounds, stage_items, stages
from bracket.sql.stage_items import get_stage_item
from bracket.utils.dummy_records import (
    DUMMY_STAGE1,
    DUMMY_STAGE2,
    DUMMY_STAGE_ITEM1,
    DUMMY_TEAM1,
)
from bracket.utils.http import HTTPMethod
from tests.integration_tests.api.shared import (
    SUCCESS_RESPONSE,
    send_tournament_request,
)
from tests.integration_tests.models import AuthContext
from tests.integration_tests.sql import (
    assert_row_count_and_clear,
    inserted_stage,
    inserted_stage_item,
    inserted_team,
)


@pytest.mark.asyncio(loop_scope="session")
async def test_create_stage_item(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with (
        inserted_stage(
            DUMMY_STAGE2.model_copy(update={"tournament_id": auth_context.tournament.id})
        ) as stage_inserted_1,
        inserted_team(
            DUMMY_TEAM1.model_copy(update={"tournament_id": auth_context.tournament.id})
        ) as team_inserted_1,
        inserted_team(
            DUMMY_TEAM1.model_copy(update={"tournament_id": auth_context.tournament.id})
        ) as team_inserted_2,
    ):
        assert team_inserted_1.id and team_inserted_2.id
        inputs = [
            StageItemInputCreateBodyFinal(slot=1, team_id=team_inserted_1.id).model_dump(),
            StageItemInputCreateBodyFinal(slot=2, team_id=team_inserted_2.id).model_dump(),
        ]
        assert (
            await send_tournament_request(
                HTTPMethod.POST,
                "stage_items",
                auth_context,
                json={
                    "type": StageType.SINGLE_ELIMINATION.value,
                    "team_count": 2,
                    "stage_id": stage_inserted_1.id,
                    "inputs": inputs,
                },
            )
            == SUCCESS_RESPONSE
        )
        await assert_row_count_and_clear(matches, 1)
        await assert_row_count_and_clear(rounds, 1)
        await assert_row_count_and_clear(stage_items, 1)
        await assert_row_count_and_clear(stages, 1)


@pytest.mark.asyncio(loop_scope="session")
async def test_create_round_robin_stage_item_generates_matches(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with inserted_stage(
        DUMMY_STAGE2.model_copy(update={"tournament_id": auth_context.tournament.id})
    ) as stage_inserted:
        response = await send_tournament_request(
            HTTPMethod.POST,
            "stage_items",
            auth_context,
            json={
                "type": StageType.ROUND_ROBIN.value,
                "team_count": 4,
                "stage_id": stage_inserted.id,
            },
        )

        assert response == SUCCESS_RESPONSE
        stage_item_row = await database.fetch_one(
            stage_items.select()
            .where(stage_items.c.stage_id == stage_inserted.id)
            .order_by(stage_items.c.id.desc())
        )
        assert stage_item_row is not None
        stage_item = await get_stage_item(auth_context.tournament.id, stage_item_row["id"])
        assert len(stage_item.rounds) == 3
        assert [len(round_.matches) for round_ in stage_item.rounds] == [2, 2, 2]
        assert all(
            match.score_entry_source is MatchScoreEntrySource.MANUAL
            for round_ in stage_item.rounds
            for match in round_.matches
        )
        await assert_row_count_and_clear(matches, 6)
        await assert_row_count_and_clear(rounds, 3)
        await assert_row_count_and_clear(stage_items, 1)


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_stage_item(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with (
        inserted_team(DUMMY_TEAM1.model_copy(update={"tournament_id": auth_context.tournament.id})),
        inserted_stage(
            DUMMY_STAGE2.model_copy(update={"tournament_id": auth_context.tournament.id})
        ) as stage_inserted_1,
        inserted_stage_item(
            DUMMY_STAGE_ITEM1.model_copy(
                update={"stage_id": stage_inserted_1.id, "ranking_id": auth_context.ranking.id}
            )
        ) as stage_item_inserted,
    ):
        assert (
            await send_tournament_request(
                HTTPMethod.DELETE, f"stage_items/{stage_item_inserted.id}", auth_context, {}
            )
            == SUCCESS_RESPONSE
        )
        await assert_row_count_and_clear(stages, 0)


@pytest.mark.asyncio(loop_scope="session")
async def test_update_stage_item(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    body = {"name": "Optimus", "ranking_id": auth_context.ranking.id}
    async with (
        inserted_stage(
            DUMMY_STAGE1.model_copy(update={"tournament_id": auth_context.tournament.id})
        ) as stage_inserted,
        inserted_stage_item(
            DUMMY_STAGE_ITEM1.model_copy(
                update={"stage_id": stage_inserted.id, "ranking_id": auth_context.ranking.id}
            )
        ) as stage_item_inserted,
    ):
        assert (
            await send_tournament_request(
                HTTPMethod.PUT, f"stage_items/{stage_item_inserted.id}", auth_context, json=body
            )
            == SUCCESS_RESPONSE
        )

        assert auth_context.tournament.id
        updated_stage_item = await get_stage_item(
            auth_context.tournament.id, stage_item_inserted.id
        )
        assert updated_stage_item.name == body["name"]
