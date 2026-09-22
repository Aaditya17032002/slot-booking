"""
One-shot slot check using the persisted browser profile.
Does not log you in — run scripts/login.py first if needed.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.browser import open_browser
from src.checker import notify_outcome, perform_check
from src.config import get_settings
from src.monitor import setup_logging
from src.notifier import Notifier
from src.state import SlotStateStore


def main() -> None:
    settings = get_settings()
    settings.ensure_dirs()
    setup_logging(settings.log_level)

    notifier = Notifier(settings)
    store = SlotStateStore(settings.state_file)

    # Prefer visible browser for first checks so you can see what happens
    with open_browser(settings, headless=settings.headless) as session:
        assert session.page is not None
        outcome = perform_check(
            session.page,
            settings,
            store,
            screenshot_fn=session.screenshot,
        )
        notify_outcome(notifier, settings, outcome)
        print(f"status={outcome.status} slots={len(outcome.slots)} new={len(outcome.new_slots)}")
        if outcome.detail:
            print(outcome.detail)
        if outcome.status != "ok":
            raise SystemExit(2)


if __name__ == "__main__":
    main()
