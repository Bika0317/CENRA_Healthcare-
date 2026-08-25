# CENRA Mission｜Codex 系統開發規格

> AI 診所業務任務指揮台｜Competition P0 Build Spec

- 規格版本：1.0
- 規格日期：2026-08-25
- 目標交付：2026 中化智匯盃初賽 Demo
- 對應題目：中化裕民題目 2——將 CRM 從紀錄工具提升為戰略大腦，減少無效拜訪，將資源集中於高價值或高風險客戶
- 實作基礎：學生現有 Streamlit 原型
- 本規格性質：decision-complete；Codex 應依此直接實作，不重新發散產品方向

---

## 0. Codex 執行摘要

Codex 必須將現有「多功能 Dashboard」大幅重構為 **CENRA Mission｜AI 診所業務任務指揮台**。

系統的主要使用時刻是：

> 診所通路業務每天出門前，輸入今日可用時間，查看跨「攻、守、增」三類候選任務，理解任務證據，採納、修改、延後或拒絕任務，再形成電話與實訪行程，最後回報結果。

P0 必須完成一條可重現的完整閉環：

> 合成事件資料 → 三類候選任務 → 統一價值排序 → 人工審核 → 電話／實訪安排 → 任務結果寫回 → 下一批次重新計算

Codex 不得把舊系統換皮後交付。首頁不得再以公司 KPI、平均成交機率、模型 AUC 或風險分布為主體。

### 0.1 P0 的唯一完成標準

在全新環境依 README 安裝與啟動後，陌生使用者能在三分鐘內完成下列流程：

1. 選擇一位診所通路業務。
2. 查看固定預約與今日可用彈性時間。
3. 看到至少一張攻、守、增任務卡。
4. 開啟一張守任務，閱讀三項可查證證據。
5. 修改任務目的，將實訪改成電話並採納。
6. 開啟一張攻任務，改為電話約訪。
7. 形成只包含實訪任務的點位與建議順序。
8. 完成一筆任務並寫回結果與下一步日期。
9. 重新整理頁面後，上述審核與結果仍存在。

若其中任何一步只能靠口頭解釋、無法在介面完成，P0 即不算完成。

---

## 1. Problem Statement

中化裕民的診所通路外勤業務同時處理新診所開發、既有客戶維繫、產品推廣、售後與後續事項。現有 CRM 能保存客戶、訂單與拜訪紀錄，但大量紀錄仍需業務自行閱讀、比較與取捨，無法直接回答：

> 今天有限的聯絡與外勤時間，最值得先用在哪一個任務上？

現有學生原型雖然提供成交預測、風險燈號、地圖、拜訪清單、產品建議、通知、模型驗證與 Human-in-the-Loop 等功能，但存在下列產品及技術問題：

1. 首頁以全公司 KPI 與模型視角為中心，不是業務今天的工作入口。
2. 所有功能平行陳列，缺乏一條清楚的使用流程。
3. 只針對既有客戶排名，沒有真正的新客開發任務。
4. 單一成交機率無法公平比較開發、挽回與成長三種不同目的。
5. 合成資料先寫入 `competitor_pressure`，模型再把該欄位當特徵，形成答案洩漏。
6. IsolationForest 只能發現異常，不能推論競品入侵原因。
7. 高風險比例以固定 contamination 決定，不代表真實風險發生率。
8. Bootstrap 先依預測分數挑高分客戶，再比較同一預測分數，不能當作效益證明。
9. 直線連點不是路網最佳化。
10. 自動產品推薦缺少產品適配、通路限制與法遵把關。
11. 審核紀錄只保存簡單採納／修改／拒絕，沒有任務狀態、延後、執行方式與結果閉環。
12. 單一大型 Streamlit 程式將資料、規則、模型與畫面耦合，難以測試與修改。

使用者需要的不是更多圖表，而是一個能將可觀察資料轉成有目的、可審核、可執行、可追蹤任務的工作系統。

---

## 2. Solution

建立 CENRA Mission，將 CRM、訂單、互動與地理資料轉成三類標準任務：

1. **攻｜開發任務**：找出值得首次接觸的高潛力新診所。
2. **守｜挽回任務**：找出尚未完全流失、目前仍可介入的既有診所。
3. **增｜成長任務**：找出合理的補貨或客戶服務深化時機。

三類任務先由各自的規則／分析引擎產生任務訊號，再轉成同一套任務價值分數。任務卡必須顯示：

- 為什麼現在。
- 可能錯失或獲得的商業價值。
- 建議行動及執行方式。
- 三項主要證據。
- 證據強度與資料缺口。
- 需要業務確認的未知事項。

業務可採納、修改、改電話、延後或拒絕。系統只替已採納的實訪任務安排點位順序；電話任務不進入地圖。任務完成後，業務回報結果與下一步，資料在下一個批次重新計算時影響候選任務。

### 2.1 產品價值主張

> CRM 記得昨天，CENRA Mission 讓業務決定今天。

### 2.2 產品原則

1. **任務優先於 Dashboard**：首頁第一眼是今日任務。
2. **證據優先於神秘分數**：每個分數都能追溯到可觀察欄位。
3. **人保留決策權**：AI 提出證據與選項，不替業務下命令。
4. **異常不等於原因**：沒有直接競品文字訊號，不得顯示競品入侵。
5. **電話也是有效任務**：不是每個高分對象都要實訪。
6. **先選任務，再排地點**：地圖只服務已確認的實訪任務。
7. **合成資料只驗證流程**：不宣稱 AUC、成交率提升或增量營收。
8. **P0 可穩定展示優先**：不為了技術炫技增加外部 API 或不穩定模型。

---

## 3. Actors

### 3.1 第一使用者：診所通路外勤業務

- 依區域負責既有診所與潛在新診所。
- 每日需要分配電話、實訪與固定預約時間。
- 擁有模型無法取得的客情與現場知識。
- 對任務採納、修改、延後、拒絕及結果負責。

### 3.2 第二使用者：區域主管

P0 不製作完整主管頁，但資料模型需支援未來查看：

- 高價值任務是否被覆蓋。
- 任務採納、修改、延後與拒絕原因。
- 各任務類型完成率與結果。
- 資料品質與系統性異常。

### 3.3 系統管理／產品負責人

P0 不製作管理後台，但設定應集中保存並可由程式設定調整：

- 任務觸發規則。
- 評分權重與門檻。
- 任務最低配額。
- 各執行方式的預估時間。
- 業務策略適配規則。

---

## 4. User Stories

### 4.1 每日規劃

1. As a 診所業務, I want to 選擇自己的身分與工作日期, so that 我只看到自己有權處理的任務。
2. As a 診所業務, I want to 看到今日固定預約, so that 必須完成的工作會先占用時間。
3. As a 診所業務, I want to 輸入今日可用彈性分鐘數, so that 任務安排符合當天實際容量。
4. As a 診所業務, I want to 同時看到攻、守、增三類任務, so that 我能跨工作目的進行取捨。
5. As a 診所業務, I want to 依全部或任務類型篩選, so that 我能快速聚焦特定工作。
6. As a 診所業務, I want to 看到候選、需確認、已採納與已完成數量, so that 我知道今日處理進度。
7. As a 診所業務, I want to 看到任務價值分數, so that 我能理解相對優先順序。
8. As a 診所業務, I want to 看到任務預估分鐘數與執行方式, so that 我能判斷當天是否做得完。

### 4.2 任務理解

9. As a 診所業務, I want to 看到「為什麼現在」, so that 我知道任務的時間敏感性。
10. As a 診所業務, I want to 看到三項主要證據, so that 我能查核系統判斷。
11. As a 診所業務, I want to 看到證據強度, so that 我能分辨可靠訊號與待確認假設。
12. As a 診所業務, I want to 看到資料更新日期, so that 我不會使用過期資訊。
13. As a 診所業務, I want to 看到資料缺口, so that 我知道要補問或補登什麼。
14. As a 診所業務, I want to 看到建議任務目的, so that 拜訪或電話具有明確目標。
15. As a 診所業務, I want to 看到前次互動摘要與未完成承諾, so that 我能快速準備。
16. As a 診所業務, I want to 看到訂單與互動時間線, so that 我能辨認變化而不是只看單一數字。
17. As a 診所業務, I want to 看到系統未知的原因, so that 我不會把異常誤認成競品入侵。

### 4.3 攻任務

18. As a 診所業務, I want to 看到高適配的新診所, so that 我能建立更高品質的新客漏斗。
19. As a 診所業務, I want to 看到科別、區域與接觸階段, so that 我能判斷是否值得首次聯絡。
20. As a 診所業務, I want to 將攻任務改為電話約訪, so that 我不必無預約直接上門。
21. As a 診所業務, I want to 知道新客資料來源與更新時間, so that 我能評估線索可信度。

### 4.4 守任務

22. As a 診所業務, I want to 收到核心品項停購、連續下降或互動中斷任務, so that 可挽回的客戶不會被忽略。
23. As a 診所業務, I want to 看到「風險待查」而不是被告知確定原因, so that 我能用現場知識確認真正問題。
24. As a 診所業務, I want to 在有直接競品文字訊號時看到提示, so that 我能準備相應問題。
25. As a 診所業務, I want to 先電話處理售後或服務事項, so that 不必將每項風險都安排成實訪。

### 4.5 增任務

26. As a 診所業務, I want to 收到接近個別補貨週期的提醒, so that 我能在合理時間確認需求。
27. As a 診所業務, I want to 看到近期訂單與歷史週期, so that 補貨提醒不是全體平均猜測。
28. As a 診所業務, I want to 看到品項機會證據而非自動產品結論, so that 我能依產品與法遵規範把關。

### 4.6 人工審核

29. As a 診所業務, I want to 採納任務, so that 任務能加入今日安排。
30. As a 診所業務, I want to 修改任務目的、時間與執行方式, so that 系統能反映真實客情。
31. As a 診所業務, I want to 延後任務並指定日期與原因, so that 有價值但不適合今天的任務不會消失。
32. As a 診所業務, I want to 拒絕任務並留下原因, so that 資料錯誤或不適用情境能被追蹤。
33. As a 診所業務, I want to 查看原始建議與修改後內容, so that 決策歷程可被稽核。
34. As a 診所業務, I want to 重新整理後保留審核狀態, so that Demo 與實際工作不會因頁面更新遺失。

### 4.7 行程與執行

35. As a 診所業務, I want to 讓固定預約優先進入行程, so that 系統不會排出無法執行的建議。
36. As a 診所業務, I want to 只將實訪任務放到地圖, so that 電話任務不會干擾路線。
37. As a 診所業務, I want to 看到拜訪點位與建議順序, so that 我能快速調整出門安排。
38. As a 診所業務, I want to 手動調整任務順序, so that 我能處理交通、預約與客情限制。
39. As a 診所業務, I want to 清楚看到這只是順序示意, so that 我不會把它誤認成即時導航或最佳路線。

### 4.8 結果回報

40. As a 診所業務, I want to 將任務標記完成或未完成, so that 系統知道實際執行情況。
41. As a 診所業務, I want to 選擇需求確認、補貨、後續約訪、無機會或資料錯誤, so that 結果能結構化保存。
42. As a 診所業務, I want to 填寫下一步日期與承諾事項, so that 後續任務能被產生。
43. As a 診所業務, I want to 補充簡短文字備註, so that 結構化選項不足時仍能保留客情。
44. As a 系統, I want to 在下一批次使用已完成結果, so that 過期候選任務不會重複出現。
45. As a 系統, I want to 保留生成版本與人工修改軌跡, so that 未來模型與規則可被驗證。

### 4.9 Demo 與維運

46. As a 評審, I want to 在沒有真實企業資料時看懂完整流程, so that 我能評估產品與落地價值。
47. As a Demo 操作者, I want to 一鍵重設固定情境, so that 每次展示都能從相同狀態開始。
48. As a 開發者, I want to 使用固定 random seed, so that 任務分數與畫面不會每次改變。
49. As a 開發者, I want to 將規則、儲存與 UI 分離, so that 我能獨立測試核心行為。
50. As a 開發者, I want to 在資料缺漏時看到明確錯誤, so that 問題不會被空白頁或錯誤分數掩蓋。

---

## 5. Scope and Definition of Done

### 5.1 P0 必做

1. 品牌、導覽與首頁全面改為 CENRA Mission。
2. 單一診所通路場景；不混用醫院、藥局與零售邏輯。
3. 三類任務引擎：攻、守、增。
4. 統一任務價值評分。
5. 今日任務首頁。
6. 任務詳情／診所 360。
7. 採納、修改、改電話、延後、拒絕。
8. 固定預約與每日可用分鐘數。
9. 實訪點位與建議順序示意。
10. 完成／未完成與結果回報。
11. 審核、狀態與結果持久化。
12. 一鍵重設固定 Demo。
13. CSV 任務匯出。
14. 最小自動測試與 README。
15. 清楚揭露合成資料與功能限制。

### 5.2 P1 可做但不得阻塞 P0

1. 主管任務覆蓋視圖。
2. 跨日任務結果分析。
3. 更完整資料品質提示。
4. 多策略情境設定。
5. Excel 匯出。

### 5.3 P2 不做

1. 真實 CRM／ERP／SAP／OA 串接。
2. 真實 LINE 或 Email 發送。
3. 真實路網、導航或最佳化 API。
4. 監督式成交、流失或 uplift 模型。
5. 即時線上模型重訓。
6. 自動產品推薦。
7. 登入、SSO、角色權限管理後台。
8. 病患層級資料。
9. 精確營收提升或 ROI 承諾。

---

## 6. Existing Prototype Audit and Migration Decisions

### 6.1 可沿用

| 現有能力 | 決策 |
|---|---|
| Streamlit 應用框架 | 沿用，避免競賽前重寫前後端 |
| pandas／NumPy 資料處理 | 沿用 |
| Plotly 圖表與 OSM 地圖 | 沿用，但只服務任務詳情與點位順序 |
| CSV／Excel 匯出工具 | 保留 CSV，Excel 降為 P1 |
| Human-in-the-Loop 概念 | 沿用概念，資料結構與狀態機重做 |
| Email／LINE Mock | 不進 P0 主導覽；舊程式可保留但不得干擾 Demo |
| 可解釋理由文字 | 保留「白話理由」概念，改用任務證據生成，不使用全域 feature importance 偽裝個案解釋 |

### 6.2 必須替換

| 現有能力 | 替換方式 |
|---|---|
| 單一成交機率排名 | 改成三類任務內部訊號＋統一任務價值層 |
| IsolationForest 競品風險 | 改成明確規則與「異常待查」語義；P0 可完全不載入模型檔 |
| 固定 15% 高風險 | 取消；任務是否產生由可觀察觸發條件決定 |
| `competitor_pressure` 隱藏真值 | 從新版資料完全移除 |
| Bootstrap 效益圖 | 從 UI、報告與 README 的主要敘事移除 |
| 全公司管理總覽 | 從 P0 主導覽移除 |
| 直線連接稱為路線 | 改稱「拜訪點位與建議順序示意」 |
| 自動 Next Best Action 產品推薦 | P0 只顯示應準備的資訊與機會證據 |
| 單一大型 Dashboard | 拆成 UI、應用服務、任務領域、資料儲存與規則模組 |

### 6.3 舊模型與舊畫面的處理

1. 不需在競賽前破壞性刪除舊檔。
2. 舊模型、舊報告與舊頁面可移入明確的 legacy 區域或停止由主應用匯入。
3. 新主應用啟動時不得訓練或載入舊 purchase／risk 模型。
4. README 必須把舊指標標成 legacy，不得讓使用者誤認為新版成效。
5. 新版的測試與啟動不得依賴舊 pickle、舊 ROC 或 Bootstrap 產物。

---

## 7. Implementation Decisions

### 7.1 技術棧

- Python 3.11 或更新的相容版本。
- Streamlit 作為展示介面。
- pandas／NumPy 作為資料與分析工具。
- Plotly 作為時間線、簡易圖表與 OSM 點位圖。
- SQLite 作為任務審核、狀態與結果的 P0 持久化儲存。
- CSV 作為固定合成資料 fixtures。
- Python dataclass 或等價型別定義領域物件；P0 不增加重型 Web API 框架。
- pytest 作為測試框架。
- Streamlit AppTest 或等價高層 smoke test 驗證主要頁面可啟動。

### 7.2 架構邊界

系統拆成五個清楚邊界：

1. **Domain**：任務、證據、審核決策、行程項目與結果等領域物件及狀態規則。
2. **Data**：CSV 載入、schema 驗證、SQLite repository、Demo seed／reset。
3. **Mission Engines**：攻、守、增候選任務產生與任務證據。
4. **Application Service**：跨引擎整合、評分、容量選擇、行程建議與結果寫回。
5. **UI**：Streamlit 頁面、session state、表單、視覺元件與導覽。

UI 不得直接實作評分公式或直接寫 CSV／SQLite。所有主要使用流程都由 Application Service 提供。

### 7.3 最高測試 seam

主要測試 seam 為「每日任務服務」：

> 給定業務、日期、可用分鐘數與 repository，產生完整 Daily Plan。

Daily Plan 必須包含：

- 固定預約。
- 候選任務。
- 跨任務排序結果。
- 建議選取任務。
- 剩餘分鐘數。
- 實訪點位順序。
- 任務及證據資料。

核心測試應從此 seam 驗證外部行為，不應逐一綁死內部 helper 實作。

### 7.4 Domain glossary

| 名稱 | 定義 |
|---|---|
| Account | 已合作的診所帳戶 |
| Prospect | 尚未合作的潛在診所 |
| Interaction | 電話、拜訪或活動等互動事件 |
| Order | 已發生的診所訂單事件 |
| Mission Task | 系統於特定日期針對 Account 或 Prospect 產生的可執行任務 |
| Attack／攻 | 新診所開發任務 |
| Defend／守 | 既有診所風險待查或挽回任務 |
| Grow／增 | 既有診所補貨或成長機會任務 |
| Evidence | 支持任務的可查證資料片段 |
| Evidence Strength | 任務證據的完整度、新鮮度與多樣性分級，不是預測機率 |
| Review Decision | 業務對任務的採納、修改、延後或拒絕 |
| Outcome | 任務執行後的結構化結果與下一步 |
| Daily Plan | 固定預約、已選任務、容量與點位順序的集合 |

### 7.5 任務狀態機

允許狀態：

1. `candidate`：系統產生，尚未審核。
2. `accepted`：業務接受原始任務。
3. `modified`：業務修改目的、方式、時間或備註後接受。
4. `deferred`：延後；必須具有原因與下一日期。
5. `rejected`：拒絕；必須具有原因。
6. `scheduled`：已加入今日行程或電話清單。
7. `completed`：已執行並填寫結果。
8. `not_completed`：今日未完成並填寫原因。
9. `cancelled`：固定預約或任務被取消；必須填寫原因。

狀態規則：

- candidate 只能轉為 accepted、modified、deferred 或 rejected。
- accepted／modified 可轉為 scheduled。
- scheduled 可轉為 completed、not_completed 或 cancelled。
- deferred 在下一日期重新成為候選任務時，必須保留前次來源關聯。
- rejected 不在同一批次重新產生。
- completed 不可直接改回 candidate；修正須新增稽核紀錄。
- 每次轉移都必須保存 actor、timestamp、原始值、修改後值與 reason。

### 7.6 批次與時間語義

- Demo 基準日期固定在設定檔，避免使用系統真實日期造成資料過期。
- 使用者可切換已提供的 Demo 日期，但不得任意超出 fixture 範圍。
- 候選任務由明確的「重新產生今日任務」動作觸發，不因每次 Streamlit rerun 重複寫入。
- 同一業務、日期、目標與任務類型只能有一個 active candidate。
- 任務產生必須具 idempotency；重跑相同輸入不建立重複任務。
- 任務完成或拒絕後，下一批次依規則決定是否產生新的不同任務。
- 單筆回饋不觸發模型重訓。

---

## 8. Data Model

### 8.1 reps

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---:|---|
| rep_id | string | 是 | 穩定識別碼 |
| rep_name | string | 是 | Demo 顯示名稱 |
| region | string | 是 | 負責區域 |
| email | string | 否 | P0 不寄信 |
| daily_available_minutes | integer | 是 | 預設彈性時間，Demo 可修改 |

### 8.2 accounts

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---:|---|
| account_id | string | 是 | 穩定識別碼 |
| name | string | 是 | 診所名稱 |
| specialty | enum/string | 是 | 診所科別 |
| region | string | 是 | 所在區域 |
| status | enum | 是 | active／at_risk／inactive |
| rep_id | string | 是 | 負責業務 |
| lat | float | 是 | Demo 點位 |
| lon | float | 是 | Demo 點位 |
| value_band | enum | 是 | high／medium／low，不宣稱精確未來價值 |
| created_at | datetime | 是 | 資料建立時間 |
| updated_at | datetime | 是 | 資料新鮮度判斷 |

### 8.3 prospects

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---:|---|
| prospect_id | string | 是 | 穩定識別碼 |
| name | string | 是 | 診所名稱 |
| specialty | string | 是 | 診所科別 |
| region | string | 是 | 所在區域 |
| rep_id | string | 是 | 指派業務 |
| contact_stage | enum | 是 | uncontacted／contacted／appointment／trial |
| fit_band | enum | 是 | high／medium／low |
| lead_source | string | 是 | Demo 資料來源 |
| source_updated_at | datetime | 是 | 線索新鮮度 |
| explicit_interest | boolean | 是 | 是否有可觀察的回應訊號 |
| lat | float | 是 | Demo 點位 |
| lon | float | 是 | Demo 點位 |

### 8.4 interactions

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---:|---|
| interaction_id | string | 是 | 穩定識別碼 |
| target_type | enum | 是 | account／prospect |
| target_id | string | 是 | 對象識別碼 |
| rep_id | string | 是 | 執行業務 |
| occurred_at | datetime | 是 | 當時已知時間 |
| channel | enum | 是 | visit／phone／event |
| summary_tag | enum/string | 是 | demand／service／price／competitor／follow_up 等 |
| note | string | 否 | 簡短合成紀錄 |
| next_step | string | 否 | 承諾事項 |
| due_date | date | 否 | 承諾期限 |
| resolved | boolean | 是 | 是否完成 |
| competitor_mentioned | boolean | 是 | 只有明確文字事件才為 true |

### 8.5 orders

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---:|---|
| order_id | string | 是 | 穩定識別碼 |
| account_id | string | 是 | 已合作診所 |
| rep_id | string | 是 | 負責業務 |
| order_date | date | 是 | 訂單日期 |
| product_line | string | 是 | 大類即可 |
| quantity | number | 是 | 正值 |
| amount | number | 是 | 非負值 |
| status | enum | 是 | completed／cancelled／returned |

### 8.6 appointments

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---:|---|
| appointment_id | string | 是 | 穩定識別碼 |
| rep_id | string | 是 | 業務 |
| target_id | string | 是 | Account 或 Prospect |
| appointment_date | date | 是 | 日期 |
| start_time | time | 是 | 固定時間 |
| duration_minutes | integer | 是 | 正整數 |
| action_mode | enum | 是 | phone／visit |
| purpose | string | 是 | 固定任務目的 |
| status | enum | 是 | fixed／completed／cancelled |

### 8.7 tasks

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---:|---|
| task_id | string | 是 | 穩定識別碼 |
| generation_key | string | 是 | 保證相同批次不重複 |
| generated_at | datetime | 是 | 生成時間 |
| task_date | date | 是 | 建議執行日期 |
| rep_id | string | 是 | 負責業務 |
| target_type | enum | 是 | account／prospect |
| target_id | string | 是 | 對象 |
| task_type | enum | 是 | attack／defend／grow |
| title | string | 是 | 短標題 |
| why_now | string | 是 | 為什麼現在 |
| objective | string | 是 | 原始建議目的 |
| action_mode | enum | 是 | phone／visit |
| estimated_minutes | integer | 是 | 容量使用 |
| signal_score | number | 是 | 0–100 |
| business_value_score | number | 是 | 0–100 |
| urgency_score | number | 是 | 0／50／100 |
| evidence_score | number | 是 | 40／70／100 |
| strategy_fit_score | number | 是 | 0／50／100 |
| cost_penalty | number | 是 | 0–20 |
| value_score | number | 是 | clamp 後 0–100 |
| evidence_strength | enum | 是 | weak／medium／strong |
| uncertainty_note | string | 是 | 需要人工確認之處 |
| data_updated_at | datetime | 是 | 最近資料時間 |
| model_version | string | 是 | P0 使用 rules-v1 |
| status | enum | 是 | 任務狀態機之一 |

### 8.8 task_evidence

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---:|---|
| evidence_id | string | 是 | 穩定識別碼 |
| task_id | string | 是 | 任務 |
| code | string | 是 | 可測試的原因碼 |
| label | string | 是 | 人類可讀標籤 |
| display_value | string | 是 | 例如「45 天未有效互動」 |
| source_type | enum | 是 | order／interaction／account／prospect／appointment |
| source_id | string | 否 | 對應來源事件 |
| occurred_at | datetime | 否 | 訊號時間 |
| strength | enum | 是 | weak／medium／strong |

### 8.9 task_reviews

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---:|---|
| review_id | string | 是 | 穩定識別碼 |
| task_id | string | 是 | 任務 |
| decision | enum | 是 | accept／modify／defer／reject |
| original_objective | string | 是 | 原始目的 |
| modified_objective | string | 否 | 修改後目的 |
| original_action_mode | enum | 是 | 原始方式 |
| modified_action_mode | enum | 否 | 修改後方式 |
| reason_code | string | 是 | 結構化原因 |
| reason_note | string | 否 | 補充說明 |
| deferred_to | date | 否 | defer 必填 |
| actor_rep_id | string | 是 | 操作者 |
| created_at | datetime | 是 | 稽核時間 |

### 8.10 task_outcomes

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---:|---|
| outcome_id | string | 是 | 穩定識別碼 |
| task_id | string | 是 | 任務 |
| execution_status | enum | 是 | completed／not_completed／cancelled |
| outcome_type | enum | 是 | demand_confirmed／replenishment／follow_up_booked／no_opportunity／data_error／service_resolved／other |
| note | string | 否 | 簡短補充 |
| next_step | string | 否 | 後續承諾 |
| next_date | date | 否 | 後續日期 |
| completed_at | datetime | 是 | 結果時間 |
| actor_rep_id | string | 是 | 操作者 |

### 8.11 資料驗證規則

1. 所有 ID 在各表內唯一。
2. 所有外鍵可解析；孤兒事件必須使 seed 失敗。
3. 日期不可晚於 Demo cutoff，除了明確的 appointment／next_date。
4. 訂單金額、數量、分鐘數不可為負。
5. 座標需落在合理台灣範圍；缺座標的實訪任務仍可存在，但成本懲罰 12 且不進地圖。
6. competitor_mentioned 不可由隱藏壓力欄位生成；必須對應一筆可見互動事件。
7. 任務至少一項、最多三項主要證據；詳情可另顯示次要證據。
8. P0 不包含病患、處方或個人健康資料。

---

## 9. Synthetic Demo Dataset

### 9.1 固定規模

Demo seed 建議包含：

- 3 位業務。
- 每位業務 8–12 個既有診所帳戶。
- 每位業務 3–5 個潛在診所。
- 至少 180 天訂單與互動事件。
- 每位業務在主要 Demo 日有 2 個固定預約。
- 主要 Demo 業務在該日產生 8 個候選任務。
- 8 個候選任務至少含攻 2、守 3、增 3。

### 9.2 必備情境

1. **守／高優先**：核心品項連續兩期下降、45 天未有效互動、售後承諾逾期；原因未知。
2. **攻／高適配**：位於服務區、科別適配、未約訪；預設建議先電話。
3. **增／補貨時機**：接近個別歷史補貨週期、近期尚未下單。
4. **守／電話優先**：售後問題未完成，不需直接實訪。
5. **增／弱證據**：疑似品項機會但資料不足，要求人工確認。
6. **明確競品訊號**：至少一筆互動文字標記 competitor_mentioned=true，可展示與一般異常的差異。
7. **缺值情境**：一筆缺少座標或互動摘要，展示證據強度降低。
8. **不產生任務情境**：資料不足或剛完成相同任務，不應重複生成。

### 9.3 生成原則

1. 先生成事件，再由規則產生任務；不可先指定最終風險 label 再回填特徵。
2. 使用固定 seed，讓畫面與分數可重現。
3. 診所名稱使用明顯的虛構名稱，不使用真實機構名稱。
4. 事件時間、訂單趨勢與觸發規則要互相一致。
5. 不生成 `competitor_pressure`、`will_purchase`、`is_high_risk` 等隱藏答案欄位。
6. 可生成 outcome 供歷史展示，但不得拿合成 outcome 宣稱模型效益。

---

## 10. Mission Engine Rules

### 10.1 共通資格條件

候選任務只針對：

- 與業務 rep_id 相符的對象。
- 對象位於業務服務區，或具有明確跨區指派。
- 目標資料未被標示 inactive／invalid。
- 同一目標、任務類型與日期不存在 active 任務。
- 近期沒有已完成且尚在冷卻期的同類任務。

必要觸發欄位缺失時不產生任務；非必要欄位缺失時降低 evidence score。

### 10.2 攻｜Attack Engine

#### 觸發條件

- Prospect 尚未合作。
- 位於負責區域。
- fit_band 不為 low。
- contact_stage 為 uncontacted 或 contacted，且目前沒有固定 appointment。

#### 原始任務訊號

- 科別／策略適配：50%。
- 明確興趣或活動回應：30%。
- 線索來源新鮮度與完整度：20%。

原始分數轉為同類 Attack candidates 的 0–100 百分位，成為 signal score。

#### 任務輸出

- 預設 action mode 為 phone。
- objective 為「確認需求與合適拜訪時間」。
- 不顯示精確成交機率。
- 若已存在 appointment，改由固定預約處理，不再產生一般 Attack task。

### 10.3 守｜Defend Engine

#### 任一強觸發或兩個一般觸發即可產生

強觸發：

- 核心產品線由穩定採購轉為連續兩個個別週期未購買。
- 未完成承諾已逾期至少 7 天。
- 明確服務／客訴事項未解決且已逾期。

一般觸發：

- 近兩個可比較期間的訂單金額下降。
- 距離上次有效互動超過該帳戶歷史常態。
- 品項廣度下降。
- 有直接 competitor_mentioned 互動事件。

#### 原始任務訊號

- 核心品項停購：35%。
- 訂單趨勢下降：25%。
- 互動中斷：15%。
- 逾期承諾／服務事項：15%。
- 直接客訴或競品文字訊號：10%。

只使用可觀察欄位。若沒有直接競品事件，任務文字只能是「風險待查」或「異常待查」。

#### 任務輸出

- 預設 action mode：有未完成服務事項時為 phone；其他情況可為 visit。
- uncertainty note 必須包含「原因需業務確認」。
- 不顯示「疑似競品入侵」，除非 evidence 包含直接 competitor_mentioned=true 的來源事件。

### 10.4 增｜Grow Engine

#### 觸發條件

至少一項：

- 距離個別中位補貨間隔落在前後 20% 時間窗內，且近期尚未下單。
- 客戶穩定採購但品項廣度相對自身歷史下降。
- 互動事件具有 demand 或 product_interest 標記，且尚未完成下一步。

#### 原始任務訊號

- 個別補貨時間窗：50%。
- 過去採購穩定度：20%。
- 自身歷史品項缺口：20%。
- 明確需求／產品興趣事件：10%。

#### 任務輸出

- objective 為「確認補貨／需求並準備相關資訊」。
- 不自動輸出產品名稱、劑量、醫療宣稱或保證適配。
- 可顯示歷史產品線與近期缺口作為證據。

---

## 11. Unified Task Scoring

### 11.1 公式

任務價值分數為：

> 30% 任務訊號 + 25% 相對商業價值 + 20% 急迫性 + 15% 證據強度 + 10% 策略適配度 − 執行成本懲罰

最終值以 `max(0, min(100, raw score))` 限制於 0–100。

### 11.2 欄位定義

#### 任務訊號

- 各任務引擎先計算原始分數。
- 只在同一任務類型、同一批次候選群體中轉為 percentile。
- 只有一個候選時使用 70，避免單一候選自動變 100。

#### 相對商業價值

- Existing Account 使用近 180 天已完成訂單金額；資料不足時使用 value_band 映射。
- Prospect 使用 opportunity／value band，不虛構精確金額。
- 只在同任務類型內轉 percentile。

#### 急迫性

- 100：固定期限已逾期、補貨窗口剩 7 天內、或明確時效事件。
- 50：補貨窗口 8–14 天、連續下降或接觸階段需跟進。
- 0：沒有明確時間窗。

#### 證據強度

- 100／strong：至少三個可追溯訊號，且主要資料 30 天內更新。
- 70／medium：兩個訊號，或一個強觸發加完整來源。
- 40／weak：只有最低可產生條件，或非必要資料缺失／過期。
- 缺少必要觸發資料時不產生任務，不使用 0 分任務混入排名。

#### 策略適配度

- 100：區域與當期重點科別／產品線皆符合。
- 50：只符合區域或一般服務範圍。
- 0：策略不適配；若同時不符合權限，應直接排除而非只給 0 分。

#### 執行成本懲罰

- phone：2。
- visit、交通估計不超過 30 分鐘：6。
- visit、31–60 分鐘：10。
- visit、超過 60 分鐘：15。
- 缺少距離／座標資料：12。
- 額外準備成本：0–5。
- 合計最高 20。

### 11.3 候選門檻與 tie-break

- value score 低於 45 不列入今日候選清單，但可在 debug／資料檢查顯示。
- evidence score 至少 40。
- 同分時依序比較：急迫性、固定期限、證據強度、較低成本、穩定 task_id。

### 11.4 容量與任務選取

1. 固定預約先占用當日分鐘數。
2. 從剩餘分鐘中，攻／守／增各先選 1 個合格任務作為最低 Demo 配額。
3. 若某類沒有合格任務，配額釋出。
4. 其餘依 value score 由高至低加入，直到剩餘時間不足。
5. phone 預設 20 分鐘。
6. visit 預設服務 45 分鐘，加上簡化交通分鐘數。
7. UI 必須顯示「建議選取」，但仍由業務採納後才進入 scheduled。

---

## 12. Scheduling and Map Behavior

### 12.1 行程選取

- 固定預約不可被自動移除。
- accepted／modified 任務才可加入行程。
- phone 任務進入電話清單，不進地圖。
- visit 任務具有效座標才進地圖。
- 缺座標的 visit 任務顯示資料品質提醒，允許業務改 phone 或延後。

### 12.2 建議順序

P0 使用可重現的簡單啟發式：

1. 依固定 appointment time 切分可用時段。
2. 每個時段從上一固定點或區域中心出發。
3. 以最近鄰方式排列尚未排序的 visit tasks。
4. 若兩點距離相同，以較高 value score 排前。
5. 不呼叫外部路網 API。

### 12.3 UI 用詞

允許：

- 拜訪點位。
- 建議順序示意。
- 可拖曳／按鈕調整順序。

禁止：

- 最佳路線。
- 即時導航。
- 節省 X% 車程。

---

## 13. UI and Interaction Specification

### 13.1 全域視覺

- 延續簡報的深森林綠、薄荷綠、藍、珊瑚、琥珀配色。
- Attack 使用藍、Defend 使用珊瑚、Grow 使用綠。
- 主要內容保持明亮背景與高對比文字。
- 不使用大量紅黃綠風險燈號作為核心導覽。
- 不在首頁放模型 AUC、全公司客戶總數或平均成交機率。
- 所有 Demo 數字旁須能看出是合成資料情境。

### 13.2 導覽

P0 只有四個主要頁面：

1. 今日任務。
2. 任務詳情／審核。
3. 行程示意。
4. 結果回報。

模型洞察、管理總覽、通知與大範圍匯出不得出現在 P0 主導覽；可放 legacy 或完全隱藏。

### 13.3 今日任務頁

必要元件：

- 業務選擇器。
- Demo 日期。
- 固定預約摘要。
- 可用彈性分鐘輸入。
- 「重新產生今日任務」動作。
- 候選、需確認、已採納、已完成摘要。
- 全部／攻／守／增篩選。
- 任務卡清單。
- 重設 Demo 動作；需二次確認。

任務卡必要欄位：

- 類型 badge。
- 診所／Prospect 名稱。
- why now。
- objective。
- evidence strength。
- value score。
- action mode。
- estimated minutes。
- status。
- 開啟詳情動作。

### 13.4 任務詳情／審核頁

必要區塊：

1. 任務摘要：類型、名稱、分數、生成時間與狀態。
2. 三項主要證據：標籤、值、來源時間。
3. 訂單／互動時間線。
4. 前次互動摘要與未完成承諾。
5. uncertainty note 與資料缺口。
6. 原始 objective 與 action mode。
7. 審核表單。

審核表單行為：

- Accept：保存原始目的與方式。
- Modify：至少修改目的、方式或時間之一，並填 reason code。
- Defer：必填原因與未來日期。
- Reject：必填 reason code；note 選填。
- 所有成功操作顯示明確確認訊息。
- 失敗不可部分寫入。

### 13.5 行程頁

- 顯示固定預約時間軸。
- 分開顯示電話清單與實訪清單。
- 地圖只顯示實訪點位。
- 點位顯示順序、名稱、任務類型與目的。
- 提供上移／下移或等價方式調整順序。
- 顯示總使用分鐘與剩餘分鐘。
- 顯示「順序示意，非即時導航或最佳路線」。

### 13.6 結果回報頁

- 只列 scheduled 且尚未完成的任務。
- 可選 completed／not_completed／cancelled。
- completed 必填 outcome type。
- not_completed／cancelled 必填 reason。
- next step 與 next date 為條件式欄位。
- 成功後更新任務狀態並顯示稽核時間。
- 已完成任務以折疊歷程顯示，不可再次重複送出。

### 13.7 Empty／Error／Loading States

- 沒有合格任務：說明原因，提供查看篩選或重設 Demo，不生成假任務。
- 資料 schema 錯誤：顯示缺少欄位與資料表名稱，不顯示完整 stack trace 給一般使用者。
- 任務已被其他操作更新：重新讀取並提示狀態已變更。
- SQLite 不可寫：停止審核／結果操作並顯示明確錯誤，不假裝成功。
- 地圖無座標：保留任務卡，提示改電話或補資料。

---

## 14. Persistence and Repository Contracts

### 14.1 Fixture repository

負責讀取 reps、accounts、prospects、interactions、orders 與 appointments。

必須：

- 啟動時驗證 schema。
- 日期欄位明確 parse。
- 不在 UI 重複讀取與轉型。
- 提供按 rep、date、target 查詢的穩定介面。

### 14.2 Task repository

負責 tasks、evidence、reviews、outcomes 與 status transition audit。

必須：

- 以 transaction 寫入任務與證據。
- 以 generation key 保證 idempotency。
- 以 transaction 寫入 review 與 task status。
- 以 transaction 寫入 outcome 與 task status。
- 提供 reset demo；只重設 Demo database，不修改 fixtures。
- 不從 UI 直接執行 SQL。

### 14.3 Demo reset

重設動作必須：

1. 二次確認。
2. 清除任務、證據、審核、結果與 audit state。
3. 重新建立固定 Demo 狀態。
4. 不重新隨機產生不同資料。
5. 顯示完成時間。

---

## 15. Explanations and Copy Rules

### 15.1 任務文字必須由 reason codes 產生

UI 文案不可直接拼接任意模型欄位。每個 evidence code 對應：

- 人類可讀 label。
- display value formatter。
- source type。
- 可接受的任務類型。
- 是否屬於直接競品訊號。

### 15.2 可用語句

- 流失風險待查。
- 異常待查。
- 接近個別補貨週期。
- 高適配潛在診所。
- 證據強度：弱／中／強。
- 原因需業務確認。
- 任務價值分數用於 Demo 排序。

### 15.3 禁止語句

- AI 已證實提升成交率。
- 客戶已被競品入侵。
- 模型準確預測競品。
- 這個產品一定適合該診所。
- 路線已最佳化。
- 已避免多少營收損失。
- 接上真實資料即可直接上線。

---

## 16. Testing Decisions

### 16.1 測試哲學

- 測試外部可觀察行為，不測 private helper 的實作細節。
- 主要 seam 是 Daily Mission Service。
- 使用固定 fixtures 與固定 clock，避免依系統日期或亂數失敗。
- 核心商業規則必須能在沒有 Streamlit 的情況下測試。
- UI 測試只驗證主要流程與元件存在，不以像素或脆弱 selector 綁死排版。

### 16.2 Domain／Service 測試

至少涵蓋：

1. Attack 只針對合格 Prospect 產生。
2. 已有 appointment 的 Prospect 不重複產生 Attack task。
3. Defend 在強觸發時產生。
4. 單一輕微信號不足時不產生 Defend task。
5. 無直接 competitor evidence 時文案不含競品入侵。
6. 有直接 competitor evidence 時才顯示疑似競品因素。
7. Grow 使用個別補貨週期而非全體平均。
8. 必要資料缺失時不產生；非必要資料缺失時降低 evidence score。
9. 分數公式與 clamp 正確。
10. 單一候選的 signal percentile 使用 70。
11. tie-break 穩定且可重現。
12. value score 低於門檻不進今日候選。
13. 固定預約先占用容量。
14. 三類最低配額在有合格任務時生效。
15. 某類無候選時配額釋出。
16. phone 不進地圖。
17. 缺座標 visit 不進地圖且具有警告。
18. 最近鄰順序對固定 fixtures 可重現。
19. 相同 generation input 重跑不建立重複任務。
20. completed／rejected 任務不在同批次重複生成。

### 16.3 State／Repository 測試

至少涵蓋：

1. candidate 可 accept、modify、defer、reject。
2. defer 缺日期失敗。
3. reject 缺 reason 失敗。
4. modify 沒有任何變更失敗。
5. scheduled 可 completed／not_completed／cancelled。
6. completed 缺 outcome type 失敗。
7. 每次 transition 產生 audit 紀錄。
8. review 與 status 在同一 transaction；任一失敗不部分寫入。
9. outcome 與 status 在同一 transaction。
10. 頁面重新載入後狀態仍存在。
11. reset 後回到固定初始狀態。

### 16.4 UI smoke／journey 測試

至少一個高層 journey 覆蓋：

1. 應用可啟動。
2. 今日任務頁可選主要 Demo 業務。
3. 任務清單含攻、守、增。
4. 守任務詳情顯示三項證據與原因未知。
5. 可將該任務改 phone 並採納。
6. 行程頁不把 phone 任務放進地圖。
7. 結果頁可完成一筆 scheduled 任務。
8. 重新載入後 completed 狀態存在。

### 16.5 Content guardrail tests

對主要 UI 輸出與 Demo fixtures 搜尋禁止語句：

- 「已被競品入侵」。
- 「提升成交率」。
- 「路線最佳化」。
- 「建議主推產品」。
- 舊 Bootstrap 效益數字。

如果文字只出現在 legacy 說明，必須不被新版主應用載入。

### 16.6 Definition of test pass

- 所有自動測試通過。
- 測試不需網路、API key 或 SMTP。
- 測試可在乾淨 clone 執行。
- 測試期間不修改固定 CSV fixtures。
- Demo database 使用獨立暫存位置。

---

## 17. Acceptance Criteria

### AC-01 今日任務生成

Given 固定 Demo fixtures、主要 Demo 業務與 240 分鐘彈性時間，When 使用者產生今日任務，Then 清單顯示 8 個候選任務，且至少含攻 2、守 3、增 3。

### AC-02 跨任務排序

Given 三類候選任務，When 系統計算價值分數，Then 每張任務保存六個 component scores、最終 0–100 分數與可追溯 evidence。

### AC-03 守任務語義

Given 安康診所具有訂單下降、互動中斷及逾期售後，且沒有直接競品文字，When 任務生成，Then title／why now 只能顯示風險待查，不得宣稱競品入侵。

### AC-04 Human-in-the-Loop

Given 一張 candidate visit task，When 業務將 objective 修改並改成 phone 後採納，Then 任務成為 modified／scheduled，原始值、修改值、原因與 actor 全部可追溯。

### AC-05 延後與拒絕

Given 一張 candidate task，When 業務延後卻未填日期或拒絕卻未填原因，Then 系統阻止送出並顯示欄位錯誤，資料庫不得部分更新。

### AC-06 容量

Given 兩個固定預約與 240 分鐘彈性時間，When 系統建議任務，Then 固定預約先占用時間，建議任務總 estimated minutes 不超過剩餘容量。

### AC-07 行程

Given 已採納的 phone 與 visit tasks，When 開啟行程頁，Then phone 只出現在電話清單，visit 才出現在地圖與點位順序。

### AC-08 結果閉環

Given 一張 scheduled task，When 業務填寫 completed、outcome type、next step 與 next date，Then task 與 outcome 在同一 transaction 保存，重新整理後仍存在。

### AC-09 Idempotency

Given 相同業務、日期與 fixtures，When 連續兩次產生任務，Then 第二次不增加重複 active tasks。

### AC-10 Demo reset

Given 已有修改與結果資料，When 使用者確認重設 Demo，Then 系統回到相同固定初始狀態，任務分數、順序與案例可重現。

### AC-11 誠實揭露

Given 任一主頁，Then 使用者能看到「合成資料／流程驗證」揭露，且看不到模型 AUC、Bootstrap 成交提升或真實企業串接宣稱。

### AC-12 乾淨環境

Given 新 clone 與支援版本的 Python，When 依 README 完成安裝、seed、test 與 launch，Then 不需外部金鑰即可啟動並完成主要 journey。

---

## 18. Non-Functional Requirements

### 18.1 Performance

- 固定 Demo 資料下，任務產生在一般筆電應於 2 秒內完成。
- 一般頁面互動不應因重新訓練模型而阻塞。
- 資料與 repository 可快取，但寫入後必須正確 invalidation。

### 18.2 Reliability

- 不依賴網路、API key、SMTP 或 LINE token。
- 所有 Demo 結果可由 seed／reset 重現。
- 寫入操作採 transaction。
- UI rerun 不可重複產生任務或重送結果。

### 18.3 Security and privacy

- 只使用合成診所與業務資料。
- 不包含病患資料。
- 不在程式碼、fixtures 或 UI 放真實帳密。
- 若保留通知模組，預設必須 Dry Run，且不在 P0 主流程呼叫。
- 錯誤畫面不顯示敏感路徑或完整資料內容。

### 18.4 Accessibility and usability

- 顏色之外同時使用「攻／守／增」文字標籤。
- 主要文字與背景保持足夠對比。
- 表單錯誤靠近欄位顯示。
- 不用只靠 emoji 傳遞狀態。
- 主要互動在 1366×768 螢幕不需水平捲動。

### 18.5 Maintainability

- 核心規則不得散落於 UI。
- 分數權重、門檻、分鐘與配額集中設定。
- reason codes 與人類文案集中管理。
- 主要資料物件與狀態使用明確型別。
- 新模組提供短 docstring，說明業務意義而非重述程式碼。

---

## 19. README Requirements

README 必須以 CENRA Mission 為主，不再以「成交預判 Dashboard」為主標。

必須包含：

1. 一句產品定位。
2. Competition P0 功能範圍。
3. Python 版本。
4. 安裝方式。
5. Demo seed／reset 方式。
6. 測試方式。
7. Streamlit 啟動方式。
8. 三分鐘 Demo 操作步驟。
9. 資料表摘要。
10. 合成資料與未串接真實系統揭露。
11. AI／規則模組的誠實說明。
12. legacy 模組說明。
13. 已知限制。
14. 不需要的外部服務／金鑰。

README 不得延續下列敘事：

- AUC 0.618 是產品價值證明。
- 15% 客戶為高風險。
- 29% 客戶有競品壓力。
- AI 排序使成交率由 54% 提升至 67%。
- IsolationForest 可辨識競品入侵。

---

## 20. Codex Implementation Sequence

Codex 應依序完成，每一階段先測試再進下一階段。

### Stage 1｜建立安全基線

- 讀取現有 README、Dashboard、資料生成、排名、風險、產品推薦、報告與審核模組。
- 記錄現有啟動方式與主要依賴。
- 不破壞性刪除舊程式。
- 建立新版主入口與架構邊界。
- 加入最小測試框架。

退出條件：舊原型可辨識，新版 skeleton 可啟動，測試命令可執行。

### Stage 2｜資料與 Demo seed

- 建立新版 fixtures schema。
- 建立固定合成事件資料。
- 建立 schema validation。
- 建立 SQLite repository 與 reset。

退出條件：seed 可重現、資料驗證通過、reset 可回到固定狀態。

### Stage 3｜Domain 與三類任務引擎

- 建立任務、證據、審核、結果與 Daily Plan 物件。
- 實作 Attack／Defend／Grow rules。
- 實作 reason codes 與文案。
- 完成核心 engine tests。

退出條件：固定 fixtures 產生預期攻 2、守 3、增 3，且禁止語句不出現。

### Stage 4｜評分、容量與點位順序

- 實作百分位、共同分數與 cost penalty。
- 實作固定預約、配額與容量選取。
- 實作 phone／visit 分流及 nearest-neighbor 示意。
- 完成 Daily Plan 高層測試。

退出條件：主要 Demo Daily Plan 可重現，容量不超額，phone 不進地圖。

### Stage 5｜任務審核與結果閉環

- 實作狀態機、review transaction、outcome transaction 與 audit。
- 實作 idempotent generation。
- 完成 state／repository tests。

退出條件：修改、延後、拒絕、完成與重新整理持久化全部通過。

### Stage 6｜Streamlit UI

- 完成品牌與四頁主導覽。
- 完成今日任務卡。
- 完成任務詳情與審核表單。
- 完成行程與結果頁。
- 完成 empty／error／loading states。

退出條件：人工可完成三分鐘 journey。

### Stage 7｜清理、文件與穩定 Demo

- 將舊頁面從主導覽移除。
- 移除新版對舊模型與產物的 runtime 依賴。
- 更新 requirements 與 README。
- 加入 CSV 匯出。
- 完成 content guardrail test。
- 在乾淨環境重跑 seed、tests、launch。

退出條件：所有測試通過，Demo reset 後三分鐘流程可重現。

### Stage 8｜最終 QA

- 逐頁檢查文案與合成資料揭露。
- 確認無病患資料、真實帳密或外部服務依賴。
- 確認 1366×768 主要頁面可用。
- 確認 Git diff 不含無關大型產物或暫存檔。
- 交付變更摘要、測試證據與已知限制。

---

## 21. Codex Working Rules

1. 依本規格實作，不重新將產品改回全功能 Dashboard。
2. 優先完成 P0；P1／P2 不得延誤 P0。
3. 保留使用者既有變更，不執行 destructive reset。
4. 不修改與 CENRA Mission 無關的檔案。
5. 每一階段完成後執行相關測試。
6. 遇到規格與舊程式衝突時，以本規格為產品真相，舊程式只作技術參考。
7. 不使用合成 label 訓練並宣稱模型有效。
8. 不新增外部付費服務或需要金鑰的依賴。
9. 不建立 FastAPI、React、Node 後端或容器編排；P0 沿用 Streamlit。
10. 不做即時模型訓練；P0 是 rules-v1＋analytic scoring。
11. 若技術細節未指定，選擇最小、可測試、可在 Streamlit Cloud 執行的方案。
12. 只有當缺少資訊會造成不可逆或明顯不同的產品結果時才詢問使用者。
13. 完成前必須提供：實作摘要、啟動方式、測試命令與結果、三分鐘 Demo 步驟、已知限制。

---

## 22. Out of Scope

本規格不包含：

- 重新設計競賽簡報。
- 建立正式企業資料串接。
- 蒐集真實診所名單。
- 建立真實成交預測或因果模型。
- 建立正式產品推薦或醫療建議。
- 建立主管績效排名。
- 發送真實通知。
- 企業級 IAM、備援、HA、監控平台與雲端基礎設施。
- 原生手機 App。
- Google Maps／Mapbox 付費路網服務。

---

## 23. Further Notes

### 23.1 誠實揭露

P0 是以合成資料驗證「任務生成與人機協作流程」的競賽原型。它不證明：

- 中化裕民目前具有相同資料欄位。
- 任務分數能造成成交或營收提升。
- 異常可識別競品原因。
- 點位順序是最佳路線。
- 產品機會一定適合特定診所。

### 23.2 企業試點後才能做的驗證

正式取得資料與 outcome labels 後，才進行：

- 時間切分離線驗證。
- 基準組或對照試點。
- 任務採納率、完成率與無效拜訪率。
- Attack 的有效接觸與新客轉換。
- Defend 的留存或恢復採購。
- Grow 的補貨與品項覆蓋。
- 模型版本、偏差與資料品質監控。

### 23.3 來源基線

- 核心產品方向：CENRA Mission 完整競賽規劃 v1.0。
- 簡報敘事：14 頁 CENRA Mission 提案簡報。
- 現有程式基線：公開 repository 的 main HEAD `76f7ae1453ac67c495998b919e9dd9c4d9b06b97`，查核日期 2026-08-25。
- 現有技術：Streamlit、pandas、NumPy、scikit-learn、Plotly、CSV 與 pickle 模型。

---

## 24. Final Delivery Checklist

- [ ] 新主標為 CENRA Mission。
- [ ] 首頁是今日任務，不是管理總覽。
- [ ] 只聚焦診所通路。
- [ ] 攻、守、增皆有候選任務與詳情。
- [ ] 三類任務共用統一價值排序。
- [ ] 每張任務有 why now、objective、evidence、uncertainty 與 score components。
- [ ] 業務可採納、修改、改電話、延後與拒絕。
- [ ] 審核與結果重新整理後仍存在。
- [ ] 固定預約優先占用容量。
- [ ] phone 不進地圖。
- [ ] 地圖只稱點位與建議順序示意。
- [ ] 任務結果可寫回。
- [ ] Demo reset 可重現固定案例。
- [ ] 新版不載入舊 purchase／risk 模型。
- [ ] 新版不顯示 Bootstrap 效益、AUC 或固定高風險比例。
- [ ] 無 `competitor_pressure` 隱藏真值。
- [ ] 無自動產品推薦結論。
- [ ] 所有核心測試通過。
- [ ] README 可讓陌生人完成安裝、測試與啟動。
- [ ] 三分鐘 Demo 流程完整通過。

