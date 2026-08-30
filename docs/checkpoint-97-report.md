# Checkpoint 97 report - Local V1.4 release hardening

Status: **Approved and complete after human review.**

## Outcome and release candidate

Checkpoint 97 prepares candidate tag `v1.4.0`, title **Second Brain Local
V1.4**, from approved/pushed Checkpoint 96 base
`49f6eaa78f2a1a27bf5e48d6d845c0f082e10d6f`. Exact push CI run `33292270431`
completed successfully. No tag, GitHub Release, PR, commit, push, or publication
action occurred.

This checkpoint changes documentation and release evidence only. It changes no
production behavior, schema, migration, API, frontend capability, dependency,
lockfile, CI, Docker configuration, Tool Registry, export format, connector
authority, or GitHub transport.

## Preflight and preserved clean-install evidence

`main` was clean and synchronized with `origin/main` at the exact base SHA.
Parsed and live databases were `second_brain` and `second_brain_test` on
`127.0.0.1:5433`. Alembic current and sole head were
`0014_connector_refresh_schedules`; `alembic check` found no new upgrade
operations. Tool Registry was `agent-tools-v1`; export was
`second-brain-project-export` version `1`. Initial free disk was 21,679,976,448
bytes.

A Git archive of the exact base SHA supplied a disposable clean copy. A fresh
Python 3.12 environment installed project and development dependencies without
the working-tree `.venv`; `pip check`, `import app`, and `import app.main`
passed. `pip-audit --local --skip-editable` found no shipped dependency
vulnerability after only the disposable bootstrap pip was upgraded from its
stale vulnerable seed to 26.2.1. Project dependencies were not changed.

Fresh locked `npm ci` installed 210 packages and reported zero vulnerabilities;
`npm audit --audit-level=high`, ESLint, TypeScript, and the 87-module production
Vite build passed. The disposable environment, build, and audit files were
removed.

## Privacy, credentials, and export compatibility

The complete tracked inventory contained 507 files. No prohibited `.env`,
private key, database dump, `.sbexport`, log, cache, virtual environment,
`node_modules`, build, or coverage artifact was tracked. Secret-pattern scans
found only the intentionally obvious synthetic PAT canary in the deterministic
adversarial fixture. Public schema/error/export tests proved credentials, raw
provider payloads, exception text, private connector content, and synthetic
canaries do not escape approved boundaries. The real `.env` was neither printed
nor modified.

The Windows credential-store contract installed, read, replaced, revoked, and
verified cleanup of one clearly synthetic credential in `finally`. The
documented operator workflow requires an expiring fine-grained PAT, selected
repositories, only necessary read permissions, an opaque reference, and
explicit replacement/revocation with no automatic refresh. No real PAT was
used. The accepted residual risk remains that the bounded GitHub API cannot
prove absence of additional provider-side grants.

A real read-only development Project export validated against the separately
verified test database. It was `second-brain-project-export` version `1` with
exact archive entries `manifest.json`, `project.json`, `memories.jsonl`,
`memory_embeddings.jsonl`, `sources.jsonl`, `memory_sources.jsonl`,
`source_documents.jsonl`, `source_chunks.jsonl`,
`memory_extraction_runs.jsonl`, and `memory_proposals.jsonl`. Connector runtime,
provenance, schedules, credential references, and secret markers were absent.
Imported ordinary Source/SourceDocument compatibility remains the existing
export-v1 contract only. Temporary bundles were removed.

## Backup, restart, and connector safety

Docker recovered at Engine 29.6.2. Existing container
`62904b6be659aa32b71dcda4d6e6af617426778ffd905c7809c6fc6979fac222`
(`second-brain-db-1`) restarted healthy on the existing named volume
`second-brain_postgres_data` mounted at `/var/lib/postgresql/data`.

A read-only custom-format `pg_dump` used role `second_brain` and database
`second_brain`. `pg_restore --list` returned 229 TOC lines, including table,
data, constraint, index, and foreign-key entries for `connector_accounts`,
`connector_sync_runs`, `external_items`, `external_item_imports`,
`connector_refresh_schedules`, and `connector_refresh_occurrences`. No restore
ran; the exact temporary dump was removed.

`dev-down.ps1` and `dev-up.ps1` preserved the same container and named volume.
Before/after facts matched exactly: database `second_brain`, revision
`0014_connector_refresh_schedules`, two Projects, and zero current connector
account/item/import/schedule/occurrence rows. Both canonical database identities,
Alembic current/head/check, direct FastAPI health/readiness, and Vite-proxied
health/readiness passed after restart. Temporary API/Vite listeners and logs
were removed.

The deterministic connector restart/revocation evidence uses fake credential
and transport boundaries only. It proves metadata/snapshot durability,
disabled/revoked zero-request fencing for manual and scheduled access,
readability of prior quarantined snapshots, independence of already imported
Source/SourceDocument state, scheduler startup without an implicit tick, no
replay-all, and zero AgentRun/import/Memory/Proposal/Approval side effects.

## Security gates and verification

The code-owned C01-C18 manifest remains green. The fixed request inventory is
GET-only for authenticated identity, configured repository metadata, issues,
and pulls. Cross-Project/account/unassigned isolation, protected-domain
snapshots, explicit one-item import, scheduled-refresh fencing, export
exclusion, no direct Agent connector Tool, and zero external writes remain
enforced. No real GitHub credential, request, or other external write occurred.

- Focused connector/security suite: **145 passed**, zero skipped.
- Full backend: **1,237 passed**, zero skipped (12 warnings).
- Full frontend: **137 passed across 14 files**, zero skipped.
- Pip integrity, Ruff lint/format, strict mypy over 182 production files,
  Alembic current/head/check, frontend ESLint/TypeScript, the 87-module
  production build, and `git diff --check`: pass.

## Deferred scope, cleanup, and handoff

The exact exclusions remain source code/diffs, Actions logs/artifacts, comments,
organizations/members/email, packages/admin/webhooks, repository discovery,
external writes, direct Agent connector Tools, automatic or scheduled import,
automatic Memory/proposal creation, Gmail/Calendar, authentication/multi-user,
remote/cloud operation, generic network execution, and export v2. No stable
document claims these capabilities.

All disposable clean-install, dependency-audit, export, backup, smoke-log, and
temporary process artifacts created by this checkpoint were removed. Temporary
ports 8000 and 5173 were closed. The PostgreSQL named volume and data were
preserved. Host free disk transiently fell from 21,130,899,456 bytes before Full
verification to 5,483,995,136 bytes and then 2,946,985,984 bytes during final
audit, then returned without cleanup. The resumed investigation began at
20,921,475,072 free bytes. `%TEMP%` contained 5,111,248,005 bytes: its largest
children were a 3,240,351,292-byte Visual Studio installer extraction cache
created the day before CP97, a 1,122,183,667-byte ScreenToGif directory, a
231,675,016-byte VS Code installer cache, and a 197,985,712-byte Docker Desktop
update cache. None was CP97-owned and none was deleted.

The repository `.git` directory was 2,300,435 bytes, including 2,052,193 bytes
in `objects/pack`. Docker reported 1.589 GB of images, 24.58 KB of containers,
861.5 MB of local volumes, and no build cache. Docker Desktop's observable WSL
virtual disk was 5,061,476,352 bytes. No `second-brain-cp97-*` or
`second-brain-pytest-*` directory remained; the only other pytest-named temp
directories were pre-existing sub-megabyte coverage fixtures. No Git, Node, or
npm process was active and no process other than the measurement command itself
referenced the candidate temp paths.

Five idle samples over about 23 seconds stayed between 20,907,159,552 and
20,908,191,744 free bytes while both the 3,240,351,292-byte Visual Studio cache
and 5,061,476,352-byte Docker VHD remained byte-for-byte stable. A bounded
`pip check` passed and changed free space only from 20,905,533,440 to
20,905,394,176 bytes. Six samples over the following 35 seconds stayed between
20,905,172,992 and 20,906,205,184 bytes and ended with two identical readings.
No multi-GB growth recurred.

The evidence rules out retained CP97 temp directories, Git packs, the identified
Visual Studio cache, bounded `pip check`, and observable Docker VHD growth as
the direct cause of the earlier collapse. Transient allocation and delayed
reclamation remain plausible, but the allocating layer is not identified. No
deletion was needed or performed.

The gate was then tested after the documentation-only update. Free space fell
again from about 20.906 GB to exactly 14,524,096,512 bytes, a recurrent
approximately 6.38 GB allocation, and three samples over six seconds were
identical. Docker, both database identities, the exact container/volume,
Tool Registry, export identity, and absence of CP97 temp directories all still
passed. Because unexplained multi-GB growth recurred during bounded work, the
checkpoint stopped again without cleanup or publication.

After the operator closed and reopened the development tools, free space
recovered from about 8 GB to about 30.6 GB without deleting project or Docker
data. Reopening VS Code alone left about 29 GB free. The approximately 2.3 MB
`.git` directory, stable approximately 4.7 GiB Docker VHD, and pre-existing
Claude VM VHDs did not account for the CP97 drops. The exact allocating storage
layer remains unproven; the best-supported explanation is transient host/tool-
environment allocation that was released when the development tools restarted.

The final resumed preflight began at 31,311,630,336 free bytes. Six idle samples
over 25 seconds stayed between 31,309,099,008 and 31,309,729,792 bytes. A
bounded `pip check` passed and changed free space from 31,309,099,008 to
31,309,025,280 bytes. Six samples during the following 30 seconds stayed between
31,308,541,952 and 31,308,886,016 bytes and ended at 31,308,595,200 bytes. No
multi-GB collapse recurred. Docker remained responsive, both database
identities passed, the exact healthy container and named volume remained, and
no CP97 or abandoned `second-brain-pytest-*` directory existed. No cleanup,
project/Docker data deletion, or unrelated user-file deletion was performed.
The final disk-stability gate passes.

Changed paths are exactly `README.md`, `docs/ARCHITECTURE.md`,
`docs/CHECKPOINTS.md`, `docs/KNOWN_LIMITATIONS.md`,
`docs/LOCAL_V1_RUNBOOK.md`, `docs/ROADMAP.md`, `docs/V1_4_ROADMAP.md`,
`docs/V1_4_THREAT_MODEL.md`, new `docs/LOCAL_V1_4_RELEASE_NOTES.md`, and new
`docs/checkpoint-97-report.md`. Everything remains unstaged and uncommitted.
No release blocker remains. Checkpoint 97 is approved and complete after human
review. Local V1.4 is ready for separately authorized publication, but remains
unpublished; `v1.4.0` has not been tagged or released.
Only release documentation changed after the authoritative focused and Full
runs, so their 145/1,237/137 zero-skip evidence was preserved and not repeated;
the final resumed bounded `pip check` passed.
