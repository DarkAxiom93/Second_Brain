"""PostgreSQL integration tests for the Memory endpoint."""

import uuid
from collections.abc import Generator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.main import create_app
from app.models.memory import Memory
from app.models.project import Project
from tests.integration.conftest import verify_connected_test_database


@pytest.fixture(autouse=True)
def clean_memory_endpoint_rows(
    migrated_test_database: None,
    test_database_url: str,
) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(Memory))
        session.execute(delete(Project))
        session.commit()
    yield
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(Memory))
        session.execute(delete(Project))
        session.commit()


def test_create_unassigned_and_assigned_memories_with_exact_fields() -> None:
    client = TestClient(create_app())
    unassigned = client.post(
        "/memories", json={"content": "  fact  ", "source": "  note  "}
    )
    project = client.post("/projects", json={"name": "Pure Axiom"})
    assigned = client.post(
        "/memories",
        json={"project_id": project.json()["id"], "content": "fact"},
    )
    assert unassigned.status_code == assigned.status_code == 201
    assert unassigned.json()["project_id"] is None
    assert unassigned.json()["content"] == "fact"
    assert unassigned.json()["source"] == "note"
    assert assigned.json()["project_id"] == project.json()["id"]
    expected = {"id", "project_id", "content", "source", "created_at", "updated_at"}
    assert set(unassigned.json()) == expected
    for field in ("created_at", "updated_at"):
        assert datetime.fromisoformat(unassigned.json()[field]).tzinfo is not None


def test_unknown_project_returns_404_and_inserts_nothing() -> None:
    response = TestClient(create_app()).post(
        "/memories",
        json={"project_id": str(uuid.uuid4()), "content": "fact"},
    )
    with Session(get_engine()) as session:
        count = session.scalar(select(func.count()).select_from(Memory))
    assert response.status_code == 404
    assert response.json() == {"detail": "project not found"}
    assert count == 0


def test_invalid_input_returns_422_and_inserts_nothing() -> None:
    response = TestClient(create_app()).post("/memories", json={"content": "   "})
    with Session(get_engine()) as session:
        count = session.scalar(select(func.count()).select_from(Memory))
    assert response.status_code == 422
    assert count == 0


def test_duplicate_content_and_post_only_routing() -> None:
    client = TestClient(create_app())
    assert client.post("/memories", json={"content": "same"}).status_code == 201
    assert client.post("/memories", json={"content": "same"}).status_code == 201
    assert client.get("/memories").status_code == 405
    assert client.get("/api/memories").status_code == 404
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200
    assert client.post("/projects", json={"name": "Still works"}).status_code == 201
    assert client.get("/projects").status_code == 200
