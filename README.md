# Second Brain

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

Warning: the following command permanently deletes the local named database
volume and its data. Do not run it casually:

```powershell
docker compose --env-file .env.example down -v
```

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
