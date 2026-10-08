from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from bracket.logic.ranking.overall_standings import aggregate_club_standings
from bracket.models.db.competition import TournamentOverallStanding
from bracket.models.db.tournament import TournamentCompetitionFormat
from bracket.sql import competitions
from bracket.utils.id_types import ClubId, TeamId, TournamentId


def row(team: int, club: int | None, game: str, technique: str) -> TournamentOverallStanding:
    return TournamentOverallStanding(
        team_id=TeamId(team),
        team_name=f"Team {team}",
        club_id=ClubId(club) if club is not None else None,
        club_name=f"Club {club}" if club is not None else None,
        game_points=Decimal(game),
        competition_points=Decimal(technique),
        total_points=Decimal(game) + Decimal(technique),
    )


@pytest.mark.parametrize("format_", list(TournamentCompetitionFormat))
@pytest.mark.asyncio
async def test_overall_endpoint_data_uses_format_without_changing_team_totals(
    monkeypatch: pytest.MonkeyPatch, format_: TournamentCompetitionFormat
) -> None:
    source = [
        row(1, 10, "3.35", "2.50"),
        row(2, 10, "1.50", "0.35"),
        row(3, 20, "1", "0"),
        row(4, None, "0", "0"),
    ]
    original = [item.model_dump() for item in source]

    async def tournament(_):
        return SimpleNamespace(competition_format=format_)

    async def fetch(_, model, query):
        assert model is TournamentOverallStanding
        sql = str(query.compile(dialect=postgresql.dialect()))
        assert "LEFT OUTER JOIN clubs" in sql
        # Both point sources are summed by team BEFORE joining them.
        assert sql.count("GROUP BY") == 2
        assert "sum(CAST(stage_item_inputs.points" in sql
        assert "sum(competition_scoring.points)" in sql
        assert "participant_club_id" in sql
        return source

    monkeypatch.setattr(competitions, "sql_get_tournament", tournament)
    monkeypatch.setattr(competitions, "fetch_all_parsed", fetch)
    result = await competitions.get_tournament_overall_standings(TournamentId(1))
    assert [item.model_dump() for item in source] == original
    if format_ is TournamentCompetitionFormat.STANDARD:
        assert result is source
        assert [item.team_id for item in result] == [1, 2, 3, 4]
    else:
        assert len(result) == 3
        club = result[0]
        assert club.club_id == 10 and club.club_name == "Club 10"
        assert club.team_id is None and club.team_name is None
        assert club.game_points == Decimal("4.85")
        assert club.competition_points == Decimal("2.85")
        assert club.total_points == Decimal("7.70")
        assert result[-1].team_id == 4 and result[-1].club_id is None


def test_empty_zero_and_single_team_clubs() -> None:
    assert aggregate_club_standings([]) == []
    source = [row(1, 10, "0", "0"), row(2, 10, "0", "0"), row(3, 20, "0.35", "0")]
    result = aggregate_club_standings(source)
    assert [item.club_id for item in result] == [20, 10]
    assert result[1].total_points == Decimal("0")
    assert result[0].game_points == Decimal("0.35")


def test_totals_not_double_counted_and_equal_totals_use_hockey_points() -> None:
    source = [
        row(1, 10, "1", "0.5"),
        row(2, 20, "2.5", "0.5"),
        row(3, 10, "1", "0.5"),
        row(4, None, "0", "3"),
    ]
    result = aggregate_club_standings(source)
    assert [item.club_id for item in result] == [20, 10, None]
    for field in ("game_points", "competition_points", "total_points"):
        assert sum(getattr(item, field) for item in result) == sum(
            getattr(item, field) for item in source
        )


def test_unassigned_teams_are_not_grouped_and_club_team_ids_do_not_collide() -> None:
    result = aggregate_club_standings(
        [row(1, 1, "1", "0"), row(2, None, "0", "0"), row(3, None, "0", "0")]
    )
    assert len(result) == 3
    assert result[0].club_id == 1 and result[0].team_id is None
    assert [item.team_id for item in result[1:]] == [2, 3]


def test_response_contract_and_backend_snapshot() -> None:
    import json
    from pathlib import Path

    from pydantic import TypeAdapter

    from openapi import openapi  # noqa: F401

    club = aggregate_club_standings([row(1, 10, "0.35", "0.50")])[0]
    payload = TypeAdapter(TournamentOverallStanding).dump_python(club, mode="json")
    assert payload["club_id"] == 10 and payload["club_name"] == "Club 10"
    assert payload["team_id"] is None and payload["team_name"] is None
    assert payload["game_points"] == "0.35"
    assert payload["competition_points"] == "0.50"
    assert payload["total_points"] == "0.85"
    snapshot = Path(__file__).resolve().parents[2] / "openapi/openapi.json"
    schema = json.loads(snapshot.read_text())["components"]["schemas"]["TournamentOverallStanding"]
    from bracket.app import app

    assert schema == app.openapi()["components"]["schemas"]["TournamentOverallStanding"]


def test_equal_clubs_preserve_deterministic_incoming_order() -> None:
    source = [row(1, 20, "1", "1"), row(2, 10, "1", "1")]
    assert [item.club_id for item in aggregate_club_standings(source)] == [20, 10]
