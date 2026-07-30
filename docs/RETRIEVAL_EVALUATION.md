# Retrieval quality evaluation

The developer-only harness measures whether existing active-Memory retrieval
returns known fixtures for compact, versioned queries. It calls
`search_answer_evidence` directly; it does not call HTTP routes, providers, or
answer generation, and it does not tune production ranking.

```powershell
.\scripts\evaluate-retrieval.ps1
.\scripts\evaluate-retrieval.ps1 -BaselineCheck
.\scripts\evaluate-retrieval.ps1 -BaselineCheck -OutputPath .\result.json
```

The script accepts only `TEST_DATABASE_URL` targeting `second_brain_test` at
`127.0.0.1`, verifies `current_database()`, creates fixtures inside one
transaction, and always rolls it back. The optional JSON file is the only
persisted output. Docker is not managed and credentials are never printed.

## Dataset and embeddings

`evaluation/retrieval_cases.v1.json` contains stable case IDs, queries, optional
project fixture scopes, relevant and explicitly irrelevant fixture keys, modes,
and limits. UUIDs resolve only after fixtures are created. Cases cover exact and
paraphrased retrieval, hybrid distractors, project and unassigned Memories,
active-only status handling, multiple/no relevant results, and ties.

Semantic queries and fixture embeddings use repository-owned 1-hot,
1536-dimensional vectors. Query vectors remain in memory and are never
persisted. No provider is resolved. Fixed UUIDs and production tie-breaking make
repeated reports reproducible.

To add a case, add or reuse a stable fixture key in the runner, add its fixed
semantic axis where needed, update the JSON, run focused and Full verification,
and explicitly review any baseline change. Never put database UUIDs or
credentials in the dataset.

## Metrics and baseline

For the first `K` returned rows and relevant set `R`:

- Hit@K is 1 when any returned row is in `R`, otherwise 0.
- Recall@K is distinct relevant rows returned divided by `|R|`.
- Reciprocal rank is `1 / rank` of the first relevant row; MRR is its mean.
- Precision@K is relevant rows divided by the number actually returned.

Recall and reciprocal rank are `null` when `R` is empty. Such cases instead
report whether no expected match was returned. Metrics are averaged per mode;
there is no combined quality score.

`evaluation/retrieval_baseline.v1.json` records the verified summary and minimum
per-mode thresholds. Comparison uses `>=`, not exact float equality. The margins
tolerate irrelevant lower-ranked semantic candidates while requiring complete
recall and near-perfect first-relevant ranking. Threshold failure exits 2. The
command never updates the baseline; changes require explicit future review.

This small synthetic corpus measures retrieval regression, not production
relevance, answer correctness, calibration, exhaustive recall, or user utility.
