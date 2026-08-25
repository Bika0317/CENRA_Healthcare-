"""覆蓋 SPEC §7.5 / §16.3 的審核與結果狀態機規則，透過 review_service / outcome_service。"""
from __future__ import annotations

import pytest

from domain.models import (
    ActionMode, ExecutionStatus, InvalidTransitionError, OutcomeType,
    ReviewDecision, TaskStatus, ValidationError,
)
from services.outcome_service import submit_outcome
from services.review_service import submit_review

from .conftest import make_task


def _save(task_repo, task):
    task_repo.save_tasks([task])
    return task


def test_accept_moves_candidate_to_accepted(task_repo, demo_date):
    task = _save(task_repo, make_task(task_id="T-1", generation_key="G-1"))
    updated = submit_review(
        "T-1", ReviewDecision.ACCEPT, modified_objective=None, modified_action_mode=None,
        reason_code="accept_as_is", reason_note=None, deferred_to=None,
        actor_rep_id="L100", task_repo=task_repo,
    )
    assert updated.status == TaskStatus.ACCEPTED
    assert task_repo.get_task("T-1").status == TaskStatus.ACCEPTED


def test_modify_requires_at_least_one_real_change(task_repo, demo_date):
    task = _save(task_repo, make_task(task_id="T-2", generation_key="G-2"))
    with pytest.raises(ValidationError):
        submit_review(
            "T-2", ReviewDecision.MODIFY,
            modified_objective=task.objective, modified_action_mode=task.action_mode,
            reason_code="scope_change", reason_note=None, deferred_to=None,
            actor_rep_id="L100", task_repo=task_repo,
        )
    # 驗證失敗不部分寫入：狀態仍是 candidate
    assert task_repo.get_task("T-2").status == TaskStatus.CANDIDATE


def test_modify_with_real_change_succeeds(task_repo, demo_date):
    _save(task_repo, make_task(task_id="T-3", generation_key="G-3", action_mode=ActionMode.VISIT))
    updated = submit_review(
        "T-3", ReviewDecision.MODIFY,
        modified_objective=None, modified_action_mode=ActionMode.PHONE,
        reason_code="scope_change", reason_note="改電話約訪即可", deferred_to=None,
        actor_rep_id="L100", task_repo=task_repo,
    )
    assert updated.status == TaskStatus.MODIFIED
    assert updated.action_mode == ActionMode.PHONE


def test_defer_without_date_is_rejected(task_repo, demo_date):
    _save(task_repo, make_task(task_id="T-4", generation_key="G-4"))
    with pytest.raises(ValidationError):
        submit_review(
            "T-4", ReviewDecision.DEFER, modified_objective=None, modified_action_mode=None,
            reason_code="not_now", reason_note=None, deferred_to=None,
            actor_rep_id="L100", task_repo=task_repo,
        )
    assert task_repo.get_task("T-4").status == TaskStatus.CANDIDATE


def test_defer_with_date_succeeds(task_repo, demo_date):
    from datetime import timedelta
    _save(task_repo, make_task(task_id="T-5", generation_key="G-5"))
    updated = submit_review(
        "T-5", ReviewDecision.DEFER, modified_objective=None, modified_action_mode=None,
        reason_code="not_now", reason_note=None, deferred_to=demo_date + timedelta(days=3),
        actor_rep_id="L100", task_repo=task_repo,
    )
    assert updated.status == TaskStatus.DEFERRED


def test_reject_without_reason_code_is_rejected(task_repo, demo_date):
    _save(task_repo, make_task(task_id="T-6", generation_key="G-6"))
    with pytest.raises(ValidationError):
        submit_review(
            "T-6", ReviewDecision.REJECT, modified_objective=None, modified_action_mode=None,
            reason_code="", reason_note=None, deferred_to=None,
            actor_rep_id="L100", task_repo=task_repo,
        )
    assert task_repo.get_task("T-6").status == TaskStatus.CANDIDATE


def test_reject_with_reason_code_succeeds(task_repo, demo_date):
    _save(task_repo, make_task(task_id="T-7", generation_key="G-7"))
    updated = submit_review(
        "T-7", ReviewDecision.REJECT, modified_objective=None, modified_action_mode=None,
        reason_code="not_relevant", reason_note="非本次責任範圍", deferred_to=None,
        actor_rep_id="L100", task_repo=task_repo,
    )
    assert updated.status == TaskStatus.REJECTED


def test_cannot_review_a_task_twice(task_repo, demo_date):
    _save(task_repo, make_task(task_id="T-8", generation_key="G-8"))
    submit_review(
        "T-8", ReviewDecision.ACCEPT, modified_objective=None, modified_action_mode=None,
        reason_code="accept_as_is", reason_note=None, deferred_to=None,
        actor_rep_id="L100", task_repo=task_repo,
    )
    with pytest.raises(InvalidTransitionError):
        submit_review(
            "T-8", ReviewDecision.REJECT, modified_objective=None, modified_action_mode=None,
            reason_code="not_relevant", reason_note=None, deferred_to=None,
            actor_rep_id="L100", task_repo=task_repo,
        )


def test_only_accepted_or_modified_can_be_scheduled(task_repo, demo_date):
    _save(task_repo, make_task(task_id="T-9", generation_key="G-9"))
    with pytest.raises(InvalidTransitionError):
        task_repo.mark_scheduled("T-9")  # 仍是 candidate，不能直接排程


def test_accepted_task_can_be_scheduled(task_repo, demo_date):
    _save(task_repo, make_task(task_id="T-10", generation_key="G-10"))
    submit_review(
        "T-10", ReviewDecision.ACCEPT, modified_objective=None, modified_action_mode=None,
        reason_code="accept_as_is", reason_note=None, deferred_to=None,
        actor_rep_id="L100", task_repo=task_repo,
    )
    updated = task_repo.mark_scheduled("T-10")
    assert updated.status == TaskStatus.SCHEDULED


def test_completed_requires_outcome_type(task_repo, demo_date):
    _save(task_repo, make_task(task_id="T-11", generation_key="G-11"))
    submit_review(
        "T-11", ReviewDecision.ACCEPT, modified_objective=None, modified_action_mode=None,
        reason_code="accept_as_is", reason_note=None, deferred_to=None,
        actor_rep_id="L100", task_repo=task_repo,
    )
    task_repo.mark_scheduled("T-11")
    with pytest.raises(ValidationError):
        submit_outcome(
            "T-11", ExecutionStatus.COMPLETED, outcome_type=None, note=None,
            next_step=None, next_date=None, actor_rep_id="L100", task_repo=task_repo,
        )
    assert task_repo.get_task("T-11").status == TaskStatus.SCHEDULED


def test_completed_with_outcome_type_succeeds(task_repo, demo_date):
    _save(task_repo, make_task(task_id="T-12", generation_key="G-12"))
    submit_review(
        "T-12", ReviewDecision.ACCEPT, modified_objective=None, modified_action_mode=None,
        reason_code="accept_as_is", reason_note=None, deferred_to=None,
        actor_rep_id="L100", task_repo=task_repo,
    )
    task_repo.mark_scheduled("T-12")
    updated = submit_outcome(
        "T-12", ExecutionStatus.COMPLETED, outcome_type=OutcomeType.DEMAND_CONFIRMED,
        note="確認有需求", next_step=None, next_date=None,
        actor_rep_id="L100", task_repo=task_repo,
    )
    assert updated.status == TaskStatus.COMPLETED
    outcome = task_repo.get_outcome("T-12")
    assert outcome.outcome_type == OutcomeType.DEMAND_CONFIRMED


def test_not_completed_does_not_require_outcome_type(task_repo, demo_date):
    _save(task_repo, make_task(task_id="T-13", generation_key="G-13"))
    submit_review(
        "T-13", ReviewDecision.ACCEPT, modified_objective=None, modified_action_mode=None,
        reason_code="accept_as_is", reason_note=None, deferred_to=None,
        actor_rep_id="L100", task_repo=task_repo,
    )
    task_repo.mark_scheduled("T-13")
    updated = submit_outcome(
        "T-13", ExecutionStatus.NOT_COMPLETED, outcome_type=None, note="診所臨時休診",
        next_step="改約下週", next_date=None, actor_rep_id="L100", task_repo=task_repo,
    )
    assert updated.status == TaskStatus.NOT_COMPLETED


def test_cannot_report_outcome_before_scheduled(task_repo, demo_date):
    _save(task_repo, make_task(task_id="T-14", generation_key="G-14"))
    with pytest.raises(InvalidTransitionError):
        submit_outcome(
            "T-14", ExecutionStatus.COMPLETED, outcome_type=OutcomeType.OTHER, note=None,
            next_step=None, next_date=None, actor_rep_id="L100", task_repo=task_repo,
        )


def test_state_persists_after_reload(task_repo, demo_date):
    _save(task_repo, make_task(task_id="T-15", generation_key="G-15"))
    submit_review(
        "T-15", ReviewDecision.ACCEPT, modified_objective=None, modified_action_mode=None,
        reason_code="accept_as_is", reason_note=None, deferred_to=None,
        actor_rep_id="L100", task_repo=task_repo,
    )
    reloaded = task_repo.get_task("T-15")  # 模擬「重新整理頁面」重新查一次
    assert reloaded.status == TaskStatus.ACCEPTED
