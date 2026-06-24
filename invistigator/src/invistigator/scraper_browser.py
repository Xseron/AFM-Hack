import random
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import instaloader
from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

from invistigator.config import Settings
from invistigator.scraper import BanSignal, profile_from_user_json
from invistigator.schemas import ProfileData

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _collect_user_nodes(obj, out: list) -> None:
    """Собирает все узлы профиля (dict с 'username' и 'biography') из graphql-ответа."""
    if isinstance(obj, dict):
        if "username" in obj and "biography" in obj:
            out.append(obj)
        for v in obj.values():
            _collect_user_nodes(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect_user_nodes(v, out)


def _pick_user_node(graphql_jsons: list, target: str):
    """Выбирает узел нужного профиля: совпадение по нику + самый полный (с подписчиками)."""
    nodes: list = []
    for data in graphql_jsons:
        _collect_user_nodes(data, nodes)
    if not nodes:
        return None

    target = target.lower()
    matching = [n for n in nodes if (n.get("username") or "").lower() == target]
    pool = matching or nodes
    # предпочитаем узел со счётчиком подписчиков (он самый полный)
    rich = [n for n in pool if "edge_followed_by" in n]
    return (rich or pool)[0]


def _load_cookies(settings: Settings) -> list[dict]:
    """Тянет куки авторизации из instaloader-сессии для переиспользования в браузере."""
    loader = instaloader.Instaloader(quiet=True)
    try:
        loader.load_session_from_file(settings.ig_username, settings.ig_session_file)
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Session-файл '{settings.ig_session_file}' не найден — "
            "сначала запусти `python scripts/login.py`"
        ) from exc
    return [
        {"name": c.name, "value": c.value, "domain": ".instagram.com", "path": "/"}
        for c in loader.context._session.cookies
    ]


def _proxy_config(http_proxy: str | None) -> dict | None:
    if not http_proxy:
        return None
    u = urlparse(http_proxy)
    cfg = {"server": f"{u.scheme}://{u.hostname}:{u.port}"}
    if u.username:
        cfg["username"] = u.username
        cfg["password"] = u.password or ""
    return cfg


class BrowserScraper:
    """Скрейпер через реальный браузер (Playwright). Устойчивее к бану, чем голый API."""

    def __init__(self, settings: Settings, headless: bool = True):
        self.settings = settings
        self._last_fetch = 0.0
        cookies = _load_cookies(settings)

        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(
            headless=headless, proxy=_proxy_config(settings.http_proxy)
        )
        self.context = self.browser.new_context(user_agent=UA, locale="en-US")
        self.context.add_cookies(cookies)

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_fetch
        delay = random.uniform(self.settings.min_delay_sec, self.settings.max_delay_sec)
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_fetch = time.monotonic()

    def fetch_profile(self, username: str) -> ProfileData:
        username = username.strip().lstrip("@").rstrip("/").split("/")[-1]
        self._throttle()

        page = self.context.new_page()
        graphql_jsons: list = []
        statuses: list = []

        def on_response(resp):
            statuses.append(resp.status)
            if "graphql" in resp.url:
                try:
                    graphql_jsons.append(resp.json())
                except Exception:
                    pass

        page.on("response", on_response)
        try:
            page.goto(
                f"https://www.instagram.com/{username}/",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            if "/accounts/login" in page.url:
                raise BanSignal("сессия невалидна — редирект на логин")
            try:
                page.wait_for_selector("header", timeout=15000)
            except PWTimeout:
                pass
            page.wait_for_timeout(2500)  # дать graphql-запросам отстреляться
            content = page.content()
        except BanSignal:
            raise
        except Exception:
            return ProfileData(username=username, status="error", scraped_at=_now())
        finally:
            if not page.is_closed():
                page.close()

        if 429 in statuses:
            raise BanSignal(f"rate-limited (429) на {username}")
        if 401 in statuses or 403 in statuses:
            raise BanSignal(f"бан/челлендж на {username}")

        user = _pick_user_node(graphql_jsons, username)
        if user is not None:
            return profile_from_user_json(user, username)

        if "isn't available" in content or "page isn't" in content:
            return ProfileData(username=username, status="not_found", scraped_at=_now())
        return ProfileData(username=username, status="error", scraped_at=_now())

    def close(self) -> None:
        try:
            self.context.close()
            self.browser.close()
            self._pw.stop()
        except Exception:
            pass
