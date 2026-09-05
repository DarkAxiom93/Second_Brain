# Second Brain Local V1.5 release notes

Candidate tag: `v1.5.0`

Candidate title: **Second Brain Local V1.5**

Status: **Approved and publication-ready. Not published.**

## Read-only Calendar context

Local V1.5 adds one local, read-only Google Calendar context workflow. The
operator authorizes one account with exactly `openid` and
`https://www.googleapis.com/auth/calendar.events.readonly`, enters an exact
calendar allowlist, and explicitly starts each bounded refresh. External
Context then shows a minimized current/stale projection and immutable local
revision/observation history.

Ordinary events retain only the bounded title and temporal/recurrence fields
needed by the UI. Private and special events use fixed labels. Attendees,
organizer, description, location, conference links, attachments, reminders,
extended properties, provider payloads, and provider-content hyperlinks are
excluded. Calendar content remains quarantined from Memories, proposals,
Approvals, Agents, and Automations.

## Consent, revoke, and recovery

Authorization uses an installed-app PKCE flow, validates the signed ID-token
identity, and stores only a versioned refresh envelope in the Windows per-user
credential store. Disable, revoke, or reauthorization-required states fail
closed before Calendar access. Reauthorization must preserve the exact account
identity. Revocation removes the credential envelope while leaving minimized
historical Calendar evidence readable for local recovery and audit.

## Deliberate omissions and residual risk

CP102 manual refresh is the sole Calendar request trigger. V1.5 has no Calendar
write, import, scheduling, startup/background refresh, sync token, tombstone
ingestion, generic Google/provider executor, or Agent/Automation Calendar
authority. Future import or scheduling requires a separate reviewed capability.

Read-only Calendar data can still be highly sensitive. The OS credential store
cannot protect an authorized token from a compromised local operator session or
process, and database/machine backups may contain minimized snapshots. Operate
only inside the documented trusted single-maintainer loopback boundary and
protect backups accordingly.

## Release hardening

The approved dependency-security remediation pins `PyJWT[crypto]==2.13.0` and
`pypdf==6.16.1`. The release audit found no known shipped Python dependency or
frontend vulnerability. Project export remains
`second-brain-project-export` version `1`; all Calendar/OAuth runtime state and
provider identity material remain excluded. Alembic remains
`0016_calendar_event_observations` and Tool Registry remains `agent-tools-v1`.

No tag, GitHub Release, PR, push, or publication action is part of CP108.
