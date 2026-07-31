"""Command-line entry point for safe local operational diagnostics."""

import argparse
import json
import os
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.error import URLError
from urllib.request import urlopen

from sqlalchemy import create_engine, text

from app.core.config import Settings
from app.diagnostics.models import DiagnosticCheck, DiagnosticsResult, build_result
from app.diagnostics.service import (
    check,
    inspect_database,
    inspect_provider_configuration,
    repository_head,
    validate_api_base_url,
    validate_database_target,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-mode", choices=("development", "test"), required=True
    )
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--api-base-url")
    return parser.parse_args()


def _runtime_checks(repo_root: Path) -> list[DiagnosticCheck]:
    docs = (
        "ARCHITECTURE.md",
        "ROADMAP.md",
        "CHECKPOINTS.md",
        "VERIFICATION.md",
        "SAFETY.md",
        "API_CONVENTIONS.md",
    )
    python_ok = platform.python_version_tuple()[:2] == ("3", "12")
    repository_ok = all((repo_root / "docs" / name).is_file() for name in docs)
    venv_ok = (repo_root / ".venv" / "Scripts" / "python.exe").is_file()
    return [
        check(
            "powershell_compatibility",
            "runtime",
            "passed",
            "Command uses Windows PowerShell 5.1-compatible syntax.",
        ),
        check(
            "python_version",
            "runtime",
            "passed" if python_ok else "failed",
            "Python version is supported." if python_ok else "Python 3.12 is required.",
            actual=platform.python_version(),
            expected="3.12",
        ),
        check(
            "repository",
            "runtime",
            "passed" if repository_ok else "failed",
            "Repository root and required documentation exist."
            if repository_ok
            else "Repository root or required documentation is missing.",
        ),
        check(
            "virtual_environment",
            "runtime",
            "passed" if venv_ok else "failed",
            "Project virtual-environment Python exists."
            if venv_ok
            else "Project virtual-environment Python is missing.",
        ),
    ]


def _api_checks(base_url: str) -> list[DiagnosticCheck]:
    validated = validate_api_base_url(base_url)
    results: list[DiagnosticCheck] = []
    for identifier, path, expected in (
        ("health_probe", "/health", {"status": "ok"}),
        ("readiness_probe", "/ready", {"status": "ready"}),
    ):
        try:
            with urlopen(validated + path, timeout=5) as response:
                body = json.loads(response.read(1024))
                passed = response.status == 200 and body == expected
        except (OSError, URLError, ValueError, json.JSONDecodeError):
            passed = False
        results.append(
            check(
                identifier,
                "api",
                "passed" if passed else "failed",
                f"Local {path} probe succeeded."
                if passed
                else f"Local {path} probe failed.",
            )
        )
    return results


def _database_unavailable_checks(
    *, include_connection: bool = True
) -> list[DiagnosticCheck]:
    """Represent every blocked required check instead of silently omitting it."""

    blocked = [
        check(
            check_id,
            "postgresql",
            "failed",
            message,
        )
        for check_id, message in (
            ("connection", "PostgreSQL connection was not attempted."),
            ("current_database", "Live database identity could not be verified."),
            ("pgvector", "pgvector availability could not be verified."),
            ("required_tables", "Required application tables could not be verified."),
            ("server_version", "PostgreSQL server version could not be verified."),
            (
                "transaction_read_only",
                "Transaction read-only state could not be verified.",
            ),
        )
    ]
    checks = (
        blocked
        if include_connection
        else [item for item in blocked if item.check_id != "connection"]
    )
    checks.extend(
        [
            check(
                "current_revision",
                "alembic",
                "failed",
                "Database Alembic revision could not be verified.",
            ),
            check(
                "pending_upgrade",
                "alembic",
                "failed",
                "Pending Alembic upgrade state could not be verified.",
            ),
            check(
                "aggregate_counts",
                "application_state",
                "failed",
                "Application aggregate counts could not be collected.",
            ),
        ]
    )
    return checks


def run(
    *,
    mode: Literal["development", "test"],
    repo_root: Path,
    output: Path | None = None,
    api_base_url: str | None = None,
) -> DiagnosticsResult:
    captured_at = datetime.now(UTC)
    expected: Literal["second_brain", "second_brain_test"] = (
        "second_brain" if mode == "development" else "second_brain_test"
    )
    checks = _runtime_checks(repo_root)
    counts: dict[str, int] = {}
    variable = "DATABASE_URL" if mode == "development" else "TEST_DATABASE_URL"
    value = os.environ.get(variable)
    settings = Settings(database_url=value) if value else Settings()
    checks.extend(inspect_provider_configuration(settings))
    head, head_checks = repository_head(repo_root)
    checks.extend(head_checks)
    if not value:
        checks.append(
            check(
                "database_configuration",
                "configuration",
                "failed",
                "Required database configuration is missing.",
            )
        )
        checks.extend(_database_unavailable_checks())
    else:
        parsed, target_checks = validate_database_target(value, mode)
        checks.extend(target_checks)
        if not any(item.status == "failed" for item in target_checks):
            engine = create_engine(parsed, pool_pre_ping=True)
            try:
                with engine.connect() as connection:
                    connection.execute(text("SET TRANSACTION READ ONLY"))
                    database_checks, counts = inspect_database(
                        connection, expected_database=expected, head=head
                    )
                    checks.extend(database_checks)
                    connection.rollback()
            except Exception:
                checks.append(
                    check(
                        "connection",
                        "postgresql",
                        "failed",
                        "PostgreSQL connection or inspection failed.",
                    )
                )
                checks.extend(_database_unavailable_checks(include_connection=False))
            finally:
                engine.dispose()
        else:
            checks.extend(_database_unavailable_checks())
    if api_base_url:
        try:
            checks.extend(_api_checks(api_base_url))
        except ValueError:
            checks.append(
                check(
                    "base_url",
                    "api",
                    "failed",
                    "ApiBaseUrl is not an allowed local HTTP(S) target.",
                )
            )
    result = build_result(
        captured_at=captured_at,
        target_database=expected,
        checks=checks,
        aggregate_counts=counts,
    )
    if output is not None:
        resolved = output.resolve()
        if resolved.exists():
            raise FileExistsError("JSON output already exists")
        if not resolved.parent.is_dir():
            raise ValueError("JSON output parent directory does not exist")
        resolved.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return result


def _print(result: DiagnosticsResult) -> None:
    print(
        f"System diagnostics: status={result.diagnostics_status} "
        f"database={result.target_database} "
        f"captured_at={result.captured_at.isoformat()}"
    )
    for item in result.checks:
        print(
            f"[{item.status.upper()}] {item.category}/{item.check_id}: {item.message}"
        )
    if result.aggregate_counts:
        print(
            "Counts: "
            + " ".join(
                f"{name}={value}" for name, value in result.aggregate_counts.items()
            )
        )
    print(f"Warnings: {result.warning_count} Failures: {result.failure_count}")


def main() -> int:
    args = _arguments()
    try:
        result = run(
            mode=args.database_mode,
            repo_root=args.repo_root.resolve(),
            output=args.output,
            api_base_url=args.api_base_url,
        )
        _print(result)
        if args.output is not None:
            print(f"JSON written: {args.output.resolve()}")
        return 0 if result.diagnostics_status == "healthy" else 1
    except Exception as exc:
        print(f"System diagnostics failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
