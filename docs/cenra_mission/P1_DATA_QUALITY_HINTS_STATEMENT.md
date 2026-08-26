# P1｜更完整資料品質提示 Statement

- 文件版本：1.0
- 建立日期：2026-08-26
- 對應母文件：SPEC §5.2 P1 項目 3「更完整資料品質提示」
- 影響檔案：`app/pages_mission/task_detail.py`、`app/pages_mission/today_tasks.py`
- 性質：純 UI 層調整，讀既有欄位、不新增 domain 欄位、不動 engines／services

---

## 1. 現況（已讀程式碼確認，非推測）

資料品質相關的欄位其實都已經存在、也都已經算好了，只是 UI 沒有把它們用滿：

1. **`data_updated_at`**（`domain/models.py:116`）：任務詳情頁目前只是原樣印出日期——
   `task_detail.py:57`：`f"資料更新日期：{task.data_updated_at:%Y-%m-%d}"`，
   沒有換算成「幾天前」，也沒有依新鮮度分級（SPEC §11.2 證據強度本身就有「主要資料 30 天內
   更新」這條 30 天分界線，但 UI 沒有把這條線視覺化）。
2. **缺座標**：`task_detail.py:75-76` 已經有檢查
   `if task.lat is None or task.lon is None: st.caption("資料缺口：缺少座標資訊...")`，
   但只是一行普通說明文字（`st.caption`），跟其他一般說明文字視覺上沒有區隔，容易被忽略。
3. **`uncertainty_note`**（三個引擎都有填，見 `engines/attack.py:87`、`engines/defend.py:153`、
   `engines/grow.py:114-115`）：目前用 `st.warning()` 顯示（`task_detail.py:74`），這部分已經
   做得不錯，不需要再改。
4. **今日任務頁完全沒有任何資料新鮮度提示**——`today_tasks.py` 的任務卡片（第99-111行）
   只顯示 `evidence_strength`／`value_score`／`action_mode` 等，沒有任何欄位透露這張卡的
   證據是幾天前的資料算出來的。

## 2. 目標與驗收標準

- [ ] 任務詳情頁的「資料更新日期」旁邊，改成同時顯示相對天數，例如
      `資料更新日期：2026-08-13（12 天前）`。
- [ ] 資料更新超過 30 天（呼應 SPEC §11.2 證據強度「強」的 30 天門檻）時，用明顯的視覺標記
      （例如 `st.caption` 改成帶顏色的提示，或加一個小 badge）標出「資料較舊，建議業務自行
      核實」，而不是只有純文字。
- [ ] 缺座標的提示從普通 `st.caption` 升級成 `st.warning` 或等價的醒目樣式，並在文字裡明講
      「無法排入實訪點位地圖，只能安排電話或延後補資料」（呼應 SPEC §12.1 這條規則）。
- [ ] 今日任務頁的任務卡片，補上一個小圖示或文字，顯示這張任務的資料新鮮度（複用同一套
      「幾天前／缺座標」判斷邏輯，不要在兩個頁面各寫一份）。
- [ ] 不新增 domain 欄位、不改 engines 產生候選的邏輯，純粹是把已經算好的資料換一種方式呈現。
- [ ] 既有 pytest 測試不受影響（純 UI 顯示邏輯目前沒有測試覆蓋，這個改動也不需要新增
      unit test，但要手動過一次瀏覽器驗證）。

## 3. 建議做法

在 `app/pages_mission/` 底下新增一個小工具模組（例如 `data_quality.py`），集中兩個 helper，
讓 `task_detail.py` 和 `today_tasks.py` 共用，不要各寫一份：

```python
from datetime import date, datetime

def freshness_label(data_updated_at: datetime, as_of: date) -> str:
    days = (as_of - data_updated_at.date()).days
    return f"{data_updated_at:%Y-%m-%d}（{days} 天前）"

def is_stale(data_updated_at: datetime, as_of: date, threshold_days: int = 30) -> bool:
    return (as_of - data_updated_at.date()).days > threshold_days
```

`task_detail.py` 裡原本這行：

```python
f" · 資料更新日期：{task.data_updated_at:%Y-%m-%d}"
```

改成：

```python
f" · 資料更新日期：{freshness_label(task.data_updated_at, demo_date)}"
```

並在下面補一段（`is_stale` 為真時才顯示）：

```python
if is_stale(task.data_updated_at, demo_date):
    st.warning("資料已超過 30 天未更新，建議業務自行核實現況再行動。")
```

缺座標提示從：

```python
st.caption("資料缺口：缺少座標資訊，無法排入實訪點位地圖。")
```

改成：

```python
st.warning("資料缺口：缺少座標資訊，無法排入實訪點位地圖，只能安排電話或補齊資料後再排實訪。")
```

`today_tasks.py` 的任務卡片 `meta` 那一排（第107-110行）可以加一欄，複用同一個
`is_stale()` 判斷，資料太舊時顯示 `⚠️ 資料較舊`。

## 4. 明確排除事項

- 不要新增任何 domain 欄位（例如額外的 `freshness_score` 或 `data_quality_score`）——
  這個 P1 項目是「提示做得更完整」，不是「新增一套資料品質評分系統」，後者會牽動
  `services/scoring.py` 的統一評分公式，超出 P1 的範圍。
- 30 天這個門檻直接沿用 SPEC §11.2 證據強度已經定義的門檻，不要另外發明一個新數字。
- 不要因為這個改動去動 `engines/` 任何檔案——`data_updated_at`、`lat`/`lon`
  這些欄位本來就已經正確地從資料層一路帶到 UI，缺的只是 UI 呈現方式。

## 5. 驗證方式

```bash
streamlit run app/mission_app.py
```

1. 開一張守任務（例如安康診所），確認「資料更新日期」旁邊多了「N 天前」。
2. 開順心診所（缺座標情境，SPEC §9.2 的缺值情境），確認缺座標提示變成醒目的
   `st.warning` 樣式，不是普通灰字。
3. 手動把某張任務的 `data_updated_at` 改到 31 天前（或直接看資料裡本來就比較舊的任務），
   確認「資料較舊」的警示有跳出來；改到 29 天前確認不會誤跳。
4. 回「今日任務」頁確認卡片上也看得到新鮮度提示。
