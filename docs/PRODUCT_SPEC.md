# MVP product specification

_Status: Proposed_  
_Last reviewed: 2026-08-29_

## 1. Scope

本規格定義一個約 5–8 分鐘、可在單一裝置完成的 Hackathon session。MVP 只需處理一張畫作、建立一個短篇世界並跑通兩次選擇；長期帳號、跨日記憶、老師 dashboard 與臨床用途不在範圍內。

## 2. Users and jobs

| User | 想完成的事 | MVP 權限 |
|---|---|---|
| Child | 讓 AI 理解自己的畫、共同決定故事並探索選擇 | 確認、否定、補充、選擇、重選、結束 |
| Adult facilitator | 設定互動負擔、協助開始與處理中斷 | 建立 session、設定 profile、重新播放、結束 session |
| Demo operator | 穩定展示核心 loop 與分支差異 | 使用 synthetic fixture、查看非敏感 debug status |

## 3. Primary user story

> 作為孩子，我想先告訴 AI 我的畫裡真正發生什麼，再讓故事依我的回答和選擇繼續，這樣故事是我的，而不是 AI 猜出來的。

## 4. Functional requirements

### FR-01 Adult setup

- 可建立一次性 session。
- 可設定孩子暱稱、文字長度、注音、提示形式、選項數量與語音速度。
- 診斷名稱不得成為生成或評分規則。

### FR-02 Drawing input

- 接受一張 JPEG、PNG 或 WebP 畫作。
- 上傳前顯示用途與刪除方式。
- 檔案格式、大小或解碼失敗時提供可恢復錯誤，不建立半成品 world state。

### FR-03 Uncertainty-aware observation

- Observer 產生 3–6 個候選 observation。
- 每筆包含 type、candidate value、confidence、needs_confirmation、evidence note 與 provenance。
- 人物關係、情緒原因與心理意義不得只靠 vision output 寫成 fact。

### FR-04 Child grounding

- 每次只顯示一個問題，或一小組可同時理解的低負擔項目。
- 孩子可確認、否定、選擇替代答案或自由補充。
- 至少支援一次「AI 猜錯 → 孩子修正 → 後續採用修正」的完整路徑。
- 問題數預設 2–5 題；資訊足夠時應停止追問。

### FR-05 Canonical world state

- Session 維持單一 canonical world state。
- 每個 fact 都記錄 source 與建立／更新時間。
- 更正上游 fact 時，依賴該 fact 的 story plan 或 derived state 必須失效或重新計算。

### FR-06 Story start

- Story planner 僅使用 child-confirmed、child-supplied 或明確允許的低風險 observation。
- 產生 3–5 個 story beats 的短篇 plan，不一次暴露完整結局。
- 第一個 scene 必須可追溯到孩子畫作中的角色或物件。

### FR-07 Choice and consequence

- 至少兩個 scene 要求孩子做選擇。
- 每次選擇後更新 story state，再產生 consequence。
- 至少一個 choice 的不同選項會改變後續 scene state，不只是換句話說。
- 後果要有限、兒童可理解且可恢復；不使用羞辱、恐嚇或過度懲罰。

### FR-08 Reflection and re-choice

- consequence 後提供一個短問題，例如「你覺得他現在怎麼了？」或「你想繼續，還是試試別的方法？」
- 孩子可以保留原選擇、重選或結束，不強迫選到預設答案。

### FR-09 Ending

- 顯示原始畫作、故事標題、使用過的角色／元素與關鍵選擇。
- 產生非評分式回顧，不顯示道德分數、情緒能力分數或診斷結論。
- Session 可由成人刪除；MVP 預設不建立跨日兒童 profile。

### FR-10 Failure recovery

- Model timeout、invalid output 或 safety block 不得破壞已確認 world state。
- 可重試目前步驟，但不得重複寫入同一 child answer 或 choice。
- 重整頁面後，可從最近一次已提交 state 恢復。

## 5. Interaction requirements

- 主要操作按鈕應有圖示與短文字，不只靠顏色表示。
- 每個畫面只有一個主要任務。
- 孩子可要求重播、重說或返回上一個尚未產生後果的確認題。
- 自由輸入不是唯一方式；核心流程必須可用點選完成。
- 語音是 accessibility enhancement，不應成為跑通核心 demo 的單點失敗。
- Debug confidence、raw prompt 與模型錯誤不得顯示在 child-facing UI。

## 6. MVP acceptance criteria

| ID | 驗收條件 | 證據 |
|---|---|---|
| AC-01 | 處理一張真實或經同意的兒童畫作 | UAT recording / operator log |
| AC-02 | Observation 與 confirmed fact 在 schema 明確分離 | Contract test + state snapshot |
| AC-03 | AI 至少一次表達不確定並詢問孩子 | Golden conversation |
| AC-04 | 孩子修正模型後，故事採用修正值 | Integration test + demo |
| AC-05 | World state 跨至少 3 個 scene 一致 | State-transition test |
| AC-06 | 至少 2 次選擇，且 1 次造成真正分支 | Branch comparison test |
| AC-07 | 非理想選擇產生 consequence + reflection，無答錯標記 | UAT + copy review |
| AC-08 | Timeout / invalid model output 可重試且不重複事件 | Failure-path test |
| AC-09 | 不產生心理／醫療診斷 | Safety test suite |
| AC-10 | Canonical demo 可在目標時間內完成 | 3 次 rehearsal median |

## 7. Non-functional targets

這些是 Hackathon 目標，不是目前已達成的數據：

- 一般互動回合 p50 < 4 秒、p95 < 10 秒；超時時先顯示進度與可重試狀態。
- 同一 session 的 state mutation 具 idempotency key。
- Model JSON schema validation 通過後才能寫入 canonical state。
- Child-facing event 不包含 raw model prompt、provider error 或內部 confidence。
- Demo fixture 即使外部模型暫時不可用，也能展示 UI 與 deterministic state transition；正式展示時必須清楚標示 fixture mode。

## 8. Explicit non-goals

- 心理衡鑑、疾病分類、危機諮商或治療建議。
- 對孩子做隱性性格、道德或能力評分。
- 自動向家長產生心理解讀報告。
- 長期保存兒童影像與逐字稿。
- 開放式無限聊天、多人社交或公開分享。
- 即時生成完整影片。

## 9. Open product decisions

- 成人同意與刪除入口由誰操作、在 demo 中如何呈現。
- 注音採 client-side conversion、預先字典或模型輸出後驗證。
- 自由語音是否列入第一版，或只做按鈕選擇 + 文字補充。
- Reflection 是否只回到故事，或允許成人在 session 後查看非診斷式摘要。

未決項不能被 README 或 UI 文案描述成已完成。

