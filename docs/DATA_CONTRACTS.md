# Data and API contracts

_Status: Session/world-state subset implemented; story/API sections proposed_
_Last reviewed: 2026-08-29_

This document defines domain boundaries. Examples are illustrative JSON, not a committed OpenAPI schema. The first implementation issue should convert accepted contracts into Pydantic models and generated API documentation.

## 1. Provenance vocabulary

| Source | Meaning | May become canonical fact? |
|---|---|---|
| `model_observation` | Vision or language model proposal | Only after an explicit safe promotion rule or confirmation |
| `child_confirmed` | Child accepted a specific proposal | Yes |
| `child_supplied` | Child introduced or corrected the value | Yes |
| `adult_setup` | Adult provided session/accessibility setting | Yes, within that scope |
| `story_derived` | Story engine derived a temporary state from prior facts/actions | Yes, with dependency references |
| `system_default` | Product default | Yes, but never as child meaning |

`confidence` represents model uncertainty, not confidence in the child. Child-confirmed or child-supplied facts do not receive a probabilistic truth score.

## 2. Session

```json
{
  "session_id": "ses_01",
  "status": "GROUNDING",
  "state_version": 4,
  "profile": {
    "display_name": "小星",
    "text_length": "short",
    "bopomofo": false,
    "choice_count": 2,
    "speech_rate": "slow",
    "repeat_prompt": true
  },
  "drawing": {
    "media_id": "med_01",
    "mime_type": "image/png",
    "width": 1280,
    "height": 960
  },
  "created_at": "2026-08-29T04:00:00Z",
  "expires_at": "2026-08-30T04:00:00Z"
}
```

Do not put diagnosis labels, public media URLs or provider credentials in this object.

## 3. Observation batch

```json
{
  "schema_version": "observation.v1",
  "batch_id": "obsb_01",
  "media_id": "med_01",
  "items": [
    {
      "observation_id": "obs_01",
      "kind": "object_count",
      "candidate": {"label": "ball", "count": 4},
      "confidence": 0.67,
      "needs_confirmation": true,
      "evidence_note": "four round shapes near the figures",
      "status": "proposed",
      "source": "model_observation"
    }
  ],
  "model_meta": {
    "provider": "adapter-name",
    "model": "model-name",
    "prompt_version": "observer.v1"
  }
}
```

Allowed `status`: `proposed`, `confirmed`, `rejected`, `corrected`, `expired`.

The observer may describe visible features but must not output diagnosis, personality assessment or hidden motive fields.

## 4. Grounding question and answer

```json
{
  "question_id": "q_01",
  "targets": ["obs_01"],
  "kind": "confirm_or_correct",
  "prompt": "這些圓圓的是四顆球嗎？",
  "options": [
    {"option_id": "yes", "label": "對，是四顆球"},
    {"option_id": "no", "label": "不是，我來告訴你"}
  ],
  "allows_free_input": true
}
```

```json
{
  "answer_id": "ans_01",
  "question_id": "q_01",
  "action": "correct",
  "selected_option_id": "no",
  "supplied_value": {"label": "balloon", "count": 4},
  "input_mode": "touch",
  "idempotency_key": "client-generated-uuid"
}
```

Allowed `action`: `confirm`, `reject`, `correct`, `skip`. A skipped high-semantic item cannot silently become confirmed.

## 5. World state

```json
{
  "schema_version": "world.v1",
  "session_id": "ses_01",
  "version": 5,
  "characters": [
    {
      "character_id": "char_01",
      "name": "小明",
      "attributes": {},
      "provenance": {
        "source": "child_supplied",
        "source_ref": "ans_02"
      }
    },
    {
      "character_id": "char_02",
      "name": "朋友",
      "attributes": {},
      "provenance": {
        "source": "child_supplied",
        "source_ref": "ans_02"
      }
    }
  ],
  "objects": [
    {
      "object_id": "obj_01",
      "type": "balloon",
      "count": 4,
      "provenance": {
        "source": "child_supplied",
        "source_ref": "ans_01"
      }
    }
  ],
  "relationships": [],
  "facts": [
    {
      "fact_id": "fact_01",
      "subject_ref": "char_02",
      "predicate": "is_sad",
      "value": true,
      "provenance": {
        "source": "child_confirmed",
        "source_ref": "ans_03"
      },
      "depends_on": []
    }
  ],
  "stale_fact_ids": []
}
```

Corrections create a new state version. Any `story_derived` fact whose `depends_on` includes a corrected fact becomes stale before the next scene.

## 5.1 Drawing revisions and reconciliation

A drawing revision stores its order within the session, the canonical world version it was
reconciled against, and the validated `ObserverPayload` that produced its candidates. Revision
ingress uses the same kind-discriminated allowlist as the observer adapter; clients cannot send
canonical status, source, identity, or provenance fields through this route.

Reconciliation classifies proposals as `added`, `changed`, `removed`, `unchanged`, or
`uncertain`. Confirmed exact matches remain unchanged and are not asked again. At most five
unresolved candidates become grounding prompts. Visible `object` and `object_count` proposals
may be confirmed directly. `character`, `fact`, and `relationship` observations do not contain
enough canonical identity/reference data, so they allow only child correction/supply, rejection,
or skip.

Resolving a revision accepts `confirm`, `correct`, `reject`, and `skip` decisions. A correction
uses an allowlisted canonical value and child-supplied provenance. Rejection and skip do not
promote model output. Removal retains a tombstone identifier and immutable event history rather
than erasing provenance. A successful resolution advances the canonical world exactly once;
duplicate retries return the stored result. If the current world no longer equals the revision's
base version, the revision becomes `superseded` with no world or event effect, after which a new
revision may be submitted against the current version.

Core revision routes are:

- `POST /v1/sessions/{id}/drawing-revisions`
- `GET /v1/sessions/{id}/drawing-revisions/{revision_id}`
- `POST /v1/sessions/{id}/drawing-revisions/{revision_id}/decisions`

## 6. Story plan, scene and choice

```json
{
  "plan_id": "plan_01",
  "world_version": 5,
  "goal": "explore responding to a sad friend",
  "beats": [
    {"beat_id": "beat_01", "purpose": "setup"},
    {"beat_id": "beat_02", "purpose": "choice"},
    {"beat_id": "beat_03", "purpose": "consequence"},
    {"beat_id": "beat_04", "purpose": "reflection"},
    {"beat_id": "beat_05", "purpose": "resolution"}
  ],
  "allowed_fact_ids": ["fact_01"],
  "status": "active"
}
```

```json
{
  "scene_id": "scene_02",
  "beat_id": "beat_02",
  "state_version": 7,
  "narration": "小明看到朋友低著頭。",
  "render": {
    "background": "playground",
    "characters": ["char_01", "char_02"],
    "actions": [{"actor": "char_02", "verb": "look_down"}]
  },
  "interaction": {
    "type": "choice",
    "prompt": "你想怎麼做？",
    "choices": [
      {"choice_id": "choice_help", "label": "問問他還好嗎"},
      {"choice_id": "choice_laugh", "label": "笑他沒投進"}
    ]
  }
}
```

A choice submission includes `choice_id`, `scene_id`, `expected_state_version`, `idempotency_key` and optional child free input.

## 7. Consequence proposal

```json
{
  "schema_version": "consequence.v1",
  "choice_id": "choice_laugh",
  "state_delta": [
    {
      "op": "add_fact",
      "fact": {
        "subject_ref": "char_02",
        "predicate": "wants_to_play",
        "value": false,
        "provenance": {
          "source": "story_derived",
          "source_ref": "choice_laugh"
        },
        "depends_on": ["fact_01"]
      }
    }
  ],
  "narration": "朋友變得更安靜，暫時走到旁邊。",
  "reflection": {
    "prompt": "他好像更安靜了，你覺得發生了什麼？",
    "allows_rechoice": true
  },
  "safety": {"route": "allow", "reason_code": null}
}
```

The application validates references, allowed operations, text length, dependency rules and safety before applying the delta.

## 8. Event log

Store immutable events and derive snapshots transactionally.

```json
{
  "event_id": "evt_09",
  "session_id": "ses_01",
  "sequence": 9,
  "event_type": "CHILD_CHOICE_ACCEPTED",
  "state_version_before": 7,
  "state_version_after": 8,
  "actor": "child",
  "payload_ref": "choice_laugh",
  "created_at": "2026-08-29T04:10:00Z"
}
```

Payloads containing child text should follow the retention/redaction policy in [SAFETY_PRIVACY.md](SAFETY_PRIVACY.md).

## 9. API surface draft

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/sessions` | Create setup/profile |
| `POST` | `/v1/sessions/{id}/drawing` | Validate and attach one drawing |
| `GET` | `/v1/sessions/{id}/next` | Get current child-facing action or scene |
| `POST` | `/v1/sessions/{id}/answers` | Submit grounding answer |
| `POST` | `/v1/sessions/{id}/choices` | Submit story choice |
| `POST` | `/v1/sessions/{id}/retry` | Retry current recoverable step |
| `GET` | `/v1/sessions/{id}/summary` | Get non-diagnostic ending summary |
| `DELETE` | `/v1/sessions/{id}` | Delete session data and media |

All mutation endpoints require an idempotency key. State-dependent requests include `expected_state_version`; conflicts return the current version without applying the stale mutation.

## 10. Contract evolution

- Every stored aggregate and model output carries `schema_version`.
- Additive optional fields may remain within a version; semantic changes require a new version.
- Provider payloads are converted at adapter boundaries and never stored as the canonical contract.
- Schema migration tests must prove old session fixtures can either load or fail with an explicit unsupported-version message.
