# Architecture

Second Brain is a local, Windows-hosted FastAPI application. PostgreSQL 16 with
pgvector runs in Docker Compose. Application persistence uses synchronous
SQLAlchemy 2 sessions and Alembic migrations; the current head is
`0010_agent_runtime_persistence`.

Local V1 operation is defined by `LOCAL_V1_RUNBOOK.md`, with capability evidence
in `LOCAL_V1_ACCEPTANCE.md` and explicit deferrals in `KNOWN_LIMITATIONS.md`.
The stable recovery architecture is released as `v1.0.0` at commit
`a1bf40c0a27e9ee508e9bf1ab151b4665fbdba32`. The supported release topology
remains loopback Vite and FastAPI plus the named-volume PostgreSQL service;
there is no authentication or cloud boundary. All nine top-level UI routes are
functional. Local V1.1 is published as `v1.1.0` from exact commit
`88dffa90ff04cde4c57dcacbe2764b8a31b0c9ce`; `v1.0.0` remains the pre-V1.1
recovery point.

The additive V1.1 architecture is documented in
[V1_1_ROADMAP.md](V1_1_ROADMAP.md). It preserves this topology and data model,
isolates dependency remediation and non-authoritative CI, then adds one
read-only explained-search contract and its accessible UI. Checkpoint 57 is
complete at `f6b9260`; Checkpoint 58 consumes `POST /memories/search/explained`
locally. Checkpoint 59 is committed at `42fdfc8`; Checkpoint 60 is complete at
the V1.1 release commit. Existing
search responses and version-1 export/import remain compatible. No V1.1
migration is proposed.

Checkpoint 61 completed the documentation-only Local V1.2 Agent architecture at
`850cfd0a749b5de072b910203ba9906ab5270b40`. Checkpoint 62 completed the durable
five-table persistence foundation at
`3da0cdd875dc8af7a60fd8af5b6f9878be5a769a`. Checkpoint 63 completed the manually
initiated Agent Run create/retrieve/list/cancel API and strict internal state
transition service at `01832a94ae6f80bdacd0cd9301af3f294302e3e8`.
Repositories accept caller-owned
synchronous sessions and never commit. AgentRun row locks serialize revision and
event-sequence allocation, and child ownership derives scope from the Run.
Version-1 Project export/import excludes these tables. Checkpoint 64 completed
the immutable code-owned `agent-tools-v1` registry and pure fail-closed policy
resolver at `35950c60fd842a4ad022f130a3074ce8d21d9bbc`. Checkpoint 65 completed
strict structured planning at `1b32d91e62feb10efd5c2f2c241ee43b75b5b5e2`.
Checkpoint 66 completed synchronous ordered execution through exactly five
scoped application-owned reads at
`d4a3533282a8ed616fa0910fcea99b07b0f1b878`. Checkpoint 67 completed a closed retry
classifier, at most one global safe-read retry, terminal execution replay,
deadline/cancellation reconciliation, stale detection, and one explicit
synchronous operator recovery command at
`7b6c6bb8c4c67f9e8a5a34c363331bc94dbb094e`. Recovery is
never automatic; there is no worker, scheduler, lease, heartbeat, or startup
recovery. The architecture is in
[V1_2_AGENT_ROADMAP.md](V1_2_AGENT_ROADMAP.md) and
[AGENT_THREAT_MODEL.md](AGENT_THREAT_MODEL.md). The existing four Agent Run
operations remain unchanged, with two additive plan operations at
`POST /agent-runs/{run_id}/plan` and `GET /agent-runs/{run_id}/plan`. Planning
commits its claim before provider latency and validates the whole result before
atomically freezing pending Steps with `ready`. There is no generic transition
or child-entity API. Execution is exposed only at
`POST /agent-runs/{run_id}/execute` with its bounded projection at
`GET /agent-runs/{run_id}/execution`. Checkpoint 69 adds the explicit-refresh-only
Agent Runs UI at `/agents` and `/agents/:runId`; there is no approval execution,
Automation, connector, or external behavior. The registry contains exactly
seven version-1 read-only metadata definitions: `project.get`, `memory.get`,
`memory.search_explained`, `source.get`, `source_chunk.get`,
`operations.diagnostics`, and `maintenance.audit`. New Runs capture
`agent-tools-v1`; existing Runs retain their captured value. Only the first five
entity/search reads are executable by Runs; both operator aggregates remain
denied. Execution revalidates policy before each reservation, releases all Run
locks across Tool latency, and persists only safe summaries and evidence
references. The boundary
separates a manually initiated durable Agent Run from a future Automation that
would trigger a Run. Initial authority is read-only: models cannot grant
authority, tools are code-owned/versioned/schema-bounded, proposals require
exact immutable human review, and execute authority is unavailable. Schedulers,
workers, connectors, external writes, arbitrary execution, and remote or
multi-user operation remain outside V1.2.

Checkpoint 70 adds the immutable `research` version `1` Agent with `read`
authority and exactly the first five entity/search Tools. Retrieved content is
untrusted evidence, never instruction. Synthesis may cite only application-
supplied evidence IDs; exact Run/Step/Invocation ownership, nullable scope,
existence, and deterministic current entity version are revalidated before one
safe result event commits. Memory versions reuse the Checkpoint 68 target-version
helper. Empty evidence returns explicit insufficiency without provider
resolution. Research has no proposal, Approval creation, execute authority,
mutation, operator aggregate, external research, browser, or HTTP capability.

Checkpoint 68 is complete at
`1bc90b4339bd5466fda10e5d04711e3f025a0e01`. Its four additive Approval APIs create,
list, retrieve, and human-review immutable `memory.update` proposals using the
existing CP62 persistence. Creation derives the exact scoped target version,
canonical payload hash, bounded preview/evidence/risk, expiry, and execution
identity server-side. Review serializes Approval, Run, and target locks; expiry
becomes `expired`, target or scope drift becomes `superseded`, and exact
same-decision replay is write-free. Approval never changes a Memory, invokes a
Tool, transitions a Run, consumes the frozen execution identity, or grants
write/execute authority.

The Checkpoint 56 CI workflow is an early regression signal on pull requests to
`main`, pushes to `main`, and manual dispatch. Its Windows runner performs the
established non-database Quick path and locked frontend checks without secrets,
write permission, PostgreSQL, Docker, artifacts, publishing, or deployment.
It does not replace the release-authoritative local
`.\scripts\verify.ps1 -Mode Full` workflow or its database and acceptance gates.

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
additive explained-search contract, preserves backend ordering and global ranks,
and presents validated channel signals as ordering aids. Answers provides an
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
- The additive explained-search projection exposes only one-based global result
  and channel ranks, six-decimal bounded lexical/semantic signals, and hybrid
  RRF contributions with `k=60`. Ranking, filtering, fusion, ordering, and
  pagination remain in one bounded SQL statement. Lexical mode never resolves
  an embedding provider; semantic and hybrid modes preserve existing safe
  provider behavior. Queries, embeddings, results, and history are not stored.
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
