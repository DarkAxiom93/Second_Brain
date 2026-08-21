# Checkpoint 74 report: Local V1.2 release hardening

Status: **Pending human review**. Local V1.2 is not published. No tag or GitHub
Release was created.

## Base and preflight

- Base: `5e3ce20495c4bea5f184c552a44524606a416693` (`HEAD`, `main`, and
  `origin/main` equal; clean preflight tree; divergence `0 0`).
- Exact `Second Brain CI` push run: GitHub Actions run `32472488396`, attempt
  1, completed successfully for the base SHA on `main`; artifact count: `0`.
- Checkpoint 73 was `Complete`; Checkpoint 74 was `Not started` before this
  documentation-only work.
- Alembic sole head and live current revision were
  `0010_agent_runtime_persistence`; `alembic check` found no upgrade operations.
- Tool registry identity was `agent-tools-v1`; Project export format version was
  `1`.
- Both pre-checkpoint remediations were present: exact pins `pypdf==6.15.0` and
  `pytest==9.0.3`, and the fail-closed Project bundle revision policy described
  below.

## Release inventory and boundaries

The candidate contains the accepted V1.1 application plus the V1.2 manual Agent
Runtime: five-table persistence, manual Run APIs and UI, immutable structured
plans, private seven-definition read-only registry, bounded five-Tool read
executor, cancellation/deadline/idempotency handling, explicit synchronous
recovery, immutable `memory.update` Approval Requests, fixed read-only Research
Agent, fixed advisory Memory Curator Agent, T01-T24 gate, and nine accessible
top-level UI routes.

The release boundary remains one trusted maintainer on loopback. Manual,
Research, and Memory Curator authority boundaries are unchanged. There is no
proposal execution, automatic Approval or promotion, Automation, scheduler,
worker, connector, external research, external write, arbitrary execution, or
remote/multi-user operation.

## Clean installation and dependency security

A Git archive of the exact base was expanded to a disposable clean checkout.
With Python 3.12, a new virtual environment was created, its disposable
packaging tooling was upgraded to pip 26.2.1, and `.[dev]` installed without
undeclared local state. `pip check` reported no broken requirements and an
application import succeeded. Installed project pins included pypdf 6.15.0 and
pytest 9.0.3.

The repository-supported Python audit (`pip-audit --local --skip-editable`) in
that environment reported no known vulnerabilities; only the editable local
project itself was skipped, while its declared installed dependencies were
audited. Pip was environment tooling and was not added as an application
dependency. Locked frontend `npm ci` installed 210 packages and audited 211;
`npm audit --audit-level=high` reported zero vulnerabilities. The installed
router was `react-router@8.3.0` with no `react-router-dom` package. The clean
Vite production build transformed 84 modules successfully.

## Security and privacy

The focused backend release gate passed 81 tests with zero skips: all 48
T01-T24 security/evaluation checks plus 33 Project export/import API, service,
script, and integration checks. The complete backend suite repeated the gate.
Static tracked-file inspection found zero sensitive filenames, zero non-test
private-key markers, and only the three intended example environment files.

Project exports expose no Agent Run, Step, Tool invocation, Agent event,
Approval, execution, raw provider/Tool payload, hidden-reasoning, or other
private runtime record. Existing safe-error, redaction, deterministic evidence,
scope, non-mutation, approval-bypass, and fail-closed tests remain green. No
release artifact or documentation contains a secret or runtime payload.

## Application, database, and accessibility verification

- Focused frontend Agent/App acceptance: 37 passed, zero skipped.
- Full backend: 920 passed, zero skipped, on Python 3.12.10 / pytest 9.0.3 with
  pytest-cov active.
- Full frontend: 114 passed across 11 files, zero skipped; lint, TypeScript, and
  Vite production build passed.
- Database identities were exactly `127.0.0.1:5433/second_brain` and the
  isolated `second_brain_test`. Alembic current/head were both
  `0010_agent_runtime_persistence`; schema check was clean.
- Loopback smoke used FastAPI at `127.0.0.1:8000` and Vite at
  `127.0.0.1:5173`; proxied health and readiness returned `ok` and `ready`.
  Both exact smoke PIDs were stopped and both HTTP ports were unreachable
  afterward. The pre-existing database service and named volume were preserved.

Checkpoint 73 acceptance remains valid: all nine routes were accepted at
390x844 without horizontal overflow; keyboard focus measured 2.66667px and was
visible; semantic headings, fieldsets, labels, live regions, and reduced-motion
behavior were present. Current focused frontend tests reconfirmed the accepted
Agent/App behavior.

## Project export and import compatibility

A real read-only export from the revision-0010 application database succeeded
and recorded format version 1 and source revision
`0010_agent_runtime_persistence`. Real script validation against the isolated
revision-0010 test target succeeded. Archive inspection found only the declared
V1 Project records and manifest; Agent, Approval, execution, and private runtime
state were absent.

Focused and Full tests proved deterministic round trip, current export and
import at 0010, legacy V1 bundles sourced at `0009_memory_expiration`, current
V1 bundles sourced at `0010_agent_runtime_persistence`, exact target revision
0010, unsupported source/target rejection, unchanged Agent state, database
identity checks, and atomic conflict-free import. Supported V1 source revisions
remain exactly 0009 and 0010; the format remains version 1.

## Backup, recovery, and cleanup

A read-only custom-format `pg_dump` of the development database was created
inside the PostgreSQL container. `pg_restore --list` successfully enumerated
the archive, including Project/Memory and Agent/Approval tables and data. No
restore was executed. The exact disposable container dump was removed and its
absence confirmed; the database and named volume were not deleted or modified
destructively.

The runbook now distinguishes complete database backup from Project export and
requires exact database identity, archive inspection, a separate target, and
separate approval before destructive restore. V1.1 `v1.1.0` remains the
recovery release: use a separate checkout with a verified revision-0009 backup
restored to a separate identity-checked database. Never run V1.1 against or
downgrade the current revision-0010 development database. Disposable checkout,
virtual environment, bundle, and audit files were removed after verification.

## Full verification and limitations

`.\scripts\verify.ps1 -Mode Full` completed successfully: database identity,
pip check, Ruff lint/format, mypy (131 source files), all 920 backend tests,
Alembic current/heads/check, frontend lint/typecheck, all 114 frontend tests,
the production build, and `git diff --check` passed. There were zero skips.

Known non-blocking limitations remain documented in
[KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md): trusted loopback-only operation,
no authentication or multi-user isolation, no Automation/background work or
connectors, proposal-only Approval, provider credentials for live
provider-backed success, unencrypted Project bundles, conflict-free-only
import, and stateless Answers. The Full suite emitted existing deprecation and
schema warnings but no failures. No release blocker was found.

## Self-audit

The final diff is documentation-only. It adds this evidence report and Local
V1.2 candidate release notes, and synchronizes existing architecture, roadmap,
checkpoint, runbook, README, and limitation facts. It changes no application,
runtime, API, schema, migration, dependency, lockfile, CI, Docker, registry,
export version, or capability. It starts no V1.3 work. Every release claim above
is backed by the recorded commands, tests, archive inspection, or accepted CP73
evidence. The repository is ready for human review, not publication.
