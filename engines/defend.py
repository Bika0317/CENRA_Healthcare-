"""
守｜Defend Engine：找出尚未完全流失、目前仍可介入的既有診所。對應 SPEC §10.3。

明確原則：沒有直接 competitor_mentioned=true 的來源事件時，文案只能是「風險待查／異常待查」，
絕不能宣稱「已被競品入侵」。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from domain.models import ActionMode, Evidence, EvidenceStrength, TargetType, TaskType
from engines.candidate import Candidate

CORE_PRODUCT = "處方藥"
PERIOD_DAYS = 30
INTERACTION_GAP_THRESHOLD_DAYS = 45  # 簡化版「歷史常態」門檻，見 README 已知限制


def _period_orders(orders, start: date, end: date):
    return [o for o in orders if o["order_date"] and start <= o["order_date"] < end]


def _detect_triggers(account, orders, interactions, as_of: date):
    p1_start, p1_end = as_of - timedelta(days=PERIOD_DAYS), as_of
    p2_start, p2_end = as_of - timedelta(days=2 * PERIOD_DAYS), p1_start
    recent_core = [o for o in _period_orders(orders, p1_start, p1_end) if o["product_line"] == CORE_PRODUCT]
    prior_core = [o for o in _period_orders(orders, p2_start, p2_end) if o["product_line"] == CORE_PRODUCT]
    older_core = [o for o in orders if o["order_date"] and o["order_date"] < p2_start and o["product_line"] == CORE_PRODUCT]
    core_stopped = len(recent_core) == 0 and len(prior_core) == 0 and len(older_core) > 0

    last90 = sum(o["amount"] for o in _period_orders(orders, as_of - timedelta(days=90), as_of))
    prior90 = sum(o["amount"] for o in _period_orders(orders, as_of - timedelta(days=180), as_of - timedelta(days=90)))
    revenue_decline = prior90 > 0 and last90 < prior90 * 0.8

    breadth_last90 = {o["product_line"] for o in _period_orders(orders, as_of - timedelta(days=90), as_of)}
    breadth_prior90 = {o["product_line"] for o in _period_orders(orders, as_of - timedelta(days=180), as_of - timedelta(days=90))}
    product_breadth_decline = len(breadth_prior90) > 0 and len(breadth_last90) < len(breadth_prior90)

    last_interaction_dt = max((i["occurred_at"] for i in interactions if i["occurred_at"]), default=None)
    interaction_gap = (
        (as_of - last_interaction_dt.date()).days > INTERACTION_GAP_THRESHOLD_DAYS
        if last_interaction_dt else True
    )

    overdue_commitment = [
        i for i in interactions if not i["resolved"] and i["due_date"]
        and (as_of - i["due_date"]).days >= 7 and i["summary_tag"] != "service"
    ]
    overdue_service = [
        i for i in interactions if not i["resolved"] and i["summary_tag"] == "service"
        and i["due_date"] and (as_of - i["due_date"]).days >= 0
    ]
    competitor_events = [i for i in interactions if i["competitor_mentioned"]]

    return {
        "core_stopped": core_stopped, "revenue_decline": revenue_decline,
        "interaction_gap": interaction_gap, "product_breadth_decline": product_breadth_decline,
        "overdue_commitment": bool(overdue_commitment), "overdue_service": bool(overdue_service),
        "competitor": bool(competitor_events),
        "_overdue_commitment_events": overdue_commitment, "_overdue_service_events": overdue_service,
        "_competitor_events": competitor_events, "_last_interaction_dt": last_interaction_dt,
    }


def generate_candidates(fixture_repo, rep_id: str, as_of: date) -> list[Candidate]:
    candidates: list[Candidate] = []

    for account in fixture_repo.get_accounts(rep_id):
        if account["status"] == "inactive":
            continue
        orders = fixture_repo.get_orders(account["account_id"])
        interactions = fixture_repo.get_interactions(account["account_id"], "account")
        t = _detect_triggers(account, orders, interactions, as_of)

        strong = t["core_stopped"] or t["overdue_commitment"] or t["overdue_service"]
        general_signals = [t["revenue_decline"], t["interaction_gap"], t["product_breadth_decline"], t["competitor"]]
        if not strong and sum(general_signals) < 2:
            continue  # 沒有足夠證據，不產生任務（SPEC §10.1 必要觸發條件）

        raw_signal = (
            35 * (100 if t["core_stopped"] else 0)
            + 25 * (100 if t["revenue_decline"] else 0)
            + 15 * (100 if t["interaction_gap"] else 0)
            + 15 * (100 if (t["overdue_commitment"] or t["overdue_service"]) else 0)
            + 10 * (100 if t["competitor"] else 0)
        ) / 100

        n_signals = sum([t["core_stopped"], t["revenue_decline"], t["interaction_gap"],
                          t["product_breadth_decline"], t["overdue_commitment"] or t["overdue_service"],
                          t["competitor"]])
        evidence_strength = (
            EvidenceStrength.STRONG if n_signals >= 3 else
            EvidenceStrength.MEDIUM if n_signals == 2 else
            EvidenceStrength.WEAK
        )
        evidence_score = {"strong": 100, "medium": 70, "weak": 40}[evidence_strength.value]

        evidences: list[Evidence] = []
        if t["core_stopped"]:
            evidences.append(Evidence(
                evidence_id=f"EV-{account['account_id']}-defend-core", task_id="", code="defend_core_product_stopped",
                label="核心品項連續停購", display_value=f"{CORE_PRODUCT} 連續 2 期無訂單",
                source_type="order", source_id=None, occurred_at=None, strength=EvidenceStrength.STRONG,
            ))
        if t["overdue_commitment"] or t["overdue_service"]:
            ev = (t["_overdue_commitment_events"] or t["_overdue_service_events"])[0]
            evidences.append(Evidence(
                evidence_id=f"EV-{account['account_id']}-defend-overdue", task_id="", code="defend_overdue_commitment",
                label="未完成承諾已逾期" if not t["overdue_service"] else "服務／客訴事項未解決",
                display_value=f"{ev['next_step'] or ev['note']}（逾期 {(as_of - ev['due_date']).days} 天）",
                source_type="interaction", source_id=ev["interaction_id"], occurred_at=ev["occurred_at"],
                strength=EvidenceStrength.STRONG,
            ))
        if t["revenue_decline"]:
            evidences.append(Evidence(
                evidence_id=f"EV-{account['account_id']}-defend-rev", task_id="", code="defend_revenue_decline",
                label="訂單金額連續下降", display_value="近 90 天營收較前期下滑逾 20%",
                source_type="order", source_id=None, occurred_at=None, strength=EvidenceStrength.MEDIUM,
            ))
        if t["interaction_gap"]:
            days = (as_of - t["_last_interaction_dt"].date()).days if t["_last_interaction_dt"] else None
            evidences.append(Evidence(
                evidence_id=f"EV-{account['account_id']}-defend-gap", task_id="", code="defend_interaction_gap",
                label="距上次有效互動過長",
                display_value=f"{days} 天未有效互動" if days else "尚無任何互動紀錄",
                source_type="interaction", source_id=None,
                occurred_at=t["_last_interaction_dt"], strength=EvidenceStrength.MEDIUM,
            ))
        if t["competitor"]:
            ev = t["_competitor_events"][0]
            evidences.append(Evidence(
                evidence_id=f"EV-{account['account_id']}-defend-comp", task_id="", code="defend_competitor_mentioned",
                label="互動紀錄出現直接競品訊號", display_value=ev["note"],
                source_type="interaction", source_id=ev["interaction_id"], occurred_at=ev["occurred_at"],
                strength=EvidenceStrength.STRONG,
            ))

        action_mode = ActionMode.PHONE if (t["overdue_service"] and not t["core_stopped"]) else ActionMode.VISIT
        why_now = "流失風險待查：核心品項停購、互動中斷或承諾逾期等多項訊號同時出現" if not t["competitor"] \
            else "流失風險待查，且互動紀錄中出現疑似競品相關文字，建議準備對應問題"
        title = f"流失挽回任務：{account['name']}"

        candidates.append(Candidate(
            target_type=TargetType.ACCOUNT, target_id=account["account_id"], target_name=account["name"],
            task_type=TaskType.DEFEND, raw_signal=raw_signal,
            raw_business_value=_account_business_value(orders, account, as_of),
            urgency_score=100 if strong else 50,
            evidence_score=evidence_score, strategy_fit_score=100,
            action_mode=action_mode,
            estimated_minutes=20 if action_mode == ActionMode.PHONE else 45,
            objective="確認庫存、需求變化與未完成承諾",
            why_now=why_now, title=title,
            uncertainty_note="原因需業務確認：異常可能來自競品、預算、換人接洽或其他因素",
            evidence_strength=evidence_strength, evidences=evidences[:3],
            lat=account["lat"], lon=account["lon"],
            data_updated_at=datetime.combine(as_of, datetime.min.time()),
            has_distance_data=account["lat"] is not None and account["lon"] is not None,
        ))

    return candidates


def _account_business_value(orders, account, as_of: date) -> float:
    last180 = sum(o["amount"] for o in _period_orders(orders, as_of - timedelta(days=180), as_of))
    if last180 > 0:
        return last180  # 百分位轉換交給 scoring.py，這裡先回傳原始金額
    return {"high": 80, "medium": 50, "low": 20}[account["value_band"]]
