"""One-time Telethon login to create a reusable session file."""
from aimw.config import get_settings
from telethon import TelegramClient


def main():
    s = get_settings()
    with TelegramClient(s.telegram_session, s.telegram_api_id, s.telegram_api_hash) as c:
        me = c.loop.run_until_complete(c.get_me())
        print(f"Logged in as {me.username or me.first_name}; session saved.")


if __name__ == "__main__":
    main()
