"""Unit tests for Memory routes."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.routes import memories as memory_routes
from app.db.dependencies import get_db_session
from app.main import create_app
from app.models.memory import Memory


@pytest.fixture
def route_client() -> tuple[TestClient, Mock]:
    session = Mock()

    def override_session() -> Generator[Mock, None, None]:
        yield session

    application = create_app()
    application.dependency_overrides[get_db_session] = override_session
    return TestClient(application), session


def memory(project_id: uuid.UUID | None = None) -> Memory:
    timestamp = datetime.now(UTC)
    return Memory(
        id=uuid.uuid4(),
        project_id=project_id,
        content="fact",
        source="note",
        created_at=timestamp,
        updated_at=timestamp,
    )


def test_post_unassigned_memory_commits_once(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, session = route_client
    stored = memory()
    monkeypatch.setattr(
        memory_routes.memory_repository, "create_memory", Mock(return_value=stored)
    )
    exists = Mock()
    monkeypatch.setattr(memory_routes.memory_repository, "project_exists", exists)
    response = client.post("/memories", json={"content": " fact ", "source": " note "})
    assert response.status_code == 201
    assert set(response.json()) == {
        "id",
        "project_id",
        "content",
        "source",
        "created_at",
        "updated_at",
    }
    exists.assert_not_called()
    session.commit.assert_called_once_with()


def test_memory_api_does_not_accept_or_expose_metadata(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, _ = route_client
    stored = memory()
    stored.title = "internal title"
    monkeypatch.setattr(
        memory_routes.memory_repository, "create_memory", Mock(return_value=stored)
    )
    assert (
        client.post(
            "/memories", json={"content": "fact", "title": "not public"}
        ).status_code
        == 422
    )
    response = client.post("/memories", json={"content": "fact"})
    assert response.status_code == 201
    assert "title" not in response.json()


def test_post_unknown_project_returns_exact_404(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, session = route_client
    monkeypatch.setattr(
        memory_routes.memory_repository, "project_exists", Mock(return_value=False)
    )
    response = client.post(
        "/memories", json={"project_id": str(uuid.uuid4()), "content": "fact"}
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "project not found"}
    session.commit.assert_not_called()
    session.rollback.assert_called_once_with()


def test_invalid_input_returns_422_without_transaction(
    route_client: tuple[TestClient, Mock],
) -> None:
    client, session = route_client
    assert client.post("/memories", json={"content": "   "}).status_code == 422
    session.commit.assert_not_called()


def test_database_failure_returns_generic_503(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, session = route_client
    failure = OperationalError("sensitive SQL", {}, Exception("password=secret"))
    monkeypatch.setattr(
        memory_routes.memory_repository, "create_memory", Mock(side_effect=failure)
    )
    response = client.post("/memories", json={"content": "fact"})
    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
    assert "sensitive" not in response.text and "secret" not in response.text
    session.rollback.assert_called_once_with()


def test_get_memories_uses_filter_and_default_pagination(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, session = route_client
    project_id = uuid.uuid4()
    repository_call = Mock(return_value=[])
    monkeypatch.setattr(
        memory_routes.memory_repository, "list_memories", repository_call
    )

    response = client.get(f"/memories?project_id={project_id}")

    assert response.status_code == 200
    assert response.json() == []
    repository_call.assert_called_once_with(
        session, project_id=project_id, limit=50, offset=0
    )


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_get_memories_rejects_invalid_pagination(
    query: str, route_client: tuple[TestClient, Mock]
) -> None:
    client, _ = route_client
    assert client.get(f"/memories?{query}").status_code == 422


def test_get_existing_memory_and_unknown_and_malformed_uuid(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, _ = route_client
    stored = memory()
    repository_call = Mock(return_value=stored)
    monkeypatch.setattr(memory_routes.memory_repository, "get_memory", repository_call)
    assert client.get(f"/memories/{stored.id}").status_code == 200
    repository_call.return_value = None
    missing = client.get(f"/memories/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "memory not found"}
    assert client.get("/memories/not-a-uuid").status_code == 422


@pytest.mark.parametrize("endpoint", ["/memories", f"/memories/{uuid.uuid4()}"])
def test_memory_retrieval_database_failure_returns_generic_503(
    endpoint: str,
    monkeypatch: pytest.MonkeyPatch,
    route_client: tuple[TestClient, Mock],
) -> None:
    client, _ = route_client
    failure = OperationalError("sensitive SQL", {}, Exception("password=secret"))
    name = "list_memories" if endpoint == "/memories" else "get_memory"
    monkeypatch.setattr(
        memory_routes.memory_repository, name, Mock(side_effect=failure)
    )
    response = client.get(endpoint)
    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
    assert "sensitive" not in response.text and "secret" not in response.text


def test_memory_paths_and_existing_endpoints_are_registered(
    route_client: tuple[TestClient, Mock],
) -> None:
    client, _ = route_client
    paths = client.app.openapi()["paths"]
    assert set(paths) == {
        "/health",
        "/ready",
        "/projects",
        "/memories",
        "/memories/{memory_id}",
        "/memories/{memory_id}/sources",
        "/sources",
        "/sources/{source_id}/memories",
    }
    assert set(paths["/projects"]) == {"get", "post"}
    assert set(paths["/memories"]) == {"get", "post"}
    assert set(paths["/memories/{memory_id}"]) == {"get"}
    assert client.get("/api/memories").status_code == 404
