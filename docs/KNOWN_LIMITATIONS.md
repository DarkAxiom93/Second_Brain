# Published Local V1.1 and proposed V1.2 known limitations

Local V1.1 is published as `v1.1.0` from
`88dffa90ff04cde4c57dcacbe2764b8a31b0c9ce`. Checkpoint 61 is complete at
`850cfd0a749b5de072b910203ba9906ab5270b40`. Checkpoint 62 is complete at
`3da0cdd875dc8af7a60fd8af5b6f9878be5a769a`; Checkpoint 63 is pending human
review, and Checkpoint 64 is not started.

- There is no authentication, authorization, role model, or multi-user
  isolation. Run the app only on loopback for one trusted local maintainer.
- Cloud deployment, synchronization, remote access, and multi-device state are
  unavailable.
- The Agent Run API supports only manual create/read/list/cancel and internal
  lifecycle transitions. There is no planner, Tool Registry/execution, Agent UI,
  Approval behavior, Research Agent, or Memory Curator Agent.
- There are no scheduled jobs, background workers, autonomous agents, or
  Automations. An Automation is deferred and would be a trigger that creates an
  Agent Run, not the Run itself.
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
  Router RSC action advisory GHSA-qwww-vcr4-c8h2. Published V1.1
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
