"""Send a one-off Telegram test message using .env credentials."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import get_settings
from src.notifier import Notifier


def main() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env first.")
    Notifier(settings).notify_status(
        "Telegram test OK\n\n"
        "Your US Visa monitor can reach this chat."
    )
    print("Sent.")


if __name__ == "__main__":
    main()
