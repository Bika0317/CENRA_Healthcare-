"""
攻｜Attack Engine：找出值得首次接觸的高潛力新診所。對應 SPEC §10.2。
"""
from __future__ import annotations

from datetime import date, datetime

from domain.models import ActionMode, Evidence, EvidenceStrength, TargetType, TaskType
from engines.candidate import Candidate

FIT_SCORE = {"high": 100, "medium": 60, "low": 0}


def _freshness_score(source_updated_at: date, as_of: date) -> float:
    days = (as_of - source_updated_at).days
    if days <= 14:
        return 100
    if days <= 30:
        return 70
    if days <= 60:
        return 40
    return 10


def generate_candidates(fixture_repo, rep_id: str, as_of: date) -> list[Candidate]:
    """回傳該業務所有合格的攻任務候選（尚未經過百分位轉換）。"""
    candidates: list[Candidate] = []

    for p in fixture_repo.get_prospects(rep_id):
        # 資格條件：尚未合作、fit_band 不為 low、uncontacted/contacted 且沒有固定 appointment
        if p["fit_band"] == "low":
            continue
        if p["contact_stage"] not in ("uncontacted", "contacted"):
            continue
        if fixture_repo.has_fixed_appointment(p["prospect_id"], as_of):
            continue  # 已有固定預約，交給固定行程處理，不重複產生攻任務

        fit = FIT_SCORE[p["fit_band"]]
        interest = 100 if p["explicit_interest"] else 0
        freshness = _freshness_score(
            date.fromisoformat(p["source_updated_at"]) if isinstance(p["source_updated_at"], str) else p["source_updated_at"],
            as_of,
        )
        raw_signal = 0.5 * fit + 0.3 * interest + 0.2 * freshness

        n_signals = sum([fit >= 60, interest > 0, freshness >= 70])
        evidence_strength = (
            EvidenceStrength.STRONG if n_signals >= 3 else
            EvidenceStrength.MEDIUM if n_signals == 2 else
            EvidenceStrength.WEAK
        )
        evidence_score = {"strong": 100, "medium": 70, "weak": 40}[evidence_strength.value]

        evidences = [
            Evidence(
                evidence_id=f"EV-{p['prospect_id']}-attack-fit", task_id="", code="attack_fit",
                label="科別／策略適配", display_value=f"適配等級：{p['fit_band']}",
                source_type="prospect", source_id=p["prospect_id"], occurred_at=None,
                strength=EvidenceStrength.STRONG if fit >= 100 else EvidenceStrength.MEDIUM,
            ),
            Evidence(
                evidence_id=f"EV-{p['prospect_id']}-attack-fresh", task_id="", code="attack_lead_freshness",
                label="線索來源新鮮度", display_value=f"{p['lead_source']}，{freshness:.0f} 分",
                source_type="prospect", source_id=p["prospect_id"], occurred_at=None,
                strength=EvidenceStrength.MEDIUM,
            ),
        ]
        if p["explicit_interest"]:
            evidences.append(Evidence(
                evidence_id=f"EV-{p['prospect_id']}-attack-interest", task_id="", code="attack_interest",
                label="明確興趣或活動回應", display_value="曾有正面回應紀錄",
                source_type="prospect", source_id=p["prospect_id"], occurred_at=None,
                strength=EvidenceStrength.STRONG,
            ))

        why_now = "位於服務區、科別高度適配，且尚未接觸" if p["contact_stage"] == "uncontacted" \
            else "已初步接觸、曾有正面回應，適合把握時機約訪"

        candidates.append(Candidate(
            target_type=TargetType.PROSPECT, target_id=p["prospect_id"], target_name=p["name"],
            task_type=TaskType.ATTACK, raw_signal=raw_signal,
            raw_business_value={"high": 80, "medium": 50, "low": 20}[p["fit_band"]],
            urgency_score=50 if p["explicit_interest"] else 0,
            evidence_score=evidence_score, strategy_fit_score=100,
            action_mode=ActionMode.PHONE, estimated_minutes=20,
            objective="確認需求與合適拜訪時間", why_now=why_now,
            title=f"開發任務：{p['name']}", uncertainty_note="新客資料來源與新鮮度需業務確認可信度",
            evidence_strength=evidence_strength, evidences=evidences[:3],
            lat=p["lat"], lon=p["lon"],
            data_updated_at=datetime.combine(
                date.fromisoformat(p["source_updated_at"]) if isinstance(p["source_updated_at"], str) else p["source_updated_at"],
                datetime.min.time(),
            ),
            has_distance_data=p["lat"] is not None and p["lon"] is not None,
        ))

    return candidates
