"""Static safety checks for the PowerShell Project import command."""

from pathlib import Path

from tests.powershell import run_powershell

SCRIPT = Path("scripts/import-project.ps1")


def test_script_is_powershell_51_safe_and_has_no_dangerous_modes() -> None:
    result = run_powershell(
        [
            "-Command",
            (
                "$errors=$null; [void][System.Management.Automation.Language.Parser]::"
                f"ParseFile('{SCRIPT.resolve()}',[ref]$null,[ref]$errors); "
                "if ($errors.Count) { exit 1 }"
            ),
        ],
    )
    assert result.returncode == 0, result.stderr
    source = SCRIPT.read_text(encoding="utf-8").lower()
    assert "exit $lastexitcode" in source
    assert "docker" not in source
    for switch in ("merge", "overwrite", "remap", "repair", "delete", "cleanup"):
        assert f"[switch]${switch}" not in source


def test_missing_bundle_and_execute_without_expected_id_fail_early(
    tmp_path: Path,
) -> None:
    missing = run_powershell(
        [
            "-File",
            str(SCRIPT),
            "-BundlePath",
            str(tmp_path / "missing.sbexport"),
        ],
    )
    assert missing.returncode != 0
    assert "existing regular file" in missing.stderr
    bundle = tmp_path / "present.sbexport"
    bundle.write_bytes(b"not-sensitive")
    execute = run_powershell(
        [
            "-File",
            str(SCRIPT),
            "-BundlePath",
            str(bundle),
            "-Execute",
        ],
    )
    assert execute.returncode != 0
    assert "ExpectedProjectId" in execute.stderr
