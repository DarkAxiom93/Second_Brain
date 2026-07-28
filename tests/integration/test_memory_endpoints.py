"""PostgreSQL integration tests for Memory endpoints."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

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


def test_list_memories_filters_orders_and_paginates() -> None:
    client = TestClient(create_app())
    first_project = client.post("/projects", json={"name": "One"}).json()
    second_project = client.post("/projects", json={"name": "Two"}).json()
    created = [
        client.post("/memories", json={"content": "unassigned"}).json(),
        client.post(
            "/memories",
            json={"project_id": first_project["id"], "content": "first"},
        ).json(),
        client.post(
            "/memories",
            json={"project_id": second_project["id"], "content": "second"},
        ).json(),
    ]
    base_time = datetime(2026, 1, 1, tzinfo=UTC)
    with Session(get_engine()) as session:
        for index, item in enumerate(created):
            stored = session.get(Memory, uuid.UUID(item["id"]))
            assert stored is not None
            stored.created_at = base_time + timedelta(minutes=index)
        session.commit()

    listing = client.get("/memories")
    assert listing.status_code == 200
    assert [item["content"] for item in listing.json()] == [
        "second",
        "first",
        "unassigned",
    ]
    first_filter = client.get(f"/memories?project_id={first_project['id']}")
    assert [item["content"] for item in first_filter.json()] == ["first"]
    second_filter = client.get(f"/memories?project_id={second_project['id']}")
    assert [item["content"] for item in second_filter.json()] == ["second"]
    assert client.get(f"/memories?project_id={uuid.uuid4()}").json() == []
    page = client.get("/memories?limit=1&offset=1")
    assert [item["content"] for item in page.json()] == ["first"]


def test_deterministic_id_order_for_equal_created_at() -> None:
    shared_time = datetime(2026, 1, 1, tzinfo=UTC)
    lower_id = uuid.UUID(int=1)
    higher_id = uuid.UUID(int=2)
    with Session(get_engine()) as session:
        session.add_all(
            [
                Memory(id=higher_id, content="higher", created_at=shared_time),
                Memory(id=lower_id, content="lower", created_at=shared_time),
            ]
        )
        session.commit()
    response = TestClient(create_app()).get("/memories")
    assert [item["id"] for item in response.json()] == [str(lower_id), str(higher_id)]


def test_get_memory_and_validation_responses() -> None:
    client = TestClient(create_app())
    created = client.post("/memories", json={"content": "retrieve me"}).json()
    found = client.get(f"/memories/{created['id']}")
    assert found.status_code == 200
    assert found.json() == created
    missing = client.get(f"/memories/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "memory not found"}
    assert client.get("/memories/not-a-uuid").status_code == 422


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_list_memories_rejects_invalid_pagination(query: str) -> None:
    assert TestClient(create_app()).get(f"/memories?{query}").status_code == 422


def test_existing_endpoints_and_routing_remain_unchanged() -> None:
    client = TestClient(create_app())
    assert client.post("/memories", json={"content": "same"}).status_code == 201
    assert client.post("/memories", json={"content": "same"}).status_code == 201
    assert client.get("/memories").status_code == 200
    assert client.get("/api/memories").status_code == 404
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200
    assert client.post("/projects", json={"name": "Still works"}).status_code == 201
    assert client.get("/projects").status_code == 200
