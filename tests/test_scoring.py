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


def test_percentile_tie_gives_equal_scores_not_zero_and_hundred():
    a = make_candidate(target_id="A001", raw_signal=80, raw_business_value=80, urgency_score=100)
    b = make_candidate(target_id="A002", raw_signal=80, raw_business_value=80, urgency_score=100)
    tasks = score_candidates([a, b], "R100", DEMO_DATE)
    by_id = {t.target_id: t for t in tasks}
    assert by_id["A001"].signal_score == by_id["A002"].signal_score == 50.0
    assert by_id["A001"].business_value_score == by_id["A002"].business_value_score == 50.0


def test_percentile_three_way_tie_all_equal():
    candidates = [make_candidate(target_id=f"A00{i}", raw_signal=50, raw_business_value=50,
                                  urgency_score=100) for i in range(3)]
    tasks = score_candidates(candidates, "R100", DEMO_DATE)
    scores = {t.signal_score for t in tasks}
    assert scores == {50.0}


def test_cost_penalty_phone_is_two_regardless_of_distance():
    c = make_candidate(action_mode=ActionMode.PHONE, lat=30.0, lon=130.0, urgency_score=100)
    tasks = score_candidates([c], "R100", DEMO_DATE, rep_home_lat=25.0, rep_home_lon=121.0)
    assert tasks[0].cost_penalty == 2.0


def test_cost_penalty_missing_rep_home_falls_back_to_missing_distance_tier():
    c = make_candidate(urgency_score=100)
    tasks = score_candidates([c], "R100", DEMO_DATE, rep_home_lat=None, rep_home_lon=None)
    assert tasks[0].cost_penalty == 12.0


def test_cost_penalty_short_visit_distance_is_lowest_visit_tier():
    # 候選就在業務駐地旁邊，車程幾乎是 0 分鐘 -> <=30 分鐘那一級
    c = make_candidate(lat=25.001, lon=121.001, urgency_score=100)
    tasks = score_candidates([c], "R100", DEMO_DATE, rep_home_lat=25.0, rep_home_lon=121.0)
    assert tasks[0].cost_penalty == 6.0


def test_cost_penalty_long_visit_distance_is_highest_visit_tier():
    # 候選離業務駐地很遠（直線距離換算車程遠超過 60 分鐘）-> 最高一級
    c = make_candidate(lat=26.5, lon=122.5, urgency_score=100)
    tasks = score_candidates([c], "R100", DEMO_DATE, rep_home_lat=25.0, rep_home_lon=121.0)
    assert tasks[0].cost_penalty == 15.0
