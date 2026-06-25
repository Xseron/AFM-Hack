from concurrent.futures import ThreadPoolExecutor

import httpx

# username → URL-шаблон. Best-effort: часть сайтов блокирует ботов.
PLATFORMS: dict[str, str] = {
    "tiktok": "https://www.tiktok.com/@{u}",
    "vk": "https://vk.com/{u}",
    "twitter": "https://x.com/{u}",
    "youtube": "https://www.youtube.com/@{u}",
    "github": "https://github.com/{u}",
    "facebook": "https://www.facebook.com/{u}",
    "ok": "https://ok.ru/{u}",
    "telegram": "https://t.me/{u}",
}


def _check(client: httpx.Client, platform: str, url: str) -> str | None:
    try:
        resp = client.get(url)
    except Exception:
        return None
    # 200 — профиль есть; 404/410 — нет. Прочее (403/429/5xx) считаем неизвестным.
    if resp.status_code == 200:
        return f"{platform}:{url}"
    return None


def search_username(
    username: str, platforms: dict[str, str] | None = None, timeout: int = 8
) -> list[str]:
    """Ищет username на наборе платформ. Возвращает 'platform:url' там, где найден."""
    username = username.strip().lstrip("@")
    if not username:
        return []
    platforms = platforms or PLATFORMS
    targets = {p: tpl.format(u=username) for p, tpl in platforms.items()}

    found: list[str] = []
    with httpx.Client(
        follow_redirects=True, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"}
    ) as client:
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = pool.map(lambda kv: _check(client, kv[0], kv[1]), targets.items())
    for r in results:
        if r:
            found.append(r)
    return found


def platforms_from_csv(csv: str | None) -> dict[str, str] | None:
    """Фильтрует PLATFORMS по CSV-списку имён из настроек (или None → все)."""
    if not csv:
        return None
    names = {n.strip().lower() for n in csv.split(",") if n.strip()}
    return {p: tpl for p, tpl in PLATFORMS.items() if p in names} or None
