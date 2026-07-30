# Audited document ingestion and proposal stages

Status: Accepted

## Context

Uploaded content, parsing, evidence selection, provider execution, review, and
promotion have different failure and trust boundaries.

## Decision

Represent documents, chunks, extraction runs, proposal evidence snapshots,
human review, and promotion as separate auditable stages. Preserve evidence in
the proposal even if a source chunk is later removed.

## Consequences

Failures and retries are attributable, review is evidence-backed, and no stage
implicitly promotes provider output into Memory.
