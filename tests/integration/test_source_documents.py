"""PostgreSQL integration coverage for Source document persistence."""

import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.models import Source, SourceChunk, SourceDocument
from tests.integration.conftest import verify_connected_test_database


def test_source_document_migration_lifecycle_preserves_prior_schema(
    test_database_url: str, alembic_config: Config
) -> None:
    verify_connected_test_database(test_database_url)
    command.downgrade(alembic_config, "0006_memory_embeddings")
    source_id = uuid.uuid4()
    memory_id = uuid.uuid4()
    with get_engine().begin() as connection:
        connection.execute(
            text(
                "INSERT INTO sources (id, source_type, name) "
                "VALUES (:id, 'note', 'preexisting')"
            ),
            {"id": source_id},
        )
        connection.execute(
            text("INSERT INTO memories (id, content) VALUES (:id, 'prior lexical')"),
            {"id": memory_id},
        )
    command.upgrade(alembic_config, "0007_source_documents")
    try:
        with get_engine().connect() as connection:
            assert connection.scalar(
                text("SELECT version_num FROM alembic_version")
            ) == ("0007_source_documents")
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM sources WHERE id=:id"), {"id": source_id}
                )
                == 1
            )
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM memories WHERE id=:id"),
                    {"id": memory_id},
                )
                == 1
            )
            assert connection.scalar(text("SELECT count(*) FROM source_documents")) == 0
        command.downgrade(alembic_config, "0006_memory_embeddings")
        tables = set(inspect(get_engine()).get_table_names())
        assert "source_documents" not in tables and "source_chunks" not in tables
        with get_engine().connect() as connection:
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_indexes WHERE "
                        "indexname='ix_memories_search_vector'"
                    )
                )
                == 1
            )
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_indexes WHERE "
                        "indexname='ix_memory_embeddings_embedding_hnsw'"
                    )
                )
                == 1
            )
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_extension WHERE "
                        "extname='vector' AND extversion='0.8.5'"
                    )
                )
                == 1
            )
    finally:
        command.upgrade(alembic_config, "head")
    assert {"source_documents", "source_chunks"} <= set(
        inspect(get_engine()).get_table_names()
    )


def test_document_chunk_storage_constraints_ordering_and_cascades(
    migrated_test_database: None, test_database_url: str
) -> None:
    verify_connected_test_database(test_database_url)
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM source_chunks"))
        connection.execute(text("DELETE FROM source_documents"))
        connection.execute(text("DELETE FROM memory_sources"))
        connection.execute(text("DELETE FROM sources"))

    first = Source(source_type="document", name="first")
    second = Source(source_type="document", name="second")
    with Session(engine) as session:
        session.add_all([first, second])
        session.flush()
        document = SourceDocument(
            source=first,
            media_type="text/plain",
            original_filename=None,
            byte_size=11,
            extracted_text=None,
        )
        other_document = SourceDocument(
            source=second,
            media_type="application/pdf",
            ingestion_status="failed",
            error_code="PARSER_UNAVAILABLE",
        )
        document.chunks.extend(
            [
                SourceChunk(
                    chunk_index=1,
                    content="world",
                    char_start=6,
                    char_end=11,
                    content_hash="b" * 64,
                    locator="page 1",
                ),
                SourceChunk(
                    chunk_index=0,
                    content="hello",
                    char_start=0,
                    char_end=5,
                    content_hash="a" * 64,
                ),
            ]
        )
        other_document.chunks.append(
            SourceChunk(
                chunk_index=0,
                content="other",
                char_start=0,
                char_end=5,
                content_hash="c" * 64,
            )
        )
        session.add_all([document, other_document])
        session.commit()
        document_id = document.id
        other_document_id = other_document.id
        first_id = first.id
        second_id = second.id

    with Session(engine) as session:
        loaded = session.get(SourceDocument, document_id)
        assert loaded is not None
        assert loaded.ingestion_status == "pending"
        assert [chunk.chunk_index for chunk in loaded.chunks] == [0, 1]
        assert loaded.chunks[1].locator == "page 1"
        one_chunk = loaded.chunks[0]
        session.delete(one_chunk)
        session.commit()
        assert session.get(SourceDocument, document_id) is not None
        assert session.get(Source, first_id) is not None

        session.delete(loaded)
        session.commit()
        assert session.get(Source, first_id) is not None
        assert (
            session.scalar(
                text("SELECT count(*) FROM source_chunks WHERE document_id=:id"),
                {"id": document_id},
            )
            == 0
        )

        source = session.get(Source, second_id)
        assert source is not None
        session.delete(source)
        session.commit()
        assert session.get(SourceDocument, other_document_id) is None


@pytest.mark.parametrize(
    ("field", "value"),
    [("byte_size", -1), ("ingestion_status", "running")],
)
def test_invalid_document_values_are_rejected(
    field: str,
    value: object,
    migrated_test_database: None,
) -> None:
    with Session(get_engine()) as session:
        source = Source(source_type="document", name=f"invalid-{field}")
        session.add(source)
        session.flush()
        values = {"source_id": source.id, "media_type": "text/plain", field: value}
        session.add(SourceDocument(**values))  # type: ignore[arg-type]
        with pytest.raises(IntegrityError):
            session.commit()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("chunk_index", -1),
        ("content", " \t\n"),
        ("char_start", -1),
        ("char_end", 0),
        ("content_hash", "A" * 64),
        ("content_hash", "not-a-hash"),
    ],
)
def test_invalid_chunk_values_are_rejected(
    field: str,
    value: object,
    migrated_test_database: None,
) -> None:
    with Session(get_engine()) as session:
        source = Source(source_type="document", name=f"invalid-chunk-{field}")
        document = SourceDocument(source=source, media_type="text/plain")
        session.add(document)
        session.flush()
        values: dict[str, object] = {
            "document_id": document.id,
            "chunk_index": 0,
            "content": "valid",
            "char_start": 0,
            "char_end": 5,
            "content_hash": "d" * 64,
        }
        values[field] = value
        session.add(SourceChunk(**values))  # type: ignore[arg-type]
        with pytest.raises(IntegrityError):
            session.commit()


def test_document_uniqueness_and_chunk_index_scope(
    migrated_test_database: None,
) -> None:
    engine = get_engine()
    with Session(engine) as session:
        source = Source(source_type="document", name="unique-document")
        session.add(source)
        session.flush()
        session.add_all(
            [
                SourceDocument(source_id=source.id, media_type="text/plain"),
                SourceDocument(source_id=source.id, media_type="text/plain"),
            ]
        )
        with pytest.raises(IntegrityError):
            session.commit()

    with Session(engine) as session:
        sources = [Source(source_type="document", name=f"scope-{i}") for i in range(2)]
        documents = [
            SourceDocument(source=source, media_type="text/plain") for source in sources
        ]
        session.add_all(documents)
        session.flush()
        for document in documents:
            session.add(
                SourceChunk(
                    document=document,
                    chunk_index=0,
                    content="ok",
                    char_start=0,
                    char_end=2,
                    content_hash="e" * 64,
                )
            )
        session.commit()
        assert (
            len(
                session.scalars(
                    select(SourceChunk).where(SourceChunk.chunk_index == 0)
                ).all()
            )
            >= 2
        )

        session.add(
            SourceChunk(
                document=documents[0],
                chunk_index=0,
                content="duplicate",
                char_start=0,
                char_end=9,
                content_hash="f" * 64,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
