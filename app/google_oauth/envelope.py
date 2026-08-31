"""Minimal versioned Google credential envelope serialization."""

import json
from dataclasses import dataclass

from app.google_oauth.contract import GoogleOAuthError

MAX_ENVELOPE_BYTES = 8192


@dataclass(frozen=True, slots=True)
class GoogleCredentialEnvelope:
    refresh_token: str
    account_fingerprint: str
    generation: int = 1
    version: int = 1

    def encode(self) -> bytearray:
        if not self.refresh_token or len(self.refresh_token) > 4096:
            raise GoogleOAuthError() from None
        payload = json.dumps(
            {
                "version": self.version,
                "generation": self.generation,
                "refresh_token": self.refresh_token,
                "account_fingerprint": self.account_fingerprint,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        if len(payload) > MAX_ENVELOPE_BYTES:
            raise GoogleOAuthError() from None
        return bytearray(payload)

    @classmethod
    def decode(cls, value: bytearray) -> "GoogleCredentialEnvelope":
        try:
            if not value or len(value) > MAX_ENVELOPE_BYTES:
                raise ValueError
            raw = json.loads(bytes(value))
            if set(raw) != {
                "version",
                "generation",
                "refresh_token",
                "account_fingerprint",
            }:
                raise ValueError
            envelope = cls(**raw)
            if (
                envelope.version != 1
                or envelope.generation < 1
                or len(envelope.account_fingerprint) != 64
                or any(
                    c not in "0123456789abcdef" for c in envelope.account_fingerprint
                )
            ):
                raise ValueError
            envelope.encode()
            return envelope
        except (TypeError, ValueError, UnicodeError, json.JSONDecodeError):
            raise GoogleOAuthError() from None
