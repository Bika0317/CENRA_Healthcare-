"""
效益估計的統計嚴謹版本：用 bootstrap 重抽樣，把單一點估計（例如「53% → 64%」）
換成帶信賴區間的估計，避免評審質疑「這個提升是不是剛好抽到的」。
這不是真正的 A/B 測試（沒有實際隨機分派的兩組使用者），
而是用現有資料模擬「若依 AI 排序 vs 隨機/依經驗拜訪」的差異量級與不確定性，
上線後應該用真實 A/B 測試（同時期隨機分派業務員名單）驗證。
"""
import numpy as np
import pandas as pd


def bootstrap_uplift(scored_df: pd.DataFrame, ai_list_size: int, n_boot: int = 400, seed: int = 42):
    rng = np.random.default_rng(seed)
    all_probs = scored_df["purchase_proba"].values
    n = len(all_probs)

    sorted_probs = scored_df.sort_values("priority_score", ascending=False)["purchase_proba"].values
    top_probs = sorted_probs[:ai_list_size] if ai_list_size <= n else sorted_probs

    random_means = np.empty(n_boot)
    ai_means = np.empty(n_boot)
    for i in range(n_boot):
        random_means[i] = rng.choice(all_probs, size=n, replace=True).mean()
        ai_means[i] = rng.choice(top_probs, size=len(top_probs), replace=True).mean()

    diff = ai_means - random_means

    def ci(arr):
        return float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))

    return {
        "random_mean": float(random_means.mean()), "random_ci": ci(random_means),
        "ai_mean": float(ai_means.mean()), "ai_ci": ci(ai_means),
        "diff_mean": float(diff.mean()), "diff_ci": ci(diff),
    }
