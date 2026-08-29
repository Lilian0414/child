# Implementation plan

_Status: Ready for issue creation_  
_Last reviewed: 2026-08-29_

## 1. Delivery principle

Build one vertical slice first: a synthetic drawing fixture → observation → child correction → world-state update → one branch → consequence → ending. Replace fixture capabilities with live providers only after the domain contracts and UI loop are testable.

Do not start with animation generation, a multi-agent framework or long-term profiles.

## 2. Decision gates before code expands

| Decision | Minimum evidence | When needed |
|---|---|---|
| Frontend framework | Team ownership, deployment target, audio/image support | Before scaffold |
| VLM + LLM provider | 10–20 synthetic drawing cases, JSON validity, latency, cost, data use | Before live observer/story integration |
| Voice scope | Browser/device test and fallback UX | Before P1 voice issue |
| Media storage | Deployment target, private access, retention/delete behavior | Before public demo |
| Realtime transport | Measured need for progress/streaming | After first request/response slice |

Until a gate is decided, keep provider/transport interfaces small and avoid vendor-specific domain fields.

## 3. Ordered backlog

Each row is intended to become one GitHub Issue with scope, non-goals, acceptance criteria and verification. Dependent issues should be implemented sequentially by one writer per coherent task.

### Issue 1 — Repository scaffold and developer loop

**Scope**

- Choose and document frontend framework.
- Create web/API layout, environment example and repository-native lint/type/test commands.
- Add health endpoint and a minimal page.
- Add CI for deterministic checks.

**Non-goals:** model integration, database domain schema, final UI.

**Acceptance:** fresh clone setup works from README; CI runs the same commands; no secrets committed.

### Issue 2 — Typed session and world-state core

**Depends on:** Issue 1.

**Scope**

- Implement accepted Pydantic/domain models from `DATA_CONTRACTS.md`.
- Implement state versions, immutable events, provenance and correction invalidation.
- Add SQLite repository and migration strategy.

**Non-goals:** external models, child-facing story UI.

**Acceptance:** unit tests prove observation cannot silently become fact, correction invalidates dependent derived facts, stale versions conflict and duplicate idempotency keys do not duplicate events.

### Issue 3 — Deterministic vertical slice

**Depends on:** Issue 2.

**Scope**

- Implement session API endpoints using synthetic provider fixtures.
- Build minimal setup, upload placeholder, grounding card, scene choice and ending screens.
- Run ball → balloon correction and one consequence branch end to end.

**Non-goals:** live VLM/LLM, speech, generated visuals.

**Acceptance:** integration + browser UAT demonstrate correction adoption, three stateful scenes, two choices and refresh recovery.

### Issue 4 — Observer adapter and provider benchmark

**Depends on:** Issue 3.

**Scope**

- Define provider interface and benchmark harness.
- Evaluate candidate model(s) on synthetic child-drawing fixtures.
- Integrate selected observer behind the adapter.
- Enforce schema, forbidden fields, timeout and repair behavior.

**Non-goals:** psychological interpretation, long image analysis report.

**Acceptance:** benchmark evidence is recorded; G-01–G-04, G-08–G-11 pass for active configuration; provider failure preserves state.

### Issue 5 — Grounding interaction and world readiness

**Depends on:** Issue 4.

**Scope**

- Implement question-selection policy and information threshold.
- Add confirm, reject, correct, free-input and skip flows.
- Apply accessibility profile to copy and choices.

**Non-goals:** diagnosis modes, unlimited chat.

**Acceptance:** 2–5 questions ground the canonical scenario; high-semantic skipped items remain unknown; UI never exposes raw confidence/debug data.

### Issue 6 — Story planner and consequence loop

**Depends on:** Issue 5.

**Scope**

- Add provider-neutral story-plan and consequence adapters.
- Validate allowed facts, stable IDs and bounded deltas.
- Implement reflection, re-choice and non-scoring ending.

**Non-goals:** generated video, long-form open chat, moral score.

**Acceptance:** G-05–G-07 pass; branch comparison shows different state + next scene; unsupported-fact rate is zero in golden cases.

### Issue 7 — Safety, privacy and deletion

**Depends on:** Issues 2–6. Safety invariants should be stubbed earlier; this issue completes the public-demo gate.

**Scope**

- Add private media handling, expiry and deletion.
- Implement safety routes and operator/adult pause behavior.
- Add redacted logging and cross-session isolation tests.

**Non-goals:** claim of legal or clinical compliance.

**Acceptance:** release checklist in `SAFETY_PRIVACY.md` passes; deletion covers media and state; safety golden cases pass.

### Issue 8 — Accessibility and optional voice

**Depends on:** stable Issue 6 flow and voice decision gate.

**Scope**

- Add replay, shorter copy, option-count control and visual prompts.
- If accepted, add push-to-talk STT and TTS via adapters with text/touch fallback.

**Non-goals:** continuous microphone, voice biometrics, voice-only core flow.

**Acceptance:** speech failure never blocks touch/text; retry does not duplicate state mutations; primary flow works without audio permission.

### Issue 9 — Demo hardening and deployment

**Depends on:** Issues 6–8 as selected for MVP.

**Scope**

- Deploy HTTPS build with private media and server-side secrets.
- Add operator-only fixture mode and visible labeling.
- Measure latency, complete browser UAT and rehearse both correction variants.

**Non-goals:** production scale or long-term analytics.

**Acceptance:** rehearsal gate in `DEMO_EVALUATION.md` passes against the deployed commit SHA; current CI corresponds to that SHA.

## 4. Suggested ownership

| Workstream | Primary owner profile | Handoff artifact |
|---|---|---|
| AI/domain | Agent engineer | Contracts, adapters, state transitions, eval evidence |
| Child-facing interaction | Frontend/UI owner | Grounding cards, scene renderer, accessible controls |
| Narrative content | Chinese/content teammate | Age-appropriate prompt/copy set, branch scenarios, review notes |
| Safety/demo | Shared review | Golden cases, deletion check, rehearsal log |

One person can cover multiple workstreams, but a single coherent issue should not have competing implementation writers.

## 5. Definition of done per issue

- Scope and non-goals are satisfied without unrelated expansion.
- Repository-native lint/type/test commands pass for the changed area.
- New behavior has unit/contract/integration evidence as appropriate.
- Relevant docs and fixtures are updated.
- No real child data or credentials are committed.
- Commit SHA and exact verification results are reported.
- Implementation complete is reported separately from PR available, CI green, UAT passed and merged.

## 6. Recommended first implementation target

Start with Issues 1–3 and stop to UAT the deterministic vertical slice. This exposes architecture and UX mistakes before model variability makes debugging ambiguous. Only then choose the live provider in Issue 4.

