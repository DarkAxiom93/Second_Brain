# Second Brain Local V1.3 candidate release notes

Release candidate: `v1.3.0`

Candidate title: **Second Brain Local V1.3**

Status: **Release hardening approved and complete; not published.**

Local V1.3 adds durable local Automations and scheduled fixed Agents without
changing the trusted single-maintainer, loopback-only deployment boundary.
Published `v1.2.1` remains the recovery release until separate publication
approval.

## Major capabilities

- Typed Automation create/read/list/edit, revision-aware lifecycle, and bounded
  one-time, daily, and weekly schedules with deterministic UTC/IANA-timezone and
  DST behavior.
- Durable occurrence materialization, bounded deterministic claiming,
  generation-fenced leases, safe `skip`/`run_once` missed-run handling, capped
  setup retries, capacity deferral, and exact linked-Run reuse.
- `create_only` as the default execution mode and explicit opt-in
  `automatic_read_only` for the two fixed Automation Agents only.
- A local, content-free notification inbox plus bounded occurrence history and
  linked Agent Run navigation.
- Accessible Automations and Notifications UI with explicit refresh and no
  polling or browser persistence.

## Daily Brief and Project Watch

Daily Brief is exactly `("daily_brief", "1")`. It summarizes bounded reviewed
local Memories and closed local application-event evidence for one exact
Project or explicit unassigned scope. Its fixed goal excludes editable labels,
and its citations are application-owned and version-checked.

Project Watch is exactly `("project_watch", "1")`. It requires one exact
non-null Project and reports bounded cited changes, or
`no_meaningful_change`, over an application-derived `(lower, upper]` window.
Only a prior successful same-scope occurrence with a completed linked Run and
persisted result advances the watermark.

Research and Memory Curator remain unschedulable. Public manual/free-form Daily
Brief and Project Watch Runs remain rejected.

## Security and recovery guarantees

- One canonical occurrence creates or reuses at most one Agent Run; linked Runs
  are never replaced.
- Stale lease owners are fenced by opaque owner and generation identity.
- No database lock or transaction spans provider or Tool latency.
- Automation configuration cannot grant Tools, authority, arbitrary prompts,
  external access, or writes.
- Automatic execution is restricted to exact fixed code-owned read definitions
  and the existing five scoped application read Tools.
- Completion notifications contain safe code-owned status and links, never
  retrieved content, prompts, provider/Tool payloads, secrets, or private
  scheduler identities.
- Stopping the scheduler is safe. Committed Automations, occurrences, Runs, and
  notifications remain durable; restart derives work only from committed
  PostgreSQL state, reclaims only expired leases, and has no replay-all path.
- The scheduler is a dedicated operator-started process and is not embedded in
  Uvicorn startup.

## Upgrade and stable identities

The sole Alembic head and required current revision are
`0011_automation_persistence`; `alembic check` must report no pending upgrade
operations. Never downgrade the development database.

The Tool Registry remains `agent-tools-v1`. Project export remains
`second-brain-project-export` version `1`. Revision-`0011` exports exclude all
Automation definitions, occurrences, and notifications; Agent Runs, Steps,
Tool invocations, and events; Approval Requests; provider/Tool payloads;
prompts, secrets, and private runtime state. Validation/import remains
validation-first, conflict-free only, and fail-closed.

## Known limitations and deferred scope

V1.3 does not include authentication or multi-user isolation; remote/cloud
operation; connector integrations; Gmail, Calendar, or GitHub automation;
arbitrary external/network research; arbitrary user-defined Agent prompts or
Tools; shell, Python, SQL, filesystem, or browser execution; automatic writes
to reviewed knowledge; Memory Curator scheduling; proposal execution;
automatic Approval; external notification delivery including webhook, email,
push, or OS notifications; automatic history deletion; import merge,
overwrite, or remap; encrypted export; or credential storage.

Project bundles remain private and unencrypted. Live provider-backed success
requires local credentials. Provider quality remains probabilistic within
strict schema, evidence, scope, and authority validation. Scheduler wake timing,
timezone-library changes beyond pinned fixtures, and host/PostgreSQL failures
outside deterministic fault hooks remain residual local operational risks.

## Recovery guidance

Stop temporary frontend and API processes before database maintenance. Use
`docker compose stop db` through `scripts/dev-down.ps1`; preserve the PostgreSQL
container and `second-brain_postgres_data` volume. Create a PostgreSQL custom-
format backup, verify it with `pg_restore --list`, and never restore over or
downgrade the development database. Any restore requires a separate,
identity-checked target and explicit approval. See
[LOCAL_V1_RUNBOOK.md](LOCAL_V1_RUNBOOK.md).

## Verification

Checkpoint 84 maps all A01-A18 Automation threats to deterministic tests.
Checkpoint 85 proves Daily Brief and Project Watch through the joined V1.3 E2E
path, including duplicate prevention, restart/recovery, notification privacy,
and zero protected-domain mutation. Checkpoint 86 Full verification passed with
1,092 backend tests and zero skips plus 128 frontend tests across 12 files and
zero skips. Dependency checks, Ruff lint/format, strict mypy, Alembic
current/heads/check, ESLint, TypeScript, production build, and diff hygiene also
passed.

These are candidate notes only. No tag or GitHub Release has been created.
