import json
from datetime import datetime
from types import SimpleNamespace

from aimw.analyzer import Analyzer
from aimw.domain import Post


class FakeCompletions:
    def __init__(self, content):
        self._content = content
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        msg = SimpleNamespace(content=self._content)
        choice = SimpleNamespace(message=msg)
        return SimpleNamespace(choices=[choice])


class FakeClient:
    def __init__(self, content):
        self.chat = SimpleNamespace(completions=FakeCompletions(content))


def _settings():
    return SimpleNamespace(
        openrouter_text_model="text-model",
        openrouter_vision_model="vision-model",
    )


def test_analyze_post_parses_json():
    content = json.dumps({
        "categories": ["illegal_gambling", "bogus"],
        "confidence": 0.9,
        "evidence_quotes": ["играй в казино"],
        "explanation": "реклама казино",
    })
    client = FakeClient(content)
    analyzer = Analyzer(client, _settings())
    post = Post(tg_message_id=7, date=datetime(2026, 1, 1), text="казино")
    result = analyzer.analyze_post(post)
    assert result.tg_message_id == 7
    assert result.categories == ["illegal_gambling"]  # bogus dropped
    assert result.confidence == 0.9
    assert result.model_used == "text-model"


def test_text_only_uses_text_model():
    client = FakeClient(json.dumps({"categories": [], "confidence": 0.0,
                                    "evidence_quotes": [], "explanation": "ok"}))
    analyzer = Analyzer(client, _settings())
    post = Post(tg_message_id=1, date=datetime(2026, 1, 1), text="hi")
    analyzer.analyze_post(post)
    assert client.chat.completions.last_kwargs["model"] == "text-model"


def test_post_with_image_uses_vision_model(tmp_path):
    img = tmp_path / "a.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0fake")
    client = FakeClient(json.dumps({"categories": [], "confidence": 0.0,
                                    "evidence_quotes": [], "explanation": "ok"}))
    analyzer = Analyzer(client, _settings())
    post = Post(tg_message_id=2, date=datetime(2026, 1, 1), text="hi",
                media_paths=[str(img)])
    analyzer.analyze_post(post)
    assert client.chat.completions.last_kwargs["model"] == "vision-model"


def test_invalid_json_returns_safe_assessment():
    client = FakeClient("not json at all")
    analyzer = Analyzer(client, _settings())
    post = Post(tg_message_id=3, date=datetime(2026, 1, 1), text="hi")
    result = analyzer.analyze_post(post)
    assert result.categories == []
    assert result.confidence == 0.0
