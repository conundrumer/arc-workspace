"""The gate's records of the machine, under `.cache/gate/` of the main
worktree, or the directory `RECORDS_ENV` names: the accepted counts of
instructions and the dependency record's file."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from engine import checkout
from engine.memo import write_whole
from gating.commands import ACCEPTED

COUNT_FILE = "accepted-instructions.json"
"""The accepted counts of instructions, a JSON object from each `Tracing`
value to an object from `<name>-<stem>` to an object with the keys
`instructions`, the count, and `after`, the sequence it ran after: a list
of runs, each a list of the command's key and the list of its arguments
(`count_file`, `AcceptedCount`)."""
DEPS_FILE = "deps.json"
"""The dependency record, under `records_dir` (`deps_file`)."""


RECORDS_ENV = "ARC_GATE_RECORDS_DIR"
"""The environment variable that names the directory of the gate's records
in place of `gate/` under `.cache/`."""


def records_dir() -> Path:
    """`gate/` under the main worktree's `.cache/`, where the machine's
    accepted counts and the dependency record stand, unless
    `RECORDS_ENV` names another directory."""
    return checkout.from_env(RECORDS_ENV, lambda: checkout.caches() / "gate")


def count_file(accepted: Path) -> Path:
    """The accepted counts of the accepted directory `accepted`: for
    `ACCEPTED`, the machine's, `COUNT_FILE` under `records_dir`; for another
    directory, its own `COUNT_FILE`."""
    if accepted.resolve() != ACCEPTED.resolve():
        return accepted / COUNT_FILE
    return records_dir() / COUNT_FILE


class Tracing(StrEnum):
    """Whether the run of a count traced its commands, as `scripts/gate.py
    --help` gives; a count compares only with one of the same tracing."""

    TRACED = "traced"
    UNTRACED = "untraced"


type RunSequence = tuple[tuple[str, tuple[str, ...]], ...]
"""The sequence a count ran after, as `scripts/gate.py --help` gives it."""


@dataclass(frozen=True)
class AcceptedCount:
    instructions: int
    after: RunSequence


type Counts = dict[Tracing, dict[str, AcceptedCount]]
"""Counts of instructions, by the tracing of their run and their command's
key."""


def no_counts() -> Counts:
    return {t: {} for t in Tracing}


def read_counts(path: Path) -> Counts:
    """The counts `path` keeps, none where no file stands there."""
    if not path.exists():
        return no_counts()
    data = json.loads(path.read_text())
    if not (isinstance(data, dict) and set(data) == set(Tracing)
            and all(isinstance(v, dict) for v in data.values())):
        raise ValueError(f"{path} holds no object of counts by tracing")
    return {t: {key: _accepted_count(path, key, v) for key, v in data[t].items()}
            for t in Tracing}


def _accepted_count(path: Path, key: str, v: object) -> AcceptedCount:
    if not (isinstance(v, dict) and set(v) == {"instructions", "after"}
            and isinstance(v["instructions"], int) and isinstance(v["after"], list)):
        raise ValueError(f"{path} holds no count for {key}")
    after: list[tuple[str, tuple[str, ...]]] = []
    for run in v["after"]:
        if not (isinstance(run, list) and len(run) == 2 and isinstance(run[0], str)
                and isinstance(run[1], list) and all(isinstance(a, str) for a in run[1])):
            raise ValueError(f"{path} holds no sequence for {key}")
        after.append((run[0], tuple(run[1])))
    return AcceptedCount(v["instructions"], tuple(after))


def keep_counts(path: Path, counts: Mapping[Tracing, Mapping[str, AcceptedCount]]) -> None:
    data = {t.value: {key: {"instructions": a.instructions,
                            "after": [[k, list(args)] for k, args in a.after]}
                      for key, a in sorted(counts[t].items())}
            for t in Tracing}
    path.parent.mkdir(parents=True, exist_ok=True)
    write_whole(path, (json.dumps(data, indent=1) + "\n").encode())


def standing(counts: Mapping[str, AcceptedCount], key: str, after: RunSequence) -> int | None:
    """The count of `key` in `counts` that ran after `after`, or None where
    none stands."""
    accepted = counts.get(key)
    return accepted.instructions if accepted is not None and accepted.after == after else None


def deps_file() -> Path:
    return records_dir() / DEPS_FILE
