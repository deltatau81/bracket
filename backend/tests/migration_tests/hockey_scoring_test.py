"""Run against a disposable PostgreSQL database named *_slice5a_migrations."""

from decimal import Decimal

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError

from alembic import command
from bracket.database import engine
from bracket.logic.ranking.calculation import determine_ranking_for_stage_item
from bracket.models.db.tournament import HOCKEY_SCORING_FIELDS, HockeyMode, HockeyScoring
from bracket.schema import metadata
from bracket.utils.alembic import get_alembic_config
from tests.unit_tests.ranking_calculation_test import make_round_robin_stage_item

HEAD = "hockey_scoring_rules_001"
PREVIOUS = "youth_club_format_001"


@pytest.fixture(autouse=True)
def disposable_schema():
    if not (engine.url.database or "").endswith("_slice5a_migrations"):
        pytest.skip("Requires a dedicated *_slice5a_migrations PostgreSQL database")
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    yield


def assert_scoring_schema():
    columns = {column["name"]: column for column in inspect(engine).get_columns("tournaments")}
    constraints = {row["name"] for row in inspect(engine).get_check_constraints("tournaments")}
    for field in HOCKEY_SCORING_FIELDS:
        column = columns[field]
        assert column["type"].precision == 8
        assert column["type"].scale == 2
        assert not column["nullable"]
        assert Decimal(column["default"].split("::")[0].strip("'")) == getattr(
            HockeyScoring(), field
        )
        assert f"ck_tournaments_{field}" in constraints
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == HEAD
        )
        assert connection.execute(text("SHOW server_version_num")).scalar_one().startswith("17")


def test_fresh_project_bootstrap():
    # Existing project procedure: create metadata, then stamp the current head.
    metadata.create_all(engine)
    command.stamp(get_alembic_config(), "head")
    command.upgrade(get_alembic_config(), "head")
    assert_scoring_schema()


def test_existing_head_upgrade_defaults_constraints_and_downgrade():
    metadata.create_all(engine)
    command.stamp(get_alembic_config(), "head")
    command.downgrade(get_alembic_config(), PREVIOUS)
    assert not set(HOCKEY_SCORING_FIELDS) & {
        column["name"] for column in inspect(engine).get_columns("tournaments")
    }
    with engine.begin() as connection:
        club_id = connection.execute(
            text("INSERT INTO clubs (name) VALUES ('Migration club') RETURNING id")
        ).scalar_one()
        for mode in ("COMPETITION", "GAME_SHOOTOUT"):
            connection.execute(
                text("""
                INSERT INTO tournaments
                    (name, club_id, start_time, dashboard_public, hockey_mode)
                VALUES (:mode, :club_id, CURRENT_TIMESTAMP, true, :mode)
            """),
                {"mode": mode, "club_id": club_id},
            )
    command.upgrade(get_alembic_config(), "head")
    assert_scoring_schema()
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT * FROM tournaments ORDER BY id")).mappings().all()
    for row in rows:
        scoring = HockeyScoring.model_validate(dict(row))
        assert scoring == HockeyScoring()
        stage, ranking = make_round_robin_stage_item()
        mode = HockeyMode(row["hockey_mode"])
        assert determine_ranking_for_stage_item(
            stage, ranking, mode, scoring
        ) == determine_ranking_for_stage_item(stage, ranking, mode)

    for field in HOCKEY_SCORING_FIELDS:
        for invalid in ("-0.01", "NaN", "Infinity", "1000000"):
            with pytest.raises(DBAPIError), engine.begin() as connection:
                connection.execute(
                    text(f"UPDATE tournaments SET {field} = :value"), {"value": Decimal(invalid)}
                )
        with engine.begin() as connection:
            connection.execute(text(f"UPDATE tournaments SET {field} = 999999.99"))
            connection.execute(
                text(f"UPDATE tournaments SET {field} = :value"),
                {"value": getattr(HockeyScoring(), field)},
            )

    command.downgrade(get_alembic_config(), PREVIOUS)
    columns = {column["name"] for column in inspect(engine).get_columns("tournaments")}
    assert not set(HOCKEY_SCORING_FIELDS) & columns
    command.upgrade(get_alembic_config(), "head")
    assert_scoring_schema()
    with engine.connect() as connection:
        for row in connection.execute(text("SELECT * FROM tournaments")).mappings():
            assert HockeyScoring.model_validate(dict(row)) == HockeyScoring()
