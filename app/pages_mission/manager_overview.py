"""
主管總覽頁（SPEC §5.2 P1 項目 1）。由 app/mission_app.py 呼叫
render(fixture_repo, task_repo, demo_date)。彙總「任務數量與狀態」，不做任何預測
或風險評分——SPEC §13.2 禁止的是舊版 dashboard.py 那種「平均成交機率／風險燈號」
風格的全公司 KPI 總覽，不是這種以任務為單位的跨業務彙總。
"""
from __future__ import annotations

import streamlit as st

from domain.models import TaskStatus, TaskType
from services.daily_plan_service import build_daily_plan

TASK_TYPE_LABELS = {"attack": "攻", "defend": "守", "grow": "增"}
_ACCEPTED_STATUSES = (TaskStatus.ACCEPTED, TaskStatus.MODIFIED)
_DONE_STATUSES = (TaskStatus.COMPLETED, TaskStatus.NOT_COMPLETED, TaskStatus.CANCELLED)


def render(fixture_repo, task_repo, demo_date) -> None:
    st.caption("依業務彙總今天的任務數量與狀態，不做任何預測或風險評分。")

    reps = fixture_repo.get_reps()
    for rep in reps:
        rep_id = rep["rep_id"]
        available_minutes = int(rep["daily_available_minutes"])
        # 主管開這頁時，某位業務可能今天還沒被任何人在「今日任務」頁點過，任務也還沒生成過；
        # build_daily_plan() 本身是 idempotent 的（同一個 generation_key 不會重複寫入），
        # 直接在這裡幫忙補生成一次，不然這位業務的列會顯示錯誤的 0。
        plan = build_daily_plan(rep_id, demo_date, available_minutes, fixture_repo, task_repo)

        counts = {tt: 0 for tt in TaskType}
        for t in plan.candidate_tasks:
            counts[t.task_type] += 1
        accepted = sum(1 for t in plan.candidate_tasks if t.status in _ACCEPTED_STATUSES)
        scheduled = sum(1 for t in plan.candidate_tasks if t.status == TaskStatus.SCHEDULED)
        completed = sum(1 for t in plan.candidate_tasks if t.status in _DONE_STATUSES)
        avg_score = (
            sum(t.value_score for t in plan.candidate_tasks) / len(plan.candidate_tasks)
            if plan.candidate_tasks else 0.0
        )

        with st.container(border=True):
            st.markdown(f"#### {rep['rep_name']}（{rep_id}）")
            cols = st.columns(7)
            cols[0].metric("候選任務數", len(plan.candidate_tasks))
            cols[1].metric("攻", counts[TaskType.ATTACK])
            cols[2].metric("守", counts[TaskType.DEFEND])
            cols[3].metric("增", counts[TaskType.GROW])
            cols[4].metric("已採納", accepted)
            cols[5].metric("待回報", scheduled)
            cols[6].metric("已完成", completed)
            st.caption(f"平均任務價值分數：{avg_score:.1f}")

            if st.button("切換到這位業務", key=f"switch-{rep_id}"):
                # 跟 today_tasks.py 的「開啟詳情」同一套跳轉模式：不能在這裡直接改
                # st.session_state["mission_nav"]／帳號切換 widget 的 session_state，
                # 那兩個 widget 這一輪都已經跑過了，改用 account_redirect／
                # nav_redirect 中繼旗標讓 mission_app.py 在建立 widget 之前套用。
                # 主管視角本來就是「只能看、只能導覽過去，不能越過業務直接操作」
                # （P1_MANAGER_OVERVIEW_STATEMENT.md 明確排除事項），所以這裡是把
                # 帳號整個切成該業務身份，而不是主管身份留著、只是換頁看而已。
                st.session_state["selected_rep_id"] = rep_id
                st.session_state["selected_available_minutes"] = available_minutes
                st.session_state["account_redirect"] = rep_id
                st.session_state["nav_redirect"] = "今日任務"
                st.rerun()
