"""Checkpoint 85 joined Local V1.3 Automation acceptance flows."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.agent_planning.provider import PlanningContext, PlanningResult
from app.automations import scheduler_runner
from app.daily_brief.service import get_result as get_daily_brief_result
from app.db.session import get_engine
from app.main import create_app
from app.models.agent_runtime import AgentEvent, AgentRun, AgentStep, ToolInvocation
from app.models.automation import (
    Automation,
    AutomationNotification,
    AutomationOccurrence,
)
from app.models.project import Project
from app.project_watch.changes import INITIAL_WINDOW
from app.project_watch.provider import ProjectWatchProviderResult
from app.project_watch.service import get_result as get_project_watch_result
from app.research.provider import ResearchProviderResult
from tests.integration.conftest import verify_connected_test_database


@pytest.fixture(autouse=True)
def clean_acceptance_rows(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        for model in (
            AutomationNotification,
            AutomationOccurrence,
            ToolInvocation,
            AgentStep,
            AgentEvent,
            AgentRun,
            Automation,
        ):
            session.execute(delete(model))
        session.execute(delete(Project).where(Project.name.like("cp85-%")))
        session.commit()
    yield
    with Session(get_engine()) as session:
        for model in (
            AutomationNotification,
            AutomationOccurrence,
            ToolInvocation,
            AgentStep,
            AgentEvent,
            AgentRun,
            Automation,
        ):
            session.execute(delete(model))
        session.execute(delete(Project).where(Project.name.like("cp85-%")))
        session.commit()


class AcceptancePlanningProvider:
    """Return one allowed local lexical read for the exact fixed goal."""

    def __init__(self) -> None:
        self.calls = 0

    def plan(self, context: PlanningContext) -> PlanningResult:
        self.calls += 1
        return PlanningResult.model_validate(
            {
                "goal_summary": context.goal_summary,
                "steps": [
                    {
                        "purpose": "Read bounded reviewed local evidence",
                        "tool_name": "memory.search_explained",
                        "tool_version": 1,
                        "candidate_input": {
                            "query": "cp85 acceptance evidence",
                            "mode": "lexical",
                            "filters": {
                                "memory_type": None,
                                "status": None,
                                "importance_min": None,
                                "importance_max": None,
                                "confidence_min": None,
                                "confidence_max": None,
                                "event_time_from": None,
                                "event_time_to": None,
                                "created_at_from": None,
                                "created_at_to": None,
                            },
                            "pagination": {"limit": 5, "offset": 0},
                        },
                        "expected_evidence": ["Reviewed local identifiers only"],
                        "success_condition": "The bounded local read returns",
                        "stop_condition": "Stop after the one read",
                    }
                ],
            },
            strict=True,
        )


class AcceptanceDailyBriefProvider:
    def synthesize(
        self, *, goal: str, evidence: list[dict[str, object]]
    ) -> ResearchProviderResult:
        return ResearchProviderResult(status="insufficient_evidence", claims=[])


class AcceptanceProjectWatchProvider:
    def synthesize(
        self, *, goal: str, evidence: list[dict[str, object]]
    ) -> ProjectWatchProviderResult:
        return ProjectWatchProviderResult(status="no_meaningful_change", findings=[])


@pytest.mark.parametrize("agent_kind", ["daily_brief", "project_watch"])
def test_api_scheduler_result_history_notification_and_reentry(
    agent_kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    client = TestClient(create_app())
    project_id = None
    if agent_kind == "project_watch":
        project = client.post("/projects", json={"name": f"cp85-{uuid.uuid4().hex}"})
        assert project.status_code == 201
        project_id = project.json()["id"]
    payload: dict[str, object] = {
        "label": f"cp85 {agent_kind}",
        "agent_kind": agent_kind,
        "project_id": project_id,
        "execution_mode": "automatic_read_only",
        "missed_run_policy": "run_once",
        "schedule": {
            "kind": "daily",
            "timezone_name": "UTC",
            "local_time": "12:00:00",
        },
    }
    preview = client.post(
        "/automations/preview",
        json={
            "schedule": payload["schedule"],
            "after_utc": now.isoformat(),
            "count": 2,
        },
    )
    assert preview.status_code == 200
    assert len(preview.json()) == 2
    created = client.post("/automations", json=payload)
    assert created.status_code == 201
    automation_id = created.json()["id"]
    enabled = client.post(
        f"/automations/{automation_id}/enable", json={"expected_revision": 0}
    )
    assert enabled.status_code == 200

    with Session(get_engine()) as session:
        automation = session.get(Automation, uuid.UUID(automation_id))
        assert automation is not None
        automation.next_occurrence_at = now - timedelta(minutes=1)
        session.commit()

    provider = AcceptancePlanningProvider()
    monkeypatch.setattr(scheduler_runner, "get_planning_provider", lambda: provider)
    monkeypatch.setattr(
        scheduler_runner,
        "get_embedding_provider",
        lambda: pytest.fail("lexical execution requested an embedding provider"),
    )
    monkeypatch.setattr(
        scheduler_runner, "configured_embedding_provider_available", lambda: False
    )
    monkeypatch.setattr(
        scheduler_runner,
        "get_daily_brief_provider",
        lambda: AcceptanceDailyBriefProvider(),
    )
    monkeypatch.setattr(
        scheduler_runner,
        "get_project_watch_provider",
        lambda: AcceptanceProjectWatchProvider(),
    )

    first = scheduler_runner.run_one_tick(now=now)
    assert len(first.materialized_ids) == 1
    assert len(first.claimed_ids) == 1
    assert len(first.linked_run_ids) == 1
    assert len(first.automatically_coordinated_ids) == 1
    second = scheduler_runner.run_one_tick(now=now + timedelta(seconds=1))
    third = scheduler_runner.run_one_tick(now=now + timedelta(seconds=2))
    assert second.linked_run_ids == third.linked_run_ids == ()
    assert provider.calls == 1

    history = client.get(f"/automations/{automation_id}/occurrences")
    assert history.status_code == 200
    assert len(history.json()) == 1
    occurrence_projection = history.json()[0]
    assert occurrence_projection["state"] == "completed"
    assert occurrence_projection["agent_run_id"] == str(first.linked_run_ids[0])
    run_projection = client.get(f"/agent-runs/{occurrence_projection['agent_run_id']}")
    assert run_projection.status_code == 200
    assert run_projection.json()["state"] == "completed"
    notifications = client.get(
        f"/automation-notifications?automation_id={automation_id}"
    )
    assert notifications.status_code == 200
    assert len(notifications.json()) == 1
    serialized = str(notifications.json()).casefold()
    for forbidden in ("provider", "tool", "knowledge", "result content"):
        assert forbidden not in serialized
    notice_id = notifications.json()[0]["id"]
    assert client.post(f"/automation-notifications/{notice_id}/read").status_code == 200
    assert client.get("/automation-notifications?unread_only=true").json() == []

    with Session(get_engine()) as session:
        assert (
            session.scalar(select(func.count()).select_from(AutomationOccurrence)) == 1
        )
        assert session.scalar(select(func.count()).select_from(AgentRun)) == 1
        run_id = first.linked_run_ids[0]
        occurrence = session.scalar(select(AutomationOccurrence))
        assert occurrence is not None
        observed_scope = (
            str(occurrence.project_id) if occurrence.project_id is not None else None
        )
        assert observed_scope == project_id
        result = (
            get_daily_brief_result(session, run_id)
            if agent_kind == "daily_brief"
            else get_project_watch_result(session, run_id)
        )
        assert result is not None
        expected_status = (
            "insufficient_evidence"
            if agent_kind == "daily_brief"
            else "no_meaningful_change"
        )
        assert result["status"] == expected_status
        result_event_type = f"{agent_kind}.result"
        assert (
            session.scalar(
                select(func.count())
                .select_from(AgentEvent)
                .where(AgentEvent.event_type == result_event_type)
            )
            == 1
        )
        if agent_kind == "project_watch":
            assert result["window_end"] == occurrence.scheduled_at.isoformat()
            assert (
                result["window_start"]
                == (occurrence.scheduled_at - INITIAL_WINDOW).isoformat()
            )
