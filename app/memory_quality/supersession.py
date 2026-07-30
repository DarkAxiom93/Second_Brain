"""Pure classification for explicit, human-controlled Memory supersession."""

from dataclasses import dataclass
from typing import Literal

from app.models.memory import Memory

SupersessionStatus = Literal["updated", "unchanged"]


@dataclass(frozen=True)
class SupersessionConflict(Exception):
    """An expected public conflict in a supersession request."""

    detail: str


def classify_supersession(
    *,
    older: Memory,
    replacement: Memory,
    existing_successors: list[Memory],
    creates_cycle: bool,
) -> SupersessionStatus:
    """Validate locked state and classify the requested transition."""

    exact_link = replacement.supersedes_id == older.id
    exact_successors = [row for row in existing_successors if row.id == replacement.id]
    other_successors = [row for row in existing_successors if row.id != replacement.id]

    if exact_link and older.status == "superseded":
        if replacement.status != "active" or other_successors or not exact_successors:
            raise SupersessionConflict("inconsistent existing supersession state")
        return "unchanged"
    if exact_link:
        raise SupersessionConflict("inconsistent existing supersession state")
    if older.status == "superseded":
        if existing_successors:
            raise SupersessionConflict("older memory already has a replacement")
        raise SupersessionConflict("inconsistent existing supersession state")
    if older.project_id != replacement.project_id:
        raise SupersessionConflict("memory project scope mismatch")
    if older.status != "active" or replacement.status != "active":
        raise SupersessionConflict("memory is not eligible for superseding")
    if replacement.supersedes_id is not None:
        raise SupersessionConflict("replacement memory already has a predecessor")
    if existing_successors:
        raise SupersessionConflict("older memory already has a replacement")
    if creates_cycle:
        raise SupersessionConflict("memory supersession would create a cycle")
    return "updated"
