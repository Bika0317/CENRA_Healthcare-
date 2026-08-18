"""
用系統實際跑出來的資料產生簡報用圖表（PNG），確保簡報上的數字跟 Dashboard 是同一組資料，
不是另外手畫的示意圖。執行一次即可，輸出到 docs/assets/。
"""
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "model"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd
from datetime import date

from ranking import score_customers
from ab_test import bootstrap_uplift

for fname in ["Microsoft JhengHei", "Microsoft YaHei", "SimHei"]:
    if any(fname.lower() in f.name.lower() for f in fm.fontManager.ttflist):
        plt.rcParams["font.sans-serif"] = [fname]
        break
plt.rcParams["axes.unicode_minus"] = False

ROOT = os.path.join(os.path.dirname(__file__), "..")
ASSETS = os.path.join(os.path.dirname(__file__), "assets")
os.makedirs(ASSETS, exist_ok=True)

RED, YELLOW, GREEN = "#d62728", "#e6b800", "#2ca02c"
PINK, NAVY, GRAY = "#c8006e", "#20232a", "#9aa0a6"
RISK_COLORS = {"紅：高風險(疑似競品入侵)": RED, "黃：需留意": YELLOW, "綠：穩定": GREEN}

customers = pd.read_csv(os.path.join(ROOT, "data", "customers.csv"))
visits = pd.read_csv(os.path.join(ROOT, "data", "visits.csv"))
orders = pd.read_csv(os.path.join(ROOT, "data", "orders.csv"))
reps = pd.read_csv(os.path.join(ROOT, "data", "reps.csv"))

scored_df = score_customers(customers, visits, orders, date(2026, 8, 1),
                             model_path=os.path.join(ROOT, "model", "purchase_model.pkl"))


def save(fig, name, dpi=180):
    fig.savefig(os.path.join(ASSETS, name), dpi=dpi, bbox_inches="tight", transparent=True)
    plt.close(fig)


# 1. 客戶價值 x 成交機率 x 風險 散佈圖
fig, ax = plt.subplots(figsize=(7, 4.5))
for flag, color in RISK_COLORS.items():
    sub = scored_df[scored_df.risk_flag == flag]
    ax.scatter(sub.purchase_proba, sub.base_monthly_value, s=(sub.revenue_last_90d / 800 + 20),
               color=color, alpha=0.7, label=flag.split("：")[1], edgecolors="white", linewidths=0.3)
ax.set_xlabel("成交機率", fontsize=12)
ax.set_ylabel("客戶月價值估計", fontsize=12)
ax.legend(frameon=False, loc="upper left", fontsize=10)
ax.spines[["top", "right"]].set_visible(False)
save(fig, "scatter_value_proba.png")

# 2. 各地區風險分佈
region_risk = scored_df.groupby(["region", "risk_flag"]).size().unstack(fill_value=0)
region_risk = region_risk[[c for c in RISK_COLORS if c in region_risk.columns]]
fig, ax = plt.subplots(figsize=(7, 4.2))
region_risk.plot(kind="bar", stacked=True, ax=ax,
                  color=[RISK_COLORS[c] for c in region_risk.columns], width=0.65)
ax.set_xlabel("")
ax.set_ylabel("客戶數", fontsize=12)
ax.legend([c.split("：")[1] for c in region_risk.columns], frameon=False, fontsize=10)
ax.spines[["top", "right"]].set_visible(False)
plt.xticks(rotation=0)
save(fig, "risk_by_region.png")

# 3. 效益模擬（含信賴區間）—— 這張圖疊在深色投影片背景上，文字/座標軸都要用淺色才看得到
boot = bootstrap_uplift(scored_df, ai_list_size=6 * len(reps), n_boot=500)
fig, ax = plt.subplots(figsize=(5.5, 4.5))
LIGHT = "#E8E6ED"
labels = ["隨機/依經驗拜訪", "AI 優先排序拜訪"]
means = [boot["random_mean"], boot["ai_mean"]]
lo = [boot["random_mean"] - boot["random_ci"][0], boot["ai_mean"] - boot["ai_ci"][0]]
hi = [boot["random_ci"][1] - boot["random_mean"], boot["ai_ci"][1] - boot["ai_mean"]]
bars = ax.bar(labels, means, color=[GRAY, PINK], width=0.5, yerr=[lo, hi], capsize=8,
              error_kw=dict(ecolor=LIGHT, elinewidth=1.5))
for b, m in zip(bars, means):
    ax.text(b.get_x() + b.get_width() / 2, m + 0.03, f"{m:.0%}", ha="center", fontsize=14, fontweight="bold", color=LIGHT)
ax.set_ylabel("平均成交機率", fontsize=12, color=LIGHT)
ax.set_ylim(0, max(means) + 0.15)
ax.spines[["top", "right"]].set_visible(False)
ax.spines[["left", "bottom"]].set_color(LIGHT)
ax.tick_params(colors=LIGHT)
save(fig, "effect_ci.png")

# 4. 特徵重要性
fi = pd.read_csv(os.path.join(ROOT, "model", "feature_importance.csv"), index_col=0).iloc[:, 0].sort_values()
fig, ax = plt.subplots(figsize=(7, 4.5))
ax.barh(fi.tail(10).index, fi.tail(10).values, color=PINK)
ax.set_xlabel("重要性", fontsize=12)
ax.spines[["top", "right"]].set_visible(False)
save(fig, "feature_importance.png")

# 5. 5-fold 交叉驗證
cv_scores = pd.read_csv(os.path.join(ROOT, "model", "cv_scores.csv"))["cv_auc"]
fig, ax = plt.subplots(figsize=(6, 4))
ax.bar([f"第{i+1}折" for i in range(len(cv_scores))], cv_scores, color=NAVY, width=0.55)
ax.axhline(cv_scores.mean(), color=PINK, linestyle="--", linewidth=2)
ax.text(len(cv_scores) - 0.5, cv_scores.mean() + 0.01, f"平均 {cv_scores.mean():.3f}", color=PINK, fontsize=11, fontweight="bold")
ax.set_ylabel("AUC", fontsize=12)
ax.set_ylim(0, max(cv_scores) + 0.15)
ax.spines[["top", "right"]].set_visible(False)
save(fig, "cv_auc.png")

# 6. 風險異常分數分佈
fig, ax = plt.subplots(figsize=(7, 4.2))
for flag, color in RISK_COLORS.items():
    sub = scored_df[scored_df.risk_flag == flag]
    ax.hist(sub.ai_risk_score, bins=30, color=color, alpha=0.75, label=flag.split("：")[1])
ax.set_xlabel("AI 異常分數（越高越像競品入侵）", fontsize=12)
ax.set_ylabel("客戶數", fontsize=12)
ax.legend(frameon=False, fontsize=10)
ax.spines[["top", "right"]].set_visible(False)
save(fig, "risk_score_dist.png")

print("Saved 6 chart images to", ASSETS)
