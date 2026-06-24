# AI Media Watch — Telegram Crawler & Risk Analyzer

Краулит Telegram-каналы и оценивает их на признаки незаконного игорного бизнеса,
финансовых пирамид и мошенничества (RU + KZ) с объяснениями и цитатами-доказательствами.

## Setup
```bash
pip install -e ".[dev]"
cp .env.example .env   # заполнить креды
python scripts/login.py  # разовый вход в Telegram (создаёт session-файл)
```

## Run
```bash
uvicorn aimw.api:get_app --factory --reload
```

## API
- `POST /channels` `{"channels": ["@chan", "t.me/chan2"]}` → риск-отчёты
- `GET /channels?sort=risk` → приоритизированный список
- `GET /channels/{username}` → один отчёт
- `GET /health`

## Тесты
```bash
python -m pytest -v
```

## Архитектура
- `crawler` — Telethon: посты + картинки
- `prefilter` — лексикон RU+KZ, дешёвый отсев
- `analyzer` — OpenRouter LLM + vision, per-post оценка
- `scoring` — агрегация в риск-оценку 0–100
- `storage` — SQLite
- `pipeline` — оркестратор; `api` — FastAPI
