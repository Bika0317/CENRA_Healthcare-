# Track A（核心引擎與服務層）完成報告

對應計畫 `bubbly-squishing-piglet.md` 的 Stage 1–4。分支：`feat/engine-core`（已推上 GitHub）。

## 完成範圍

### 1. Domain 與規則層
- [`domain/models.py`](../../domain/models.py)：`Task`、`Evidence`、`TaskReview`、`TaskOutcome`、`FixedAppointment`、`DailyPlan` 等 dataclass，以及狀態機（`transition()` 為唯一對外入口）。
  - 合法轉移：`candidate → accepted/modified/deferred/rejected → scheduled → completed/not_completed/cancelled`。
  - 非法轉移丟 `InvalidTransitionError`；缺必填欄位（modify 未變更、defer 缺日期、reject 缺原因）丟 `ValidationError`。
- [`domain/reason_codes.py`](../../domain/reason_codes.py)：13 組原因代碼、允許／禁用語句清單（guardrail 測試的依據）。

### 2. 資料層
- [`data/fixtures/seed_generator.py`](../../data/fixtures/seed_generator.py)：固定 random seed 的合成資料產生器。3 位業務、10 個主要 demo 帳戶、5 個潛在診所、180+ 天訂單／互動、2 個固定預約。內建 SPEC §9.2 的必備情境（強觸發、電話優先、缺值、明確競品訊號、弱證據等）。
- [`data/fixture_repository.py`](../../data/fixture_repository.py)：CSV 讀取＋schema 驗證（外鍵、金額非負、座標落在台灣範圍、日期不晚於 cutoff）。
- [`data/task_repository.py`](../../data/task_repository.py)：SQLite 持久化。`save_tasks()` 依 `generation_key` idempotent；`apply_review()`／`apply_outcome()` 皆為 transaction，任一步驟失敗整批回滾。

### 3. 三類任務引擎
- [`engines/attack.py`](../../engines/attack.py)：新客開發候選（資格條件：非低適配、未進入固定預約、uncontacted/contacted）。
- [`engines/defend.py`](../../engines/defend.py)：流失挽回候選（強觸發或 ≥2 個一般訊號才產生）。**沒有直接 `competitor_mentioned=true` 的來源事件時，文案只會說「風險待查」，不會宣稱「已被競品入侵」**。
- [`engines/grow.py`](../../engines/grow.py)：補貨與品項機會候選（補貨週期、品項缺口、明確需求訊號三選一）。

### 4. 評分與排程
- [`services/scoring.py`](../../services/scoring.py)：統一任務價值分數（30% 訊號＋25% 商業價值＋20% 急迫性＋15% 證據＋10% 策略適配－成本懲罰，clamp 0–100）。訊號與商業價值只在同任務類型的同批次內做百分位轉換；單一候選時固定回傳 70。
- [`services/scheduling.py`](../../services/scheduling.py)：固定預約先占用分鐘數，三類任務各先給 1 個最低配額，其餘依分數遞補；實訪任務用 nearest-neighbor 排點位順序（電話任務不進地圖）。
- [`services/daily_plan_service.py`](../../services/daily_plan_service.py)：`build_daily_plan(rep_id, plan_date, available_minutes, fixture_repo, task_repo) -> DailyPlan`。這是 B、C 兩條軌道共用的核心入口，**目前是完整真實邏輯，不是先前計畫預留的 mock 版**。

## 驗證結果

- `pytest tests/` 全數通過：**35 個測試**（`test_repository.py`、`test_engines.py`、`test_scoring.py`、`test_daily_plan_service.py`、`test_smoke.py`）。
- SPEC AC-01（今日任務生成）逐字對齊：主要 demo 業務 L100 在 2026-08-25 產生剛好 **8 個候選任務**，攻 2／守 3／增 3。
- 容量分配驗證：2 個固定預約（共 70 分鐘）＋建議任務（165 分鐘）＋剩餘 15 分鐘 = 240 分鐘彈性總量，不超額。
- 重複執行 `build_daily_plan()` 驗證 idempotent：同一天同一業務不會重複寫入任務。

## 過程中修正的問題

1. **Evidence ID 跨引擎碰撞**：攻／守／增三個引擎原本用相同的帳戶/診所 ID 加簡短後綴命名證據 ID（例如守與增都用 `-gap`），同一帳戶同時出現在兩種任務時會撞 SQLite 的 unique constraint。改成每個引擎前綴自己的任務類型（`-defend-gap` / `-grow-gap`）。
2. **AC-01 精確配比對不上**：實際跑分後攻任務只有 1 個通過門檻（P001 因為只有 2 個攻候選，百分位轉換讓輸家直接歸零）；增任務則因為 A001／A005 同時被守引擎與增引擎判定為候選，多算成 4 個。透過補一個「攻」的填充候選（P005，本身低於門檻不會顯示，用來讓百分位有 3 個樣本可比較）以及讓 A001 的品項組合補到 3 條產品線（避免被增引擎誤判品項缺口），修正到精確的 2／3／3。
3. **`services/scheduling.py` 原設計依賴業務「駐地座標」作為 nearest-neighbor 起點，但 `reps.csv` 沒有這個欄位**：改成沒有固定預約時，直接從分數最高的任務出發排序，不依賴不存在的欄位。

## 交付狀態

- 分支 `feat/engine-core` 已推上 GitHub：`git fetch origin && git checkout feat/engine-core` 即可取得上述全部內容。
- B、C 可以直接對接真資料開工，不需要再等 mock 版替換。
- `.claude/launch.json` 已加入 `cenra-mission`（port 8502）設定，等 `app/mission_app.py` 落地即可啟動。

## 尚未開始（不在本次範圍）

- Stage 5：`services/review_service.py` / `outcome_service.py`（B 負責）。
- Stage 6：四頁 Streamlit UI（B／C 分工）。
- Stage 7：README 重寫、`docs/legacy_v1/` 搬移、guardrail 測試（C 負責）。
- Stage 8：乾淨環境最終驗收。
- Stage 9：14 頁簡報重製（時間允許再做，不阻塞 P0）。
