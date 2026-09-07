#!/usr/bin/env bash
set -euo pipefail

CONTAINER="bracket-hockey-test-backend"
VENV_BIN="/home/bracket/.local/share/virtualenvs/app-4PlAip0Q/bin"

docker exec "$CONTAINER" sh -c "
set -eu
PG_TEST_DSN=\"\${PG_DSN%/*}/bracket_pytest\"

case \"\$PG_TEST_DSN\" in
  */bracket_pytest) ;;
  *)
    echo 'SAFETY ERROR: migration database is not bracket_pytest' >&2
    exit 10
    ;;
esac

cd /app

ENVIRONMENT=CI PG_DSN=\"\$PG_TEST_DSN\" \"$VENV_BIN/python\" -c '
import os
from sqlalchemy import create_engine, text
from bracket.schema import metadata

engine = create_engine(os.environ[\"PG_DSN\"])
with engine.begin() as connection:
    connection.execute(text(\"DROP SCHEMA public CASCADE\"))
    connection.execute(text(\"CREATE SCHEMA public\"))
metadata.create_all(engine)
with engine.begin() as connection:
    connection.execute(text(\"ALTER TABLE match_events DROP COLUMN penalty_code\"))
    connection.execute(text(\"ALTER TABLE match_events DROP COLUMN penalty_rule\"))
    connection.execute(text(\"ALTER TABLE match_events DROP COLUMN game_misconduct\"))
'

ENVIRONMENT=CI PG_DSN=\"\$PG_TEST_DSN\" \"$VENV_BIN/alembic\" stamp hockey_match_phase_001
ENVIRONMENT=CI PG_DSN=\"\$PG_TEST_DSN\" \"$VENV_BIN/alembic\" upgrade head
ENVIRONMENT=CI PG_DSN=\"\$PG_TEST_DSN\" \"$VENV_BIN/alembic\" downgrade hockey_match_phase_001
ENVIRONMENT=CI PG_DSN=\"\$PG_TEST_DSN\" \"$VENV_BIN/alembic\" upgrade head
ENVIRONMENT=CI PG_DSN=\"\$PG_TEST_DSN\" \"$VENV_BIN/alembic\" current
"