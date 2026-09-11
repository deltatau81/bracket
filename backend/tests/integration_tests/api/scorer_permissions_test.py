from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import aiohttp
import pytest

from bracket.database import database
from bracket.models.db.account import UserAccountType
from bracket.models.db.match import Match, MatchBody, MatchStatus
from bracket.models.db.stage_item import StageType
from bracket.models.db.stage_item_inputs import StageItemInputInsertable
from bracket.models.db.tournament import HockeyAgeCategory, HockeyRuleset
from bracket.models.db.user_x_club import UserXClubInsertable, UserXClubRelation
from bracket.schema import matches
from bracket.sql.matches import sql_update_match_results
from bracket.utils.db import fetch_one_parsed_certain
from bracket.utils.dummy_records import (
    DUMMY_COURT1,
    DUMMY_MATCH1,
    DUMMY_ROUND1,
    DUMMY_STAGE1,
    DUMMY_STAGE_ITEM1,
    DUMMY_TEAM1,
    DUMMY_TEAM2,
)
from bracket.utils.http import HTTPMethod
from tests.integration_tests.api.shared import (
    get_root_uvicorn_url,
)
from tests.integration_tests.mocks import get_mock_token, get_mock_user
from tests.integration_tests.models import AuthContext
from tests.integration_tests.sql import (
    inserted_court,
    inserted_match,
    inserted_round,
    inserted_stage,
    inserted_stage_item,
    inserted_stage_item_input,
    inserted_team,
    inserted_user,
    inserted_user_x_club,
)


@asynccontextmanager
async def scorer_auth_context(
    auth_context: AuthContext,
) -> AsyncIterator[AuthContext]:
    mock_user = get_mock_user().model_copy(
        update={"account_type": UserAccountType.SCORER}
    )

    headers = {
        "Authorization": f"Bearer {get_mock_token(mock_user)}",
    }

    async with (
        inserted_user(mock_user) as scorer_user,
        inserted_user_x_club(
            UserXClubInsertable(
                user_id=scorer_user.id,
                club_id=auth_context.club.id,
                relation=UserXClubRelation.COLLABORATOR,
            )
        ) as scorer_user_x_club,
    ):
        yield auth_context.model_copy(
            update={
                "user": scorer_user,
                "user_x_club": scorer_user_x_club,
                "headers": headers,
            }
        )


@pytest.mark.parametrize(
    "account_type",
    [
        UserAccountType.REGULAR,
        UserAccountType.ADMIN,
        UserAccountType.SCORER,
    ],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_supported_account_types_are_persisted_and_serialized(
    startup_and_shutdown_uvicorn_server: None,
    account_type: UserAccountType,
) -> None:
    user = get_mock_user().model_copy(
        update={"account_type": account_type}
    )
    headers = {"Authorization": f"Bearer {get_mock_token(user)}"}

    async with inserted_user(user):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                get_root_uvicorn_url() + "users/me",
                headers=headers,
            ) as response:
                body = await response.json()
                assert response.status == 200, body
                assert body["data"]["account_type"] == account_type.value


@asynccontextmanager
async def scorer_match_context(
    auth_context: AuthContext,
    *,
    is_draft: bool = True,
    status: MatchStatus = MatchStatus.PLANNED,
) -> AsyncIterator[dict[str, Any]]:
    tournament_id = auth_context.tournament.id

    async with (
        inserted_stage(
            DUMMY_STAGE1.model_copy(
                update={"tournament_id": tournament_id}
            )
        ) as stage,
        inserted_stage_item(
            DUMMY_STAGE_ITEM1.model_copy(
                update={
                    "stage_id": stage.id,
                    "ranking_id": auth_context.ranking.id,
                    "type": StageType.SWISS,
                }
            )
        ) as stage_item,
        inserted_round(
            DUMMY_ROUND1.model_copy(
                update={
                    "stage_item_id": stage_item.id,
                    "is_draft": is_draft,
                }
            )
        ) as round_,
        inserted_team(
            DUMMY_TEAM1.model_copy(
                update={"tournament_id": tournament_id}
            )
        ) as team1,
        inserted_team(
            DUMMY_TEAM2.model_copy(
                update={"tournament_id": tournament_id}
            )
        ) as team2,
        inserted_stage_item_input(
            StageItemInputInsertable(
                slot=0,
                team_id=team1.id,
                tournament_id=tournament_id,
                stage_item_id=stage_item.id,
            )
        ) as input1,
        inserted_stage_item_input(
            StageItemInputInsertable(
                slot=1,
                team_id=team2.id,
                tournament_id=tournament_id,
                stage_item_id=stage_item.id,
            )
        ) as input2,
        inserted_court(
            DUMMY_COURT1.model_copy(
                update={"tournament_id": tournament_id}
            )
        ) as court,
        inserted_match(
            DUMMY_MATCH1.model_copy(
                update={
                    "round_id": round_.id,
                    "stage_item_input1_id": input1.id,
                    "stage_item_input2_id": input2.id,
                    "court_id": court.id,
                    "stage_item_input1_half1_score": 4,
                    "stage_item_input2_half1_score": 3,
                    "stage_item_input1_half2_score": 2,
                    "stage_item_input2_half2_score": 1,
                    "stage_item_input1_penalty_score": 1,
                    "stage_item_input2_penalty_score": 0,
                    "stage_item_input1_score": 6,
                    "stage_item_input2_score": 4,
                    "custom_duration_minutes": 17,
                    "custom_margin_minutes": 8,
                    "ruleset_override": HockeyRuleset.IIHF,
                    "age_category_override": HockeyAgeCategory.SENIOR,
                    "ruleset_season_override": "2029/30",
                    "status": status,
                }
            )
        ) as match,
    ):
        yield {
            "stage": stage,
            "stage_item": stage_item,
            "round": round_,
            "team1": team1,
            "team2": team2,
            "input1": input1,
            "input2": input2,
            "court": court,
            "match": match,
        }


async def send_tournament_request_with_status(
    method: HTTPMethod,
    endpoint: str,
    auth_context: AuthContext,
    json: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    url = (
        get_root_uvicorn_url()
        + f"tournaments/{auth_context.tournament.id}/{endpoint}"
    )

    async with aiohttp.ClientSession() as session:
        async with session.request(
            method=method.value,
            url=url,
            json=json,
            headers=auth_context.headers,
        ) as response:
            return response.status, await response.json()


@pytest.mark.asyncio(loop_scope="session")
async def test_scorer_cannot_manage_tournament_sponsors(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
) -> None:
    async with scorer_auth_context(auth_context) as scorer_context:
        response_status, body = await send_tournament_request_with_status(
            HTTPMethod.POST,
            "sponsors",
            scorer_context,
            json={
                "name": "Sponsor",
                "logo_path": "sponsor.png",
                "position": "LEFT",
            },
        )
        assert response_status == 403
        assert body["detail"] == "Administrator permissions required"

        upload_url = (
            get_root_uvicorn_url()
            + f"tournaments/{auth_context.tournament.id}/sponsors/999999/logo"
        )
        data = aiohttp.FormData()
        data.add_field("file", b"image", filename="sponsor.png", content_type="image/png")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                upload_url,
                headers=scorer_context.headers,
                data=data,
            ) as response:
                upload_body = await response.json()
                assert response.status == 403
                assert upload_body["detail"] == "Administrator permissions required"


@pytest.mark.asyncio(loop_scope="session")
async def test_scorer_result_update_preserves_administrative_match_fields(
    auth_context: AuthContext,
) -> None:
    async with scorer_match_context(
        auth_context,
        status=MatchStatus.RUNNING,
    ) as context:
        match = context["match"]

        before = await fetch_one_parsed_certain(
            database,
            Match,
            query=matches.select().where(matches.c.id == match.id),
        )

        body = MatchBody(
            round_id=context["round"].id,
            stage_item_input1_half1_score=5,
            status=MatchStatus.FINISHED,
        )

        await sql_update_match_results(
            match.id,
            before,
            body,
        )

        after = await fetch_one_parsed_certain(
            database,
            Match,
            query=matches.select().where(matches.c.id == match.id),
        )

        assert after.stage_item_input1_half1_score == 5

        assert after.stage_item_input2_half1_score == 3
        assert after.stage_item_input1_half2_score == 2
        assert after.stage_item_input2_half2_score == 1
        assert after.stage_item_input1_penalty_score == 1
        assert after.stage_item_input2_penalty_score == 0

        assert after.stage_item_input1_score == 7
        assert after.stage_item_input2_score == 4

        assert after.round_id == before.round_id
        assert after.court_id == before.court_id
        assert after.start_time == before.start_time
        assert (
            after.custom_duration_minutes
            == before.custom_duration_minutes
        )
        assert (
            after.custom_margin_minutes
            == before.custom_margin_minutes
        )
        assert after.duration_minutes == before.duration_minutes
        assert after.margin_minutes == before.margin_minutes
        assert after.ruleset_override == before.ruleset_override
        assert (
            after.age_category_override
            == before.age_category_override
        )
        assert (
            after.ruleset_season_override
            == before.ruleset_season_override
        )

        assert after.status == MatchStatus.RUNNING


@pytest.mark.asyncio(loop_scope="session")
async def test_scorer_can_update_match_results(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
) -> None:
    async with (
        scorer_auth_context(auth_context) as scorer_context,
        scorer_match_context(
            auth_context,
            status=MatchStatus.PLANNED,
        ) as context,
    ):
        match = context["match"]

        status_code, response = await send_tournament_request_with_status(
            HTTPMethod.PUT,
            f"matches/{match.id}",
            scorer_context,
            json={
                "round_id": context["round"].id,
                "stage_item_input1_half1_score": 7,
                "stage_item_input2_half1_score": 5,
            },
        )

        assert status_code == 200, response

        updated_match = await fetch_one_parsed_certain(
            database,
            Match,
            query=matches.select().where(matches.c.id == match.id),
        )

        assert updated_match.stage_item_input1_half1_score == 7
        assert updated_match.stage_item_input2_half1_score == 5

        assert updated_match.stage_item_input1_half2_score == 2
        assert updated_match.stage_item_input2_half2_score == 1
        assert updated_match.stage_item_input1_penalty_score == 1
        assert updated_match.stage_item_input2_penalty_score == 0

        assert updated_match.stage_item_input1_score == 9
        assert updated_match.stage_item_input2_score == 6

        assert updated_match.status == MatchStatus.PLANNED

        assert updated_match.court_id == match.court_id
        assert updated_match.start_time == match.start_time
        assert (
            updated_match.custom_duration_minutes
            == match.custom_duration_minutes
        )
        assert (
            updated_match.custom_margin_minutes
            == match.custom_margin_minutes
        )
        assert (
            updated_match.ruleset_override
            == match.ruleset_override
        )
        assert (
            updated_match.age_category_override
            == match.age_category_override
        )
        assert (
            updated_match.ruleset_season_override
            == match.ruleset_season_override
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_scorer_cannot_update_match_status_through_general_put(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
) -> None:
    async with (
        scorer_auth_context(auth_context) as scorer_context,
        scorer_match_context(
            auth_context,
            status=MatchStatus.PLANNED,
        ) as context,
    ):
        match = context["match"]

        status_code, response = await send_tournament_request_with_status(
            HTTPMethod.PUT,
            f"matches/{match.id}",
            scorer_context,
            json={
                "round_id": context["round"].id,
                "stage_item_input1_half1_score": 4,
                "stage_item_input2_half1_score": 3,
                "stage_item_input1_half2_score": 2,
                "stage_item_input2_half2_score": 1,
                "stage_item_input1_penalty_score": 1,
                "stage_item_input2_penalty_score": 0,
                "status": "RUNNING",
            },
        )

        assert status_code == 403, response

        unchanged_match = await fetch_one_parsed_certain(
            database,
            Match,
            query=matches.select().where(matches.c.id == match.id),
        )

        assert unchanged_match.status == MatchStatus.PLANNED
        assert unchanged_match.stage_item_input1_half1_score == 4
        assert unchanged_match.stage_item_input2_half1_score == 3
        assert unchanged_match.stage_item_input1_half2_score == 2
        assert unchanged_match.stage_item_input2_half2_score == 1
        assert unchanged_match.stage_item_input1_penalty_score == 1
        assert unchanged_match.stage_item_input2_penalty_score == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_scorer_cannot_update_administrative_match_fields(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
) -> None:
    async with (
        scorer_auth_context(auth_context) as scorer_context,
        scorer_match_context(auth_context) as context,
    ):
        match = context["match"]

        forbidden_bodies = (
            {
                "round_id": context["round"].id,
                "court_id": None,
            },
            {
                "round_id": context["round"].id,
                "start_time": None,
            },
            {
                "round_id": context["round"].id,
                "custom_duration_minutes": 25,
            },
            {
                "round_id": context["round"].id,
                "custom_margin_minutes": 12,
            },
            {
                "round_id": context["round"].id,
                "ruleset_override": "DEB",
            },
            {
                "round_id": context["round"].id,
                "age_category_override": "U15",
            },
            {
                "round_id": context["round"].id,
                "ruleset_season_override": "2026/27",
            },
        )

        for body in forbidden_bodies:
            status_code, response = (
                await send_tournament_request_with_status(
                    HTTPMethod.PUT,
                    f"matches/{match.id}",
                    scorer_context,
                    json=body,
                )
            )

            assert status_code == 403, {
                "body": body,
                "response": response,
            }

        unchanged_match = await fetch_one_parsed_certain(
            database,
            Match,
            query=matches.select().where(matches.c.id == match.id),
        )

        assert unchanged_match.court_id == match.court_id
        assert unchanged_match.start_time == match.start_time
        assert (
            unchanged_match.custom_duration_minutes
            == match.custom_duration_minutes
        )
        assert (
            unchanged_match.custom_margin_minutes
            == match.custom_margin_minutes
        )
        assert (
            unchanged_match.ruleset_override
            == match.ruleset_override
        )
        assert (
            unchanged_match.age_category_override
            == match.age_category_override
        )
        assert (
            unchanged_match.ruleset_season_override
            == match.ruleset_season_override
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_scorer_cannot_create_or_delete_matches(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
) -> None:
    async with (
        scorer_auth_context(auth_context) as scorer_context,
        scorer_match_context(
            auth_context,
            is_draft=True,
        ) as context,
    ):
        create_body = {
            "team1_id": context["team1"].id,
            "team2_id": context["team2"].id,
            "round_id": context["round"].id,
            "court_id": context["court"].id,
        }

        status_code, response = await send_tournament_request_with_status(
            HTTPMethod.POST,
            "matches",
            scorer_context,
            json=create_body,
        )

        assert status_code == 403, response

        status_code, response = await send_tournament_request_with_status(
            HTTPMethod.DELETE,
            f"matches/{context['match'].id}",
            scorer_context,
        )

        assert status_code == 403, response

        stored_match = await fetch_one_parsed_certain(
            database,
            Match,
            query=matches.select().where(
                matches.c.id == context["match"].id
            ),
        )

        assert stored_match.id == context["match"].id


@pytest.mark.asyncio(loop_scope="session")
async def test_scorer_can_manage_match_events(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
) -> None:
    async with (
        scorer_auth_context(auth_context) as scorer_context,
        scorer_match_context(auth_context) as context,
    ):
        match = context["match"]

        status_code, response = await send_tournament_request_with_status(
            HTTPMethod.POST,
            f"matches/{match.id}/phase",
            scorer_context,
            json={"action": "START_MATCH"},
        )
        assert status_code == 200, response
        assert response["data"]["status"] == "RUNNING"
        assert response["data"]["phase_state"] == "ACTIVE"

        goal_body = {
            "team_id": context["team1"].id,
            "event_type": "GOAL",
            "period": "HALF1",
            "game_time_seconds": 120,
            "player_number": 9,
            "player_name": "Testspieler",
        }

        status_code, response = await send_tournament_request_with_status(
            HTTPMethod.POST,
            f"matches/{match.id}/events",
            scorer_context,
            json=goal_body,
        )

        assert status_code == 200, response
        goal = response["data"]
        assert goal["event_type"] == "GOAL"
        assert goal["player_number"] == 9

        penalty_body = {
            "team_id": context["team2"].id,
            "event_type": "PENALTY",
            "period": "HALF1",
            "game_time_seconds": 180,
            "penalty_type": "Team penalty",
            "penalty_minutes": 2,
            "infraction": "Too many players",
        }

        status_code, response = await send_tournament_request_with_status(
            HTTPMethod.POST,
            f"matches/{match.id}/events",
            scorer_context,
            json=penalty_body,
        )

        assert status_code == 200, response
        penalty = response["data"]
        assert penalty["event_type"] == "PENALTY"
        assert penalty["penalty_minutes"] == 2

        status_code, response = await send_tournament_request_with_status(
            HTTPMethod.PUT,
            f"matches/{match.id}/events/{goal['id']}",
            scorer_context,
            json=goal_body | {"game_time_seconds": 135},
        )

        assert status_code == 200, response
        assert response["data"]["game_time_seconds"] == 135

        status_code, response = await send_tournament_request_with_status(
            HTTPMethod.DELETE,
            f"matches/{match.id}/events/{goal['id']}",
            scorer_context,
        )

        assert status_code == 200, response


@pytest.mark.asyncio(loop_scope="session")
async def test_scorer_cannot_update_tournament(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
) -> None:
    async with scorer_auth_context(auth_context) as scorer_context:
        status_code, response = await send_tournament_request_with_status(
            HTTPMethod.PUT,
            "",
            scorer_context,
            json={
                "name": "Nicht erlaubt",
            },
        )

        assert status_code == 403, response


@pytest.mark.asyncio(loop_scope="session")
async def test_scorer_cannot_manage_club_users(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
) -> None:
    async with scorer_auth_context(auth_context) as scorer_context:
        url = (
            get_root_uvicorn_url()
            + f"clubs/{auth_context.club.id}/users"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=scorer_context.headers,
            ) as response:
                body = await response.json()
                assert response.status == 403, body

            async with session.post(
                url,
                headers=scorer_context.headers,
                json={
                    "email": "forbidden-scorer@example.test",
                    "name": "Forbidden User",
                    "password": "test-password-123",
                    "account_type": "SCORER",
                },
            ) as response:
                body = await response.json()
                assert response.status == 403, body


@pytest.mark.asyncio(loop_scope="session")
async def test_regular_admin_can_create_scorer_user(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
) -> None:
    url = (
        get_root_uvicorn_url()
        + f"clubs/{auth_context.club.id}/users"
    )

    email = "new-scorer@example.test"

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            headers=auth_context.headers,
            json={
                "email": email,
                "name": "New Scorer",
                "password": "test-password-123",
                "account_type": "SCORER",
            },
        ) as response:
            body = await response.json()

            assert response.status == 200, body
            assert body["data"]["email"] == email
            assert body["data"]["account_type"] == "SCORER"

        async with session.get(
            url,
            headers=auth_context.headers,
        ) as response:
            body = await response.json()

            assert response.status == 200, body

            scorer = next(
                user
                for user in body["data"]
                if user["email"] == email
            )

            assert scorer["account_type"] == "SCORER"

    relation = await database.fetch_one(
        """
        SELECT relation
        FROM users_x_clubs
        WHERE user_id = (
            SELECT id
            FROM users
            WHERE email = :email
        )
        AND club_id = :club_id
        """,
        values={
            "email": email,
            "club_id": auth_context.club.id,
        },
    )

    assert relation is not None
    assert relation["relation"] == "COLLABORATOR"


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_user_endpoint_rejects_demo_accounts(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
) -> None:
    url = (
        get_root_uvicorn_url()
        + f"clubs/{auth_context.club.id}/users"
    )

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            headers=auth_context.headers,
            json={
                "email": "demo-not-allowed@example.test",
                "name": "Demo Not Allowed",
                "password": "test-password-123",
                "account_type": "DEMO",
            },
        ) as response:
            body = await response.json()

            assert response.status == 422, body
