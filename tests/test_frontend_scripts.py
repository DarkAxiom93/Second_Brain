"""Static safety and compatibility checks for the frontend PowerShell workflow."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.powershell import run_powershell

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = REPOSITORY_ROOT / "scripts"
FRONTEND_SCRIPTS = (
    SCRIPT_ROOT / "frontend-setup.ps1",
    SCRIPT_ROOT / "frontend-dev.ps1",
    SCRIPT_ROOT / "verify-frontend.ps1",
)


@pytest.mark.parametrize("script", FRONTEND_SCRIPTS)
def test_frontend_script_parses_in_windows_powershell_51(script: Path) -> None:
    command = (
        "$errors = $null; "
        f"[void][System.Management.Automation.Language.Parser]::ParseFile("
        f"'{script}', [ref]$null, [ref]$errors); "
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


def test_setup_uses_npm_ci_and_never_installs_globally() -> None:
    setup = (SCRIPT_ROOT / "frontend-setup.ps1").read_text(encoding="utf-8")
    all_scripts = "\n".join(
        script.read_text(encoding="utf-8") for script in FRONTEND_SCRIPTS
    )
    assert "& npm.cmd ci" in setup
    assert "npm install" not in all_scripts.lower()
    assert " -g " not in all_scripts.lower()
    assert "--global" not in all_scripts.lower()


def test_scripts_have_clear_missing_runtime_and_dependency_failures() -> None:
    setup = (SCRIPT_ROOT / "frontend-setup.ps1").read_text(encoding="utf-8")
    development = (SCRIPT_ROOT / "frontend-dev.ps1").read_text(encoding="utf-8")
    verification = (SCRIPT_ROOT / "verify-frontend.ps1").read_text(encoding="utf-8")
    assert "Node.js was not found" in setup
    assert "npm was not found" in setup
    assert "Frontend dependencies are missing" in development
    assert "Frontend dependencies are missing" in verification
    assert r".\scripts\frontend-setup.ps1" in development
    assert r".\scripts\frontend-setup.ps1" in verification


def test_frontend_verification_is_isolated_and_propagates_exit_codes() -> None:
    verification = (SCRIPT_ROOT / "verify-frontend.ps1").read_text(encoding="utf-8")
    assert "Invoke-IsolatedProcess" in verification
    assert "exit $result.ExitCode" in verification
    for script in ("lint", "typecheck", "test", "build"):
        assert f'"{script}"' in verification


def test_full_verification_invokes_frontend_verification() -> None:
    verification = (SCRIPT_ROOT / "verify.ps1").read_text(encoding="utf-8")
    assert 'if ($Mode -eq "Full")' in verification
    assert '"verify-frontend.ps1"' in verification
    assert "Invoke-IsolatedProcess" in verification
