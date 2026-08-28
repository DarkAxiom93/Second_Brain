# Checkpoint 87 report - Local V1.4 scope, architecture, roadmap, and threat model

Status: **Approved and complete after human review.**

## Outcome

Checkpoint 87 defines
**Local V1.4 — Read-only Connectors & External Context**. The proposed release
establishes a narrow connector foundation and
one independently reviewed GitHub read-only implementation. External records
remain quarantined, untrusted, versioned snapshots. They can enter the existing
audited Source/SourceDocument pipeline only through an explicit single-item
operator import; existing proposal review and separate promotion remain
mandatory before any Memory is created.

No V1.4 production code, test implementation, migration, dependency, API, UI,
credential, network call, Tool Registry version, Agent authority, Automation
authority, Project export version, connector capability, external write, or
reviewed-knowledge mutation was added.

## Preflight

- Branch: `main`.
- Working tree before edits: clean.
- Local/remote synchronization: HEAD and `origin/main` both
  `c2ca78be2f8bfd7f3eb88f6c0dbe24aaca902aba`; ahead/behind `0/0`.
- Published release: `v1.3.0`, **Second Brain Local V1.3**, published
  2026-08-28 from release commit
  `f79d556cb8d99961aa081464ef151ef1037fe87a`.
- Post-publication documentation-sync CI: successful run `33161803071` for
  `c2ca78be2f8bfd7f3eb88f6c0dbe24aaca902aba`.
- Alembic expected current/head: `0011_automation_persistence`.
- Tool Registry: `agent-tools-v1`.
- Project export: `second-brain-project-export` version `1`.

## Decision rationale

Five candidate directions were evaluated in `V1_4_ROADMAP.md` for user value,
architectural dependency, security and credential risk, migration impact,
testability, rollback/recovery complexity, and compatibility with the local
single-maintainer boundary.

Read-only connectors provide the largest new product value while preserving the
current authority boundary, provided that V1.4 ships one provider, uses an OS
credential store, permits only closed bounded reads, quarantines content, and
keeps Agents unchanged. Agent/Automation UX is safer but incremental. Import/
export evolution adds resilience but introduces encryption/key and compatibility
decisions without comparable daily value. Proposal/write execution has much
higher ambiguity and confused-deputy risk. Authentication/multi-user operation
would redesign the fundamental deployment and ownership boundary.

GitHub is selected first because fine-grained, repository-scoped, read-only,
expiring personal access tokens avoid OAuth client-secret and refresh-token
machinery. Initial scope is explicit repositories plus bounded repository
metadata, issues, and pull requests. Google Calendar is deferred to its own
OAuth/privacy review; Gmail is deferred because mailbox content, attachments,
metadata, and injection/phishing exposure create a materially broader risk.

## Credential and trust decisions

Secrets may live only in the OS per-user credential store. PostgreSQL stores at
most an opaque non-secret reference and safe identity/scope/expiry metadata.
There is no automatic token refresh in the proposed GitHub release. Expired,
revoked, missing, identity-drifted, or scope-expanded credentials fail closed
and require explicit replacement. Credentials are excluded from logs, errors,
events, notifications, prompts, browser state, diagnostics, exports, application
backups, and test artifacts. Checkpoint 88 is a blocking prerequisite; plaintext
credential persistence is not authorized.

Every external item captures provider, immutable external account/repository/
item identity, exact nullable Project scope, source version, content hash,
application revision, sync provenance, first/last-seen state, and stale/deleted
status. Partial/failed pagination never implies deletion. External content is
displayed as untrusted and inert, cannot be read by existing Agents, and never
silently becomes reviewed Memory.

## Agent, Automation, persistence, and export boundary

Manual Research, Memory Curator, Daily Brief, Project Watch, their existing Tool
allowlists, and current Automation behavior remain unchanged. V1.4 proposes no
new Agent Tool and no Tool Registry identity. Manual connector refresh precedes
an optional late scheduling checkpoint; scheduled refresh would be a separate
non-Agent occurrence and grant no import or Agent authority.

Implementation is expected to require additive ConnectorAccount,
ConnectorSyncRun, and ExternalItem persistence after Checkpoint 88. Credentials
remain outside PostgreSQL. Exact migration shape is reviewed in Checkpoint 89.
Project export `second-brain-project-export` version `1` remains unchanged and
excludes all connector records and references.

## Proposed implementation sequence

1. 88 - OS credential-store prerequisite and secret boundary.
2. 89 - Inert connector persistence and catalog.
3. 90 - Connector account lifecycle and safe UI.
4. 91 - Bounded GitHub read transport and manual sync.
5. 92 - External context browser and reconciliation.
6. 93 - Explicit single-item import into audited ingestion.
7. 94 - Optional explicit connector refresh scheduling.
8. 95 - Connector security and evaluation gate.
9. 96 - Local V1.4 end-to-end acceptance.
10. 97 - Local V1.4 release hardening.

Every checkpoint states dependency, goal, production areas, persistence/API/UI
impact, concurrency/transactions, security acceptance, focused tests, and
rollback. Checkpoint 87 starts none of them.

## Threat coverage

`V1_4_THREAT_MODEL.md` defines C01-C18: credential leakage, excessive scopes,
confused deputy, prompt injection, cross-Project leakage, stale/revoked
credentials, duplicate ingestion/import, pagination/retry amplification, rate-
limit exhaustion, malicious content, connector identity spoofing, update/
deletion reconciliation, scheduler-triggered access, outage/ambiguous response,
logging/notification leakage, export/backup leakage, privilege expansion through
configuration, and accidental external or reviewed-local mutation. Every row
defines prevention, fail-closed behavior, and deterministic tests.

## Explicit deferrals

Gmail; Calendar pending separate OAuth/privacy review; other connectors; generic
integration/HTTP/GraphQL; source code/diffs/logs/artifacts/attachments; direct
Agent connector access; Tool Registry changes; connector access for existing
Agents; automatic/bulk import; automatic proposals/review/promotion; external or
reviewed-local writes; OAuth client-secret/refresh-token support; webhooks;
external notifications; arbitrary execution; authentication/multi-user/remote/
cloud operation; export v2/encrypted backup/import merge or remap; and automatic
snapshot deletion.

## Verification evidence

Focused verification passed:

- `tests/test_verification_script.py` and `tests/test_ci_workflow.py`: 12 passed,
  zero skipped;
- documentation/repository consistency: exactly the five intended `docs/`
  paths and no production/dependency/schema/test path;
- `git diff --check`: passed; and
- static Alembic sole head, diagnostics expected head, and export database
  revision: `0011_automation_persistence`; Tool Registry: `agent-tools-v1`;
  Project export: `second-brain-project-export` version `1`.

The authoritative `.\scripts\verify.ps1 -Mode Full` rerun passed after the
existing PostgreSQL service became available:

- parsed and live development identity:
  `127.0.0.1:5433/second_brain`;
- parsed and live test identity: `127.0.0.1:5433/second_brain_test`;
- `pip check`, Ruff lint, Ruff format check, and strict mypy: passed;
- backend: 1,092 passed, zero skipped (10 warnings);
- Alembic current and sole head: `0011_automation_persistence`;
- Alembic check: no new upgrade operations detected;
- frontend ESLint and TypeScript: passed;
- frontend Vitest: 128 passed across 12 files, zero skipped;
- frontend production Vite build: passed; and
- final `git diff --check`: passed.

The healthy existing `second-brain-db-1` container continued to bind PostgreSQL
only at `127.0.0.1:5433`, and named volume `second-brain_postgres_data` remained
present. Verification used the repository's identity-checked test lifecycle;
no destructive development-database command, volume deletion, downgrade, or
manual cleanup was performed.

Checkpoint 87 is now safe for human approval. Its architecture, threat model,
scope, and proposed Checkpoints 88-97 are unchanged, and Checkpoint 88 has not
started.

## Self-audit

- Documentation/planning only: yes.
- V1.4 implementation checkpoint started: no.
- Production/application/frontend/test code changed: no.
- Migration/schema/dependency change: no.
- Credential storage or connector network call added: no.
- Tool Registry/Agent/Automation authority changed: no.
- Project export identity/version changed: no.
- External or reviewed-knowledge mutation authorized: no.
