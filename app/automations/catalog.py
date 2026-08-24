"""Closed application-owned catalog of planned schedulable Automations."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SchedulableAgent:
    kind: str
    version: str
    project_required: bool


CATALOG: dict[tuple[str, str], SchedulableAgent] = {
    ("daily_brief", "1"): SchedulableAgent("daily_brief", "1", False),
    ("project_watch", "1"): SchedulableAgent("project_watch", "1", True),
}


def get_schedulable_agent(kind: str, version: str) -> SchedulableAgent | None:
    """Return only an exact code-owned planned identity.

    Catalog membership describes configuration validity only. It grants no Run,
    Tool, provider, planning, or execution authority.
    """

    return CATALOG.get((kind, version))
