from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import List, Optional, Set

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from .config import Settings
from . import human
from .state import Slot


log = logging.getLogger(__name__)

# Common Indian post city labels on the portal
CITY_ALIASES = {
    "kolkata": ["kolkata", "calcutta"],
    "mumbai": ["mumbai", "bombay"],
    "new delhi": ["new delhi", "delhi"],
    "chennai": ["chennai", "madras"],
    "hyderabad": ["hyderabad"],
}


class SlotChecker:
    """Navigate to appointment availability and parse listed dates/times."""

    def __init__(self, page: Page, settings: Settings) -> None:
        self.page = page
        self.settings = settings

    def go_to_schedule_area(self) -> None:
        """Try common entry points from the post-login UI."""
        human.think(1.0, 2.0)
        human.scroll_casually(self.page)

        link_patterns = [
            r"reschedule",
            r"schedule\s*appointment",
            r"manage\s*appointment",
            r"appointment",
            r"continue",
        ]
        for pattern in link_patterns:
            loc = self.page.get_by_role("link", name=re.compile(pattern, re.I))
            if loc.count() and loc.first.is_visible():
                log.info("Opening navigation: %s", pattern)
                human.move_and_click(self.page, loc.first)
                human.think(2.0, 4.0)
                return

            loc = self.page.get_by_role("button", name=re.compile(pattern, re.I))
            if loc.count() and loc.first.is_visible():
                log.info("Clicking button: %s", pattern)
                human.move_and_click(self.page, loc.first)
                human.think(2.0, 4.0)
                return

        # Soft fallback: text click
        for label in ("Reschedule", "Schedule Appointment", "Appointments"):
            loc = self.page.locator(f"text={label}")
            if loc.count() and loc.first.is_visible():
                human.move_and_click(self.page, loc.first)
                human.think(2.0, 4.0)
                return

        log.warning("Could not auto-find schedule link; staying on current page")

    def collect(self) -> List[Slot]:
        """Check preferred consulates and return available slots found."""
        wanted = [c.strip() for c in self.settings.consulate_list]
        found: List[Slot] = []

        self.go_to_schedule_area()
        human.maybe_idle()

        # Prefer reading any already-visible calendar / list once
        page_slots = self._parse_page_slots(wanted)
        if page_slots:
            found.extend(page_slots)

        # Then try selecting each consulate if a dropdown exists
        for city in wanted:
            human.pause(0.8, 2.0)
            if self._select_consulate(city):
                human.think(1.5, 3.5)
                human.scroll_casually(self.page)
                city_slots = self._parse_page_slots([city])
                found.extend(city_slots)
                log.info("%s → %d slot(s) parsed", city, len(city_slots))
            else:
                # Still try to parse if city name is on page
                city_slots = self._parse_page_slots([city])
                found.extend(city_slots)
                if not city_slots:
                    log.info("%s → no selectable control / no slots visible", city)

        return self._dedupe(found)

    def _select_consulate(self, city: str) -> bool:
        aliases = CITY_ALIASES.get(city.lower(), [city.lower()])
        # Native <select>
        selects = self.page.locator("select")
        for i in range(selects.count()):
            select = selects.nth(i)
            options = select.locator("option").all_inner_texts()
            for opt in options:
                if any(a in opt.lower() for a in aliases):
                    log.info("Selecting consulate option: %s", opt.strip())
                    human.move_and_click(self.page, select)
                    select.select_option(label=opt)
                    human.pause(0.8, 1.8)
                    try:
                        self.page.wait_for_load_state("networkidle", timeout=20_000)
                    except PlaywrightTimeout:
                        pass
                    return True

        # Custom dropdown / radio / button
        for alias in aliases:
            for role in ("option", "radio", "button", "link"):
                loc = self.page.get_by_role(role, name=re.compile(alias, re.I))
                if loc.count() and loc.first.is_visible():
                    human.move_and_click(self.page, loc.first)
                    human.pause(0.8, 1.8)
                    return True
            loc = self.page.locator(f"text=/{re.escape(alias)}/i")
            if loc.count() and loc.first.is_visible():
                # Avoid clicking random body text; prefer smaller elements
                try:
                    human.move_and_click(self.page, loc.first)
                    human.pause(0.8, 1.8)
                    return True
                except Exception:
                    continue
        return False

    def _parse_page_slots(self, cities: List[str]) -> List[Slot]:
        text = human.safe_text(self.page.locator("body")) or ""
        lowered = text.lower()

        # Explicit "no appointments available" short-circuit for a city
        no_avail = any(
            phrase in lowered
            for phrase in (
                "no appointments available",
                "there are no available appointments",
                "no appointment slots",
                "currently no availability",
            )
        )

        slots: List[Slot] = []
        active_city = self._infer_city_from_context(cities, lowered)

        # Dates like 14 October 2026 / October 14, 2026 / 14-Oct-2026 / 2026-10-14
        date_patterns = [
            r"\b(\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+20\d{2})\b",
            r"\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+20\d{2})\b",
            r"\b(\d{1,2}[-/]\d{1,2}[-/]20\d{2})\b",
            r"\b(20\d{2}-\d{2}-\d{2})\b",
        ]
        time_pattern = re.compile(
            r"\b(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)\b"
        )

        # Prefer calendar day cells that look selectable
        day_cells = self.page.locator(
            "[class*='available'], [class*='day']:not([disabled]), "
            "td:not(.disabled) a, button[class*='day'], "
            "[data-available='true'], .a-calendar-date"
        )
        try:
            count = min(day_cells.count(), 60)
        except Exception:
            count = 0

        for i in range(count):
            cell = day_cells.nth(i)
            try:
                if not cell.is_visible():
                    continue
                label = (cell.get_attribute("aria-label") or cell.inner_text() or "").strip()
            except Exception:
                continue
            date = self._normalize_date(label) or self._first_date_in(label, date_patterns)
            if not date:
                continue
            city = active_city or (cities[0] if len(cities) == 1 else "Unknown")
            times = time_pattern.findall(label)
            if times:
                for t in times:
                    slots.append(Slot(consulate=city, date=date, time=t.strip()))
            else:
                slots.append(Slot(consulate=city, date=date, time=""))

        # Fallback: regex over full page text, scoped if possible
        if not slots and not no_avail:
            for pattern in date_patterns:
                for match in re.finditer(pattern, text, flags=re.I):
                    date = self._normalize_date(match.group(1)) or match.group(1)
                    # Grab nearby time within 40 chars
                    vicinity = text[match.end() : match.end() + 40]
                    tm = time_pattern.search(vicinity)
                    city = active_city or (cities[0] if len(cities) == 1 else self._city_near(text, match.start(), cities))
                    if not city:
                        continue
                    slots.append(
                        Slot(
                            consulate=city,
                            date=date,
                            time=tm.group(1).strip() if tm else "",
                        )
                    )

        if no_avail and not slots:
            log.info("Page indicates no appointments available")

        return self._dedupe(slots)

    def _infer_city_from_context(self, cities: List[str], lowered: str) -> Optional[str]:
        for city in cities:
            aliases = CITY_ALIASES.get(city.lower(), [city.lower()])
            if any(a in lowered for a in aliases):
                # If multiple preferred cities appear, prefer exact select value presence
                return city
        return cities[0] if len(cities) == 1 else None

    def _city_near(self, text: str, index: int, cities: List[str]) -> Optional[str]:
        window = text[max(0, index - 120) : index + 120].lower()
        for city in cities:
            aliases = CITY_ALIASES.get(city.lower(), [city.lower()])
            if any(a in window for a in aliases):
                return city
        return None

    def _first_date_in(self, text: str, patterns: List[str]) -> Optional[str]:
        for pattern in patterns:
            m = re.search(pattern, text, flags=re.I)
            if m:
                return self._normalize_date(m.group(1)) or m.group(1)
        return None

    def _normalize_date(self, raw: str) -> Optional[str]:
        raw = re.sub(r"\s+", " ", raw.strip())
        formats = [
            "%d %B %Y",
            "%d %b %Y",
            "%B %d, %Y",
            "%B %d %Y",
            "%b %d, %Y",
            "%b %d %Y",
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%m/%d/%Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        # aria-labels sometimes: "Wednesday, October 14, 2026"
        m = re.search(
            r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
            r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
            r"Dec(?:ember)?)\s+\d{1,2},?\s+20\d{2}",
            raw,
            flags=re.I,
        )
        if m:
            return self._normalize_date(m.group(0))
        return None

    @staticmethod
    def _dedupe(slots: List[Slot]) -> List[Slot]:
        seen: Set[str] = set()
        out: List[Slot] = []
        for s in slots:
            k = s.key()
            if k in seen:
                continue
            seen.add(k)
            out.append(s)
        return out
