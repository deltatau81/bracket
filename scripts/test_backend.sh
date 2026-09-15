#!/usr/bin/env bash
set -euo pipefail

CONTAINER="bracket-hockey-test-backend"
PYTEST="/home/bracket/.local/share/virtualenvs/app-4PlAip0Q/bin/pytest"

case "${1:-all}" in
  scorer)
    TESTS=(
      tests/integration_tests/api/scorer_permissions_test.py
    )
    ;;
  catalog)
    TESTS=(
      tests/unit_tests/penalty_catalog_test.py
    )
    ;;
  events)
    TESTS=(
      tests/integration_tests/api/match_events_test.py
    )
    ;;
  phase)
    TESTS=(
      tests/unit_tests/match_phase_test.py
      tests/integration_tests/api/match_phase_test.py
    )
    ;;
  sponsors)
    TESTS=(
      tests/integration_tests/api/tournament_sponsors_test.py
    )
    ;;
  authorization)
    TESTS=(
      tests/integration_tests/api/admin_authorization_test.py
    )
    ;;
  user_creation)
    TESTS=(
      tests/integration_tests/api/user_creation_authorization_test.py
    )
    ;;
  club_listing)
    TESTS=(
      tests/integration_tests/api/club_listing_authorization_test.py
    )
    ;;
  player_statistics)
    TESTS=(
      tests/integration_tests/api/player_statistics_test.py
    )
    ;;
  ranking)
    TESTS=(
      tests/unit_tests/ranking_calculation_test.py
    )
    ;;
  teams)
    TESTS=(
      tests/integration_tests/api/teams_test.py
    )
    ;;
  all)
    TESTS=(
      tests/unit_tests/penalty_catalog_test.py
      tests/unit_tests/ranking_calculation_test.py
      tests/integration_tests/api/scorer_permissions_test.py
      tests/integration_tests/api/match_events_test.py
      tests/unit_tests/match_phase_test.py
      tests/integration_tests/api/match_phase_test.py
      tests/integration_tests/api/tournament_sponsors_test.py
      tests/integration_tests/api/admin_authorization_test.py
      tests/integration_tests/api/user_creation_authorization_test.py
      tests/integration_tests/api/club_listing_authorization_test.py
      tests/integration_tests/api/player_statistics_test.py
      tests/integration_tests/api/teams_test.py
    )
    ;;
  *)
    echo "Usage: $0 {authorization|catalog|club_listing|player_statistics|ranking|scorer|events|phase|sponsors|teams|user_creation|all}"
    exit 2
    ;;
esac

printf -v TEST_ARGS ' %q' "${TESTS[@]}"

docker exec "$CONTAINER" sh -c "
set -eu
PG_TEST_DSN=\"\${PG_DSN%/*}/bracket_pytest\"

case \"\$PG_TEST_DSN\" in
  */bracket_pytest) ;;
  *)
    echo 'SAFETY ERROR: test database is not bracket_pytest' >&2
    exit 10
    ;;
esac

cd /app

ENVIRONMENT=CI \
TMPDIR=/tmp \
PG_DSN=\"\$PG_TEST_DSN\" \
\"$PYTEST\" \
-q \
-o cache_dir=/tmp/bracket-pytest-cache \
$TEST_ARGS
"
