# 精準打擊：AI 驅動的「智慧巡訪與成交預判」系統

2026 中化智匯盃 AI 創新應用挑戰賽｜中化裕民 CENRA+ Healthcare 賽題原型。

**線上展示**：https://esxawprwq7kwnvghmr8mbe.streamlit.app/

## 執行方式

```bash
pip install -r requirements.txt
python data/generate_synthetic_data.py   # 產生模擬 CRM 資料
python model/train_model.py               # 訓練成交預判模型
streamlit run app/dashboard.py            # 啟動展示 Dashboard
```

### 每日通知信（Dry Run）

```bash
python notify/send_daily_email.py
```

預設為 Dry Run：不會真的寄信，會把每位業務員的「今日建議拜訪清單」與主管的「高風險客戶彙總」渲染成 HTML，存到 `outbox/` 資料夾供預覽（Dashboard 的「每日通知信 / 匯出」頁籤也能直接預覽同樣內容）。

要正式啟用寄信與排程，需要：
1. 設定環境變數 `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM`（與 `MANAGER_EMAIL`）
2. 執行時加上 `--send` 參數
3. 用 Windows 工作排程器（`schtasks`）或 cron 設定每天定時觸發

## 專案結構
- `data/` 模擬資料產生器與資料檔（客戶、拜訪、訂單、業務員，含經緯度座標）
- `model/`
  - `features.py` 特徵工程（RFM、業績趨勢、拜訪-訂單轉換率等）
  - `train_model.py` 訓練成交預判模型（RandomForest）與風險偵測模型（IsolationForest）
  - `risk_model.py` 競品入侵風險：IsolationForest 無監督異常偵測
  - `explain.py` 客戶層級可解釋性：把模型分數翻譯成白話理由
  - `next_best_action.py` Next Best Action：依同儕（同通路×等級）品項滲透缺口推薦主推品項
  - `ab_test.py` 效益估計的 Bootstrap 信賴區間（非真實 A/B 測試，正式上線建議改用同期隨機分派驗證）
  - `ranking.py` 拜訪優先順序排序引擎
  - `review_log.py` Human-in-the-Loop 審核日誌：業務員標記 AI 建議「採納／修改／拒絕」並記錄，作為未來調整排序權重/重新訓練的回饋資料
  - `report.py` 日報/信件內容產生（email + LINE 訊息格式）、CSV/Excel 匯出格式
- `app/` Streamlit 展示介面：管理總覽（含客戶地理分佈地圖、效益信賴區間）、業務員每日建議（含拜訪路線地圖、Next Best Action）、
  客戶診斷（含系統判斷原因、Next Best Action）、模型洞察（含異常分數分佈）、每日通知信 / 匯出（含 LINE 訊息 mock）
- `notify/` 每日通知信排程腳本（預設 Dry Run，可切換為真實 SMTP 寄送）
- `docs/`
  - `cenra_topic_0803.pdf` 賽題原始 PDF
  - `generate_slide_assets.py` 用系統實際資料產生圖表（KPI 散佈圖、效益模擬、交叉驗證等）
  - `assets/` 上述腳本產出的圖表 PNG
  - `screenshots/` Dashboard 各頁籤的實際畫面截圖（`crop/` 為裁切後版本）

## 現況與待辦
- 目前使用合成資料驗證整條 pipeline，成交預判模型以 5-fold 交叉驗證得 AUC 0.618 ± 0.023（單次 holdout 為 0.608，兩者一致，模型表現穩定非抽樣運氣）；換上真實 CRM/ERP 資料後需重新訓練。
- 競品入侵風險已改用 IsolationForest 無監督異常偵測（`model/risk_model.py`），取代早期的規則式加權公式。
- 客戶層級可解釋性（`model/explain.py`）目前是「特徵重要性 × 同儕百分位」的簡化版說明，非嚴謹的 SHAP 值分解。
- 拜訪路線目前用直線連接示意優先順序，尚未串接真實路網導航（如 Google Maps Directions API）。
- 通知信目前為 Dry Run（存本地 HTML 預覽），尚未串接真實 SMTP 帳號與收件人信箱。
- LINE 通知目前僅為視覺化 mock，尚未串接 LINE Messaging API。
- 效益提升的信賴區間是用現有資料 bootstrap 重抽樣估計，不是真正隨機分派的 A/B 測試結果。
