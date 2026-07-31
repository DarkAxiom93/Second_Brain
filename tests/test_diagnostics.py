"""Focused unit coverage for operational diagnostics."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.diagnostics.models import DiagnosticCheck, build_result
from app.diagnostics.runner import run
from app.diagnostics.service import (
    inspect_provider_configuration,
    validate_api_base_url,
    validate_database_target,
)


def _item(check_id: str, category: str, status: str = "passed") -> DiagnosticCheck:
    return DiagnosticCheck(
        check_id=check_id,
        category=category,
        status=status,
        message="Safe result.",
    )


def test_overall_status_ordering_warnings_failures_and_json() -> None:
    captured = datetime(2026, 7, 31, tzinfo=UTC)
    result = build_result(
        captured_at=captured,
        target_database="second_brain",
        checks=[
            _item("z", "runtime", "warning"),
            _item("b", "configuration", "failed"),
            _item("a", "configuration"),
        ],
        aggregate_counts={"Projects": 2},
    )
    assert [(item.category, item.check_id) for item in result.checks] == [
        ("configuration", "a"),
        ("configuration", "b"),
        ("runtime", "z"),
    ]
    assert result.diagnostics_status == "unhealthy"
    assert result.warning_count == 1
    assert result.failure_count == 1
    assert '"diagnostics_status":"unhealthy"' in result.model_dump_json()


@pytest.mark.parametrize(
    ("message", "metadata"),
    [
        ("postgresql://user:value@host/database", {}),
        ("Safe.", {"password": "value"}),
        ("Safe.", {"actual": "user@example.test"}),
    ],
)
def test_safe_message_and_metadata_boundaries(
    message: str, metadata: dict[str, str]
) -> None:
    with pytest.raises(ValidationError, match=r"sensitive|unsupported"):
        DiagnosticCheck(
            check_id="safe",
            category="runtime",
            status="passed",
            message=message,
            metadata=metadata,
        )


def test_provider_inspection_does_not_resolve_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = Mock(side_effect=AssertionError("must not resolve"))
    monkeypatch.setattr("app.embeddings.dependencies.get_embedding_provider", resolver)
    checks = inspect_provider_configuration(Settings(openai_api_key=None))
    assert resolver.call_count == 0
    assert (
        next(item for item in checks if item.check_id == "provider_credentials").status
        == "warning"
    )


@pytest.mark.parametrize(
    "value",
    [
        "ftp://127.0.0.1",
        "http://user:value@127.0.0.1",
        "http://example.com",
        "http://localhost?leak=value",
    ],
)
def test_unsafe_api_base_url_rejected(value: str) -> None:
    with pytest.raises(ValueError, match=r"local|credential"):
        validate_api_base_url(value)


def test_database_identity_classification() -> None:
    _, development = validate_database_target(
        "postgresql+psycopg://user:value@127.0.0.1:5433/second_brain",
        "development",
    )
    _, confused = validate_database_target(
        "postgresql+psycopg://user:value@127.0.0.1:5433/second_brain",
        "test",
    )
    assert development[-1].status == "passed"
    assert confused[-1].status == "failed"


def test_existing_output_is_refused_before_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "existing.json"
    output.write_text("preserve", encoding="utf-8")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(FileExistsError, match="already exists"):
        run(
            mode="development",
            repo_root=Path.cwd(),
            output=output,
        )
    assert output.read_text(encoding="utf-8") == "preserve"
