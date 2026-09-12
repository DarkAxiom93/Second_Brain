# Second Brain Local V1.6 release notes

Published tag: `v1.6.0`

Release title: **Second Brain Local V1.6**

Status: **Published.** Annotated tag object
`3d2bc5f774729459f89db7187f407db1b273c9dd` peels to exact release commit
`64c8215d142ba66f7788d2a71f3debf291cd9862`. GitHub Release `387495253` was
published at `2026-09-12T07:46:12Z`; it is neither a draft nor a prerelease and
has zero assets:
<https://github.com/DarkAxiom93/Second_Brain/releases/tag/v1.6.0>

Local V1.5 `v1.5.0` is the preceding recovery release.

## Unified Read-only Context Hub

Local V1.6 adds one loopback-only Context Hub for finding and reopening
already-held context from three fixed families, in fixed order:

1. audited local `Source` / `SourceDocument` / `SourceChunk` knowledge;
2. quarantined GitHub repository, issue, and pull-request context; and
3. privacy-minimized quarantined Google Calendar event context.

Every request chooses exactly one Project or explicit unassigned scope. Results
keep application-owned `local_audited` or `quarantined_external` trust, native
family state/freshness, and immutable native provenance. There is no universal
score or trust upgrade; hostile external content remains inert,
non-authoritative plain text.

The Hub is read-only and local-only. Its reads perform no GitHub, Google, OAuth,
credential-store, network, model, or embedding request. The Hub cannot import,
refresh, write, schedule, or create knowledge/workflow state. It is absent from
the seven-definition `agent-tools-v1` registry and grants no Agent, Automation,
Tool, or evidence authority.

## Compatibility, upgrade, and recovery

V1.6 adds no schema or migration. The sole Alembic head remains
`0016_calendar_event_observations`; normal upgrade, startup, and restart steps
are unchanged. Hub state needs no backup or recovery because the Hub owns no
persistence. Authoritative local, GitHub, and Calendar records remain in their
existing systems.

Project export remains `second-brain-project-export` version `1`. It retains
the existing audited local contract and excludes Hub runtime/token state,
GitHub connector/runtime/account/reconciliation state, Calendar OAuth/account/
revision/observation/runtime state, credentials, and private provider
identifiers outside that contract.

On Windows, credential tests execute in the current user's Credential Manager
context. A restricted sandbox can report `credential_store_locked`; do not
weaken or skip that gate. Run final verification from the authorized
interactive maintainer context when necessary.

Rollback removes or reverts the additive Context Hub service/routes/UI. It does
not rewrite, migrate, delete, or take ownership of local Source, GitHub, or
Calendar records. Never downgrade or restore over the development database.

## Release identities and omissions

- baseline before CP115: `f21e01ea8afe4fa5797a63f8b717d6f0f93a66fb`;
- Tool Registry: `agent-tools-v1`, exactly seven definitions;
- Project export: `second-brain-project-export`, version `1`;
- Alembic head: `0016_calendar_event_observations`;
- Google OAuth scopes unchanged: `openid` and
  `https://www.googleapis.com/auth/calendar.events.readonly`;
- no product capability or production-code addition in CP115; and
- publication introduced no product capability or production authority change.
