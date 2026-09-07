#!/usr/bin/env bash
set -euo pipefail

CONTAINER="bracket-hockey-test-frontend"

docker exec "$CONTAINER" sh -c \
  'cd /app && npx tsc --noEmit && echo "TypeScript OK"'
