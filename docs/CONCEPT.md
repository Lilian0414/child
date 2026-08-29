# Project Concept — Child-Grounded Story Agent

_Last reviewed: 2026-08-29_

## 1. 一句話題目

**讓 AI 先向孩子理解他的畫，再把孩子自己定義的世界變成可以做選擇、看見後果的互動故事。**

英文暫定：

> **Child-Grounded Story Agent: Interactive social-situation exploration from children's own drawings**

## 2. 問題

兒童畫作很容易成為故事與對話的起點，但現有生成式 AI 很容易把「模型看到的東西」直接當成「孩子真正想表達的意思」。

例如 AI 可能看見嘴角向下、紅色線條、人物大小差異，就自行推論人物在難過、生氣，甚至進一步替孩子解釋原因。對兒童、尤其語言表達或閱讀能力差異較大的使用者，這種錯誤解讀會讓互動失去孩子本人的主體性，也可能把不可靠的心理推論包裝成事實。

本專案的核心問題因此不是「AI 能不能從一張畫生成故事」，而是：

> **AI 能不能先承認自己不知道，透過孩子的確認建立一個可靠的故事世界，再用這個世界陪孩子探索不同選擇的結果？**

## 3. 設計原則

### 3.1 Observation ≠ Fact

Vision model 的輸出先記為 `observation`，包含內容與 confidence。

例如：

```json
{
  "observation": "four round objects",
  "candidate_label": "balls",
  "confidence": 0.67,
  "needs_confirmation": true
}
```

孩子確認之後，才成為 story world 的 `fact`。

### 3.2 Meaning belongs to the child

低階、較客觀的視覺資訊可以由模型提出候選：

- 人物數量
- 物件數量
- 顏色
- 大致位置
- 可見的表情線索

高階語意原則上要詢問孩子：

- 「這是誰？」
- 「他是在哭嗎？」
- 「他為什麼哭？」
- 「他們是朋友嗎？」
- 「剛剛發生了什麼？」

尤其禁止把顏色、人物大小、構圖等直接轉成心理或臨床判讀。

### 3.3 Consequence, not correctness

孩子遇到情境時可以做選擇，但系統不立即把選項分成「正確／錯誤」。

例如：

```text
朋友投球失敗正在哭。

孩子選擇：笑他。
        ↓
故事狀態更新：朋友更難過，暫時不想一起玩。
        ↓
Agent：
「他好像變得更難過了。你覺得發生了什麼？」
        ↓
孩子可以繼續原本做法，也可以換方法。
```

這讓互動成為情境探索，而不是選擇題測驗。

## 4. 目標使用者

Hackathon MVP 可先聚焦約 7–10 歲兒童。

系統不直接建立「ADHD mode」「autism mode」等診斷分類。由家長／老師設定互動需求，例如：

```text
文字長度：短
注音：開
圖片提示：多
單題選項：2
語音速度：慢
需要重複提示：是
```

這些設定形成 accessibility profile，讓 Agent 調整語言與互動負擔。

## 5. 使用流程

### Step 0 — Adult setup

父母或老師可設定：

- 孩子暱稱
- 閱讀／語言難度
- 注音需求
- 選項數量
- 語音速度
- 可選的互動目標，例如同理、情緒辨識、合作、衝突處理

### Step 1 — Drawing observation

孩子上傳畫作。

VLM 只產生：

- candidate objects
- candidate people
- visible attributes
- spatial relationships
- confidence
- uncertainties

### Step 2 — Child grounding

Agent 選擇最值得確認的 2–5 個項目，不要把所有模型辨識結果一次塞給孩子。

例：

> 「我好像找到四個人，是四個嗎？」

> 「這幾個圓圓的是球嗎？還是別的東西？」

> 「這兩個人的表情不太一樣，他們在做什麼呢？」

孩子可以：

- 確認
- 否定
- 修改
- 用語音補充

### Step 3 — Build child-authored world state

範例：

```json
{
  "characters": [
    {"id": "c1", "name": "小明", "source": "child"},
    {"id": "c2", "name": "朋友A", "source": "child"}
  ],
  "objects": [
    {"type": "ball", "count": 4, "source": "child_confirmed"}
  ],
  "events": [],
  "emotions": [
    {"character": "c2", "emotion": "sad", "source": "child_confirmed"}
  ],
  "constraints": [
    "Do not change child-confirmed identities without asking"
  ]
}
```

### Step 4 — Story planning

Agent 使用 world state 規劃短故事，不一次生成完整長篇。

建議 3–5 個 story beats：

```text
Setup
→ event
→ child choice
→ consequence
→ reflection / second choice
→ resolution
```

### Step 5 — Child choice and consequence simulation

每次孩子選擇後：

1. 驗證是否違反已確認 world state。
2. 推演一個兒童可理解、低風險的自然後果。
3. 更新 story state。
4. 決定下一個 scene 或 reflection question。

### Step 6 — Ending

故事結束時可顯示：

- 孩子的原始畫作
- 故事中使用的角色／元素
- 故事標題
- 孩子做過的關鍵選擇
- 一句非評分式回顧

例如：

> 「今天你讓小明試了兩種不同的方法，也看到朋友有不同的反應。」

## 6. Agent responsibilities

MVP 不需要堆很多彼此聊天的 agents。建議一個 orchestrator 搭配結構化步驟／工具即可。

### A. Observer

輸入畫作，輸出 observations + confidence + uncertainty。

### B. Grounding policy

決定：

- 哪些內容可以直接保留為低風險 observation
- 哪些需要孩子確認
- 下一題問什麼最有資訊價值

### C. World-state manager

維持：

- characters
- objects
- child-confirmed facts
- uncertain facts
- relationships
- current emotions（若孩子／故事已明確建立）
- story history
- child choices

### D. Story planner

依據 world state、互動目標與年齡建立下一個 story beat。

### E. Consequence simulator

將孩子的 action 轉成合理 consequence，並避免：

- 強迫單一價值答案
- 懲罰式敘事
- 過度恐嚇
- 心理診斷
- 不必要的危險內容

### F. Narrator / renderer contract

Agent 不需要直接生成完整動畫影片。比較適合輸出結構化 scene：

```json
{
  "scene_id": "retry_ball",
  "narration": "他們決定再試一次。",
  "characters": ["c1", "c2"],
  "actions": [
    {"actor": "c2", "action": "shoot_ball"},
    {"object": "ball", "result": "miss"}
  ],
  "interaction": {
    "type": "choice",
    "prompt": "你想怎麼幫他？"
  }
}
```

前端再以 SVG、sprite、emoji 或固定動畫元件呈現，比每個 scene 即時生成影片更適合 hackathon。

## 7. Demo scenario

以四個人物、四顆球的畫作為 demo：

1. AI：候選辨識「4 people / 4 round objects / 2 different facial expressions」。
2. 孩子確認：四個人、四顆球；其中兩人在哭。
3. AI 不猜哭的原因，問孩子。
4. 孩子回答：「因為投球沒有進。」
5. world state 寫入 child-confirmed reason。
6. Agent 建立體育課情境。
7. 孩子選擇怎麼回應哭泣的朋友。
8. 故事依選擇呈現不同自然後果。
9. Agent 追問「現在他有什麼感覺？」或「你還想試別的方法嗎？」
10. 完成故事並回到原始畫作。

Demo 必須另外準備一個「非理想選擇」分支，證明系統不是固定劇本。

## 8. MVP acceptance criteria

Hackathon demo 達到以下條件就算核心成立：

- [ ] 能處理一張真實兒童畫作。
- [ ] AI observation 與 child-confirmed fact 在資料結構中有明確區別。
- [ ] 至少一次 AI 主動承認不確定並詢問孩子。
- [ ] 孩子可以修正 AI 的判斷，且後續故事採用修正結果。
- [ ] story state 在至少 3 個 scene 之間保持一致。
- [ ] 至少有 2 次 child choice。
- [ ] 至少有 1 個 choice 會真正改變後續 scene，而非只改一句旁白。
- [ ] 非理想選擇不顯示「錯誤」，而呈現 consequence + reflection。
- [ ] 不對畫作做心理／醫療診斷。
- [ ] demo 在可接受延遲內完整跑完，不依賴逐 scene 影片生成。

## 9. Non-goals for hackathon

先不做：

- 臨床心理評估
- 從畫作預測 ADHD／ASD／情緒障礙
- 長期療效宣稱
- 完整動畫影片生成 pipeline
- 大型多 Agent framework
- 長期學習成效 dashboard
- 所有年齡與所有特殊需求一次支援

## 10. Hackathon positioning

對外不要主打：

> 「把孩子的畫變成 AI 故事。」

因為這個產品類型已經相當常見。

建議主打：

> **「AI 不替孩子解釋他的畫；AI 先問孩子，再把孩子自己定義的世界變成可以探索選擇與後果的故事。」**

對 FUTUREMODE / BUILDMODE 類型賽事，概念較適合放在 **AI for Taiwan / Social Impact** 或 **AI × Creative Tech**，而 Agent orchestration 可作為技術亮點，而不是作品唯一賣點。
