# Checkpoint 85 report - Local V1.3 end-to-end acceptance

Status: **Approved and complete after human review.**

## Outcome

Checkpoint 85 proves the Local V1.3 Automation loop across the loopback API,
PostgreSQL, explicit one-tick scheduler, Agent Runtime, both fixed Agents,
durable result events, occurrence history, notifications, and existing UI
projections. The new joined acceptance test covers both `daily_brief` version
`1` and `project_watch` version `1` in `automatic_read_only`; the existing
release gates supply the complete schedule, lifecycle, create-only, restart,
missed-run, capacity, UI, and security matrix.

No production defect was found and no production code changed. No migration,
Agent, Tool, authority, connector, network path, or external access was added.
Checkpoint 86 was not started.

## Scenario matrix

| Area | Result | Acceptance evidence |
|---|---|---|
| Schedules | PASS | `tests/test_automation_schedule.py::test_one_time_daily_and_weekly_calculation`; `tests/test_automation_schedule.py::test_dst_gap_uses_first_valid_instant_and_fold_uses_fold_zero_once`; `tests/integration/test_automation_scheduler.py::test_materialization_filters_orders_bounds_and_advances_from_slot` |
| Lifecycle | PASS | `tests/integration/test_automation_api.py::test_lifecycle_revisions_edits_and_terminal_cancellation`; `tests/integration/test_automation_api.py::test_invalid_transitions_stale_revision_and_one_time_past_fail_safely`; `tests/integration/test_automation_scheduler.py::test_lifecycle_and_edit_race_before_run_link`; exact-scope predecessor isolation is asserted by `tests/integration/test_project_watch_changes.py::test_window_successful_predecessor_scope_and_version_revalidation` |
| Create-only | PASS | `tests/integration/test_automation_scheduler.py::test_claiming_is_bounded_deterministic_and_create_only`; `tests/integration/test_automation_scheduler.py::test_concurrent_link_and_replay_resolve_one_inert_run` |
| Automatic Daily Brief | PASS | `tests/integration/test_v1_3_automation_acceptance.py::test_api_scheduler_result_history_notification_and_reentry[daily_brief]`; exact Project/unassigned evidence isolation is asserted by `tests/integration/test_daily_brief_events.py::test_exact_project_and_unassigned_scope_are_isolated_and_redacted` |
| Automatic Project Watch | PASS | `tests/integration/test_v1_3_automation_acceptance.py::test_api_scheduler_result_history_notification_and_reentry[project_watch]`; `tests/integration/test_project_watch_changes.py::test_window_successful_predecessor_scope_and_version_revalidation` |
| Restart/recovery | PASS | `tests/integration/test_automation_scheduler.py::test_materialization_failure_rolls_back_insert_and_advance`; `test_claim_failure_rolls_back_state_and_lease`; `test_expired_claim_reclaims_and_fences_old_generation`; `test_repeated_restart_reconciles_exact_link_without_replacement`; `test_linked_terminal_run_reconciliation_is_idempotent`; `tests/integration/test_automation_coordinator.py::test_fixed_read_only_definition_executes_once_replays_and_mutates_no_domain` |
| Missed-run policy | PASS | `tests/integration/test_automation_scheduler.py::test_missed_policy_materializes_only_latest_slot[skip-missed]`; `test_missed_policy_materializes_only_latest_slot[run_once-due]`; `test_backward_clock_does_not_reopen_terminal_slot` |
| Capacity | PASS | `tests/integration/test_automation_scheduler.py::test_capacity_rejection_preserves_durable_claim`; `test_retry_budget_timing_and_capacity_deferral` |
| History/notifications | PASS | Both joined E2E parameter cases; `tests/integration/test_automation_operator_api.py::test_occurrence_history_is_bounded_newest_first_and_redacted`; `test_notification_inbox_dedup_redaction_and_idempotent_mark_read` |
| UI/API consistency | PASS | Both joined E2E parameter cases plus the four executable assertions in `frontend/src/Automations.test.tsx`, which ran as the focused frontend suite |
| Security/mutation invariants | PASS | `tests/test_automation_security_evaluation.py::test_manifest_covers_exact_automation_threat_register`; `test_every_manifest_reference_is_an_assertive_automated_test`; `test_manifest_includes_postgresql_fault_prompt_privacy_and_mutation_proofs`; `tests/integration/test_automation_coordinator.py::test_fixed_read_only_definition_executes_once_replays_and_mutates_no_domain` |

## Joined scheduler/API/UI evidence

`tests/integration/test_v1_3_automation_acceptance.py` creates each fixed Agent
through the real FastAPI routes, previews its daily UTC schedule, enables it,
sets only the deterministic due-time fixture, and invokes the production
`run_one_tick` function. Each invocation creates a new database session and
opaque scheduler owner. Controlled providers remain inside the existing fake
boundaries and make no network call.

For each Agent the test observes exactly one canonical occurrence, claim, Run,
Step, Tool invocation, durable fixed-Agent result, linked history projection,
and content-free completion notification. Two subsequent fresh ticks create no
replacement Run/result and the planner call count stays one. The history Run ID
matches the Agent Run API and durable foreign key. The notification is readable
and disappears from the unread projection after the explicit mark-read action.

The operator CLI's database guard remains unchanged: it deliberately accepts
only the loopback development database. Acceptance therefore calls the same
production one-tick function directly under the verified test-database fixture;
weakening the CLI guard to permit destructive test operation was neither needed
nor safe.

The existing frontend infrastructure uses deterministic API mocks rather than
a browser E2E framework. Its four Automations tests passed. Per checkpoint
instruction, no browser framework or dependency was introduced solely to add a
second UI harness.

## Detailed results

- Schedule/DST: one-time, daily, weekly, gap and fold fixtures pass; occurrence
  local date/time, zone, offset and UTC are captured canonically; recurrence
  advances from the prior slot rather than worker wake time; uniqueness prevents
  a duplicate canonical slot.
- Lifecycle/races: all requested transitions and permitted edits pass. Captured
  occurrence configuration remains historical, while lifecycle, revision,
  execution-mode, and scope drift fence unlinked stale work.
- Restart/recovery: atomic rollback hooks cover materialization and Run/link;
  lease-generation tests fence expired owners; linked nonterminal and terminal
  replay reuses the exact Run; terminal work does not reopen; automatic
  coordination replays durable planning/execution without replacement.
- Missed/capacity: closed `skip`/`run_once`, seven-day lookback, latest-slot
  behavior, retry bounds, 32-Run capacity, capacity deferral, exact later retry,
  and manual idempotent replay all pass without replay-all or duplicate work.
- Daily Brief: exact Project and explicit-unassigned isolation, reviewed local
  Memory/application-event evidence, closed event projection, citation/version
  revalidation, insufficiency, safe notice, and no protected mutation pass.
- Project Watch: exact Project, deterministic `(lower, upper]`, seven-day first
  window, successful same-scope predecessor watermark, scope-change isolation,
  `changes_found`, `no_meaningful_change`, failed/cancelled predecessor
  exclusion, safe notice, and no protected mutation pass.
- Security: Research and Curator remain unschedulable; manual/free-form fixed
  Agent creation remains fenced; the automatic catalog contains exactly two
  fixed read-only definitions over the existing five application reads.

Protected-domain complete-row snapshots before and after automatic execution
remain identical for `projects`, `memories`, `sources`, `source_documents`,
`source_chunks`, `memory_proposals`, and `approval_requests`. Allowed writes are
limited to Automation metadata/notifications and Agent Runtime records.

## Defects and fixes

No product defect was encountered. The initial acceptance fixture inherited the
safe default `skip` missed-run policy, so its intentionally overdue slot became
a correct durable missed occurrence. The fixture was corrected to explicitly
select `run_once`, matching the scenario being exercised. No production fix or
semantic change was made.

## Verification

- Focused joined E2E: **2 passed**, zero skipped.
- Focused Automation acceptance backend: **115 passed**, zero skipped.
- Focused Automations/Notifications frontend: **4 passed**, zero skipped.
- Full dependency check, Ruff lint/format, strict mypy, and `git diff --check`:
  pass.
- Full backend: **1,092 passed**, zero skipped.
- Full frontend: **128 passed across 12 files**, zero skipped; ESLint,
  TypeScript, and production Vite build pass.
- Alembic current and sole head: `0011_automation_persistence`.
- Alembic check: no new upgrade operations.
- Tool Registry: `agent-tools-v1`.
- Project export: `second-brain-project-export` version `1`.

## Exact changes and handoff

Changed paths are exactly:

1. `tests/integration/test_v1_3_automation_acceptance.py`
2. `docs/checkpoint-85-report.md`

The diff is two additive files only: one parametrized joined acceptance module
and this report. Everything is unstaged and uncommitted. No commit, push, PR,
migration, new Agent, new Tool, new authority, proposal/Approval execution,
connector, external access, or release-hardening work occurred.

Checkpoint 85 is safe for human review. Subject to that review and approval,
Local V1.3 is ready to proceed separately to Checkpoint 86 release hardening.
