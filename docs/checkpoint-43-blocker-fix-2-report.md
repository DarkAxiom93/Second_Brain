# Checkpoint report

Checkpoint: 43 blocker fix 2 — stable PowerShell subprocess capture.

Files changed: `tests/powershell.py` provides shared file-backed capture and
`tests/test_powershell_process.py` covers its lifecycle. Eight existing
PowerShell-launching test modules use the helper. The outer handle-lifetime
correction is in `scripts/Invoke-IsolatedProcess.ps1`, with focused coverage in
`scripts/tests/verify-process.ps1` and `tests/test_verification_script.py`.
`docs/VERIFICATION.md` and `scripts/README.md` document both capture boundaries.
This report is the only other file added.

Behavior: Nested Windows PowerShell children receive `DEVNULL` stdin and
separate uniquely owned stdout/stderr files instead of nested Python PIPEs.
Capture files remain open through child termination, are decoded independently,
and are removed by exact path. The helper launches once and returns the real
exit code. The outer runner now retains all three redirected handles through
child exit and completion of both asynchronous output reads, then closes stdin
and disposes the process. `scripts/verify.ps1` itself is unchanged.

API: No application or frontend API behavior changed.

Database: No model, migration, Docker, or database behavior changed.

Transactions: No application transaction behavior changed.

Tests: The complete non-database PowerShell script group passed 26/26, including
the originally failing maintenance-script assertion. The focused outer-runner
harness passed high-volume separate-stream capture, sequential reuse, nonzero
exit propagation, and 20 consecutive `_overlapped` imports. Eleven focused
helper/maintenance/runner tests passed. Final Full verification passed all 624
Python tests with zero skips and all 25 frontend tests; pip check, Ruff
lint/format, mypy, frontend lint/typecheck/build, and `git diff --check` passed.

PostgreSQL verification: Parsed and live development/test database identities
passed. Alembic current and sole head are `0009_memory_expiration`; `alembic
check` reports no new upgrade operations.

Smoke test: Not applicable to this test-only capture change; application smoke
is explicitly paused by the checkpoint instructions.

API regression: All existing backend/integration and frontend tests passed. No
API, application, frontend, database, Docker, migration, or provider behavior
was changed by this blocker fix.

External calls: Docker used the already-running local PostgreSQL container. No
provider or external application call occurred.

Warnings: The inaccessible default `pytest-of-KushKush` base-temp issue was
fixed previously by per-verification `--basetemp`; two initial direct focused
invocations that omitted or could not create a usable base-temp reproduced only
that separate setup error and did not exercise the affected fixtures. No ACL or
permission repair was attempted. This checkpoint first removed nested test-side
PIPE capture. A subsequent Full run passed all 623 then-current Python tests but
exposed `WinError 6` in the next outer `Alembic current` Python process, proving
the outer stdin lifetime also required correction. The unchanged final Full run
then passed. Pytest reported two existing library warnings unrelated to handles.

Git status: Blocker-fix and pre-existing Checkpoint 43 files remain unstaged on
`main`. No commit, push, or PR was created.

Scope confirmation: Checkpoint 43 feature work remained paused. All 11 feature
files matched their recorded pre-fix SHA-256 hashes after implementation and
Full verification. No smoke test or further feature work was performed. No
files are staged or committed. No headings were omitted.
