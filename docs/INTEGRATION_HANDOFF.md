# Multimodal / Provider Integration Handoff

_Last reviewed: 2026-09-05_

這份文件提供給負責多模態、模型與前端串接的 integration owner。目的不是重述整個 backend，而是說清楚：**哪些事情 Core 已經處理、integration layer 要提供什麼、資料要長什麼樣子，以及怎麼驗收完整 MVP。**

核心原則：

> **AI proposes; the child owns the world and story.**

Provider 只負責「感知」或「生成候選內容」，不能直接決定 canonical world / story。孩子確認、修正或 redirect 後，Core 才更新正式狀態。

---

## 1. Ownership boundary

### Core owner 已負責

- Session lifecycle、state version、optimistic concurrency、idempotency。
- Canonical world state 與 provenance。
- Observation grounding：`confirm / correct / reject / skip`。
- Drawing revision 與 semantic reconciliation：`added / changed / removed / unchanged / uncertain`。
- Selective grounding：只詢問真正需要孩子決定的變化，不重問 unchanged facts。
- Canonical story state、story proposal、story grounding：`accept / correct / redirect`。
- Drawing/world 改變後的 stale story dependency invalidation。
- Continue story / revise drawing / complete story lifecycle。
- Canonical full-story projection。
- Persistence、refresh/retry safety、immutable event history。

### Integration owner 自由決定

- 使用哪個 VLM / multimodal model。
- 圖片是 upload、camera capture 或其他 input UX。
- Story LLM provider / model。
- 是否做 STT，以及使用哪個 STT。
- TTS provider 與播放 UX。
- 前端如何呈現 confirm / correct / continue / revise / complete。

Integration layer **不需要，也不應該**重新實作 revision diff、canonical state、story memory 或第二套 state machine。

---

## 2. Runtime flow

目標 runtime flow：

```text
Drawing / media
    ↓
VLM / Observer adapter
    ↓
Observation proposal
    ↓
Child grounding
    ↓
Canonical World
    ↓
StoryProvider
    ↓
Short story proposal
    ↓
Child accept / correct / redirect
    ↓
Canonical Story Segment
    ↓
Next intent
    ├─ Continue story
    ├─ Revise drawing
    └─ Complete story
```

若孩子重新畫：

```text
Drawing Revision N+1
    ↓
VLM observations
    ↓
Core reconciliation against current canonical world
    ↓
added / changed / removed / unchanged / uncertain
    ↓
Selective grounding
    ↓
Updated canonical world
    ↓
Next story proposal uses newest world + existing canonical story
```

---

## 3. Observer contract

VLM output is **proposal-only**. It must not invent application-owned canonical fields such as `confirmed`, `child_supplied`, `provenance`, canonical IDs, session status, or state version.

The Core observer boundary accepts only allowlisted visible information. Current provider-neutral observer contract supports these kinds:

- `object_count`
- `object`
- `character`
- `fact`
- `relationship`

`character.candidate.visible_description` is required and non-empty. Core owns conversion of that
visible description (and optional `visible_gesture`) into a canonical `Character`; browser confirm
and correction flows must not supply canonical names or IDs. Added/changed/uncertain `fact` and
`relationship` observations lack canonical references and therefore remain proposal/evidence rather
than child-facing prompts. Every returned object, object-count, or character prompt has the four
actions `confirm / correct / reject / skip`.

Typical observation batch passed into the Core:

```json
{
  "schema_version": "observation.v1",
  "batch_id": "obsb_r1",
  "media_id": "med_r1",
  "items": [
    {
      "observation_id": "obs_balls",
      "kind": "object_count",
      "candidate": {
        "label": "ball",
        "count": 4
      },
      "confidence": 0.91,
      "needs_confirmation": true
    }
  ]
}
```

Important rules:

- AI observation is never canonical truth.
- Child correction takes precedence over the model.
- Model output must remain inside the strict schema/policy boundary.
- Do not infer diagnosis, personality, development, hidden motives, moral character, identity, school/address, or causes of emotions from drawings.
- Provider failure, timeout, invalid schema, or policy failure must mutate zero canonical state.

The repository already contains:

```text
services/api/src/child_agent_api/observer.py
services/api/src/child_agent_api/providers/openai_compatible.py
```

`ObservationPipeline` validates provider output and supports one schema-only repair attempt. `OpenAICompatibleObserver` already provides a provider adapter example.

### Current integration gap

The internal service path already supports:

```text
ImageInput
→ ObservationPipeline
→ WorldStateService.observe_and_record(...)
```

but the public FastAPI boundary does **not yet expose a finished child-facing image upload endpoint** that performs:

```text
HTTP upload → ImageInput → live VLM → observation proposal → Core
```

The current drawing-revision API can consume a validated `ObservationBatch`. The integration owner should connect media ingestion/live VLM to this existing Core boundary rather than creating another canonical-state path.

---

## 4. Drawing revision handoff

For revision N+1, the integration layer should provide new observations for the new drawing. Core compares them against the current canonical world.

Example:

```text
Canonical R1
- 4 balloons

VLM observations for R2
- 4 balloons
- 1 dog
```

Core reconciliation should produce conceptually:

```text
balloons → unchanged → no need to ask again
dog      → added     → requires grounding
```

The integration/frontend layer should render the returned grounding prompts, but **must not calculate its own semantic diff**.

If the child confirms the dog, Core updates canonical world. If the child says it is actually a fox, use a `correct` decision with a supplied value; Core records it as child-supplied provenance.

---

## 5. Story provider contract

Story generation follows the same proposal/grounding rule as drawing observation.

The provider input is authoritative canonical state only:

```text
Canonical WorldState
+
Canonical StoryState
    ↓
StoryProvider
    ↓
StoryProviderResult
```

Do not build a story prompt directly from raw/unconfirmed VLM output.

Provider-neutral contract lives in:

```text
services/api/src/child_agent_api/story.py
```

Current `main` uses `DeterministicStoryProvider` by default. That implementation is intentional for tests and Core verification; production/demo integration still needs a real Story LLM adapter behind the same boundary.

A story provider returns a short proposal plus any canonical world dependencies it used. The proposal remains pending until the child accepts, corrects, or redirects it.

Conceptually:

```text
AI: 「大家帶著氣球往天空飛。」
        ↓ pending proposal
Child: 「不要，他們要飛去月亮。」
        ↓ redirect
Canonical story segment:
「他們飛去月亮。」
```

Only the grounded segment is used as story memory for later generation.

---

## 6. TTS / STT boundary

Current Core exposes:

```http
POST /v1/tts
```

TTS is rendering only:

```text
committed story/full-story text
→ TTS
→ audio playback
```

Playback must not create world/story events or advance state.

STT is optional. If implemented, speech should map to an existing Core action such as confirm/correct/redirect rather than creating a separate conversational state path. A readable/touch/text fallback should remain available for MVP reliability.

---

## 7. Core API surface for integration

Session / restore:

```http
POST /v1/sessions
GET  /v1/sessions/{session_id}/state
```

Drawing revision:

```http
POST /v1/sessions/{session_id}/drawing-revisions
GET  /v1/sessions/{session_id}/drawing-revisions/{revision_id}
POST /v1/sessions/{session_id}/drawing-revisions/{revision_id}/decisions
```

Story:

```http
GET  /v1/sessions/{session_id}/story
POST /v1/sessions/{session_id}/story/proposals
POST /v1/sessions/{session_id}/story/proposals/{proposal_id}/ground
GET  /v1/sessions/{session_id}/story/full
POST /v1/sessions/{session_id}/story/complete
```

Speech output:

```http
POST /v1/tts
```

For mutation endpoints, preserve the Core concurrency/retry contract:

```json
{
  "expected_state_version": 3,
  "idempotency_key": "unique-client-generated-key"
}
```

`expected_state_version` prevents stale clients from overwriting newer state. `idempotency_key` prevents retry/double-click from committing the same mutation twice.

On `409 state_conflict`, reload canonical state before retrying with a new valid action.

---

## 8. Integration invariants

These rules must remain true regardless of provider or UI choice:

1. VLM output is proposal-only; VLM cannot confirm itself.
2. Child correction/confirmation is authoritative.
3. Frontend does not own a duplicate canonical world/story state machine.
4. Story LLM reads canonical world + canonical story, not raw VLM output.
5. Revisions use Core reconciliation; unchanged facts are not re-asked by frontend logic.
6. Provider failure mutates zero canonical state.
7. TTS/playback is read-only.
8. STT, if used, maps to existing Core actions.
9. Secrets remain server-side.
10. Generated story image/video is not an MVP dependency.

---

## 9. Shared MVP acceptance scenario

Use one fixed R1/R2 scenario as the first local E2E integration test.

### R1

1. Child uploads the first drawing.
2. VLM proposes `4 balls`.
3. Child corrects `ball → balloon`.
4. Canonical world contains `4 balloons` with child-supplied provenance.
5. Story provider generates Story Proposal 1 from canonical world.
6. The proposal uses `balloon`, not the original `ball` observation.
7. Child redirects the story: `他們飛去月亮`.
8. Redirected text becomes the canonical story segment.

### R2

1. Child adds a dog to the original drawing and uploads R2.
2. VLM observes the current drawing.
3. Core reconciliation preserves the confirmed balloons as `unchanged` and surfaces the new dog as `added`.
4. Frontend asks only about the meaningful new change.
5. Child confirms the dog.
6. Canonical world now contains balloons + dog.
7. Next story proposal is generated from the newest world and existing canonical story.
8. The next segment must preserve the prior balloon correction and moon direction while incorporating the dog when appropriate.

### Complete

1. Child chooses to complete the story.
2. `POST /v1/sessions/{id}/story/complete` commits the lifecycle transition.
3. `GET /v1/sessions/{id}/story/full` contains only current, grounded canonical segments.
4. Pending, rejected, superseded, unconfirmed, or stale-invalidated content is absent.
5. Optional TTS can play the canonical full story without mutating state.
6. Refresh can still read `status: COMPLETE` from `GET /v1/sessions/{id}/state`.

This scenario is the first target for local/browser UAT before deployment hardening.

---

## 10. Definition of integration-ready MVP

The MVP is ready for team testing when one local browser session can complete this loop using real media and at least one live/sandbox model path:

```text
R1 upload
→ live VLM observation
→ child correction
→ real or approved demo StoryProvider
→ child story grounding
→ R2 upload
→ Core semantic reconciliation
→ child confirms meaningful change
→ next story reflects old + new canonical state
→ complete
→ canonical full story
→ optional audio playback
```

Deployment, animation, STT, generated illustrations, user accounts, long-term profiles, and production-scale infrastructure are not prerequisites for this local E2E milestone.

---

## 11. Useful source files

```text
services/api/src/child_agent_api/main.py
    FastAPI public boundary

services/api/src/child_agent_api/service.py
    WorldStateService and transactional state transitions

services/api/src/child_agent_api/domain/models.py
    Typed canonical contracts

services/api/src/child_agent_api/observer.py
    Provider-neutral observer + schema/policy boundary

services/api/src/child_agent_api/providers/openai_compatible.py
    Example live vision adapter

services/api/src/child_agent_api/story.py
    StoryProvider protocol + deterministic provider

services/api/src/child_agent_api/reconciliation.py
    added/changed/removed/unchanged/uncertain comparison and prompt selection

services/api/src/child_agent_api/providers/tts_elevenlabs.py
    Current TTS provider boundary

docs/DATA_CONTRACTS.md
    Detailed domain/data contracts
```

If integration work appears to require changing canonical semantics rather than only wiring media/providers/UI, coordinate that change with the Core owner instead of adding a parallel path.
