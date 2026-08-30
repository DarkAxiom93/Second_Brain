# Checkpoint 96 report - Local V1.4 end-to-end acceptance

Status: **Complete and safe for human review.**

## Outcome

Checkpoint 96 proves the Local V1.4 operator journey across the public FastAPI
routes, real PostgreSQL `second_brain_test`, production connector services and
scheduler coordinator, the fake credential-store boundary, deterministic fake
GitHub transport, and the existing frontend contract suite. No production
defect was found and no production code changed.

No real GitHub credential or request, provider write, external write, migration,
provider endpoint, Tool, Agent/Automation connector authority, automatic import,
export-v2 work, or Checkpoint 97 work occurred.

## Preflight

- Clean synchronized `main`: local HEAD and `origin/main` were exactly
  `c9811f7909fbd17f3f8b6fbcb332313c54b2ce7d` after `git fetch origin main`.
- Exact Checkpoint 95 push CI: **Second Brain CI** run `33272620729`, event
  `push`, exact head SHA `c9811f7909fbd17f3f8b6fbcb332313c54b2ce7d`,
  completed successfully with no reported artifacts.
- Parsed and live identities: `second_brain` and `second_brain_test` at
  `127.0.0.1:5433`, both verified.
- Alembic current and sole head: `0014_connector_refresh_schedules`; check:
  `No new upgrade operations detected.`
- Tool Registry: `agent-tools-v1`.
- Project export: `second-brain-project-export` version `1`.
- Focused CP95 connector/security gate: 134 passed before implementation, zero
  skipped. The post-change connector gate was 136 passed, zero skipped.

## Joined scenario matrix

| Area | Result | Exact acceptance evidence |
|---|---|---|
| Credential/account setup | PASS | `tests/integration/test_v1_4_connector_acceptance.py::test_joined_account_refresh_browse_reconcile_and_exact_import` |
| Manual refresh and exact GET inventory | PASS | same joined node; `tests/integration/test_connector_refresh_api.py::test_manual_refresh_inventory_quarantine_replay_and_safe_status`; `tests/test_github_transport.py::test_exact_get_only_request_inventory_and_headers` |
| Browse, provenance, hostile content | PASS | same joined node; `tests/integration/test_connector_refresh_api.py::test_external_browser_history_cursor_links_and_scope_fail_closed` |
| Complete reconciliation and incomplete failure | PASS | same joined node; `tests/integration/test_connector_refresh_api.py::test_complete_absence_stales_partial_does_not_and_replay_restores` |
| Explicit exact import, replay, drift | PASS | same joined node; `tests/integration/test_external_item_imports.py::test_sequential_and_concurrent_confirmation_create_exactly_one_import`; `tests/integration/test_external_item_imports.py::test_drift_scope_state_and_closed_confirmation_fail_without_creation` |
| Scheduled refresh and restart | PASS | `tests/integration/test_v1_4_connector_acceptance.py::test_scheduled_restart_and_credential_or_authority_failure_are_fenced`; `tests/integration/test_connector_refresh_schedules.py::test_materialize_claim_link_is_deterministic_and_never_agent_or_import` |
| Duplicate/failure/recovery | PASS | both joined nodes; existing refresh/import/schedule replay and expired-lease nodes in the CP95 C01-C18 manifest |
| Project/account/unassigned isolation | PASS | joined Project A/B/unassigned assertions; `tests/integration/test_connector_account_api.py::test_exact_project_or_explicit_unassigned_and_closed_input` |
| Frontend/operator journey | PASS | `frontend/src/ConnectorAccounts.test.tsx` (4 tests); `frontend/src/ExternalContext.test.tsx` (4 tests) |
| Protected domains/security/export | PASS | joined complete-row/count snapshots; all C01-C18 manifest nodes; `tests/integration/test_connector_persistence.py::test_project_export_v1_excludes_all_connector_data` |

## Acceptance results

Account creation used one opaque CP88 reference backed only by an instance-local
fake store containing an obvious synthetic canary. Creation was disabled-first,
preserved exact Project A scope and one repository allowlist, made zero provider
requests, and exposed neither reference nor token. Explicit re-enable produced
the revision-valid state required for refresh.

The first manual run was one `manual` `ConnectorSyncRun`, succeeded with complete
reconciliation, and recorded exactly GET-only fake calls for authenticated user,
`owner/cp96-repository` metadata, issues page 1, and pulls page 1. It quarantined
one repository, one hostile issue, and one pull request. Public sync status
matched the run and contained no secret. No AgentRun, Source, Memory, proposal,
Approval, or Automation changed.

External Context list/detail/bounded versions used the exact account and Project
A. The public projection remained `external_untrusted`, reconstructed the safe
GitHub issue URL, retained exact sync provenance, and rendered hostile HTML,
Markdown, JavaScript-scheme text, and instruction-like content as inert data.
Project B and explicit unassigned access both failed closed rather than widening
scope.

The second complete refresh changed only the issue fixture, replayed repository
metadata unchanged, and omitted the prior pull. It created one new issue
revision, preserved two-version history, made the pull stale, and retained all
historical content/provenance. A following deterministic provider timeout was
`failed`/incomplete with safe code `github_timeout` and made no additional
absence inference.

Preview and exact confirmation copied the current latest issue revision into
one `connector_import` Source, one SourceDocument, deterministic chunks, and one
ExternalItemImport. Text and the application-reconstructed historical URL came
from the exact quarantined revision; provenance retained Project A. Replay
returned the same Source/Document without duplication. A deliberately changed
confirmation fingerprint returned conflict and created nothing. Memory,
MemoryProposal, ApprovalRequest, AgentRun, and Automation counts were unchanged.

The schedule API created draft-first and made zero provider requests. After
explicit enable, the test deterministically materialized and claimed one due
slot, durably linked one scheduled ConnectorSyncRun, then simulated restart by
letting the lease expire before invoking the production connector tick with a
fresh owner/session. Recovery reused the exact linked run, completed one
scheduled sync through CP91 authority, and a subsequent fresh tick created no
replacement. History was content-free. No AgentRun or import was created.

Credential revocation before a later manual refresh returned only
`credential_missing` and made zero additional provider calls. A paused schedule
produced no claim. Existing CP91-95 tests retain duplicate active/manual
fencing, complete/incomplete provider failures, account/revision fences,
concurrent exact-import idempotency, lease-generation fencing, and no fallback
account, credential, repository, replay-all, or replacement Run behavior.

## Frontend and loopback evidence

The focused existing frontend infrastructure passed **8 tests across 2 files**,
zero skipped. It covers account/configuration state, explicit manual refresh,
list/detail/history, External/Untrusted and current/stale presentation, safe
GitHub links, preview/confirmation and resulting Source link, draft-first
warning, explicit enable/pause/resume/cancel controls, safe occurrence status,
safe conflict/recovery text, no polling, no browser credential/reference
persistence, and no raw HTML/Markdown execution. No browser/E2E dependency was
added.

Real loopback smoke used the real FastAPI application against only
`second_brain_test` and the existing Vite server, both bound to `127.0.0.1`.
API `/ready`, Vite-proxied `/api/ready`, and `/external-context` returned HTTP
200; the served route contained the SPA root. Recorded process evidence:
FastAPI launcher PID 57408/listener PID 3928 and Vite launcher PID 64232/listener
PID 54252. Cleanup stopped only the captured processes and left zero listeners
on ports 8000 and 5173. The repository has no browser automation framework, so
the strongest approved evidence is this real HTTP/proxy smoke plus the
deterministic frontend contract suite. Fake credential/GitHub dependencies are
wired and exercised by the joined TestClient journey; the readiness/UI smoke
performed no connector operation or provider access.

## Security, protected domains, and export

Complete-row snapshots of Memories, MemoryProposals, ApprovalRequests,
AgentRuns, Automations, Sources, SourceDocuments, and SourceChunks were identical
across sync, browse, reconciliation, failure, and scheduling. The import step
allowed only its exact Source, SourceDocument, chunks, and ExternalItemImport;
reviewed/proposal/approval/agent/automation domains remained unchanged.

The code-owned C01-C18 gate remains green. Request inventory is fixed GET-only
and no real provider transport was instantiated. Synthetic canary scanning found
the canary only at its intentional fake test-fixture declaration/use and found
no secret-bearing report, logs, public responses, export artifact, or generated
artifact. No acceptance output was retained outside source/report text.

Project export remains `second-brain-project-export` version `1`. Connector
account/runtime/snapshot/import-provenance/schedule/occurrence/notification data
remains excluded. Imported ordinary Source/SourceDocument records continue only
under the existing export-v1 semantics. Tool Registry remains `agent-tools-v1`.

## Verification

- Joined backend acceptance: **2 passed**, zero skipped.
- Focused connector backend/security: **136 passed**, zero skipped.
- Focused connector frontend: **8 passed across 2 files**, zero skipped.
- Full backend: **1,237 passed**, zero skipped.
- Full frontend: **137 passed across 14 files**, zero skipped.
- Pip integrity, Ruff lint/format, strict mypy over 182 production files,
  frontend ESLint/TypeScript/build, and `git diff --check`: pass.
- Alembic current/sole head/check: `0014_connector_refresh_schedules`, clean.

The first sandboxed Full invocation reported the existing Windows credential
adapter as locked after 1,236 passes. Its isolated rerun with normal OS
Credential Manager access passed, and the authoritative Full rerun with that
same access passed all 1,237 tests. This was an execution-environment permission
condition, not a product defect; no code was changed for it.

## Exact changes and handoff

Changed paths are exactly:

1. `tests/integration/test_v1_4_connector_acceptance.py`
2. `frontend/src/ExternalContext.test.tsx`
3. `docs/checkpoint-96-report.md`

All changes are acceptance evidence only and remain unstaged and uncommitted.
Checkpoint 96 is safe for human review. Local V1.4 is ready for separately
authorized release hardening; Checkpoint 97 has not started.
