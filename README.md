# Child-Grounded Story Agent

> **不是讓 AI 替孩子完成故事，而是讓故事跟著孩子的畫、說法與修正持續改變。**

Child-Grounded Story Agent 是一個以兒童畫作作為持續互動介面的 AI 共創故事系統。AI 不把視覺模型的判斷直接當成事實，也不一次生成完整故事；它先提出「我看到了什麼」與「故事接下來可能怎麼走」，再讓孩子確認、修正、補充，甚至直接修改原本的畫作。

系統把孩子確認過的內容保存成 **canonical world state** 與 **canonical story state**。下一次 AI 觀察或生成故事時，只能從這些已確認的狀態繼續，因此孩子的修正會真正影響後續敘事，而不是只變成下一輪 prompt 裡的一句話。

## Hackathon 核心主張

很多 AI storytelling 系統是：

```text
Drawing → AI → Story
```

我們要做的是一個持續運作的 child-grounded closed loop：

```text
Drawing Revision N
        ↓
VLM Observation Proposal
        ↓
Child Grounding
確認 / 修正 / 略過
        ↓
Canonical World State
        ↓
Short Story Proposal
        ↓
Child Grounding
接受 / 修正 / 改寫 / 改畫
        ↓
Canonical Story State
        ↓
Optional TTS Story Audio
        ↓
Drawing Revision N+1 or Next Story Segment
        ↺
```

核心原則只有一句：

> **AI proposes; the child owns the world and story.**

## 為什麼不是「看圖生故事」

畫作不是一次性的 prompt，而是會持續變動的世界介面。

例如第一次 AI 把氣球看成球：

```text
AI observation: 4 balls
        ↓
Child correction: 不是球，是氣球
        ↓
Canonical world: 4 balloons
```

後面的故事只能使用 `balloon`。

之後孩子在原畫新增一隻狗，再上傳第二版：

```text
Drawing R1
- 4 people
- 4 balloons

Drawing R2
- 4 people
- 4 balloons
+ dog
```

系統不重新把整張圖當成全新故事，而是做 semantic reconciliation，保留已確認的氣球，只追問真正的新變化：

> 「我好像看到你新畫了一隻狗，是嗎？」

確認後，下一段故事才把狗帶進來。

## 兩層 Grounding

### Drawing grounding

VLM 只能建立 observation proposal，不能直接寫入 canonical world。孩子可以確認、修正、拒絕或略過。已確認且沒有改變的資訊不應每一輪重新詢問。

### Narrative grounding

Story Agent 每次只提出一小段 story proposal。孩子可以接受、修正故事細節、改寫發展，或直接修改畫作來改變世界。確認後才更新 canonical story state，再生成下一段。

## Hackathon MVP

比賽版不追求「生成一本完整故事書」，也不依賴生成故事圖片。只需要把以下閉回路跑穩：

1. AI 看畫並提出候選觀察。
2. 孩子可以糾正 AI，糾正會進入 canonical world state。
3. AI 從確認過的 world/story state 產生一小段故事。
4. 孩子可以接受、修正或改變故事方向。
5. 語音播放由 integration layer 決定是否使用 TTS，文字永遠可作為 fallback。
6. 孩子可以修改原畫再上傳。
7. 新畫作只找出 `added / changed / removed / unchanged / uncertain` 的語意變化。
8. 系統只詢問真正重要的新變化。
9. 下一段故事同時尊重先前修正與最新畫作變化。
10. Refresh / retry 不會遺失或重複已提交的狀態。
11. 最後可取得 canonical full story，供完整閱讀或播放。

不做的事情同樣重要：不從兒童畫作推論心理疾病、人格或隱藏動機；不把 AI observation 當成真相；不靠 generated illustration / video / animation 當主要賣點；不把黑客松 scope 擴張成帳號平台或長期兒童 profile。

## 2–3 分鐘 Demo 劇本

1. 上傳第一版畫作。
2. AI：「我看到四個人和四顆球，對嗎？」
3. 孩子：「不是球，是氣球。」
4. 系統顯示 `ball → balloon ✓`。
5. 第一段故事真的使用「氣球」。
6. 孩子修正一個故事發展，或在畫上新增一隻狗。
7. 上傳 Drawing Revision 2。
8. 系統只指出 `+ dog`，而不是重新詢問已確認的氣球。
9. 孩子確認狗。
10. 下一段故事出現狗，同時仍記得「氣球」與先前的故事修正。
11. 最後按下完整故事功能，取得由已確認片段組成的最終故事，並可交給 TTS 播放。

這個流程就是 hackathon 的主要 **wow moment**。

## 協作方式：Core first, Integration second

為避免前端、模型與 state logic 同時開發時互相踩 code，專案分成兩個責任層。

### Core logic

Core 已完成，且可在沒有真實 VLM、TTS、STT 和正式 UI 的情況下，用 deterministic fixtures / fake providers 驗證完整狀態流程。

Core 負責：

- session / event / version / idempotency；
- canonical world state；
- drawing revision；
- semantic reconciliation；
- selective grounding policy；
- canonical story state；
- narrative grounding；
- closed-loop orchestrator；
- provider-neutral contracts；
- FastAPI application/API boundary；
- persistence、migration 與 deterministic tests；
- canonical full-story projection。

Core **不負責**：畫面設計、真實圖片上傳、camera、實際 VLM SDK 選型、STT/TTS UX、音訊播放或部署 UI。

### Frontend & multimodal integration

Core contracts 穩定後，由 integration layer 接入：

- child-facing Web UI（目前採純 HTML/CSS/JS，同源由 FastAPI serve）；
- drawing upload / camera；
- live VLM adapter；
- Story LLM adapter；
- ElevenLabs 或其他 TTS（可自行選擇）；
- optional STT；
- audio playback / replay；
- loading/error/fallback UX；
- browser UAT。

Integration layer 的規則是：**providers sense or render; the core decides state.** 前端和 provider 都不能建立第二套 canonical truth。

## 開發順序與 Issues

目前的執行鏈為：

1. ✅ [#8 — MVP-04: Observer adapter, safety boundary and VLM benchmark harness](https://github.com/futuremodeokok/child/issues/8)  
   Observer boundary foundation，已由 [PR #9](https://github.com/futuremodeokok/child/pull/9) merge。

2. ✅ [#11 — CORE-01: Drawing revision, semantic reconciliation and selective grounding](https://github.com/futuremodeokok/child/issues/11)  
   Drawing/world core 已完成並 merge。

3. ✅ [#12 — CORE-02: Canonical story state, narrative grounding, orchestration and full-story projection](https://github.com/futuremodeokok/child/issues/12)  
   Story core 已完成並 merge。

4. 🚧 [#17 — INTEGRATION-01: Multimodal providers for VLM, TTS and optional STT](https://github.com/futuremodeokok/child/issues/17)  
   接真實 multimodal/story/speech providers；provider 不得改變 core state semantics。

5. 🚧 [#18 — INTEGRATION-02: Child-facing closed-loop demo UI](https://github.com/futuremodeokok/child/issues/18)  
   接前端、上傳、grounding interaction、完整故事播放與 browser UAT。前端實作已開始，後續仍以 Core API 為唯一 canonical truth。

6. ⏳ [#13 — RELEASE-01: Public demo deployment and hackathon hardening](https://github.com/futuremodeokok/child/issues/13)  
   最後處理 Railway、persistent state、正式 browser rehearsal 與 demo hardening。

## 專案目前狀態

### 目前已可運作的功能（`main`）

Core closed loop 已具備完整的狀態能力，現在不是只有 scaffold。

**Session 與一致性**

- 建立與恢復故事 session。
- SQLite + SQLAlchemy + Alembic persistence。
- immutable events、state version、optimistic concurrency 與 idempotency。
- refresh / retry 可重建同一份 canonical state，避免重複提交。

**Drawing / World Core**

- VLM/Observer 輸出只會形成 observation proposal，不會直接成為事實。
- 孩子可對 observation `confirm / correct / reject / skip`。
- 孩子的確認與修正會進入 canonical world state，並保留 provenance。
- 支援 Drawing Revision；新畫作不是新 session，而是同一個世界的下一版。
- semantic reconciliation 支援 `added / changed / removed / unchanged / uncertain`。
- selective grounding 只詢問需要孩子決定的變化，不重複詢問已確認且 unchanged 的內容。
- changed / removed canonical facts 會留下歷史與 invalidation semantics，而不是直接無痕覆寫。

**Story Core / Session-local Memory**

- StoryProvider 每次只產生一小段 provider-neutral story proposal。
- Story proposal 在孩子確認前不屬於 canonical story。
- 孩子可 `accept / correct / redirect` 故事內容；修正後的版本會成為後續故事依據。
- 「記憶」目前明確指同一 session 的 canonical world state + canonical story state，不做跨 session profile、embedding/vector memory 或心理推論。
- 畫作 world version 改變時，舊的 pending story proposal 會失效，不能把舊世界生成的內容提交到新世界。
- 若 canonical object 的語意 changed / removed，依賴舊語意的 story segment 可標成 stale，不再出現在 current full story。

**完整故事**

- `GET /v1/sessions/{session_id}/story/full` 可取得由 current、已確認 story segments 組成的 canonical full story。
- full story 會反映孩子的 correction / redirect，排除 rejected、superseded、unconfirmed 與 stale-invalidated 內容。
- full story 可在 refresh / persistence reconstruction 後保持一致。
- 前端可直接把這份 canonical text 用於「播放完整故事」，不需要自行維護第二套故事狀態。

**Audio / Web boundary**

- `POST /v1/tts` 已有 server-side TTS boundary，可回傳 `audio/mpeg`；實際語音 provider、播放 UX 與是否加入 STT 仍由 integration owner 決定。
- `apps/web` 目前為純 HTML/CSS/JS，由 FastAPI 同源 serve，不需要獨立 Node/Vite runtime。
- 前端只負責呈現與提交 API actions，不擁有 canonical state machine。

### 現在已能用 deterministic flow 證明的閉回路

```text
建立 Session
↓
Observation Proposal：4 balls
↓
孩子修正：ball → balloon
↓
Canonical World：4 balloons
↓
Story Proposal 1
↓
孩子 redirect：他們飛往月亮
↓
Canonical Story State 記住孩子版本
↓
Drawing Revision 2：+ dog
↓
Semantic Reconciliation：added dog
↓
孩子確認 dog
↓
舊 pending proposal 失效
↓
新 Story Proposal 從最新 World + 既有 Story State 繼續
↓
GET /story/full
↓
完整故事文字 → optional TTS playback
```

### 目前仍在整合

Core 已完成；剩下主要是把真實 multimodal I/O 與 demo UX 接到已穩定的 Core contracts：

- 真實 drawing upload / camera → VLM → Observer boundary 的完整路徑；
- production/demo Story LLM adapter；
- TTS 播放 UX，以及是否加入 STT；
- child-facing grounding / revision / story UI 的完整 closed-loop 串接；
- 完整故事播放按鈕與 replay；
- browser UAT、loading / retry / provider failure fallback；
- Railway 公開 deployment 與持久化設定。

## 系統邊界

```mermaid
flowchart LR
    UI["Child-facing Web"] --> API["FastAPI Core"]
    MEDIA["Drawing / Voice"] --> UI
    API --> OBS["Observer Adapter / VLM"]
    OBS --> API
    API --> STATE["Canonical World + Story State"]
    API --> STORY["Story Provider / LLM"]
    STORY --> API
    API --> TTS["Optional TTS Provider"]
    TTS --> UI
```

重要邊界：

1. **Observation is not fact**：VLM raw output 只能形成 proposal。
2. **Child authority**：孩子的 confirm/correct/supply 優先於模型判斷。
3. **State before generation**：Story Provider 只能把 canonical state 當成權威資料來源。
4. **Story is proposed, not imposed**：AI 逐段提出，孩子可以改。
5. **Revision is interaction**：修改原畫本身就是故事互動。
6. **TTS owns no story logic**：語音 provider 只負責 rendering audio。
7. Provider-specific SDK、payload、model name 與 secret 不進 domain model。
8. Web UI 不複製 canonical state machine，只呈現與提交 core API actions。

## 技術基線

- Web：純 HTML/CSS/JS（`apps/web`），無 build step，由 API 服務同源掛載 serve。
- API：Python 3.12、FastAPI、Pydantic。
- Persistence：SQLAlchemy、Alembic；本機 SQLite，公開部署可切 Railway persistent DB。
- AI boundaries：VLM Observer、Story LLM、TTS 都透過 provider adapter 隔離。
- Deterministic fallback：repository-owned synthetic fixtures，不依賴外部模型即可跑 regression / rehearsal。

VLM / story generation / ElevenLabs TTS 的能力已從獨立 `dev` branch 的 prototype 逐步重新接入目前的 FastAPI/domain boundary（見 `services/api/src/child_agent_api/providers/`）；是否作為最終 demo provider 由 #17 決定。

## 本機開發

需求：Python 3.12、[uv](https://docs.astral.sh/uv/)。不需要 Node.js——前端是純 HTML/CSS/JS。

```bash
make setup
uv run --project services/api alembic -c services/api/alembic.ini upgrade head
make dev-api
```

開啟 `http://localhost:8000`——FastAPI 會同源 serve `apps/web`（`index.html` + `style.css` + `app.js`），API 與前端共用同一個埠，不需要另開 terminal，也不會有 CORS 問題。

`ELEVENLABS_API_KEY`（若使用 ElevenLabs TTS）等 secrets 放在 repo 根目錄的 `.env`，啟動時會自動載入。

完整 deterministic checks：

```bash
make check
```

## 部署方向

- Web + API：以 **Railway** 為 hackathon-first runtime，同一個服務，由 FastAPI 掛載靜態前端一併 serve，避免額外處理 CORS 與多平台管理成本。
- Persistent state：先依 demo 需求決定 SQLite + Railway Volume 或 Railway Postgres；不把換 DB 當成核心功能。
- Drawing / audio：MVP 不要求永久媒體儲存；需要保留時再接 private / short-lived object storage。
- Secrets：只放 server-side environment variables（Railway Variables）。

最終 hosting / storage 選型以 [#13](https://github.com/futuremodeokok/child/issues/13) 的實際 deployment evidence 為準。

## 文件導覽

- [Concept](docs/CONCEPT.md)
- [Product spec](docs/PRODUCT_SPEC.md)
- [Technical design](docs/TECHNICAL_DESIGN.md)
- [Data contracts](docs/DATA_CONTRACTS.md)
- [Agent policy](docs/AGENT_POLICY.md)
- [Safety and privacy](docs/SAFETY_PRIVACY.md)
- [Demo and evaluation](docs/DEMO_EVALUATION.md)
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md)
- [Prior art](docs/PRIOR_ART.md)

## 一句話版本

> **AI 不一次決定完整故事，而是逐段提出畫作理解與故事發展；孩子透過確認、修正、語音／文字補充或直接修改畫作持續改變世界，系統再依孩子確認過的狀態繼續說下去。**