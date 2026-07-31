"""PostgreSQL proof for the read-only Memory maintenance audit."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.memory_maintenance.service import run_memory_maintenance_audit
from app.models import Memory, MemoryEmbedding, Project
from app.repositories.memory_embeddings import (
    canonical_input_hash,
    canonical_memory_text,
)
from tests.integration.conftest import verify_connected_test_database


@pytest.fixture
def clean_audit_database(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(Memory))
        session.execute(delete(Project))
        session.commit()
    yield
    with Session(get_engine()) as session:
        session.execute(delete(Memory))
        session.execute(delete(Project))
        session.commit()


def _embedding(
    memory: Memory,
    *,
    provider: str = "openai",
    model: str = "current-model",
    input_hash: str | None = None,
) -> MemoryEmbedding:
    return MemoryEmbedding(
        memory_id=memory.id,
        provider=provider,
        model=model,
        dimensions=1536,
        embedding=[0.1] * 1536,
        input_hash=input_hash
        if input_hash is not None
        else canonical_input_hash(canonical_memory_text(memory)),
        embedded_at=datetime.now(UTC),
    )


def test_complete_deterministic_read_only_audit(
    clean_audit_database: None, test_database_url: str
) -> None:
    verify_connected_test_database(test_database_url)
    captured = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
    base = captured - timedelta(days=2)
    with Session(get_engine()) as session:
        project = Project(name=f"audit-{uuid.uuid4()}")
        session.add(project)
        session.flush()
        current = Memory(
            id=uuid.UUID(int=1),
            project_id=project.id,
            content="current",
            created_at=base,
        )
        missing_first = Memory(
            id=uuid.UUID(int=2),
            content="missing first",
            created_at=base + timedelta(seconds=1),
        )
        missing_second = Memory(
            id=uuid.UUID(int=3),
            content="missing second",
            expires_at=captured,
            created_at=base + timedelta(seconds=1),
        )
        future = Memory(
            id=uuid.UUID(int=4),
            content="future",
            expires_at=captured + timedelta(seconds=1),
            created_at=base + timedelta(seconds=2),
        )
        stale_hash = Memory(id=uuid.UUID(int=5), content="stale hash", created_at=base)
        stale_provider = Memory(
            id=uuid.UUID(int=6), content="stale provider", created_at=base
        )
        stale_model = Memory(
            id=uuid.UUID(int=7), content="stale model", created_at=base
        )
        inactive_rows = [
            Memory(
                id=uuid.UUID(int=number),
                content=status,
                status=status,
                expires_at=captured if status == "expired" and number == 11 else None,
                created_at=base + timedelta(seconds=number),
            )
            for number, status in (
                (8, "superseded"),
                (9, "invalid"),
                (10, "archived"),
                (11, "expired"),
                (12, "expired"),
            )
        ]
        session.add_all(
            [
                current,
                missing_first,
                missing_second,
                future,
                stale_hash,
                stale_provider,
                stale_model,
                *inactive_rows,
            ]
        )
        session.flush()
        session.add_all(
            [
                _embedding(current),
                _embedding(stale_hash, input_hash="a" * 64),
                _embedding(stale_provider, provider="other"),
                _embedding(stale_model, model="other"),
                _embedding(inactive_rows[0]),
                _embedding(inactive_rows[3]),
            ]
        )
        session.commit()

    with Session(get_engine()) as session:
        before_memories = {
            row.id: (row.updated_at, row.status, row.expires_at)
            for row in session.scalars(select(Memory))
        }
        before_embeddings = {
            row.id: (row.updated_at, row.input_hash, row.provider, row.model)
            for row in session.scalars(select(MemoryEmbedding))
        }
        before_counts = (
            session.scalar(select(func.count()).select_from(Memory)),
            session.scalar(select(func.count()).select_from(MemoryEmbedding)),
            session.scalar(select(func.count()).select_from(Project)),
        )
        report = run_memory_maintenance_audit(
            session,
            expected_embedding_identity=("openai", "current-model", 1536),
            detail_limit=1,
            clock=lambda: captured,
        )
        repeated = run_memory_maintenance_audit(
            session,
            expected_embedding_identity=("openai", "current-model", 1536),
            detail_limit=1,
            clock=lambda: captured,
        )
        dimension_report = run_memory_maintenance_audit(
            session,
            expected_embedding_identity=("openai", "current-model", 999),
            clock=lambda: captured,
        )
        after_memories = {
            row.id: (row.updated_at, row.status, row.expires_at)
            for row in session.scalars(select(Memory))
        }
        after_embeddings = {
            row.id: (row.updated_at, row.input_hash, row.provider, row.model)
            for row in session.scalars(select(MemoryEmbedding))
        }
        after_counts = (
            session.scalar(select(func.count()).select_from(Memory)),
            session.scalar(select(func.count()).select_from(MemoryEmbedding)),
            session.scalar(select(func.count()).select_from(Project)),
        )

    assert report.model_dump() == repeated.model_dump()
    assert report.total_memories == 12
    assert report.project_assigned_memories == 1
    assert report.unassigned_memories == 11
    assert report.counts_by_status == {
        "active": 7,
        "superseded": 1,
        "invalid": 1,
        "archived": 1,
        "expired": 2,
    }
    assert report.active_missing_embedding.count == 3
    assert report.active_missing_embedding.memory_ids == [uuid.UUID(int=2)]
    assert report.active_missing_embedding.truncated is True
    assert report.active_stale_embedding.count == 3
    assert report.active_stale_embedding.memory_ids == [uuid.UUID(int=5)]
    assert uuid.UUID(int=1) not in report.active_stale_embedding.memory_ids
    assert report.active_expiration_due.memory_ids == [uuid.UUID(int=3)]
    assert report.active_future_expiration.memory_ids == [uuid.UUID(int=4)]
    assert report.expired_missing_expires_at.memory_ids == [uuid.UUID(int=12)]
    assert report.non_active_with_embedding.count == 2
    assert report.non_active_with_embedding.memory_ids == [uuid.UUID(int=8)]
    assert dimension_report.active_stale_embedding.count == 4
    assert before_memories == after_memories
    assert before_embeddings == after_embeddings
    assert before_counts == after_counts
