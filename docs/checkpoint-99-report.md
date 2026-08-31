# Checkpoint 99 report - Google OAuth account-identity blocker

Status: **Architecture gate remediated in documentation; production
implementation not started and checkpoint not complete.**

## Outcome

Checkpoint 99 stopped at its mandatory provider-contract and account-identity
gate. No officially documented stable Google Account identity is available
under only the approved scope:

`https://www.googleapis.com/auth/calendar.events.readonly`

Google documents that scope as authority to view Calendar events. Google
documents the stable, never-reused account identifier as the OpenID Connect ID
token `sub` claim, and obtaining OpenID identity requires the additional
`openid` scope. The Google `tokeninfo` endpoint is documented as an ID-token
debugging validator, not as a production account-identity service for a
Calendar-only access token.

The Calendar `calendars.get` method is not an acceptable substitute. It requires
one of the broader Calendar scopes, including `calendar.readonly` or
`calendar.calendars.readonly`; it does not accept the approved
`calendar.events.readonly` scope. Calling it would also violate Checkpoint 99's
explicit prohibition on Calendar data requests.

Therefore the CP98 account-substitution invariant could not be implemented while
simultaneously preserving the originally approved scope and the CP99 no-Calendar-
data boundary. The gate correctly stopped implementation rather than silently
adding `openid`, `email`, `profile`, a broader Calendar scope, or an undocumented
identity mechanism. No implementation occurred before architecture remediation.

## Human-approved architecture remediation

The architecture is amended to authorize exactly these two OAuth scopes:

- `openid`, solely to obtain and validate the stable Google `sub`; and
- `https://www.googleapis.com/auth/calendar.events.readonly`, solely for the
  later approved Calendar events-list lifecycle.

`email`, `profile`, `calendar`, `calendar.readonly`, CalendarList and calendar
metadata scopes, Gmail, Drive, Contacts, generic Google scopes, and every write
scope remain prohibited. This amendment authorizes no broader Calendar data
access, profile collection, userinfo request, or production request.

The corrected identity gate requires an ID token from the authorization-code
flow and a supported Google OpenID Connect validation library. Validation must
cover the trusted Google issuer, exact application client audience, expiration
and issued-at validity, fresh authorization-attempt nonce, and a non-empty
bounded `sub`. Application code uses `sub` as the sole provider identity input,
ignores and discards all unapproved claims, and never persists the ID token or
raw provider authentication response. Email is neither requested nor used as
identity. Userinfo, Calendar metadata and CalendarList are not authorized as
fallbacks. A validation library that requires any such authority is an
implementation blocker.

The version-1 stable account fingerprint is:

1. Form the exact string `second-brain:google-account:v1:<sub>`, substituting
   the fully validated Google `sub` without other transformation.
2. Encode that string as UTF-8.
3. Compute SHA-256 and serialize the digest as lowercase hexadecimal.

No client secret, access token, refresh token, email, or other claim contributes
to the fingerprint. Future persistence contains only the non-secret fingerprint,
preferably never raw `sub`. Reauthorization requires a fresh fully validated ID
token whose derived fingerprint exactly matches the credential/account being
replaced. A different `sub` is account substitution and fails closed while the
previous valid envelope is preserved.

Any JWK retrieval required by the selected official validation mechanism is
limited to fixed, code-owned, bounded GET access to Google's
`https://www.googleapis.com/oauth2/v3/certs`, outside database transactions.
Arbitrary OIDC discovery, issuer/JWK configuration, certificate URLs and
userinfo remain prohibited.

## Official Google contract findings

- Desktop installed applications may use the system browser, authorization-code
  flow, PKCE, and an ephemeral loopback redirect on `127.0.0.1`; Google documents
  loopback redirects as the recommended mechanism for Windows desktop apps.
- The reviewed authorization endpoint is
  `https://accounts.google.com/o/oauth2/v2/auth`.
- The reviewed token endpoint is `https://oauth2.googleapis.com/token`.
- Google's installed-app documentation describes revocation through
  `https://oauth2.googleapis.com/revoke`.
- The exact approved Calendar scope permits viewing events, but it grants no
  documented stable account identifier.
- OpenID Connect supplies stable identity through the ID-token `sub` claim and
  requires `openid`; the human amendment now approves only that minimal identity
  scope alongside the unchanged Calendar events-readonly scope. Email/profile
  claims require broader scopes that remain forbidden.

Official sources reviewed on 2026-08-31:

- <https://developers.google.com/identity/protocols/oauth2/native-app>
- <https://developers.google.com/workspace/calendar/api/auth>
- <https://developers.google.com/identity/openid-connect/openid-connect>
- <https://developers.google.com/identity/openid-connect/reference>
- <https://developers.google.com/workspace/calendar/api/v3/reference/calendars/get>

## Preflight evidence

- After an explicit fetch, `main`, `origin/main`, and `HEAD` were the approved
  CP98 commit `20805905f81ef1a9056a70b14df148d155e4472e` with a clean worktree.
- Exact push CI run `33358621056` for that SHA completed successfully.
- Parsed and live database identities were exactly `second_brain` and
  `second_brain_test` on `127.0.0.1:5433`.
- Alembic current and sole head were
  `0014_connector_refresh_schedules`; `alembic check` reported no new upgrade
  operations.
- Tool Registry was `agent-tools-v1`.
- Project export was `second-brain-project-export` version `1`.

## Change and safety inventory

The original gate produced only this report. The subsequent remediation changes
documentation only: the V1.5 roadmap and threat model, lifecycle summaries, the
CP98 historical report amendment note, and this report. No production code,
test, migration, dependency, configuration, credential-store behavior, API,
frontend, browser workflow, Calendar persistence, Calendar account table, event
API, refresh, sync, scheduling, import, Agent, Automation, Tool Registry, or
export behavior was added or changed. Checkpoint 100 was not started.

Exact changed paths for the combined blocker report and documentation-only
remediation are:

- `docs/ARCHITECTURE.md`
- `docs/CHECKPOINTS.md`
- `docs/ROADMAP.md`
- `docs/V1_5_CALENDAR_ROADMAP.md`
- `docs/V1_5_CALENDAR_THREAT_MODEL.md`
- `docs/checkpoint-98-report.md`
- `docs/checkpoint-99-report.md`

No real Google credential was read, printed, modified, or used. No OAuth,
token, revocation, identity, Calendar, or other Google request was made. No
Calendar data request occurred. PostgreSQL was used only for the required
identity and Alembic preflight and contains no CP99 state.

Focused and Full implementation verification were not run because the mandatory
architecture gate stopped the checkpoint before implementation and this
remediation is documentation-only. The preflight database, Alembic, identity,
clean-worktree, synchronization, and exact push-CI checks passed before the
blocker report was created. Documentation verification uses `git diff --check`
and consistency searches. Fake OAuth and secret-canary gates remain future CP99
implementation work.

This amendment is the human-approved architecture resolution, but it does not
complete or implement CP99. CP99 may resume only after the documentation
amendment is reviewed, committed, pushed, and its exact push CI is green. Until
then CP99 remains not implemented and CP100 remains not started.
