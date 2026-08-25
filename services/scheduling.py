"""
容量分配與點位順序（SPEC §11.4, §12.2）。
固定預約先占用當日分鐘數；攻/守/增各先給 1 個最低配額（沒有合格任務就釋出）；
其餘依 value_score 遞補；電話預設 20 分鐘、實訪預設 45 分鐘＋簡化交通估計。
點位順序用 nearest-neighbor 啟發式，非真實路網最佳化，UI 必須標示為「示意」。
"""
from __future__ import annotations

from dataclasses import replace

from domain.geo import haversine_km
from domain.models import ActionMode, FixedAppointment, Task, TaskType

# SPEC §12.2 沒有定義營業時段的起訖時間，這是唯一需要自己假設的地方：
# 一般外勤業務的工作時段，用來把一天依固定預約切成好幾個可排點的時段。
DEFAULT_DAY_START = "08:30"
DEFAULT_DAY_END = "18:00"

_EVIDENCE_RANK = {"weak": 0, "medium": 1, "strong": 2}


def _tie_break_key(task: Task):
    """SPEC §11.3 tie-break：急迫性 > 證據強度 > 較低成本 > 穩定 task_id。"""
    return (
        -task.value_score,
        -task.urgency_score,
        -_EVIDENCE_RANK[task.evidence_strength.value],
        task.cost_penalty,
        task.task_id,
    )


def allocate_daily_capacity(
    candidate_tasks: list[Task],
    fixed_appointments: list[FixedAppointment],
    available_minutes: int,
) -> tuple[list[Task], int]:
    """回傳 (建議選取的任務清單, 剩餘分鐘數)。固定預約先扣掉分鐘數（AC-06）。"""
    fixed_minutes = sum(ap.duration_minutes for ap in fixed_appointments)
    remaining = max(available_minutes - fixed_minutes, 0)

    selected: list[Task] = []
    selected_ids: set[str] = set()

    # 三類各先給 1 個最低配額；沒有合格任務就釋出給其他類型（不強制湊數）
    for task_type in (TaskType.ATTACK, TaskType.DEFEND, TaskType.GROW):
        pool = sorted(
            [t for t in candidate_tasks if t.task_type == task_type and t.task_id not in selected_ids],
            key=_tie_break_key,
        )
        for t in pool:
            if t.estimated_minutes <= remaining:
                selected.append(t)
                selected_ids.add(t.task_id)
                remaining -= t.estimated_minutes
                break

    # 其餘依 value_score 由高到低遞補，直到剩餘時間不足
    rest = sorted(
        [t for t in candidate_tasks if t.task_id not in selected_ids],
        key=_tie_break_key,
    )
    for t in rest:
        if t.estimated_minutes <= remaining:
            selected.append(t)
            selected_ids.add(t.task_id)
            remaining -= t.estimated_minutes

    selected.sort(key=_tie_break_key)
    return selected, remaining


def _minutes_since_midnight(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _hhmm(total_minutes: int) -> str:
    h, m = divmod(max(0, total_minutes), 60)
    return f"{h % 24:02d}:{m:02d}"


def build_visit_sequence(
    selected_tasks: list[Task],
    fixed_appointments: list[FixedAppointment],
    home_lat: float | None = None,
    home_lon: float | None = None,
    day_start: str = DEFAULT_DAY_START,
    day_end: str = DEFAULT_DAY_END,
) -> list[Task]:
    """
    只排 action_mode=visit 且有座標的任務（SPEC §12.1）。依 SPEC §12.2 的五步驟：
    1. 依固定 appointment time 切分可用時段（day_start/day_end 是唯一自己假設的部分）。
    2. 每個時段從上一個固定點、或業務駐地座標（沒有的話退回分數最高的候選）出發。
    3. 時段內用最近鄰依序排入還沒排的 visit 任務，直到這個時段時間用完就換下一段。
    4. 同距離以較高 value_score 排前。
    5. 不呼叫外部路網 API，用 haversine 直線距離示意，不是真實路網最佳化
       （UI 文案不可以講「最佳路線」）。

    回傳的 Task 是帶了 scheduled_start_time（HH:MM，示意用）的副本，不影響傳入的原物件。
    某個時段容量塞不下的任務會直接跳過（不會硬塞進不合理的時段），可能導致
    result 少於 selected_tasks 裡的 visit 任務數——這是容量分配（依總分鐘數）跟
    實際切時段（依固定預約把一天切碎）本來就可能對不齊的正常結果，不是 bug。
    """
    visit_tasks = [t for t in selected_tasks if t.action_mode == ActionMode.VISIT and t.lat is not None and t.lon is not None]
    if not visit_tasks:
        return []

    sorted_fixed = sorted(fixed_appointments, key=lambda a: a.start_time)
    day_end_min = _minutes_since_midnight(day_end)

    segments: list[tuple[int, int, float | None, float | None]] = []
    cursor_min = _minutes_since_midnight(day_start)
    cursor_lat, cursor_lon = home_lat, home_lon
    for ap in sorted_fixed:
        ap_start = _minutes_since_midnight(ap.start_time)
        if ap_start > cursor_min:
            segments.append((cursor_min, ap_start, cursor_lat, cursor_lon))
        cursor_min = max(cursor_min, ap_start + ap.duration_minutes)
        if ap.lat is not None and ap.lon is not None:
            cursor_lat, cursor_lon = ap.lat, ap.lon
    if cursor_min < day_end_min:
        segments.append((cursor_min, day_end_min, cursor_lat, cursor_lon))
    if not segments:
        segments = [(cursor_min, cursor_min + sum(t.estimated_minutes for t in visit_tasks), cursor_lat, cursor_lon)]

    remaining = list(visit_tasks)
    ordered: list[Task] = []

    for seg_start, seg_end, seg_lat, seg_lon in segments:
        if not remaining:
            break
        capacity = seg_end - seg_start
        cur_lat, cur_lon = seg_lat, seg_lon
        cur_min = seg_start
        if cur_lat is None or cur_lon is None:
            first = min(remaining, key=lambda t: (-t.value_score, t.task_id))
            cur_lat, cur_lon = first.lat, first.lon

        while remaining and capacity > 0:
            remaining.sort(key=lambda t: (haversine_km(cur_lat, cur_lon, t.lat, t.lon), -t.value_score, t.task_id))
            candidate = remaining[0]
            if candidate.estimated_minutes > capacity:
                break
            remaining.pop(0)
            ordered.append(replace(candidate, scheduled_start_time=_hhmm(cur_min)))
            cur_min += candidate.estimated_minutes
            capacity -= candidate.estimated_minutes
            cur_lat, cur_lon = candidate.lat, candidate.lon

    return ordered
