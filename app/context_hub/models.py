"""Closed internal contract for Context Hub checkpoint 110."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

CONTRACT_VERSION: Final[Literal["context-hub-v1"]] = "context-hub-v1"
MAX_QUERY_CHARACTERS = 256
MAX_QUERY_BYTES = 768
MAX_PAGE_SIZE = 50
MAX_FAMILIES = 3
MAX_KINDS = 5
MAX_STATES = 4
MAX_TRUST_LABELS = 2
MAX_TITLE_CHARACTERS = 500
MAX_TEXT_CHARACTERS = 4_000
MAX_FAMILY_WORK = 200


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ContextFamily(StrEnum):
    LOCAL_SOURCE = "local_source"
    GITHUB = "github"
    GOOGLE_CALENDAR = "google_calendar"


FAMILY_ORDER = (
    ContextFamily.LOCAL_SOURCE,
    ContextFamily.GITHUB,
    ContextFamily.GOOGLE_CALENDAR,
)


class ContextKind(StrEnum):
    SOURCE_CHUNK = "source_chunk"
    REPOSITORY = "repository"
    ISSUE = "issue"
    PULL_REQUEST = "pull_request"
    CALENDAR_EVENT = "calendar_event"


class TrustLabel(StrEnum):
    LOCAL_AUDITED = "local_audited"
    QUARANTINED_EXTERNAL = "quarantined_external"


class ContextState(StrEnum):
    EXTRACTED = "extracted"
    CURRENT = "current"
    STALE = "stale"
    DELETED = "deleted"


KIND_FAMILY = {
    ContextKind.SOURCE_CHUNK: ContextFamily.LOCAL_SOURCE,
    ContextKind.REPOSITORY: ContextFamily.GITHUB,
    ContextKind.ISSUE: ContextFamily.GITHUB,
    ContextKind.PULL_REQUEST: ContextFamily.GITHUB,
    ContextKind.CALENDAR_EVENT: ContextFamily.GOOGLE_CALENDAR,
}
STATE_FAMILIES = {
    ContextState.EXTRACTED: frozenset({ContextFamily.LOCAL_SOURCE}),
    ContextState.CURRENT: frozenset(
        {ContextFamily.GITHUB, ContextFamily.GOOGLE_CALENDAR}
    ),
    ContextState.STALE: frozenset(
        {ContextFamily.GITHUB, ContextFamily.GOOGLE_CALENDAR}
    ),
    ContextState.DELETED: frozenset({ContextFamily.GITHUB}),
}
TRUST_FAMILIES = {
    TrustLabel.LOCAL_AUDITED: frozenset({ContextFamily.LOCAL_SOURCE}),
    TrustLabel.QUARANTINED_EXTERNAL: frozenset(
        {ContextFamily.GITHUB, ContextFamily.GOOGLE_CALENDAR}
    ),
}


class ContextScope(ClosedModel):
    project_id: uuid.UUID | None = None
    unassigned: bool = False

    @model_validator(mode="after")
    def exact_scope(self) -> ContextScope:
        if (self.project_id is not None) == self.unassigned:
            raise ValueError(
                "select exactly one project_id or explicit unassigned=true"
            )
        return self


BoundedQuery = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=MAX_QUERY_CHARACTERS)
]


class ContextHubQuery(ClosedModel):
    scope: ContextScope
    families: Annotated[
        tuple[ContextFamily, ...], Field(min_length=1, max_length=MAX_FAMILIES)
    ] = FAMILY_ORDER
    kinds: Annotated[tuple[ContextKind, ...], Field(max_length=MAX_KINDS)] = ()
    trust: Annotated[tuple[TrustLabel, ...], Field(max_length=MAX_TRUST_LABELS)] = ()
    states: Annotated[tuple[ContextState, ...], Field(max_length=MAX_STATES)] = ()
    query: BoundedQuery = ""
    page_size: Annotated[int, Field(ge=1, le=MAX_PAGE_SIZE)] = 20

    @model_validator(mode="after")
    def closed_compatible_filters(self) -> ContextHubQuery:
        if any(
            len(values) != len(set(values))
            for values in (self.families, self.kinds, self.trust, self.states)
        ):
            raise ValueError("duplicate filters are not allowed")
        if len(self.query.encode("utf-8")) > MAX_QUERY_BYTES:
            raise ValueError("query exceeds UTF-8 byte limit")
        selected = set(self.families)
        if self.kinds and not all(KIND_FAMILY[kind] in selected for kind in self.kinds):
            raise ValueError("kind is incompatible with selected families")
        if self.trust and not all(
            TRUST_FAMILIES[label] & selected for label in self.trust
        ):
            raise ValueError("trust is incompatible with selected families")
        if self.states and not all(
            STATE_FAMILIES[state] & selected for state in self.states
        ):
            raise ValueError("state is incompatible with selected families")
        eligible = selected
        if self.kinds:
            eligible &= {KIND_FAMILY[kind] for kind in self.kinds}
        if self.trust:
            eligible &= set().union(*(TRUST_FAMILIES[label] for label in self.trust))
        if self.states:
            eligible &= set().union(*(STATE_FAMILIES[state] for state in self.states))
        if not eligible:
            raise ValueError("filters select no compatible family")
        return self


class LocalSourceProvenance(ClosedModel):
    family: Literal[ContextFamily.LOCAL_SOURCE] = ContextFamily.LOCAL_SOURCE
    source_id: uuid.UUID
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    chunk_index: int
    content_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class GitHubProvenance(ClosedModel):
    family: Literal[ContextFamily.GITHUB] = ContextFamily.GITHUB
    account_id: uuid.UUID
    external_resource_id: Annotated[
        str, StringConstraints(min_length=1, max_length=255)
    ]
    external_item_id: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    revision_id: uuid.UUID
    application_revision: Annotated[int, Field(ge=1)]


class CalendarProvenance(ClosedModel):
    family: Literal[ContextFamily.GOOGLE_CALENDAR] = ContextFamily.GOOGLE_CALENDAR
    account_revision_id: uuid.UUID
    calendar_identity_id: uuid.UUID
    occurrence_key: Annotated[str, StringConstraints(min_length=1, max_length=2200)]
    event_revision_id: uuid.UUID
    application_revision: Annotated[int, Field(ge=1)]
    evidence_sync_run_id: uuid.UUID
    evidence_version: Literal["calendar-observations-v1"] = "calendar-observations-v1"


ContextProvenance = Annotated[
    LocalSourceProvenance | GitHubProvenance | CalendarProvenance,
    Field(discriminator="family"),
]


class LocalSourcePosition(ClosedModel):
    family: Literal[ContextFamily.LOCAL_SOURCE] = ContextFamily.LOCAL_SOURCE
    source_created_at: datetime
    source_id: uuid.UUID
    chunk_index: int
    chunk_id: uuid.UUID


class GitHubPosition(ClosedModel):
    family: Literal[ContextFamily.GITHUB] = ContextFamily.GITHUB
    application_revision: int
    revision_id: uuid.UUID


class CalendarPosition(ClosedModel):
    family: Literal[ContextFamily.GOOGLE_CALENDAR] = ContextFamily.GOOGLE_CALENDAR
    application_revision: int
    revision_id: uuid.UUID


ContextPosition = Annotated[
    LocalSourcePosition | GitHubPosition | CalendarPosition,
    Field(discriminator="family"),
]


class ContextItem(ClosedModel):
    contract_version: Literal["context-hub-v1"] = CONTRACT_VERSION
    family: ContextFamily
    kind: ContextKind
    scope: ContextScope
    trust: TrustLabel
    state: ContextState
    title: Annotated[str, StringConstraints(max_length=MAX_TITLE_CHARACTERS)]
    text: Annotated[str, StringConstraints(max_length=MAX_TEXT_CHARACTERS)]
    provenance: ContextProvenance
    position: ContextPosition


class ContextFamilyResult(ClosedModel):
    family: ContextFamily
    items: tuple[ContextItem, ...]
    exhausted: bool


class ContextHubResult(ClosedModel):
    contract_version: Literal["context-hub-v1"] = CONTRACT_VERSION
    groups: tuple[ContextFamilyResult, ...]
