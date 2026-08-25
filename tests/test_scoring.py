"""覆蓋 SPEC §11 統一評分公式：百分位、門檻、clamp、tie-break。"""
from __future__ import annotations

from datetime import date, datetime

from domain.models import ActionMode, EvidenceStrength, TargetType, TaskStatus, TaskType
from engines.candidate import Candidate
from services.scoring import EVIDENCE_SCORE_THRESHOLD, VALUE_SCORE_THRESHOLD, score_candidates

DEMO_DATE = date(2026, 8, 25)


def make_candidate(**overrides) -> Candidate:
    defaults = dict(
        target_type=TargetType.ACCOUNT, target_id="A999", target_name="測試診所",
        task_type=TaskType.DEFEND, raw_signal=80.0, raw_business_value=80.0,
        urgency_score=50.0, evidence_score=70.0, strategy_fit_score=100.0,
        action_mode=ActionMode.VISIT, estimated_minutes=45,
        objective="確認狀況", why_now="測試", title="測試任務",
        uncertainty_note="原因需業務確認", evidence_strength=EvidenceStrength.MEDIUM,
        evidences=[], lat=25.03, lon=121.56,
        data_updated_at=datetime(2026, 8, 24, 9, 0), has_distance_data=True,
    )
    defaults.update(overrides)
    return Candidate(**defaults)


def test_single_candidate_percentile_is_seventy_not_hundred():
    tasks = score_candidates([make_candidate(evidence_score=100, urgency_score=100)], "R100", DEMO_DATE)
    assert len(tasks) == 1
    assert tasks[0].signal_score == 70.0
    assert tasks[0].business_value_score == 70.0


def test_value_score_below_threshold_is_excluded():
    weak = make_candidate(raw_signal=0, raw_business_value=0, urgency_score=0,
                           evidence_score=40, strategy_fit_score=0)
    tasks = score_candidates([weak], "R100", DEMO_DATE)
    assert tasks == []  # 單一候選 percentile=70，但其餘維度全 0，算出的分數必然低於門檻


def test_evidence_score_below_threshold_is_excluded_even_if_value_high():
    candidate = make_candidate(evidence_score=EVIDENCE_SCORE_THRESHOLD - 1, raw_signal=100,
                                raw_business_value=100, urgency_score=100, strategy_fit_score=100)
    tasks = score_candidates([candidate], "R100", DEMO_DATE)
    assert tasks == []


def test_value_score_clamped_between_0_and_100():
    strong = make_candidate(raw_signal=100, raw_business_value=100, urgency_score=100,
                             evidence_score=100, strategy_fit_score=100, action_mode=ActionMode.PHONE)
    tasks = score_candidates([strong], "R100", DEMO_DATE)
    assert 0 <= tasks[0].value_score <= 100


def test_percentile_only_compares_within_same_task_type():
    attack_c = make_candidate(target_id="P001", task_type=TaskType.ATTACK, raw_signal=100,
                               raw_business_value=100, target_type=TargetType.PROSPECT)
    defend_c = make_candidate(target_id="A001", task_type=TaskType.DEFEND, raw_signal=10,
                               raw_business_value=10)
    tasks = score_candidates([attack_c, defend_c], "R100", DEMO_DATE)
    by_id = {t.target_id: t for t in tasks}
    # 各自獨立批次內都是唯一候選，因此都應套用單一候選 70 規則，而不是互相比較
    assert by_id["P001"].signal_score == 70.0
    assert by_id["A001"].signal_score == 70.0


def test_generated_tasks_use_candidate_status_and_are_sorted_desc():
    strong = make_candidate(target_id="A001", raw_signal=100, raw_business_value=100, urgency_score=100)
    weak = make_candidate(target_id="A002", raw_signal=100, raw_business_value=100, urgency_score=100,
                           evidence_score=40)
    tasks = score_candidates([strong, weak], "R100", DEMO_DATE)
    assert all(t.status == TaskStatus.CANDIDATE for t in tasks)
    assert tasks == sorted(tasks, key=lambda t: t.value_score, reverse=True)


def test_task_id_and_generation_key_are_deterministic():
    c = make_candidate()
    tasks1 = score_candidates([c], "R100", DEMO_DATE)
    tasks2 = score_candidates([make_candidate()], "R100", DEMO_DATE)
    assert tasks1[0].task_id == tasks2[0].task_id
    assert tasks1[0].generation_key == tasks2[0].generation_key
