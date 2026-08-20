# API conventions

- Use typed FastAPI routes and Pydantic v2 schemas. Preserve bare arrays where
  already established.
- Preserve exact documented error `detail` strings; return generic database and
  provider errors without internal details.
- Routes own commit/rollback. Repositories never commit.
- Perform filtering, ordering, ranking, and pagination in SQL. Avoid N+1 queries
  and provide deterministic tie-breaking order.
- Use UUID identifiers and timezone-aware timestamps.
- Public schemas never expose vectors, secrets, raw provider output, prompts,
  SQL, or complete internal document content.
- Public operations schemas additionally exclude complete database URLs,
  environment values, filesystem paths, arbitrary diagnostic metadata, entity
  UUID samples, and raw exceptions. Diagnostics and maintenance operations are
  aggregate-only, database-enforced read-only, and advisory. Bundle operations
  expose only safe manifest summaries and require direct loopback plus an exact
  operation header; forwarded-client headers never establish locality.
- Prefer explicit actions to hidden automation: embedding, proposal generation,
  review, and promotion are separate operations.
- Maintain backward compatibility unless the checkpoint explicitly changes the
  contract. API-only work does not require a migration.

## Agent Runs

The manual lifecycle exposes those four existing operations plus exactly
`POST /agent-runs/{run_id}/plan`, `GET /agent-runs/{run_id}/plan`,
`POST /agent-runs/{run_id}/execute`, and
`GET /agent-runs/{run_id}/execution`. Creation
requires a validated `Idempotency-Key`, stores only its SHA-256 hash, binds it to
a canonical request fingerprint, and atomically appends the sequence-zero event.
Listing uses SQL filters and `created_at DESC, id DESC`; Project scope and
explicit unassigned scope never widen each other. Cancellation locks the Run,
checks its monotonic revision, and atomically appends one event; replay of an
already cancelled Run is unchanged.

Creation is bounded to 32 nonterminal Runs across the local instance. The
capacity decision is serialized in PostgreSQL; exact idempotent replay remains
available at capacity. A distinct new request over capacity returns HTTP 429
with `active Agent Run capacity reached` and creates no Run or event.

The public projection is limited to Run identity/scope, agent and policy
versions, bounded goal and budgets, state/deadlines/revision, safe error code,
and timestamps. Correlation identity, idempotency/fingerprint hashes, events,
child entities, metadata, prompts, provider/tool payloads, secrets, SQL, and raw
exceptions are private. There is no public generic transition route.

New Runs capture the private Tool Registry version `agent-tools-v1`; idempotent
replay returns the original Run and its original captured version. The registry
has no public route and contains metadata/schemas only. Policy lookup is exact
name plus positive integer version and permits only `read` authority. Null Run
scope is explicit unassigned scope, never unrestricted. Entity reads must apply
the exact captured scope; `project.get` is denied for null scope. Operator
aggregate definitions default denied and require an application-owned internal
capability. Semantic/hybrid explained search may use only the configured
provider boundary; lexical mode is provider/network free. Captured total budget,
per-Tool calls, 15-second timeout, and 65,536-byte validated output ceilings can
only be tightened.

Planning claims `created` as `planning` in one short committed transaction,
calls the application-selected configured text provider outside every database
transaction, validates the complete bounded JSON plan through registry policy,
then atomically inserts ordered pending Steps and transitions to `ready`.
Failures store only a stable safe code and no partial Steps. The public plan is
an allowlisted projection, and planning invokes no Tool.

Execution claims a complete frozen `ready` plan in one short transaction, then
reserves, invokes, and finalizes one ordered Step at a time without holding the
Run lock across Tool latency. Policy is revalidated from persisted state before
every call. Only the exact version-1 `project.get`, `memory.get`,
`memory.search_explained`, `source.get`, and `source_chunk.get` read Tools are
executable; operator aggregates remain denied. Successful output is strictly
validated and size-bounded, then reduced to a safe summary and typed evidence
references. Retry classification is closed to `never`, `safe_transient_read`,
and `ambiguous_manual_recovery`; only exact registered `read`/`pure_read` Tools
with `tool_timeout`, `tool_provider_unavailable`, or `tool_provider_failed` may
consume the single global retry. Exact terminal execute replay returns the
durable projection without writes or Tool calls. Cancellation and expiry lock
and reconcile unfinished children, and late results are discarded. Recovery is
an explicit synchronous local operator command for one Run only; no recovery
worker, scheduler, lease, heartbeat, polling, or startup recovery is available.

Research kind `research` version `1` is code-owned and read-only; unknown
Research versions are rejected. Its allowlist is exactly `project.get`,
`memory.get`, `memory.search_explained`, `source.get`, and `source_chunk.get`.
The execution projection adds nullable `research_result`. Answered results use
bounded claims and deterministic citation numbers; citations expose only entity
type, public UUID, and application-owned current version. Insufficient results
contain no claims or citations. Raw evidence, provider/Tool payloads, prompts,
and private Run/Step/Invocation identities remain private.

Curator kind `memory_curator` version `1` is code-owned with maximum authority
`propose`; unknown versions are rejected. Its exact read Tool allowlist is
`memory.get` and `memory.search_explained`, both version 1. The execution
projection adds nullable `curator_result` with bounded findings, versioned
public evidence identities, and immutable proposed-action identities. Its
closed proposal catalog is only `memory.update`; proposal creation occurs only
during validated synthesis. Existing explicit human review never executes it.

## Explained Memory search

`POST /memories/search/explained` is the only additive explained-search route.
Its required request fields are `query`, `mode`, `filters`, and `pagination`;
`mode` has no default. The response is one bare array. Each item contains only global
one-based `rank`, an unchanged `MemoryRead` under `memory`, and a typed
`explanation` with `mode`, ordered `matched_by`, lexical/semantic ranks and
signals, lexical/semantic RRF contributions, and fused RRF score.

Public float serialization rounds to six decimal places. Lexical signal is the
clamped value `raw_ts_rank_cd / (1 + raw_ts_rank_cd)`. Semantic signal is the
clamped value `1 - cosine_distance / 2`. Hybrid uses `k=60`; each available
channel contributes `1 / (60 + channel_rank)`, and the fused value is the sum
of unrounded available contributions before public rounding. These values are
deterministic ranking aids, never confidence, probability, truth, certainty,
model reasoning, or a relevance guarantee.

Lexical mode resolves no provider and has null semantic and RRF fields.
Semantic mode preserves the established provider validation and safe failures
and has null lexical and RRF fields. Hybrid preserves the established bounded
candidate formula and exposes channel values only when that candidate set
contained the Memory. The route is read-only and persists nothing. Raw lexical
scores, cosine distances, vectors, dimensions, SQL, prompts, provider responses,
secrets, and exception text remain private. Existing search and Answer request,
response, ranking, filtering, pagination, provider, and error contracts remain
unchanged.
