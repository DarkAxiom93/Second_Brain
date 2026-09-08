"""Opaque authenticated Context Hub cursor and reopen identities."""

from __future__ import annotations

import base64
import json
import os
from typing import Any, Final

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pydantic import TypeAdapter, ValidationError

from app.context_hub.models import (
    CONTRACT_VERSION,
    MAX_CURSOR_CHARACTERS,
    MAX_REOPEN_ID_CHARACTERS,
    ORDERING_MODE,
    ContextFamily,
    ContextHubQuery,
    ContextPosition,
    ContextProvenance,
    ContextScope,
)

_CURSOR_DOMAIN: Final = b"second-brain:context-hub:cursor:v1"
_REOPEN_DOMAIN: Final = b"second-brain:context-hub:reopen:v1"
_TOKEN_VERSION: Final = 1
_KDF_NAME: Final = "pbkdf2-hmac-sha256"
PBKDF2_ITERATIONS: Final = 100_000
_KEY_BYTES: Final = 32
_SALT_BYTES: Final = 16
_NONCE_BYTES: Final = 12
_POSITION_ADAPTER: TypeAdapter[ContextPosition] = TypeAdapter(ContextPosition)
_PROVENANCE_ADAPTER: TypeAdapter[ContextProvenance] = TypeAdapter(ContextProvenance)


class ContextTokenError(Exception):
    """An opaque public token was invalid or did not match its request."""


def _key(secret: str, domain: bytes, salt: bytes) -> bytes:
    return PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=_KEY_BYTES,
        salt=domain + b":" + salt,
        iterations=PBKDF2_ITERATIONS,
    ).derive(secret.encode())


def _metadata(domain: bytes) -> dict[str, Any]:
    return {
        "token_version": _TOKEN_VERSION,
        "domain": domain.decode(),
        "kdf": _KDF_NAME,
        "iterations": PBKDF2_ITERATIONS,
    }


def _aad(domain: bytes, salt: bytes) -> bytes:
    return json.dumps(
        {**_metadata(domain), "salt": base64.urlsafe_b64encode(salt).decode()},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _seal(value: dict[str, Any], domain: bytes, secret: str) -> str:
    salt = os.urandom(_SALT_BYTES)
    nonce = os.urandom(_NONCE_BYTES)
    payload = json.dumps(
        {**_metadata(domain), "data": value},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    encrypted = AESGCM(_key(secret, domain, salt)).encrypt(
        nonce, payload, _aad(domain, salt)
    )
    return base64.urlsafe_b64encode(salt + nonce + encrypted).decode().rstrip("=")


def _open(value: str, domain: bytes, maximum: int, secret: str) -> dict[str, Any]:
    if not value or len(value) > maximum:
        raise ContextTokenError
    try:
        raw = base64.b64decode(
            value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
        )
        canonical = base64.urlsafe_b64encode(raw).decode().rstrip("=")
        if canonical != value:
            raise ContextTokenError
        if len(raw) <= _SALT_BYTES + _NONCE_BYTES + 16:
            raise ContextTokenError
        salt = raw[:_SALT_BYTES]
        nonce = raw[_SALT_BYTES : _SALT_BYTES + _NONCE_BYTES]
        ciphertext = raw[_SALT_BYTES + _NONCE_BYTES :]
        payload = AESGCM(_key(secret, domain, salt)).decrypt(
            nonce, ciphertext, _aad(domain, salt)
        )
        decoded = json.loads(payload)
        if (
            not isinstance(decoded, dict)
            or set(decoded)
            != {
                "token_version",
                "domain",
                "kdf",
                "iterations",
                "data",
            }
            or {key: decoded[key] for key in _metadata(domain)} != _metadata(domain)
            or not isinstance(decoded["data"], dict)
        ):
            raise ContextTokenError
        return decoded["data"]
    except (ValueError, UnicodeError, json.JSONDecodeError, InvalidTag):
        raise ContextTokenError from None


def canonical_request(request: ContextHubQuery) -> dict[str, Any]:
    return {
        "contract": CONTRACT_VERSION,
        "scope": request.scope.model_dump(mode="json"),
        "query": request.query,
        "families": sorted(value.value for value in request.families),
        "kinds": sorted(value.value for value in request.kinds),
        "trust": sorted(value.value for value in request.trust),
        "states": sorted(value.value for value in request.states),
        "page_size": request.page_size,
        "ordering": ORDERING_MODE,
    }


def encode_cursor(
    request: ContextHubQuery,
    positions: dict[ContextFamily, ContextPosition | None],
    exhausted: dict[ContextFamily, bool],
    secret: str,
) -> str:
    def dumped(family: ContextFamily) -> dict[str, Any] | None:
        position = positions[family]
        return position.model_dump(mode="json") if position is not None else None

    groups = [
        {
            "family": family.value,
            "exhausted": exhausted[family],
            "position": dumped(family),
        }
        for family in request.families
    ]
    return _seal(
        {"v": 1, "request": canonical_request(request), "groups": groups},
        _CURSOR_DOMAIN,
        secret,
    )


def decode_cursor(
    value: str, request: ContextHubQuery, secret: str
) -> tuple[dict[ContextFamily, ContextPosition | None], dict[ContextFamily, bool]]:
    data = _open(value, _CURSOR_DOMAIN, MAX_CURSOR_CHARACTERS, secret)
    if set(data) != {"v", "request", "groups"} or data["v"] != 1:
        raise ContextTokenError
    if data["request"] != canonical_request(request) or not isinstance(
        data["groups"], list
    ):
        raise ContextTokenError
    positions: dict[ContextFamily, ContextPosition | None] = {}
    exhausted: dict[ContextFamily, bool] = {}
    if len(data["groups"]) != len(request.families):
        raise ContextTokenError
    try:
        for raw in data["groups"]:
            if not isinstance(raw, dict) or set(raw) != {
                "family",
                "exhausted",
                "position",
            }:
                raise ContextTokenError
            family = ContextFamily(raw["family"])
            if (
                family not in request.families
                or family in positions
                or type(raw["exhausted"]) is not bool
            ):
                raise ContextTokenError
            position = (
                None
                if raw["position"] is None
                else _POSITION_ADAPTER.validate_python(raw["position"])
            )
            if position is not None and position.family != family:
                raise ContextTokenError
            if raw["exhausted"] and position is None:
                positions[family] = None
            else:
                positions[family] = position
            exhausted[family] = raw["exhausted"]
    except (ValueError, ValidationError, KeyError, TypeError):
        raise ContextTokenError from None
    if set(positions) != set(request.families):
        raise ContextTokenError
    return positions, exhausted


def encode_reopen(
    scope: ContextScope, provenance: ContextProvenance, secret: str
) -> str:
    return _seal(
        {
            "v": 1,
            "scope": scope.model_dump(mode="json"),
            "provenance": provenance.model_dump(mode="json"),
        },
        _REOPEN_DOMAIN,
        secret,
    )


def decode_reopen(
    value: str, scope: ContextScope, family: ContextFamily, secret: str
) -> ContextProvenance:
    data = _open(value, _REOPEN_DOMAIN, MAX_REOPEN_ID_CHARACTERS, secret)
    if set(data) != {"v", "scope", "provenance"} or data["v"] != 1:
        raise ContextTokenError
    if data["scope"] != scope.model_dump(mode="json"):
        raise ContextTokenError
    try:
        provenance = _PROVENANCE_ADAPTER.validate_python(data["provenance"])
    except ValidationError:
        raise ContextTokenError from None
    if provenance.family != family:
        raise ContextTokenError
    return provenance
