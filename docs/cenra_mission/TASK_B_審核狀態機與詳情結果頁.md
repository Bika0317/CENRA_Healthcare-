# 組員 1（B）任務交接：審核狀態機 + 任務詳情/審核頁 + 結果回報頁

先讀 `docs/cenra_mission/00_CONTRACTS.md`（共用契約，domain 物件與 repository 介面都在那裡），再讀 SPEC 對應章節：§7.5（狀態機）、§13.4（審核頁）、§13.6（結果頁）、§16.3（你要通過的測試清單）。

## 你負責的檔案

- `services/review_service.py`
- `services/outcome_service.py`
- `app/pages_mission/task_detail.py`（任務詳情／審核頁）
- `app/pages_mission/outcomes.py`（結果回報頁）
- `tests/test_state_machine.py`

**不要動**：`domain/models.py`（A 維護，你只 import）、`app/pages_mission/today_tasks.py` 和 `itinerary.py`（C 的檔案）。

## 現在就能開工的部分（不用等 A）

`00_CONTRACTS.md` 裡的 `Task`、`TaskReview`、`TaskOutcome`、`transition()` 函式簽名已經定案，你可以：

1. 先寫 `tests/test_state_machine.py`（TDD），對著 domain 契約寫測試案例，不用等真的資料庫：
   - candidate 可以 accept / modify / defer / reject。
   - defer 沒填 `deferred_to` → 要噴 `ValidationError`。
   - reject 沒填 `reason_code` → 要噴 `ValidationError`。
   - modify 沒有任何欄位真的變更（objective 和 action_mode 都跟原本一樣）→ 要噴 `ValidationError`。
   - accepted/modified 才能轉 scheduled；scheduled 才能轉 completed/not_completed/cancelled。
   - completed 缺 `outcome_type` → 要噴 `ValidationError`。
   - 任何轉移失敗都不可以部分寫入（review 或 outcome 沒存成功，task.status 也不該被改）。

2. 先把 `app/pages_mission/task_detail.py` 的畫面刻出來，用假的 `Task` 物件（自己在檔案裡手寫幾筆 mock 資料）撐著畫面：
   - 任務摘要：類型、名稱、分數、生成時間、狀態。
   - 三項主要證據：label、display_value、來源時間。
   - 訂單／互動時間線（先用假資料畫）。
   - 前次互動摘要與未完成承諾。
   - uncertainty_note 與資料缺口提示。
   - 審核表單：Accept／Modify（至少改 objective 或 action_mode 之一 + reason_code）／Defer（必填日期+原因）／Reject（必填原因）。
   - 成功操作要顯示明確確認訊息；失敗要顯示欄位級錯誤，不能整頁噴 traceback。

3. `app/pages_mission/outcomes.py`：
   - 只列出 `status == scheduled` 且尚未完成的任務（先用假資料）。
   - 表單：completed / not_completed / cancelled 三選一。
   - completed 必填 `outcome_type`（下拉：需求確認／補貨／後續約訪／無機會／資料錯誤／服務事項已解決／其他）。
   - not_completed／cancelled 必填原因。
   - next_step、next_date 是條件式欄位（不強制）。
   - 送出成功後顯示更新時間，並把該任務改成「已完成」的折疊區塊呈現，不能再重複送出。

## A 會交給你的東西（等到了再串真的資料）

- `services/review_service.py` 裡你要實作的函式簽名：
  ```python
  def submit_review(task_id: str, decision: ReviewDecision,
                     modified_objective: str | None, modified_action_mode: ActionMode | None,
                     reason_code: str, reason_note: str | None, deferred_to: date | None,
                     actor_rep_id: str, task_repo: TaskRepository) -> Task:
      """呼叫 domain.transition() 檢查合法性 -> 組出 TaskReview -> 呼叫 task_repo.apply_review()"""
  ```
- `services/outcome_service.py` 同樣模式：
  ```python
  def submit_outcome(task_id: str, execution_status: ExecutionStatus,
                      outcome_type: OutcomeType | None, note: str | None,
                      next_step: str | None, next_date: date | None,
                      actor_rep_id: str, task_repo: TaskRepository) -> Task: ...
  ```
- `TaskRepository` 的 `apply_review()` / `apply_outcome()` 今天稍晚會由 A 補上真正的 SQLite transaction 實作，你先對著介面寫，不用等。

## 你要驗證的東西（今天結束前）

1. `pytest tests/test_state_machine.py` 全綠。
2. 用 Playwright（或手動）跑一次：開一張 candidate visit 任務 → 改 objective + 改成 phone → 採納 → 狀態變成 modified/scheduled → 重新整理頁面狀態還在。
3. 跑一次：candidate → defer 但不填日期 → 應該被擋下來、不能送出。
4. 跑一次：scheduled 任務 → 填 completed + outcome_type → 重新整理後任務出現在「已完成」折疊區塊。

## 文案護欄

任務詳情頁裡如果要顯示風險/異常相關文字，只能用「流失風險待查」「異常待查」「原因需業務確認」，不能寫「已被競品入侵」，除非該任務的 evidence 裡有一筆 `source_type=interaction` 且 `competitor_mentioned=true` 的直接證據。
