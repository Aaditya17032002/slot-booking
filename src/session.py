from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Optional

from playwright.sync_api import Page

from . import human


log = logging.getLogger(__name__)


class PageKind(str, Enum):
    UNKNOWN = "unknown"
    BLOCKED = "blocked"
    CLOUDFLARE = "cloudflare"
    LOGIN = "login"
    SECURITY = "security"
    DASHBOARD = "dashboard"
    SCHEDULE = "schedule"


class SessionProbe:
    """Detect what page we're on — never tries to bypass Cloudflare."""

    def __init__(self, page: Page) -> None:
        self.page = page

    def detect(self) -> PageKind:
        content = ""
        try:
            content = (self.page.content() or "").lower()
        except Exception:
            pass
        title = (self.page.title() or "").lower()
        url = (self.page.url or "").lower()

        if "sorry, you have been blocked" in content or (
            "you are unable to access" in content and "cloudflare" in content
        ):
            return PageKind.BLOCKED

        if self._is_cloudflare(title, content):
            return PageKind.CLOUDFLARE

        if self._has_security_prompt(content):
            return PageKind.SECURITY

        if self._has_login_form():
            return PageKind.LOGIN

        if any(k in url for k in ("schedule", "appointment", "reschedule", "calendar")):
            return PageKind.SCHEDULE

        if any(
            k in content or k in title or k in url
            for k in (
                "dashboard",
                "my applications",
                "account home",
                "applicant",
                "sign out",
                "log out",
                "logout",
            )
        ):
            return PageKind.DASHBOARD

        return PageKind.UNKNOWN

    def is_authenticated(self) -> bool:
        return self.detect() in (PageKind.DASHBOARD, PageKind.SCHEDULE)

    def needs_manual_login(self) -> bool:
        return self.detect() in (
            PageKind.LOGIN,
            PageKind.SECURITY,
            PageKind.CLOUDFLARE,
            PageKind.BLOCKED,
        )

    def _is_cloudflare(self, title: str, content: str) -> bool:
        markers = (
            "just a moment",
            "performing security verification",
            "checking your browser",
            "verify you are human",
            "attention required",
        )
        if any(m in title for m in markers):
            return True
        if "verifying..." in content and "cloudflare" in content:
            return True
        if "performing security verification" in content:
            return True
        return False

    def _has_login_form(self) -> bool:
        for sel in (
            "input[type='password']",
            "input[name*='pass' i]",
            "input[id*='pass' i]",
            "#password",
        ):
            try:
                if self.page.locator(sel).count():
                    return True
            except Exception:
                continue
        return False

    def _has_security_prompt(self, content: str) -> bool:
        if "security question" in content or "answer the following" in content:
            return True
        return False

    def open_url(self, url: str) -> PageKind:
        log.info("Navigating to %s", url)
        self.page.goto(url, wait_until="domcontentloaded")
        human.think(1.5, 3.0)
        kind = self.detect()
        log.info("Page kind after navigate: %s (title=%r)", kind.value, self.page.title())
        return kind

    def find_schedule_entry(self) -> bool:
        """Click common post-login appointment links if present."""
        patterns = [
            r"reschedule",
            r"schedule\s*appointment",
            r"manage\s*appointment",
            r"appointment",
        ]
        for pattern in patterns:
            for role in ("link", "button"):
                loc = self.page.get_by_role(role, name=re.compile(pattern, re.I))
                if loc.count() and loc.first.is_visible():
                    log.info("Opening %s via %s", pattern, role)
                    human.move_and_click(self.page, loc.first)
                    human.think(2.0, 3.5)
                    return True
        return False
