"""Date parsing and session-entry date filtering."""

from datetime import datetime


def parse_date_to_ms(date_str: str, end_of_day: bool = False) -> int:
    """Parse 'YYYY-MM-DD' into epoch milliseconds, using the local timezone
    so the boundary matches what you'd expect from the calendar date on
    your machine (not UTC, which can shift the boundary by several hours)."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    if end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=999000)
    dt = dt.astimezone()  # attaches the system's local timezone
    return int(dt.timestamp() * 1000)


def filter_entries_by_date(entries: dict, from_ms: int | None, to_ms: int | None) -> dict:
    """Keep only session entries whose lastMessageDate falls within [from_ms, to_ms]."""
    if from_ms is None and to_ms is None:
        return dict(entries)
    filtered = {}
    for session_id, entry in entries.items():
        ts = entry.get("lastMessageDate", 0)
        if from_ms is not None and ts < from_ms:
            continue
        if to_ms is not None and ts > to_ms:
            continue
        filtered[session_id] = entry
    return filtered
