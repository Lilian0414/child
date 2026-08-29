# Documentation map

_Last reviewed: 2026-08-29_

本目錄把「為什麼做」「產品要做什麼」「系統如何實現」「如何證明可用」分開維護，避免同一規則散落在 README、簡報與程式碼註解中。

## Source of truth

| 文件 | 負責回答 | 狀態 |
|---|---|---|
| [CONCEPT.md](CONCEPT.md) | 題目、核心觀點、差異化與 non-goals | Accepted concept |
| [PRODUCT_SPEC.md](PRODUCT_SPEC.md) | 使用者、流程、功能需求與產品驗收 | Proposed MVP spec |
| [TECHNICAL_DESIGN.md](TECHNICAL_DESIGN.md) | 架構、元件責任、狀態機、失敗處理 | Proposed design |
| [DATA_CONTRACTS.md](DATA_CONTRACTS.md) | Domain objects、provenance、scene 與 API 契約 | Proposed contracts |
| [AGENT_POLICY.md](AGENT_POLICY.md) | Agent 步驟、結構化輸出、提問與故事規則 | Proposed policy |
| [SAFETY_PRIVACY.md](SAFETY_PRIVACY.md) | 兒童安全、資料最小化、內容處理與升級 | Required baseline |
| [DEMO_EVALUATION.md](DEMO_EVALUATION.md) | Demo 劇本、golden cases、指標與 UAT | Proposed verification |
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | 技術決策門檻、依賴順序與 Issue backlog | Ready for issue creation |
| [PRIOR_ART.md](PRIOR_ART.md) | 相鄰工作、撞題風險與對外說法 | Research snapshot |

## 文件狀態的意思

- **Proposed**：可作為討論基線，但尚未由實作或驗證證明。
- **Accepted**：團隊已採用的產品或技術決策；變更時需同步受影響文件。
- **Implemented**：目前 code path 已符合文件描述。
- **Verified**：有 repository-native test、UAT 或量測證據支持。

文件不能因為寫得完整就被稱為 implemented。README 也不應宣稱尚未跑通的功能。

## 需求衝突時的優先順序

1. 兒童安全與資料保護限制。
2. 已接受的 GitHub Issue / decision record。
3. Product spec 與 data contracts。
4. Technical design 與 agent policy。
5. Demo 文案與 README。

若 code、test、Issue 與文件互相矛盾，先停下來確認，不用「看起來合理」的方式自行選一個版本。

## 何時新增 ADR

開始寫程式後，以下決策不要只藏在 commit message：

- VLM / LLM provider 與備援方式。
- Session persistence 與圖片保存政策。
- 同步 HTTP、SSE 或 WebSocket 的互動方式。
- 語音是否在 MVP 內、由瀏覽器或後端處理。
- 部署區域、資料保留與第三方模型的資料使用設定。

建議格式：`docs/decisions/NNNN-short-title.md`，包含 context、decision、alternatives、consequences 與 status。

## 更新檢查

行為改動完成前，至少確認：

- Product spec 的 acceptance criteria 是否改變。
- Data contracts 是否需要版本或 migration。
- Agent policy 是否仍與實作一致。
- Safety policy 是否出現新的資料或內容風險。
- Demo golden cases 是否需要更新。

