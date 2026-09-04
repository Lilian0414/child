# Implementation plan

_Status: Hackathon roadmap_  
_Last reviewed: 2026-09-04_

## 1. Delivery principle

The hackathon build is not a general AI storybook generator. The target is one reliable, stateful closed loop:

```text
Drawing
  → Observer proposal
  → Child grounding
  → Canonical world
  → Short story proposal
  → TTS
  → Child correction / drawing revision
  → State update
  → Next story segment
  ↺
```

The product succeeds when the child can visibly change what the AI believes and what the story does next.

Do not add generated story visuals, video, animation, long-form open chat, accounts, long-term child profiles or multi-agent orchestration before this loop is complete.

## 2. Current repository state

### Completed

- MVP-01: repository scaffold and developer loop.
- MVP-02: typed session/world-state core, persistence, events, provenance, idempotency and versioning.
- MVP-03: deterministic browser vertical slice, ball → balloon correction, stateful story choices and refresh recovery.

### Active prerequisite

- [Issue #8 — MVP-04: Observer adapter, safety boundary and VLM benchmark harness](https://github.com/futuremodeokok/child/issues/8)
- [PR #9](https://github.com/futuremodeokok/child/pull/9)

MVP-04 remains the provider-neutral VLM boundary. Its scope should not grow to include drawing revisions, story generation or TTS. Finish and merge it before the next implementation issue.

## 3. Ordered Hackathon backlog

Dependent issues are implemented sequentially. One coherent task gets one implementation writer.

### MVP-05 — Drawing revision closed loop and selective grounding

GitHub: [Issue #11](https://github.com/futuremodeokok/child/issues/11)

**Depends on:** MVP-04 / Issue #8.

**Goal**

Turn the drawing into a revisable state interface rather than a one-shot prompt.

**Scope**

- Represent Drawing Revision N / N+1 within one session.
- Reconcile new structured observations against canonical world state.
- Produce bounded semantic change candidates: `added`, `changed`, `removed`, `unchanged`, `uncertain`.
- Ask only about meaningful unresolved changes.
- Preserve child-confirmed unchanged facts without re-asking them.
- Apply normal provenance, events, idempotency, stale-version and dependency invalidation rules.
- Demonstrate R1 → grounding → R2 → selective grounding → World v2 in browser/fixture UAT.

**Non-goals**

- Story generation/state.
- TTS/STT.
- Pixel-diff/image-registration research.
- Production media storage.
- Generated visuals.

**Acceptance wow moment**

R1 confirms four balloons. R2 adds a dog. The system asks only about the dog, confirms it, and keeps the already-confirmed balloons without resetting the session.

### MVP-06 — Incremental story state, narrative grounding and TTS loop

GitHub: [Issue #12](https://github.com/futuremodeokok/child/issues/12)

**Depends on:** MVP-05 / Issue #11.

**Goal**

Make story generation incremental and child-authoritative.

**Scope**

- Add minimal canonical story state.
- Add provider-neutral Story Provider boundary.
- Generate one short story segment at a time from canonical world/story state.
- Let the child accept, correct or redirect a proposal.
- Make the next segment respect the accepted correction.
- Integrate TTS behind a provider-neutral boundary.
- Use the existing `dev`-branch ElevenLabs spike only as reference; do not merge unrelated branch history.
- Demonstrate at least two short story segments plus one child correction and one later drawing revision affecting a subsequent segment.

**Non-goals**

- Full voice-only UX.
- Continuous microphone / voice biometrics.
- Generated story images/video.
- Long-form autonomous storytelling.
- Multi-agent framework.

**Acceptance wow moment**

The first audio says “balloon”, the child changes a story detail, then a later confirmed `+ dog` drawing revision appears in the next audio without reverting any earlier correction.

### MVP-07 — Public demo deployment and hackathon hardening

GitHub: [Issue #13](https://github.com/futuremodeokok/child/issues/13)

**Depends on:** MVP-05 and MVP-06.

**Goal**

Ship one reliable public HTTPS demo and rehearse the exact 2–3 minute closed-loop scenario.

**Scope**

- Deploy the React web app.
- Deploy FastAPI on the smallest reliable backend shape.
- Replace production-local SQLite assumptions with external persistent storage.
- Add bounded/private/temporary media handling if real uploads are enabled.
- Keep secrets server-side only.
- Add audio replay, loading/recoverable error states and duplicate-submission protection.
- Preserve deterministic fixture mode as a clearly labelled fallback.
- Record exact deployed SHA, CI status, UAT URL and rough provider latency.

**Preferred deployment direction**

- Web: Vercel.
- API: Vercel-compatible FastAPI if reliable enough; otherwise a small external backend.
- State: external Postgres.
- Media: private/short-lived object storage only if the public demo truly needs real image/audio persistence.

**Non-goals**

- Production scale.
- Accounts/social features.
- Analytics/long-term child profiles.
- Decorative animation.
- Native apps.

**Acceptance wow moment**

The full closed loop runs twice on the deployed build without state loss, duplicate events or fallback to a previously corrected fact.

## 4. Canonical hackathon rehearsal

The implementation should always optimize for this one demo path:

1. Start a session.
2. Observe initial drawing.
3. AI proposes four balls.
4. Child corrects them to four balloons.
5. Canonical world stores balloons.
6. Story Segment 1 is generated and played in audio using balloons.
7. Child redirects one story detail.
8. Canonical story state stores the correction.
9. Child submits Drawing Revision 2 with a new dog.
10. Reconciliation identifies only the meaningful `+ dog` change.
11. Child confirms the dog.
12. Next story audio includes the dog and still respects balloons + prior story correction.
13. Refresh/retry restores the same committed state.

If this path is not stable, do not add more features.

## 5. Decision gates

| Decision | Minimum evidence | Needed before |
|---|---|---|
| Active VLM configuration | Synthetic benchmark, schema validity, latency, policy behavior | Finish MVP-04 |
| Story provider | Strict output contract + deterministic tests + one live smoke test if credentials exist | MVP-06 live integration |
| TTS provider | Browser playback + failure fallback | MVP-06 completion |
| Public persistence | Deployment compatibility and migration test | MVP-07 |
| Media storage | Only if public real-image upload is required | MVP-07 |

Do not hard-code provider-specific fields into canonical domain models.

## 6. Deferred after hackathon MVP

These are intentionally **not** blockers for the competition build:

- generated story illustration/video;
- continuous speech interaction;
- full STT conversation;
- authentication/accounts;
- long-term child profiles or personalization;
- analytics dashboards;
- production-scale deletion/retention platform;
- multi-agent frameworks;
- native mobile app;
- long-form open-ended story engine.

## 7. Definition of done per issue

- Scope and non-goals are respected.
- Repository-native lint/type/test/build checks pass.
- New behavior has deterministic unit/contract/integration evidence where practical.
- Failure paths preserve state.
- No secrets or real child data are committed.
- Commit SHA and exact verification results are reported.
- Implementation complete, PR available, CI green, UAT passed and merged are reported separately.

## 8. Work order

Current order is strict:

1. Finish/review/merge MVP-04 / Issue #8 / PR #9.
2. Implement MVP-05 / Issue #11.
3. Implement MVP-06 / Issue #12.
4. Implement MVP-07 / Issue #13.

Do not begin a dependent issue while the previous one still has unresolved correctness findings.
