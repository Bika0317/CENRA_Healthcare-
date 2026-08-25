"""覆蓋 SPEC §12.2 的多時段 nearest-neighbor 排序，以及 tie-break 容量分配。"""
from __future__ import annotations

from datetime import date, datetime

from domain.models import (
    ActionMode, EvidenceStrength, FixedAppointment, TargetType, TaskStatus, TaskType,
)
from services.scheduling import build_visit_sequence

from .conftest import make_task


def make_visit_task(task_id, lat, lon, minutes=45, value_score=60.0):
    return make_task(
        task_id=task_id, generation_key=f"GEN-{task_id}", action_mode=ActionMode.VISIT,
        estimated_minutes=minutes, value_score=value_score, lat=lat, lon=lon,
    )


def test_single_segment_orders_by_nearest_neighbor_from_home():
    home_lat, home_lon = 25.0330, 121.5654
    near = make_visit_task("T-near", 25.034, 121.566)   # 很靠近起點
    far = make_visit_task("T-far", 25.20, 121.80)        # 明顯較遠
    seq = build_visit_sequence([near, far], [], home_lat, home_lon, day_start="08:30", day_end="18:00")
    assert [t.task_id for t in seq] == ["T-near", "T-far"]
    assert seq[0].scheduled_start_time == "08:30"


def test_tasks_are_split_across_fixed_appointment_segments():
    home_lat, home_lon = 25.0330, 121.5654
    # 第一段只有 09:30-10:00（30 分鐘），塞不下一個 45 分鐘的任務，
    # 應該被跳過、留給固定預約結束後的第二段。
    fixed = [FixedAppointment(
        appointment_id="AP1", rep_id="L100", target_id="A999", target_name="固定預約診所",
        appointment_date=date(2026, 8, 25), start_time="10:00", duration_minutes=30,
        action_mode=ActionMode.VISIT, purpose="既定回訪", status="fixed", lat=25.05, lon=121.58,
    )]
    task = make_visit_task("T-after", 25.051, 121.581, minutes=45)
    seq = build_visit_sequence([task], fixed, home_lat, home_lon, day_start="09:30", day_end="18:00")
    assert [t.task_id for t in seq] == ["T-after"]
    # 第一段（09:30-10:00）塞不下，落到固定預約結束時間 10:30 之後的第二段開始
    assert seq[0].scheduled_start_time == "10:30"


def test_task_that_does_not_fit_any_segment_is_dropped_not_crammed():
    home_lat, home_lon = 25.0330, 121.5654
    # 兩個固定預約幾乎佔滿整天，只留一個 20 分鐘的小縫，但任務要 45 分鐘
    fixed = [
        FixedAppointment(appointment_id="AP1", rep_id="L100", target_id="A1", target_name="A",
                          appointment_date=date(2026, 8, 25), start_time="08:30", duration_minutes=540,
                          action_mode=ActionMode.VISIT, purpose="x", status="fixed", lat=25.03, lon=121.56),
    ]
    too_big = make_visit_task("T-big", 25.05, 121.58, minutes=45)
    seq = build_visit_sequence([too_big], fixed, home_lat, home_lon, day_start="08:30", day_end="18:00")
    assert seq == []


def test_no_coords_no_appointments_falls_back_to_highest_value_start():
    weak = make_visit_task("T-weak", 25.0, 121.5, value_score=40.0)
    strong = make_visit_task("T-strong", 25.5, 122.0, value_score=90.0)
    seq = build_visit_sequence([weak, strong], [], home_lat=None, home_lon=None)
    assert seq[0].task_id == "T-strong"


def test_phone_tasks_never_appear_in_visit_sequence():
    phone = make_task(task_id="T-phone", generation_key="G-phone", action_mode=ActionMode.PHONE,
                       lat=25.03, lon=121.56)
    seq = build_visit_sequence([phone], [], 25.0330, 121.5654)
    assert seq == []
