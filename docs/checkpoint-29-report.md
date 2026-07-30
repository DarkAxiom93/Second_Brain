# Checkpoint report

Checkpoint: 29 — Advisory, read-only Memory contradiction detection.

Files changed: `app/memory_quality/contradiction.py` adds the deterministic
policy; the Checkpoint 28 similarity policy exposes one small internal bounded
candidate-pool helper; Memory routes and schemas add the public contract;
focused unit/integration tests prove behavior and safety; README, architecture,
checkpoint history, and handoff document the capability.

Behavior: V1 reports only `potential_contradiction`. Supported explicit
negation pairs are `is/is not`, `are/are not`, `was/was not`, `were/were not`,
`can/cannot`, and `can/can not`. Supported boolean-state pairs are
`enabled/disabled`, `active/inactive`, `true/false`, `on/off`, and
`available/unavailable`. Markers must start at the same token position and
removal must leave exactly equal case-folded anchors after ASCII-whitespace and
limited surrounding-punctuation normalization. Exact duplicates and pairs with
different non-null structured event times are excluded.

API: `GET /memories/{memory_id}/contradictions`, with limit default 10 and range
1..50, returns the target UUID and bounded candidates containing candidate UUID,
classification, evidence type, deterministic reason, nullable lexical and
semantic scores, and target/candidate states. Missing or inactive targets return
`404 memory not found`; invalid input returns 422; database failures return the
generic 503 response.

Database: No migration, new table, persisted result, or cache. Alembic head
remains `0008_memory_proposals`.

Transactions: SELECT-only. No commit, rollback, flush, Memory/embedding update,
or provider resolution occurs. Before/after tests compare relevant Memory
fields, embeddings, and related Project/Source/MemorySource/MemoryProposal
counts.

Tests: Pure tests cover every supported pair, both directions, exact anchors,
case/ASCII-whitespace/punctuation handling, subject/attribute/context/number
exclusion, compatible statements, unsupported antonyms, scalar conflicts, and
non-ASCII whitespace. PostgreSQL tests cover explicit detection, no match,
self/exact-duplicate exclusion, active targets/candidates, project and
assigned/unassigned isolation, unassigned detection, missing embeddings,
compatible semantic recovery beyond the bounded lexical pool, incompatible
metadata, evidence ordering/limit, 404/422/generic 503, no provider resolution,
and full relevant-state equality before/after requests.

PostgreSQL verification: `scripts/verify-databases.ps1` verified parsed and live
identity for `second_brain` and `second_brain_test` on `127.0.0.1:5433`. The
complete suite passed with 461 tests and zero skips. Pip check, Ruff lint, Ruff
formatting, and mypy passed. Alembic current and the sole Alembic head are
`0008_memory_proposals`. A direct project-virtual-environment
`python -m alembic check` completed with exit code 0 and reported `No new
upgrade operations detected.` No schema operation was proposed, and
`git diff --check` passed.

Verification-wrapper exception: `scripts/verify.ps1 -Mode Full` did not return
success on the final retry. After its identity, dependency, lint, formatting,
typing, and 461-test stages passed, Windows raised `OSError: [WinError 6] The
handle is invalid` while Python was starting the wrapper's later `alembic
current` subprocess. This was a subprocess-handle failure, not a logical
Alembic, schema, test, or application failure: Alembic current/head had already
been independently confirmed and the direct Alembic check passed. Checkpoint 29
was approved with this documented verification-wrapper exception. No migration,
provider call, development-data mutation, or Docker-volume deletion occurred.

Smoke test: A temporary host Uvicorn process on `127.0.0.1:8012` returned 200
from `/health` and the expected 404 from the contradiction route for a missing
UUID. It was stopped afterward. The smoke issued no write or cleanup request.

API regression: The unchanged similarities endpoint and all prior CRUD, search,
embedding, ingestion, proposal, health, readiness, migration, and workflow
tests remain in the full suite.

External calls: None. Only existing stored embeddings are read.

Warnings: Retrieval is bounded to 250 lexical and 250 compatible-semantic rows,
so results are advisory and potentially non-exhaustive. V1 is English-only and
does not infer general antonyms, environment/device/location/version/effective
time, scalar conflicts, approximate anchors, stemming, multilingual meaning,
or provider-assisted reasoning. Scalar, richer temporal, multilingual, and
provider-assisted detection are deferred.

Git status: Branch `main`; Checkpoint 29 changes remain unstaged and uncommitted.

Scope confirmation: Checkpoint 29 only. No winner/loser decision, confirmed
contradiction, Memory/status/confidence/importance/supersedes change, embedding
generation/update, migration, persistent result, external call, staging,
commit, push, PR, or Checkpoint 30 work.
