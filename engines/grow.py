"""
增｜Grow Engine：找出合理的補貨或客戶服務深化時機。對應 SPEC §10.4。
"""
from __future__ import annotations

import statistics
from datetime import date, datetime, timedelta

from domain.models import ActionMode, Evidence, EvidenceStrength, TargetType, TaskType
from engines.candidate import Candidate
from engines.defend import _account_business_value

ALL_PRODUCT_LINES = {"處方藥", "OTC", "營養補充品", "個人護理", "醫療器材"}


def _replenishment_window(orders, as_of: date):
    dates = sorted(o["order_date"] for o in orders if o["order_date"])
    if len(dates) < 3:
        return False, None
    intervals = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
    median_interval = statistics.median(intervals)
    last_order = dates[-1]
    predicted_next = last_order + timedelta(days=median_interval)
    within_window = abs((as_of - predicted_next).days) <= max(median_interval * 0.2, 3)
    no_order_since = last_order < as_of
    return (within_window and no_order_since), median_interval


def _purchase_stability(orders) -> bool:
    dates = sorted(o["order_date"] for o in orders if o["order_date"])
    if len(dates) < 3:
        return False
    intervals = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
    mean_interval = statistics.mean(intervals)
    if mean_interval == 0:
        return False
    cv = statistics.pstdev(intervals) / mean_interval
    return cv < 0.5


def _product_gap(orders) -> tuple[bool, set[str]]:
    purchased = {o["product_line"] for o in orders}
    missing = ALL_PRODUCT_LINES - purchased
    return len(purchased) < 3, missing


def generate_candidates(fixture_repo, rep_id: str, as_of: date) -> list[Candidate]:
    candidates: list[Candidate] = []

    for account in fixture_repo.get_accounts(rep_id):
        if account["status"] == "inactive":
            continue
        orders = fixture_repo.get_orders(account["account_id"])
        interactions = fixture_repo.get_interactions(account["account_id"], "account")

        replenishment, median_interval = _replenishment_window(orders, as_of)
        stability = _purchase_stability(orders)
        gap, missing_lines = _product_gap(orders)
        demand_events = [i for i in interactions if not i["resolved"]
                          and i["summary_tag"] in ("demand", "product_interest")]
        demand_signal = bool(demand_events)

        if not (replenishment or gap or demand_signal):
            continue  # 沒有可用訊號，不產生任務（SPEC §10.1）

        raw_signal = (
            50 * (100 if replenishment else 0)
            + 20 * (100 if stability else 0)
            + 20 * (100 if gap else 0)
            + 10 * (100 if demand_signal else 0)
        ) / 100

        n_signals = sum([replenishment, stability, gap, demand_signal])
        evidence_strength = (
            EvidenceStrength.STRONG if n_signals >= 3 else
            EvidenceStrength.MEDIUM if n_signals == 2 else
            EvidenceStrength.WEAK
        )
        evidence_score = {"strong": 100, "medium": 70, "weak": 40}[evidence_strength.value]

        evidences: list[Evidence] = []
        if replenishment:
            last_order = max(o["order_date"] for o in orders if o["order_date"])
            evidences.append(Evidence(
                evidence_id=f"EV-{account['account_id']}-grow-repl", task_id="", code="grow_replenishment_window",
                label="接近個別補貨週期",
                display_value=f"歷史約每 {median_interval:.0f} 天補貨一次，距上次下單已 {(as_of - last_order).days} 天",
                source_type="order", source_id=None, occurred_at=None, strength=EvidenceStrength.STRONG,
            ))
        if gap:
            evidences.append(Evidence(
                evidence_id=f"EV-{account['account_id']}-grow-gap", task_id="", code="grow_product_gap",
                label="自身歷史品項缺口",
                display_value=f"尚未採購：{'、'.join(sorted(missing_lines)) or '（品項組合單一）'}",
                source_type="order", source_id=None, occurred_at=None, strength=EvidenceStrength.MEDIUM,
            ))
        if stability:
            evidences.append(Evidence(
                evidence_id=f"EV-{account['account_id']}-grow-stab", task_id="", code="grow_purchase_stability",
                label="過去採購穩定", display_value="訂單間隔規律，屬穩定採購客戶",
                source_type="order", source_id=None, occurred_at=None, strength=EvidenceStrength.MEDIUM,
            ))
        if demand_signal:
            ev = demand_events[0]
            evidences.append(Evidence(
                evidence_id=f"EV-{account['account_id']}-grow-demand", task_id="", code="grow_demand_signal",
                label="明確需求／產品興趣事件", display_value=ev["note"],
                source_type="interaction", source_id=ev["interaction_id"], occurred_at=ev["occurred_at"],
                strength=EvidenceStrength.STRONG,
            ))

        why_now = "接近個別補貨週期，近期尚未下單" if replenishment else \
            ("品項組合與同類診所相比存在缺口，值得確認需求" if gap else "近期出現明確需求／產品興趣訊號")
        uncertainty_note = "品項機會為初步假設，證據不足，需業務確認實際需求與適用性" if evidence_strength == EvidenceStrength.WEAK \
            else "品項機會需依產品適配與通路規範由業務把關，不代表最終建議"

        candidates.append(Candidate(
            target_type=TargetType.ACCOUNT, target_id=account["account_id"], target_name=account["name"],
            task_type=TaskType.GROW, raw_signal=raw_signal,
            raw_business_value=_account_business_value(orders, account, as_of),
            urgency_score=100 if replenishment and median_interval and
            abs((as_of - (max(o["order_date"] for o in orders if o["order_date"]) + timedelta(days=median_interval))).days) <= 7
            else (50 if replenishment else 0),
            evidence_score=evidence_score, strategy_fit_score=100,
            action_mode=ActionMode.VISIT,
            estimated_minutes=45,
            objective="確認補貨／需求並準備相關資訊",
            why_now=why_now, title=f"成長任務：{account['name']}",
            uncertainty_note=uncertainty_note,
            evidence_strength=evidence_strength, evidences=evidences[:3],
            lat=account["lat"], lon=account["lon"],
            data_updated_at=datetime.combine(as_of, datetime.min.time()),
            has_distance_data=account["lat"] is not None and account["lon"] is not None,
        ))

    return candidates
