"""PostgreSQL verification for explicit semantic Memory search."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.routes.memories import provider_dependency
from app.db.session import get_engine
from app.main import create_app
from app.models import Memory, MemoryEmbedding, Project
from tests.integration.conftest import verify_connected_test_database


def vector(x: float, y: float) -> list[float]:
    """Build a deterministic 1536-dimensional vector."""

    return [x, y, *([0.0] * 1534)]


class FixedProvider:
    name = "fake"
    model = "fixed-1536"
    dimensions = 1536

    def __init__(self) -> None:
        self.inputs: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.inputs.append(text)
        return vector(1.0, 0.0)


@pytest.fixture
def semantic_client(
    migrated_test_database: None, test_database_url: str
) -> Generator[tuple[TestClient, FixedProvider], None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(Memory))
        session.execute(delete(Project))
        session.commit()
    provider = FixedProvider()
    application = create_app()
    application.dependency_overrides[provider_dependency] = lambda: provider
    yield TestClient(application), provider
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(Memory))
        session.execute(delete(Project))
        session.commit()


def add_embedded(
    session: Session,
    *,
    content: str,
    embedding: list[float] | None,
    created_at: datetime,
    project_id: uuid.UUID | None = None,
    memory_type: str = "semantic",
    status: str = "active",
    importance: float = 0.5,
    confidence: float = 1.0,
    event_time: datetime | None = None,
    memory_id: uuid.UUID | None = None,
) -> Memory:
    memory = Memory(
        id=memory_id or uuid.uuid4(),
        project_id=project_id,
        content=content,
        memory_type=memory_type,
        status=status,
        importance=importance,
        confidence=confidence,
        event_time=event_time,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(memory)
    session.flush()
    if embedding is not None:
        session.add(
            MemoryEmbedding(
                memory_id=memory.id,
                provider="fake",
                model="fixed-1536",
                dimensions=1536,
                embedding=embedding,
                input_hash="a" * 64,
                embedded_at=created_at,
            )
        )
    return memory


def test_empty_dataset_excludes_unembedded_and_does_not_persist_query(
    semantic_client: tuple[TestClient, FixedProvider],
) -> None:
    client, provider = semantic_client
    with Session(get_engine()) as session:
        add_embedded(
            session,
            content="lexical needle",
            embedding=None,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        session.commit()
    response = client.post("/memories/search", json={"query": " needle "})
    assert response.status_code == 200
    assert response.json() == []
    assert provider.inputs == ["needle"]
    assert client.get("/memories?query=needle").status_code == 200
    assert len(client.get("/memories?query=needle").json()) == 1
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count()).select_from(MemoryEmbedding)) == 0


def test_distance_ties_pagination_public_shape_and_rows_unchanged(
    semantic_client: tuple[TestClient, FixedProvider],
) -> None:
    client, _ = semantic_client
    base = datetime(2026, 1, 1, tzinfo=UTC)
    low_id = uuid.UUID(int=1)
    high_id = uuid.UUID(int=2)
    with Session(get_engine()) as session:
        closest = add_embedded(
            session, content="closest", embedding=vector(1, 0), created_at=base
        )
        newer_tie_low_id = add_embedded(
            session,
            content="tie-low",
            embedding=vector(1, 1),
            created_at=base + timedelta(minutes=2),
            memory_id=low_id,
        )
        add_embedded(
            session,
            content="tie-high",
            embedding=vector(1, 1),
            created_at=base + timedelta(minutes=2),
            memory_id=high_id,
        )
        add_embedded(
            session,
            content="far",
            embedding=vector(0, 1),
            created_at=base + timedelta(minutes=3),
        )
        add_embedded(
            session,
            content="no-vector",
            embedding=None,
            created_at=base + timedelta(minutes=4),
        )
        session.commit()
        closest_id = closest.id
        newer_tie_low_id_value = newer_tie_low_id.id
        before = {
            row.memory_id: list(row.embedding)
            for row in session.scalars(select(MemoryEmbedding)).all()
        }

    response = client.post("/memories/search", json={"query": "meaning"})
    assert response.status_code == 200
    body = response.json()
    assert [item["content"] for item in body] == [
        "closest",
        "tie-low",
        "tie-high",
        "far",
    ]
    assert body[0]["id"] == str(closest_id)
    assert body[1]["id"] == str(newer_tie_low_id_value)
    assert "embedding" not in body[0] and "score" not in body[0]
    paged = client.post(
        "/memories/search",
        json={"query": "meaning", "pagination": {"limit": 2, "offset": 1}},
    )
    assert [item["content"] for item in paged.json()] == ["tie-low", "tie-high"]
    with Session(get_engine()) as session:
        after = {
            row.memory_id: list(row.embedding)
            for row in session.scalars(select(MemoryEmbedding)).all()
        }
    assert after == before


def test_every_filter_category_and_multiple_filters_use_and(
    semantic_client: tuple[TestClient, FixedProvider],
) -> None:
    client, _ = semantic_client
    base = datetime(2026, 2, 1, tzinfo=UTC)
    with Session(get_engine()) as session:
        project = Project(name="Filter project")
        other_project = Project(name="Other project")
        session.add_all([project, other_project])
        session.flush()
        target = add_embedded(
            session,
            content="target",
            embedding=vector(1, 0),
            created_at=base,
            project_id=project.id,
            memory_type="decision",
            status="archived",
            importance=0.8,
            confidence=0.7,
            event_time=base - timedelta(days=1),
        )
        add_embedded(
            session,
            content="wrong",
            embedding=vector(1, 0),
            created_at=base,
            project_id=other_project.id,
            memory_type="semantic",
            status="active",
            importance=0.2,
            confidence=0.3,
            event_time=base - timedelta(days=10),
        )
        session.commit()
        project_id = project.id
        target_id = target.id

    filters = {
        "project_id": str(project_id),
        "memory_type": "decision",
        "status": "archived",
        "importance_min": 0.7,
        "importance_max": 0.9,
        "confidence_min": 0.6,
        "confidence_max": 0.8,
        "event_time_from": (base - timedelta(days=2)).isoformat(),
        "event_time_to": base.isoformat(),
        "created_at_from": (base - timedelta(minutes=1)).isoformat(),
        "created_at_to": (base + timedelta(minutes=1)).isoformat(),
    }
    response = client.post(
        "/memories/search", json={"query": "meaning", "filters": filters}
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [str(target_id)]

    filters["status"] = "active"
    assert (
        client.post(
            "/memories/search", json={"query": "meaning", "filters": filters}
        ).json()
        == []
    )
