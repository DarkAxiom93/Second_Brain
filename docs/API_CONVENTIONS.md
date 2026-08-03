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
