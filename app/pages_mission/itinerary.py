"""
行程頁（SPEC §13.5）。由 app/mission_app.py 呼叫 render(fixture_repo, task_repo, demo_date)。
用「今日任務」頁選過的業務／可用分鐘（存在 session_state）重算 DailyPlan，不快取，
確保審核／結果頁剛寫入的狀態變化能立刻反映在這裡（快取會看到舊狀態，已踩過這個坑）。
"""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from domain.models import ActionMode, TaskStatus
from services.daily_plan_service import build_daily_plan
from services.scheduling import build_visit_sequence

TASK_TYPE_LABELS = {"attack": "攻", "defend": "守", "grow": "增"}
_ACCEPTED_STATUSES = (TaskStatus.ACCEPTED, TaskStatus.MODIFIED, TaskStatus.SCHEDULED)


def render(fixture_repo, task_repo, demo_date) -> None:
    rep_id = st.session_state.get("selected_rep_id")
    if not rep_id:
        st.info("請先到「今日任務」頁選擇業務並產生今日任務。")
        return
    available_minutes = st.session_state.get("selected_available_minutes", 240)
    plan = build_daily_plan(rep_id, demo_date, available_minutes, fixture_repo, task_repo)

    st.markdown("#### 固定預約時間軸")
    if plan.fixed_appointments:
        for ap in plan.fixed_appointments:
            st.caption(f"{ap.start_time}　{ap.target_name}　{ap.purpose}　({ap.duration_minutes} 分鐘)")
    else:
        st.caption("今日沒有固定預約。")

    accepted = [t for t in plan.candidate_tasks if t.status in _ACCEPTED_STATUSES]
    phone_tasks = [t for t in accepted if t.action_mode == ActionMode.PHONE]
    visit_tasks = {t.task_id: t for t in accepted if t.action_mode == ActionMode.VISIT}

    # plan.visit_sequence 只涵蓋「還沒審核」的建議候選（daily_plan_service.py 的容量分配
    # 只會處理 still-pending 的任務），已經採納的任務不會出現在那裡——這裡要對「已採納的
    # 實訪任務」自己重算一次順序，不能直接拿 plan.visit_sequence 當初始值。
    accepted_visit_sequence = build_visit_sequence(list(visit_tasks.values()), plan.fixed_appointments)

    order_key = "itinerary_visit_order"
    default_order = [t.task_id for t in accepted_visit_sequence]
    if st.session_state.get(f"{order_key}_source") != tuple(sorted(visit_tasks)):
        st.session_state[order_key] = default_order
        st.session_state[f"{order_key}_source"] = tuple(sorted(visit_tasks))
    order = st.session_state[order_key]

    cols = st.columns(2)
    with cols[0]:
        st.markdown("#### 電話清單")
        if not phone_tasks:
            st.caption("目前沒有已採納的電話任務。")
        for t in phone_tasks:
            st.write(f"[{TASK_TYPE_LABELS[t.task_type.value]}] {t.target_name}　{t.objective}")

    with cols[1]:
        st.markdown("#### 實訪清單（點位順序）")
        if not order:
            st.caption("目前沒有已採納且有座標的實訪任務。")
        for i, task_id in enumerate(order):
            t = visit_tasks[task_id]
            row = st.columns([5, 1, 1])
            row[0].write(f"{i + 1}. [{TASK_TYPE_LABELS[t.task_type.value]}] {t.target_name}　{t.objective}")
            if row[1].button("↑", key=f"up-{task_id}", disabled=(i == 0)):
                order[i - 1], order[i] = order[i], order[i - 1]
                st.rerun()
            if row[2].button("↓", key=f"down-{task_id}", disabled=(i == len(order) - 1)):
                order[i + 1], order[i] = order[i], order[i + 1]
                st.rerun()

    if order:
        ordered_tasks = [visit_tasks[tid] for tid in order]
        fig = go.Figure(go.Scattermapbox(
            lat=[t.lat for t in ordered_tasks], lon=[t.lon for t in ordered_tasks],
            mode="markers+lines+text",
            text=[str(i + 1) for i in range(len(ordered_tasks))], textposition="top center",
            marker=dict(size=16, color="#D85A30"),
            line=dict(width=2, color="#888"),
            hovertext=[f"{i + 1}. {t.target_name}（{TASK_TYPE_LABELS[t.task_type.value]}）"
                       for i, t in enumerate(ordered_tasks)],
            hoverinfo="text",
        ))
        fig.update_layout(
            mapbox_style="open-street-map", height=420,
            mapbox_center={"lat": sum(t.lat for t in ordered_tasks) / len(ordered_tasks),
                            "lon": sum(t.lon for t in ordered_tasks) / len(ordered_tasks)},
            mapbox_zoom=9.5, margin={"r": 0, "t": 0, "l": 0, "b": 0}, showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    st.caption("拜訪點位與建議順序示意，非即時導航或最佳路線。")

    fixed_minutes = sum(ap.duration_minutes for ap in plan.fixed_appointments)
    used_minutes = fixed_minutes + sum(t.estimated_minutes for t in accepted)
    st.metric("今日總使用分鐘", used_minutes)
    st.metric("剩餘分鐘", max(plan.available_minutes - used_minutes, 0))
