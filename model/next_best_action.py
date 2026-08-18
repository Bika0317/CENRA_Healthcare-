"""
Next Best Action：不只告訴業務員「去誰家」，還建議「推什麼品項」。
邏輯：用「同通路 × 同等級」客戶的品項採購佔比當作同儕基準（peer benchmark），
找出該客戶採購佔比明顯低於同儕的品項 —— 代表滲透缺口最大、最值得主動推薦的品項。
"""
import pandas as pd


def build_product_affinity(orders: pd.DataFrame, customers: pd.DataFrame):
    merged = orders.merge(customers[["customer_id", "channel", "tier"]], on="customer_id")

    peer_counts = merged.groupby(["channel", "tier", "product_line"]).size().rename("n").reset_index()
    peer_counts["peer_share"] = peer_counts["n"] / peer_counts.groupby(["channel", "tier"])["n"].transform("sum")
    peer_share = peer_counts[["channel", "tier", "product_line", "peer_share"]]

    own_counts = merged.groupby(["customer_id", "product_line"]).size().rename("n").reset_index()
    own_counts["own_share"] = own_counts["n"] / own_counts.groupby("customer_id")["n"].transform("sum")
    own_share = own_counts[["customer_id", "product_line", "own_share"]]

    return peer_share, own_share


def recommend_for_customer(customer_id: str, customers: pd.DataFrame, peer_share: pd.DataFrame,
                            own_share: pd.DataFrame):
    cust_rows = customers.loc[customers.customer_id == customer_id]
    if cust_rows.empty:
        return None
    cust = cust_rows.iloc[0]

    peers = peer_share[(peer_share.channel == cust.channel) & (peer_share.tier == cust.tier)]
    if peers.empty:
        return None

    own = own_share[own_share.customer_id == customer_id]
    merged = peers.merge(own[["product_line", "own_share"]], on="product_line", how="left")
    merged["own_share"] = merged["own_share"].fillna(0)
    merged["gap"] = merged["peer_share"] - merged["own_share"]
    merged = merged.sort_values("gap", ascending=False)

    if merged.empty or merged.iloc[0]["gap"] <= 0.02:
        return None

    top = merged.iloc[0]
    return {
        "product_line": top["product_line"],
        "peer_share": float(top["peer_share"]),
        "own_share": float(top["own_share"]),
        "gap": float(top["gap"]),
    }


def recommendation_text(rec: dict) -> str:
    if rec is None:
        return "目前品項組合已接近同儕客戶水準，無明顯滲透缺口。"
    return (
        f"建議主推「{rec['product_line']}」——同通路/等級客戶平均有 {rec['peer_share']:.0%} 會採購此品項，"
        f"此客戶目前僅 {rec['own_share']:.0%}，存在約 {rec['gap']:.0%} 的滲透缺口。"
    )
