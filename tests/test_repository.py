from datetime import date

import pytest

from domain.models import ActionMode, ExecutionStatus, OutcomeType, ReviewDecision, ValidationError
from tests.conftest import make_task


def test_save_tasks_is_idempotent(task_repo):
    t = make_task()
    inserted1 = task_repo.save_tasks([t])
    inserted2 = task_repo.save_tasks([t])  # 同一個 generation_key 再存一次
    assert inserted1 == 1
    assert inserted2 == 0
    assert len(task_repo.get_candidate_tasks("R100", t.task_date)) == 1


def test_save_tasks_persists_evidence(task_repo):
    t = make_task()
    task_repo.save_tasks([t])
    loaded = task_repo.get_task(t.task_id)
    assert len(loaded.evidences) == 1
    assert loaded.evidences[0].code == "defend_revenue_decline"


def test_apply_review_accept_updates_status(task_repo):
    t = make_task()
    task_repo.save_tasks([t])
    updated = task_repo.apply_review(
        t.task_id, ReviewDecision.ACCEPT, modified_objective=None, modified_action_mode=None,
        reason_code="", reason_note=None, deferred_to=None, actor_rep_id="R100",
    )
    assert updated.status.value == "accepted"
    reloaded = task_repo.get_task(t.task_id)
    assert reloaded.status.value == "accepted"


def test_apply_review_modify_requires_change(task_repo):
    t = make_task()
    task_repo.save_tasks([t])
    with pytest.raises(ValidationError):
        task_repo.apply_review(
            t.task_id, ReviewDecision.MODIFY, modified_objective=t.objective,
            modified_action_mode=t.action_mode, reason_code="prefer_phone_first",
            reason_note=None, deferred_to=None, actor_rep_id="R100",
        )
    # 失敗後任務狀態不應被改動
    assert task_repo.get_task(t.task_id).status.value == "candidate"


def test_apply_review_defer_requires_date(task_repo):
    t = make_task()
    task_repo.save_tasks([t])
    with pytest.raises(ValidationError):
        task_repo.apply_review(
            t.task_id, ReviewDecision.DEFER, modified_objective=None, modified_action_mode=None,
            reason_code="wrong_timing", reason_note=None, deferred_to=None, actor_rep_id="R100",
        )
    assert task_repo.get_task(t.task_id).status.value == "candidate"


def test_apply_review_reject_requires_reason(task_repo):
    t = make_task()
    task_repo.save_tasks([t])
    with pytest.raises(ValidationError):
        task_repo.apply_review(
            t.task_id, ReviewDecision.REJECT, modified_objective=None, modified_action_mode=None,
            reason_code="", reason_note=None, deferred_to=None, actor_rep_id="R100",
        )


def test_full_journey_accept_schedule_complete(task_repo):
    t = make_task()
    task_repo.save_tasks([t])
    task_repo.apply_review(
        t.task_id, ReviewDecision.MODIFY, modified_objective="確認庫存並電話跟進",
        modified_action_mode=ActionMode.PHONE, reason_code="prefer_phone_first",
        reason_note=None, deferred_to=None, actor_rep_id="R100",
    )
    scheduled = task_repo.mark_scheduled(t.task_id)
    assert scheduled.status.value == "scheduled"
    assert scheduled.action_mode == ActionMode.PHONE

    completed = task_repo.apply_outcome(
        t.task_id, ExecutionStatus.COMPLETED, OutcomeType.DEMAND_CONFIRMED,
        note="客戶確認下一批訂單", next_step="安排補貨", next_date=date(2026, 9, 1),
        actor_rep_id="R100",
    )
    assert completed.status.value == "completed"
    reloaded = task_repo.get_task(t.task_id)
    assert reloaded.status.value == "completed"


def test_outcome_completed_requires_outcome_type(task_repo):
    t = make_task()
    task_repo.save_tasks([t])
    task_repo.apply_review(
        t.task_id, ReviewDecision.ACCEPT, modified_objective=None, modified_action_mode=None,
        reason_code="", reason_note=None, deferred_to=None, actor_rep_id="R100",
    )
    task_repo.mark_scheduled(t.task_id)
    with pytest.raises(ValidationError):
        task_repo.apply_outcome(
            t.task_id, ExecutionStatus.COMPLETED, None, note=None,
            next_step=None, next_date=None, actor_rep_id="R100",
        )


def test_reset_demo_clears_all(task_repo):
    t = make_task()
    task_repo.save_tasks([t])
    task_repo.reset_demo()
    assert task_repo.get_candidate_tasks("R100", t.task_date) == []


def test_fixture_repository_loads_and_validates(fixture_repo):
    assert len(fixture_repo.get_reps()) == 3
    r100_accounts = fixture_repo.get_accounts("R100")
    assert len(r100_accounts) == 10
    r100_prospects = fixture_repo.get_prospects("R100")
    assert len(r100_prospects) == 5
