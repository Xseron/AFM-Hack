from fastapi.testclient import TestClient

from aimw.api import create_app
from aimw.domain import ChannelReport, PostAssessment
from aimw.storage import Repository


class FakePipeline:
    async def analyze_channel(self, username):
        return ChannelReport(
            username=username, title="T", status="ok", risk_score=80,
            categories=["illegal_gambling"], explanation="ad",
            post_assessments=[PostAssessment(
                tg_message_id=1, categories=["illegal_gambling"], confidence=0.9,
                evidence_quotes=["казино"], explanation="ad", model_used="m",
            )],
        )


def _client(tmp_path):
    repo = Repository(f"sqlite:///{tmp_path/'t.db'}")
    return TestClient(create_app(repo, FakePipeline())), repo


def test_health(tmp_path):
    client, _ = _client(tmp_path)
    assert client.get("/health").json() == {"status": "ok"}


def test_post_channels_returns_reports(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.post("/channels", json={"channels": ["chan1"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["username"] == "chan1"
    assert body[0]["risk_score"] == 80
    assert body[0]["categories"] == ["illegal_gambling"]


def test_post_then_get_by_username(tmp_path):
    client, _ = _client(tmp_path)
    client.post("/channels", json={"channels": ["chan1"]})
    resp = client.get("/channels/chan1")
    assert resp.status_code == 200
    assert resp.json()["risk_score"] == 80


def test_get_missing_returns_404(tmp_path):
    client, _ = _client(tmp_path)
    assert client.get("/channels/nope").status_code == 404


def test_list_sorted_by_risk(tmp_path):
    client, repo = _client(tmp_path)
    repo.save_report(ChannelReport("low", "L", "ok", 10, [], "x", []))
    repo.save_report(ChannelReport("high", "H", "ok", 90, [], "x", []))
    usernames = [r["username"] for r in client.get("/channels").json()]
    assert usernames[0] == "high"
