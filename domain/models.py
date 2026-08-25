"""
CENRA Mission 領域物件與狀態機規則。
所有型別定義以 docs/cenra_mission/00_CONTRACTS.md 為準——B、C 兩條軌道都直接
import 這個檔案，不要各自定義自己的 Task/Review 形狀。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class TargetType(str, Enum):
    ACCOUNT = "account"
    PROSPECT = "prospect"


class TaskType(str, Enum):
    ATTACK = "attack"   # 攻
    DEFEND = "defend"   # 守
    GROW = "grow"       # 增


class ActionMode(str, Enum):
    PHONE = "phone"
    VISIT = "visit"


class EvidenceStrength(str, Enum):
    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"


class TaskStatus(str, Enum):
    CANDIDATE = "candidate"
    ACCEPTED = "accepted"
    MODIFIED = "modified"
    DEFERRED = "deferred"
    REJECTED = "rejected"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    NOT_COMPLETED = "not_completed"
    CANCELLED = "cancelled"


class ReviewDecision(str, Enum):
    ACCEPT = "accept"
    MODIFY = "modify"
    DEFER = "defer"
    REJECT = "reject"


class ExecutionStatus(str, Enum):
    COMPLETED = "completed"
    NOT_COMPLETED = "not_completed"
    CANCELLED = "cancelled"


class OutcomeType(str, Enum):
    DEMAND_CONFIRMED = "demand_confirmed"
    REPLENISHMENT = "replenishment"
    FOLLOW_UP_BOOKED = "follow_up_booked"
    NO_OPPORTUNITY = "no_opportunity"
    DATA_ERROR = "data_error"
    SERVICE_RESOLVED = "service_resolved"
    OTHER = "other"


class ValidationError(Exception):
    """審核/結果表單缺必填欄位時丟出。"""


class InvalidTransitionError(Exception):
    """任務狀態不允許這種轉移時丟出。"""


@dataclass
class Evidence:
    evidence_id: str
    task_id: str
    code: str
    label: str
    display_value: str
    source_type: str
    source_id: str | None
    occurred_at: datetime | None
    strength: EvidenceStrength


@dataclass
class Task:
    task_id: str
    generation_key: str
    generated_at: datetime
    task_date: date
    rep_id: str
    target_type: TargetType
    target_id: str
    target_name: str
    task_type: TaskType
    title: str
    why_now: str
    objective: str
    action_mode: ActionMode
    estimated_minutes: int
    signal_score: float
    business_value_score: float
    urgency_score: float
    evidence_score: float
    strategy_fit_score: float
    cost_penalty: float
    value_score: float
    evidence_strength: EvidenceStrength
    uncertainty_note: str
    data_updated_at: datetime
    lat: float | None = None
    lon: float | None = None
    model_version: str = "rules-v1"
    status: TaskStatus = TaskStatus.CANDIDATE
    evidences: list[Evidence] = field(default_factory=list)


@dataclass
class TaskReview:
    review_id: str
    task_id: str
    decision: ReviewDecision
    original_objective: str
    modified_objective: str | None
    original_action_mode: ActionMode
    modified_action_mode: ActionMode | None
    reason_code: str
    reason_note: str | None
    deferred_to: date | None
    actor_rep_id: str
    created_at: datetime


@dataclass
class TaskOutcome:
    outcome_id: str
    task_id: str
    execution_status: ExecutionStatus
    outcome_type: OutcomeType | None
    note: str | None
    next_step: str | None
    next_date: date | None
    completed_at: datetime
    actor_rep_id: str


@dataclass
class FixedAppointment:
    appointment_id: str
    rep_id: str
    target_id: str
    target_name: str
    appointment_date: date
    start_time: str
    duration_minutes: int
    action_mode: ActionMode
    purpose: str
    status: str
    lat: float | None = None
    lon: float | None = None


@dataclass
class DailyPlan:
    rep_id: str
    plan_date: date
    available_minutes: int
    fixed_appointments: list[FixedAppointment]
    candidate_tasks: list[Task]
    suggested_tasks: list[Task]
    remaining_minutes: int
    visit_sequence: list[Task]


# ---------------------------------------------------------------------------
# 狀態機
# ---------------------------------------------------------------------------

_CANDIDATE_DECISIONS = {
    ReviewDecision.ACCEPT: TaskStatus.ACCEPTED,
    ReviewDecision.MODIFY: TaskStatus.MODIFIED,
    ReviewDecision.DEFER: TaskStatus.DEFERRED,
    ReviewDecision.REJECT: TaskStatus.REJECTED,
}

_SCHEDULABLE_STATUSES = {TaskStatus.ACCEPTED, TaskStatus.MODIFIED}

_EXECUTION_STATUS_MAP = {
    ExecutionStatus.COMPLETED: TaskStatus.COMPLETED,
    ExecutionStatus.NOT_COMPLETED: TaskStatus.NOT_COMPLETED,
    ExecutionStatus.CANCELLED: TaskStatus.CANCELLED,
}


def validate_review(task: Task, decision: ReviewDecision, modified_objective: str | None,
                     modified_action_mode: ActionMode | None, reason_code: str | None,
                     deferred_to: date | None) -> None:
    """檢查審核表單是否符合 SPEC §7.5 的必填規則，不合法就丟 ValidationError。"""
    if task.status != TaskStatus.CANDIDATE:
        raise InvalidTransitionError(
            f"task {task.task_id} 目前狀態是 {task.status}，只有 candidate 可以審核"
        )
    if decision == ReviewDecision.MODIFY:
        no_objective_change = modified_objective is None or modified_objective == task.objective
        no_mode_change = modified_action_mode is None or modified_action_mode == task.action_mode
        if no_objective_change and no_mode_change:
            raise ValidationError("modify 必須至少修改 objective 或 action_mode 其中之一")
        if not reason_code:
            raise ValidationError("modify 必須填 reason_code")
    if decision == ReviewDecision.DEFER and deferred_to is None:
        raise ValidationError("defer 必須填 deferred_to")
    if decision == ReviewDecision.REJECT and not reason_code:
        raise ValidationError("reject 必須填 reason_code")


def apply_review_to_task(task: Task, decision: ReviewDecision,
                          modified_objective: str | None = None,
                          modified_action_mode: ActionMode | None = None) -> Task:
    """回傳一份狀態已更新的新 Task（不修改原物件、不寫 DB，寫 DB 是 review_service 的事）。
    呼叫前必須先跑過 validate_review()，這裡不重複檢查 reason_code/deferred_to。"""
    new_status = _CANDIDATE_DECISIONS[decision]
    updated = Task(**{**task.__dict__})
    updated.status = new_status
    if decision == ReviewDecision.MODIFY:
        if modified_objective:
            updated.objective = modified_objective
        if modified_action_mode:
            updated.action_mode = modified_action_mode
    return updated


def schedule_task(task: Task) -> Task:
    if task.status not in _SCHEDULABLE_STATUSES:
        raise InvalidTransitionError(
            f"task {task.task_id} 狀態是 {task.status}，只有 accepted/modified 可以排入行程"
        )
    updated = Task(**{**task.__dict__})
    updated.status = TaskStatus.SCHEDULED
    return updated


def validate_outcome(task: Task, execution_status: ExecutionStatus,
                      outcome_type: OutcomeType | None) -> None:
    if task.status != TaskStatus.SCHEDULED:
        raise InvalidTransitionError(
            f"task {task.task_id} 狀態是 {task.status}，只有 scheduled 可以回報結果"
        )
    if execution_status == ExecutionStatus.COMPLETED and outcome_type is None:
        raise ValidationError("completed 必須填 outcome_type")


def apply_outcome_to_task(task: Task, execution_status: ExecutionStatus) -> Task:
    updated = Task(**{**task.__dict__})
    updated.status = _EXECUTION_STATUS_MAP[execution_status]
    return updated


def transition(task: Task, decision: ReviewDecision, *,
                modified_objective: str | None = None,
                modified_action_mode: ActionMode | None = None,
                reason_code: str | None = None,
                deferred_to: date | None = None) -> Task:
    """
    唯一對外的狀態轉移入口，對應 00_CONTRACTS.md 的函式簽名。
    合法轉移：candidate -> accepted/modified/deferred/rejected。
    """
    validate_review(task, decision, modified_objective, modified_action_mode, reason_code, deferred_to)
    return apply_review_to_task(task, decision, modified_objective, modified_action_mode)
