# Checkpoint 115 report - Local V1.6 release hardening

Status: **Implemented and fully verified; pending human review. Unpublished.**

## Candidate and preflight

CP115 began from clean synchronized `main` at exact baseline
`f21e01ea8afe4fa5797a63f8b717d6f0f93a66fb`. Local and live remote `main`
matched, `origin/main...main = 0 0`, and exact push CI run `34593595991` was
`completed` / `success` for that SHA. No tag, release, PR, commit, push, or
publication action occurred.

## Clean install and dependencies

A detached disposable clone used neither repository `.venv` nor `node_modules`.
Python 3.12.10 installed `.[dev]` with `--no-cache-dir`; `pip check`, backend
import, and Alembic head passed. Fresh locked `npm ci` used an isolated cache,
installed 210 packages, passed the high-severity audit gate, and built 89
production modules. The graph reported two moderate development-only Vitest
advisories; repository policy gates high severity, so no upgrade was made.

V1.5-to-candidate manifests have no backend or frontend runtime dependency
addition. `pyproject.toml` changed only by the CP113 pytest marker;
`frontend/package.json` and its lockfile are unchanged. No dependency exists
solely to bypass security or evaluation tests.

## Schema, authority, privacy, and export

Parsed and live database identities were exact. Current and sole Alembic head
were `0016_calendar_event_observations`; lineage was linear, `alembic check`
reported no new operations, and migration lifecycle passed. V1.6 adds no
migration, table, index, projection, or Hub persistence.

The authoritative CP113 manifest remains all 18 threat IDs, U01 through U18.
The focused release-hardening invocation passed 17 selected PostgreSQL pytest
nodes with zero skips; that execution count is not a threat-ID count, and some
selected nodes cover multiple manifest IDs. CP114 joined/reconciliation plus
migration lifecycle passed 8 tests; the Hub UI file passed 9. These
authoritative nodes cover three-scope isolation,
pagination/filter/facet/detail, native GitHub/Calendar transitions, hostile
inert rendering, accessibility, restart/stable ordering, runtime zero-call
tripwires, protected-domain zero delta, authority omissions, and export.

A real development Project export produced the exact ten-file inventory,
`second-brain-project-export` version `1`, at source revision
`0016_calendar_event_observations`. It excludes Hub, GitHub connector/runtime,
Calendar OAuth/account/revision/observation/runtime, credentials, and Agent/
Automation state. CP113/CP114 canaries confirm content-level exclusions.

Tool Registry remains `agent-tools-v1` with seven definitions and no Hub Tool.
Google OAuth scopes remain `openid` and
`https://www.googleapis.com/auth/calendar.events.readonly`.

## Backup, restart, and recovery

A 208,395-byte custom-format backup had a valid `pg_restore --list` inventory.
It restored into a uniquely named disposable database whose identity, revision
0016, and two-Project count were verified. The disposable database and exact
temporary dumps were removed; `second_brain` was never restored, reset,
downgraded, or destructively modified.

Repository stop/start scripts preserved the named volume and fingerprint
`second_brain|0016_calendar_event_observations|2|0|0|0`. CP114's fresh-
application restart node preserved Hub behavior and stable order. V1.6 needs no
new recovery step because the Hub owns no persistence.

## Final verification

- dependency integrity, Ruff lint/format, strict mypy: pass;
- backend: **1,404 passed, zero skipped**;
- Alembic current/head/check: revision 0016, sole head, no new operations;
- frontend ESLint and TypeScript: pass;
- frontend: **157 passed in 16 files, zero skipped**;
- production Vite build: **89 modules**, pass; and
- `git diff --check`: pass.

The authoritative Full ran after the substantive CP115 documentation was
complete. The sole later change was this factual clarification distinguishing
the 18-ID U01-U18 manifest from the focused invocation's 17 selected pytest
nodes; it changed no executable or configuration file and required no new Full
run under the commit instruction. `git diff --check` was rerun afterward.

## Exact CP115 changed paths

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/CHECKPOINTS.md`
- `docs/LOCAL_V1_6_RELEASE_NOTES.md`
- `docs/LOCAL_V1_RUNBOOK.md`
- `docs/ROADMAP.md`
- `docs/V1_6_CONTEXT_HUB_ROADMAP.md`
- `docs/checkpoint-115-report.md`

All changes remain unstaged and uncommitted. CP115 adds no production feature,
dependency, migration, schema, OAuth-scope, registry, export-format, or release
publication change.
