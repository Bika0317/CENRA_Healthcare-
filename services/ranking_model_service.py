"""
本地學習排序層（示範性質，不取代 rules-v1 排序）。

現況：`services/scoring.py` 的任務價值分數是規則式加權公式，不是訓練出來的模型。
這裡示範「如果從業務實際審核決定（採納/拒絕）裡學習，模型會怎麼看這批候選任務」——
用 scikit-learn 的 LogisticRegression，特徵就是任務本來就有的五個分項分數＋成本懲罰，
標籤是業務的審核結果。

刻意的邊界（呼應審查意見「不要把規則系統包裝成已訓練模型」）：
- 只在累積夠多審核紀錄（見 MIN_TRAINING_SAMPLES）才訓練、才顯示，樣本不足時完全不出現，
  不會硬顯示一個沒有統計意義的分數。
- 只當「並列參考資訊」呈現，不寫回 Task.value_score、不影響容量分配或建議選取。
- 不宣稱效度、不宣稱準確率——demo 資料量太小，任何「準確率 XX%」的說法都站不住腳，
  這裡刻意不算、也不顯示這類數字。
"""
from __future__ import annotations

MIN_TRAINING_SAMPLES = 20

FEATURE_FIELDS = (
    "signal_score", "business_value_score", "urgency_score",
    "evidence_score", "strategy_fit_score", "cost_penalty",
)

# 延後（defer）代表「還沒決定要不要做」，不是正向也不是負向的業務判斷，訓練時排除；
# 只有「採納/修改採納」（正向）跟「拒絕」（負向）兩種明確決定才進訓練集。
_POSITIVE_DECISIONS = ("accept", "modify")
_NEGATIVE_DECISIONS = ("reject",)


def _features(task) -> list[float]:
    return [getattr(task, field) for field in FEATURE_FIELDS]


def train_reference_model(task_repo):
    """回傳 (訓練好的 model, 訓練樣本數)；樣本不足或標籤只有單一類別時回傳 None
    （LogisticRegression 需要至少兩個類別才能訓練，樣本數太少的模型也沒有參考價值）。"""
    reviewed = task_repo.get_all_reviewed_tasks_with_decisions()
    X, y = [], []
    for task, decision in reviewed:
        if decision in _POSITIVE_DECISIONS:
            X.append(_features(task))
            y.append(1)
        elif decision in _NEGATIVE_DECISIONS:
            X.append(_features(task))
            y.append(0)
        # defer 以外，還有沒被涵蓋到的 decision 值理論上不存在（domain 層已經限制
        # 只有 accept/modify/defer/reject 四種），這裡不用額外處理。

    if len(X) < MIN_TRAINING_SAMPLES or len(set(y)) < 2:
        return None

    from sklearn.linear_model import LogisticRegression

    model = LogisticRegression(max_iter=1000)
    model.fit(X, y)
    return model, len(X)


def score_tasks_with_reference_model(task_repo, tasks) -> tuple[dict[str, float], int] | None:
    """給一批任務（今天的候選任務），回傳 (task_id -> 模型參考分數 0-100, 訓練樣本數)；
    樣本不足時回傳 None，呼叫端應該完全不顯示這欄，不要顯示「資料不足」這種空狀態占位。"""
    trained = train_reference_model(task_repo)
    if trained is None:
        return None
    model, n_samples = trained
    if not tasks:
        return {}, n_samples

    X = [_features(t) for t in tasks]
    probabilities = model.predict_proba(X)[:, 1]
    scores = {t.task_id: float(p * 100) for t, p in zip(tasks, probabilities)}
    return scores, n_samples
