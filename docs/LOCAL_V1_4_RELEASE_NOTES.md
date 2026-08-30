# Second Brain Local V1.4 release notes

Status: **Checkpoint 97 approved and complete after human review. Release
candidate ready for publication but not published.**

Candidate tag: `v1.4.0`

Candidate title: **Second Brain Local V1.4**

Release-candidate base: `49f6eaa78f2a1a27bf5e48d6d845c0f082e10d6f`

## Read-only Connectors and External Context

Local V1.4 adds one closed GitHub connector inside the existing trusted,
single-maintainer, loopback-only deployment. The operator configures an exact
non-empty selected-repository allowlist. The fixed production transport makes
GET requests only to `api.github.com` for authenticated-user identity,
repository metadata, issues, and pull requests. There is no repository
discovery, generic HTTP/GraphQL, redirect following, or external write.

External content is quarantined, versioned, and labeled untrusted. Every item
retains account, repository, immutable provider identity, application revision,
content hash, scope, last-seen/current-or-stale state, and sync provenance.
Deterministic equal-version replay is write-free; complete bounded refreshes
alone may infer absence, while partial or failed refreshes never do.

One explicit preview/confirm action may import exactly one current item revision
into the existing audited Source/SourceDocument/plain-text-chunk boundary.
Import is network-free and idempotent. It creates no Memory, proposal, Approval,
Agent Run, or Automation. Existing proposal generation, human review, and
explicit promotion remain separate.

Optional connector refresh schedules are disabled drafts by default. An
operator must explicitly enable them and explicitly invoke the existing bounded
scheduler command. Connector occurrences do not create Agent Runs or imports;
restart uses fenced leases and has no replay-all behavior.

## Credential architecture and least privilege

GitHub credentials live only in the current Windows user's OS credential store.
PostgreSQL stores an opaque `sbcred:v1:...` reference and safe metadata, never a
token. Browser storage, exports, diagnostics, notifications, logs, exceptions,
and public schemas exclude both tokens and credential references.

Create a fine-grained PAT directly in GitHub with an explicit expiry, selected
repositories only, and only the read permissions needed for repository
metadata, issues, and pull requests. Install it through
`scripts/manage-credential.ps1`; replacement and revocation are explicit, and
there is no automatic token refresh. Revocation prevents manual and scheduled
provider access while preserving locally quarantined history and previously
imported local documents.

Residual risk: the approved bounded GitHub endpoints cannot provide a complete
inventory of fine-grained-PAT grants. Successful validation proves usability
for configured repositories, not absence of additional provider-side grants.
Operator review, expiry, replacement, and revocation remain necessary even
though application authority is independently fixed to the GET-only allowlist.

## Compatibility, security, and acceptance

- Alembic advances additively through `0014_connector_refresh_schedules`.
- Tool Registry remains `agent-tools-v1`; Agents and Automations have no direct
  connector Tool or ExternalItem access.
- Project export remains `second-brain-project-export` version `1`. Connector
  configuration/runtime/snapshots/import provenance/scheduling and credential
  references remain excluded. Imported ordinary Sources/Documents follow only
  existing export-v1 semantics.
- The deterministic C01-C18 manifest covers credential leakage, least privilege,
  identity and scope isolation, injection, bounded transport, reconciliation,
  scheduling, export exclusion, and zero external/reviewed-local mutation.
- Checkpoint 96 joined acceptance covers configuration, manual refresh, browse,
  history/reconciliation, explicit import, optional scheduling, restart/failure,
  isolation, and frontend operator journeys using only fake credential and
  GitHub boundaries.

Checkpoint 97 additionally verified a fresh Python 3.12/project install,
application imports, Python and npm dependency security, locked frontend build,
complete tracked-content/secret inventory, a real read-only export validation,
synthetic OS credential install/read/replace/revoke cleanup, PostgreSQL
custom-format backup listing, stopped-service data retention, loopback API/Vite
readiness, and the complete local verification contract. Detailed evidence is
in [checkpoint-97-report.md](checkpoint-97-report.md).

## Known limitations and excluded scope

The release does not include source code or commit diffs, Actions logs or
artifacts, comments, organizations/members/email, packages, administration,
webhooks, repository discovery, external writes, direct Agent connector Tools,
automatic or bulk import, automatic Memory/proposal creation, Gmail, Calendar,
authentication, multi-user isolation, or remote/cloud operation. Connector
snapshots and database backups may contain private repository content and must
be protected. See [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

## Upgrade and recovery

Back up PostgreSQL in custom format and verify it with `pg_restore --list`
before upgrade or recovery. Start PostgreSQL through `scripts/dev-up.ps1`, then
verify both database identities and run Alembic to the sole head
`0014_connector_refresh_schedules`. Never downgrade or recreate the development
database and never delete `second-brain_postgres_data`.

OS credentials are outside PostgreSQL and Project export; reinstall or replace
the exact credential explicitly after machine recovery. A machine-level backup
may independently include OS-protected credentials and must preserve platform
protections. Disabling/revoking an account is the safe connector rollback;
quarantined snapshots and imported local documents remain locally readable.
V1.3.0 remains the preceding published recovery release, but recovery must use
a separate checkout and identity-verified backup rather than downgrading the
development database.

No tag or GitHub Release was created while preparing these notes.
