"""Checkpoint 110 PostgreSQL federation, isolation, and provenance coverage."""

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.calendar.identity import occurrence_identity
from app.connectors.validation import snapshot_content_hash
from app.context_hub.models import ContextFamily, ContextHubQuery, ContextScope
from app.context_hub.service import ContextNotFoundError, query_context, reopen_context
from app.db.session import get_engine
from app.main import create_app
from app.models.calendar import (
    CalendarAccountRevision,
    CalendarEventObservation,
    CalendarEventRevision,
    CalendarIdentity,
    CalendarSyncRun,
)
from app.models.connector import ConnectorAccount, ConnectorSyncRun, ExternalItem
from app.models.memory import Memory
from app.models.memory_source import MemorySource
from app.models.project import Project
from app.models.source import Source
from app.models.source_chunk import SourceChunk
from app.models.source_document import SourceDocument
from app.repositories.calendar import (
    create_account_revision,
    create_calendar_identity,
    mark_observation_evidence_complete,
    record_event_observation,
    record_event_revision,
)
from app.repositories.calendar import (
    create_sync_run as create_calendar_run,
)
from app.repositories.connectors import (
    create_account,
    create_sync_run,
    record_item_revision,
)


def _cleanup_api_scopes(project_ids: tuple[uuid.UUID, ...]) -> None:
    """Remove only the exact synthetic scopes owned by one API test."""
    with Session(get_engine()) as session:
        calendar_run_ids = tuple(
            session.scalars(
                select(CalendarSyncRun.id).where(
                    CalendarSyncRun.project_id.in_(project_ids)
                )
            )
        )
        account_revision_ids = tuple(
            session.scalars(
                select(CalendarAccountRevision.id).where(
                    CalendarAccountRevision.project_id.in_(project_ids)
                )
            )
        )
        memory_ids = tuple(
            session.scalars(select(Memory.id).where(Memory.project_id.in_(project_ids)))
        )
        source_ids = tuple(
            session.scalars(
                select(MemorySource.source_id).where(
                    MemorySource.memory_id.in_(memory_ids)
                )
            )
        )
        document_ids = tuple(
            session.scalars(
                select(SourceDocument.id).where(
                    SourceDocument.source_id.in_(source_ids)
                )
            )
        )
        session.execute(
            delete(CalendarEventObservation).where(
                CalendarEventObservation.sync_run_id.in_(calendar_run_ids)
            )
        )
        session.execute(
            delete(CalendarEventRevision).where(
                CalendarEventRevision.project_id.in_(project_ids)
            )
        )
        session.execute(
            delete(CalendarSyncRun).where(CalendarSyncRun.project_id.in_(project_ids))
        )
        session.execute(
            delete(CalendarIdentity).where(
                CalendarIdentity.account_revision_id.in_(account_revision_ids)
            )
        )
        session.execute(
            delete(CalendarAccountRevision).where(
                CalendarAccountRevision.project_id.in_(project_ids)
            )
        )
        session.execute(
            delete(ExternalItem).where(ExternalItem.project_id.in_(project_ids))
        )
        session.execute(
            delete(ConnectorSyncRun).where(ConnectorSyncRun.project_id.in_(project_ids))
        )
        session.execute(
            delete(ConnectorAccount).where(ConnectorAccount.project_id.in_(project_ids))
        )
        session.execute(
            delete(SourceChunk).where(SourceChunk.document_id.in_(document_ids))
        )
        session.execute(
            delete(SourceDocument).where(SourceDocument.source_id.in_(source_ids))
        )
        session.execute(
            delete(MemorySource).where(MemorySource.memory_id.in_(memory_ids))
        )
        session.execute(delete(Source).where(Source.id.in_(source_ids)))
        session.execute(delete(Memory).where(Memory.id.in_(memory_ids)))
        session.execute(delete(Project).where(Project.id.in_(project_ids)))
        session.commit()


def _seed_scope(session: Session, project_id: uuid.UUID | None, label: str) -> None:
    now = datetime.now(UTC)
    source = Source(source_type="document", name=f"local-{label}")
    document = SourceDocument(
        source=source,
        media_type="text/plain",
        ingestion_status="extracted",
        extracted_text=f"hostile <script>{label}</script>",
    )
    document.chunks.append(
        SourceChunk(
            chunk_index=0,
            content=f"local text {label}",
            char_start=0,
            char_end=len(f"local text {label}"),
            content_hash=(label[0].encode().hex() * 64)[:64],
        )
    )
    memory = Memory(project_id=project_id, content=f"memory {label}")
    session.add_all((source, document, memory))
    session.flush()
    session.add(MemorySource(memory_id=memory.id, source_id=source.id))

    account = create_account(
        session,
        ConnectorAccount(
            external_account_id=f"account:{label}",
            external_account_fingerprint=hashlib.sha256(
                f"github:{label}".encode()
            ).hexdigest(),
            credential_reference=f"sbcred:v1:{uuid.uuid4()}",
            project_id=project_id,
            resource_allowlist=[f"owner/repo-{label}"],
            granted_scope_fingerprint="c" * 64,
        ),
    )
    run = create_sync_run(
        session,
        ConnectorSyncRun(
            account_id=account.id,
            provider="github",
            external_account_id=account.external_account_id,
            account_revision=account.revision,
            project_id=project_id,
            trigger_kind="manual",
            trigger_identity=f"hub_{label}",
        ),
    )
    body = json.dumps({"body": f"github text {label}", "number": 1, "state": "open"})
    title = f"github-{label}"
    record_item_revision(
        session,
        ExternalItem(
            account_id=account.id,
            provider="github",
            external_account_id=account.external_account_id,
            external_resource_id=f"repository:R_{label}",
            external_item_id=f"issue:I_{label}",
            resource_type="issue",
            provider_source_version=f"version-{label}",
            title=title,
            body=body,
            content_hash=snapshot_content_hash(title, body),
            application_revision=999,
            project_id=project_id,
            created_sync_run_id=run.id,
            last_seen_sync_run_id=run.id,
            first_seen_at=now,
            last_seen_at=now,
        ),
        seen_at=now,
    )

    calendar_account = create_account_revision(
        session,
        CalendarAccountRevision(
            configuration_id=uuid.uuid4(),
            configuration_revision=1,
            account_fingerprint=hashlib.sha256(
                f"calendar:{label}".encode()
            ).hexdigest(),
            credential_reference=f"sbcred:v1:{uuid.uuid4()}",
            project_id=project_id,
        ),
    )
    calendar = create_calendar_identity(
        session,
        CalendarIdentity(
            account_revision_id=calendar_account.id,
            account_fingerprint=calendar_account.account_fingerprint,
            provider_calendar_id=f"calendar-{label}",
        ),
    )
    calendar_run = create_calendar_run(
        session,
        CalendarSyncRun(
            account_revision_id=calendar_account.id,
            calendar_identity_id=calendar.id,
            project_id=project_id,
            window_start=now - timedelta(days=1),
            window_end=now + timedelta(days=1),
            trigger_kind="manual",
        ),
    )
    identity = occurrence_identity(event_id=f"event-{label}")
    event, _ = record_event_revision(
        session,
        CalendarEventRevision(
            account_revision_id=calendar_account.id,
            calendar_identity_id=calendar.id,
            sync_run_id=calendar_run.id,
            project_id=project_id,
            provider_event_id=f"event-{label}",
            occurrence_key=identity.key,
            provider_etag=f'"etag-{label}"',
            provider_updated_at=now,
            application_revision=999,
            content_hash="f" * 64,
            event_type="default",
            title=f"calendar-{label}",
            all_day=False,
            start_instant=now,
            end_instant=now + timedelta(hours=1),
            source_timezone="UTC",
            state="current",
            is_private=False,
            first_seen_at=now,
            last_seen_at=now,
        ),
        seen_at=now,
    )
    record_event_observation(session, calendar_run, event, observed_at=now)
    calendar_run.items_seen = 1
    calendar_run.items_written = 1
    calendar_run.status = "succeeded"
    calendar_run.completeness = "complete"
    calendar_run.started_at = now
    calendar_run.completed_at = now
    mark_observation_evidence_complete(session, calendar_run)
    session.flush()


def test_exact_scope_grouping_inert_text_and_reopen(
    migrated_test_database: None,
) -> None:
    with Session(get_engine()) as session:
        first = Project(name="hub-a-" + uuid.uuid4().hex)
        second = Project(name="hub-b-" + uuid.uuid4().hex)
        session.add_all((first, second))
        session.flush()
        _seed_scope(session, first.id, "a")
        _seed_scope(session, second.id, "b")

        result = query_context(
            session, ContextHubQuery(scope=ContextScope(project_id=first.id))
        )
        assert tuple(group.family for group in result.groups) == (
            ContextFamily.LOCAL_SOURCE,
            ContextFamily.GITHUB,
            ContextFamily.GOOGLE_CALENDAR,
        )
        items = [item for group in result.groups for item in group.items]
        assert [item.title for item in items] == ["local-a", "github-a", "calendar-a"]
        assert all(item.scope.project_id == first.id for item in items)
        assert "<script>" not in items[0].text
        assert [
            reopen_context(session, ContextScope(project_id=first.id), item.provenance)
            for item in items
        ] == items
        with pytest.raises(ContextNotFoundError):
            reopen_context(
                session, ContextScope(project_id=second.id), items[0].provenance
            )
        session.rollback()


def test_explicit_unassigned_isolation(migrated_test_database: None) -> None:
    with Session(get_engine()) as session:
        project = Project(name="hub-project-" + uuid.uuid4().hex)
        session.add(project)
        session.flush()
        _seed_scope(session, project.id, "a")
        _seed_scope(session, None, "u")
        result = query_context(
            session, ContextHubQuery(scope=ContextScope(unassigned=True))
        )
        assert [item.title for group in result.groups for item in group.items] == [
            "local-u",
            "github-u",
            "calendar-u",
        ]
        session.rollback()


def test_context_hub_api_paginates_reopens_facets_and_rejects_replay(
    migrated_test_database: None,
) -> None:
    with Session(get_engine()) as session:
        project = Project(name="hub-api-" + uuid.uuid4().hex)
        other = Project(name="hub-other-" + uuid.uuid4().hex)
        session.add_all((project, other))
        session.flush()
        _seed_scope(session, project.id, "a")
        _seed_scope(session, project.id, "b")
        _seed_scope(session, other.id, "u")
        session.commit()
        project_id = str(project.id)
        other_id = str(other.id)

    try:
        client = TestClient(create_app(), client=("127.0.0.1", 50000))
        body = {"scope": {"project_id": project_id}, "page_size": 1}
        first = client.post("/context-hub/query", json=body)
        assert first.status_code == 200
        first_body = first.json()
        assert [group["family"] for group in first_body["groups"]] == [
            "local_source",
            "github",
            "google_calendar",
        ]
        assert all(len(group["items"]) == 1 for group in first_body["groups"])
        assert first_body["next_cursor"]
        assert "account:" not in first.text and "sbcred:" not in first.text

        pages = [first_body]
        cursor = first_body["next_cursor"]
        while cursor is not None:
            response = client.post(
                "/context-hub/query", json={**body, "cursor": cursor}
            )
            assert response.status_code == 200
            pages.append(response.json())
            cursor = pages[-1]["next_cursor"]
            assert len(pages) <= 4
        first_ids = {
            item["reopen_id"]
            for group in first_body["groups"]
            for item in group["items"]
        }
        second_ids = {
            item["reopen_id"] for group in pages[1]["groups"] for item in group["items"]
        }
        assert first_ids.isdisjoint(second_ids)
        all_ids = [
            item["reopen_id"]
            for page in pages
            for group in page["groups"]
            for item in group["items"]
        ]
        assert len(all_ids) == len(set(all_ids)) == 6

        item = first_body["groups"][1]["items"][0]
        detail = client.post(
            "/context-hub/detail",
            json={
                "scope": {"project_id": project_id},
                "family": item["family"],
                "reopen_id": item["reopen_id"],
            },
        )
        assert detail.status_code == 200 and detail.json() == item
        forged = client.post(
            "/context-hub/detail",
            json={
                "scope": {"project_id": other_id},
                "family": item["family"],
                "reopen_id": item["reopen_id"],
            },
        )
        assert forged.status_code == 404
        wrong_family = client.post(
            "/context-hub/detail",
            json={
                "scope": {"project_id": project_id},
                "family": "local_source",
                "reopen_id": item["reopen_id"],
            },
        )
        assert wrong_family.status_code == 404

        facets = client.post(
            "/context-hub/facets", json={"scope": {"project_id": project_id}}
        )
        assert facets.status_code == 200
        assert facets.json()["families"] == [
            {"value": "github", "count": 2},
            {"value": "google_calendar", "count": 2},
            {"value": "local_source", "count": 2},
        ]
        replay = client.post(
            "/context-hub/query",
            json={
                "scope": {"project_id": other_id},
                "page_size": 1,
                "cursor": first_body["next_cursor"],
            },
        )
        assert replay.status_code == 422
        malformed = client.post(
            "/context-hub/query", json={**body, "cursor": "not-a-cursor"}
        )
        assert malformed.status_code == 422
        missing_scope = client.post("/context-hub/query", json={})
        both_scope = client.post(
            "/context-hub/query",
            json={"scope": {"project_id": project_id, "unassigned": True}},
        )
        assert missing_scope.status_code == both_scope.status_code == 422
        assert missing_scope.json() == {"detail": "invalid context hub request"}
    finally:
        _cleanup_api_scopes((project.id, other.id))


def test_context_hub_rejects_non_loopback_before_database() -> None:
    response = TestClient(create_app()).post(
        "/context-hub/query", json={"scope": {"unassigned": True}}
    )
    assert response.status_code == 403
