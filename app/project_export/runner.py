"""Safe command-line entry point for a Project export."""

import argparse
import os
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.project_export.service import export_project


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-mode", choices=("development", "test"), required=True
    )
    parser.add_argument("--project-id", type=UUID, required=True)
    parser.add_argument("--output", type=Path, required=True)
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


def main() -> int:
    args = _arguments()
    try:
        output = args.output.resolve()
        if output.suffix.lower() != ".sbexport":
            raise ValueError("OutputPath must use the .sbexport extension")
        database_url, expected_database = _database_url(args.database_mode)
        engine = create_engine(database_url, pool_pre_ping=True)
        try:
            with engine.connect().execution_options(
                isolation_level="REPEATABLE READ"
            ) as connection:
                connection.execute(text("SET TRANSACTION READ ONLY"))
                actual = connection.scalar(text("SELECT current_database()"))
                if actual != expected_database:
                    raise ValueError("live database identity mismatch")
                revision = connection.scalar(
                    text("SELECT version_num FROM alembic_version")
                )
                if revision != "0009_memory_expiration":
                    raise ValueError("unexpected Alembic revision")
                with Session(bind=connection, autoflush=False) as session:
                    result = export_project(
                        session,
                        args.project_id,
                        output,
                        source_alembic_revision=revision,
                    )
                connection.rollback()
        finally:
            engine.dispose()
        print(f"Project export written: {result.output_path}")
        print(
            f"format_version={result.format_version} project_id={result.project_id} "
            f"project_name={result.project_name}"
        )
        print(
            "entity_counts="
            + ",".join(f"{key}:{value}" for key, value in result.entity_counts.items())
        )
        print(
            f"package_bytes={result.package_byte_size} "
            f"package_sha256={result.package_sha256} "
            f"alembic_revision={result.source_alembic_revision}"
        )
        return 0
    except Exception as exc:
        print(f"Project export failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
