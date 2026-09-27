"""Joined real-PostgreSQL CP121 Capture security evidence."""

from __future__ import annotations

import subprocess
import uuid
import zipfile
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.session import get_engine, reset_database_state
from app.main import create_app
from app.models import AgentRun, Memory, MemoryEmbedding, MemoryProposal
from app.models.automation import Automation, AutomationOccurrence
from app.models.capture_item import CaptureItem
from app.models.project import Project
from app.models.source import Source
from app.models.source_chunk import SourceChunk
from app.models.source_document import SourceDocument
from app.project_export.models import CURRENT_DATABASE_REVISION, FORMAT_NAME
from app.project_export.service import export_project
from tests.integration.conftest import verify_connected_test_database
from tests.integration.test_context_hub import _complete_rows, _runtime_tripwires
from tests.test_capture_security_adversarial import ADVERSARIAL_CAPTURE_CORPUS

pytestmark = pytest.mark.usefixtures("migrated_test_database")


@pytest.fixture(autouse=True)
def clean_security_captures(test_database_url: str) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(CaptureItem))
        session.commit()
    yield
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(CaptureItem))
        session.commit()


def _create(
    client: TestClient, content: str, project_id: uuid.UUID | None = None
) -> dict[str, object]:
    body: dict[str, object] = {"content": content}
    if project_id is not None:
        body["project_id"] = str(project_id)
    response = client.post(
        "/capture-items",
        json=body,
        headers={"Idempotency-Key": f"cp121-{uuid.uuid4()}"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.cp121_security
def test_cap08_hostile_corpus_stays_inert_through_real_capture_flows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _runtime_tripwires(monkeypatch)
    protected = (
        Memory,
        MemoryEmbedding,
        MemoryProposal,
        AgentRun,
        Automation,
        AutomationOccurrence,
    )
    before = _complete_rows(protected)
    client = TestClient(create_app(), client=("127.0.0.1", 52180))
    for index, value in enumerate(ADVERSARIAL_CAPTURE_CORPUS):
        created = _create(client, value)
        detail = client.post(
            f"/capture-items/{created['id']}/detail",
            json={"scope": {"unassigned": True}},
        )
        assert detail.status_code == 200 and detail.json()["content"] == value
        query = client.post(
            "/capture-items/query",
            json={"scope": {"unassigned": True}, "page_size": 50},
        )
        assert query.status_code == 200
        edited = client.patch(
            f"/capture-items/{created['id']}",
            json={
                "scope": {"unassigned": True},
                "revision": 1,
                "content": f"{value}\nrevision-{index}",
            },
        )
        assert edited.status_code == 200
    assert calls == []
    assert _complete_rows(protected) == before


@pytest.mark.cp121_security
def test_cap10_private_canaries_never_escape_public_errors_logs_or_cursors(
    caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    client = TestClient(create_app(), client=("127.0.0.1", 52184))
    content = f"cp121-content-{uuid.uuid4()}"
    key = f"cp121-private-{uuid.uuid4()}"
    created = client.post(
        "/capture-items",
        json={"content": content},
        headers={"Idempotency-Key": key},
    )
    assert created.status_code == 201
    public = created.json()
    cursor_response = client.post(
        "/capture-items/query",
        json={"scope": {"unassigned": True}, "page_size": 1},
    )
    conflict = client.post(
        "/capture-items",
        json={"content": "changed"},
        headers={"Idempotency-Key": key},
    )
    malformed = client.post(
        f"/capture-items/{uuid.uuid4()}/detail",
        json={"scope": {"unassigned": True}},
    )
    material = "\n".join(
        (
            str(public),
            str(cursor_response.headers),
            str(cursor_response.json().get("next_cursor")),
            str(conflict.json()),
            str(malformed.json()),
            caplog.text,
            capsys.readouterr().out,
            capsys.readouterr().err,
        )
    )
    assert key not in material
    assert "idempotency_key_hash" not in material
    assert "request_fingerprint" not in material
    assert "SELECT " not in material and "Traceback" not in material
    assert content in str(public)
    assert content not in str(conflict.json()) and content not in str(malformed.json())


@pytest.mark.cp121_security
def test_cap13_runtime_authority_surfaces_have_zero_capture_delta() -> None:
    from app.agent_tools.dispatch import (
        ToolCallContext,
        ToolUnavailableError,
        dispatch_exact,
    )

    protected = (
        Memory,
        MemoryEmbedding,
        MemoryProposal,
        AgentRun,
        Automation,
        AutomationOccurrence,
    )
    before = _complete_rows(protected)
    with Session(get_engine()) as session, pytest.raises(ToolUnavailableError):
        dispatch_exact(
            name="capture.get",
            version=1,
            normalized_input={"capture_id": uuid.uuid4()},
            context=ToolCallContext(session, None),
        )
    assert _complete_rows(protected) == before


@pytest.mark.cp121_security
def test_cap12_external_tripwires_are_zero_on_success_failure_and_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _runtime_tripwires(monkeypatch)
    client = TestClient(create_app(), client=("127.0.0.1", 52181))
    key = f"cp121-replay-{uuid.uuid4()}"
    first = client.post(
        "/capture-items",
        json={"content": "inert provider instruction"},
        headers={"Idempotency-Key": key},
    )
    replay = client.post(
        "/capture-items",
        json={"content": "inert provider instruction"},
        headers={"Idempotency-Key": key},
    )
    failure = client.post(
        "/capture-items",
        json={"content": "changed"},
        headers={"Idempotency-Key": key},
    )
    query = client.post("/capture-items/query", json={"scope": {"unassigned": True}})
    converted = client.post(
        f"/capture-items/{first.json()['id']}/convert-to-source",
        json={"scope": {"unassigned": True}, "revision": 1},
    )
    replay_conversion = client.post(
        f"/capture-items/{first.json()['id']}/convert-to-source",
        json={"scope": {"unassigned": True}, "revision": 1},
    )
    assert (first.status_code, replay.status_code, failure.status_code) == (
        201,
        200,
        409,
    )
    assert query.status_code == 200
    assert converted.status_code == replay_conversion.status_code == 200
    assert calls == []
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count(MemoryEmbedding.id))) == 0


@pytest.mark.cp121_security
def test_cap14_export_v1_archive_and_round_trip_exclude_capture(tmp_path: Path) -> None:
    client = TestClient(create_app(), client=("127.0.0.1", 52182))
    canary = f"cp121-export-private-{uuid.uuid4()}"
    with Session(get_engine()) as session:
        project = Project(name=f"cp121-export-{uuid.uuid4()}")
        session.add(project)
        session.commit()
        project_id = project.id
    assigned = _create(client, canary, project_id)
    unassigned = _create(client, canary + "-unassigned")
    outputs = (tmp_path / "first.sbexport", tmp_path / "second.sbexport")
    for output in outputs:
        with Session(get_engine(), autoflush=False) as session:
            result = export_project(
                session,
                project_id,
                output,
                source_alembic_revision=CURRENT_DATABASE_REVISION,
            )
            session.rollback()
        assert (
            result.format_version == 1 and FORMAT_NAME == "second-brain-project-export"
        )
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
            payload = b"".join(archive.read(name) for name in names)
        assert not any("capture" in name.lower() for name in names)
        assert canary.encode() not in payload
        assert str(assigned["id"]).encode() not in payload
        assert str(unassigned["id"]).encode() not in payload
    with Session(get_engine()) as session:
        assert (
            session.scalar(
                select(CaptureItem).where(
                    CaptureItem.id == uuid.UUID(str(assigned["id"]))
                )
            )
            is not None
        )
        assert (
            session.scalar(
                select(CaptureItem).where(
                    CaptureItem.id == uuid.UUID(str(unassigned["id"]))
                )
            )
            is not None
        )


@pytest.mark.cp121_security
def test_cap15_protected_postgresql_backup_restores_capture_exactly(
    test_database_url: str,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    verify_connected_test_database(test_database_url)
    client = TestClient(create_app(), client=("127.0.0.1", 52183))
    canary = f"cp121-backup-private-{uuid.uuid4()}"
    with Session(get_engine()) as session:
        project = Project(name=f"cp121-backup-{uuid.uuid4()}")
        session.add(project)
        session.commit()
        project_id = project.id
    created = _create(client, canary, project_id)
    edited = client.patch(
        f"/capture-items/{created['id']}",
        json={
            "scope": {"project_id": str(project_id)},
            "revision": 1,
            "content": canary + "-edited",
        },
    )
    assert edited.status_code == 200
    converted = client.post(
        f"/capture-items/{created['id']}/convert-to-source",
        json={"scope": {"project_id": str(project_id)}, "revision": 2},
    )
    assert converted.status_code == 200
    item_id = uuid.UUID(str(created["id"]))
    source_id = uuid.UUID(converted.json()["source"]["id"])
    with Session(get_engine()) as session:
        original = session.get(CaptureItem, item_id)
        document = session.scalar(
            select(SourceDocument).where(SourceDocument.source_id == source_id)
        )
        assert original is not None and document is not None
        chunks = session.scalars(
            select(SourceChunk)
            .where(SourceChunk.document_id == document.id)
            .order_by(SourceChunk.chunk_index)
        ).all()
        expected = (
            original.id,
            original.content,
            original.state,
            original.revision,
            original.project_id,
            original.resulting_source_id,
            document.id,
            document.extracted_text,
            tuple((row.id, row.chunk_index, row.content) for row in chunks),
        )

    backup = tmp_path / "cp121-postgresql.dump"
    container_backup = f"/tmp/cp121-{uuid.uuid4()}.dump"
    compose = ["docker", "compose", "--env-file", ".env.example"]

    def run(*arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [*compose, *arguments],
            check=True,
            capture_output=True,
            text=True,
        )

    try:
        run(
            "exec",
            "-T",
            "db",
            "pg_dump",
            "-U",
            "second_brain",
            "-d",
            "second_brain_test",
            "-Fc",
            "-f",
            container_backup,
        )
        run("exec", "-T", "db", "pg_restore", "--list", container_backup)
        run("cp", f"db:{container_backup}", str(backup))
        assert backup.is_file() and backup.stat().st_size > 0

        verify_connected_test_database(test_database_url)
        with Session(get_engine()) as session:
            session.execute(delete(CaptureItem).where(CaptureItem.id == item_id))
            session.execute(
                delete(SourceChunk).where(SourceChunk.document_id == document.id)
            )
            session.execute(
                delete(SourceDocument).where(SourceDocument.id == document.id)
            )
            session.execute(delete(Source).where(Source.id == source_id))
            session.commit()

        verify_connected_test_database(test_database_url)
        get_engine().dispose()
        run(
            "exec",
            "-T",
            "db",
            "pg_restore",
            "-U",
            "second_brain",
            "-d",
            "second_brain_test",
            "--clean",
            "--if-exists",
            "--single-transaction",
            "--no-owner",
            container_backup,
        )
        reset_database_state()
        with Session(get_engine()) as session:
            restored = session.get(CaptureItem, item_id)
            restored_document = session.scalar(
                select(SourceDocument).where(SourceDocument.source_id == source_id)
            )
            assert restored is not None and restored_document is not None
            restored_chunks = session.scalars(
                select(SourceChunk)
                .where(SourceChunk.document_id == restored_document.id)
                .order_by(SourceChunk.chunk_index)
            ).all()
            assert (
                restored.id,
                restored.content,
                restored.state,
                restored.revision,
                restored.project_id,
                restored.resulting_source_id,
                restored_document.id,
                restored_document.extracted_text,
                tuple(
                    (row.id, row.chunk_index, row.content) for row in restored_chunks
                ),
            ) == expected
            assert (
                session.scalar(
                    select(func.count(Source.id)).where(Source.id == source_id)
                )
                == 1
            )
            assert (
                session.scalar(
                    select(func.count(SourceDocument.id)).where(
                        SourceDocument.source_id == source_id
                    )
                )
                == 1
            )
    finally:
        subprocess.run(
            [*compose, "exec", "-T", "db", "rm", "-f", container_backup],
            check=False,
            capture_output=True,
            text=True,
        )
        backup.unlink(missing_ok=True)

    assert not backup.exists() and list(tmp_path.iterdir()) == []
    public_material = "\n".join(
        (
            (Path("frontend/src/Capture.tsx")).read_text(encoding="utf-8"),
            (Path("docs/checkpoint-121-report.md")).read_text(encoding="utf-8"),
            caplog.text,
        )
    )
    assert canary not in public_material
    assert "localStorage.setItem" not in public_material
    assert "sessionStorage.setItem" not in public_material
