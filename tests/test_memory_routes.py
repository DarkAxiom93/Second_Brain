"""Unit tests for the Memory creation route."""

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


def test_only_post_memory_path_is_registered(
    route_client: tuple[TestClient, Mock],
) -> None:
    client, _ = route_client
    paths = client.app.openapi()["paths"]
    assert set(paths) == {"/health", "/ready", "/projects", "/memories"}
    assert set(paths["/projects"]) == {"get", "post"}
    assert set(paths["/memories"]) == {"post"}
    assert client.get("/memories").status_code == 405
    assert client.get("/api/memories").status_code == 404
