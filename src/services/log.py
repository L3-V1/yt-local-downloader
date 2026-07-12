from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

LogLevel = Literal["info", "warning", "error"]
LogSource = Literal["downloads", "system", "library", "search"]


@dataclass(slots=True)
class LogEntry:
    id: str
    level: LogLevel
    source: LogSource
    message: str
    created_at: datetime
    details: str | None = None
    reference_id: str | None = None

    @property
    def created_at_display(self) -> str:
        return self.created_at.strftime("%d/%m/%Y %H:%M:%S")

    def to_dict(self) -> dict[str, str | None]:
        return {
            "id": self.id,
            "level": self.level,
            "source": self.source,
            "message": self.message,
            "details": self.details,
            "reference_id": self.reference_id,
            "created_at_display": self.created_at_display,
        }


@dataclass
class LogRegistry:
    _items: list[LogEntry] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add(
        self,
        *,
        level: LogLevel,
        source: LogSource,
        message: str,
        details: str | None = None,
        reference_id: str | None = None,
    ) -> LogEntry:
        entry = LogEntry(
            id=str(uuid.uuid4()),
            level=level,
            source=source,
            message=message,
            details=details,
            reference_id=reference_id,
            created_at=datetime.now(),
        )
        with self._lock:
            self._items.insert(0, entry)
        return entry

    def list_logs(self) -> list[LogEntry]:
        with self._lock:
            return list(self._items)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


log_registry = LogRegistry()


def add_application_log(
    *,
    level: LogLevel,
    source: LogSource,
    message: str,
    details: str | None = None,
    reference_id: str | None = None,
) -> LogEntry:
    """Store an application log entry in memory for UI inspection."""
    return log_registry.add(
        level=level,
        source=source,
        message=message,
        details=details,
        reference_id=reference_id,
    )
