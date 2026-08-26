"""
統一任務價值分數（SPEC §11）：
value_score = 30% 任務訊號 + 25% 相對商業價值 + 20% 急迫性 + 15% 證據強度 + 10% 策略適配度 − 執行成本懲罰
clamp 到 0–100。任務訊號與商業價值只在「同一任務類型的同批次候選群體」內做百分位轉換。
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime

from domain.geo import haversine_km
from domain.models import ActionMode, Task, TaskStatus, TaskType
from engines.candidate import Candidate

VALUE_SCORE_THRESHOLD = 45
EVIDENCE_SCORE_THRESHOLD = 40

# SPEC 沒有規定路網速度，這是唯一需要自己假設的數字：郊區/市區混合車程的粗估均速，
# 只用來把 haversine 直線距離換算成分鐘數，分到 SPEC §11.2 的三個等級，不宣稱是真實路網時間。
_AVG_TRAVEL_SPEED_KMH = 25.0

_WEIGHTS = dict(signal=0.30, business_value=0.25, urgency=0.20, evidence=0.15, strategy_fit=0.10)


def _percentile_scores(raw_values: list[float]) -> list[float]:
    """單一候選時回傳 70（避免自動變 100）；否則依排名轉成 0-100 百分位。
    同分用平均名次（fractional ranking），避免兩個原始分數幾乎相同的候選被
    百分位硬拆成 0 和 100 這種不合理的極端值（n 很小時尤其明顯）。"""
    n = len(raw_values)
    if n == 1:
        return [70.0]
    sorted_vals = sorted(raw_values)
    scores = []
    for v in raw_values:
        equal_positions = [i for i, sv in enumerate(sorted_vals) if sv == v]
        avg_rank = sum(equal_positions) / len(equal_positions)
        scores.append(100.0 * avg_rank / (n - 1))
    return scores


def _cost_penalty(candidate: Candidate, rep_home_lat: float | None, rep_home_lon: float | None) -> float:
    """SPEC §11.2：phone=2；visit 依粗估交通分鐘數分三級（<=30/31-60/>60）；
    缺距離資料（沒有業務駐地座標或候選本身沒座標）＝12。「額外準備成本 0-5」
    SPEC 沒定義判斷依據，這裡不硬編一個數字，維持 0（不納入合計）。"""
    if candidate.action_mode == ActionMode.PHONE:
        return 2.0
    if not candidate.has_distance_data or rep_home_lat is None or rep_home_lon is None:
        return 12.0
    distance_km = haversine_km(rep_home_lat, rep_home_lon, candidate.lat, candidate.lon)
    travel_minutes = distance_km / _AVG_TRAVEL_SPEED_KMH * 60
    if travel_minutes <= 30:
        return 6.0
    if travel_minutes <= 60:
        return 10.0
    return 15.0


def _make_task_id(rep_id: str, target_id: str, task_type: TaskType, task_date: date) -> tuple[str, str]:
    key_str = f"{rep_id}|{target_id}|{task_type.value}|{task_date.isoformat()}"
    digest = hashlib.sha1(key_str.encode()).hexdigest()[:12]
    task_id = f"TASK-{digest}"
    generation_key = f"GEN-{digest}"
    return task_id, generation_key


def score_candidates(candidates: list[Candidate], rep_id: str, task_date: date,
                      rep_home_lat: float | None = None, rep_home_lon: float | None = None) -> list[Task]:
    """把同一批次的候選（可能混合攻/守/增）轉成正式 Task，含百分位評分與 clamp。
    rep_home_lat/lon 用來估算 visit 任務的交通成本懲罰（SPEC §11.2），不提供時
    一律視為缺距離資料（cost_penalty=12）。"""
    tasks: list[Task] = []
    by_type: dict[TaskType, list[Candidate]] = {}
    for c in candidates:
        by_type.setdefault(c.task_type, []).append(c)

    for task_type, group in by_type.items():
        signal_scores = _percentile_scores([c.raw_signal for c in group])
        value_scores = _percentile_scores([c.raw_business_value for c in group])

        for candidate, signal_score, business_value_score in zip(group, signal_scores, value_scores):
            cost_penalty = _cost_penalty(candidate, rep_home_lat, rep_home_lon)
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
                # 引擎產生的 evidence_id 只有「帳戶＋規則代碼」（例如 EV-A008-defend-core），
                # 沒有日期資訊；task_evidence.evidence_id 是全表 PRIMARY KEY，同一帳戶在
                # 不同天觸發同一條規則就會撞到同一個 evidence_id，INSERT 直接 IntegrityError
                # ——這在「延後任務隔天回到候選」這條路徑上幾乎必定發生（帳戶資料沒變，
                # 隔天多半還是會再次觸發同一條規則）。task_id 本身已經把 rep/target/type/date
                # 都編碼進去，拿它當 evidence_id 的前綴就能讓每次生成天然全域唯一。
                e.evidence_id = f"{task_id}-{e.code}"

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
