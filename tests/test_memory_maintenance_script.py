"""Safe checks for the PowerShell Memory maintenance audit command."""

import subprocess
from pathlib import Path


def test_script_is_powershell_51_safe_and_has_no_mutation_modes() -> None:
    script = Path("scripts/audit-memory-maintenance.ps1")
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                "$errors=$null; [void][System.Management.Automation.Language.Parser]::"
                f"ParseFile('{script.resolve()}',[ref]$null,[ref]$errors); "
                "if ($errors.Count) { exit 1 }"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    source = script.read_text(encoding="utf-8").lower()
    assert "exit $lastexitcode" in source
    assert "docker" not in source
    assert "[switch]$execute" not in source
    assert "[switch]$repair" not in source
    assert "[switch]$cleanup" not in source


def test_invalid_database_identity_fails_without_credential_exposure() -> None:
    secret = "never-print-this"
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            "scripts/audit-memory-maintenance.ps1",
            "-DatabaseUrl",
            f"postgresql+psycopg://user:{secret}@127.0.0.1:5433/wrong_database",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "must target" in result.stdout
    assert secret not in result.stdout + result.stderr
