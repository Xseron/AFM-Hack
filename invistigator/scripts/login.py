"""Разовый интерактивный вход в Instagram → сохраняет session-файл.

Запусти ОДИН раз: `python scripts/login.py`.
Дальше сервис только переиспользует сессию, не логинясь повторно (анти-бан).
"""
import sys
from getpass import getpass

import instaloader

sys.path.insert(0, "src")
from invistigator.config import get_settings  # noqa: E402


def main() -> None:
    settings = get_settings()
    username = settings.ig_username or input("IG username: ").strip()
    password = settings.ig_password or getpass("IG password: ")

    L = instaloader.Instaloader(quiet=True)
    if settings.http_proxy:
        L.context._session.proxies.update(
            {"http": settings.http_proxy, "https": settings.http_proxy}
        )
        print("Логин идёт через прокси.")
    else:
        print("HTTP_PROXY не задан — вход с твоего реального IP (осознанный выбор).")
    try:
        L.login(username, password)
    except instaloader.exceptions.TwoFactorAuthRequiredException:
        secret = settings.ig_2fa_secret.replace(" ", "")
        if secret:
            import pyotp

            code = pyotp.TOTP(secret).now()
            print(f"2FA-код сгенерирован из ключа: {code}")
        else:
            code = input("2FA код: ").strip()
        L.two_factor_login(code)

    L.save_session_to_file(settings.ig_session_file)
    print(f"OK — сессия сохранена в '{settings.ig_session_file}'")


if __name__ == "__main__":
    main()
