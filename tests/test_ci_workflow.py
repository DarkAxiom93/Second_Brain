import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml"


def _workflow_text() -> str:
    assert WORKFLOW_PATH.is_file()
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def test_ci_workflow_has_only_approved_triggers_and_permissions() -> None:
    text = _workflow_text()

    trigger_block = text.split("\npermissions:\n", maxsplit=1)[0]
    assert re.findall(r"^  ([a-z_]+):", trigger_block, flags=re.MULTILINE) == [
        "pull_request",
        "push",
        "workflow_dispatch",
    ]
    assert "pull_request_target" not in text
    assert re.search(r"^permissions:\n  contents: read\n\n", text, re.MULTILINE)
    assert not re.search(r"^  [a-z-]+: (?:write|id-token)\s*$", text, re.MULTILINE)


def test_ci_workflow_is_bounded_and_credential_free() -> None:
    text = _workflow_text()
    lowered = text.lower()
    active_yaml = "\n".join(
        line for line in lowered.splitlines() if not line.lstrip().startswith("#")
    )

    assert re.findall(r"^    runs-on: (.+)$", text, flags=re.MULTILINE) == [
        "windows-2022"
    ]
    assert "persist-credentials: false" in text
    assert "continue-on-error" not in text
    assert "secrets." not in lowered
    assert "database_url" not in lowered
    assert "test_database_url" not in lowered

    forbidden_behavior = (
        "pull_request_target",
        "id-token",
        "docker",
        "postgres",
        "services:",
        "artifact",
        "deploy",
        "publish",
        "repository_dispatch",
        "release:",
        "schedule:",
    )
    assert all(term not in active_yaml for term in forbidden_behavior)


def test_ci_workflow_uses_only_pinned_reviewed_actions() -> None:
    text = _workflow_text()
    uses = re.findall(r"^\s*uses:\s*([^\s]+)$", text, flags=re.MULTILINE)

    assert len(uses) == 3
    assert {entry.split("@", maxsplit=1)[0] for entry in uses} == {
        "actions/checkout",
        "actions/setup-python",
        "actions/setup-node",
    }
    assert all(re.fullmatch(r"actions/[a-z-]+@[0-9a-f]{40}", entry) for entry in uses)
    assert "actions/checkout v4.2.2" in text
    assert "actions/setup-python v5.6.0" in text
    assert "actions/setup-node v4.4.0" in text


def test_ci_workflow_uses_exact_runtimes_and_established_commands() -> None:
    text = _workflow_text()

    assert "python-version: 3.12.10" in text
    assert "node-version: 22.22.0" in text
    assert 'python.exe -m pip install -e ".[dev]"' in text
    assert ".\\scripts\\verify.ps1 -Mode Quick -SkipDatabase" in text
    assert ".\\scripts\\frontend-setup.ps1" in text
    assert ".\\scripts\\verify-frontend.ps1" in text
    assert "npm audit --audit-level=high" in text
    assert "verify.ps1 -Mode Full" not in text


# These focused text assertions enforce this repository's CI policy; they are
# intentionally not presented as a complete GitHub Actions YAML parser.
