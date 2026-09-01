"""Focused read-only checks for configuration, PostgreSQL, and Alembic."""

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, inspect, text
from sqlalchemy.engine import URL, make_url

from app.core.config import Settings
from app.diagnostics.models import DiagnosticCheck

EXPECTED_HEAD = "0015_calendar_persistence"
EXPECTED_HOST = "127.0.0.1"
EXPECTED_PORT = 5433
MIN_POSTGRESQL_VERSION = 16
REQUIRED_TABLES = (
    "alembic_version",
    "projects",
    "memories",
    "memory_embeddings",
    "sources",
    "memory_sources",
    "source_documents",
    "source_chunks",
    "memory_extraction_runs",
    "memory_proposals",
    "calendar_account_revisions",
    "calendar_identities",
    "calendar_sync_runs",
    "calendar_event_revisions",
    "agent_runs",
    "agent_steps",
    "tool_invocations",
    "approval_requests",
    "agent_events",
    "connector_accounts",
    "connector_sync_runs",
    "external_items",
)
COUNT_TABLES = {
    "Projects": "projects",
    "Memories": "memories",
    "MemoryEmbeddings": "memory_embeddings",
    "Sources": "sources",
    "SourceDocuments": "source_documents",
    "SourceChunks": "source_chunks",
    "MemoryExtractionRuns": "memory_extraction_runs",
    "MemoryProposals": "memory_proposals",
}


def check(
    check_id: str,
    category: str,
    status: Literal["passed", "failed", "warning"],
    message: str,
    **metadata: str | int | bool | None,
) -> DiagnosticCheck:
    return DiagnosticCheck(
        check_id=check_id,
        category=category,
        status=status,
        message=message,
        metadata=metadata,
    )


def validate_database_target(
    value: str, mode: Literal["development", "test"]
) -> tuple[URL, list[DiagnosticCheck]]:
    """Parse and classify the configured URL without returning credentials."""

    expected = "second_brain" if mode == "development" else "second_brain_test"
    try:
        parsed = make_url(value)
    except Exception:
        return make_url("postgresql://invalid/invalid"), [
            check(
                "database_configuration",
                "configuration",
                "failed",
                "Database configuration could not be parsed.",
            )
        ]
    checks = [
        check(
            "database_configuration",
            "configuration",
            "passed",
            "Required database configuration is present and parseable.",
        )
    ]
    identity_ok = (
        parsed.drivername.startswith("postgresql")
        and parsed.host == EXPECTED_HOST
        and parsed.port == EXPECTED_PORT
        and parsed.database == expected
    )
    checks.append(
        check(
            "database_identity",
            "configuration",
            "passed" if identity_ok else "failed",
            (
                "Parsed database target matches the documented local identity."
                if identity_ok
                else (
                    "Parsed database target does not match the selected local identity."
                )
            ),
            host=parsed.host,
            port=parsed.port,
            database=parsed.database,
            expected=expected,
        )
    )
    return parsed, checks


def inspect_provider_configuration(settings: Settings) -> list[DiagnosticCheck]:
    """Inspect values only; deliberately never imports provider dependencies."""

    configured = all(
        (
            settings.embedding_provider,
            settings.embedding_model,
            settings.extraction_provider,
            settings.extraction_model,
            settings.answer_provider,
            settings.answer_model,
        )
    )
    has_key = bool(
        settings.openai_api_key and settings.openai_api_key.get_secret_value().strip()
    )
    return [
        check(
            "embedding_dimensions",
            "configuration",
            "passed" if settings.embedding_dimensions == 1536 else "failed",
            "Configured embedding dimensions are valid."
            if settings.embedding_dimensions == 1536
            else "Configured embedding dimensions are invalid.",
            dimensions=settings.embedding_dimensions,
        ),
        check(
            "provider_configuration",
            "configuration",
            "passed" if configured else "failed",
            "Provider and model names required by workflows are configured."
            if configured
            else "A required provider or model name is missing.",
        ),
        check(
            "provider_credentials",
            "configuration",
            "passed" if has_key else "warning",
            "Provider credentials are configured."
            if has_key
            else (
                "Provider-backed workflows are unavailable until credentials "
                "are configured."
            ),
        ),
    ]


def validate_api_base_url(value: str) -> str:
    """Allow only credential-free loopback HTTP(S) URLs."""

    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("ApiBaseUrl must be a credential-free local HTTP(S) target")
    try:
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("ApiBaseUrl has an invalid port") from exc
    return value.rstrip("/")


def repository_head(repo_root: Path) -> tuple[str | None, list[DiagnosticCheck]]:
    config = Config(str(repo_root / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    sole = heads[0] if len(heads) == 1 else None
    return sole, [
        check(
            "repository_head",
            "alembic",
            "passed" if sole == EXPECTED_HEAD else "failed",
            "Repository has the expected sole Alembic head."
            if sole == EXPECTED_HEAD
            else "Repository does not have the expected sole Alembic head.",
            head=sole,
            expected=EXPECTED_HEAD,
        )
    ]


def inspect_database(
    connection: Connection, *, expected_database: str, head: str | None
) -> tuple[list[DiagnosticCheck], dict[str, int]]:
    """Run bounded SELECT/inspection operations inside a read-only transaction."""

    checks: list[DiagnosticCheck] = []
    actual = connection.scalar(text("SELECT current_database()"))
    checks.append(
        check(
            "connection",
            "postgresql",
            "passed",
            "PostgreSQL connection succeeded.",
        )
    )
    checks.append(
        check(
            "current_database",
            "postgresql",
            "passed" if actual == expected_database else "failed",
            "Live database identity matches the parsed target."
            if actual == expected_database
            else "Live database identity does not match the parsed target.",
            actual=actual,
            expected=expected_database,
        )
    )
    version_num = int(connection.scalar(text("SHOW server_version_num")))
    checks.append(
        check(
            "server_version",
            "postgresql",
            "passed" if version_num // 10000 >= MIN_POSTGRESQL_VERSION else "failed",
            "PostgreSQL server version is supported."
            if version_num // 10000 >= MIN_POSTGRESQL_VERSION
            else "PostgreSQL server version is unsupported.",
            version=version_num,
        )
    )
    read_only = connection.scalar(text("SHOW transaction_read_only"))
    checks.append(
        check(
            "transaction_read_only",
            "postgresql",
            "passed" if read_only == "on" else "failed",
            "Diagnostics transaction is database-enforced read-only."
            if read_only == "on"
            else "Diagnostics transaction is not read-only.",
            actual=read_only,
        )
    )
    vector_version = connection.scalar(
        text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
    )
    checks.append(
        check(
            "pgvector",
            "postgresql",
            "passed" if vector_version else "failed",
            "pgvector extension is installed."
            if vector_version
            else "pgvector extension is missing.",
            version=vector_version,
        )
    )
    tables = set(inspect(connection).get_table_names())
    missing = sorted(set(REQUIRED_TABLES) - tables)
    checks.append(
        check(
            "required_tables",
            "postgresql",
            "failed" if missing else "passed",
            "Required application tables exist."
            if not missing
            else "One or more required application tables are missing.",
        )
    )
    current = (
        connection.scalar(text("SELECT version_num FROM alembic_version"))
        if "alembic_version" in tables
        else None
    )
    consistent = current == head == EXPECTED_HEAD
    checks.extend(
        [
            check(
                "current_revision",
                "alembic",
                "passed" if current == EXPECTED_HEAD else "failed",
                "Database is at the expected Alembic revision."
                if current == EXPECTED_HEAD
                else "Database is not at the expected Alembic revision.",
                revision=current,
                expected=EXPECTED_HEAD,
            ),
            check(
                "pending_upgrade",
                "alembic",
                "passed" if consistent else "failed",
                "No pending Alembic upgrade exists."
                if consistent
                else "Database and repository Alembic revisions differ.",
                revision=current,
                head=head,
            ),
        ]
    )
    counts: dict[str, int] = {}
    if not missing:
        for label, table_name in COUNT_TABLES.items():
            counts[label] = int(
                connection.scalar(text(f'SELECT count(*) FROM "{table_name}"')) or 0
            )
        checks.append(
            check(
                "aggregate_counts",
                "application_state",
                "passed",
                "Safe application aggregate counts were collected.",
            )
        )
    else:
        checks.append(
            check(
                "aggregate_counts",
                "application_state",
                "failed",
                "Aggregate counts could not be collected because required "
                "tables are missing.",
            )
        )
    return checks, counts
