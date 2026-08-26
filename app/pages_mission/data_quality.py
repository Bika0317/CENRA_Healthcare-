"""
資料品質提示共用 helper（SPEC §5.2 P1 項目 3）。task_detail.py 與 today_tasks.py
共用同一套「幾天前／是否過舊」判斷邏輯，不要各寫一份。
"""
from __future__ import annotations

from datetime import date, datetime

STALE_THRESHOLD_DAYS = 30


def freshness_label(data_updated_at: datetime, as_of: date) -> str:
    days = (as_of - data_updated_at.date()).days
    return f"{data_updated_at:%Y-%m-%d}（{days} 天前）"


def is_stale(data_updated_at: datetime, as_of: date, threshold_days: int = STALE_THRESHOLD_DAYS) -> bool:
    return (as_of - data_updated_at.date()).days > threshold_days
