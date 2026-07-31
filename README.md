# Second Brain

## Developer workflow

Stable project guidance is split into concise references: [architecture](docs/ARCHITECTURE.md),
[roadmap](docs/ROADMAP.md), [verification](docs/VERIFICATION.md),
[safety](docs/SAFETY.md), [API conventions](docs/API_CONVENTIONS.md),
[checkpoint history](docs/CHECKPOINTS.md), [ADRs](docs/decisions/README.md), and
the [new-chat handoff](docs/CHAT_HANDOFF.md). Reusable Windows commands are
documented in [scripts/README.md](scripts/README.md).

Second Brain is a Python 3.12 project with Foundation configuration, local
PostgreSQL infrastructure, and a minimal FastAPI liveness API.

## Prerequisites

- CPython 3.12
- Git

## Local setup on Windows

Create a project-local virtual environment with a Python 3.12 interpreter, then
install the project and development dependencies into it:

```powershell
& 'C:\path\to\Python312\python.exe' -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install --upgrade pip
& '.\.venv\Scripts\python.exe' -m pip install -e '.[dev]'
```

Copy `.env.example` to `.env` when local configuration overrides are needed.
The supported environment variables are:

- `APP_NAME`, `APP_ENV`, `APP_HOST`, `APP_PORT`, and `APP_LOG_LEVEL`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and
  `POSTGRES_PORT`
- `DATABASE_URL`

No prefix is required. The checked-in values are development placeholders, not
production credentials. On Windows, commands can invoke the virtual
environment's Python executable directly without activating it.

## Quality checks

```powershell
& '.\.venv\Scripts\python.exe' -m pip check
& '.\.venv\Scripts\python.exe' -m ruff check .
& '.\.venv\Scripts\python.exe' -m ruff format --check .
& '.\.venv\Scripts\python.exe' -m mypy app
& '.\.venv\Scripts\python.exe' -m pytest
```

## Checkpoint 2: local PostgreSQL

Docker Desktop must be installed and running with Linux containers, and Docker
Compose v2 is required. `.env.example` is only a local-development template; no
real `.env` file is committed. Validate the rendered Compose configuration with:

```powershell
docker compose --env-file .env.example config
docker compose --env-file .env.example config --quiet
```

Start only PostgreSQL, inspect its health, view its logs, and stop it safely:

```powershell
docker compose --env-file .env.example up -d --wait db
docker compose --env-file .env.example ps
docker compose --env-file .env.example logs db
docker compose --env-file .env.example stop db
```

Connect with `psql` inside the database container, using its configured
environment values:

```powershell
docker compose --env-file .env.example exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

PostgreSQL is published only on `127.0.0.1`, and its data persists in the named
`postgres_data` Docker volume. The selected image includes pgvector, but the
`vector` extension is intentionally not enabled yet; a future approved migration
will enable it.

To remove stopped containers without deleting database data, use:

```powershell
docker compose --env-file .env.example down
```

Do not use `down -v`; project safety rules prohibit deleting the database
volume. Prefer `scripts/dev-down.ps1`, which stops only `db` and preserves data.

## Checkpoint 3: FastAPI liveness API

The FastAPI skeleton is implemented, with `GET /health` as its only application
endpoint. It is a process liveness check and does not connect to PostgreSQL. The
database remains a separate Docker service; the API does not run in Docker.

Start the API locally on Windows:

```powershell
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

While the server is running, use these URLs:

- Health: <http://127.0.0.1:8000/health>
- Interactive OpenAPI documentation: <http://127.0.0.1:8000/docs>
- OpenAPI schema: <http://127.0.0.1:8000/openapi.json>

Call the health endpoint from PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Stop the local development server with `Ctrl+C`. Run the test and quality suite
with the commands in [Quality checks](#quality-checks).

## Checkpoint 4: database integration and readiness

The application now has a synchronous SQLAlchemy engine and request-scoped
sessions using Psycopg 3. `GET /health` remains a database-independent liveness
check, while `GET /ready` executes `SELECT 1` and reports whether PostgreSQL is
reachable. The API still runs locally rather than in Docker.

Migrations are explicit developer or deployment actions; they do not run during
application import or startup. The initial migration enables pgvector only. No
projects or memories tables exist yet.

When host port 5432 is occupied, start the database on temporary port 5433 and
set the host-accessible application URL for the current PowerShell session:

```powershell
$env:POSTGRES_PORT = "5433"
docker compose --env-file .env.example up -d --wait db
$env:DATABASE_URL = "postgresql+psycopg://second_brain:change-me@127.0.0.1:5433/second_brain"
```

Apply and inspect migrations explicitly:

```powershell
& '.\.venv\Scripts\python.exe' -m alembic upgrade head
& '.\.venv\Scripts\python.exe' -m alembic current
```

Run the normal unit suite without a test database:

```powershell
Remove-Item Env:TEST_DATABASE_URL -ErrorAction SilentlyContinue
& '.\.venv\Scripts\python.exe' -m pytest
```

Integration tests require the separate database named exactly
`second_brain_test`. Never point `TEST_DATABASE_URL` at `second_brain`,
`postgres`, or another database. `.env.test.example` contains placeholders only;
do not commit a real `.env.test` file.

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://second_brain:change-me@127.0.0.1:5433/second_brain_test"
& '.\.venv\Scripts\python.exe' -m pytest tests/integration
```

## Checkpoint 5: Project and Memory persistence

SQLAlchemy persistence models now define `projects` and `memories`, created by
migration file `0002_create_projects_and_memories.py` with Alembic revision
`0002_projects_memories`. Project names are not unique. A Memory may exist
without a Project, and deleting a Project preserves its memories by setting
`Memory.project_id` to `NULL`.

Both models use application-generated UUIDs, timezone-aware database timestamps,
and SQLAlchemy ORM-managed `updated_at` updates. pgvector remains installed, but
neither model has an embedding or vector column.

Apply and inspect the current migration explicitly:

```powershell
& '.\.venv\Scripts\python.exe' -m alembic upgrade head
& '.\.venv\Scripts\python.exe' -m alembic current
```

Run metadata/unit tests normally, or set the guarded test URL to run the real
PostgreSQL integration suite:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests/test_models.py
$env:TEST_DATABASE_URL = "postgresql+psycopg://second_brain:change-me@127.0.0.1:5433/second_brain_test"
& '.\.venv\Scripts\python.exe' -m pytest tests/integration
```

Integration tests accept only the exact database `second_brain_test`. The API
still runs locally, Docker Compose remains database-only, and there are no
Project or Memory API endpoints yet.

## Checkpoint 6: Project API

The locally run API now supports `POST /projects` and `GET /projects`. Project
names are trimmed at their edges, must contain at least one character, and may
not exceed 200 characters. Internal whitespace and letter casing are preserved,
the description is optional, and duplicate names are allowed.

Create a Project from PowerShell:

```powershell
$body = @{
    name = "Pure Axiom"
    description = "Interactive mathematics platform"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/projects -ContentType application/json -Body $body
```

List Projects as a bare JSON array, optionally using the validated pagination
parameters (`limit` defaults to 50 and accepts 1 through 100; `offset` defaults
to 0 and must be nonnegative):

```powershell
Invoke-RestMethod http://127.0.0.1:8000/projects
Invoke-RestMethod 'http://127.0.0.1:8000/projects?limit=25&offset=50'
```

Repository functions use an existing SQLAlchemy session, apply pagination in
SQL, and never commit. The API owns the single write transaction for Project
creation. Database errors produce a generic HTTP 503 response without exposing
connection details.

Checkpoint 6 required no schema change or migration. Docker Compose remains
database-only and the API continues to run locally. There is no Memory API,
Project update endpoint, or Project delete endpoint yet.

## Checkpoint 7: Memory creation API

The API supports `POST /memories` for creating an unassigned Memory or one
associated with an existing Project. Content is trimmed and must not be blank.
An optional source is also trimmed, must not be blank when provided, and is
limited to 100 characters.

```powershell
$body = @{ content = "A useful fact"; source = "notes" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/memories -ContentType application/json -Body $body
```

To associate a Memory, include a Project UUID as `project_id`. Unknown projects
return HTTP 404. Database failures return a generic HTTP 503 response. The
Memory repository does not commit; the route owns its single successful commit.
There is no Memory listing, update, or deletion endpoint.

## Checkpoint 8: Memory retrieval API

The API now supports `GET /memories` and `GET /memories/{memory_id}`. Memory
listings are returned as a bare JSON array ordered by newest creation time and
then UUID. Pagination uses `limit` (default 50, range 1 through 100) and
nonnegative `offset`; an optional `project_id` UUID filters the list to assigned
memories for that Project. Unknown Project filters return an empty array.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/memories
Invoke-RestMethod 'http://127.0.0.1:8000/memories?project_id=<project-uuid>&limit=25&offset=0'
Invoke-RestMethod http://127.0.0.1:8000/memories/<memory-uuid>
```

An unknown Memory UUID returns HTTP 404. Database failures return a generic HTTP
503 response. Checkpoint 8 adds no migration, search, update, or delete behavior.

## Current scope

Liveness, database readiness, Project creation/listing, and Memory creation and
retrieval are implemented. Checkpoint 9 adds normalized `sources` persistence
and association-object `memory_sources` links while retaining the legacy
`memories.source` string. Sources have no API endpoints yet. Apply the schema
with `python -m alembic upgrade head`; the current revision is `0003_sources`.
Project updates and deletion, Memory update/deletion, ingestion, search,
authentication, agent workflows, and frontend code are not implemented.

## Checkpoint 10: Source creation and linking API

Create normalized Sources with `POST /sources`, then link an existing Source to
an existing Memory with `POST /memories/{memory_id}/sources`. Both endpoints
return HTTP 201. Unknown parents return HTTP 404, and an existing link returns
HTTP 409. Source names and checksums are intentionally not unique.

```powershell
$source = @{ source_type = "note"; name = "Research notes" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/sources -ContentType application/json -Body $source

$link = @{ source_id = "<source-uuid>"; source_location = "page 4" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/memories/<memory-uuid>/sources -ContentType application/json -Body $link
```

There are no Source listing, linked-Source retrieval, update, or delete
endpoints. Checkpoint 10 adds no migration; the Alembic head remains
`0003_sources`.

## Checkpoint 11: linked Source retrieval

Retrieve Sources linked to a Memory or Memories linked to a Source. Both routes
return bare JSON arrays ordered by newest link first, with `limit` (default 50,
range 1 through 100) and nonnegative `offset` pagination:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/memories/<memory-uuid>/sources?limit=25&offset=0'
Invoke-RestMethod 'http://127.0.0.1:8000/sources/<source-uuid>/memories?limit=25&offset=0'
```

Unknown parent UUIDs return HTTP 404. The legacy `memories.source` value is
returned as `legacy_source` by the second route. There is still no general
Source listing or individual Source retrieval endpoint. Checkpoint 11 adds no
migration; the Alembic head remains `0003_sources`.

## Checkpoint 12: structured Memory metadata persistence

Memory persistence now supports optional `title` and `summary`. `memory_type`
defaults to `semantic` and accepts `working`, `episodic`, `semantic`, `decision`,
`procedural`, `preference`, or `temporary`. `status` defaults to `active` and
accepts `active`, `superseded`, `invalid`, or `archived`. `importance` and
`confidence` range from 0.0 through 1.0, defaulting to 0.5 and 1.0.

`event_time` records when the remembered event occurred and is independent of
the persistence `created_at` timestamp. `expires_at` records an optional expiry
time but does not trigger automatic deletion. `supersedes_id` may point to an
older Memory; setting it does not automatically change either Memory's status.

Existing Memory API request and response shapes remain unchanged; the new
fields are persistence-only. API support will be added in a later checkpoint.
The Alembic head is `0004_memory_metadata`. There is no automatic
classification, expiration, or superseding behavior.

## Checkpoint 13: structured Memory metadata API

The existing Memory creation and retrieval endpoints now accept and return the
structured metadata introduced in Checkpoint 12. A minimal request containing
only `content` remains valid and returns `memory_type` `semantic`, `importance`
`0.5`, `confidence` `1.0`, and `status` `active`.

Allowed `memory_type` values are `working`, `episodic`, `semantic`, `decision`,
`procedural`, `preference`, and `temporary`. Allowed `status` values are
`active`, `superseded`, `invalid`, and `archived`. Both `importance` and
`confidence` accept values from 0.0 through 1.0, inclusive. Optional
`event_time` and `expires_at` values must include a timezone offset. Expiration
is stored only; it has no automatic behavior.

When supplied, `supersedes_id` must identify an existing Memory. Creating a
superseding Memory does not automatically update the older Memory's status.
There are still no Memory update or delete endpoints.

Create a minimal Memory:

```powershell
$body = @{ content = "A useful fact" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/memories -ContentType application/json -Body $body
```

Create a Memory with all structured metadata:

```powershell
$body = @{
    content = "The team selected PostgreSQL"
    source = "architecture notes"
    title = "Database decision"
    summary = "PostgreSQL was selected for durable storage."
    memory_type = "decision"
    importance = 0.9
    confidence = 1.0
    status = "active"
    event_time = "2026-07-29T10:00:00+03:00"
    expires_at = "2027-07-29T10:00:00+03:00"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/memories -ContentType application/json -Body $body
```

Create a Memory that supersedes an existing Memory:

```powershell
$body = @{
    content = "The revised decision"
    memory_type = "decision"
    supersedes_id = "<older-memory-uuid>"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/memories -ContentType application/json -Body $body
```

Checkpoint 13 adds no migration. The Alembic head remains
`0004_memory_metadata`.

## Checkpoint 14: structured Memory filtering

`GET /memories` accepts optional `memory_type` and `status` filters, inclusive
score ranges (`importance_min`, `importance_max`, `confidence_min`, and
`confidence_max`), and inclusive timestamp ranges (`event_time_from`,
`event_time_to`, `created_at_from`, and `created_at_to`). Allowed Memory types
are `working`, `episodic`, `semantic`, `decision`, `procedural`, `preference`,
and `temporary`; allowed statuses are `active`, `superseded`, `invalid`, and
`archived`. Score bounds must be from 0.0 through 1.0. Timestamp bounds must
include a timezone offset.

All supplied filters, including the existing optional `project_id`, combine
with AND and are applied in SQL. No status is hidden by default, expired
Memories are not automatically excluded, and an event-time range does not
include rows whose `event_time` is null. The endpoint remains a bare JSON array
ordered by `created_at` descending and then `id` ascending. `limit` still
defaults to 50 (range 1 through 100), and `offset` still defaults to 0.

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/memories?memory_type=semantic&status=active'
Invoke-RestMethod 'http://127.0.0.1:8000/memories?importance_min=0.7&confidence_min=0.8&confidence_max=1.0'
Invoke-RestMethod 'http://127.0.0.1:8000/memories?event_time_from=2026-07-01T00%3A00%3A00%2B03%3A00&event_time_to=2026-08-01T00%3A00%3A00%2B03%3A00'
Invoke-RestMethod 'http://127.0.0.1:8000/memories?project_id=<project-uuid>&memory_type=decision&status=active&importance_min=0.8'
```

Checkpoint 14 adds no migration. The Alembic head remains
`0004_memory_metadata`.

## Checkpoint 15: PostgreSQL full-text Memory search

`GET /memories` now accepts an optional `query` parameter for PostgreSQL lexical
full-text search. The generated, stored `search_vector` searches `title` (weight
A), `summary` (B), `content` (C), and the legacy `source` string (D), using the
PostgreSQL `simple` configuration for multilingual text, code, product names,
and identifiers. This is lexical search, not semantic or embedding search.

PostgreSQL web-search syntax supports normal words, quoted phrases, `OR`, and
excluded terms. Queries are trimmed, must contain non-whitespace text, and may
not exceed 500 characters:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/memories?query=postgres'
Invoke-RestMethod 'http://127.0.0.1:8000/memories?query=%22database%20decision%22'
Invoke-RestMethod 'http://127.0.0.1:8000/memories?query=postgres%20OR%20sqlite'
Invoke-RestMethod 'http://127.0.0.1:8000/memories?query=database%20-sqlite'
```

Search combines with every structured filter using AND. Search results are
ordered by relevance descending, then `created_at` descending and `id`
ascending; limit and offset are applied afterward in SQL. Without `query`, the
existing chronological ordering and all existing behavior remain unchanged.
The generated column has a GIN index and updates automatically when searchable
fields change. The Alembic head is `0005_memory_search`.

## Checkpoint 16: Memory embedding persistence

The separate `memory_embeddings` table stores at most one current semantic
embedding per Memory. It uses `VECTOR(1536)` and a cosine-distance HNSW index,
and records the provider, exact model identifier, input SHA-256 hash,
embedding time, and creation/update timestamps. Deleting a Memory cascades only
to its embedding record; deleting that record leaves the Memory intact.

Existing Memories are not backfilled and creating a Memory does not generate an
embedding. No external embedding API is called, no API key is required, and no
semantic-search API or public embedding field exists yet. Embedding generation
is reserved for the next checkpoint. The Alembic head is
`0006_memory_embeddings`; PostgreSQL lexical search remains unchanged.

## Checkpoint 17: explicit Memory embedding generation

Generate or refresh one Memory embedding explicitly with:

```text
POST /memories/{memory_id}/embedding
```

The endpoint returns HTTP 200 with embedding metadata and a
`generation_status` of `created`, `updated`, or `unchanged`; the vector is never
included in public responses. The canonical provider input contains only the
labeled `title`, `summary`, `content`, and legacy `source` fields, with line
endings normalized to LF. A lowercase SHA-256 hash of the exact UTF-8 input,
together with provider, model, and dimensions, makes unchanged requests
idempotent without another provider call or vector write.

The default provider is OpenAI, using `text-embedding-3-small` at 1536
dimensions and a 30-second timeout. Supply the API key locally without
displaying it:

```powershell
$env:OPENAI_API_KEY = Read-Host "OpenAI API key"
```

Never commit secrets or a local `.env` file. Missing provider configuration,
provider failures, invalid responses, and database failures produce generic API
errors without raw exceptions, request identifiers, connection details, input
text, or vectors.

Memory creation still does not generate embeddings automatically. Existing lexical search, structured filters,
and Source relationships are unchanged. Automated tests inject a deterministic
fake provider, never call OpenAI, and incur no API cost. No migration is added;
the Alembic head remains `0006_memory_embeddings`.

## Checkpoint 36: explicit batch Memory embedding generation

`POST /memory-embeddings/batch` explicitly generates embeddings for a bounded
selection of active Memories that do not already have one. The extra-forbidden
body accepts `scope` as `project`, `unassigned`, or `all`; `project` requires
`project_id`, while the other scopes forbid it. `limit` defaults to 20 and is
restricted to 1 through 50. An unknown project UUID returns an empty HTTP 200
result without a separate Project existence query.

SQL selects by `created_at` then UUID and applies the limit. Empty selection
resolves no provider and performs no write or commit. Non-empty selection reuses
the canonical Memory text and SHA-256 hash and makes one ordered provider batch
call. After validation, UUID-ordered row locks recheck each candidate. Atomic
inserts return `created`; a concurrent winner is `unchanged`; a newly inactive
row is `skipped` with `memory_not_active`. Responses preserve candidate order,
include counts and metadata, and never expose vectors.

The action never replaces or re-embeds an existing embedding, changes a Memory,
or runs automatically or in the background. Tests use fake providers. No
migration is added; Alembic remains
`0009_memory_expiration`.

## Checkpoint 37: controlled batch Memory re-embedding

`POST /memory-embeddings/reembed` explicitly replaces existing embeddings for
active Memories. Its extra-forbidden body uses the same `scope`, optional
`project_id`, and 1-through-50 `limit` rules as the missing-embedding batch and
adds `selection`, either `stale` or `all`. Stale means the stored canonical
input hash, provider, model, or dimensions differs from current configuration;
timestamps alone never make an embedding stale. All forces replacement of every
eligible in-scope existing embedding.

SQL selects only active Memories with embeddings, ordered by `created_at` then
UUID with the limit applied. Empty selection resolves no provider. A non-empty
selection makes exactly one canonical-order provider batch call and validates
the complete result before writes. Deterministic row locks then recheck status,
embedding existence, and current identity. Replacements are atomic and update
the existing row, preserving its ID, `memory_id`, and `created_at`. Concurrent
stale requests yield one update and later unchanged results; concurrent forced
requests serialize to one valid final embedding. Responses include previous and
current metadata and counts but never vectors.

This route never creates a missing embedding, embeds a non-active Memory,
changes Memory data, or runs automatically or on a schedule. Tests and smoke
verification make no live provider call. No migration is added; Alembic remains
`0009_memory_expiration`.

## Checkpoint 38: read-only Memory maintenance audit

Run the deterministic maintainer audit against development:

```powershell
.\scripts\audit-memory-maintenance.ps1
```

Use `-TestDatabase` for the separately verified test database,
`-DetailLimit 25` to bound each category's ID details, and
`-OutputPath .\audit.json` to additionally write typed JSON. JSON is never
written unless an output path is supplied.

The report includes total, project-assigned, and unassigned Memories; complete
counts for every status; active Memories missing embeddings; active Memories
with stale embeddings; active expiration timestamps that are due or future;
expired Memories missing `expires_at`; and embeddings attached to non-active
Memories. One timezone-aware UTC timestamp is captured for the complete audit.
Each actionable category returns its full count and up to the requested number
of IDs, ordered by `created_at` ascending and UUID ascending.

Embedding staleness is exactly the controlled re-embedding rule: canonical
input SHA-256 hash, configured provider, model, or dimensions differs. The audit
does not resolve or call a provider. It validates parsed and live database
identity, uses a database read-only transaction, and never flushes, commits,
repairs, expires, embeds, re-embeds, archives, invalidates, supersedes, deletes,
or rewrites application data. It is a point-in-time diagnostic, not exhaustive
history or a maintenance executor; future execution remains separate and
explicit. No API route, schema change, migration, job, or telemetry is added.

## Checkpoint 18: explicit semantic Memory search

Search only Memories that already have an explicitly generated embedding:

```powershell
$body = @{
  query = "database migration decisions"
  filters = @{ status = "active"; importance_min = 0.6 }
  pagination = @{ limit = 20; offset = 0 }
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/memories/search `
  -ContentType "application/json" -Body $body
```

`POST /memories/search` embeds the trimmed query once and ranks matching
`memory_embeddings` rows by pgvector cosine distance. Supplied structured
Memory filters are applied with `AND`; ordering is semantic distance ascending,
then `created_at` descending and `id` ascending. Pagination is applied in SQL.
Generate each participating Memory's embedding first with
`POST /memories/{memory_id}/embedding`; Memories without an embedding row are
not returned.

The query vector is never persisted. Responses are bare arrays of Memory data
and contain no vectors, provider response data, distances, or scores. Missing
provider configuration returns HTTP 503 with `embedding provider unavailable`.
This checkpoint is semantic-only: the existing `GET /memories?query=...`
lexical behavior is unchanged, and no hybrid ranking is performed. Automated
tests use fake providers and make no paid API calls. No schema migration is
added; the Alembic head remains `0006_memory_embeddings`.

## Checkpoint 19: hybrid Memory search

`POST /memories/search` supports `semantic` and `hybrid` modes. Semantic is the
default, so omitting `mode` preserves the cosine-distance behavior described
above; an explicit semantic request is equivalent:

```powershell
$body = @{ query = "database migration decisions" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/memories/search -ContentType "application/json" -Body $body

$body = @{ query = "database migration decisions"; mode = "semantic" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/memories/search -ContentType "application/json" -Body $body
```

Hybrid mode combines PostgreSQL full-text ranking over `memories.search_vector`
with pgvector cosine-distance ranking. It uses equal-weight Reciprocal Rank
Fusion with a constant of 60:

```powershell
$body = @{ query = "database migration decisions"; mode = "hybrid" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/memories/search -ContentType "application/json" -Body $body

$body = @{
  query = "database migration decisions"; mode = "hybrid"
  filters = @{ project_id = "00000000-0000-0000-0000-000000000001"; memory_type = "decision"; status = "active"; importance_min = 0.6 }
  pagination = @{ limit = 20; offset = 10 }
} | ConvertTo-Json -Depth 3
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/memories/search -ContentType "application/json" -Body $body
```

All structured filters apply independently to both candidate branches. The
internal candidate pool for each branch is
`min(1000, max(100, (limit + offset) * 5))`; it is not configurable. Fusion is
performed in one SQL statement and final pagination occurs after fusion.
Lexical-only Memories may participate without embedding rows, while semantic
candidates require embedding rows. The response remains a bare Memory array:
the RRF score, branch ranks, distances, and vectors are not exposed.

Both modes require the embedding provider, embed the trimmed query exactly
once, and never persist the query embedding. There is no automatic Memory
embedding and no fallback to lexical-only results after provider errors.
`GET /memories?query=...` remains lexical-only. Automated tests use fixed fake
vectors and make no OpenAI calls. No schema migration is added; the Alembic
head remains `0006_memory_embeddings`.

## Checkpoint 20: Source document and text-chunk persistence

A Source may now have one optional `SourceDocument` record, and a document may
contain ordered `SourceChunk` rows. Document metadata includes media type,
optional original filename and byte size, ingestion status, and optional
`extracted_text` storage for future parser output. Chunks preserve exact text,
inclusive/exclusive character offsets, lowercase SHA-256 content hashes, and an
optional human-readable locator.

This checkpoint provides persistence only. There is no upload endpoint, file
parsing, automatic extraction or chunking, chunk embedding, or automatic Memory
creation. Existing Source and Memory APIs and response shapes remain unchanged.
The next checkpoint will add explicit plain-text ingestion. The Alembic head is
`0007_source_documents`.
# Plain-text Source ingestion

An existing Source can receive normalized plain text explicitly through JSON:

```text
PUT /sources/{source_id}/document/text
```

The request accepts `text`, optional `original_filename`, `chunk_size` (default
2000, range 1000–10000), and `chunk_overlap` (default 200, range 0–500 and
smaller than the chunk size). CRLF and CR line endings become LF; every other
character is preserved. Normalized text is limited to 5,000,000 UTF-8 bytes.

Chunks are deterministic fixed-size windows with overlap. Offsets count
Unicode/Python characters, are start-inclusive and end-exclusive, and each
chunk hash is the lowercase SHA-256 of its exact UTF-8 content. Responses report
`created`, `updated`, or `unchanged`. An identical request preserves document
timestamps and document/chunk IDs; changed chunks are replaced transactionally.

```powershell
$source = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/sources `
  -ContentType 'application/json' -Body '{"source_type":"note","name":"Example"}'
$uri = "http://127.0.0.1:8000/sources/$($source.id)/document/text"
Invoke-RestMethod -Method Put -Uri $uri -ContentType 'application/json' `
  -Body '{"text":"First text","original_filename":"notes.txt"}'
Invoke-RestMethod -Method Put -Uri $uri -ContentType 'application/json' `
  -Body '{"text":"First text","original_filename":"notes.txt"}'
Invoke-RestMethod -Method Put -Uri $uri -ContentType 'application/json' `
  -Body '{"text":"Updated text","chunk_size":1000,"chunk_overlap":100}'
```

## TXT and PDF Source upload

Checkpoint 22 adds one explicit multipart endpoint for an existing Source:

```text
PUT /sources/{source_id}/document/file
```

The required `file` field accepts UTF-8 `.txt` files and `.pdf` files with an
extractable text layer. Raw uploads are limited to 20,000,000 bytes; extracted
normalized text is limited to 5,000,000 UTF-8 bytes. PDFs are limited to 1,000
pages. OCR is not supported, and encrypted, malformed, or image-only PDFs are
rejected.

The trimmed filename must be 1–255 characters and a filename only: paths,
drive-qualified names, NUL, `.`, and `..` are rejected. The filename extension,
declared MIME type, and actual content/signature must agree. An
`application/octet-stream` declaration is accepted only when the `.txt` UTF-8
content or `.pdf` signature conclusively identifies a supported format.

TXT decoding accepts UTF-8 only, removes one leading UTF-8 BOM, and normalizes
CRLF/CR to LF while preserving all other characters. PDF pages are extracted
once in page order and joined with exactly two LF characters, including around
blank intermediate pages. Character chunks use the same `chunk_size` (default
2000, range 1000–10000) and `chunk_overlap` (default 200, range 0–500 and
smaller than the chunk size) rules as JSON ingestion. PDF chunk locators are
`page N` or `pages N-M` when chunk content overlaps page text; separator-only
text does not invent a locator. TXT locators are null.

In PowerShell 7 and later:

```powershell
$uri = "http://127.0.0.1:8000/sources/$sourceId/document/file"
Invoke-RestMethod -Method Put -Uri $uri -Form @{
  file = Get-Item '.\notes.txt'
  chunk_size = 2000
  chunk_overlap = 200
}
```

Equivalent Windows curl usage:

```powershell
curl.exe -X PUT -F "file=@notes.txt;type=text/plain" `
  -F "chunk_size=2000" -F "chunk_overlap=200" `
  "http://127.0.0.1:8000/sources/$sourceId/document/file"
```

Responses reuse the existing document schema and report `created`, `updated`,
or `unchanged`. Repeating an identical upload and chunk settings does not
rewrite document or chunk rows. Raw bytes are never persisted. No Memory is
created automatically, and no chunk embeddings or chunk search are added. The
JSON `PUT /sources/{source_id}/document/text` endpoint remains available and
unchanged. Alembic head remains `0007_source_documents`.

## Checkpoint 23: reviewable Memory proposal persistence

`memory_extraction_runs` records the document, future provider and exact model,
prompt version, deterministic input hash, status, and timestamps for an auditable
attempt. `memory_proposals` stores proposed Memory fields in pending review status
with immutable evidence text, offsets, chunk hash, and locator snapshots, so
SourceChunk replacement does not destroy proposal evidence.

Proposals do not automatically become Memories. No AI extraction call, proposal
generation, review, approval, rejection, promotion endpoint, or public proposal
data exists yet. The next checkpoint will add explicit AI proposal generation.
The Alembic head is `0008_memory_proposals`.
# Explicit Memory-proposal generation

`POST /sources/{source_id}/memory-proposals` synchronously analyzes a bounded,
ordered batch of already-ingested source chunks (`chunk_start` defaults to 0 and
`chunk_limit` to 10, maximum 20). It makes one strict OpenAI Responses API call
for each new or retried run. Document content is untrusted evidence: embedded
instructions are ignored and every evidence range must match an exact chunk
substring before a proposal is stored.

Inputs and proposals use deterministic SHA-256 hashes. Completed identical runs
are returned as `unchanged`; failed runs retain stable, non-secret error codes
and may be `retried`; new runs report `created`. Proposals always begin as
`pending`. They are not Memories, are never automatically approved or promoted,
and raw prompts/provider responses are not stored.

```powershell
$body = @{ chunk_start = 0; chunk_limit = 10; max_proposals_per_chunk = 3 } |
  ConvertTo-Json
Invoke-RestMethod -Method Post -ContentType 'application/json' -Body $body `
  -Uri 'http://127.0.0.1:8000/sources/<source-uuid>/memory-proposals'
```

Keep `OPENAI_API_KEY` local and uncommitted. Defaults are model
`gpt-5.6-terra` and prompt version `memory_proposals_v1`. Automated tests inject
a fake provider and make no paid API calls. Alembic head remains
`0008_memory_proposals`.

## Checkpoint 25: human review of Memory proposals

`GET /memory-proposals` returns the public review queue as a bare array. It
defaults to `review_status=pending`; `review_status=all` removes that predicate.
Filters for `run_id`, `source_id`, `document_id`, proposal `project_id`,
`memory_type`, importance/confidence ranges, `limit`, and `offset` combine in
SQL. Results are always oldest first (`created_at`, then `id`).

`GET /memory-proposals/{proposal_id}` includes the immutable evidence text,
offsets, chunk/proposal hashes, run status, and `source_chunk_available` flag.
The stored evidence remains inspectable if re-ingestion deletes the original
SourceChunk; complete chunk/document text, prompts, and provider output are not
returned.

`POST /memory-proposals/{proposal_id}/approve` accepts an optional
`review_note`. `POST /memory-proposals/{proposal_id}/reject` requires a nonblank
note. Only proposals from completed extraction runs can be reviewed. Repeating
the same terminal decision is idempotent and reports `transition_status` as
`unchanged`; requesting the opposite decision returns HTTP 409. Reviewed
proposals cannot be reopened.

Approval is only a human review decision: it creates no Memory or
MemoryEmbedding, and `memory_id` remains null until a separate promotion.
Alembic head remains `0008_memory_proposals`.

```powershell
# List pending proposals (the default queue)
Invoke-RestMethod 'http://127.0.0.1:8000/memory-proposals'

# Filter by Source or Project
Invoke-RestMethod "http://127.0.0.1:8000/memory-proposals?source_id=$sourceId"
Invoke-RestMethod "http://127.0.0.1:8000/memory-proposals?project_id=$projectId&review_status=all"

# Inspect immutable evidence
Invoke-RestMethod "http://127.0.0.1:8000/memory-proposals/$proposalId"

# Approve, or reject with the required note
Invoke-RestMethod -Method Post -ContentType 'application/json' `
  -Body '{"review_note":"Evidence verified"}' `
  "http://127.0.0.1:8000/memory-proposals/$proposalId/approve"
Invoke-RestMethod -Method Post -ContentType 'application/json' `
  -Body '{"review_note":"Evidence does not support the claim"}' `
  "http://127.0.0.1:8000/memory-proposals/$proposalId/reject"
```

## Checkpoint 26: explicit Memory-proposal promotion

`POST /memory-proposals/{proposal_id}/promote` has no request body. It promotes
only an approved proposal whose extraction run is completed; pending or
rejected proposals are not eligible. Approval and promotion remain separate,
deliberate actions, and there is no batch or automatic promotion route.

Promotion copies `project_id`, `title`, `summary`, `content`, `memory_type`,
`importance`, and `confidence` exactly from the proposal. The new Memory is
`active`; `event_time`, `expires_at`, and `supersedes_id` remain null rather
than being inferred. The legacy `source` value is the originating Source's
nonblank `reference`, falling back to its `name`.

The operation also creates exactly one structured link to the Source that owns
the extraction run's document. Its location is the proposal's nonblank
`source_locator`, or `chars <inclusive-start>-<exclusive-end>` from the stored
evidence range. The proposal's `memory_id` links to the created Memory.

The first promotion returns `promotion_status=created`. Repeating it returns
`unchanged` with the same Memory and changes no persisted data. A proposal row
lock makes concurrent requests create only one Memory and one Source link.
Promotion creates no embedding: the Memory participates immediately in lexical
and structured filtering, while semantic-only search requires the existing
explicit embedding action. If the linked Memory is later deleted, the existing
foreign key sets `memory_id` to null; a later explicit promotion may then create
a replacement. Alembic head remains `0008_memory_proposals`; no migration is
added.

```powershell
# Approve, then explicitly promote
Invoke-RestMethod -Method Post -ContentType 'application/json' `
  -Body '{"review_note":"Evidence verified"}' `
  "http://127.0.0.1:8000/memory-proposals/$proposalId/approve"
$promotion = Invoke-RestMethod -Method Post `
  "http://127.0.0.1:8000/memory-proposals/$proposalId/promote"

# Repeat promotion (returns unchanged)
Invoke-RestMethod -Method Post `
  "http://127.0.0.1:8000/memory-proposals/$proposalId/promote"

# Retrieve the Memory and its originating Source
$memoryId = $promotion.memory.id
Invoke-RestMethod "http://127.0.0.1:8000/memories/$memoryId"
Invoke-RestMethod "http://127.0.0.1:8000/memories/$memoryId/sources"
```

## Checkpoint 28: advisory Memory duplicate and similarity detection

Inspect one existing Memory without changing it or any candidate:

```powershell
Invoke-RestMethod `
  "http://127.0.0.1:8000/memories/<memory-uuid>/similarities?limit=10"
```

`GET /memories/{memory_id}/similarities` returns the target UUID and at most 50
same-project active candidates. The default limit is 10. The target is always
excluded, including when it would otherwise match itself. An unassigned Memory
is compared only with other unassigned Memories.

`exact_duplicate` means case-sensitive content equality after stripping ASCII
space, tab, LF, CR, form-feed, and vertical-tab characters from the ends and
replacing each internal run of those characters with one ASCII space. Unicode
separators such as non-breaking spaces remain significant. Punctuation and
letter case are preserved. A `similar` candidate must
meet either a lexical token-set Jaccard threshold of 0.60 with at least three
shared tokens, or a stored-embedding cosine-similarity threshold of 0.85.
Lexical and semantic scores are separate nullable fields and are never treated
as interchangeable.

Stored embeddings are used only when the target and candidate already have the
same provider, model, and fixed dimension. This endpoint never calls an
embedding or AI provider and never creates
or refreshes an embedding. Without stored embeddings it falls back to lexical
evidence. Results are advisory: they do not delete, merge, update, supersede,
archive, expire, promote, reject, or otherwise modify any Memory or related
record. Exact duplicate matching is exhaustive within the scope before the
public limit is applied. Similar-candidate discovery is advisory and
approximate: lexical and compatible-semantic retrieval each use a deterministic
relevance-ranked pool of at most 250 candidates. The public limit can truncate
both exact and similar results, including when more exact duplicates exist than
requested. Exact duplicates sort first, then stronger semantic evidence,
stronger lexical evidence, and UUID ascending. No migration is required;
Alembic head remains `0008_memory_proposals`.

## Checkpoint 29: advisory Memory contradiction detection

Inspect one active Memory for conservative potential contradictions:

```powershell
Invoke-RestMethod `
  "http://127.0.0.1:8000/memories/<memory-uuid>/contradictions?limit=10"
```

`GET /memories/{memory_id}/contradictions` uses the similarities endpoint's
default limit 10 and range 1..50. It returns `200` for a valid result, `404
memory not found` for a missing or inactive target, 422 for invalid input, and
the generic 503 database response when PostgreSQL is unavailable.

V1 is English-only and recognizes only `is/is not`, `are/are not`, `was/was
not`, `were/were not`, `can/cannot`, `can/can not`, and the state pairs
`enabled/disabled`, `active/inactive`, `true/false`, `on/off`, and
`available/unavailable`. The opposing markers must begin at the same token
position and removing them must leave exactly the same case-folded proposition
anchor after conservative ASCII-whitespace and surrounding-punctuation
normalization. Subject, attribute, qualifiers, identifier numbers, and token
order remain significant. Pairs with differing non-null structured
`event_time` values are excluded.

Results are `potential_contradiction` evidence for human review, never confirmed
contradictions. Project/null-project isolation, active candidate filtering,
self-exclusion, exact-duplicate exclusion, and bounded lexical and compatible
stored-embedding retrieval are inherited from similarity detection. Evidence
category precedes semantic score (descending, null last), lexical score
(descending, null last), and UUID in ordering; the public limit is applied only
after contradiction evaluation. Because each retrieval branch is bounded to
250 rows, results are advisory and potentially non-exhaustive.

The endpoint makes no provider call, writes nothing, and does not create or
update embeddings. General antonyms, scalar conflicts, inferred context,
approximate anchors, stemming, temporal reasoning beyond the structured-time
exclusion, multilingual rules, and provider-assisted reasoning are deferred.
No migration is required; Alembic head remains `0008_memory_proposals`.

## Checkpoint 31: explicit Memory superseding

Declare that an existing active replacement Memory supersedes an existing active
older Memory:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/memories/<older-memory-uuid>/supersede" `
  -ContentType "application/json" `
  -Body '{"replacement_memory_id":"<replacement-memory-uuid>"}'
```

The older Memory is always the path identifier and the replacement is always in
the body. Both must be distinct and active for the first transition, and their
nullable project scopes must be equal: the same project, or both unassigned.
Success stores the older identifier in `replacement.supersedes_id`, changes only
the older status to `superseded`, preserves the replacement as `active`, and
returns the complete two public Memories with `supersession_status: updated`.

Repeating that exact consistent request returns `unchanged` without a model
write or timestamp change. An older Memory may have only one direct successor;
a replacement may retain only its existing single predecessor. Multi-level
chains such as `A <- B <- C` are allowed, but self-links and direct or indirect
cycles are rejected. The transaction locks requested rows in UUID order and
serializes successor checks on the older row, so identical concurrent requests
converge on one relationship and competing replacements cannot overwrite it.

This workflow is explicitly human-controlled. Contradiction detection,
ingestion, proposal review/promotion, creation, and search never invoke it
automatically. Superseding does not copy or rewrite content, metadata,
provenance links, proposals, or embeddings. Current limitations are that the
one-successor rule is transactionally enforced rather than backed by a new
unique constraint, and inconsistent legacy state is reported as a conflict
rather than repaired. No migration is required; Alembic head remains
`0008_memory_proposals`.

## Checkpoint 32: explicit Memory expiration

Explicitly expire one active Memory without a request body:

```powershell
Invoke-RestMethod -Method Post `
  "http://127.0.0.1:8000/memories/<memory-uuid>/expire"
```

`POST /memories/{memory_id}/expire` returns the complete Memory with
`expiration_status: updated` for the first eligible transition. It changes the
status from `active` to `expired`. A null `expires_at` becomes the one UTC time
captured for the request; a future value is replaced with that time; an equal or
past value is preserved. Only status, `expires_at`, and the normal `updated_at`
effect may change.

Repeating a consistent expiration returns `unchanged` without a model write and
preserves both `expires_at` and `updated_at`. Missing Memories return `404 memory
not found`. Superseded, invalid, and archived Memories return `409 memory not
eligible for expiration`; an expired Memory with a null timestamp returns `409
memory expiration state is inconsistent`. Database failures return the generic
503 response.

The route locks the target PostgreSQL row and owns one transaction, so concurrent
identical requests produce exactly one `updated` result and then `unchanged`
results with one stable expiration timestamp. It never changes content,
metadata, provenance, embeddings, proposals, projects, or supersession links.

Expiration is human-controlled only. Passing `expires_at`, or allowing that time
to pass, never changes status automatically. Search and retrieval do not process
scheduled expiration. Similarity continues to accept an existing non-active
target under its established behavior but considers only active candidates;
contradiction detection requires an active target and active candidates.
Scheduled expiration processing is deferred. Migration
`0009_memory_expiration` only extends `ck_memories_status` with `expired`; its
downgrade refuses to proceed while expired rows exist rather than rewriting
them.

## Checkpoint 33: explicit Memory quality refinement

Refine one active Memory's persisted quality metadata explicitly:

```powershell
Invoke-RestMethod -Method Post -ContentType 'application/json' `
  -Body '{"confidence":0.8,"importance":0.7}' `
  'http://127.0.0.1:8000/memories/<memory-uuid>/quality'
```

`POST /memories/{memory_id}/quality` accepts `confidence`, `importance`, or
both. Each supplied non-null value must be finite and within 0.0 through 1.0;
at least one is required. Omitted fields are preserved exactly. An actual
change returns `refinement_status: updated`; equal supplied values return
`unchanged` without a model write and preserve `updated_at`.

Only active Memories are eligible. The operation locks the Memory row, applies
a complete supplied pair atomically, and serializes concurrent requests. It
does not change status, expiration, supersession, content, provenance,
embeddings, proposals, or projects. Quality scoring remains entirely manual:
there is no automatic scoring or provider call, and confidence/importance do
not alter any ranking policy. Current limitations are that refinement is
single-Memory only and retains the existing binary floating-point database
representation. No migration is required; Alembic head remains
`0009_memory_expiration`.

## Checkpoint 34: evidence-backed Memory answers

`POST /answers` accepts a required question (`query`, trimmed, 1–500
characters), optional `project_id`, `search_mode` (`lexical`, `semantic`, or
`hybrid`, default `hybrid`), and `limit` (1–20, default 10). Unknown fields are
rejected. Retrieval uses the existing deterministic active-Memory search rules
and nullable-project/project filtering; an unknown project simply yields no
evidence.

The provider receives only deterministic `M1`…`Mn` evidence blocks, capped at
2,000 characters per Memory and 12,000 characters total. Memory content is
untrusted evidence: embedded instructions are ignored, and the provider may use
no general knowledge, tools, web content, or external sources. Output is capped
by project configuration and must strictly report `answered` with at least one
valid evidence label, or `insufficient_evidence` with no labels. Duplicate
labels are deduplicated; unknown labels fail generically. Returned citations
preserve retrieval order and include the full public Memory plus separate
nullable lexical and semantic scores.

When retrieval is empty, the API returns HTTP 200 with a deterministic
`insufficient_evidence` message and no citations without resolving the answer
provider. Semantic and hybrid modes require the configured embedding provider;
lexical mode does not. The operation is stateless and read-only: it commits no
transaction and persists no question, answer, conversation, retrieval history,
query embedding, usage counter, or search statistic. It is not chat and has no
follow-up history, agent framework, tool calling, or document/chunk retrieval.
