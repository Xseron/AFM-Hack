import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
import whois
from dns import resolver as dns_resolver

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def _host(url: str | None) -> str | None:
    if not url:
        return None
    if "://" not in url:
        url = "http://" + url
    host = urlparse(url).hostname
    if not host:
        return None
    return host[4:] if host.startswith("www.") else host


def _domain_age_days(creation) -> int | None:
    if isinstance(creation, list):
        creation = creation[0] if creation else None
    if not isinstance(creation, datetime):
        return None
    if creation.tzinfo is None:
        creation = creation.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - creation).days


def analyze_domain(url: str | None, timeout: int = 8) -> dict:
    """Анализ домена из link-in-bio. Бесплатно/без ключа. Сетевые сбои не роняют."""
    result = {
        "final_url": None, "domain": _host(url), "domain_age_days": None,
        "registrar": None, "nameservers": [], "redirect_chain": [], "page_title": None,
    }
    if not url:
        return result

    # 1. Следуем редиректам, тянем финальный URL + заголовок страницы.
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout,
                          headers={"User-Agent": "Mozilla/5.0"}) as client:
            resp = client.get(url if "://" in url else "http://" + url)
        result["final_url"] = str(resp.url)
        result["domain"] = _host(str(resp.url))
        result["redirect_chain"] = [str(h.url) for h in resp.history] + [str(resp.url)]
        m = _TITLE_RE.search(resp.text or "")
        if m:
            result["page_title"] = m.group(1).strip()[:200]
    except Exception:
        pass  # оставляем домен, вытащенный из исходного url

    domain = result["domain"]
    if not domain:
        return result

    # 2. WHOIS — возраст домена и регистратор.
    try:
        rec = whois.whois(domain)
        result["domain_age_days"] = _domain_age_days(rec.creation_date)
        reg = rec.registrar
        result["registrar"] = reg[0] if isinstance(reg, list) else reg
    except Exception:
        pass

    # 3. DNS — nameservers.
    try:
        answers = dns_resolver.resolve(domain, "NS")
        result["nameservers"] = sorted(str(r).rstrip(".") for r in answers)
    except Exception:
        pass

    return result
