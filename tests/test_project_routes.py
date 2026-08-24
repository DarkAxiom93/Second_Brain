"""Unit tests for Project routes without PostgreSQL."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.routes import projects as project_routes
from app.db.dependencies import get_db_session
from app.main import create_app
from app.models.project import Project


@pytest.fixture
def project() -> Project:
    timestamp = datetime.now(UTC)
    return Project(
        id=uuid.uuid4(),
        name="Pure Axiom",
        description="Interactive mathematics platform",
        created_at=timestamp,
        updated_at=timestamp,
    )


@pytest.fixture
def route_client() -> tuple[TestClient, Mock]:
    session = Mock()

    def override_session() -> Generator[Mock, None, None]:
        yield session

    application = create_app()
    application.dependency_overrides[get_db_session] = override_session
    return TestClient(application), session


def test_post_projects_returns_201_and_exact_fields(
    monkeypatch: pytest.MonkeyPatch,
    route_client: tuple[TestClient, Mock],
    project: Project,
) -> None:
    client, session = route_client
    monkeypatch.setattr(
        project_routes.project_repository, "create_project", Mock(return_value=project)
    )

    response = client.post(
        "/projects",
        json={"name": project.name, "description": project.description},
    )

    assert response.status_code == 201
    assert set(response.json()) == {
        "id",
        "name",
        "description",
        "created_at",
        "updated_at",
    }
    session.commit.assert_called_once_with()
    session.refresh.assert_called_once_with(project)


@pytest.mark.parametrize("name", ["", "   ", "x" * 201])
def test_post_projects_rejects_invalid_name(
    name: str,
    route_client: tuple[TestClient, Mock],
) -> None:
    client, session = route_client
    response = client.post("/projects", json={"name": name})
    assert response.status_code == 422
    session.commit.assert_not_called()


def test_get_projects_uses_default_pagination(
    monkeypatch: pytest.MonkeyPatch,
    route_client: tuple[TestClient, Mock],
) -> None:
    client, session = route_client
    repository_call = Mock(return_value=[])
    monkeypatch.setattr(
        project_routes.project_repository, "list_projects", repository_call
    )

    response = client.get("/projects")

    assert response.status_code == 200
    assert response.json() == []
    repository_call.assert_called_once_with(session, limit=50, offset=0)
    session.commit.assert_not_called()


def test_get_project_returns_complete_project_read_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
    route_client: tuple[TestClient, Mock],
    project: Project,
) -> None:
    client, session = route_client
    repository_call = Mock(return_value=project)
    monkeypatch.setattr(
        project_routes.project_repository, "get_project", repository_call
    )

    response = client.get(f"/projects/{project.id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
        "created_at": project.created_at.isoformat().replace("+00:00", "Z"),
        "updated_at": project.updated_at.isoformat().replace("+00:00", "Z"),
    }
    repository_call.assert_called_once_with(session, project.id)
    session.commit.assert_not_called()
    session.flush.assert_not_called()


def test_get_missing_project_returns_exact_404(
    monkeypatch: pytest.MonkeyPatch,
    route_client: tuple[TestClient, Mock],
) -> None:
    client, session = route_client
    project_id = uuid.uuid4()
    monkeypatch.setattr(
        project_routes.project_repository, "get_project", Mock(return_value=None)
    )

    response = client.get(f"/projects/{project_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "project not found"}
    session.commit.assert_not_called()
    session.flush.assert_not_called()


def test_get_project_rejects_malformed_uuid_before_repository(
    monkeypatch: pytest.MonkeyPatch,
    route_client: tuple[TestClient, Mock],
) -> None:
    client, session = route_client
    repository_call = Mock()
    monkeypatch.setattr(
        project_routes.project_repository, "get_project", repository_call
    )

    response = client.get("/projects/not-a-uuid")

    assert response.status_code == 422
    repository_call.assert_not_called()
    session.commit.assert_not_called()
    session.flush.assert_not_called()


def test_get_project_database_failure_returns_generic_503(
    monkeypatch: pytest.MonkeyPatch,
    route_client: tuple[TestClient, Mock],
) -> None:
    client, session = route_client
    failure = OperationalError("sensitive SQL", {}, Exception("password=secret"))
    monkeypatch.setattr(
        project_routes.project_repository, "get_project", Mock(side_effect=failure)
    )

    response = client.get(f"/projects/{uuid.uuid4()}")

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
    assert "sensitive" not in response.text
    assert "secret" not in response.text
    session.commit.assert_not_called()
    session.flush.assert_not_called()


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_get_projects_rejects_invalid_pagination(
    query: str,
    route_client: tuple[TestClient, Mock],
) -> None:
    client, _ = route_client
    assert client.get(f"/projects?{query}").status_code == 422


@pytest.mark.parametrize("method", ["post", "get"])
def test_project_database_failure_returns_generic_503(
    method: str,
    monkeypatch: pytest.MonkeyPatch,
    route_client: tuple[TestClient, Mock],
) -> None:
    client, session = route_client
    failure = OperationalError("sensitive SQL", {}, Exception("password=secret"))
    if method == "post":
        monkeypatch.setattr(
            project_routes.project_repository,
            "create_project",
            Mock(side_effect=failure),
        )
        response = client.post("/projects", json={"name": "Pure Axiom"})
        session.rollback.assert_called_once_with()
    else:
        monkeypatch.setattr(
            project_routes.project_repository,
            "list_projects",
            Mock(side_effect=failure),
        )
        response = client.get("/projects")

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
    assert "sensitive" not in response.text
    assert "secret" not in response.text


def test_existing_routes_and_only_public_project_paths_remain_present(
    route_client: tuple[TestClient, Mock],
) -> None:
    client, _ = route_client
    paths = client.app.openapi()["paths"]
    assert set(paths) == {
        "/agent-runs",
        "/agent-runs/{run_id}",
        "/agent-runs/{run_id}/cancel",
        "/agent-runs/{run_id}/plan",
        "/agent-runs/{run_id}/execute",
        "/agent-runs/{run_id}/execution",
        "/agent-runs/{run_id}/approval-requests",
        "/approval-requests/{approval_id}",
        "/approval-requests/{approval_id}/review",
        "/answers",
        "/automations",
        "/automations/preview",
        "/automations/{automation_id}",
        "/automations/{automation_id}/enable",
        "/automations/{automation_id}/pause",
        "/automations/{automation_id}/resume",
        "/automations/{automation_id}/cancel",
        "/health",
        "/ready",
        "/projects",
        "/projects/{project_id}",
        "/memories",
        "/memories/search",
        "/memories/search/explained",
        "/memories/{memory_id}",
        "/memories/{memory_id}/embedding",
        "/memories/{memory_id}/expire",
        "/memories/{memory_id}/quality",
        "/memories/{memory_id}/contradictions",
        "/memories/{memory_id}/similarities",
        "/memories/{memory_id}/supersede",
        "/memories/{memory_id}/sources",
        "/memory-proposals",
        "/memory-proposals/{proposal_id}",
        "/memory-proposals/{proposal_id}/approve",
        "/memory-proposals/{proposal_id}/reject",
        "/memory-proposals/{proposal_id}/promote",
        "/memory-embeddings/batch",
        "/memory-embeddings/reembed",
        "/operations/diagnostics",
        "/operations/maintenance-audit",
        "/operations/project-exports/{project_id}",
        "/operations/project-imports/validate",
        "/operations/project-imports/execute",
        "/sources",
        "/sources/{source_id}",
        "/sources/{source_id}/document/file",
        "/sources/{source_id}/document/text",
        "/sources/{source_id}/memories",
        "/sources/{source_id}/memory-proposals",
        "/sources/{source_id}/documents",
        "/source-documents/{document_id}",
        "/source-documents/{document_id}/chunks",
    }
    assert set(paths["/projects"]) == {"get", "post"}
    assert set(paths["/projects/{project_id}"]) == {"get"}
    assert set(paths["/projects/{project_id}"]["get"]["responses"]) == {
        "200",
        "404",
        "422",
        "503",
    }
    assert set(paths["/memories"]) == {"get", "post"}
