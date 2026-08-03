"""Safety and compatibility checks for repository verification."""

from __future__ import annotations

import ast
from pathlib import Path

from tests.powershell import run_powershell

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VERIFY_SCRIPT = REPOSITORY_ROOT / "scripts" / "verify.ps1"
PROCESS_HELPER = REPOSITORY_ROOT / "scripts" / "Invoke-IsolatedProcess.ps1"
DIAGNOSTICS_TESTS = REPOSITORY_ROOT / "tests" / "test_diagnostics_script.py"
LIVE_DATABASE_TEST = (
    "tests/test_diagnostics_script.py::"
    "test_healthy_test_database_execution_and_optional_json"
)


def _script() -> str:
    return VERIFY_SCRIPT.read_text(encoding="utf-8")


def test_verify_script_parses_in_windows_powershell_51() -> None:
    command = (
        "$errors = $null; "
        "[void][System.Management.Automation.Language.Parser]::ParseFile("
        f"'{VERIFY_SCRIPT}', [ref]$null, [ref]$errors); "
        "if ($errors.Count -gt 0) { $errors | Out-String | Write-Error; exit 1 }"
    )
    result = run_powershell(
        [
            "-Command",
            command,
        ],
        cwd=REPOSITORY_ROOT,
    )
    assert result.returncode == 0, result.stderr


def test_every_pytest_mode_uses_one_isolated_guid_base_temp() -> None:
    script = _script()
    assert '$pytestTempPrefix = "second-brain-pytest-"' in script
    assert "[System.Guid]::NewGuid()" in script
    assert script.count('"--basetemp=$pytestBaseTemp"') == 2
    assert '@("-m", "pytest", "--basetemp=$pytestBaseTemp")' in script
    assert '"--basetemp=$pytestBaseTemp", "--deselect=$quickDatabaseTestNode"' in script
    assert "+ $quickTests" in script
    assert "if ($SkipDatabase)" in script
    assert "pytest-of-" not in script


def test_quick_deselects_only_the_exact_live_database_test() -> None:
    script = _script()

    assert f'$quickDatabaseTestNode = "{LIVE_DATABASE_TEST}"' in script
    assert script.count('"--deselect=$quickDatabaseTestNode"') == 1
    assert '$quickArguments = @("-m", "pytest"' in script
    assert "-ArgumentList $quickArguments" in script
    assert "--ignore=tests/test_diagnostics_script.py" not in script
    assert '"--ignore", "tests/test_diagnostics_script.py"' not in script


def test_full_keeps_the_complete_suite_without_deselection() -> None:
    script = _script()
    verification_start = script.index('Invoke-Stage "mypy"')
    full_start = script.index('if ($Mode -eq "Full") {', verification_start)
    quick_start = script.index("    } else {", full_start)
    full_block = script[full_start:quick_start]

    assert '@("-m", "pytest", "--basetemp=$pytestBaseTemp")' in full_block
    assert "deselect" not in full_block.lower()
    assert "$quickDatabaseTestNode" not in full_block


def test_deselected_test_is_live_database_only_and_siblings_remain_collected() -> None:
    source = DIAGNOSTICS_TESTS.read_text(encoding="utf-8")
    module = ast.parse(source)
    tests = {
        node.name: node
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }
    target_name = LIVE_DATABASE_TEST.rsplit("::", maxsplit=1)[1]

    assert set(tests) == {
        "test_script_parses_in_windows_powershell_51_and_has_no_mutation_switches",
        "test_invalid_identity_and_unsafe_api_fail_without_secret_exposure",
        "test_output_overwrite_refusal",
        target_name,
    }
    target = tests[target_name]
    assert target.decorator_list == []
    target_source = ast.get_source_segment(source, target)
    assert target_source is not None
    assert 'env["TEST_DATABASE_URL"]' in target_source
    assert "second_brain_test" in target_source
    assert '"-UseTestDatabase"' in target_source
    assert "_powershell(" in target_source
    assert "pytest.skip" not in target_source


def test_cleanup_is_exact_guarded_and_has_no_privilege_or_wildcard_operations() -> None:
    script = _script()
    lowered = script.lower()
    assert "Assert-PytestTempPathSafe $pytestBaseTemp" in script
    assert "Remove-Item -LiteralPath $pytestBaseTemp -Recurse -Force" in script
    assert "$resolvedCandidate -ne $pytestBaseTemp" in script
    assert "$leaf -ne ($pytestTempPrefix + $pytestRunId)" in script
    assert "finally {" in script
    for forbidden in (
        "takeown",
        "icacls",
        "runas",
        "-verb runas",
        "pytest-of-",
        "remove-item *",
    ):
        assert forbidden not in lowered


def test_failure_propagation_and_existing_stages_remain_present() -> None:
    script = _script()
    assert "$verificationFailure = $_" in script
    assert "if ($null -eq $verificationFailure)" in script
    assert "throw $verificationFailure" in script
    for stage in (
        '"pip check"',
        '"Ruff lint"',
        '"Ruff format check"',
        '"mypy"',
        '"Alembic current"',
        '"Alembic heads"',
        '"Alembic check"',
        '"verify-frontend.ps1"',
        "git diff --check",
    ):
        assert stage in script


def test_outer_runner_keeps_all_redirected_handles_until_child_exit() -> None:
    helper = PROCESS_HELPER.read_text(encoding="utf-8")
    wait = helper.index("$process.WaitForExit()")
    read_stdout = helper.index("$stdoutTask.GetAwaiter().GetResult()")
    read_stderr = helper.index("$stderrTask.GetAwaiter().GetResult()")
    close_stdin = helper.index("$standardInput.Close()")
    dispose = helper.index("$process.Dispose()")

    assert wait < read_stdout < close_stdin < dispose
    assert wait < read_stderr < close_stdin
    assert "ReadToEndAsync()" in helper
    assert "RedirectStandardInput = $true" in helper
