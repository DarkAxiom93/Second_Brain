# Checkpoint 108 dependency-security blocker remediation report

Status: **Approved and complete after human review. CP108 remains blocked
pending remediation commit, push, and successful exact push CI.**

## Scope and advisory evidence

Preflight passed on clean synchronized `main` at approved CP107 commit
`abcba1274d7fbe6cc3755aca787dbbd153f4b8a9`; push CI run `33968380904`
completed successfully for that exact SHA. Development and test database
identities passed. Alembic current and sole head were
`0016_calendar_event_observations`. Tool Registry was `agent-tools-v1` and
Project export was `second-brain-project-export` version `1`.

Before editing, pip-audit 2.10.1 reported 15 records across the two shipped
packages. PyJWT 2.10.1 had PYSEC-2026-120 (fix 2.12.0), PYSEC-2025-183 (no fix
listed), and the PYSEC-2026-175/176/177/178/179 family whose highest listed fix
was 2.13.0. pypdf 6.15.0 had CVE-2026-84309 (fix 6.16.0) and
CVE-2026-84310/CVE-2026-84311 (fix 6.16.1). The requested versions therefore
covered every listed fixed-version floor.

## Remediation and compatibility

Only two `pyproject.toml` pins changed: `PyJWT[crypto]==2.10.1` to 2.13.0 and
`pypdf==6.15.0` to 6.16.1. The repository has no backend lockfile or separate
requirements file. No unrelated dependency, production code, migration,
schema, export format, registry, API, frontend, OAuth scope, or authority
changed.

Focused OAuth/JWT, fingerprint, reauthorization/revocation, PDF ingestion and
malformed-PDF, CP106 G01-G18 manifest/adversarial, Calendar persistence/API,
and CP107 joined acceptance verification passed **127 tests**, zero skipped.
The G01-G18 manifest remains exactly 37 unique mapped nodes and no security
expectation was weakened.

A disposable Python 3.12 environment installed the edited project plus dev
dependencies from tracked metadata. `pip check`, `import app`, and
`import app.main` passed with PyJWT 2.13.0 and pypdf 6.16.1. A fresh full local
pip-audit reported **no known vulnerabilities** among shipped dependencies;
only the editable local project distribution was intentionally skipped. Both
disposable audit environments were removed.

## Full verification and boundaries

The first sandbox-context Full run passed 1,340 tests and failed only the known
Windows Credential Manager host-context availability test with
`credential_store_locked`; no code or test changed in response. The fresh
authoritative normal-Windows-host Full run passed dependency integrity, Ruff
lint/format over 478 files, strict mypy over 203 production files,
**1,341 backend tests**, Alembic current/head/check, frontend lint/typecheck,
**148 frontend tests across 15 files**, the 88-module production Vite build,
and `git diff --check`, all with zero skips.

The remediation used no real credential enumeration and no real Google or
Calendar request. It creates no Calendar write, import, scheduling, Agent or
Automation authority, and widens no OAuth scope. CP104 import omission, CP105
manual-refresh-only scheduling omission, the `0016` schema, `agent-tools-v1`,
and Project export version 1 remain unchanged.

Changed paths are exactly `pyproject.toml`, `docs/ARCHITECTURE.md`,
`docs/CHECKPOINTS.md`, `docs/ROADMAP.md`, `docs/V1_5_CALENDAR_ROADMAP.md`, and
this report. Everything remains unstaged and uncommitted. No PR, push, tag,
release, or publication action occurred. The remediation is approved and
complete after human review. CP108 must not resume until this remediation is
committed, pushed, and its exact push CI succeeds.
