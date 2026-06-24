import re

# t.me/<name>, telegram.me/<name>, telegram.dog/<name> — с/без https://, с/без @.
# Захватываем имя канала/группы; приватные инвайты (joinchat / +hash) пропускаем,
# т.к. telegramcrawler принимает только публичные @username.
_TG_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:t(?:elegram)?\.me|telegram\.dog)/@?([A-Za-z0-9_]{4,32})",
    re.IGNORECASE,
)

_SKIP = {"joinchat", "s", "share", "proxy", "addstickers", "setlanguage"}


def find_telegram_links(*texts: str | None) -> list[str]:
    """Находит публичные Telegram-каналы в переданных текстах.

    Возвращает нормализованные '@username' без дублей, сохраняя порядок.
    Голые @упоминания (без t.me) не считаются Telegram — в Instagram это меншены.
    """
    found: list[str] = []
    seen: set[str] = set()
    for text in texts:
        if not text:
            continue
        for name in _TG_RE.findall(text):
            low = name.lower()
            if low in _SKIP or low.startswith("+"):
                continue
            handle = f"@{name}"
            if low not in seen:
                seen.add(low)
                found.append(handle)
    return found
