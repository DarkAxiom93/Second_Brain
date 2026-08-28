# Checkpoint 89 report - inert connector persistence and closed catalog

Status: **Approved and complete after human review.**

## Outcome and recovery

Checkpoint 89 adds three inert PostgreSQL concepts, caller-transaction-owned
repository primitives, pure validation, and one immutable code-owned GitHub
catalog. It adds no transport, credential lookup, public API/UI, Agent Tool,
Agent or Automation authority, import, reviewed-local mutation, or external
write behavior. Checkpoint 90 has not started.

The corrected Windows preflight used only process-local canonical URLs. The
repository database verifier confirmed `127.0.0.1:5433/second_brain` and
`127.0.0.1:5433/second_brain_test`; the live development identity was exactly
`second_brain`. Before implementation, Alembic current/head was
`0011_automation_persistence` and `alembic check` reported no pending
operations. The earlier `db` hostname failure was configuration-context only
and required no `.env`, Docker, compose, or application configuration change.

During focused verification, an unrelated installer exhausted drive C: and a
formatter truncated `app/repositories/connectors.py`. Recovery preserved all
valid work, reconstructed that file first, then checked every changed path for
zero bytes, binary NULs, Python syntax, imports, mapper configuration, and
migration graph integrity. Free space was stable at 23.83 GiB before recovery
and 22.64 GiB after the complete integrity audit.

## Persistence and invariants

- `ConnectorAccount` stores only `github`, immutable external account identity
  and SHA-256 fingerprint, exact opaque credential reference, nullable exact
  Project scope, a 1-32 repository allowlist, permission-name-derived scope
  fingerprint, closed lifecycle/validation state, revision, and safe timestamps.
  Null Project means explicit unassigned scope. Provider/account and credential
  references are unique; Project deletion is restrictive.
- `ConnectorSyncRun` captures exact account/provider ownership, account revision,
  historical Project/unassigned scope, closed manual/reserved-scheduled trigger,
  bounded state/counts, safe application error code, reconciliation flag, and
  timestamps. A partial unique index permits one `claimed`/`running` run per
  account. It stores no request, response, URL, header, payload, exception, or
  credential.
- `ExternalItem` is an append-only quarantined revision containing exact account,
  immutable resource/item identity, one closed resource type, provider source
  version, bounded untrusted title/body, deterministic content hash, closed
  state, first/last-seen timestamps, captured Project/unassigned scope, and exact
  creating/last-seen sync provenance.

Migration `0012_connector_persistence` is the sole additive migration, directly
after `0011_automation_persistence`. Composite restrictive foreign keys prevent
cross-account provenance substitution. Equal provider-version/content replay
returns the existing row without an update; a changed version/content appends
the next deterministic application revision and retains the original
first-seen scope/provenance. Repositories flush but never commit, so transaction
ownership remains with the caller. No repository path imports a network or OS
credential adapter, and no lock is held across either boundary.

## Closed catalog and credential boundary

The catalog contains exactly GitHub version 1. Enabled persistence resources are
repository metadata, issues, and pull requests. Comments are represented only
as disabled/reserved. The definition has no URL, host, method, query, GraphQL,
header, Tool, Agent, Automation, import, discovery, executable, or write field.
Source code, diffs, Actions data, organizations/members, email, packages,
secrets, administration, webhooks, writes, and arbitrary repository discovery
remain absent.

Credential references accept exactly lowercase `sbcred:v1:<UUIDv4>`. The shared
Checkpoint 88 validator is a type/invariant dependency only; connector code does
not instantiate or call a credential store. Database and application checks
reject token/password/authorization/cookie-shaped values from credential and
safe-metadata fields. Scope fingerprints are derived deterministically from the
closed names `metadata_read`, `issues_read`, and `pull_requests_read`, never from
credential material. External title/body content intentionally remains bounded
untrusted data rather than being treated as safe metadata.

## Export, isolation, and protected domains

Project export remains `second-brain-project-export` version `1`. Its exact file
inventory is unchanged and contains no connector table. The export test creates
all three connector entities in a Project, expands every archive member, and
proves the opaque credential reference and connector trigger/provenance metadata
are absent.

Repository ownership checks reject captured revision or Project drift and
cross-account item provenance. Database provider/account composite foreign keys,
per-account/resource/item uniqueness, and restrictive deletion behavior backstop
that application isolation. Complete-row snapshots of every pre-existing
application table remain byte-for-byte unchanged while malicious external title
and body content is persisted. Therefore no Source, SourceDocument, proposal,
Memory, Agent, Approval, Automation, occurrence, or notification is created or
updated.

## Security acceptance advanced

- **C01/C06/C15:** exact opaque references only; no secret-derived persistence,
  credential lookup, secret exception, payload, or unsafe diagnostic field.
- **C02/C03/C17:** one provider and three enabled read-resource identities;
  closed schemas cannot express requests, authority, discovery, import, or write.
- **C04/C05/C11:** exact account/provider/Project ownership and immutable external
  resource/item identities reject cross-account, cross-Project, and spoofed
  provenance.
- **C07:** unique replay identity plus write-free equal replay and deterministic
  changed revision semantics.
- **C08/C09/C13/C14:** no transport, retry, pagination, rate-limit, scheduler, or
  outage behavior exists in this checkpoint.
- **C10:** hostile external text persists only in bounded quarantined fields and
  produces zero protected-domain or execution mutation.
- **C12:** append-only revisions, first/last-seen state, exact sync provenance,
  and restrictive FKs preserve update/delete history.
- **C16:** export v1 inventory and canary scans exclude connector rows, opaque
  references, and runtime/provenance metadata.
- **C18:** complete-row protected-domain snapshots remain unchanged.

## Verification evidence

Focused connector, migration, and export verification: **36 passed, zero
skipped**. It covers the sole migration head/lifecycle on the verified
`second_brain_test` database, constraints/FKs, caller transaction neutrality,
revision/scope isolation, reference and secret rejection, replay/versioning,
catalog closure, archive exclusion, inert malicious content, and protected-row
snapshots.

The authoritative host-context `./scripts/verify.ps1 -Mode Full` completed
successfully:

- database identities and `pip check`: passed;
- Ruff lint/format and strict mypy: passed;
- backend: **1,130 passed, zero skipped** (13 warnings);
- Alembic current and sole head: `0012_connector_persistence`;
- Alembic check: no new upgrade operations;
- frontend ESLint and TypeScript: passed;
- frontend Vitest: **128 passed in 12 files, zero skipped**;
- frontend production build and final `git diff --check`: passed.

The sandboxed Full attempt correctly reported the pre-existing Checkpoint 88
Windows credential probe as `credential_store_locked`; its exact standalone
test and the authoritative Full run passed in the supported Windows host
context. This was execution-context isolation, not connector access or a
weakened assertion. No test was skipped. Disk free space was 23.68 GiB before
the first Full attempt, 20.50 GiB before the authoritative host-context run, and
21.05 GiB after it.

## Changed paths

- `app/connectors/__init__.py`
- `app/connectors/catalog.py`
- `app/connectors/validation.py`
- `app/credentials/contract.py`
- `app/credentials/windows.py`
- `app/diagnostics/service.py`
- `app/models/__init__.py`
- `app/models/connector.py`
- `app/project_export/models.py`
- `app/repositories/connectors.py`
- `migrations/versions/0012_create_connector_persistence.py`
- `tests/integration/test_connector_persistence.py`
- `tests/integration/test_migrations.py`
- `tests/test_connector_catalog.py`
- `tests/test_models.py`
- `tests/test_operations_routes.py`
- `docs/CHECKPOINTS.md`
- `docs/ROADMAP.md`
- `docs/V1_4_ROADMAP.md`
- `docs/checkpoint-89-report.md`

All work remains unstaged and uncommitted for human review. Tool Registry
identity remains `agent-tools-v1`; Project export remains
`second-brain-project-export` version `1`.

Final worktree summary: 20 changed/untracked paths, 1,467 insertions and 22
deletions when new-file contents are included. Everything is unstaged and
uncommitted.
