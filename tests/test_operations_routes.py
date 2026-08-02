"""Public contract coverage for aggregate-only operations routes."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.config import Settings, get_settings
from app.db.dependencies import get_db_session
from app.diagnostics.models import DiagnosticCheck
from app.main import create_app
from app.memory_maintenance.models import AuditCategory, MemoryMaintenanceAudit


def _client(session: Mock) -> TestClient:
    def override_session() -> Generator[Mock, None, None]:
        yield session

    application = create_app()
    application.dependency_overrides[get_db_session] = override_session
    application.dependency_overrides[get_settings] = lambda: Settings(
        database_url=("postgresql+psycopg://user:value@127.0.0.1:5433/second_brain")
    )
    return TestClient(application)


def test_diagnostics_exposes_only_safe_ordered_fields(monkeypatch) -> None:
    session = Mock()
    session.connection.return_value = Mock()
    checks = [
        DiagnosticCheck(
            check_id="z_check",
            category="postgresql",
            status="passed",
            message="Safe PostgreSQL result.",
            metadata={"actual": "internal-value"},
        ),
        DiagnosticCheck(
            check_id="a_check",
            category="alembic",
            status="warning",
            message="Safe Alembic warning.",
            metadata={"revision": "0009_memory_expiration"},
        ),
    ]
    monkeypatch.setattr(
        "app.api.routes.operations.repository_head",
        lambda _: ("0009_memory_expiration", []),
    )
    monkeypatch.setattr(
        "app.api.routes.operations.inspect_provider_configuration", lambda _: []
    )
    monkeypatch.setattr(
        "app.api.routes.operations.inspect_database",
        lambda *args, **kwargs: (checks, {"Memories": 2, "Projects": 1}),
    )

    response = _client(session).get("/operations/diagnostics")

    assert response.status_code == 200
    body = response.json()
    assert [(item["category"], item["check_id"]) for item in body["checks"]] == [
        ("alembic", "a_check"),
        ("configuration", "database_configuration"),
        ("configuration", "database_identity"),
        ("postgresql", "z_check"),
    ]
    assert list(body["aggregate_counts"]) == ["Memories", "Projects"]
    assert all(
        set(item) == {"check_id", "category", "status", "message"}
        for item in body["checks"]
    )
    assert "metadata" not in response.text
    assert "internal-value" not in response.text
    assert "://" not in response.text
    session.execute.assert_called_once()
    session.flush.assert_not_called()
    session.commit.assert_not_called()


def test_maintenance_exposes_only_ordered_aggregate_findings(monkeypatch) -> None:
    session = Mock()
    session.scalar.return_value = "second_brain"

    def category(count: int) -> AuditCategory:
        return AuditCategory(count=count, memory_ids=[], truncated=count > 0)

    report = MemoryMaintenanceAudit(
        captured_at=datetime(2026, 8, 2, tzinfo=UTC),
        detail_limit=0,
        total_memories=5,
        project_assigned_memories=3,
        unassigned_memories=2,
        counts_by_status={
            "active": 4,
            "expired": 1,
            "archived": 0,
            "invalid": 0,
            "superseded": 0,
        },
        active_missing_embedding=category(2),
        active_stale_embedding=category(1),
        active_expiration_due=category(0),
        active_future_expiration=category(1),
        expired_missing_expires_at=category(0),
        non_active_with_embedding=category(1),
    )
    audit = Mock(return_value=report)
    monkeypatch.setattr("app.api.routes.operations.run_memory_maintenance_audit", audit)
    provider = Mock(side_effect=AssertionError("provider must not resolve"))
    monkeypatch.setattr("app.embeddings.dependencies.get_embedding_provider", provider)

    response = _client(session).get("/operations/maintenance-audit")

    assert response.status_code == 200
    body = response.json()
    assert [item["finding_id"] for item in body["findings"]] == sorted(
        item["finding_id"] for item in body["findings"]
    )
    assert all(set(item) == {"finding_id", "count"} for item in body["findings"])
    assert "memory_ids" not in response.text
    assert audit.call_args.kwargs["detail_limit"] == 0
    provider.assert_not_called()
    session.flush.assert_not_called()
    session.commit.assert_not_called()


def test_operations_database_failure_is_generic(monkeypatch) -> None:
    session = Mock()
    session.execute.side_effect = OperationalError(
        "statement", {}, Exception("postgresql://secret")
    )
    client = _client(session)
    for path in ("/operations/diagnostics", "/operations/maintenance-audit"):
        response = client.get(path)
        assert response.status_code == 503
        assert response.json() == {"detail": "database unavailable"}
        assert "secret" not in response.text


def test_maintenance_refuses_live_database_identity_mismatch(monkeypatch) -> None:
    session = Mock()
    session.scalar.return_value = "second_brain_test"
    audit = Mock(side_effect=AssertionError("audit must not run"))
    monkeypatch.setattr("app.api.routes.operations.run_memory_maintenance_audit", audit)

    response = _client(session).get("/operations/maintenance-audit")

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
    audit.assert_not_called()


def test_operations_are_documented_get_routes() -> None:
    schema = create_app().openapi()
    assert set(schema["paths"]["/operations/diagnostics"]) >= {"get"}
    assert set(schema["paths"]["/operations/maintenance-audit"]) >= {"get"}
