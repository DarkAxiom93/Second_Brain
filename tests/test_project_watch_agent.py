from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.automations.catalog import PROJECT_WATCH_DEFINITION
from app.project_watch.openai_provider import INSTRUCTIONS
from app.project_watch.provider import ProjectWatchProviderResult


def test_project_watch_definition_is_fixed_read_only() -> None:
    assert (PROJECT_WATCH_DEFINITION.kind, PROJECT_WATCH_DEFINITION.version) == (
        "project_watch",
        "1",
    )
    assert PROJECT_WATCH_DEFINITION.authority == "read"
    assert PROJECT_WATCH_DEFINITION.registry_version == "agent-tools-v1"
    assert PROJECT_WATCH_DEFINITION.scope_rules == "exact-non-null-project"
    assert PROJECT_WATCH_DEFINITION.max_evidence == 20


def test_project_watch_contract_is_closed() -> None:
    assert (
        ProjectWatchProviderResult.model_validate(
            {"status": "no_meaningful_change", "findings": []}, strict=True
        ).status
        == "no_meaningful_change"
    )
    with pytest.raises(ValidationError):
        ProjectWatchProviderResult.model_validate(
            {"status": "changes_found", "findings": [], "prompt": "override"},
            strict=True,
        )


def test_project_watch_instructions_treat_content_as_data() -> None:
    lowered = INSTRUCTIONS.lower()
    for boundary in ("untrusted data", "exact project", "time window", "never"):
        assert boundary in lowered


def test_window_timestamps_are_aware_fixture() -> None:
    assert datetime(2026, 8, 27, tzinfo=UTC).utcoffset() is not None
