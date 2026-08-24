"""PostgreSQL scoping and preservation proof for Project export."""

import hashlib
import json
import shutil
import uuid
import zipfile
from collections.abc import Generator
from datetime import time
from pathlib import Path

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.models import Memory, Project
from app.models.automation import (
    Automation,
    AutomationNotification,
    AutomationOccurrence,
)
from app.project_export.models import CURRENT_DATABASE_REVISION
from app.project_export.service import export_project
from tests.integration.conftest import verify_connected_test_database


@pytest.fixture
def export_tmp_path() -> Generator[Path, None, None]:
    path = Path(".tmp-tests") / f"project-export-integration-{uuid.uuid4()}"
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path)


@pytest.fixture
def clean_export_database(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(AutomationNotification))
        session.execute(delete(AutomationOccurrence))
        session.execute(delete(Automation))
        session.execute(delete(Memory))
        session.execute(delete(Project))
        session.commit()
    yield
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(AutomationNotification))
        session.execute(delete(AutomationOccurrence))
        session.execute(delete(Automation))
        session.execute(delete(Memory))
        session.execute(delete(Project))
        session.commit()


def test_project_export_preserves_fields_and_excludes_other_scopes(
    clean_export_database: None,
    test_database_url: str,
    export_tmp_path: Path,
) -> None:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        target = Project(name=f"export-{uuid.uuid4()}", description="target")
        unrelated = Project(name=f"other-{uuid.uuid4()}")
        session.add_all((target, unrelated))
        session.flush()
        session.add(
            Automation(
                label="must remain excluded",
                agent_kind="daily_brief",
                project_id=target.id,
                schedule_kind="daily",
                timezone_name="UTC",
                local_time=time(8, 0),
            )
        )
        first = Memory(
            project_id=target.id,
            content="first content",
            title="First",
            summary=None,
            source="manual",
            memory_type="decision",
            importance=0.75,
            confidence=0.8,
        )
        session.add(first)
        session.flush()
        second = Memory(
            project_id=target.id,
            content="replacement",
            supersedes_id=first.id,
            status="active",
        )
        session.add_all(
            (
                second,
                Memory(project_id=unrelated.id, content="must not leak"),
                Memory(content="unassigned must not leak"),
            )
        )
        session.commit()
        target_id = target.id
        first_id = first.id
        second_id = second.id

    output = export_tmp_path / "project.sbexport"
    with Session(get_engine(), autoflush=False) as session:
        result = export_project(
            session,
            target_id,
            output,
            source_alembic_revision=CURRENT_DATABASE_REVISION,
        )
        session.rollback()

    with zipfile.ZipFile(output) as archive:
        assert not any("automation" in name for name in archive.namelist())
        project = json.loads(archive.read("project.json"))
        memories = [
            json.loads(line)
            for line in archive.read("memories.jsonl").decode().splitlines()
        ]
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["format_version"] == 1
        assert manifest["source_alembic_revision"] == CURRENT_DATABASE_REVISION
        assert project["id"] == str(target_id)
        assert project["description"] == "target"
        assert {row["id"] for row in memories} == {str(first_id), str(second_id)}
        replacement = next(row for row in memories if row["id"] == str(second_id))
        assert replacement["supersedes_id"] == str(first_id)
        preserved = next(row for row in memories if row["id"] == str(first_id))
        assert preserved["content"] == "first content"
        assert preserved["importance"] == 0.75
        assert result.entity_counts["memories"] == 2
        for entry in manifest["files"]:
            payload = archive.read(entry["path"])
            assert hashlib.sha256(payload).hexdigest() == entry["sha256"]
