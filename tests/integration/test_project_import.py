"""PostgreSQL transaction and round-trip proof for Project import."""

import shutil
import uuid
import zipfile
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.models import Memory, MemoryEmbedding, Project
from app.project_export.service import DATA_FILES, export_project
from app.project_import.models import ImportConflictError
from app.project_import.service import import_project
from tests.integration.conftest import verify_connected_test_database


@pytest.fixture
def import_tmp_path() -> Generator[Path, None, None]:
    path = Path(".tmp-tests") / f"project-import-integration-{uuid.uuid4()}"
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path)


@pytest.fixture
def clean_import_database(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(MemoryEmbedding))
        session.execute(delete(Memory))
        session.execute(delete(Project))
        session.commit()
    yield
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(MemoryEmbedding))
        session.execute(delete(Memory))
        session.execute(delete(Project))
        session.commit()


def _data_files(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in DATA_FILES}


def test_import_preserves_fields_vector_search_and_round_trip(
    clean_import_database: None,
    test_database_url: str,
    import_tmp_path: Path,
) -> None:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        project = Project(name=f"restore-{uuid.uuid4()}", description="round trip")
        session.add(project)
        session.flush()
        memory = Memory(
            project_id=project.id,
            content="restored searchable phrase",
            title="Restored",
            memory_type="decision",
            importance=0.8,
            confidence=0.9,
            status="active",
        )
        session.add(memory)
        session.flush()
        embedding = MemoryEmbedding(
            memory_id=memory.id,
            provider="fake",
            model="fake-1536",
            dimensions=1536,
            embedding=[0.25] * 1536,
            input_hash="a" * 64,
        )
        session.add(embedding)
        session.commit()
        project_id = project.id
        memory_id = memory.id
        created_at = memory.created_at

    first = import_tmp_path / "first.sbexport"
    with Session(get_engine(), autoflush=False) as session:
        export_project(
            session,
            project_id,
            first,
            source_alembic_revision="0009_memory_expiration",
        )
        session.rollback()
    before = _data_files(first)
    with Session(get_engine()) as session:
        session.execute(
            delete(MemoryEmbedding).where(MemoryEmbedding.memory_id == memory_id)
        )
        session.execute(delete(Memory).where(Memory.id == memory_id))
        session.execute(delete(Project).where(Project.id == project_id))
        session.commit()

    with Session(get_engine(), autoflush=False) as session:
        result = import_project(
            session,
            first,
            execute=True,
            expected_project_id=project_id,
        )
        session.commit()
    assert result.import_status == "imported"
    with Session(get_engine()) as session:
        restored = session.get(Memory, memory_id)
        restored_embedding = session.scalar(
            select(MemoryEmbedding).where(MemoryEmbedding.memory_id == memory_id)
        )
        assert restored is not None
        assert restored.created_at == created_at
        assert restored_embedding is not None
        assert restored_embedding.provider == "fake"
        assert list(restored_embedding.embedding) == pytest.approx([0.25] * 1536)
        assert (
            session.scalar(
                select(func.count())
                .select_from(Memory)
                .where(
                    Memory.search_vector.op("@@")(
                        func.plainto_tsquery("simple", "searchable")
                    )
                )
            )
            == 1
        )

    second = import_tmp_path / "second.sbexport"
    with Session(get_engine(), autoflush=False) as session:
        export_project(
            session,
            project_id,
            second,
            source_alembic_revision="0009_memory_expiration",
        )
        session.rollback()
    assert _data_files(second) == before


def test_conflict_and_mid_import_failure_leave_no_partial_project(
    clean_import_database: None,
    test_database_url: str,
    import_tmp_path: Path,
) -> None:
    verify_connected_test_database(test_database_url)
    project_id = uuid.uuid4()
    path = import_tmp_path / "rollback.sbexport"
    with Session(get_engine()) as session:
        session.add(Project(id=project_id, name="rollback"))
        session.commit()
    with Session(get_engine(), autoflush=False) as session:
        export_project(
            session,
            project_id,
            path,
            source_alembic_revision="0009_memory_expiration",
        )
        session.rollback()
    with Session(get_engine()) as session:
        with pytest.raises(ImportConflictError):
            import_project(session, path, execute=False)
        assert session.scalar(select(func.count()).select_from(Project)) == 1
        session.execute(delete(Project).where(Project.id == project_id))
        session.commit()

    def fail_after_project(name: str) -> None:
        if name == "sources.jsonl":
            raise RuntimeError("controlled failure")

    with Session(get_engine(), autoflush=False) as session:
        with pytest.raises(RuntimeError, match="controlled"):
            import_project(
                session,
                path,
                execute=True,
                expected_project_id=project_id,
                before_insert=fail_after_project,
            )
        session.rollback()
    with Session(get_engine()) as session:
        assert session.get(Project, project_id) is None
