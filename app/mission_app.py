"""
CENRA Mission 主應用入口。刻意保持很薄：只做四頁路由，實際內容都在 app/pages_mission/。
不 import 任何 model/*.py（舊模型不進新主應用，SPEC §6.3）。
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

st.set_page_config(page_title="CENRA Mission", layout="wide")


@st.cache_resource
def get_fixture_repo() -> FixtureRepository:
    return FixtureRepository(demo_cutoff=DEMO_DATE)


@st.cache_resource
def get_task_repo() -> TaskRepository:
    return TaskRepository(DB_PATH)


fixture_repo = get_fixture_repo()
task_repo = get_task_repo()

st.title("CENRA Mission｜AI 診所業務任務指揮台")
st.caption("CRM 記得昨天，CENRA Mission 讓業務決定今天。合成 Demo 資料，未接任何真實系統。")

PAGES = ["今日任務", "任務詳情／審核", "行程", "結果回報", "主管總覽"]
if "mission_nav" not in st.session_state:
    st.session_state["mission_nav"] = PAGES[0]
if "nav_redirect" in st.session_state:
    st.session_state["mission_nav"] = st.session_state.pop("nav_redirect")

nav = st.radio("導覽", PAGES, horizontal=True, key="mission_nav", label_visibility="collapsed")

if nav == "今日任務":
    today_tasks.render(fixture_repo, task_repo, DEMO_DATE)
elif nav == "任務詳情／審核":
    task_detail.render(task_repo, DEMO_DATE)
elif nav == "行程":
    itinerary.render(fixture_repo, task_repo, DEMO_DATE)
elif nav == "結果回報":
    rep_id = st.session_state.get("selected_rep_id", "L100")
    outcomes.render(task_repo, rep_id, DEMO_DATE)
else:
    manager_overview.render(fixture_repo, task_repo, DEMO_DATE)
