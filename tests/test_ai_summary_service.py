"""覆蓋 services/ai_summary_service.py 的 opt-in 邊界：沒有金鑰時不可用，
prompt 只包含 task 既有欄位、不會要求 LLM 猜測任何額外原因。"""
from __future__ import annotations

from services.ai_summary_service import _build_prompt, is_available
from tests.conftest import make_task


def test_unavailable_without_api_key():
    """測試環境／CI 不會設定 secrets.toml，st.secrets 存取空值或丟例外都算「沒有金鑰」。"""
    assert is_available() is False


def test_prompt_only_uses_existing_task_fields():
    task = make_task(why_now="測試原因", objective="測試目標")
    prompt = _build_prompt(task)
    assert "測試原因" in prompt
    assert "測試目標" in prompt
    assert task.title in prompt
    for e in task.evidences:
        assert e.label in prompt
        assert e.display_value in prompt
    # 明確要求「不要新增未出現的原因」，避免 LLM 憑空補資訊。
    assert "不要新增" in prompt


def test_prompt_handles_task_with_no_evidence():
    task = make_task(evidences=[])
    prompt = _build_prompt(task)
    assert "無額外證據紀錄" in prompt
