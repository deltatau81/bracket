from contextlib import AsyncExitStack

import pytest

from bracket.database import database
from bracket.models.db.stage_item import StageItemCreateBody, StageType
from bracket.models.db.stage_item_inputs import StageItemInputCreateBodyFinal
from bracket.models.db.tournament import (
    HockeyMode,
    TournamentCompetitionFormat,
    TournamentInsertable,
)
from bracket.schema import matches, rounds, stage_items, stages, teams, tournaments
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.stage_item_inputs import sql_create_stage_item_input
from bracket.sql.stage_items import sql_create_stage_item
from bracket.utils.dummy_records import DUMMY_CLUB, DUMMY_STAGE1, DUMMY_TEAM1
from bracket.utils.http import HTTPMethod
from tests.integration_tests.api.shared import SUCCESS_RESPONSE, send_tournament_request
from tests.integration_tests.models import AuthContext
from tests.integration_tests.sql import (
    inserted_club,
    inserted_stage,
    inserted_team,
    inserted_tournament,
)


async def delete_generated_stage_items(stage_id: int) -> None:
    generated_stage_item_ids = stage_items.select().with_only_columns(stage_items.c.id).where(
        stage_items.c.stage_id == stage_id
    )
    await database.execute(
        query=matches.delete().where(
            matches.c.round_id.in_(
                rounds.select()
                .with_only_columns(rounds.c.id)
                .where(rounds.c.stage_item_id.in_(generated_stage_item_ids))
            )
        )
    )
    await database.execute(
        query=rounds.delete().where(rounds.c.stage_item_id.in_(generated_stage_item_ids))
    )
    await database.execute(query=stage_items.delete().where(stage_items.c.stage_id == stage_id))


async def create_youth_fixture(
    auth_context: AuthContext, club_count: int, groups: tuple[str, ...]
) -> tuple[AsyncExitStack, int, list[int]]:
    original_competition_format = await database.fetch_val(
        tournaments.select()
        .with_only_columns(tournaments.c.competition_format)
        .where(tournaments.c.id == auth_context.tournament.id)
    )

    await database.execute(
        query=tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
        values={"competition_format": TournamentCompetitionFormat.YOUTH_CLUB.value},
    )

    stack = AsyncExitStack()
    await stack.__aenter__()

    async def restore_competition_format() -> None:
        await database.execute(
            query=tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
            values={"competition_format": original_competition_format},
        )

    stack.push_async_callback(restore_competition_format)
    stage = await stack.enter_async_context(
        inserted_stage(DUMMY_STAGE1.model_copy(update={"tournament_id": auth_context.tournament.id}))
    )
    team_ids: list[int] = []
    for club_index in range(club_count):
        club = await stack.enter_async_context(
            inserted_club(DUMMY_CLUB.model_copy(update={"name": f"Youth Club {club_index}"}))
        )
        for group in groups:
            team = await stack.enter_async_context(
                inserted_team(
                    DUMMY_TEAM1.model_copy(
                        update={
                            "name": f"Club {club_index} {group}",
                            "tournament_id": auth_context.tournament.id,
                            "participant_club_id": club.id,
                            "pairing_group": group,
                        }
                    )
                )
            )
            team_ids.append(team.id)
    return stack, stage.id, team_ids


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize(
    ("club_count", "groups", "expected_matches"),
    [(2, ("A", "B"), 2), (3, ("A", "B"), 6), (6, ("A", "B"), 30), (3, ("A", "B", "C"), 9)],
)
async def test_youth_schedule_generation(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
    club_count: int,
    groups: tuple[str, ...],
    expected_matches: int,
) -> None:
    stack, stage_id, team_ids = await create_youth_fixture(auth_context, club_count, groups)
    try:
        response = await send_tournament_request(
            HTTPMethod.POST,
            f"stages/{stage_id}/youth_schedule",
            auth_context,
            json={"team_ids": team_ids},
        )
        assert response == SUCCESS_RESPONSE
        [stage] = await get_full_tournament_details(auth_context.tournament.id, stage_id=stage_id)
        generated_items = [item for item in stage.stage_items if item.type is StageType.ROUND_ROBIN]
        assert len(generated_items) == len(groups)
        assert all(item.is_youth_club_group for item in generated_items)
        assert sum(len(round_.matches) for item in generated_items for round_ in item.rounds) == expected_matches
        assert all(
            match.stage_item_input1.team_id is not None
            and match.stage_item_input2.team_id is not None
            and match.stage_item_input1.team_id != match.stage_item_input2.team_id
            and match.stage_item_input1.team.pairing_group == match.stage_item_input2.team.pairing_group
            and match.stage_item_input1.team.participant_club_id
            != match.stage_item_input2.team.participant_club_id
            for item in generated_items
            for round_ in item.rounds
            for match in round_.matches
        )
        assert all(
            match.score_entry_source.value == "MANUAL"
            for item in generated_items
            for round_ in item.rounds
            for match in round_.matches
        )
    finally:
        await delete_generated_stage_items(stage_id)
        await stack.aclose()


@pytest.mark.asyncio(loop_scope="session")
async def test_youth_schedule_rejects_invalid_selection_atomically(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    stack, stage_id, team_ids = await create_youth_fixture(auth_context, 2, ("A", "B"))
    try:
        invalid_ids = team_ids[:2] + [team_ids[0]]
        response = await send_tournament_request(
            HTTPMethod.POST,
            f"stages/{stage_id}/youth_schedule",
            auth_context,
            json={"team_ids": invalid_ids},
        )
        assert response["detail"] == "Selected team IDs must be unique"
        assert await database.fetch_val(
            stage_items.select().with_only_columns(stage_items.c.id).where(stage_items.c.stage_id == stage_id)
        ) is None

        response = await send_tournament_request(
            HTTPMethod.POST,
            f"stages/{stage_id}/youth_schedule",
            auth_context,
            json={"team_ids": team_ids[:1]},
        )
        assert "at least two teams" in response["detail"]
        assert await database.fetch_val(
            stage_items.select().with_only_columns(stage_items.c.id).where(stage_items.c.stage_id == stage_id)
        ) is None
    finally:
        await delete_generated_stage_items(stage_id)
        await stack.aclose()


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize(
    ("mutation", "expected_detail"),
    [
        ("missing_club", "must have a participant club"),
        ("null_group", "must have a pairing group"),
        ("blank_group", "must have a pairing group"),
        ("duplicate_club_group", "contains a club more than once"),
    ],
)
async def test_youth_schedule_rejects_invalid_team_metadata(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
    mutation: str,
    expected_detail: str,
) -> None:
    stack, stage_id, team_ids = await create_youth_fixture(auth_context, 2, ("A", "B"))
    try:
        if mutation == "missing_club":
            await database.execute(
                query=teams.update().where(teams.c.id == team_ids[0]),
                values={"participant_club_id": None},
            )
        elif mutation in {"null_group", "blank_group"}:
            await database.execute(
                query=teams.update().where(teams.c.id == team_ids[0]),
                values={"pairing_group": None if mutation == "null_group" else "  "},
            )
        else:
            first_team_club_id = await database.fetch_val(
                teams.select()
                .with_only_columns(teams.c.participant_club_id)
                .where(teams.c.id == team_ids[0])
            )
            assert first_team_club_id is not None

            await database.execute(
                query=teams.update().where(teams.c.id == team_ids[2]),
                values={
                    "participant_club_id": first_team_club_id,
                    "pairing_group": "A",
                },
            )
        response = await send_tournament_request(
            HTTPMethod.POST,
            f"stages/{stage_id}/youth_schedule",
            auth_context,
            json={"team_ids": team_ids},
        )
        assert expected_detail in response["detail"]
        assert await database.fetch_val(
            stage_items.select().with_only_columns(stage_items.c.id).where(stage_items.c.stage_id == stage_id)
        ) is None
    finally:
        await delete_generated_stage_items(stage_id)
        await stack.aclose()


@pytest.mark.asyncio(loop_scope="session")
async def test_youth_schedule_rejects_team_from_another_tournament(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    stack, stage_id, team_ids = await create_youth_fixture(auth_context, 2, ("A", "B"))
    other_tournament = await stack.enter_async_context(
        inserted_tournament(
            TournamentInsertable(
                **auth_context.tournament.model_dump(exclude={"id"})
                | {
                    "name": "Other tournament",
                    "club_id": auth_context.club.id,
                    "dashboard_endpoint": None,
                }
            )
        )
    )
    other_team = await stack.enter_async_context(
        inserted_team(
            DUMMY_TEAM1.model_copy(
                update={
                    "tournament_id": other_tournament.id,
                    "participant_club_id": auth_context.club.id,
                    "pairing_group": "A",
                }
            )
        )
    )
    try:
        response = await send_tournament_request(
            HTTPMethod.POST,
            f"stages/{stage_id}/youth_schedule",
            auth_context,
            json={"team_ids": team_ids[:1] + [other_team.id]},
        )
        assert response["detail"] == "All selected teams must belong to the tournament"
    finally:
        await delete_generated_stage_items(stage_id)
        await stack.aclose()


@pytest.mark.asyncio(loop_scope="session")
async def test_youth_schedule_rejects_duplicate_generation(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    stack, stage_id, team_ids = await create_youth_fixture(auth_context, 2, ("A", "B"))
    try:
        body = {"team_ids": team_ids}
        assert await send_tournament_request(
            HTTPMethod.POST, f"stages/{stage_id}/youth_schedule", auth_context, json=body
        ) == SUCCESS_RESPONSE
        response = await send_tournament_request(
            HTTPMethod.POST, f"stages/{stage_id}/youth_schedule", auth_context, json=body
        )
        assert response["detail"] == "Pairing group A has already been generated"
    finally:
        await delete_generated_stage_items(stage_id)
        await stack.aclose()


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize("hockey_mode", [HockeyMode.GAME_SHOOTOUT, HockeyMode.COMPETITION])
async def test_youth_schedule_requires_youth_club_format(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
    hockey_mode: HockeyMode,
) -> None:
    stack, stage_id, team_ids = await create_youth_fixture(auth_context, 2, ("A",))
    try:
        await database.execute(
            query=tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
            values={
                "competition_format": TournamentCompetitionFormat.STANDARD.value,
                "hockey_mode": hockey_mode.value,
            },
        )
        response = await send_tournament_request(
            HTTPMethod.POST,
            f"stages/{stage_id}/youth_schedule",
            auth_context,
            json={"team_ids": team_ids},
        )
        assert response["detail"] == (
            "Youth schedule generation requires YOUTH_CLUB competition format"
        )
        assert await database.fetch_val(
            stage_items.select()
            .with_only_columns(stage_items.c.id)
            .where(stage_items.c.stage_id == stage_id)
        ) is None
    finally:
        await delete_generated_stage_items(stage_id)
        await stack.aclose()


@pytest.mark.asyncio(loop_scope="session")
async def test_youth_schedule_score_source_for_game_shootout(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    await database.execute(
        query=tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
        values={"hockey_mode": HockeyMode.GAME_SHOOTOUT.value},
    )
    stack, stage_id, team_ids = await create_youth_fixture(auth_context, 2, ("A", "B"))
    try:
        assert await send_tournament_request(
            HTTPMethod.POST, f"stages/{stage_id}/youth_schedule", auth_context, json={"team_ids": team_ids}
        ) == SUCCESS_RESPONSE
        [stage] = await get_full_tournament_details(auth_context.tournament.id, stage_id=stage_id)
        assert all(
            match.score_entry_source.value == "MANUAL"
            for item in stage.stage_items
            for round_ in item.rounds
            for match in round_.matches
        )
    finally:
        await delete_generated_stage_items(stage_id)
        await stack.aclose()
        await database.execute(
            query=tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
            values={"hockey_mode": HockeyMode.COMPETITION.value},
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_manual_round_robin_does_not_trigger_youth_duplicate_guard(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    stack, stage_id, team_ids = await create_youth_fixture(auth_context, 2, ("A",))
    try:
        manual_item = await sql_create_stage_item(
            auth_context.tournament.id,
            StageItemCreateBody(
                stage_id=stage_id,
                name="Manual round robin",
                type=StageType.ROUND_ROBIN,
                team_count=2,
            ),
        )
        for slot, team_id in enumerate(team_ids, start=1):
            await sql_create_stage_item_input(
                auth_context.tournament.id,
                manual_item.id,
                StageItemInputCreateBodyFinal(slot=slot, team_id=team_id),
            )
        assert manual_item.is_youth_club_group is False

        assert await send_tournament_request(
            HTTPMethod.POST,
            f"stages/{stage_id}/youth_schedule",
            auth_context,
            json={"team_ids": team_ids},
        ) == SUCCESS_RESPONSE
        [stage] = await get_full_tournament_details(auth_context.tournament.id, stage_id=stage_id)
        assert len(stage.stage_items) == 2
        assert sum(item.is_youth_club_group for item in stage.stage_items) == 1
    finally:
        await delete_generated_stage_items(stage_id)
        await stack.aclose()
