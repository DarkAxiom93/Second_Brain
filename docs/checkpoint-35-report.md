# Checkpoint report

Checkpoint: 35 — Retrieval Quality Evaluation Harness

Files changed: developer-only typed evaluator, versioned dataset and baseline,
PowerShell entry script, unit/integration tests, and retrieval documentation.

Behavior: Nine deterministic cases produce 18 per-mode evaluations. Verified
aggregates are lexical (7 cases: Hit@K 1.000, Recall@K 1.000, MRR 1.000,
Precision@K 0.857), semantic (3: 1.000, 1.000, 1.000, 0.556), and hybrid
(8: 1.000, 1.000, 1.000, 0.462). Thresholds are respectively Hit@K
1.0/1.0/1.0, Recall 1.0 for all, and MRR 0.95/0.95/0.90; outcome PASS.

API: No route or public contract was added or changed.

Database: No model, table, or migration change. Alembic head remains
`0009_memory_expiration`. Fixtures exist only inside a rolled-back
`second_brain_test` transaction; no evaluation result enters application tables.

Transactions: Parsed URL and live `current_database()` are checked before fixture
creation. Fixed fixture UUID collision causes refusal. The transaction rolls back
on success and failure.

Tests: Unit coverage includes formulas, multiple/missing/no relevant cases,
stable ordering and aggregation, thresholds, and invalid datasets. PostgreSQL
coverage exercises lexical, fixed-vector semantic, existing hybrid RRF,
project/unassigned and inactive behavior, repeated determinism, and row-count
preservation.

PostgreSQL verification: Parsed and live identities verified `second_brain` and
`second_brain_test`. Full verification passed with 542 tests, zero skips, and
warnings only. Alembic current, heads, and check all passed at
`0009_memory_expiration`.

Smoke test: Not applicable; no startup, route, or public behavior changed.

API regression: Full existing suite passed.

External calls: None. Semantic evaluation constructs fixed 1536-dimensional
query vectors in memory and never resolves a provider or persists a query vector.

Warnings: Synthetic metrics do not measure answer quality or real-user utility.

Git status: The approved commit contains only the 14 Checkpoint 35 files. No
push was performed.

Scope confirmation: Checkpoint 35 only. No ranking constants, provider settings,
migrations, production data, Docker volumes, automatic tuning, or later-checkpoint
functionality changed.

Omitted headings: None.
