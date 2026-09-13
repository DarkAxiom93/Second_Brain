# Checkpoint 117 report

Status: **Implemented; awaiting human review.** Baseline:
`b436613c0dab78609e03e41458a715a5cfc1d2ff`.

## Delivered boundary

The sole migration head is `0017_capture_items`, linearly after
`0016_calendar_event_observations`. It creates only `capture_items`: UUID `id`,
nullable restricted Project FK, normalized text `content`, closed `state`,
positive `revision` defaulting to 1, timezone-aware creation/update timestamps,
nullable processing timestamp, nullable unique restricted resulting-Source FK,
private 64-character lowercase SHA-256 key hash and request fingerprint, and a
stored generated `to_tsvector('simple', coalesce(content, ''))` column.

Database checks enforce the closed state, positive revision, processed iff both
conversion fields exist, content character/UTF-8 bounds, and lowercase digest
shape. Unique constraints protect the key hash and one-to-one resulting Source.
Indexes are the exact `(project_id, state, created_at DESC, id DESC)` B-tree and
GIN over the generated lexical vector. `Source` was not given a Project field.

Creation normalizes CRLF/CR to LF, preserves every other leading/trailing
character, rejects NUL, whitespace-only input, surrogate/non-scalar strings,
more than 8,000 scalar values, or more than 32,000 UTF-8 bytes. Keys are exactly
8-128 visible ASCII characters and only their SHA-256 hashes persist. The
fingerprint is SHA-256 over UTF-8 canonical JSON with sorted keys and compact
separators containing domain `second-brain.capture-create.v1`, normalized
content, and exact scope `project:<canonical UUID>` or `unassigned`.

Assigned creation first validates the exact Project. It then executes one
PostgreSQL `INSERT ... ON CONFLICT (idempotency_key_hash) DO NOTHING RETURNING`.
An inserted row is the winner. A losing insert performs one exact lookup:
matching fingerprint returns the original safe projection; mismatch raises the
deterministic conflict. PostgreSQL uniqueness serializes races. There is no
process lock or retry loop. Paths use one statement for a new unassigned item,
two for its replay, two for a new assigned item, and three for assigned replay,
within the approved ceiling.

## Evidence

Focused unit and PostgreSQL evidence covers normalization and exact character/
byte boundaries, keys, fingerprints, private projection omission, defaults,
lexical generation/indexes, Project/unassigned creation, missing Project,
sequential replay/conflicts, real concurrent equal/conflicting requests,
constraints, FK delete restrictions, the exact 0016-to-0017 upgrade, single
head, and absence of a public route or Source Project column.

The focused pre-Full run passed 26 tests (13 unit and 13 PostgreSQL/migration
nodes) with zero skips. The authoritative Full totals are reported in the
checkpoint handoff after the final post-edit run.

### Pre-commit audit remediation

The read-only audit identified five evidence gaps; no production defect was
found and remediation changed tests and this report only.

1. Direct real-PostgreSQL cases now independently reject invalid state, zero
   and negative revision, each missing/retained processing-field combination,
   malformed private digests, character and UTF-8 overflow, and duplicate
   resulting Source identity. Both restricted FK deletion cases remain direct.
2. Exact snapshots now prove Capture is absent from the seven-definition
   `agent-tools-v1` registry, all Context Hub family/kind enums, Project export
   data files/models, and Project import table/insert inventories. Export stays
   `second-brain-project-export` version `1` with its existing manifest fields.
3. The conflicting two-session PostgreSQL race now records both submitted
   requests, identifies the sole successful caller, reloads the one physical
   row, and proves its normalized content, identity, and fingerprint match that
   winner while the other caller receives the deterministic conflict.
4. Exact 7/8/128/129 key lengths, whitespace, tab/newline, DEL, non-ASCII, and
   visible punctuation are covered. Persistence proves only SHA-256 is stored;
   safe-projection and captured-log assertions exclude the raw key and both
   private digests.
5. PostgreSQL `pg_indexes` and `information_schema.columns` assertions prove
   exact B-tree order/directions, GIN target, stored `simple` generated-vector
   expression, and automatic replacement after content changes.

The migration lifecycle fixture calls `verify_connected_test_database` before
its downgrade. That helper parses the configured URL, connects, executes
`SELECT current_database()`, and aborts unless both identities are exactly
`second_brain_test`. Fresh human authorization covers that test-only lifecycle;
the development database is never downgraded, reset, truncated, or deleted.

## Explicit omissions

There is no Capture API route or frontend/UI. CP118+ query/detail/edit,
reassignment, state transitions, Source conversion/resolver, scoped Source
guard, Context Hub/Tool/Agent/Automation/search/Answer integration,
provider/network/model/embedding behavior, export/import change, background
work, or delete/purge has begun. The processing columns have no production code
path that sets them. Tool Registry remains `agent-tools-v1`; Project export
remains `second-brain-project-export` version `1` and excludes CaptureItems.
