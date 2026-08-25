"""
Engine 內部輸出的候選任務原始訊號（尚未經過百分位轉換，還不是最終 Task）。
scoring.py 會把同一批次、同一 task_type 的 Candidate 轉成正式的 domain.models.Task。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from domain.models import ActionMode, Evidence, EvidenceStrength, TargetType, TaskType


@dataclass
class Candidate:
    target_type: TargetType
    target_id: str
    target_name: str
    task_type: TaskType
    raw_signal: float              # 0-100，同批次候選群體內才有比較意義
    raw_business_value: float      # 0-100，account 用近180天營收百分位、prospect 用 fit/value band 映射
    urgency_score: float           # 0 / 50 / 100
    evidence_score: float          # 40 / 70 / 100（對應 weak/medium/strong）
    strategy_fit_score: float      # 0 / 50 / 100
    action_mode: ActionMode
    estimated_minutes: int
    objective: str
    why_now: str
    title: str
    uncertainty_note: str
    evidence_strength: EvidenceStrength
    evidences: list[Evidence]
    lat: float | None
    lon: float | None
    data_updated_at: datetime
    has_distance_data: bool = True
    generation_key_suffix: str = ""  # 通常用 target_id，特殊情況可覆寫
