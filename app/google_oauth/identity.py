"""Google ID-token verification and minimized account identity."""

import hashlib
import time
from collections.abc import Callable

import jwt

from app.google_oauth.contract import GoogleOAuthIdentityError

ISSUERS = frozenset({"https://accounts.google.com", "accounts.google.com"})
MAX_SUB_LENGTH = 255


def account_fingerprint(sub: str) -> str:
    if not sub or len(sub) > MAX_SUB_LENGTH:
        raise GoogleOAuthIdentityError() from None
    return hashlib.sha256(f"second-brain:google-account:v1:{sub}".encode()).hexdigest()


def validate_id_token(
    token: str,
    *,
    client_id: str,
    nonce: str,
    jwks: dict[str, object],
    now: Callable[[], float] = time.time,
) -> str:
    """Validate the signed token and return only the derived fingerprint."""

    try:
        key_set = jwt.PyJWKSet.from_dict(jwks)
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
            raise ValueError
        matches = [key for key in key_set.keys if key.key_id == header["kid"]]
        if len(matches) != 1:
            raise ValueError
        claims = jwt.decode(
            token,
            matches[0].key,
            algorithms=["RS256"],
            audience=client_id,
            options={
                "require": ["iss", "aud", "exp", "iat", "nonce", "sub"],
                "verify_exp": False,
                "verify_iat": False,
            },
            leeway=30,
        )
        current = int(now())
        issued_at = claims["iat"]
        expires_at = claims["exp"]
        if (
            claims["iss"] not in ISSUERS
            or claims["nonce"] != nonce
            or type(issued_at) is not int
            or type(expires_at) is not int
            or issued_at > current + 30
            or current - issued_at > 3600
            or expires_at < current - 30
            or not isinstance(claims["sub"], str)
        ):
            raise ValueError
        return account_fingerprint(claims["sub"])
    except Exception:
        raise GoogleOAuthIdentityError() from None
