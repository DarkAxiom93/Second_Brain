"""PostgreSQL tests for linked Source and Memory retrieval."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.main import create_app
from app.models.memory import Memory
from app.models.memory_source import MemorySource
from app.models.project import Project
from app.models.source import Source
from tests.integration.conftest import verify_connected_test_database


@pytest.fixture(autouse=True)
def clean_rows(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    def clean() -> None:
        verify_connected_test_database(test_database_url)
        with Session(get_engine()) as session:
            session.execute(delete(MemorySource))
            session.execute(delete(Source))
            session.execute(delete(Memory))
            session.execute(delete(Project))
            session.commit()

    clean()
    yield
    clean()


def test_bidirectional_retrieval_fields_order_pagination_and_empty_parents() -> None:
    client = TestClient(create_app())
    project = client.post("/projects", json={"name": "P"}).json()
    memory_one = client.post(
        "/memories",
        json={
            "project_id": project["id"],
            "content": "one",
            "source": "legacy",
            "title": "One title",
            "summary": "One summary",
            "memory_type": "episodic",
            "importance": 0.7,
            "confidence": 0.8,
            "status": "archived",
            "event_time": datetime.now(UTC).isoformat(),
            "expires_at": datetime.now(UTC).isoformat(),
        },
    ).json()
    memory_two = client.post("/memories", json={"content": "two"}).json()
    memory_empty = client.post("/memories", json={"content": "empty"}).json()
    source_one = client.post(
        "/sources", json={"source_type": "note", "name": "One", "reference": "r"}
    ).json()
    source_two = client.post(
        "/sources", json={"source_type": "file", "name": "Two", "checksum": "c"}
    ).json()
    source_empty = client.post(
        "/sources", json={"source_type": "note", "name": "Empty"}
    ).json()
    links = [
        client.post(
            f"/memories/{memory_one['id']}/sources",
            json={"source_id": source_one["id"], "source_location": None},
        ).json(),
        client.post(
            f"/memories/{memory_one['id']}/sources",
            json={"source_id": source_two["id"], "source_location": "page 8"},
        ).json(),
        client.post(
            f"/memories/{memory_two['id']}/sources",
            json={"source_id": source_one["id"], "source_location": "line 2"},
        ).json(),
    ]
    base = datetime.now(UTC) - timedelta(hours=1)
    with Session(get_engine()) as session:
        for index, link in enumerate(links):
            session.execute(
                update(MemorySource)
                .where(MemorySource.id == uuid.UUID(link["id"]))
                .values(created_at=base + timedelta(minutes=index))
            )
        session.commit()

    sources = client.get(f"/memories/{memory_one['id']}/sources").json()
    assert [item["link_id"] for item in sources] == [links[1]["id"], links[0]["id"]]
    assert sources[0]["source_location"] == "page 8"
    assert sources[1]["source_location"] is None
    assert set(sources[0]) == {
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
    assert client.get(
        f"/memories/{memory_one['id']}/sources?limit=1&offset=1"
    ).json() == [sources[1]]

    memories = client.get(f"/sources/{source_one['id']}/memories").json()
    assert [item["link_id"] for item in memories] == [links[2]["id"], links[0]["id"]]
    assert memories[1]["legacy_source"] == "legacy"
    assert memories[1]["title"] == "One title"
    assert memories[1]["summary"] == "One summary"
    assert memories[1]["memory_type"] == "episodic"
    assert memories[1]["importance"] == 0.7
    assert memories[1]["confidence"] == 0.8
    assert memories[1]["status"] == "archived"
    assert memories[1]["event_time"] is not None
    assert memories[1]["expires_at"] is not None
    assert memories[1]["supersedes_id"] is None
    assert memories[0]["project_id"] is None
    assert set(memories[0]) == {
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
    assert client.get(f"/sources/{source_one['id']}/memories?limit=1").json() == [
        memories[0]
    ]
    assert client.get(f"/memories/{memory_empty['id']}/sources").json() == []
    assert client.get(f"/sources/{source_empty['id']}/memories").json() == []
    missing_memory = client.get(f"/memories/{uuid.uuid4()}/sources")
    missing_source = client.get(f"/sources/{uuid.uuid4()}/memories")
    assert missing_memory.status_code == missing_source.status_code == 404
    assert missing_memory.json() == {"detail": "memory not found"}
    assert missing_source.json() == {"detail": "source not found"}
    assert client.get("/api/sources").status_code == 404
