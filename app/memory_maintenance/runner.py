"""Command-line entry point for the read-only Memory maintenance audit."""

import argparse
import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.memory_maintenance.models import MemoryMaintenanceAudit
from app.memory_maintenance.service import run_memory_maintenance_audit


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-mode", choices=("development", "test"), required=True
    )
    parser.add_argument("--detail-limit", type=int, default=100)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _database_url(mode: str) -> tuple[str, str]:
    variable = "DATABASE_URL" if mode == "development" else "TEST_DATABASE_URL"
    expected = "second_brain" if mode == "development" else "second_brain_test"
    value = os.environ.get(variable)
    if not value:
        raise ValueError(f"{variable} is required")
    parsed = make_url(value)
    if parsed.host != "127.0.0.1" or parsed.database != expected:
        raise ValueError(
            f"{variable} must target host 127.0.0.1 and database {expected}"
        )
    return value, expected


def _print_summary(report: MemoryMaintenanceAudit, database: str) -> None:
    print(
        f"Memory maintenance audit: database={database} "
        f"captured_at={report.captured_at.isoformat()}"
    )
    print(
        f"Memories: total={report.total_memories} "
        f"assigned={report.project_assigned_memories} "
        f"unassigned={report.unassigned_memories}"
    )
    print(
        "Statuses: "
        + " ".join(f"{name}={count}" for name, count in report.counts_by_status.items())
    )
    for name in (
        "active_missing_embedding",
        "active_stale_embedding",
        "active_expiration_due",
        "active_future_expiration",
        "expired_missing_expires_at",
        "non_active_with_embedding",
    ):
        category = getattr(report, name)
        suffix = " (details truncated)" if category.truncated else ""
        print(f"{name}: {category.count}{suffix}")


def main() -> int:
    args = _arguments()
    try:
        database_url, expected_database = _database_url(args.database_mode)
        settings = Settings(database_url=database_url)
        engine = create_engine(database_url, pool_pre_ping=True)
        try:
            with engine.connect() as connection:
                actual_database = connection.scalar(text("SELECT current_database()"))
                if actual_database != expected_database:
                    raise ValueError("live database identity mismatch")
                connection.execute(text("SET TRANSACTION READ ONLY"))
                with Session(bind=connection) as session:
                    report = run_memory_maintenance_audit(
                        session,
                        expected_embedding_identity=(
                            settings.embedding_provider,
                            settings.embedding_model,
                            settings.embedding_dimensions,
                        ),
                        detail_limit=args.detail_limit,
                    )
                connection.rollback()
        finally:
            engine.dispose()
        _print_summary(report, expected_database)
        if args.output is not None:
            output = args.output.resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
            print(f"JSON written: {output}")
        return 0
    except Exception as exc:
        print(f"Memory maintenance audit failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
