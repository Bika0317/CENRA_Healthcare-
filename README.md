# CENRA Mission｜AI 診所業務任務指揮台

> CRM 記得昨天，CENRA Mission 讓業務決定今天。

2026 中化智匯盃 AI 創新應用挑戰賽｜中化裕民題目 2 原型：把 CRM 從紀錄工具變成戰略大腦，
將診所通路業務的「攻（新客開發）／守（流失挽回）／增（成長機會）」候選任務統一排序，
交給業務員審核（採納／修改／延後／拒絕），排成電話與實訪行程，完成後把結果寫回，形成閉環。

## 線上展示

- **v2｜CENRA Mission（現行版本）**：https://cenra-healthcare-dev.streamlit.app/
- v1｜精準打擊 Dashboard（上一版提交，保留供對照）：https://cenra-healthcare-dashboard.streamlit.app/

## Competition P0 功能範圍

- 三類任務引擎（攻／守／增），依規則從合成事件資料生成、附證據，不是黑箱模型。
- 統一任務價值分數排序（30% 訊號＋25% 商業價值＋20% 急迫性＋15% 證據＋10% 策略適配－成本懲罰）。
- 今日任務、任務詳情／審核、行程、結果回報四頁 Streamlit UI。
- 固定預約＋每日可用分鐘容量分配，實訪點位建議順序（nearest-neighbor 示意，非真實路網最佳化）。
- 審核／結果狀態機，SQLite 持久化，一鍵重設 Demo。
- CSV 任務清單匯出。
- 不做（P1／P2，見下方「已知限制」）：主管跨業務視圖、跨日分析、Excel 匯出、真實系統串接、監督式模型。

## Python 版本

Python 3.11（3.10+ 應該也可以，未特別驗證）。

## 安裝方式

```bash
pip install -r requirements.txt
```

## Demo Seed／Reset 方式

```bash
python -m data.fixtures.seed_generator
```

會用固定 random seed 重新產生 `data/fixtures/*.csv`（3 位業務、10 個主要 demo 帳戶、5 個潛在診所、
180+ 天訂單／互動、2 個固定預約），重複執行結果一致。

任務、審核、結果的 SQLite 資料庫（`data/db/mission.db`，不進版控）可以直接在「今日任務」頁按
**重設 Demo**（需勾選二次確認）清空回到初始狀態，不需要手動刪檔案。

## 測試方式

```bash
pytest
```

涵蓋 domain 狀態機、repository、三個任務引擎、評分公式、`build_daily_plan()`、審核／結果狀態機、
文案護欄（guardrail）共 60+ 個測試。

## Streamlit 啟動方式

```bash
streamlit run app/mission_app.py
```

預設在 `http://localhost:8501`（或用 `.claude/launch.json` 裡的 `cenra-mission` 設定，走 port 8502）。

## 三分鐘 Demo 操作步驟

1. 選擇一位診所通路業務（今日任務頁的業務選擇器）。
2. 查看固定預約與今日可用彈性時間。
3. 看到至少一張攻、守、增任務卡。
4. 開啟一張守任務，閱讀三項可查證證據。
5. 修改任務目的，將實訪改成電話並採納。
6. 開啟一張攻任務，改為電話約訪。
7. 到「行程」頁，看到只包含實訪任務的點位與建議順序。
8. 到「結果回報」頁，完成一筆任務並寫回結果與下一步日期。
9. 重新整理頁面（`F5`）後，上述審核與結果仍然存在（SQLite 持久化，不是 session 暫存）。

## 資料表摘要

| 檔案 | 欄位（依序） |
|---|---|
| `reps.csv` | rep_id, rep_name, region, email, daily_available_minutes, home_lat, home_lon |
| `accounts.csv` | account_id, name, specialty, region, status(active/at_risk/inactive), rep_id, lat, lon, value_band(high/medium/low), created_at, updated_at |
| `prospects.csv` | prospect_id, name, specialty, region, rep_id, contact_stage(uncontacted/contacted/appointment/trial), fit_band(high/medium/low), lead_source, source_updated_at, explicit_interest(bool), lat, lon |
| `interactions.csv` | interaction_id, target_type(account/prospect), target_id, rep_id, occurred_at, channel(visit/phone/event), summary_tag, note, next_step, due_date, resolved(bool), competitor_mentioned(bool) |
| `orders.csv` | order_id, account_id, rep_id, order_date, product_line, quantity, amount, status(completed/cancelled/returned) |
| `appointments.csv` | appointment_id, rep_id, target_id, appointment_date, start_time, duration_minutes, action_mode, purpose, status |

任務、審核、結果存在 SQLite（`data/task_repository.py`），欄位對應 `docs/cenra_mission/00_CONTRACTS.md`
第一節的 `Task` / `TaskReview` / `TaskOutcome` dataclass。

## 合成資料與未串接真實系統揭露

**所有資料都是合成的**（`data/fixtures/seed_generator.py` 用固定 random seed 產生），不是任何真實診所、
業務員或交易紀錄。系統沒有串接任何真實 CRM／ERP／SAP／OA、真實 LINE 或 Email 發送、真實路網或導航
API。地圖上的點位順序是簡化的 nearest-neighbor 示意，不是即時導航或最佳路線。

## AI／規則模組的誠實說明

三個任務引擎（`engines/attack.py` / `defend.py` / `grow.py`）與統一評分公式（`services/scoring.py`）
是**規則系統（`model_version="rules-v1"`），不是訓練出來的監督式模型**——沒有 AUC、沒有交叉驗證分數，
每一個判斷都能回溯到具體的訂單／互動證據，寫在任務卡的「三項主要證據」與「原因需業務確認」提示裡。
守任務沒有直接 `competitor_mentioned=true` 的來源事件時，文案只會標示「風險待查」，不會片面認定流失原因。

## Legacy 模組說明

`app/dashboard.py` 與 `model/` 是上一版提交（「精準打擊：AI 驅動的智慧巡訪與成交預判」系統，單一
成交機率排序＋公司 KPI Dashboard）留下的程式碼，**保留但新版 `app/mission_app.py` 不使用、不 import**。
仍可用 `streamlit run app/dashboard.py` 獨立執行。對應的說明文件搬到 `docs/legacy_v1/`。

舊版線上展示（Streamlit Community Cloud，跑的是 `app/dashboard.py`，不是 CENRA Mission）：
https://cenra-healthcare-dashboard.streamlit.app/

## 已知限制

- P1（不阻塞 P0，但這次沒做）：主管任務覆蓋視圖、跨日任務結果分析、多策略情境設定、Excel 匯出。
- P2（這次刻意不做）：真實 CRM／ERP／SAP／OA 串接、真實 LINE 或 Email 發送、真實路網／導航／最佳化
  API、監督式成交／流失／uplift 模型、即時線上模型重訓、自動產品推薦、登入／SSO／角色權限管理。
- 執行成本懲罰（SPEC §11.2）用業務駐地座標到候選座標的 haversine 直線距離換算車程分鐘數分級，
  假設均速 25 km/h——這是唯一需要自己假設的數字，不是真實路網時間，也不宣稱是。
- 點位順序（SPEC §12.2）依固定預約把一天切成好幾個時段，每段各自從上一個固定點（或業務駐地）
  出發排最近鄰；假設一天的工作時段是 08:30–18:00，SPEC 沒定義這個範圍，是自己假設的。
- 延後（defer）任務會在 `deferred_to` 那天被 `build_daily_plan()` 自動轉回候選（`task_repo.resurface_deferred_tasks()`）；
  已知取捨：分數沿用原本產生當天的計算結果，不會重新跑一次百分位。

## 不需要的外部服務／金鑰

不需要任何 API Key、SMTP 帳密、地圖服務金鑰或雲端資料庫連線字串——地圖用不需要 token 的
open-street-map 樣式，資料庫是本機 SQLite 檔案，全部可以在離線環境跑起來。
