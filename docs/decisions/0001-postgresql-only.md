# PostgreSQL-only production and integration behavior

Status: Accepted

## Context

The application depends on PostgreSQL UUIDs, full-text search, constraints,
locking, and pgvector behavior. SQLite cannot faithfully exercise these.

## Decision

Production behavior and behavioral integration tests use PostgreSQL. Integration
tests use the separately verified `second_brain_test` database; SQLite is not a
behavioral substitute.

## Consequences

Integration verification requires PostgreSQL, but tests cover the same database
semantics used by the application and cannot accidentally target development.
