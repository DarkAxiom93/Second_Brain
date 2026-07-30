"""PostgreSQL-backed command runner for deterministic retrieval evaluation."""

import argparse
import hashlib
import json
import os
import uuid
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.models.memory import Memory
from app.models.memory_embedding import MemoryEmbedding
from app.models.project import Project
from app.repositories.memories import ScoredMemory, search_answer_evidence
from app.retrieval_evaluation.models import (
    EvaluationDataset,
    EvaluationReport,
    SearchMode,
)
from app.retrieval_evaluation.service import apply_thresholds, evaluate_dataset

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "evaluation" / "retrieval_cases.v1.json"
BASELINE_PATH = ROOT / "evaluation" / "retrieval_baseline.v1.json"
TEST_DATABASE = "second_brain_test"
NAMESPACE = uuid.UUID("144981d1-8f14-4af0-9490-ccb65b4b71ce")


def _vector(axis: int) -> list[float]:
    values = [0.0] * 1536
    values[axis] = 1.0
    return values


QUERY_AXES = {
    "release checklist": 0,
    "identical ranking phrase": 1,
    "cobalt lighthouse protocol": 2,
    "quarterly retention forecast": 3,
    "incident response handbook": 4,
    "where are customer backups kept": 5,
    "private alpha roadmap": 6,
    "unassigned orchid note": 7,
}

FIXTURES: dict[str, tuple[str, str | None, str, int]] = {
    "active_release": (
        "The release checklist requires two approvals.",
        "alpha",
        "active",
        0,
    ),
    "archived_release": ("Archived release checklist copy.", "alpha", "archived", 0),
    "expired_release": ("Expired release checklist copy.", "alpha", "expired", 0),
    "invalid_release": ("Invalid release checklist copy.", "alpha", "invalid", 0),
    "superseded_release": (
        "Superseded release checklist copy.",
        "alpha",
        "superseded",
        0,
    ),
    "tie_a": ("identical ranking phrase", "alpha", "active", 1),
    "tie_b": ("identical ranking phrase", "alpha", "active", 1),
    "lexical_exact": (
        "Use the cobalt lighthouse protocol for recovery.",
        "alpha",
        "active",
        2,
    ),
    "lexical_distractor": (
        "Cobalt paint is stored near the lighthouse model.",
        "alpha",
        "active",
        8,
    ),
    "hybrid_target": (
        "The quarterly retention forecast predicts renewals.",
        "alpha",
        "active",
        3,
    ),
    "hybrid_distractor": (
        "A quarterly forecast covers retention vocabulary.",
        "alpha",
        "active",
        9,
    ),
    "incident_primary": (
        "The incident response handbook defines escalation.",
        "alpha",
        "active",
        4,
    ),
    "incident_secondary": (
        "Read the incident response handbook before paging.",
        "alpha",
        "active",
        4,
    ),
    "semantic_backup": (
        "Client archives reside in the northern storage vault.",
        "alpha",
        "active",
        5,
    ),
    "alpha_roadmap": (
        "The private alpha roadmap launches in autumn.",
        "alpha",
        "active",
        6,
    ),
    "beta_roadmap": (
        "The private alpha roadmap was copied into beta.",
        "beta",
        "active",
        6,
    ),
    "unassigned_note": (
        "This unassigned orchid note has no project.",
        None,
        "active",
        7,
    ),
}


def load_dataset(path: Path = DATASET_PATH) -> EvaluationDataset:
    try:
        return EvaluationDataset.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValidationError) as error:
        raise ValueError(f"invalid evaluation dataset: {error}") from error


def verify_test_database_url(value: str) -> None:
    url = make_url(value)
    if url.host != "127.0.0.1" or url.database != TEST_DATABASE:
        raise ValueError("TEST_DATABASE_URL must target second_brain_test on 127.0.0.1")


def _seed(session: Session) -> tuple[dict[str, uuid.UUID], dict[str, uuid.UUID]]:
    projects = {
        key: uuid.uuid5(NAMESPACE, f"project:{key}") for key in ("alpha", "beta")
    }
    fixture_ids = {key: uuid.uuid5(NAMESPACE, f"memory:{key}") for key in FIXTURES}
    occupied = session.scalars(
        select(Memory.id).where(Memory.id.in_(fixture_ids.values()))
    ).first()
    if occupied is not None:
        raise RuntimeError(
            "evaluation fixture UUID already exists; refusing to mutate it"
        )
    session.add_all(
        Project(id=project_id, name=f"retrieval-evaluation-{key}")
        for key, project_id in projects.items()
    )
    session.flush()
    for key, (content, project, status, axis) in FIXTURES.items():
        memory = Memory(
            id=fixture_ids[key],
            content=content,
            project_id=projects.get(project) if project else None,
            status=status,
        )
        session.add(memory)
        session.flush()
        session.add(
            MemoryEmbedding(
                memory_id=memory.id,
                provider="retrieval-evaluation-fixed",
                model="axis-v1",
                dimensions=1536,
                embedding=_vector(axis),
                input_hash=hashlib.sha256(content.encode()).hexdigest(),
            )
        )
    session.flush()
    return fixture_ids, projects


def run(database_url: str, *, baseline_check: bool) -> EvaluationReport:
    verify_test_database_url(database_url)
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            if connection.scalar(text("SELECT current_database()")) != TEST_DATABASE:
                raise RuntimeError("live database identity is not second_brain_test")
            connection.rollback()
            transaction = connection.begin()
            session = Session(bind=connection)
            try:
                fixture_ids, project_ids = _seed(session)

                def retrieve(
                    query: str,
                    mode: SearchMode,
                    project_id: uuid.UUID | None,
                    limit: int,
                ) -> list[ScoredMemory]:
                    query_vector = (
                        None if mode == "lexical" else _vector(QUERY_AXES[query])
                    )
                    return search_answer_evidence(
                        session,
                        query=query,
                        mode=mode,
                        project_id=project_id,
                        limit=limit,
                        query_vector=query_vector,
                    )

                report = evaluate_dataset(
                    load_dataset(),
                    fixture_ids=fixture_ids,
                    project_ids=project_ids,
                    retrieve=retrieve,
                )
                if baseline_check:
                    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
                    apply_thresholds(report, baseline["minimums"])
                return report
            finally:
                session.close()
                transaction.rollback()
    finally:
        engine.dispose()


def _print_report(report: EvaluationReport) -> None:
    print("Mode      Cases  Hit@K  Recall@K  MRR    Precision@K  Baseline")
    for mode in report.modes:
        metrics = mode.metrics
        baseline = (
            "-"
            if mode.threshold_passed is None
            else ("PASS" if mode.threshold_passed else "FAIL")
        )
        print(
            f"{mode.mode:<9} {metrics.case_count:>5}  {metrics.hit_at_k:.3f}  "
            f"{metrics.recall_at_k or 0:.3f}     "
            f"{metrics.mean_reciprocal_rank or 0:.3f}  "
            f"{metrics.precision_at_k:.3f}        {baseline}"
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-check", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        parser.error("TEST_DATABASE_URL is required")
    report = run(database_url, baseline_check=args.baseline_check)
    _print_report(report)
    if args.output:
        args.output.write_text(
            json.dumps(report.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )
    return 0 if report.baseline_passed is not False else 2


if __name__ == "__main__":
    raise SystemExit(main())
