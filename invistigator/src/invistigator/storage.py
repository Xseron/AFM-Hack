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


def append_row(profile: ProfileData, csv_path: str) -> None:
    """Дозаписывает строку в CSV, создавая заголовок при первом запуске."""
    exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
    row = profile.model_dump()
    row["telegram_links"] = ", ".join(profile.telegram_links)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in COLUMNS})
