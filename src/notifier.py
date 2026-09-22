from __future__ import annotations

import logging
import smtplib
from datetime import datetime
from email.message import EmailMessage
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

import httpx

from .config import Settings
from .state import Slot


log = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _now_ist() -> str:
    return datetime.now(IST).strftime("%d %b %Y · %I:%M %p IST")


def _group(slots: List[Slot]) -> Dict[str, List[Slot]]:
    grouped: Dict[str, List[Slot]] = {}
    for slot in slots:
        grouped.setdefault(slot.consulate, []).append(slot)
    return grouped


class Notifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def notify_check_result(
        self,
        *,
        slots: List[Slot],
        new_slots: List[Slot],
        consulates: Optional[List[str]] = None,
    ) -> None:
        """Send a formatted update after every successful check."""
        cities = consulates or self.settings.consulate_list
        if new_slots:
            self.send_html(self._format_new_slots(new_slots, slots))
        elif slots:
            self.send_html(self._format_existing_slots(slots, cities))
        else:
            self.send_html(self._format_no_slots(cities))

    def notify_slots(self, slots: List[Slot], note: str = "") -> None:
        if not slots:
            return
        self.send_html(self._format_new_slots(slots, slots, note=note))

    def notify_challenge(self, kind: str, detail: str = "") -> None:
        html = (
            f"<b>⚠️ Monitor needs attention</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>Issue</b>\n"
            f"{_esc(kind)}\n\n"
        )
        if detail:
            html += f"<b>Details</b>\n{_esc(detail)}\n\n"
        html += (
            f"The bot backed off automatically.\n"
            f"Check the <code>screenshots/</code> folder if needed.\n\n"
            f"<i>{_esc(_now_ist())}</i>"
        )
        self.send_html(html)

    def notify_status(self, text: str) -> None:
        html = (
            f"<b>ℹ️ US Visa Monitor</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{_esc(text)}\n\n"
            f"<i>{_esc(_now_ist())}</i>"
        )
        self.send_html(html)

    def _format_new_slots(
        self,
        new_slots: List[Slot],
        all_slots: List[Slot],
        note: str = "",
    ) -> str:
        lines = [
            "<b>🚨 NEW SLOT AVAILABLE</b>",
            "━━━━━━━━━━━━━━━━━━━━",
            "",
            f"<b>Visa</b>  ·  {_esc(self.settings.visa_category)}",
            f"<b>Type</b>  ·  {_esc(self.settings.visa_type)}",
            "",
            "<b>New openings</b>",
        ]
        for city, items in _group(new_slots).items():
            lines.append(f"\n📍 <b>{_esc(city)}</b>")
            for slot in items:
                time_part = f"  ·  {_esc(slot.time)}" if slot.time else ""
                lines.append(f"    •  {_esc(slot.date)}{time_part}")

        if all_slots and len(all_slots) != len(new_slots):
            lines.extend(["", "<b>Also currently listed</b>"])
            for city, items in _group(all_slots).items():
                lines.append(f"\n📍 <b>{_esc(city)}</b>")
                for slot in items:
                    time_part = f"  ·  {_esc(slot.time)}" if slot.time else ""
                    lines.append(f"    •  {_esc(slot.date)}{time_part}")

        lines.extend(
            [
                "",
                "🔗 <a href=\"https://www.usvisascheduling.com/en-US/\">Open USVisaScheduling</a>",
                "",
                "<b>Book / reschedule manually</b> — this bot does not book for you.",
                "",
                f"<i>{_esc(note or _now_ist())}</i>",
            ]
        )
        return "\n".join(lines)

    def _format_existing_slots(self, slots: List[Slot], cities: List[str]) -> str:
        lines = [
            "<b>📋 Check complete</b>",
            "━━━━━━━━━━━━━━━━━━━━",
            "",
            f"<b>Visa</b>  ·  {_esc(self.settings.visa_category)}",
            f"<b>Watching</b>  ·  {_esc(', '.join(cities))}",
            "",
            "<b>Status</b>  ·  Slots visible (no new ones)",
            "",
            "<b>Currently listed</b>",
        ]
        for city, items in _group(slots).items():
            lines.append(f"\n📍 <b>{_esc(city)}</b>")
            for slot in items:
                time_part = f"  ·  {_esc(slot.time)}" if slot.time else ""
                lines.append(f"    •  {_esc(slot.date)}{time_part}")

        missing = [c for c in cities if c not in _group(slots)]
        if missing:
            lines.extend(["", "<b>No slots shown for</b>"])
            for city in missing:
                lines.append(f"  ○  {_esc(city)}")

        lines.extend(["", f"<i>{_esc(_now_ist())}</i>"])
        return "\n".join(lines)

    def _format_no_slots(self, cities: List[str]) -> str:
        city_lines = "\n".join(f"  ○  {_esc(c)}" for c in cities)
        return (
            f"<b>📭 Check complete</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>Visa</b>  ·  {_esc(self.settings.visa_category)}\n"
            f"<b>Type</b>  ·  {_esc(self.settings.visa_type)}\n\n"
            f"<b>Status</b>  ·  No appointments available\n\n"
            f"<b>Checked</b>\n"
            f"{city_lines}\n\n"
            f"I'll keep watching and alert you when something opens.\n\n"
            f"<i>{_esc(_now_ist())}</i>"
        )

    def send(self, text: str) -> None:
        self.send_html(_esc(text).replace("\n", "\n"))

    def send_html(self, html: str) -> None:
        sent = False
        if self.settings.telegram_bot_token and self.settings.telegram_chat_id:
            try:
                self._telegram(html)
                sent = True
            except Exception as exc:
                log.error("Telegram notify failed: %s", exc)
        if self.settings.smtp_host and self.settings.alert_email_to:
            try:
                # Strip tags roughly for email plaintext
                plain = (
                    html.replace("<b>", "")
                    .replace("</b>", "")
                    .replace("<i>", "")
                    .replace("</i>", "")
                    .replace("<code>", "")
                    .replace("</code>", "")
                    .replace("&amp;", "&")
                    .replace("&lt;", "<")
                    .replace("&gt;", ">")
                )
                import re

                plain = re.sub(r"<a href=\"([^\"]+)\">([^<]+)</a>", r"\2 (\1)", plain)
                plain = re.sub(r"<[^>]+>", "", plain)
                self._email(plain)
                sent = True
            except Exception as exc:
                log.error("Email notify failed: %s", exc)
        if not sent:
            log.warning("No notifier configured; message was:\n%s", html)

    def _telegram(self, html: str) -> None:
        url = (
            f"https://api.telegram.org/bot"
            f"{self.settings.telegram_bot_token}/sendMessage"
        )
        payload = {
            "chat_id": self.settings.telegram_chat_id,
            "text": html,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, json=payload)
            if resp.status_code >= 400:
                log.error("Telegram API error: %s", resp.text)
            resp.raise_for_status()

    def _email(self, text: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = "US Visa Slot Alert"
        msg["From"] = self.settings.smtp_user or "visa-monitor@localhost"
        msg["To"] = self.settings.alert_email_to
        msg.set_content(text)
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port) as smtp:
            smtp.starttls()
            if self.settings.smtp_user and self.settings.smtp_password:
                smtp.login(self.settings.smtp_user, self.settings.smtp_password)
            smtp.send_message(msg)


def format_slots_summary(slots: List[Slot]) -> str:
    if not slots:
        return "No slots currently listed for preferred consulates."
    return "\n".join(f"• {s.pretty()}" for s in slots)
