"""Windows Credential Manager adapter using only Python stdlib ``ctypes``."""

import ctypes
import re
import sys
import threading
import uuid
from contextlib import suppress
from ctypes import wintypes
from typing import Any

from app.credentials.contract import (
    CredentialReference,
    CredentialStoreError,
    CredentialStoreLockedError,
    CredentialStoreMissingError,
    CredentialStoreStatus,
    CredentialStoreUnavailableError,
    clear_secret,
)

_REFERENCE_PREFIX = "sbcred:v1:"
_TARGET_PREFIX = "SecondBrain/connector/v1/"
_REFERENCE_PATTERN = re.compile(
    r"\Asbcred:v1:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z"
)
_CRED_TYPE_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2
_ERROR_NOT_FOUND = 1168
_LOCKED_ERRORS = {5, 1312}
_MAX_SECRET_BYTES = 2560
_locks_guard = threading.Lock()
_reference_locks: dict[str, threading.Lock] = {}


class _CredentialAttribute(ctypes.Structure):
    _fields_ = [
        ("Keyword", wintypes.LPWSTR),
        ("Flags", wintypes.DWORD),
        ("ValueSize", wintypes.DWORD),
        ("Value", ctypes.POINTER(ctypes.c_ubyte)),
    ]


class _Credential(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.POINTER(_CredentialAttribute)),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


def _lock_for(reference: CredentialReference) -> threading.Lock:
    with _locks_guard:
        return _reference_locks.setdefault(str(reference), threading.Lock())


def _target(reference: CredentialReference) -> str:
    raw = str(reference)
    if _REFERENCE_PATTERN.fullmatch(raw) is None:
        raise CredentialStoreError() from None
    return f"{_TARGET_PREFIX}{raw.removeprefix(_REFERENCE_PREFIX)}"


class WindowsCredentialStore:
    """Non-enumerating exact-target adapter for the current Windows user."""

    def __init__(self) -> None:
        self._advapi32: Any | None = None
        if sys.platform != "win32":
            return
        try:
            library = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
            library.CredWriteW.argtypes = [ctypes.POINTER(_Credential), wintypes.DWORD]
            library.CredWriteW.restype = wintypes.BOOL
            library.CredReadW.argtypes = [
                wintypes.LPCWSTR,
                wintypes.DWORD,
                wintypes.DWORD,
                ctypes.POINTER(ctypes.POINTER(_Credential)),
            ]
            library.CredReadW.restype = wintypes.BOOL
            library.CredDeleteW.argtypes = [
                wintypes.LPCWSTR,
                wintypes.DWORD,
                wintypes.DWORD,
            ]
            library.CredDeleteW.restype = wintypes.BOOL
            library.CredFree.argtypes = [ctypes.c_void_p]
            library.CredFree.restype = None
            self._advapi32 = library
        except (AttributeError, OSError):
            self._advapi32 = None

    def _library(self) -> Any:
        if self._advapi32 is None:
            raise CredentialStoreUnavailableError() from None
        return self._advapi32

    @staticmethod
    def _raise_platform_error(error: int) -> None:
        if error == _ERROR_NOT_FOUND:
            raise CredentialStoreMissingError() from None
        if error in _LOCKED_ERRORS:
            raise CredentialStoreLockedError() from None
        raise CredentialStoreUnavailableError() from None

    def _read_unlocked(self, reference: CredentialReference) -> bytearray:
        library = self._library()
        pointer = ctypes.POINTER(_Credential)()
        if not library.CredReadW(
            _target(reference), _CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)
        ):
            self._raise_platform_error(ctypes.get_last_error())
        try:
            credential = pointer.contents
            return bytearray(
                ctypes.string_at(
                    credential.CredentialBlob, credential.CredentialBlobSize
                )
            )
        finally:
            library.CredFree(pointer)

    def _write_unlocked(
        self, reference: CredentialReference, secret: bytearray
    ) -> None:
        library = self._library()
        if not secret or len(secret) > _MAX_SECRET_BYTES:
            raise CredentialStoreError() from None
        blob = (ctypes.c_ubyte * len(secret)).from_buffer(secret)
        credential = _Credential()
        credential.Type = _CRED_TYPE_GENERIC
        credential.TargetName = _target(reference)
        credential.CredentialBlobSize = len(secret)
        credential.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
        credential.Persist = _CRED_PERSIST_LOCAL_MACHINE
        credential.UserName = "Second Brain connector credential"
        if not library.CredWriteW(ctypes.byref(credential), 0):
            self._raise_platform_error(ctypes.get_last_error())

    def install(self, secret: bytearray) -> CredentialReference:
        self._library()
        for _ in range(3):
            reference = CredentialReference(f"{_REFERENCE_PREFIX}{uuid.uuid4()}")
            with _lock_for(reference):
                try:
                    existing = self._read_unlocked(reference)
                except CredentialStoreMissingError:
                    self._write_unlocked(reference, secret)
                    return reference
                else:
                    clear_secret(existing)
        raise CredentialStoreUnavailableError() from None

    def read(self, reference: CredentialReference) -> bytearray:
        with _lock_for(reference):
            return self._read_unlocked(reference)

    def replace(self, reference: CredentialReference, secret: bytearray) -> None:
        with _lock_for(reference):
            existing = self._read_unlocked(reference)
            try:
                self._write_unlocked(reference, secret)
            finally:
                clear_secret(existing)

    def revoke(self, reference: CredentialReference) -> None:
        library = self._library()
        with _lock_for(reference):
            if not library.CredDeleteW(_target(reference), _CRED_TYPE_GENERIC, 0):
                self._raise_platform_error(ctypes.get_last_error())

    def status(self) -> CredentialStoreStatus:
        if self._advapi32 is None:
            return CredentialStoreStatus(False, "credential_store_unavailable")
        probe = bytearray(b"second-brain-credential-store-capability-probe")
        reference: CredentialReference | None = None
        try:
            reference = self.install(probe)
            recovered = self.read(reference)
            clear_secret(recovered)
            self.revoke(reference)
        except CredentialStoreError as exc:
            if reference is not None:
                with suppress(CredentialStoreError):
                    self.revoke(reference)
            return CredentialStoreStatus(False, exc.code)
        finally:
            clear_secret(probe)
        return CredentialStoreStatus(True, "available")
