# Checkpoint 107 Local V1.5 end-to-end acceptance report

Status: **Approved and complete after human review. Joined Local V1.5
acceptance is green. CP108 has not started.**

## Preflight

Preflight passed on clean synchronized `main` at exact approved CP106 commit
`f5eddec6d5f7794e14ed93a8980cec1844cd7391`; `HEAD`, `main`, and
`origin/main` matched. Exact push CI run `33965297602` for that SHA completed
successfully. Development and test database identities were verified as
`127.0.0.1:5433/second_brain` and
`127.0.0.1:5433/second_brain_test`. Alembic current and sole head were
`0016_calendar_event_observations`; `alembic check` was clean. Tool Registry was
`agent-tools-v1`; Project export was `second-brain-project-export` version `1`.
The CP106 G01-G18 gate remained green with exactly 37 unique mapped nodes.

## Joined acceptance result

`tests/integration/test_v1_5_calendar_acceptance.py` exercises synthetic CP99
PKCE authorization, exact two-scope validation and signed approved-account
identity, then uses the resulting fake credential boundary through the real
Calendar account, manual-refresh and External Context routes. Exact Project and
explicit-unassigned configurations use an exact one-calendar allowlist.

Deterministic fake Calendar pages cover an ordinary timed hostile-text event,
an all-day event, recurring exception with original-start identity, private
event fixed to `Busy`, and special event fixed to `Focus time`. The joined flow
proves initial revisions and exact `calendar-observations-v1` evidence; equal
replay reuses five content revisions while adding five fresh observations;
changed ordinary content appends application revision 2; a later complete
covering omission makes the timed recurring occurrence effectively `stale`;
and later positive evidence restores `current`. Absence creates no persisted
`stale`, `cancelled`, or `deleted` revision.

Project A can browse its own minimized list/detail projection. Project B,
unassigned scope, forged detail IDs and forged cursors cannot cross that scope.
The separate explicit-unassigned journey remains invisible to Project scopes.
Browsing is PostgreSQL-only and adds no provider call.

## Privacy, failure, recovery, and omissions

Excluded description/location/attendee/organizer/conference/attachment/
reminder/extended-property and identity-claim canaries do not occur in the
approved persistence schema, public Calendar API projection, tested UI,
Project export, Source/Memory state, or Agent/Automation-visible state. No
provider-content hyperlink is exposed. HTML, Markdown, script-like and bidi
text remains inert text in React; disallowed control text fails the refresh
closed without changing prior current evidence.

A failed/incomplete refresh carries no evidence version and infers no stale.
The existing G01-G18 focused corpus additionally proves unversioned/incomplete
manifest rejection, atomic page faults, idempotent replay, stale worker and
configuration/scope fencing, revoke races, cross-lineage rejection, bounded
retry and safe recovery. The joined restart creates a fresh application
instance, reads the committed safe state, and rejects a stale revision refresh
before credential or Calendar transport access. Disable/revoke preserves all
historical event revisions and observations; revoked state prevents refresh.

Executable omission gates confirm no Calendar import route/action/path, no
Calendar-to-Source/SourceDocument/chunk path, no Calendar scheduling or
background/API-startup refresh, no scheduler-triggered `AgentRun`, no Agent or
Automation Calendar access, no Calendar write, no generic Google/provider
executor, and no OAuth scope widening. CP102 manual refresh remains the sole
Calendar request trigger. Existing GitHub External Context behavior remains in
the focused and Full frontend suites.

## Verification

Focused Calendar/OAuth/security acceptance passed **104 backend tests** and
**15 frontend tests**, zero failed and zero skipped.

The first sandbox-context Full attempt passed database identities, dependency
integrity, Ruff lint/format, strict mypy and all Calendar acceptance, then
reported **1,340 passed, 1 failed, 0 skipped**. The sole failure was the known
Windows Credential Manager host-context availability check reporting
`credential_store_locked`; it was not a Calendar production or joined-
acceptance defect. No production code was changed in response.

A fresh authoritative normal-Windows-host `scripts/verify.ps1 -Mode Full` run
passed dependency integrity, Ruff lint/format over 478 files, strict mypy over
203 production files, **1,341 backend tests**, Alembic current/head/check,
frontend ESLint/typecheck, **148 frontend tests**, the Vite production build,
and `git diff --check`, all with zero skips. No destructive database lifecycle
was needed.

No production defect was found. There is no migration or dependency change.
There was zero real credential enumeration, zero real Google/Calendar request,
and zero Calendar write. All OAuth, credential, network and provider behavior
was deterministic and fake. G01-G18 remains green with 37 unique nodes. Tool
Registry remains `agent-tools-v1`; Project export remains
`second-brain-project-export` version `1`. CP108 was not started.

## Exact changed paths

- `docs/ARCHITECTURE.md`
- `docs/CHECKPOINTS.md`
- `docs/ROADMAP.md`
- `docs/V1_5_CALENDAR_ROADMAP.md`
- `docs/V1_5_CALENDAR_THREAT_MODEL.md`
- `docs/checkpoint-107-report.md`
- `frontend/src/CalendarAccounts.test.tsx`
- `frontend/src/ExternalContext.test.tsx`
- `tests/integration/test_v1_5_calendar_acceptance.py`

All nine approved CP107 paths are committed together by the final lifecycle
audit. Nothing is pushed by that audit.
