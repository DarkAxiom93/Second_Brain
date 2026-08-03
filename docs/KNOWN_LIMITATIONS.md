# Local V1 known limitations

- There is no authentication, authorization, role model, or multi-user
  isolation. Run the app only on loopback for one trusted local maintainer.
- Cloud deployment, synchronization, remote access, and multi-device state are
  unavailable.
- There are no scheduled jobs, background workers, or autonomous agents.
- Maintenance and diagnostics are read-only. There is no automatic
  maintenance, repair, expiration processing, or re-embedding.
- Version 1 `.sbexport` bundles are private but not encrypted. Protect them as
  sensitive data.
- Import has no merge, overwrite, remap, repair, or partial-import behavior.
- Answers are stateless. Questions, answers, citations, and conversation history
  are not persisted.
- Live provider-dependent success smoke is unavailable without credentials.
  Automated tests use deterministic fake providers for proposal generation,
  semantic/hybrid search, embeddings, and evidence-backed answer success.
- The `v1.0.0` release lockfile retains the historical high-severity React
  Router RSC action advisory GHSA-qwww-vcr4-c8h2. The current V1.1 candidate
  uses `react-router` 8.3.0 and `npm audit` reports zero vulnerabilities.
- Explained search provides deterministic ordering aids, not confidence,
  probability, certainty, model reasoning, or a relevance guarantee. Live
  semantic and hybrid success remains unavailable without provider credentials;
  deterministic fake-provider tests cover those paths.
- The Chrome extension acceptance environment cannot upload local files unless
  its optional “Allow access to file URLs” permission is enabled. The same
  bundle was exported and conflict-validated through the Vite-origin operations
  service, while deterministic UI tests cover file selection, validation,
  conflict rendering, plan invalidation, confirmation, and successful execution.
