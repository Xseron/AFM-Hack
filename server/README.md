# AI Media Watch — Backend (скелет)

Приём видео+описания → буфер → точный dedup (SHA-256) → лёгкий триаж (приоритет) →
приоритетная очередь → мультимодальные стаб-пайплайны → риск-оценка с объяснениями
(SHAP/LIME-контракт) → БД → API.

## Локальный запуск (без Docker, in-memory очередь)

```bash
cd server
python -m pip install -e ".[dev]"
cp .env.example .env            # при желании поправить
uvicorn app.main:app --reload   # API на http://localhost:8000/docs
```

> In-memory очередь живёт внутри одного процесса. Для разнесённых воркеров используйте Redis (ниже).

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
# -> {"job_id": "...", "duplicate": false, "near_duplicates": []}
curl http://localhost:8000/jobs/<job_id>
curl http://localhost:8000/jobs/<job_id>/explanations
curl http://localhost:8000/review-queue
```

## Реальные модели (Whisper / CLIP / OCR)

По умолчанию работают стаб-пайплайны (быстро, без тяжёлых зависимостей). Чтобы включить
реальные модели из `audio_detect.py` / `casino_clip_detector.py` / `scam_image_detector.py`:

```bash
pip install -e ".[models]"        # faster-whisper, torch, transformers, opencv, rapidocr, ...
# в .env:
MW_MODELS_ENABLED=true
MW_MODEL_DEVICE=cpu               # или cuda
```

При старте сервер грузит модели один раз (warm). Если какой-то зависимости/весов нет —
этот пайплайн отключается с логом, остальные работают. Пайплайны:

- **triage** (easy classifier) — Whisper транскрипт → русский scam-лексикон → приоритет
  (фолбэк на текст описания, если Whisper недоступен). Транскрипт кэшируется и переиспользуется.
- **audio** — Whisper + лексикон · **ocr** — OCR кадров + embedding · **visual** — CLIP казино.
- Риск-агрегация включает и triage-сигнал; категория (gambling/pyramid/fraud/clean) — по
  signal_type + evidence.

## Тесты

```bash
cd server
python -m pytest -v
```

## Как подключить реальную модель / источник

1. Пайплайн: класс с `name`, `modality`, `process(ctx, unit)`, `explain(ctx, findings)`
   (см. `app/pipelines/base.py`); зарегистрируй в `app/pipelines/stubs.py::register_default_pipelines`.
2. Извлечение кадров/аудио: замени `StubExtractor` в `app/pipelines/extract.py` (ffmpeg/PyAV/opencv).
3. Скраперы: реализуй `app/sources/base.py::Source` вместо `StubSource`.
4. Near-dup: реализуй `app/dedup/neardup.py::NearDupIndex` (фингерпринт + векторный индекс)
   вместо `NullNearDupIndex`. Точный SHA-256 dedup уже работает на `POST /videos`.

## Архитектура

См. `docs/superpowers/specs/2026-06-24-ai-media-watch-backend-design.md`
и план `docs/superpowers/plans/2026-06-24-ai-media-watch-backend.md`.
