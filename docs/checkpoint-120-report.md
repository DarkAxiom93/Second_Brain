# Checkpoint 120 report

Status: **Implemented; awaiting human review.** Baseline:
`c954868179d651a73acd1d279569e77255262a19`.

## Delivered frontend contract

The shell now exposes persistent `+ Capture` and document-local `Ctrl+Shift+C`.
The shortcut ignores composing input and editable targets or descendants. The
labelled modal starts at visible explicit Unassigned scope, loads the existing
Project list, focuses the text field, traps focus, closes on Escape, restores
launcher focus, and announces safe states. A `crypto.randomUUID()` idempotency
key exists only in a component ref for one logical content/scope pair. Unchanged
retry reuses it; changing content or scope creates a new key. Success clears and
closes the draft and sends one in-memory, content-free refresh notification to a
mounted matching Inbox.

`/inbox` begins with exact Unassigned, `pending`, and a 25-item bounded browse.
Its selector contains only Unassigned and one exact Project. Pending, discarded,
and processed are distinct views. Search changes make no requests until submit;
Clear returns to browse. The applied request and opaque next/previous cursor
stack remain in memory and never enter DOM text, URLs, logs, or browser storage.

Selection performs exact-scope detail resolution. Pending items expose edit,
exact-scope reassignment, discard, and atomic conversion; discarded items expose
restore; processed items expose only scoped Source reopen. Every mutation uses
the observed positive revision and current exact scope. Reassignment removes the
item from its old-scope view. Conversion uses its returned Capture and Source
projections without another ingestion route.

## Safety and accessibility evidence

Capture projections and pages use closed exact-key validators. A valid revision
409 alone becomes a dedicated typed conflict containing the authoritative safe
Capture projection. The UI replaces stale data, announces that the item changed
and refreshed, and requires deliberate retry. Malformed conflicts and other
failures remain generic and content-free.

Content is React text with `white-space: pre-wrap`, overflow containment, word
breaking, and `unicode-bidi: isolate`; there is no Markdown, HTML interpretation,
content-derived link, or `dangerouslySetInnerHTML`. Tests cover markup-shaped
text, bidi, multiline/long text, modal focus/Escape/return, keyboard controls,
labels/live regions, Unassigned default, exact Project selection, submitted
search, state/scope/cursor binding, edit conflict, reassign/discard/restore/
convert, and browser-persistence absence.

Processed Source reopen always calls `POST /capture-items/{id}/source` with the
current exact Capture scope first. Because the existing Source screen issues an
unscoped read, the resolver-authorized projection remains inside Inbox. Tests
prove no direct `/sources/{sourceId}` request occurs.

## Explicit omissions

There is no migration, backend route or authority change, provider/model or
embedding behavior, Capture export/import, Context Hub Capture family, Agent,
Tool, Automation, background work, polling, service worker, browser persistence,
file/rich capture, global hotkey, or CP121 security-gate work. Tool Registry
remains `agent-tools-v1`; export remains `second-brain-project-export` version
`1`; the sole Alembic head remains `0017_capture_items`.

## Files changed

- `docs/ARCHITECTURE.md`
- `docs/checkpoint-120-report.md`
- `frontend/src/App.tsx`
- `frontend/src/Capture.test.tsx`
- `frontend/src/Capture.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/styles.css`

## Verification

The read-only final audit verdict was **FAIL — CP120 requires remediation**.
Remediation kept the backend and authority boundary unchanged and corrected each
blocker:

- successful Quick Capture now closes immediately while a shell-owned live
  region retains the content-free `Capture saved.` announcement;
- the client now validates scalar/UTF-8 content bounds, non-whitespace content,
  valid scalar values, UUIDs, timestamps, positive revision, closed state, and
  the exact processed/provenance invariant before any Capture projection can
  become authoritative;
- only an exact revision-conflict envelope containing that strict projection
  creates `CaptureRevisionConflictError`; malformed conflict variants remain
  generic safe failures;
- filter/search changes synchronously remove pagination controls, abort the
  prior request, reset cursor history, and use a monotonic generation fence so
  delayed responses cannot overwrite the current exact view; and
- focused evidence now covers both focus-wrap directions, Escape/focus return,
  input/textarea/select/contenteditable/editable-descendant/IME shortcut
  suppression, unchanged/content-only/scope-only/success-reset idempotency,
  persistent success, submitted search and Clear, every cursor invalidation,
  delayed-response fencing, successful edit and all other actions, deliberate
  conflict retry with the refreshed revision, malformed conflicts, processed
  action closure, hostile content, scoped Source reopen, browser-storage
  absence, and polling-interval absence.

The second read-only remediation audit also returned **FAIL — CP120 still
requires remediation** for two remaining boundaries. The client validator now
rejects NUL and every carriage return, including CRLF, rather than silently
normalizing malformed server projections. Isolated conflict cases prove NUL,
lone-CR, and CRLF projections all produce generic `SafeApiError`; UI evidence
also proves none replaces the visible authoritative content or revision. The
successful Quick Capture path now explicitly proves that, after the dialog
closes and its persistent success announcement remains, focus returns to the
original `+ Capture` trigger.

Final post-remediation focused CP120 Vitest: **22 passed, 0 failed, 0 skipped**.
Frontend ESLint, TypeScript checking, and the production Vite build passed.
At that remediation stage, ordinary-user Full verification was still pending;
no earlier Full result was treated as the final remediation gate.

The subsequent ordinary-user Full run passed **1,504 backend tests**, with zero
failures and zero skips. Alembic current and sole head were
`0017_capture_items`, and Alembic check reported no new upgrade operations. Its
first frontend attempt passed **178 tests** and failed one existing Context Hub
test because that test used a global `getByRole("status")` after CP120 added the
intentional persistent shell-level Quick Capture live region alongside Context
Hub's intentional page-level status. Diagnosis found no production accessibility
defect or duplicate Context Hub status. The correction is test-only and scopes
the assertion semantically to the main page region while retaining its no-read,
validation-message, and unchanged-fetch-count proofs. The final ordinary-user
Full rerun was still pending when that test-only correction was recorded.

The pre-remediation Full run verified the parsed and live development/test identities
as `second_brain` and `second_brain_test`, then passed pip check, Ruff lint,
Ruff format, and mypy. The backend collected **1,504 tests**: **1,503 passed,
1 failed, 0 skipped**. The only failure was the pre-existing environment-bound
Windows Credential Manager round-trip because the current session returned
`credential_store_locked`; an immediate isolated rerun reproduced that same
condition. Every Capture and database test passed. Because Full correctly stops
at a backend failure, its later stages did not execute in that invocation.

The pre-remediation frontend verification was run independently and passed 164
tests. Independent post-run Alembic evidence reports current and sole head
`0017_capture_items` and `No new upgrade operations detected.` `git diff
--check` passes. Final `git status --short` contains only the seven paths listed
above, all unstaged; nothing was committed or pushed.

## Final ordinary-user verification

After every CP120 remediation, the final ordinary-user Full verification
completed successfully. Pip check, Ruff lint, Ruff format check, and mypy all
passed. The complete backend suite passed **1,504 tests, 0 failed, 0 skipped**.
Alembic current and sole head were both `0017_capture_items`, and Alembic check
reported no new upgrade operations.

Frontend verification passed ESLint, TypeScript checking, the production Vite
build, and **179 tests across 17 files**. The final focused CP120 suite passed
**22 tests, 0 failed, 0 skipped**. `git diff --check` passed, and Full
verification completed successfully.

The immutable Tool Registry remains `agent-tools-v1`. Project export remains
`second-brain-project-export` version `1`. CP120 changed no backend production
code, migration, schema, or dependency; no CP121 work began. All CP120 paths
remain unstaged and uncommitted for human review.
