"""
SPEC §16.5 guardrail：對新版主應用會被使用者看到的檔案 grep 禁用語句。
model/ 和 docs/legacy_v1/ 底下的舊文件不檢查，那些本來就是允許保留的 legacy 內容。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from domain.reason_codes import BANNED_PHRASES

REPO_ROOT = Path(__file__).resolve().parents[1]

SCANNED_PATHS = [
    REPO_ROOT / "app" / "mission_app.py",
    *sorted((REPO_ROOT / "app" / "pages_mission").glob("*.py")),
    REPO_ROOT / "README.md",
]


@pytest.mark.parametrize("path", [p for p in SCANNED_PATHS if p.exists()], ids=lambda p: p.name)
def test_file_has_no_banned_phrases(path: Path):
    text = path.read_text(encoding="utf-8")
    for phrase in BANNED_PHRASES:
        assert phrase not in text, f"{path.relative_to(REPO_ROOT)} 出現禁用語句：{phrase}"


def test_scanned_paths_are_not_empty():
    # 防呆：確保清單真的有掃到檔案，不是路徑打錯導致測試永遠通過
    assert len([p for p in SCANNED_PATHS if p.exists()]) >= 5


def test_itinerary_page_has_required_disclaimer():
    text = (REPO_ROOT / "app" / "pages_mission" / "itinerary.py").read_text(encoding="utf-8")
    assert "拜訪點位與建議順序示意，非即時導航或最佳路線" in text
