"""Safety and compatibility checks for repository verification."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VERIFY_SCRIPT = REPOSITORY_ROOT / "scripts" / "verify.ps1"


def _script() -> str:
    return VERIFY_SCRIPT.read_text(encoding="utf-8")


def test_verify_script_parses_in_windows_powershell_51() -> None:
    command = (
        "$errors = $null; "
        "[void][System.Management.Automation.Language.Parser]::ParseFile("
        f"'{VERIFY_SCRIPT}', [ref]$null, [ref]$errors); "
        "if ($errors.Count -gt 0) { $errors | Out-String | Write-Error; exit 1 }"
    )
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            command,
        ],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_every_pytest_mode_uses_one_isolated_guid_base_temp() -> None:
    script = _script()
    assert '$pytestTempPrefix = "second-brain-pytest-"' in script
    assert "[System.Guid]::NewGuid()" in script
    assert script.count('"--basetemp=$pytestBaseTemp"') == 2
    assert '@("-m", "pytest", "--basetemp=$pytestBaseTemp")' in script
    assert (
        "@(" + '"-m", "pytest", "--basetemp=$pytestBaseTemp") + $quickTests' in script
    )
    assert "if ($SkipDatabase)" in script
    assert "pytest-of-" not in script


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
