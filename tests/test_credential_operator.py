"""Secret-redaction and exact-action tests for the credential operator CLI."""

from pathlib import Path

from app.credentials import (
    CredentialReference,
    CredentialStoreUnavailableError,
    operator,
)
from app.credentials.fake import FakeCredentialStore

_REFERENCE = CredentialReference("sbcred:v1:12345678-1234-4123-8123-123456789abc")
_CANARY = "cp88-command-output-must-never-contain-this"


def _store() -> FakeCredentialStore:
    return FakeCredentialStore(reference_factory=lambda: _REFERENCE)


def test_operator_install_replace_revoke_never_prints_secret(
    monkeypatch, capsys
) -> None:
    store = _store()
    monkeypatch.setattr(operator, "WindowsCredentialStore", lambda: store)
    monkeypatch.setattr(operator.getpass, "getpass", lambda _prompt: _CANARY)
    assert operator.main(["install"]) == 0
    output = capsys.readouterr().out
    assert _CANARY not in output
    assert str(_REFERENCE) in output
    assert operator.main(["replace", str(_REFERENCE)]) == 0
    assert _CANARY not in capsys.readouterr().out
    assert operator.main(["revoke", str(_REFERENCE)]) == 0
    assert _CANARY not in capsys.readouterr().out


def test_operator_errors_and_status_are_content_free(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        operator,
        "WindowsCredentialStore",
        lambda: FakeCredentialStore(
            reference_factory=lambda: _REFERENCE,
            failure=CredentialStoreUnavailableError(),
        ),
    )
    assert operator.main(["status"]) == 1
    assert capsys.readouterr().out.strip() == (
        '{"available": false, "status": "credential_store_unavailable"}'
    )
    assert operator.main(["revoke", str(_REFERENCE)]) == 2
    assert capsys.readouterr().out.strip() == (
        '{"error": "credential_store_unavailable"}'
    )


def test_cli_rejects_token_argument_without_echoing_it(capsys) -> None:
    try:
        operator.main(["install", _CANARY])
    except SystemExit as exc:
        assert str(exc) == "credential_command_invalid"
    captured = capsys.readouterr()
    assert _CANARY not in captured.out
    assert _CANARY not in captured.err


def test_unexpected_nested_exception_text_is_redacted(monkeypatch, capsys) -> None:
    class HostileStore:
        def revoke(self, reference: CredentialReference) -> None:
            del reference
            raise OSError(_CANARY)

    monkeypatch.setattr(operator, "WindowsCredentialStore", HostileStore)
    assert operator.main(["revoke", str(_REFERENCE)]) == 2
    captured = capsys.readouterr()
    assert _CANARY not in captured.out
    assert _CANARY not in captured.err
    assert captured.out.strip() == '{"error": "credential_store_unavailable"}'


def test_powershell_wrapper_has_no_secret_parameter_or_argument() -> None:
    script = Path("scripts/manage-credential.ps1").read_text(encoding="utf-8")
    assert "[string]$Secret" not in script
    assert "[SecureString]" not in script
    assert '"-m", "app.credentials.operator", $Action' in script
