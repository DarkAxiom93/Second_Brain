# Architecture

Second Brain is a local, Windows-hosted FastAPI application. PostgreSQL 16 with
pgvector runs in Docker Compose. Application persistence uses synchronous
SQLAlchemy 2 sessions and Alembic migrations; the current head is
`0009_memory_expiration`.

A client-only React and TypeScript application lives in `frontend/`. Vite serves
the local development UI and proxies `/api/*` to the existing loopback FastAPI
routes after removing `/api`. The browser uses same-origin relative requests by
default, so the backend requires no CORS changes. The initial dashboard reads
only `/health` and `/ready`. Projects uses the existing paginated list and
creation contracts plus read-only single-Project retrieval; its routes provide
list, creation, and detail screens. Sources uses paginated list and creation
contracts, read-only single-Source retrieval, and the existing Source-to-Memory
relationship listing for safe provenance detail. Source detail also lists its
persisted document, links to explicit JSON/TXT/PDF ingestion, and provides a
read-only paginated chunk browser. Proposals provides explicit SourceDocument-triggered
generation, a filtered paginated review queue, evidence/provenance detail, human
approval or rejection, and separate explicit promotion. Memories provides
persisted-field filtering and pagination, safe detail provenance, explicit
quality/supersession/expiration actions, and read-only quality advisories.
Search provides explicit lexical, semantic, and hybrid retrieval through the
existing Memory contracts and preserves backend ordering. Answers provides an
explicit stateless question workflow through the existing answer contract,
preserves returned citation order, and links returned public Memory IDs without
follow-up requests. Settings is a local operations dashboard over
health, readiness, safe diagnostics, aggregate maintenance findings, and
embedding coverage. It also provides explicit, loopback-only version-1 Project
export, import validation, and conflict-free import execution. Bundles stream
through exact temporary files; validation remains read-only and execution owns
one atomic commit. It exposes no repair, migration, or embedding control.
The frontend has no authentication, persistent browser storage,
service worker, or provider integration.

## Components and data

- `Project` groups Memories and proposal work.
- `Memory` is the reviewed knowledge record. `Source` and `MemorySource` provide
  normalized provenance links.
- `MemoryEmbedding` stores the optional current provider/model embedding outside
  `Memory`.
- `SourceDocument` stores TXT/PDF ingestion metadata and extracted text;
  `SourceChunk` stores ordered evidence ranges.
- `MemoryExtractionRun` records a deterministic AI extraction attempt;
  `MemoryProposal` stores immutable evidence snapshots and review state.
- Memory retrieval supports lexical PostgreSQL text search, semantic pgvector
  search, and hybrid Reciprocal Rank Fusion (RRF).
- Evidence-backed answers are stateless, read-only operations over one bounded
  active-Memory retrieval. A strict answer provider may cite only deterministic
  evidence labels; questions, answers, prompts, and retrieval history are not
  persisted.
- Memory quality detection performs advisory, read-only exact and similar
  candidate classification within one project. It may read existing embeddings
  only when provider, model, and dimensions match, but never generates them or
  modifies a Memory. Exact equality is queried independently; advisory similar
  discovery uses bounded relevance-ranked lexical and semantic pools.
- Contradiction detection reuses those same scoped, bounded candidate pools and
  reports only deterministic English explicit-negation or opposing-boolean-state
  pairs whose remaining normalized proposition anchors match exactly. It is
  advisory, non-exhaustive, provider-free, and never persists its results.
- Memory supersession is an explicit human action between two existing active
  Memories in equal nullable project scope. It preserves provenance and content,
  supports acyclic predecessor chains, and atomically marks only the older row
  superseded while linking the active replacement. Deterministic row locking
  enforces one direct successor and idempotent concurrency without automatic
  contradiction resolution.
- Memory expiration is an explicit human action on one active Memory. A row lock
  makes the active-to-expired transition idempotent under concurrency; the
  operation preserves an existing past expiration timestamp and replaces a null
  or future timestamp with the request's captured UTC time. No scheduler changes
  status merely because `expires_at` passes.
- Memory quality refinement is an explicit human action on one active Memory.
  A row lock serializes partial or complete confidence/importance updates;
  equal requests write nothing. No provider, automatic scoring, or retrieval
  ranking policy participates.
- Batch Memory embedding generation is an explicit synchronous action over at
  most 50 active Memories that lack embeddings. Project, unassigned, and all
  scopes select deterministically by creation time and UUID. One ordered
  provider request is validated before deterministic row locks recheck status
  and existing embeddings; successful inserts commit atomically, concurrent
  winners remain unchanged, and newly inactive rows are skipped. Empty batches
  resolve no provider. Existing embeddings are never replaced, and no
  background generation or re-embedding occurs.
- Batch Memory re-embedding is a separate explicit synchronous action over at
  most 50 active Memories that already have embeddings. Stale selection compares
  the canonical input hash and configured provider, model, and dimensions;
  forced-all selection replaces every eligible in-scope row. SQL selects in
  creation-time and UUID order, one validated provider batch runs without row
  locks, and deterministic locks then recheck eligibility before atomic in-place
  replacement. Embedding identity and creation time are preserved. Missing
  embeddings are never created, and no scheduled or background re-embedding
  occurs.
- Memory maintenance auditing is a developer-only, point-in-time, read-only
  operation. It captures one UTC instant, aggregates status/project assignment,
  and reports bounded creation-time/UUID-ordered IDs for missing or stale active
  embeddings, due/future active expiration timestamps, inconsistent expired
  state, and non-active embeddings. Staleness reuses the controlled
  re-embedding SQL predicate. Parsed/live database identity and a database
  read-only transaction prevent accidental writes; no provider is resolved.
- AI generation produces proposals. Human approval and explicit promotion are
  separate actions; only promotion creates a `Memory` and `MemorySource`.
- Project export is an explicit maintainer-only, read-only operation. It streams
  one project-scoped graph from a repeatable-read PostgreSQL snapshot into the
  checksummed `second-brain-project-export` version 1 private bundle.
- Project import is an explicit maintainer-only operation. It validates a
  complete version-1 bundle and target conflicts before dependency-safe inserts
  in one transaction. Validation-only is read-only; restore never merges,
  overwrites, remaps, repairs, or calls a provider.
- Operational diagnostics are an explicit local, read-only command. One captured
  UTC instant covers runtime/configuration identity, PostgreSQL and pgvector,
  Alembic consistency, required tables, and safe aggregate counts. Provider
  configuration is inspected without resolution or network calls; optional API
  probes are restricted to credential-free loopback targets.
- `GET /operations/diagnostics` reuses the established configuration, PostgreSQL,
  pgvector, Alembic, required-table, and aggregate-count checks inside the request
  session's database-enforced read-only transaction. Its public contract removes
  the target database and all diagnostic metadata; each check exposes only its
  ID, category, status, and safe message.
- `GET /operations/maintenance-audit` reuses the established audit with a zero
  detail limit and exposes aggregate status and finding counts only. Memory UUID
  samples and truncation details remain private. The underlying audit has no
  Project-scoped contract, so the route accepts no Project filter.
- `POST /operations/project-exports/{project_id}` streams the established
  deterministic bundle as a private attachment. `POST
  /operations/project-imports/validate` and `/execute` accept bounded raw bundle
  bodies. All three require the direct loopback client and a distinct exact
  operation header, ignore forwarded-client headers, return `no-store`, and
  remove only their request-owned temporary file.

```mermaid
flowchart LR
  S[Source] --> D[SourceDocument] --> C[SourceChunk]
  C --> R[MemoryExtractionRun] --> P[MemoryProposal]
  P --> H[human review] --> X[explicit promotion] --> M[Memory]
  M --> MS[MemorySource]
  M --> E[optional MemoryEmbedding]
  M --> Q[lexical / semantic / hybrid search]
```

## Boundaries and transactions

Persistence models define database shape and relationships. Repositories own
SQL-side filtering, locking, ordering, ranking, and persistence operations, but
never commit. Typed FastAPI routes validate public input, map expected failures,
own commit/rollback, and shape public responses. Provider integrations isolate
paid/external embedding and extraction calls. Ingestion and extraction helpers
that parse, normalize, chunk, hash, or validate data remain pure where possible.
The caller that owns the SQLAlchemy session owns the transaction.
