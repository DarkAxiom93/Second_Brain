"""Safe static and argument checks for the PowerShell export command."""

import subprocess
from pathlib import Path

SCRIPT = Path("scripts/export-project.ps1")


def test_script_is_powershell_51_safe_and_has_no_dangerous_modes() -> None:
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                "$errors=$null; [void][System.Management.Automation.Language.Parser]::"
                f"ParseFile('{SCRIPT.resolve()}',[ref]$null,[ref]$errors); "
                "if ($errors.Count) { exit 1 }"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    source = SCRIPT.read_text(encoding="utf-8").lower()
    assert "exit $lastexitcode" in source
    assert "docker" not in source
    for switch in ("import", "overwrite", "repair", "delete"):
        assert f"[switch]${switch}" not in source


def test_invalid_uuid_fails_before_database_access() -> None:
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(SCRIPT),
            "-ProjectId",
            "not-a-uuid",
            "-OutputPath",
            "unused.sbexport",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "valid UUID" in result.stderr
    assert "postgresql" not in result.stdout + result.stderr
