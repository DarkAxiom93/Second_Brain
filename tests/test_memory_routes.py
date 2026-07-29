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
        title=None,
        summary=None,
        memory_type="semantic",
        importance=0.5,
        confidence=1.0,
        status="active",
        event_time=None,
        expires_at=None,
        supersedes_id=None,
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
        "title",
        "summary",
        "memory_type",
        "importance",
        "confidence",
        "status",
        "event_time",
        "expires_at",
        "supersedes_id",
        "created_at",
        "updated_at",
    }
    assert response.json()["memory_type"] == "semantic"
    assert response.json()["importance"] == 0.5
    assert response.json()["confidence"] == 1.0
    assert response.json()["status"] == "active"
    exists.assert_not_called()
    session.commit.assert_called_once_with()


def test_full_metadata_post_returns_exact_values(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, _ = route_client
    stored = memory()
    timestamp = datetime.now(UTC)
    supersedes_id = uuid.uuid4()
    stored.title = "Title"
    stored.summary = "Summary"
    stored.memory_type = "decision"
    stored.importance = 0.8
    stored.confidence = 0.9
    stored.status = "archived"
    stored.event_time = timestamp
    stored.expires_at = timestamp
    stored.supersedes_id = supersedes_id
    monkeypatch.setattr(
        memory_routes.memory_repository, "create_memory", Mock(return_value=stored)
    )
    monkeypatch.setattr(
        memory_routes.memory_repository, "get_memory", Mock(return_value=memory())
    )
    response = client.post(
        "/memories",
        json={
            "content": "fact",
            "title": "Title",
            "summary": "Summary",
            "memory_type": "decision",
            "importance": 0.8,
            "confidence": 0.9,
            "status": "archived",
            "event_time": timestamp.isoformat(),
            "expires_at": timestamp.isoformat(),
            "supersedes_id": str(supersedes_id),
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Title"
    assert body["summary"] == "Summary"
    assert body["memory_type"] == "decision"
    assert body["importance"] == 0.8
    assert body["confidence"] == 0.9
    assert body["status"] == "archived"
    assert datetime.fromisoformat(body["event_time"]) == timestamp
    assert datetime.fromisoformat(body["expires_at"]) == timestamp
    assert body["supersedes_id"] == str(supersedes_id)


def test_post_unknown_supersedes_returns_exact_404_before_write(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, session = route_client
    missing_id = uuid.uuid4()
    monkeypatch.setattr(
        memory_routes.memory_repository, "get_memory", Mock(return_value=None)
    )
    create = Mock()
    monkeypatch.setattr(memory_routes.memory_repository, "create_memory", create)
    response = client.post(
        "/memories", json={"content": "fact", "supersedes_id": str(missing_id)}
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "superseded memory not found"}
    create.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_called_once_with()


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
    repository_call.assert_called_once()
    assert repository_call.call_args.args == (session,)
    assert repository_call.call_args.kwargs == {
        "project_id": project_id,
        "query": None,
        "memory_type": None,
        "status": None,
        "importance_min": None,
        "importance_max": None,
        "confidence_min": None,
        "confidence_max": None,
        "event_time_from": None,
        "event_time_to": None,
        "created_at_from": None,
        "created_at_to": None,
        "limit": 50,
        "offset": 0,
    }


def test_get_memories_trims_and_passes_search_query(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, _ = route_client
    repository_call = Mock(return_value=[])
    monkeypatch.setattr(
        memory_routes.memory_repository, "list_memories", repository_call
    )

    assert client.get("/memories?query=%20%20postgres%20%20").status_code == 200
    assert repository_call.call_args.kwargs["query"] == "postgres"


@pytest.mark.parametrize("query", ["%20%20%20", "x" * 501])
def test_get_memories_rejects_invalid_search_query(
    query: str, route_client: tuple[TestClient, Mock]
) -> None:
    client, _ = route_client
    assert client.get(f"/memories?query={query}").status_code == 422


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_get_memories_rejects_invalid_pagination(
    query: str, route_client: tuple[TestClient, Mock]
) -> None:
    client, _ = route_client
    assert client.get(f"/memories?{query}").status_code == 422


@pytest.mark.parametrize(
    "query",
    [
        "memory_type=unknown",
        "status=unknown",
        "importance_min=-0.1",
        "importance_max=1.1",
        "confidence_min=-0.1",
        "confidence_max=1.1",
        "importance_min=0.8&importance_max=0.2",
        "confidence_min=0.8&confidence_max=0.2",
        "event_time_from=2026-02-01T00:00:00Z&event_time_to=2026-01-01T00:00:00Z",
        "created_at_from=2026-02-01T00:00:00Z&created_at_to=2026-01-01T00:00:00Z",
        "event_time_from=2026-01-01T00:00:00",
        "created_at_to=2026-01-01T00:00:00",
    ],
)
def test_get_memories_rejects_invalid_filters(
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
        "/memories/{memory_id}/embedding",
        "/memories/{memory_id}/sources",
        "/sources",
        "/sources/{source_id}/memories",
    }
    assert set(paths["/projects"]) == {"get", "post"}
    assert set(paths["/memories"]) == {"get", "post"}
    assert set(paths["/memories/{memory_id}"]) == {"get"}
    assert set(paths["/memories/{memory_id}/embedding"]) == {"post"}
    assert client.get("/api/memories").status_code == 404
