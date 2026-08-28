# Checkpoint 90 report - connector account lifecycle and safe UI

Status: **Approved and complete after human review.**

## Outcome and boundary

Checkpoint 90 adds metadata-only GitHub `ConnectorAccount` creation, list,
retrieve, disabled-only configuration, disable, re-enable, and terminal revoke
operations plus an accessible Settings flow. No migration, GitHub/network call,
credential-store lookup/deletion, live credential validation, ConnectorSyncRun,
ExternalItem access, import, external write, Agent/Automation capability, or
Checkpoint 91 work was added.

Public responses are constructed from an explicit allowlist: account ID,
provider, operator-supplied unvalidated external identity, exact Project or
explicit unassigned scope, repository allowlist, lifecycle, validation status,
revision, and safe timestamps. They contain no credential reference,
fingerprint, credential metadata, authorization state, or internal error text.
Connector request-validation failures use a closed content-free 422 because the
framework default would echo hostile rejected input.

## API contracts and lifecycle

- `POST /connector-accounts` creates exact provider `github`, lifecycle
  `disabled`, validation `unvalidated`, revision `0` from one write-only
  `sbcred:v1:<UUIDv4>` reference, one exact Project or explicit unassigned
  scope, and 1-32 canonical `owner/repository` entries.
- `GET /connector-accounts?limit=&offset=` lists safe projections in
  `created_at DESC, id DESC` order; `GET /connector-accounts/{id}` retrieves one.
- `PATCH /connector-accounts/{id}` accepts only `expected_revision`, optional
  exact scope, and optional repository allowlist. It is allowed only while
  disabled and with no active pre-existing sync claim; it resets validation to
  `unvalidated` and never remaps historical rows.
- `POST /connector-accounts/{id}/disable`, `/re-enable`, and `/revoke` accept
  only `expected_revision`.

| Current | Action | Result |
|---|---|---|
| `disabled` | re-enable | `enabled` |
| `disabled` | revoke | `revoked` |
| `enabled` | disable | `disabled` |
| `enabled` | revoke | `revoked` |
| `revoked` | any lifecycle/configuration action | conflict |
| any other same-state/invalid transition | lifecycle conflict |

Every successful lifecycle/configuration mutation locks the account row,
compares the exact expected revision, and increments revision exactly once.
Concurrent same-revision mutations yield one success and one closed 409.
Disabling changes the captured revision and lifecycle, fencing later sync
eligibility; Checkpoint 90 itself creates no sync claim.

## Safe Settings behavior

Settings explains that credentials must be installed with
`scripts/manage-credential.ps1`, accepts only the opaque reference, labels the
external identity as operator-supplied/unvalidated, requires explicit
Unassigned-or-Project scope and repository lines, and clears the reference
after successful or failed submission. It lists safe status and supports
disable, re-enable, and confirmed terminal revoke. A stale 409 triggers one
explicit authoritative refresh and asks the operator to review current state.
There is no polling, service worker, external configuration link, or use of
localStorage, sessionStorage, IndexedDB, cookies, or other browser persistence.

## Security acceptance advanced

- **C01/C06/C15:** opaque reference is write-only at the API, never serialized,
  cleared from UI state, and hostile validation receives content-free errors.
- **C02/C03/C17:** provider, permissions, scope shape, repository syntax, fields,
  and lifecycle are closed/application-owned; configuration grants no runtime
  authority.
- **C04/C10:** hostile and secret-shaped metadata is rejected and no external
  content becomes accessible.
- **C05:** one exact existing Project or explicit unassigned scope is required;
  null is never interpreted as unrestricted.
- **C07/C13/C14:** row locks plus revision CAS fence stale configuration and
  lifecycle requests; disabled/revoked accounts fail closed for future work.
- **C08/C09/C11/C12:** no transport, pagination, retry, provider identity
  validation, or reconciliation behavior was introduced.
- **C16:** Project export identity/version and exclusion remain unchanged.
- **C18:** protected-domain snapshots remain unchanged and no sync run or
  external item is created.

## Verification evidence

Focused connector/API/route verification: **38 passed, zero skipped** (one
upstream TestClient deprecation warning). Focused Settings/connector frontend
verification: **13 passed in 2 files, zero skipped**. The tests cover creation,
list/retrieve, exact initial states/provider, explicit scope, allowlist bounds,
hostile/reference privacy, closed request fields/errors, lifecycle matrix,
terminal revoke, stale and concurrent CAS, disabled-only configuration,
active-sync fencing, zero sync/item/protected-domain mutation, no network,
accessible UI actions, confirmation, conflict reconciliation, transient
reference clearing, and zero browser-storage writes.

The authoritative host-context `./scripts/verify.ps1 -Mode Full` completed
successfully:

- verified live development/test database identities and `pip check`: passed;
- Ruff lint/format and strict mypy over 170 source files: passed;
- backend: **1,142 passed, zero skipped** (13 warnings);
- Alembic current and sole head: `0012_connector_persistence`;
- Alembic check: no new upgrade operations;
- frontend ESLint and TypeScript: passed;
- frontend Vitest: **131 passed in 13 files, zero skipped**;
- frontend production build and final `git diff --check`: passed.

The earlier focused sandbox attempt correctly reported the pre-existing
Checkpoint 88 Windows credential probe as `credential_store_locked`; the exact
test passed in the authoritative supported host-context Full run. No assertion
was weakened and no test was skipped.

Tool Registry remains `agent-tools-v1`; Project export remains
`second-brain-project-export` version `1`. Exact diff summary and final Git
status are recorded in the final handoff.
