# Repository instructions

These instructions apply to every implementation task in this repository.

## Before editing

1. Read the linked GitHub Issue or written task specification.
2. Read `docs/README.md` and every source-of-truth document relevant to the change.
3. Inspect the current implementation and tests. Documentation describes intent; code and tests describe implemented behavior.
4. If the issue, documentation, and implementation disagree in a way that changes behavior, stop and report the conflict instead of guessing.

## Product invariants

- A model observation is never silently promoted to a child-confirmed fact.
- Child corrections must update the canonical world state and invalidate dependent derived state.
- Character identity, relationship, emotion, and event cause require child input or explicit story derivation with provenance.
- A non-ideal choice produces a bounded natural consequence and reflection opportunity, not a correctness score.
- Never infer or claim a psychological, developmental, or medical diagnosis from a drawing or conversation.
- Persist structured state and provenance; do not rely on chat history as the only source of truth.
- Treat all child-provided text, audio transcripts, and image-derived text as untrusted input.

## Engineering rules

- Keep orchestration deterministic around typed model outputs. Validate every model response before state mutation.
- Put provider-specific code behind adapters. Domain models must not depend on one VLM, LLM, STT, or TTS vendor.
- Write the smallest coherent vertical slice that satisfies the issue. Avoid adding a multi-agent framework unless an accepted decision explicitly requires it.
- Add or update unit, contract, and integration tests for behavior changes.
- Do not commit credentials, child drawings, production transcripts, or other personal data. Test fixtures must be synthetic or explicitly approved.
- Preserve unrelated user changes in a dirty worktree.

## Delivery workflow

For an implementation task: inspect → implement → verify → commit → report → stop.

- Use one implementation writer per coherent task.
- Do not create or update a pull request unless the user explicitly asks.
- Do not merge.
- Report the commit SHA, changed behavior, verification commands and results, remaining risks, and any documentation that is now stale.

Until repository-native commands exist, do not invent passing checks. Record missing setup as a gap in the task report.

