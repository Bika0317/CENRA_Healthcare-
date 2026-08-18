"""
單一客戶層級的可解釋性：把模型分數翻譯成業務員看得懂的白話理由。
做法：拿全域重要特徵，比較該客戶在同儕群體中的百分位，挑出最極端的幾個，
轉成「這個數字，比多少比例的客戶高/低，代表什麼訊號」的句子。
不是嚴謹的 SHAP 值分解，但足以讓業務主管理解系統判斷依據、建立信任。
"""
import pandas as pd

FEATURE_META = {
    "base_monthly_value":       {"label": "客戶月價值",        "higher_is": "good", "kind": "money"},
    "revenue_last_90d":         {"label": "近90天營收",         "higher_is": "good", "kind": "money"},
    "revenue_prev_90d":         {"label": "前一期(90天前)營收", "higher_is": "good", "kind": "money"},
    "revenue_trend":            {"label": "業績趨勢變化",       "higher_is": "good", "kind": "pct"},
    "days_since_last_order":    {"label": "距上次下單天數",     "higher_is": "bad",  "kind": "days"},
    "days_since_last_visit":    {"label": "距上次拜訪天數",     "higher_is": "bad",  "kind": "days"},
    "visits_last_90d":          {"label": "近90天拜訪次數",     "higher_is": "good", "kind": "count"},
    "visits_prev_90d":          {"label": "前一期拜訪次數",     "higher_is": "good", "kind": "count"},
    "competitor_mentions_180d": {"label": "近180天提及競品次數", "higher_is": "bad",  "kind": "count"},
    "orders_last_180d":         {"label": "近180天訂單數",      "higher_is": "good", "kind": "count"},
    "tenure_days":              {"label": "合作年資",           "higher_is": "good", "kind": "days"},
    "visit_order_ratio":        {"label": "拜訪/訂單轉換比",    "higher_is": "bad",  "kind": "ratio"},
}


def _fmt(val, kind):
    if kind == "money":
        return f"{val:,.0f} 元"
    if kind == "pct":
        return f"{val:+.0%}"
    if kind == "days":
        return f"{val:.0f} 天"
    if kind == "count":
        return f"{val:.0f} 次"
    return f"{val:.2f}"


def top_explainable_features(feature_importance: pd.Series, max_n: int = 8) -> list:
    """把 feature_importance.csv 的欄位名（可能含 one-hot 後綴）對回可解釋的原始欄位。"""
    ordered = []
    for name in feature_importance.sort_values(ascending=False).index:
        base = name
        if base in FEATURE_META and base not in ordered:
            ordered.append(base)
        if len(ordered) >= max_n:
            break
    return ordered


def explain_customer(row: pd.Series, population: pd.DataFrame, top_features: list, n_reasons: int = 3) -> list:
    scored = []
    for feat in top_features:
        if feat not in row.index or feat not in population.columns:
            continue
        meta = FEATURE_META[feat]
        val = row[feat]
        pct = (population[feat] < val).mean()  # 該客戶勝過多少比例的同儕
        extremity = abs(pct - 0.5)
        scored.append((extremity, feat, val, pct, meta))

    scored.sort(key=lambda x: x[0], reverse=True)

    reasons = []
    for extremity, feat, val, pct, meta in scored[:n_reasons]:
        is_high = pct >= 0.5
        direction_word = "高於" if is_high else "低於"
        pct_display = int(pct * 100) if is_high else int((1 - pct) * 100)
        is_favorable = (meta["higher_is"] == "good") == is_high
        sentiment = "有利訊號" if is_favorable else "警訊"
        reasons.append(
            f"{meta['label']} {_fmt(val, meta['kind'])}，{direction_word} {pct_display}% 的客戶（{sentiment}）"
        )
    return reasons
