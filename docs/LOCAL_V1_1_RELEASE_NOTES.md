# Local V1.1 release notes

Status: release-hardened candidate pending human review. `v1.1.0` is not tagged
or published; tagging and publication require separate explicit approval.

## What changed since v1.0.0

- React Router was migrated to the patched direct `react-router` 8.3.0 package;
  `react-router-dom` is absent and the locked npm graph audits cleanly.
- Least-privilege `Second Brain CI` now provides an early, non-authoritative
  push, pull-request, and manual regression signal.
- `POST /memories/search/explained` adds deterministic lexical, semantic, and
  hybrid ordering explanations without changing legacy search responses.
- Search presents those explanations with keyboard-accessible focus, semantic
  labels and announcements, text channel names, responsive layout, reduced-
  motion compatibility, and explicit ordering-aid wording.
- Integrated local acceptance and release hardening cover the real Vite proxy,
  safe missing-provider behavior, installation reproducibility, compatibility,
  privacy, accessibility, and one release-authoritative local Full run.

## Compatibility and migration

The change set is additive. Existing lexical, semantic, and hybrid Memory
search contracts and the Answer contract are unchanged. The sole Alembic head
remains `0009_memory_expiration`; no V1.1 schema or stored-data migration exists.
Existing development data is preserved.

`second-brain-project-export` format version 1 remains supported. Import remains
validation-first, conflict-safe, and atomic, with no merge, overwrite, remap,
repair, or partial-import behavior.

## Installation and verification

Use CPython 3.12, Node.js 22.22 or newer, npm 10 or newer, Docker Desktop with
Compose v2, and PowerShell 5.1 or newer. Follow
[LOCAL_V1_RUNBOOK.md](LOCAL_V1_RUNBOOK.md), install backend development
dependencies with `python -m pip install -e ".[dev]"`, and install frontend
dependencies with locked `npm ci` through `scripts/frontend-setup.ps1`.

Before release approval, `npm audit --audit-level=high` must report zero
vulnerabilities and `react-router` must resolve exactly to 8.3.0 without
`react-router-dom`. `Second Brain CI` is only an early signal. The authoritative
gate is the local `./scripts/verify.ps1 -Mode Full` workflow with PostgreSQL,
Alembic, all backend and frontend tests, static checks, and production build.

## Security and privacy boundaries

The application remains loopback-only for one trusted local maintainer. It has
no authentication, authorization, remote access, multi-user boundary, cloud
sync, autonomous agents, browser persistence, polling, background worker,
scheduled maintenance, or persistent conversation history. Explained lexical
search requires no provider. Semantic and hybrid searches preserve safe generic
missing-provider and provider-failure behavior.

Public contracts do not expose credentials, database URLs, environment values,
filesystem paths, vectors, raw ranking values, provider responses, prompts, SQL,
or raw exceptions. Queries, explanations, results, and Answer history are not
persisted. Project bundles contain private application data and are not
encrypted; store them securely.

## Accessibility

The accepted Search behavior supports keyboard operation, visible focus,
semantic headings and labels, status and alert announcements, result-first
reading order followed by labelled explanations, text-based channel
distinctions, ordering-aid wording, narrow viewports without horizontal
clipping, and reduced-motion preferences.

## Known limitations

There is no authentication, remote or multi-user operation, cloud sync,
automatic maintenance, encrypted bundle format, persistent conversation
history, or provider-free semantic/hybrid success. See
[KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) for the complete boundaries.

## Recovery

`v1.0.0` remains the stable pre-V1.1 recovery point. Roll back V1.1 by reverting
its isolated commits. No database downgrade, recreation, reset, or volume
deletion is required. Preserve the PostgreSQL container and
`second-brain_postgres_data` named volume. Version 1 bundles remain supported.

Checkpoint 60 does not authorize a tag or GitHub Release. Human review of its
evidence and a separate explicit publication instruction are required.
