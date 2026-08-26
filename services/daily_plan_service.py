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

# 已經被業務決定「今天要花這些分鐘」的狀態：即使任務本身已完成/取消，時間也已經花掉了，
# 不該被容量分配演算法當成「還沒用」而遞補別的候選進來。REJECTED／DEFERRED 不在這裡，
# 因為那代表業務決定「今天不做」，分鐘數本來就該釋出。
_COMMITTED_STATUSES = (
    TaskStatus.ACCEPTED, TaskStatus.MODIFIED, TaskStatus.SCHEDULED,
    TaskStatus.COMPLETED, TaskStatus.NOT_COMPLETED, TaskStatus.CANCELLED,
)


def build_daily_plan(rep_id: str, plan_date: date, available_minutes: int,
                      fixture_repo, task_repo) -> DailyPlan:
    """
    0. 把過了 deferred_to 的延後任務轉回候選 -> 1. 三引擎各自產生新候選 -> 2. 統一評分
    （含依業務駐地座標估算的交通成本懲罰）-> 3. 存入 task_repository（idempotent，
    同 generation_key 不重複寫入）-> 4. 取回今天全部候選任務（含歷史已存在的）
    -> 5. 固定預約 + 容量分配 + 三類最低配額 -> 6. 依固定預約切時段的 nearest-neighbor 點位順序。
    """
    task_repo.resurface_deferred_tasks(rep_id, plan_date)

    rep = fixture_repo.get_rep(rep_id)
    rep_home_lat, rep_home_lon = rep.get("home_lat"), rep.get("home_lon")

    candidates = (
        attack.generate_candidates(fixture_repo, rep_id, plan_date)
        + defend.generate_candidates(fixture_repo, rep_id, plan_date)
        + grow.generate_candidates(fixture_repo, rep_id, plan_date)
    )
    new_tasks = score_candidates(candidates, rep_id, plan_date, rep_home_lat, rep_home_lon)
    if new_tasks:
        task_repo.save_tasks(new_tasks)

    # candidate_tasks 依契約（00_CONTRACTS.md）要含這批次「所有 status」，不是只有還沒審核的，
    # UI 才能顯示已採納/已排程/已完成的任務卡。容量分配只該從「還沒審核」的子集裡挑，
    # 已經審核過的任務不該被重新建議一次。
    candidate_tasks = task_repo.get_candidate_tasks(rep_id, plan_date)
    still_pending = [t for t in candidate_tasks if t.status == TaskStatus.CANDIDATE]

    # 已經被業務實際「排進今天」的任務（採納/修改採納/排入行程/完成/未完成/取消）就算離開
    # candidate 狀態，佔用的分鐘數也不該憑空釋出——不然使用者完成一張建議任務後，
    # allocate_daily_capacity() 會把它讓出來的容量塞給另一張全新候選遞補，讓「⭐建議」
    # 清單張數維持不變甚至變多，而不是像使用者預期的那樣單純減少。
    # 拒絕／延後則是業務明確決定「今天不做」，這份分鐘數才應該真的釋出讓別的候選遞補。
    committed_minutes = sum(
        t.estimated_minutes for t in candidate_tasks if t.status in _COMMITTED_STATUSES
    )
    effective_available_minutes = max(available_minutes - committed_minutes, 0)

    fixed_appointments = fixture_repo.get_fixed_appointments(rep_id, plan_date)

    suggested_tasks, remaining_minutes = allocate_daily_capacity(
        still_pending, fixed_appointments, effective_available_minutes
    )

    visit_sequence = build_visit_sequence(
        suggested_tasks, fixed_appointments, rep_home_lat, rep_home_lon
    )

    return DailyPlan(
        rep_id=rep_id, plan_date=plan_date, available_minutes=available_minutes,
        fixed_appointments=fixed_appointments, candidate_tasks=candidate_tasks,
        suggested_tasks=suggested_tasks, remaining_minutes=remaining_minutes,
        visit_sequence=visit_sequence,
    )
