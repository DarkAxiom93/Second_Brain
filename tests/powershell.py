"""Stable, file-backed Windows PowerShell subprocess capture for tests."""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO


@dataclass(frozen=True)
class PowerShellResult:
    """Captured child result with paths retained for cleanup assertions."""

    returncode: int
    stdout: str
    stderr: str
    stdout_path: Path
    stderr_path: Path


def run_powershell(
    arguments: Sequence[str],
    *,
    cwd: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    capture_root: Path | None = None,
) -> PowerShellResult:
    """Run Windows PowerShell with owned files instead of nested PIPE handles."""

    capture_directory = Path(
        tempfile.mkdtemp(
            prefix="second-brain-powershell-",
            dir=capture_root,
        )
    )
    stdout_path = capture_directory / "stdout.bin"
    stderr_path = capture_directory / "stderr.bin"
    stdout_handle: IO[bytes] | None = None
    stderr_handle: IO[bytes] | None = None
    try:
        stdout_handle = stdout_path.open("w+b")
        stderr_handle = stderr_path.open("w+b")
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                *arguments,
            ],
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stdout_handle,
            stderr=stderr_handle,
            check=False,
            shell=False,
        )
        stdout_handle.flush()
        stderr_handle.flush()
        stdout_handle.seek(0)
        stderr_handle.seek(0)
        stdout = stdout_handle.read().decode("utf-8", errors="replace")
        stderr = stderr_handle.read().decode("utf-8", errors="replace")
        return PowerShellResult(
            returncode=completed.returncode,
            stdout=stdout,
            stderr=stderr,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    finally:
        if stdout_handle is not None:
            stdout_handle.close()
        if stderr_handle is not None:
            stderr_handle.close()
        stdout_path.unlink(missing_ok=True)
        stderr_path.unlink(missing_ok=True)
        capture_directory.rmdir()
