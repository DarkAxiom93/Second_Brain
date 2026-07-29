"""Metadata-only tests for Project and Memory models."""

import importlib

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import RelationshipProperty

from app.db.base import Base
from app.db.session import get_engine, reset_database_state
from app.models import Memory, MemoryEmbedding, MemorySource, Project, Source
from app.schemas.memory import MemoryCreate, MemoryRead


def test_metadata_contains_only_approved_tables() -> None:
    assert set(Base.metadata.tables) == {
        "projects",
        "memories",
        "sources",
        "memory_sources",
        "memory_embeddings",
    }


def test_source_columns_match_approved_schema() -> None:
    assert set(Source.__table__.c.keys()) == {
        "id",
        "source_type",
        "name",
        "reference",
        "checksum",
        "created_at",
        "updated_at",
    }
    assert Source.__table__.c.source_type.nullable is False
    assert Source.__table__.c.name.nullable is False
    assert Source.__table__.c.reference.nullable is True
    assert Source.__table__.c.checksum.nullable is True


def test_memory_source_columns_and_constraints() -> None:
    assert set(MemorySource.__table__.c.keys()) == {
        "id",
        "memory_id",
        "source_id",
        "source_location",
        "created_at",
    }
    assert MemorySource.__table__.c.memory_id.nullable is False
    assert MemorySource.__table__.c.source_id.nullable is False
    foreign_keys = {key.parent.name: key for key in MemorySource.__table__.foreign_keys}
    assert foreign_keys["memory_id"].target_fullname == "memories.id"
    assert foreign_keys["source_id"].target_fullname == "sources.id"
    assert all(key.ondelete == "CASCADE" for key in foreign_keys.values())
    unique_pairs = {
        tuple(column.name for column in constraint.columns)
        for constraint in MemorySource.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("memory_id", "source_id") in unique_pairs


def test_project_name_is_not_unique() -> None:
    assert Project.__table__.c.name.unique in (None, False)


def test_memory_column_nullability() -> None:
    assert Memory.__table__.c.project_id.nullable is True
    assert Memory.__table__.c.content.nullable is False


def test_memory_structured_metadata_schema() -> None:
    columns = Memory.__table__.c
    assert {
        "title",
        "summary",
        "memory_type",
        "importance",
        "confidence",
        "status",
        "event_time",
        "expires_at",
        "supersedes_id",
    } <= set(columns.keys())
    for name in ("memory_type", "importance", "confidence", "status"):
        assert columns[name].nullable is False
    for name in ("title", "summary", "event_time", "expires_at", "supersedes_id"):
        assert columns[name].nullable is True


def test_memory_metadata_constraints_foreign_key_and_indexes() -> None:
    checks = {
        constraint.name
        for constraint in Memory.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert checks == {
        "ck_memories_memory_type",
        "ck_memories_importance_range",
        "ck_memories_confidence_range",
        "ck_memories_status",
    }
    foreign_key = next(iter(Memory.__table__.c.supersedes_id.foreign_keys))
    assert foreign_key.target_fullname == "memories.id"
    assert foreign_key.ondelete == "SET NULL"
    indexed = {
        tuple(column.name for column in index.columns)
        for index in Memory.__table__.indexes
    }
    assert {
        ("memory_type",),
        ("status",),
        ("event_time",),
        ("supersedes_id",),
    } <= indexed


def test_existing_models_have_no_embedding_or_vector_columns() -> None:
    for table in (
        Project.__table__,
        Memory.__table__,
        Source.__table__,
        MemorySource.__table__,
    ):
        assert "embedding" not in table.c
        assert all(column.name != "embedding" for column in table.c)


def test_memory_embedding_schema_and_constraints() -> None:
    columns = MemoryEmbedding.__table__.c
    assert set(columns.keys()) == {
        "id",
        "memory_id",
        "provider",
        "model",
        "dimensions",
        "embedding",
        "input_hash",
        "embedded_at",
        "created_at",
        "updated_at",
    }
    assert all(column.nullable is False for column in columns)
    assert isinstance(columns.embedding.type, Vector)
    assert columns.embedding.type.dim == 1536
    foreign_key = next(iter(columns.memory_id.foreign_keys))
    assert foreign_key.target_fullname == "memories.id"
    assert foreign_key.ondelete == "CASCADE"
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in MemoryEmbedding.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("memory_id",) in unique_columns
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in MemoryEmbedding.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert checks["ck_memory_embeddings_dimensions"] == "dimensions = 1536"
    assert "{64}" in checks["ck_memory_embeddings_input_hash_format"]
    for name in ("embedded_at", "created_at", "updated_at"):
        assert isinstance(columns[name].type, DateTime)
        assert columns[name].type.timezone is True


def test_memory_embedding_indexes_and_relationships() -> None:
    indexes = {index.name: index for index in MemoryEmbedding.__table__.indexes}
    assert {"ix_memory_embeddings_provider", "ix_memory_embeddings_model"} < set(
        indexes
    )
    hnsw = indexes["ix_memory_embeddings_embedding_hnsw"]
    assert hnsw.dialect_options["postgresql"]["using"] == "hnsw"
    assert hnsw.dialect_options["postgresql"]["ops"] == {
        "embedding": "vector_cosine_ops"
    }
    parent = Memory.embedding_record.property
    child = MemoryEmbedding.memory.property
    assert parent.uselist is False and parent.passive_deletes is True
    assert "delete-orphan" in parent.cascade
    assert "delete" not in child.cascade and "delete-orphan" not in child.cascade


def test_embedding_is_not_part_of_public_memory_schemas() -> None:
    for schema in (MemoryCreate, MemoryRead):
        assert "embedding" not in schema.model_fields
        assert "embedding_record" not in schema.model_fields


def test_memory_search_vector_is_generated_tsvector_with_gin_index() -> None:
    column = Memory.__table__.c.search_vector
    assert isinstance(column.type, TSVECTOR)
    assert column.computed is not None and column.computed.persisted is True
    assert "to_tsvector('simple'" in str(column.computed.sqltext)
    index = next(
        index
        for index in Memory.__table__.indexes
        if index.name == "ix_memories_search_vector"
    )
    assert index.dialect_options["postgresql"]["using"] == "gin"


def test_relationships_do_not_delete_memories() -> None:
    relationship = Project.memories.property

    assert isinstance(relationship, RelationshipProperty)
    assert "delete" not in relationship.cascade
    assert "delete-orphan" not in relationship.cascade
    assert relationship.passive_deletes is True


def test_source_link_relationships_only_delete_association_rows() -> None:
    for relationship in (Memory.source_links.property, Source.memory_links.property):
        assert isinstance(relationship, RelationshipProperty)
        assert "delete-orphan" in relationship.cascade
        assert relationship.passive_deletes is True
    for relationship in (MemorySource.memory.property, MemorySource.source.property):
        assert "delete" not in relationship.cascade
        assert "delete-orphan" not in relationship.cascade


def test_importing_models_does_not_create_engine() -> None:
    reset_database_state()

    importlib.import_module("app.models.project")
    importlib.import_module("app.models.memory")
    importlib.import_module("app.models.memory_embedding")
    importlib.import_module("app.models.memory_source")
    importlib.import_module("app.models.source")

    assert get_engine.cache_info().currsize == 0
