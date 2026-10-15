"""Find the Claude Code transcripts of sessions and of agents under the
project directories, and read their entries, each read held for one state
of the process (`state_cache`)."""

import bisect
import filecmp
import json
import os
import re
from collections.abc import Callable, Iterable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

# `transcripts.new_state` is the name the tests of these reads open a state by.
from state_reads import (DERIVED, Named, is_file, listed, new_state, stat_of,  # noqa: F401
                         state_cache)

from controlled_markdown import mctx
from handbook.paths import console_importable
from operations.roles import AGENT_ID as AGENT_ID_FORM

console_importable()

from solver_console import config  # noqa: E402

type Entry = dict[str, Any]

class Refused(Exception):
    """A call the command does not carry out, with the reason."""


@state_cache(None)
def project_dirs() -> list[Path]:
    dirs: list[Path] = []
    for d in (config.USER_PROJECTS, config.PROJECTS):
        if d.is_dir() and d.resolve() not in [x.resolve() for x in dirs]:
            dirs.append(d)
    return dirs


@state_cache(lambda p, q: (stat_of(p), stat_of(q)))
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


def subdirectories(d: Path, depth: int,
                   listing: Callable[[Path], tuple[Named, ...]] = listed) -> list[Path]:
    """The directories `depth` levels under `d`, in path order, with
    `listing` as each directory's entries."""
    if depth == 0:
        return [d]
    return [s for p in sorted((os.path.join(d, e.name) for e in listing(d) if e.is_dir),
                              key=path_order)
            for s in subdirectories(Path(p), depth - 1, listing)]


def walked(top: str, listing: Callable[[Path], tuple[Named, ...]]) -> Iterator[str]:
    """The path of each entry that is no directory in the tree of `top`, as
    `os.walk` gives the files of each directory, with `listing` as each
    directory's entries: a link to a directory is not descended."""
    for e in listing(Path(top)):
        path = os.path.join(top, e.name)
        if not e.is_dir:
            yield path
        elif not e.is_link:
            yield from walked(path, listing)


def path_order(path: str) -> list[str]:
    """The sort key of `path` that orders it as `Path` orders paths."""
    return path.split(os.sep)


def main_transcript(session: Path) -> Path:
    return session.with_suffix(".jsonl")


def session_directory(main: Path) -> Path:
    return main.with_suffix("")


def subagent_transcripts(session: Path,
                         listing: Callable[[Path], tuple[Named, ...]] = listed) -> list[Path]:
    """The subagent transcripts of `session`, in path order, with `listing`
    as each directory's entries."""
    found = [p for p in walked(str(session / SUBAGENTS), listing)
             if os.path.basename(p).startswith("agent-") and p.endswith(".jsonl")]
    return [Path(p) for p in sorted(found, key=path_order)]


@state_cache(DERIVED)
def session_subagents(session: Path) -> tuple[Path, ...]:
    """`subagent_transcripts` of `session`, of the listings this state
    holds."""
    return tuple(subagent_transcripts(session))


def agent_index(dirs: tuple[Path, ...],
                listing: Callable[[Path], tuple[Named, ...]]) -> dict[str, list[Path]]:
    """The subagent transcripts under the project directories `dirs`, by
    agent id, with `listing` as each directory's entries."""
    return by_agent(p for s in sessions_under(dirs, listing)
                    for p in subagent_transcripts(s, listing))


def sessions_under(dirs: tuple[Path, ...],
                   listing: Callable[[Path], tuple[Named, ...]]) -> list[Path]:
    """The session directories under the project directories `dirs`, with
    `listing` as each directory's entries."""
    return [s for d in dirs for s in subdirectories(d, 2, listing)]


def by_agent(paths: Iterable[Path]) -> dict[str, list[Path]]:
    """The subagent transcripts `paths`, by agent id, in their order."""
    out: dict[str, list[Path]] = {}
    for p in paths:
        out.setdefault(agent_id(p), []).append(p)
    return out


def agent_transcripts() -> dict[str, list[Path]]:
    """The subagent transcripts under the project directories, by agent id."""
    return agent_transcripts_in(tuple(project_dirs()))


@state_cache(DERIVED)
def agent_transcripts_in(dirs: tuple[Path, ...]) -> dict[str, list[Path]]:
    """`agent_index` of `dirs`, of the listings this state holds, each
    session's from `session_subagents`."""
    return by_agent(p for s in sessions_under(dirs, listed) for p in session_subagents(s))


def transcripts_of(agent: str) -> list[Path]:
    """The transcripts `agent_transcripts` gives the agent `agent`."""
    return agent_paths(tuple(project_dirs()), agent)


@state_cache(DERIVED)
def agent_paths(dirs: tuple[Path, ...], agent: str) -> list[Path]:
    """`transcripts_of` the agent `agent` under `dirs`, held so that a read
    derived from them sees a change only where they change."""
    return agent_transcripts_in(dirs).get(agent, [])


def mains_named(name: str) -> list[Path]:
    """The transcripts `main_transcripts` gives `name`."""
    return main_paths(tuple(project_dirs()), name)


@state_cache(DERIVED)
def main_paths(dirs: tuple[Path, ...], name: str) -> list[Path]:
    """`mains_named` `name` under `dirs`, held as `agent_paths` is."""
    return main_transcripts_in(dirs).get(name, [])


def main_transcripts() -> dict[str, list[Path]]:
    """The transcripts at `*/<name>.jsonl` under each project directory, by
    `<name>`, as a glob of that pattern finds them."""
    return main_transcripts_in(tuple(project_dirs()))


@state_cache(DERIVED)
def main_transcripts_in(dirs: tuple[Path, ...]) -> dict[str, list[Path]]:
    """`main_transcripts` under `dirs`, of the listings this state holds."""
    out: dict[str, list[Path]] = {}
    for d in dirs:
        for e in listed(d):
            if e.is_dir:
                for f in listed(d / e.name):
                    if f.name.endswith(".jsonl") and (f.is_file or f.is_dir):
                        name = f.name.removesuffix(".jsonl")
                        out.setdefault(name, []).append(d / e.name / f.name)
    return out


def find(ident: str, *, recheck: bool = False) -> Path:
    """The transcript `ident` names, and for a run of more than one
    transcript, its last. `recheck` reads the agent index again on a miss,
    for an id taken from a read later than the index."""
    if ident.endswith(".jsonl"):
        path = Path(ident).expanduser()
        if not is_file(path):
            raise Refused(mctx("no file `{path}`").format(path=path))
        return path
    for found in (sorted(mains_named(ident)), transcripts_of(bare_id(ident))):
        path = one_of(ident, found)
        if path:
            return path
    if recheck:
        fresh = agent_index(tuple(project_dirs()), listed.__wrapped__)
        path = one_of(ident, fresh.get(bare_id(ident), []))
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
    others = [p for p in distinct(transcripts_of(agent_id(path)))
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


HEX = bytes(ord("1") if chr(c) in "0123456789abcdef" else ord("0") for c in range(256))
"""The table that maps each hexadecimal digit to `1` and each other byte to
`0`."""
HEX_RUN = b"1" * (len("a") + 16)
"""The mask of the shortest run of digits that holds an agent id."""


def agent_ids_in(text: bytes, start: int) -> Iterator[tuple[bytes, int]]:
    """Each substring of `text` from `start` on of the form of an agent id,
    overlapping ones too, with its offset: each `a` of a run of hexadecimal
    digits with 16 digits after it in the run. The runs are found in a mask
    of the text, so the text is scanned once. `start` is the offset of a
    line, which no run crosses."""
    mask = text[start:].translate(HEX)
    k = mask.find(HEX_RUN)
    while k >= 0:
        end = mask.find(b"0", k)
        end = len(mask) if end < 0 else end
        j = text.find(b"a", start + k, start + end - 16)
        while j >= 0:
            yield text[j:j + 17], j
            j = text.find(b"a", j + 1, start + end - 16)
        k = mask.find(HEX_RUN, end)


class Snapshot:
    """The lines of a transcript as they stood when it was read, with the
    lines that hold each word asked about, and the entries of the lines
    parsed for such a word.

    `starts` gives the offset of each line, so a word is found by a search
    of the whole text, and at the first word of the form of an agent id
    asked about, one search indexes every substring of that form,
    overlapping ones too, by the lines that hold it.

    A snapshot read on from an earlier one (`extended`) keeps what that one
    found in its whole lines."""

    def __init__(self, text: bytes) -> None:
        self.text = text
        self.starts = line_starts(text, 0, [])
        self.found: dict[str, frozenset[int]] = {}
        self.agent_ids: dict[str, frozenset[int]] | None = None
        self.parsed: dict[int, list[Entry]] = {}

    @property
    def count(self) -> int:
        """The number of its lines."""
        return len(self.starts)

    def line(self, i: int) -> bytes:
        """The `i`-th line, without the line break that ends it, as
        `bytes.splitlines` gives it."""
        end = self.starts[i + 1] if i + 1 < len(self.starts) else len(self.text)
        line = self.text[self.starts[i]:end]
        if line.endswith(b"\r\n"):
            return line[:-2]
        return line[:-1] if line.endswith((b"\n", b"\r")) else line

    def settled(self) -> int:
        """The number of its whole lines, those a newline ends."""
        return self.count - (0 if self.text.endswith(b"\n") or not self.text else 1)

    def settled_end(self) -> int:
        """The offset after its whole lines."""
        whole = self.settled()
        return self.starts[whole] if whole < self.count else len(self.text)

    def line_of(self, offset: int) -> int:
        return bisect.bisect_right(self.starts, offset) - 1

    def holding(self, word: str) -> frozenset[int]:
        if re.fullmatch(AGENT_ID_FORM, word):
            if self.agent_ids is None:
                self.agent_ids = self.index_agent_ids(0)
            return self.agent_ids.get(word, frozenset())
        if word not in self.found:
            self.found[word] = self.lines_holding(word.encode(), 0)
        return self.found[word]

    def lines_holding(self, w: bytes, start: int) -> frozenset[int]:
        """The lines from the one at offset `start` on that hold `w`, a word
        with no line break in it."""
        if not w or b"\n" in w or b"\r" in w:
            raise ValueError(f"{w!r} is no word a line holds")
        out: set[int] = set()
        k = self.text.find(w, start)
        while k >= 0:
            out.add(self.line_of(k))
            k = self.text.find(w, k + 1)
        return frozenset(out)

    def index_agent_ids(self, start: int) -> dict[str, frozenset[int]]:
        """Each substring of the form of an agent id from offset `start` on,
        by the lines that hold it."""
        index: dict[bytes, set[int]] = {}
        for aid, k in agent_ids_in(self.text, start):
            index.setdefault(aid, set()).add(self.line_of(k))
        return {aid.decode(): frozenset(found) for aid, found in index.items()}

    def entry(self, i: int) -> list[Entry]:
        if i not in self.parsed:
            self.parsed[i] = parse(self.line(i))
        return self.parsed[i]

    def extended(self, more: bytes) -> "Snapshot":
        """This snapshot's whole lines followed by `more`, the text of its
        file after them, with what this one found in them kept. A carriage
        return also breaks a line, and one at the end of a read can open a
        break that the next byte ends, so a text that holds one is read
        whole."""
        whole = self.settled()
        offset = self.settled_end()
        text = self.text[:offset] + more
        if b"\r" in text:
            return Snapshot(text)
        out = Snapshot.__new__(Snapshot)
        out.text = text
        out.starts = line_starts(text, offset, self.starts[:whole])
        out.found = {w: frozenset(i for i in lines if i < whole)
                     | out.lines_holding(w.encode(), offset) for w, lines in self.found.items()}
        out.agent_ids = None
        if self.agent_ids is not None:
            kept = {aid: frozenset(i for i in lines if i < whole) if whole < self.count else lines
                    for aid, lines in self.agent_ids.items()}
            for aid, lines in out.index_agent_ids(offset).items():
                kept[aid] = kept.get(aid, frozenset()) | lines
            out.agent_ids = {aid: lines for aid, lines in kept.items() if lines}
        out.parsed = {i: e for i, e in self.parsed.items() if i < whole}
        return out


LINE_BREAK = re.compile(rb"\r\n|\r|\n")
"""A line break, as `bytes.splitlines` takes one."""


def line_starts(text: bytes, offset: int, before: list[int]) -> list[int]:
    """`before`, the offsets of the lines before `offset`, followed by the
    offset of each line of `text` from `offset` on, as `bytes.splitlines`
    splits it. A text with no carriage return is split by a search for each
    newline, which is faster than `LINE_BREAK`."""
    out = list(before)
    if offset >= len(text):
        return out
    out.append(offset)
    if b"\r" in text:
        out += [m.end() for m in LINE_BREAK.finditer(text, offset) if m.end() < len(text)]
        return out
    n = text.find(b"\n", offset)
    while 0 <= n < len(text) - 1:
        out.append(n + 1)
        n = text.find(b"\n", n + 1)
    return out


def epoch(iso: str) -> float:
    return datetime.fromisoformat(iso).timestamp()


def parse(line: str | bytes) -> list[Entry]:
    """The entry of `line`, or none where it is no JSON."""
    try:
        return [json.loads(line)]
    except json.JSONDecodeError:
        return []


_read: dict[Path, tuple[Snapshot, int, int]] = {}
"""The last snapshot of each transcript, with the device and inode of its
file, which a later read of a transcript that grew goes on from."""

CHECKED = 4096
"""How many bytes at each end of the whole lines of a transcript's last
snapshot a later read compares, to find a file that was written anew
rather than added to."""


@state_cache(stat_of)
def snapshot(path: Path) -> Snapshot:
    """The transcript at `path` as it stands at the state this process is
    in (`state_cache`). A transcript is added to at its end, so where the
    file is the one of its last snapshot and its bytes there still stand,
    only the bytes after that snapshot's whole lines are read."""
    with path.open("rb") as fh:
        st = os.fstat(fh.fileno())
        last = _read.get(path)
        snap = None
        if last is not None and last[1:] == (st.st_dev, st.st_ino):
            before = last[0]
            offset = before.settled_end()
            head = before.text[:min(CHECKED, offset)]
            tail_at = max(len(head), offset - CHECKED)
            if st.st_size >= offset and fh.read(len(head)) == head:
                fh.seek(tail_at)
                if fh.read(offset - tail_at) == before.text[tail_at:offset]:
                    snap = before.extended(fh.read())
        if snap is None:
            fh.seek(0)
            snap = Snapshot(fh.read())
    _read[path] = (snap, st.st_dev, st.st_ino)
    return snap


def read_entries(path: Path, naming: Iterable[str] | None = None) -> list[Entry]:
    """The entries of the transcript at `path` as it stands at the state this
    process is in, or with `naming` only those whose line holds one of its
    words, which spares parsing the rest."""
    return entries_naming(path, None if naming is None else frozenset(naming))


@state_cache(DERIVED)
def entries_naming(path: Path, naming: frozenset[str] | None) -> list[Entry]:
    """`read_entries`, held so that a read derived from it sees a change of
    the transcript only where the entries it gives change."""
    if naming is None:
        return list(entries_forward(path))
    snap = snapshot(path)
    start = own_start(path)
    lines = sorted(i for i in frozenset[int]().union(*(snap.holding(w) for w in naming))
                   if i >= start)
    return [e for i in lines for e in snap.entry(i)]


def entries_forward(path: Path) -> Iterator[Entry]:
    """The entries of the transcript at `path` as it stands at the state this
    process is in, in their order, each line parsed only when it is reached."""
    snap = snapshot(path)
    for i in range(own_start(path), snap.count):
        yield from snap.entry(i)


def entries_back(path: Path) -> Iterator[Entry]:
    """The entries of the transcript at `path` as it stands at the state this
    process is in, last first, each line parsed only when it is reached."""
    snap = snapshot(path)
    for i in range(snap.count - 1, own_start(path) - 1, -1):
        yield from snap.entry(i)


def meta_path(path: Path) -> Path:
    """The `.meta.json` file of the transcript at `path`."""
    return path.with_suffix(".meta.json")


@state_cache(lambda path: stat_of(meta_path(path)))
def transcript_meta(path: Path) -> dict[str, Any] | None:
    m = meta_path(path)
    return json.loads(m.read_text()) if m.is_file() else None


def blocks(entry: Entry, kind: str) -> list[dict[str, Any]]:
    content = (entry.get("message") or {}).get("content")
    if not isinstance(content, list):
        return []
    return [b for b in content if isinstance(b, dict) and b.get("type") == kind]


@state_cache(DERIVED)
def own_start(path: Path) -> int:
    """The index of the first line of the entries of the transcript at
    `path` that are its run's own. A fork's transcript opens with a copy of
    its parent's entries, through the Agent call that launched the fork,
    which its `.meta.json` gives as `toolUseId`, and its own entries open
    at the entry that holds that call's result. For each other transcript,
    and for a fork's where no line holds that result, it is 0."""
    meta = transcript_meta(path) or {}
    call = meta.get("toolUseId")
    if meta.get("isFork") is not True or not isinstance(call, str):
        return 0
    snap = snapshot(path)
    return next((i for i in sorted(snap.holding(call))
                 if any(b.get("tool_use_id") == call
                        for e in snap.entry(i) for b in blocks(e, "tool_result"))), 0)


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
