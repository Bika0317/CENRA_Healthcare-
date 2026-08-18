"""
特徵工程：把「拜訪＋訂單」原始事件轉成每個客戶在每個觀察切點(cutoff)的特徵快照。
核心思路對齊題目說明——把 CRM 從紀錄工具變成可預判、可排序的決策依據：
  - RFM：拜訪/訂單的 recency, frequency, monetary
  - trend：近3個月 vs 前3個月 業績變化 -> 競品入侵/流失的早期訊號
  - engagement：拜訪是否有跟上（拜訪骤降但客戶價值高 = 高風險）
"""
import pandas as pd
import numpy as np


def build_features(customers, visits, orders, cutoff_date):
    cutoff_date = pd.Timestamp(cutoff_date)
    visits = visits.copy()
    orders = orders.copy()
    visits["visit_date"] = pd.to_datetime(visits["visit_date"])
    orders["order_date"] = pd.to_datetime(orders["order_date"])

    v_hist = visits[visits.visit_date <= cutoff_date]
    o_hist = orders[orders.order_date <= cutoff_date]

    feats = customers.copy()
    feats["onboard_date"] = pd.to_datetime(feats["onboard_date"])

    def days_since(dates_series, ref_ids, id_col):
        last = dates_series.groupby(id_col).max()
        out = ref_ids.map(last)
        return (cutoff_date - out).dt.days

    feats["days_since_last_visit"] = days_since(
        v_hist.set_index("customer_id")["visit_date"], feats["customer_id"], "customer_id"
    ).fillna(999)
    feats["days_since_last_order"] = days_since(
        o_hist.set_index("customer_id")["order_date"], feats["customer_id"], "customer_id"
    ).fillna(999)

    def window_count(df, date_col, days, id_col="customer_id"):
        w = df[df[date_col] > cutoff_date - pd.Timedelta(days=days)]
        return w.groupby(id_col).size()

    def window_sum(df, date_col, val_col, days, id_col="customer_id"):
        w = df[df[date_col] > cutoff_date - pd.Timedelta(days=days)]
        return w.groupby(id_col)[val_col].sum()

    feats["visits_last_90d"] = feats["customer_id"].map(window_count(v_hist, "visit_date", 90)).fillna(0)
    feats["visits_prev_90d"] = feats["customer_id"].map(
        window_count(v_hist[v_hist.visit_date <= cutoff_date - pd.Timedelta(days=90)], "visit_date", 90)
    ).fillna(0)
    feats["competitor_mentions_180d"] = feats["customer_id"].map(
        window_sum(v_hist, "visit_date", "mentions_competitor", 180)
    ).fillna(0)

    feats["revenue_last_90d"] = feats["customer_id"].map(window_sum(o_hist, "order_date", "amount", 90)).fillna(0)
    feats["revenue_prev_90d"] = feats["customer_id"].map(
        window_sum(o_hist[o_hist.order_date <= cutoff_date - pd.Timedelta(days=90)], "order_date", "amount", 90)
    ).fillna(0)

    feats["revenue_trend"] = (feats["revenue_last_90d"] - feats["revenue_prev_90d"]) / (
        feats["revenue_prev_90d"].replace(0, np.nan)
    )
    feats["revenue_trend"] = feats["revenue_trend"].fillna(0).clip(-1, 3)

    feats["orders_last_180d"] = feats["customer_id"].map(window_count(o_hist, "order_date", 180)).fillna(0)
    feats["visit_order_ratio"] = feats["visits_last_90d"] / feats["orders_last_180d"].replace(0, np.nan)
    feats["visit_order_ratio"] = feats["visit_order_ratio"].fillna(feats["visits_last_90d"])

    feats["tenure_days"] = (cutoff_date - feats["onboard_date"]).dt.days

    # 風險早期訊號：拜訪頻率下滑 + 業績下滑 + 出現競品提及
    feats["risk_score"] = (
        (feats["visits_prev_90d"] - feats["visits_last_90d"]).clip(lower=0) * 0.15
        + (-feats["revenue_trend"]).clip(lower=0) * 3.0
        + feats["competitor_mentions_180d"] * 0.8
    )

    return feats


def make_labels(customers, orders, cutoff_date, horizon_days=90):
    """下一個 horizon 內是否會下單 -> 成交預判的訓練標籤。"""
    cutoff_date = pd.Timestamp(cutoff_date)
    orders = orders.copy()
    orders["order_date"] = pd.to_datetime(orders["order_date"])
    future = orders[
        (orders.order_date > cutoff_date) & (orders.order_date <= cutoff_date + pd.Timedelta(days=horizon_days))
    ]
    will_buy = future.groupby("customer_id").size().rename("will_purchase")
    labels = customers[["customer_id"]].copy()
    labels["will_purchase"] = labels["customer_id"].map(will_buy).fillna(0).clip(upper=1).astype(int)
    return labels
