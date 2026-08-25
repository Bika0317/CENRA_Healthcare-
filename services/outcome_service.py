"""
結果回報的服務層入口。跟 review_service.py 一樣刻意保持很薄：驗證與 transaction
寫入都在 data/task_repository.py::TaskRepository.apply_outcome() 裡完成。
"""
from __future__ import annotations

from datetime import date

from domain.models import ExecutionStatus, OutcomeType, Task
from data.task_repository import TaskRepository


def submit_outcome(task_id: str, execution_status: ExecutionStatus, *,
                    outcome_type: OutcomeType | None, note: str | None,
                    next_step: str | None, next_date: date | None,
                    actor_rep_id: str, task_repo: TaskRepository) -> Task:
    """成功回傳更新後的 Task；不合法時讓 ValidationError / InvalidTransitionError
    原樣往上丟，由呼叫端（UI 層）接住並轉成欄位級錯誤訊息。"""
    return task_repo.apply_outcome(
        task_id, execution_status,
        outcome_type=outcome_type, note=note,
        next_step=next_step, next_date=next_date,
        actor_rep_id=actor_rep_id,
    )
