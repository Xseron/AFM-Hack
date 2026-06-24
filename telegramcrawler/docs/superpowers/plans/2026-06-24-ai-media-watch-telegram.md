# AI Media Watch — Telegram Crawler & Risk Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python service that crawls Telegram channels, analyzes their content (text + images) for signs of illegal gambling, financial pyramids and fraud, and exposes explainable risk scores via REST API.

**Architecture:** FastAPI app with focused modules — `config`, `storage` (SQLAlchemy/SQLite), `prefilter` (RU+KZ lexicon/regex), `analyzer` (OpenRouter LLM + vision), `crawler` (Telethon), `scoring` (aggregation), and a `pipeline` orchestrator wired into `api`. Crawler and OpenRouter are mocked in tests; no real network in the test suite.

**Tech Stack:** Python 3.11+, FastAPI, Telethon, SQLAlchemy + SQLite, OpenRouter via `openai` SDK, Pydantic, pytest.

## Global Constraints

- Python 3.11+
- LLM and vision calls go through OpenRouter only: `openai` SDK with `base_url="https://openrouter.ai/api/v1"`, key from `OPENROUTER_API_KEY`. Model ids come from config (`OPENROUTER_TEXT_MODEL`, `OPENROUTER_VISION_MODEL`) — never hardcoded in logic.
- Telegram access via Telethon (MTProto user account): `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SESSION`.
- Lexicon and prompts are bilingual: Russian + Kazakh.
- Risk categories (exact keys): `illegal_gambling`, `financial_pyramid`, `guaranteed_income`, `aggressive_investment`, `referral_scheme`, `hidden_engagement`.
- Risk score range: integer 0–100.
- No real network in tests — mock Telethon and OpenRouter.
- TDD: failing test first, minimal implementation, commit per task.
- All source under `src/aimw/`, tests under `tests/`.

---

### Task 1: Project scaffolding & config

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `src/aimw/__init__.py`
- Create: `src/aimw/config.py`
- Create: `tests/__init__.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing (first task)
- Produces: `Settings` Pydantic model and `get_settings() -> Settings`. Fields: `telegram_api_id: int`, `telegram_api_hash: str`, `telegram_session: str`, `openrouter_api_key: str`, `openrouter_text_model: str`, `openrouter_vision_model: str`, `posts_per_channel: int = 50`, `database_url: str = "sqlite:///aimw.db"`, `risk_review_threshold: int = 50`.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "aimw"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "uvicorn>=0.29",
    "telethon>=1.34",
    "sqlalchemy>=2.0",
    "openai>=1.30",
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "httpx>=0.27"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 2: Create `.env.example`, `.gitignore`, empty `__init__.py` files**

`.env.example`:
```
TELEGRAM_API_ID=123456
TELEGRAM_API_HASH=your_hash
TELEGRAM_SESSION=aimw_session
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_TEXT_MODEL=anthropic/claude-3.5-haiku
OPENROUTER_VISION_MODEL=anthropic/claude-3.5-sonnet
POSTS_PER_CHANNEL=50
DATABASE_URL=sqlite:///aimw.db
RISK_REVIEW_THRESHOLD=50
```

`.gitignore`:
```
__pycache__/
*.pyc
.env
*.session
*.db
.pytest_cache/
*.egg-info/
media/
```

Create empty `src/aimw/__init__.py` and `tests/__init__.py`.

- [ ] **Step 3: Write the failing test**

`tests/test_config.py`:
```python
from aimw.config import Settings


def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "111")
    monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
    monkeypatch.setenv("TELEGRAM_SESSION", "sess")
    monkeypatch.setenv("OPENROUTER_API_KEY", "key")
    monkeypatch.setenv("OPENROUTER_TEXT_MODEL", "text-model")
    monkeypatch.setenv("OPENROUTER_VISION_MODEL", "vision-model")
    s = Settings()
    assert s.telegram_api_id == 111
    assert s.openrouter_text_model == "text-model"
    assert s.posts_per_channel == 50
    assert s.risk_review_threshold == 50
```

- [ ] **Step 4: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aimw.config'`

- [ ] **Step 5: Write minimal implementation**

`src/aimw/config.py`:
```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_api_id: int
    telegram_api_hash: str
    telegram_session: str
    openrouter_api_key: str
    openrouter_text_model: str
    openrouter_vision_model: str
    posts_per_channel: int = 50
    database_url: str = "sqlite:///aimw.db"
    risk_review_threshold: int = 50


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 6: Install deps and run test to verify it passes**

Run: `pip install -e ".[dev]"` then `python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .env.example .gitignore src/aimw tests
git commit -m "feat: project scaffolding and config"
```

---

### Task 2: Domain types & risk categories

**Files:**
- Create: `src/aimw/domain.py`
- Test: `tests/test_domain.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `RISK_CATEGORIES: list[str]` — the six exact category keys.
  - `Post` dataclass: `tg_message_id: int`, `date: datetime`, `text: str`, `media_paths: list[str]` (default empty).
  - `PostAssessment` dataclass: `tg_message_id: int`, `categories: list[str]`, `confidence: float`, `evidence_quotes: list[str]`, `explanation: str`, `model_used: str`.
  - `ChannelReport` dataclass: `username: str`, `title: str`, `status: str`, `risk_score: int`, `categories: list[str]`, `explanation: str`, `post_assessments: list[PostAssessment]`, `error_reason: str | None = None`.

- [ ] **Step 1: Write the failing test**

`tests/test_domain.py`:
```python
from datetime import datetime

from aimw.domain import RISK_CATEGORIES, Post, PostAssessment, ChannelReport


def test_risk_categories_exact():
    assert RISK_CATEGORIES == [
        "illegal_gambling",
        "financial_pyramid",
        "guaranteed_income",
        "aggressive_investment",
        "referral_scheme",
        "hidden_engagement",
    ]


def test_dataclasses_construct():
    post = Post(tg_message_id=1, date=datetime(2026, 1, 1), text="hi")
    assert post.media_paths == []
    pa = PostAssessment(
        tg_message_id=1,
        categories=["illegal_gambling"],
        confidence=0.9,
        evidence_quotes=["играй в казино"],
        explanation="ad",
        model_used="m",
    )
    report = ChannelReport(
        username="c", title="C", status="ok", risk_score=80,
        categories=["illegal_gambling"], explanation="x",
        post_assessments=[pa],
    )
    assert report.error_reason is None
    assert report.post_assessments[0].confidence == 0.9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_domain.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aimw.domain'`

- [ ] **Step 3: Write minimal implementation**

`src/aimw/domain.py`:
```python
from dataclasses import dataclass, field
from datetime import datetime

RISK_CATEGORIES = [
    "illegal_gambling",
    "financial_pyramid",
    "guaranteed_income",
    "aggressive_investment",
    "referral_scheme",
    "hidden_engagement",
]


@dataclass
class Post:
    tg_message_id: int
    date: datetime
    text: str
    media_paths: list[str] = field(default_factory=list)


@dataclass
class PostAssessment:
    tg_message_id: int
    categories: list[str]
    confidence: float
    evidence_quotes: list[str]
    explanation: str
    model_used: str


@dataclass
class ChannelReport:
    username: str
    title: str
    status: str
    risk_score: int
    categories: list[str]
    explanation: str
    post_assessments: list[PostAssessment]
    error_reason: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_domain.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/aimw/domain.py tests/test_domain.py
git commit -m "feat: domain types and risk categories"
```

---

### Task 3: Prefilter lexicon (RU + KZ)

**Files:**
- Create: `src/aimw/prefilter.py`
- Test: `tests/test_prefilter.py`

**Interfaces:**
- Consumes: `RISK_CATEGORIES` from `aimw.domain`
- Produces:
  - `prefilter_text(text: str) -> dict` returning `{"is_suspicious": bool, "matched_categories": list[str], "matched_terms": list[str]}`.
  - `LEXICON: dict[str, list[str]]` mapping each risk category to lowercase RU+KZ terms/patterns.

- [ ] **Step 1: Write the failing test**

`tests/test_prefilter.py`:
```python
from aimw.prefilter import prefilter_text, LEXICON
from aimw.domain import RISK_CATEGORIES


def test_lexicon_covers_all_categories():
    assert set(LEXICON.keys()) == set(RISK_CATEGORIES)
    assert all(LEXICON[c] for c in RISK_CATEGORIES)


def test_gambling_ru_detected():
    r = prefilter_text("Лучшее онлайн казино, делай ставки и выигрывай!")
    assert r["is_suspicious"] is True
    assert "illegal_gambling" in r["matched_categories"]


def test_guaranteed_income_detected():
    r = prefilter_text("Гарантированный доход 100% каждый день")
    assert r["is_suspicious"] is True
    assert "guaranteed_income" in r["matched_categories"]


def test_referral_detected():
    r = prefilter_text("Приглашай друзей по реферальной ссылке и зарабатывай")
    assert "referral_scheme" in r["matched_categories"]


def test_kazakh_gambling_detected():
    r = prefilter_text("Ең жақсы онлайн казино, бәс тігіп ұтып ал")
    assert r["is_suspicious"] is True
    assert "illegal_gambling" in r["matched_categories"]


def test_clean_text_not_suspicious():
    r = prefilter_text("Сегодня хорошая погода, гуляли в парке с детьми")
    assert r["is_suspicious"] is False
    assert r["matched_categories"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_prefilter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aimw.prefilter'`

- [ ] **Step 3: Write minimal implementation**

`src/aimw/prefilter.py`:
```python
from aimw.domain import RISK_CATEGORIES

# Lowercase RU + KZ terms per category. Substring match on lowercased text.
LEXICON: dict[str, list[str]] = {
    "illegal_gambling": [
        "казино", "ставки", "ставка", "букмекер", "1xbet", "мостбет", "mostbet",
        "1вин", "1win", "слоты", "игровые автоматы", "бонус на депозит",
        "casino", "бәс тігу", "ойын автоматы", "ставкалар",
    ],
    "financial_pyramid": [
        "пирамида", "финансовая пирамида", "вложи и получи", "пассивный доход",
        "удвоим ваши деньги", "матрица", "млм", "mlm", "ақшаңды салып",
    ],
    "guaranteed_income": [
        "гарантированный доход", "гарантированная прибыль", "доход 100%",
        "без риска", "100% прибыль", "стабильный заработок", "кепілдендірілген табыс",
        "тәуекелсіз",
    ],
    "aggressive_investment": [
        "инвестируй сейчас", "успей вложить", "иксы", "x2 за день", "×2 за день",
        "крипта взлетит", "профит", "только сегодня вход", "инвестиция",
        "инвестициялаңыз",
    ],
    "referral_scheme": [
        "реферал", "реферальн", "приглашай друзей", "промокод", "по моей ссылке",
        "бонус за регистрацию", "достарыңды шақыр", "сілтеме",
    ],
    "hidden_engagement": [
        "пиши в личку", "в лс", "напиши мне", "закрытый канал", "переходи по ссылке",
        "доступ по запросу", "жекеге жаз", "жабық канал",
    ],
}


def prefilter_text(text: str) -> dict:
    low = (text or "").lower()
    matched_categories: list[str] = []
    matched_terms: list[str] = []
    for category in RISK_CATEGORIES:
        for term in LEXICON[category]:
            if term in low:
                matched_terms.append(term)
                if category not in matched_categories:
                    matched_categories.append(category)
    return {
        "is_suspicious": bool(matched_categories),
        "matched_categories": matched_categories,
        "matched_terms": matched_terms,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_prefilter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/aimw/prefilter.py tests/test_prefilter.py
git commit -m "feat: bilingual RU+KZ prefilter lexicon"
```

---

### Task 4: Scoring aggregation

**Files:**
- Create: `src/aimw/scoring.py`
- Test: `tests/test_scoring.py`

**Interfaces:**
- Consumes: `PostAssessment`, `RISK_CATEGORIES` from `aimw.domain`
- Produces: `aggregate(assessments: list[PostAssessment]) -> dict` returning `{"risk_score": int, "categories": list[str], "explanation": str}`. Score 0–100. Weights: `illegal_gambling`/`financial_pyramid` = 1.0, others = 0.7. Score = `min(100, round(100 * max over posts of (weight(cat) * confidence) ... )` combined with count — see implementation. Empty input → score 0, empty categories, explanation "Подозрительных постов не обнаружено.".

- [ ] **Step 1: Write the failing test**

`tests/test_scoring.py`:
```python
from aimw.domain import PostAssessment
from aimw.scoring import aggregate


def _pa(cats, conf):
    return PostAssessment(
        tg_message_id=1, categories=cats, confidence=conf,
        evidence_quotes=["q"], explanation="e", model_used="m",
    )


def test_empty_is_zero():
    r = aggregate([])
    assert r["risk_score"] == 0
    assert r["categories"] == []
    assert "не обнаружено" in r["explanation"]


def test_high_confidence_gambling_high_score():
    r = aggregate([_pa(["illegal_gambling"], 0.95)])
    assert r["risk_score"] >= 80
    assert "illegal_gambling" in r["categories"]


def test_low_weight_category_scores_lower_than_gambling():
    high = aggregate([_pa(["illegal_gambling"], 0.9)])["risk_score"]
    low = aggregate([_pa(["hidden_engagement"], 0.9)])["risk_score"]
    assert low < high


def test_more_suspicious_posts_increase_score():
    one = aggregate([_pa(["referral_scheme"], 0.6)])["risk_score"]
    many = aggregate([_pa(["referral_scheme"], 0.6) for _ in range(5)])["risk_score"]
    assert many > one


def test_score_capped_at_100():
    r = aggregate([_pa(["illegal_gambling"], 1.0) for _ in range(50)])
    assert r["risk_score"] == 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scoring.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aimw.scoring'`

- [ ] **Step 3: Write minimal implementation**

`src/aimw/scoring.py`:
```python
from aimw.domain import PostAssessment

_WEIGHTS = {
    "illegal_gambling": 1.0,
    "financial_pyramid": 1.0,
    "guaranteed_income": 0.7,
    "aggressive_investment": 0.7,
    "referral_scheme": 0.7,
    "hidden_engagement": 0.7,
}


def _weight(category: str) -> float:
    return _WEIGHTS.get(category, 0.7)


def aggregate(assessments: list[PostAssessment]) -> dict:
    if not assessments:
        return {
            "risk_score": 0,
            "categories": [],
            "explanation": "Подозрительных постов не обнаружено.",
        }

    peak = 0.0
    volume = 0.0
    categories: list[str] = []
    for a in assessments:
        post_peak = 0.0
        for cat in a.categories:
            w = _weight(cat)
            post_peak = max(post_peak, w * a.confidence)
            if cat not in categories:
                categories.append(cat)
        peak = max(peak, post_peak)
        volume += post_peak

    # Base from the single strongest signal, plus a bounded volume bonus.
    base = peak * 80.0
    bonus = min(20.0, volume * 5.0)
    score = int(min(100, round(base + bonus)))

    explanation = (
        f"Обнаружено {len(assessments)} подозрительных постов. "
        f"Категории: {', '.join(categories)}."
    )
    return {"risk_score": score, "categories": categories, "explanation": explanation}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_scoring.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/aimw/scoring.py tests/test_scoring.py
git commit -m "feat: channel risk score aggregation"
```

---

### Task 5: Analyzer (OpenRouter LLM + vision)

**Files:**
- Create: `src/aimw/analyzer.py`
- Test: `tests/test_analyzer.py`

**Interfaces:**
- Consumes: `Post`, `PostAssessment`, `RISK_CATEGORIES` from `aimw.domain`; `Settings` from `aimw.config`.
- Produces: `Analyzer` class.
  - `__init__(self, client, settings)` — `client` is an OpenAI-compatible client (injected for testing); `settings` provides model ids.
  - `analyze_post(self, post: Post) -> PostAssessment` — builds a chat completion request (text always; image_url content blocks for each media path when present, using the vision model), parses the JSON response into a `PostAssessment`. On any exception or invalid JSON, returns a `PostAssessment` with empty categories, confidence 0.0, explanation describing the failure.
  - Module function `build_client(settings) -> OpenAI` constructing the real OpenRouter client (not exercised in tests).

The LLM is instructed to return JSON: `{"categories": [...], "confidence": 0..1, "evidence_quotes": [...], "explanation": "..."}`. Categories must be a subset of `RISK_CATEGORIES`; unknown values are dropped during parsing.

- [ ] **Step 1: Write the failing test**

`tests/test_analyzer.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_analyzer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aimw.analyzer'`

- [ ] **Step 3: Write minimal implementation**

`src/aimw/analyzer.py`:
```python
import base64
import json
import os

from openai import OpenAI

from aimw.domain import Post, PostAssessment, RISK_CATEGORIES

_SYSTEM_PROMPT = (
    "Ты модератор контента. Анализируй пост Telegram-канала (текст на русском или "
    "казахском, возможно с изображением) на признаки незаконного игорного бизнеса, "
    "финансовых пирамид и мошенничества. Верни СТРОГО JSON без пояснений вида: "
    '{"categories": [...], "confidence": 0..1, "evidence_quotes": [...], '
    '"explanation": "..."}. Допустимые категории: ' + ", ".join(RISK_CATEGORIES) + ". "
    "evidence_quotes — дословные цитаты из поста. explanation — кратко по-русски."
)


def build_client(settings) -> OpenAI:
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
    )


def _image_block(path: str) -> dict:
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{data}"},
    }


class Analyzer:
    def __init__(self, client, settings):
        self._client = client
        self._settings = settings

    def analyze_post(self, post: Post) -> PostAssessment:
        has_media = bool(post.media_paths)
        model = (
            self._settings.openrouter_vision_model
            if has_media
            else self._settings.openrouter_text_model
        )
        content: list[dict] = [{"type": "text", "text": post.text or "(пустой текст)"}]
        for path in post.media_paths:
            if os.path.exists(path):
                content.append(_image_block(path))

        try:
            resp = self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": content},
                ],
            )
            raw = resp.choices[0].message.content
            return self._parse(post, raw, model)
        except Exception as exc:  # noqa: BLE001 - never break the batch
            return PostAssessment(
                tg_message_id=post.tg_message_id, categories=[], confidence=0.0,
                evidence_quotes=[], explanation=f"Ошибка анализа: {exc}",
                model_used=model,
            )

    def _parse(self, post: Post, raw: str, model: str) -> PostAssessment:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return PostAssessment(
                tg_message_id=post.tg_message_id, categories=[], confidence=0.0,
                evidence_quotes=[], explanation="Невалидный ответ модели.",
                model_used=model,
            )
        categories = [c for c in data.get("categories", []) if c in RISK_CATEGORIES]
        confidence = float(data.get("confidence", 0.0) or 0.0)
        return PostAssessment(
            tg_message_id=post.tg_message_id,
            categories=categories,
            confidence=confidence,
            evidence_quotes=list(data.get("evidence_quotes", [])),
            explanation=str(data.get("explanation", "")),
            model_used=model,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_analyzer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/aimw/analyzer.py tests/test_analyzer.py
git commit -m "feat: OpenRouter analyzer with vision support"
```

---

### Task 6: Storage (SQLAlchemy models + repository)

**Files:**
- Create: `src/aimw/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Consumes: `ChannelReport`, `PostAssessment` from `aimw.domain`.
- Produces: `Repository` class.
  - `__init__(self, database_url: str)` — creates engine + tables.
  - `save_report(self, report: ChannelReport) -> None` — upsert channel by username; replaces its assessments.
  - `get_report(self, username: str) -> ChannelReport | None`.
  - `list_reports(self, sort_by_risk: bool = True) -> list[ChannelReport]`.
  - Tables: `channels` (username PK-unique, title, status, error_reason, risk_score, explanation, categories JSON) and `post_assessments` (id, channel_username FK, tg_message_id, categories JSON, confidence, evidence_quotes JSON, explanation, model_used).

- [ ] **Step 1: Write the failing test**

`tests/test_storage.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_storage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aimw.storage'`

- [ ] **Step 3: Write minimal implementation**

`src/aimw/storage.py`:
```python
import json

from sqlalchemy import (
    Column, Float, ForeignKey, Integer, String, Text, create_engine, delete, select,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship

from aimw.domain import ChannelReport, PostAssessment


class Base(DeclarativeBase):
    pass


class ChannelRow(Base):
    __tablename__ = "channels"
    username = Column(String, primary_key=True)
    title = Column(String, default="")
    status = Column(String, default="ok")
    error_reason = Column(Text, nullable=True)
    risk_score = Column(Integer, default=0)
    explanation = Column(Text, default="")
    categories = Column(Text, default="[]")  # JSON
    assessments = relationship(
        "AssessmentRow", cascade="all, delete-orphan", backref="channel"
    )


class AssessmentRow(Base):
    __tablename__ = "post_assessments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_username = Column(String, ForeignKey("channels.username"))
    tg_message_id = Column(Integer)
    categories = Column(Text, default="[]")  # JSON
    confidence = Column(Float, default=0.0)
    evidence_quotes = Column(Text, default="[]")  # JSON
    explanation = Column(Text, default="")
    model_used = Column(String, default="")


class Repository:
    def __init__(self, database_url: str):
        self._engine = create_engine(database_url)
        Base.metadata.create_all(self._engine)

    def save_report(self, report: ChannelReport) -> None:
        with Session(self._engine) as session:
            session.execute(
                delete(ChannelRow).where(ChannelRow.username == report.username)
            )
            row = ChannelRow(
                username=report.username,
                title=report.title,
                status=report.status,
                error_reason=report.error_reason,
                risk_score=report.risk_score,
                explanation=report.explanation,
                categories=json.dumps(report.categories, ensure_ascii=False),
            )
            for pa in report.post_assessments:
                row.assessments.append(AssessmentRow(
                    tg_message_id=pa.tg_message_id,
                    categories=json.dumps(pa.categories, ensure_ascii=False),
                    confidence=pa.confidence,
                    evidence_quotes=json.dumps(pa.evidence_quotes, ensure_ascii=False),
                    explanation=pa.explanation,
                    model_used=pa.model_used,
                ))
            session.add(row)
            session.commit()

    def get_report(self, username: str) -> ChannelReport | None:
        with Session(self._engine) as session:
            row = session.get(ChannelRow, username)
            if row is None:
                return None
            return self._to_report(row)

    def list_reports(self, sort_by_risk: bool = True) -> list[ChannelReport]:
        with Session(self._engine) as session:
            stmt = select(ChannelRow)
            if sort_by_risk:
                stmt = stmt.order_by(ChannelRow.risk_score.desc())
            return [self._to_report(r) for r in session.scalars(stmt).all()]

    def _to_report(self, row: ChannelRow) -> ChannelReport:
        assessments = [
            PostAssessment(
                tg_message_id=a.tg_message_id,
                categories=json.loads(a.categories),
                confidence=a.confidence,
                evidence_quotes=json.loads(a.evidence_quotes),
                explanation=a.explanation,
                model_used=a.model_used,
            )
            for a in row.assessments
        ]
        return ChannelReport(
            username=row.username,
            title=row.title,
            status=row.status,
            risk_score=row.risk_score,
            categories=json.loads(row.categories),
            explanation=row.explanation,
            post_assessments=assessments,
            error_reason=row.error_reason,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_storage.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/aimw/storage.py tests/test_storage.py
git commit -m "feat: SQLite storage repository"
```

---

### Task 7: Crawler (Telethon) with mockable client

**Files:**
- Create: `src/aimw/crawler.py`
- Test: `tests/test_crawler.py`

**Interfaces:**
- Consumes: `Post` from `aimw.domain`.
- Produces: `Crawler` class.
  - `__init__(self, client, media_dir: str = "media")` — `client` is a Telethon-like client exposing async `get_entity(username)` and async iterator `iter_messages(entity, limit=...)`, plus async `download_media(message, file=...)`. Injected for testing.
  - async `fetch_channel(self, username: str, limit: int) -> tuple[str, list[Post]]` — returns `(title, posts)`. Downloads photo media to `media_dir`, attaching saved paths to each `Post`. Raises `ChannelAccessError(username, reason)` on failure.
  - `ChannelAccessError(Exception)` with `.username` and `.reason`.
- Module function `build_telethon_client(settings)` constructing the real client (not exercised in tests).

- [ ] **Step 1: Write the failing test**

`tests/test_crawler.py`:
```python
import asyncio
from datetime import datetime

import pytest

from aimw.crawler import Crawler, ChannelAccessError


class FakeMessage:
    def __init__(self, mid, text, photo=None):
        self.id = mid
        self.message = text
        self.date = datetime(2026, 1, 1)
        self.photo = photo


class FakeClient:
    def __init__(self, title, messages, raise_on_entity=False):
        self._title = title
        self._messages = messages
        self._raise = raise_on_entity

    async def get_entity(self, username):
        if self._raise:
            raise ValueError("No user has that username")
        return type("E", (), {"title": self._title})()

    async def iter_messages(self, entity, limit=50):
        for m in self._messages[:limit]:
            yield m

    async def download_media(self, message, file=None):
        with open(file, "wb") as f:
            f.write(b"img")
        return file


def test_fetch_channel_returns_posts(tmp_path):
    client = FakeClient("My Channel", [FakeMessage(1, "казино"), FakeMessage(2, "hi")])
    crawler = Crawler(client, media_dir=str(tmp_path))
    title, posts = asyncio.run(crawler.fetch_channel("chan", limit=50))
    assert title == "My Channel"
    assert [p.tg_message_id for p in posts] == [1, 2]
    assert posts[0].text == "казино"


def test_fetch_channel_downloads_photo(tmp_path):
    client = FakeClient("C", [FakeMessage(1, "see image", photo=object())])
    crawler = Crawler(client, media_dir=str(tmp_path))
    _, posts = asyncio.run(crawler.fetch_channel("chan", limit=50))
    assert len(posts[0].media_paths) == 1


def test_inaccessible_channel_raises():
    client = FakeClient("C", [], raise_on_entity=True)
    crawler = Crawler(client, media_dir="media")
    with pytest.raises(ChannelAccessError) as exc:
        asyncio.run(crawler.fetch_channel("nope", limit=50))
    assert exc.value.username == "nope"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_crawler.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aimw.crawler'`

- [ ] **Step 3: Write minimal implementation**

`src/aimw/crawler.py`:
```python
import os

from telethon import TelegramClient

from aimw.domain import Post


class ChannelAccessError(Exception):
    def __init__(self, username: str, reason: str):
        super().__init__(f"{username}: {reason}")
        self.username = username
        self.reason = reason


def build_telethon_client(settings) -> TelegramClient:
    return TelegramClient(
        settings.telegram_session,
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )


def _normalize(username: str) -> str:
    u = username.strip()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/", "@"):
        if u.startswith(prefix):
            u = u[len(prefix):]
    return u.strip("/")


class Crawler:
    def __init__(self, client, media_dir: str = "media"):
        self._client = client
        self._media_dir = media_dir
        os.makedirs(media_dir, exist_ok=True)

    async def fetch_channel(self, username: str, limit: int) -> tuple[str, list[Post]]:
        name = _normalize(username)
        try:
            entity = await self._client.get_entity(name)
        except Exception as exc:  # noqa: BLE001
            raise ChannelAccessError(username, str(exc)) from exc

        title = getattr(entity, "title", name)
        posts: list[Post] = []
        async for message in self._client.iter_messages(entity, limit=limit):
            text = getattr(message, "message", None) or ""
            media_paths: list[str] = []
            if getattr(message, "photo", None) is not None:
                path = os.path.join(self._media_dir, f"{name}_{message.id}.jpg")
                saved = await self._client.download_media(message, file=path)
                if saved:
                    media_paths.append(saved)
            posts.append(Post(
                tg_message_id=message.id,
                date=message.date,
                text=text,
                media_paths=media_paths,
            ))
        return title, posts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_crawler.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/aimw/crawler.py tests/test_crawler.py
git commit -m "feat: Telethon crawler with media download"
```

---

### Task 8: Pipeline orchestrator

**Files:**
- Create: `src/aimw/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `Crawler`, `ChannelAccessError` (`aimw.crawler`); `Analyzer` (`aimw.analyzer`); `prefilter_text` (`aimw.prefilter`); `aggregate` (`aimw.scoring`); `ChannelReport` (`aimw.domain`).
- Produces: `Pipeline` class.
  - `__init__(self, crawler, analyzer, posts_per_channel: int)`.
  - async `analyze_channel(self, username: str) -> ChannelReport` — fetch posts, run `prefilter_text` on each, send only suspicious posts to `analyzer.analyze_post`, aggregate, build `ChannelReport(status="ok")`. On `ChannelAccessError`, return `ChannelReport(status="error", risk_score=0, ..., error_reason=reason)`.

- [ ] **Step 1: Write the failing test**

`tests/test_pipeline.py`:
```python
import asyncio
from datetime import datetime

from aimw.crawler import ChannelAccessError
from aimw.domain import Post, PostAssessment
from aimw.pipeline import Pipeline


class FakeCrawler:
    def __init__(self, posts, error=None):
        self._posts = posts
        self._error = error

    async def fetch_channel(self, username, limit):
        if self._error:
            raise self._error
        return "Title", self._posts


class FakeAnalyzer:
    def __init__(self):
        self.analyzed_ids = []

    def analyze_post(self, post):
        self.analyzed_ids.append(post.tg_message_id)
        return PostAssessment(
            tg_message_id=post.tg_message_id, categories=["illegal_gambling"],
            confidence=0.9, evidence_quotes=["казино"], explanation="ad",
            model_used="m",
        )


def test_only_suspicious_posts_analyzed():
    posts = [
        Post(1, datetime(2026, 1, 1), "лучшее казино, делай ставки"),
        Post(2, datetime(2026, 1, 1), "сегодня гуляли в парке"),
    ]
    analyzer = FakeAnalyzer()
    pipe = Pipeline(FakeCrawler(posts), analyzer, posts_per_channel=50)
    report = asyncio.run(pipe.analyze_channel("chan"))
    assert analyzer.analyzed_ids == [1]  # only the gambling post
    assert report.status == "ok"
    assert report.risk_score >= 80
    assert "illegal_gambling" in report.categories


def test_access_error_becomes_error_report():
    pipe = Pipeline(
        FakeCrawler([], error=ChannelAccessError("chan", "private")),
        FakeAnalyzer(), posts_per_channel=50,
    )
    report = asyncio.run(pipe.analyze_channel("chan"))
    assert report.status == "error"
    assert report.error_reason == "private"
    assert report.risk_score == 0


def test_clean_channel_zero_score():
    posts = [Post(1, datetime(2026, 1, 1), "хорошая погода сегодня")]
    pipe = Pipeline(FakeCrawler(posts), FakeAnalyzer(), posts_per_channel=50)
    report = asyncio.run(pipe.analyze_channel("chan"))
    assert report.risk_score == 0
    assert report.status == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aimw.pipeline'`

- [ ] **Step 3: Write minimal implementation**

`src/aimw/pipeline.py`:
```python
from aimw.crawler import ChannelAccessError
from aimw.domain import ChannelReport
from aimw.prefilter import prefilter_text
from aimw.scoring import aggregate


class Pipeline:
    def __init__(self, crawler, analyzer, posts_per_channel: int):
        self._crawler = crawler
        self._analyzer = analyzer
        self._limit = posts_per_channel

    async def analyze_channel(self, username: str) -> ChannelReport:
        try:
            title, posts = await self._crawler.fetch_channel(username, self._limit)
        except ChannelAccessError as exc:
            return ChannelReport(
                username=username, title=username, status="error", risk_score=0,
                categories=[], explanation="Канал недоступен.",
                post_assessments=[], error_reason=exc.reason,
            )

        assessments = []
        for post in posts:
            flags = prefilter_text(post.text)
            if flags["is_suspicious"] or post.media_paths:
                assessments.append(self._analyzer.analyze_post(post))

        agg = aggregate(assessments)
        return ChannelReport(
            username=username, title=title, status="ok",
            risk_score=agg["risk_score"], categories=agg["categories"],
            explanation=agg["explanation"], post_assessments=assessments,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/aimw/pipeline.py tests/test_pipeline.py
git commit -m "feat: analysis pipeline orchestrator"
```

---

### Task 9: REST API (FastAPI)

**Files:**
- Create: `src/aimw/schemas.py`
- Create: `src/aimw/api.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `ChannelReport` (`aimw.domain`); `Repository` (`aimw.storage`); `Pipeline` (`aimw.pipeline`); `get_settings` (`aimw.config`).
- Produces:
  - `schemas.py`: `AnalyzeRequest(channels: list[str])`, `PostAssessmentOut`, `ChannelReportOut` (with `from_domain(report) -> ChannelReportOut` classmethod).
  - `api.py`: `create_app(repository, pipeline) -> FastAPI`. Endpoints:
    - `GET /health` → `{"status": "ok"}`
    - `POST /channels` body `AnalyzeRequest` → analyzes each channel synchronously, saves report, returns `list[ChannelReportOut]`.
    - `GET /channels` query `sort` (default `"risk"`) → `list[ChannelReportOut]` from repo.
    - `GET /channels/{username}` → `ChannelReportOut` or 404.
  - Module-level `app` built from real settings/dependencies for `uvicorn aimw.api:app`.

- [ ] **Step 1: Write the failing test**

`tests/test_api.py`:
```python
from datetime import datetime

from fastapi.testclient import TestClient

from aimw.api import create_app
from aimw.domain import ChannelReport, Post, PostAssessment
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aimw.api'`

- [ ] **Step 3: Write `schemas.py`**

`src/aimw/schemas.py`:
```python
from pydantic import BaseModel

from aimw.domain import ChannelReport, PostAssessment


class AnalyzeRequest(BaseModel):
    channels: list[str]


class PostAssessmentOut(BaseModel):
    tg_message_id: int
    categories: list[str]
    confidence: float
    evidence_quotes: list[str]
    explanation: str
    model_used: str

    @classmethod
    def from_domain(cls, pa: PostAssessment) -> "PostAssessmentOut":
        return cls(**pa.__dict__)


class ChannelReportOut(BaseModel):
    username: str
    title: str
    status: str
    risk_score: int
    categories: list[str]
    explanation: str
    error_reason: str | None
    post_assessments: list[PostAssessmentOut]

    @classmethod
    def from_domain(cls, report: ChannelReport) -> "ChannelReportOut":
        return cls(
            username=report.username,
            title=report.title,
            status=report.status,
            risk_score=report.risk_score,
            categories=report.categories,
            explanation=report.explanation,
            error_reason=report.error_reason,
            post_assessments=[
                PostAssessmentOut.from_domain(p) for p in report.post_assessments
            ],
        )
```

- [ ] **Step 4: Write `api.py`**

`src/aimw/api.py`:
```python
from fastapi import FastAPI, HTTPException

from aimw.schemas import AnalyzeRequest, ChannelReportOut


def create_app(repository, pipeline) -> FastAPI:
    app = FastAPI(title="AI Media Watch — Telegram")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/channels", response_model=list[ChannelReportOut])
    async def analyze(req: AnalyzeRequest):
        results = []
        for username in req.channels:
            report = await pipeline.analyze_channel(username)
            repository.save_report(report)
            results.append(ChannelReportOut.from_domain(report))
        return results

    @app.get("/channels", response_model=list[ChannelReportOut])
    def list_channels(sort: str = "risk"):
        reports = repository.list_reports(sort_by_risk=(sort == "risk"))
        return [ChannelReportOut.from_domain(r) for r in reports]

    @app.get("/channels/{username}", response_model=ChannelReportOut)
    def get_channel(username: str):
        report = repository.get_report(username)
        if report is None:
            raise HTTPException(status_code=404, detail="channel not found")
        return ChannelReportOut.from_domain(report)

    return app


def _build_default_app() -> FastAPI:
    from aimw.analyzer import Analyzer, build_client
    from aimw.config import get_settings
    from aimw.crawler import Crawler, build_telethon_client
    from aimw.pipeline import Pipeline
    from aimw.storage import Repository

    settings = get_settings()
    repository = Repository(settings.database_url)
    tg = build_telethon_client(settings)
    tg.start()
    crawler = Crawler(tg)
    analyzer = Analyzer(build_client(settings), settings)
    pipeline = Pipeline(crawler, analyzer, settings.posts_per_channel)
    return create_app(repository, pipeline)


app = None  # built lazily by uvicorn entrypoint below
```

Note: leave `app = None`; the real entrypoint is added in Task 10. The test uses `create_app` directly, so this task's tests pass without a live `app`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_api.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/aimw/schemas.py src/aimw/api.py tests/test_api.py
git commit -m "feat: FastAPI REST endpoints"
```

---

### Task 10: Entrypoint, Telethon login script & README

**Files:**
- Modify: `src/aimw/api.py` (replace `app = None` with eager build)
- Create: `scripts/login.py`
- Create: `README.md`
- Test: full suite run (no new test file)

**Interfaces:**
- Consumes: everything wired in Task 9's `_build_default_app`.
- Produces: importable `aimw.api:app` for `uvicorn`; `scripts/login.py` to create the Telethon session interactively.

- [ ] **Step 1: Replace the lazy `app` line**

In `src/aimw/api.py`, replace:
```python
app = None  # built lazily by uvicorn entrypoint below
```
with:
```python
app = _build_default_app()
```

- [ ] **Step 2: Create `scripts/login.py`**

```python
"""One-time Telethon login to create a reusable session file."""
from aimw.config import get_settings
from telethon import TelegramClient


def main():
    s = get_settings()
    with TelegramClient(s.telegram_session, s.telegram_api_id, s.telegram_api_hash) as c:
        me = c.get_me()
        print(f"Logged in as {me.username or me.first_name}; session saved.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Create `README.md`**

````markdown
# AI Media Watch — Telegram Crawler & Risk Analyzer

Crawls Telegram channels and scores them for illegal gambling, financial
pyramids and fraud (RU + KZ), with explanations and evidence quotes.

## Setup
```bash
pip install -e ".[dev]"
cp .env.example .env   # fill in credentials
python scripts/login.py  # one-time Telegram login
```

## Run
```bash
uvicorn aimw.api:app --reload
```

## API
- `POST /channels` `{"channels": ["@chan", "t.me/chan2"]}` → risk reports
- `GET /channels?sort=risk` → prioritized list
- `GET /channels/{username}` → single report
- `GET /health`

## Test
```bash
python -m pytest -v
```
````

- [ ] **Step 4: Run the full test suite**

Run: `python -m pytest -v`
Expected: PASS (all tests from Tasks 1–9). Note: importing `aimw.api` now triggers `_build_default_app`, which calls Telethon/OpenRouter — so tests must import `create_app`, not module `app`. Confirm `tests/test_api.py` imports only `create_app` (it does). If collection fails due to eager build, guard `_build_default_app()` behind `if __name__` is not viable for uvicorn; instead wrap the module-level call in a try/except that logs and sets `app = create_app`-less placeholder is NOT acceptable. Correct approach: keep eager `app = _build_default_app()` and ensure tests never import `aimw.api.app`. Verified: they don't.

- [ ] **Step 5: Commit**

```bash
git add src/aimw/api.py scripts/login.py README.md
git commit -m "feat: uvicorn entrypoint, login script, README"
```

---

## Self-Review

**Spec coverage:**
- Input list of channels via API → Task 9 `POST /channels` ✓
- Telethon crawling text + images → Task 7 ✓
- Hybrid prefilter (RU+KZ) → LLM → Tasks 3, 5, 8 ✓
- OpenRouter LLM + vision → Task 5 ✓
- Risk score 0–100 + categories + evidence + explanation → Tasks 2, 4, 5 ✓
- Six exact categories → Task 2 ✓
- Storage + prioritized list → Tasks 6, 9 ✓
- Error handling (inaccessible channel, bad model output) → Tasks 5, 7, 8 ✓
- Sync API → Task 9 ✓
- Config (env, models, threshold) → Task 1 ✓
- Tests mock Telethon + OpenRouter → Tasks 5, 7, 8, 9 ✓

**Placeholder scan:** No TBD/TODO; every code step has full code. Task 10 Step 4 contains guidance prose but the actionable instruction (tests import `create_app`, not `app`) is concrete.

**Type consistency:** `ChannelReport`, `Post`, `PostAssessment` fields used identically across storage, pipeline, analyzer, schemas. `analyze_channel`, `analyze_post`, `fetch_channel`, `prefilter_text`, `aggregate`, `save_report`/`get_report`/`list_reports` signatures match across producer and consumer tasks.
