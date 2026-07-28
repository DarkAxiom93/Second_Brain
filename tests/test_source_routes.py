"""Unit tests for Source creation and linking routes."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.routes import memories as memory_routes
from app.api.routes import sources as source_routes
from app.db.dependencies import get_db_session
from app.main import create_app
from app.models.memory import Memory
from app.models.source import Source


@pytest.fixture
def route_client() -> tuple[TestClient, Mock]:
    session = Mock()

    def override() -> Generator[Mock, None, None]:
        yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = override
    return TestClient(app), session


def test_create_source_returns_exact_fields_and_commits(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, session = route_client
    now = datetime.now(UTC)
    source = Source(
        id=uuid.uuid4(),
        source_type="note",
        name="Notes",
        reference=None,
        checksum=None,
        created_at=now,
        updated_at=now,
    )
    monkeypatch.setattr(
        source_routes.source_repository, "create_source", Mock(return_value=source)
    )
    response = client.post("/sources", json={"source_type": "note", "name": "Notes"})
    assert response.status_code == 201
    assert set(response.json()) == {
        "id",
        "source_type",
        "name",
        "reference",
        "checksum",
        "created_at",
        "updated_at",
    }
    session.commit.assert_called_once_with()


@pytest.mark.parametrize(
    "missing,detail", [("memory", "memory not found"), ("source", "source not found")]
)
def test_link_unknown_parent_exact_404(
    missing: str,
    detail: str,
    monkeypatch: pytest.MonkeyPatch,
    route_client: tuple[TestClient, Mock],
) -> None:
    client, session = route_client
    monkeypatch.setattr(
        memory_routes.memory_repository,
        "get_memory",
        Mock(return_value=None if missing == "memory" else Memory()),
    )
    monkeypatch.setattr(
        memory_routes.source_repository,
        "get_source",
        Mock(return_value=None if missing == "source" else Source()),
    )
    response = client.post(
        f"/memories/{uuid.uuid4()}/sources", json={"source_id": str(uuid.uuid4())}
    )
    assert response.status_code == 404 and response.json() == {"detail": detail}
    session.commit.assert_not_called()


def test_duplicate_link_and_integrity_race_return_exact_409(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, session = route_client
    monkeypatch.setattr(
        memory_routes.memory_repository, "get_memory", Mock(return_value=Memory())
    )
    monkeypatch.setattr(
        memory_routes.source_repository, "get_source", Mock(return_value=Source())
    )
    monkeypatch.setattr(
        memory_routes.source_repository,
        "memory_source_link_exists",
        Mock(return_value=True),
    )
    response = client.post(
        f"/memories/{uuid.uuid4()}/sources", json={"source_id": str(uuid.uuid4())}
    )
    assert response.status_code == 409 and response.json() == {
        "detail": "source already linked to memory"
    }
    session.commit.assert_not_called()


def test_database_failure_is_generic(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, session = route_client
    failure = OperationalError("secret SQL", {}, Exception("password=secret"))
    monkeypatch.setattr(
        source_routes.source_repository, "create_source", Mock(side_effect=failure)
    )
    response = client.post("/sources", json={"source_type": "note", "name": "Notes"})
    assert response.status_code == 503 and response.json() == {
        "detail": "database unavailable"
    }
    assert "secret" not in response.text
    session.rollback.assert_called_once_with()


def test_only_approved_source_paths_exist(
    route_client: tuple[TestClient, Mock],
) -> None:
    client, _ = route_client
    assert client.get("/sources").status_code == 405
    assert client.get("/api/sources").status_code == 404
