"""
CENRA Mission 主應用入口。刻意保持很薄：只做帳號切換／頁面路由，實際內容都在
app/pages_mission/。不 import 任何 model/*.py（舊模型不進新主應用，SPEC §6.3）。

帳號切換（右上角）決定「身份」：選某位業務＝以該業務身份操作今日任務／審核／
行程／結果回報；選「主管」＝只能看「主管總覽」這個彙總頁，不能代替業務審核
任務——這是刻意的權限邊界（呼應 P1_MANAGER_OVERVIEW_STATEMENT.md 的排除事項），
不是頁面沒做完。這不是真的登入／權限系統（SPEC §5.3 P2 明確排除），單純是一個
demo 用的身份切換器，用來模擬「業務視角」與「主管視角」的差異。
"""
from __future__ import annotations

import os
import sys
from datetime import date

# streamlit run app/mission_app.py 執行時，sys.path[0] 只有 app/ 這個資料夾，
# 需要把 repo 根目錄加進去才能 import data/domain/engines/services 這些頂層套件。
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import streamlit as st

from data.fixture_repository import FixtureRepository
from data.task_repository import TaskRepository
from app.pages_mission import itinerary, manager_overview, outcomes, task_detail, today_tasks

DEMO_DATE = date(2026, 8, 25)
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "db", "mission.db")
MANAGER_ACCOUNT = "MANAGER"
REP_PAGES = ["今日任務", "任務詳情／審核", "行程", "結果回報"]

st.set_page_config(page_title="CENRA Mission", layout="wide")


@st.cache_resource
def get_fixture_repo() -> FixtureRepository:
    return FixtureRepository(demo_cutoff=DEMO_DATE)


@st.cache_resource
def get_task_repo() -> TaskRepository:
    return TaskRepository(DB_PATH)


fixture_repo = get_fixture_repo()
task_repo = get_task_repo()

reps = fixture_repo.get_reps()
rep_names = {r["rep_id"]: r["rep_name"] for r in reps}
account_options = list(rep_names.keys()) + [MANAGER_ACCOUNT]


def _account_label(account_id: str) -> str:
    return "主管" if account_id == MANAGER_ACCOUNT else f"{rep_names[account_id]}（{account_id}）"


# 跟 nav_redirect 同一套中繼旗標手法：manager_overview.py 的「切換到這位業務」
# 要把帳號從「主管」切回某位業務，但那顆按鈕是在 account_widget 這個 widget
# 已經在本輪實例化「之後」才被按下的（下一輪才會重新走到這裡），所以不能直接
# 改 account_widget 綁定的 session_state——要在「建立 widget 之前」用這個旗標套用。
account_widget_key = "account_switcher_widget"
if "account_redirect" in st.session_state:
    st.session_state[account_widget_key] = st.session_state.pop("account_redirect")

header_cols = st.columns([4, 1])
with header_cols[0]:
    st.title("CENRA Mission｜AI 診所業務任務指揮台")
    st.caption("CRM 記得昨天，CENRA Mission 讓業務決定今天。合成 Demo 資料，未接任何真實系統。")
with header_cols[1]:
    account = st.selectbox(
        "帳號", account_options, format_func=_account_label, key=account_widget_key,
    )

is_manager = account == MANAGER_ACCOUNT
if not is_manager:
    # 給行程／結果回報／主管總覽頁跨頁讀取用的鏡像（既有機制），現在也是
    # today_tasks.py 判斷「目前業務」的唯一來源。
    st.session_state["selected_rep_id"] = account

if "nav_redirect" in st.session_state:
    st.session_state["mission_nav"] = st.session_state.pop("nav_redirect")

if is_manager:
    st.caption("主管視角：只能瀏覽跨業務彙總，無法代替業務審核任務——請切換到該業務的帳號才能操作。")
    manager_overview.render(fixture_repo, task_repo, DEMO_DATE)
else:
    if st.session_state.get("mission_nav") not in REP_PAGES:
        st.session_state["mission_nav"] = REP_PAGES[0]
    nav = st.radio("導覽", REP_PAGES, horizontal=True, key="mission_nav", label_visibility="collapsed")

    if nav == "今日任務":
        today_tasks.render(fixture_repo, task_repo, DEMO_DATE)
    elif nav == "任務詳情／審核":
        task_detail.render(task_repo, DEMO_DATE)
    elif nav == "行程":
        itinerary.render(fixture_repo, task_repo, DEMO_DATE)
    else:
        outcomes.render(task_repo, account, DEMO_DATE)
