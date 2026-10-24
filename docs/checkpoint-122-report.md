# Checkpoint 122 report - joined Capture acceptance

Status: **Implemented and fully verified; pending human review.** CP123 has not
started.

## Baseline and database identity

CP122 began from clean synchronized `main` at
`5e84b7b7ee05a3f0e83e98e48e6112c86a91c91f`; `origin/main` was the same commit
and exact push CI run 94 was successful. The sole Alembic head was and remains
`0017_capture_items`.

The focused and Full gates used the configured local test connection at
`127.0.0.1:5433/second_brain_test`; credentials are intentionally omitted.
Before migration or cleanup, the CP122 fixture validates the parsed database
name and executes `SELECT current_database()`; both were exactly
`second_brain_test`. Full verification also printed:
`TEST_DATABASE_URL: host=127.0.0.1 port=5433 database=second_brain_test
verified`.

## Cleanup-safety remediation

The final read-only audit exposed one CP122 blocker: the joined backend fixture
used an unsafe unscoped `delete(CaptureItem)` before and after its acceptance
journey. Although the live test-database identity was verified, that deletion
could remove unrelated Capture fixtures from `second_brain_test`.

The final acceptance gate then found a second cleanup blocker: the first
ownership remediation resolved fallback rows with the global reserved prefix,
so cleanup for one run could select a concurrent or retained different-run
namespace. The accepted remediation scopes every fallback lookup to the exact
current marker, including its per-run UUID, and performs the live database
identity check inside the cleanup helper before opening its delete transaction.

The fixture now assigns every CP122 Project, Capture, and ordinary legacy
Source a reserved `__cp122_joined_capture_acceptance_owned_v1__:` marker plus a
per-run UUID, while recording each returned Project, Capture, resulting Source,
extraction run, proposal, and promoted Memory UUID immediately as the journey
advances. Before each cleanup transaction, the cleanup helper itself verifies
the live database is exactly `second_brain_test`. It uses only the current run's
complete reserved marker, including its UUID, to resolve interrupted-run
Project, Capture, and legacy Source UUIDs, then follows those exact Source IDs
to exact document, extraction-run, proposal, and promoted-Memory UUIDs.

Deletion is limited to those resolved UUID sets, in FK-safe order: owned
Memories, proposals, extraction runs, Captures, Sources (whose owned document
and chunk graph uses existing cascades), and Projects. Every DELETE has an
exact primary-key predicate; there is no unscoped delete, TRUNCATE, reset,
table-wide purge, development-database access, or volume operation. The
`try/finally` fixture and persistent reserved marker preserve cleanup safety
after in-process failures at any point after a marked row is committed. A
terminated process is not silently swept by a later run with a different UUID;
such cross-run deletion would violate namespace isolation. Production behavior
was not changed.

The subsequent cleanup-evidence audit required executable proof beyond the
bounded implementation. Ten dedicated PostgreSQL cases now provide it. Six
deterministic interruption cases raise immediately after Project, CaptureItem,
conversion/resulting Source, MemoryExtractionRun, MemoryProposal, and promoted
Memory creation, then exercise the same cleanup scope used by the acceptance
fixture. Four cleanup-delete fault cases inject at the knowledge, CaptureItem,
Source, and Project deletion boundaries. If acceptance and cleanup both fail,
an exception group preserves both errors rather than hiding the original.

## Joined backend and restart evidence

`tests/integration/test_v1_7_capture_acceptance.py` drives public FastAPI routes,
real services/repositories, and PostgreSQL. It creates Project A, Project B,
and explicit unassigned canaries. Omitted creation becomes unassigned, assigned
creation retains its exact Project, same-key replay returns the same row, and
scope queries remain isolated.

The route journey covers browse, detail, submitted PostgreSQL lexical search,
a forced one-item keyset page boundary, edit, reassignment, discard, restore,
and one stale-revision conflict. The conflict returns the authoritative
projection and a follow-up detail proves committed state was preserved.

Conversion changes the edited Project A Capture from revision 2 to processed
revision 3, populates `processed_at` and `resulting_source_id`, and persists one
exact Source/document/chunk graph whose extracted text and 2,000/200 chunks
match the Capture. Conversion and replay make zero extraction-provider calls
and create no Memory, proposal, embedding, Agent Run, or Automation. Replay
returns the identical Capture/Source projection and graph.

The public processed-Capture resolver succeeds only with Project A and rejects
Project B. The legacy unscoped Source API rejects the bound Source, while
Source/document/chunk guards preserve the frozen Project A scope. A separately
created ordinary unbound Source retains normal legacy get/document behavior.

After the first client closes, a fresh application and client recover the exact
pending, discarded, and processed states and revisions, exact scopes, stable
Source binding, query/detail projections, and scoped Source resolver result.

## Explicit reviewed knowledge continuation

Before explicit continuation, protected-domain snapshots are unchanged. The
existing public `POST /sources/{id}/memory-proposals` route consumes the
capture-bound Source with its exact Project scope through a bounded fake
provider. The existing proposal list, explicit approve route, and explicit
promote route then create one Project A Memory. It appears only after approval
and promotion, has no embedding, and its `MemorySource` provenance points to
the exact converted Source.

## Frontend and boundary evidence

The existing `frontend/src/Capture.test.tsx` suite now includes one coherent
Quick Capture, Inbox, conflict, lifecycle, conversion, and scoped-reopen
journey. It proves persistent `+ Capture`, visible Unassigned default,
successful submission and focus restoration, exact scope/state selection,
submitted lexical search, opaque pagination, detail, edit/conflict deliberate
retry, reassignment, discard/restore, conversion, and resolver-only Source
reopen. Hostile script/Markdown/javascript-link/bidi/long text remains inert
React text with no content-derived element or navigation.

The joined case and existing focused assertions prove no Capture content,
scope, cursor, idempotency material, or provenance enters browser storage; no
polling or hidden work exists; no unscoped Source request is made; accessibility
and focus assertions remain intact; and no timeout was increased.

CP121 runtime tripwires and protected snapshots prove zero network/provider/
model/embedding/credential calls during Capture/Inbox operations, zero
automatic Agent/Automation/Tool/Context Hub/Brief/Watch/Curator authority, and
zero unexpected Memory/proposal/embedding delta before explicit review.
Project export remains `second-brain-project-export` version `1`, excludes
Capture rows and bindings, and the Tool Registry remains `agent-tools-v1` with
seven definitions.

## Verification

- Focused CP122 backend/PostgreSQL acceptance: **1 passed** in each of four
  consecutive runs, zero skipped, exercising setup/finalizer cleanup safety.
- Focused cleanup evidence: **10 passed**, covering six creation-stage
  interruptions and four atomic cleanup-delete rollback/retry cases. The whole
  CP122 backend file passed **11/11**.
- Focused joined Capture frontend file: **24 passed**, zero skipped.
- Restart and reviewed-pipeline results: passed inside the focused backend node.
- CP121 manifest/meta gate: **12 passed**.
- CP121 marked regression: **57 passed** before the sandbox-only Docker denial;
  the protected backup/restore node subsequently passed inside the elevated
  complete backend run before its two unrelated Calendar failures.
- Frontend Full verification: ESLint, TypeScript, production build, and
  **181/181 tests** passed across 17 files.
- The initial Full run exposed two pre-existing date-sensitive V1.5 Calendar
  fixtures. Production Calendar behavior was not changed. Each affected module
  now captures one UTC anchor at import, derives event times inside the rolling
  refresh window, and converts timed events through `Asia/Jerusalem` so the
  correct DST offset is preserved. Provider event and recurring-exception
  identities remain stable across refreshes; changed revisions and every
  original current/stale/current assertion remain intact.
- The two corrected targets passed together **2/2** in three consecutive runs.
  Their complete files passed **16/16** and **2/2**, respectively.
- Final authoritative Full backend verification: **1,545 passed**, zero failed,
  zero skipped.
- Alembic current and sole head: `0017_capture_items`; Alembic check reports
  `No new upgrade operations detected.`
- Pip check, Ruff lint/format, and strict mypy over 217 production files passed
  before the complete backend run.

No production file changed. No schema, migration, dependency, API contract, or
authority changed. Nothing was staged, committed, pushed, or opened as a pull
request. CP123 has not started.

## Cleanup fault and isolation evidence

The six stage tests interrupt owned setup after Project, CaptureItem,
conversion/resulting Source, extraction-run, proposal, and Memory/promotion
creation. Each exact-marker finalizer leaves zero owned Capture, Project, and
legacy Source residue. IDs are recorded after every flush, including the
extraction run, and fallback matching escapes SQL wildcard characters. A
converted fallback Source is accepted only when its exact UUID, `capture` type,
and generated `Capture {capture_id}` name all agree.

Every scenario preserves an exact all-column snapshot of a different-run
sentinel graph spanning Project, CaptureItem, Source, SourceDocument,
SourceChunk, MemoryExtractionRun, MemoryProposal, Memory, and MemorySource
linkage. The four delete-fault cases prove the cleanup transaction rolls back
at the knowledge, CaptureItem, Source, and Project boundaries, propagates the
cleanup error without losing the original acceptance error, runs no emergency
fallback, succeeds on an exact retry, and remains idempotent on a repeated
cleanup. Sentinel rows are removed only after preservation assertions, through
their separately recorded exact IDs.

## Exact changed paths

- `docs/ARCHITECTURE.md`
- `docs/CHECKPOINTS.md`
- `docs/ROADMAP.md`
- `docs/V1_7_CAPTURE_TRIAGE_ROADMAP.md`
- `docs/checkpoint-122-report.md`
- `frontend/src/Capture.test.tsx`
- `pyproject.toml`
- `tests/integration/conftest.py`
- `tests/integration/test_calendar_account_api.py`
- `tests/integration/test_v1_5_calendar_acceptance.py`
- `tests/integration/test_v1_7_capture_acceptance.py`
