"""PostgreSQL integration coverage for additive explained Memory search."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.routes.memories import provider_dependency, provider_resolver_dependency
from app.db.session import get_engine
from app.main import create_app
from app.models import Memory, MemoryEmbedding, Project
from tests.integration.conftest import verify_connected_test_database


def vector(x: float, y: float) -> list[float]:
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
def explained_client(
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
    application.dependency_overrides[provider_resolver_dependency] = lambda: (
        lambda: provider
    )
    yield TestClient(application), provider
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(Memory))
        session.execute(delete(Project))
        session.commit()


def add_memory(
    session: Session,
    *,
    content: str,
    created_at: datetime,
    embedding: list[float] | None,
    memory_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
) -> Memory:
    memory = Memory(
        id=memory_id or uuid.uuid4(),
        project_id=project_id,
        content=content,
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


def test_all_modes_match_legacy_order_and_expose_exact_channel_values(
    explained_client: tuple[TestClient, FixedProvider],
) -> None:
    client, provider = explained_client
    base = datetime(2026, 4, 1, tzinfo=UTC)
    with Session(get_engine()) as session:
        both = add_memory(
            session,
            content="needle both",
            created_at=base,
            embedding=vector(1, 0),
        )
        lexical_only = add_memory(
            session,
            content="needle lexical",
            created_at=base + timedelta(minutes=1),
            embedding=None,
        )
        semantic_only = add_memory(
            session,
            content="semantic only",
            created_at=base + timedelta(minutes=2),
            embedding=vector(1, 0),
        )
        session.commit()
        expected_ids = {str(both.id), str(lexical_only.id), str(semantic_only.id)}

    lexical = client.post(
        "/memories/search/explained",
        json={"query": "needle", "mode": "lexical", "filters": {}, "pagination": {}},
    )
    legacy_lexical = client.get("/memories?query=needle")
    assert lexical.status_code == legacy_lexical.status_code == 200
    assert [row["memory"]["id"] for row in lexical.json()] == [
        row["id"] for row in legacy_lexical.json()
    ]
    assert provider.inputs == []
    assert [row["rank"] for row in lexical.json()] == [1, 2]
    assert all(
        row["explanation"]["matched_by"] == ["lexical"] for row in lexical.json()
    )

    semantic = client.post(
        "/memories/search/explained",
        json={"query": "needle", "mode": "semantic", "filters": {}, "pagination": {}},
    )
    legacy_semantic = client.post("/memories/search", json={"query": "needle"})
    assert [row["memory"]["id"] for row in semantic.json()] == [
        row["id"] for row in legacy_semantic.json()
    ]
    assert all(row["explanation"]["semantic_signal"] == 1.0 for row in semantic.json())

    hybrid = client.post(
        "/memories/search/explained",
        json={"query": "needle", "mode": "hybrid", "filters": {}, "pagination": {}},
    )
    legacy_hybrid = client.post(
        "/memories/search", json={"query": "needle", "mode": "hybrid"}
    )
    body = hybrid.json()
    assert [row["memory"]["id"] for row in body] == [
        row["id"] for row in legacy_hybrid.json()
    ]
    assert {row["memory"]["id"] for row in body} == expected_ids
    channels = {row["memory"]["id"]: row["explanation"] for row in body}
    assert channels[str(both.id)]["matched_by"] == ["lexical", "semantic"]
    assert channels[str(lexical_only.id)]["matched_by"] == ["lexical"]
    assert channels[str(semantic_only.id)]["matched_by"] == ["semantic"]
    for explanation in channels.values():
        expected = sum(
            1.0 / (60 + explanation[key])
            for key in ("lexical_rank", "semantic_rank")
            if explanation[key] is not None
        )
        assert explanation["fused_rrf_score"] == round(expected, 6)


def test_global_rank_offset_filters_and_rows_are_unchanged(
    explained_client: tuple[TestClient, FixedProvider],
) -> None:
    client, _ = explained_client
    base = datetime(2026, 4, 2, tzinfo=UTC)
    with Session(get_engine()) as session:
        project = Project(name="explained isolation")
        other = Project(name="other isolation")
        session.add_all([project, other])
        session.flush()
        for index in range(3):
            add_memory(
                session,
                content="rankword",
                created_at=base + timedelta(minutes=index),
                embedding=None,
                memory_id=uuid.UUID(int=index + 1),
                project_id=project.id,
            )
        add_memory(
            session,
            content="rankword",
            created_at=base + timedelta(days=1),
            embedding=None,
            project_id=other.id,
        )
        session.commit()
        before = session.scalar(select(func.count()).select_from(Memory))
        project_id = project.id

    response = client.post(
        "/memories/search/explained",
        json={
            "query": "rankword",
            "mode": "lexical",
            "filters": {"project_id": str(project_id)},
            "pagination": {"limit": 1, "offset": 1},
        },
    )
    assert response.status_code == 200
    assert response.json()[0]["rank"] == 2
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count()).select_from(Memory)) == before
