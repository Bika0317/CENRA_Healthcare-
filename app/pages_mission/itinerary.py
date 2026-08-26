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
# 「電話清單」「實訪清單」只列還沒執行完的已採納任務（給業務今天還要做的事），
# 所以維持只含 ACCEPTED/MODIFIED/SCHEDULED，COMPLETED 等狀態的任務本來就該從
# 這兩份清單消失，這裡不用改。
_ACCEPTED_STATUSES = (TaskStatus.ACCEPTED, TaskStatus.MODIFIED, TaskStatus.SCHEDULED)
# 但「今日總使用分鐘／剩餘分鐘」是在算「今天分鐘總量被用掉多少」，跟
# daily_plan_service.py 的 _COMMITTED_STATUSES 邏輯必須一致：已完成/未完成/取消
# 的任務時間也已經真的花掉了，不能因為它從上面兩份清單消失，就連帶從這個分鐘數
# 計算裡消失，不然這裡跟「今日任務」頁 plan.remaining_minutes 顯示的數字會對不上
# （這兩個頁面理論上該是同一件事的兩種呈現方式）。
_COMMITTED_STATUSES = _ACCEPTED_STATUSES + (
    TaskStatus.COMPLETED, TaskStatus.NOT_COMPLETED, TaskStatus.CANCELLED,
)


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

    rep = fixture_repo.get_rep(rep_id)

    # plan.visit_sequence 只涵蓋「還沒審核」的建議候選（daily_plan_service.py 的容量分配
    # 只會處理 still-pending 的任務），已經採納的任務不會出現在那裡——這裡要對「已採納的
    # 實訪任務」自己重算一次順序，不能直接拿 plan.visit_sequence 當初始值。
    accepted_visit_sequence = build_visit_sequence(
        list(visit_tasks.values()), plan.fixed_appointments, rep.get("home_lat"), rep.get("home_lon"),
    )
    # 依固定預約切時段後，可能有任務塞不進任何時段（時段容量比任務總分鐘數更零碎），
    # scheduled_start_time 就是 None，不畫進地圖/順序清單，但還是要讓業務看到、能改成電話。
    unscheduled_visit_ids = set(visit_tasks) - {t.task_id for t in accepted_visit_sequence}
    scheduled_start_by_id = {t.task_id: t.scheduled_start_time for t in accepted_visit_sequence}

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
            start_time = scheduled_start_by_id.get(task_id)
            row = st.columns([5, 1, 1])
            time_prefix = f"{start_time}　" if start_time else ""
            row[0].write(f"{i + 1}. {time_prefix}[{TASK_TYPE_LABELS[t.task_type.value]}] {t.target_name}　{t.objective}")
            if row[1].button("↑", key=f"up-{task_id}", disabled=(i == 0)):
                order[i - 1], order[i] = order[i], order[i - 1]
                st.rerun()
            if row[2].button("↓", key=f"down-{task_id}", disabled=(i == len(order) - 1)):
                order[i + 1], order[i] = order[i], order[i + 1]
                st.rerun()
        if unscheduled_visit_ids:
            st.caption(
                f"{len(unscheduled_visit_ids)} 筆已採納實訪任務今天的時段塞不下"
                "（固定預約切出來的空檔都不夠），建議改電話或延後。"
            )

    # 固定預約本身也是今天真的要去的實訪點位（有座標就該畫在地圖上），不能因為
    # 「地圖只畫已採納候選任務」這條舊邏輯，讓使用者只有固定預約、還沒採納任何實訪
    # 候選時，地圖整個不見——這是使用者實測回報的落差：明明有固定預約，卻看不到地圖。
    fixed_points = [ap for ap in plan.fixed_appointments if ap.lat is not None and ap.lon is not None]
    ordered_tasks = [visit_tasks[tid] for tid in order]

    if ordered_tasks or fixed_points:
        # plotly 從 6.x 某個版本開始把 go.Scattermapbox／layout.mapbox 這整組
        # Mapbox-GL 底的舊 API 標成 deprecated、後續版本直接砍掉（存取時丟
        # AttributeError），改用不需要 Mapbox token、MapLibre 底的 go.Scattermap／
        # layout.map 取代。requirements.txt 沒鎖 plotly 版本，Streamlit Cloud
        # 部署時裝到的版本比本機新，就是舊 API 已經被砍掉的那個版本，本機沒鎖版本
        # 卻沒有立刻踩到，是因為本機剛好還在兩者都保留的版本區間。
        fig = go.Figure()
        if fixed_points:
            fig.add_trace(go.Scattermap(
                lat=[ap.lat for ap in fixed_points], lon=[ap.lon for ap in fixed_points],
                mode="markers+text",
                text=[ap.start_time for ap in fixed_points], textposition="top center",
                marker=dict(size=16, color="#2C5AA0", symbol="circle"),
                hovertext=[f"固定預約　{ap.start_time}　{ap.target_name}　{ap.purpose}" for ap in fixed_points],
                hoverinfo="text", name="固定預約",
            ))
        if ordered_tasks:
            fig.add_trace(go.Scattermap(
                lat=[t.lat for t in ordered_tasks], lon=[t.lon for t in ordered_tasks],
                mode="markers+lines+text",
                text=[str(i + 1) for i in range(len(ordered_tasks))], textposition="top center",
                marker=dict(size=16, color="#D85A30"),
                line=dict(width=2, color="#888"),
                hovertext=[
                    f"{i + 1}. {t.target_name}（{TASK_TYPE_LABELS[t.task_type.value]}）"
                    + (f" · {scheduled_start_by_id.get(t.task_id)}" if scheduled_start_by_id.get(t.task_id) else "")
                    for i, t in enumerate(ordered_tasks)
                ],
                hoverinfo="text", name="已採納實訪任務",
            ))
        all_lats = [ap.lat for ap in fixed_points] + [t.lat for t in ordered_tasks]
        all_lons = [ap.lon for ap in fixed_points] + [t.lon for t in ordered_tasks]
        fig.update_layout(
            map_style="open-street-map", height=420,
            map_center={"lat": sum(all_lats) / len(all_lats), "lon": sum(all_lons) / len(all_lons)},
            map_zoom=9.5, margin={"r": 0, "t": 0, "l": 0, "b": 0}, showlegend=bool(fixed_points and ordered_tasks),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.caption("拜訪點位與建議順序示意，非即時導航或最佳路線。")

    committed = [t for t in plan.candidate_tasks if t.status in _COMMITTED_STATUSES]
    fixed_minutes = sum(ap.duration_minutes for ap in plan.fixed_appointments)
    used_minutes = fixed_minutes + sum(t.estimated_minutes for t in committed)
    st.metric("今日總使用分鐘", used_minutes)
    st.metric("剩餘分鐘", max(plan.available_minutes - used_minutes, 0))
