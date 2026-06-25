import os
from urllib.parse import quote

import imagehash
from PIL import Image


def _reverse_url(profile_pic_url: str | None) -> str | None:
    """Готовая ссылка на ручной reverse-search (авто требует платного ключа)."""
    if not profile_pic_url or not profile_pic_url.startswith("http"):
        return None
    return "https://lens.google.com/uploadbyurl?url=" + quote(profile_pic_url, safe="")


def analyze_image(local_path: str | None, profile_pic_url: str | None = None) -> dict:
    """pHash локальной аватарки (для детекта переиспользования) + reverse-search URL."""
    result = {"avatar_phash": None, "reverse_image_url": _reverse_url(profile_pic_url)}
    if not local_path or not os.path.exists(local_path):
        return result
    try:
        with Image.open(local_path) as im:
            result["avatar_phash"] = str(imagehash.phash(im))
    except Exception:
        pass
    return result
