# CENRA Mission｜給 Codex 的執行提示詞

請在學生現有專案上直接實作 CENRA Mission Competition P0。

現有專案：

`https://github.com/Bika0317/CENRA_Healthcare-`

完整規格：

`/Users/peiyucheng/Projects/works/output/cenra_mission/CENRA_Mission_Codex_系統開發_SPEC.md`

執行要求：

1. 先完整閱讀 SPEC，再檢查現有 README、Streamlit Dashboard、資料生成、排名、風險、產品推薦、報告與 Human-in-the-Loop 模組。
2. 依 SPEC 的 Stage 1 至 Stage 8 直接完成實作，不只產生計畫或 skeleton。
3. 沿用 Streamlit、pandas、Plotly；不要改做 React、FastAPI 或其他新架構。
4. 首頁必須改成「今日任務」，完成攻、守、增三類任務、統一排序、人工審核、電話／實訪、行程示意與結果寫回。
5. 不得沿用 `competitor_pressure` 隱藏真值、IsolationForest 競品結論、固定 15% 高風險、Bootstrap 假效益或自動產品推薦作為新版主流程。
6. 先完成 P0；P1、P2 不得延誤交付。
7. 保留使用者現有變更，不執行 destructive reset，不修改無關檔案。
8. 每個階段完成後執行相關測試；完成前必須在乾淨環境驗證 seed、tests、launch 與三分鐘 Demo journey。
9. 若規格與舊程式衝突，以 SPEC 為產品真相；舊程式只作技術參考。
10. 只有遇到會造成不可逆或完全不同產品結果的缺失資訊才詢問；其餘採最小、可測試、可在 Streamlit Cloud 執行的方案繼續。

完成時請交付：

- 實作摘要。
- 主要架構與資料變更。
- 啟動方式。
- 測試命令與實際結果。
- 三分鐘 Demo 操作步驟。
- 已知限制。
- 所有修改檔案清單。

