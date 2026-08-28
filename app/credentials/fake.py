"""Deterministic isolated credential store for tests."""

from collections.abc import Callable

from app.credentials.contract import (
    CredentialReference,
    CredentialStoreError,
    CredentialStoreMissingError,
    CredentialStoreStatus,
    clear_secret,
)


class FakeCredentialStore:
    """Instance-local exact-reference fake that never accesses the OS store."""

    def __init__(
        self,
        *,
        reference_factory: Callable[[], CredentialReference],
        failure: CredentialStoreError | None = None,
    ) -> None:
        self._reference_factory = reference_factory
        self._failure = failure
        self._secrets: dict[CredentialReference, bytearray] = {}

    def _raise_failure(self) -> None:
        if self._failure is not None:
            raise type(self._failure)() from None

    def install(self, secret: bytearray) -> CredentialReference:
        self._raise_failure()
        reference = self._reference_factory()
        if reference in self._secrets:
            raise CredentialStoreError() from None
        self._secrets[reference] = bytearray(secret)
        return reference

    def read(self, reference: CredentialReference) -> bytearray:
        self._raise_failure()
        try:
            return bytearray(self._secrets[reference])
        except KeyError:
            raise CredentialStoreMissingError() from None

    def replace(self, reference: CredentialReference, secret: bytearray) -> None:
        self._raise_failure()
        if reference not in self._secrets:
            raise CredentialStoreMissingError() from None
        old_secret = self._secrets[reference]
        self._secrets[reference] = bytearray(secret)
        clear_secret(old_secret)

    def revoke(self, reference: CredentialReference) -> None:
        self._raise_failure()
        try:
            secret = self._secrets.pop(reference)
        except KeyError:
            raise CredentialStoreMissingError() from None
        clear_secret(secret)

    def status(self) -> CredentialStoreStatus:
        try:
            self._raise_failure()
        except CredentialStoreError as exc:
            return CredentialStoreStatus(available=False, code=exc.code)
        return CredentialStoreStatus(available=True, code="available")
