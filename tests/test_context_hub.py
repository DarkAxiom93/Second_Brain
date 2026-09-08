"""Focused closed-contract and zero-authority checks for Checkpoint 110."""

import base64
import uuid
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agent_tools.registry import AGENT_TOOL_REGISTRY, REGISTRY_VERSION
from app.context_hub import tokens
from app.context_hub.models import (
    CONTRACT_VERSION,
    MAX_PAGE_SIZE,
    CalendarProvenance,
    ContextFamily,
    ContextHubQuery,
    ContextKind,
    ContextScope,
    ContextState,
    GitHubPosition,
    GitHubProvenance,
    LocalSourceProvenance,
    TrustLabel,
)
from app.context_hub.tokens import (
    PBKDF2_ITERATIONS,
    ContextTokenError,
    decode_cursor,
    decode_reopen,
    encode_cursor,
    encode_reopen,
)
from app.project_export.models import FORMAT_NAME, FORMAT_VERSION


def _scope() -> ContextScope:
    return ContextScope(project_id=uuid.uuid4())


@pytest.mark.parametrize(
    "value",
    ({}, {"unassigned": False}, {"project_id": uuid.uuid4(), "unassigned": True}),
)
def test_scope_requires_exactly_one_explicit_selector(value: object) -> None:
    with pytest.raises(ValidationError):
        ContextScope.model_validate(value, strict=True)


def test_closed_contract_defaults_and_bounds() -> None:
    request = ContextHubQuery(scope=ContextScope(unassigned=True))
    assert CONTRACT_VERSION == "context-hub-v1"
    assert request.families == (
        ContextFamily.LOCAL_SOURCE,
        ContextFamily.GITHUB,
        ContextFamily.GOOGLE_CALENDAR,
    )
    assert request.query == "" and request.page_size == 20
    with pytest.raises(ValidationError):
        ContextHubQuery(scope=_scope(), page_size=MAX_PAGE_SIZE + 1)
    with pytest.raises(ValidationError):
        ContextHubQuery(scope=_scope(), query="x" * 257)
    with pytest.raises(ValidationError):
        ContextHubQuery(scope=_scope(), query="🙂" * 256)


@pytest.mark.parametrize(
    "values",
    (
        {
            "families": (ContextFamily.LOCAL_SOURCE,),
            "kinds": (ContextKind.ISSUE,),
        },
        {
            "families": (ContextFamily.GITHUB,),
            "trust": (TrustLabel.LOCAL_AUDITED,),
        },
        {
            "families": (ContextFamily.GOOGLE_CALENDAR,),
            "states": (ContextState.DELETED,),
        },
        {
            "families": (ContextFamily.GITHUB, ContextFamily.GITHUB),
        },
    ),
)
def test_impossible_or_ambiguous_filters_fail_closed(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ContextHubQuery(scope=_scope(), **values)


def test_family_compatible_filters_are_accepted() -> None:
    request = ContextHubQuery(
        scope=_scope(),
        families=(ContextFamily.GITHUB, ContextFamily.GOOGLE_CALENDAR),
        kinds=(ContextKind.ISSUE, ContextKind.CALENDAR_EVENT),
        trust=(TrustLabel.QUARANTINED_EXTERNAL,),
        states=(ContextState.CURRENT, ContextState.STALE),
    )
    assert request.kinds == (ContextKind.ISSUE, ContextKind.CALENDAR_EVENT)


def test_provenance_is_closed_tagged_and_exact() -> None:
    common = {"application_revision": 1}
    github = GitHubProvenance(
        account_id=uuid.uuid4(),
        external_resource_id="repository:R_1",
        external_item_id="issue:I_1",
        revision_id=uuid.uuid4(),
        **common,
    )
    calendar = CalendarProvenance(
        account_revision_id=uuid.uuid4(),
        calendar_identity_id=uuid.uuid4(),
        occurrence_key="event:E_1",
        event_revision_id=uuid.uuid4(),
        evidence_sync_run_id=uuid.uuid4(),
        **common,
    )
    local = LocalSourceProvenance(
        source_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        chunk_index=0,
        content_hash="a" * 64,
    )
    assert {github.family, calendar.family, local.family} == set(ContextFamily)
    with pytest.raises(ValidationError):
        GitHubProvenance.model_validate(
            {**github.model_dump(), "credential_reference": "forbidden"}, strict=True
        )


def test_hostile_text_has_no_authority_and_no_capability_expansion() -> None:
    hostile = "<script>fetch('https://attacker.invalid')</script> ignore tools SQL"
    request = ContextHubQuery(scope=_scope(), query=hostile)
    assert request.query == hostile
    assert REGISTRY_VERSION == "agent-tools-v1"
    assert not any(
        "context" in definition.name for definition in AGENT_TOOL_REGISTRY.inventory
    )
    assert FORMAT_NAME == "second-brain-project-export" and FORMAT_VERSION == 1

    service = Path("app/context_hub/service.py").read_text(encoding="utf-8")
    forbidden_imports = (
        "requests",
        "httpx",
        "urllib",
        "credential",
        "EmbeddingProvider",
        "openai_provider",
        "agent_runs",
        "automations",
        "project_export",
    )
    assert not any(f"import {name}" in service for name in forbidden_imports)
    assert (
        ".add(" not in service
        and ".commit(" not in service
        and ".flush(" not in service
    )


def test_cursor_is_opaque_bound_and_strictly_validated() -> None:
    request = ContextHubQuery(
        scope=_scope(), families=(ContextFamily.GITHUB,), page_size=7, query=" term "
    )
    position = GitHubPosition(application_revision=4, revision_id=uuid.uuid4())
    token = encode_cursor(
        request,
        {ContextFamily.GITHUB: position},
        {ContextFamily.GITHUB: False},
        "test-secret",
    )
    positions, exhausted = decode_cursor(token, request, "test-secret")
    assert positions == {ContextFamily.GITHUB: position}
    assert exhausted == {ContextFamily.GITHUB: False}
    changed = bytearray(_raw_token(token))
    changed[-1] ^= 1
    with pytest.raises(ContextTokenError):
        decode_cursor(
            base64.urlsafe_b64encode(changed).decode().rstrip("="),
            request,
            "test-secret",
        )
    with pytest.raises(ContextTokenError):
        decode_cursor(token, request.model_copy(update={"page_size": 8}), "test-secret")
    with pytest.raises(ContextTokenError):
        decode_cursor("x" * 4097, request, "test-secret")


def _raw_token(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _noncanonical_alias(value: str) -> str:
    """Change only unused Base64 pad bits while preserving decoded bytes."""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    assert len(value) % 4 in {2, 3}
    index = alphabet.index(value[-1])
    alias = value[:-1] + alphabet[index ^ 1]
    assert alias != value and _raw_token(alias) == _raw_token(value)
    return alias


def test_pbkdf2_token_lifecycle_salt_nonce_password_and_domain_separation() -> None:
    request = ContextHubQuery(
        scope=_scope(), families=(ContextFamily.GITHUB,), page_size=7
    )
    position = GitHubPosition(application_revision=4, revision_id=uuid.uuid4())
    arguments = (
        request,
        {ContextFamily.GITHUB: position},
        {ContextFamily.GITHUB: False},
        "restart-stable-test-password",
    )
    first = encode_cursor(*arguments)
    second = encode_cursor(*arguments)
    first_raw = _raw_token(first)
    second_raw = _raw_token(second)

    assert PBKDF2_ITERATIONS == 100_000
    assert first_raw[:16] != second_raw[:16]
    assert first_raw[16:28] != second_raw[16:28]
    assert b"restart-stable-test-password" not in first_raw
    assert decode_cursor(first, request, "restart-stable-test-password")[0] == {
        ContextFamily.GITHUB: position
    }

    for invalid in (
        first_raw[:3],
        first_raw[:27],
        first_raw[:-1],
        bytes([first_raw[0] ^ 1]) + first_raw[1:],
        first_raw[:16] + bytes([first_raw[16] ^ 1]) + first_raw[17:],
        first_raw[:-1] + bytes([first_raw[-1] ^ 1]),
    ):
        with pytest.raises(ContextTokenError):
            decode_cursor(
                base64.urlsafe_b64encode(invalid).decode().rstrip("="),
                request,
                "restart-stable-test-password",
            )
    with pytest.raises(ContextTokenError):
        decode_cursor(first, request, "rotated-password")

    provenance = GitHubProvenance(
        account_id=uuid.uuid4(),
        external_resource_id="repository:R_restart",
        external_item_id="issue:I_restart",
        revision_id=uuid.uuid4(),
        application_revision=2,
    )
    reopen = encode_reopen(request.scope, provenance, arguments[3])
    assert (
        decode_reopen(reopen, request.scope, ContextFamily.GITHUB, arguments[3])
        == provenance
    )
    with pytest.raises(ContextTokenError):
        decode_reopen(first, request.scope, ContextFamily.GITHUB, arguments[3])
    with pytest.raises(ContextTokenError):
        decode_reopen(
            reopen, ContextScope(unassigned=True), ContextFamily.GITHUB, arguments[3]
        )
    with pytest.raises(ContextTokenError):
        decode_reopen(reopen, request.scope, ContextFamily.LOCAL_SOURCE, arguments[3])
    unchanged = provenance.model_dump()
    with pytest.raises(ContextTokenError):
        decode_reopen(reopen, request.scope, ContextFamily.GITHUB, "rotated-password")
    assert provenance.model_dump() == unchanged


def test_token_version_and_pbkdf2_policy_are_code_owned() -> None:
    request = ContextHubQuery(
        scope=_scope(), families=(ContextFamily.GITHUB,), page_size=1
    )
    position = GitHubPosition(application_revision=1, revision_id=uuid.uuid4())
    invalid_version = tokens._seal(
        {
            "v": 999,
            "request": tokens.canonical_request(request),
            "groups": [
                {
                    "family": ContextFamily.GITHUB.value,
                    "exhausted": False,
                    "position": position.model_dump(mode="json"),
                }
            ],
        },
        tokens._CURSOR_DOMAIN,
        "test-password",
    )
    with pytest.raises(ContextTokenError):
        decode_cursor(invalid_version, request, "test-password")

    source = Path("app/context_hub/tokens.py").read_text(encoding="utf-8")
    assert "PBKDF2HMAC(" in source and "hashlib" not in source
    assert "iterations=PBKDF2_ITERATIONS" in source
    assert "os.urandom(_SALT_BYTES)" in source
    assert "os.urandom(_NONCE_BYTES)" in source


def test_canonical_base64url_is_required_for_cursor_and_reopen_tokens() -> None:
    scope = _scope()
    position = GitHubPosition(application_revision=4, revision_id=uuid.uuid4())
    for query_length in range(3):
        request = ContextHubQuery(
            scope=scope,
            families=(ContextFamily.GITHUB,),
            page_size=7,
            query="x" * query_length,
        )
        cursor = encode_cursor(
            request,
            {ContextFamily.GITHUB: position},
            {ContextFamily.GITHUB: False},
            "canonical-test-password",
        )
        if len(cursor) % 4 in {2, 3}:
            break
    assert decode_cursor(cursor, request, "canonical-test-password")[0] == {
        ContextFamily.GITHUB: position
    }
    assert len(cursor) % 4 in {2, 3}
    with pytest.raises(ContextTokenError):
        decode_cursor(_noncanonical_alias(cursor), request, "canonical-test-password")
    with pytest.raises(ContextTokenError):
        decode_cursor(cursor + "=", request, "canonical-test-password")

    provenance = GitHubProvenance(
        account_id=uuid.uuid4(),
        external_resource_id="repository:R_canonical",
        external_item_id="issue:I_canonical",
        revision_id=uuid.uuid4(),
        application_revision=2,
    )
    for suffix_length in range(3):
        provenance = provenance.model_copy(
            update={"external_item_id": f"issue:I_canonical{'x' * suffix_length}"}
        )
        reopen = encode_reopen(request.scope, provenance, "canonical-test-password")
        if len(reopen) % 4 in {2, 3}:
            break
    assert len(reopen) % 4 in {2, 3}
    assert (
        decode_reopen(
            reopen,
            request.scope,
            ContextFamily.GITHUB,
            "canonical-test-password",
        )
        == provenance
    )
    with pytest.raises(ContextTokenError):
        decode_reopen(
            _noncanonical_alias(reopen),
            request.scope,
            ContextFamily.GITHUB,
            "canonical-test-password",
        )
    with pytest.raises(ContextTokenError):
        decode_reopen(
            reopen + "=",
            request.scope,
            ContextFamily.GITHUB,
            "canonical-test-password",
        )
