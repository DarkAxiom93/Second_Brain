"""Safe static checks for the PowerShell retrieval evaluation entry point."""

from pathlib import Path

from tests.powershell import run_powershell


def test_script_parses_in_windows_powershell_and_propagates_exit_code() -> None:
    script = Path("scripts/evaluate-retrieval.ps1")
    result = run_powershell(
        [
            "-Command",
            (
                "$errors=$null; [void][System.Management.Automation.Language.Parser]::"
                f"ParseFile('{script.resolve()}',[ref]$null,[ref]$errors); "
                "if ($errors.Count) { exit 1 }"
            ),
        ],
    )
    assert result.returncode == 0, result.stderr
    source = script.read_text(encoding="utf-8")
    assert "exit $LASTEXITCODE" in source
    assert "docker" not in source.lower()
