"""The gate's records of the machine, under `.cache/gate/` of the main
worktree: the accepted times, the commands an earlier timed run gave a
`LOADED` line, the commit of the last timed run that `--since-timed`
accepted, and the dependency record's file."""

import json
from collections.abc import Mapping, Set
from dataclasses import dataclass
from pathlib import Path

from engine import checkout
from engine.memo import write_whole
from gating.commands import ACCEPTED

TIMES_FILE = "accepted-times.json"
"""The accepted times, a JSON object from `<name>-<stem>` to an object
with the keys `seconds`, the time, and `after`, the sequence it was timed
after: a list of the runs before it on its stem, in their order, each a
list of the command's key and the list of the arguments it ran with
(`times_file`, `AcceptedTime`)."""
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


type RunSequence = tuple[tuple[str, tuple[str, ...]], ...]
"""The runs before a command on its stem, in their order, each its key and
the arguments it ran with."""


@dataclass(frozen=True)
class AcceptedTime:
    """An accepted time: its seconds and the sequence it was timed after."""
    seconds: float
    after: RunSequence


def read_times(path: Path) -> dict[str, AcceptedTime]:
    """The accepted times `path` keeps, none where no file stands there."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path} holds no object of accepted times")
    return {key: _accepted_time(path, key, v) for key, v in data.items()}


def _accepted_time(path: Path, key: str, v: object) -> AcceptedTime:
    if not (isinstance(v, dict) and set(v) == {"seconds", "after"}
            and isinstance(v["seconds"], int | float) and isinstance(v["after"], list)):
        raise ValueError(f"{path} holds no accepted time for {key}")
    after: list[tuple[str, tuple[str, ...]]] = []
    for run in v["after"]:
        if not (isinstance(run, list) and len(run) == 2 and isinstance(run[0], str)
                and isinstance(run[1], list) and all(isinstance(a, str) for a in run[1])):
            raise ValueError(f"{path} holds no sequence for {key}")
        after.append((run[0], tuple(run[1])))
    return AcceptedTime(float(v["seconds"]), tuple(after))


def keep_times(path: Path, times: Mapping[str, AcceptedTime]) -> None:
    data = {key: {"seconds": t.seconds, "after": [[k, list(args)] for k, args in t.after]}
            for key, t in sorted(times.items())}
    path.parent.mkdir(parents=True, exist_ok=True)
    write_whole(path, (json.dumps(data, indent=1) + "\n").encode())


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
