"""
容量分配與點位順序（SPEC §11.4, §12.2）。
固定預約先占用當日分鐘數；攻/守/增各先給 1 個最低配額（沒有合格任務就釋出）；
其餘依 value_score 遞補；電話預設 20 分鐘、實訪預設 45 分鐘＋簡化交通估計。
點位順序用 nearest-neighbor 啟發式，非真實路網最佳化，UI 必須標示為「示意」。
"""
from __future__ import annotations

import math

from domain.models import ActionMode, FixedAppointment, Task, TaskType

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


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def build_visit_sequence(
    selected_tasks: list[Task],
    fixed_appointments: list[FixedAppointment],
) -> list[Task]:
    """
    只排 action_mode=visit 且有座標的任務（SPEC §12.1）。
    簡單 nearest-neighbor：從上一個固定點出發（沒有固定預約時，從分數最高的任務出發），
    每次挑最近的下一個未排點位。這是示意用的簡化啟發式，不是真實路網最佳化
    （UI 文案不可以講「最佳路線」）。
    """
    visit_tasks = [t for t in selected_tasks if t.action_mode == ActionMode.VISIT and t.lat is not None and t.lon is not None]
    if not visit_tasks:
        return []

    remaining = list(visit_tasks)
    ordered: list[Task] = []

    fixed_with_coords = [ap for ap in fixed_appointments if ap.lat is not None and ap.lon is not None]
    if fixed_with_coords:
        cur_lat, cur_lon = fixed_with_coords[0].lat, fixed_with_coords[0].lon
    else:
        first = min(remaining, key=lambda t: (-t.value_score, t.task_id))
        remaining.remove(first)
        ordered.append(first)
        cur_lat, cur_lon = first.lat, first.lon

    while remaining:
        remaining.sort(key=lambda t: (_haversine_km(cur_lat, cur_lon, t.lat, t.lon), -t.value_score, t.task_id))
        nxt = remaining.pop(0)
        ordered.append(nxt)
        cur_lat, cur_lon = nxt.lat, nxt.lon

    return ordered
