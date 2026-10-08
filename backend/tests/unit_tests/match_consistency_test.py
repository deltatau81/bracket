import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from bracket.logic.permissions import validate_match_update_permissions
from bracket.models.db.account import UserAccountType
from bracket.models.db.match import Match, MatchBody, MatchScoreEntrySource
from bracket.models.db.tournament import HockeyMode
from bracket.sql.matches import (
    ScoreEntrySourceConflictError,
    _score_update_values,
    sql_update_match,
    sql_update_match_results,
)
from bracket.utils.dummy_records import DUMMY_MATCH1, DUMMY_TOURNAMENT


class MatchConsistencyTest(unittest.IsolatedAsyncioTestCase):
    def current(self):
        return Match.model_validate({**DUMMY_MATCH1.model_dump(), "id": 1,
            "stage_item_input1_score": 7, "stage_item_input2_score": 4,
            "stage_item_input1_half1_score": 5, "stage_item_input2_half1_score": 3,
            "stage_item_input1_half2_score": 2, "stage_item_input2_half2_score": 1,
            "stage_item_input1_penalty_score": 1, "stage_item_input2_penalty_score": 2,
        })

    def test_partial_and_explicit_zero_by_mode(self):
        for mode in HockeyMode:
            with self.subTest(mode=mode):
                current = self.current()
                omitted = _score_update_values(current, MatchBody(round_id=current.round_id), mode)
                self.assertTrue(all(value == getattr(current, key) for key, value in omitted.items()))
                body = MatchBody(round_id=current.round_id, stage_item_input1_half1_score=0,
                                 stage_item_input2_penalty_score=0)
                values = _score_update_values(current, body, mode)
                self.assertEqual(values["stage_item_input1_half1_score"], 0)
                self.assertEqual(values["stage_item_input2_penalty_score"], 0)
                self.assertEqual(values["stage_item_input1_score"],
                                 2 if mode is HockeyMode.COMPETITION else 7)

    def test_full_update_and_null_contract(self):
        current = self.current()
        for field in ("stage_item_input1_half1_score", "stage_item_input1_penalty_score"):
            with self.assertRaises(ValidationError):
                MatchBody(round_id=current.round_id, **{field: None})
        body = MatchBody(round_id=current.round_id, stage_item_input1_score=None,
                         stage_item_input1_half1_score=1, stage_item_input2_half1_score=2,
                         stage_item_input1_half2_score=3, stage_item_input2_half2_score=4,
                         stage_item_input1_penalty_score=5, stage_item_input2_penalty_score=6)
        values = _score_update_values(current, body, HockeyMode.COMPETITION)
        self.assertEqual(values["stage_item_input1_score"], 4)
        self.assertEqual(values["stage_item_input2_score"], 6)
        self.assertEqual(_score_update_values(current, body, HockeyMode.STANDARD)
                         ["stage_item_input1_score"], 7)

    async def test_standard_and_game_updates_keep_explicit_totals(self):
        current = self.current()
        body = MatchBody(round_id=current.round_id, stage_item_input1_score=0,
                         stage_item_input2_score=9)
        for mode in (HockeyMode.STANDARD, HockeyMode.GAME_SHOOTOUT):
            with self.subTest(mode=mode), patch("bracket.sql.matches.sql_get_match", AsyncMock(return_value=current)), patch("bracket.sql.matches.database.execute", AsyncMock()) as execute:
                await sql_update_match(current.id, body, DUMMY_TOURNAMENT.model_copy(update={"hockey_mode": mode}))
                values = execute.call_args.kwargs["values"]
                self.assertEqual(values["stage_item_input1_score"], 0)
                self.assertEqual(values["stage_item_input2_score"], 9)
                self.assertEqual(values["stage_item_input1_half1_score"], 5)
                self.assertEqual(values["court_id"], current.court_id)
                self.assertEqual(values["duration_minutes"], current.duration_minutes)
                self.assertEqual(values["margin_minutes"], current.margin_minutes)
                self.assertFalse(values["ruleset_override_is_set"])

    async def test_repeated_partial_saves_are_identical(self):
        current = self.current()
        body = MatchBody(round_id=current.round_id, stage_item_input1_penalty_score=0)
        with patch("bracket.sql.matches.sql_get_match", AsyncMock(return_value=current)), patch("bracket.sql.matches.database.execute", AsyncMock()) as execute:
            await sql_update_match(current.id, body, DUMMY_TOURNAMENT)
            await sql_update_match(current.id, body, DUMMY_TOURNAMENT)
            self.assertEqual(execute.call_args_list[0], execute.call_args_list[1])

    async def test_scorer_game_scores_are_saved(self):
        current = self.current()
        body = MatchBody(round_id=current.round_id, stage_item_input1_score=0)
        with patch("bracket.sql.matches.database.execute", AsyncMock()) as execute:
            await sql_update_match_results(current.id, current, body, HockeyMode.GAME_SHOOTOUT)
            values = execute.call_args.kwargs["values"]
            self.assertEqual(values["stage_item_input1_score"], 0)
            self.assertEqual(values["stage_item_input2_score"], 4)
            self.assertEqual(values["stage_item_input1_penalty_score"], 1)
            self.assertNotIn("court_id", values)

    def test_scorer_permissions_are_mode_specific(self):
        current = self.current()
        user = SimpleNamespace(account_type=UserAccountType.SCORER)
        body = MatchBody(round_id=current.round_id, stage_item_input1_score=2)
        validate_match_update_permissions(user, current, body, HockeyMode.GAME_SHOOTOUT)
        for mode in (HockeyMode.STANDARD, HockeyMode.COMPETITION):
            with self.assertRaises(HTTPException) as error:
                validate_match_update_permissions(user, current, body, mode)
            self.assertEqual(error.exception.status_code, 403)
        for field, value in (("court_id", None), ("status", "FINISHED"), ("custom_duration_minutes", 12)):
            with self.assertRaises(HTTPException):
                validate_match_update_permissions(user, current,
                    MatchBody(round_id=current.round_id, **{field: value}), HockeyMode.GAME_SHOOTOUT)

    async def test_events_source_remains_protected(self):
        current = self.current().model_copy(update={"score_entry_source": MatchScoreEntrySource.EVENTS})
        with patch("bracket.sql.matches.database.execute", AsyncMock()) as execute:
            with self.assertRaises(ScoreEntrySourceConflictError):
                await sql_update_match_results(current.id, current,
                    MatchBody(round_id=current.round_id, stage_item_input1_score=0), HockeyMode.GAME_SHOOTOUT)
            execute.assert_not_awaited()
