"""The store of the lines `operate.py send` records, on disk under the main
tree: the file of a session, and the write and the read of its lines."""

import json
import os
from collections.abc import Sequence
from pathlib import Path

STORE = Path(".cache") / "op-lines"
"""The directory, under the main tree, of the store of the lines
`operate.py send` records: one file per session, named by its id, of one
JSON object per line, with the line's `time` and `text`."""


def store_file(main_tree: Path, session: str) -> Path:
    return main_tree / STORE / f"{session}.jsonl"


def record_lines(main_tree: Path, session: str, texts: Sequence[str], time: float) -> None:
    """Append `texts` to the session's store, each with `time`, in one
    write, so that the lines of two calls at once do not mix."""
    path = store_file(main_tree, session)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = "".join(json.dumps({"time": time, "text": t}) + "\n" for t in texts).encode()
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def recorded_lines(main_tree: Path, session: str) -> list[tuple[float, str]]:
    """The lines of the session's store, each with the time of its record,
    in the order of their records, or none where the store has no file."""
    try:
        raw = store_file(main_tree, session).read_bytes()
    except FileNotFoundError:
        return []
    out: list[tuple[float, str]] = []
    rows = raw.splitlines(keepends=True)
    for i, row in enumerate(rows):
        if not row.strip():
            continue
        try:
            d = json.loads(row)
        except (json.JSONDecodeError, UnicodeDecodeError):
            if i == len(rows) - 1 and not row.endswith(b"\n"):
                continue
            raise
        out.append((float(d["time"]), str(d["text"])))
    return out
