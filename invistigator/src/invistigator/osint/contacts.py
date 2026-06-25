import re

# email
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# телефон в международном формате: + и 10-15 цифр, между ними допускаем пробелы/-/()
_PHONE_RE = re.compile(r"\+\d[\d\s\-()]{8,16}\d")

# whatsapp: wa.me/<digits> или api.whatsapp.com/send?phone=<digits>
_WA_RE = re.compile(
    r"(?:wa\.me/|api\.whatsapp\.com/send\?phone=)(\d{6,15})", re.IGNORECASE
)

# крипто-кошельки
_BTC_RE = re.compile(r"\b(?:bc1[a-z0-9]{25,90}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b")
_ETH_RE = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
_TON_RE = re.compile(r"\b[EU]Q[A-Za-z0-9_\-]{46}\b")

# прочие соцсети (берём ссылку целиком, нормализуем без схемы)
_SOCIAL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?"
    r"((?:tiktok\.com|vk\.com|youtube\.com|youtu\.be|twitter\.com|x\.com|"
    r"facebook\.com|fb\.com|ok\.ru)/[^\s,)]+)",
    re.IGNORECASE,
)


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        key = it.lower()
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out


def extract_contacts(*texts: str | None) -> dict:
    """Извлекает контакты из переданных текстов (bio, full_name). Чистая функция."""
    blob = "\n".join(t for t in texts if t)

    phones = [re.sub(r"[\s\-()]", "", p) for p in _PHONE_RE.findall(blob)]
    socials = _SOCIAL_RE.findall(blob)
    wallets = _BTC_RE.findall(blob) + _ETH_RE.findall(blob) + _TON_RE.findall(blob)

    return {
        "phones": _dedup(phones),
        "emails": _dedup(_EMAIL_RE.findall(blob)),
        "whatsapp": _dedup(_WA_RE.findall(blob)),
        "crypto_wallets": _dedup(wallets),
        "other_socials": _dedup(socials),
    }
