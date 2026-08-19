# Checkpoint 68 report

Checkpoint: 68 — Approval and Proposed-Action Foundation. Complete.
Checkpoint 67 is complete at
`7b6c6bb8c4c67f9e8a5a34c363331bc94dbb094e`. Human review approved Checkpoint
68, which was committed as `1bc90b4339bd5466fda10e5d04711e3f025a0e01`
and pushed to `origin/main`. Checkpoint 69 is not started.

Preflight: documentation-sync base, `HEAD`, `main`, and `origin/main` were all
`448de6322bf71985cab7ff554005c19f5fc00ad3` with divergence `0 0`, a clean tree,
and latest subject `docs: finalize checkpoint 67 state`. The exact successful
`Second Brain CI` push run was `32166008961`: branch `main`, event `push`, exact
base SHA, attempt 1, completed/success, with zero artifacts.

Post-review synchronization: `HEAD`, `main`, and `origin/main` are all
`1bc90b4339bd5466fda10e5d04711e3f025a0e01` with divergence `0 0`, latest
subject `feat: add approval request foundation`, and a clean repository. The
exact successful `Second Brain CI` push run for that commit is `32219122039`:
workflow `Second Brain CI`, branch `main`, event `push`, exact head SHA, attempt
1, status `completed`, conclusion `success`, and zero artifacts.

Behavior: Adds exactly one code-owned proposal-only action, `memory.update`.
Creation locks and revalidates the Run, Step, and exact Project/unassigned
Memory target; validates a strict partial update without mutation; rejects
unknown, empty, and no-op input; and derives the canonical payload, complete
target version, SHA-256 proposal identity, bounded preview/evidence/risk,
24-hour expiry, and frozen execution identity server-side. Exact replay returns
the durable Request without renewing it or adding an event.

API: Adds exactly `POST /agent-runs/{run_id}/approval-requests`, `GET
/agent-runs/{run_id}/approval-requests`, `GET
/approval-requests/{approval_id}`, and `POST
/approval-requests/{approval_id}/review`. Public projections exclude proposal
hash, execution identity, internal Step ID, reviewer metadata, correlation and
idempotency data, raw Tool/provider output, prompts, reasoning, and exceptions.

Review: Human API review is the only approval source. Review locks Approval,
Run, then target. Exact same-decision replay is write-free; the opposite
decision conflicts. Expired Requests become terminal `expired`; missing,
moved, or version-changed targets become terminal `superseded`. Every new
terminal transition appends one safe AgentEvent atomically.

Critical invariant: Approval creation and review never mutate Memory, invoke a
Tool, create a ToolInvocation, transition a Run, consume `execution_identity`,
or grant propose/write/execute authority. `execution_identity` remains frozen
future-use persistence only; there is no execution handler or route.

Persistence: Existing CP62 `ApprovalRequest` fields and constraints safely
express all required invariants, so no migration was created. Alembic remains
at sole/current head `0010_agent_runtime_persistence`; registry remains
`agent-tools-v1`; Project export remains `second-brain-project-export` version
1.

Verification: Focused pure and PostgreSQL tests cover strict/canonical
definition behavior, bounded evidence, safe projection, exact replay, human
review, stale terminal behavior, event sequencing, and unchanged target. The
authoritative `scripts/verify.ps1 -Mode Full` gate is rerun after the final
acceptance-audit coverage additions; final counts are recorded below.

## Final acceptance audit

Target-version identity is canonical SHA-256 over `id`, `project_id`, `content`,
`source`, `title`, `summary`, `memory_type`, `importance`, `confidence`, `status`,
`event_time`, `expires_at`, `supersedes_id`, and `updated_at`. Every mutable
stored field and the scope are included. Immutable `created_at` is intentionally
excluded; generated `search_vector` is derived only from included content,
source, title, and summary fields. Focused tests prove every included field
changes the token and equivalent reads retain it.

Proposal identity uses sorted-key, compact, ASCII JSON and SHA-256 over exact
action type, target type, target public ID, frozen target version, and canonical
normalized input. Run/Step identity is separately frozen in columns and in the
database exact-proposal uniqueness constraint, matching the approved proposal
definition.

Acceptance matrix (test names are from `tests/test_agent_approvals.py` and
`tests/integration/test_agent_approval_api.py`):

1. Exact definition, unknown action, strict input, and empty/no-op rejection —
   `test_memory_update_is_strict_canonical_and_rejects_noop` plus API schema
   validation in `test_evidence_is_only_from_the_exact_persisted_run_step`.
2. Deterministic target version and all relevant mutations —
   `test_version_and_proposal_hash_are_deterministic_and_target_bound`,
   `test_every_mutable_memory_field_changes_target_version`, and
   `test_create_replay_projection_and_review_never_mutate_target`.
3. Canonical proposal hash and changed value/version —
   `test_version_and_proposal_hash_are_deterministic_and_target_bound`.
4. Bounded preview/evidence and provenance —
   `test_preview_is_server_owned_bounded_and_content_free`,
   `test_evidence_is_allowlisted_deduplicated_and_bounded`, and
   `test_evidence_is_only_from_the_exact_persisted_run_step`.
5. Safe projection and private hash/execution identity —
   `test_create_replay_projection_and_review_never_mutate_target`.
6. Exact creation/replay zero writes and frozen expiry/execution identity —
   `test_create_replay_projection_and_review_never_mutate_target` and
   `test_concurrent_duplicate_creation_has_one_row_event_and_frozen_fields`.
7. Concurrent duplicate one row/event and changed payload distinct —
   `test_concurrent_duplicate_creation_has_one_row_event_and_frozen_fields` and
   `test_scope_matrix_changed_payload_and_reject_replay_are_exact`.
8. Project A/B and Project/unassigned/null isolation —
   `test_scope_matrix_changed_payload_and_reject_replay_are_exact`.
9. Approve/reject unchanged target, same replay zero writes, and opposite
   conflict — `test_create_replay_projection_and_review_never_mutate_target`
   and `test_scope_matrix_changed_payload_and_reject_replay_are_exact`.
10. Concurrent approve/reject one winner/event —
    `test_concurrent_opposite_review_has_one_winner_and_one_event`.
11. Permanent expiry and stale/missing/out-of-scope fail closed —
    `test_expiry_is_permanent_write_safe_and_does_not_renew`,
    `test_changed_target_becomes_superseded_and_opposite_decision_conflicts`,
    and `test_missing_and_moved_targets_fail_closed_without_mutation`.
12. Create/review rollback atomicity —
    `test_create_and_review_failures_roll_back_every_partial_fact`.
13. Memory unchanged across lifecycle, zero ToolInvocation, zero Run elevation,
    monotonic safe events, and no execution path — lifecycle tests compare every
    mapped Memory column; `test_create_replay_projection_and_review_never_mutate_target`,
    `test_scope_matrix_changed_payload_and_reject_replay_are_exact`, and both
    concurrency tests assert Run/count/event invariants. The complete production
    code search finds no approved-Approval consumer or execution handler.

Test-count reconciliation: CP67 had 767 backend cases. CP68 originally added
five; the final audit adds nine more, for 14 new non-parametrized test functions
and 781 total backend cases. Existing OpenAPI inventory assertions were updated
without adding cases.

The first final-audit Full run exposed PostgreSQL test-database wear rather than
a Checkpoint 68 product failure. Repeated historical migration lifecycle runs
had exhausted dropped-column attribute slots in `second_brain_test`; PostgreSQL
raised `TooManyColumns` while the test database was left at
`0002_projects_memories`, causing dependent missing-table failures. No
development-database failure occurred.

The human explicitly approved recreation of only the disposable
`second_brain_test` database. Immediately before the destructive action, both
the parsed configured identity and live `current_database()` returned exactly
`second_brain_test`. Connections to only that database were eligible for
termination (zero existed); exactly `second_brain_test` was dropped and
recreated. The container, named volume, and development `second_brain` database
were preserved. A clean migration then ran every revision from base through
`0010_agent_runtime_persistence`; Alembic current and sole head both reported
`0010_agent_runtime_persistence`, and `alembic check` reported no new upgrade
operations.

Final focused verification on the clean database passed 14 tests with zero
failures. The authoritative `scripts/verify.ps1 -Mode Full` gate then passed:
781 backend tests collected and passed with zero skips, three existing warnings,
90 frontend tests, pip check, Ruff lint/format, mypy, Alembic current/heads/check,
frontend lint/typecheck/build, and `git diff --check` all succeeded.

Lifecycle: Human review approved Checkpoint 68. It is committed as
`1bc90b4339bd5466fda10e5d04711e3f025a0e01`, pushed to `origin/main`, CI-green,
and synchronized with a clean repository. No dependency, lockfile, CI, Docker,
frontend, export-format, worker, scheduler, connector, or Checkpoint 69 change
was made. Checkpoint 69 remains not started.
