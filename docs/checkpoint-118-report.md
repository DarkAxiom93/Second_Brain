# Checkpoint 118 report

Status: **Implemented; awaiting human review.** Baseline:
`87a5650158629bae49c21def39f1b332c5a1996f`.

## Delivered public contract

The loopback-only API now exposes `POST /capture-items`,
`POST /capture-items/query`, `POST /capture-items/{id}/detail`,
`PATCH /capture-items/{id}`, and the `/reassign`, `/discard`, and `/restore`
actions. Bodies reject unknown fields. Responses contain only `id`,
`project_id`, `content`, `state`, `revision`, creation/update/processing
timestamps, and `resulting_source_id`.

Creation requires an 8-128 visible-ASCII `Idempotency-Key`; omitted scope and
explicit `{unassigned: true}` mean unassigned, while one non-null `project_id`
means assigned. Null, false, or ambiguous scope forms fail validation. New
creation returns 201, exact normalized replay returns 200, and reuse for another
normalized content/scope fingerprint returns deterministic 409.

Every other operation requires exactly `{project_id: UUID}` or
`{unassigned: true}`. A requested Project is validated, and item ID and current
scope are combined in the repository predicate. Cross-Project and
assigned/unassigned identifier replay therefore returns the same item-not-found
shape as a forged/nonmatching item.

## Query, cursor, and resource behavior

Query defaults to pending, accepts 1-3 unique closed states, page size 1-50
(default 25), and an optional trimmed 1-200-character/800-byte control-free
lexical query. Browse order is `created_at DESC, id DESC`. Lexical search uses
the generated PostgreSQL `simple` vector and `plainto_tsquery`, orders by
`ts_rank_cd DESC, created_at DESC, id DESC`, and does not expose rank.

Pagination fetches at most page-size plus one row and uses only keyset
predicates. The opaque AES-GCM cursor uses a PBKDF2-derived, domain-separated
key and canonical unpadded base64url. Its authenticated payload binds exact
scope, normalized query/browse mode, sorted state set, page size, ordering
version, and final rank/creation/UUID tuple. Malformed, noncanonical, tampered,
or request-replayed cursors fail with 422. It contains no Capture content or
idempotency data. There is no OFFSET, count, facet, semantic/model/provider/
network call, caller-selected sort, or unbounded application iteration.

## Mutation and concurrency behavior

Content edit and reassignment require pending state. Discard is only
`pending -> discarded`; restore is only `discarded -> pending`; processed is
terminal. Each action validates exact scope, locks the exact scoped row with
PostgreSQL `FOR UPDATE`, revalidates state and the positive observed revision,
changes only the action-owned fields, increments revision once, advances
`updated_at`, and commits in the route-owned transaction. Stale revisions write
nothing and return 409 with the authoritative safe projection. A barrier-driven
two-connection test proves two same-revision edits have exactly one winner,
revision advances once, and the loser receives deterministic conflict.

Normal paths preserve the approved ceilings: create/replay <=3, query <=2,
detail <=2, edit <=3, reassignment <=4, and discard/restore <=3 counted SQL
statements, excluding transaction control. Instrumented API coverage verifies
representative creation, query, detail, edit, and transition successes.

## Privacy, authority, and omissions

Raw keys, key hashes, request fingerprints, lexical vectors/ranks, cursor
authentication material, and SQL are absent from projections. Capture content,
scope UUIDs, idempotency data, provenance, and cursor secrets are not logged.
The immutable Tool Registry remains `agent-tools-v1`; Project export remains
`second-brain-project-export` version 1. Capture remains absent from Context Hub,
Agents/Tools, Automations, Daily Brief, Project Watch, Curator, Memory search,
Answers, embeddings/models/providers/network, and export/import.

No migration or schema change was made. Alembic remains solely
`0017_capture_items`. `/convert-to-source` and `/{id}/source` do not exist;
Source conversion/resolver guards, frontend Quick Capture/Inbox, purge, rich
capture, AI routing, tasks/reminders, and all CP119+ work remain unstarted.

## Verification evidence

Before destructive focused test cleanup, the configured URL named
`second_brain_test` and live `SELECT current_database()` returned exactly
`second_brain_test`; `second_brain` was never modified. Focused CP117/CP118
tests passed **49 tests**, zero skipped, with one existing TestClient warning.
The final Full verification totals, Alembic evidence, repository identities,
and final hygiene output are recorded in the handoff after the required
post-final-edit run.

## Pre-commit audit remediation

The read-only pre-commit audit found one production validation-order defect and
three material evidence gaps. The implementation now rejects raw NUL and all
prohibited C0/C1 controls before trimming a lexical query; ordinary surrounding
spaces still trim for interpretation, after which the 1-200 scalar and 800-byte
UTF-8 limits apply.

Direct API evidence now covers public idempotency-header and creation-scope
matrices, every closed state-filter combination and bound, browse and lexical
ordering with timestamp/rank/UUID ties, stable keyset traversal, every cursor
request binding plus malformed/tampered/noncanonical/version cases, exact-scope
isolation for every action, both reassignment directions and Project-to-Project,
the complete pending/discarded/processed action matrix, stale revisions, and
revision/timestamp advancement.

Real PostgreSQL races use distinct Sessions and an explicit barrier for
edit/edit, reassign/reassign, discard/discard, restore/restore, and reassignment
versus an old-scope edit. Each test identifies the successful worker and proves
that the final content, scope, or state matches that winner with revision
advanced exactly once.

Instrumented exact statement counts are: new unassigned/assigned creation 1/2,
unassigned/assigned replay 2/3, query 1/2, detail 1/2, edit 2/3,
unassigned/assigned discard and restore 2/3, unassigned-to-assigned and
assigned-to-unassigned reassignment 3, and assigned-to-assigned reassignment 4.
Transaction control is excluded and no retry was introduced.

The remediated focused CP117/CP118 suite passed **77 tests**, zero skipped, with
one existing TestClient warning. The earlier Full run passed every Capture test
but ended at **1,453 passed, one failed, zero skipped** solely because Windows
Credential Manager returned `credential_store_locked`; credential production
or test behavior was not changed. The final post-remediation Full result is
recorded below after the required post-final-edit run.
