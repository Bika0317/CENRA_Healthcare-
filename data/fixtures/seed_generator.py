"""
CENRA Mission 合成資料產生器。

原則（SPEC §9.3）：先生成事件（訂單/互動），再讓 engines/ 依規則判斷要不要產生任務；
不預先決定「這家診所是高風險」再回填特徵——那是舊版 competitor_pressure 洩漏標籤的錯誤。

主要 Demo 業務 R100 的資料是手工精心設計的，確保剛好對出 SPEC AC-01：
今日候選任務 = 8 個，攻 2、守 3、增 3。R101/R102 用簡單規則產生，補足團隊規模但不強求精確數字。

固定 random seed，重跑會得到一模一樣的資料。
"""
from __future__ import annotations

import csv
import os
from datetime import date, datetime, timedelta

import numpy as np

RNG = np.random.default_rng(42)

DEMO_DATE = date(2026, 8, 25)
HISTORY_START = DEMO_DATE - timedelta(days=200)

OUT_DIR = os.path.join(os.path.dirname(__file__))

REGION_CENTERS = {
    "台北": (25.0330, 121.5654),
    "新北": (25.0169, 121.4628),
    "桃園": (24.9936, 121.3010),
}
SPECIALTIES = ["家醫科", "內科", "皮膚科", "小兒科", "婦產科", "耳鼻喉科"]
PRODUCT_LINES = ["處方藥", "OTC", "營養補充品", "個人護理", "醫療器材"]
CORE_PRODUCT = "處方藥"


def jitter_latlon(region: str):
    lat, lon = REGION_CENTERS[region]
    return round(lat + RNG.normal(0, 0.03), 5), round(lon + RNG.normal(0, 0.03), 5)


def iso(d) -> str:
    if isinstance(d, date) and not isinstance(d, datetime):
        return d.isoformat()
    return d.isoformat()


# ---------------------------------------------------------------------------
# reps
# ---------------------------------------------------------------------------

REPS = [
    {"rep_id": "R100", "rep_name": "陳雅婷", "region": "台北", "email": "r100@cenra-demo.internal",
     "daily_available_minutes": 240},
    {"rep_id": "R101", "rep_name": "林柏宇", "region": "新北", "email": "r101@cenra-demo.internal",
     "daily_available_minutes": 240},
    {"rep_id": "R102", "rep_name": "黃思穎", "region": "桃園", "email": "r102@cenra-demo.internal",
     "daily_available_minutes": 240},
]


def build_r100_accounts():
    """主要 Demo 業務 R100 的 10 家既有帳戶，逐一對應 SPEC §9.2 情境。"""
    accounts = []
    interactions = []
    orders = []

    def add_account(account_id, name, specialty, status="active", value_band="medium"):
        lat, lon = jitter_latlon("台北")
        accounts.append({
            "account_id": account_id, "name": name, "specialty": specialty, "region": "台北",
            "status": status, "rep_id": "R100", "lat": lat, "lon": lon, "value_band": value_band,
            "created_at": iso(HISTORY_START - timedelta(days=400)),
            "updated_at": iso(DEMO_DATE - timedelta(days=1)),
        })
        return accounts[-1]

    def add_order(order_id, account_id, days_ago, product_line, amount, qty=10, status="completed"):
        orders.append({
            "order_id": order_id, "account_id": account_id, "rep_id": "R100",
            "order_date": iso(DEMO_DATE - timedelta(days=days_ago)),
            "product_line": product_line, "quantity": qty, "amount": amount, "status": status,
        })

    def add_interaction(iid, target_id, days_ago, channel, summary_tag, note, resolved=True,
                         competitor_mentioned=False, next_step=None, due_days_ago=None):
        interactions.append({
            "interaction_id": iid, "target_type": "account", "target_id": target_id, "rep_id": "R100",
            "occurred_at": iso(DEMO_DATE - timedelta(days=days_ago)), "channel": channel,
            "summary_tag": summary_tag, "note": note,
            "next_step": next_step or "", "due_date": iso(DEMO_DATE - timedelta(days=due_days_ago)) if due_days_ago else "",
            "resolved": resolved, "competitor_mentioned": competitor_mentioned,
        })

    # A001 守／強觸發：核心品項連續兩期停購 + 45天未有效互動 + 售後承諾逾期；無競品文字 -> 風險待查
    add_account("A001", "安康診所", "家醫科", value_band="high")
    for k in range(1, 7):
        add_order(f"O_A001_{k}", "A001", 200 - k * 25, CORE_PRODUCT, 42000)
    # 極舊的其他品項訂單（>300 天前，不落入任何守/增的分析窗），只為了讓品項組合 >=3 條，
    # 避免同時被增引擎判定為「品項缺口」而重複產生增任務（此帳戶定位是純守情境）
    add_order("O_A001_old1", "A001", 300, "OTC", 9000)
    add_order("O_A001_old2", "A001", 320, "營養補充品", 9000)
    # 近兩期核心品項完全沒有訂單（連續停購）
    add_interaction("I_A001_1", "A001", 60, "visit", "product_demo", "例行拜訪，關係穩定", resolved=True)
    add_interaction("I_A001_2", "A001", 50, "interaction", "follow_up", "承諾補送醫材資料，未完成",
                     resolved=False, next_step="補送醫材資料", due_days_ago=35)

    # A002 守／電話優先：服務事項未解決，不需要直接實訪
    add_account("A002", "康泰診所", "內科", value_band="medium")
    for k in range(1, 8):
        add_order(f"O_A002_{k}", "A002", 200 - k * 22, RNG.choice(PRODUCT_LINES), 18000)
    add_interaction("I_A002_1", "A002", 10, "phone", "service", "客訴：上批貨品破損未退換",
                     resolved=False, next_step="確認退換貨進度", due_days_ago=3)

    # A003 增／補貨時機：接近個別歷史補貨週期、近期尚未下單（缺座標，展示資料缺口）
    a003 = add_account("A003", "順心診所", "小兒科", value_band="medium")
    a003["lat"], a003["lon"] = "", ""  # 缺值情境：缺座標
    # 補一筆平常的互動，避免同時被守引擎判定為「互動中斷」而重複產生守任務
    add_interaction("I_A003_1", "A003", 20, "visit", "product_demo", "例行拜訪，關係正常", resolved=True)
    # 歷史穩定每 30 天補貨一次，最近一次是 32 天前，剛好接近下一個週期
    for k in range(1, 7):
        add_order(f"O_A003_{k}", "A003", 32 + (k - 1) * 30, "OTC", 15000)

    # A004 增／弱證據：品項機會但資料不足，需人工確認
    add_account("A004", "杏語診所", "皮膚科", value_band="low")
    add_order("O_A004_1", "A004", 150, "個人護理", 8000)
    add_order("O_A004_2", "A004", 70, "個人護理", 9000)
    # 只有微弱的品項缺口訊號，沒有其他佐證

    # A005 守／明確競品訊號：互動紀錄有直接文字標記
    add_account("A005", "海碩診所", "耳鼻喉科", value_band="high")
    for k in range(1, 6):
        add_order(f"O_A005_{k}", "A005", 200 - k * 20, CORE_PRODUCT, 35000)
    add_interaction("I_A005_1", "A005", 15, "visit", "competitor",
                     "醫師提到另一家廠商業務頻繁來訪、報價更低", resolved=False,
                     competitor_mentioned=True)

    # A006 增／採購穩定 + 品項缺口（第三個增任務）
    add_account("A006", "文心診所", "婦產科", value_band="medium")
    for k in range(1, 9):
        add_order(f"O_A006_{k}", "A006", 190 - k * 20, RNG.choice(["OTC", "營養補充品"]), 12000)
    # 從未買過個人護理線 -> 品項缺口

    # A007-A010 穩定填充帳戶：正常訂單節奏、無觸發訊號（對應「不產生任務」情境）
    # 品項固定輪替 3 種（>=3 條產品線，避免被判定為「品項缺口」）；訂單間隔短且互動已解決，
    # 避免湊巧落入補貨窗口或互動中斷的假訊號。
    filler_lines = ["OTC", "營養補充品", "個人護理"]
    for idx, (name, spec) in enumerate([
        ("福祐診所", "家醫科"), ("仁心診所", "內科"), ("康寧診所", "小兒科"), ("好日診所", "皮膚科"),
    ], start=7):
        aid = f"A{idx:03d}"
        add_account(aid, name, spec, value_band="medium")
        for k in range(1, 7):
            add_order(f"O_{aid}_{k}", aid, 10 + (k - 1) * 18, filler_lines[k % 3], 14000)
        add_interaction(f"I_{aid}_1", aid, 20, "visit", "product_demo", "例行拜訪，狀況穩定", resolved=True)

    return accounts, interactions, orders


def build_r100_prospects():
    prospects = []
    lat, lon = jitter_latlon("台北")
    prospects.append({
        "prospect_id": "P001", "name": "康悅診所", "specialty": "家醫科", "region": "台北",
        "rep_id": "R100", "contact_stage": "uncontacted", "fit_band": "high",
        "lead_source": "區域普查名單", "source_updated_at": iso(DEMO_DATE - timedelta(days=5)),
        "explicit_interest": False, "lat": lat, "lon": lon,
    })
    lat, lon = jitter_latlon("台北")
    prospects.append({
        "prospect_id": "P002", "name": "青禾診所", "specialty": "內科", "region": "台北",
        "rep_id": "R100", "contact_stage": "contacted", "fit_band": "high",
        "lead_source": "既有客戶轉介", "source_updated_at": iso(DEMO_DATE - timedelta(days=12)),
        "explicit_interest": True, "lat": lat, "lon": lon,
    })
    # P003：fit_band=low，不合格，用來測試攻引擎會排除它
    lat, lon = jitter_latlon("台北")
    prospects.append({
        "prospect_id": "P003", "name": "遠山診所", "specialty": "骨科", "region": "台北",
        "rep_id": "R100", "contact_stage": "uncontacted", "fit_band": "low",
        "lead_source": "公開名冊", "source_updated_at": iso(DEMO_DATE - timedelta(days=90)),
        "explicit_interest": False, "lat": lat, "lon": lon,
    })
    # P005：中適配、無明確興趣、線索偏舊，用來讓攻引擎百分位計算有 3 個樣本可比較
    # （避免只有 2 個候選時強制二選一產生 0/100 極端百分位），本身分數低於門檻不會顯示
    lat, lon = jitter_latlon("台北")
    prospects.append({
        "prospect_id": "P005", "name": "岳華診所", "specialty": "皮膚科", "region": "台北",
        "rep_id": "R100", "contact_stage": "uncontacted", "fit_band": "medium",
        "lead_source": "公開名冊", "source_updated_at": iso(DEMO_DATE - timedelta(days=40)),
        "explicit_interest": False, "lat": lat, "lon": lon,
    })
    # P004：已經有固定預約，不應再產生一般攻任務
    lat, lon = jitter_latlon("台北")
    prospects.append({
        "prospect_id": "P004", "name": "晴天診所", "specialty": "家醫科", "region": "台北",
        "rep_id": "R100", "contact_stage": "appointment", "fit_band": "high",
        "lead_source": "展會名單", "source_updated_at": iso(DEMO_DATE - timedelta(days=20)),
        "explicit_interest": True, "lat": lat, "lon": lon,
    })
    return prospects


def build_r100_appointments():
    return [
        {"appointment_id": "AP001", "rep_id": "R100", "target_id": "P004",
         "appointment_date": iso(DEMO_DATE), "start_time": "09:30", "duration_minutes": 40,
         "action_mode": "visit", "purpose": "新診所首次拜訪", "status": "fixed"},
        {"appointment_id": "AP002", "rep_id": "R100", "target_id": "A008",
         "appointment_date": iso(DEMO_DATE), "start_time": "14:00", "duration_minutes": 30,
         "action_mode": "visit", "purpose": "既定季度回訪", "status": "fixed"},
    ]


def build_other_rep_data(rep_id: str, region: str, n_accounts=9, n_prospects=4):
    """R101/R102：用簡單機率規則產生，不強求精確任務數量，只求資料合理豐富。"""
    accounts, prospects, interactions, orders, appointments = [], [], [], [], []

    for i in range(1, n_accounts + 1):
        aid = f"{rep_id}_A{i:03d}"
        lat, lon = jitter_latlon(region)
        value_band = RNG.choice(["high", "medium", "low"], p=[0.2, 0.5, 0.3])
        accounts.append({
            "account_id": aid, "name": f"{region}第{i}診所", "specialty": RNG.choice(SPECIALTIES),
            "region": region, "status": "active", "rep_id": rep_id, "lat": lat, "lon": lon,
            "value_band": value_band, "created_at": iso(HISTORY_START - timedelta(days=300)),
            "updated_at": iso(DEMO_DATE - timedelta(days=int(RNG.integers(1, 30)))),
        })
        n_orders = int(RNG.integers(3, 8))
        for k in range(n_orders):
            days_ago = int(RNG.integers(1, 190))
            orders.append({
                "order_id": f"O_{aid}_{k}", "account_id": aid, "rep_id": rep_id,
                "order_date": iso(DEMO_DATE - timedelta(days=days_ago)),
                "product_line": RNG.choice(PRODUCT_LINES),
                "quantity": int(RNG.integers(3, 20)), "amount": float(RNG.uniform(6000, 40000)),
                "status": "completed",
            })
        if RNG.random() < 0.5:
            days_ago = int(RNG.integers(1, 60))
            interactions.append({
                "interaction_id": f"I_{aid}_1", "target_type": "account", "target_id": aid, "rep_id": rep_id,
                "occurred_at": iso(DEMO_DATE - timedelta(days=days_ago)), "channel": RNG.choice(["visit", "phone"]),
                "summary_tag": RNG.choice(["product_demo", "follow_up", "service"]),
                "note": "例行互動紀錄", "next_step": "", "due_date": "",
                "resolved": bool(RNG.random() < 0.8), "competitor_mentioned": False,
            })

    for i in range(1, n_prospects + 1):
        pid = f"{rep_id}_P{i:03d}"
        lat, lon = jitter_latlon(region)
        prospects.append({
            "prospect_id": pid, "name": f"{region}潛力診所{i}", "specialty": RNG.choice(SPECIALTIES),
            "region": region, "rep_id": rep_id,
            "contact_stage": RNG.choice(["uncontacted", "contacted"]),
            "fit_band": RNG.choice(["high", "medium", "low"], p=[0.35, 0.4, 0.25]),
            "lead_source": "區域普查名單", "source_updated_at": iso(DEMO_DATE - timedelta(days=int(RNG.integers(1, 60)))),
            "explicit_interest": bool(RNG.random() < 0.3), "lat": lat, "lon": lon,
        })

    return accounts, prospects, interactions, orders, appointments


def write_csv(rows: list[dict], filename: str, fieldnames: list[str]):
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def generate_all():
    all_accounts, all_prospects, all_interactions, all_orders, all_appointments = [], [], [], [], []

    r100_accounts, r100_interactions, r100_orders = build_r100_accounts()
    all_accounts += r100_accounts
    all_interactions += r100_interactions
    all_orders += r100_orders
    all_prospects += build_r100_prospects()
    all_appointments += build_r100_appointments()

    for rep_id, region in [("R101", "新北"), ("R102", "桃園")]:
        accounts, prospects, interactions, orders, appointments = build_other_rep_data(rep_id, region)
        all_accounts += accounts
        all_prospects += prospects
        all_interactions += interactions
        all_orders += orders
        all_appointments += appointments

    write_csv(REPS, "reps.csv",
              ["rep_id", "rep_name", "region", "email", "daily_available_minutes"])
    write_csv(all_accounts, "accounts.csv",
              ["account_id", "name", "specialty", "region", "status", "rep_id", "lat", "lon",
               "value_band", "created_at", "updated_at"])
    write_csv(all_prospects, "prospects.csv",
              ["prospect_id", "name", "specialty", "region", "rep_id", "contact_stage", "fit_band",
               "lead_source", "source_updated_at", "explicit_interest", "lat", "lon"])
    write_csv(all_interactions, "interactions.csv",
              ["interaction_id", "target_type", "target_id", "rep_id", "occurred_at", "channel",
               "summary_tag", "note", "next_step", "due_date", "resolved", "competitor_mentioned"])
    write_csv(all_orders, "orders.csv",
              ["order_id", "account_id", "rep_id", "order_date", "product_line", "quantity",
               "amount", "status"])
    write_csv(all_appointments, "appointments.csv",
              ["appointment_id", "rep_id", "target_id", "appointment_date", "start_time",
               "duration_minutes", "action_mode", "purpose", "status"])

    return {
        "reps": len(REPS), "accounts": len(all_accounts), "prospects": len(all_prospects),
        "interactions": len(all_interactions), "orders": len(all_orders),
        "appointments": len(all_appointments),
    }


if __name__ == "__main__":
    counts = generate_all()
    print("Generated fixtures:", counts)
