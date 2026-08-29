# Child safety and privacy baseline

_Status: Required baseline_  
_Last reviewed: 2026-08-29_

This document is a product and engineering baseline for the prototype. It is not a claim of legal, clinical or regulatory compliance. Any public deployment with real children requires review appropriate to the deployment region, institution, data flow and model providers.

## 1. Product boundary

The system is a guided creative and social-situation exploration tool. It is not:

- a psychological assessment;
- a diagnostic or screening tool;
- therapy, crisis counseling or medical advice;
- a behavior score for children;
- a substitute for a parent, teacher or qualified professional.

Do not infer mental state, trauma, family condition, diagnosis or risk level from color, line pressure, composition, character size or other drawing features.

## 2. Adult involvement

- An adult initiates the session and sees the purpose, data use and delete action.
- The child-facing interface uses a nickname, not a required legal name.
- The adult can pause or end the session at any time.
- A public demo should use synthetic fixtures unless explicit consent and the approved data path are both available.

## 3. Data minimization

Collect only what the session needs:

- one drawing;
- minimal accessibility settings;
- confirmation answers and story choices;
- operational metadata needed for reliability.

Do not collect by default:

- legal name, birthday, school, address or contact information;
- diagnosis or health history;
- continuous camera/microphone recordings;
- location;
- unrelated chat history;
- biometric identification.

Free input should be bounded and the UI should discourage entering real names, school names, addresses or contact details.

## 4. Retention and deletion

MVP baseline:

- Give every session an expiry.
- Store original media privately and separately from application logs.
- Delete media, transcripts and derived child content when the session expires or the adult requests deletion.
- Keep only aggregated, non-identifying operational metrics when possible.
- Do not use child content for model training, demos or publications without a separate explicit approval process.
- Verify whether third-party providers retain or train on submitted data before sending real child content.

Deletion must cover database rows, media objects, caches and queued jobs. A successful UI message cannot be shown until deletion is confirmed or clearly queued with status.

## 5. Access and logging

- Server-side secrets only; never expose provider API keys to the browser.
- Media URLs are private, expiring and unguessable.
- Separate operator/debug views from child-facing UI.
- Do not log raw image bytes, raw audio, full transcript or prompt by default.
- Redact child free text from error tracking unless a reviewed debugging mode explicitly requires it.
- Use synthetic drawings and names in tests.

## 6. Content risk handling

| Signal | Default route | Child-facing behavior | Adult signal |
|---|---|---|---|
| Mild fictional conflict or sadness | `allow` / `redirect` | Keep consequence bounded and offer reflection | No automatic escalation |
| Graphic violence, sexual content or dangerous instruction request | `block` / `redirect` | Decline detail and move to a safe scene | Optional notice in active adult session |
| Child shares sensitive personal information | `redirect` | Ask not to share private details; return to story | Mark for deletion/redaction |
| Possible abuse, self-harm or immediate danger disclosure | `pause_for_adult` | Calmly encourage contacting a trusted nearby adult; stop open-ended story generation | High-priority adult action flag |
| Model tries to diagnose or psychologically interpret drawing | `block` | Replace with neutral observation/clarification | Record policy failure |

The system must not conduct an interrogation, promise secrecy, investigate allegations or improvise emergency instructions. Exact escalation copy and regional support information require separate expert and legal review before production use.

## 7. Narrative guardrails

- No erotic or sexual content involving children.
- No graphic injury, cruelty, self-harm details or realistic dangerous challenges.
- No shame, humiliation, threats of abandonment or divine/legal punishment as a teaching mechanism.
- No stereotyping based on disability, gender, culture, family structure or appearance.
- No persuasive request to keep secrets from trusted adults.
- No encouragement to meet, contact or share information with strangers.
- Avoid turning a single social choice into a permanent label about the child.

## 8. Drawing interpretation guardrails

Allowed:

-「我好像看到兩個人的嘴巴形狀不一樣。」
-「這個人是在哭嗎？你可以告訴我。」

Not allowed:

-「畫得比較大代表他控制你。」
-「你一直用黑色，所以你很憂鬱。」
-「這張畫顯示你有某個障礙。」

The observer schema should not contain diagnosis, personality or hidden-motive fields, making these outputs invalid by construction rather than relying only on prompt wording.

## 9. Threat model

Minimum risks to test:

- Prompt injection embedded in uploaded-image text or child free input.
- Model output containing remote URLs, HTML or executable content.
- Public or long-lived drawing URLs.
- Cross-session state leakage.
- Duplicate requests creating repeated choices or provider charges.
- Operator debug endpoints exposing child content.
- A correction failing to invalidate a harmful or false derived story fact.

Mitigations include strict schemas, allowlisted render assets, session authorization, private media storage, idempotency, state versions, output escaping and redacted logs.

## 10. Release gate

Before showing the prototype to real children, verify:

- [ ] Adult-facing purpose, consent and delete flow are present.
- [ ] Media and transcripts have an explicit retention policy.
- [ ] Provider data-use settings have been reviewed.
- [ ] Child-facing UI cannot expose raw model/debug content.
- [ ] Safety golden cases pass for every active model/provider.
- [ ] Cross-session isolation and deletion are tested.
- [ ] A responsible adult is present and knows how to pause the session.
- [ ] Claims and presentation avoid diagnosis, treatment and guaranteed learning outcomes.

