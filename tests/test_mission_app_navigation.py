"""
覆蓋 app/mission_app.py 右上角帳號切換器的角色權限邊界：業務身份只能看四頁
業務導覽、看不到主管總覽；主管身份只能看主管總覽、看不到業務導覽；
主管總覽的「切換到這位業務」要能把帳號整個切成該業務身份並跳轉到今日任務。

用 streamlit.testing.v1.AppTest 而非 Playwright：這個帳號切換器是 BaseWeb
selectbox，在真的瀏覽器裡用 accessibility tree 自動化偶爾會因為虛擬化清單
只渲染可視範圍內選項而點不到，AppTest 直接操作 widget 的 session_state，
不受這個限制，驗證起來更穩定。
"""
from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

_MISSION_APP_PATH = str(Path(__file__).resolve().parents[1] / "app" / "mission_app.py")


def _run_app() -> AppTest:
    at = AppTest.from_file(_MISSION_APP_PATH)
    at.run(timeout=30)
    return at


def test_default_account_is_a_rep_with_three_nav_tabs():
    at = _run_app()
    assert not at.exception
    nav = at.radio(key="mission_nav")
    # 「任務詳情／審核」故意不在頂層導覽裡——那頁只能靠今日任務頁點任務卡的
    # 「開啟詳情」進入，不是一個可以直接點的平行分頁（見 mission_app.py 的說明）。
    assert list(nav.options) == ["今日任務", "行程", "結果回報"]


def test_manager_account_hides_nav_tabs_and_shows_overview():
    at = _run_app()
    at.selectbox(key="account_switcher_widget").set_value("MANAGER").run(timeout=30)
    assert not at.exception
    # 主管視角沒有「導覽」四頁的 radio，只有主管總覽自己的內容。
    assert len(at.radio) == 0
    headings = [m.value for m in at.markdown if m.value.startswith("####")]
    assert len(headings) == 3  # L100/L101/L102 各一張卡片
    switch_buttons = [b for b in at.button if b.key and b.key.startswith("switch-")]
    assert {b.key for b in switch_buttons} == {"switch-L100", "switch-L101", "switch-L102"}


def test_switch_to_rep_button_flips_account_and_lands_on_today_tasks():
    at = _run_app()
    at.selectbox(key="account_switcher_widget").set_value("MANAGER").run(timeout=30)
    at.button(key="switch-L101").click().run(timeout=30)
    assert not at.exception
    assert at.selectbox(key="account_switcher_widget").value == "L101"
    assert at.radio(key="mission_nav").value == "今日任務"
    assert any("林柏宇（L101）" in c.value for c in at.caption)


def test_opening_a_task_shows_detail_without_a_matching_nav_tab():
    """點任務卡的「開啟詳情」後，畫面要換成任務詳情頁，但頂層導覽本身
    （3 個選項）維持不變——這頁疊在導覽之上，不是導覽的第 4 個分頁。"""
    at = _run_app()
    open_buttons = [b for b in at.button if b.key and b.key.startswith("open-")]
    assert open_buttons
    open_buttons[0].click().run(timeout=30)

    assert not at.exception
    assert list(at.radio(key="mission_nav").options) == ["今日任務", "行程", "結果回報"]
    assert any(h.value.startswith("###") for h in at.markdown)  # task_detail.py 的任務標題
    back_buttons = [b for b in at.button if b.key == "back_to_today_tasks"]
    assert back_buttons


def test_back_button_returns_to_today_tasks():
    at = _run_app()
    open_buttons = [b for b in at.button if b.key and b.key.startswith("open-")]
    open_buttons[0].click().run(timeout=30)

    at.button(key="back_to_today_tasks").click().run(timeout=30)
    assert not at.exception
    # 回到今日任務後，篩選任務類型那個 radio（today_tasks.py 專屬）應該又出現了。
    assert any(r.label == "篩選任務類型" for r in at.radio)
