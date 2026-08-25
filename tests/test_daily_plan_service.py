"""覆蓋 SPEC AC-01/AC-06 與 daily_plan_service 的 idempotent／容量／點位順序行為。"""
from __future__ import annotations

from domain.models import ActionMode, TaskType
from services.daily_plan_service import build_daily_plan


def test_ac01_main_demo_rep_generates_exactly_eight_with_min_split(demo_date, fixture_repo, task_repo):
    plan = build_daily_plan("R100", demo_date, 240, fixture_repo, task_repo)
    assert len(plan.candidate_tasks) == 8
    counts = {tt: 0 for tt in TaskType}
    for t in plan.candidate_tasks:
        counts[t.task_type] += 1
    assert counts[TaskType.ATTACK] >= 2
    assert counts[TaskType.DEFEND] >= 3
    assert counts[TaskType.GROW] >= 3


def test_two_fixed_appointments_reduce_available_capacity(demo_date, fixture_repo, task_repo):
    plan = build_daily_plan("R100", demo_date, 240, fixture_repo, task_repo)
    assert len(plan.fixed_appointments) == 2
    fixed_minutes = sum(ap.duration_minutes for ap in plan.fixed_appointments)
    suggested_minutes = sum(t.estimated_minutes for t in plan.suggested_tasks)
    assert fixed_minutes + suggested_minutes + plan.remaining_minutes == 240


def test_suggested_tasks_never_exceed_available_capacity(demo_date, fixture_repo, task_repo):
    plan = build_daily_plan("R100", demo_date, 240, fixture_repo, task_repo)
    assert plan.remaining_minutes >= 0


def test_generation_is_idempotent_across_repeated_calls(demo_date, fixture_repo, task_repo):
    plan1 = build_daily_plan("R100", demo_date, 240, fixture_repo, task_repo)
    plan2 = build_daily_plan("R100", demo_date, 240, fixture_repo, task_repo)
    assert len(plan1.candidate_tasks) == len(plan2.candidate_tasks)
    assert {t.task_id for t in plan1.candidate_tasks} == {t.task_id for t in plan2.candidate_tasks}


def test_visit_sequence_excludes_phone_tasks(demo_date, fixture_repo, task_repo):
    plan = build_daily_plan("R100", demo_date, 240, fixture_repo, task_repo)
    phone_ids = {t.task_id for t in plan.suggested_tasks if t.action_mode == ActionMode.PHONE}
    visit_ids = {t.task_id for t in plan.visit_sequence}
    assert phone_ids.isdisjoint(visit_ids)


def test_low_available_minutes_still_produces_valid_plan(demo_date, fixture_repo, task_repo):
    plan = build_daily_plan("R100", demo_date, 60, fixture_repo, task_repo)
    assert plan.remaining_minutes >= 0
    total = sum(t.estimated_minutes for t in plan.suggested_tasks)
    fixed_minutes = sum(ap.duration_minutes for ap in plan.fixed_appointments)
    assert total <= max(60 - fixed_minutes, 0)
