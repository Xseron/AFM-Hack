import csv
import os
from pathlib import Path

import httpx

from invistigator.schemas import ProfileData

COLUMNS = [
    "username",
    "full_name",
    "biography",
    "external_url",
    "profile_pic",
    "followers",
    "is_private",
    "telegram_links",
    "tg_triggered",
    "status",
    "scraped_at",
    "phones",
    "emails",
    "whatsapp",
    "crypto_wallets",
    "other_socials",
    "final_url",
    "domain",
    "domain_age_days",
    "registrar",
    "nameservers",
    "redirect_chain",
    "page_title",
    "accounts_found",
    "avatar_phash",
    "reverse_image_url",
    "osint_error",
]


def download_photo(url: str, username: str, media_dir: str, proxy: str | None = None) -> str:
    """Скачивает фото профиля в media_dir/<username>.jpg. При ошибке возвращает URL."""
    if not url:
        return ""
    try:
        Path(media_dir).mkdir(parents=True, exist_ok=True)
        dest = Path(media_dir) / f"{username}.jpg"
        with httpx.Client(proxy=proxy, timeout=30, follow_redirects=True) as client:
            resp = client.get(url)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return str(dest)
    except Exception:
        return url


def _flatten_osint(profile: ProfileData) -> dict:
    """Плоские строковые значения OSINT-полей для CSV (списки → ', ')."""
    o = profile.osint
    if o is None:
        return {}
    flat: dict = {}
    for key, val in o.model_dump().items():
        if isinstance(val, list):
            flat[key] = ", ".join(map(str, val))
        else:
            flat[key] = val if val is not None else ""
    return flat


def append_row(profile: ProfileData, csv_path: str) -> None:
    """Дозаписывает строку в CSV, создавая заголовок при первом запуске."""
    exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
    row = profile.model_dump()
    row["telegram_links"] = ", ".join(profile.telegram_links)
    row.update(_flatten_osint(profile))
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in COLUMNS})


def append_jsonl(profile: ProfileData, path: str) -> None:
    """Дозаписывает полный ProfileData (с osint) построчно — источник для графа."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(profile.model_dump_json() + "\n")


def read_jsonl(path: str) -> list[ProfileData]:
    """Читает JSONL обратно в список ProfileData. Нет файла → []."""
    if not os.path.exists(path):
        return []
    out: list[ProfileData] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(ProfileData.model_validate_json(line))
    return out
