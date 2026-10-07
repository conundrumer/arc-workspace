"""Find the Claude Code transcripts of sessions and of agents under the
project directories, and read their entries."""

import filecmp
import json
import re
from collections.abc import Iterator
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any

from controlled_markdown import mctx
from handbook.paths import console_importable

console_importable()

from solver_console import config  # noqa: E402

type Entry = dict[str, Any]


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


SUBAGENTS = "subagents/**/agent-*.jsonl"
"""The glob of a session's subagent transcripts, under its directory."""


def main_transcript(session: Path) -> Path:
    return session.with_suffix(".jsonl")


def session_directory(main: Path) -> Path:
    return main.with_suffix("")


def subagent_transcripts(session: Path) -> list[Path]:
    return sorted(session.glob(SUBAGENTS))


@cache
def agent_transcripts() -> dict[str, list[Path]]:
    """The subagent transcripts under the project directories, by agent id."""
    out: dict[str, list[Path]] = {}
    for p in sorted(p for d in project_dirs() for s in d.glob("*/*/")
                    for p in subagent_transcripts(s)):
        out.setdefault(agent_id(p), []).append(p)
    return out


def find(ident: str) -> Path:
    """The transcript `ident` names, and for a run of more than one
    transcript, its last."""
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


def first_parent(path: Path) -> str | None:
    """The `parentUuid` of the first entry of the transcript at `path`, with
    only the lines up to that entry parsed."""
    first = next(entries_forward(path), None)
    return first.get("parentUuid") if first is not None else None


@cache
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
    parsed for such a word."""

    def __init__(self, path: Path) -> None:
        self.lines = path.read_bytes().splitlines()
        self.found: dict[str, frozenset[int]] = {}
        self.agents: dict[str, frozenset[int]] | None = None
        self.parsed: dict[int, list[Entry]] = {}

    def by_agent(self, agent_id: re.Pattern[str]) -> dict[str, frozenset[int]]:
        """The lines that hold each agent id, found in one pass."""
        if self.agents is None:
            # A lookahead finds each of two ids that overlap.
            at = re.compile(rb"(?=(%s))" % agent_id.pattern.encode())
            index: dict[str, set[int]] = {}
            for i, line in enumerate(self.lines):
                for aid in at.findall(line):
                    index.setdefault(aid.decode(), set()).add(i)
            self.agents = {aid: frozenset(v) for aid, v in index.items()}
        return self.agents

    def holding(self, word: str) -> frozenset[int]:
        #`ticket_log` imports this module.
        from ticket_log import AGENT_ID

        if word not in self.found:
            if AGENT_ID.fullmatch(word):
                self.found[word] = self.by_agent(AGENT_ID).get(word, frozenset())
            else:
                w = word.encode()
                self.found[word] = frozenset(
                    i for i, line in enumerate(self.lines) if w in line)
        return self.found[word]

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


@cache
def snapshot(path: Path) -> Snapshot:
    """The transcript at `path` as it stood when this process first read
    it."""
    return Snapshot(path)


def read_entries(path: Path, naming: set[str] | None = None) -> list[Entry]:
    """The entries of the transcript at `path` as it stood when this process
    first read it, or with `naming` only those whose line holds one of its
    words, which spares parsing the rest."""
    snap = snapshot(path)
    if naming is None:
        return [e for line in snap.lines for e in parse(line)]
    lines = sorted(frozenset[int]().union(*(snap.holding(w) for w in naming)))
    return [e for i in lines for e in snap.entry(i)]


def entries_forward(path: Path) -> Iterator[Entry]:
    """The entries of the transcript at `path` as it stood when this process
    first read it, in their order, each line parsed only when it is reached."""
    snap = snapshot(path)
    for i in range(len(snap.lines)):
        yield from snap.entry(i)


def entries_back(path: Path) -> Iterator[Entry]:
    """The entries of the transcript at `path` as it stood when this process
    first read it, last first, each line parsed only when it is reached."""
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
