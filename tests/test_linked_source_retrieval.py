"""Unit tests for linked Source and Memory retrieval."""

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
from app.repositories.sources import LinkedMemory, LinkedSource


@pytest.fixture
def route_client() -> tuple[TestClient, Mock]:
    session = Mock()

    def override() -> Generator[Mock, None, None]:
        yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = override
    return TestClient(app), session


def test_linked_repositories_use_one_joined_paginated_query() -> None:
    from app.repositories.sources import (
        list_memories_for_source,
        list_sources_for_memory,
    )

    session = Mock()
    session.execute.return_value.all.return_value = []
    parent_id = uuid.uuid4()
    assert (
        list_sources_for_memory(session, memory_id=parent_id, limit=10, offset=20) == []
    )
    source_sql = str(session.execute.call_args.args[0].compile()).lower()
    assert " join sources " in source_sql
    assert (
        "order by memory_sources.created_at desc, memory_sources.id asc" in source_sql
    )
    assert " limit " in source_sql and " offset " in source_sql

    session.reset_mock()
    session.execute.return_value.all.return_value = []
    assert (
        list_memories_for_source(session, source_id=parent_id, limit=5, offset=2) == []
    )
    memory_sql = str(session.execute.call_args.args[0].compile()).lower()
    assert " join memories " in memory_sql
    assert (
        "order by memory_sources.created_at desc, memory_sources.id asc" in memory_sql
    )
    assert session.execute.call_count == 1
    session.commit.assert_not_called()


def test_linked_routes_return_exact_fields_and_forward_pagination(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, session = route_client
    now = datetime.now(UTC)
    memory_id, source_id, link_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    monkeypatch.setattr(
        memory_routes.memory_repository, "get_memory", Mock(return_value=Memory())
    )
    source_call = Mock(
        return_value=[
            LinkedSource(
                link_id,
                memory_id,
                source_id,
                None,
                now,
                "note",
                "N",
                None,
                "sum",
                now,
                now,
            )
        ]
    )
    monkeypatch.setattr(
        memory_routes.source_repository, "list_sources_for_memory", source_call
    )
    response = client.get(f"/memories/{memory_id}/sources?limit=7&offset=3")
    assert response.status_code == 200
    assert set(response.json()[0]) == {
        "link_id",
        "memory_id",
        "source_id",
        "source_location",
        "linked_at",
        "source_type",
        "name",
        "reference",
        "checksum",
        "source_created_at",
        "source_updated_at",
    }
    source_call.assert_called_once_with(session, memory_id=memory_id, limit=7, offset=3)

    monkeypatch.setattr(
        source_routes.source_repository, "get_source", Mock(return_value=Source())
    )
    memory_call = Mock(
        return_value=[
            LinkedMemory(
                link_id,
                source_id,
                memory_id,
                "p. 2",
                now,
                None,
                "body",
                "legacy",
                "Title",
                "Summary",
                "semantic",
                0.5,
                1.0,
                "active",
                now,
                now,
                None,
                now,
                now,
            )
        ]
    )
    monkeypatch.setattr(
        source_routes.source_repository, "list_memories_for_source", memory_call
    )
    response = client.get(f"/sources/{source_id}/memories")
    assert response.status_code == 200
    assert set(response.json()[0]) == {
        "link_id",
        "source_id",
        "memory_id",
        "source_location",
        "linked_at",
        "project_id",
        "content",
        "legacy_source",
        "title",
        "summary",
        "memory_type",
        "importance",
        "confidence",
        "status",
        "event_time",
        "expires_at",
        "supersedes_id",
        "memory_created_at",
        "memory_updated_at",
    }


def test_unknown_parents_and_empty_pages(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, _ = route_client
    monkeypatch.setattr(
        memory_routes.memory_repository, "get_memory", Mock(return_value=None)
    )
    response = client.get(f"/memories/{uuid.uuid4()}/sources")
    assert response.status_code == 404
    assert response.json() == {"detail": "memory not found"}

    monkeypatch.setattr(
        source_routes.source_repository, "get_source", Mock(return_value=None)
    )
    response = client.get(f"/sources/{uuid.uuid4()}/memories")
    assert response.status_code == 404
    assert response.json() == {"detail": "source not found"}

    monkeypatch.setattr(
        memory_routes.memory_repository, "get_memory", Mock(return_value=Memory())
    )
    monkeypatch.setattr(
        memory_routes.source_repository,
        "list_sources_for_memory",
        Mock(return_value=[]),
    )
    assert client.get(f"/memories/{uuid.uuid4()}/sources").json() == []


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_linked_routes_reject_invalid_pagination(
    query: str, route_client: tuple[TestClient, Mock]
) -> None:
    client, _ = route_client
    assert client.get(f"/memories/{uuid.uuid4()}/sources?{query}").status_code == 422
    assert client.get(f"/sources/{uuid.uuid4()}/memories?{query}").status_code == 422


@pytest.mark.parametrize("direction", ["sources", "memories"])
def test_linked_route_database_failure_is_generic(
    direction: str,
    monkeypatch: pytest.MonkeyPatch,
    route_client: tuple[TestClient, Mock],
) -> None:
    client, _ = route_client
    failure = OperationalError("secret SQL", {}, Exception("password=secret"))
    if direction == "sources":
        monkeypatch.setattr(
            memory_routes.memory_repository, "get_memory", Mock(side_effect=failure)
        )
        url = f"/memories/{uuid.uuid4()}/sources"
    else:
        monkeypatch.setattr(
            source_routes.source_repository, "get_source", Mock(side_effect=failure)
        )
        url = f"/sources/{uuid.uuid4()}/memories"
    response = client.get(url)
    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
    assert "secret" not in response.text


def test_existing_route_scope_remains_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    route_client: tuple[TestClient, Mock],
) -> None:
    client, _ = route_client
    monkeypatch.setattr(
        source_routes.source_repository, "list_sources", Mock(return_value=[])
    )
    assert client.get("/sources").status_code == 200
    assert client.get("/api/sources").status_code == 404
