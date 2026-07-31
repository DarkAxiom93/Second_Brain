"""Focused guarantees for stable nested Windows PowerShell capture."""

from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from tests.powershell import run_powershell


def test_captures_streams_separately_and_preserves_nonzero_exit_code() -> None:
    result = run_powershell(
        [
            "-Command",
            "[Console]::Out.Write('standard-output'); "
            "[Console]::Error.Write('standard-error'); exit 7",
        ]
    )

    assert result.returncode == 7
    assert result.stdout == "standard-output"
    assert result.stderr == "standard-error"
    assert not result.stdout_path.exists()
    assert not result.stderr_path.exists()


def test_uses_owned_live_files_devnull_and_one_launch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    launches: list[list[str]] = []

    def fake_run(
        command: list[str], **options: Any
    ) -> subprocess.CompletedProcess[str]:
        launches.append(command)
        assert options["stdin"] is subprocess.DEVNULL
        assert options["stdout"] is not subprocess.PIPE
        assert options["stderr"] is not subprocess.PIPE
        assert options["stdout"] is not options["stderr"]
        assert not options["stdout"].closed
        assert not options["stderr"].closed
        assert options["check"] is False
        assert options["shell"] is False
        options["stdout"].write(b"out")
        options["stderr"].write(b"err")
        return subprocess.CompletedProcess(command, 3)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = run_powershell(["-Command", "exit 3"], capture_root=tmp_path)

    assert launches == [
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "exit 3",
        ]
    ]
    assert result.returncode == 3
    assert result.stdout == "out"
    assert result.stderr == "err"
    assert list(tmp_path.iterdir()) == []


def test_concurrent_calls_own_distinct_capture_files(tmp_path: Path) -> None:
    def invoke(label: str):
        return run_powershell(
            ["-Command", f"[Console]::Out.Write('{label}')"],
            capture_root=tmp_path,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = executor.map(invoke, ("first", "second"))

    assert (first.stdout, second.stdout) == ("first", "second")
    assert first.stdout_path.parent != second.stdout_path.parent
    assert not first.stdout_path.exists()
    assert not second.stdout_path.exists()
    assert list(tmp_path.iterdir()) == []


def test_sensitive_arguments_are_not_added_to_helper_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "never-expose-helper-secret"

    def fail_without_command(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("PowerShell launch failed")

    monkeypatch.setattr(subprocess, "run", fail_without_command)
    with pytest.raises(OSError) as failure:
        run_powershell(["-Command", f"Write-Output '{secret}'"])

    assert secret not in str(failure.value)
