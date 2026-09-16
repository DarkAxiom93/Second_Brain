# Local V1.7 Capture & Triage Inbox roadmap

Status: **Proposed for human review; Checkpoint 116 documentation only.**

Local V1.6 (`v1.6.0`, release commit
`64c8215d142ba66f7788d2a71f3debf291cd9862`) remains the current published
release. This document defines a proposed additive Local V1.7. It authorizes no
implementation until Checkpoint 116 is approved.

## Product decision

Local V1.7 adds a **Capture & Triage Inbox**. A short note can be captured in
seconds, retained durably in PostgreSQL, and later routed by an explicit human
action into the existing audited text Source pipeline.

A capture is unreviewed local user input. It is not a Memory, Source,
Notification, Agent Run, Automation, or Context Hub record and does not inherit
the authority of any of them. Capture is not AI classification, task
management, file capture, remote access, or autonomous processing.

## Domain and persistence

`CaptureItem` is a first-class PostgreSQL domain with:

- immutable UUID `id`;
- nullable `project_id`, where a UUID means exactly that Project and `NULL`
  means explicitly unassigned;
- normalized plain-text `content` containing 1-8,000 Unicode scalar values and
  at most 32,000 UTF-8 bytes;
- closed `state`: `pending`, `processed`, or `discarded`;
- monotonic positive `revision` for compare-and-set mutation;
- timezone-aware `created_at` and genuinely updating `updated_at`;
- nullable `processed_at` and nullable exact `resulting_source_id`; and
- private creation idempotency-key hash plus canonical request fingerprint.

The planned migration after sole current head
`0016_calendar_event_observations` creates one `capture_items` table, checks the
closed state and the coupled invariant
`processed <=> resulting_source_id and processed_at are non-null`, and indexes
exact-scope/state/order and the unique idempotency hash. It adds no second
persistence system, blob store, worker, provider store, or connector.

`project_id` uses `ON DELETE RESTRICT`: Project removal must not silently turn
assigned capture into unassigned capture. `resulting_source_id` is unique and
uses `ON DELETE RESTRICT`. The current application has no public Source-delete
route, but database/ORM deletion can cascade its document, chunks, extraction
runs, and Memory association rows. Restriction is therefore required so a
processed CaptureItem can never silently lose or ambiguously replace its exact
Source provenance. V1.7 adds no Source or Capture delete/purge operation.

`id` and `created_at` are immutable. `updated_at` changes on every successful
CaptureItem mutation. `processed_at` is null before processing, is written
exactly once by successful conversion, and never changes afterward because
`processed` is terminal. Pending content and scope, state, revision, updated
time, and conversion provenance are mutable only through their closed actions.
Content is stored as entered after existing
plain-text newline/NUL normalization; leading/trailing whitespace is preserved
when the value contains a non-whitespace character. Limits are checked after
normalization.

## State machine and concurrency

```text
pending --discard--> discarded --restore--> pending
pending --successful conversion--> processed (terminal)
```

Pending items alone may be edited or reassigned. Every edit, reassignment,
discard, restore, and conversion supplies the last observed positive revision.
The service locks the exact row, revalidates exact scope/state/revision, and
increments revision in the same commit. A stale request returns a conflict with
the authoritative safe projection and performs no write. There is no generic
state update endpoint.

Creation requires an `Idempotency-Key` of 8-128 visible ASCII characters. Only
its SHA-256 hash is stored. The hash is bound to a canonical fingerprint of
normalized content and exact scope. Same-key/same-fingerprint replay returns
the original item; same-key/different-fingerprint is a conflict. The unique
constraint serializes concurrent creation. Keys, hashes, and fingerprints are
private and excluded from responses, logs, diagnostics, exports, and UI.

## Exact Source conversion

Conversion is one route-owned PostgreSQL transaction using the existing
application repository functions that create a `Source` and upsert normalized
plain text into its `SourceDocument` and deterministic `SourceChunk` records.
It does not call the public routes in sequence and does not create a parallel
ingestion implementation.

The transaction resolves exact scope, locks and revalidates the item, and—for
pending state—creates one code-owned `capture` Source and ingests the exact text
with established defaults (chunk size 2,000; overlap 200). It then records the
Source UUID, processed time, terminal state, and next revision and commits all
Source/document/chunk/provenance changes atomically. Any failure rolls back all
of them. The row lock and unique Source FK prevent concurrent double creation.

If already processed, conversion validates scope and returns the recorded
Source without writing or rerunning ingestion. Replay accepts the prior
conversion revision or current revision only; this narrow exception makes an
ambiguous successful response safe. Other stale mutations conflict. The UI
reopens `/sources/{resulting_source_id}`.

The Source uses `source_type="capture"`, an application-generated bounded name,
no caller-controlled URL/reference, and the ingestion-derived checksum. The
existing Source schema gains no Project field. Instead, the unique reverse
`CaptureItem.resulting_source_id` relationship defines a **capture-bound
Source**. On successful conversion, the processed CaptureItem's exact
`project_id` or explicit-unassigned ownership becomes immutable and is the
authoritative origin/scope binding for that Source. The binding uses the scope
observed inside the locked conversion transaction, so reassignment cannot
commit one scope while conversion binds another. Sources without a reverse
CaptureItem binding are legacy/unbound Sources and retain existing contracts.

One common scoped Source resolver must reverse-detect this binding before any
read or action. For a capture-bound Source it requires exactly one requested
Project or explicit-unassigned scope and compares it with the immutable
processed CaptureItem scope. Mismatch, omission, null, both/neither scope, an
invalid processed binding, and forged Source/Capture/Project identifiers fail
closed. A legacy/unbound Source follows its existing contract. Existing global
Source list/detail routes must never return a capture-bound Source merely
because its UUID is known: an unscoped list omits capture-bound Sources, and an
unscoped ID/detail/document/action request rejects them. A scoped request may
resolve one only through the common guard.

The Inbox frontend reopens a converted Source through the planned scoped
`POST /capture-items/{id}/source` resolver using the current exact scope; it
must not navigate blindly to unscoped `/sources/{id}`. The resolver validates
CaptureItem ID, processed state, immutable scope, and its one Source before
returning the existing safe Source projection.

CP119 must inventory and apply the common guard to every existing path that can
encounter a capture-bound Source or its document/chunk: Source list/detail,
linked-Memory and document/chunk reads; text/file ingestion; proposal
generation/extraction; Memory-to-Source linking; proposal read/review/promotion;
`source.get` and `source_chunk.get` Agent Tools; Context Hub local query/detail;
and Project export/import selection. Internal calls must carry an existing
authoritative exact scope and cannot synthesize unassigned from omission.
Project export remains v1 and never exports the CaptureItem binding; a
capture-bound Source may enter its existing Source files only when its binding
matches the exact exported Project and the existing reviewed linkage selects
it. Imported Sources remain legacy/unbound. Later proposal generation still
requires the existing explicit exact-Project operation. Conversion creates no
Memory, proposal, embedding, model prompt, or provider request.

## API contracts and bounds

Bodies forbid unknown fields. Except for Quick Capture creation, every read or
action carries exactly one scope object: `{ "project_id": <UUID> }` or
`{ "unassigned": true }`. Both, neither, omitted, or `null` are invalid and
never mean all Projects. On creation only, omitted scope defaults to explicit
unassigned; supplied `project_id: null` is invalid.

- `POST /capture-items`: content, optional creation scope, required
  `Idempotency-Key`; `201` new or `200` exact replay.
- `POST /capture-items/query`: exact scope, closed state set (default pending),
  optional lexical query, page size, cursor.
- `POST /capture-items/{id}/detail`: exact scope.
- `PATCH /capture-items/{id}`: exact scope, revision, pending content.
- `POST /capture-items/{id}/reassign`: exact current and target scopes,
  revision; pending only.
- `POST /capture-items/{id}/discard` and `/restore`: exact scope and revision.
- `POST /capture-items/{id}/convert-to-source`: exact scope and revision;
  returns CaptureItem plus exact Source projection.
- `POST /capture-items/{id}/source`: exact-scope resolver for the already
  processed item's resulting Source; no write.

Content is 1-8,000 characters and at most 32,000 UTF-8 bytes. Optional lexical
query is trimmed, 1-200 characters, at most 800 UTF-8 bytes, and rejects NUL and
disallowed C0/C1 controls. Page size defaults to 25 and is 1-50; cursor input is
at most 2,048 characters; state filters contain 1-3 unique closed values.

Browse ordering is `created_at DESC, id DESC`. Lexical ordering is deterministic
PostgreSQL lexical rank descending, then that same tie order; rank is not
public and there is no semantic search or universal relevance score. A
versioned authenticated cursor binds exact scope, normalized query, states,
page size, mode, and final tuple. SQL applies ownership before search/order/
limit. Detail/actions combine ID and scope; identifier knowledge grants nothing.

### Deterministic query-resource contract

Every Capture endpoint uses a closed code-owned query shape. It uses keyset
pagination only: no offset pagination, count query, facet query, semantic or
embedding query, caller-selected sort/expression, or application-side iteration
over an unbounded result set. Query and response cardinality never exceed the
page-size limit. The migration must provide a composite B-tree index supporting
`(project_id, state, created_at DESC, id DESC)` scope/state/browse predicates
and a GIN index over the code-owned lexical search vector. Lexical queries must
apply exact scope/state predicates and the indexed lexical predicate before the
bounded keyset/order/limit operation.

Normal successful non-error paths have these SQL-statement ceilings; transaction
control statements are excluded, while every ORM SELECT/INSERT/UPDATE and one
batch chunk INSERT counts as one. Implementations may issue fewer statements.

| Operation | Maximum | Accounted statements |
|---|---:|---|
| create or exact create replay | 3 | optional Project validation; atomic idempotency insert/claim; original-item lookup/projection |
| query/list | 2 | optional Project validation; one bounded indexed result query |
| detail | 2 | optional Project validation; one exact scoped item query |
| pending content edit | 3 | optional Project validation; exact scoped row lock; update |
| reassignment | 4 | optional current-Project validation; destination-Project validation; exact current-scope row lock; update |
| discard or restore | 3 | optional Project validation; exact scoped row lock; update |
| convert or processed replay | 10 | optional Project validation; Capture row lock; Source insert/refresh; document lookup/insert; one batch chunk insert; Capture update; bounded response reloads |
| processed Source resolver | 3 | optional Project validation; exact scoped processed-Capture/reverse-binding lookup; Source projection |

The ceiling applies independently to each endpoint invocation. Error handling
may perform rollback but may not start an unbounded retry/repair loop. V1.7
makes no deterministic wall-clock, PostgreSQL examined-row, or fixed database-
work claim; index use, closed shapes, statement counts, and returned cardinality
are the deterministic controls.

## Trust, UX, export, and recovery

While content remains CaptureItem it is inert unreviewed input and absent from
Memory search/Answers, Context Hub, Agents/Tools/Automations, Daily Brief,
Project Watch, Curator, embeddings, prompts, providers/network, and automatic
Source/Memory creation. Conversion only enters audited Source ingestion; later
Memory trust still requires existing proposal, review, and promotion.

The shell gains persistent `+ Capture`, a focus-trapped fast modal with visible
unassigned default, and `/inbox` with exact scope, state views, submitted search,
pagination, detail, revision-aware actions, scoped Source reopen, and safe
conflict refresh. Content
is React text, never HTML/Markdown, with wrapping, overflow and
`unicode-bidi: isolate`. Escape closes and focus returns. Any shortcut is
application-local, never a Windows/global listener, and is ignored in input,
textarea, select, contenteditable, or editable descendants. No polling,
clipboard monitor, service worker, or browser persistence exists.

`second-brain-project-export` remains version `1`; CaptureItems are excluded
from export/import. Full PostgreSQL backups naturally include CaptureItems and
must be protected, retained, copied, and disposed like the database because
notes may be highly sensitive. Logs/diagnostics/telemetry/reports/browser
storage must not copy content, scope IDs, idempotency material, or provenance.
Recovery restores the whole database; there is no Capture export/purge/partial
restore.

## Explicit exclusions

Excluded: file/image/screenshot capture, OCR, voice, URL fetch, browser
extension, OS/global hotkeys, clipboard monitoring, AI classification/routing,
automatic Project/Source/Memory/proposal creation, tasks/dates/reminders,
email/Drive, Context Hub Capture, Agent/Automation access, background work,
external writes, remote/mobile/cloud access, and physical purge/delete.

## Independently reviewable sequence

- **CP116:** architecture and CAP01-CAP18 threat model; documentation only.
- **CP117:** implemented and awaiting human review: migration
  `0017_capture_items`, model/repository constraints and idempotent internal
  create; no public API/UI.
- **CP118:** implemented and awaiting human review: exact-scope Inbox
  query/detail and revision-aware triage API; no Source conversion or UI.
- **CP119:** transactional/idempotent audited Source conversion.
- **CP120:** accessible Quick Capture and Inbox frontend.
- **CP121:** one-to-one deterministic CAP01-CAP18 security gate.
- **CP122:** joined real-route/PostgreSQL/frontend acceptance.
- **CP123:** release hardening and evidence. Publication is separate.

Every checkpoint stops for human review; no later checkpoint begins implicitly.
