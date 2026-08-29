# Child-Grounded Story Agent

> 讓 AI 先向孩子理解畫作，再以孩子自己定義的世界陪他探索「如果這樣做，接下來會發生什麼？」

這是一個以兒童畫作為起點的互動式 AI Agent 專案。系統不把視覺模型的判斷直接當成孩子的真實意圖，而是把 AI 看見的內容視為「候選觀察」，先讓孩子確認、修正與補充，再建立由孩子定義的故事世界。

故事進行時，孩子的選擇會真的改變後續情節。Agent 不以「答對／答錯」評分，而是模擬合理的社會情境後果，再透過提問讓孩子觀察、理解與重新選擇。

## 核心流程

```text
Child drawing
    ↓
AI observation
    ↓
Clarify uncertainty with the child
    ↓
Child-confirmed world state
    ↓
Interactive story / social situation
    ↓
Child action
    ↓
Consequence simulation
    ↓
Reflection / next choice
    ↓
Story ending
```

## 三個核心差異

1. **Child-grounded understanding**：AI 的辨識結果不是事實；孩子確認後才寫入故事世界。
2. **Child-authored world state**：角色身分、情緒、事件原因與關係，以孩子的說法為優先。
3. **Consequence simulation**：孩子的選擇造成故事後果，Agent 再依新狀態繼續互動，而不是給標準答案。

## MVP

Hackathon MVP 只需要跑通一條完整流程：

- 上傳一張兒童畫作。
- VLM 找出 3–6 個可觀察元素與不確定項目。
- 孩子確認或修正關鍵內容。
- 建立結構化 world state。
- Agent 產生 3–5 個故事節點。
- 至少兩次由孩子做選擇。
- 至少一次選擇會明顯改變後續情節。
- 最後回顧孩子原畫與共同完成的故事。

## 安全與產品原則

- 不從顏色、構圖、人物大小等直接推論孩子的心理狀態。
- 不宣稱診斷 ADHD、自閉症、學習障礙或任何心理／醫療狀況。
- 可提供「短句、注音、圖片提示、較少選項、慢速語音」等 accessibility profile，而不是 diagnosis mode。
- 對人物情緒、人物關係、事件原因等高語意內容，優先詢問孩子，而不是由 AI 自行定義。
- 非理想選擇不顯示「答錯」，而由故事呈現自然後果並提供反思機會。

## 文件

- [Project concept and hackathon outline](docs/CONCEPT.md)
- [Prior-art / collision scan](docs/PRIOR_ART.md)

## 目前定位

本專案不是單純的「AI 兒童繪本生成器」，也不是「AI 從畫作判讀孩子情緒」。

目前最清楚的定位是：

> **A child-grounded interactive story agent that turns a child's own drawing and explanation into a world for social-situation exploration.**
