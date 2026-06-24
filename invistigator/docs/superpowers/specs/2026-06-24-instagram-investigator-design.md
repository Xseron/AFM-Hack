# Instagram Investigator — Design

**Дата:** 2026-06-24
**Статус:** утверждён, готов к плану реализации

## Цель

Сервис (`invistigator`), который по списку Instagram-аккаунтов достаёт метаданные
профиля (ник, описание, link-in-bio, фото), пишет их в таблицу, и если в bio найдена
Telegram-ссылка — триггерит соседний сервис `telegramcrawler` для риск-анализа канала.

Часть антифрод-пайплайна хакатона (детект нелегального гэмблинга / пирамид / мошенничества).

## Контекст

Соседние сервисы в `hakaton/`:
- **telegramcrawler** — FastAPI + Telethon + SQLite + LLM. API: `POST /channels {"channels": [...]}`.
- **server** — основное приложение.

`invistigator` строится с нуля, зеркалит стек и структуру telegramcrawler.

## Ключевые решения

| Вопрос | Решение |
|---|---|
| Метод скрейпинга | Бёрнер-аккаунт + `instaloader` (сессия переиспользуется) |
| Источник входа | Свой FastAPI: `POST /accounts {"usernames": [...]}` |
| Хранилище | CSV (`media/` для фото). Google Sheets — опциональная замена позже |
| Триггер TG | HTTP POST на запущенный telegramcrawler `/channels` |

## Структура проекта

```
invistigator/
  pyproject.toml          # fastapi, uvicorn, instaloader, httpx, pydantic-settings, python-dotenv
  .env.example
  .gitignore              # .env, *.session, media/, *.csv
  scripts/login.py        # РАЗОВЫЙ интерактивный логин → сохраняет .session
  src/invistigator/
    __init__.py
    config.py             # настройки из .env (pydantic-settings)
    schemas.py            # pydantic-модели запроса/ответа
    scraper.py            # instaloader-обёртка: сессия + rate-limit + backoff
    linkdetect.py         # поиск Telegram-ссылок в bio/external_url (чистая логика)
    storage.py            # запись строки в CSV + скачивание фото в media/
    trigger.py            # httpx POST на telegramcrawler /channels
    pipeline.py           # оркестратор одного username
    api.py                # FastAPI: POST /accounts, GET /health
  tests/
```

## Компоненты

### config.py
Читает из `.env`:
- `IG_USERNAME`, `IG_PASSWORD` — креды бёрнера (логин только через `scripts/login.py`)
- `IG_SESSION_FILE` — путь к session-файлу (по умолчанию `invistigator_session`)
- `MIN_DELAY_SEC=8`, `MAX_DELAY_SEC=20` — рандомная пауза между профилями
- `MAX_PROFILES_PER_HOUR=120` — потолок
- `HTTP_PROXY` — опциональный прокси
- `CRAWLER_URL` — базовый URL telegramcrawler (например `http://localhost:8001`)
- `CSV_PATH` — путь к таблице результатов
- `MEDIA_DIR` — папка для скачанных фото

### scraper.py
Обёртка над `instaloader.Instaloader`:
- При старте загружает сессию из `IG_SESSION_FILE` (если нет — понятная ошибка с подсказкой запустить `scripts/login.py`).
- `fetch_profile(username) -> ProfileData`: один вызов `Profile.from_username(L.context, username)`.
  Достаёт `full_name`, `biography`, `external_url`, `profile_pic_url`, `followers`, `is_private`.
- Между вызовами — рандомный `sleep(MIN_DELAY..MAX_DELAY)` + `instaloader.RateController`.
- Backoff: на `429 / 401 / ChallengeRequiredException / ConnectionException` —
  экспоненциальная пауза, и сигнал пайплайну остановить весь батч.
- Маппинг исключений в статус: `ProfileNotExistsException → not_found`, приватный → `private`.

### linkdetect.py
Чистая функция `find_telegram_links(text: str) -> list[str]`:
- Регекс по `t.me/<name>`, `telegram.me/<name>`, `telegram.dog/<name>` (с/без `https://`, с `@`).
- Возвращает нормализованные `@<name>` (без `/joinchat`/`+invite` приватных — их пропускаем, crawler их не возьмёт).
- Применяется к `external_url` И `biography`.
- Голые `@упоминания` НЕ считаются Telegram (в IG это меншены).

### storage.py
- `append_row(profile: ProfileData)`: дозапись строки в CSV (создаёт заголовок при первом запуске).
- `download_photo(url, username)`: скачивает фото в `MEDIA_DIR/<username>.jpg`, возвращает путь; при ошибке — пишет URL.
- Колонки: `username, full_name, biography, external_url, profile_pic, followers, is_private, telegram_links, tg_triggered, status, scraped_at`.

### trigger.py
- `post_channels(channels: list[str]) -> bool`: `httpx.post(f"{CRAWLER_URL}/channels", json={"channels": channels})`.
- Ошибка/недоступность crawler не роняет пайплайн — логируется, `tg_triggered=error`.

### pipeline.py
`process_username(username)`:
1. `scraper.fetch_profile()` → при ошибке записать строку со `status` и выйти.
2. `linkdetect.find_telegram_links(external_url + biography)`.
3. `storage.append_row(...)`.
4. Если есть TG-ссылки → `trigger.post_channels(...)`, выставить `tg_triggered`.
`process_batch(usernames)`: последовательно с паузами; при backoff-сигнале — стоп.

### api.py
- `POST /accounts {"usernames": [...]}` → запускает `process_batch` в `BackgroundTasks`, сразу отдаёт `{"job_id", "accepted": N}`.
- `GET /health` → `{"status": "ok"}`.

## Модель данных

`ProfileData` (pydantic):
```
username: str
full_name: str | None
biography: str | None
external_url: str | None
profile_pic: str          # локальный путь или URL
followers: int | None
is_private: bool
telegram_links: list[str]
tg_triggered: str         # "yes" | "no" | "error"
status: str               # ok | private | not_found | rate_limited | error
scraped_at: str           # ISO-время
```

## Стратегия анти-бана (ядро)

1. **Логин один раз** — `scripts/login.py` сохраняет `.session`; рантайм только грузит сессию, не логинится повторно.
2. **Только метаданные профиля** — один GraphQL-запрос на аккаунт, без листания постов/подписчиков.
3. **Rate-limit** — `RateController` + рандом 8–20 сек, потолок ~120 профилей/час (конфиг).
4. **Бёрнер** — креды только в `.env` (gitignored), аккаунт-расходник.
5. **Backoff** — на 429/401/Challenge/Connection — экспоненциальная пауза + стоп батча.
6. **Прокси опционально** — `HTTP_PROXY` (резидентный IP).
7. **Асинхронно** — `POST /accounts` сразу возвращает job_id, скрейпинг в фоне.

## Обработка ошибок

- Каждый username в `try/except`: ошибка пишется в `status`, батч продолжается.
- Backoff-исключения (бан/лимит) — исключение: останавливают весь батч, чтобы не углублять бан.
- Недоступность telegramcrawler не роняет скрейпинг (`tg_triggered=error`).

## Тестирование (pytest)

- `linkdetect` — чистая логика, табличные тесты (t.me, telegram.me, @, мусор, приватные invite).
- `storage` — запись CSV в tmp, проверка колонок/дозаписи.
- `trigger` — мок httpx, проверка payload и graceful-fail.
- `scraper`/`pipeline` — мок instaloader, проверка маппинга статусов и порядка вызовов.
- Живой Instagram в тестах не дёргаем.

## Вне scope (YAGNI)

- Google Sheets (легко добавить позже как замену storage).
- Прокси-ротация/пул (один прокси из env достаточно).
- Скрейпинг постов/сторис/подписчиков.
- Авторетрай забаненного аккаунта.
```
