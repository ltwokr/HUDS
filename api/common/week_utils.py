from __future__ import annotations

import datetime as dt
from dateutil import tz
from typing import Tuple

NY_TZ = tz.gettz("America/New_York")
UTC = tz.UTC

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

def now_ny() -> dt.datetime:
    return dt.datetime.now(tz=NY_TZ)

def today_ny_date() -> dt.date:
    return now_ny().date()

def start_of_week(d: dt.date | None = None) -> dt.date:
    """Return Monday of the week for the given date in America/New_York."""
    if d is None:
        d = today_ny_date()
    # Python Monday = 0
    return d - dt.timedelta(days=d.weekday())

def end_of_week(d: dt.date | None = None) -> dt.date:
    """Return Sunday of the week for the given date in America/New_York."""
    start = start_of_week(d)
    return start + dt.timedelta(days=6)

def week_bounds_iso(d: dt.date | None = None) -> Tuple[str, str]:
    s = start_of_week(d)
    e = end_of_week(d)
    return s.isoformat(), e.isoformat()

def format_dtdate_param(d: dt.date | None = None) -> str:
    """Return MM/DD/YYYY string for HUDS dtdate param."""
    if d is None:
        d = today_ny_date()
    return d.strftime("%m/%d/%Y")

def iso_today() -> str:
    return today_ny_date().isoformat()

def utc_now_iso() -> str:
    return dt.datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def week_date_list(d: dt.date | None = None) -> list[dt.date]:
    start = start_of_week(d)
    return [start + dt.timedelta(days=i) for i in range(7)]
