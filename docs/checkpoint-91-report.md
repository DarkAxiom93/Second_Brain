# Checkpoint 91 report - bounded GitHub read transport and manual sync

Status: **Approved and complete after human review.**

## Outcome and boundary

Checkpoint 91 adds one explicit synchronous manual refresh for an enabled,
revision-matched GitHub ConnectorAccount. It uses the existing
`0012_connector_persistence` schema and appends only quarantined ExternalItem
revisions plus safe ConnectorSyncRun/account-validation metadata. It adds no
migration, generic proxy, external write, scheduling, import, reconciliation or
deletion inference, Agent/Automation authority, Tool Registry change, or
Checkpoint 92 behavior.

The only dependency-scope change moves the already pinned `httpx==0.28.1` from
the dev extra to runtime dependencies. Its version and all other dependencies
are unchanged.

## Closed transport and hard bounds

The production transport exposes four typed reads only:

- `GET /user`
- `GET /repos/{configured_owner}/{configured_repository}`
- `GET /repos/{configured_owner}/{configured_repository}/issues` with
  code-owned `state=all`, `per_page=50`, and page number
- `GET /repos/{configured_owner}/{configured_repository}/pulls` with the same
  code-owned list parameters

It fixes the host to `https://api.github.com`, disables redirects, and fixes the
GitHub JSON Accept header, API version `2022-11-28`, User-Agent, and
`Accept-Encoding: identity`. No public transport method accepts a URL, host,
method, header, body, GraphQL/query language, continuation URL, or discovery
request. `/issues` entries containing the GitHub pull-request marker are
excluded so a PR is ingested only through `/pulls`. Comments remain disabled.

The code-owned bounds are page size 50, at most two issue pages and two pull
pages per exact repository, 2,000 accepted records per run, 128 attempts
including retry attempts, 2 MiB decoded bytes per response, 32 MiB decoded
bytes per run, and a 60-second overall sync deadline. Exactly one retry is
allowed for connect/timeout and 502/503/504 failures. Authentication,
authorization, 404 ambiguity, redirect, rate limit, identity, schema/JSON,
content-size, and revision/scope failures are never retried. Rate-limit reset
values are never slept on or trusted.

## Credential, claim, and fencing boundary

Refresh reads exactly the account's Checkpoint 88 opaque reference through
CredentialStore after the claim commits. There is no enumeration, install,
replacement, or deletion path. Authorization is constructed only inside the
fixed GET transport; invalid secret bytes fail before HTTP. The mutable secret
bytearray is overwritten in `finally`. API schemas, database rows, UI state,
logs, errors, exports, and diagnostics expose no token, reference, header, or
derivative. `httpx` and `httpcore` request logging is held at warning to prevent
repository URL logging.

The short claim transaction takes the exact account row lock and a fixed
PostgreSQL advisory transaction lock. It requires lifecycle `enabled`, exact
`expected_revision`, internally consistent account fingerprint, current
code-owned permission fingerprint, valid exact allowlist, no active run for the
account, and fewer than four global active runs. It creates one manual run with
safe trigger identity `operator_manual_refresh` and commits before credential or
network latency. No database lock or transaction spans either boundary.

Despite its schema-compatible name, `granted_scope_fingerprint` is the SHA-256
fingerprint of exactly the application-owned names `metadata_read`,
`issues_read`, and `pull_requests_read`. It is not derived from the credential,
GitHub response headers, or a provider-reported grant inventory. In particular,
`X-Accepted-GitHub-Permissions` describes endpoint requirements and is discarded;
it is not evidence of permissions granted to the PAT.

Before user/repository/list requests and before each page transaction, the
coordinator revalidates account existence, enabled lifecycle, captured revision,
provider/account identity, exact nullable Project scope, permission fingerprint,
and repository membership. Drift prevents the next request or persistence.

## Identity, quarantine, replay, and page atomicity

The authenticated GitHub login is compared to configured identity using
case-insensitive GitHub semantics. Every exact configured repository response
must return the same canonical `owner/repository`, and its immutable numeric ID
must match any prior snapshot for that configured name. Redirect,
rename/transfer ambiguity, recreated numeric identity, missing access, and
account mismatch fail closed. Complete repository validation may update only
`validation_status=valid` and `last_validated_at`; it does not increment the
configuration revision. Here `valid` means credential usability, authenticated
account identity, configured repository access and immutable identity, and the
closed application read policy were validated. It does not mean the application
proved the PAT has no additional GitHub permissions or repository grants.
Identity/access failures fence a still-matching account as disabled/invalid
without guessing expired versus revoked.

Repository snapshots contain only `private`, `archived`, and description.
Issue/pull snapshots contain immutable numeric ID, number, title, body, closed
state, and strict GitHub `updated_at`-derived source version. Application-owned
identities use `github_repo:<numeric_id>`, `github_issue:<numeric_id>`, and
`github_pull:<numeric_id>`. Raw JSON, response headers, URLs, authorization data,
and unknown fields are not persisted. Text is size-checked without truncation
and remains inert untrusted quarantine content.

Each complete provider page is normalized and validated before its short
transaction. The transaction rechecks captured account/scope/allowlist, applies
the Checkpoint 89 replay primitive, and updates safe run counts. Exact
provider-version/content replay is write-free; changed content/version appends
the next deterministic application revision. Earlier committed pages remain if
a later page fails, but the run cannot report complete success. No prior item is
marked stale or deleted.

## Run, API, and UI contracts

`POST /connector-accounts/{account_id}/refresh` accepts only
`expected_revision` and returns allowlisted ConnectorSyncRun IDs, captured
revision, manual trigger kind, closed status, safe counts/error code,
reconciliation boolean, and timestamps. The read-only
`GET /connector-accounts/{account_id}/sync-status` returns only the latest same
safe projection for reload persistence.

Exhaustive reads finish `succeeded` with `reconciliation_complete=true`.
Pagination/item/request/deadline/run-byte ceilings finish `incomplete`.
Credential, identity, invalid/oversized response, rate-limit, timeout, and outage
failures finish `failed`. Every non-success has
`reconciliation_complete=false`. Safe codes cover credential failures, account
drift, provider authentication/access/rate-limit/outage/identity failures,
invalid or oversized response/items, and all approved ceilings. Capacity and
active-account claim conflicts return a content-free 409 before a run or request
exists.

Settings exposes Refresh only for enabled accounts, disables that account's
controls while active, shows only safe final state/counts/error code, and then
reloads account metadata. The client uses a dedicated 65-second timeout for the
server's 60-second budget plus response margin. There is no polling, browser
storage, credential rendering, or ExternalItem content UI.

## Security acceptance advanced

- **C01/C06/C15:** exact-reference lookup, final-boundary Authorization,
  bytearray cleanup, safe closed errors, and request-log suppression.
- **C02/C03/C17:** fixed application-policy fingerprint, exact allowlist, closed
  endpoint inventory, no caller-defined request capability, and provider
  permission headers discarded rather than treated as grant evidence.
- **C04/C10:** bounded normalized content remains inert quarantine and is never
  rendered or given to an Agent.
- **C05:** captured nullable Project equality and per-page fencing preserve
  exact assigned/unassigned scope.
- **C07:** one-active-run barrier and exact write-free replay versus deterministic
  changed revision.
- **C08/C09:** fixed pages/items/attempts/bytes/deadline/retry bounds and no
  automatic rate-limit wait/retry.
- **C11:** authenticated-login, canonical repository name, immutable numeric
  repository identity, fixed-host TLS, and redirect rejection.
- **C12/C14:** completeness is explicit; partial/outage results preserve prior
  snapshots and infer no deletion.
- **C13:** manual route only; no scheduler, occurrence, Automation, or Agent Run.
- **C16:** export name/version and connector-table exclusion remain unchanged.
- **C18:** GET-only inventory and protected-domain snapshots prove zero
  reviewed-local or external mutation.

## Verification evidence

Focused verification passed with zero skips: **62 backend tests** and **20
frontend tests in 3 files**. Repository-wide Ruff lint/format, strict mypy over
173 production files, frontend ESLint, and TypeScript checks passed.

The first sandbox Full attempt correctly exposed two stale OpenAPI route
inventories, which were fixed and focused-tested, while the pre-existing Windows
Credential Manager probe reported the expected sandbox-only
`credential_store_locked`. The final authoritative supported host-context
`./scripts/verify.ps1 -Mode Full` completed successfully:

- canonical development/test database identities and `pip check`: passed;
- Ruff lint/format and strict mypy over 173 production files: passed;
- backend: **1,169 passed, zero skipped** (11 warnings after the final C02 audit);
- Alembic current and sole head: `0012_connector_persistence`;
- Alembic check: no new upgrade operations;
- frontend ESLint and TypeScript: passed;
- frontend Vitest: **133 passed in 13 files, zero skipped**;
- frontend production build and final `git diff --check`: passed.

Disk headroom was 25.02 GiB before focused verification, 25.01 GiB before the
authoritative host Full run, and 25.01 GiB at final audit. All changed files
were non-empty and NUL-free before focused/Full verification and at final audit.
No disk-corrupted file required reconstruction after the earlier environment-
only `os error 112` stop.

Tool Registry remains `agent-tools-v1`; Project export remains
`second-brain-project-export` version `1`. Automated tests used only fake
CredentialStore instances and fake/Mock GitHub transports and made no real
GitHub request or used any real GitHub credential. Final changed paths, exact
diff totals, and unstaged Git status are recorded in the final handoff.

Residual C02/C06 risk remains: an operator may install a fine-grained PAT with
additional permissions or repository grants that GitHub does not positively
enumerate through the approved bounded endpoints. Successful exact-repository
access cannot prove absence of other access. Mitigation is application-enforced
GET-only authority, exact configured repository addressing, external token
least-privilege/expiry/revocation discipline, and explicit operator review—not
an unsupported claim of provider-token grant verification.

The final focused C02 audit added a hostile-header regression proving that
`X-Accepted-GitHub-Permissions` and `X-OAuth-Scopes` are discarded and cannot
alter the application policy fingerprint or typed transport result. Its focused
backend set passed **50 tests, zero skipped**; the subsequent authoritative Full
run is the 1,169/133 zero-skip evidence above.
