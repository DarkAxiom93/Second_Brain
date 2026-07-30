# Human review before promotion

Status: Accepted

## Context

Provider output is probabilistic and must not silently become trusted memory.

## Decision

AI extraction creates pending `MemoryProposal` records. A human explicitly
approves or rejects each proposal, and a separate explicit promotion action is
required before an approved proposal becomes a `Memory`.

## Consequences

Generation, review, and promotion are auditable and independently retryable.
There is no automatic or batch promotion path.
