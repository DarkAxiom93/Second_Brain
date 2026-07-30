# Checkpoint report

Checkpoint: 30 — Windows Full Verification Process Reliability.

Files changed: `scripts/Invoke-IsolatedProcess.ps1` adds the shared isolated
process runner; `scripts/verify.ps1` uses it for every external verification
command; `scripts/tests/verify-process.ps1` adds deterministic focused checks;
`scripts/README.md` and `docs/VERIFICATION.md` document the maintained process
contract; `docs/CHECKPOINTS.md` records Checkpoint 29's committed hash and this
checkpoint; this report records the evidence and results.

Behavior: Full and Quick retain their existing stages, ordering, zero-skip rule,
and stop-on-failure behavior. Each external command now receives redirected
standard input, output, and error in a new `System.Diagnostics.Process` context.
Child stdin closes immediately; stdout and stderr drain concurrently; the
runner waits for process completion, reads the real exit code, emits both
streams, and disposes the process in `finally` before another command starts.
There is no global host-stream mutation, retry, sleep, prompt, swallowed stderr,
false success, or intentionally retained child process.

Diagnosis and evidence: The exact Windows root cause could not be proven from
the available failure alone. The strongest supported diagnosis is a mixed
standard-handle lifecycle in the former wrapper: pytest alone ran through the
PowerShell native pipeline `2>&1 | Out-String`, while later Alembic Python
processes inherited host handles directly. Checkpoint 29 recorded that all 461
tests completed before Python raised `OSError: [WinError 6] The handle is
invalid` while starting the following `alembic current` process. Direct Alembic
execution succeeded, localizing the defect to wrapper process/stream lifecycle
rather than Alembic or database logic. An unchanged baseline attempt during
this checkpoint stopped earlier at database identity verification because the
database service was initially offline, so it could not independently
reproduce the handle failure. The change removes the observed mixed pipeline
and inherited-handle boundary; the precise Windows component that invalidated
the earlier handle remains uncertain.

Exit-code and failure propagation: Focused checks preserved exit code 0 and
both output streams for successful commands, preserved a deliberate exit code
23 and its stderr, and proved a deliberate exit code 19 stops a sequential
command loop before its later command. `verify.ps1` checks each returned exit
code and throws with that value; no verification failure is converted to
success.

Focused validation: Two fresh Windows PowerShell invocations of
`scripts/tests/verify-process.ps1` passed. Each exercised sequential Python
processes, stdout and stderr capture, 4,000 stdout plus 4,000 stderr lines,
successful execution after that high-output process, real nonzero exit codes,
stop-on-failure behavior, and output usability across commands. Repeated
invocation produced no invalid or leaked-handle symptom.

Tests: Three independent Windows PowerShell 5.1-compatible `powershell.exe
-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File
.\scripts\verify.ps1 -Mode Full` processes completed with exit code 0 in 60.2,
68.3, and 62.9 seconds. Every run passed pip check, Ruff lint, Ruff format check,
mypy, the complete 461-test suite with zero skips, Alembic current, Alembic
heads, Alembic check, and `git diff --check`. All three later Alembic sequences
completed normally; current and heads were `0008_memory_proposals`, and check
reported no new upgrade operations. No WinError 6, invalid-handle, or
bad-file-descriptor error occurred.

PostgreSQL verification: The existing Docker database service was started by
the documented workflow and became healthy on `127.0.0.1:5433`; its named volume
was preserved. After verification it was safely stopped to restore its initial
state; the container and named volume remain preserved. Every Full run verified parsed and live identities for
`second_brain` and `second_brain_test`. No development database downgrade,
reset, deletion, volume removal, migration, or lifecycle-rule change occurred.

API: Unchanged. No application code, route, public schema, or behavior changed.

Database: Unchanged. No model, migration, dependency, Docker Compose service,
container configuration, data rule, or migration head changed.

Transactions: Unchanged; this script-only checkpoint adds no application or
database transaction behavior.

Smoke test: Omitted because no startup, routing, dependency wiring, or public
behavior changed; the verification contract requires safe script behavior
checks for documentation/script-only work, which the focused process checks
provide.

API regression: The complete 461-test suite passed three times with zero skips.

External calls: None.

Warnings and limitations: The pre-existing Starlette `httpx` deprecation
warning appeared in all runs, and one run also emitted a pre-existing Pydantic
field-alias warning. Git reported the existing Windows LF-to-CRLF working-copy
warning for `scripts/verify.ps1`. None affected exit codes. The earlier OS-level
handle invalidation mechanism is not proven; reliability evidence is limited to
the deterministic focused checks and three required fresh Full runs on this
Windows environment.

Git status: Branch `main` remains synchronized with `origin/main` at the pushed
Checkpoint 29 commit `4a96e56`. The seven intended Checkpoint 30 files are
modified or untracked and remain unstaged and uncommitted; no commit, push, or
PR was created.

Scope confirmation: Checkpoint 30 maintenance only. No verification stage was
removed, skipped, weakened, hidden, or retried. No Checkpoint 29 implementation
or test, application/API/model/schema/migration/dependency/Docker/database
behavior, provider call, staging, commit, push, PR, or next-checkpoint work.
