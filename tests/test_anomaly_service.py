"""覆蓋 services/anomaly_service.py 的統計離群標記：批次太小不判斷、批次夠大時
能抓出刻意做出來的極端值。"""
from __future__ import annotations

from dataclasses import replace

from services.anomaly_service import MIN_BATCH_SIZE, flag_statistical_outliers
from services.daily_plan_service import build_daily_plan


def test_batch_smaller_than_minimum_flags_nothing(demo_date, fixture_repo, task_repo):
    tasks = build_daily_plan("L100", demo_date, 240, fixture_repo, task_repo).candidate_tasks[:MIN_BATCH_SIZE - 1]
    assert flag_statistical_outliers(tasks) == set()


def test_extreme_value_gets_flagged_in_a_large_enough_batch(demo_date, fixture_repo, task_repo):
    plan = build_daily_plan("L100", demo_date, 240, fixture_repo, task_repo)
    tasks = list(plan.candidate_tasks)
    assert len(tasks) >= MIN_BATCH_SIZE

    # 把其中一張任務的分項分數全部推到極端值，其餘任務維持不動，製造一個
    # 明顯偏離同批其他候選的樣本。
    extreme = replace(
        tasks[0], signal_score=999.0, business_value_score=999.0, urgency_score=999.0,
        evidence_score=999.0, strategy_fit_score=999.0, cost_penalty=-999.0,
    )
    batch = [extreme] + tasks[1:]

    outliers = flag_statistical_outliers(batch)
    assert extreme.task_id in outliers


def test_deterministic_across_repeated_calls(demo_date, fixture_repo, task_repo):
    tasks = build_daily_plan("L100", demo_date, 240, fixture_repo, task_repo).candidate_tasks
    assert flag_statistical_outliers(tasks) == flag_statistical_outliers(tasks)
