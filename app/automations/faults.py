"""Test-only deterministic scheduler transaction fault boundaries."""

from enum import StrEnum


class FaultPoint(StrEnum):
    AFTER_OCCURRENCE_INSERT = "after_occurrence_insert"
    AFTER_NEXT_OCCURRENCE_ADVANCE = "after_next_occurrence_advance"
    AFTER_CLAIM_STATE = "after_claim_state"
    AFTER_LEASE_GENERATION = "after_lease_generation"
    AFTER_RUN_CREATION = "after_run_creation"
    AFTER_RUN_LINK = "after_run_link"


class FaultInjectionError(RuntimeError):
    """Test signal that callers must roll back without translation."""


def fire(_point: FaultPoint) -> None:
    """No-op in production; focused tests monkeypatch this function."""
