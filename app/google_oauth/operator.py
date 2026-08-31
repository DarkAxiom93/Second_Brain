"""Secret-safe local Google authorization operator surface."""

import argparse
import json
from collections.abc import Sequence
from typing import Never

from app.core.config import get_settings
from app.credentials import CredentialStoreError, validate_credential_reference
from app.credentials.windows import WindowsCredentialStore
from app.google_oauth.contract import GoogleOAuthError
from app.google_oauth.service import GoogleOAuthService
from app.google_oauth.transport import GoogleHttpProvider


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        del message
        raise SystemExit("google_oauth_command_invalid")


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="manage-google-calendar-credential")
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("authorize")
    for action in ("status", "reauthorize", "revoke"):
        command = commands.add_parser(action)
        command.add_argument("reference")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        client_id = get_settings().google_oauth_client_id
        if client_id is None:
            print(json.dumps({"error": "google_oauth_not_configured"}))
            return 2
        service = GoogleOAuthService(
            client_id=client_id,
            store=WindowsCredentialStore(),
            provider=GoogleHttpProvider(),
        )
        if args.action == "authorize":
            result = service.authorize()
            output: dict[str, object] = {
                "status": "authorized",
                "credential_reference": str(result.credential_reference),
                "account_fingerprint": result.account_fingerprint,
            }
        else:
            reference = validate_credential_reference(args.reference)
            if args.action == "status":
                output = service.status(reference)
            elif args.action == "reauthorize":
                result = service.reauthorize(reference)
                output = {
                    "status": "reauthorized",
                    "credential_reference": str(result.credential_reference),
                    "account_fingerprint": result.account_fingerprint,
                }
            else:
                revoked = service.revoke(reference)
                output = {
                    "status": "revocation_attempted",
                    "provider_revoked": revoked.provider_revoked,
                    "local_deleted": revoked.local_deleted,
                }
        print(json.dumps(output, sort_keys=True))
        return 0
    except (GoogleOAuthError, CredentialStoreError, ValueError) as exc:
        code = getattr(exc, "code", "google_oauth_command_invalid")
        print(json.dumps({"error": code}))
        return 2
    except Exception:
        print(json.dumps({"error": "google_oauth_failed"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
