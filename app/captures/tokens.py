"""Opaque authenticated, request-bound Capture Inbox cursors."""

import base64
import json
import os
import uuid
from datetime import datetime
from typing import Any, Final

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.schemas.capture import CaptureQueryRequest

_DOMAIN: Final = b"second-brain:capture-inbox:cursor:v1"
_SALT_BYTES: Final = 16
_NONCE_BYTES: Final = 12
_ITERATIONS: Final = 100_000


class CaptureCursorError(Exception):
    pass


def _request(request: CaptureQueryRequest) -> dict[str, Any]:
    return {
        "scope": request.scope.model_dump(mode="json", exclude_none=True),
        "query": request.query,
        "states": sorted(request.states),
        "page_size": request.page_size,
        "ordering": "lexical-rank-created-id-v1" if request.query else "created-id-v1",
    }


def _key(secret: str, salt: bytes) -> bytes:
    return PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_DOMAIN + b":" + salt,
        iterations=_ITERATIONS,
    ).derive(secret.encode())


def _aad(salt: bytes) -> bytes:
    return json.dumps(
        {
            "domain": _DOMAIN.decode(),
            "iterations": _ITERATIONS,
            "salt": base64.urlsafe_b64encode(salt).decode(),
            "v": 1,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def encode_cursor(
    request: CaptureQueryRequest,
    created_at: datetime,
    item_id: str,
    rank: float | None,
    secret: str,
) -> str:
    salt, nonce = os.urandom(_SALT_BYTES), os.urandom(_NONCE_BYTES)
    payload = json.dumps(
        {
            "v": 1,
            "request": _request(request),
            "position": {
                "created_at": created_at.isoformat(),
                "id": item_id,
                "rank": rank,
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    sealed = AESGCM(_key(secret, salt)).encrypt(nonce, payload, _aad(salt))
    return base64.urlsafe_b64encode(salt + nonce + sealed).decode().rstrip("=")


def decode_cursor(
    value: str, request: CaptureQueryRequest, secret: str
) -> tuple[datetime, str, float | None]:
    if not value or len(value) > 2048:
        raise CaptureCursorError
    try:
        raw = base64.b64decode(
            value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
        )
        if (
            base64.urlsafe_b64encode(raw).decode().rstrip("=") != value
            or len(raw) <= 44
        ):
            raise CaptureCursorError
        salt, nonce, ciphertext = raw[:16], raw[16:28], raw[28:]
        data = json.loads(
            AESGCM(_key(secret, salt)).decrypt(nonce, ciphertext, _aad(salt))
        )
        if (
            set(data) != {"v", "request", "position"}
            or data["v"] != 1
            or data["request"] != _request(request)
        ):
            raise CaptureCursorError
        position = data["position"]
        if not isinstance(position, dict) or set(position) != {
            "created_at",
            "id",
            "rank",
        }:
            raise CaptureCursorError
        created_at = datetime.fromisoformat(position["created_at"])
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise CaptureCursorError
        item_id = str(position["id"])
        uuid.UUID(item_id)
        rank = position["rank"]
        if request.query is None and rank is not None:
            raise CaptureCursorError
        if request.query is not None and type(rank) not in {int, float}:
            raise CaptureCursorError
        return created_at, item_id, None if rank is None else float(rank)
    except (
        ValueError,
        TypeError,
        KeyError,
        UnicodeError,
        json.JSONDecodeError,
        InvalidTag,
    ):
        raise CaptureCursorError from None
