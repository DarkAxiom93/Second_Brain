# Checkpoint 99 report - Google OAuth and credential prerequisite

Status: **Approved and complete after human review.**

## Exact implementation boundary

Checkpoint 99 adds only the local Google installed-app OAuth and credential
prerequisite: authorization, safe status, same-account reauthorization, refresh-
token rotation, and explicit revocation. It adds no migration, Calendar account
or event persistence, Calendar request, public Calendar API/UI, browser
credential storage, sync, reconciliation, import, scheduling, Agent/Automation
access, Tool Registry/export change, or Checkpoint 100 work.

After `git fetch --prune origin`, clean `main`, `HEAD`, and `origin/main` were
exactly `d9601109c3767e71a8992fe34c062660b256ad2f`. Exact push CI run
`33377284610` for that SHA was completed/successful. Live database identities
were `second_brain` and `second_brain_test` on `127.0.0.1:5433`. Alembic current
and sole head were `0014_connector_refresh_schedules`; `alembic check` found no
upgrade operations. Tool Registry remained `agent-tools-v1`; Project export
remained `second-brain-project-export` version `1`.

## OAuth/OIDC inventory and installed-app behavior

The only provider endpoints are:

- system-browser authorization:
  `https://accounts.google.com/o/oauth2/v2/auth`;
- bounded token exchange/refresh POST:
  `https://oauth2.googleapis.com/token`;
- bounded revocation POST: `https://oauth2.googleapis.com/revoke`;
- bounded cached JWK GET: `https://www.googleapis.com/oauth2/v3/certs`.

The requested and accepted scope set is exactly `openid` and
`https://www.googleapis.com/auth/calendar.events.readonly`. Missing, additional,
email/profile, userinfo, generic Google, broader Calendar, CalendarList/metadata,
Gmail/Drive/Contacts, and write scopes fail closed. No arbitrary URL, host,
method, header, redirect target, provider, discovery, userinfo, or raw HTTP
escape hatch exists.

Each attempt creates fresh cryptographic verifier, state, and nonce values. PKCE
is S256. The system browser receives the fixed authorization origin and an OS-
selected `127.0.0.1` port with fixed `/oauth/google/callback` path. The bounded
listener accepts one exact `code` and `state`, rejects wrong/absolute paths,
duplicate/extra parameters, OAuth-error ambiguity and replay, and closes on
success, failure, timeout, cancellation, or browser failure. Provider/store
latency occurs without SQL transactions or locks.

## ID-token validation and fingerprint proof

`PyJWT[crypto]==2.10.1` is the sole new direct dependency. It is the smallest
pinned addition for RS256/JWK signature and registered-claim validation; JWK
retrieval, endpoint/cache/bounds, issuer/audience/time/nonce policy, and claim
minimization remain application-owned.

Validation permits only RS256, an exact single `kid` from the fixed JWK set, a
trusted Google issuer, exact configured audience, bounded expiration/issued-at,
the fresh attempt nonce, and a non-empty maximum-255-character string `sub`.
Forged, malformed, unknown-key, wrong issuer/audience/nonce/time, and invalid
subject tokens fail with content-free errors. Only the fingerprint survives;
raw `sub`, ID token, email, and all other claims are discarded.

The exact UTF-8 string `second-brain:google-account:v1:<sub>` is SHA-256 hashed
to lowercase hexadecimal. The deterministic `sub = "abc"` vector is
`b6abc4eb824ae8a436da6ff9a3264777b8232631d76de1cc70f10838b45c51cc`.

## Envelope, rotation, fencing, and operator lifecycle

The CP88 non-enumerating Windows per-user store is reused. Its strict, bounded
version-1 envelope contains only version, monotonic generation, refresh token,
and non-secret fingerprint. Access tokens remain memory-only. Refresh performs
provider latency outside the per-reference lock, then rereads under the lock and
atomically replaces only if the captured generation matches. Rotated refresh
tokens replace old tokens; stale concurrent refresh is fenced. No background
refresh exists.

Reauthorization fully repeats PKCE and ID-token validation before replacement.
Only an identical derived fingerprint may replace the envelope; substitution
fails while preserving the prior credential. Revocation attempts provider
revocation and exact local deletion, reporting separate `provider_revoked` and
`local_deleted` booleans without leaking material or falsely reporting success.

The operator surface is `scripts/manage-google-calendar-credential.ps1` with
only `authorize`, `status`, `reauthorize`, and `revoke`. The non-secret desktop
client ID uses `GOOGLE_OAUTH_CLIENT_ID`. Output is limited to safe status, opaque
reference, fingerprint, generation, and the two revocation outcomes.

## Tests, canaries, and verification

`tests/test_google_oauth.py` contains 21 zero-network tests with fake OAuth/JWK/
token/revocation/store boundaries and synthetic RSA keys. They cover successful
two-scope PKCE/OIDC authorization; email/profile absence; issuer, audience,
nonce, issued-at, expiration, subject, forged/malformed/unknown-key failures;
fingerprint determinism; same/different-account reauthorization; refresh-token
rotation; barrier-driven stale-refresh fencing without sleeps; separate provider
and local revocation failures; fixed JWK caching; scope drift; callback path,
duplicate, ambiguity, absolute request, replay and timeout; envelope
minimization; and provider-body/error secret-canary non-leakage.

The canary test proves provider body and exception text cannot escape the safe
taxonomy. Envelope inspection proves access token, ID token, and email absence.
No OAuth secret field was added to PostgreSQL, export, logs, diagnostics,
reports, prompts, tracked fixtures, browser storage, or a public API.

Focused verification: **21 passed, 0 failed, 0 skipped**. Required Full
verification: **1,258 backend and 137 frontend passed, 0 failed, 0 skipped**;
pip check, Ruff lint/format, strict mypy, frontend lint/typecheck/build, Alembic
current/head/check, and `git diff --check` passed. A first sandboxed Full attempt
had 1,254 passes and one environmental Windows Credential Manager lock; that
exact test passed with OS-store access, and the final unrestricted Full run
passed completely.

## Exact changed paths

- `app/core/config.py`
- `app/credentials/__init__.py`
- `app/google_oauth/__init__.py`
- `app/google_oauth/contract.py`
- `app/google_oauth/envelope.py`
- `app/google_oauth/identity.py`
- `app/google_oauth/loopback.py`
- `app/google_oauth/operator.py`
- `app/google_oauth/service.py`
- `app/google_oauth/transport.py`
- `docs/ARCHITECTURE.md`
- `docs/CHECKPOINTS.md`
- `docs/ROADMAP.md`
- `docs/V1_5_CALENDAR_ROADMAP.md`
- `docs/checkpoint-99-report.md`
- `pyproject.toml`
- `scripts/README.md`
- `scripts/manage-google-calendar-credential.ps1`
- `tests/test_google_oauth.py`

No real Google credential was read, created, printed, modified, or used. No real
Google/OAuth/JWK/revocation/Calendar request occurred. No Calendar data request
occurred. There is no migration, Calendar persistence/API/UI/sync/import/
scheduling, Agent/Automation authority, registry/export change, or CP100 work.
Checkpoint 99 is approved and complete after human review. Checkpoint 100 was
not started.
