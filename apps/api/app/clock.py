"""A single injectable clock so reminder/event logic is deterministic in
tests. Application code calls `now()` / `today()`; tests monkeypatch
`clock.now_provider` instead of reaching for `freezegun` or real sleeps.

Always returns wall-clock time in `app.config.settings.timezone` (or this
machine's own local timezone when unset) — medication schedule times
("08:30") are local times, not UTC, and comparing them against a UTC clock
fires reminders hours off (caught during manual end-to-end testing: an
09:00 schedule fired at 06:22 local time).
"""
from datetime import datetime, timezone, tzinfo
from typing import Callable
from zoneinfo import ZoneInfo

from app.config import settings

_tz: tzinfo = ZoneInfo(settings.timezone) if settings.timezone else datetime.now().astimezone().tzinfo

now_provider: Callable[[], datetime] = lambda: datetime.now(_tz)


def now() -> datetime:
    return now_provider()


def today_str() -> str:
    return now().date().isoformat()


def now_iso() -> str:
    """Every timestamp written to the database must go through this, not
    `now().isoformat()` directly — SQLite compares timestamp columns as
    plain strings, and ISO-8601 strings with different UTC offsets (local
    "+05:30" from one writer, "+00:00" from another) don't sort correctly
    against each other even though the datetimes themselves compare fine
    in Python. Normalizing everything to UTC before storage keeps
    "ORDER BY uploaded_at" and "< ?" comparisons correct (caught during
    manual testing: a seeded older report was picked as "more recent" than
    a same-day upload because of exactly this mismatch).
    """
    return now().astimezone(timezone.utc).isoformat()


def to_iso(dt: datetime) -> str:
    """Same UTC normalization as `now_iso()`, for a datetime computed from
    `now()` (e.g. a snooze or a custom reminder's due time) rather than
    `now()` itself. Naive datetimes are assumed to already be in this
    process's local timezone, matching `datetime.astimezone`'s own default.
    """
    return dt.astimezone(timezone.utc).isoformat()


def format_friendly_time(iso_str: str | None) -> str:
    """"2026-10-02T08:42:13+05:30" -> "8:42 AM" if today, else
    "Sep 24, 5:00 PM" — chat should never show Dad a raw ISO timestamp, and
    never imply "today" for something that wasn't (caught during manual
    testing: "I sent this last week" answered with a bare time of day).
    """
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str).astimezone(_tz)
    except ValueError:
        return iso_str
    if dt.date() == now().date():
        return dt.strftime("%-I:%M %p")
    return dt.strftime("%b %-d, %-I:%M %p")


def format_friendly_status(status: str) -> str:
    return status.replace("_", " ").lower()
