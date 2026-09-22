from __future__ import annotations

import logging
import random
import time
from typing import Optional

from playwright.sync_api import Locator, Page


log = logging.getLogger(__name__)


def pause(min_s: float = 0.4, max_s: float = 1.4) -> None:
    """Short human-like pause."""
    time.sleep(random.uniform(min_s, max_s))


def think(min_s: float = 1.2, max_s: float = 3.5) -> None:
    """Longer pause as if reading the page."""
    time.sleep(random.uniform(min_s, max_s))


def type_like_human(locator: Locator, text: str, clear: bool = True) -> None:
    """Type with variable key delays; occasional short hesitations."""
    locator.click()
    pause(0.2, 0.5)
    if clear:
        locator.fill("")
        pause(0.15, 0.4)
    for ch in text:
        locator.type(ch, delay=random.randint(45, 140))
        if random.random() < 0.08:
            time.sleep(random.uniform(0.15, 0.45))


def move_and_click(page: Page, locator: Locator) -> None:
    """Move toward element with a small jitter, then click."""
    box = locator.bounding_box()
    if box:
        x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
        y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
        page.mouse.move(x, y, steps=random.randint(8, 22))
        pause(0.1, 0.35)
    locator.click()
    pause(0.3, 0.9)


def scroll_casually(page: Page) -> None:
    """Light scroll to mimic scanning the page."""
    delta = random.randint(120, 420) * random.choice([1, -1, 1])
    page.mouse.wheel(0, delta)
    pause(0.4, 1.0)


def random_poll_interval(min_s: int, max_s: int) -> float:
    """Skewed toward mid-range so intervals feel uneven."""
    return random.triangular(min_s, max_s, (min_s + max_s) / 2)


def next_backoff(attempt: int, base: int, maximum: int) -> float:
    """Exponential backoff with jitter after errors / challenges."""
    delay = min(maximum, base * (2 ** max(0, attempt - 1)))
    return delay * random.uniform(0.75, 1.25)


def maybe_idle() -> None:
    """Occasionally take a longer break like a real person."""
    if random.random() < 0.12:
        idle = random.uniform(8, 25)
        log.info("Taking a short idle break (%.0fs)…", idle)
        time.sleep(idle)


def safe_text(locator: Locator, timeout: int = 2000) -> Optional[str]:
    try:
        if locator.count() == 0:
            return None
        return (locator.first.inner_text(timeout=timeout) or "").strip()
    except Exception:
        return None
