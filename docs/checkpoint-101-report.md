# Checkpoint 101 report - Calendar account lifecycle and safe UI

Status: **Approved and complete after human review.**

## Preflight and boundary

Clean synchronized `main`, `HEAD`, and `origin/main` were exactly approved CP100
commit `bb41d3ad223f794c495fbeb4b26fa4263195c8d4`. Exact push CI run
`33554191788` was completed/successful for that SHA. Live database identities
were `127.0.0.1:5433/second_brain` and
`127.0.0.1:5433/second_brain_test`. Alembic current/sole head was
`0015_calendar_persistence` and `alembic check` was clean. Tool Registry was
`agent-tools-v1`; Project export was `second-brain-project-export` version `1`.

CP101 is metadata/configuration only. It adds no Calendar data transport,
event request, refresh, sync, reconciliation, browser, import, scheduling, or
Agent/Automation authority. CP102 was not started.

## Lifecycle, identity, revision, and public API

The stable public application account ID is CP100's `configuration_id`. Create
requires one exact validated CP99 opaque credential reference, its exact safe
account fingerprint, one non-empty maximum-10 exact opaque calendar allowlist,
and one exact Project or explicit unassigned scope. Calendar IDs receive no
email, owner, URL, host, or path interpretation; only documented whitespace,
length, byte, duplicate, and ownership checks apply.

Every authority-relevant edit and lifecycle transition appends a new immutable
`CalendarAccountRevision` and new exact `CalendarIdentity` rows. The current
revision is selected per stable account ID; row locking plus expected-revision
CAS rejects stale concurrent edits. Configuration edits require disabled state.
Historical account, scope, allowlist, sync, and event provenance is never
updated or deleted. Null Project is exactly unassigned and never all Projects.

Create and re-enable inspect the exact CP99 credential envelope and require its
safe fingerprint to equal the Calendar account fingerprint. Missing, malformed,
revoked/unavailable, generation-invalid, unexpected-status, or mismatched
credentials fail closed without refresh or Calendar access. Credential changes
are allowed only on a disabled revision and must prove the same account.

The closed lifecycle is enabled, disabled, or revoked. Disable creates a new
fenced revision and preserves history. Re-enable requires the current revision
and currently valid same-account credential. Explicit revoke first commits a
revoked revision in a short transaction so future capability is fenced, then
invokes CP99's exact-reference provider/local revocation outside database locks.
The response separately projects `provider_revoked` and `local_deleted`,
including partial outcomes; all Calendar history remains.

Public responses contain only application account ID, provider constant, safe
account fingerprint, lifecycle, configuration revision, exact allowlist,
Project/unassigned scope, safe credential status, and timestamps. The revoke
response adds only two booleans. Credential reference/envelope, tokens, raw
`sub`, OAuth fields, email/profile, provider body, and raw errors are absent.

## Settings UI and security

Settings provides labeled flows to load accounts and Projects, configure exact
metadata, edit only disabled accounts, view safe lifecycle/credential state,
disable, re-enable, and explicitly confirm exact credential revocation. It has
no token/email/profile/client-secret field. Credential metadata inputs are
cleared after submission. No localStorage, sessionStorage, IndexedDB, cookie,
query-string, DOM-data-attribute, or frontend logging secret persistence exists.
Hostile calendar IDs render only as escaped inert text and never become links.

Deterministic tests cover create/list/read, Project/unassigned isolation,
allowlist validation and bounds, duplicate/cross-account ownership, hostile
IDs, fingerprint mismatch, missing credentials, lifecycle and immutable
history, stale and concurrent CAS, revocation success/partial projection,
public secret exclusion, browser-storage exclusion, accessibility and explicit
confirmation, and zero Calendar/provider-data or protected-domain activity.

## Migration, dependencies, changed paths, and verification

No migration or dependency changed. Alembic remains
`0015_calendar_persistence`; Tool Registry and Project export identities remain
unchanged.

Exact changed paths:

- `app/api/router.py`
- `app/api/routes/calendar_accounts.py`
- `app/calendar/dependencies.py`
- `app/calendar/service.py`
- `app/main.py`
- `app/schemas/calendar.py`
- `docs/ARCHITECTURE.md`
- `docs/CHECKPOINTS.md`
- `docs/ROADMAP.md`
- `docs/V1_5_CALENDAR_ROADMAP.md`
- `docs/checkpoint-101-report.md`
- `frontend/src/CalendarAccounts.test.tsx`
- `frontend/src/CalendarAccounts.tsx`
- `frontend/src/Settings.tsx`
- `frontend/src/api/client.ts`
- `tests/integration/test_calendar_account_api.py`
- `tests/test_memory_routes.py`
- `tests/test_project_routes.py`

Focused verification passed **19 backend** and **15 frontend** tests, zero
failed and zero skipped. The final authoritative Full run with Windows
Credential Manager access passed **1,278 backend** and **142 frontend** tests,
zero failed and zero skipped. `pip check`, Ruff lint/format, strict mypy over
199 production files, frontend ESLint/typecheck/build, and `git diff --check`
passed. Alembic current and sole head were `0015_calendar_persistence` and
`alembic check` reported no new upgrade operations. Both exact database
identities passed again. Tool Registry remains `agent-tools-v1`; Project export
remains `second-brain-project-export` version `1`.

Automated tests use only synthetic credential references, fingerprints, fake
CP99 credential/OAuth boundaries, and no real Google credential. Zero Calendar
data request occurs. There is no sync, reconciliation, import, scheduling,
Calendar Agent/Automation authority, or CP102 implementation.

CP101 is approved and complete after human review. No push, PR, or
next-checkpoint work was performed. CP102 remains not started.
