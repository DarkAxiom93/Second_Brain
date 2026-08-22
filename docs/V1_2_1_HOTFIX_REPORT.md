# Local V1.2.1 Agent live-provider hotfix report

Publication status: **Pending explicit human approval**.

The complete V1.2.1 hotfix is implemented at
`a8530adc5f97b75927fa1f61e2383cf27bdcc925` (`fix: harden agent live provider
workflows`). Its exact `Second Brain CI` push run `32557073033` on `main`,
attempt 1, completed successfully. This report prepares a patch release; no
`v1.2.1` tag or GitHub Release exists yet.

## Confirmed defects and corrections

1. **Planning strict schema.** The planning provider exposed
   `candidate_input` as an open object, which OpenAI strict Structured Outputs
   rejected. The provider contract now derives closed tool/input variants from
   the immutable registry. Every submitted object remains closed, and the
   translated candidate still passes application-owned registry, tool-schema,
   scope, authority, and budget validation.
2. **Application-owned goal.** A provider-generated `goal_summary` could differ
   from the exact Run goal. The provider no longer controls that value;
   translation restores the application-owned Run goal verbatim before the
   unchanged internal planning validation.
3. **Research and Curator strict schemas.** Research's nullable
   `insufficiency` field was not required by the submitted schema, and Curator's
   proposed input was an open structured object. Provider-only strict DTOs now
   require and close these shapes, then translate into the unchanged
   authoritative internal Research and Curator models. Application validation
   remains the trust boundary.
4. **Long-running frontend operations.** The shared five-second client timeout
   caused false planning and execution failures while synchronous provider work
   continued successfully. Planning and execution now use separate bounded
   timeouts compatible with their backend limits. An interrupted request makes
   exactly one read-only reconciliation request against persisted Run state.
   There is no polling and no automatic planning or execution retry.

Malformed or trailing provider JSON, non-object candidate inputs, forbidden or
unknown Tool fields, policy violations, and scope/authority violations continue
to fail closed. No provider-controlled value bypasses application validation.

## Live human acceptance

Planning acceptance used five fresh exact-Project Research Runs. All five
reached `ready`; there were zero provider, output, or policy failures, and every
frozen Step used only permitted Research read Tools.

The final Research Run reached `ready`, execution was started exactly once, all
read-only Steps succeeded, synthesis succeeded, and the Run finished
`completed` with safe status `None`. The evidence-backed result and citations
rendered correctly, with no false frontend execution failure.

The final Memory Curator Run reached `ready`, execution was started exactly
once, synthesis succeeded, and the Run finished `completed`. Its advisory
finding rendered correctly. Insufficient evidence produced no speculative
proposal: there were no proposed actions, no Approval Requests, no Memory
mutation, and no proposal execution. No false frontend execution failure
remained.

## Verification and unchanged identities

- Backend: 938 passed, zero skipped.
- Frontend: 124 passed, zero skipped.
- Pip check, Ruff lint/format, mypy, ESLint, TypeScript, production build, and
  `git diff --check`: passed.
- Alembic current/head: `0010_agent_runtime_persistence`; Alembic check: clean.
- Tool Registry: `agent-tools-v1`.
- Project export: `second-brain-project-export` version `1`.
- CI: `Second Brain CI` run `32557073033`, push to `main`, attempt 1,
  completed/success.

There was no migration, dependency, registry-version, export-version, CI,
Docker, or Agent-authority change.

## Preserved safety boundary and rollback

Strict Structured Outputs, exact Project scope, application-owned policy and
registry validation, bounded read-only Research, advisory-only Memory Curator,
and fail-closed behavior remain mandatory. There is no proposal execution,
autonomous Approval, Automation, worker, scheduler, connector, external
research, or arbitrary shell, Python, SQL, filesystem, browser, or network
authority.

Published `v1.2.0` remains unchanged and is the recovery release until V1.2.1
is separately approved and published. Recovery must follow
[LOCAL_V1_RUNBOOK.md](LOCAL_V1_RUNBOOK.md); never downgrade the development
database or delete its named volume.
