"""PostgreSQL integration tests for Project endpoints."""

from collections.abc import Generator

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
def clean_endpoint_projects(
    migrated_test_database: None,
    test_database_url: str,
) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(Project))
        session.commit()
    yield
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(Project))
        session.commit()


def test_post_then_get_project_and_duplicate_names() -> None:
    client = TestClient(create_app())
    payload = {
        "name": "Pure Axiom",
        "description": "Interactive mathematics platform",
    }

    first = client.post("/projects", json=payload)
    second = client.post("/projects", json=payload)
    listing = client.get("/projects")

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["name"] == payload["name"]
    assert first.json()["description"] == payload["description"]
    assert len(listing.json()) == 2
    assert first.json()["id"] in {project["id"] for project in listing.json()}


def test_invalid_project_does_not_insert_or_touch_memories() -> None:
    with Session(get_engine()) as session:
        memory_count_before = session.scalar(select(func.count()).select_from(Memory))

    response = TestClient(create_app()).post("/projects", json={"name": "   "})

    with Session(get_engine()) as session:
        project_count = session.scalar(select(func.count()).select_from(Project))
        memory_count_after = session.scalar(select(func.count()).select_from(Memory))
    assert response.status_code == 422
    assert project_count == 0
    assert memory_count_after == memory_count_before


def test_get_projects_empty_and_applies_pagination() -> None:
    client = TestClient(create_app())
    assert client.get("/projects").json() == []
    for name in ("One", "Two", "Three"):
        assert client.post("/projects", json={"name": name}).status_code == 201

    assert len(client.get("/projects?limit=1").json()) == 1
    full_ids = [project["id"] for project in client.get("/projects").json()]
    offset_ids = [
        project["id"] for project in client.get("/projects?limit=2&offset=1").json()
    ]
    assert offset_ids == full_ids[1:3]
