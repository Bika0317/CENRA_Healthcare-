# P1｜Excel 匯出 Statement

- 文件版本：1.0
- 建立日期：2026-08-26
- 對應母文件：SPEC §5.2 P1 項目 5「Excel 匯出」
- 影響檔案：`app/pages_mission/today_tasks.py`（唯一需要改的檔案）
- 性質：UI 層新增一個匯出按鈕，不涉及 domain／engines／services 邏輯改動

---

## 1. 現況（已讀程式碼確認，非推測）

`today_tasks.py` 目前只有 CSV 匯出，實作在 `_export_csv()`：

```python
def _export_csv(tasks) -> bytes:
    buf = io.StringIO()
    buf.write("task_type,target_name,why_now,objective,value_score,action_mode,estimated_minutes,status\n")
    for t in tasks:
        cells = [
            TASK_TYPE_LABELS[t.task_type.value], t.target_name, t.why_now, t.objective,
            f"{t.value_score:.1f}", ACTION_MODE_LABELS[t.action_mode.value],
            str(t.estimated_minutes), STATUS_LABELS[t.status.value],
        ]
        buf.write(",".join('"' + c.replace('"', '""') + '"' for c in cells) + "\n")
    return buf.getvalue().encode("utf-8-sig")
```

透過 `st.download_button("匯出今日任務清單（CSV）", _export_csv(tasks), ...)` 掛在頁面最下面。
`requirements.txt` 已經有 `openpyxl`（原本是給舊版 `model/report.py` 用的），不需要新增依賴。

## 2. 目標與驗收標準

- [ ] 「今日任務」頁多一個「匯出今日任務清單（Excel）」按鈕，跟現有 CSV 按鈕並列。
- [ ] 匯出的 `.xlsx` 欄位與 CSV 版本一致（`task_type, target_name, why_now, objective, value_score, action_mode, estimated_minutes, status`），值也要一致（同一份 `tasks`，不要各自重算）。
- [ ] 中文欄位與內容不能亂碼，數字欄位（`value_score`、`estimated_minutes`）在 Excel 開起來要是可排序/加總的數字格式，不是純文字。
- [ ] 不改動 CSV 匯出既有行為，兩個按鈕同時存在。
- [ ] 既有 pytest 測試不受影響（這個改動不影響任何測試覆蓋到的函式）。

## 3. 建議做法

在 `today_tasks.py` 新增 `_export_xlsx(tasks) -> bytes`，用 `openpyxl.Workbook()` 直接寫記憶體再
用 `io.BytesIO()` 取出 bytes（跟 CSV 版本一樣回傳 bytes 給 `st.download_button`，不要落地寫暫存檔）：

```python
def _export_xlsx(tasks) -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "今日任務"
    headers = ["task_type", "target_name", "why_now", "objective",
               "value_score", "action_mode", "estimated_minutes", "status"]
    ws.append(headers)
    for t in tasks:
        ws.append([
            TASK_TYPE_LABELS[t.task_type.value], t.target_name, t.why_now, t.objective,
            round(t.value_score, 1), ACTION_MODE_LABELS[t.action_mode.value],
            t.estimated_minutes, STATUS_LABELS[t.status.value],
        ])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
```

`value_score` 寫 `round(t.value_score, 1)`（真正的 float）而不是字串，`estimated_minutes` 寫
`t.estimated_minutes`（int），這樣 Excel 才能直接排序/加總，不用像 CSV 那樣全部包成字串。

在既有 CSV 按鈕旁邊加一個新按鈕：

```python
st.download_button(
    "匯出今日任務清單（Excel）",
    _export_xlsx(tasks),
    file_name=f"{rep_id}_{demo_date}_today_tasks.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
```

## 4. 明確排除事項

- 不要做「多分頁 Excel」（例如攻/守/增各一個分頁）或加條件式格式（色階、篩選器）——SPEC 只要求
  「Excel 匯出」這個能力存在，不是要做一份正式報表，做過頭會超出 P1 的最小範圍。
- 不要把已完成/已排程等其他狀態的任務也混進同一份匯出（維持跟 CSV 版本一樣，只匯出目前
  `tasks = plan.candidate_tasks` 這批，不要另外開一個「全部歷史」的匯出範圍）。

## 5. 驗證方式

```bash
streamlit run app/mission_app.py
```

進「今日任務」頁，兩個按鈕都要能點，Excel 檔案下載後用 Excel／LibreOffice Calc 開起來確認：
1. 中文顯示正常。
2. `value_score` 欄位是靠右對齊的數字（不是靠左的文字）。
3. 資料列數與畫面上顯示的候選任務數一致。
