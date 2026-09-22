from __future__ import annotations

import logging
import sys
import time
import traceback

from .browser import open_browser
from .checker import notify_outcome, perform_check
from .config import get_settings
from .notifier import Notifier
from .state import SlotStateStore
from . import human


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def main(once: bool = False) -> None:
    """
    Keep ONE browser open on the persistent profile and poll periodically.
    Never auto-defeats Cloudflare — if session dies, Telegram asks you to re-login.
    """
    settings = get_settings()
    settings.ensure_dirs()
    setup_logging(settings.log_level)
    log = logging.getLogger("monitor")

    notifier = Notifier(settings)
    store = SlotStateStore(settings.state_file)

    log.info(
        "Monitor starting | consulates=%s | poll=%ss–%ss | once=%s | profile=%s",
        settings.consulate_list,
        settings.poll_min_seconds,
        settings.poll_max_seconds,
        once,
        settings.session_dir.resolve(),
    )
    notifier.notify_status(
        "Monitor started\n\n"
        f"Watching: {', '.join(settings.consulate_list)}\n"
        f"Visa: {settings.visa_category} ({settings.visa_type})\n\n"
        "Uses your saved browser profile.\n"
        "If Cloudflare/session expires, re-run:\n"
        "python scripts/login.py"
    )

    consecutive_errors = 0

    # One long-lived browser — do not relaunch every cycle
    with open_browser(settings, headless=settings.headless) as session:
        assert session.page is not None

        while True:
            try:
                outcome = perform_check(
                    session.page,
                    settings,
                    store,
                    screenshot_fn=session.screenshot,
                )
                notify_outcome(notifier, settings, outcome)

                if outcome.status == "ok":
                    consecutive_errors = 0
                    delay = human.random_poll_interval(
                        settings.poll_min_seconds,
                        settings.poll_max_seconds,
                    )
                else:
                    consecutive_errors += 1
                    delay = human.next_backoff(
                        consecutive_errors,
                        settings.backoff_base_seconds,
                        settings.backoff_max_seconds,
                    )
                    log.warning(
                        "status=%s — pausing %.0fs (fix: scripts/login.py)",
                        outcome.status,
                        delay,
                    )

                if once:
                    log.info("Single check done (status=%s)", outcome.status)
                    return

            except KeyboardInterrupt:
                log.info("Stopped by user")
                notifier.notify_status("Monitor stopped.")
                return
            except Exception as exc:
                consecutive_errors += 1
                delay = human.next_backoff(
                    consecutive_errors,
                    settings.backoff_base_seconds,
                    settings.backoff_max_seconds,
                )
                log.error("Check failed: %s\n%s", exc, traceback.format_exc())
                if consecutive_errors in (1, 3, 6) or once:
                    notifier.notify_challenge("Unexpected error", str(exc)[:500])
                if once:
                    return

            log.info("Browser stays open — sleeping %.0fs…", delay)
            time.sleep(delay)


if __name__ == "__main__":
    main()
