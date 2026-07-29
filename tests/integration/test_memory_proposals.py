"""Guarded PostgreSQL coverage for extraction-run proposal persistence."""

import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.models import (
    MemoryExtractionRun,
    MemoryProposal,
    Source,
    SourceChunk,
    SourceDocument,
)
from tests.integration.conftest import verify_connected_test_database


def test_proposal_migration_lifecycle(
    test_database_url: str, alembic_config: Config
) -> None:
    verify_connected_test_database(test_database_url)
    command.downgrade(alembic_config, "0007_source_documents")
    try:
        assert not {"memory_extraction_runs", "memory_proposals"} & set(
            inspect(get_engine()).get_table_names()
        )
        command.upgrade(alembic_config, "0008_memory_proposals")
        with get_engine().connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "0008_memory_proposals"
            )
            assert (
                connection.scalar(text("SELECT count(*) FROM memory_extraction_runs"))
                == 0
            )
            assert connection.scalar(text("SELECT count(*) FROM memory_proposals")) == 0
        command.downgrade(alembic_config, "0007_source_documents")
        tables = set(inspect(get_engine()).get_table_names())
        assert "source_documents" in tables and "source_chunks" in tables
        assert not {"memory_extraction_runs", "memory_proposals"} & tables
    finally:
        command.upgrade(alembic_config, "head")


def _persist_run_and_chunk() -> tuple[uuid.UUID, uuid.UUID]:
    with Session(get_engine()) as session:
        source = Source(source_type="document", name="proposal-source")
        document = SourceDocument(
            source=source, media_type="text/plain", extracted_text="evidence"
        )
        chunk = SourceChunk(
            document=document,
            chunk_index=0,
            content="evidence",
            char_start=0,
            char_end=8,
            content_hash="a" * 64,
        )
        run = MemoryExtractionRun(
            document=document,
            provider="future",
            model="exact-model",
            prompt_version="v1",
            input_hash="b" * 64,
        )
        session.add_all([chunk, run])
        session.commit()
        return run.id, chunk.id


def test_valid_proposal_snapshots_and_chunk_set_null(
    migrated_test_database: None,
) -> None:
    run_id, chunk_id = _persist_run_and_chunk()
    with Session(get_engine()) as session:
        proposal = MemoryProposal(
            run_id=run_id,
            source_chunk_id=chunk_id,
            source_chunk_hash="a" * 64,
            proposal_index=0,
            content="candidate",
            memory_type="semantic",
            evidence_text="evidence",
            evidence_char_start=0,
            evidence_char_end=8,
            source_locator="page 1",
            proposal_hash="c" * 64,
        )
        session.add(proposal)
        session.commit()
        proposal_id = proposal.id
        assert proposal.review_status == "pending" and proposal.importance == 0.5
        session.delete(session.get(SourceChunk, chunk_id))
        session.commit()
        retained = session.get(MemoryProposal, proposal_id)
        assert retained is not None and retained.source_chunk_id is None
        assert (
            retained.source_chunk_hash == "a" * 64
            and retained.evidence_text == "evidence"
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("content", " \n"),
        ("evidence_text", "\t"),
        ("proposal_index", -1),
        ("memory_type", "unknown"),
        ("review_status", "unknown"),
        ("importance", -0.1),
        ("confidence", 1.1),
        ("proposal_hash", "A" * 64),
        ("source_chunk_hash", "bad"),
        ("evidence_char_end", 0),
    ],
)
def test_invalid_proposal_values_are_rejected(
    field: str, value: object, migrated_test_database: None
) -> None:
    run_id, chunk_id = _persist_run_and_chunk()
    values: dict[str, object] = {
        "run_id": run_id,
        "source_chunk_id": chunk_id,
        "source_chunk_hash": "d" * 64,
        "proposal_index": 0,
        "content": "valid",
        "memory_type": "working",
        "evidence_text": "valid",
        "evidence_char_start": 0,
        "evidence_char_end": 5,
        "proposal_hash": uuid.uuid4().hex * 2,
    }
    values[field] = value
    with Session(get_engine()) as session:
        session.add(MemoryProposal(**values))  # type: ignore[arg-type]
        with pytest.raises(IntegrityError):
            session.commit()
