"""The dependency record: the commands it selects for a change, the record
a traced run writes, its entries moved to the lines of `HEAD`, and its
adoption."""

import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from controlled_markdown import mctx
from engine import checkout
from engine.memo import write_whole
from gating.commands import COMMANDS, GateCommand, keys_of
from gating.deps import PY_SUFFIXES, Deps, affects, moved, touched_from
from gating.records import deps_file

RECORD_OUT = "record.json"
"""The file under `<out-dir>/gate/` that holds the dependencies an
`--affected` run traced, as a dependency record."""


def head_clean() -> bool:
    """Whether the checkout changes no tracked file against `HEAD`, so that
    a traced run records the lines of the `HEAD` commit."""
    return all(c.change is checkout.Change.UNTRACKED
               for c in checkout.changed_paths(checkout.ROOT, "HEAD"))


def head() -> str:
    return checkout.git_out(checkout.ROOT, "rev-parse", "HEAD").strip()


@dataclass(frozen=True)
class Record:
    """The dependency record: the commit whose lines it records, and each
    command's dependencies by its key."""
    commit: str
    deps: dict[str, Deps]

    @staticmethod
    def read(path: Path) -> "Record":
        data = json.loads(path.read_text())
        return Record(data["commit"],
                      {k: Deps.from_json(v) for k, v in data["commands"].items()})

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        body = {"commit": self.commit,
                "commands": {k: d.to_json() for k, d in sorted(self.deps.items())}}
        write_whole(path, (json.dumps(body) + "\n").encode())

    @staticmethod
    def traced(deps_dir: Path, kept: dict[str, Deps]) -> "Record":
        """The record at `HEAD` of the dependencies traced under
        `deps_dir`, each over the entry of its key in `kept`, with an
        entry for each command of the gate and for no other key."""
        deps = {**kept, **{p.stem: Deps.from_json(json.loads(p.read_text()))
                           for p in sorted(deps_dir.glob("*.json"))}}
        return Record(head(), {k: deps[k] for k in keys_of(COMMANDS.values()) if k in deps})

    def moved(self) -> dict[str, Deps]:
        """Each entry, with each line number of a Python file the change
        from the record's commit to the checkout modifies moved to the
        number that line has in the checkout. It is exact for the entries
        of the commands that `traced_keys` leaves untraced."""
        hunks = {t.path: t.hunks for t in touched_from(self.commit, self.commit)
                 if t.status is checkout.Change.MODIFIED and Path(t.path).suffix in PY_SUFFIXES}
        return {k: Deps({p: moved(ns, hunks[p]) if p in hunks else ns
                         for p, ns in d.lines.items()}, d.reads, d.listed)
                for k, d in self.deps.items()}


def read_record() -> Record | None:
    path = deps_file()
    return Record.read(path) if path.exists() else None


def traced_keys(keys: set[str]) -> set[str]:
    """`keys`, and on each stem each key of `COMMANDS` after the first of
    them, since what a command runs depends on what the commands before it
    on its stem cached."""
    stems = sorted({s for c in COMMANDS.values() for s in c.stems})
    out = set(keys)
    for s in stems:
        on = [c.key(s) for c in COMMANDS.values() if s in c.stems]
        first = next((i for i, k in enumerate(on) if k in keys), len(on))
        out.update(on[first:])
    return out


def affected(cmds: Sequence[GateCommand], base: str) -> tuple[set[str], str | None, int]:
    """The keys of `cmds` on their stems that the change from the commit
    `base` can affect, each key with no dependency record among them; the
    commit of the record, or None where none stands; and the count of the
    keys of `cmds`."""
    keys = keys_of(cmds)
    record = read_record()
    if record is None:
        return keys, None, len(keys)
    touched = touched_from(base, record.commit)
    recorded = {t.path: checkout.git_out(checkout.ROOT, "show", f"{record.commit}:{t.path}")
                for t in touched if Path(t.path).suffix in PY_SUFFIXES
                and not (t.status.added or t.unrecorded)}
    run = {k for c in cmds for s in c.stems for k in [c.key(s)]
           if k not in record.deps or affects(c, s, record.deps[k], touched, recorded)}
    return run, record.commit, len(keys)


def adopt_record(out: Path) -> int:
    """Write the `RECORD_OUT` under `out` as the dependency record, where
    its commit is `HEAD`."""
    path = out.resolve() / "gate" / RECORD_OUT
    if not path.exists():
        print(mctx("record: no {path} stands, so the dependency record at {deps} stays as "
                   "it is").format(path=path, deps=deps_file()))
        return 0
    record = Record.read(path)
    at = head()
    if record.commit != at:
        print(mctx("record: {path} records {commit}, and HEAD is {head}").format(
            path=path, commit=record.commit[:12], head=at[:12]), file=sys.stderr)
        return 1
    record.write(deps_file())
    print(mctx("record: the dependency record of {commit} is written to {deps}").format(
        commit=record.commit[:12], deps=deps_file()))
    return 0
