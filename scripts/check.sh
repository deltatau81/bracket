#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "== Backend tests =="
./scripts/test_backend.sh all

echo
echo "== Frontend TypeScript =="
./scripts/test_frontend.sh

echo
echo "== Git diff check =="
git -c core.filemode=false diff --check

echo
echo "All checks passed."
