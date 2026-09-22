"""
Import cookies from your everyday Chrome profile into the visa profile.

Close ALL Chrome windows first (cookie DB is locked while Chrome runs).

This copies usvisascheduling.com cookies after you've logged in normally
in your daily browser. Cloudflare cf_clearance may still be IP/UA bound —
if checks fail, prefer scripts/login.py (real Chrome + CDP) instead.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import get_settings
from src.monitor import setup_logging


DOMAINS = ("usvisascheduling.com",)


def main() -> None:
    try:
        import browser_cookie3
    except ImportError:
        raise SystemExit(
            "Install helper first:\n  pip install browser-cookie3\n"
            "Then close Chrome completely and re-run this script."
        )

    settings = get_settings()
    settings.ensure_dirs()
    setup_logging(settings.log_level)

    print("Reading cookies from your default Chrome profile…")
    print("Chrome must be FULLY closed.")
    print()

    try:
        jar = browser_cookie3.chrome(domain_name="usvisascheduling.com")
    except Exception as exc:
        raise SystemExit(
            f"Could not read Chrome cookies: {exc}\n"
            "Close every Chrome process (Task Manager) and retry.\n"
            "Or use: python scripts/login.py  (recommended)"
        ) from exc

    cookies = []
    for c in jar:
        if not any(d in (c.domain or "") for d in DOMAINS):
            continue
        cookies.append(
            {
                "name": c.name,
                "value": c.value,
                "domain": c.domain,
                "path": c.path or "/",
                "expires": int(c.expires) if c.expires else -1,
                "httpOnly": bool(getattr(c, "_rest", {}).get("HttpOnly", False)),
                "secure": bool(c.secure),
                "sameSite": "Lax",
            }
        )

    out = Path("data/imported_cookies.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
    print(f"Saved {len(cookies)} cookie(s) → {out.resolve()}")

    if not cookies:
        raise SystemExit(
            "No usvisascheduling.com cookies found.\n"
            "Log into the site in normal Chrome first, close Chrome, then retry.\n"
            "Best path: python scripts/login.py"
        )

    # Inject into the dedicated CDP/profile via a short Playwright connect or launch
    from src.browser import open_browser

    print("Injecting into visa browser profile / open Chrome…")
    with open_browser(settings, mode="cdp") as session:
        assert session.context is not None and session.page is not None
        # Playwright add_cookies wants URLs without leading dot domains normalized
        payload = []
        for c in cookies:
            item = {
                "name": c["name"],
                "value": c["value"],
                "domain": c["domain"],
                "path": c["path"],
                "secure": c["secure"],
                "httpOnly": c.get("httpOnly", False),
                "sameSite": "Lax",
            }
            if c.get("expires", -1) and c["expires"] > 0:
                item["expires"] = c["expires"]
            payload.append(item)
        session.context.add_cookies(payload)
        session.page.goto(settings.base_url, wait_until="domcontentloaded")
        session.screenshot("after_cookie_import.png")
        print(f"Opened: {session.page.url}")
        print(f"Title:  {session.page.title()}")
        print()
        print("If you see your account — good. Leave Chrome open and run check_slots.")
        print("If Cloudflare still blocks — use scripts/login.py instead.")


if __name__ == "__main__":
    main()
