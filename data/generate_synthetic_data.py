"""
模擬「中化裕民」業務情境的 CRM 資料集：客戶、拜訪紀錄、訂單。
真實資料未提供，先用具business sense的合成資料跑通整條 pipeline，
之後只要把資料來源換成公司真實 CRM/ERP 匯出檔，模型與 dashboard 不需大改。
"""
import numpy as np
import pandas as pd
from faker import Faker
from datetime import date, timedelta

fake = Faker("zh_TW")
rng = np.random.default_rng(42)

N_REPS = 18
N_CUSTOMERS = 420
END_DATE = date(2026, 8, 1)
START_DATE = END_DATE - timedelta(days=540)  # 18個月歷史

REGIONS = ["台北", "新北", "桃園", "台中", "台南", "高雄", "花東"]
CHANNELS = ["醫院", "診所", "藥局", "藥妝通路"]
PRODUCT_LINES = ["處方藥", "OTC", "營養補充品", "個人護理", "醫療器材"]

REGION_CENTERS = {
    "台北": (25.0330, 121.5654),
    "新北": (25.0169, 121.4628),
    "桃園": (24.9936, 121.3010),
    "台中": (24.1477, 120.6736),
    "台南": (22.9997, 120.2270),
    "高雄": (22.6273, 120.3014),
    "花東": (23.6978, 121.1444),
}

def gen_reps():
    names = [fake.name() for _ in range(N_REPS)]
    reps = pd.DataFrame({
        "rep_id": [f"L{100+i}" for i in range(N_REPS)],
        "rep_name": names,
        "region": rng.choice(REGIONS, N_REPS),
        "email": [f"rep{100+i}@cenra-demo.internal" for i in range(N_REPS)],
    })
    return reps

def gen_customers(reps):
    rows = []
    for i in range(N_CUSTOMERS):
        region = rng.choice(REGIONS)
        rep_id = rng.choice(reps.loc[reps.region == region, "rep_id"].values
                             if (reps.region == region).any() else reps.rep_id.values)
        channel = rng.choice(CHANNELS, p=[0.1, 0.35, 0.4, 0.15])
        tier = rng.choice(["A", "B", "C"], p=[0.15, 0.35, 0.5])
        base_monthly_value = {"A": rng.uniform(80000, 200000),
                               "B": rng.uniform(25000, 80000),
                               "C": rng.uniform(3000, 25000)}[tier]
        onboard_days_ago = int(rng.uniform(60, 1500))
        center_lat, center_lon = REGION_CENTERS[region]
        rows.append({
            "customer_id": f"C{1000+i}",
            "customer_name": fake.company(),
            "region": region,
            "rep_id": rep_id,
            "channel": channel,
            "tier": tier,
            "base_monthly_value": base_monthly_value,
            "onboard_date": END_DATE - timedelta(days=onboard_days_ago),
            "competitor_pressure": rng.choice([0, 1], p=[0.72, 0.28]),  # 是否處於競品積極滲透地區/客群
            "lat": center_lat + rng.normal(0, 0.06),
            "lon": center_lon + rng.normal(0, 0.06),
        })
    return pd.DataFrame(rows)

def gen_visits_and_orders(customers):
    visit_rows, order_rows = [], []
    days_total = (END_DATE - START_DATE).days

    for _, cust in customers.iterrows():
        # 拜訪頻率隨 tier 不同，競品壓力大者業務員近期拜訪反而常常變少（真實痛點：資源沒配到刀口上）
        base_visits_per_month = {"A": 3.2, "B": 1.8, "C": 0.8}[cust.tier]
        decline_factor = 1.0
        if cust.competitor_pressure:
            decline_factor = rng.uniform(0.35, 0.7)  # 近期拜訪量萎縮

        n_months = days_total // 30
        for m in range(n_months):
            month_start = START_DATE + timedelta(days=30 * m)
            recent = m >= n_months - 4  # 最近4個月
            lam = base_visits_per_month * (decline_factor if recent and cust.competitor_pressure else 1.0)
            n_visits = rng.poisson(max(lam, 0.05))
            for _ in range(n_visits):
                v_date = month_start + timedelta(days=int(rng.uniform(0, 29)))
                purpose = rng.choice(["產品推廣", "關係維護", "收款", "客訴處理"], p=[0.5, 0.25, 0.15, 0.1])
                mentions_competitor = int(cust.competitor_pressure and rng.random() < 0.4)
                visit_rows.append({
                    "customer_id": cust.customer_id,
                    "rep_id": cust.rep_id,
                    "visit_date": v_date,
                    "purpose": purpose,
                    "mentions_competitor": mentions_competitor,
                })

            # 訂單：與拜訪弱相關，competitor_pressure 使近期金額下滑
            order_prob = 0.55 if n_visits > 0 else 0.15
            if rng.random() < order_prob:
                monthly_value = cust.base_monthly_value
                if recent and cust.competitor_pressure:
                    monthly_value *= rng.uniform(0.3, 0.65)
                amount = max(0, rng.normal(monthly_value, monthly_value * 0.25))
                order_rows.append({
                    "customer_id": cust.customer_id,
                    "rep_id": cust.rep_id,
                    "order_date": month_start + timedelta(days=int(rng.uniform(0, 29))),
                    "product_line": rng.choice(PRODUCT_LINES),
                    "amount": round(amount, 0),
                    "gross_margin_pct": round(rng.uniform(0.15, 0.45), 3),
                    "is_self_pay": int(rng.random() < 0.35),
                })

    return pd.DataFrame(visit_rows), pd.DataFrame(order_rows)


if __name__ == "__main__":
    reps = gen_reps()
    customers = gen_customers(reps)
    visits, orders = gen_visits_and_orders(customers)

    reps.to_csv("data/reps.csv", index=False)
    customers.to_csv("data/customers.csv", index=False)
    visits.to_csv("data/visits.csv", index=False)
    orders.to_csv("data/orders.csv", index=False)

    print(f"reps={len(reps)}, customers={len(customers)}, visits={len(visits)}, orders={len(orders)}")
