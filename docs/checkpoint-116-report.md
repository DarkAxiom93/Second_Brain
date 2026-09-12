# Checkpoint 116 report - Local V1.7 Capture & Triage architecture

Status: **Proposed for human review; implementation has not begun.**

## Preflight and source of truth

- Baseline `main` and local HEAD were exact commit
  `131ec7db31ff0d6d88a81b2fba57117df46d1ca9`; the worktree was clean before
  CP116 edits.
- Local V1.6 remains current published tag `v1.6.0` from exact release commit
  `64c8215d142ba66f7788d2a71f3debf291cd9862`.
- The documented current Alembic head remains
  `0016_calendar_event_observations`; planned Capture persistence begins only in
  CP117 with a new migration after that head.
- `agent-tools-v1`, provider/Agent/Automation authority, OAuth scopes, and
  `second-brain-project-export` version `1` remain unchanged.

## Architecture decisions

Local V1.7 is a durable Capture & Triage Inbox for bounded plain-text notes.
`CaptureItem` is separate from Source, Memory, Notification, Agent, Automation,
and Context Hub state. It has immutable UUID identity, exact Project or explicit
unassigned ownership, pending/processed/discarded state, timestamps, monotonic
revision, private idempotency state, and exact resulting Source provenance.

`id` and `created_at` are immutable. `updated_at` changes on every successful
CaptureItem mutation. `processed_at` is null before processing, is written
exactly once by successful conversion, and never changes because processed is
terminal.

The closed transitions are pending-to-discarded, discarded-to-pending, and
pending-to-processed only through successful Source conversion. Pending alone
may be edited/reassigned; processed is terminal; no physical delete/purge exists.
All non-create operations require one explicit exact scope. Quick Capture alone
defaults an omitted scope to unassigned. Conservative exact bounds are 8,000
content characters/32,000 UTF-8 bytes, 200 query characters/800 bytes, page
size 1-50 (default 25), and 2,048 cursor characters.

Creation uses a required hashed request-bound idempotency key. Mutations use
row locking plus revision compare-and-set. Query/list uses deterministic
PostgreSQL-only lexical or browse ordering and request-bound keyset pagination;
there is no semantic search or public/universal relevance score.

Conversion reuses existing Source creation and normalized text document/chunk
repository primitives inside one route-owned transaction. It locks/revalidates
the CaptureItem, creates at most one Source, records provenance and processed
state atomically, rolls back everything on failure, and returns the recorded
Source on replay. No Memory/proposal/embedding/provider action occurs.

A processed CaptureItem's exact scope becomes immutable and its unique reverse
`resulting_source_id` relationship is the authoritative scope binding for the
capture-bound Source. Sources with no binding remain legacy/unbound. A common
resolver detects the binding across every Source/document/chunk read and
downstream ingestion/link/proposal/Tool/Hub/export path, requires exactly one
requested scope for bound Sources, and fails closed unless it matches. Existing
unscoped Source routes omit or reject bound Sources; the Inbox uses the scoped
Capture Source resolver rather than `/sources/{id}`. Conversion freezes the
scope inside its row-locked transaction, preventing reassignment/conversion
scope splits.

The current code has no public Source deletion route, but ORM/database Source
deletion cascades SourceDocument/chunks/extraction and Memory association rows.
The planned `resulting_source_id` is therefore unique and `ON DELETE RESTRICT`;
the planned Project FK is also restrictive so deletion cannot silently launder
assigned ownership into unassigned. Capture has no delete route.

Capture text remains inert unreviewed input. It is excluded from Memory search,
Answers, Context Hub, Agents, Agent Tools, Automations, Daily Brief, Project
Watch, Curator, prompts, embeddings, provider/network reads, and automatic
knowledge creation. React text rendering plus current bidi/overflow rules form
the UI direction. Any shortcut is application-local and disabled in editable
controls; there is no global listener.

CaptureItems remain excluded from Project export v1/import. Full PostgreSQL
backup/recovery naturally includes them, with explicit sensitivity, retention,
copying, and disposal implications.

## Threat model and checkpoint sequence

The dedicated model covers CAP01-CAP18 one-to-one: cross-scope leakage; forged
IDs; creation replay; invalid transitions; partial and concurrent conversion;
lost updates; hostile instructions and active/spoofing text; privacy; resource
exhaustion; hidden model/provider/network use; Agent/Automation/Tool/Hub leakage;
export and backup exposure; reassignment races; destructive loss; and exact
Source provenance/lifecycle. Every entry states an invariant/control and a
planned deterministic evaluation. CP121 requires unique no-skip executable
mapping; CP122 proves the joined boundary.

CAP11 now uses exact deterministic resource controls: existing byte/character/
page/cursor limits, maximum 50 returned items, closed indexed query shapes,
keyset-only pagination, and no offset/count/facet/semantic query or unbounded
application iteration. Normal successful-path SQL statement ceilings are:
create/replay 3, query 2, detail 2, edit 3, reassign 4, discard/restore 3,
convert/replay 10, and processed Source resolver 3. CAP11 tests every boundary
and +1 rejection, instruments those ceilings, verifies required indexes/query
shapes, and proves forbidden/unbounded operations absent. It makes no false
wall-clock or examined-row guarantee.

The proposed review sequence is CP116 architecture/threat model, CP117 domain
persistence, CP118 Inbox API/state machine, CP119 atomic conversion, CP120
frontend, CP121 security gate, CP122 joined acceptance, and CP123 release
hardening. Publication remains a separate post-review action.

## Verification

Post-remediation focused tests: **67 passed**, zero failures, one existing Starlette/httpx
deprecation warning. The set covered Project export identity/contents, Source
routes, text-ingestion bounds, and persistence relationship behavior.
`git diff --check` passed.

Post-remediation Full verification ultimately passed on the unchanged final
documentation: **1,404 backend tests** and **157 frontend tests across 16
files**, zero skipped. `pip check`, Ruff lint, Ruff format over 503 files,
strict mypy over 208 production files, frontend ESLint/TypeScript, the 89-module
Vite production build, Alembic current/heads/check, and `git diff --check` all
passed. Alembic remained exactly `0016_calendar_event_observations` and reported
no new upgrade operations.

Two preceding post-remediation attempts exposed an existing Context Hub fixture
timing race and were not hidden: the first ended with **1,401 passed and 3
failed**; a clean unchanged rerun ended with **1,403 passed and 1 failed**, zero
skipped. The remaining failure assigned a Python `now` 876 microseconds earlier
than PostgreSQL's generated `created_at` to `started_at`, violating the existing
`ck_calendar_sync_started` constraint. No out-of-scope production/test edit was
made. The next unchanged Full run passed every backend and frontend gate above.

The first sandboxed Full attempt had **1,403 passed and 1 failed**, solely
because Windows Credential Manager reported `credential_store_locked`; it was
not treated as product evidence. The first authorized attempt passed that
credential test but encountered broad test-database interference (10 failures
and 27 errors, including tables disappearing and unrelated rows changing).
After confirming no other pytest/verifier process remained, the identical clean
authorized rerun passed in full. These environmental attempts were not hidden
or addressed through product/database changes.

## Exact changed paths

- `docs/ARCHITECTURE.md`
- `docs/CHECKPOINTS.md`
- `docs/ROADMAP.md`
- `docs/V1_7_CAPTURE_TRIAGE_ROADMAP.md`
- `docs/V1_7_CAPTURE_TRIAGE_THREAT_MODEL.md`
- `docs/checkpoint-116-report.md`

## Pre-commit audit remediation and scope confirmation

The read-only pre-commit audit found three documentation blockers: capture-
created Source scope was not enforceably bound, timestamp mutability was
contradictory, and CAP11 claimed an unspecified SQL-work budget. Before commit,
this remediation defined the immutable processed-Capture reverse scope binding
and common guarded Source resolver, corrected exact timestamp semantics, and
replaced the unsupported resource claim with concrete query-shape, index,
cardinality, and per-endpoint SQL-statement ceilings. CAP01/CAP18 now explicitly
test legacy Source/downstream bypass attempts. The original draft's no-blocker
claim is withdrawn; these three findings are resolved in the current draft.

No remaining architecture blocker or open question is identified. Exact safe
public error strings and authenticated cursor encoding keys remain CP118 design
details within this boundary; they may not widen scope or authority.

CP116 changed documentation only. No production code, tests, migration, schema,
dependency, lockfile, runtime behavior, Tool Registry, OAuth scope, export
version, provider authority, Agent authority, or Automation authority changed.
No V1.7 implementation began. CP117 was not started. Changes remain unstaged
and uncommitted.
