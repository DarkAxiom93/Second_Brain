"""Executable CP121 CAP01-CAP18 threat-to-test release manifest."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_THREATS = tuple(f"CAP{number:02d}" for number in range(1, 19))

THREAT_TESTS: dict[str, tuple[str, ...]] = {
    "CAP01": (
        "tests/integration/test_capture_api.py::test_scope_isolation_across_detail_and_every_mutation",
        "tests/integration/test_capture_conversion.py::test_unscoped_source_document_ingestion_and_link_boundaries_fail_closed",
        "tests/integration/test_capture_conversion.py::test_tools_hub_research_and_export_use_their_authoritative_project_scope",
    ),
    "CAP02": (
        "tests/integration/test_capture_conversion.py::test_conversion_scope_state_identity_and_stale_fail_without_writes",
        "tests/integration/test_capture_conversion.py::test_source_resolver_rejects_pending_discarded_missing_and_broken_binding",
    ),
    "CAP03": (
        "tests/integration/test_capture_api.py::test_create_replay_scope_and_private_projection",
        "tests/integration/test_capture_persistence.py::test_concurrent_same_key_creation_has_one_winner",
        "tests/test_capture_service.py::test_invalid_idempotency_keys",
        "tests/test_capture_service.py::test_raw_key_is_absent_from_projection_and_logs",
    ),
    "CAP04": (
        "tests/integration/test_capture_api.py::test_stale_discard_restore_and_complete_state_action_matrix",
        "tests/test_capture_security_adversarial.py::test_cap17_route_and_openapi_inventory_has_no_delete_or_purge",
    ),
    "CAP05": (
        "tests/integration/test_capture_conversion.py::test_cap05_fault_boundaries_rollback_and_clean_retry_once",
    ),
    "CAP06": (
        "tests/integration/test_capture_conversion.py::test_concurrent_conversion_serializes_to_one_graph",
        "tests/integration/test_capture_conversion.py::test_source_resolver_is_scoped_safe_and_read_only",
    ),
    "CAP07": (
        "tests/integration/test_capture_api.py::test_concurrent_same_revision_mutations_correlate_persisted_winner",
        "tests/integration/test_capture_api.py::test_reassignment_directions_stale_conflicts_and_timestamps",
    ),
    "CAP08": (
        "tests/integration/test_capture_security.py::test_cap08_hostile_corpus_stays_inert_through_real_capture_flows",
    ),
    "CAP09": (
        "frontend/src/Capture.test.tsx::contains the complete hostile rendering corpus without execution navigation or control spoofing",  # noqa: E501
    ),
    "CAP10": (
        "tests/integration/test_capture_security.py::test_cap10_private_canaries_never_escape_public_errors_logs_or_cursors",
        "tests/test_capture_service.py::test_safe_projection_has_no_private_idempotency_material",
        "frontend/src/Capture.test.tsx::uses no polling interval or browser persistence during Inbox operation",  # noqa: E501
    ),
    "CAP11": (
        "tests/integration/test_capture_api.py::test_query_normalization_character_utf8_and_page_cursor_boundaries",
        "tests/integration/test_capture_api.py::test_query_closed_shape_result_cap_and_bounded_sql",
        "tests/integration/test_capture_api.py::test_state_filters_default_all_combinations_and_bounds",
        "tests/integration/test_capture_api.py::test_cursor_all_bindings_malformed_canonical_and_stable_browse_pages",
        "tests/integration/test_capture_api.py::test_normal_success_statement_ceilings",
        "tests/integration/test_capture_conversion.py::test_cp119_statement_ceilings",
        "tests/integration/test_capture_persistence.py::test_schema_indexes_defaults_and_generated_search_vector",
    ),
    "CAP12": (
        "tests/integration/test_capture_security.py::test_cap12_external_tripwires_are_zero_on_success_failure_and_replay",
    ),
    "CAP13": (
        "tests/test_capture_security_adversarial.py::test_cap13_capture_is_absent_from_every_authority_catalog",
        "tests/integration/test_capture_security.py::test_cap13_runtime_authority_surfaces_have_zero_capture_delta",
    ),
    "CAP14": (
        "tests/integration/test_capture_security.py::test_cap14_export_v1_archive_and_round_trip_exclude_capture",
        "tests/integration/test_project_import.py::test_import_preserves_fields_vector_search_and_round_trip",
    ),
    "CAP15": (
        "tests/integration/test_capture_security.py::test_cap15_protected_postgresql_backup_restores_capture_exactly",
    ),
    "CAP16": (
        "tests/integration/test_capture_conversion.py::test_cap16_reassignment_conversion_race_freezes_one_complete_scope",
        "tests/integration/test_capture_conversion.py::test_cap16_conversion_win_closes_old_new_visibility_and_downstream_paths",
        "tests/integration/test_capture_api.py::test_reassignment_vs_old_scope_edit_has_one_correlated_winner",
    ),
    "CAP17": (
        "tests/integration/test_capture_persistence.py::test_database_constraints_and_delete_restrictions",
        "tests/test_project_routes.py::test_existing_routes_and_only_public_project_paths_remain_present",
    ),
    "CAP18": (
        "tests/integration/test_capture_conversion.py::test_cap18_equal_content_has_distinct_stable_write_once_provenance",
        "tests/integration/test_capture_conversion.py::test_conversion_persists_exact_text_metadata_chunks_and_capture",
        "tests/integration/test_capture_conversion.py::test_processed_replay_accepts_only_original_and_current_revision",
        "tests/integration/test_capture_conversion.py::test_proposal_generation_distinguishes_omitted_null_and_project_scope",
        "tests/integration/test_capture_conversion.py::test_proposal_read_review_and_promotion_fail_after_binding_scope_mismatch",
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


def _fixtures(
    path: Path, node: ast.FunctionDef | ast.AsyncFunctionDef, root: Path
) -> tuple[ast.AST, ...]:
    definitions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for candidate in {
        path.parent / "conftest.py",
        root / "tests/integration/conftest.py",
    }:
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
        raise ManifestValidationError("inventory must be exactly ordered CAP01-CAP18")
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
            fixtures = _fixtures(path, node, root)
            conditional = tuple(item for item in fixtures if _conditional(item))
            decorators = " ".join(ast.unparse(item) for item in node.decorator_list)
            gate = "cp121_security" in decorators and any(
                "CP121 security tests require TEST_DATABASE_URL=second_brain_test"
                in ast.unparse(item)
                and "pytest.fail" in ast.unparse(item)
                for item in conditional
            )
            if _conditional(node) or (conditional and not gate):
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
    assert sum(len(nodes) for nodes in THREAT_TESTS.values()) == 44


@pytest.mark.parametrize(
    ("mutation", "fragment"),
    (
        ("missing", "inventory"),
        ("extra", "inventory"),
        ("empty", "evidence"),
        ("duplicate", "reused"),
        ("renamed", "missing"),
    ),
)
def test_manifest_mutations_fail_closed(mutation: str, fragment: str) -> None:
    changed = dict(THREAT_TESTS)
    if mutation == "missing":
        changed.pop("CAP18")
    elif mutation == "extra":
        changed["CAP19"] = changed["CAP18"]
    elif mutation == "empty":
        changed["CAP01"] = ()
    elif mutation == "duplicate":
        changed["CAP02"] = changed["CAP01"]
    else:
        changed["CAP01"] = ("tests/not_present.py::test_missing",)
    with pytest.raises(ManifestValidationError, match=fragment):
        validate_manifest(changed)


@pytest.mark.parametrize(
    "kind", ("non_assertive", "skip", "skipif", "xfail", "fixture_skip")
)
def test_conditional_source_mutations_fail_closed(tmp_path: Path, kind: str) -> None:
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
    changed["CAP01"] = ("tests/node.py::test_node",)
    with pytest.raises(ManifestValidationError):
        validate_manifest(changed, root=tmp_path)


def test_ui_skip_and_todo_mutations_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "frontend/src/node.tsx"
    path.parent.mkdir(parents=True)
    path.write_text(
        'it("node", () => { expect(true).toBe(true); }).todo();', encoding="utf-8"
    )
    changed = dict(THREAT_TESTS)
    changed["CAP09"] = ("frontend/src/node.tsx::node",)
    with pytest.raises(ManifestValidationError):
        validate_manifest(changed, root=tmp_path)
