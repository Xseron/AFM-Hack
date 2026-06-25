# AI Media Watch — How to run

---

## 1. Backend + Dashboard — `:8000`

```bash
uvicorn app.main:app --reload
```

- Дашборд: http://localhost:8000/
- API-доки: http://localhost:8000/docs

Со стеком (Redis + отдельные воркеры):

```bash
cd server
docker compose up --build
```

---

## 2. Investigator (OSINT + граф)

```bash
pip install -e ".[dev]"
python scripts/login.py
uvicorn invistigator.api:get_app --factory --reload --port 8010
```

---

## 3. Telegram crawler (риск-анализ каналов)

```bash
cd telegramcrawler
pip install -e ".[dev]"
uvicorn aimw.api:get_app --factory --reload --port 8020
```

---

## 4. Parser (запись Instagram Reels) - анти-детект браузер + CDP

```bash
cd parser
python -m pip install -r requirements.txt
python -m playwright install chromium
```

```
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\David\Programming\hakaton\parser\state\chrome-profile" "https://www.instagram.com/reels/"
```

```bash
# боевой режим — заливает рилсы в бэкенд
python -m reels_recorder --server-url http://localhost:8000

# сухой прогон (без заливки)
python -m reels_recorder --max-reels 3
```