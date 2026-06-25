# Investigator — Instagram

Тянет метаданные Instagram-профиля (ник, описание, link-in-bio, фото),
пишет в CSV-таблицу, и если в bio найдена Telegram-ссылка — триггерит
соседний `telegramcrawler` для риск-анализа канала.

## Setup
```bash
pip install -e ".[dev]"
cp .env.example .env          # заполнить креды бёрнера
python scripts/login.py       # РАЗОВЫЙ вход (создаёт session-файл)
```

## Run
```bash
uvicorn invistigator.api:get_app --factory --reload --port 8010
```
`telegramcrawler` должен быть запущен на `CRAWLER_URL` (по умолчанию `:8000`).

## API
- `POST /accounts` `{"usernames": ["nasa", "some_casino_kz"]}` → `{"job_id", "accepted"}`
  (скрейпинг идёт в фоне, результаты дозаписываются в `CSV_PATH` и `JSONL_PATH`)
- `GET /graph?min_shared=2` → граф связей (nodes/edges JSON) по накопленным
  результатам: связывает аккаунты по общим домену/телефону/кошельку/аватарке/
  кросс-платформенному username. `min_shared` — мин. число аккаунтов на атрибут.
- `GET /health`

## OSINT
По каждому профилю собираются открытые сигналы (всё бесплатно, без ключей):
- **контакты** из bio: телефоны, email, WhatsApp, крипто-кошельки, ссылки на др. соцсети;
- **домен** из link-in-bio: финальный URL после редиректов, возраст домена (WHOIS), nameservers, заголовок страницы;
- **username** на TikTok/VK/X/YouTube/GitHub/Facebook/OK/Telegram (best-effort);
- **аватарка**: pHash (детект переиспользования) + ссылка на reverse-search.

Управление: `OSINT_ENABLED`, `OSINT_TIMEOUT_SEC`, `USERNAME_SEARCH_PLATFORMS` в `.env`.
Результаты дублируются в `JSONL_PATH` (источник для графа `GET /graph`).

## Анти-бан
- Логин **один раз** через `scripts/login.py`, дальше переиспользуется сессия.
- Только метаданные профиля — один запрос на аккаунт, без листания постов.
- Рандомные паузы 8–20 сек, потолок ~120 профилей/час (`.env`).
- Backoff на 429/401/challenge — батч останавливается.
- Бёрнер-аккаунт + опциональный `HTTP_PROXY`.

## Тесты
```bash
python -m pytest -v
```

## Архитектура
- `scraper` — instaloader: сессия + rate-limit + backoff (`BanSignal`)
- `linkdetect` — поиск Telegram-каналов в bio/external_url
- `storage` — CSV + скачивание фото в `media/`
- `trigger` — httpx POST на telegramcrawler `/channels`
- `pipeline` — оркестратор; `api` — FastAPI
