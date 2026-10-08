# Hockey score-source API

This contract applies only to COMPETITION and GAME_SHOOTOUT tournaments. It does
not migrate legacy matches or modify STANDARD behavior. Existing events are never
removed or rewritten by a source change. No new database migration is needed.

## Operations

Both endpoints use the configured router API prefix and existing administrative
authentication: REGULAR (existing global administrative role), or ADMIN with
access to the tournament. SCORER cannot preview or confirm a change.

POST /tournaments/{tournament_id}/matches/{match_id}/score-source/preview

Request: {"target_source": "EVENTS"} (or MANUAL). Extra fields are rejected.
Response is wrapped in data and contains:

- match_id, current_source (MANUAL, EVENTS, or null), target_source;
- current_scores and resulting_scores: ordered lists of period, team1_score,
  team2_score;
- differences: period, team1_difference, team2_difference (result minus current);
- relevant_goal_count: total GOALs belonging to the resolved participants in the
  mode's supported periods;
- scores_changed; rankings_may_change (changed scores on a finished match);
- conflict_token: 64 lowercase hexadecimal characters.

A zero-event EVENTS projection explicitly contains zero section scores and their
negative differences from existing manual scores. The frontend must show these
consequences before invoking confirmation. Preview performs no database writes.

POST /tournaments/{tournament_id}/matches/{match_id}/score-source/confirm

Request: {"target_source": "EVENTS", "conflict_token": "<preview token>"}.
Response: {"data": {"match": <updated Match>, "active_source": "EVENTS",
"current_scores": <ordered section scores>}}.

Calling the confirm endpoint with a matching preview token constitutes explicit
confirmation of exactly the previewed state. Never automatically replay a request
whose network outcome is unknown; reload the match and preview again.

## Switch rules

| Current | Target | Scores |
| --- | --- | --- |
| MANUAL | EVENTS | Fully recount relevant GOALs; do not add previous scores. |
| null | EVENTS | Fully recount; do not continue legacy delta behavior. |
| EVENTS | MANUAL | Preserve every official score exactly. |
| null | MANUAL | Preserve every official score exactly. |
| Same target already active | Same | Strict no-op; never recount scores. |

Null is not an accepted target. Events always remain unchanged. MANUAL events
remain documentary and do not change official scores. The existing EVENTS and
legacy-null event mutation behavior is preserved outside explicit source switches.

GAME_SHOOTOUT counts GAME and SHOOTOUT. COMPETITION independently counts HALF1,
HALF2 and SHOOTOUT; its technical total is updated to half1 + half2. This technical
total creates no additional hockey points. Only GOAL events count, including GOALs
in SHOOTOUT; PENALTY disciplinary events do not count as goals. Unresolved teams
have zero event-derived goals.

PLANNED, RUNNING (including active/break phases), and FINISHED matches can switch.
Status and phase are preserved. Archived tournaments and STANDARD are rejected.

## Consistency and ranking

The HMAC-SHA256 token binds the target, match, resolved team identities, relevant
GOAL records and full tournament configuration. It is not a client-editable score
projection. Changes to scores, source, goals, phase, or configuration invalidate
it. A token cannot confirm another target or another match.

Each preview/confirmation obtains short-lived transaction locks: tournament,
then the tournament-scoped match. Existing event CRUD, score saves and phase
transitions use the same lock context. These operations are serialized per
tournament, including ranking updates for different matches. This deliberately
trades same-tournament write concurrency for consistent rankings and avoids lock
order inversion. No lock survives the preview response.

Confirmation rechecks administrative permission, membership, archive status and
current state under the transaction. Source, all score fields, existing stage
ranking recalculation and applicable elimination propagation commit together.
Any exception rolls back the entire operation. There is no automatic retry.

Ranking uses existing configured points and finished-match filtering. Combined
and YOUTH_CLUB standings read the updated stage points through existing backend
aggregation; Competition points and points formulas are not changed. A same-source
no-op does not recalculate rankings. Repeating an old successful confirmation
normally returns 409 because the source changed; a new same-source preview gives
a no-op confirmation without accidentally recounting.

## Errors

- 400: archived tournament, including archival after preview.
- 401: missing/invalid authentication.
- 403: no administrative permission, including SCORER.
- 404: unknown tournament/match or match belongs to another tournament.
- 409: preview token does not match current locked state.
- 422: invalid/missing target or token, additional request fields, or STANDARD.
- 500: unexpected database/ranking failure; changes are rolled back.

For ADMIN without tournament access, permission rejection may precede the 404
membership check. The existing general match PUT does not accept score_entry_source.

## Generation for Slice 5E-B3b

Generate the backend snapshot with the existing command, from backend:

    uv run --no-sync python cli.py generate-openapi

The frontend client is intentionally unchanged in this backend slice. In the
separately authorized frontend slice, from frontend run:

    pnpm run openapi-ts

Review generated changes, then run frontend typecheck/format/tests/build. Do not
manually edit generated client types.