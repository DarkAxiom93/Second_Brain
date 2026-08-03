# Roadmap

This is a capability sequence, not a schedule.

## Local V1 release

Released: Local V1 is published as `v1.0.0` from commit `a1bf40c`, with
reproducible backend/frontend installation, safe startup and shutdown, full
zero-skip verification, all eight top-level UI routes functional, controlled
Project export/conflict validation, security/privacy/accessibility audits, and
maintainer runbook/handoff documentation. The current phase is post-V1
maintenance and V1.1 implementation. Checkpoints 55 and 56 are committed and
pushed at `cefdc4e` and `2c4ed44`. Checkpoint 57 implements the additive
explained-search backend locally and remains pending human review.

## Proposed Local V1.1

Checkpoint 54 proposes a small Local V1.1 focused on dependency safety,
non-authoritative continuous integration, and deterministic retrieval
explanations. The proposal adds no authentication, cloud boundary, background
automation, destructive maintenance, schema migration, or export-format
change. See [V1_1_ROADMAP.md](V1_1_ROADMAP.md) for evidence, priorities,
approval decisions, and independently reviewable checkpoints beginning with
55. Checkpoints 55 and 56 are committed and pushed. Checkpoint 56 CI is only an
early regression signal, while local Full verification remains
release-authoritative. Checkpoint 57 is implemented locally and pending review.

## Completed foundation

Completed: persistence; normalized sources; lexical, semantic, and hybrid
search; optional embeddings; TXT/PDF ingestion; AI proposals; human review; and
explicit promotion into Memory.

## Memory quality

Completed: duplicate detection, contradiction detection, explicit superseding,
explicit expiration, and explicit confidence/importance refinement. Planned:
scheduled-expiration handling.

## Retrieval and answers

Completed: explicit evidence-backed question answering with validated Memory
citations and an additive explained-search backend pending review. Planned:
explained-search UI; retrieval-quality evaluation is already available.

## Operations

Completed: explicit bounded batch embedding for active Memories missing an
embedding, controlled re-embedding of existing embeddings, deterministic
read-only maintenance auditing, versioned project export, and controlled
project import, plus read-only operational diagnostics and configuration
validation. Planned: maintenance execution, backups, and persistent
observability.

## User interface

Completed: maintainable local React/TypeScript workspace, responsive application
shell, deterministic routing, a read-only health/readiness dashboard, and a
Project workflow for paginated listing, creation, and detail retrieval, plus
Source listing, creation, detail, existing relationship summaries, explicit
JSON/TXT/PDF ingestion, document/chunk inspection, and the complete proposal
generation, review, rejection, approval, and promotion workflow, plus a Memory
browser with quality/lifecycle actions and read-only advisories, plus explicit
lexical, semantic, and hybrid Memory search, plus explicit evidence-backed
answers with returned Memory citations, plus an operations and settings
dashboard with explicit manual refresh and controlled Project export/import.
Future: chat with citations, authentication, and additional write workflows.

## Future agents and integrations

Future: executive coordinator, memory librarian, project specialists, Gmail,
Google Drive, Calendar, GitHub, and an approval center.
