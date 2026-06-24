import csv

from invistigator.schemas import ProfileData
from invistigator.storage import append_row
from invistigator import trigger


def test_append_row_writes_header_once(tmp_path):
    path = str(tmp_path / "out.csv")
    append_row(ProfileData(username="a", telegram_links=["@x", "@y"]), path)
    append_row(ProfileData(username="b", status="not_found"), path)

    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [r["username"] for r in rows] == ["a", "b"]
    assert rows[0]["telegram_links"] == "@x, @y"
    assert rows[1]["status"] == "not_found"


def test_post_channels_empty_is_noop():
    assert trigger.post_channels([], "http://localhost:8000") is False


def test_post_channels_sends_payload(monkeypatch):
    captured = {}

    class Resp:
        def raise_for_status(self):
            pass

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return Resp()

    monkeypatch.setattr(trigger.httpx, "post", fake_post)
    assert trigger.post_channels(["@chan"], "http://localhost:8000/") is True
    assert captured["url"] == "http://localhost:8000/channels"
    assert captured["json"] == {"channels": ["@chan"]}


def test_post_channels_graceful_fail(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(trigger.httpx, "post", boom)
    assert trigger.post_channels(["@chan"], "http://localhost:8000") is False
