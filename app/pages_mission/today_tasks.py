"""
今日任務頁（SPEC §13.3）。由 app/mission_app.py 呼叫 render(fixture_repo, task_repo)。
"""
from __future__ import annotations

import io

import streamlit as st

from domain.models import TaskStatus, TaskType
from services.daily_plan_service import build_daily_plan

TASK_TYPE_LABELS = {"attack": "攻", "defend": "守", "grow": "增"}
TASK_TYPE_BADGE_COLOR = {"attack": "blue", "defend": "orange", "grow": "green"}
EVIDENCE_LABELS = {"weak": "弱", "medium": "中", "strong": "強"}
ACTION_MODE_LABELS = {"phone": "電話", "visit": "實訪"}
STATUS_LABELS = {
    "candidate": "待審核", "accepted": "已採納", "modified": "已修改採納",
    "deferred": "已延後", "rejected": "已拒絕", "scheduled": "已排入行程",
    "completed": "已完成", "not_completed": "未完成", "cancelled": "已取消",
}

_ACCEPTED_STATUSES = (TaskStatus.ACCEPTED, TaskStatus.MODIFIED)
_DONE_STATUSES = (TaskStatus.COMPLETED, TaskStatus.NOT_COMPLETED, TaskStatus.CANCELLED)


def _export_csv(tasks) -> bytes:
    buf = io.StringIO()
    buf.write("task_type,target_name,why_now,objective,value_score,action_mode,estimated_minutes,status\n")
    for t in tasks:
        cells = [
            TASK_TYPE_LABELS[t.task_type.value], t.target_name, t.why_now, t.objective,
            f"{t.value_score:.1f}", ACTION_MODE_LABELS[t.action_mode.value],
            str(t.estimated_minutes), STATUS_LABELS[t.status.value],
        ]
        buf.write(",".join('"' + c.replace('"', '""') + '"' for c in cells) + "\n")
    return buf.getvalue().encode("utf-8-sig")


def render(fixture_repo, task_repo, demo_date) -> None:
    reps = fixture_repo.get_reps()
    rep_names = {r["rep_id"]: r["rep_name"] for r in reps}
    rep_id = st.selectbox(
        "選擇業務", options=list(rep_names.keys()), format_func=lambda r: f"{rep_names[r]}（{r}）",
        key="today_tasks_rep_id_widget",
    )
    st.caption(f"Demo 日期：{demo_date}（合成資料情境，非即時資料）")

    default_minutes = next((int(r["daily_available_minutes"]) for r in reps if r["rep_id"] == rep_id), 240)
    available_minutes = st.number_input(
        "今日可用彈性分鐘", min_value=0, max_value=600, value=default_minutes, step=10,
        key="today_tasks_available_minutes_widget",
    )
    # 用一組獨立、非 widget 綁定的 key 保存目前選擇，行程頁／結果回報頁靠這個取值。
    # widget 綁定的 key 只有在該 widget 這一輪真的被渲染時才保證讀得到，換頁到其他分支
    # （itinerary.py／outcomes.py 那個 elif 分支）today_tasks.render() 根本沒執行，
    # 直接讀 widget key 會拿到 None，這裡已經踩過這個坑。
    st.session_state["selected_rep_id"] = rep_id
    st.session_state["selected_available_minutes"] = available_minutes

    if st.button("重新產生今日任務", key="regen_plan"):
        st.rerun()

    # 每次都直接重算，不快取：build_daily_plan() 本身依 generation_key idempotent，
    # 重算成本在 demo 規模下可忽略；快取反而會在審核/結果寫入後看到舊狀態（已踩過這個坑）。
    plan = build_daily_plan(rep_id, demo_date, available_minutes, fixture_repo, task_repo)

    if plan.fixed_appointments:
        st.markdown("#### 今日固定預約")
        for ap in plan.fixed_appointments:
            st.caption(f"{ap.start_time}　{ap.target_name}　{ap.purpose}　({ap.duration_minutes} 分鐘)")
    else:
        st.caption("今日沒有固定預約。")

    tasks = plan.candidate_tasks
    counts = {
        "候選": sum(1 for t in tasks if t.status == TaskStatus.CANDIDATE),
        "需確認": sum(1 for t in tasks if t.status == TaskStatus.CANDIDATE),
        "已採納": sum(1 for t in tasks if t.status in _ACCEPTED_STATUSES),
        "已完成": sum(1 for t in tasks if t.status in _DONE_STATUSES),
    }
    cols = st.columns(4)
    for col, (label, n) in zip(cols, counts.items()):
        col.metric(label, n)

    if not tasks:
        st.info("目前沒有合格的候選任務。可以調整可用分鐘後重新產生，或確認 Demo 資料是否已重設。")
        return

    type_filter = st.radio(
        "篩選任務類型", ["全部", "攻", "守", "增"], horizontal=True, key="today_tasks_type_filter",
    )
    label_to_type = {"攻": TaskType.ATTACK, "守": TaskType.DEFEND, "增": TaskType.GROW}
    filtered = tasks if type_filter == "全部" else [t for t in tasks if t.task_type == label_to_type[type_filter]]

    st.markdown("#### 建議選取（依任務價值分數排序）")
    suggested_ids = {t.task_id for t in plan.suggested_tasks}

    for t in filtered:
        with st.container(border=True):
            top = st.columns([1, 5, 2])
            top[0].badge(TASK_TYPE_LABELS[t.task_type.value], color=TASK_TYPE_BADGE_COLOR[t.task_type.value])
            top[1].markdown(f"**{t.target_name}**　{t.title}")
            top[2].markdown(f"分數 **{t.value_score:.1f}**" + ("　⭐建議" if t.task_id in suggested_ids else ""))
            st.caption(f"為什麼現在：{t.why_now}")
            st.caption(f"建議目標：{t.objective}")
            meta = st.columns(4)
            meta[0].caption(f"證據強度：{EVIDENCE_LABELS[t.evidence_strength.value]}")
            meta[1].caption(f"{ACTION_MODE_LABELS[t.action_mode.value]} · {t.estimated_minutes} 分鐘")
            meta[2].caption(f"狀態：{STATUS_LABELS[t.status.value]}")
            if meta[3].button("開啟詳情", key=f"open-{t.task_id}"):
                st.session_state["selected_task_id"] = t.task_id
                # 不能在這裡直接改 st.session_state["mission_nav"]：
                # 那個 key 綁定的 radio widget已經在 mission_app.py 這一輪跑過了，
                # Streamlit 不允許 widget 實例化後再改它的 session_state。
                # 改用一個中繼旗標，讓 mission_app.py 在「建立 radio 之前」讀取並套用。
                st.session_state["nav_redirect"] = "任務詳情／審核"
                st.rerun()

    st.download_button(
        "匯出今日任務清單（CSV）",
        _export_csv(tasks), file_name=f"{rep_id}_{demo_date}_today_tasks.csv", mime="text/csv",
    )

    st.divider()
    st.markdown("#### 重設 Demo")
    st.caption("會清空所有任務、審核與結果紀錄，回到初始狀態，此操作無法復原。")
    confirm_reset = st.checkbox("我確定要重設 Demo 資料", key="confirm_reset_demo")
    if st.button("重設 Demo", disabled=not confirm_reset, key="reset_demo_btn"):
        task_repo.reset_demo()
        st.session_state.pop("daily_plan_cache", None)
        st.session_state.pop("daily_plan_cache_key", None)
        st.session_state.pop("confirm_reset_demo", None)
        st.success("已重設 Demo 資料。")
        st.rerun()
