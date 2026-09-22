"""Long-running monitor — keeps one browser open on the persistent profile."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.monitor import main as monitor_main


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="US Visa slot monitor (session-reuse)")
    parser.add_argument("--once", action="store_true", help="Single check then exit")
    args = parser.parse_args()
    monitor_main(once=args.once)
