"""
統計離群任務標記（誠實版無監督異常偵測）。

上一版原型（app/dashboard.py）曾經用 IsolationForest 偵測「competitor_pressure」
之類的合成標籤，實質上是拿模型包裝一個先射箭再畫靶的因果宣稱（「異常＝競品入侵」）。
這裡示範同一種技術的正確用法：只在同一批候選任務內部，對既有的分項分數做統計離群值
偵測，標記「這張任務的訊號組合，跟同一批其他候選比起來不尋常」——不推測原因、
不宣稱競品或任何因果關係，純粹是統計上的離群提示，讓業務自己判斷要不要多看一眼。
"""
from __future__ import annotations

MIN_BATCH_SIZE = 6

_FEATURE_FIELDS = (
    "signal_score", "business_value_score", "urgency_score",
    "evidence_score", "strategy_fit_score", "cost_penalty",
)


def flag_statistical_outliers(tasks) -> set[str]:
    """回傳這批任務裡，統計上屬於離群值的 task_id 集合。批次太小（樣本不足以判斷
    「常態」是什麼）時直接回傳空集合，不勉強跑一個沒有意義的偵測。"""
    if len(tasks) < MIN_BATCH_SIZE:
        return set()

    from sklearn.ensemble import IsolationForest

    X = [[getattr(t, field) for field in _FEATURE_FIELDS] for t in tasks]
    # contamination 用固定比例（不用 "auto"）：demo 規模的批次通常只有 6~10 筆，
    # "auto" 那套依論文公式算出來的門檻在樣本這麼少時會嚴重over-flag——實測一批
    # 8 筆的候選裡，"auto" 標了 5 筆「離群」，等於半數都算異常，這樣的標記沒有
    # 任何篩選意義。固定成一個保守比例，一批裡最多抓出 1、2 筆真正突出的。
    # random_state 固定：這批候選給定的話，離群判斷要能重現，不能同一批資料
    # 每次重新整理頁面就標記不同的任務。
    clf = IsolationForest(n_estimators=100, contamination=0.125, random_state=42)
    predictions = clf.fit_predict(X)
    return {t.task_id for t, pred in zip(tasks, predictions) if pred == -1}
