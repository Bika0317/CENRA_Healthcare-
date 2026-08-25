"""
審核決策的服務層入口。刻意保持很薄：所有狀態機驗證與 transaction 寫入都已經在
data/task_repository.py::TaskRepository.apply_review() 裡完成（它直接呼叫
domain.transition()）。這裡不重新驗證一次規則，避免規則分散在兩個地方、
以後改一條規則要改兩處還可能漏改。
"""
from __future__ import annotations

from datetime import date

from domain.models import ActionMode, ReviewDecision, Task
from data.task_repository import TaskRepository


def submit_review(task_id: str, decision: ReviewDecision, *,
                   modified_objective: str | None, modified_action_mode: ActionMode | None,
                   reason_code: str, reason_note: str | None, deferred_to: date | None,
                   actor_rep_id: str, task_repo: TaskRepository) -> Task:
    """成功回傳更新後的 Task；不合法時讓 ValidationError / InvalidTransitionError
    原樣往上丟，由呼叫端（UI 層）接住並轉成欄位級錯誤訊息，不要在這裡吞掉。"""
    return task_repo.apply_review(
        task_id, decision,
        modified_objective=modified_objective, modified_action_mode=modified_action_mode,
        reason_code=reason_code, reason_note=reason_note, deferred_to=deferred_to,
        actor_rep_id=actor_rep_id,
    )
