# Checkpoint 108 report - Local V1.5 release hardening

Status: **Approved and complete after human review. Local V1.5 was subsequently
published without changing CP108's release-hardening evidence.**

## Candidate and preflight

Candidate tag is `v1.5.0`; candidate title is **Second Brain Local V1.5**.
Clean synchronized `main` was exact remediation commit
`05e74db5d029d5688eef39fdae1fae6ac6fa6857` on `origin/main`; exact push CI run
`33973369749` completed successfully. Pins are exactly
`PyJWT[crypto]==2.13.0` and `pypdf==6.16.1`.

Development/test identities were `127.0.0.1:5433/second_brain` and
`127.0.0.1:5433/second_brain_test`. Alembic current and sole head were
`0016_calendar_event_observations`; `alembic check` was clean. Tool Registry is
`agent-tools-v1`; Project export is `second-brain-project-export` version `1`.
G01-G18 remained green with exactly 37 unique mapped nodes.

## Clean install and privacy audit

A Git archive of the exact SHA supplied a disposable clean copy. Fresh Python
3.12 installation, `pip check`, `import app`, and `import app.main` passed with
the exact remediated versions. `pip-audit` 2.10.1 reported no known shipped
vulnerabilities; only the editable local distribution was skipped. Fresh
locked `npm ci` installed 210 packages, both npm audit commands reported zero
vulnerabilities, ESLint and TypeScript passed, and Vite built 88 modules.
Disposable environments and build output were removed.

The tracked inventory contained 556 files. No tracked `.env`, private key,
database dump, log/cache/temp artifact, virtual environment, `node_modules`,
build/coverage output, or exported bundle was found. A bounded production-file
secret-pattern scan found zero matches. The real `.env` was neither printed nor
modified. Calendar privacy/authority tests and bounded schema/surface review
found no raw provider payload, raw Google `sub`, token, or private secret in an
approved release surface.

## Calendar boundary and export compatibility

The release retains only `openid` and
`https://www.googleapis.com/auth/calendar.events.readonly`, an exact
operator-entered calendar allowlist, minimized ordinary projections, fixed
private/special labels, and exclusion of sensitive fields and provider-content
links. It has no sync-token or tombstone ingestion, Calendar write/import/
scheduling, generic provider executor, or Calendar authority for Agents or
Automations. CP102 manual refresh remains the sole request trigger.

A read-only development Project export contained exactly `manifest.json`,
`project.json`, `memories.jsonl`, `memory_embeddings.jsonl`, `sources.jsonl`,
`memory_sources.jsonl`, `source_documents.jsonl`, `source_chunks.jsonl`,
`memory_extraction_runs.jsonl`, and `memory_proposals.jsonl`. Its identity was
`second-brain-project-export` version `1`. Calendar accounts/identities, runs,
event revisions, observations/evidence, credential references/envelopes, OAuth
tokens, and provider identity material were absent. The temporary bundle was
removed.

## Backup, restart, and recovery

A read-only custom-format dump of verified development database `second_brain`
produced a 264-line `pg_restore --list` inventory. It contained table/data/
constraint/index relationships for `calendar_account_revisions`,
`calendar_identities`, `calendar_sync_runs`, `calendar_event_revisions`, and
`calendar_event_observations`, proving the approved schema through `0016`. No
restore ran and both container/host temporary dumps were removed.

The established stop/start scripts preserved exact container
`62904b6be659aa32b71dcda4d6e6af617426778ffd905c7809c6fc6979fac222`, named
volume `second-brain_postgres_data`, and the fingerprint
`second_brain|0016_calendar_event_observations|2|0|0|0|0|0` (database, revision,
Project and five Calendar-table counts). After restart both database identities,
Alembic current/check, and API health/readiness passed. The documented normal
Vite path returned HTTP 200 and its `/api/health` and `/api/ready` proxy calls
returned `ok` and `ready`; the exact temporary API/Vite processes were stopped.

Only fresh synthetic credential-store targets and fake OAuth/Calendar providers
were used. Focused tests prove install/read/replace/revoke/cleanup, disabled or
revoked zero-request fencing, reauthorization-required fail-closed behavior,
and readable historical local evidence. Cleanup is guarded by `finally`. There
was zero real credential enumeration, real Google/Calendar request, Calendar
write, import, scheduling, or Agent/Automation Calendar authority.

## Verification

- Focused Calendar/OAuth/security/CP107 backend: **104 passed**, zero skipped.
- Focused Calendar/External Context frontend: **15 passed**, zero skipped.
- Full backend: **1,341 passed**, zero skipped (13 warnings).
- Full frontend: **148 passed across 15 files**, zero skipped.
- `pip check`, Ruff lint/format over 481 files, strict mypy over 203 production
  files, Alembic current/head/check, frontend ESLint/TypeScript, the 88-module
  production Vite build, and `git diff --check`: pass.

No production defect or critical security blocker was found. This checkpoint
changes documentation only: no production code, migration, schema, dependency,
lockfile, CI authority, registry, or export-format change. No tag, GitHub
Release, PR, commit, push, or publication action occurred.

## Exact changed paths

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/CHECKPOINTS.md`
- `docs/KNOWN_LIMITATIONS.md`
- `docs/LOCAL_V1_RUNBOOK.md`
- `docs/LOCAL_V1_5_RELEASE_NOTES.md`
- `docs/ROADMAP.md`
- `docs/V1_5_CALENDAR_ROADMAP.md`
- `docs/V1_5_CALENDAR_THREAT_MODEL.md`
- `docs/checkpoint-108-report.md`

CP108 is approved and complete after human review. At CP108 completion, Local
V1.5 was publication-ready only: no tag, GitHub Release, push, or publication
occurred during the checkpoint, and `v1.4.0` remained the recovery release.

## Post-checkpoint publication outcome

After CP108 and its exact evidence were complete, Local V1.5 was published as
annotated tag `v1.5.0`, titled **Second Brain Local V1.5**. Tag object
`e8f281a0b805b887768e53a447fc9e3b4444e04b` peels to exact approved release
commit `9c140dd83a84072743facefb55c2f56e91691535`. GitHub Release `383369546` was
published at `2026-09-05T20:45:42Z`, is neither draft nor prerelease, has zero
assets, and is available at
<https://github.com/DarkAxiom93/Second_Brain/releases/tag/v1.5.0>.

`v1.5.0` is now the current published release and `v1.4.0` is the preceding
recovery release. CP99-CP108 remain approved and complete; Alembic remains
`0016_calendar_event_observations`, Tool Registry remains `agent-tools-v1`, and
Project export remains `second-brain-project-export` version `1`. Publication
introduced no Calendar import or scheduling, Calendar write, or Agent/Automation
Calendar authority, and no post-V1.5 roadmap capability has started.
