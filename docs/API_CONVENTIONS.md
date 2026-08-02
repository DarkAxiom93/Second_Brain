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
