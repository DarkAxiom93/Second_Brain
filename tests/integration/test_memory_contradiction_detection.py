"""PostgreSQL API coverage for advisory Memory contradiction detection."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db.dependencies import get_db_session
from app.db.session import get_engine
from app.main import create_app
from app.models import (
    Memory,
    MemoryEmbedding,
    MemoryProposal,
    MemorySource,
    Project,
    Source,
)
from tests.integration.conftest import verify_connected_test_database

CONTRADICTION_SOURCE_NAME = "Checkpoint 29 contradiction snapshot source"


def vector(x: float, y: float) -> list[float]:
    return [x, y, *([0.0] * 1534)]


@pytest.fixture
def contradiction_client(
    migrated_test_database: None, test_database_url: str
) -> Generator[TestClient, None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(Memory))
        session.execute(delete(Source).where(Source.name == CONTRADICTION_SOURCE_NAME))
        session.execute(delete(Project))
        session.commit()
    yield TestClient(create_app())
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(Memory))
        session.execute(delete(Source).where(Source.name == CONTRADICTION_SOURCE_NAME))
        session.execute(delete(Project))
        session.commit()


def add_memory(
    session: Session,
    content: str,
    *,
    project_id: uuid.UUID | None,
    memory_id: uuid.UUID | None = None,
    status: str = "active",
    event_time: datetime | None = None,
    embedding: list[float] | None = None,
    provider: str = "fake",
    model: str = "fixed-1536",
) -> Memory:
    now = datetime(2026, 7, 30, tzinfo=UTC)
    memory = Memory(
        id=memory_id or uuid.uuid4(),
        project_id=project_id,
        content=content,
        status=status,
        event_time=event_time,
        created_at=now,
        updated_at=now,
    )
    session.add(memory)
    session.flush()
    if embedding is not None:
        session.add(
            MemoryEmbedding(
                memory_id=memory.id,
                provider=provider,
                model=model,
                dimensions=1536,
                embedding=embedding,
                input_hash="b" * 64,
                embedded_at=now,
            )
        )
    return memory


def snapshot(session: Session) -> dict[str, object]:
    memories = session.scalars(select(Memory).order_by(Memory.id)).all()
    embeddings = session.scalars(
        select(MemoryEmbedding).order_by(MemoryEmbedding.id)
    ).all()
    links = session.scalars(select(MemorySource).order_by(MemorySource.id)).all()
    proposals = session.scalars(
        select(MemoryProposal).order_by(MemoryProposal.id)
    ).all()
    sources = session.scalars(select(Source).order_by(Source.id)).all()
    projects = session.scalars(select(Project).order_by(Project.id)).all()
    return {
        "memories": [
            (
                row.id,
                row.project_id,
                row.content,
                row.source,
                row.title,
                row.summary,
                row.memory_type,
                row.importance,
                row.confidence,
                row.status,
                row.event_time,
                row.expires_at,
                row.supersedes_id,
                row.created_at,
                row.updated_at,
            )
            for row in memories
        ],
        "embeddings": [
            (
                row.id,
                row.memory_id,
                row.provider,
                row.model,
                row.dimensions,
                list(row.embedding),
                row.input_hash,
                row.embedded_at,
                row.created_at,
                row.updated_at,
            )
            for row in embeddings
        ],
        "links": [
            (
                row.id,
                row.memory_id,
                row.source_id,
                row.source_location,
                row.created_at,
            )
            for row in links
        ],
        "proposals": [
            (
                row.id,
                row.review_status,
                row.memory_id,
                row.review_note,
                row.reviewed_at,
                row.updated_at,
            )
            for row in proposals
        ],
        "sources": [
            (
                row.id,
                row.source_type,
                row.name,
                row.reference,
                row.checksum,
                row.created_at,
                row.updated_at,
            )
            for row in sources
        ],
        "projects": [
            (
                row.id,
                row.name,
                row.description,
                row.created_at,
                row.updated_at,
            )
            for row in projects
        ],
        "memory_count": session.scalar(select(func.count()).select_from(Memory)),
        "embedding_count": session.scalar(
            select(func.count()).select_from(MemoryEmbedding)
        ),
        "link_count": session.scalar(select(func.count()).select_from(MemorySource)),
        "proposal_count": session.scalar(
            select(func.count()).select_from(MemoryProposal)
        ),
        "source_count": session.scalar(select(func.count()).select_from(Source)),
        "project_count": session.scalar(select(func.count()).select_from(Project)),
    }


def test_detection_scope_filters_order_limit_and_no_mutation(
    contradiction_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.api.routes.memories.get_embedding_provider",
        lambda: pytest.fail("contradiction detection must not resolve a provider"),
    )
    now = datetime(2026, 7, 30, tzinfo=UTC)
    explicit_id = uuid.UUID(int=1)
    boolean_id = uuid.UUID(int=2)
    with Session(get_engine()) as session:
        project = Project(name="Contradiction project")
        other = Project(name="Other contradiction project")
        session.add_all([project, other])
        session.flush()
        target = add_memory(
            session,
            "service is available",
            project_id=project.id,
            event_time=now,
            embedding=vector(1.0, 0.0),
        )
        source = Source(source_type="test", name=CONTRADICTION_SOURCE_NAME)
        session.add(source)
        session.flush()
        session.add(
            MemorySource(
                memory_id=target.id,
                source_id=source.id,
                source_location="approval-audit",
            )
        )
        add_memory(
            session,
            "service is not available",
            project_id=project.id,
            memory_id=explicit_id,
            event_time=now,
            embedding=vector(1.0, 0.0),
        )
        add_memory(
            session,
            "service is unavailable",
            project_id=project.id,
            memory_id=boolean_id,
        )
        add_memory(session, "service is available", project_id=project.id)
        add_memory(
            session,
            "service is not available",
            project_id=project.id,
            status="archived",
        )
        add_memory(session, "service is not available", project_id=other.id)
        add_memory(session, "other is not available", project_id=project.id)
        add_memory(
            session,
            "service is not available",
            project_id=project.id,
            event_time=now + timedelta(days=1),
        )
        session.commit()
        target_id = target.id
        before = snapshot(session)

    response = contradiction_client.get(
        f"/memories/{target_id}/contradictions", params={"limit": 1}
    )
    assert response.status_code == 200
    assert response.json() == {
        "target_memory_id": str(target_id),
        "candidates": [
            {
                "memory_id": str(explicit_id),
                "classification": "potential_contradiction",
                "evidence_type": "explicit_negation",
                "reason": (
                    "supported opposing states occur at the same position and "
                    "the remaining normalized proposition anchor is exactly equal"
                ),
                "lexical_similarity": 0.75,
                "semantic_similarity": 1.0,
                "target_state": "is",
                "candidate_state": "is not",
            }
        ],
    }
    all_candidates = contradiction_client.get(
        f"/memories/{target_id}/contradictions"
    ).json()["candidates"]
    assert [row["memory_id"] for row in all_candidates] == [
        str(explicit_id),
        str(boolean_id),
    ]
    assert all_candidates[1]["semantic_similarity"] is None

    with Session(get_engine()) as session:
        assert snapshot(session) == before


def test_unassigned_scope_empty_missing_inactive_and_validation(
    contradiction_client: TestClient,
) -> None:
    with Session(get_engine()) as session:
        project = Project(name="Assigned scope")
        session.add(project)
        session.flush()
        unassigned = add_memory(session, "flag is on", project_id=None)
        unassigned_candidate = add_memory(session, "flag is off", project_id=None)
        assigned_candidate = add_memory(session, "flag is off", project_id=project.id)
        assigned_target = add_memory(session, "flag is on", project_id=project.id)
        inactive_target = add_memory(
            session, "flag is on", project_id=None, status="archived"
        )
        no_match = add_memory(session, "unrelated statement", project_id=project.id)
        session.commit()
        ids = (
            unassigned.id,
            unassigned_candidate.id,
            assigned_target.id,
            inactive_target.id,
            assigned_candidate.id,
            no_match.id,
        )

    unassigned_response = contradiction_client.get(f"/memories/{ids[0]}/contradictions")
    assert [row["memory_id"] for row in unassigned_response.json()["candidates"]] == [
        str(ids[1])
    ]
    assert [
        row["memory_id"]
        for row in contradiction_client.get(
            f"/memories/{ids[2]}/contradictions"
        ).json()["candidates"]
    ] == [str(ids[4])]
    assert (
        contradiction_client.get(f"/memories/{ids[5]}/contradictions").json()[
            "candidates"
        ]
        == []
    )
    for missing_id in (ids[3], uuid.uuid4()):
        response = contradiction_client.get(f"/memories/{missing_id}/contradictions")
        assert response.status_code == 404
        assert response.json() == {"detail": "memory not found"}
    assert (
        contradiction_client.get(
            f"/memories/{ids[0]}/contradictions", params={"limit": 0}
        ).status_code
        == 422
    )


def test_incompatible_embedding_metadata_is_ignored_semantically(
    contradiction_client: TestClient,
) -> None:
    with Session(get_engine()) as session:
        target = add_memory(
            session,
            "feature active",
            project_id=None,
            embedding=vector(1.0, 0.0),
        )
        candidate = add_memory(
            session,
            "feature inactive",
            project_id=None,
            embedding=vector(1.0, 0.0),
            model="incompatible",
        )
        session.commit()
        target_id, candidate_id = target.id, candidate.id

    rows = contradiction_client.get(f"/memories/{target_id}/contradictions").json()[
        "candidates"
    ]
    assert len(rows) == 1
    assert rows[0]["memory_id"] == str(candidate_id)
    assert rows[0]["semantic_similarity"] is None


def test_compatible_stored_embedding_can_recover_from_bounded_lexical_pool(
    contradiction_client: TestClient,
) -> None:
    with Session(get_engine()) as session:
        target = add_memory(
            session,
            "flag is on",
            project_id=None,
            embedding=vector(1.0, 0.0),
        )
        for index in range(251):
            add_memory(session, f"flag is on filler {index}", project_id=None)
        candidate = add_memory(
            session,
            "flag is off",
            project_id=None,
            embedding=vector(1.0, 0.0),
        )
        session.commit()
        target_id, candidate_id = target.id, candidate.id

    rows = contradiction_client.get(f"/memories/{target_id}/contradictions").json()[
        "candidates"
    ]
    assert [row["memory_id"] for row in rows] == [str(candidate_id)]
    assert rows[0]["semantic_similarity"] == 1.0


def test_database_unavailability_returns_generic_503(
    migrated_test_database: None, test_database_url: str
) -> None:
    unavailable_url = make_url(test_database_url).set(port=1)
    unavailable_engine = create_engine(
        unavailable_url, connect_args={"connect_timeout": 1}
    )
    app = create_app()

    def unavailable_session() -> Generator[Session, None, None]:
        with Session(unavailable_engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = unavailable_session
    try:
        response = TestClient(app).get(f"/memories/{uuid.uuid4()}/contradictions")
    finally:
        unavailable_engine.dispose()
    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
