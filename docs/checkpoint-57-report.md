# Checkpoint 57 report

Checkpoint: Additive explained Memory search backend. Status: pending human
review.

Files changed:

- `app/schemas/memory.py`, `app/repositories/memories.py`, and
  `app/api/routes/memories.py`
- `tests/test_memory_search_explained.py`,
  `tests/integration/test_memory_search_explained.py`, and focused existing
  route/repository inventory tests
- `README.md`, `docs/API_CONVENTIONS.md`, `docs/ARCHITECTURE.md`,
  `docs/V1_1_ROADMAP.md`, `docs/ROADMAP.md`, `docs/CHECKPOINTS.md`,
  `docs/CHAT_HANDOFF.md`, and this report

Behavior:

Added only `POST /memories/search/explained`. Its required strict request fields
are `query`, `mode`, `filters`, and `pagination`. The query is trimmed and
bounded to 1–500 characters; mode is exactly lexical, semantic, or hybrid and
has no default. Filters and pagination reuse the canonical existing contracts.
The response is a bare array of global one-based rank, unchanged `MemoryRead`,
and a typed deterministic explanation.

Public explanations contain exactly mode, ordered matched channels, positive
nullable channel ranks, bounded nullable channel signals, nullable channel RRF
contributions, and nullable fused RRF score. Public floats round to six decimal
places. Lexical signal is the defensively clamped
`ts_rank_cd / (1 + ts_rank_cd)` value. Semantic signal is the defensively
clamped `1 - cosine_distance / 2` value. Hybrid uses `k=60`; each available
channel contributes `1 / (60 + channel_rank)`, and the unrounded contributions
are summed before public rounding. These values are documented only as ranking
aids, never confidence, probability, truth, certainty, model reasoning, or a
relevance guarantee.

API:

Lexical mode exposes only lexical rank/signal and never resolves an embedding
provider. Semantic mode exposes only semantic rank/signal. Hybrid exposes ranks,
signals, and contributions only for candidate channels that actually contained
the Memory; lexical precedes semantic in `matched_by`. RRF fields are non-null
only for hybrid results. Semantic/hybrid preserve exact safe errors:
`embedding provider unavailable` (503), `embedding provider failed` (502),
`invalid embedding response` (502), and `database unavailable` (503).

`GET /memories`, legacy `POST /memories/search`, and `POST /answers` retain their
request/response schemas, ordering, filtering, pagination, provider behavior,
errors, and score fields. No explanation field appears in legacy results.

Database:

No model, migration, stored-data, Docker, export/import, dependency, or lockfile
change exists. The parsed/live development and test identities were verified as
`second_brain` and `second_brain_test`. Alembic current and sole code head remain
`0009_memory_expiration`; `alembic check` reports no new upgrade operations.

Transactions:

The repository uses one bounded SQL statement per explained request for
structured filtering, matching, channel ranking, hybrid fusion, deterministic
final ordering, offset, and limit. The hybrid candidate formula remains exactly
`min(1000, max(100, (limit + offset) * 5))`. There is no Python reranking, N+1
query, per-Memory query, unbounded fetch, vector response, add, flush, commit,
row lock, entity modification, embedding creation, or persistence of query,
result, explanation, or history.

Tests:

- Focused schema/route/repository/PostgreSQL selection: 133 passed.
- Final `./scripts/verify.ps1 -Mode Full`: passed with pip consistency, Ruff
  lint/format, strict mypy, 674/674 Python tests with zero skips, Alembic
  current/heads/check, ESLint, TypeScript, 9 frontend files/78 tests, production
  build, and `git diff --check`.
- The first Full attempt passed 673 tests and exposed one stale route-inventory
  assertion in `tests/test_project_routes.py`; that exact inventory was updated
  for the authorized route, and the complete rerun passed.

PostgreSQL verification:

Focused integration coverage used only the parsed and live verified
`second_brain_test` database. It proved lexical/semantic/hybrid ordering equality
with the applicable legacy route, deterministic tie behavior, global offset
ranks, lexical-only/semantic-only/dual-channel hybrid results, exact RRF values,
structured/project isolation, unembedded-Memory behavior, and unchanged row
counts. No database was recreated.

Smoke test:

A FastAPI lexical explained search ran against existing development data with a
limit of five. It returned HTTP 200 and one bounded typed result. A forbidden
provider resolver proved no provider resolution occurred. Counts for all ten
application tables were captured before and after and remained identical.
Semantic/hybrid coverage used only the deterministic fake provider; no live or
paid provider call was made.

API regression:

Focused and full tests prove legacy lexical, semantic, hybrid, and Answer
contracts remain bare unchanged shapes; no explanation leaks into them; ordered
IDs equal the explained route for identical inputs; existing validation and safe
error details remain unchanged; and `/answers` retrieval and scores are
unchanged.

External calls:

The unauthenticated public GitHub Actions API was queried with an explicit
User-Agent. The first pushed `Second Brain CI` run for exact Checkpoint 56 commit
`2c4ed449c2471d4c4729164714e551979028d0f8` is run ID `30806886319` at
`https://github.com/DarkAxiom93/Second_Brain/actions/runs/30806886319`. It is the
`push` run on `main`, used `.github/workflows/ci.yml`, completed successfully on
attempt one, and uploaded zero artifacts. npm audit reported zero
vulnerabilities. No authentication, `gh`, rerun, GitHub mutation, application
provider call, or paid call occurred.

Warnings:

Pytest retained the existing Starlette `httpx` deprecation warning and an
intermittent existing Pydantic field-metadata warning in proposal-promotion
coverage. Vitest retained the existing jsdom navigation notice. Git reported
the existing working-copy LF-to-CRLF notices. None failed verification or
exposed private data.

Git status:

Preflight was clean. HEAD, `main`, and `origin/main` were exactly
`2c4ed449c2471d4c4729164714e551979028d0f8` with divergence `0 0`, and the
latest message was `ci: add non-authoritative verification workflow`.
Checkpoint 55 remains committed at `cefdc4e`; local `v1.0.0` still peels to
`a1bf40c0a27e9ee508e9bf1ab151b4665fbdba32`. Checkpoint 57 changes remain
unstaged and uncommitted. Nothing was staged, committed, pushed, tagged,
published, or opened as a pull request.

Scope confirmation:

Only the approved additive backend route, its strict public schemas, bounded SQL
projection, tests, and genuinely necessary documentation changed. Raw vectors,
distances, lexical scores, SQL, prompts, provider responses, secrets, and
exception text remain private. Frontend application code, existing schemas and
routes, ranking policy, Answer behavior, models, migrations, dependencies,
lockfiles, CI, Docker, export/import, authentication, CORS, provider
implementations, tags, and releases are unchanged. Checkpoint 56 is marked
complete at its exact commit; Checkpoint 57 remains pending review; Checkpoint
58 has not started. No report-template heading was omitted.
