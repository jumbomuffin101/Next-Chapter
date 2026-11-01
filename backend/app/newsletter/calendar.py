"""One shared calendar for manual dispatch and the standalone monthly runner."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

TIMEZONE = "America/New_York"


def local_now(now: datetime | None = None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(TIMEZONE))


def current_month(now: datetime | None = None) -> str:
    return local_now(now).strftime("%Y-%m")


def month_start(value: str) -> date:
    try:
        parsed = date.fromisoformat(value + "-01")
        if parsed.strftime("%Y-%m") != value:
            raise ValueError
        return parsed
    except (ValueError, TypeError):
        raise ValueError("Month must use YYYY-MM") from None


def scheduled_at(month: str) -> datetime:
    day = month_start(month)
    return datetime(day.year, day.month, 1, 9, tzinfo=ZoneInfo(TIMEZONE))
