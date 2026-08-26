"""
任務詳情／審核頁（SPEC §13.4）。由 app/mission_app.py 呼叫 render(task_repo)。
被選中的任務 id 透過 st.session_state["selected_task_id"] 傳入（today_tasks.py 負責設定）。
"""
from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from domain.models import (
    ActionMode, EvidenceStrength, InvalidTransitionError, ReviewDecision,
    TaskStatus, ValidationError,
)
from domain.reason_codes import REVIEW_REASON_CODES
from services.review_service import submit_review

TASK_TYPE_LABELS = {"attack": "攻", "defend": "守", "grow": "增"}
EVIDENCE_LABELS = {"weak": "弱", "medium": "中", "strong": "強"}
STATUS_LABELS = {
    "candidate": "待審核", "accepted": "已採納", "modified": "已修改採納",
    "deferred": "已延後", "rejected": "已拒絕", "scheduled": "已排入行程",
    "completed": "已完成", "not_completed": "未完成", "cancelled": "已取消",
}
ACTION_MODE_LABELS = {"phone": "電話", "visit": "實訪"}


def _reason_options():
    return [code for code, _label in REVIEW_REASON_CODES]


def _reason_label(code: str) -> str:
    return dict(REVIEW_REASON_CODES).get(code, code)


def render(task_repo, demo_date: date) -> None:
    task_id = st.session_state.get("selected_task_id")
    if not task_id:
        st.info("請先從「今日任務」頁面選擇一張任務。")
        return

    try:
        task = task_repo.get_task(task_id)
    except KeyError:
        st.error("找不到這張任務，可能已經被重設。")
        return

    st.markdown(f"### {task.title}")
    cols = st.columns(4)
    cols[0].metric("任務類型", TASK_TYPE_LABELS[task.task_type.value])
    cols[1].metric("任務價值分數", f"{task.value_score:.1f}")
    cols[2].metric("證據強度", EVIDENCE_LABELS[task.evidence_strength.value])
    cols[3].metric("狀態", STATUS_LABELS[task.status.value])

    st.caption(
        f"生成時間：{task.generated_at:%Y-%m-%d %H:%M}"
        f" · 資料更新日期：{task.data_updated_at:%Y-%m-%d}"
        f" · 任務價值分數用於 Demo 排序"
    )
    st.write(f"**為什麼現在**　{task.why_now}")
    st.write(f"**建議目標**　{task.objective}")
    st.write(
        f"**建議執行方式**　{ACTION_MODE_LABELS[task.action_mode.value]}"
        f" · 預估 {task.estimated_minutes} 分鐘"
    )

    st.markdown("#### 三項主要證據")
    if not task.evidences:
        st.caption("此任務尚無可展示的證據紀錄。")
    for e in task.evidences:
        when = f"（{e.occurred_at:%Y-%m-%d}）" if e.occurred_at else ""
        st.markdown(f"- **{e.label}**：{e.display_value}{when}")

    st.warning(task.uncertainty_note)
    if task.lat is None or task.lon is None:
        st.caption("資料缺口：缺少座標資訊，無法排入實訪點位地圖。")

    if task.status != TaskStatus.CANDIDATE:
        st.info(f"這張任務已經審核過，目前狀態：{STATUS_LABELS[task.status.value]}")
        _render_review_history(task_repo, task_id)
        if task.status in (TaskStatus.ACCEPTED, TaskStatus.MODIFIED):
            st.markdown("#### 排入行程")
            st.caption("確認要把這張任務排進今天的電話／實訪行程，之後才能在「結果回報」頁回報結果。")
            if st.button("排入今日行程", key=f"schedule-{task_id}"):
                try:
                    updated = task_repo.mark_scheduled(task_id)
                except InvalidTransitionError as exc:
                    st.error(f"無法排入行程：{exc}")
                else:
                    st.success(f"已排入今日行程，目前狀態：{STATUS_LABELS[updated.status.value]}")
                    st.rerun()
        return

    st.markdown("#### 審核")
    decision_label = st.radio(
        "請選擇決定", ["採納", "修改後採納", "延後", "拒絕"], horizontal=True, key=f"decision-{task_id}",
    )

    modified_objective = None
    modified_action_mode = None
    reason_code = ""
    reason_note = None
    deferred_to = None

    if decision_label == "採納":
        decision = ReviewDecision.ACCEPT
    elif decision_label == "修改後採納":
        decision = ReviewDecision.MODIFY
        # 不要傳 value=""：text_input 同時給 key 又給 value 的話，每次 rerun（例如底下
        # 改執行方式的 radio 一動）都會被 value 蓋回空字串，使用者剛打的字會憑空消失。
        modified_objective = st.text_input("修改後的任務目標（留空表示不改）", key=f"mobj-{task_id}") or None
        new_mode_label = st.radio(
            "修改後的執行方式", ["不變", "改成電話", "改成實訪"], horizontal=True, key=f"mmode-{task_id}",
        )
        if new_mode_label == "改成電話":
            modified_action_mode = ActionMode.PHONE
        elif new_mode_label == "改成實訪":
            modified_action_mode = ActionMode.VISIT
        reason_code = st.selectbox(
            "修改原因", options=_reason_options(), format_func=_reason_label, key=f"mreason-{task_id}",
        )
        reason_note = st.text_area("補充說明（選填）", key=f"mnote-{task_id}") or None
    elif decision_label == "延後":
        decision = ReviewDecision.DEFER
        deferred_to = st.date_input(
            "延後至", value=demo_date + timedelta(days=1), min_value=demo_date + timedelta(days=1),
            key=f"defer-{task_id}",
        )
        reason_code = st.selectbox(
            "延後原因", options=_reason_options(), format_func=_reason_label, key=f"dreason-{task_id}",
        )
    else:
        decision = ReviewDecision.REJECT
        reason_code = st.selectbox(
            "拒絕原因", options=_reason_options(), format_func=_reason_label, key=f"rreason-{task_id}",
        )
        reason_note = st.text_area("補充說明（選填）", key=f"rnote-{task_id}") or None

    if st.button("送出審核結果", key=f"submit-{task_id}"):
        try:
            updated = submit_review(
                task_id, decision,
                modified_objective=modified_objective, modified_action_mode=modified_action_mode,
                reason_code=reason_code, reason_note=reason_note, deferred_to=deferred_to,
                actor_rep_id=task.rep_id, task_repo=task_repo,
            )
        except ValidationError as exc:
            st.error(f"無法送出：{exc}")
        except InvalidTransitionError as exc:
            st.error(f"這張任務目前的狀態不允許這個操作：{exc}")
        else:
            st.success(f"已更新，目前狀態：{STATUS_LABELS[updated.status.value]}")
            st.rerun()


def _render_review_history(task_repo, task_id: str) -> None:
    history = task_repo.get_review_history(task_id)
    if not history:
        return
    st.markdown("#### 審核紀錄")
    for r in history:
        st.caption(
            f"{r.created_at:%Y-%m-%d %H:%M} · {r.actor_rep_id} · {r.decision.value}"
            + (f" · 原因：{_reason_label(r.reason_code)}" if r.reason_code else "")
        )
