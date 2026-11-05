"""Hisobot davrini aniqlash: Bugun, Kecha, Shu hafta, Shu oy, O'tgan oy yoki istalgan oraliq."""

from datetime import date, timedelta

from django.utils.dateparse import parse_date

PRESETS = [
    ("today", "Bugun"),
    ("yesterday", "Kecha"),
    ("week", "Shu hafta"),
    ("month", "Shu oy"),
    ("last_month", "O'tgan oy"),
]
DEFAULT_PERIOD = "month"
MAX_DAYS = 366


def _parse(value):
    try:
        return parse_date(value or "")
    except ValueError:
        return None


def resolve_period(params, today: date) -> tuple[str, date, date, str | None]:
    """GET parametrlaridan (period, from, to) -> (davr, boshlanish, tugash, xato matni)."""
    period = params.get("period", DEFAULT_PERIOD)

    if period == "custom":
        start, end = _parse(params.get("from")), _parse(params.get("to"))
        if not start or not end:
            return _preset(DEFAULT_PERIOD, today) + ("Sanalarni to'g'ri kiriting.",)
        if start > end:
            start, end = end, start
        if (end - start).days + 1 > MAX_DAYS:
            return _preset(DEFAULT_PERIOD, today) + (f"Oraliq {MAX_DAYS} kundan oshmasin.",)
        return ("custom", start, end, None)

    if period not in dict(PRESETS):
        period = DEFAULT_PERIOD
    return _preset(period, today) + (None,)


def _preset(period: str, today: date) -> tuple[str, date, date]:
    if period == "today":
        return (period, today, today)
    if period == "yesterday":
        day = today - timedelta(days=1)
        return (period, day, day)
    if period == "week":
        return (period, today - timedelta(days=today.weekday()), today)
    if period == "last_month":
        last_day = today.replace(day=1) - timedelta(days=1)
        return (period, last_day.replace(day=1), last_day)
    return ("month", today.replace(day=1), today)
