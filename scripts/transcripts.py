"""Find the Claude Code transcripts of sessions and of agents under the
project directories, and read their entries, each read held for one state
of the process (`state_cache`)."""

import filecmp
import json
import os
import re
import time
from collections.abc import Callable, Hashable, Iterator
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any

from controlled_markdown import mctx
from handbook.paths import console_importable
from operations.roles import AGENT_ID as AGENT_ID_FORM

console_importable()

from solver_console import config  # noqa: E402

type Entry = dict[str, Any]

AGENT_ID_IN_TEXT = re.compile(rf"(?=({AGENT_ID_FORM}))".encode())
"""Each substring of the form of an agent id, overlapping ones too, as a
substring search finds it."""

_state = 0
"""The count of the states this process has opened (`new_state`)."""


def new_state() -> float:
    """Open a new state, and give the time it opened: from then on, each
    `state_cache` read gives what it reads as it stands now where its stamp
    changed, and as held where it did not."""
    global _state
    _state += 1
    return time.time()


def state_cache[**P, R](stamp: Callable[P, Hashable] | None) -> Callable[
        [Callable[P, R]], Callable[P, R]]:
    """Hold the result of a read for each of its arguments. Within one state
    the held result stands. At the first call of a new state the read runs
    again, unless `stamp` of its arguments is the stamp of the held result.
    The stamp of a read of files is their stat, and that of a read derived
    from other `state_cache` reads is their results, so it agrees with
    them within a state. A read with nothing to stamp, `stamp` None, runs
    again at each new state.

    Each process-life read cache that `operator_state.read_state` reaches,
    in any module, is a `state_cache`, so the readers of one state see one
    state, and a change between two states reaches the second."""
    def hold(read: Callable[P, R]) -> Callable[P, R]:
        held: dict[Hashable, tuple[int, Hashable, R]] = {}

        @wraps(read)
        def at_state(*args: P.args, **kwargs: P.kwargs) -> R:
            key = (args, tuple(sorted(kwargs.items())))
            hit = held.get(key)
            if hit is not None and hit[0] == _state:
                return hit[2]
            mark = stamp(*args, **kwargs) if stamp is not None else None
            if hit is not None and stamp is not None and hit[1] == mark:
                value = hit[2]
            else:
                value = read(*args, **kwargs)
            held[key] = (_state, mark, value)
            return value
        return at_state
    return hold


def stat_of(path: Path) -> tuple[int, int] | None:
    """The modification time and size of the file at `path`, or None where
    there is none."""
    try:
        st = path.stat()
    except FileNotFoundError:
        return None
    return st.st_mtime_ns, st.st_size


class Refused(Exception):
    """A call the command does not carry out, with the reason."""


def project_dirs() -> list[Path]:
    dirs: list[Path] = []
    for d in (config.USER_PROJECTS, config.PROJECTS):
        if d.is_dir() and d.resolve() not in [x.resolve() for x in dirs]:
            dirs.append(d)
    return dirs


def identical(p: Path, q: Path) -> bool:
    """Whether the transcripts at `p` and `q` are one file or copies."""
    return p == q or filecmp.cmp(p, q, shallow=False)


def distinct(found: list[Path]) -> list[Path]:
    """`found` less each transcript identical to one before it."""
    out: list[Path] = []
    for p in found:
        if not any(identical(p, q) for q in out):
            out.append(p)
    return out


def one_of(ident: str, found: list[Path]) -> Path | None:
    """The transcript `ident` names among `found`, less identical copies:
    the one transcript, or the last of the transcripts of one run."""
    found = distinct(found)
    if not found:
        return None
    run = chain(found[0])
    if sorted(run) == sorted(found):
        return run[-1]
    raise Refused(mctx("`{ident}` names more than one transcript, and they "
                       "differ; give the path of one of {paths}").format(
        ident=ident, paths=", ".join(str(p) for p in found)))


SUBAGENTS = "subagents"
"""The directory, under a session's, whose tree holds the session's
subagent transcripts, each named `agent-*.jsonl`."""


def subdirectories(d: Path, depth: int) -> list[Path]:
    """The directories `depth` levels under `d`, in path order."""
    if depth == 0:
        return [d]
    return [s for p in sorted((e.path for e in os.scandir(d) if e.is_dir()), key=path_order)
            for s in subdirectories(Path(p), depth - 1)]


def path_order(path: str) -> list[str]:
    """The sort key of `path` that orders it as `Path` orders paths."""
    return path.split(os.sep)


def main_transcript(session: Path) -> Path:
    return session.with_suffix(".jsonl")


def session_directory(main: Path) -> Path:
    return main.with_suffix("")


def subagent_transcripts(session: Path) -> list[Path]:
    # A walk of the tree lists it with no stat of each file, which a glob
    # of every session at each state cannot afford.
    return [Path(p) for p in sorted(
        (os.path.join(root, f) for root, _, files in os.walk(session / SUBAGENTS)
         for f in files if f.startswith("agent-") and f.endswith(".jsonl")),
        key=path_order)]


@state_cache(None)
def agent_transcripts() -> dict[str, list[Path]]:
    """The subagent transcripts under the project directories, by agent id."""
    out: dict[str, list[Path]] = {}
    for p in (p for d in project_dirs() for s in subdirectories(d, 2)
              for p in subagent_transcripts(s)):
        out.setdefault(agent_id(p), []).append(p)
    return out


def find(ident: str, *, recheck: bool = False) -> Path:
    """The transcript `ident` names, and for a run of more than one
    transcript, its last. `recheck` reads the agent index again on a miss,
    for an id taken from a read later than the index."""
    if ident.endswith(".jsonl"):
        path = Path(ident).expanduser()
        if not path.is_file():
            raise Refused(mctx("no file `{path}`").format(path=path))
        return path
    for found in (sorted(p for d in project_dirs() for p in d.glob(f"*/{ident}.jsonl")),
                  agent_transcripts().get(bare_id(ident), [])):
        path = one_of(ident, found)
        if path:
            return path
    if recheck:
        path = one_of(ident, agent_transcripts.__wrapped__().get(bare_id(ident), []))
        if path:
            return path
    raise Refused(mctx("no transcript of session or agent `{ident}` under "
                       "{dirs}").format(ident=ident, dirs=", ".join(
                           str(d) for d in project_dirs())))


def is_subagent(path: Path) -> bool:
    return "subagents" in path.parts


def transcripts(ident: str) -> list[Path]:
    """The last transcript of each run `ident` names."""
    path = find(ident)
    if is_subagent(path):
        return [path]
    return [path, *dict.fromkeys(chain(p)[-1] for p in subagent_transcripts(
        session_directory(path)))]


def bare_id(ident: str) -> str:
    """The agent id `ident` gives, with or without the `agent-` prefix of
    its transcript's name."""
    return ident.removeprefix("agent-")


def agent_id(path: Path) -> str:
    return bare_id(path.stem)


@state_cache(stat_of)
def first_parent(path: Path) -> str | None:
    """The `parentUuid` of the first entry of the transcript at `path`, with
    only the lines up to that entry read."""
    with path.open("rb") as fh:
        first = next((e for line in fh for e in parse(line)), None)
    return first.get("parentUuid") if first is not None else None


@state_cache(lambda path: snapshot(path))
def ends(path: Path) -> tuple[str | None, str | None]:
    """The `parentUuid` of the first entry of the transcript at `path`, and
    the `uuid` of its last entry that gives one."""
    last = next((u for e in entries_back(path) if (u := e.get("uuid"))), None)
    return first_parent(path), last


def chain(path: Path) -> list[Path]:
    """The transcripts of the run of the agent whose transcript is at
    `path`, earliest first: each after the first goes on from the one
    before it, its first entry answering that one's last."""
    if not is_subagent(path):
        return [path]
    others = [p for p in distinct(agent_transcripts().get(agent_id(path), []))
              if not identical(p, path)]
    run = [path]
    while True:
        before = [p for p in others if p not in run
                  and ends(run[0])[0] is not None
                  and ends(p)[1] == ends(run[0])[0]]
        after = [p for p in others if p not in run
                 and ends(run[-1])[1] is not None
                 and ends(p)[0] == ends(run[-1])[1]]
        if len(before) > 1 or len(after) > 1:
            raise Refused(mctx("more than one transcript of agent `{agent}` "
                               "goes on from {path}, or {path} goes on from "
                               "more than one: {paths}").format(
                agent=agent_id(path), path=run[0] if len(before) > 1 else run[-1],
                paths=", ".join(str(p) for p in before + after)))
        if not before and not after:
            return run
        run = before + run + after


class Snapshot:
    """The lines of a transcript as they stood when it was read, with the
    lines that hold each word asked about, and the entries of the lines
    parsed for such a word.

    At the first word of the form of an agent id asked about, one pass over
    the lines indexes every substring of that form, overlapping ones too,
    by the lines that hold it, so a search for many agent ids reads the text
    once."""

    def __init__(self, path: Path) -> None:
        self.text = path.read_bytes()
        self.lines = self.text.splitlines()
        self.found: dict[str, frozenset[int]] = {}
        self.agent_ids: dict[str, frozenset[int]] | None = None
        self.parsed: dict[int, list[Entry]] = {}

    def holding(self, word: str) -> frozenset[int]:
        if re.fullmatch(AGENT_ID_FORM, word):
            if self.agent_ids is None:
                self.agent_ids = self.index_agent_ids()
            return self.agent_ids.get(word, frozenset())
        if word not in self.found:
            w = word.encode()
            # One search of the whole text spares the scan of each line
            # for a word the transcript does not hold.
            self.found[word] = frozenset(
                i for i, line in enumerate(self.lines) if w in line
            ) if w in self.text else frozenset()
        return self.found[word]

    def index_agent_ids(self) -> dict[str, frozenset[int]]:
        index: dict[bytes, set[int]] = {}
        for i, line in enumerate(self.lines):
            for aid in AGENT_ID_IN_TEXT.findall(line):
                index.setdefault(aid, set()).add(i)
        return {aid.decode(): frozenset(found) for aid, found in index.items()}

    def entry(self, i: int) -> list[Entry]:
        if i not in self.parsed:
            self.parsed[i] = parse(self.lines[i])
        return self.parsed[i]


def epoch(iso: str) -> float:
    return datetime.fromisoformat(iso).timestamp()


def parse(line: str | bytes) -> list[Entry]:
    """The entry of `line`, or none where it is no JSON."""
    try:
        return [json.loads(line)]
    except json.JSONDecodeError:
        return []


@state_cache(stat_of)
def snapshot(path: Path) -> Snapshot:
    """The transcript at `path` as it stands at the state this process is
    in (`state_cache`)."""
    return Snapshot(path)


def read_entries(path: Path, naming: set[str] | None = None) -> list[Entry]:
    """The entries of the transcript at `path` as it stands at the state this
    process is in, or with `naming` only those whose line holds one of its
    words, which spares parsing the rest."""
    if naming is None:
        return list(entries_forward(path))
    snap = snapshot(path)
    lines = sorted(frozenset[int]().union(*(snap.holding(w) for w in naming)))
    return [e for i in lines for e in snap.entry(i)]


def entries_forward(path: Path) -> Iterator[Entry]:
    """The entries of the transcript at `path` as it stands at the state this
    process is in, in their order, each line parsed only when it is reached."""
    snap = snapshot(path)
    for i in range(len(snap.lines)):
        yield from snap.entry(i)


def entries_back(path: Path) -> Iterator[Entry]:
    """The entries of the transcript at `path` as it stands at the state this
    process is in, last first, each line parsed only when it is reached."""
    snap = snapshot(path)
    for i in range(len(snap.lines) - 1, -1, -1):
        yield from snap.entry(i)


def forked_from(path: Path) -> str | None:
    """The id of the session that the session whose transcript is at
    `path` was forked from, which the transcript's first line names, or
    None where that line names none."""
    with path.open() as fh:
        first = fh.readline()
    entry = next(iter(parse(first)), None)
    if not isinstance(entry, dict):
        raise Refused(mctx("the first line of {path} is no transcript entry").format(path=path))
    fork = entry.get("forkedFrom")
    return fork["sessionId"] if fork else None
