"""
生成式 AI 開場白建議（opt-in，需使用者自備 Anthropic API 金鑰）。

刻意的職責邊界（呼應審查意見「AI 提出證據」這種說法不精確——系統只是彙整/顯示
證據，原因永遠由業務確認）：
- 只把 Task 物件本身已經算好、已經顯示在畫面上的欄位（why_now／objective／
  evidences）轉成一段自然語言開場白，不會被要求推測任何沒有出現在這些欄位裡的
  原因或資訊。
- 沒有設定金鑰時，`is_available()` 回傳 False，呼叫端（task_detail.py）應該直接
  不顯示相關按鈕，不是顯示一個永遠失敗的按鈕——這是 SPEC §5.3「不新增需要金鑰的
  依賴」的具體做法：功能存在，但不是任何人的必要依賴，預設關閉。
- API 呼叫失敗要降級成一句錯誤說明文字，不能讓整頁跟著掛掉。
"""
from __future__ import annotations

from domain.models import Task

MODEL = "claude-opus-5"
MAX_TOKENS = 300


def is_available() -> bool:
    try:
        import streamlit as st
        return bool(st.secrets.get("ANTHROPIC_API_KEY"))
    except Exception:
        # st.secrets 在沒有 secrets.toml 的環境（例如本機沒建這個檔、或 CI）
        # 存取時可能直接丟例外，而不是回傳空值——這裡當成「沒有金鑰」處理，
        # 不是真的錯誤。
        return False


def _build_prompt(task: Task) -> str:
    evidence_lines = "\n".join(f"- {e.label}：{e.display_value}" for e in task.evidences) or "（無額外證據紀錄）"
    return (
        "你是診所業務的助理。以下是一張任務系統已經算好的既有資訊，全部都是事實，"
        "不要新增任何沒有在這裡出現的原因或猜測：\n\n"
        f"任務：{task.title}\n"
        f"為什麼現在：{task.why_now}\n"
        f"建議目標：{task.objective}\n"
        f"證據：\n{evidence_lines}\n\n"
        "請把上面的資訊轉成一段給業務員參考的開場白（繁體中文，2-3 句話，"
        "自然口語，只整理既有資訊，不要加上你自己的判斷或未提及的原因）。"
    )


def generate_opening_line(task: Task) -> str:
    import streamlit as st
    import anthropic

    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    try:
        response = client.messages.create(
            model=MODEL, max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": _build_prompt(task)}],
        )
        return next((b.text for b in response.content if b.type == "text"), "").strip()
    except anthropic.AuthenticationError:
        return "（AI 開場白暫時無法使用：API 金鑰無效，請確認 secrets 設定。）"
    except anthropic.RateLimitError:
        return "（AI 開場白暫時無法使用：請求過於頻繁，請稍後再試。）"
    except anthropic.APIStatusError as exc:
        return f"（AI 開場白暫時無法使用：伺服器錯誤 {exc.status_code}。）"
    except anthropic.APIConnectionError:
        return "（AI 開場白暫時無法使用：網路連線問題，請稍後再試。）"
