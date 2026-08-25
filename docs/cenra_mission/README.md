# CENRA Mission 重構文件索引

今天（8/25）要把「智慧巡訪與成交預判」原型全面轉向成 **CENRA Mission｜AI 診所業務任務指揮台**，一天內做完 P0。3 人平行開工，請照下面順序讀：

1. **`00_CONTRACTS.md`** — 全部人先讀這份。domain 物件、CSV schema、repository 介面、用詞護欄，都在這裡定案。任何人要改這份文件定義的形狀，先在群組講一聲。
2. **`TASK_A_核心引擎與服務層.md`** — 我（A）負責 domain / fixtures / 攻守增三引擎 / 評分 / DailyPlan 服務。
3. **`TASK_B_審核狀態機與詳情結果頁.md`** — 組員 1（B）負責審核狀態機 + 任務詳情/審核頁 + 結果回報頁。
4. **`TASK_C_今日任務與行程頁.md`** — 組員 2（C）負責今日任務頁 + 行程頁 + CSV 匯出 + README/文件整理。

完整技術規格在專案根目錄外的三份原始文件（`CENRA_Mission_Codex_系統開發_SPEC.md` 等），有任何 contract 文件沒寫清楚的細節，回去查 SPEC 對應章節（每份 TASK 文件都有標章節號）。

**今天的節奏**：契約先行（已完成）→ 三人平行實作 → 整合串接 → 全員一起走一次 SPEC §0.1 的 9 步驟 P0 驗收 → commit + push。8/26–8/28 只留給簡報與最後修修補補，不排入核心開發。

完整分工邏輯與時程表在 `C:\Users\sherr\.claude\plans\bubbly-squishing-piglet.md`（這份是規劃過程留的，內容跟這裡一致，供對照）。
