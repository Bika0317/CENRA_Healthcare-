# P1｜主管任務覆蓋視圖 Statement

- 文件版本：1.0
- 建立日期：2026-08-26
- 對應母文件：SPEC §5.2 P1 項目 1「主管任務覆蓋視圖」
- 影響檔案：新增 `app/pages_mission/manager_overview.py`；修改 `app/mission_app.py`（掛新頁籤）
- 性質：新頁面＋跨業務查詢邏輯，不動 domain／engines／services 既有函式簽名

---

## 1. 現況（已讀程式碼確認，非推測）

目前系統完全沒有任何「跨業務彙總」的能力：

1. `data/task_repository.py::get_candidate_tasks(rep_id, task_date)` 只接受**單一** `rep_id`，
   沒有「查全部業務」的方法。要看三位業務的狀況，現在得手動切換「今日任務」頁的業務選單，
   一次只能看一位。
2. `data/fixture_repository.py::get_reps()` 已經回傳全部業務清單（`rep_id`、`rep_name`、
   `region`、`daily_available_minutes` 等），可以直接拿來當跨業務彙總的迭代來源，不用改
   `fixture_repository.py`。
3. `services/daily_plan_service.py::build_daily_plan(rep_id, plan_date, available_minutes, ...)`
   一次只算一位業務的 `DailyPlan`，且內部會呼叫 `task_repo.resurface_deferred_tasks()` 與
   引擎重新產生候選——對三位業務各呼叫一次沒有問題（`generation_key` idempotent，不會
   重複寫入），但目前沒有任何地方會主動幫全部業務都跑過一次；如果主管開這頁時某位業務
   從來沒被任何人在「今日任務」頁點過，該業務的候選任務可能還沒生成過。
4. SPEC §13.2 寫「模型洞察、管理總覽、通知與大範圍匯出不得出現在 P0 主導覽」——這句話的
   脈絡是舊版 `dashboard.py` 那種「全公司 KPI／平均成交機率」風格的總覽不該混進 P0 的四頁
   導覽，**不是**禁止 P1 之後另外加一個以「任務」為單位（不是以「成交機率」為單位）的
   跨業務彙總頁。這個 P1 項目做的是後者，性質不同，但實作時要注意用詞：不能用回舊版的
   「平均成交機率」「風險燈號」這類敘事，要延續 CENRA Mission 的「任務」語言。

## 2. 目標與驗收標準

- [ ] 新增「主管總覽」頁籤（第 5 個頁籤，掛在既有「今日任務／任務詳情審核／行程／結果回報」
      之後，不取代、不插在中間）。
- [ ] 頁面內容：一個表格或卡片列表，每一列是一位業務（L100/L101/L102），欄位至少包含：
      候選任務數、依 `task_type` 拆分的攻/守/增數量、已採納數、待回報（`scheduled`）數、
      已完成數、平均 `value_score`。
- [ ] 點某一位業務的列，可以直接跳到「今日任務」頁並把 `selected_rep_id`／
      `selected_available_minutes` 切到那位業務（複用既有的 session_state key，不要另外
      發明一組新的業務選擇機制）。
- [ ] 開這頁時，如果有業務還沒生成過今日任務，要能正確處理（呼叫 `build_daily_plan()`
      幫忙補生成，或至少不能整頁噴錯／顯示錯誤的 0）。
- [ ] 不出現任何 SPEC §15.3 禁用語句（沿用既有 `tests/test_content_guardrails.py` 的
      `BANNED_PHRASES` 清單，新頁面要納入 guardrail 掃描範圍）。
- [ ] 既有 73 個 pytest 測試不因此改動而失敗；新頁面本身建議至少補 2-3 個測試
      （例如「跨業務彙總數字加總起來要等於各業務分別查詢的結果」）。

## 3. 建議做法

在 `app/pages_mission/manager_overview.py` 新增 `render(fixture_repo, task_repo, demo_date)`：

```python
def render(fixture_repo, task_repo, demo_date):
    rows = []
    for rep in fixture_repo.get_reps():
        rep_id = rep["rep_id"]
        available_minutes = int(rep["daily_available_minutes"])
        plan = build_daily_plan(rep_id, demo_date, available_minutes, fixture_repo, task_repo)
        counts = {tt: 0 for tt in TaskType}
        for t in plan.candidate_tasks:
            counts[t.task_type] += 1
        accepted = sum(1 for t in plan.candidate_tasks if t.status in (TaskStatus.ACCEPTED, TaskStatus.MODIFIED))
        scheduled = sum(1 for t in plan.candidate_tasks if t.status == TaskStatus.SCHEDULED)
        completed = sum(1 for t in plan.candidate_tasks if t.status in (
            TaskStatus.COMPLETED, TaskStatus.NOT_COMPLETED, TaskStatus.CANCELLED))
        avg_score = sum(t.value_score for t in plan.candidate_tasks) / len(plan.candidate_tasks) if plan.candidate_tasks else 0
        rows.append({
            "rep_id": rep_id, "rep_name": rep["rep_name"], "total": len(plan.candidate_tasks),
            "attack": counts[TaskType.ATTACK], "defend": counts[TaskType.DEFEND], "grow": counts[TaskType.GROW],
            "accepted": accepted, "scheduled": scheduled, "completed": completed, "avg_score": round(avg_score, 1),
        })
    # st.dataframe(rows) 或逐列 st.container 卡片，每列一個「切換到這位業務」按鈕
```

「切換到這位業務」按鈕的寫法比照 `today_tasks.py` 現有的「開啟詳情」跳轉模式（設
`st.session_state["selected_rep_id"]` / `selected_available_minutes`，用同一套
`nav_redirect` 中繼旗標機制跳轉到「今日任務」頁，不要直接改 `mission_nav` 的
session_state——那個 key 綁定的 radio widget在這一輪已經跑過，會噴
`StreamlitAPIException`，這個 session 已經真的踩過這個坑）。

`app/mission_app.py` 的 `PAGES` list 加一項，`nav == "主管總覽"` 時呼叫
`manager_overview.render(fixture_repo, task_repo, DEMO_DATE)`。

## 4. 明確排除事項

- 不要做成本重的「全公司 KPI 儀表板」（成交機率分布圖、地理熱力圖、風險燈號）——這正是
  SPEC 明確要求移除的舊版敘事語言，這頁只彙總「任務數量與狀態」，不做任何預測或風險評分。
- 不要新增資料庫 schema 或新的 `task_repository` 方法——`get_candidate_tasks()` 逐業務
  呼叫三次（L100/L101/L102 固定只有 3 位業務，效能不是問題）就夠了，不需要為了這個
  P1 功能去改動已經穩定、被 73 個測試覆蓋的 repository 介面。
- 不要讓這頁擁有「代替業務審核任務」的能力（例如在這頁直接顯示採納/拒絕按鈕）——
  審核權限的唯一入口維持在「任務詳情／審核」頁，主管總覽只能看、只能導覽過去，不能
  越過業務直接操作，這是刻意的權限邊界，不是遺漏。

## 5. 驗證方式

```bash
streamlit run app/mission_app.py
```

1. 開「主管總覽」頁，確認三位業務都有一列，數字不是全部 0（尤其是從沒點開過的業務）。
2. 手動核對：把「主管總覽」顯示的 L100 攻/守/增數字，跟直接去「今日任務」頁選 L100
   看到的候選任務類型分布比對，必須一致。
3. 點某一列的「切換到這位業務」，確認正確跳轉到「今日任務」頁且業務選擇器已經是對的人，
   不需要再手動選一次。
4. `pytest tests/test_content_guardrails.py` 涵蓋新檔案後仍全綠。
