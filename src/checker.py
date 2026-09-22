from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from zoneinfo import ZoneInfo

from playwright.sync_api import Page

from .browser import BrowserSession
from .config import Settings
from . import human
from .notifier import Notifier, format_slots_summary
from .session import PageKind, SessionProbe
from .slots import SlotChecker
from .state import Slot, SlotStateStore


log = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


@dataclass
class CheckOutcome:
    status: str  # ok | session_expired | cloudflare | blocked | error
    slots: List[Slot]
    new_slots: List[Slot]
    detail: str = ""


def _ts() -> str:
    return datetime.now(IST).strftime("%Y%m%d_%H%M%S")


def perform_check(
    page: Page,
    settings: Settings,
    store: SlotStateStore,
    *,
    screenshot_fn=None,
) -> CheckOutcome:
    """
    One availability check using an already-open browser page.
    Does NOT attempt automated login or Cloudflare bypass.
    """
    probe = SessionProbe(page)
    target = settings.schedule_url.strip() or settings.base_url
    kind = probe.open_url(target)

    if kind == PageKind.BLOCKED:
        if screenshot_fn:
            screenshot_fn(f"blocked_{_ts()}.png")
        return CheckOutcome("blocked", [], [], "Cloudflare blocked this IP/session")

    if kind == PageKind.CLOUDFLARE:
        if screenshot_fn:
            screenshot_fn(f"cloudflare_{_ts()}.png")
        return CheckOutcome(
            "cloudflare",
            [],
            [],
            "Cloudflare challenge — run scripts/login.py and complete it manually",
        )

    if kind in (PageKind.LOGIN, PageKind.SECURITY):
        if screenshot_fn:
            screenshot_fn(f"session_expired_{_ts()}.png")
        return CheckOutcome(
            "session_expired",
            [],
            [],
            "Session expired — run scripts/login.py to refresh the profile",
        )

    if kind == PageKind.DASHBOARD or kind == PageKind.UNKNOWN:
        probe.find_schedule_entry()
        kind = probe.detect()

    if probe.needs_manual_login():
        if screenshot_fn:
            screenshot_fn(f"need_login_{_ts()}.png")
        return CheckOutcome(
            "session_expired",
            [],
            [],
            f"Not authenticated (page={kind.value}). Run scripts/login.py",
        )

    human.maybe_idle()
    checker = SlotChecker(page, settings)
    # SlotChecker.go_to_schedule_area is called inside collect — ok if already there
    slots = checker.collect()
    log.info("Observed %d slot(s):\n%s", len(slots), format_slots_summary(slots))

    new_slots = store.diff_new(slots)
    store.save(slots)

    if screenshot_fn:
        screenshot_fn(f"last_check_{_ts()}.png")

    return CheckOutcome("ok", slots, new_slots)


def notify_outcome(notifier: Notifier, settings: Settings, outcome: CheckOutcome) -> None:
    if outcome.status == "ok":
        if settings.notify_every_check or outcome.new_slots:
            notifier.notify_check_result(
                slots=outcome.slots,
                new_slots=outcome.new_slots,
                consulates=settings.consulate_list,
            )
        return

    labels = {
        "cloudflare": "Cloudflare challenge",
        "blocked": "IP / Cloudflare block",
        "session_expired": "Session expired",
        "error": "Check error",
    }
    notifier.notify_challenge(
        labels.get(outcome.status, outcome.status),
        outcome.detail
        + "\n\nFix: python scripts/login.py\n"
        "Complete Cloudflare + login in the opened window, then restart the monitor.",
    )
