from aimw.domain import ChannelReport, PostAssessment
from aimw.storage import Repository


def _report(username, score):
    pa = PostAssessment(
        tg_message_id=1, categories=["illegal_gambling"], confidence=0.9,
        evidence_quotes=["казино"], explanation="ad", model_used="m",
    )
    return ChannelReport(
        username=username, title=username.upper(), status="ok", risk_score=score,
        categories=["illegal_gambling"], explanation="x", post_assessments=[pa],
    )


def test_save_and_get(tmp_path):
    repo = Repository(f"sqlite:///{tmp_path/'t.db'}")
    repo.save_report(_report("chan1", 80))
    got = repo.get_report("chan1")
    assert got is not None
    assert got.risk_score == 80
    assert got.post_assessments[0].categories == ["illegal_gambling"]


def test_save_is_upsert(tmp_path):
    repo = Repository(f"sqlite:///{tmp_path/'t.db'}")
    repo.save_report(_report("chan1", 10))
    repo.save_report(_report("chan1", 90))
    got = repo.get_report("chan1")
    assert got.risk_score == 90
    assert len(got.post_assessments) == 1  # replaced, not duplicated


def test_list_sorted_by_risk(tmp_path):
    repo = Repository(f"sqlite:///{tmp_path/'t.db'}")
    repo.save_report(_report("low", 10))
    repo.save_report(_report("high", 90))
    reports = repo.list_reports(sort_by_risk=True)
    assert [r.username for r in reports] == ["high", "low"]


def test_get_missing_returns_none(tmp_path):
    repo = Repository(f"sqlite:///{tmp_path/'t.db'}")
    assert repo.get_report("nope") is None
