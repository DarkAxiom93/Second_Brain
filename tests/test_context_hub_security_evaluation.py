"""Executable CP113 U01-U18 threat-to-test release manifest."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_THREATS = tuple(f"U{number:02d}" for number in range(1, 19))

THREAT_TESTS: dict[str, tuple[str, ...]] = {
    "U01": (
        "tests/integration/test_context_hub.py::test_u01_all_surfaces_exhaust_exact_three_scope_canaries",
    ),
    "U02": (
        "tests/integration/test_context_hub.py::test_u02_all_family_kind_reopen_substitutions_fail_closed",
    ),
    "U03": (
        "tests/test_context_hub.py::test_cursor_is_opaque_bound_and_strictly_validated",
    ),
    "U04": (
        "frontend/src/ContextHub.test.tsx::renders fixed family order and visible kind, trust, state, scope, provenance, and exact facets",  # noqa: E501
    ),
    "U05": (
        "tests/integration/test_context_hub.py::test_u05_hostile_instructions_execute_no_authority_or_mutation",
        "frontend/src/ContextHub.test.tsx::keeps hostile content inert and reopens detail in-page without exposing or persisting the token",  # noqa: E501
    ),
    "U06": (
        "frontend/src/ContextHub.test.tsx::contains the complete hostile rendering corpus without execution navigation or label spoofing",  # noqa: E501
    ),
    "U07": (
        "tests/integration/test_context_hub.py::test_u07_excluded_canaries_never_reach_hub_surfaces_or_errors",
        "frontend/src/ContextHub.test.tsx::keeps excluded privacy and capability canaries out of the DOM",  # noqa: E501
    ),
    "U08": (
        "tests/integration/test_context_hub.py::test_exact_scope_grouping_inert_text_and_reopen",
    ),
    "U09": (
        "tests/integration/test_context_hub.py::test_u09_native_github_and_calendar_state_is_preserved",
    ),
    "U10": (
        "tests/integration/test_context_hub.py::test_u10_family_flood_keeps_fixed_groups_stable_ties_and_no_scores",
    ),
    "U11": (
        "tests/integration/test_context_hub.py::test_context_hub_api_paginates_reopens_facets_and_rejects_replay",
        "frontend/src/ContextHub.test.tsx::paginates with the canonical applied snapshot and invalidates the cursor when controls change",  # noqa: E501
    ),
    "U12": (
        "tests/integration/test_context_hub.py::test_u12_boundaries_overbounds_repetition_and_sql_work_are_bounded",
    ),
    "U13": (
        "tests/integration/test_context_hub.py::test_u13_runtime_tripwires_stay_zero_across_success_and_error_paths",
    ),
    "U14": (
        "tests/integration/test_context_hub.py::test_u14_query_facets_and_detail_mutate_no_protected_domain",
    ),
    "U15": (
        "tests/test_context_hub_security_adversarial.py::test_u15_registry_agent_automation_and_evidence_catalogs_have_no_hub_authority",
        "tests/integration/test_context_hub.py::test_u15_agent_automation_and_tool_interfaces_reject_context_hub",
    ),
    "U16": (
        "tests/integration/test_connector_persistence.py::test_project_export_v1_excludes_all_connector_data",
        "tests/integration/test_calendar_persistence.py::test_export_v1_excludes_calendar_and_secret_canary",
    ),
    "U17": (
        "tests/test_context_hub_security_adversarial.py::test_u17_unknown_nested_configuration_and_confusable_injection_rejects",
    ),
    "U18": (
        "tests/integration/test_context_hub.py::test_u18_postgresql_event_barriers_preserve_scope_provenance_and_keysets",
        "tests/integration/test_context_hub.py::test_u18_github_commit_between_hub_pages_is_old_or_new_not_mixed",
        "tests/integration/test_context_hub.py::test_u18_calendar_and_scope_commits_make_detail_exact_or_fail_closed",
    ),
}


class ManifestValidationError(AssertionError):
    """The manifest is not a closed unconditional executable gate."""


def _definitions(path: Path) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    return {
        node.name: node
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _has_assertion(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Assert)
        or (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr in {"raises", "fail"}
        )
        for child in ast.walk(node)
    )


def _conditional(node: ast.AST) -> bool:
    calls = {
        child.func.attr
        if isinstance(child.func, ast.Attribute)
        else child.func.id
        if isinstance(child.func, ast.Name)
        else ""
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
    }
    decorators = " ".join(
        ast.unparse(item).lower() for item in getattr(node, "decorator_list", ())
    )
    return bool(calls & {"skip", "skipif", "xfail"}) or any(
        token in decorators for token in ("skip", "skipif", "xfail")
    )


def _cp113_database_gate(node: ast.AST, fixtures: tuple[ast.AST, ...]) -> bool:
    decorators = " ".join(
        ast.unparse(item) for item in getattr(node, "decorator_list", ())
    )
    fixture_source = "\n".join(ast.unparse(item) for item in fixtures)
    return (
        "cp113_security" in decorators
        and "CP113 security tests require TEST_DATABASE_URL=second_brain_test"
        in fixture_source
        and "pytest.fail" in fixture_source
    )


def _fixture_dependencies(
    path: Path, node: ast.FunctionDef | ast.AsyncFunctionDef, root: Path
) -> tuple[ast.AST, ...]:
    candidates = {path.parent / "conftest.py", root / "tests/integration/conftest.py"}
    definitions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for candidate in candidates:
        if candidate.is_file():
            definitions.update(_definitions(candidate))
    pending = [argument.arg for argument in node.args.args]
    seen: set[str] = set()
    result: list[ast.AST] = []
    while pending:
        name = pending.pop()
        if name in seen or name not in definitions:
            continue
        seen.add(name)
        fixture = definitions[name]
        result.append(fixture)
        pending.extend(argument.arg for argument in fixture.args.args)
    return tuple(result)


def validate_manifest(
    manifest: Mapping[str, tuple[str, ...]], *, root: Path = ROOT
) -> None:
    if tuple(manifest) != EXPECTED_THREATS or len(manifest) != 18:
        raise ManifestValidationError("inventory must be exactly ordered U01-U18")
    nodes = [node for mapped in manifest.values() for node in mapped]
    if any(not mapped for mapped in manifest.values()):
        raise ManifestValidationError("every threat requires evidence")
    if len(nodes) != len(set(nodes)):
        raise ManifestValidationError("mapped nodes may not be reused")
    for node_id in nodes:
        try:
            relative_path, test_name = node_id.split("::", 1)
        except ValueError as exc:
            raise ManifestValidationError("invalid node selector") from exc
        path = root / relative_path
        if not path.is_file():
            raise ManifestValidationError(f"missing node path: {node_id}")
        source = path.read_text(encoding="utf-8")
        if path.suffix == ".py":
            node = _definitions(path).get(test_name)
            if node is None:
                raise ManifestValidationError(f"missing test: {node_id}")
            if not _has_assertion(node):
                raise ManifestValidationError(f"non-assertive test: {node_id}")
            fixtures = _fixture_dependencies(path, node, root)
            conditional_fixtures = tuple(
                item for item in fixtures if _conditional(item)
            )
            if _conditional(node) or (
                conditional_fixtures
                and not _cp113_database_gate(node, conditional_fixtures)
            ):
                raise ManifestValidationError(f"conditional test: {node_id}")
        else:
            marker = f'it("{test_name}"'
            if marker not in source:
                raise ManifestValidationError(f"missing UI test: {node_id}")
            body = source[source.index(marker) :].split("\n  it(", 1)[0]
            if "expect(" not in body:
                raise ManifestValidationError(f"non-assertive UI test: {node_id}")
            if any(token in body for token in (".skip(", ".todo(", ".skipIf(")):
                raise ManifestValidationError(f"conditional UI test: {node_id}")


def test_real_manifest_passes_the_closed_validator() -> None:
    validate_manifest(THREAT_TESTS)
    assert sum(len(nodes) for nodes in THREAT_TESTS.values()) == 25


@pytest.mark.parametrize(
    ("mutation", "fragment"),
    (
        ("missing", "inventory"),
        ("extra", "inventory"),
        ("empty", "evidence"),
        ("duplicate", "reused"),
        ("nonexistent", "missing"),
    ),
)
def test_manifest_mutations_fail_closed(mutation: str, fragment: str) -> None:
    changed = dict(THREAT_TESTS)
    if mutation == "missing":
        changed.pop("U18")
    elif mutation == "extra":
        changed["U19"] = changed["U18"]
    elif mutation == "empty":
        changed["U01"] = ()
    elif mutation == "duplicate":
        changed["U02"] = changed["U01"]
    else:
        changed["U01"] = ("tests/not_present.py::test_missing",)
    with pytest.raises(ManifestValidationError, match=fragment):
        validate_manifest(changed)


@pytest.mark.parametrize(
    "kind", ("non_assertive", "skip", "skipif", "xfail", "fixture_skip")
)
def test_source_and_hidden_fixture_condition_mutations_fail_closed(
    tmp_path: Path, kind: str
) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    body = {
        "non_assertive": "def test_node():\n    return None\n",
        "skip": "import pytest\n@pytest.mark.skip\ndef test_node():\n    assert True\n",
        "skipif": (
            "import pytest\n@pytest.mark.skipif(True, reason='x')\n"
            "def test_node():\n    assert True\n"
        ),
        "xfail": (
            "import pytest\n@pytest.mark.xfail\ndef test_node():\n    assert True\n"
        ),
        "fixture_skip": "def test_node(hidden):\n    assert True\n",
    }[kind]
    (tests_dir / "node.py").write_text(body, encoding="utf-8")
    if kind == "fixture_skip":
        (tests_dir / "conftest.py").write_text(
            "import pytest\n@pytest.fixture\ndef hidden():\n"
            "    pytest.skip('environment')\n",
            encoding="utf-8",
        )
    changed = dict(THREAT_TESTS)
    changed["U01"] = ("tests/node.py::test_node",)
    with pytest.raises(ManifestValidationError):
        validate_manifest(changed, root=tmp_path)


def test_ui_todo_mutation_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "frontend/src/node.tsx"
    path.parent.mkdir(parents=True)
    path.write_text(
        'it("node".todo(() => { expect(true).toBe(true); }));', encoding="utf-8"
    )
    changed = dict(THREAT_TESTS)
    changed["U01"] = ("frontend/src/node.tsx::node",)
    with pytest.raises(ManifestValidationError):
        validate_manifest(changed, root=tmp_path)
