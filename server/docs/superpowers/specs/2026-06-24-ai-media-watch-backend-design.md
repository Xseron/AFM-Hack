# AI Media Watch — Backend (скелет): дизайн

**Дата:** 2026-06-24
**Статус:** утверждён, готов к плану реализации
**Кейс:** «AI Media Watch: выявление признаков незаконного игорного бизнеса и финансовых пирамид в социальных сетях»

## 1. Контекст и цель

Бэкенд принимает видеоконтент из соцсетей (TikTok/Instagram и др.), буферизует его,
прогоняет через мультимодальные ИИ-пайплайны (видео, аудио, текст, субтитры, визуальные
маркеры), формирует **риск-оценку** контента с **объяснением** (findings + XAI: SHAP/LIME/…)
и **приоритизирует** материалы для дальнейшей ручной проверки.

Цель этого документа — спроектировать **начало бекенда (скелет)**: рабочую сквозную
архитектуру со всеми абстракциями и стаб-пайплайнами. Реальные ИИ-модели и скраперы
подключаются позже без изменения каркаса.

### Что входит в scope (скелет)

- Приём по HTTP: **видео + текст описания** (потоковая буферизация видео), расширяемый контракт входа.
- **Точная дедупликация** на intake: SHA-256 контента, уникальный индекс — дубликат не запускает тяжёлые пайплайны.
- **Seam для near-dup**: интерфейс `NearDupIndex` + no-op стаб (перцептивный dedup подключается позже).
- Абстракция хранилища (буфер) с локальной реализацией.
- Абстракция очереди задач с **приоритизацией** (in-memory + Redis).
- Двухуровневая обработка: лёгкий триаж-классификатор → приоритет → тяжёлый анализ.
- Фреймворк пайплайнов (реестр + оркестратор) с **доменными стаб-пайплайнами**.
- Слой explainability (SHAP/LIME/… контракт) со стабами.
- Хранение Job / Finding / Explanation в БД.
- API: загрузка, статус джобы, объяснения, приоритизированная очередь на проверку.
- Воркеры как отдельные процессы (triage + analysis).
- Тесты (TDD) поверх in-memory реализаций.
- Docker-compose (Redis сейчас; Postgres — закомментирован на потом).

### Что вне scope (подключается позже)

- Реальные скраперы TikTok/Instagram (коллекторы) — отдельный компонент, шлёт в `POST /videos`.
  В скелете: интерфейс источника + стаб.
- Реальные ИИ-модели (ASR, CV, NLP-классификаторы) — подключаются через протокол `Pipeline`.
- Реальные библиотеки `shap` / `lime` / Grad-CAM — в скелете только контракт + стабы.
- AuthN/AuthZ, многопользовательность, продакшн-деплой — не в этом этапе.

## 2. Архитектура

Каждый компонент — одна ответственность, общается через явный интерфейс, тестируется отдельно.

| Компонент | Назначение | Сейчас → потом |
|---|---|---|
| **API (FastAPI)** | приём загрузки, статусы, объяснения, очередь на проверку | — |
| **BlobStorage** | буфер видео (стрим на диск, не в RAM) | `LocalStorage` → S3/MinIO |
| **DB (job store)** | Job + Finding + Explanation, статусы, риск | SQLite → Postgres (смена DSN) |
| **JobQueue** | приоритетная шина задач за интерфейсом, 2 лейна | `InMemory` / `Redis` |
| **Triage worker** | лёгкий классификатор → приоритет | 1 процесс → N |
| **Analysis worker** | тяжёлые мультимодальные пайплайны | 1 процесс → N (и N машин) |
| **Pipeline framework** | реестр + оркестратор пайплайнов | стабы → реальные модели |
| **Explainability** | единый контракт XAI поверх пайплайнов | стабы → SHAP/LIME/Grad-CAM |
| **Source (collector) iface** | контракт источника видео | стаб → реальные скраперы |

### Принцип масштабирования

«Одна машина с воркерами сейчас → несколько машин потом» обеспечивается абстракцией
`JobQueue`. На Redis переход на несколько машин = направить воркеры на тот же Redis,
код не меняется. Triage и Analysis воркеры масштабируются независимо (triage дешёвый,
analysis — бутылочное горлышко).

## 3. Поток данных

```
collector/клиент → POST /videos (видео + текст описания + метаданные поста)
        → стрим в BlobStorage + SHA-256 (один проход)
        → exact dedup: hash уже есть? → да: вернуть существующий job_id (duplicate=true), НЕ ставить в очередь
        → нет: near-dup seam (find_similar → []) → Job(status=queued, content_hash) в БД
        → INTAKE-очередь (FIFO) → отдаём job_id (+ near_duplicates)

[Triage worker] consume(intake)
        → TriageClassifier (дёшево: текст поста/субтитры + 1 кадр)
        → preliminary risk → Job.priority
        → enqueue(analysis, score=priority)

[Analysis worker] consume(analysis, по приоритету — высокий риск первым)
        → extract units (кадры/сегменты/аудио)
        → мультимодальные пайплайны (visual/audio/ocr/text) → Finding[]
        → каждый пайплайн опц. explain() → Explanation[]
        → RiskAggregator → risk_score + category + aggregate Explanation
        → save Finding/Explanation, Job.status=done | failed(+error)

client → GET /review-queue           (приоритизированный список на проверку)
       → GET /jobs/{id}              (статус, risk, findings)
       → GET /jobs/{id}/explanations (per-model + aggregate XAI)
```

## 4. Очередь и приоритизация

`JobQueue` — единый интерфейс с двумя лейнами:

- `intake` — FIFO, сырые джобы после загрузки.
- `analysis` — **priority** (score = риск от триажа), тяжёлый разбирает сверху вниз.

```python
class JobQueue(Protocol):
    async def enqueue(self, lane: str, job_id: str, *, priority: float = 0.0) -> None: ...
    async def consume(self, lane: str) -> AsyncIterator[QueueMessage]: ...
    async def ack(self, lane: str, message: QueueMessage) -> None: ...
    async def nack(self, lane: str, message: QueueMessage) -> None: ...
```

Реализации:

- **InMemoryQueue** — `deque` для FIFO, `heapq` для priority. Для тестов и быстрого
  локального запуска без Redis.
- **RedisQueue** — `intake` на Redis Stream + consumer group (ack/reclaim упавших);
  `analysis` на Redis Sorted Set (ZSET, score=priority) с атомарным pop максимума.

Выбор бэкенда — через настройку `QUEUE_BACKEND=memory|redis` (фабрика).

## 4a. Дедупликация

Два уровня, чтобы не гонять тяжёлые пайплайны на повторах:

- **Точный dedup (сейчас)** — SHA-256 контента считается на том же проходе, что и стрим в
  буфер (без загрузки файла в RAM). `Job.content_hash` с уникальным индексом. На intake:
  если хэш уже встречался — возвращаем существующий `job_id` с `duplicate=true`, временный
  буфер удаляем, в очередь НЕ ставим. Дёшево, высокий ROI.
- **Near-dup (seam на потом)** — перцептивный dedup (pHash по кадрам, аудио-фингерпринт,
  эмбеддинги + векторный индекс). В скелете — интерфейс `NearDupIndex` (`find_similar(ctx)`,
  `index(ctx)`) + no-op `NullNearDupIndex`. Вызывается на intake (сейчас всегда `[]`), результат
  отдаётся как `near_duplicates`. Реальная реализация подключается без смены API; в отдельный
  сервис выносится только если векторный индекс понадобится масштабировать независимо.

```python
class NearDupIndex(Protocol):
    async def find_similar(self, ctx: JobContext) -> list[str]: ...  # похожие job_id
    async def index(self, ctx: JobContext) -> None: ...
```

## 5. Фреймворк пайплайнов (ключевое требование — гибкость)

```python
class Pipeline(Protocol):
    name: str
    modality: str  # "text" | "audio" | "visual" | "ocr" | "triage" | "aggregate"
    async def process(self, ctx: JobContext, unit: Unit) -> list[Finding]: ...
    async def explain(self, ctx: JobContext, findings: list[Finding]) -> Explanation | None: ...
```

- `PipelineRegistry` с декоратором `@register` — новая модель = новый класс + регистрация,
  оркестратор и API не трогаем.
- `Orchestrator` — для джобы извлекает units (через `Extractor`), запускает зарегистрированные
  пайплайны нужной модальности, собирает `Finding[]` и `Explanation[]`, вызывает `RiskAggregator`.
- `Extractor` — абстракция извлечения units из буферизованного видео (кадры/сегменты/аудио).
  В скелете — стаб; реальная реализация (ffmpeg/PyAV/opencv) — позже.

### Доменные пайплайны (в скелете — стабы с корректными контрактами)

- `TriageClassifier` (modality=triage) — лёгкий, на тексте поста/метаданных: эвристика по
  паттернам («гарантированный доход», «казино», реферальные схемы) → preliminary risk → приоритет.
- `TextPipeline` (text) — подпись/метаданные поста → NLP-сигналы.
- `OCRPipeline` (ocr) — текст на экране + субтитры.
- `AudioPipeline` (audio) — извлечение аудио → ASR → анализ речи (обещания дохода, инвест-призывы).
- `VisualPipeline` (visual) — кадры → логотипы казино/беттинг-маркеры/визуальные признаки.
- `RiskAggregator` (aggregate) — сводит `Finding[]` всех модальностей → `risk_score` (0..1),
  `category` (gambling | pyramid | fraud | clean), aggregate `Explanation`.

## 6. Explainability (XAI)

Единый контракт поверх разных методов (SHAP, LIME, feature-importance, Grad-CAM, …):

```python
@dataclass
class Attribution:
    feature: str       # токен / признак / регион
    value: str | float
    weight: float      # вклад в решение (знак = направление)

@dataclass
class Explanation:
    scope: str         # "triage" | "text" | "audio" | "visual" | "ocr" | "aggregate"
    method: str        # "shap" | "lime" | "feature_importance" | "gradcam" | ...
    attributions: list[Attribution]
    media: bytes | None  # напр. saliency-картинка
    summary: str         # человекочитаемое объяснение
```

Два уровня:

- **Per-model / per-modality** — `Pipeline.explain()` по каждому классификатору (токены подписи,
  ASR-транскрипт, OCR-текст; saliency по кадрам).
- **Job-level (aggregate)** — `RiskAggregator` отдаёт SHAP-style разбивку вклада каждой
  модальности/находки в итоговый `risk_score`.

В скелете стабы выдают данные в форме SHAP/LIME (правильный JSON-контракт). Объяснения
считаются и сохраняются на этапе analysis (ленивый расчёт по запросу — оптимизация на потом).
Тяжёлые либы (`shap`, `lime`) в скелет не тащим — только контракт + стабы.

## 7. Модель данных (БД)

- **Job**: `id`, `status` (queued|triaged|processing|done|failed), `description` (текст
  описания поста), `content_hash` (SHA-256, **уникальный индекс** — точный dedup),
  `source_platform`, `source_url`, `source_meta(JSON)`, `buffer_path`,
  `priority`, `risk_score`, `category`, `error`, `created_at`, `updated_at`.
- **Finding**: `id`, `job_id`, `modality`, `signal_type`, `evidence(JSON)`, `confidence`,
  `ts_in_video`, `created_at`.
- **Explanation**: `id`, `job_id`, `scope`, `method`, `payload(JSON)`, `media_path`, `summary`,
  `created_at`.

Риск-оценка джобы = `risk_score` + `category` на `Job` + список `Finding` (признаки) +
`Explanation` (XAI). Доступ через репозиторий (`JobRepository`), не напрямую из API/воркеров.

## 8. API

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/videos` | потоковая загрузка **видео + текст описания** (+ опц. метаданные) → SHA-256 + exact dedup → создаёт Job, кладёт в intake, отдаёт `{job_id, duplicate, near_duplicates}` |
| GET | `/jobs/{id}` | статус, risk_score, category, findings |
| GET | `/jobs/{id}/explanations` | per-model + aggregate XAI по джобе |
| GET | `/review-queue` | джобы, отсортированные по риску/приоритету (на проверку) |
| GET | `/pipelines` | список зарегистрированных пайплайнов (интроспекция) |
| GET | `/health` | health check |

**Контракт `POST /videos`** (multipart/form-data, расширяемый):

- `video` — файл (стримится в `BlobStorage`, не в RAM); обязательное.
- `description` — текст описания/подписи поста; обязательное (используется триажем и `TextPipeline`).
- `source_meta` — опц. JSON (platform, url, author, …) для расширения без смены API.

Расширяемость: входной контракт описан Pydantic-моделью `VideoIngestRequest` с фиксированными
полями (`video`, `description`) и свободным `source_meta(JSON)` — новые модальности/поля
(доп. файлы, отдельные субтитры и т.п.) добавляются без ломающих изменений.

Ответ: `{"job_id": str, "duplicate": bool, "near_duplicates": [job_id, ...]}`. При точном
дубликате `duplicate=true` и `job_id` указывает на исходную джобу (новая не создаётся, в
очередь ничего не ставится).

Валидация загрузки: content-type/размер видео, непустое `description`, отклонять пустые.

## 9. Обработка ошибок

- Статусы Job: `queued → triaged → processing → done | failed`.
- Воркеры — try/except на задачу; в Redis Stream ack только после успеха, упавшие
  переобрабатываются consumer-group (reclaim). На исключении — `Job.status=failed` + `error`.
- API: 404 на неизвестный `job_id`, 413/415 на невалидную загрузку.

## 10. Тестирование (TDD)

`InMemoryQueue` и `LocalStorage` делают весь воркер-конвейер тестируемым без внешней инфры.

- Юнит: `JobQueue` (FIFO + priority порядок), `PipelineRegistry`, `Orchestrator` со стабами,
  `RiskAggregator`, репозиторий, эндпоинты (httpx/TestClient).
- Интеграция: `POST /videos` → triage → analysis (in-memory) → `GET /jobs/{id}` = done с
  findings → `GET /jobs/{id}/explanations` отдаёт XAI.

## 11. Стек

Python 3.11+, FastAPI, Uvicorn, Pydantic v2 + pydantic-settings, SQLAlchemy 2.0 async +
aiosqlite (→ Postgres), redis-py (async), pytest + httpx. ffmpeg/PyAV/opencv — позже (стаб).

## 12. Структура проекта

```
server/
  app/
    main.py              # FastAPI app factory
    config.py            # pydantic-settings (env)
    api/
      videos.py jobs.py review.py pipelines.py health.py
    storage/
      base.py local.py
    db/
      base.py models.py session.py repository.py
    queue/
      base.py memory.py redis.py factory.py
    sources/
      base.py stub.py    # интерфейс источника + стаб (скраперы — потом)
    dedup/
      hashing.py         # потоковый SHA-256 (tee)
      neardup.py         # NearDupIndex протокол + NullNearDupIndex (seam)
    pipelines/
      base.py            # Pipeline протокол, Unit, Finding, JobContext
      registry.py orchestrator.py extract.py aggregator.py
      explain.py         # Explanation/Attribution + XAI-контракт
      stubs.py           # Triage/Text/OCR/Audio/Visual стабы
    worker/
      base.py
      triage.py          # python -m app.worker.triage
      analysis.py        # python -m app.worker.analysis
  tests/
  docker-compose.yml     # redis (+ postgres закомментирован)
  Dockerfile
  pyproject.toml
  .env.example
  README.md
```

## 13. Открытые вопросы / на будущее

- On-demand (ленивый) расчёт XAI вместо хранения — при росте объёма.
- Near-dup (перцептивный) dedup: реализация `NearDupIndex` поверх векторного индекса
  (seam уже заложен; точный SHA-256 dedup — сделан).
- Backpressure/лимиты при непрерывном сборе большого объёма.
- Переход `analysis`-лейна на Kafka/RabbitMQ, если понадобится durability/throughput.
