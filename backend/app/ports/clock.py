from datetime import datetime, timezone
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime:
        """Return the current timezone-aware UTC timestamp."""
        ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)
