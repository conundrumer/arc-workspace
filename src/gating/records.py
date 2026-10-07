"""The gate's records of the machine, under `.cache/gate/` of the main
worktree: the accepted times, the commands an earlier timed run gave a
`LOADED` line, the commit of the last timed run that `--since-timed`
accepted, and the dependency record's file."""

import json
from collections.abc import Set
from pathlib import Path

from engine import checkout
from engine.memo import write_whole
from gating.commands import ACCEPTED

TIMES_FILE = "times.json"
"""The accepted times, a JSON object from `<name>-<stem>` to seconds
(`times_file`)."""
LOADED_FILE = "loaded.json"
"""The keys of the commands kept for a timed run to judge, a JSON list
(`loaded_file`)."""
BASE_FILE = "timed.json"
"""The commit of the last timed run with `--accept --since-timed`, a JSON
object with the key `commit` (`base_file`)."""
DEPS_FILE = "deps.json"
"""The dependency record, under `records_dir` (`deps_file`)."""


def records_dir() -> Path:
    """`gate/` under the main worktree's `.cache/`, where the machine's
    accepted times and the dependency record stand."""
    return checkout.caches() / "gate"


def times_file(accepted: Path) -> Path:
    """The accepted times of the accepted directory `accepted`: for
    `ACCEPTED`, the machine's, `TIMES_FILE` under `records_dir`; for
    another directory, its own `TIMES_FILE`."""
    if accepted.resolve() != ACCEPTED.resolve():
        return accepted / TIMES_FILE
    return records_dir() / TIMES_FILE


def loaded_file(accepted: Path) -> Path:
    return times_file(accepted).with_name(LOADED_FILE)


def base_file(accepted: Path) -> Path:
    return times_file(accepted).with_name(BASE_FILE)


def read_base(path: Path) -> str | None:
    """The commit `path` keeps, or None where no file stands there."""
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    if not (isinstance(data, dict) and isinstance(data.get("commit"), str)):
        raise ValueError(f"{path} holds no commit")
    return data["commit"]


def keep_base(path: Path, commit: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_whole(path, (json.dumps({"commit": commit}) + "\n").encode())


def deps_file() -> Path:
    return records_dir() / DEPS_FILE


def read_loaded(path: Path) -> set[str]:
    if not path.exists():
        return set()
    data = json.loads(path.read_text())
    if not (isinstance(data, list) and all(isinstance(k, str) for k in data)):
        raise ValueError(f"{path} holds no list of command keys")
    return set(data)


def keep_loaded(path: Path, judged: Set[str], loaded: Set[str]) -> None:
    kept = (read_loaded(path) - judged) | loaded
    path.parent.mkdir(parents=True, exist_ok=True)
    write_whole(path, (json.dumps(sorted(kept), indent=1) + "\n").encode())
