"""Public contract coverage for aggregate-only operations routes."""

from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.config import Settings, get_settings
from app.db.dependencies import get_db_session
from app.diagnostics.models import DiagnosticCheck
from app.main import create_app
from app.memory_maintenance.models import AuditCategory, MemoryMaintenanceAudit
from app.project_export.models import ExportManifest
from app.project_import.models import ImportConflictError, ImportResult


def _client(session: Mock, *, loopback: bool = False) -> TestClient:
    def override_session() -> Generator[Mock, None, None]:
        yield session

    application = create_app()
    application.dependency_overrides[get_db_session] = override_session
    application.dependency_overrides[get_settings] = lambda: Settings(
        database_url=("postgresql+psycopg://user:value@127.0.0.1:5433/second_brain")
    )
    return TestClient(
        application, client=("127.0.0.1", 54321) if loopback else ("testclient", 50000)
    )


def _local_client(session: Mock) -> TestClient:
    return _client(session, loopback=True)


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


def test_project_export_requires_direct_loopback_and_exact_header(monkeypatch) -> None:
    session = Mock()
    called = Mock()
    monkeypatch.setattr("app.api.routes.operations.export_project", called)
    project_id = uuid4()
    client = _client(session)

    assert client.post(f"/operations/project-exports/{project_id}").status_code == 403
    response = client.post(
        f"/operations/project-exports/{project_id}",
        headers={
            "X-Second-Brain-Operation": "project-export-v1",
            "X-Forwarded-For": "127.0.0.1",
        },
    )
    assert response.status_code == 403
    called.assert_not_called()


def test_project_export_streams_safe_attachment_and_cleans_exact_file(
    monkeypatch,
) -> None:
    session = Mock()
    session.scalar.side_effect = ["second_brain", "0015_calendar_persistence"]
    created: list[Path] = []

    captured: dict[str, str] = {}

    def fake_export(_session, project_id, output, **kwargs):
        created.append(output)
        captured.update(kwargs)
        output.write_bytes(b"bundle")

    monkeypatch.setattr("app.api.routes.operations.export_project", fake_export)
    project_id = uuid4()
    response = _local_client(session).post(
        f"/operations/project-exports/{project_id}",
        headers={"X-Second-Brain-Operation": "project-export-v1"},
    )
    assert response.status_code == 200
    assert response.content == b"bundle"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert (
        response.headers["content-disposition"]
        == f'attachment; filename="project-{project_id}.sbexport"'
    )
    assert created and not created[0].exists()
    assert captured == {"source_alembic_revision": "0015_calendar_persistence"}
    session.commit.assert_not_called()


def test_project_export_rejects_legacy_target_revision(monkeypatch) -> None:
    session = Mock()
    session.scalar.side_effect = ["second_brain", "0009_memory_expiration"]
    exporter = Mock()
    monkeypatch.setattr("app.api.routes.operations.export_project", exporter)
    response = _local_client(session).post(
        f"/operations/project-exports/{uuid4()}",
        headers={"X-Second-Brain-Operation": "project-export-v1"},
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
    exporter.assert_not_called()


def test_project_import_rejects_legacy_target_revision() -> None:
    session = Mock()
    session.scalar.side_effect = ["second_brain", "0009_memory_expiration"]
    response = _local_client(session).post(
        "/operations/project-imports/validate",
        content=b"not-read",
        headers={
            "Content-Type": "application/octet-stream",
            "X-Second-Brain-Operation": "project-import-validate-v1",
        },
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}


def test_import_validation_returns_safe_conflict_plan_and_cleans_upload(
    monkeypatch,
) -> None:
    session = Mock()
    session.scalar.side_effect = ["second_brain", "0015_calendar_persistence"]
    project_id = uuid4()
    manifest = ExportManifest(
        exported_at=datetime(2026, 8, 2, tzinfo=UTC),
        source_alembic_revision="0009_memory_expiration",
        project_id=project_id,
        project_name="Safe Project",
        entity_counts={"project": 1},
        files=[],
    )
    paths: list[Path] = []
    monkeypatch.setattr(
        "app.api.routes.operations.load_bundle",
        lambda path: (paths.append(path) or manifest, {}, "a" * 64),
    )
    monkeypatch.setattr(
        "app.api.routes.operations.import_project",
        Mock(side_effect=ImportConflictError("project.json primary-key conflict")),
    )
    response = _local_client(session).post(
        "/operations/project-imports/validate",
        content=b"zip",
        headers={
            "Content-Type": "application/octet-stream",
            "X-Second-Brain-Operation": "project-import-validate-v1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["validation_status"] == "valid" and body["importable"] is False
    assert body["conflicts"] == ["project.json primary-key conflict"]
    assert "path" not in response.text.lower()
    assert paths and not paths[0].exists()
    session.commit.assert_not_called()


def test_import_execute_requires_exact_confirmations_and_commits_once(
    monkeypatch,
) -> None:
    session = Mock()
    session.scalar.side_effect = ["second_brain", "0015_calendar_persistence"]
    project_id = uuid4()
    manifest = ExportManifest(
        exported_at=datetime(2026, 8, 2, tzinfo=UTC),
        source_alembic_revision="0009_memory_expiration",
        project_id=project_id,
        project_name="Safe Project",
        entity_counts={"project": 1},
        files=[],
    )
    result = ImportResult(
        import_status="imported",
        format_name=manifest.format_name,
        format_version=1,
        project_id=project_id,
        project_name="Safe Project",
        source_alembic_revision="0009_memory_expiration",
        entity_counts={"project": 1},
        bundle_sha256="b" * 64,
    )
    monkeypatch.setattr(
        "app.api.routes.operations.load_bundle", lambda _path: (manifest, {}, "b" * 64)
    )
    importer = Mock(return_value=result)
    monkeypatch.setattr("app.api.routes.operations.import_project", importer)
    query = f"expected_project_id={project_id}&expected_bundle_sha256={'b' * 64}"
    response = _local_client(session).post(
        f"/operations/project-imports/execute?{query}",
        content=b"zip",
        headers={
            "Content-Type": "application/octet-stream",
            "X-Second-Brain-Operation": "project-import-execute-v1",
        },
    )
    assert response.status_code == 200
    assert set(response.json()) == {
        "import_status",
        "format_name",
        "format_version",
        "project_id",
        "project_name",
        "source_alembic_revision",
        "entity_counts",
        "bundle_sha256",
    }
    session.commit.assert_called_once_with()
    importer.assert_called_once()
