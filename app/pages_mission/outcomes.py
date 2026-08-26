"""
結果回報頁（SPEC §13.6）。由 app/mission_app.py 呼叫 render(task_repo, rep_id, plan_date)。
"""
from __future__ import annotations

from datetime import date

import streamlit as st

from domain.models import ExecutionStatus, OutcomeType, TaskStatus, ValidationError

from services.outcome_service import submit_outcome

TASK_TYPE_LABELS = {"attack": "攻", "defend": "守", "grow": "增"}
OUTCOME_TYPE_OPTIONS = [
    (OutcomeType.DEMAND_CONFIRMED, "需求確認"),
    (OutcomeType.REPLENISHMENT, "補貨"),
    (OutcomeType.FOLLOW_UP_BOOKED, "後續約訪"),
    (OutcomeType.NO_OPPORTUNITY, "無機會"),
    (OutcomeType.DATA_ERROR, "資料錯誤"),
    (OutcomeType.SERVICE_RESOLVED, "服務事項已解決"),
    (OutcomeType.OTHER, "其他"),
]
EXECUTION_STATUS_LABELS = {
    ExecutionStatus.COMPLETED: "已完成",
    ExecutionStatus.NOT_COMPLETED: "未完成",
    ExecutionStatus.CANCELLED: "已取消",
}


def render(task_repo, rep_id: str, plan_date: date) -> None:
    tasks = [
        t for t in task_repo.get_candidate_tasks(rep_id, plan_date)
        if t.status == TaskStatus.SCHEDULED
    ]
    completed = [
        t for t in task_repo.get_candidate_tasks(rep_id, plan_date)
        if t.status in (TaskStatus.COMPLETED, TaskStatus.NOT_COMPLETED, TaskStatus.CANCELLED)
    ]

    st.markdown("### 待回報結果")
    if not tasks:
        st.caption("目前沒有已排入行程、尚待回報結果的任務。")
    for task in tasks:
        # task.title 已經是「{類型描述}：{診所名稱}」，前面再加 task.target_name
        # 會讓診所名稱重複出現兩次（同一個坑，today_tasks.py 的任務卡也踩過）。
        with st.expander(f"[{TASK_TYPE_LABELS[task.task_type.value]}] {task.title}"):
            status_label = st.radio(
                "執行狀態", ["已完成", "未完成", "已取消"], horizontal=True, key=f"exec-{task.task_id}",
            )
            outcome_type = None
            note = None
            next_step = None
            next_date_value = None

            if status_label == "已完成":
                execution_status = ExecutionStatus.COMPLETED
                outcome_type = st.selectbox(
                    "結果類型", options=[o for o, _ in OUTCOME_TYPE_OPTIONS],
                    format_func=lambda o: dict(OUTCOME_TYPE_OPTIONS)[o], key=f"otype-{task.task_id}",
                )
            elif status_label == "未完成":
                execution_status = ExecutionStatus.NOT_COMPLETED
                note = st.text_input("未完成原因", key=f"note-{task.task_id}") or None
            else:
                execution_status = ExecutionStatus.CANCELLED
                note = st.text_input("取消原因", key=f"cnote-{task.task_id}") or None

            has_next_step = st.checkbox("需要後續追蹤", key=f"hasnext-{task.task_id}")
            if has_next_step:
                next_step = st.text_input("下一步", key=f"nstep-{task.task_id}") or None
                next_date_value = st.date_input("預計日期", key=f"ndate-{task.task_id}")

            if st.button("送出結果", key=f"osubmit-{task.task_id}"):
                try:
                    updated = submit_outcome(
                        task.task_id, execution_status, outcome_type=outcome_type, note=note,
                        next_step=next_step, next_date=next_date_value,
                        actor_rep_id=rep_id, task_repo=task_repo,
                    )
                except ValidationError as exc:
                    st.error(f"無法送出：{exc}")
                else:
                    st.success(f"已更新，完成時間：{updated.status.value}")
                    st.rerun()

    if completed:
        with st.expander(f"已完成／已結案（{len(completed)}）", expanded=False):
            for task in completed:
                outcome = task_repo.get_outcome(task.task_id)
                st.markdown(f"- [{TASK_TYPE_LABELS[task.task_type.value]}] {task.target_name}：{task.status.value}"
                             + (f" · {outcome.completed_at:%Y-%m-%d %H:%M}" if outcome else ""))
