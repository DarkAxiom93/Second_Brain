# Hybrid search with Reciprocal Rank Fusion

Status: Accepted

## Context

PostgreSQL `ts_rank_cd` and cosine similarity have unrelated score scales;
direct weighted mixing creates unstable calibration.

## Decision

Fuse lexical and semantic result ranks with Reciprocal Rank Fusion (RRF), using
deterministic ordering.

## Consequences

Hybrid relevance does not depend on comparing incomparable raw scores. Rank
contributions remain explainable, while retrieval still depends on both lists.
