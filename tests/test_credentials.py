"""Checkpoint 88 credential-store contract and secret-boundary tests."""

import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.credentials import (
    CredentialReference,
    CredentialStoreError,
    CredentialStoreLockedError,
    CredentialStoreMissingError,
    CredentialStoreUnavailableError,
    clear_secret,
)
from app.credentials.fake import FakeCredentialStore
from app.credentials.windows import WindowsCredentialStore

_REFERENCE = CredentialReference("sbcred:v1:12345678-1234-4123-8123-123456789abc")
_FAKE_SECRET = bytearray(b"cp88-obviously-fake-test-secret")


def _references() -> Iterator[CredentialReference]:
    yield _REFERENCE
    yield CredentialReference("sbcred:v1:22345678-1234-4123-8123-123456789abc")


def test_fake_store_exact_replace_revoke_and_instance_isolation() -> None:
    references = _references()
    first = FakeCredentialStore(reference_factory=lambda: next(references))
    second = FakeCredentialStore(reference_factory=lambda: next(references))
    reference = first.install(bytearray(_FAKE_SECRET))
    assert reference == _REFERENCE
    assert bytes(first.read(reference)) == bytes(_FAKE_SECRET)
    with pytest.raises(CredentialStoreMissingError, match=r"^credential_missing$"):
        second.read(reference)

    replacement = bytearray(b"cp88-obviously-fake-replacement")
    first.replace(reference, replacement)
    assert bytes(first.read(reference)) == bytes(replacement)
    assert reference == _REFERENCE
    first.revoke(reference)
    with pytest.raises(CredentialStoreMissingError, match=r"^credential_missing$"):
        first.read(reference)


@pytest.mark.parametrize(
    ("failure_type", "code"),
    [
        (CredentialStoreMissingError, "credential_missing"),
        (CredentialStoreLockedError, "credential_store_locked"),
        (CredentialStoreUnavailableError, "credential_store_unavailable"),
    ],
)
def test_fake_store_injected_failures_are_safe(
    failure_type: type[CredentialStoreError], code: str
) -> None:
    store = FakeCredentialStore(
        reference_factory=lambda: _REFERENCE, failure=failure_type()
    )
    status = store.status()
    assert status.available is False
    assert status.code == code
    with pytest.raises(failure_type, match=f"^{code}$") as raised:
        store.install(bytearray(_FAKE_SECRET))
    assert bytes(_FAKE_SECRET).decode() not in repr(raised.value)


def test_secret_buffer_can_be_cleared_and_reference_is_opaque() -> None:
    secret = bytearray(_FAKE_SECRET)
    clear_secret(secret)
    assert secret == bytearray(len(secret))
    assert re.fullmatch(
        r"sbcred:v1:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        str(_REFERENCE),
    )
    assert bytes(_FAKE_SECRET).decode() not in str(_REFERENCE)


def test_windows_adapter_real_round_trip_or_explicit_unsupported() -> None:
    store = WindowsCredentialStore()
    if sys.platform != "win32":
        assert store.status().available is False
        with pytest.raises(CredentialStoreUnavailableError):
            store.install(bytearray(_FAKE_SECRET))
        return

    assert store.status().available is True
    reference: CredentialReference | None = None
    created = False
    try:
        reference = store.install(bytearray(_FAKE_SECRET))
        created = True
        assert bytes(store.read(reference)) == bytes(_FAKE_SECRET)
        replacement = bytearray(b"cp88-obviously-fake-windows-replacement")
        store.replace(reference, replacement)
        assert bytes(store.read(reference)) == bytes(replacement)
        store.revoke(reference)
        created = False
        with pytest.raises(CredentialStoreMissingError):
            store.read(reference)
    finally:
        if created and reference is not None:
            store.revoke(reference)


def test_invalid_reference_never_targets_the_os_store() -> None:
    store = WindowsCredentialStore()
    if sys.platform == "win32":
        with pytest.raises(CredentialStoreError, match=r"^credential_store_error$"):
            store.read(CredentialReference("not-an-application-reference"))


def test_export_identity_has_no_credential_field() -> None:
    from app.project_export.models import FORMAT_NAME, FORMAT_VERSION, ExportManifest

    schema = json.dumps(ExportManifest.model_json_schema(), sort_keys=True).lower()
    assert FORMAT_NAME == "second-brain-project-export"
    assert FORMAT_VERSION == 1
    assert "credential" not in schema
    assert "secret" not in schema


def test_credential_boundary_has_no_persistence_network_or_enumeration() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(Path("app/credentials").glob("*.py"))
    ).lower()
    for forbidden in (
        "credenumerate",
        "sqlalchemy",
        "app.models",
        "app.project_export",
        "httpx",
        "requests",
        "urllib",
    ):
        assert forbidden not in source
