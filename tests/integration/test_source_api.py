"""PostgreSQL integration tests for Source creation and linking."""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.main import create_app
from app.models.memory import Memory
from app.models.memory_source import MemorySource
from app.models.project import Project
from app.models.source import Source
from app.repositories.sources import create_source
from app.schemas.source import SourceCreate
from tests.integration.conftest import verify_connected_test_database


@pytest.fixture(autouse=True)
def clean_source_rows(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    """Clean only relevant rows after verifying the test database identity."""

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


def test_create_source_repository_persists_nullable_and_duplicate_checksum() -> None:
    with Session(get_engine()) as session:
        first = create_source(session, SourceCreate(source_type="note", name="One"))
        second = create_source(
            session,
            SourceCreate(source_type="note", name="Two", checksum="same"),
        )
        third = create_source(
            session,
            SourceCreate(source_type="file", name="Three", checksum="same"),
        )
        session.commit()
        assert isinstance(first.id, uuid.UUID)
        assert first.reference is None and first.checksum is None
        assert (
            first.created_at.tzinfo is not None and first.updated_at.tzinfo is not None
        )
        assert second.checksum == third.checksum == "same"


def test_source_listing_pagination_and_detail() -> None:
    client = TestClient(create_app())
    created = [
        client.post("/sources", json={"source_type": "note", "name": name}).json()
        for name in ("One", "Two", "Three")
    ]
    listing = client.get("/sources").json()
    assert len(listing) == 3
    assert client.get("/sources?limit=2&offset=1").json() == listing[1:3]
    assert client.get(f"/sources/{created[0]['id']}").json() == created[0]
    missing = client.get("/sources/00000000-0000-0000-0000-000000000001")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "source not found"}


def test_document_and_chunk_reads_are_scoped_and_deterministically_paginated() -> None:
    client = TestClient(create_app())
    first = client.post(
        "/sources", json={"source_type": "note", "name": "First"}
    ).json()
    second = client.post(
        "/sources", json={"source_type": "note", "name": "Second"}
    ).json()
    ingested = client.put(
        f"/sources/{first['id']}/document/text",
        json={"text": "a" * 2500, "chunk_size": 1000, "chunk_overlap": 0},
    ).json()
    other = client.put(
        f"/sources/{second['id']}/document/text", json={"text": "other"}
    ).json()
    assert client.get(f"/sources/{first['id']}/documents?limit=1&offset=0").json() == [
        {key: value for key, value in ingested.items() if key != "generation_status"}
    ]
    assert client.get(f"/sources/{first['id']}/documents?limit=1&offset=1").json() == []
    assert other["id"] not in client.get(f"/sources/{first['id']}/documents").text
    detail = client.get(f"/source-documents/{ingested['id']}")
    assert detail.status_code == 200 and detail.json()["chunk_count"] == 3
    chunks = client.get(f"/source-documents/{ingested['id']}/chunks").json()
    assert [chunk["chunk_index"] for chunk in chunks] == [0, 1, 2]
    assert client.get(
        f"/source-documents/{ingested['id']}/chunks?limit=1&offset=1"
    ).json() == [chunks[1]]
    missing_source = client.get(f"/sources/{uuid.uuid4()}/documents")
    assert missing_source.status_code == 404 and missing_source.json() == {
        "detail": "source not found"
    }
    missing_document = client.get(f"/source-documents/{uuid.uuid4()}")
    assert missing_document.status_code == 404 and missing_document.json() == {
        "detail": "source document not found"
    }


def test_source_endpoint_and_link_cardinalities_preserve_legacy_source() -> None:
    client = TestClient(create_app())
    project = client.post("/projects", json={"name": "Project"}).json()
    memory_one = client.post(
        "/memories",
        json={"project_id": project["id"], "content": "one", "source": "legacy"},
    ).json()
    memory_two = client.post("/memories", json={"content": "two"}).json()
    source_one = client.post("/sources", json={"source_type": "note", "name": "One"})
    source_two = client.post("/sources", json={"source_type": "note", "name": "Two"})
    assert source_one.status_code == source_two.status_code == 201
    link_one = client.post(
        f"/memories/{memory_one['id']}/sources",
        json={"source_id": source_one.json()["id"], "source_location": None},
    )
    link_two = client.post(
        f"/memories/{memory_two['id']}/sources",
        json={"source_id": source_one.json()["id"]},
    )
    link_three = client.post(
        f"/memories/{memory_one['id']}/sources",
        json={"source_id": source_two.json()["id"]},
    )
    assert link_one.status_code == link_two.status_code == link_three.status_code == 201
    assert set(link_one.json()) == {
        "id",
        "memory_id",
        "source_id",
        "source_location",
        "created_at",
    }
    assert link_one.json()["source_location"] is None
    with Session(get_engine()) as session:
        stored = session.get(Memory, uuid.UUID(memory_one["id"]))
        assert stored is not None and stored.source == "legacy"


def test_duplicate_and_unknown_links_create_no_rows() -> None:
    client = TestClient(create_app())
    memory = client.post("/memories", json={"content": "one"}).json()
    source = client.post("/sources", json={"source_type": "note", "name": "One"}).json()
    url = f"/memories/{memory['id']}/sources"
    assert client.post(url, json={"source_id": source["id"]}).status_code == 201
    duplicate = client.post(url, json={"source_id": source["id"]})
    missing_memory = client.post(
        f"/memories/{uuid.uuid4()}/sources", json={"source_id": source["id"]}
    )
    missing_source = client.post(url, json={"source_id": str(uuid.uuid4())})
    assert duplicate.status_code == 409
    assert missing_memory.status_code == missing_source.status_code == 404
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count()).select_from(MemorySource)) == 1
