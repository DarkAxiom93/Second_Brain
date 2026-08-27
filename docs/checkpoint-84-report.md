# Checkpoint 84 report - Automation security and evaluation harness

Status: **Approved and complete after human review.**

## Outcome

Checkpoint 84 adds a deterministic, code-owned release manifest for every
Automation threat A01-A18, a bounded adversarial corpus, and a complete-row
before/after protected-domain snapshot. It reuses the production scheduler,
Agent Runtime, fixed providers, controlled Tool dispatch, PostgreSQL fixtures,
fault hooks, barriers, and frontend tests; it does not implement a second
scheduler or Agent.

No production defect was exposed. No production code, schema, migration,
scheduling semantic, Agent authority, Tool Registry entry, connector, or
external path changed.

## A01-A18 release matrix

All references below are exact pytest node IDs and passed in the authoritative
Full run.

| Threat | Deterministic tests | Result |
|---|---|---|
| A01 | `tests/integration/test_automation_scheduler.py::test_concurrent_materializers_create_one_occurrence`; `tests/integration/test_automation_scheduler.py::test_concurrent_link_and_replay_resolve_one_inert_run` | Pass |
| A02 | `tests/integration/test_automation_scheduler.py::test_lifecycle_and_edit_race_before_run_link` | Pass |
| A03 | `tests/integration/test_automation_scheduler.py::test_owner_generation_expiry_and_lifecycle_fences`; `tests/integration/test_automation_scheduler.py::test_expired_claim_reclaims_and_fences_old_generation` | Pass |
| A04 | `tests/integration/test_automation_scheduler.py::test_concurrent_materializers_create_one_occurrence`; `tests/integration/test_automation_scheduler.py::test_concurrent_claimers_claim_once`; `tests/integration/test_automation_scheduler.py::test_serialization_and_deadlock_codes_are_bounded_retryable` | Pass |
| A05 | `tests/test_automation_schedule.py::test_calculation_is_host_timezone_independent`; `tests/integration/test_automation_scheduler.py::test_backward_clock_does_not_reopen_terminal_slot` | Pass |
| A06 | `tests/test_automation_schedule.py::test_dst_gap_uses_first_valid_instant_and_fold_uses_fold_zero_once` | Pass |
| A07 | `tests/integration/test_automation_scheduler.py::test_materialization_failure_rolls_back_insert_and_advance` | Pass |
| A08 | `tests/integration/test_automation_scheduler.py::test_run_link_failure_rolls_back_run_and_link`; `tests/integration/test_automation_scheduler.py::test_repeated_restart_reconciles_exact_link_without_replacement` | Pass |
| A09 | `tests/integration/test_automation_scheduler.py::test_missed_policy_materializes_only_latest_slot` | Pass |
| A10 | `tests/test_automation_schedule.py::test_invalid_closed_schedule_fields_fail`; `tests/test_automation_schedule.py::test_preview_rejects_non_progressing_calculation` | Pass |
| A11 | `tests/integration/test_automation_scheduler.py::test_retry_budget_timing_and_capacity_deferral`; `tests/integration/test_automation_scheduler.py::test_retry_exhaustion_is_terminal_and_operator_visible` | Pass |
| A12 | `tests/integration/test_automation_api.py::test_concurrent_pause_uses_row_lock_and_revision_cas`; `tests/integration/test_automation_scheduler.py::test_lifecycle_and_edit_race_before_run_link` | Pass |
| A13 | `tests/integration/test_daily_brief_events.py::test_exact_project_and_unassigned_scope_are_isolated_and_redacted`; `tests/integration/test_project_watch_changes.py::test_window_successful_predecessor_scope_and_version_revalidation` | Pass |
| A14 | `tests/test_automation_adversarial_evaluation.py::test_configuration_and_provider_output_reject_capability_injection`; `tests/test_automation_adversarial_evaluation.py::test_automatic_inventory_is_exact_read_only_without_external_mutation` | Pass |
| A15 | `tests/test_automation_adversarial_evaluation.py::test_hostile_labels_and_local_evidence_cannot_alter_fixed_goal_or_authority`; `tests/test_daily_brief_agent.py::test_forged_evidence_identifier_is_rejected` | Pass |
| A16 | `tests/integration/test_automation_scheduler.py::test_capacity_rejection_preserves_durable_claim` | Pass |
| A17 | `tests/integration/test_automation_operator_api.py::test_notification_inbox_dedup_redaction_and_idempotent_mark_read`; `tests/integration/test_automation_operator_api.py::test_occurrence_history_is_bounded_newest_first_and_redacted` | Pass |
| A18 | `tests/integration/test_automation_coordinator.py::test_fixed_read_only_definition_executes_once_replays_and_mutates_no_domain`; `tests/integration/test_automation_coordinator.py::test_unimplemented_and_non_read_definitions_fail_before_planning` | Pass |

`tests/test_automation_security_evaluation.py` additionally proves that the
manifest contains exactly A01-A18, every node ID exists, and every referenced
test contains an executable assertion or fail-closed exception assertion.

## Concurrency, restart, time, and fault injection

The Full run executed 30 PostgreSQL scheduler cases and three coordinator cases.
The broader Automation PostgreSQL surface executed 72 cases across persistence,
API lifecycle, scheduler, coordinator, history/notification, reserved-Agent,
Daily Brief, and Project Watch files. All ran only after parsed and live
`second_brain_test` identity verification.

The gate covers simultaneous materialization and claim with barriers; expired
lease reclaim and stale-generation rejection; atomic occurrence/advance and
Run/link rollback fault points; concurrent replay; lifecycle/edit/cancel races;
32-Run capacity saturation; closed PostgreSQL deadlock/serialization retry
classification; retry exhaustion/backoff; linked terminal and nonterminal
restart reconciliation; bounded missed-run lookback; backward clock behavior;
host-zone independence; and representative IANA spring-gap/fall-fold behavior.
There are no timing sleeps in the PostgreSQL concurrency tests.

## Prompt injection, notification privacy, and authority

The bounded corpus has seven adversarial payload families crossed with both
fixed Agents, plus seven forbidden configuration/provider fields. It covers
scope widening, Tool requests, write/propose authority, shell/Python/SQL/
filesystem/browser/network/connectors, citation suppression, forged evidence,
goal/window alteration, secret/provider leakage, and proposal/Approval/mutation
requests. Fixed goals exclude labels, evidence identifiers are application-
owned, closed schemas reject injected fields, and automatic definitions remain
exactly code-owned `read` with the five existing application reads.

Notification/history tests inject a secret-bearing private deduplication key
and prove the API omits it together with occurrence keys, labels, and lease
credentials. Public notifications remain code-owned, content-free,
deduplicated, loopback-only records. Focused UI tests prove inert React text
rendering, explicit refresh with no polling, no browser persistence, linked-Run
navigation, revision-conflict messaging, live-region status, labels/headings,
keyboard-driven controls, DST/UTC-offset clarity, and non-color status text.
Responsive/reflow, visible focus, touch sizing, and reduced-motion behavior
remain enforced by the existing frontend stylesheet and Full lint/build gate.

## Protected-domain mutation result

The automatic coordinator proof now snapshots every column of every row before
and after automatic read-only execution and replay for:

- `projects`
- `memories`
- `sources`
- `source_documents`
- `source_chunks`
- `memory_proposals` (including proposal targets)
- `approval_requests`

The snapshots are identical. Allowed changes are confined to Agent Runtime,
Automation occurrence/recovery state, and safe Automation notifications. The
coordinator invokes the fake planner once on replay, creates exactly one Run,
one Step, and one Tool invocation, and admits no non-read definition.

## Verification evidence

- Focused non-database harness: **77 passed**, zero skipped.
- Focused Agent/Automation frontend: **34 passed**, zero skipped.
- Full dependency, Ruff lint/format, strict mypy, and `git diff --check`: pass.
- Full backend: **1,090 passed**, zero skipped.
- Full frontend: **128 passed across 12 files**, zero skipped; ESLint,
  TypeScript, and production Vite build pass.
- Alembic current and sole head: `0011_automation_persistence`.
- Alembic check: no new upgrade operations.
- Tool Registry: `agent-tools-v1`.
- Project export: `second-brain-project-export` version `1`.

## Residual risks and acceptance recommendation

Residual risk is limited to the approved local boundary: scheduler wake timing,
IANA timezone database/library changes beyond pinned fixtures, PostgreSQL/host
failure modes not reproducible by deterministic transaction hooks, and
probabilistic provider quality within strict output/evidence validation. V1.3
still has no authentication or remote/multi-user boundary. These risks do not
grant authority, widen scope, or permit protected-domain mutation.

Checkpoint 84 is approved and complete after human review. The deterministic
gates support proceeding to Checkpoint 85 E2E acceptance. Checkpoint 85 has not
started.

## Exact changed paths and boundary confirmation

Checkpoint 84 changes exactly five paths:

1. `tests/test_automation_security_evaluation.py`
2. `tests/test_automation_adversarial_evaluation.py`
3. `tests/integration/test_automation_scheduler.py`
4. `tests/integration/test_automation_coordinator.py`
5. `docs/checkpoint-84-report.md`

Implemented Automation identities remain exactly Daily Brief v1 and Project
Watch v1. Research and Memory Curator remain unschedulable; manual/free-form
Daily Brief and Project Watch Runs remain fenced. No migration, Agent, Tool,
authority, proposal/Approval execution, connector, web/network/external
research, or write path was added. All work is intentionally unstaged and
uncommitted.
