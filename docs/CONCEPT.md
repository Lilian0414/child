# Project concept — Child-Grounded Story Agent

_Status: Accepted concept_  
_Last reviewed: 2026-08-29_

## 一句話題目

**讓 AI 先向孩子理解他的畫，再把孩子自己定義的世界變成可以做選擇、看見後果的互動故事。**

英文暫定：

> **Child-Grounded Story Agent: Interactive social-situation exploration from children's own drawings**

## 問題

兒童畫作可以成為故事與對話的起點，但視覺模型很容易把「模型看到的東西」直接當成孩子真正想表達的意思。例如，AI 可能從嘴角、紅色線條或人物大小推論人物正在難過、生氣，甚至替孩子補上事件原因。

本專案不把重點放在「AI 能不能從畫生成故事」，而是：

> **AI 能不能承認自己不知道，透過孩子的確認建立可靠的故事世界，再陪孩子探索不同選擇的結果？**

## 核心主張

### Observation is not fact

模型輸出先是帶有不確定性的候選 observation。孩子確認後才成為 world state 的 fact；孩子否定時，系統必須採用修正並停止沿用舊推論。

### Meaning belongs to the child

人物身分、人物關係、情緒與事件原因屬於高語意內容，必須來自孩子的說法或故事中清楚標記的衍生狀態，不能由畫面特徵直接推論。

### Consequence, not correctness

孩子可以嘗試不同做法。系統呈現兒童可理解、有限且可恢復的自然後果，再詢問孩子看見了什麼、想繼續或換一種方法，而不是用紅叉、分數或道德答案評判。

## 目標使用者

Hackathon MVP 聚焦約 7–10 歲兒童，由家長、老師或現場引導者協助開始 session。

系統可以依互動需求調整短句、注音、圖片提示、選項數量、語音速度與重複提示，但不建立「ADHD mode」「autism mode」或其他診斷模式。

## 產品旅程

1. 成人設定暱稱、文字難度、提示形式與本次互動目標。
2. 孩子上傳畫作。
3. AI 提出少量、可理解的候選觀察並標示不確定。
4. 孩子確認、否定或補充。
5. 系統建立有 provenance 的 child-authored world state。
6. Agent 以 world state 規劃短篇情境，而非一次生成完整長篇。
7. 孩子做出選擇，Agent 更新狀態並呈現自然後果。
8. 孩子反思、重選或繼續，最後回顧共同完成的故事。

可驗收的細節見 [PRODUCT_SPEC.md](PRODUCT_SPEC.md)。

## Demo anchor

以「四個人物、四顆球」的畫作作為 canonical demo：

- AI 先提出人物、圓形物件與表情差異等候選觀察。
- 孩子確認四個人、四顆球，其中兩個人在哭。
- AI 不猜哭的原因，改問孩子。
- 孩子回答「因為投球沒有進」。
- Agent 建立體育課情境，讓孩子選擇如何回應哭泣的朋友。
- 不同選擇產生不同 consequence，孩子可以反思或換一種方法。

Demo 必須包含一次 AI 被孩子修正，以及一個非理想選擇分支，否則無法證明本案與固定腳本故事生成器的差異。

## 定位與差異化

對外不要只說「把孩子的畫變成 AI 故事」，因為 drawing-to-story、兒童共創故事與 SEL storybook 都已有大量相鄰工作。

本案應維持完整鏈條：

> **Child-created drawing → uncertainty-aware observation → child verification/correction → persistent child-authored world state → child action → agent-simulated consequence → reflection / re-choice**

完整撞題分析與安全說法見 [PRIOR_ART.md](PRIOR_ART.md)。

## Hackathon non-goals

- 臨床心理評估或心理治療。
- 從畫作預測 ADHD、ASD、情緒障礙或其他狀況。
- 宣稱長期學習或療效。
- 即時生成完整動畫影片。
- 大型 multi-agent framework。
- 長期學習成效 dashboard。
- 一次支援所有年齡與所有特殊需求。

## 成功的最小定義

成功不是畫面最華麗，而是評審能從一條完整 demo 看見：

1. AI 承認不確定。
2. 孩子具有修正權。
3. 修正會改變持續的 world state。
4. 選擇會造成可觀察的分支後果。
5. Agent 協助反思，但不替孩子診斷或評分。

