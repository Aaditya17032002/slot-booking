"""
Open REAL Google Chrome (not Playwright) for login.

Cloudflare sees a normal browser. After you log in, leave Chrome open
and run:  python scripts/check_slots.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.browser import find_chrome_executable, launch_real_chrome, wait_for_cdp
from src.config import get_settings
from src.monitor import setup_logging


def main() -> None:
    settings = get_settings()
    settings.ensure_dirs()
    setup_logging(settings.log_level)

    chrome = find_chrome_executable(settings.chrome_path)
    profile = settings.session_dir.resolve()

    print()
    print("=" * 60)
    print("  Use your REAL Chrome (Cloudflare-friendly)")
    print("=" * 60)
    print(f"  Chrome  : {chrome}")
    print(f"  Profile : {profile}")
    print(f"  CDP     : {settings.cdp_url}")
    print()
    print("  IMPORTANT")
    print("  • Close other Chrome windows that use this same profile")
    print("  • This is a dedicated visa profile (not your daily Chrome)")
    print("  • Pass Cloudflare + login yourself in the window")
    print("  • Leave Chrome OPEN when done")
    print()
    print("  Then run:  python scripts/check_slots.py")
    print("=" * 60)
    print()

    if settings.usvisa_username:
        print(f"  Username hint: {settings.usvisa_username}")
        print()

    launch_real_chrome(settings, open_url=True)
    wait_for_cdp(settings.cdp_url, timeout_s=45.0)

    print("Chrome is open. Complete Cloudflare + login there.")
    print()
    try:
        input("Press ENTER here when you are fully logged in… ")
    except KeyboardInterrupt:
        print("\nOK — leave Chrome open if you already logged in.")
        return

    print()
    print("Session lives inside that Chrome window/profile.")
    print("Keep Chrome running, then:")
    print("  python scripts/check_slots.py")
    print("  python scripts/monitor.py")
    print()
    print("(Monitor attaches to this Chrome — it will not fight Cloudflare.)")


if __name__ == "__main__":
    main()
