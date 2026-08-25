"""
統一任務價值分數（SPEC §11）：
value_score = 30% 任務訊號 + 25% 相對商業價值 + 20% 急迫性 + 15% 證據強度 + 10% 策略適配度 − 執行成本懲罰
clamp 到 0–100。任務訊號與商業價值只在「同一任務類型的同批次候選群體」內做百分位轉換。
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime

from domain.models import ActionMode, Task, TaskStatus, TaskType
from engines.candidate import Candidate

VALUE_SCORE_THRESHOLD = 45
EVIDENCE_SCORE_THRESHOLD = 40

_WEIGHTS = dict(signal=0.30, business_value=0.25, urgency=0.20, evidence=0.15, strategy_fit=0.10)


def _percentile_scores(raw_values: list[float]) -> list[float]:
    """單一候選時回傳 70（避免自動變 100）；否則依排名轉成 0-100 百分位。"""
    n = len(raw_values)
    if n == 1:
        return [70.0]
    order = sorted(range(n), key=lambda i: raw_values[i])
    ranks = [0] * n
    for rank, idx in enumerate(order):
        ranks[idx] = rank
    return [100.0 * r / (n - 1) for r in ranks]


def _cost_penalty(candidate: Candidate) -> float:
    if candidate.action_mode == ActionMode.PHONE:
        return 2.0
    if not candidate.has_distance_data:
        return 12.0
    # 簡化版：沒有真實路網距離，先假設實訪交通時間落在 <=30 分鐘這一級（SPEC §11.2）。
    return 6.0


def _make_task_id(rep_id: str, target_id: str, task_type: TaskType, task_date: date) -> tuple[str, str]:
    key_str = f"{rep_id}|{target_id}|{task_type.value}|{task_date.isoformat()}"
    digest = hashlib.sha1(key_str.encode()).hexdigest()[:12]
    task_id = f"TASK-{digest}"
    generation_key = f"GEN-{digest}"
    return task_id, generation_key


def score_candidates(candidates: list[Candidate], rep_id: str, task_date: date) -> list[Task]:
    """把同一批次的候選（可能混合攻/守/增）轉成正式 Task，含百分位評分與 clamp。"""
    tasks: list[Task] = []
    by_type: dict[TaskType, list[Candidate]] = {}
    for c in candidates:
        by_type.setdefault(c.task_type, []).append(c)

    for task_type, group in by_type.items():
        signal_scores = _percentile_scores([c.raw_signal for c in group])
        value_scores = _percentile_scores([c.raw_business_value for c in group])

        for candidate, signal_score, business_value_score in zip(group, signal_scores, value_scores):
            cost_penalty = _cost_penalty(candidate)
            raw = (
                _WEIGHTS["signal"] * signal_score
                + _WEIGHTS["business_value"] * business_value_score
                + _WEIGHTS["urgency"] * candidate.urgency_score
                + _WEIGHTS["evidence"] * candidate.evidence_score
                + _WEIGHTS["strategy_fit"] * candidate.strategy_fit_score
                - cost_penalty
            )
            value_score = max(0.0, min(100.0, raw))

            if value_score < VALUE_SCORE_THRESHOLD or candidate.evidence_score < EVIDENCE_SCORE_THRESHOLD:
                continue  # SPEC §11.3 候選門檻，未達標不進今日候選清單

            task_id, generation_key = _make_task_id(rep_id, candidate.target_id, task_type, task_date)
            evidences = list(candidate.evidences)
            for e in evidences:
                e.task_id = task_id

            tasks.append(Task(
                task_id=task_id, generation_key=generation_key, generated_at=datetime.now(),
                task_date=task_date, rep_id=rep_id, target_type=candidate.target_type,
                target_id=candidate.target_id, target_name=candidate.target_name,
                task_type=task_type, title=candidate.title, why_now=candidate.why_now,
                objective=candidate.objective, action_mode=candidate.action_mode,
                estimated_minutes=candidate.estimated_minutes,
                signal_score=signal_score, business_value_score=business_value_score,
                urgency_score=candidate.urgency_score, evidence_score=candidate.evidence_score,
                strategy_fit_score=candidate.strategy_fit_score, cost_penalty=cost_penalty,
                value_score=value_score, evidence_strength=candidate.evidence_strength,
                uncertainty_note=candidate.uncertainty_note, data_updated_at=candidate.data_updated_at,
                lat=candidate.lat, lon=candidate.lon, status=TaskStatus.CANDIDATE,
                evidences=evidences,
            ))

    return sorted(tasks, key=lambda t: t.value_score, reverse=True)
