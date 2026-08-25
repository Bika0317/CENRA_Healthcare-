# 組員 2（C）任務交接：今日任務頁 + 行程頁 + CSV 匯出 + README/文件整理

先讀 `docs/cenra_mission/00_CONTRACTS.md`（共用契約），再讀 SPEC 對應章節：§13.3（今日任務頁）、§13.5（行程頁）、§19（README 要求）、§16.5（guardrail 測試）。

## 你負責的檔案

- `app/pages_mission/today_tasks.py`
- `app/pages_mission/itinerary.py`
- `app/mission_app.py`（很薄的路由層，四個頁面用 tab 或 sidebar 切換，實際內容都在 `pages_mission/` 底下）
- `.gitignore` 的 `data/db/*.db` 這行（跟 A 對一下）
- `README.md`（新版主標，內容見下方第 4 節）
- `docs/legacy_v1/`（把舊 `docs/專案完整說明.md`、舊簡報 pptx 用 `git mv` 搬過去，不要用 `rm` 刪除）
- `tests/test_content_guardrails.py`

**不要動**：`app/pages_mission/task_detail.py` 和 `outcomes.py`（B 的檔案）、`domain/models.py`（A 維護）。

## 現在就能開工的部分（不用等 A）

先用假的 `DailyPlan` 物件（自己在檔案裡手寫幾筆 mock 資料，形狀照 `00_CONTRACTS.md` 的 `DailyPlan` dataclass）把兩個頁面刻出來：

### `today_tasks.py` 必要元件（SPEC §13.3）
- 業務選擇器（下拉，先寫死 3 個假業務員名字）。
- Demo 日期顯示。
- 固定預約摘要（`plan.fixed_appointments`）。
- 可用彈性分鐘輸入框。
- 「重新產生今日任務」按鈕（先呼叫假函式）。
- 候選／需確認／已採納／已完成 數量摘要（依 `task.status` 分組計算）。
- 全部／攻／守／增 篩選（`task.task_type`）。
- 任務卡清單，每張卡要有：類型 badge（攻=藍、守=珊瑚、增=綠）、對象名稱、why_now、objective、evidence_strength、value_score、action_mode、estimated_minutes、status、「開啟詳情」按鈕（點了之後導到 B 做的 `task_detail.py`，先用 session_state 存 selected_task_id 就好）。
- 重設 Demo 按鈕，要二次確認（`st.button` + 一個 checkbox 或第二次按鈕確認）。

### `itinerary.py` 必要元件（SPEC §13.5）
- 固定預約時間軸。
- 電話清單（`action_mode == phone` 的已採納任務）跟實訪清單分開顯示，**不要**把 phone 任務畫進地圖。
- 地圖只畫 `visit_sequence` 裡的點（可以直接沿用 `app/dashboard.py` 裡已經驗證過的 Plotly `Scattermapbox` 寫法，open-street-map style，不用 mapbox token）。
- 點位要標示順序數字、名稱、任務類型、目的。
- 上移／下移按鈕調整順序（改 `visit_sequence` 這個 list 的順序，存在 session_state）。
- 顯示總使用分鐘與剩餘分鐘。
- 一定要有一行字：「拜訪點位與建議順序示意，非即時導航或最佳路線」——這句話是 guardrail test 會檢查有沒有出現的正面表列，不能省略或改寫。

## CSV 匯出

在 `today_tasks.py` 加一個「匯出今日任務清單（CSV）」按鈕，把候選任務清單（含 task_type, target, why_now, objective, value_score, action_mode, estimated_minutes, status）用 `st.download_button` 匯出，可以直接參考舊系統 `app/dashboard.py` 裡 `export_table()` / `download_button` 的寫法（不要 import 舊模組本身，照抄寫法就好）。

## README 重寫要求（SPEC §19，14 項必須全部有）

新版 `README.md` 主標必須是 CENRA Mission，不再是「成交預判 Dashboard」。必須包含：
1. 一句產品定位（可以直接用：「CRM 記得昨天，CENRA Mission 讓業務決定今天。」）
2. Competition P0 功能範圍
3. Python 版本
4. 安裝方式
5. Demo seed／reset 方式
6. 測試方式（`pytest`）
7. Streamlit 啟動方式（`streamlit run app/mission_app.py`）
8. 三分鐘 Demo 操作步驟（照 SPEC §0.1 的 9 步驟寫）
9. 資料表摘要（抄 `00_CONTRACTS.md` 第 2 節的表格）
10. 合成資料與未串接真實系統揭露
11. AI／規則模組的誠實說明（rules-v1，不是監督式模型）
12. legacy 模組說明（一段話講清楚 `app/dashboard.py`、`model/` 是上一版提交，保留但新版不使用）
13. 已知限制
14. 不需要的外部服務／金鑰

**README 絕對不能出現**：AUC 0.618、15% 高風險、29% 競品壓力、54%→67%、IsolationForest 判斷競品入侵——這些是舊版敘事，新版要拿掉。

## Guardrail 測試（`tests/test_content_guardrails.py`）

對 `app/pages_mission/`、`app/mission_app.py`、`README.md` 這幾個檔案的文字內容，grep 下面這些禁用語句，出現任何一個就測試失敗：

```python
BANNED_PHRASES = [
    "已被競品入侵", "提升成交率", "路線最佳化", "建議主推產品",
    "AI 已證實", "已避免多少營收損失", "接上真實資料即可直接上線",
    "AUC 0.618", "0.618", "54%", "67%", "IsolationForest",
]
```
（`model/` 和 `docs/legacy_v1/` 底下的舊文件不檢查，那些本來就是允許保留的 legacy 內容，guardrail 只掃新版主應用會被使用者看到的檔案。）

## 你要驗證的東西（今天結束前）

1. `pytest tests/test_content_guardrails.py` 全綠。
2. 今日任務頁能篩選攻/守/增、能開一張任務詳情（跟 B 對接）。
3. 行程頁：phone 任務不出現在地圖上，只有 visit 任務出現且有順序數字。
4. README 從頭到尾看一遍，任何人拿到乾淨環境都能照著裝起來。

## 跟 B 對接的地方

B 的 `task_detail.py` 需要知道「使用者在 `today_tasks.py` 點了哪張任務」，用 `st.session_state["selected_task_id"]` 傳遞，這個 key 名稱先定案，不要中途改。
