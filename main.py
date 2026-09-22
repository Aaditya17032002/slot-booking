"""Entry point — prefer the scripts/ workflow.

  python scripts/login.py        # one-time manual session
  python scripts/check_slots.py  # single check + Telegram
  python scripts/monitor.py      # keep browser open, poll
"""

from __future__ import annotations

import argparse

from src.monitor import main


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="US Visa slot monitor (session-reuse)")
    parser.add_argument("--once", action="store_true", help="Single check then exit")
    args = parser.parse_args()
    main(once=args.once)
