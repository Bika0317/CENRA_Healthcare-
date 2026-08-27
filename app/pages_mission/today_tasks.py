"""
今日任務頁（SPEC §13.3）。由 app/mission_app.py 呼叫 render(fixture_repo, task_repo)。
"""
from __future__ import annotations

import io

import streamlit as st

from app.pages_mission.data_quality import is_stale
from domain.models import TaskStatus, TaskType
from services.anomaly_service import flag_statistical_outliers
from services.daily_plan_service import build_daily_plan
from services.ranking_model_service import score_tasks_with_reference_model

TASK_TYPE_LABELS = {"attack": "攻", "defend": "守", "grow": "增"}
TASK_TYPE_BADGE_COLOR = {"attack": "blue", "defend": "orange", "grow": "green"}
EVIDENCE_LABELS = {"weak": "弱", "medium": "中", "strong": "強"}
ACTION_MODE_LABELS = {"phone": "電話", "visit": "實訪"}
STATUS_LABELS = {
    "candidate": "待審核", "accepted": "已採納", "modified": "已修改採納",
    "deferred": "已延後", "rejected": "已拒絕", "scheduled": "已排入行程",
    "completed": "已完成", "not_completed": "未完成", "cancelled": "已取消",
}

_ACCEPTED_STATUSES = (TaskStatus.ACCEPTED, TaskStatus.MODIFIED, TaskStatus.SCHEDULED)
_DONE_STATUSES = (
    TaskStatus.COMPLETED, TaskStatus.NOT_COMPLETED, TaskStatus.CANCELLED,
    TaskStatus.REJECTED, TaskStatus.DEFERRED,
)


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


def _export_xlsx(tasks) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "今日任務"
    ws.append(["task_type", "target_name", "why_now", "objective",
               "value_score", "action_mode", "estimated_minutes", "status"])
    for t in tasks:
        ws.append([
            TASK_TYPE_LABELS[t.task_type.value], t.target_name, t.why_now, t.objective,
            round(t.value_score, 1), ACTION_MODE_LABELS[t.action_mode.value],
            t.estimated_minutes, STATUS_LABELS[t.status.value],
        ])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def render(fixture_repo, task_repo, demo_date) -> None:
    reps = fixture_repo.get_reps()
    rep_names = {r["rep_id"]: r["rep_name"] for r in reps}

    # 業務身份現在由 mission_app.py 右上角的帳號切換器決定，寫入 selected_rep_id；
    # 這裡不再自己放一個「選擇業務」下拉——兩個地方各自能選業務會互相打架，也會
    # 讓使用者搞不清楚該用哪一個切業務。mission_app.py 保證進這頁前一定有設好。
    rep_id = st.session_state["selected_rep_id"]
    st.caption(f"目前業務：{rep_names[rep_id]}（{rep_id}） · Demo 日期：{demo_date}（合成資料情境，非即時資料）")

    # Streamlit 有一個容易踩到的坑：widget 綁定的 session_state（用 key= 建立的那種），
    # 只要那個 widget 在某一輪完全沒被渲染到（例如使用者切去「行程」頁，
    # today_tasks.render() 整個沒執行），Streamlit 事後可能把它的 session_state 清掉；
    # 回到這頁時 widget 會用自己的內建預設值重開（number_input 用 min_value），
    # 完全蓋掉使用者原本輸入的東西。這裡也曾經每次都傳 value=default_minutes，結果
    # 使用者調整過的分鐘數下一輪就被蓋回預設值——st.number_input 只要同時給 key 又給
    # value，每輪都會用 value 蓋掉使用者輸入。現在只在「換了業務」時才重置成新業務
    # 自己的預設分鐘數；同一位業務、widget 狀態因為換頁被清掉時，用
    # selected_available_minutes 鏡像復原，不會掉回 min_value(0)。
    minutes_key = "today_tasks_available_minutes_widget"
    minutes_for_rep_key = "today_tasks_available_minutes_for_rep"
    if st.session_state.get(minutes_for_rep_key) != rep_id:
        default_minutes = next((int(r["daily_available_minutes"]) for r in reps if r["rep_id"] == rep_id), 240)
        st.session_state[minutes_key] = default_minutes
        st.session_state[minutes_for_rep_key] = rep_id
    elif minutes_key not in st.session_state and "selected_available_minutes" in st.session_state:
        st.session_state[minutes_key] = st.session_state["selected_available_minutes"]
    available_minutes = st.number_input(
        "今日可用彈性分鐘", min_value=0, max_value=600, step=10, key=minutes_key,
    )
    # 這組是給行程頁／結果回報頁跨頁讀取用的鏡像（本來就存在），現在也兼職拿來
    # 復原上面這個 widget 被 Streamlit 意外清掉的狀態。
    st.session_state["selected_available_minutes"] = available_minutes

    if st.button("重新產生今日任務", key="regen_plan"):
        # build_daily_plan() 本來就每次都重算，這個按鈕唯一該做的額外事情是把行程頁
        # 使用者手動調整過的點位順序重置掉，並給明確的「有反應」提示——不然單純
        # rerun() 因為資料本來就是新的，畫面完全不會變，會讓人以為按鈕壞了。
        st.session_state.pop("itinerary_visit_order", None)
        st.session_state.pop("itinerary_visit_order_source", None)
        st.toast("已重新產生今日任務清單。")
        st.rerun()

    # 每次都直接重算，不快取：build_daily_plan() 本身依 generation_key idempotent，
    # 重算成本在 demo 規模下可忽略；快取反而會在審核/結果寫入後看到舊狀態（已踩過這個坑）。
    plan = build_daily_plan(rep_id, demo_date, available_minutes, fixture_repo, task_repo)

    fixed_minutes = sum(ap.duration_minutes for ap in plan.fixed_appointments)
    total_candidates = len(plan.candidate_tasks)
    suggested_count = len(plan.suggested_tasks)
    st.caption(
        f"候選任務清單本身不會因為可用分鐘變動（共 {total_candidates} 張，是引擎依規則產生、"
        f"分數篩過的全部候選）；會變的是下面每張卡片上的「⭐建議」——"
        f"固定預約先占用 {fixed_minutes} 分鐘，剩下的 {available_minutes - fixed_minutes} 分鐘裡，"
        f"目前可以排入 **{suggested_count}／{total_candidates}** 張任務（剩餘 {plan.remaining_minutes} 分鐘沒排滿）。"
        "把上面的分鐘數調大，建議選取的張數才會跟著變多。"
    )

    if plan.fixed_appointments:
        st.markdown("#### 今日固定預約")
        for ap in plan.fixed_appointments:
            st.caption(f"{ap.start_time}　{ap.target_name}　{ap.purpose}　({ap.duration_minutes} 分鐘)")
    else:
        st.caption("今日沒有固定預約。")

    tasks = plan.candidate_tasks
    # 四個數字要能涵蓋 Task 狀態機的全部 9 種狀態、加起來剛好等於候選總數，
    # 不能有任何狀態「消失」在摘要外——之前「候選」「需確認」重複算同一個狀態，
    # 且 scheduled/deferred/rejected 三種狀態完全沒被任何一欄計入，會讓「已排入行程」
    # 或「已延後/拒絕」的任務憑空從摘要消失，數字對不上總數，看起來像 bug。
    counts = {
        "候選": len(tasks),
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

    st.markdown("#### 建議選取（⭐建議優先置頂，其餘依任務價值分數排序）")
    suggested_ids = {t.task_id for t in plan.suggested_tasks}
    # tasks 原本已經是 value_score DESC（task_repository.py 的 SQL ORDER BY），
    # Python 的 sort 是 stable sort，只用「是否為⭐建議」當 key 重排，兩個群組
    # 內部彼此的相對順序（分數高低）不會被打亂，只是把⭐建議整組提到最前面。
    filtered = sorted(filtered, key=lambda t: t.task_id not in suggested_ids)

    # 兩個輔助資訊層，都只是「並列參考」，不影響上面已經算好的候選/建議/容量分配：
    # 模型參考分數樣本不足時 model_scores 是 None，整欄不顯示；離群標記批次太小
    # 時回傳空集合，同樣不顯示，不會硬湊一個沒有統計意義的結果出來。
    model_scores_result = score_tasks_with_reference_model(task_repo, tasks)
    outlier_ids = flag_statistical_outliers(tasks)

    for t in filtered:
        with st.container(border=True):
            top = st.columns([1, 5, 2])
            top[0].badge(TASK_TYPE_LABELS[t.task_type.value], color=TASK_TYPE_BADGE_COLOR[t.task_type.value])
            # t.title 本身就是「{類型描述}：{診所名稱}」（例如「開發任務：青禾診所」），
            # 前面再放一次 t.target_name 會讓診所名稱在同一行連續出現兩次
            # （「青禾診所　開發任務：青禾診所」），看起來像重複渲染的排版錯誤。
            top[1].markdown(f"**{t.title}**")
            top[2].markdown(f"分數 **{t.value_score:.1f}**" + ("　⭐建議" if t.task_id in suggested_ids else ""))
            st.caption(f"為什麼現在：{t.why_now}")
            st.caption(f"建議目標：{t.objective}")
            if model_scores_result is not None:
                model_scores, n_samples = model_scores_result
                st.caption(
                    f"模型參考分數：{model_scores[t.task_id]:.1f}"
                    f"（示範性質，訓練樣本 {n_samples} 筆，不宣稱效度）"
                )
            if t.task_id in outlier_ids:
                st.caption("📊 統計離群：訊號組合與同批候選不同，非因果判斷")
            meta = st.columns(4)
            stale_suffix = "　⚠️ 資料較舊" if is_stale(t.data_updated_at, demo_date) else ""
            meta[0].caption(f"證據強度：{EVIDENCE_LABELS[t.evidence_strength.value]}{stale_suffix}")
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

    export_cols = st.columns(2)
    export_cols[0].download_button(
        "匯出今日任務清單（CSV）",
        _export_csv(tasks), file_name=f"{rep_id}_{demo_date}_today_tasks.csv", mime="text/csv",
    )
    export_cols[1].download_button(
        "匯出今日任務清單（Excel）",
        _export_xlsx(tasks), file_name=f"{rep_id}_{demo_date}_today_tasks.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.divider()
    st.markdown("#### 重設 Demo")
    st.caption("會清空所有任務、審核與結果紀錄，回到初始狀態，此操作無法復原。")
    confirm_reset = st.checkbox("我確定要重設 Demo 資料", key="confirm_reset_demo")
    if st.button("重設 Demo", disabled=not confirm_reset, key="reset_demo_btn"):
        task_repo.reset_demo()
        st.session_state.pop("itinerary_visit_order", None)
        st.session_state.pop("itinerary_visit_order_source", None)
        st.session_state.pop("confirm_reset_demo", None)
        st.success("已重設 Demo 資料。")
        st.rerun()
