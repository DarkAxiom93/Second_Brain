"""PostgreSQL integration coverage for Memory embedding persistence."""

import uuid
from datetime import datetime

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.models import Memory, MemoryEmbedding
from tests.integration.conftest import verify_connected_test_database

DIMENSIONS = 1536
INPUT_HASH = "a" * 64


def fixed_vector(first: float, second: float = 0.0) -> list[float]:
    """Create a deterministic vector with only its first coordinates populated."""

    return [first, second, *([0.0] * (DIMENSIONS - 2))]


def test_embedding_migration_lifecycle_preserves_existing_memory(
    test_database_url: str, alembic_config: Config
) -> None:
    verify_connected_test_database(test_database_url)
    command.downgrade(alembic_config, "0005_memory_search")
    memory_id = uuid.uuid4()
    with get_engine().begin() as connection:
        connection.execute(
            text("INSERT INTO memories (id, content) VALUES (:id, 'preexisting')"),
            {"id": memory_id},
        )
    command.upgrade(alembic_config, "0006_memory_embeddings")
    with get_engine().connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0006_memory_embeddings"
        )
        assert (
            connection.scalar(
                text("SELECT count(*) FROM memories WHERE id=:id"), {"id": memory_id}
            )
            == 1
        )
        assert connection.scalar(text("SELECT count(*) FROM memory_embeddings")) == 0
    command.downgrade(alembic_config, "0005_memory_search")
    assert "memory_embeddings" not in inspect(get_engine()).get_table_names()
    with get_engine().connect() as connection:
        assert (
            connection.scalar(
                text("SELECT count(*) FROM memories WHERE id=:id"), {"id": memory_id}
            )
            == 1
        )
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM pg_extension "
                    "WHERE extname='vector' AND extversion='0.8.5'"
                )
            )
            == 1
        )
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM pg_indexes WHERE tablename='memories' "
                    "AND indexname='ix_memories_search_vector'"
                )
            )
            == 1
        )
    command.upgrade(alembic_config, "head")
    assert "memory_embeddings" in inspect(get_engine()).get_table_names()


def test_embedding_storage_constraints_relationships_and_distance(
    migrated_test_database: None, test_database_url: str
) -> None:
    verify_connected_test_database(test_database_url)
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM memory_embeddings"))
        connection.execute(text("DELETE FROM memory_sources"))
        connection.execute(text("DELETE FROM memories"))

    first = Memory(content="semantic alpha")
    second = Memory(content="semantic beta")
    with Session(engine) as session:
        session.add_all([first, second])
        session.flush()
        first_embedding = MemoryEmbedding(
            memory=first,
            provider="test-provider",
            model="fixed-1536",
            dimensions=DIMENSIONS,
            embedding=fixed_vector(1.0),
            input_hash=INPUT_HASH,
        )
        second_embedding = MemoryEmbedding(
            memory=second,
            provider="test-provider",
            model="fixed-1536",
            dimensions=DIMENSIONS,
            embedding=fixed_vector(0.0, 1.0),
            input_hash="b" * 64,
        )
        session.add_all([first_embedding, second_embedding])
        session.commit()
        session.refresh(first_embedding)
        assert isinstance(first_embedding.id, uuid.UUID)
        assert isinstance(first_embedding.memory_id, uuid.UUID)
        assert all(
            isinstance(value, datetime) and value.tzinfo is not None
            for value in (
                first_embedding.embedded_at,
                first_embedding.created_at,
                first_embedding.updated_at,
            )
        )
        assert list(first_embedding.embedding) == fixed_vector(1.0)
        assert (first_embedding.provider, first_embedding.model) == (
            "test-provider",
            "fixed-1536",
        )
        assert first_embedding.input_hash == INPUT_HASH
        ordered = session.scalars(
            text(
                "SELECT memory_id FROM memory_embeddings "
                "ORDER BY embedding <=> CAST(:query AS vector)"
            ).columns(memory_id=MemoryEmbedding.__table__.c.memory_id.type),
            {"query": str(fixed_vector(1.0))},
        ).all()
        assert ordered[0] == first.id

        session.add(
            MemoryEmbedding(
                memory_id=first.id,
                provider="duplicate",
                model="duplicate",
                dimensions=DIMENSIONS,
                embedding=fixed_vector(1.0),
                input_hash="c" * 64,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        invalid_memory = Memory(content="invalid dimensions")
        session.add(invalid_memory)
        session.flush()
        session.add(
            MemoryEmbedding(
                memory=invalid_memory,
                provider="test",
                model="test",
                dimensions=2,
                embedding=fixed_vector(1.0),
                input_hash="d" * 64,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        second_id = second.id
        session.delete(second_embedding)
        session.commit()
        assert session.get(Memory, second_id) is not None
        first_id = first.id
        session.delete(first)
        session.commit()
        assert (
            session.scalar(
                text("SELECT count(*) FROM memory_embeddings WHERE memory_id=:id"),
                {"id": first_id},
            )
            == 0
        )


def test_embedding_database_indexes_extension_and_lexical_search(
    migrated_test_database: None,
) -> None:
    with get_engine().connect() as connection:
        index = connection.execute(
            text(
                "SELECT indexdef FROM pg_indexes WHERE tablename='memory_embeddings' "
                "AND indexname='ix_memory_embeddings_embedding_hnsw'"
            )
        ).scalar_one()
        assert "USING hnsw" in index and "vector_cosine_ops" in index
        assert (
            connection.scalar(
                text("SELECT extversion FROM pg_extension WHERE extname='vector'")
            )
            == "0.8.5"
        )
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM memories WHERE search_vector @@ "
                    "websearch_to_tsquery('simple', 'semantic')"
                )
            )
            >= 1
        )
