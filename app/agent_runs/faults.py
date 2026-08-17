"""Deterministic in-process fault boundaries for tests.

Production owns no switch, environment variable, or public API for these hooks.
Tests may monkeypatch ``fire`` to raise at an exact transaction boundary.
"""

from enum import StrEnum


class FaultPoint(StrEnum):
    AFTER_RUN_CLAIM = "after_run_claim"
    BEFORE_INVOCATION_RESERVATION = "before_invocation_reservation"
    AFTER_INVOCATION_RESERVATION = "after_invocation_reservation"
    BEFORE_TOOL_CALL = "before_tool_call"
    AFTER_TOOL_RETURN = "after_tool_return"
    BEFORE_INVOCATION_FINALIZATION = "before_invocation_finalization"
    AFTER_INVOCATION_FINALIZATION = "after_invocation_finalization"
    BEFORE_RUN_COMPLETION = "before_run_completion"


class FaultInjectionError(RuntimeError):
    """Test-only signal that must cross production error translation unchanged."""


def fire(_point: FaultPoint) -> None:
    """No-op production implementation; deterministic tests monkeypatch it."""
