"""覆蓋 services/ranking_model_service.py 的示範性學習排序層：樣本不足不訓練、
樣本充足且有兩種決定時才給出模型參考分數，且不影響任何既有分數欄位。"""
from __future__ import annotations

from domain.models import ReviewDecision
from services.daily_plan_service import build_daily_plan
from services.ranking_model_service import (
    MIN_TRAINING_SAMPLES, score_tasks_with_reference_model, train_reference_model,
)
from services.review_service import submit_review


def _seed_reviews(task_repo, tasks, n_accept: int, n_reject: int, reason_code: str = "wrong_timing"):
    i = 0
    for _ in range(n_accept):
        submit_review(
            tasks[i].task_id, ReviewDecision.ACCEPT, modified_objective=None, modified_action_mode=None,
            reason_code="", reason_note=None, deferred_to=None, actor_rep_id="L100", task_repo=task_repo,
        )
        i += 1
    for _ in range(n_reject):
        submit_review(
            tasks[i].task_id, ReviewDecision.REJECT, modified_objective=None, modified_action_mode=None,
            reason_code=reason_code, reason_note=None, deferred_to=None, actor_rep_id="L100", task_repo=task_repo,
        )
        i += 1


def test_insufficient_samples_returns_none(demo_date, fixture_repo, task_repo):
    plan = build_daily_plan("L100", demo_date, 240, fixture_repo, task_repo)
    _seed_reviews(task_repo, plan.candidate_tasks, n_accept=2, n_reject=1)

    assert train_reference_model(task_repo) is None
    assert score_tasks_with_reference_model(task_repo, plan.candidate_tasks) is None


def test_single_class_labels_returns_none_even_above_sample_threshold(demo_date, fixture_repo, task_repo):
    """跨三位業務湊到 MIN_TRAINING_SAMPLES 以上，但全部都是同一種決定（全部採納）：
    LogisticRegression 需要至少兩個類別才能訓練，這裡要回傳 None，不能拋例外。"""
    for rep_id in ("L100", "L101", "L102"):
        plan = build_daily_plan(rep_id, demo_date, 240, fixture_repo, task_repo)
        _seed_reviews(task_repo, plan.candidate_tasks, n_accept=len(plan.candidate_tasks), n_reject=0)

    assert train_reference_model(task_repo) is None


def test_sufficient_mixed_samples_trains_and_scores(demo_date, fixture_repo, task_repo):
    """跨三位業務累積到門檻以上、且有採納也有拒絕，才會真的訓練出模型並給分數。"""
    for rep_id in ("L100", "L101", "L102"):
        plan = build_daily_plan(rep_id, demo_date, 240, fixture_repo, task_repo)
        half = len(plan.candidate_tasks) // 2
        _seed_reviews(task_repo, plan.candidate_tasks, n_accept=half, n_reject=len(plan.candidate_tasks) - half)

    result = train_reference_model(task_repo)
    assert result is not None
    _, n_samples = result
    assert n_samples >= MIN_TRAINING_SAMPLES

    plan = build_daily_plan("L100", demo_date, 240, fixture_repo, task_repo)
    scored = score_tasks_with_reference_model(task_repo, plan.candidate_tasks)
    assert scored is not None
    scores, n = scored
    assert n == n_samples
    assert set(scores.keys()) == {t.task_id for t in plan.candidate_tasks}
    assert all(0.0 <= v <= 100.0 for v in scores.values())
