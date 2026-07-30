# Separate Memory embeddings

Status: Accepted

## Context

Embeddings are optional derived data with provider, model, dimensions, input
hash, and generation time provenance. Models and vectors may change.

## Decision

Store the current embedding in `memory_embeddings`, linked one-to-one to
`memories`, rather than adding a vector to `memories`.

## Consequences

A Memory may exist without an embedding. Re-embedding and model changes can
replace derived state while preserving the Memory and its provenance boundary.
