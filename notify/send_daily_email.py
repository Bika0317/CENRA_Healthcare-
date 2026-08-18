"""
每日通知信排程腳本。

執行方式：
    python notify/send_daily_email.py

模式：
  - 預設 DRY RUN：不會真的寄出，只會把渲染好的 email 內容存到 outbox/ 資料夾供預覽。
  - 若要真的寄送，設定以下環境變數後，加上 --send 參數執行：
      SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM
    以及在 data/reps.csv 與主管信箱設定 MANAGER_EMAIL 環境變數。

排程建議（Windows 工作排程器）：
    schtasks /create /tn "CRM每日拜訪通知" /tr "python C:\\path\\to\\notify\\send_daily_email.py --send" /sc daily /st 08:00
"""
import argparse
import os
import smtplib
import sys
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "model"))

import pandas as pd
from ranking import score_customers
from report import rep_daily_visit_list, render_rep_email_html, render_manager_digest_html

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
MODEL_PATH = ROOT / "model" / "purchase_model.pkl"
OUTBOX_DIR = ROOT / "outbox"
CUTOFF = date(2026, 8, 1)


def send_via_smtp(to_addr: str, subject: str, html_body: str) -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    sender = os.environ.get("SMTP_FROM", user)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_addr
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(sender, [to_addr], msg.as_string())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true",
                         help="真的透過 SMTP 寄送（需先設定 SMTP_* 環境變數）。省略則為 dry run，只存檔預覽。")
    parser.add_argument("--top-n", type=int, default=8, help="每位業務員的建議拜訪清單筆數")
    args = parser.parse_args()

    customers = pd.read_csv(DATA_DIR / "customers.csv")
    visits = pd.read_csv(DATA_DIR / "visits.csv")
    orders = pd.read_csv(DATA_DIR / "orders.csv")
    reps = pd.read_csv(DATA_DIR / "reps.csv")

    scored_df = score_customers(customers, visits, orders, CUTOFF, model_path=str(MODEL_PATH))
    report_date = date.today().isoformat()

    OUTBOX_DIR.mkdir(exist_ok=True)
    sent_count, dryrun_count = 0, 0

    for _, rep in reps.iterrows():
        visit_list = rep_daily_visit_list(scored_df, rep.rep_id, top_n=args.top_n)
        if visit_list.empty:
            continue
        html = render_rep_email_html(rep.rep_name, visit_list, report_date)
        subject = f"【智慧巡訪系統】{report_date} {rep.rep_name} 今日建議拜訪清單"

        if args.send:
            send_via_smtp(rep.email, subject, html)
            sent_count += 1
        else:
            out_file = OUTBOX_DIR / f"{report_date}_{rep.rep_id}_{rep.rep_name}.html"
            out_file.write_text(html, encoding="utf-8")
            dryrun_count += 1

    manager_html = render_manager_digest_html(scored_df, reps, report_date)
    manager_subject = f"【智慧巡訪系統】{report_date} 高風險客戶彙總"
    if args.send:
        manager_addr = os.environ.get("MANAGER_EMAIL")
        if manager_addr:
            send_via_smtp(manager_addr, manager_subject, manager_html)
            sent_count += 1
    else:
        (OUTBOX_DIR / f"{report_date}_manager_digest.html").write_text(manager_html, encoding="utf-8")
        dryrun_count += 1

    if args.send:
        print(f"已寄出 {sent_count} 封信。")
    else:
        print(f"DRY RUN：共產生 {dryrun_count} 封信件預覽，存於 {OUTBOX_DIR}（未實際寄送）。")
        print("若要真的寄送，請設定 SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD/SMTP_FROM 環境變數，並加上 --send 參數。")


if __name__ == "__main__":
    main()
