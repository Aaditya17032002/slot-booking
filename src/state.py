from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set


log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Slot:
    consulate: str
    date: str
    time: str = ""

    def key(self) -> str:
        return f"{self.consulate}|{self.date}|{self.time}"

    def pretty(self) -> str:
        if self.time:
            return f"{self.consulate} — {self.date} @ {self.time}"
        return f"{self.consulate} — {self.date}"


class SlotStateStore:
    """Persists last-seen slots so we only alert on NEW availability."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._by_consulate: Dict[str, List[Slot]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for consulate, items in raw.get("slots", {}).items():
                self._by_consulate[consulate] = [
                    Slot(
                        consulate=consulate,
                        date=item["date"],
                        time=item.get("time", ""),
                    )
                    for item in items
                ]
        except Exception as exc:
            log.warning("Could not load state file: %s", exc)

    def save(self, slots: List[Slot]) -> None:
        grouped: Dict[str, List[Slot]] = {}
        for slot in slots:
            grouped.setdefault(slot.consulate, []).append(slot)
        self._by_consulate = grouped
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "slots": {
                name: [
                    {"date": s.date, "time": s.time}
                    for s in items
                ]
                for name, items in grouped.items()
            },
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def known_keys(self) -> Set[str]:
        keys: Set[str] = set()
        for items in self._by_consulate.values():
            for slot in items:
                keys.add(slot.key())
        return keys

    def diff_new(self, current: List[Slot]) -> List[Slot]:
        known = self.known_keys()
        return [s for s in current if s.key() not in known]

    def snapshot(self) -> dict:
        return {
            name: [asdict(s) for s in items]
            for name, items in self._by_consulate.items()
        }
