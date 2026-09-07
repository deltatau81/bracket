# Development instructions

## Repository

This repository is the development/test version of the Bracket hockey tournament application.

Preserve existing uncommitted work. Do not overwrite unrelated changes.

Do not commit unless explicitly requested.

Never stage or modify `.vscode/`.

## Git

Because the repository is stored on an SMB/ACL-backed dataset, use:

git -c core.filemode=false ...

Do not treat file-mode-only changes as source changes.

Keep source files LF-only. Do not introduce CRLF line endings.

Before finishing a task run:

git -c core.filemode=false diff --check

It must complete without errors.

## Backend tests

Backend integration tests MUST NEVER run against the normal `bracket` database.

The dedicated integration-test database is:

bracket_pytest

Do not construct alternative test database commands yourself.

Use the repository test scripts:

./scripts/test_backend.sh scorer

for SCORER permission tests.

./scripts/test_backend.sh phase

for match-phase unit and integration tests.

./scripts/test_backend.sh all

for the current backend regression suite.

The scripts derive the test DSN from the test backend container environment and enforce `bracket_pytest`.

If Docker access is unavailable, report that clearly. Do not fall back to another database and do not run integration tests directly against the normal application database.

## Frontend tests

After relevant frontend changes run:

./scripts/test_frontend.sh

This executes TypeScript validation in the existing frontend test container.

## Full validation

For changes spanning backend and frontend, use:

./scripts/check.sh

This runs:
- backend regression tests
- frontend TypeScript validation
- git diff --check

## Test environment

Test backend container:

bracket-hockey-test-backend

Test frontend container:

bracket-hockey-test-frontend

Do not restart, replace, remove, recreate, or reconfigure production containers unless explicitly requested.

Do not use ad-hoc production `docker rm` or `docker run` commands.

## Scope discipline

Make only changes required for the current task.

Do not modify migrations, APIs, permissions, frontend behavior, or unrelated files unless the task explicitly requires them.

When tests fail, diagnose the failure before changing unrelated code.

At the end of a task report:
- files changed
- implementation summary
- tests executed
- test results
- git diff --check result
- anything that could not be tested

## Codex remote test execution

The Codex execution host does not have local Docker or Bash access.

Do NOT attempt to run Docker locally from Codex.

Run repository tests remotely on the TrueNAS host through the configured SSH alias:

truenas-bracket

Backend SCORER tests:

ssh truenas-bracket "cd /mnt/HDD/bracket-dev && bash scripts/test_backend.sh scorer"

Backend match-phase tests:

ssh truenas-bracket "cd /mnt/HDD/bracket-dev && bash scripts/test_backend.sh phase"

Full current backend regression suite:

ssh truenas-bracket "cd /mnt/HDD/bracket-dev && bash scripts/test_backend.sh all"

Frontend TypeScript validation:

ssh truenas-bracket "cd /mnt/HDD/bracket-dev && bash scripts/test_frontend.sh"

For backend + frontend validation, run the appropriate backend tests and frontend validation separately through SSH.

Never run integration tests against the normal `bracket` database.
The backend test scripts enforce use of `bracket_pytest`.

If SSH or the remote test command fails, report the failure. Never fall back to the production database.

Do not modify TrueNAS configuration, Docker containers, SSH configuration, or test database configuration while running tests.

## Test database isolation

All backend integration test suites use the same dedicated PostgreSQL database:

bracket_pytest

Because of this, backend integration suites MUST NOT be run in parallel.

Do not start SCORER, phase, event, or full backend integration suites concurrently.

Always run them sequentially.

Correct examples:

ssh truenas-bracket "cd /mnt/HDD/bracket-dev && bash scripts/test_backend.sh events"

ssh truenas-bracket "cd /mnt/HDD/bracket-dev && bash scripts/test_backend.sh scorer"

ssh truenas-bracket "cd /mnt/HDD/bracket-dev && bash scripts/test_backend.sh phase"

Or run the repository backend wrapper once:

ssh truenas-bracket "cd /mnt/HDD/bracket-dev && bash scripts/test_backend.sh all"

Do NOT run commands such as these in parallel:

- events + scorer
- scorer + phase
- events + phase
- multiple `test_backend.sh` processes at the same time

A parallel run may corrupt or interfere with the shared `bracket_pytest` test state and its result must be considered invalid.

If parallel backend suites were accidentally started, discard their results and rerun the affected suites sequentially.

Frontend TypeScript validation does not use `bracket_pytest` and may technically run independently, but prefer sequential validation unless there is a specific reason to parallelize.

## Standard validation order

For changes affecting match events, scoring, phases, or SCORER permissions, use this order:

1. Narrow affected backend suite first.
2. Event integration tests if events/scoring are affected.
3. SCORER integration tests if permissions or scorer workflows are affected.
4. Match-phase integration tests if lifecycle/phase behavior is affected.
5. Frontend TypeScript validation if frontend files changed.
6. `git -c core.filemode=false diff --check`

For the current hockey workflow, the safe comprehensive validation is:

ssh truenas-bracket "cd /mnt/HDD/bracket-dev && bash scripts/test_backend.sh events"

ssh truenas-bracket "cd /mnt/HDD/bracket-dev && bash scripts/test_backend.sh scorer"

ssh truenas-bracket "cd /mnt/HDD/bracket-dev && bash scripts/test_backend.sh phase"

ssh truenas-bracket "cd /mnt/HDD/bracket-dev && bash scripts/test_frontend.sh"

ssh truenas-bracket "cd /mnt/HDD/bracket-dev && git -c core.filemode=false diff --check"

Run the backend commands sequentially and wait for each one to finish before starting the next.

## Browser verification

Automated tests do not replace browser verification for interactive hockey workflows.

After changes to match events, score synchronization, or phase controls, manually verify the relevant flow in the test frontend when practical.

Typical COMPETITION smoke test:

- start match
- create GOAL with player number only
- verify segmented and aggregate score update
- create PENALTY and verify score stays unchanged
- end period and verify BREAK state
- edit/delete historical GOAL during BREAK
- start next period
- verify score mapping for the new period
- verify SHOOTOUT modifies penalty score but not aggregate goals
- finish match
- verify historical corrections still work

Do not report a browser flow as verified unless it was actually tested in the browser.
