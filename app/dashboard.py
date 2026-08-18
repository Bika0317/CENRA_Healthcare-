"""
智慧巡訪與成交預判系統 — 展示原型
執行方式：streamlit run app/dashboard.py
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "model"))

import io
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from datetime import date

from ranking import score_customers
from report import (
    export_table, rep_daily_visit_list, render_rep_email_html, render_manager_digest_html,
    render_rep_line_text, render_line_bubble_html,
)
from explain import top_explainable_features, explain_customer
from next_best_action import build_product_affinity, recommend_for_customer, recommendation_text
from ab_test import bootstrap_uplift
from sklearn.metrics import auc as sk_auc

RISK_COLOR_MAP = {"紅：高風險(疑似競品入侵)": "#d62728", "黃：需留意": "#e6b800", "綠：穩定": "#2ca02c"}
RISK_EMOJI_MAP = {"紅": "🔴", "黃": "🟡", "綠": "🟢"}


def with_risk_emoji(risk_flag: str) -> str:
    emoji = RISK_EMOJI_MAP.get(risk_flag.split("：")[0], "⚪")
    return f"{emoji} {risk_flag}"


def legend_below(fig):
    """把圖例移到圖表下方，避免跟右上角的縮放/平移工具列疊在一起。"""
    fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5))
    return fig

st.set_page_config(page_title="智慧巡訪與成交預判系統", layout="wide")

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "model", "purchase_model.pkl")
CUTOFF = date(2026, 8, 1)


@st.cache_data
def load_data():
    customers = pd.read_csv(os.path.join(DATA_DIR, "customers.csv"))
    visits = pd.read_csv(os.path.join(DATA_DIR, "visits.csv"))
    orders = pd.read_csv(os.path.join(DATA_DIR, "orders.csv"))
    reps = pd.read_csv(os.path.join(DATA_DIR, "reps.csv"))
    return customers, visits, orders, reps


@st.cache_data
def scored():
    customers, visits, orders, reps = load_data()
    scored_df = score_customers(customers, visits, orders, CUTOFF, model_path=MODEL_PATH)
    return scored_df, visits, orders, reps


scored_df, visits, orders, reps = scored()


customers = pd.read_csv(os.path.join(DATA_DIR, "customers.csv"))


@st.cache_data
def product_affinity():
    return build_product_affinity(orders, customers)


peer_share, own_share = product_affinity()

st.title("精準打擊：AI 驅動的「智慧巡訪與成交預判」系統")
st.caption("中化裕民 CENRA+ Healthcare ｜ 原型展示（合成資料，架構可直接接上真實 CRM/ERP）")

tab_overview, tab_rep, tab_customer, tab_model, tab_export = st.tabs(
    ["管理總覽", "業務員每日建議", "客戶診斷", "模型洞察", "每日通知信 / 匯出"]
)


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="拜訪優先清單")
    return buf.getvalue()

# ---------------- 管理總覽 ----------------
with tab_overview:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("客戶總數", len(scored_df))
    c2.metric("高風險客戶（疑似競品入侵）", int((scored_df.risk_flag.str.startswith("紅")).sum()))
    c3.metric("平均成交機率", f"{scored_df.purchase_proba.mean():.0%}")
    c4.metric("近90天總拜訪次數", int(scored_df.visits_last_90d.sum()))

    st.subheader("客戶價值 × 成交機率 × 風險 分佈")
    fig = px.scatter(
        scored_df, x="purchase_proba", y="base_monthly_value", color="risk_flag",
        size="revenue_last_90d", hover_data=["customer_name", "region", "channel", "tier"],
        color_discrete_map=RISK_COLOR_MAP,
        labels={"purchase_proba": "成交機率", "base_monthly_value": "客戶月價值估計"},
    )
    st.plotly_chart(legend_below(fig), use_container_width=True)

    st.subheader("客戶地理分佈（風險燈號）")
    map_fig = px.scatter_mapbox(
        scored_df, lat="lat", lon="lon", color="risk_flag", size="base_monthly_value",
        hover_data=["customer_name", "region", "channel", "purchase_proba"],
        color_discrete_map=RISK_COLOR_MAP, zoom=6.3, height=480,
        center={"lat": 23.9, "lon": 121.0},
    )
    map_fig.update_layout(mapbox_style="open-street-map", margin={"r": 0, "t": 0, "l": 0, "b": 0})
    map_fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))
    st.plotly_chart(map_fig, use_container_width=True)
    st.caption("紅點為疑似競品入侵的高風險客戶，可直接看出風險是否集中在特定區域，作為人力調度參考。")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("各業務員負責客戶之風險分佈")
        rep_risk = scored_df.merge(reps, on="rep_id").groupby(["rep_name", "risk_flag"]).size().reset_index(name="count")
        st.plotly_chart(legend_below(px.bar(rep_risk, x="rep_name", y="count", color="risk_flag",
                                color_discrete_map=RISK_COLOR_MAP)),
                         use_container_width=True)
    with col_b:
        st.subheader("預期效益模擬：AI 排序 vs 隨機拜訪（含信賴區間）")
        top_n = st.slider("假設每位業務員每天可拜訪客戶數", 3, 15, 6)
        boot = bootstrap_uplift(scored_df, ai_list_size=top_n * len(reps), n_boot=400)

        sim_fig = go.Figure()
        sim_fig.add_trace(go.Bar(
            x=["隨機/依經驗拜訪", "AI 優先排序拜訪"],
            y=[boot["random_mean"], boot["ai_mean"]],
            error_y=dict(
                type="data", symmetric=False,
                array=[boot["random_ci"][1] - boot["random_mean"], boot["ai_ci"][1] - boot["ai_mean"]],
                arrayminus=[boot["random_mean"] - boot["random_ci"][0], boot["ai_mean"] - boot["ai_ci"][0]],
            ),
            text=[f"{boot['random_mean']:.0%}", f"{boot['ai_mean']:.0%}"], textposition="outside",
            marker_color=["#9aa0a6", "#c8006e"],
        ))
        sim_fig.update_layout(yaxis_title="平均成交機率", showlegend=False)
        st.plotly_chart(sim_fig, use_container_width=True)
        st.caption(
            f"Bootstrap 重抽樣 400 次估計：隨機拜訪 {boot['random_mean']:.0%}"
            f"（95% CI {boot['random_ci'][0]:.0%}–{boot['random_ci'][1]:.0%}）→ "
            f"AI 排序 {boot['ai_mean']:.0%}（95% CI {boot['ai_ci'][0]:.0%}–{boot['ai_ci'][1]:.0%}），"
            f"提升 {boot['diff_mean']:+.0%}（95% CI {boot['diff_ci'][0]:+.0%}–{boot['diff_ci'][1]:+.0%}）。"
            "此為合成資料下的統計模擬，非真實 A/B 測試，正式上線建議以同期隨機分派驗證。"
        )

# ---------------- 業務員每日建議 ----------------
with tab_rep:
    rep_name = st.selectbox("選擇業務員", reps.sort_values("rep_name").rep_name.tolist())
    rep_id = reps.loc[reps.rep_name == rep_name, "rep_id"].iloc[0]

    my_customers = scored_df[scored_df.rep_id == rep_id].sort_values("priority_score", ascending=False)
    st.subheader(f"{rep_name} 的今日建議拜訪清單（依優先分數排序）")

    show_cols = {
        "customer_name": "客戶名稱", "region": "地區", "channel": "通路", "tier": "等級",
        "purchase_proba": "成交機率", "risk_flag": "風險燈號",
        "days_since_last_visit": "距上次拜訪天數", "revenue_last_90d": "近90天營收",
    }
    display_df = my_customers[list(show_cols.keys())].rename(columns=show_cols)
    display_df["成交機率"] = display_df["成交機率"].map(lambda x: f"{x:.0%}")
    display_df["風險燈號"] = display_df["風險燈號"].map(with_risk_emoji)
    st.dataframe(display_df, use_container_width=True, height=420)

    st.subheader("今日建議拜訪路線（依優先分數排序）")
    route_n = st.slider("今天預計拜訪幾家", 3, min(15, max(3, len(my_customers))), min(6, len(my_customers)) if len(my_customers) else 3)
    route_df = my_customers.head(route_n).reset_index(drop=True)
    if not route_df.empty:
        route_df["順序"] = route_df.index + 1
        route_fig = go.Figure(go.Scattermapbox(
            lat=route_df["lat"], lon=route_df["lon"], mode="markers+lines+text",
            text=route_df["順序"].astype(str), textposition="top center",
            marker=dict(size=16, color=route_df["risk_flag"].map(RISK_COLOR_MAP)),
            line=dict(width=2, color="#888"),
            hovertext=route_df["customer_name"] + "｜成交機率 " + (route_df["purchase_proba"] * 100).round(0).astype(str) + "%",
            hoverinfo="text",
        ))
        route_fig.update_layout(
            mapbox_style="open-street-map", height=440,
            mapbox_center={"lat": route_df["lat"].mean(), "lon": route_df["lon"].mean()},
            mapbox_zoom=9.5, margin={"r": 0, "t": 0, "l": 0, "b": 0}, showlegend=False,
        )
        st.plotly_chart(route_fig, use_container_width=True)
        st.caption("數字為建議拜訪順序（直線示意，非實際路網路徑），可作為排路線的起點。")

    st.markdown("**建議行動範例（Top 3，含 Next Best Action 推薦品項）：**")
    for _, row in my_customers.head(3).iterrows():
        action = "優先攔截競品滲透，安排面對面拜訪並確認需求缺口" if row.risk_flag.startswith("紅") else \
                 ("成交機率高，建議直接推進報價/簽約" if row.purchase_proba > 0.6 else "維繫關係，了解近況與潛在需求")
        rec = recommend_for_customer(row.customer_id, customers, peer_share, own_share)
        nba = recommendation_text(rec)
        st.write(f"- **{row.customer_name}**（{row.risk_flag}，成交機率 {row.purchase_proba:.0%}）→ {action}")
        st.caption(f"　　💡 {nba}")

    st.download_button(
        f"匯出 {rep_name} 的拜訪清單（CSV）",
        export_table(my_customers).to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{rep_name}_拜訪清單.csv", mime="text/csv",
    )

# ---------------- 客戶診斷 ----------------
with tab_customer:
    cust_name = st.selectbox("選擇客戶", scored_df.sort_values("customer_name").customer_name.tolist())
    cust = scored_df[scored_df.customer_name == cust_name].iloc[0]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("成交機率", f"{cust.purchase_proba:.0%}")
    m2.metric("風險燈號", f"{RISK_EMOJI_MAP.get(cust.risk_flag.split('：')[0], '⚪')} {cust.risk_flag.split('：')[0]}")
    m3.metric("距上次拜訪(天)", int(cust.days_since_last_visit))
    m4.metric("近90天營收", f"{cust.revenue_last_90d:,.0f}")

    fi_path_local = os.path.join(os.path.dirname(__file__), "..", "model", "feature_importance.csv")
    if os.path.exists(fi_path_local):
        fi_series = pd.read_csv(fi_path_local, index_col=0).iloc[:, 0]
        top_feats = top_explainable_features(fi_series, max_n=8)
        reasons = explain_customer(cust, scored_df, top_feats, n_reasons=3)
        st.subheader("系統判斷原因（成交機率預測依據）")
        if reasons:
            for r in reasons:
                st.write(f"- {r}")
        else:
            st.caption("暫無足夠特徵可解釋。")
        st.caption("依模型最重要的特徵，比較此客戶與全體客戶的百分位差異自動生成，非嚴謹的 SHAP 值分解，僅供業務主管快速理解判斷依據。")

    st.subheader("Next Best Action：建議主推品項")
    nba_rec = recommend_for_customer(cust.customer_id, customers, peer_share, own_share)
    st.info(recommendation_text(nba_rec))

    cust_visits = visits[visits.customer_id == cust.customer_id].copy()
    cust_orders = orders[orders.customer_id == cust.customer_id].copy()
    cust_visits["visit_date"] = pd.to_datetime(cust_visits.visit_date)
    cust_orders["order_date"] = pd.to_datetime(cust_orders.order_date)

    monthly_orders = cust_orders.set_index("order_date").resample("ME")["amount"].sum().reset_index()
    st.subheader("訂單金額趨勢")
    st.plotly_chart(px.line(monthly_orders, x="order_date", y="amount", markers=True), use_container_width=True)

    st.subheader("拜訪紀錄（近期）")
    st.dataframe(cust_visits.sort_values("visit_date", ascending=False).head(15), use_container_width=True)

# ---------------- 模型洞察 ----------------
with tab_model:
    st.subheader("成交預判模型：5-fold 交叉驗證")
    cv_path = os.path.join(os.path.dirname(__file__), "..", "model", "cv_scores.csv")
    if os.path.exists(cv_path):
        cv_scores = pd.read_csv(cv_path)["cv_auc"]
        cv1, cv2, cv3 = st.columns(3)
        cv1.metric("平均 AUC（5-fold）", f"{cv_scores.mean():.3f}")
        cv2.metric("標準差", f"±{cv_scores.std():.3f}")
        cv3.metric("最低 / 最高折", f"{cv_scores.min():.3f} / {cv_scores.max():.3f}")
        cv_fig = px.bar(
            pd.DataFrame({"fold": [f"第{i+1}折" for i in range(len(cv_scores))], "AUC": cv_scores}),
            x="fold", y="AUC",
        )
        cv_fig.add_hline(y=cv_scores.mean(), line_dash="dash", line_color="#c8006e",
                          annotation_text=f"平均 {cv_scores.mean():.3f}")
        st.plotly_chart(cv_fig, use_container_width=True)
        st.caption("用 5-fold 交叉驗證取代單次 train/test 切分，確認模型表現不是抽到特定切分運氣好，各折 AUC 落在相近區間代表穩定。")

    with st.expander("AUC 與交叉驗證是怎麼算出來的（公式 + 可驗證證據）"):
        st.markdown("**AUC（ROC 曲線下面積）定義：**")
        st.latex(r"\text{AUC} = P\big(\hat{p}(x^{+}) > \hat{p}(x^{-})\big)")
        st.caption("白話說：隨機各抽一位「有下單」與「沒下單」的客戶，模型給前者的預測分數比後者高的機率。0.5 = 純猜測，1.0 = 完美排序。")
        st.markdown("**5-fold Stratified 交叉驗證流程：**")
        st.latex(r"\overline{\text{AUC}} = \frac{1}{5}\sum_{k=1}^{5} \text{AUC}_k \,,\quad \text{std} = \sqrt{\frac{1}{5}\sum_{k=1}^{5}(\text{AUC}_k-\overline{\text{AUC}})^2}")
        st.caption("資料依標籤比例切成 5 折；每折輪流當測試集，其餘 4 折訓練，共訓練 5 個模型；平均值與標準差就是上方長條圖的依據。")

        roc_path = os.path.join(os.path.dirname(__file__), "..", "model", "roc_curve.csv")
        if os.path.exists(roc_path):
            roc_df = pd.read_csv(roc_path)
            oof_auc = sk_auc(roc_df["fpr"], roc_df["tpr"])
            st.markdown(f"**Out-of-fold ROC 曲線**（整體 AUC = {oof_auc:.3f}，每筆樣本的預測都來自沒看過它的那一折模型，可與上方 5-fold 平均互相驗證）")
            roc_fig = go.Figure()
            roc_fig.add_trace(go.Scatter(x=roc_df["fpr"], y=roc_df["tpr"], mode="lines", name="模型 ROC", line=dict(color="#c8006e", width=3)))
            roc_fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="隨機猜測基準線", line=dict(color="#aaa", dash="dash")))
            roc_fig.update_layout(xaxis_title="False Positive Rate", yaxis_title="True Positive Rate", height=420)
            st.plotly_chart(roc_fig, use_container_width=True)
            st.caption("這條曲線是用 sklearn `cross_val_predict` 產生的 out-of-fold 預測機率直接畫出來的，不是憑空編的數字；原始 fpr/tpr 資料存於 model/roc_curve.csv，任何人都能重算驗證。")

    st.divider()
    st.subheader("成交預判模型：特徵重要性")
    fi_path = os.path.join(os.path.dirname(__file__), "..", "model", "feature_importance.csv")
    if os.path.exists(fi_path):
        fi = pd.read_csv(fi_path, index_col=0).reset_index()
        fi.columns = ["feature", "importance"]
        st.plotly_chart(px.bar(fi.head(12), x="importance", y="feature", orientation="h"), use_container_width=True)
    st.markdown(
        "**成交預判模型**：以 RandomForest 對客戶未來90天是否下單進行分類，"
        "特徵涵蓋 RFM（拜訪/訂單的近度、頻率、金額）、業績趨勢、競品提及次數等。"
        "目前使用合成資料驗證 pipeline 可行性，換上真實 CRM/ERP 資料後即可重新訓練並提升準確度。"
    )

    st.divider()
    st.subheader("風險偵測模型：IsolationForest 異常分數分佈")
    st.plotly_chart(
        legend_below(px.histogram(scored_df, x="ai_risk_score", color="risk_flag", nbins=40,
                      color_discrete_map=RISK_COLOR_MAP,
                      labels={"ai_risk_score": "AI 異常分數（越高越像競品入侵）"})),
        use_container_width=True,
    )
    st.markdown(
        "**風險模型說明**：競品入侵風險已從人工加權規則升級為 **IsolationForest 無監督異常偵測**——"
        "以「拜訪頻率變化、業績趨勢、競品提及次數、拜訪/訂單轉換率」等特徵組合，"
        "找出偏離群體常態的客戶，不需要事先定義「多異常才算異常」的門檻，能隨資料自動調整。"
    )

# ---------------- 每日通知信 / 匯出 ----------------
with tab_export:
    st.subheader("完整拜訪優先清單匯出")
    full_table = export_table(scored_df.sort_values("priority_score", ascending=False))
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "匯出全公司拜訪優先清單（CSV）",
            full_table.to_csv(index=False).encode("utf-8-sig"),
            file_name="全公司拜訪優先清單.csv", mime="text/csv",
        )
    with col2:
        st.download_button(
            "匯出全公司拜訪優先清單（Excel）",
            to_excel_bytes(full_table),
            file_name="全公司拜訪優先清單.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    st.divider()
    st.subheader("每日通知信預覽（Dry Run）")
    st.caption(
        "以下為系統每天會自動產生的信件內容預覽。目前為 Dry Run 模式：內容會渲染出來但不會真的寄出。"
        "正式上線時，只要設定 SMTP 帳密並排程執行 notify/send_daily_email.py --send，"
        "即可依此內容每天定時自動寄給業務員與主管。"
    )

    report_date_str = date.today().isoformat()
    preview_rep = st.selectbox("預覽對象（業務員）", reps.sort_values("rep_name").rep_name.tolist(), key="email_preview_rep")
    preview_rep_id = reps.loc[reps.rep_name == preview_rep, "rep_id"].iloc[0]
    preview_list = rep_daily_visit_list(scored_df, preview_rep_id, top_n=8)
    email_html = render_rep_email_html(preview_rep, preview_list, report_date_str)

    components.html(email_html, height=560, scrolling=True)
    st.download_button(
        f"下載 {preview_rep} 的通知信（HTML）", email_html.encode("utf-8"),
        file_name=f"{report_date_str}_{preview_rep}_通知信.html", mime="text/html",
    )

    st.markdown("**主管高風險客戶彙總信預覽**")
    manager_html = render_manager_digest_html(scored_df, reps, report_date_str)
    components.html(manager_html, height=560, scrolling=True)
    st.download_button(
        "下載主管彙總信（HTML）", manager_html.encode("utf-8"),
        file_name=f"{report_date_str}_主管彙總信.html", mime="text/html",
    )

    st.divider()
    st.subheader("LINE 通知預覽（Mock）")
    st.caption(
        "業務員多數時間在外面跑客戶，email 不一定即時看到——LINE 訊息更貼近實際使用情境。"
        "以下為同一份建議清單改成 LINE 訊息格式的視覺化 mock，尚未串接 LINE Bot API（原型展示用）。"
    )
    line_text = render_rep_line_text(preview_rep, preview_list, report_date_str)
    line_html = render_line_bubble_html(line_text)
    components.html(line_html, height=320, scrolling=True)
    st.download_button(
        f"下載 {preview_rep} 的 LINE 訊息文字", line_text.encode("utf-8"),
        file_name=f"{report_date_str}_{preview_rep}_LINE訊息.txt", mime="text/plain",
    )
