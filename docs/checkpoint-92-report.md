# Checkpoint 92 report - external context browser and reconciliation

Status: **Approved and complete after human review.**

## Outcome and stable boundary

Checkpoint 92 adds an External Context browser over quarantined, versioned
`ExternalItem` snapshots and complete-run-only absence reconciliation. It uses
the existing `0012_connector_persistence` schema and indexes. No migration,
GitHub request family, write method, scheduling, import, Source/SourceDocument,
Memory/Proposal/Approval mutation, Agent/Automation authority, Tool Registry or
export change, or Checkpoint 93 work exists. Tests use fake credentials and
`FakeGitHubTransport` only and make zero real GitHub requests.

## API, query, and public projection

The account-scoped routes are:

- `GET /connector-accounts/{account_id}/external-items`
- `GET /connector-accounts/{account_id}/external-items/{row_id}`
- `GET /connector-accounts/{account_id}/external-items/{row_id}/versions`

Every route requires one exact canonical Project UUID or literal `unassigned`.
Account and item scope must match. Filters are closed to the three approved
resource types and three reconciliation states. Lists return only the maximum
application revision per exact identity, ordered deterministically by revision
and UUID descending. Page size is 1-50 (default 25). The opaque keyset cursor is
length/alphabet/shape/integrity checked, account/scope/filter bound, and anchored
to a still-eligible latest row; malformed, cross-filter, and stale cursors fail
closed. Explicit history is exact-identity-bound, newest first, and bounded 50.

The allowlisted projection contains scope and immutable identities, closed type,
application/provider versions, state, bounded title, typed normalized content,
safe provenance/timestamps, derived confirmation time, `is_latest`, and fixed
`external_untrusted`. Repository JSON becomes description/private/archived;
issue/PR JSON becomes positive number/open-or-closed/body. It excludes hashes,
payloads, headers, raw/provider URLs, credentials/references, internal errors,
SQL, and arbitrary metadata.

## Reconciliation and last-seen semantics

Refresh retains at most the existing 2,000 accepted identities plus configured
repositories in memory. Only the final short transaction for a fully exhausted
success revalidates lifecycle, revision, Project, provider identity, policy, and
allowlist. It locks only latest identities in the captured account/scope:
observed identities become/remain `current`; absent ones become `stale`.
Incomplete, failed, cancelled, ceiling, outage, authorization, 404, rename,
transfer, and recreation ambiguity infer no absence or deletion. Rows are never
deleted and `deleted` remains reserved.

Exact current replay remains write-free. Exact stale replay changes only state
and observation provenance back to current, with no content revision. State
reconciliation never changes content, hash, version, identity, or Project.
`revision_last_observed_at` is honest stored revision observation metadata and
does not claim unchanged current replay wrote last-seen. The separately labeled
`confirmed_present_through` is derived from the latest complete successful
reconciliation for the exact account/scope and appears only on current items.

## Safe links, rendering, UI, and threat coverage

Links are reconstructed only from validated historical `owner/repo` identity
plus the typed integer issue/PR number, yielding fixed `https://github.com/...`,
`/issues/{number}`, or `/pull/{number}` forms. Provider URLs and current account
configuration are unused; an unsafe/unavailable history yields no link.

React uses escaped text and `pre` nodes only: no raw HTML, Markdown renderer,
`dangerouslySetInnerHTML`, scriptable URL, embed, or automatic navigation. The
view has explicit account/scope/type/state controls, loading/error/empty states,
latest pagination, detail/history/provenance, visible External/Untrusted and
state labels, optional safe link, and the existing explicit manual Refresh. It
adds no polling, browser persistence, import/Memory/bulk action, or hidden refresh.

CP92 advances C03/C05 through exact ownership predicates and bound cursors;
C04/C10 through typed projection, inert rendering, hostile-content tests and
fixed links; C07 through latest-only/history/replay proofs; C11/C12 through
immutable historical identities and complete-only reconciliation; C14 through
partial/failure preservation; C15/C17 through closed public/query schemas; and
C18 through unchanged GET-only fake transport plus protected-domain snapshots.
Research, Curator, Daily Brief, Project Watch, and Automations retain no
`ExternalItem` query path. Registry remains `agent-tools-v1`; export remains
`second-brain-project-export` version `1`.

## Verification evidence

Focused PostgreSQL connector tests: **41 passed**, zero skipped. Focused frontend:
**15 passed in 2 files**, zero skipped. Ruff, formatting, strict mypy over 174
production files, ESLint, and TypeScript passed. A sandbox Full run stopped only
at the expected host-only Credential Manager probe after 1,170 passes. The first
host run passed all **1,171 backend tests**, Alembic and static gates, then had
one transient pre-existing Settings focus assertion; an immediate complete
frontend rerun passed **134 tests in 14 files** and production build.

The final authoritative host-context `scripts/verify.ps1 -Mode Full` passed:
**1,171 backend tests**, zero skipped; **134 frontend tests in 14 files**, zero
skipped; Ruff lint/format, strict mypy over 174 files, database identities, pip
check, ESLint, TypeScript, production build, and `git diff --check`. Alembic
current and sole head were `0012_connector_persistence`; check reported no new
upgrade operations. Free disk was 21,746,765,824 bytes before and 21,746,151,424
bytes after the final Full run.
