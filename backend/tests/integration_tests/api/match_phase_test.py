import asyncio
from typing import Any

import pytest
from fastapi import HTTPException

import bracket.routes.matches as match_routes
from bracket.database import database
from bracket.logic.match_phase import MatchPhaseTransition
from bracket.models.db.match import (
    Match,
    MatchPeriod,
    MatchPhaseAction,
    MatchPhaseBody,
    MatchPhaseState,
    MatchStatus,
)
from bracket.schema import matches, stage_item_inputs, tournaments
from bracket.sql.matches import sql_transition_match_phase
from bracket.utils.db import fetch_one_parsed_certain
from bracket.utils.http import HTTPMethod
from tests.integration_tests.api.scorer_permissions_test import (
    scorer_auth_context,
    scorer_match_context,
    send_tournament_request_with_status,
)
from tests.integration_tests.models import AuthContext


async def phase_request(
    auth_context: AuthContext,
    match_id: int,
    action: str,
) -> tuple[int, dict[str, Any]]:
    return await send_tournament_request_with_status(
        HTTPMethod.POST,
        f"matches/{match_id}/phase",
        auth_context,
        json={"action": action},
    )


def phase_tuple(response: dict[str, Any]) -> tuple[str, str | None, str | None]:
    match = response["data"]
    return match["status"], match["active_period"], match["phase_state"]


@pytest.mark.asyncio(loop_scope="session")
async def test_competition_phase_sequence_and_isolation(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
) -> None:
    async with scorer_match_context(
        auth_context,
        is_draft=False,
        status=MatchStatus.PLANNED,
    ) as context:
        match = context["match"]
        isolated_fields = (
            "stage_item_input1_score",
            "stage_item_input2_score",
            "stage_item_input1_half1_score",
            "stage_item_input2_half1_score",
            "stage_item_input1_half2_score",
            "stage_item_input2_half2_score",
            "stage_item_input1_penalty_score",
            "stage_item_input2_penalty_score",
            "court_id",
            "start_time",
            "duration_minutes",
            "margin_minutes",
            "custom_duration_minutes",
            "custom_margin_minutes",
            "ruleset_override",
            "age_category_override",
            "ruleset_season_override",
        )
        expected = (
            ("START_MATCH", ("RUNNING", "HALF1", "ACTIVE")),
            ("END_PERIOD", ("RUNNING", "HALF1", "BREAK")),
            ("START_NEXT_PERIOD", ("RUNNING", "HALF2", "ACTIVE")),
            ("END_PERIOD", ("RUNNING", "HALF2", "BREAK")),
            ("START_NEXT_PERIOD", ("RUNNING", "SHOOTOUT", "ACTIVE")),
            ("FINISH_MATCH", ("FINISHED", "SHOOTOUT", "BREAK")),
        )
        for action, next_state in expected:
            status_code, response = await phase_request(auth_context, match.id, action)
            assert status_code == 200, response
            assert phase_tuple(response) == next_state

        stored = await fetch_one_parsed_certain(
            database,
            Match,
            query=matches.select().where(matches.c.id == match.id),
        )
        assert stored.status.value == "FINISHED"
        assert stored.active_period is not None
        assert stored.active_period.value == "SHOOTOUT"
        assert stored.phase_state is not None
        assert stored.phase_state.value == "BREAK"
        for field in isolated_fields:
            assert getattr(stored, field) == getattr(match, field)


@pytest.mark.asyncio(loop_scope="session")
async def test_standard_phase_sequences(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
) -> None:
    await database.execute(
        query=tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
        values={"hockey_mode": "STANDARD"},
    )
    try:
        async with scorer_match_context(
            auth_context,
            is_draft=False,
            status=MatchStatus.PLANNED,
        ) as context:
            match_id = context["match"].id
            for action, expected in (
                ("START_MATCH", ("RUNNING", "PERIOD1", "ACTIVE")),
                ("END_PERIOD", ("RUNNING", "PERIOD1", "BREAK")),
                ("START_NEXT_PERIOD", ("RUNNING", "PERIOD2", "ACTIVE")),
                ("END_PERIOD", ("RUNNING", "PERIOD2", "BREAK")),
                ("START_NEXT_PERIOD", ("RUNNING", "PERIOD3", "ACTIVE")),
                ("FINISH_MATCH", ("FINISHED", "PERIOD3", "BREAK")),
            ):
                status_code, response = await phase_request(auth_context, match_id, action)
                assert status_code == 200, response
                assert phase_tuple(response) == expected

        async with scorer_match_context(
            auth_context,
            is_draft=False,
            status=MatchStatus.PLANNED,
        ) as context:
            match_id = context["match"].id
            for action in (
                "START_MATCH",
                "END_PERIOD",
                "START_NEXT_PERIOD",
                "END_PERIOD",
                "START_NEXT_PERIOD",
                "END_PERIOD",
            ):
                status_code, response = await phase_request(auth_context, match_id, action)
                assert status_code == 200, response
            status_code, response = await phase_request(
                auth_context,
                match_id,
                "START_OVERTIME",
            )
            assert status_code == 200, response
            assert phase_tuple(response) == ("RUNNING", "OVERTIME", "ACTIVE")
            status_code, response = await phase_request(
                auth_context,
                match_id,
                "FINISH_MATCH",
            )
            assert status_code == 200, response
            assert phase_tuple(response) == ("FINISHED", "OVERTIME", "BREAK")
    finally:
        await database.execute(
            query=tournaments.update().where(tournaments.c.id == auth_context.tournament.id),
            values={"hockey_mode": "COMPETITION"},
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_phase_endpoint_rejects_invalid_and_legacy_states(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
) -> None:
    async with scorer_match_context(
        auth_context,
        is_draft=False,
        status=MatchStatus.PLANNED,
    ) as context:
        match_id = context["match"].id
        status_code, response = await phase_request(
            auth_context,
            match_id,
            "START_NEXT_PERIOD",
        )
        assert status_code == 422, response

        await database.execute(
            query=matches.update().where(matches.c.id == match_id),
            values={"status": "RUNNING", "active_period": None, "phase_state": None},
        )
        status_code, response = await phase_request(auth_context, match_id, "END_PERIOD")
        assert status_code == 422, response
        assert "requires an active period" in response["detail"]

        await database.execute(
            query=matches.update().where(matches.c.id == match_id),
            values={"status": "FINISHED", "active_period": None, "phase_state": None},
        )
        status_code, response = await phase_request(auth_context, match_id, "REOPEN_MATCH")
        assert status_code == 422, response
        assert "requires an active period" in response["detail"]


@pytest.mark.asyncio(loop_scope="session")
async def test_scorer_can_transition_but_cannot_raw_write_phase(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
) -> None:
    async with (
        scorer_auth_context(auth_context) as scorer_context,
        scorer_match_context(
            auth_context,
            is_draft=False,
            status=MatchStatus.PLANNED,
        ) as context,
    ):
        match = context["match"]
        status_code, response = await phase_request(
            scorer_context,
            match.id,
            "START_MATCH",
        )
        assert status_code == 200, response
        assert phase_tuple(response) == ("RUNNING", "HALF1", "ACTIVE")

        status_code, response = await send_tournament_request_with_status(
            HTTPMethod.PUT,
            f"matches/{match.id}",
            scorer_context,
            json={
                "round_id": context["round"].id,
                "active_period": "HALF2",
                "phase_state": "BREAK",
            },
        )
        assert status_code == 422, response

        status_code, response = await send_tournament_request_with_status(
            HTTPMethod.PUT,
            f"matches/{match.id}",
            auth_context,
            json={
                "round_id": context["round"].id,
                "active_period": "HALF2",
                "phase_state": "BREAK",
            },
        )
        assert status_code == 422, response

        stored = await fetch_one_parsed_certain(
            database,
            Match,
            query=matches.select().where(matches.c.id == match.id),
        )
        assert stored.status.value == "RUNNING"
        assert stored.active_period is not None
        assert stored.active_period.value == "HALF1"
        assert stored.phase_state is not None
        assert stored.phase_state.value == "ACTIVE"


@pytest.mark.asyncio(loop_scope="session")
async def test_concurrent_phase_transition_is_applied_once(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
) -> None:
    async with scorer_match_context(
        auth_context,
        is_draft=False,
        status=MatchStatus.PLANNED,
    ) as context:
        match_id = context["match"].id
        status_code, response = await phase_request(auth_context, match_id, "START_MATCH")
        assert status_code == 200, response

        responses = await asyncio.gather(
            phase_request(auth_context, match_id, "END_PERIOD"),
            phase_request(auth_context, match_id, "END_PERIOD"),
        )
        status_codes = [status_code for status_code, _ in responses]
        assert status_codes.count(200) == 1
        assert len(status_codes) == 2
        # 422 means the loser observed BREAK before validation. 409 means it
        # observed ACTIVE but lost the optimistic compare-and-update race.
        assert next(code for code in status_codes if code != 200) in {409, 422}

        stored = await fetch_one_parsed_certain(
            database,
            Match,
            query=matches.select().where(matches.c.id == match_id),
        )
        assert stored.status is MatchStatus.RUNNING
        assert stored.active_period is MatchPeriod.HALF1
        assert stored.phase_state is MatchPhaseState.BREAK


@pytest.mark.asyncio(loop_scope="session")
async def test_phase_sql_rejects_a_deterministically_stale_expected_state(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
) -> None:
    async with scorer_match_context(
        auth_context,
        is_draft=False,
        status=MatchStatus.PLANNED,
    ) as context:
        match_id = context["match"].id
        await database.execute(
            query=matches.update().where(matches.c.id == match_id),
            values={
                "status": "RUNNING",
                "active_period": "HALF1",
                "phase_state": "ACTIVE",
            },
        )
        expected_status = MatchStatus.RUNNING
        expected_period = MatchPeriod.HALF1
        expected_phase = MatchPhaseState.ACTIVE
        next_state = MatchPhaseTransition(
            MatchStatus.RUNNING,
            MatchPeriod.HALF1,
            MatchPhaseState.BREAK,
        )

        updated = await sql_transition_match_phase(
            match_id,
            expected_status,
            expected_period,
            expected_phase,
            next_state,
        )
        assert updated is not None

        stale_result = await sql_transition_match_phase(
            match_id,
            expected_status,
            expected_period,
            expected_phase,
            next_state,
        )
        assert stale_result is None

        stored = await fetch_one_parsed_certain(
            database,
            Match,
            query=matches.select().where(matches.c.id == match_id),
        )
        assert stored.status is MatchStatus.RUNNING
        assert stored.active_period is MatchPeriod.HALF1
        assert stored.phase_state is MatchPhaseState.BREAK


@pytest.mark.asyncio(loop_scope="session")
async def test_phase_endpoint_maps_stale_sql_result_to_conflict(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with scorer_match_context(
        auth_context,
        is_draft=False,
        status=MatchStatus.PLANNED,
    ) as context:
        active_match = context["match"].model_copy(
            update={
                "status": MatchStatus.RUNNING,
                "active_period": MatchPeriod.HALF1,
                "phase_state": MatchPhaseState.ACTIVE,
            }
        )

        async def stale_update(*args: object, **kwargs: object) -> None:
            return None

        monkeypatch.setattr(match_routes, "sql_transition_match_phase", stale_update)

        with pytest.raises(HTTPException) as exception:
            await match_routes.transition_match_phase_by_id(
                auth_context.tournament.id,
                active_match.id,
                MatchPhaseBody(action=MatchPhaseAction.END_PERIOD),
                auth_context.user,
                auth_context.tournament,
                active_match,
            )
        assert exception.value.status_code == 409


@pytest.mark.asyncio(loop_scope="session")
async def test_finish_and_reopen_recalculate_ranking(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
) -> None:
    async with scorer_match_context(
        auth_context,
        is_draft=False,
        status=MatchStatus.PLANNED,
    ) as context:
        match_id = context["match"].id
        input1_id = context["input1"].id
        input2_id = context["input2"].id

        for action in (
            "START_MATCH",
            "END_PERIOD",
            "START_NEXT_PERIOD",
            "END_PERIOD",
            "START_NEXT_PERIOD",
        ):
            status_code, response = await phase_request(auth_context, match_id, action)
            assert status_code == 200, response

        before_finish = await database.fetch_one(
            query=stage_item_inputs.select().where(stage_item_inputs.c.id == input1_id)
        )
        assert before_finish is not None
        assert before_finish["wins"] == 0

        status_code, response = await phase_request(auth_context, match_id, "FINISH_MATCH")
        assert status_code == 200, response
        winner = await database.fetch_one(
            query=stage_item_inputs.select().where(stage_item_inputs.c.id == input1_id)
        )
        loser = await database.fetch_one(
            query=stage_item_inputs.select().where(stage_item_inputs.c.id == input2_id)
        )
        assert winner is not None
        assert loser is not None
        assert winner["wins"] == 1
        assert loser["losses"] == 1

        status_code, response = await phase_request(auth_context, match_id, "REOPEN_MATCH")
        assert status_code == 200, response
        winner = await database.fetch_one(
            query=stage_item_inputs.select().where(stage_item_inputs.c.id == input1_id)
        )
        loser = await database.fetch_one(
            query=stage_item_inputs.select().where(stage_item_inputs.c.id == input2_id)
        )
        assert winner is not None
        assert loser is not None
        assert winner["wins"] == 0
        assert loser["losses"] == 0
