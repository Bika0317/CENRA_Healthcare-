"""
核心 seam（SPEC §7.3）：把三個引擎、統一評分、容量分配、點位排序、SQLite 持久化
串成單一入口。UI 層（app/mission_app.py）只呼叫 build_daily_plan()，不直接碰引擎或 repository。
"""
from __future__ import annotations

from datetime import date

from domain.models import DailyPlan, TaskStatus
from engines import attack, defend, grow
from services.scheduling import allocate_daily_capacity, build_visit_sequence
from services.scoring import score_candidates


def build_daily_plan(rep_id: str, plan_date: date, available_minutes: int,
                      fixture_repo, task_repo) -> DailyPlan:
    """
    1. 三引擎各自產生候選 -> 2. 統一評分 -> 3. 存入 task_repository（idempotent，
    同 generation_key 不重複寫入）-> 4. 取回今天全部 candidate 任務（含歷史已存在的）
    -> 5. 固定預約 + 容量分配 + 三類最低配額 -> 6. nearest-neighbor 點位順序。
    """
    candidates = (
        attack.generate_candidates(fixture_repo, rep_id, plan_date)
        + defend.generate_candidates(fixture_repo, rep_id, plan_date)
        + grow.generate_candidates(fixture_repo, rep_id, plan_date)
    )
    new_tasks = score_candidates(candidates, rep_id, plan_date)
    if new_tasks:
        task_repo.save_tasks(new_tasks)

    # candidate_tasks 依契約（00_CONTRACTS.md）要含這批次「所有 status」，不是只有還沒審核的，
    # UI 才能顯示已採納/已排程/已完成的任務卡。容量分配只該從「還沒審核」的子集裡挑，
    # 已經審核過的任務不該被重新建議一次。
    candidate_tasks = task_repo.get_candidate_tasks(rep_id, plan_date)
    still_pending = [t for t in candidate_tasks if t.status == TaskStatus.CANDIDATE]

    fixed_appointments = fixture_repo.get_fixed_appointments(rep_id, plan_date)

    suggested_tasks, remaining_minutes = allocate_daily_capacity(
        still_pending, fixed_appointments, available_minutes
    )

    visit_sequence = build_visit_sequence(suggested_tasks, fixed_appointments)

    return DailyPlan(
        rep_id=rep_id, plan_date=plan_date, available_minutes=available_minutes,
        fixed_appointments=fixed_appointments, candidate_tasks=candidate_tasks,
        suggested_tasks=suggested_tasks, remaining_minutes=remaining_minutes,
        visit_sequence=visit_sequence,
    )
