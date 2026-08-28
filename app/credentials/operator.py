"""Secret-safe local operator entry point for credential lifecycle actions."""

import argparse
import getpass
import json
from collections.abc import Sequence
from typing import Never

from app.credentials import CredentialReference, CredentialStoreError, clear_secret
from app.credentials.windows import WindowsCredentialStore


class _SafeArgumentParser(argparse.ArgumentParser):
    """Reject malformed commands without echoing supplied argument material."""

    def error(self, message: str) -> Never:
        del message
        raise SystemExit("credential_command_invalid")


def _parser() -> argparse.ArgumentParser:
    parser = _SafeArgumentParser(prog="manage-credential")
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("install")
    replace = subparsers.add_parser("replace")
    replace.add_argument("reference")
    revoke = subparsers.add_parser("revoke")
    revoke.add_argument("reference")
    subparsers.add_parser("status")
    return parser


def _prompt_secret() -> bytearray:
    entered = getpass.getpass("Credential: ")
    try:
        return bytearray(entered.encode("utf-8"))
    finally:
        entered = ""


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    store = WindowsCredentialStore()
    try:
        if args.action == "status":
            status = store.status()
            print(json.dumps({"available": status.available, "status": status.code}))
            return 0 if status.available else 1
        if args.action == "revoke":
            store.revoke(CredentialReference(args.reference))
            print(json.dumps({"status": "revoked"}))
            return 0
        secret = _prompt_secret()
        try:
            if args.action == "install":
                reference = store.install(secret)
                print(
                    json.dumps(
                        {"credential_reference": reference, "status": "installed"}
                    )
                )
            else:
                store.replace(CredentialReference(args.reference), secret)
                print(
                    json.dumps(
                        {"credential_reference": args.reference, "status": "replaced"}
                    )
                )
        finally:
            clear_secret(secret)
        return 0
    except CredentialStoreError as exc:
        print(json.dumps({"error": exc.code}))
        return 2
    except Exception:
        print(json.dumps({"error": "credential_store_unavailable"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
