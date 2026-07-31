"""PostgreSQL integration proof for the retrieval evaluation harness."""

import os
import uuid
from pathlib import Path

from sqlalchemy import func, select, text

from app.models.memory import Memory
from app.models.memory_embedding import MemoryEmbedding
from app.retrieval_evaluation.runner import run
from tests.integration.conftest import verify_connected_test_database
from tests.powershell import run_powershell


def test_harness_reuses_production_retrieval_and_rolls_back_all_fixtures(
    migrated_test_database: None, test_database_url: str, monkeypatch
) -> None:
    verify_connected_test_database(test_database_url)
    from sqlalchemy import create_engine

    engine = create_engine(test_database_url)
    with engine.connect() as connection:
        before = (
            connection.scalar(select(func.count()).select_from(Memory)),
            connection.scalar(select(func.count()).select_from(MemoryEmbedding)),
        )
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    report = run(test_database_url, baseline_check=True)
    assert report.baseline_passed is True
    assert [mode.mode for mode in report.modes] == ["lexical", "semantic", "hybrid"]
    repeated = run(test_database_url, baseline_check=True)
    assert repeated == report
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT current_database()")) == "second_brain_test"
        )
        after = (
            connection.scalar(select(func.count()).select_from(Memory)),
            connection.scalar(select(func.count()).select_from(MemoryEmbedding)),
        )
    engine.dispose()
    assert after == before
    assert os.environ["OPENAI_API_KEY"] == "must-not-be-used"


def test_inactive_and_project_scopes_are_excluded_in_dataset_results(
    migrated_test_database: None, test_database_url: str
) -> None:
    report = run(test_database_url, baseline_check=False)
    results = {(row.case_id, row.mode): row for row in report.case_results}
    active = results[("active_only", "lexical")]
    assert active.retrieved_keys == ["active_release"]
    project = results[("project_isolation", "hybrid")]
    assert "alpha_roadmap" in project.retrieved_keys
    assert "beta_roadmap" not in project.retrieved_keys
    assert results[("paraphrase_semantic", "semantic")].retrieved_keys[0] == (
        "semantic_backup"
    )


def test_powershell_command_succeeds_writes_optional_json_and_hides_credentials(
    migrated_test_database: None, test_database_url: str
) -> None:
    output = Path("evaluation") / f"retrieval-result-{uuid.uuid4()}.json"
    environment = os.environ.copy()
    environment["TEST_DATABASE_URL"] = test_database_url
    result = run_powershell(
        [
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "scripts/evaluate-retrieval.ps1",
            "-BaselineCheck",
            "-OutputPath",
            str(output),
        ],
        env=environment,
    )
    try:
        assert result.returncode == 0, result.stderr
        assert "PASS" in result.stdout
        assert "change-me" not in result.stdout + result.stderr
        assert '"baseline_passed": true' in output.read_text(encoding="utf-8")
    finally:
        output.unlink(missing_ok=True)
