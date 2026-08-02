# Second Brain chat handoff

Checkpoint 48 is implemented locally and approved for commit, but is not yet
recorded as committed or pushed in this handoff. The functional `/search` screen
uses the existing lexical `GET /memories` contract and semantic/hybrid `POST
/memories/search` contract. It preserves backend order, exposes only supported
persisted-field filters, validates public `MemoryRead[]` responses, and links
results to Memory detail without N+1 reads or invented scores. See
`docs/checkpoint-48-report.md` for Full verification and read-only browser-smoke
evidence. Do not begin Checkpoint 49 until Checkpoint 48 is committed, reviewed,
pushed, and the repository is clean.

Second Brain is a local knowledge-memory API. The repository is normally at
`C:\Users\user\Desktop\second-brain` on Windows with Python 3.12 in `.venv`.
FastAPI runs on the host; PostgreSQL 16 + pgvector runs in Docker. Host database
connections use `127.0.0.1:5433`: development database `second_brain`, test
database `second_brain_test`. Obtain credentials from local example/configuration
workflow; never paste secrets.

Current Alembic head: `0009_memory_expiration`. Checkpoints 1 through 47 are
complete; Checkpoint 48 is implemented and approved for commit. Completed capabilities include:
persistence, projects, Memories, normalized sources, structured metadata,
lexical/semantic/hybrid search, optional embeddings, TXT/PDF ingestion, AI
proposal generation, human review, explicit promotion, and reusable developer
workflow documentation/scripts, advisory Memory duplicate/similarity detection,
conservative explicit-polarity contradiction detection, and explicit Memory
supersession, explicit Memory expiration, and explicit Memory quality
refinement. Endpoint categories
are health/readiness,
projects, Memories/search/embedding, sources/ingestion/proposal generation, and
proposal review/promotion.

`POST /answers` explicitly answers one trimmed question from a single bounded
active-Memory lexical, semantic, or hybrid retrieval (hybrid default), with an
optional project filter. Evidence receives deterministic M1..Mn labels and is
bounded to 2,000 characters per Memory and 12,000 characters total. Provider
output is strictly typed and capped; only validated cited Memories are returned,
in retrieval order, with separate nullable lexical and semantic scores. Empty
retrieval returns deterministic `insufficient_evidence` without resolving an
answer provider. Memory text is untrusted evidence, never instructions. The
operation commits nothing and stores no query, answer, prompt, conversation, or
history. There is no chat follow-up, agent, tool use, web access, or external
source retrieval.

Duplicate detection uses exhaustive normalized equality within the target's
project scope before the requested result limit. Similar-candidate discovery is
advisory and approximate, using bounded relevance-ranked lexical and compatible
stored-embedding pools; it never calls a provider or modifies stored data.

Contradiction detection is English-only and advisory. It recognizes only the
documented explicit negation and boolean-state pairs when the remaining
normalized proposition anchors match exactly. It reuses the same active,
same-project/null-project, bounded lexical and compatible stored-embedding
candidate pools, excludes differing non-null event times, calls no provider,
and persists nothing. Results may be non-exhaustive.

Memory supersession is a human-controlled `POST
/memories/{older_memory_id}/supersede` action whose body identifies an existing
active replacement. It requires equal nullable project scope, atomically links
the active replacement and marks the older Memory superseded, permits acyclic
chains, enforces one direct successor under deterministic row locking, and is
idempotent without timestamp writes. It never resolves contradictions
automatically or rewrites content, provenance, proposals, or embeddings.

Memory expiration is the human-controlled `POST /memories/{memory_id}/expire`
action. It locks one row, transitions only an active Memory to `expired`, uses
the request UTC time for a null or future `expires_at`, preserves an equal or
past timestamp, and is idempotent without repeat timestamp writes. No scheduler
or timestamp-passing behavior changes status automatically. Similarity keeps its
existing non-active-target behavior while filtering candidates to active rows;
contradiction detection requires active targets and candidates.

Memory quality refinement is the human-controlled `POST
/memories/{memory_id}/quality` action. It row-locks one active Memory and
updates supplied finite confidence and/or importance values in the inclusive
0.0..1.0 range. Omitted fields are preserved, complete pairs are atomic, and
equal requests return unchanged without writing. It makes no provider call,
performs no automatic scoring, and changes no ranking policy.

Retrieval quality evaluation is a developer-only, nine-case versioned harness
for lexical, semantic, and hybrid active-Memory retrieval. It directly reuses
production retrieval, uses fixed local 1536-dimensional vectors, and reports
Hit@K, Recall@K, MRR, and Precision@K separately by mode. The PowerShell 5.1
command verifies `second_brain_test`, creates fixtures inside one transaction,
rolls back every application-table write, makes no provider call, and optionally
writes JSON only to an explicit output path. Baseline checks use reviewed minimum
thresholds and never update the checked-in baseline automatically.

`POST /memory-embeddings/batch` explicitly embeds at most 50 active Memories
that are missing embeddings, scoped to one project, unassigned rows, or all
rows. SQL selection is stable by creation time and UUID. A non-empty selection
makes one validated ordered provider call before UUID-ordered row locks recheck
status and existing embeddings. Inserts are atomic; concurrent winners return
unchanged and newly inactive rows return skipped. Empty batches resolve no
provider or commit. Existing embeddings are never replaced, and there is no
automatic/background generation.

`POST /memory-embeddings/reembed` explicitly replaces bounded existing active
Memory embeddings. Stale selection compares canonical input hash, provider,
model, and dimensions; all selection forces replacement. SQL ordering and limit
are deterministic, one fully validated provider batch precedes UUID-ordered
locks, and eligible rows update atomically in place while preserving embedding
identity and creation time. Concurrent stale winners become unchanged; deleted
or newly inactive candidates are skipped. Missing embeddings are never created,
and there is no automatic or scheduled re-embedding.

The developer-only `scripts/audit-memory-maintenance.ps1` command produces a
deterministic, read-only point-in-time report over Memory status, project
assignment, missing/stale active embeddings, due/future active expiration
timestamps, inconsistent expired state, and embeddings on non-active Memories.
It captures one UTC instant, returns full counts with bounded IDs ordered by
creation time and UUID, reuses the controlled re-embedding staleness predicate,
validates parsed/live database identity, and runs in a database read-only
transaction. It resolves no provider, exposes no API, and performs no repair or
application-data write.

Read `AGENTS.md` and stable docs before work. One checkpoint at a time; preserve
exact API behavior; use the test database for integration tests; never downgrade
development, expose secrets, call paid providers without approval, delete
volumes, or commit/push without approval. Run Full verification with zero skips.

Most recently implemented: Checkpoint 43, the Project retrieval API and Projects
UI. `GET /projects/{project_id}` returns the complete `ProjectRead`, returns
exactly `{"detail":"project not found"}` for a valid missing UUID, preserves
FastAPI malformed-UUID validation, and maps database failures to the established
generic 503. It is read-only and does not commit or flush. Existing `GET
/projects` and `POST /projects` contracts are unchanged.

The `/projects` screen lists Projects with real `limit=20`/`offset` pagination
and provides a controlled, trimmed creation form. Validation focuses the first
invalid field, submission is single-flight, successful responses are strictly
validated before navigation, and failed creation remains on the form. The
`/projects/:projectId` screen validates the route UUID locally, retrieves one
Project, displays all safe fields, distinguishes missing from generic failure,
and links back to the list. Loading, populated, empty, validation, missing, and
safe error states are accessible; retry is manual and requests are cancelled on
unmount. There is no polling, browser persistence, optimistic creation, fake
data, Project edit, or Project delete.

The `/sources` screen now lists and creates Sources with the exact existing
contract and real limit/offset pagination. `/sources/:sourceId` validates UUIDs,
retrieves every safe Source field, and summarizes existing Source-to-Memory
relationships through the established read-only endpoint. Source detail also
lists its real document and links to exact-contract JSON/TXT/PDF ingestion.
`/source-documents/:documentId` shows public metadata and paginated chunk evidence.
All screens use strict response validation, cancellation, accessible states, and
manual retry. There is no automatic proposal generation, edit, delete, polling,
browser persistence, or optimistic document. `/search` is now functional for
explicit lexical, semantic, and hybrid retrieval; Answers and Settings remain
placeholders.

Frontend setup, development, and verification use
`scripts/frontend-setup.ps1`, `scripts/frontend-dev.ps1`, and
`scripts/verify-frontend.ps1`. Full project verification now includes frontend
lint, TypeScript checking, non-watch Vitest, and the production build. The UI
has no authentication, application-data write workflow, persistent browser
storage, provider call, analytics, or telemetry. Checkpoint 43 Full verification
passed 624 Python tests and 25 frontend tests with zero skips after the explicitly
approved recreation of only the exhausted `second_brain_test` database. The
development database remained Projects=1 and Memories=1. Maintenance execution,
scheduled expiration processing, and persistent observability remain deferred.
Continue one approved checkpoint at a time and attach
`docs/checkpoint-45-report.md` to the new conversation.

## Copy from PowerShell

```powershell
Get-Content .\docs\CHAT_HANDOFF.md -Raw | Set-Clipboard
```
# Checkpoint 42 handoff

Checkpoint 42 adds the maintainable local React/TypeScript/Vite workspace,
responsive accessible shell, strict health/readiness dashboard, safe typed API
boundary, deterministic placeholder and Not Found routes, locked npm
dependencies, Windows PowerShell 5.1 frontend scripts, and Full verification
integration. Full verification passes 610 Python tests and 14 frontend tests
with zero skips; browser smoke passes through the Vite proxy. No backend code,
API contract, Python dependency, Docker service, database behavior, or migration
changed. Alembic remains `0009_memory_expiration`. Review
`docs/checkpoint-42-report.md`. Do not begin another checkpoint until this
checkpoint is approved, committed, pushed, and the repository is clean.
