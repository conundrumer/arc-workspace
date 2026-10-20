"""The session's records of the times from which an operator's step has
been due on each ticket (`operations.state.State.due_since`, in the file
`DUE_SINCE`) and from which each ticket has waited on no party
(`operations.state.State.unwaited_since`, in the file `UNWAITED_SINCE`),
each a JSON object in the session's scratchpad, read by `record_read` and
written by `write_record`; and the replacement of such a file at once
(`replaced`)."""

import json
import math
import os
from collections.abc import Mapping
from pathlib import Path

from ticket_numbers import staged

from operations.state import DueEntry

DUE_SINCE = "due-since.json"
"""The name of the file, in the session's scratchpad, that holds
`State.due_since`."""

UNWAITED_SINCE = "unwaited-since.json"
"""The name of the file, in the session's scratchpad, that holds
`State.unwaited_since`."""


def record_read(here: Path, name: str) -> dict[str, DueEntry]:
    """The record the file `name` under `here` gives, or empty where that
    file is missing or holds no JSON object whose values are each a pair of
    finite numbers, the `since` and the `last` of a `DueEntry`."""
    try:
        record = json.loads((here / name).read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(record, dict) or not all(
            isinstance(v, list) and len(v) == 2
            and all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
                    for x in v)
            for v in record.values()):
        return {}
    return {n: DueEntry(float(v[0]), float(v[1])) for n, v in record.items()}


def write_record(here: Path, name: str, times: Mapping[str, DueEntry]) -> None:
    """Replaces the file `name` under `here` with `times`, each entry as the
    pair its `DueEntry` gives."""
    replaced(here, name, {n: [e.since, e.last] for n, e in sorted(times.items())})


def replaced(here: Path, name: str, record: object) -> None:
    """Replaces the file `name` under `here` with the JSON of `record`, at
    once."""
    with staged(here, json.dumps(record)) as tmp:
        os.replace(tmp, here / name)
