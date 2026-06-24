# AI Media Watch Backend (скелет) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Поднять рабочий сквозной скелет FastAPI-бекенда: приём видео+описания → буфер → лёгкий триаж задаёт приоритет → приоритетная очередь → мультимодальные стаб-пайплайны → риск-оценка с объяснениями (SHAP/LIME-контракт) → БД → API.

**Architecture:** Гексагональная: домен (типы, протоколы пайплайнов) в центре; адаптеры (очередь, хранилище, БД) за интерфейсами с in-memory и Redis/SQLite реализациями. Двухуровневая обработка через два воркера (triage → analysis) поверх приоритетной `JobQueue`. Все ИИ-модели и скраперы — стабы за протоколами, подключаются позже без изменения каркаса.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Pydantic v2 + pydantic-settings, SQLAlchemy 2.0 async + aiosqlite, redis-py (async), pytest + pytest-asyncio + httpx.

## Global Constraints

- Python ≥ 3.11 (используется `X | None`, `list[...]` синтаксис).
- В скелете НЕ тащим реальные ML-либы (`shap`, `lime`, `torch`, `opencv`) и НЕ пишем скраперы — только контракты + детерминированные стабы.
- `JobQueue` имеет ровно два бэкенда: `memory` и `redis`, выбор через `MW_QUEUE_BACKEND`.
- Лейны очереди: `intake` (FIFO) и `analysis` (priority). Константы `INTAKE="intake"`, `ANALYSIS="analysis"`.
- Статусы Job: `queued → triaged → processing → done | failed` (строго эти строки).
- Все настройки — через env с префиксом `MW_` (pydantic-settings).
- **Git не используется (по решению пользователя).** Шагов `commit` нет; каждая задача завершается прогоном тестов как чекпоинтом.
- Стабы детерминированы (никакого `random`) — иначе тесты будут флакать.
- `pytest` сконфигурирован с `asyncio_mode = "auto"` — async-тесты не требуют декоратора.
- Все команды запускаются из директории `server/`.

---

## File Structure

```
server/
  pyproject.toml                 # Task 1
  .env.example                   # Task 1
  app/
    __init__.py                  # Task 1
    config.py                    # Task 1
    main.py                      # Task 14
    api/
      __init__.py                # Task 14
      deps.py                    # Task 14
      health.py jobs.py review.py videos.py pipelines.py  # Task 14
    pipelines/
      __init__.py                # Task 2
      base.py                    # Task 2  (Unit, Finding, JobContext, Pipeline)
      explain.py                 # Task 2  (Attribution, Explanation)
      registry.py                # Task 7
      stubs.py                   # Task 8
      extract.py                 # Task 9
      aggregator.py              # Task 10
      orchestrator.py            # Task 11 (run_triage, run_analysis)
    queue/
      __init__.py                # Task 3
      base.py                    # Task 3  (QueueMessage, JobQueue, INTAKE, ANALYSIS)
      memory.py                  # Task 3
      redis.py                   # Task 15
      factory.py                 # Task 15
    storage/
      __init__.py                # Task 4
      base.py local.py           # Task 4
    db/
      __init__.py                # Task 5
      base.py models.py session.py  # Task 5
      repository.py              # Task 6
    sources/
      __init__.py base.py stub.py  # Task 13
    dedup/
      __init__.py hashing.py neardup.py  # Task 17 (exact SHA-256 + near-dup seam)
    worker/
      __init__.py base.py        # Task 12
      handlers.py triage.py analysis.py  # Task 12
  tests/
    __init__.py conftest.py      # Task 1 / Task 14
    test_*.py                    # per task
  docker-compose.yml Dockerfile README.md  # Task 16
```

---

### Task 1: Project setup + config

**Files:**
- Create: `server/pyproject.toml`
- Create: `server/.env.example`
- Create: `server/app/__init__.py` (empty)
- Create: `server/app/config.py`
- Create: `server/tests/__init__.py` (empty)
- Test: `server/tests/test_config.py`

**Interfaces:**
- Produces: `app.config.Settings` (pydantic-settings) with fields `queue_backend: str`, `redis_url: str`, `database_url: str`, `storage_dir: str`, `max_upload_bytes: int`; helper `get_settings() -> Settings`.

- [ ] **Step 1: Create `server/pyproject.toml`**

```toml
[project]
name = "ai-media-watch"
version = "0.1.0"
description = "AI Media Watch backend skeleton"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
    "sqlalchemy[asyncio]>=2.0",
    "aiosqlite>=0.20",
    "redis>=5.0",
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["app*"]
```

- [ ] **Step 2: Create `server/.env.example`**

```bash
MW_QUEUE_BACKEND=memory
MW_REDIS_URL=redis://localhost:6379/0
MW_DATABASE_URL=sqlite+aiosqlite:///./media_watch.db
MW_STORAGE_DIR=./buffer
MW_MAX_UPLOAD_BYTES=524288000
```

- [ ] **Step 3: Create empty `server/app/__init__.py` and `server/tests/__init__.py`**

Both files are empty.

- [ ] **Step 4: Write the failing test** in `server/tests/test_config.py`

```python
from app.config import Settings, get_settings


def test_defaults():
    s = Settings()
    assert s.queue_backend == "memory"
    assert s.database_url.startswith("sqlite+aiosqlite")
    assert s.storage_dir
    assert s.max_upload_bytes > 0


def test_env_override(monkeypatch):
    monkeypatch.setenv("MW_QUEUE_BACKEND", "redis")
    assert Settings().queue_backend == "redis"


def test_get_settings_cached():
    assert get_settings() is get_settings()
```

- [ ] **Step 5: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.config'`

- [ ] **Step 6: Create `server/app/config.py`**

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MW_", env_file=".env", extra="ignore")

    queue_backend: str = "memory"
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "sqlite+aiosqlite:///./media_watch.db"
    storage_dir: str = "./buffer"
    max_upload_bytes: int = 500 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 7: Install dev deps and run tests (checkpoint)**

Run: `python -m pip install -e ".[dev]"` then `python -m pytest tests/test_config.py -v`
Expected: PASS (3 passed)

---

### Task 2: Core domain types

**Files:**
- Create: `server/app/pipelines/__init__.py` (empty)
- Create: `server/app/pipelines/base.py`
- Create: `server/app/pipelines/explain.py`
- Test: `server/tests/test_domain_types.py`

**Interfaces:**
- Produces:
  - `Unit(kind: str, index: int, payload: dict)`
  - `Finding(modality: str, signal_type: str, confidence: float, evidence: dict, ts_in_video: float | None = None)`
  - `JobContext(job_id: str, description: str, source_meta: dict, buffer_path: str | None = None)`
  - `Pipeline` Protocol: attrs `name: str`, `modality: str`; `async process(ctx: JobContext, unit: Unit) -> list[Finding]`; `async explain(ctx: JobContext, findings: list[Finding]) -> Explanation | None`
  - `Attribution(feature: str, value: str | float, weight: float)`
  - `Explanation(scope: str, method: str, attributions: list[Attribution], summary: str, media: bytes | None = None)`

- [ ] **Step 1: Write the failing test** in `server/tests/test_domain_types.py`

```python
from app.pipelines.base import Finding, JobContext, Unit
from app.pipelines.explain import Attribution, Explanation


def test_unit_and_finding():
    u = Unit(kind="text", index=0, payload={"text": "hi"})
    assert u.payload["text"] == "hi"
    f = Finding(modality="text", signal_type="kw", confidence=0.5, evidence={"k": 1})
    assert f.ts_in_video is None


def test_job_context_defaults():
    ctx = JobContext(job_id="j1", description="d", source_meta={})
    assert ctx.buffer_path is None


def test_explanation_holds_attributions():
    exp = Explanation(
        scope="aggregate",
        method="shap",
        attributions=[Attribution(feature="casino", value=1.0, weight=0.5)],
        summary="x",
    )
    assert exp.attributions[0].weight == 0.5
    assert exp.media is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_domain_types.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.pipelines.base'`

- [ ] **Step 3: Create empty `server/app/pipelines/__init__.py`**

- [ ] **Step 4: Create `server/app/pipelines/explain.py`**

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Attribution:
    feature: str
    value: str | float
    weight: float


@dataclass
class Explanation:
    scope: str
    method: str
    attributions: list[Attribution]
    summary: str
    media: bytes | None = None
```

- [ ] **Step 5: Create `server/app/pipelines/base.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from app.pipelines.explain import Explanation


@dataclass
class Unit:
    kind: str          # "text" | "frame" | "audio"
    index: int
    payload: dict = field(default_factory=dict)


@dataclass
class Finding:
    modality: str      # "triage" | "text" | "ocr" | "audio" | "visual"
    signal_type: str
    confidence: float
    evidence: dict = field(default_factory=dict)
    ts_in_video: float | None = None


@dataclass
class JobContext:
    job_id: str
    description: str
    source_meta: dict = field(default_factory=dict)
    buffer_path: str | None = None


@runtime_checkable
class Pipeline(Protocol):
    name: str
    modality: str

    async def process(self, ctx: JobContext, unit: Unit) -> list[Finding]: ...

    async def explain(self, ctx: JobContext, findings: list[Finding]) -> Explanation | None: ...
```

- [ ] **Step 6: Run tests (checkpoint)**

Run: `python -m pytest tests/test_domain_types.py -v`
Expected: PASS (3 passed)

---

### Task 3: JobQueue abstraction + InMemoryQueue

**Files:**
- Create: `server/app/queue/__init__.py` (empty)
- Create: `server/app/queue/base.py`
- Create: `server/app/queue/memory.py`
- Test: `server/tests/test_queue_memory.py`

**Interfaces:**
- Produces:
  - `QueueMessage(lane: str, job_id: str, receipt: str)`
  - constants `INTAKE = "intake"`, `ANALYSIS = "analysis"`
  - `JobQueue` Protocol: `async enqueue(lane: str, job_id: str, *, priority: float = 0.0) -> None`; `async dequeue(lane: str) -> QueueMessage | None`; `async ack(msg: QueueMessage) -> None`; `async nack(msg: QueueMessage) -> None`
  - `InMemoryQueue()` implementing `JobQueue`

- [ ] **Step 1: Write the failing test** in `server/tests/test_queue_memory.py`

```python
from app.queue.base import ANALYSIS, INTAKE
from app.queue.memory import InMemoryQueue


async def test_fifo_order():
    q = InMemoryQueue()
    await q.enqueue(INTAKE, "a")
    await q.enqueue(INTAKE, "b")
    m1 = await q.dequeue(INTAKE)
    m2 = await q.dequeue(INTAKE)
    assert (m1.job_id, m2.job_id) == ("a", "b")
    assert await q.dequeue(INTAKE) is None


async def test_priority_order_highest_first():
    q = InMemoryQueue()
    await q.enqueue(ANALYSIS, "low", priority=0.1)
    await q.enqueue(ANALYSIS, "high", priority=0.9)
    await q.enqueue(ANALYSIS, "mid", priority=0.5)
    order = [(await q.dequeue(ANALYSIS)).job_id for _ in range(3)]
    assert order == ["high", "mid", "low"]


async def test_nack_requeues_with_priority():
    q = InMemoryQueue()
    await q.enqueue(ANALYSIS, "x", priority=0.7)
    msg = await q.dequeue(ANALYSIS)
    await q.nack(msg)
    again = await q.dequeue(ANALYSIS)
    assert again.job_id == "x"


async def test_ack_removes_inflight():
    q = InMemoryQueue()
    await q.enqueue(INTAKE, "x")
    msg = await q.dequeue(INTAKE)
    await q.ack(msg)
    await q.nack(msg)  # no-op after ack
    assert await q.dequeue(INTAKE) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_queue_memory.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.queue.base'`

- [ ] **Step 3: Create empty `server/app/queue/__init__.py`**

- [ ] **Step 4: Create `server/app/queue/base.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

INTAKE = "intake"
ANALYSIS = "analysis"


@dataclass
class QueueMessage:
    lane: str
    job_id: str
    receipt: str


class JobQueue(Protocol):
    async def enqueue(self, lane: str, job_id: str, *, priority: float = 0.0) -> None: ...

    async def dequeue(self, lane: str) -> QueueMessage | None: ...

    async def ack(self, msg: QueueMessage) -> None: ...

    async def nack(self, msg: QueueMessage) -> None: ...
```

- [ ] **Step 5: Create `server/app/queue/memory.py`**

```python
from __future__ import annotations

import asyncio
import heapq
from collections import defaultdict, deque
from itertools import count

from app.queue.base import QueueMessage


class InMemoryQueue:
    """Single-process queue. FIFO for priority==0 lanes, max-heap otherwise."""

    def __init__(self) -> None:
        self._fifo: dict[str, deque[str]] = defaultdict(deque)
        self._heap: dict[str, list[tuple[float, int, str, float]]] = defaultdict(list)
        self._inflight: dict[str, tuple[str, str, float]] = {}
        self._seq = count(1)
        self._lock = asyncio.Lock()

    def _put(self, lane: str, job_id: str, priority: float) -> None:
        if priority:
            heapq.heappush(self._heap[lane], (-priority, next(self._seq), job_id, priority))
        else:
            self._fifo[lane].append(job_id)

    async def enqueue(self, lane: str, job_id: str, *, priority: float = 0.0) -> None:
        async with self._lock:
            self._put(lane, job_id, priority)

    async def dequeue(self, lane: str) -> QueueMessage | None:
        async with self._lock:
            if self._heap[lane]:
                _, _, job_id, priority = heapq.heappop(self._heap[lane])
            elif self._fifo[lane]:
                job_id, priority = self._fifo[lane].popleft(), 0.0
            else:
                return None
            receipt = str(next(self._seq))
            self._inflight[receipt] = (lane, job_id, priority)
            return QueueMessage(lane=lane, job_id=job_id, receipt=receipt)

    async def ack(self, msg: QueueMessage) -> None:
        async with self._lock:
            self._inflight.pop(msg.receipt, None)

    async def nack(self, msg: QueueMessage) -> None:
        async with self._lock:
            entry = self._inflight.pop(msg.receipt, None)
            if entry is not None:
                lane, job_id, priority = entry
                self._put(lane, job_id, priority)
```

- [ ] **Step 6: Run tests (checkpoint)**

Run: `python -m pytest tests/test_queue_memory.py -v`
Expected: PASS (4 passed)

---

### Task 4: BlobStorage abstraction + LocalStorage

**Files:**
- Create: `server/app/storage/__init__.py` (empty)
- Create: `server/app/storage/base.py`
- Create: `server/app/storage/local.py`
- Test: `server/tests/test_storage_local.py`

**Interfaces:**
- Produces:
  - `BlobStorage` Protocol: `async save_stream(key: str, chunks: AsyncIterator[bytes]) -> str` (returns absolute path/uri); `def path_for(key: str) -> str`; `async delete(key: str) -> None`
  - `LocalStorage(root: str)` implementing `BlobStorage`

- [ ] **Step 1: Write the failing test** in `server/tests/test_storage_local.py`

```python
from pathlib import Path

from app.storage.local import LocalStorage


async def _chunks(parts):
    for p in parts:
        yield p


async def test_save_stream_writes_file(tmp_path):
    storage = LocalStorage(str(tmp_path))
    path = await storage.save_stream("job1/video.mp4", _chunks([b"abc", b"def"]))
    assert Path(path).read_bytes() == b"abcdef"
    assert Path(path).name == "video.mp4"


async def test_save_stream_creates_nested_dirs(tmp_path):
    storage = LocalStorage(str(tmp_path))
    path = await storage.save_stream("a/b/c.bin", _chunks([b"x"]))
    assert Path(path).exists()


async def test_delete_removes_file(tmp_path):
    storage = LocalStorage(str(tmp_path))
    path = await storage.save_stream("d/x.bin", _chunks([b"x"]))
    await storage.delete("d/x.bin")
    assert not Path(path).exists()


async def test_delete_missing_is_noop(tmp_path):
    storage = LocalStorage(str(tmp_path))
    await storage.delete("nope/missing.bin")  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_storage_local.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.storage.local'`

- [ ] **Step 3: Create empty `server/app/storage/__init__.py`**

- [ ] **Step 4: Create `server/app/storage/base.py`**

```python
from __future__ import annotations

from typing import AsyncIterator, Protocol


class BlobStorage(Protocol):
    async def save_stream(self, key: str, chunks: AsyncIterator[bytes]) -> str: ...

    def path_for(self, key: str) -> str: ...

    async def delete(self, key: str) -> None: ...
```

- [ ] **Step 5: Create `server/app/storage/local.py`**

```python
from __future__ import annotations

from pathlib import Path
from typing import AsyncIterator


class LocalStorage:
    def __init__(self, root: str) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def path_for(self, key: str) -> str:
        return str(self._root / key)

    async def save_stream(self, key: str, chunks: AsyncIterator[bytes]) -> str:
        target = self._root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "wb") as fh:
            async for chunk in chunks:
                fh.write(chunk)
        return str(target)

    async def delete(self, key: str) -> None:
        (self._root / key).unlink(missing_ok=True)
```

- [ ] **Step 6: Run tests (checkpoint)**

Run: `python -m pytest tests/test_storage_local.py -v`
Expected: PASS (4 passed)

---

### Task 5: DB models + session

**Files:**
- Create: `server/app/db/__init__.py` (empty)
- Create: `server/app/db/base.py`
- Create: `server/app/db/models.py`
- Create: `server/app/db/session.py`
- Test: `server/tests/test_db_models.py`

**Interfaces:**
- Produces:
  - `Base` (DeclarativeBase)
  - ORM `Job`, `Finding`, `Explanation` (columns per spec §7)
  - `make_engine(url: str)`, `make_sessionmaker(engine)`, `async init_db(engine)`

- [ ] **Step 1: Write the failing test** in `server/tests/test_db_models.py`

```python
from sqlalchemy import select

from app.db.models import Job
from app.db.session import init_db, make_engine, make_sessionmaker


async def test_create_and_read_job():
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    Session = make_sessionmaker(engine)
    async with Session() as s:
        s.add(Job(id="j1", description="hello", content_hash="hash-1", source_meta={"platform": "tiktok"}))
        await s.commit()
    async with Session() as s:
        job = (await s.execute(select(Job).where(Job.id == "j1"))).scalar_one()
        assert job.status == "queued"
        assert job.priority == 0.0
        assert job.source_meta["platform"] == "tiktok"
        assert job.risk_score is None
        assert job.content_hash == "hash-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_db_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.db.models'`

- [ ] **Step 3: Create empty `server/app/db/__init__.py`**

- [ ] **Step 4: Create `server/app/db/base.py`**

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 5: Create `server/app/db/models.py`**

```python
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, default="queued")
    description: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)
    source_platform: Mapped[str | None] = mapped_column(String, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    source_meta: Mapped[dict] = mapped_column(JSON, default=dict)
    buffer_path: Mapped[str | None] = mapped_column(String, nullable=True)
    priority: Mapped[float] = mapped_column(Float, default=0.0)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    findings: Mapped[list["Finding"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    explanations: Mapped[list["Explanation"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    modality: Mapped[str] = mapped_column(String)
    signal_type: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    ts_in_video: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    job: Mapped[Job] = relationship(back_populates="findings")


class Explanation(Base):
    __tablename__ = "explanations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    scope: Mapped[str] = mapped_column(String)
    method: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    media_path: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    job: Mapped[Job] = relationship(back_populates="explanations")
```

- [ ] **Step 6: Create `server/app/db/session.py`**

```python
from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base


def make_engine(url: str) -> AsyncEngine:
    return create_async_engine(url, future=True)


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

- [ ] **Step 7: Run tests (checkpoint)**

Run: `python -m pytest tests/test_db_models.py -v`
Expected: PASS (1 passed)

---

### Task 6: JobRepository

**Files:**
- Create: `server/app/db/repository.py`
- Test: `server/tests/test_db_repository.py`

**Interfaces:**
- Consumes: `Job/Finding/Explanation` ORM (Task 5); `Finding` domain dataclass (Task 2); `Explanation` domain dataclass (Task 2).
- Produces: `JobRepository(session_factory)` with:
  - `async create_job(description: str, source_platform: str | None, source_url: str | None, source_meta: dict, buffer_path: str | None = None, content_hash: str | None = None) -> str` (returns job_id)
  - `async get_job(job_id: str) -> Job | None`
  - `async get_job_by_hash(content_hash: str) -> Job | None` (exact-dedup lookup)
  - `async set_status(job_id: str, status: str, error: str | None = None) -> None`
  - `async set_priority(job_id: str, priority: float) -> None`
  - `async set_risk(job_id: str, risk_score: float, category: str) -> None`
  - `async add_findings(job_id: str, findings: list[DomainFinding]) -> None`
  - `async add_explanations(job_id: str, explanations: list[DomainExplanation]) -> None`
  - `async get_findings(job_id: str) -> list[Finding]`
  - `async get_explanations(job_id: str) -> list[Explanation]`
  - `async review_queue(limit: int = 50) -> list[Job]` (order: risk_score desc nulls last, then priority desc)

- [ ] **Step 1: Write the failing test** in `server/tests/test_db_repository.py`

```python
import pytest

from app.db.repository import JobRepository
from app.db.session import init_db, make_engine, make_sessionmaker
from app.pipelines.base import Finding
from app.pipelines.explain import Attribution, Explanation


@pytest.fixture
async def repo():
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    return JobRepository(make_sessionmaker(engine))


async def test_create_and_get(repo):
    job_id = await repo.create_job("desc", "tiktok", "http://x", {"a": 1}, "/buf/v.mp4")
    job = await repo.get_job(job_id)
    assert job.description == "desc"
    assert job.buffer_path == "/buf/v.mp4"
    assert job.status == "queued"


async def test_status_priority_risk(repo):
    job_id = await repo.create_job("d", None, None, {})
    await repo.set_priority(job_id, 0.8)
    await repo.set_status(job_id, "processing")
    await repo.set_risk(job_id, 0.9, "gambling")
    job = await repo.get_job(job_id)
    assert (job.priority, job.status, job.risk_score, job.category) == (0.8, "processing", 0.9, "gambling")


async def test_findings_and_explanations(repo):
    job_id = await repo.create_job("d", None, None, {})
    await repo.add_findings(job_id, [Finding(modality="text", signal_type="kw", confidence=0.5, evidence={"k": "v"})])
    await repo.add_explanations(job_id, [Explanation(scope="aggregate", method="shap",
        attributions=[Attribution(feature="casino", value=1.0, weight=0.4)], summary="s")])
    findings = await repo.get_findings(job_id)
    exps = await repo.get_explanations(job_id)
    assert findings[0].signal_type == "kw"
    assert exps[0].payload["attributions"][0]["feature"] == "casino"


async def test_review_queue_orders_by_risk(repo):
    a = await repo.create_job("a", None, None, {})
    b = await repo.create_job("b", None, None, {})
    await repo.set_risk(a, 0.2, "clean")
    await repo.set_risk(b, 0.95, "gambling")
    ids = [j.id for j in await repo.review_queue()]
    assert ids[:2] == [b, a]
    assert ids[-1] == c  # NULL risk_score sorts after scored jobs


async def test_get_job_by_hash(repo):
    job_id = await repo.create_job("d", None, None, {}, content_hash="abc123")
    found = await repo.get_job_by_hash("abc123")
    assert found is not None and found.id == job_id
    assert await repo.get_job_by_hash("missing") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_db_repository.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.db.repository'`

- [ ] **Step 3: Create `server/app/db/repository.py`**

```python
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.db.models import Explanation, Finding, Job
from app.pipelines.base import Finding as DomainFinding
from app.pipelines.explain import Explanation as DomainExplanation


class JobRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def create_job(
        self,
        description: str,
        source_platform: str | None,
        source_url: str | None,
        source_meta: dict,
        buffer_path: str | None = None,
        content_hash: str | None = None,
    ) -> str:
        job_id = uuid.uuid4().hex
        async with self._sf() as s:
            s.add(Job(
                id=job_id,
                description=description,
                source_platform=source_platform,
                source_url=source_url,
                source_meta=source_meta,
                buffer_path=buffer_path,
                content_hash=content_hash,
            ))
            await s.commit()
        return job_id

    async def get_job(self, job_id: str) -> Job | None:
        async with self._sf() as s:
            stmt = (
                select(Job)
                .where(Job.id == job_id)
                .options(selectinload(Job.findings), selectinload(Job.explanations))
            )
            return (await s.execute(stmt)).scalar_one_or_none()

    async def get_job_by_hash(self, content_hash: str) -> Job | None:
        async with self._sf() as s:
            stmt = select(Job).where(Job.content_hash == content_hash)
            return (await s.execute(stmt)).scalar_one_or_none()

    async def _update(self, job_id: str, **values) -> None:
        async with self._sf() as s:
            job = await s.get(Job, job_id)
            if job is None:
                return
            for key, val in values.items():
                setattr(job, key, val)
            await s.commit()

    async def set_status(self, job_id: str, status: str, error: str | None = None) -> None:
        await self._update(job_id, status=status, error=error)

    async def set_priority(self, job_id: str, priority: float) -> None:
        await self._update(job_id, priority=priority)

    async def set_risk(self, job_id: str, risk_score: float, category: str) -> None:
        await self._update(job_id, risk_score=risk_score, category=category)

    async def add_findings(self, job_id: str, findings: list[DomainFinding]) -> None:
        async with self._sf() as s:
            for f in findings:
                s.add(Finding(
                    job_id=job_id,
                    modality=f.modality,
                    signal_type=f.signal_type,
                    confidence=f.confidence,
                    evidence=f.evidence,
                    ts_in_video=f.ts_in_video,
                ))
            await s.commit()

    async def add_explanations(self, job_id: str, explanations: list[DomainExplanation]) -> None:
        async with self._sf() as s:
            for e in explanations:
                s.add(Explanation(
                    job_id=job_id,
                    scope=e.scope,
                    method=e.method,
                    summary=e.summary,
                    payload={"attributions": [
                        {"feature": a.feature, "value": a.value, "weight": a.weight}
                        for a in e.attributions
                    ]},
                ))
            await s.commit()

    async def get_findings(self, job_id: str) -> list[Finding]:
        async with self._sf() as s:
            stmt = select(Finding).where(Finding.job_id == job_id).order_by(Finding.id)
            return list((await s.execute(stmt)).scalars().all())

    async def get_explanations(self, job_id: str) -> list[Explanation]:
        async with self._sf() as s:
            stmt = select(Explanation).where(Explanation.job_id == job_id).order_by(Explanation.id)
            return list((await s.execute(stmt)).scalars().all())

    async def review_queue(self, limit: int = 50) -> list[Job]:
        async with self._sf() as s:
            stmt = (
                select(Job)
                .order_by(Job.risk_score.is_(None), Job.risk_score.desc(), Job.priority.desc())
                .limit(limit)
            )
            return list((await s.execute(stmt)).scalars().all())
```

- [ ] **Step 4: Run tests (checkpoint)**

Run: `python -m pytest tests/test_db_repository.py -v`
Expected: PASS (5 passed)

---

### Task 7: PipelineRegistry

**Files:**
- Create: `server/app/pipelines/registry.py`
- Test: `server/tests/test_registry.py`

**Interfaces:**
- Consumes: `Pipeline` protocol (Task 2).
- Produces: `PipelineRegistry()` with `register(p: Pipeline) -> Pipeline`, `all() -> list[Pipeline]`, `by_modality(m: str) -> list[Pipeline]`, `triage_pipelines() -> list[Pipeline]`, `analysis_pipelines() -> list[Pipeline]` (all non-triage).

- [ ] **Step 1: Write the failing test** in `server/tests/test_registry.py`

```python
from app.pipelines.base import Finding, JobContext, Unit
from app.pipelines.registry import PipelineRegistry


class _P:
    def __init__(self, name, modality):
        self.name = name
        self.modality = modality

    async def process(self, ctx, unit):
        return []

    async def explain(self, ctx, findings):
        return None


def test_register_and_query():
    reg = PipelineRegistry()
    reg.register(_P("t", "triage"))
    reg.register(_P("txt", "text"))
    reg.register(_P("vis", "visual"))
    assert {p.name for p in reg.all()} == {"t", "txt", "vis"}
    assert [p.name for p in reg.triage_pipelines()] == ["t"]
    assert {p.name for p in reg.analysis_pipelines()} == {"txt", "vis"}
    assert reg.by_modality("text")[0].name == "txt"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.pipelines.registry'`

- [ ] **Step 3: Create `server/app/pipelines/registry.py`**

```python
from __future__ import annotations

from app.pipelines.base import Pipeline


class PipelineRegistry:
    def __init__(self) -> None:
        self._pipelines: dict[str, Pipeline] = {}

    def register(self, pipeline: Pipeline) -> Pipeline:
        self._pipelines[pipeline.name] = pipeline
        return pipeline

    def all(self) -> list[Pipeline]:
        return list(self._pipelines.values())

    def by_modality(self, modality: str) -> list[Pipeline]:
        return [p for p in self._pipelines.values() if p.modality == modality]

    def triage_pipelines(self) -> list[Pipeline]:
        return self.by_modality("triage")

    def analysis_pipelines(self) -> list[Pipeline]:
        return [p for p in self._pipelines.values() if p.modality != "triage"]
```

- [ ] **Step 4: Run tests (checkpoint)**

Run: `python -m pytest tests/test_registry.py -v`
Expected: PASS (1 passed)

---

### Task 8: Domain stub pipelines

**Files:**
- Create: `server/app/pipelines/stubs.py`
- Test: `server/tests/test_stubs.py`

**Interfaces:**
- Consumes: `Finding`, `JobContext`, `Unit`, `Pipeline` (Task 2); `Attribution`, `Explanation` (Task 2); `PipelineRegistry` (Task 7).
- Produces: classes `TriageClassifier`, `TextPipeline`, `OCRPipeline`, `AudioPipeline`, `VisualPipeline`; helper `register_default_pipelines(registry: PipelineRegistry) -> PipelineRegistry`.
- Behaviour contract (deterministic):
  - `TriageClassifier.modality == "triage"`; matches substrings from `PATTERNS` in `unit.payload["text"]` (lowercased), one `Finding` per matched keyword.
  - `TextPipeline.modality == "text"`; same text source, signal_type `"text_signal:<kw>"`.
  - `OCRPipeline.modality == "ocr"`; processes `frame` units; emits one finding on frame index 0 if description contains digits-or-`%` markers; else none.
  - `AudioPipeline.modality == "audio"`; processes `audio` units; emits `"speech_promise"` if `"доход"` in description.
  - `VisualPipeline.modality == "visual"`; processes `frame` units; emits `"casino_marker"` on frame 0 if `"казино"` or `"casino"` in description.

- [ ] **Step 1: Write the failing test** in `server/tests/test_stubs.py`

```python
from app.pipelines.base import JobContext, Unit
from app.pipelines.registry import PipelineRegistry
from app.pipelines.stubs import (
    AudioPipeline,
    TextPipeline,
    TriageClassifier,
    VisualPipeline,
    register_default_pipelines,
)


def _ctx(desc):
    return JobContext(job_id="j", description=desc, source_meta={})


async def test_triage_matches_keywords_and_explains():
    p = TriageClassifier()
    ctx = _ctx("Лучшее КАЗИНО и гарантированный доход")
    findings = await p.process(ctx, Unit(kind="text", index=0, payload={"text": ctx.description}))
    kinds = {f.signal_type for f in findings}
    assert any("казино" in k for k in kinds)
    exp = await p.explain(ctx, findings)
    assert exp.scope == "triage"
    assert exp.attributions


async def test_triage_clean_text_no_findings():
    p = TriageClassifier()
    ctx = _ctx("милые котики на природе")
    findings = await p.process(ctx, Unit(kind="text", index=0, payload={"text": ctx.description}))
    assert findings == []


async def test_visual_emits_marker_for_casino():
    p = VisualPipeline()
    ctx = _ctx("реклама casino")
    findings = await p.process(ctx, Unit(kind="frame", index=0, payload={"ts": 0.0}))
    assert findings and findings[0].signal_type == "casino_marker"
    assert findings[0].modality == "visual"


async def test_audio_promise_detected():
    p = AudioPipeline()
    ctx = _ctx("обещаю доход каждый день")
    findings = await p.process(ctx, Unit(kind="audio", index=0, payload={"ts": 0.0}))
    assert findings and findings[0].signal_type == "speech_promise"


async def test_register_default_pipelines():
    reg = register_default_pipelines(PipelineRegistry())
    assert {p.modality for p in reg.all()} >= {"triage", "text", "ocr", "audio", "visual"}
    assert len(reg.triage_pipelines()) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stubs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.pipelines.stubs'`

- [ ] **Step 3: Create `server/app/pipelines/stubs.py`**

```python
from __future__ import annotations

from app.pipelines.base import Finding, JobContext, Unit
from app.pipelines.explain import Attribution, Explanation
from app.pipelines.registry import PipelineRegistry

# Shared risk lexicon (substring -> weight). Lowercased matching.
PATTERNS: dict[str, float] = {
    "казино": 0.5,
    "casino": 0.5,
    "ставк": 0.4,
    "гарантированн": 0.45,
    "доход": 0.3,
    "инвест": 0.3,
    "реферал": 0.35,
    "бонус": 0.2,
    "пирамид": 0.5,
}


def _matched(text: str) -> list[tuple[str, float]]:
    low = text.lower()
    return [(kw, w) for kw, w in PATTERNS.items() if kw in low]


class TriageClassifier:
    name = "triage_keyword"
    modality = "triage"

    async def process(self, ctx: JobContext, unit: Unit) -> list[Finding]:
        text = unit.payload.get("text", "")
        return [
            Finding(modality="triage", signal_type=f"keyword:{kw}", confidence=w, evidence={"keyword": kw})
            for kw, w in _matched(text)
        ]

    async def explain(self, ctx: JobContext, findings: list[Finding]) -> Explanation | None:
        if not findings:
            return None
        attrs = [Attribution(feature=f.evidence["keyword"], value=1.0, weight=f.confidence) for f in findings]
        return Explanation(
            scope="triage",
            method="feature_importance",
            attributions=attrs,
            summary=f"{len(findings)} risk keyword(s) matched in description",
        )


class TextPipeline:
    name = "text_nlp"
    modality = "text"

    async def process(self, ctx: JobContext, unit: Unit) -> list[Finding]:
        text = unit.payload.get("text", "")
        return [
            Finding(modality="text", signal_type=f"text_signal:{kw}", confidence=w, evidence={"keyword": kw})
            for kw, w in _matched(text)
        ]

    async def explain(self, ctx: JobContext, findings: list[Finding]) -> Explanation | None:
        if not findings:
            return None
        attrs = [Attribution(feature=f.evidence["keyword"], value=1.0, weight=f.confidence) for f in findings]
        return Explanation(
            scope="text",
            method="shap",
            attributions=attrs,
            summary="Token-level contributions (stub SHAP)",
        )


class OCRPipeline:
    name = "ocr_text"
    modality = "ocr"

    async def process(self, ctx: JobContext, unit: Unit) -> list[Finding]:
        if unit.index != 0:
            return []
        low = ctx.description.lower()
        if any(ch.isdigit() for ch in low) or "%" in low:
            return [Finding(modality="ocr", signal_type="on_screen_number", confidence=0.3,
                            evidence={"note": "numeric/percent marker (stub)"}, ts_in_video=0.0)]
        return []

    async def explain(self, ctx: JobContext, findings: list[Finding]) -> Explanation | None:
        if not findings:
            return None
        return Explanation(scope="ocr", method="lime", attributions=[], summary="OCR region attribution (stub)")


class AudioPipeline:
    name = "audio_asr"
    modality = "audio"

    async def process(self, ctx: JobContext, unit: Unit) -> list[Finding]:
        if unit.index != 0:
            return []
        if "доход" in ctx.description.lower():
            return [Finding(modality="audio", signal_type="speech_promise", confidence=0.4,
                            evidence={"transcript": "(stub) обещание дохода"}, ts_in_video=unit.payload.get("ts"))]
        return []

    async def explain(self, ctx: JobContext, findings: list[Finding]) -> Explanation | None:
        if not findings:
            return None
        return Explanation(scope="audio", method="shap", attributions=[], summary="ASR token attribution (stub)")


class VisualPipeline:
    name = "visual_cv"
    modality = "visual"

    async def process(self, ctx: JobContext, unit: Unit) -> list[Finding]:
        if unit.index != 0:
            return []
        low = ctx.description.lower()
        if "казино" in low or "casino" in low:
            return [Finding(modality="visual", signal_type="casino_marker", confidence=0.45,
                            evidence={"note": "casino visual marker (stub)"}, ts_in_video=0.0)]
        return []

    async def explain(self, ctx: JobContext, findings: list[Finding]) -> Explanation | None:
        if not findings:
            return None
        return Explanation(scope="visual", method="gradcam", attributions=[], summary="Saliency over frame (stub)")


def register_default_pipelines(registry: PipelineRegistry) -> PipelineRegistry:
    for p in (TriageClassifier(), TextPipeline(), OCRPipeline(), AudioPipeline(), VisualPipeline()):
        registry.register(p)
    return registry
```

- [ ] **Step 4: Run tests (checkpoint)**

Run: `python -m pytest tests/test_stubs.py -v`
Expected: PASS (5 passed)

---

### Task 9: Extractor (units from buffer)

**Files:**
- Create: `server/app/pipelines/extract.py`
- Test: `server/tests/test_extract.py`

**Interfaces:**
- Consumes: `Unit`, `JobContext` (Task 2).
- Produces: `Extractor` Protocol (`async extract(ctx: JobContext) -> list[Unit]`); `StubExtractor(n_frames: int = 3, n_audio: int = 2)` implementing it. Emits exactly one `text` unit (the description), then `n_frames` `frame` units, then `n_audio` `audio` units.

- [ ] **Step 1: Write the failing test** in `server/tests/test_extract.py`

```python
from app.pipelines.base import JobContext
from app.pipelines.extract import StubExtractor


async def test_extract_emits_units():
    ex = StubExtractor(n_frames=2, n_audio=1)
    units = await ex.extract(JobContext(job_id="j", description="hello", source_meta={}))
    kinds = [u.kind for u in units]
    assert kinds == ["text", "frame", "frame", "audio"]
    text_unit = units[0]
    assert text_unit.payload["text"] == "hello"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_extract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.pipelines.extract'`

- [ ] **Step 3: Create `server/app/pipelines/extract.py`**

```python
from __future__ import annotations

from typing import Protocol

from app.pipelines.base import JobContext, Unit


class Extractor(Protocol):
    async def extract(self, ctx: JobContext) -> list[Unit]: ...


class StubExtractor:
    """Deterministic stand-in for ffmpeg/PyAV frame & audio extraction."""

    def __init__(self, n_frames: int = 3, n_audio: int = 2) -> None:
        self._n_frames = n_frames
        self._n_audio = n_audio

    async def extract(self, ctx: JobContext) -> list[Unit]:
        units: list[Unit] = [Unit(kind="text", index=0, payload={"text": ctx.description})]
        units += [Unit(kind="frame", index=i, payload={"ts": float(i)}) for i in range(self._n_frames)]
        units += [Unit(kind="audio", index=i, payload={"ts": float(i * 5)}) for i in range(self._n_audio)]
        return units
```

- [ ] **Step 4: Run tests (checkpoint)**

Run: `python -m pytest tests/test_extract.py -v`
Expected: PASS (1 passed)

---

### Task 10: RiskAggregator

**Files:**
- Create: `server/app/pipelines/aggregator.py`
- Test: `server/tests/test_aggregator.py`

**Interfaces:**
- Consumes: `Finding` (Task 2); `Attribution`, `Explanation` (Task 2).
- Produces: `aggregate(findings: list[Finding]) -> tuple[float, str, Explanation]` returning `(risk_score in [0,1], category, aggregate_explanation)`.
- Contract: `risk_score = min(1.0, sum(MODALITY_WEIGHT[f.modality] * f.confidence))`. Category: `"gambling"` if any signal mentions казино/ставк/casino; else `"pyramid"` if any mentions пирамид/реферал/инвест/доход; else `"fraud"` if score ≥ 0.5; else `"clean"`. Empty findings → `(0.0, "clean", Explanation(...))`.

- [ ] **Step 1: Write the failing test** in `server/tests/test_aggregator.py`

```python
from app.pipelines.aggregator import aggregate
from app.pipelines.base import Finding


def test_empty_is_clean():
    score, category, exp = aggregate([])
    assert score == 0.0
    assert category == "clean"
    assert exp.scope == "aggregate"


def test_gambling_category_and_score():
    findings = [
        Finding(modality="visual", signal_type="casino_marker", confidence=0.45, evidence={}),
        Finding(modality="text", signal_type="text_signal:казино", confidence=0.5, evidence={}),
    ]
    score, category, exp = aggregate(findings)
    assert category == "gambling"
    assert 0.0 < score <= 1.0
    assert len(exp.attributions) == 2


def test_pyramid_category():
    findings = [Finding(modality="text", signal_type="text_signal:реферал", confidence=0.35, evidence={})]
    _, category, _ = aggregate(findings)
    assert category == "pyramid"


def test_score_clamped():
    findings = [Finding(modality="text", signal_type=f"s{i}", confidence=1.0, evidence={}) for i in range(20)]
    score, _, _ = aggregate(findings)
    assert score == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_aggregator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.pipelines.aggregator'`

- [ ] **Step 3: Create `server/app/pipelines/aggregator.py`**

```python
from __future__ import annotations

from app.pipelines.base import Finding
from app.pipelines.explain import Attribution, Explanation

MODALITY_WEIGHT: dict[str, float] = {
    "triage": 0.2,
    "text": 0.3,
    "ocr": 0.15,
    "audio": 0.2,
    "visual": 0.15,
}

_GAMBLING = ("казино", "ставк", "casino")
_PYRAMID = ("пирамид", "реферал", "инвест", "доход")


def _category(findings: list[Finding], score: float) -> str:
    blob = " ".join(f.signal_type.lower() for f in findings)
    if any(k in blob for k in _GAMBLING):
        return "gambling"
    if any(k in blob for k in _PYRAMID):
        return "pyramid"
    return "fraud" if score >= 0.5 else "clean"


def aggregate(findings: list[Finding]) -> tuple[float, str, Explanation]:
    score = 0.0
    attrs: list[Attribution] = []
    for f in findings:
        contribution = MODALITY_WEIGHT.get(f.modality, 0.1) * f.confidence
        score += contribution
        attrs.append(Attribution(feature=f"{f.modality}:{f.signal_type}", value=f.confidence, weight=contribution))
    score = min(1.0, score)
    category = _category(findings, score)
    exp = Explanation(
        scope="aggregate",
        method="shap",
        attributions=attrs,
        summary=f"risk={score:.2f} category={category} from {len(findings)} finding(s)",
    )
    return score, category, exp
```

- [ ] **Step 4: Run tests (checkpoint)**

Run: `python -m pytest tests/test_aggregator.py -v`
Expected: PASS (4 passed)

---

### Task 11: Orchestrator (run_triage, run_analysis)

**Files:**
- Create: `server/app/pipelines/orchestrator.py`
- Test: `server/tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `JobContext`, `Unit`, `Finding` (Task 2); `Explanation` (Task 2); `PipelineRegistry` (Task 7); `aggregate` (Task 10).
- Produces:
  - `async run_triage(ctx: JobContext, registry: PipelineRegistry) -> tuple[float, list[Finding]]` (priority = `min(1.0, sum(confidence))` over triage findings).
  - `async run_analysis(ctx: JobContext, units: list[Unit], registry: PipelineRegistry) -> tuple[list[Finding], list[Explanation], float, str]` (findings, explanations incl. aggregate last, risk_score, category).
  - `MODALITY_UNIT_KIND: dict[str, str]` mapping analysis modality → unit kind.

- [ ] **Step 1: Write the failing test** in `server/tests/test_orchestrator.py`

```python
from app.pipelines.base import JobContext
from app.pipelines.extract import StubExtractor
from app.pipelines.orchestrator import run_analysis, run_triage
from app.pipelines.registry import PipelineRegistry
from app.pipelines.stubs import register_default_pipelines


def _ctx(desc):
    return JobContext(job_id="j", description=desc, source_meta={})


async def test_run_triage_sets_priority():
    reg = register_default_pipelines(PipelineRegistry())
    priority, findings = await run_triage(_ctx("казино и доход"), reg)
    assert priority > 0.0
    assert findings


async def test_run_triage_clean_zero_priority():
    reg = register_default_pipelines(PipelineRegistry())
    priority, findings = await run_triage(_ctx("котики"), reg)
    assert priority == 0.0
    assert findings == []


async def test_run_analysis_end_to_end():
    reg = register_default_pipelines(PipelineRegistry())
    ctx = _ctx("реклама casino, гарантированный доход 200%")
    units = await StubExtractor().extract(ctx)
    findings, explanations, score, category = await run_analysis(ctx, units, reg)
    assert findings
    assert score > 0.0
    assert category in {"gambling", "pyramid", "fraud"}
    assert explanations[-1].scope == "aggregate"
    # triage findings excluded from analysis findings
    assert all(f.modality != "triage" for f in findings)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.pipelines.orchestrator'`

- [ ] **Step 3: Create `server/app/pipelines/orchestrator.py`**

```python
from __future__ import annotations

from app.pipelines.aggregator import aggregate
from app.pipelines.base import Finding, JobContext, Unit
from app.pipelines.explain import Explanation
from app.pipelines.registry import PipelineRegistry

MODALITY_UNIT_KIND: dict[str, str] = {
    "text": "text",
    "ocr": "frame",
    "audio": "audio",
    "visual": "frame",
}


async def run_triage(ctx: JobContext, registry: PipelineRegistry) -> tuple[float, list[Finding]]:
    text_unit = Unit(kind="text", index=0, payload={"text": ctx.description})
    findings: list[Finding] = []
    for pipeline in registry.triage_pipelines():
        findings.extend(await pipeline.process(ctx, text_unit))
    priority = min(1.0, sum(f.confidence for f in findings))
    return priority, findings


async def run_analysis(
    ctx: JobContext, units: list[Unit], registry: PipelineRegistry
) -> tuple[list[Finding], list[Explanation], float, str]:
    all_findings: list[Finding] = []
    explanations: list[Explanation] = []
    for pipeline in registry.analysis_pipelines():
        wanted = MODALITY_UNIT_KIND.get(pipeline.modality)
        pipeline_findings: list[Finding] = []
        for unit in units:
            if wanted is None or unit.kind == wanted:
                pipeline_findings.extend(await pipeline.process(ctx, unit))
        all_findings.extend(pipeline_findings)
        exp = await pipeline.explain(ctx, pipeline_findings)
        if exp is not None:
            explanations.append(exp)
    score, category, agg_exp = aggregate(all_findings)
    explanations.append(agg_exp)
    return all_findings, explanations, score, category
```

- [ ] **Step 4: Run tests (checkpoint)**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: PASS (3 passed)

---

### Task 12: Workers (base + triage + analysis handlers)

**Files:**
- Create: `server/app/worker/__init__.py` (empty)
- Create: `server/app/worker/base.py`
- Create: `server/app/worker/handlers.py`
- Create: `server/app/worker/triage.py`
- Create: `server/app/worker/analysis.py`
- Test: `server/tests/test_workers.py`

**Interfaces:**
- Consumes: `JobQueue`, `QueueMessage`, `INTAKE`, `ANALYSIS` (Task 3); `JobRepository` (Task 6); `PipelineRegistry` (Task 7); `Extractor` (Task 9); `run_triage`, `run_analysis` (Task 11); `JobContext` (Task 2).
- Produces:
  - `Worker(queue: JobQueue, lane: str, handler, poll_interval: float = 0.1)` with `async run_once() -> bool` and `async run_forever() -> None`.
  - `make_triage_handler(repo, registry, queue)` → async `handler(msg)`.
  - `make_analysis_handler(repo, registry, extractor)` → async `handler(msg)`.
  - `triage.py` / `analysis.py` each expose `async def main() -> None` and `if __name__ == "__main__": asyncio.run(main())`.

- [ ] **Step 1: Write the failing test** in `server/tests/test_workers.py`

```python
import pytest

from app.db.repository import JobRepository
from app.db.session import init_db, make_engine, make_sessionmaker
from app.pipelines.extract import StubExtractor
from app.pipelines.registry import PipelineRegistry
from app.pipelines.stubs import register_default_pipelines
from app.queue.base import ANALYSIS, INTAKE
from app.queue.memory import InMemoryQueue
from app.worker.base import Worker
from app.worker.handlers import make_analysis_handler, make_triage_handler


@pytest.fixture
async def env():
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    repo = JobRepository(make_sessionmaker(engine))
    reg = register_default_pipelines(PipelineRegistry())
    queue = InMemoryQueue()
    return repo, reg, queue


async def test_triage_worker_sets_priority_and_enqueues_analysis(env):
    repo, reg, queue = env
    job_id = await repo.create_job("казино и доход", "tiktok", None, {})
    await queue.enqueue(INTAKE, job_id)
    worker = Worker(queue, INTAKE, make_triage_handler(repo, reg, queue))
    assert await worker.run_once() is True
    job = await repo.get_job(job_id)
    assert job.status == "triaged"
    assert job.priority > 0.0
    msg = await queue.dequeue(ANALYSIS)
    assert msg.job_id == job_id


async def test_analysis_worker_completes_job(env):
    repo, reg, queue = env
    job_id = await repo.create_job("casino, гарантированный доход", None, None, {})
    await queue.enqueue(ANALYSIS, job_id, priority=0.8)
    worker = Worker(queue, ANALYSIS, make_analysis_handler(repo, reg, StubExtractor()))
    assert await worker.run_once() is True
    job = await repo.get_job(job_id)
    assert job.status == "done"
    assert job.risk_score is not None
    assert len(job.findings) > 0
    assert any(e.scope == "aggregate" for e in job.explanations)


async def test_run_once_returns_false_when_empty(env):
    repo, reg, queue = env
    worker = Worker(queue, INTAKE, make_triage_handler(repo, reg, queue))
    assert await worker.run_once() is False


async def test_analysis_worker_marks_failed_on_bad_job(env):
    repo, reg, queue = env
    await queue.enqueue(ANALYSIS, "does-not-exist", priority=0.5)
    worker = Worker(queue, ANALYSIS, make_analysis_handler(repo, reg, StubExtractor()))
    # missing job is a no-op, not a crash
    assert await worker.run_once() is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_workers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.worker.base'`

- [ ] **Step 3: Create empty `server/app/worker/__init__.py`**

- [ ] **Step 4: Create `server/app/worker/base.py`**

```python
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from app.queue.base import JobQueue, QueueMessage

Handler = Callable[[QueueMessage], Awaitable[None]]


class Worker:
    def __init__(self, queue: JobQueue, lane: str, handler: Handler, poll_interval: float = 0.1) -> None:
        self._queue = queue
        self._lane = lane
        self._handler = handler
        self._poll = poll_interval

    async def run_once(self) -> bool:
        msg = await self._queue.dequeue(self._lane)
        if msg is None:
            return False
        try:
            await self._handler(msg)
            await self._queue.ack(msg)
        except Exception:
            await self._queue.nack(msg)
            raise
        return True

    async def run_forever(self) -> None:
        while True:
            did_work = await self.run_once()
            if not did_work:
                await asyncio.sleep(self._poll)
```

- [ ] **Step 5: Create `server/app/worker/handlers.py`**

```python
from __future__ import annotations

from app.db.repository import JobRepository
from app.pipelines.base import JobContext
from app.pipelines.extract import Extractor
from app.pipelines.orchestrator import run_analysis, run_triage
from app.pipelines.registry import PipelineRegistry
from app.queue.base import ANALYSIS, JobQueue, QueueMessage
from app.worker.base import Handler


def _ctx(job) -> JobContext:
    return JobContext(
        job_id=job.id,
        description=job.description,
        source_meta=job.source_meta or {},
        buffer_path=job.buffer_path,
    )


def make_triage_handler(repo: JobRepository, registry: PipelineRegistry, queue: JobQueue) -> Handler:
    async def handler(msg: QueueMessage) -> None:
        job = await repo.get_job(msg.job_id)
        if job is None:
            return
        priority, findings = await run_triage(_ctx(job), registry)
        if findings:
            await repo.add_findings(job.id, findings)
        await repo.set_priority(job.id, priority)
        await repo.set_status(job.id, "triaged")
        await queue.enqueue(ANALYSIS, job.id, priority=priority)

    return handler


def make_analysis_handler(repo: JobRepository, registry: PipelineRegistry, extractor: Extractor) -> Handler:
    async def handler(msg: QueueMessage) -> None:
        job = await repo.get_job(msg.job_id)
        if job is None:
            return
        await repo.set_status(job.id, "processing")
        try:
            ctx = _ctx(job)
            units = await extractor.extract(ctx)
            findings, explanations, score, category = await run_analysis(ctx, units, registry)
            await repo.add_findings(job.id, findings)
            await repo.add_explanations(job.id, explanations)
            await repo.set_risk(job.id, score, category)
            await repo.set_status(job.id, "done")
        except Exception as exc:  # domain failure: mark job, do not loop forever
            await repo.set_status(job.id, "failed", error=str(exc))

    return handler
```

- [ ] **Step 6: Create `server/app/worker/triage.py`**

```python
from __future__ import annotations

import asyncio

from app.config import get_settings
from app.db.repository import JobRepository
from app.db.session import init_db, make_engine, make_sessionmaker
from app.pipelines.registry import PipelineRegistry
from app.pipelines.stubs import register_default_pipelines
from app.queue.base import INTAKE
from app.queue.factory import build_queue
from app.worker.base import Worker
from app.worker.handlers import make_triage_handler


async def main() -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    await init_db(engine)
    repo = JobRepository(make_sessionmaker(engine))
    registry = register_default_pipelines(PipelineRegistry())
    queue = build_queue(settings)
    worker = Worker(queue, INTAKE, make_triage_handler(repo, registry, queue))
    await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 7: Create `server/app/worker/analysis.py`**

```python
from __future__ import annotations

import asyncio

from app.config import get_settings
from app.db.repository import JobRepository
from app.db.session import init_db, make_engine, make_sessionmaker
from app.pipelines.extract import StubExtractor
from app.pipelines.registry import PipelineRegistry
from app.pipelines.stubs import register_default_pipelines
from app.queue.base import ANALYSIS
from app.queue.factory import build_queue
from app.worker.base import Worker
from app.worker.handlers import make_analysis_handler


async def main() -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    await init_db(engine)
    repo = JobRepository(make_sessionmaker(engine))
    registry = register_default_pipelines(PipelineRegistry())
    queue = build_queue(settings)
    worker = Worker(queue, ANALYSIS, make_analysis_handler(repo, registry, StubExtractor()))
    await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
```

> Note: `triage.py`/`analysis.py` import `app.queue.factory.build_queue` (Task 15). Run the worker entrypoints only after Task 15. The handler tests in this task do not import the entrypoints, so they pass now.

- [ ] **Step 8: Run tests (checkpoint)**

Run: `python -m pytest tests/test_workers.py -v`
Expected: PASS (4 passed)

---

### Task 13: Source interface + stub

**Files:**
- Create: `server/app/sources/__init__.py` (empty)
- Create: `server/app/sources/base.py`
- Create: `server/app/sources/stub.py`
- Test: `server/tests/test_sources.py`

**Interfaces:**
- Produces:
  - `SourceItem(video_path: str, description: str, platform: str, url: str | None, meta: dict)`
  - `Source` Protocol: `async fetch() -> AsyncIterator[SourceItem]`
  - `StubSource(items: list[SourceItem] | None = None)` implementing it (yields a single canned item by default).

- [ ] **Step 1: Write the failing test** in `server/tests/test_sources.py`

```python
from app.sources.stub import StubSource


async def test_stub_source_yields_item():
    items = [item async for item in StubSource().fetch()]
    assert len(items) == 1
    assert items[0].platform
    assert items[0].description
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sources.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.sources.stub'`

- [ ] **Step 3: Create empty `server/app/sources/__init__.py`**

- [ ] **Step 4: Create `server/app/sources/base.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterator, Protocol


@dataclass
class SourceItem:
    video_path: str
    description: str
    platform: str
    url: str | None = None
    meta: dict = field(default_factory=dict)


class Source(Protocol):
    def fetch(self) -> AsyncIterator[SourceItem]: ...
```

- [ ] **Step 5: Create `server/app/sources/stub.py`**

```python
from __future__ import annotations

from typing import AsyncIterator

from app.sources.base import SourceItem


class StubSource:
    """Placeholder collector. Real TikTok/Instagram scrapers replace this later."""

    def __init__(self, items: list[SourceItem] | None = None) -> None:
        self._items = items if items is not None else [
            SourceItem(
                video_path="sample/clip.mp4",
                description="Лучшее онлайн казино, гарантированный доход 200% по реферальной ссылке",
                platform="tiktok",
                url="https://example.com/clip",
                meta={"author": "@stub"},
            )
        ]

    async def fetch(self) -> AsyncIterator[SourceItem]:
        for item in self._items:
            yield item
```

- [ ] **Step 6: Run tests (checkpoint)**

Run: `python -m pytest tests/test_sources.py -v`
Expected: PASS (1 passed)

---

### Task 14: API layer + integration test

**Files:**
- Create: `server/app/api/__init__.py` (empty)
- Create: `server/app/api/deps.py`
- Create: `server/app/api/health.py`
- Create: `server/app/api/videos.py`
- Create: `server/app/api/jobs.py`
- Create: `server/app/api/review.py`
- Create: `server/app/api/pipelines.py`
- Create: `server/app/main.py`
- Create: `server/tests/conftest.py`
- Test: `server/tests/test_api.py`
- Test: `server/tests/test_integration.py`

**Interfaces:**
- Consumes: everything from Tasks 2–13, Task 15 (`build_queue`), and Task 17 (`tee_sha256`/`new_hasher`, `NearDupIndex`/`NullNearDupIndex`).
- Produces:
  - `app.main.Components` dataclass: `engine`, `repo: JobRepository`, `queue: JobQueue`, `storage: BlobStorage`, `registry: PipelineRegistry`, `extractor: Extractor`, `neardup: NearDupIndex`.
  - `app.main.build_components(settings) -> Components` (sync, no I/O beyond engine creation).
  - `app.main.init_components(components) -> None` (async, runs `init_db`).
  - `app.main.create_app(settings: Settings | None = None, components: Components | None = None) -> FastAPI`.
  - Routes: `GET /health`, `POST /videos`, `GET /jobs/{job_id}`, `GET /jobs/{job_id}/explanations`, `GET /review-queue`, `GET /pipelines`.

- [ ] **Step 1: Create `server/app/api/deps.py`**

```python
from __future__ import annotations

from fastapi import Request


def get_components(request: Request):
    return request.app.state.components
```

- [ ] **Step 2: Create `server/app/api/health.py`**

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 3: Create `server/app/api/videos.py`**

```python
from __future__ import annotations

import json
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.deps import get_components
from app.dedup.hashing import new_hasher, tee_sha256
from app.pipelines.base import JobContext
from app.queue.base import INTAKE

router = APIRouter()


async def _chunks(upload: UploadFile, chunk_size: int = 1 << 20) -> AsyncIterator[bytes]:
    while True:
        chunk = await upload.read(chunk_size)
        if not chunk:
            break
        yield chunk


@router.post("/videos", status_code=202)
async def ingest_video(
    video: UploadFile = File(...),
    description: str = Form(...),
    source_platform: str | None = Form(None),
    source_url: str | None = Form(None),
    source_meta: str | None = Form(None),
    components=Depends(get_components),
) -> dict:
    if not description.strip():
        raise HTTPException(status_code=422, detail="description must not be empty")
    if video.content_type and not video.content_type.startswith("video/"):
        raise HTTPException(status_code=415, detail="expected a video/* upload")

    meta: dict = {}
    if source_meta:
        try:
            meta = json.loads(source_meta)
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="source_meta must be valid JSON")

    # Stream to a temp buffer key while computing SHA-256 in the same pass (no full file in RAM).
    filename = video.filename or "video.bin"
    temp_key = f"incoming/{uuid.uuid4().hex}/{filename}"
    hasher = new_hasher()
    path = await components.storage.save_stream(temp_key, tee_sha256(_chunks(video), hasher))
    content_hash = hasher.hexdigest()

    # Exact dedup: identical content already ingested -> short-circuit (no new job, no enqueue).
    existing = await components.repo.get_job_by_hash(content_hash)
    if existing is not None:
        await components.storage.delete(temp_key)
        return {"job_id": existing.id, "duplicate": True, "near_duplicates": []}

    job_id = await components.repo.create_job(
        description, source_platform, source_url, meta,
        buffer_path=path, content_hash=content_hash,
    )
    ctx = JobContext(job_id=job_id, description=description, source_meta=meta, buffer_path=path)
    near_duplicates = await components.neardup.find_similar(ctx)  # [] from NullNearDupIndex seam
    await components.neardup.index(ctx)
    await components.queue.enqueue(INTAKE, job_id)
    return {"job_id": job_id, "duplicate": False, "near_duplicates": near_duplicates}
```

> Note: `create_job` takes `buffer_path` and `content_hash` directly (no post-hoc setter). The
> temp buffer key uses a random UUID so the dedup decision happens before any job row exists;
> on an exact-dup hit the temp file is deleted and no job/queue work occurs. `neardup` is the
> seam — `NullNearDupIndex` returns `[]` today; a real perceptual index drops in without API change.

- [ ] **Step 4: Create `server/app/api/jobs.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_components

router = APIRouter()


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, components=Depends(get_components)) -> dict:
    job = await components.repo.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "job_id": job.id,
        "status": job.status,
        "priority": job.priority,
        "risk_score": job.risk_score,
        "category": job.category,
        "description": job.description,
        "error": job.error,
        "findings": [
            {
                "modality": f.modality,
                "signal_type": f.signal_type,
                "confidence": f.confidence,
                "evidence": f.evidence,
                "ts_in_video": f.ts_in_video,
            }
            for f in job.findings
        ],
    }


@router.get("/jobs/{job_id}/explanations")
async def get_explanations(job_id: str, components=Depends(get_components)) -> dict:
    job = await components.repo.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "job_id": job.id,
        "explanations": [
            {"scope": e.scope, "method": e.method, "summary": e.summary, "payload": e.payload}
            for e in job.explanations
        ],
    }
```

- [ ] **Step 5: Create `server/app/api/review.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_components

router = APIRouter()


@router.get("/review-queue")
async def review_queue(limit: int = 50, components=Depends(get_components)) -> dict:
    jobs = await components.repo.review_queue(limit=limit)
    return {
        "items": [
            {
                "job_id": j.id,
                "status": j.status,
                "risk_score": j.risk_score,
                "priority": j.priority,
                "category": j.category,
            }
            for j in jobs
        ]
    }
```

- [ ] **Step 6: Create `server/app/api/pipelines.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_components

router = APIRouter()


@router.get("/pipelines")
async def list_pipelines(components=Depends(get_components)) -> dict:
    return {
        "pipelines": [
            {"name": p.name, "modality": p.modality} for p in components.registry.all()
        ]
    }
```

- [ ] **Step 7: Create `server/app/main.py`**

```python
from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI

from app.api import health, jobs, pipelines, review, videos
from app.config import Settings, get_settings
from app.db.repository import JobRepository
from app.db.session import init_db, make_engine, make_sessionmaker
from app.dedup.neardup import NearDupIndex, NullNearDupIndex
from app.pipelines.extract import Extractor, StubExtractor
from app.pipelines.registry import PipelineRegistry
from app.pipelines.stubs import register_default_pipelines
from app.queue.factory import build_queue
from app.storage.local import LocalStorage


@dataclass
class Components:
    engine: object
    repo: JobRepository
    queue: object
    storage: object
    registry: PipelineRegistry
    extractor: Extractor
    neardup: NearDupIndex


def build_components(settings: Settings) -> Components:
    engine = make_engine(settings.database_url)
    repo = JobRepository(make_sessionmaker(engine))
    queue = build_queue(settings)
    storage = LocalStorage(settings.storage_dir)
    registry = register_default_pipelines(PipelineRegistry())
    return Components(
        engine=engine,
        repo=repo,
        queue=queue,
        storage=storage,
        registry=registry,
        extractor=StubExtractor(),
        neardup=NullNearDupIndex(),
    )


async def init_components(components: Components) -> None:
    await init_db(components.engine)


def create_app(settings: Settings | None = None, components: Components | None = None) -> FastAPI:
    settings = settings or get_settings()
    components = components or build_components(settings)

    app = FastAPI(title="AI Media Watch")
    app.state.components = components

    @app.on_event("startup")
    async def _startup() -> None:
        await init_components(components)

    for module in (health, videos, jobs, review, pipelines):
        app.include_router(module.router)
    return app


app = create_app()
```

- [ ] **Step 8: Create `server/tests/conftest.py`**

```python
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import build_components, create_app, init_components


@pytest_asyncio.fixture
async def app_client(tmp_path):
    settings = Settings(
        queue_backend="memory",
        database_url="sqlite+aiosqlite:///:memory:",
        storage_dir=str(tmp_path / "buffer"),
    )
    components = build_components(settings)
    await init_components(components)
    app = create_app(settings=settings, components=components)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, components
```

- [ ] **Step 9: Write the failing test** in `server/tests/test_api.py`

```python
async def test_health(app_client):
    client, _ = app_client
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_pipelines_listed(app_client):
    client, _ = app_client
    resp = await client.get("/pipelines")
    names = {p["name"] for p in resp.json()["pipelines"]}
    assert "triage_keyword" in names


async def test_post_video_creates_job(app_client):
    client, _ = app_client
    files = {"video": ("clip.mp4", b"\x00\x01\x02", "video/mp4")}
    data = {"description": "казино и доход"}
    resp = await client.post("/videos", files=files, data=data)
    assert resp.status_code == 202
    body = resp.json()
    assert "job_id" in body
    assert body["duplicate"] is False
    assert body["near_duplicates"] == []


async def test_post_duplicate_video_short_circuits(app_client):
    client, _ = app_client
    payload = {"video": ("clip.mp4", b"\x00\x01\x02\x03", "video/mp4")}
    first = await client.post("/videos", files=payload, data={"description": "казино"})
    first_body = first.json()
    assert first_body["duplicate"] is False
    # Same bytes again (different filename) -> exact duplicate, same job_id, not re-queued.
    again = {"video": ("renamed.mp4", b"\x00\x01\x02\x03", "video/mp4")}
    second = await client.post("/videos", files=again, data={"description": "казино"})
    second_body = second.json()
    assert second_body["duplicate"] is True
    assert second_body["job_id"] == first_body["job_id"]


async def test_post_video_rejects_empty_description(app_client):
    client, _ = app_client
    files = {"video": ("clip.mp4", b"\x00", "video/mp4")}
    resp = await client.post("/videos", files=files, data={"description": "   "})
    assert resp.status_code == 422


async def test_get_missing_job_404(app_client):
    client, _ = app_client
    resp = await client.get("/jobs/nope")
    assert resp.status_code == 404
```

- [ ] **Step 10: Write the integration test** in `server/tests/test_integration.py`

```python
from app.queue.base import ANALYSIS, INTAKE
from app.worker.base import Worker
from app.worker.handlers import make_analysis_handler, make_triage_handler


async def test_full_pipeline(app_client):
    client, components = app_client
    files = {"video": ("clip.mp4", b"\x00\x01", "video/mp4")}
    data = {"description": "реклама casino, гарантированный доход 200%, реферальная ссылка"}
    job_id = (await client.post("/videos", files=files, data=data)).json()["job_id"]

    triage = Worker(components.queue, INTAKE,
                    make_triage_handler(components.repo, components.registry, components.queue))
    analysis = Worker(components.queue, ANALYSIS,
                      make_analysis_handler(components.repo, components.registry, components.extractor))

    assert await triage.run_once() is True
    assert await analysis.run_once() is True

    job = (await client.get(f"/jobs/{job_id}")).json()
    assert job["status"] == "done"
    assert job["risk_score"] is not None
    assert job["category"] in {"gambling", "pyramid", "fraud"}
    assert len(job["findings"]) > 0

    exps = (await client.get(f"/jobs/{job_id}/explanations")).json()["explanations"]
    assert any(e["scope"] == "aggregate" for e in exps)

    review = (await client.get("/review-queue")).json()["items"]
    assert review[0]["job_id"] == job_id
```

- [ ] **Step 11: Run the task's tests (checkpoint)**

In our execution order Task 15 (`app.queue.factory.build_queue`) and Task 17 (dedup module:
`tee_sha256`, `NullNearDupIndex`) are already done, so every import in `main.py`/`videos.py`
resolves.

Run: `python -m pytest tests/test_api.py tests/test_integration.py -v`
Expected: PASS (7 passed)

- [ ] **Step 12: Run the FULL suite (checkpoint)**

Run: `python -m pytest -v`
Expected: All PASS (redis integration SKIPPED if no Redis).

---

### Task 15: Redis queue backend + factory

**Files:**
- Create: `server/app/queue/redis.py`
- Create: `server/app/queue/factory.py`
- Test: `server/tests/test_queue_factory.py`
- Test: `server/tests/test_queue_redis.py` (integration, auto-skips without Redis)

**Interfaces:**
- Consumes: `JobQueue`, `QueueMessage`, `INTAKE`, `ANALYSIS` (Task 3); `Settings` (Task 1); `InMemoryQueue` (Task 3).
- Produces:
  - `RedisQueue(redis_url: str)` implementing `JobQueue`. `intake` lane → Redis Stream + consumer group; `analysis` lane → ZSET (`ZADD`/`ZPOPMAX`).
  - `build_queue(settings: Settings) -> JobQueue` returning `InMemoryQueue` or `RedisQueue` per `settings.queue_backend`.

- [ ] **Step 1: Write the failing test** in `server/tests/test_queue_factory.py`

```python
from app.config import Settings
from app.queue.factory import build_queue
from app.queue.memory import InMemoryQueue
from app.queue.redis import RedisQueue


def test_factory_memory():
    assert isinstance(build_queue(Settings(queue_backend="memory")), InMemoryQueue)


def test_factory_redis():
    q = build_queue(Settings(queue_backend="redis", redis_url="redis://localhost:6379/0"))
    assert isinstance(q, RedisQueue)


def test_factory_unknown_raises():
    import pytest
    with pytest.raises(ValueError):
        build_queue(Settings(queue_backend="kafka"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_queue_factory.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.queue.factory'`

- [ ] **Step 3: Create `server/app/queue/redis.py`**

```python
from __future__ import annotations

import redis.asyncio as redis

from app.queue.base import ANALYSIS, INTAKE, QueueMessage

_GROUP = "media-watch"
_CONSUMER = "worker"


class RedisQueue:
    """intake -> Redis Stream (consumer group); analysis -> ZSET (priority)."""

    def __init__(self, redis_url: str) -> None:
        self._r = redis.from_url(redis_url, decode_responses=True)

    def _stream_key(self, lane: str) -> str:
        return f"mw:stream:{lane}"

    def _zset_key(self, lane: str) -> str:
        return f"mw:zset:{lane}"

    async def _ensure_group(self, lane: str) -> None:
        try:
            await self._r.xgroup_create(self._stream_key(lane), _GROUP, id="0", mkstream=True)
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def enqueue(self, lane: str, job_id: str, *, priority: float = 0.0) -> None:
        if lane == ANALYSIS:
            await self._r.zadd(self._zset_key(lane), {job_id: priority})
        else:
            await self._r.xadd(self._stream_key(lane), {"job_id": job_id})

    async def dequeue(self, lane: str) -> QueueMessage | None:
        if lane == ANALYSIS:
            popped = await self._r.zpopmax(self._zset_key(lane), 1)
            if not popped:
                return None
            job_id, score = popped[0]
            return QueueMessage(lane=lane, job_id=job_id, receipt=f"{job_id}|{score}")
        await self._ensure_group(lane)
        resp = await self._r.xreadgroup(
            _GROUP, _CONSUMER, {self._stream_key(lane): ">"}, count=1, block=10
        )
        if not resp:
            return None
        _, entries = resp[0]
        msg_id, fields = entries[0]
        return QueueMessage(lane=lane, job_id=fields["job_id"], receipt=msg_id)

    async def ack(self, msg: QueueMessage) -> None:
        if msg.lane == ANALYSIS:
            return  # zpopmax already removed it
        await self._r.xack(self._stream_key(msg.lane), _GROUP, msg.receipt)
        await self._r.xdel(self._stream_key(msg.lane), msg.receipt)

    async def nack(self, msg: QueueMessage) -> None:
        if msg.lane == ANALYSIS:
            job_id, score = msg.receipt.split("|", 1)
            await self._r.zadd(self._zset_key(msg.lane), {job_id: float(score)})
        # intake: leave unacked so it can be reclaimed by the group later
```

- [ ] **Step 4: Create `server/app/queue/factory.py`**

```python
from __future__ import annotations

from app.config import Settings
from app.queue.base import JobQueue
from app.queue.memory import InMemoryQueue
from app.queue.redis import RedisQueue


def build_queue(settings: Settings) -> JobQueue:
    backend = settings.queue_backend
    if backend == "memory":
        return InMemoryQueue()
    if backend == "redis":
        return RedisQueue(settings.redis_url)
    raise ValueError(f"unknown queue backend: {backend!r}")
```

- [ ] **Step 5: Create `server/tests/test_queue_redis.py`** (integration; auto-skips without Redis)

```python
import pytest

from app.queue.base import ANALYSIS, INTAKE
from app.queue.redis import RedisQueue

pytestmark = pytest.mark.asyncio


async def _redis_available(q) -> bool:
    try:
        await q._r.ping()
        return True
    except Exception:
        return False


async def test_redis_priority_roundtrip():
    q = RedisQueue("redis://localhost:6379/15")
    if not await _redis_available(q):
        pytest.skip("redis not available")
    await q._r.flushdb()
    await q.enqueue(ANALYSIS, "low", priority=0.1)
    await q.enqueue(ANALYSIS, "high", priority=0.9)
    m = await q.dequeue(ANALYSIS)
    assert m.job_id == "high"
    await q.ack(m)


async def test_redis_intake_fifo():
    q = RedisQueue("redis://localhost:6379/15")
    if not await _redis_available(q):
        pytest.skip("redis not available")
    await q._r.flushdb()
    await q.enqueue(INTAKE, "a")
    m = await q.dequeue(INTAKE)
    assert m.job_id == "a"
    await q.ack(m)
```

- [ ] **Step 6: Run tests (checkpoint)**

Run: `python -m pytest tests/test_queue_factory.py tests/test_queue_redis.py -v`
Expected: `test_queue_factory.py` PASS (3 passed); redis tests PASS if Redis is up, otherwise SKIPPED.

- [ ] **Step 7: Run the full suite (now that `main.py` import resolves)**

Run: `python -m pytest -v`
Expected: All tests PASS (redis integration SKIPPED if no Redis).

---

### Task 16: Docker, compose, README

**Files:**
- Create: `server/Dockerfile`
- Create: `server/docker-compose.yml`
- Create: `server/README.md`

**Interfaces:**
- Consumes: app entrypoint `app.main:app`; worker entrypoints `app.worker.triage`, `app.worker.analysis`.
- Produces: runnable container images + compose stack (api, triage worker, analysis worker, redis).

- [ ] **Step 1: Create `server/Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]"
COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create `server/docker-compose.yml`**

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  api:
    build: .
    environment:
      MW_QUEUE_BACKEND: redis
      MW_REDIS_URL: redis://redis:6379/0
      MW_DATABASE_URL: sqlite+aiosqlite:////data/media_watch.db
      MW_STORAGE_DIR: /data/buffer
    volumes:
      - app-data:/data
    ports:
      - "8000:8000"
    depends_on:
      - redis

  triage-worker:
    build: .
    command: ["python", "-m", "app.worker.triage"]
    environment:
      MW_QUEUE_BACKEND: redis
      MW_REDIS_URL: redis://redis:6379/0
      MW_DATABASE_URL: sqlite+aiosqlite:////data/media_watch.db
      MW_STORAGE_DIR: /data/buffer
    volumes:
      - app-data:/data
    depends_on:
      - redis

  analysis-worker:
    build: .
    command: ["python", "-m", "app.worker.analysis"]
    environment:
      MW_QUEUE_BACKEND: redis
      MW_REDIS_URL: redis://redis:6379/0
      MW_DATABASE_URL: sqlite+aiosqlite:////data/media_watch.db
      MW_STORAGE_DIR: /data/buffer
    volumes:
      - app-data:/data
    depends_on:
      - redis

# Later, for multiple machines / durability, swap SQLite for Postgres:
#   postgres:
#     image: postgres:16-alpine
#     environment:
#       POSTGRES_PASSWORD: mw
#     ports: ["5432:5432"]
#   then set MW_DATABASE_URL=postgresql+asyncpg://postgres:mw@postgres/postgres
#   (add asyncpg to dependencies)

volumes:
  app-data:
```

> Note: SQLite over a shared volume works for the single-machine demo. For multiple machines, switch `MW_DATABASE_URL` to Postgres (commented above) — the queue (Redis) already scales across machines unchanged.

- [ ] **Step 3: Create `server/README.md`**

````markdown
# AI Media Watch — Backend (скелет)

Приём видео+описания → буфер → лёгкий триаж (приоритет) → приоритетная очередь →
мультимодальные стаб-пайплайны → риск-оценка с объяснениями (SHAP/LIME-контракт) → БД → API.

## Локальный запуск (без Docker, in-memory очередь)

```bash
cd server
python -m pip install -e ".[dev]"
cp .env.example .env            # при желании поправить
uvicorn app.main:app --reload   # API на http://localhost:8000/docs
# в отдельных терминалах (для memory-очереди воркеры должны делить процесс с API —
# для реальной обработки используйте Docker/Redis ниже)
```

> In-memory очередь живёт внутри одного процесса. Для разнесённых воркеров используйте Redis.

## Запуск со стеком (Redis + воркеры)

```bash
cd server
docker compose up --build
# api: http://localhost:8000/docs
```

## Проверка вручную

```bash
curl -F "video=@clip.mp4;type=video/mp4" -F "description=казино и гарантированный доход" \
  http://localhost:8000/videos
# -> {"job_id": "..."}
curl http://localhost:8000/jobs/<job_id>
curl http://localhost:8000/jobs/<job_id>/explanations
curl http://localhost:8000/review-queue
```

## Тесты

```bash
cd server
python -m pytest -v
```

## Как подключить реальную модель

1. Реализуй класс с атрибутами `name`, `modality` и методами `process(ctx, unit)`,
   `explain(ctx, findings)` (см. `app/pipelines/base.py`).
2. Зарегистрируй его в `app/pipelines/stubs.py::register_default_pipelines`
   (или в собственной функции регистрации).
3. Реальное извлечение кадров/аудио — замени `StubExtractor` в `app/pipelines/extract.py`.
4. Реальные скраперы — реализуй `app/sources/base.py::Source` вместо `StubSource`.
5. Near-dup (перцептивный dedup) — реализуй `app/dedup/neardup.py::NearDupIndex`
   (фингерпринт из `ctx.buffer_path` + векторный индекс) вместо `NullNearDupIndex`.
   Точный SHA-256 dedup уже работает на `POST /videos`.

## Архитектура

См. `docs/superpowers/specs/2026-06-24-ai-media-watch-backend-design.md`.
````

- [ ] **Step 4: Final full-suite checkpoint**

Run: `python -m pytest -v`
Expected: All tests PASS (redis integration SKIPPED if no Redis). Optionally bring up Redis (`docker compose up redis -d`) and run `MW...` redis tests to confirm they pass.

---

### Task 17: Dedup module (exact hash + near-dup seam)

> **Execution order:** run this task right after Task 6 (it needs only Task 2's `JobContext`), before Task 7. Task 14 consumes it.

**Files:**
- Create: `server/app/dedup/__init__.py` (empty)
- Create: `server/app/dedup/hashing.py`
- Create: `server/app/dedup/neardup.py`
- Test: `server/tests/test_dedup.py`

**Interfaces:**
- Consumes: `JobContext` (Task 2).
- Produces:
  - `new_hasher()` → a `hashlib.sha256` object.
  - `async tee_sha256(chunks: AsyncIterator[bytes], hasher) -> AsyncIterator[bytes]` — yields each chunk unchanged while updating `hasher` (single-pass hashing during upload streaming).
  - `NearDupIndex` Protocol: `async find_similar(ctx: JobContext) -> list[str]`; `async index(ctx: JobContext) -> None`.
  - `NullNearDupIndex()` implementing it (no-op seam: `find_similar` → `[]`, `index` → `None`).

- [ ] **Step 1: Write the failing test** in `server/tests/test_dedup.py`

```python
import hashlib

from app.dedup.hashing import new_hasher, tee_sha256
from app.dedup.neardup import NullNearDupIndex
from app.pipelines.base import JobContext


async def _agen(parts):
    for p in parts:
        yield p


async def test_tee_sha256_passes_through_and_hashes():
    hasher = new_hasher()
    out = b"".join([chunk async for chunk in tee_sha256(_agen([b"ab", b"cd"]), hasher)])
    assert out == b"abcd"
    assert hasher.hexdigest() == hashlib.sha256(b"abcd").hexdigest()


async def test_null_neardup_returns_empty():
    idx = NullNearDupIndex()
    ctx = JobContext(job_id="j", description="d", source_meta={})
    assert await idx.find_similar(ctx) == []
    assert await idx.index(ctx) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_dedup.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.dedup.hashing'`

- [ ] **Step 3: Create empty `server/app/dedup/__init__.py`**

- [ ] **Step 4: Create `server/app/dedup/hashing.py`**

```python
from __future__ import annotations

import hashlib
from typing import AsyncIterator


def new_hasher():
    return hashlib.sha256()


async def tee_sha256(chunks: AsyncIterator[bytes], hasher) -> AsyncIterator[bytes]:
    """Yield each chunk unchanged while feeding it to `hasher` (single-pass)."""
    async for chunk in chunks:
        hasher.update(chunk)
        yield chunk
```

- [ ] **Step 5: Create `server/app/dedup/neardup.py`**

```python
from __future__ import annotations

from typing import Protocol

from app.pipelines.base import JobContext


class NearDupIndex(Protocol):
    async def find_similar(self, ctx: JobContext) -> list[str]: ...

    async def index(self, ctx: JobContext) -> None: ...


class NullNearDupIndex:
    """Seam for perceptual near-duplicate detection.

    A real implementation computes a perceptual fingerprint (pHash over frames,
    audio fingerprint, or an embedding) from ``ctx.buffer_path`` and queries a
    similarity/vector index. The skeleton ships this no-op so the call sites and
    API contract exist now.
    """

    async def find_similar(self, ctx: JobContext) -> list[str]:
        return []

    async def index(self, ctx: JobContext) -> None:
        return None
```

- [ ] **Step 6: Run tests (checkpoint)**

Run: `python -m pytest tests/test_dedup.py -v`
Expected: PASS (2 passed)

---

## Self-Review

**1. Spec coverage:**
- §1 scope (video+description ingest, buffer, queue abstraction, two-tier, pipeline framework, XAI, DB, API, workers, tests, docker) → Tasks 1–16. ✓
- §3 data flow (POST → buffer → intake → triage → priority → analysis → aggregate → DB → review) → Tasks 12, 14 integration test. ✓
- §4 queue (intake FIFO + analysis priority; memory + redis) → Tasks 3, 15. ✓
- §5 pipeline framework (protocol, registry, orchestrator, extractor, stubs) → Tasks 2, 7, 8, 9, 11. ✓
- §6 explainability (Explanation contract, per-model + aggregate, SHAP/LIME stubs) → Tasks 2, 8, 10, 14 (`/jobs/{id}/explanations`). ✓
- §7 DB models (Job/Finding/Explanation incl. `description`) → Task 5. ✓
- §8 API (videos, jobs, jobs/explanations, review-queue, pipelines, health) → Task 14. ✓
- §9 error handling (statuses, failed+error, 404/415/422) → Tasks 12, 14. ✓
- §10 tests (in-memory testability, unit + integration) → every task + Task 14. ✓
- §11 stack, §12 structure → Task 1 + file layout. ✓
- Source interface + stub (scope note) → Task 13. ✓

**2. Placeholder scan:** No "TBD"/"add error handling"/"similar to" — all steps carry complete code. Stub bodies are intentional, deterministic implementations, not placeholders. ✓

**3. Type consistency:**
- `Finding(modality, signal_type, confidence, evidence, ts_in_video)` consistent across Tasks 2/6/8/10/11/12. ✓
- `Explanation(scope, method, attributions, summary, media)` consistent across Tasks 2/6/8/10. ✓
- `JobQueue.enqueue(lane, job_id, *, priority)` / `dequeue` / `ack` / `nack` consistent across Tasks 3/12/15. ✓
- `JobRepository` method names match between Task 6 definition and Tasks 12/14 usage (`create_job`, `get_job`, `set_status`, `set_priority`, `set_risk`, `add_findings`, `add_explanations`, `review_queue`, `_update`). ✓
- `run_triage` / `run_analysis` signatures match between Task 11 and Task 12. ✓
- `build_queue` / `Components` / `create_app` match between Task 15/14 and worker entrypoints (Task 12). ✓

**Cross-task ordering note:** Task 14 (`main.py`) imports `app.queue.factory` (Task 15). Task 14 explicitly defers its final test run until Task 15 is complete (Steps 12–13). If executing strictly in order, do Task 15 immediately after Task 14's code is written, before the Task 14 checkpoint — both are called out inline.
