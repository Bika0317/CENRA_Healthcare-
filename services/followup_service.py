"""
後續追蹤事項轉候選任務。

「結果回報」頁勾選「需要後續追蹤」時填的 next_step/next_date，原本只是寫進
task_outcomes 表，沒有任何程序讀它、也不會再出現在任何畫面上——填了就石沉大海。
這裡補上：到了 next_date（或已經過期）當天，build_daily_plan() 會把它轉成一張
新的候選任務，重新出現在「今日任務」頁，業務可以像對待其他候選任務一樣審核它
（採納/修改/延後/拒絕）。

不算 SPEC 既定的三個規則引擎（攻/守/增）之一——這是額外補的功能，觸發規則
很單純（到期就轉任務），不像 engines/ 那樣依訂單/互動證據判斷資格，所以刻意
放在獨立檔案，不跟 engines/attack.py 等混在一起。
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime

from domain.models import Evidence, EvidenceStrength, Task, TaskStatus

FOLLOWUP_MODEL_VERSION = "followup-v1"
# 後續追蹤不是引擎依訊號/商業價值/急迫性等公式算出來的分數，是業務自己當初
# 判斷「這件事之後要追」——給一個中等偏高的固定分數，不假裝套用 services/scoring.py
# 那套百分位公式（那套公式是設計來讓同一批候選互相比較用的，後續追蹤沒有
# 「同一批」的概念，套用會誤導）。
FOLLOWUP_VALUE_SCORE = 65.0


def _followup_task_id(original_task_id: str) -> tuple[str, str]:
    """跟原任務綁定、不含日期的 id——同一個後續追蹤事項只會被轉成任務一次，
    不會因為業務隔好幾天才打開 app、每天都重新生一張。"""
    digest = hashlib.sha1(f"FOLLOWUP|{original_task_id}".encode()).hexdigest()[:12]
    return f"TASK-FU-{digest}", f"GEN-FU-{digest}"


def has_been_converted(task_repo, original_task_id: str) -> bool:
    """給「待追蹤事項」清單 UI 判斷：這筆後續追蹤是否已經被轉成過候選任務。"""
    task_id, _ = _followup_task_id(original_task_id)
    return task_repo.task_exists(task_id)


def generate_followup_tasks(task_repo, rep_id: str, plan_date: date) -> list[Task]:
    """回傳這位業務今天到期（含逾期）、且還沒被轉成任務過的後續追蹤候選任務。
    是否「已經轉過」交給呼叫端的 task_repo.save_tasks() 依 generation_key 判斷
    （跟 attack/defend/grow 三個引擎共用同一套 idempotent 寫入邏輯），這裡不用
    自己再查一次。"""
    due = [
        (task, outcome)
        for task, outcome in task_repo.get_all_followups(rep_id)
        if outcome.next_date <= plan_date
    ]
    tasks = []
    for original, outcome in due:
        task_id, generation_key = _followup_task_id(original.task_id)
        objective = outcome.next_step or "確認後續進度"
        tasks.append(Task(
            task_id=task_id, generation_key=generation_key, generated_at=datetime.now(),
            task_date=plan_date, rep_id=rep_id,
            target_type=original.target_type, target_id=original.target_id,
            target_name=original.target_name, task_type=original.task_type,
            title=f"後續追蹤：{original.target_name}",
            why_now=f"先前任務結果回報時標記需要追蹤（預計 {outcome.next_date}）：{objective}",
            objective=objective, action_mode=original.action_mode,
            estimated_minutes=original.estimated_minutes,
            signal_score=FOLLOWUP_VALUE_SCORE, business_value_score=FOLLOWUP_VALUE_SCORE,
            urgency_score=FOLLOWUP_VALUE_SCORE, evidence_score=FOLLOWUP_VALUE_SCORE,
            strategy_fit_score=FOLLOWUP_VALUE_SCORE, cost_penalty=original.cost_penalty,
            value_score=FOLLOWUP_VALUE_SCORE, evidence_strength=EvidenceStrength.MEDIUM,
            uncertainty_note="這是先前任務標記的後續追蹤事項，分數為固定值，不是引擎規則算出來的，實際優先順序請自行判斷。",
            data_updated_at=outcome.completed_at, lat=original.lat, lon=original.lon,
            model_version=FOLLOWUP_MODEL_VERSION, status=TaskStatus.CANDIDATE,
            evidences=[Evidence(
                evidence_id=f"{task_id}-followup", task_id=task_id, code="followup_next_step",
                label="後續追蹤事項", display_value=objective, source_type="outcome",
                source_id=original.task_id, occurred_at=outcome.completed_at,
                strength=EvidenceStrength.MEDIUM,
            )],
        ))
    return tasks
