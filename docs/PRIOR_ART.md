# Prior-Art / Collision Scan

_Last reviewed: 2026-08-29_

## 結論先行

目前不適合宣稱「沒有人做過 AI + 兒童畫作 + 故事」。這一層已有明確產品與研究。

但截至本次公開資料搜尋，**尚未找到一個系統同時具備以下完整組合**：

1. 以孩子自己的原始畫作作為故事世界起點。
2. 明確區分 `AI observation` 與 `child-confirmed fact`。
3. AI 對不確定的畫意主動詢問孩子，且孩子可以修正模型。
4. 由孩子的修正與補充建立持續的 child-authored world state。
5. 將孩子自己的世界轉成 social situation，而非只生成一本故事書。
6. 孩子的行動會改變故事狀態，Agent 模擬自然 consequence。
7. consequence 後再進行 reflection / re-choice，而非判定答對答錯。
8. 避免從畫作直接做心理或醫療診斷。

因此，目前較安全的說法不是「世界首創」，而是：

> **我們找到許多相鄰工作，但尚未找到與「child-grounded drawing understanding + child-authored world state + agentic consequence simulation」完整相同的公開系統。**

這足以支持 hackathon 的差異化定位，但不能保證世界上不存在未公開專案，也不能保證其他參賽隊伍不會獨立提出相近概念。

---

## 最接近的產品與研究

| 系統 | 兒童畫作作為輸入 | AI 與孩子對話 | 孩子可修正 AI 理解 | 持續 world state | SEL / 情緒能力 | 行動 → consequence | 與本案主要差異 |
|---|---|---|---|---|---|---|---|
| StoryTailor | ✅ | ✅ | 部分：孩子回答問題、可編輯抽取詞 | 部分 | 非核心 | 未見為核心 | 主要目標是把畫作與對話生成互動故事書 |
| TaleWeaver | ✅ sketch / object | ✅ voice-first | 孩子可隨時改故事 | ✅ | 可有 life-skills theme | ✅ 劇情會改變 | 強在即時共創故事，不以「AI 理解必須先被孩子確認」或 SEL consequence loop 為核心 |
| StoryDrawer | ✅ collaborative drawing | ✅ context-based voice agent | 共創過程可影響內容 | 部分 | ❌ | ❌ | 核心是創意視覺敘事與人機共同繪圖 |
| Tinker Tales | 非孩子原始畫作，主要為實體故事元件 | ✅ | ✅ 反覆共創 | ✅ | ✅ social-emotional scaffolding | 部分 | 強調 tangible co-creation 與教育 scaffolding |
| EmoEden | ❌ | ✅ | 回應情緒情境 | 情境上下文 | ✅ 很強 | ✅ simulated emotional feedback | 為 HFA 兒童情緒學習，沒有孩子原畫與 child-defined drawing world |
| eaSEL | 活動中可要求畫圖，但來源是影片 | 間接 | — | ❌ | ✅ | ❌ | 從既有兒童影音偵測 SEL teachable moments 並生成反思活動 |
| SELf-Storybook | ❌ | 主要由家長操作 | 家長可引導輸入 | 部分 | ✅ | ❌ | AI 協助家長製作個人化 SEL 故事書，不是兒童即時互動 Agent |
| Autiverse | ❌，以真實生活事件為輸入 | ✅ | ✅ 明確 verification / correction | ✅ ABCE | ✅ emotion / narrative | ✅ 記錄 consequence | 在「逐步詢問、驗證、consequence」上很接近，但目標是自閉症青少年日記與真實事件整理，不是從孩子畫作進行情境探索 |
| ArtInsight | ✅ | ❌ | ❌ | ❌ | 情緒／心理分析 | ❌ | 直接從畫作產生 emotional themes、assessment、recommendations，方向反而與本案 guardrail 相反 |

---

## 1. StoryTailor — 最大的表面撞題來源

Website: https://storytailor.co.kr/

Brand story: https://storytailor.co.kr/brand-story

GitHub: https://github.com/StoryTailor-KR

公開描述顯示 StoryTailor 已經做到：

- 上傳孩子自己畫的圖。
- AI chatbot 與孩子對話。
- 透過問題取得角色、情境與孩子想像。
- 從對話抽取關鍵詞，且可增刪。
- 生成個人化故事書與插圖。
- 新版加入可拖曳、縮放、點擊的互動角色。

### 撞題判斷

如果本案被描述成：

> 「上傳兒童畫作，AI 問問題，再生成互動故事。」

則與 StoryTailor **高度重疊**。

因此 Demo 與簡報不能停在這裡。

### 本案需要明確展示的差異

- AI 自己看到的內容標示為 tentative observation。
- 孩子可以明確否定 AI，例如「那不是球」。
- 修正後 world state 立即改變。
- 故事不是一次生成完成，而是 child action → consequence → reflection 的 stateful simulation。
- 社會情境不是由模型偷偷替孩子定義，而是從孩子確認後的角色、事件、原因出發。

---

## 2. TaleWeaver — 最大的 Agent storytelling 撞題來源

GitHub: https://github.com/padmanabhan-r/TaleWeaver

TaleWeaver 是 voice-first 兒童即時共創故事產品：

- 4–10 歲。
- 可以展示玩具、物件，或直接畫 sketch。
- Gemini Live 即時說故事並接受插話。
- 孩子可增加角色、改劇情方向。
- Agent 自行選擇何時生成新插圖。
- 跨 scene 維持角色與視覺連續性。

### 撞題判斷

「Agent + 即時兒童故事 + sketch + voice + world continuity」本身已經不是新點。

### 本案需要守住的差異

TaleWeaver 的主要目標是 imagination / co-creation；本案要把重點放在：

> **先建立孩子確認過的世界，再用這個世界進行情境決策與後果探索。**

---

## 3. StoryDrawer — Child-AI drawing storytelling 已有 CHI 研究

Paper: https://doi.org/10.1145/3491102.3501914

CHI 2022 的 StoryDrawer 是 child-AI collaborative drawing system，使用 contextual voice agent 與 AI drawing strategies 支援 6–10 歲兒童的 creative visual storytelling。

### 撞題判斷

不可把「兒童 + AI + 畫畫 + 故事共創」當成研究創新點。

---

## 4. Tinker Tales — 2026 的教育式 child-AI co-creation

Paper: https://arxiv.org/abs/2602.04109

Tinker Tales 使用：

- 實體 storytelling board
- NFC 玩具（角色、地點、物件、情緒）
- voice-based child-AI interaction
- narrative + social-emotional scaffolding

孩子透過移動實體元素反覆塑造故事。

### 撞題判斷

「共創故事 + SEL scaffolding」已有 2026 工作。

本案差異仍需依靠「孩子自己的原始畫作 → grounding → consequence simulation」這條鏈。

---

## 5. EmoEden — 生成式 AI + 情緒學習已經成熟

Paper: https://doi.org/10.1145/3613904.3642899

Open source: https://github.com/zju-d3/EmoEden

CHI 2024 EmoEden 對 8–12 歲高功能自閉症兒童提供：

- 個人化生成式對話。
- 情緒辨識與回應練習。
- voice / touch interaction。
- simulated emotional feedback。
- 依情境產生視覺內容。

### 撞題判斷

不要宣稱「我們首次用 GenAI 教孩子認識情緒」。

本案的獨特來源應該是孩子自己的創作世界，而不是 AI 預先生成的訓練情境。

---

## 6. eaSEL — LLM 生成 SEL reflection activities

Paper: https://doi.org/10.1145/3706598.3713405

Apple Research: https://machinelearning.apple.com/research/easel-promoting-social-emotional

CHI 2025 eaSEL：

- 從兒童影音中偵測 SEL teachable moments。
- 生成孩子可執行的反思活動。
- 生成親子討論問題。
- 使用者研究發現活動能增加孩子對影片情緒內容的反思。

### 撞題判斷

「LLM 找情緒學習時機 + 生成反思問題」也不是本案的新點。

---

## 7. SELf-Storybook — 個人化 SEL 故事書已有 2026 CHI EA

Paper: https://doi.org/10.1145/3772363.3798869

SELf-Storybook 是家長導向的 guided AI authoring system：

- 家長輸入孩子 profile 與 temperament。
- 系統分析 situation / SEL competency。
- 生成個人化 SEL storybook。
- 研究焦點是家長 authoring interface。

### 撞題判斷

不要把「個人化 SEL AI storybook」當成作品名稱與主要賣點。

---

## 8. Autiverse — 最值得注意的新近鄰近研究

Project: https://naver-ai.github.io/autiverse/

Paper DOI: https://doi.org/10.1145/3772318.3791381

Technical overview: https://clova.ai/en/tech-blog/autiverse-turning-autistic-adolescents-daily-experiences-into-stories-with-ai-guided-comic-journals

CHI 2026 Autiverse 對自閉症青少年做 AI-guided multimodal journaling，使用 ABCE：

- Antecedent
- Behavior
- Consequence
- Emotion

其中尤其重要的是：

- AI 逐步問問題，不要求孩子一次完整敘述。
- 系統整理孩子的資訊後會進入 **Verification**。
- 孩子可以確認或修正錯誤。
- AI 只生成資訊足夠的 comic panel，缺資料就再追問。
- Consequence 與 Emotion 常是在後續 targeted questions 才被引導出來。

### 與本案的重疊

Autiverse 已證明以下設計不能當成我們單獨的新點：

- AI stepwise elicitation。
- AI 先整理，再請兒童／青少年 verification。
- 由 AI 追問 consequence 和 emotion。
- multimodal visual support。

### 仍然不同的地方

Autiverse 的來源是孩子「真實發生過的生活事件」，目標是幫助自閉症青少年組織 daily narratives。

本案則是：

> **從孩子自己畫出的虛構／半虛構世界開始，在不替孩子解讀畫意的前提下，建立 world state，再讓孩子主動選擇未來行動並由 Agent 模擬尚未發生的 consequence。**

這個差別很重要：

- Autiverse：**reconstruct past event**。
- 本案：**ground a child-created world and simulate possible futures**。

---

## 9. ArtInsight 與 drawing-emotion AI — 本案最好主動站在相反方向

ArtInsight: https://doi.org/10.3233/SHTI250471

2026 的 ArtInsight 會直接從兒童畫作生成：

- artwork description
- emotional themes
- psychological interpretation
- assessment
- personalized recommendations

另外，2026 年一篇針對兒童畫作自動情緒分類的 benchmark 指出，這是一個高度模糊的 machine-vision problem，情緒訊號存在於稀疏線條、象徵物與構圖，模型可靠度應以 coverage / selective prediction 等方式評估，而不是假設全覆蓋都可信。

Benchmark: https://doi.org/10.3390/app16168333

### 對本案的意義

這其實給我們很好的產品立場：

> **AI 不替孩子判讀心理；AI 把不確定性轉成與孩子對話的機會。**

因此「uncertainty → ask the child」不只是一個 UX gimmick，也可以被說明成對 drawing interpretation reliability 的設計回應。

---

## Collision risk by positioning

### 9/10 — 不可用

> 「把孩子的畫變成 AI 故事書。」

大量產品已經存在。

### 8/10 — 很危險

> 「AI 看孩子的畫、跟孩子聊天、共同生成故事。」

StoryTailor、TaleWeaver 等已非常接近。

### 7/10 — 仍然偏高

> 「用生成式 AI 故事培養兒童情緒／社交能力。」

EmoEden、eaSEL、SELf-Storybook、Tinker Tales 等已有直接或鄰近工作。

### 4/10 — 可以做，但必須 Demo 證明

> 「先讓孩子確認 AI 對畫作的理解，再由孩子的說法生成故事。」

StoryTailor 已經透過提問取得孩子故事資訊；Autiverse 也有 verification，因此單靠 confirmation 還不夠。

### 2–3/10 — 目前最適合的核心機制定位

> **Child-created drawing → uncertainty-aware observation → child verification/correction → persistent child-authored world state → child action → agent-simulated consequence → reflection / re-choice.**

本次公開搜尋沒有發現完全相同的整體流程。

---

## 評審可能問：「StoryTailor 不是一樣嗎？」

建議回答：

> StoryTailor 已經很好地證明「孩子畫作可以成為 AI 共創故事的起點」，所以我們不是把「畫作生成故事」當創新點。我們關注的是另一個問題：vision model 對孩子畫作的理解可能是錯的，因此 AI 的 observation 不直接成為故事事實，而要先讓孩子確認。確認後，我們維持一個由孩子定義的 world state；故事中的選擇會真的改變世界，Agent 再模擬後果並讓孩子反思或重新選擇。我們做的比較接近 child-grounded social-situation simulation，而不是一次完成一本故事書。

## 評審可能問：「Autiverse 不是也會 verification + consequence？」

建議回答：

> Autiverse 很接近我們的互動設計思路，但它是協助自閉症青少年把已經發生的真實生活事件整理成 ABCE comic journal。我們的輸入是孩子自己的畫作，而且不假設 AI 已經理解畫意；孩子先建立自己的世界，接著 Agent 模擬尚未發生的不同選擇與後果。因此一個是 past-event narrative reconstruction，一個是 child-grounded possible-future simulation。

---

## 目前可使用的差異化宣言

### 對一般觀眾

> **AI 不替孩子解釋他的畫；AI 先問孩子，再陪他看看故事接下來可能發生什麼。**

### 對評審

> **We separate model observation from child-confirmed meaning, maintain a child-authored world state, and use an agent to simulate the consequences of the child's choices rather than scoring them against a fixed answer.**

### 對技術簡報

> **Observe → Clarify → Ground → Simulate → Reflect**

---

## 搜尋範圍與限制

本次檢查涵蓋截至 2026-08-29 可公開搜尋到的：

- AI 兒童故事產品。
- drawing-to-story / sketch-to-story 系統。
- child-AI collaborative storytelling HCI 研究。
- generative AI + social-emotional learning 研究。
- AI + children's drawing emotional interpretation 研究。
- 2026 年較新的 child / autism / multimodal narrative systems。

沒有任何 prior-art scan 能證明「世界上絕對沒有人做過」。尤其以下內容無法完全排除：

- 尚未公開的 startup / internal prototype。
- 尚未發表論文。
- 2026 FUTUREMODE 其他尚未公開的參賽提案。

因此正式簡報建議使用：

> **「我們目前未找到完整相同的公開系統」**

而不要使用：

> **「全球首創／世界第一個」**。
