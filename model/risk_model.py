"""
競品入侵風險：從人工加權規則升級為 IsolationForest 無監督異常偵測。
概念：多數客戶的「拜訪/業績/競品提及」組合應該落在正常區間，
若某客戶的組合明顯偏離群體（業績驟降、拜訪驟減、卻又被提及競品），
就是異常點 —— 用異常分數取代主觀加權公式，且能隨資料自動適應。
"""
import numpy as np
from sklearn.ensemble import IsolationForest

RISK_FEATURES = [
    "revenue_trend", "visits_last_90d", "visits_prev_90d",
    "competitor_mentions_180d", "days_since_last_order", "visit_order_ratio",
]


def train_risk_model(feats, contamination=0.15, random_state=42):
    X = feats[RISK_FEATURES].fillna(0)
    model = IsolationForest(n_estimators=300, contamination=contamination, random_state=random_state)
    model.fit(X)
    raw = -model.score_samples(X)  # 分數越高 = 越異常
    return {"model": model, "columns": RISK_FEATURES, "score_min": float(raw.min()), "score_max": float(raw.max())}


def score_risk(feats, bundle):
    X = feats[bundle["columns"]].fillna(0)
    raw = -bundle["model"].score_samples(X)
    lo, hi = bundle["score_min"], bundle["score_max"]
    norm = (raw - lo) / (hi - lo) if hi > lo else raw * 0
    return np.clip(norm, 0, 1)
