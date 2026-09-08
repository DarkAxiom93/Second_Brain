# Checkpoint 111 report - Context Hub API and typed pagination/filtering

Status: **Implemented; pending human review.** CP112 has not started.

## Preflight

- Clean synchronized `main` at exact HEAD
  `f5f3afac5e8e60e11e9896bf891e3c8d06f39939` with `0 0` divergence.
- GitHub Actions run `34048341062` was `completed` / `success` for that exact
  SHA.
- Sole Alembic head `0016_calendar_event_observations`, Tool Registry
  `agent-tools-v1`, and Project export `second-brain-project-export` version `1`.

## Exact public surface

- `POST /context-hub/query` accepts one closed `ContextHubPageRequest` and
  returns fixed-order typed family groups plus a nullable opaque cursor.
- `POST /context-hub/detail` accepts exact scope, family, and opaque reopen ID,
  then revalidates the complete CP110 immutable provenance relationship.
- `POST /context-hub/facets` accepts the closed CP110 query/filter envelope and
  returns only sorted family, kind, trust, and state buckets with an
  `observed_at` request-time timestamp.

Every route rejects non-loopback peers, starts `SET TRANSACTION READ ONLY`, and
rolls back before closing its request-owned session. Validation, cursor, not-
found, and database errors are content-free and reveal no rejected input, SQL,
exception, secret, credential reference, or hidden provider identifier.

## Cursor and keyset contract

Cursor version `1` is confidential and authenticated with AES-GCM using
application secret material and distinct code-owned domain separation. The
pre-commit security audit rejected the original unpublished ad hoc
`SHA-256(domain || password)` derivation. CP111 now uses the existing
`cryptography` implementation of PBKDF2-HMAC-SHA256 with a fixed code-owned
100,000-iteration policy and a 32-byte AES-256 key. Every token receives a
fresh 16-byte operating-system CSPRNG salt and a separate fresh 12-byte
AES-GCM nonce. The salt is the only non-secret KDF input carried outside the
ciphertext.

Cursor tokens use the code-owned
`second-brain:context-hub:cursor:v1` domain and reopen tokens use
`second-brain:context-hub:reopen:v1`. The domain is included in the PBKDF2 salt
input and AES-GCM AAD. Token version, domain, KDF name, and iteration policy are
also inside the authenticated ciphertext and must exactly match code-owned
values. Iterations are never read from the token or selected by the client.
Salt mutation changes both the derived key and AAD and therefore fails
authentication. Derived key bytes exist only for the in-memory cryptographic
operation and are never logged, serialized, persisted, returned, or committed.

The cursor
contains only the validated canonical request and per-selected-family native
position/exhaustion state. The request binding includes contract version, exact
Project or explicit-unassigned scope, normalized query, sorted families/kinds/
trust/states, exact page size, and `family-native-v1` ordering mode. Input is
limited to 4,096 characters. Authentication failure, malformed shape/type,
unknown version, family/position mismatch, changed request, or cross-scope
replay returns deterministic HTTP 422.

The token key is derived in memory from the runtime `postgres_password`, the
per-token salt, and the separate cursor or reopen domain; no key, password,
nonce seed, salt seed, or `.env` value is committed by CP111. Consequently,
cursors and reopen IDs survive an application restart while that runtime secret
is unchanged. Changing the configured PostgreSQL password intentionally
invalidates outstanding tokens, which then fail authentication and require a
fresh query. These are bounded API transport capabilities, not the immutable
provenance itself: CP110 provenance remains authoritative in PostgreSQL and can
be projected into a new token independently. Each encryption uses a fresh
96-bit nonce and independent 128-bit salt from the operating system CSPRNG;
neither is deterministically seeded or stored outside the transport envelope.

The SQL predicates exactly follow CP110:

- local: rows after `(created_at DESC, source_id ASC, chunk_index ASC,
  chunk_id ASC)` use earlier `created_at`, or lexicographically greater values
  at each equal prefix;
- GitHub and Calendar: rows after `(application_revision DESC, revision UUID
  DESC)` use a smaller revision, or a smaller UUID at equal revision.

There is no offset or universal rank. Each group advances independently,
preserves `local_source`, `github`, `google_calendar` order, and never re-emits
an already-passed tuple. Exhausted families remain exhausted in later pages.

## Public reopen identity and facets

The reopen ID is a separate confidential authenticated version-1 token bound to
the exact scope and full typed CP110 provenance. Encryption prevents the public
token from disclosing account, provider-item, occurrence, evidence, or internal
revision identifiers. Detail additionally requires the caller's closed family
and revalidates authoritative scope, ownership, immutable revision/document/
chunk/observation relationships, and Calendar evidence eligibility. Forgery,
cross-family substitution, cross-scope replay, and stale evidence fail as one
safe not-found response.

Facets reuse the same adapters, scope, query, family, kind, trust, state, and
native-state derivation. Buckets are code-owned and deterministically sorted;
counts are request-time observations rather than snapshots. Work remains capped
at 200 native candidates per selected family, with at most three families; a
domain that cannot be counted exactly within that cap fails closed instead of
returning partial or misleading counts.
Free-form fields, grouping, expressions, sorts, SQL, and provider queries do not
exist in the schema.

## Concurrency and authority boundary

PostgreSQL read committed applies independently to each request/page. Inserts
or reconciliation committed between pages may become visible only if they fall
after the saved native keyset; earlier inserts need a fresh walk. This avoids
duplicates but does not promise a snapshot. Each detail read independently
revalidates provenance and Calendar evidence, so concurrency cannot broaden
scope, substitute provenance, collapse trust, or fabricate state.

The route dependency graph adds zero GitHub, Google, credential-store, generic
network, model, or embedding call. It exposes no refresh, import, provider
write, Source/Memory/Approval mutation, Agent Run, Automation, schedule, Tool,
or export action. Context Hub remains absent from `agent-tools-v1`, Agent and
Automation catalogs, and export version 1. There is no table, projection, index,
migration, schema change, dependency addition, or second source of truth.

## Limits

- query: 256 characters and 768 UTF-8 bytes;
- page size: 1-50 per selected family;
- selected families/kinds/states/trust labels: 3/5/4/2;
- cursor and reopen ID: 4,096 characters each;
- title/text: 500/4,000 characters;
- bounded adapter/facet work: 200 native candidates per selected family.

## Changed paths

- `app/api/router.py`
- `app/api/routes/context_hub.py`
- `app/context_hub/models.py`
- `app/context_hub/service.py`
- `app/context_hub/tokens.py`
- `app/main.py`
- `tests/test_context_hub.py`
- `tests/integration/test_context_hub.py`
- `tests/test_memory_routes.py`
- `tests/test_project_routes.py`
- `docs/ARCHITECTURE.md`
- `docs/CHECKPOINTS.md`
- `docs/ROADMAP.md`
- `docs/checkpoint-111-report.md`

## Verification

Focused CP110/CP111 contract, PostgreSQL API, and route-inventory selection:
**21 passed**, zero skipped (one framework deprecation warning). The focused
set includes PBKDF2 restart/password lifecycle, fresh salt and nonce, domain
substitution, mutation/truncation/malformed/oversized/version rejection,
code-owned parameters, secret non-exposure, and request/scope/family binding.
The two canonical-transport regression nodes also passed **20 consecutive
repeated runs** (40 node executions) with no randomness-dependent failure.

The first Full run passed pip integrity, Ruff, formatting, and strict mypy, then
reported **1,346 passed / 4 failed / 7 errors**. One CP111 test incorrectly
committed synthetic records without guaranteed cleanup, causing seven later
fixture errors; two exact route inventories needed the approved CP111 paths;
and the known restricted-context Windows Credential Manager check returned
`credential_store_locked`. The CP111 test now cleans only its exact captured
Project UUIDs in `finally`, and the route inventories are updated. Final Full
verification then passed: `pip check`; Ruff lint and format over 493 files;
strict mypy over 208 production files; **1,357 backend tests passed**, zero
skipped (14 warnings); Alembic current/head/check at
`0016_calendar_event_observations` with no upgrade operations; frontend ESLint,
TypeScript, **148 tests across 15 files**, the 88-module production build; and
`git diff --check`.

Live loopback Uvicorn smoke passed: `GET /health` returned `200` / `ok`, and
`POST /context-hub/query` with explicit unassigned local scope returned `200`,
`context-hub-v1`, one family group, and a correctly null exhausted cursor. The
server was stopped cleanly after the smoke.

After the PBKDF2 remediation, final Full verification passed again: dependency
integrity; Ruff lint and format over 493 files; strict mypy over 208 production
files; **1,359 backend tests passed**, zero skipped (13 warnings); Alembic
current/heads/check at `0016_calendar_event_observations` with no upgrade
operations; frontend ESLint and TypeScript; **148 tests across 15 files**; the
88-module production build; and `git diff --check`.

Exact push CI run `34259425918` for commit
`eaec944e5eb2a7389bc5f18774032588c83bfb9e` subsequently failed only at
`test_cursor_is_opaque_bound_and_strictly_validated` after **917 passed / 1
failed / 1 deselected** in Quick verification. The test changed only the final
unpadded Base64URL character. Some alternate final characters change only
unused pad bits, so Python's strict decoder can produce the same authenticated
bytes from two textual spellings. AES-GCM was not bypassed: salt, nonce,
ciphertext, tag, plaintext, and authentication result were identical.

The production decoder now re-encodes decoded bytes with the exact code-owned
unpadded Base64URL encoder and requires byte-for-byte textual equality before
decrypting. Alternate pad-bit spellings, supplied padding, and other textual
aliases therefore fail as `ContextTokenError`. Regression coverage separately
uses a canonical byte-changing ciphertext mutation that must fail AES-GCM and a
deliberately constructed non-canonical alias proven to decode to the same raw
bytes; both cursor and reopen domains reject aliases and padded forms while
canonical tokens continue to decode. Final post-remediation Full verification
passed: dependency integrity; Ruff lint and format over 493 files; strict mypy
over 208 production files; **1,360 backend tests passed**, zero skipped (13
warnings); Alembic current/heads/check at
`0016_calendar_event_observations` with no upgrade operations; frontend ESLint
and TypeScript; **148 tests across 15 files**; the 88-module production build;
and `git diff --check`.

## Residual risk

Read-committed traversal is intentionally not a durable snapshot. A concurrent
insert before a saved keyset is visible only in a fresh query. Direct bounded
`ILIKE` and Calendar evidence evaluation retain CP110's measured work boundary;
any future index/projection remains a separately reviewed architecture change.
