def test_pytest_works():
    assert 1 + 1 == 2


def test_domain_imports():
    from domain.models import Task, DailyPlan, transition  # noqa: F401
    from domain.reason_codes import REASON_CODES  # noqa: F401
    assert True
