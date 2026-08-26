"""覆蓋 SPEC AC-01/AC-06 與 daily_plan_service 的 idempotent／容量／點位順序行為。"""
from __future__ import annotations

from datetime import timedelta

from domain.models import ActionMode, ExecutionStatus, OutcomeType, ReviewDecision, TaskType
from services.daily_plan_service import build_daily_plan
from services.review_service import submit_review


def test_ac01_main_demo_rep_generates_exactly_eight_with_min_split(demo_date, fixture_repo, task_repo):
    plan = build_daily_plan("L100", demo_date, 240, fixture_repo, task_repo)
    assert len(plan.candidate_tasks) == 8
    counts = {tt: 0 for tt in TaskType}
    for t in plan.candidate_tasks:
        counts[t.task_type] += 1
    assert counts[TaskType.ATTACK] >= 2
    assert counts[TaskType.DEFEND] >= 3
    assert counts[TaskType.GROW] >= 3


def test_two_fixed_appointments_reduce_available_capacity(demo_date, fixture_repo, task_repo):
    plan = build_daily_plan("L100", demo_date, 240, fixture_repo, task_repo)
    assert len(plan.fixed_appointments) == 2
    fixed_minutes = sum(ap.duration_minutes for ap in plan.fixed_appointments)
    suggested_minutes = sum(t.estimated_minutes for t in plan.suggested_tasks)
    assert fixed_minutes + suggested_minutes + plan.remaining_minutes == 240


def test_suggested_tasks_never_exceed_available_capacity(demo_date, fixture_repo, task_repo):
    plan = build_daily_plan("L100", demo_date, 240, fixture_repo, task_repo)
    assert plan.remaining_minutes >= 0


def test_generation_is_idempotent_across_repeated_calls(demo_date, fixture_repo, task_repo):
    plan1 = build_daily_plan("L100", demo_date, 240, fixture_repo, task_repo)
    plan2 = build_daily_plan("L100", demo_date, 240, fixture_repo, task_repo)
    assert len(plan1.candidate_tasks) == len(plan2.candidate_tasks)
    assert {t.task_id for t in plan1.candidate_tasks} == {t.task_id for t in plan2.candidate_tasks}


def test_visit_sequence_excludes_phone_tasks(demo_date, fixture_repo, task_repo):
    plan = build_daily_plan("L100", demo_date, 240, fixture_repo, task_repo)
    phone_ids = {t.task_id for t in plan.suggested_tasks if t.action_mode == ActionMode.PHONE}
    visit_ids = {t.task_id for t in plan.visit_sequence}
    assert phone_ids.isdisjoint(visit_ids)


def test_low_available_minutes_still_produces_valid_plan(demo_date, fixture_repo, task_repo):
    plan = build_daily_plan("L100", demo_date, 60, fixture_repo, task_repo)
    assert plan.remaining_minutes >= 0
    total = sum(t.estimated_minutes for t in plan.suggested_tasks)
    fixed_minutes = sum(ap.duration_minutes for ap in plan.fixed_appointments)
    assert total <= max(60 - fixed_minutes, 0)


def test_completing_a_suggested_task_shrinks_suggested_count_without_backfill(
    demo_date, fixture_repo, task_repo,
):
    """
    使用者實測回報的行為：建議 3～4 張、完成其中 1 張後，剩下的建議張數應該
    跟著減少，不該因為完成的任務讓出分鐘數，就被 allocate_daily_capacity()
    遞補一張全新候選進來、讓總張數維持不變甚至變多。
    """
    plan = build_daily_plan("L100", demo_date, 240, fixture_repo, task_repo)
    before_count = len(plan.suggested_tasks)
    assert before_count >= 1

    t = plan.suggested_tasks[0]
    task_repo.apply_review(
        t.task_id, ReviewDecision.ACCEPT, modified_objective=None, modified_action_mode=None,
        reason_code="", reason_note=None, deferred_to=None, actor_rep_id="L100",
    )
    task_repo.mark_scheduled(t.task_id)
    task_repo.apply_outcome(
        t.task_id, ExecutionStatus.COMPLETED, OutcomeType.DEMAND_CONFIRMED,
        note=None, next_step=None, next_date=None, actor_rep_id="L100",
    )

    plan2 = build_daily_plan("L100", demo_date, 240, fixture_repo, task_repo)
    assert len(plan2.suggested_tasks) == before_count - 1
    assert t.task_id not in {task.task_id for task in plan2.suggested_tasks}


def test_building_a_second_days_plan_does_not_crash_on_evidence_id_collision(
    demo_date, fixture_repo, task_repo,
):
    """
    引擎產生的 evidence_id 只由帳戶/規則代碼組成（不含日期），task_evidence.evidence_id
    又是全表 PRIMARY KEY——同一帳戶在不同天觸發同一條規則會撞到同一個 evidence_id，
    在「延後任務隔天回到候選」這條路徑上幾乎必定發生（延後任務會讓 build_daily_plan()
    在另一天被呼叫，重新對同一批帳戶跑一次引擎）。這裡直接重現「延後到明天」再對明天
    呼叫 build_daily_plan() 的路徑，確認不會丟出 IntegrityError。
    """
    plan = build_daily_plan("L100", demo_date, 240, fixture_repo, task_repo)
    t = plan.suggested_tasks[0]
    tomorrow = demo_date + timedelta(days=1)
    submit_review(
        t.task_id, ReviewDecision.DEFER, modified_objective=None, modified_action_mode=None,
        reason_code="needs_more_time", reason_note=None, deferred_to=tomorrow,
        actor_rep_id="L100", task_repo=task_repo,
    )
    plan_tomorrow = build_daily_plan("L100", tomorrow, 240, fixture_repo, task_repo)
    resurfaced = [x for x in plan_tomorrow.candidate_tasks if x.task_id == t.task_id]
    assert resurfaced and resurfaced[0].status.value == "candidate"
