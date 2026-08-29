# Checkpoint 94 report - optional connector refresh scheduling

Status: **Approved and complete after human review.**

## Architecture and persistence

Checkpoint 94 adds the approved `0014_connector_refresh_schedules` migration
with exactly three connector-owned tables. `connector_refresh_schedules` owns
one disabled-by-default typed schedule per ConnectorAccount, fences every
mutation with `revision`, and increments `schedule_revision` whenever the
canonical definition changes. `connector_refresh_occurrences` captures exact
account and schedule revisions, the canonical UTC/local slot, an opaque lease
owner and generation, safe status codes, and at most one linked
ConnectorSyncRun. `connector_refresh_notifications` is occurrence/schedule
owned, deduplicated, and persists only closed event/severity/status codes.

The V1.3 `Automation`, `AutomationOccurrence`, and Automation notification
models, constraints, repositories, services, and routes were not weakened or
reused. Connector scheduling has no Agent identity or AgentRun foreign key.

## Lifecycle, identity, and missed work

Schedules transition only `draft -> enabled`, `enabled -> paused`, `paused ->
enabled`, or `draft|enabled|paused -> cancelled`. Cancelled is terminal. Enable
and resume recalculate the next slot through the existing deterministic
one-time/daily/weekly IANA schedule calculator and its gap/fold policy.

Occurrence identity is the bounded domain-separated value
`connector-refresh-occurrence:v1:{schedule UUID}:{schedule revision}:{canonical
UTC instant}` and is protected by both key and `(schedule, revision, instant)`
uniqueness. ConnectorSyncRun receives a separate safe
`connector_schedule_{sha256}` trigger identity and `trigger_kind=scheduled`.

Missed work uses a seven-day maximum lookback and never replays all slots.
`skip` records one canonical missed occurrence without provider access;
`run_once` materializes at most one catch-up occurrence. One-time schedules
have no future slot after materialization.

## Coordinator, restart safety, and authority

The explicit operator-started scheduler ticks Agent Automation first and then
the independently owned connector coordinator. Materialization, claim,
ConnectorSyncRun creation/linkage, and finalization use separate short
transactions. CredentialStore and GitHub latency occur only after claim and
link commits and outside database locks.

Claims require exact owner UUID and generation. Expired unlinked or linked
claims increment the generation, fencing stale owners. A linked occurrence
always reuses its exact ConnectorSyncRun: terminal durable state is finalized;
claimed/running durable state resumes through the existing CP91 refresh
implementation. Unique linkage prevents a replacement run after ambiguous
local outcomes.

The shared CP91 claim boundary retains enabled account, exact account revision,
captured Project/unassigned scope, repository allowlist, closed policy
fingerprint, one-active-sync/account, global capacity, and safe trigger fields.
The refresh implementation and GitHub transport/request inventory are not
duplicated. Manual refresh continues to call the original `claim` wrapper with
`trigger_kind=manual` and `operator_manual_refresh`.

Failures map only the exact linked sync to succeeded, incomplete, or failed
occurrence state and preserve only safe disposition/error codes. Notifications
render from closed codes and cannot contain credentials, references, provider
payloads, repository/item content, URLs, exception text, or model content.

## API, UI, and stable boundaries

Closed revision-aware APIs create/read/update schedules, enable/pause/resume/
cancel them, and return bounded safe occurrence/notification history. External
Context exposes disabled-draft creation and explicit lifecycle controls with
the warning: “Scheduled refresh reads GitHub using the existing connector
permissions. It does not run an Agent and does not import content.” There is no
polling or browser credential persistence.

Project export remains `second-brain-project-export` version `1` and excludes
all connector runtime tables. Tool Registry remains `agent-tools-v1`.
Scheduling creates no AgentRun, ExternalItemImport, Source, SourceDocument,
Memory, MemoryProposal, or ApprovalRequest and adds no external write,
scheduled import, automatic proposal/Memory creation, or Checkpoint 95 work.

## Verification

Focused tests passed 19 connector refresh/manual-refresh backend tests, 23
migration/export/operations tests, and 6 frontend tests, zero skips. The first
sandboxed Full run exposed four expected schema/route inventory assertions and
the sandboxed Windows credential-store boundary; the inventories were updated.
The authoritative host-context Full run then passed 1,177 backend tests and 135
frontend tests in 14 files, zero skips, plus pip check, Ruff lint/format, strict
mypy over 182 production files, database identity checks, Alembic current/head/
check, ESLint, TypeScript, production build, and `git diff --check`.

Alembic current and sole head are `0014_connector_refresh_schedules`; check
reports no pending operations. All connector scheduling tests use database
state and fake/local boundaries; no real GitHub request is made by CP94 tests.
