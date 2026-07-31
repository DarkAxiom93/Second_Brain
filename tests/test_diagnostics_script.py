"""Safe script-level checks for operational diagnostics."""

import json
import os
import subprocess
from pathlib import Path

SCRIPT = Path("scripts/diagnose-system.ps1")


def _powershell(
    *arguments: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT),
            *arguments,
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_script_parses_in_windows_powershell_51_and_has_no_mutation_switches() -> None:
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
    for forbidden in (
        "docker",
        "[switch]$repair",
        "[switch]$execute",
        "migrate",
        "delete",
    ):
        assert forbidden not in source


def test_invalid_identity_and_unsafe_api_fail_without_secret_exposure() -> None:
    secret = "never-print-this-diagnostic-secret"
    env = os.environ.copy()
    env["DATABASE_URL"] = (
        f"postgresql+psycopg://user:{secret}@127.0.0.1:5433/second_brain_test"
    )
    identity = _powershell(env=env)
    unsafe = _powershell("-ApiBaseUrl", f"http://user:{secret}@127.0.0.1", env=env)
    assert identity.returncode != 0
    assert unsafe.returncode != 0
    assert (
        secret not in identity.stdout + identity.stderr + unsafe.stdout + unsafe.stderr
    )


def test_output_overwrite_refusal(tmp_path: Path) -> None:
    output = tmp_path / "existing.json"
    output.write_text("preserve", encoding="utf-8")
    result = _powershell("-OutputPath", str(output))
    assert result.returncode != 0
    assert output.read_text(encoding="utf-8") == "preserve"


def test_healthy_test_database_execution_and_optional_json(
    tmp_path: Path,
) -> None:
    output = tmp_path / "diagnostics.json"
    env = os.environ.copy()
    env["TEST_DATABASE_URL"] = (
        "postgresql+psycopg://second_brain:change-me@127.0.0.1:5433/second_brain_test"
    )
    result = _powershell(
        "-UseTestDatabase",
        "-OutputPath",
        str(output),
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["diagnostics_status"] == "healthy"
    assert payload["target_database"] == "second_brain_test"
