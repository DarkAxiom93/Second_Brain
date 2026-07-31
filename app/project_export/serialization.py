"""Canonical JSON primitives for the export format."""

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any
from uuid import UUID


def validate_archive_path(name: str) -> str:
    """Return a safe POSIX archive path or reject it."""

    path = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or path.is_absolute()
        or ".." in path.parts
        or str(path) != name
    ):
        raise ValueError("unsafe archive path")
    return name


def _canonical(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return _canonical(value.tolist())
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return (
            value.astimezone(UTC)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite floating-point value")
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


def canonical_json(value: Any) -> bytes:
    """Serialize one value as deterministic UTF-8 JSON with an LF."""

    return (
        json.dumps(
            _canonical(value),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def sha256_bytes(value: bytes) -> str:
    """Return the lowercase SHA-256 digest."""

    return hashlib.sha256(value).hexdigest()
