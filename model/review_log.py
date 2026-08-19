"""
Human-in-the-Loop 審核日誌：AI 只負責產生建議（拜訪優先清單），
最終決定權在業務員——採納/修改/拒絕都會被記錄下來，
形成可追溯的審核歷程，也是未來優化模型/排序權重的回饋資料。
"""
import os
import pandas as pd
from datetime import datetime

LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "review_log.csv")
LOG_COLS = [
    "timestamp", "rep_id", "rep_name", "customer_id", "customer_name",
    "ai_purchase_proba", "ai_risk_flag", "ai_priority_rank", "action", "note",
]


def load_review_log() -> pd.DataFrame:
    if os.path.exists(LOG_PATH):
        return pd.read_csv(LOG_PATH)
    return pd.DataFrame(columns=LOG_COLS)


def append_review(rows: list) -> pd.DataFrame:
    df_new = pd.DataFrame(rows, columns=LOG_COLS)
    combined = pd.concat([load_review_log(), df_new], ignore_index=True)
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    combined.to_csv(LOG_PATH, index=False)
    return combined


def build_log_rows(edited_df: pd.DataFrame, rep_id: str, rep_name: str) -> list:
    now = datetime.now().isoformat(timespec="seconds")
    rows = []
    for rank, (_, r) in enumerate(edited_df.iterrows(), start=1):
        rows.append({
            "timestamp": now, "rep_id": rep_id, "rep_name": rep_name,
            "customer_id": r["customer_id"], "customer_name": r["customer_name"],
            "ai_purchase_proba": r["purchase_proba"], "ai_risk_flag": r["risk_flag"],
            "ai_priority_rank": rank, "action": r["審核動作"], "note": r.get("備註", ""),
        })
    return rows
