"""Pure fail-closed validation for inert connector persistence values."""

import re
from hashlib import sha256

from app.connectors.catalog import get_connector, supports_resource
from app.credentials.contract import validate_credential_reference

_SHA256 = re.compile(r"\A[0-9a-f]{64}\Z")
_IDENTITY = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9:._-]{0,254}\Z")
_RESOURCE = re.compile(
    r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,99}/[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z"
)
_SAFE_CODE = re.compile(r"\A[a-z][a-z0-9_]{0,99}\Z")
_GITHUB_GRANTED_SCOPES = frozenset(
    {"metadata_read", "issues_read", "pull_requests_read"}
)
_SECRET_MARKERS = (
    "ghp_",
    "github_pat_",
    "bearer ",
    "authorization",
    "password",
    "client_secret",
    "refresh_token",
    "access_token",
    "cookie",
)


def _safe(value: str) -> bool:
    lowered = value.lower()
    return not any(marker in lowered for marker in _SECRET_MARKERS)


def require_safe_identity(value: str) -> str:
    if _IDENTITY.fullmatch(value) is None or not _safe(value):
        raise ValueError("invalid safe connector identity")
    return value


def require_safe_code(value: str) -> str:
    if _SAFE_CODE.fullmatch(value) is None or not _safe(value):
        raise ValueError("invalid safe connector code")
    return value


def validate_account_values(
    *,
    provider: str,
    external_account_id: str,
    external_account_fingerprint: str,
    credential_reference: str,
    resource_allowlist: list[str],
    granted_scope_fingerprint: str,
) -> None:
    if get_connector(provider) is None:
        raise ValueError("unknown connector provider")
    require_safe_identity(external_account_id)
    if _SHA256.fullmatch(external_account_fingerprint) is None:
        raise ValueError("invalid external account fingerprint")
    validate_credential_reference(credential_reference)
    if _SHA256.fullmatch(granted_scope_fingerprint) is None:
        raise ValueError("invalid granted scope fingerprint")
    if not 1 <= len(resource_allowlist) <= 32 or len(set(resource_allowlist)) != len(
        resource_allowlist
    ):
        raise ValueError("invalid resource allowlist")
    if any(
        _RESOURCE.fullmatch(value) is None or not _safe(value)
        for value in resource_allowlist
    ):
        raise ValueError("invalid resource allowlist")


def validate_item_values(
    *,
    provider: str,
    resource_type: str,
    external_resource_id: str,
    external_item_id: str,
    provider_source_version: str,
    title: str,
    body: str,
    content_hash: str,
) -> None:
    if not supports_resource(provider, resource_type):
        raise ValueError("unsupported connector resource")
    require_safe_identity(external_resource_id)
    require_safe_identity(external_item_id)
    if not 1 <= len(provider_source_version) <= 255 or not _safe(
        provider_source_version
    ):
        raise ValueError("invalid provider source version")
    if len(title) > 500 or len(title.encode()) > 2000:
        raise ValueError("external title exceeds limit")
    if len(body) > 20_000 or len(body.encode()) > 80_000:
        raise ValueError("external body exceeds limit")
    if content_hash != snapshot_content_hash(title, body):
        raise ValueError("invalid external content hash")


def snapshot_content_hash(title: str, body: str) -> str:
    """Hash an unambiguous length-prefixed UTF-8 title/body snapshot."""

    title_bytes = title.encode()
    body_bytes = body.encode()
    payload = len(title_bytes).to_bytes(8, "big") + title_bytes + body_bytes
    return sha256(payload).hexdigest()


def granted_scope_fingerprint(scope_names: tuple[str, ...]) -> str:
    """Derive a fingerprint from closed permission names, never credential material."""

    if not scope_names or len(scope_names) > 32:
        raise ValueError("invalid granted scopes")
    normalized = tuple(sorted(set(scope_names)))
    if (
        len(normalized) != len(scope_names)
        or not set(normalized) <= _GITHUB_GRANTED_SCOPES
    ):
        raise ValueError("invalid granted scopes")
    return sha256("\n".join(normalized).encode()).hexdigest()
