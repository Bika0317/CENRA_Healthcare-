"""
覆蓋「需要後續追蹤」到期後轉候選任務的行為（services/followup_service.py）。
"""
from __future__ import annotations

from datetime import timedelta

from domain.models import ExecutionStatus, OutcomeType, ReviewDecision, TaskStatus
from services.daily_plan_service import build_daily_plan
from services.followup_service import generate_followup_tasks, has_been_converted
from services.review_service import submit_review


def _complete_first_suggested_task_with_followup(demo_date, fixture_repo, task_repo, next_date):
    plan = build_daily_plan("L100", demo_date, 240, fixture_repo, task_repo)
    t = plan.suggested_tasks[0]
    submit_review(
        t.task_id, ReviewDecision.ACCEPT, modified_objective=None, modified_action_mode=None,
        reason_code="", reason_note=None, deferred_to=None, actor_rep_id="L100", task_repo=task_repo,
    )
    task_repo.mark_scheduled(t.task_id)
    task_repo.apply_outcome(
        t.task_id, ExecutionStatus.COMPLETED, OutcomeType.FOLLOW_UP_BOOKED,
        note=None, next_step="確認下一批訂單需求", next_date=next_date, actor_rep_id="L100",
    )
    return t


def test_followup_not_yet_due_generates_nothing(demo_date, fixture_repo, task_repo):
    future_date = demo_date + timedelta(days=5)
    _complete_first_suggested_task_with_followup(demo_date, fixture_repo, task_repo, future_date)

    followup_tasks = generate_followup_tasks(task_repo, "L100", demo_date)
    assert followup_tasks == []


def test_followup_due_today_generates_one_candidate_task(demo_date, fixture_repo, task_repo):
    original = _complete_first_suggested_task_with_followup(demo_date, fixture_repo, task_repo, demo_date)

    followup_tasks = generate_followup_tasks(task_repo, "L100", demo_date)
    assert len(followup_tasks) == 1
    new_task = followup_tasks[0]
    assert new_task.status == TaskStatus.CANDIDATE
    assert new_task.target_id == original.target_id
    assert new_task.task_type == original.task_type
    assert new_task.objective == "確認下一批訂單需求"


def test_followup_appears_in_next_days_daily_plan_and_is_idempotent(demo_date, fixture_repo, task_repo):
    original = _complete_first_suggested_task_with_followup(demo_date, fixture_repo, task_repo, demo_date)

    plan_today = build_daily_plan("L100", demo_date, 240, fixture_repo, task_repo)
    matching = [t for t in plan_today.candidate_tasks if t.target_id == original.target_id
                and t.status == TaskStatus.CANDIDATE and t.task_id != original.task_id]
    assert len(matching) == 1
    assert has_been_converted(task_repo, original.task_id)

    # 明天再重算一次，同一筆後續追蹤不會重複轉成第二張任務（generation_key idempotent）。
    tomorrow = demo_date + timedelta(days=1)
    plan_tomorrow = build_daily_plan("L100", tomorrow, 240, fixture_repo, task_repo)
    followup_like = [t for t in plan_tomorrow.candidate_tasks if t.model_version == "followup-v1"]
    assert len(followup_like) == 1


def test_overdue_followup_still_generates_a_task(demo_date, fixture_repo, task_repo):
    past_date = demo_date - timedelta(days=3)
    _complete_first_suggested_task_with_followup(demo_date, fixture_repo, task_repo, past_date)

    followup_tasks = generate_followup_tasks(task_repo, "L100", demo_date)
    assert len(followup_tasks) == 1
