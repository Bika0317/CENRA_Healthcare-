"""覆蓋 SPEC §10 / §16.2 的引擎規則：資格條件、觸發門檻、禁用語句。"""
from __future__ import annotations

from datetime import date

import pytest

from domain.models import ActionMode, TaskType
from engines import attack, defend, grow

DEMO_DATE = date(2026, 8, 25)

BANNED_PHRASES = ["已被競品入侵", "competitor_pressure", "已確認競品"]


@pytest.fixture
def fixture_repo():
    from data.fixture_repository import FixtureRepository
    return FixtureRepository(demo_cutoff=DEMO_DATE)


def test_attack_excludes_low_fit_prospect(fixture_repo):
    candidates = attack.generate_candidates(fixture_repo, "L100", DEMO_DATE)
    ids = [c.target_id for c in candidates]
    assert "P003" not in ids  # fit_band=low


def test_attack_excludes_prospect_with_fixed_appointment(fixture_repo):
    candidates = attack.generate_candidates(fixture_repo, "L100", DEMO_DATE)
    ids = [c.target_id for c in candidates]
    assert "P004" not in ids  # 已有固定預約


def test_attack_candidates_are_phone_mode(fixture_repo):
    candidates = attack.generate_candidates(fixture_repo, "L100", DEMO_DATE)
    assert candidates
    assert all(c.action_mode == ActionMode.PHONE for c in candidates)
    assert all(c.estimated_minutes == 20 for c in candidates)


def test_defend_requires_strong_trigger_or_two_general_signals(fixture_repo):
    candidates = defend.generate_candidates(fixture_repo, "L100", DEMO_DATE)
    ids = [c.target_id for c in candidates]
    # A007-A010 是穩定填充帳戶，不應觸發任何守任務
    for filler_id in ("A007", "A008", "A009", "A010"):
        assert filler_id not in ids


def test_defend_without_direct_competitor_evidence_uses_uncertain_wording(fixture_repo):
    candidates = defend.generate_candidates(fixture_repo, "L100", DEMO_DATE)
    a001 = next(c for c in candidates if c.target_id == "A001")  # 無競品文字的強觸發情境
    assert "已被競品入侵" not in a001.why_now
    assert "已被競品入侵" not in a001.uncertainty_note
    assert not any(e.code == "defend_competitor_mentioned" for e in a001.evidences)


def test_defend_with_direct_competitor_evidence_includes_it(fixture_repo):
    candidates = defend.generate_candidates(fixture_repo, "L100", DEMO_DATE)
    a005 = next(c for c in candidates if c.target_id == "A005")
    assert any(e.code == "defend_competitor_mentioned" for e in a005.evidences)


def test_no_banned_phrases_in_any_engine_output(fixture_repo):
    all_candidates = (
        attack.generate_candidates(fixture_repo, "L100", DEMO_DATE)
        + defend.generate_candidates(fixture_repo, "L100", DEMO_DATE)
        + grow.generate_candidates(fixture_repo, "L100", DEMO_DATE)
    )
    for c in all_candidates:
        text = " ".join([c.title, c.why_now, c.uncertainty_note] + [e.display_value for e in c.evidences])
        for phrase in BANNED_PHRASES:
            assert phrase not in text, f"{c.target_id} 出現禁用語句：{phrase}"


def test_grow_requires_at_least_one_signal(fixture_repo):
    candidates = grow.generate_candidates(fixture_repo, "L100", DEMO_DATE)
    ids = [c.target_id for c in candidates]
    for filler_id in ("A007", "A008", "A009", "A010"):
        assert filler_id not in ids


def test_grow_a003_missing_coords_scenario(fixture_repo):
    candidates = grow.generate_candidates(fixture_repo, "L100", DEMO_DATE)
    a003 = next(c for c in candidates if c.target_id == "A003")
    assert a003.lat is None and a003.lon is None
    assert a003.has_distance_data is False


def test_engine_candidates_carry_at_most_three_evidences(fixture_repo):
    all_candidates = (
        attack.generate_candidates(fixture_repo, "L100", DEMO_DATE)
        + defend.generate_candidates(fixture_repo, "L100", DEMO_DATE)
        + grow.generate_candidates(fixture_repo, "L100", DEMO_DATE)
    )
    for c in all_candidates:
        assert len(c.evidences) <= 3
