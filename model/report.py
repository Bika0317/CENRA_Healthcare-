"""
每日巡訪日報：把 ranking.py 產出的優先排序結果，轉成
(1) 給業務員個人的今日建議拜訪清單 email 內容
(2) 給主管的高風險客戶彙總 email 內容
(3) 可匯出的 CSV/Excel 報表
"""
import pandas as pd

EXPORT_COLS = {
    "customer_id": "客戶編號", "customer_name": "客戶名稱", "region": "地區", "channel": "通路",
    "tier": "等級", "rep_id": "業務員編號", "purchase_proba": "成交機率", "risk_flag": "風險燈號",
    "priority_score": "優先分數", "days_since_last_visit": "距上次拜訪天數",
    "revenue_last_90d": "近90天營收",
}

BRAND_GRADIENT = "background:linear-gradient(135deg,#c8006e 0%,#e8395a 100%);"
FONT = "font-family:'Microsoft JhengHei','Segoe UI',Helvetica,Arial,sans-serif;"

_BADGE_STYLES = {
    "紅": ("#fdecea", "#c0392b"),
    "黃": ("#fff6da", "#8a6d00"),
    "綠": ("#e6f4ea", "#1e7d32"),
}


def export_table(scored_df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in EXPORT_COLS if c in scored_df.columns]
    out = scored_df[cols].rename(columns=EXPORT_COLS).copy()
    if "成交機率" in out.columns:
        out["成交機率"] = (out["成交機率"] * 100).round(1)
    return out


def rep_daily_visit_list(scored_df: pd.DataFrame, rep_id: str, top_n: int = 8) -> pd.DataFrame:
    my = scored_df[scored_df.rep_id == rep_id].sort_values("priority_score", ascending=False).head(top_n)
    return export_table(my)


def _risk_badge(risk_flag: str) -> str:
    label = risk_flag.split("：")[0]
    detail = risk_flag.split("：")[1] if "：" in risk_flag else ""
    bg, fg = _BADGE_STYLES.get(label, ("#eee", "#333"))
    return (
        f'<span style="display:inline-block;padding:3px 10px;border-radius:12px;'
        f'background:{bg};color:{fg};font-size:12px;font-weight:600;white-space:nowrap;">'
        f'{label}{("・" + detail) if detail else ""}</span>'
    )


def _stat_card(label: str, value: str, accent: str = "#c8006e") -> str:
    return f"""
    <td style="padding:0 6px;">
      <div style="background:#faf9fb;border:1px solid #eee;border-radius:10px;padding:14px 10px;text-align:center;">
        <div style="font-size:12px;color:#888;margin-bottom:4px;">{label}</div>
        <div style="font-size:20px;font-weight:700;color:{accent};">{value}</div>
      </div>
    </td>
    """


def _table_header_row(cols: list) -> str:
    ths = "".join(
        f'<th style="text-align:left;padding:10px 12px;font-size:12px;color:#666;'
        f'text-transform:uppercase;letter-spacing:.03em;border-bottom:2px solid #eee;">{c}</th>'
        for c in cols
    )
    return f"<tr>{ths}</tr>"


def render_rep_email_html(rep_name: str, visit_list: pd.DataFrame, report_date: str) -> str:
    n = len(visit_list)
    n_red = int(visit_list["風險燈號"].str.startswith("紅").sum()) if n else 0
    avg_proba = visit_list["成交機率"].mean() if n else 0

    rows_html = "".join(
        f'<tr style="background:{"#fff" if i % 2 == 0 else "#fbfafc"};">'
        f'<td style="padding:10px 12px;font-size:13px;color:#222;border-bottom:1px solid #f0f0f0;">{r["客戶名稱"]}</td>'
        f'<td style="padding:10px 12px;font-size:13px;color:#555;border-bottom:1px solid #f0f0f0;">{r["地區"]}</td>'
        f'<td style="padding:10px 12px;font-size:13px;color:#555;border-bottom:1px solid #f0f0f0;">{r["通路"]}</td>'
        f'<td style="padding:10px 12px;font-size:13px;color:#222;font-weight:600;border-bottom:1px solid #f0f0f0;">{r["成交機率"]}%</td>'
        f'<td style="padding:10px 12px;border-bottom:1px solid #f0f0f0;">{_risk_badge(r["風險燈號"])}</td>'
        f'</tr>'
        for i, (_, r) in enumerate(visit_list.iterrows())
    )

    return f"""
    <html><body style="{FONT} margin:0;padding:24px;background:#f4f5f7;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;margin:0 auto;">
        <tr><td style="{BRAND_GRADIENT}border-radius:14px 14px 0 0;padding:22px 26px;">
          <div style="color:#fff;font-size:12px;letter-spacing:.08em;opacity:.85;">中化裕民 CENRA+ Healthcare</div>
          <div style="color:#fff;font-size:20px;font-weight:700;margin-top:4px;">今日建議拜訪清單</div>
          <div style="color:#ffe1ec;font-size:13px;margin-top:2px;">{report_date}</div>
        </td></tr>
        <tr><td style="background:#fff;padding:22px 26px;border:1px solid #eee;border-top:none;">
          <p style="font-size:14px;color:#333;margin:0 0 16px;">{rep_name} 您好，以下是系統依「成交機率 × 客戶價值 × 風險」排序的今日建議拜訪名單：</p>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
            {_stat_card("建議拜訪數", str(n))}
            {_stat_card("高風險客戶", str(n_red), accent="#c0392b")}
            {_stat_card("平均成交機率", f"{avg_proba:.0f}%")}
          </tr></table>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:18px;border-collapse:collapse;">
            {_table_header_row(["客戶名稱", "地區", "通路", "成交機率", "風險燈號"])}
            {rows_html}
          </table>
        </td></tr>
        <tr><td style="background:#fff;border:1px solid #eee;border-top:none;border-radius:0 0 14px 14px;padding:14px 26px;">
          <p style="color:#999;font-size:11px;margin:0;">本信由智慧巡訪與成交預判系統自動產生（原型測試信件）。</p>
        </td></tr>
      </table>
    </body></html>
    """


def render_manager_digest_html(scored_df: pd.DataFrame, reps: pd.DataFrame, report_date: str, risk_top_n: int = 20) -> str:
    risky = scored_df[scored_df.risk_flag.str.startswith("紅")].sort_values("ai_risk_score", ascending=False).head(risk_top_n)
    risky = risky.merge(reps[["rep_id", "rep_name"]], on="rep_id", how="left")
    n_red = int((scored_df.risk_flag.str.startswith("紅")).sum())
    avg_proba_all = scored_df["purchase_proba"].mean() * 100

    rows_html = "".join(
        f'<tr style="background:{"#fff" if i % 2 == 0 else "#fbfafc"};">'
        f'<td style="padding:10px 12px;font-size:13px;color:#222;border-bottom:1px solid #f0f0f0;">{r["customer_name"]}</td>'
        f'<td style="padding:10px 12px;font-size:13px;color:#555;border-bottom:1px solid #f0f0f0;">{r["rep_name"]}</td>'
        f'<td style="padding:10px 12px;font-size:13px;color:#555;border-bottom:1px solid #f0f0f0;">{r["region"]}</td>'
        f'<td style="padding:10px 12px;font-size:13px;color:#222;font-weight:600;border-bottom:1px solid #f0f0f0;">{r["purchase_proba"]:.0%}</td>'
        f'<td style="padding:10px 12px;font-size:13px;color:#555;border-bottom:1px solid #f0f0f0;">{r["revenue_last_90d"]:,.0f}</td>'
        f'</tr>'
        for i, (_, r) in enumerate(risky.iterrows())
    )

    return f"""
    <html><body style="{FONT} margin:0;padding:24px;background:#f4f5f7;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:680px;margin:0 auto;">
        <tr><td style="background:linear-gradient(135deg,#3b3f47 0%,#20232a 100%);border-radius:14px 14px 0 0;padding:22px 26px;">
          <div style="color:#fff;font-size:12px;letter-spacing:.08em;opacity:.8;">中化裕民 CENRA+ Healthcare ・ 主管彙總</div>
          <div style="color:#fff;font-size:20px;font-weight:700;margin-top:4px;">高風險客戶彙總（疑似競品入侵）</div>
          <div style="color:#cfd3da;font-size:13px;margin-top:2px;">{report_date}</div>
        </td></tr>
        <tr><td style="background:#fff;padding:22px 26px;border:1px solid #eee;border-top:none;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
            {_stat_card("全公司高風險客戶", str(n_red), accent="#c0392b")}
            {_stat_card("本次列出", str(len(risky)))}
            {_stat_card("全公司平均成交機率", f"{avg_proba_all:.0f}%")}
          </tr></table>
          <p style="font-size:13px;color:#666;margin:16px 0 8px;">以下為風險分數最高的客戶，建議優先安排業務員回訪：</p>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
            {_table_header_row(["客戶名稱", "負責業務", "地區", "成交機率", "近90天營收"])}
            {rows_html}
          </table>
        </td></tr>
        <tr><td style="background:#fff;border:1px solid #eee;border-top:none;border-radius:0 0 14px 14px;padding:14px 26px;">
          <p style="color:#999;font-size:11px;margin:0;">本信由智慧巡訪與成交預判系統自動產生（原型測試信件）。</p>
        </td></tr>
      </table>
    </body></html>
    """


_RISK_EMOJI = {"紅": "🔴", "黃": "🟡", "綠": "🟢"}


def render_rep_line_text(rep_name: str, visit_list: pd.DataFrame, report_date: str, top_n: int = 5) -> str:
    """業務員在外面跑時，LINE 訊息比 email 更容易被看到——純文字格式，手機讀起來不用捲很久。"""
    lines = [f"📋 {report_date} 今日拜訪建議（{rep_name}）"]
    for i, (_, r) in enumerate(visit_list.head(top_n).iterrows(), start=1):
        emoji = _RISK_EMOJI.get(r["風險燈號"].split("：")[0], "⚪")
        lines.append(f"{i}. {emoji} {r['客戶名稱']}｜成交機率 {r['成交機率']}%")
    n_red = int(visit_list["風險燈號"].str.startswith("紅").sum())
    if n_red:
        lines.append(f"⚠️ 其中 {n_red} 家疑似競品入侵，建議優先安排")
    lines.append("點擊開啟系統查看完整清單與建議話術 →")
    return "\n".join(lines)


def render_line_bubble_html(message_text: str) -> str:
    """把 LINE 訊息文字包成聊天氣泡樣式，方便在 Dashboard／簡報裡直接展示視覺效果。"""
    escaped = message_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
    return f"""
    <div style="{FONT} background:#7494c0;padding:24px;border-radius:12px;max-width:380px;">
      <div style="background:#fff;border-radius:14px 14px 14px 2px;padding:14px 16px;
                  box-shadow:0 1px 2px rgba(0,0,0,.15);font-size:14px;line-height:1.6;color:#222;">
        {escaped}
      </div>
      <div style="text-align:right;color:#e8edf5;font-size:11px;margin-top:6px;">智慧巡訪系統 LINE 官方帳號（原型 mock）</div>
    </div>
    """
