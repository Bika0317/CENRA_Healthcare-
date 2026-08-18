"""
訓練「成交預判」模型：以多個歷史 cutoff 切點滾動取樣，避免用未來資訊洩漏，
輸出模型檔給 app/dashboard.py 直接載入使用。
"""
import joblib
import numpy as np
import pandas as pd
from datetime import date, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score, cross_val_predict
from sklearn.metrics import roc_auc_score, roc_curve, classification_report

from features import build_features, make_labels
from risk_model import train_risk_model

FEATURE_COLS = [
    "base_monthly_value", "tenure_days", "days_since_last_visit", "days_since_last_order",
    "visits_last_90d", "visits_prev_90d", "competitor_mentions_180d",
    "revenue_last_90d", "revenue_prev_90d", "revenue_trend",
    "orders_last_180d", "visit_order_ratio", "risk_score", "competitor_pressure",
]
CAT_COLS = ["tier", "channel", "region"]


def load_data():
    customers = pd.read_csv("data/customers.csv")
    visits = pd.read_csv("data/visits.csv")
    orders = pd.read_csv("data/orders.csv")
    return customers, visits, orders


def build_training_table(customers, visits, orders, cutoffs):
    frames = []
    for cutoff in cutoffs:
        feats = build_features(customers, visits, orders, cutoff)
        labels = make_labels(customers, orders, cutoff)
        merged = feats.merge(labels, on="customer_id")
        merged["cutoff"] = cutoff
        frames.append(merged)
    return pd.concat(frames, ignore_index=True)


def main():
    customers, visits, orders = load_data()

    cutoffs = [date(2026, 8, 1) - timedelta(days=90 * k) for k in range(1, 6)]
    train_table = build_training_table(customers, visits, orders, cutoffs)

    X = pd.get_dummies(train_table[FEATURE_COLS + CAT_COLS], columns=CAT_COLS)
    y = train_table["will_purchase"]

    # 5-fold 交叉驗證：單一次 train_test_split 的 AUC 只是一次抽樣結果，
    # 樣本量不大時波動可能不小；k-fold 讓「模型多穩定」這件事有數字可以講。
    cv_clf = RandomForestClassifier(n_estimators=300, max_depth=6, min_samples_leaf=8, random_state=42, class_weight="balanced")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(cv_clf, X, y, cv=cv, scoring="roc_auc")
    print(f"5-fold CV AUC: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}  (每折: {np.round(cv_scores, 3).tolist()})")
    pd.Series(cv_scores, name="cv_auc").to_csv("model/cv_scores.csv", index=False)

    # Out-of-fold 預測：每筆樣本的預測都來自「沒看過它的那一折」訓練出的模型，
    # 拿這組預測畫 ROC 曲線，是比單一 AUC 數字更可驗證的證據
    # （AUC 定義：ROC 曲線下面積 = P(隨機一個正樣本的預測分數 > 隨機一個負樣本的預測分數)）。
    oof_proba = cross_val_predict(cv_clf, X, y, cv=cv, method="predict_proba")[:, 1]
    oof_auc = roc_auc_score(y, oof_proba)
    fpr, tpr, thresholds = roc_curve(y, oof_proba)
    pd.DataFrame({"fpr": fpr, "tpr": tpr, "threshold": thresholds}).to_csv("model/roc_curve.csv", index=False)
    print(f"Out-of-fold AUC (整體，非逐折平均): {oof_auc:.3f} — 與 5-fold 平均 {cv_scores.mean():.3f} 應相近，驗證 CV 結果一致")

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)

    clf = RandomForestClassifier(n_estimators=300, max_depth=6, min_samples_leaf=8, random_state=42, class_weight="balanced")
    clf.fit(X_train, y_train)

    proba = clf.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, proba)
    print(f"Holdout Test AUC: {auc:.3f}")
    print(classification_report(y_test, (proba > 0.5).astype(int)))

    importances = pd.Series(clf.feature_importances_, index=X.columns).sort_values(ascending=False)
    print("\nTop features:\n", importances.head(10))

    joblib.dump({"model": clf, "columns": list(X.columns)}, "model/purchase_model.pkl")
    importances.to_csv("model/feature_importance.csv")
    print("\nSaved model/purchase_model.pkl")

    risk_bundle = train_risk_model(train_table)
    joblib.dump(risk_bundle, "model/risk_model.pkl")
    print("Saved model/risk_model.pkl (IsolationForest, contamination=0.15)")


if __name__ == "__main__":
    main()
