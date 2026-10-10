"""The form of the time a ticket's log line opens with, which the operator's
messages give as well."""

import time
from datetime import UTC, datetime

_TO_MINUTE = "%Y-%m-%dT%H:%M"

TIME_FORM = _TO_MINUTE + ":%SZ"
"""The form of a log line's time, in UTC."""

MINUTE_FORM = _TO_MINUTE + "Z"
"""`TIME_FORM` cut to the minute."""


def utc_stamp(t: float) -> str:
    """The epoch time `t` in `TIME_FORM`."""
    return time.strftime(TIME_FORM, time.gmtime(t))


def stamp_time(text: str) -> float:
    """The epoch time of `text`, a time in `TIME_FORM`; `ValueError` where
    `text` is none."""
    return datetime.strptime(text, TIME_FORM).replace(tzinfo=UTC).timestamp()
