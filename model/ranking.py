"""
拜訪優先順序排序引擎：把「成交機率 × 客戶價值」與「風險緊急度」合成單一分數，
這是題目要求的核心——把 CRM 從紀錄工具變成戰略大腦，資源集中在高價值/高風險客戶。

風險分數改用 IsolationForest 無監督異常偵測（見 risk_model.py），
取代人工加權規則，作為排序與燈號依據；規則式的 rule_risk_score 保留下來
供可解釋性模組（explain.py）引用，向使用者說明「哪些訊號讓風險升高」。
"""
import os
import numpy as np
import pandas as pd
import joblib
from features import build_features
from risk_model import score_risk

FEATURE_COLS = [
    "base_monthly_value", "tenure_days", "days_since_last_visit", "days_since_last_order",
    "visits_last_90d", "visits_prev_90d", "competitor_mentions_180d",
    "revenue_last_90d", "revenue_prev_90d", "revenue_trend",
    "orders_last_180d", "visit_order_ratio", "risk_score", "competitor_pressure",
]
CAT_COLS = ["tier", "channel", "region"]


def score_customers(customers, visits, orders, cutoff_date, model_path="model/purchase_model.pkl",
                     risk_model_path=None, w_purchase=0.5, w_value=0.3, w_risk=0.2,
                     recent_visit_penalty_days=7):
    bundle = joblib.load(model_path)
    clf, columns = bundle["model"], bundle["columns"]

    if risk_model_path is None:
        risk_model_path = os.path.join(os.path.dirname(model_path), "risk_model.pkl")
    risk_bundle = joblib.load(risk_model_path)

    feats = build_features(customers, visits, orders, cutoff_date)
    feats = feats.rename(columns={"risk_score": "rule_risk_score"})

    X = pd.get_dummies(feats[[c if c != "risk_score" else "rule_risk_score" for c in FEATURE_COLS] + CAT_COLS], columns=CAT_COLS)
    X = X.rename(columns={"rule_risk_score": "risk_score"})
    X = X.reindex(columns=columns, fill_value=0)
    feats["purchase_proba"] = clf.predict_proba(X)[:, 1]

    feats["ai_risk_score"] = score_risk(feats, risk_bundle)

    def norm(s):
        s = s.astype(float)
        rng = s.max() - s.min()
        return (s - s.min()) / rng if rng > 0 else s * 0

    value_norm = norm(feats["base_monthly_value"])
    risk_norm = feats["ai_risk_score"]  # 已經是 0-1
    purchase_norm = norm(feats["purchase_proba"])

    penalty = np.where(feats["days_since_last_visit"] < recent_visit_penalty_days, 0.15, 0)

    feats["priority_score"] = (
        w_purchase * purchase_norm + w_value * value_norm + w_risk * risk_norm - penalty
    )

    def risk_flag(row):
        if row["ai_risk_score"] > feats["ai_risk_score"].quantile(0.85):
            return "紅：高風險(疑似競品入侵)"
        if row["ai_risk_score"] > feats["ai_risk_score"].quantile(0.6):
            return "黃：需留意"
        return "綠：穩定"

    feats["risk_flag"] = feats.apply(risk_flag, axis=1)

    return feats.sort_values("priority_score", ascending=False)
