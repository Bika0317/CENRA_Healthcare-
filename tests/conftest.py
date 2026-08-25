"""共用測試 fixtures：固定 clock、tmp sqlite path，避免依賴系統日期或亂數。"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from domain.models import (
    ActionMode, Evidence, EvidenceStrength, Task, TargetType, TaskStatus, TaskType,
)

DEMO_DATE = date(2026, 8, 25)


def make_task(**overrides) -> Task:
    defaults = dict(
        task_id="T-TEST-1", generation_key="GEN-TEST-1",
        generated_at=datetime(2026, 8, 25, 8, 0), task_date=DEMO_DATE,
        rep_id="R100", target_type=TargetType.ACCOUNT, target_id="A001", target_name="測試診所",
        task_type=TaskType.DEFEND, title="測試任務", why_now="測試原因", objective="確認狀況",
        action_mode=ActionMode.VISIT, estimated_minutes=45,
        signal_score=70.0, business_value_score=60.0, urgency_score=50.0, evidence_score=70.0,
        strategy_fit_score=50.0, cost_penalty=6.0, value_score=55.0,
        evidence_strength=EvidenceStrength.MEDIUM, uncertainty_note="原因需業務確認",
        data_updated_at=datetime(2026, 8, 24, 9, 0), lat=25.03, lon=121.56,
        status=TaskStatus.CANDIDATE,
        evidences=[Evidence(
            evidence_id="EV-1", task_id="T-TEST-1", code="defend_revenue_decline",
            label="訂單金額連續下降", display_value="近兩期下降 30%", source_type="order",
            source_id="O-1", occurred_at=datetime(2026, 8, 20, 10, 0), strength=EvidenceStrength.MEDIUM,
        )],
    )
    defaults.update(overrides)
    return Task(**defaults)


@pytest.fixture
def demo_date() -> date:
    return DEMO_DATE


@pytest.fixture
def task_repo(tmp_path):
    from data.task_repository import TaskRepository
    repo = TaskRepository(str(tmp_path / "test_mission.db"))
    yield repo
    repo.close()


@pytest.fixture
def fixture_repo():
    from data.fixture_repository import FixtureRepository
    return FixtureRepository(demo_cutoff=DEMO_DATE)
