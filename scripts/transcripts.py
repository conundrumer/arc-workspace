"""Find the Claude Code transcripts of sessions and of agents under the
project directories: the project directories, the main and subagent
transcripts of sessions and agents, the runs they make up, and the lookup
of a transcript by id, each read held for one state of the process
(`state_cache`). `entry_reads` reads their entries."""

import filecmp
import os
import zlib
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path

from file_reads import Named, is_file, listed, stat_of  # noqa: F401
# `transcripts.new_state` is the name the tests of these reads open a state by.
from state_reads import DERIVED, Kept, new_state, state_cache  # noqa: F401

from controlled_markdown import mctx
from subagent_paths import SUBAGENTS, is_subagent  # noqa: F401
from claude_config import config_dir
from entry_reads import entries_back
from transcript_snapshots import Refused, parse, snapshot

CONSOLE_HOME_ENV = "CONSOLE_CLAUDE_HOME"


def console_home() -> Path:
    """The Claude home the console's workers run under, as
    `solver_console.config.CLAUDE_HOME` gives it; the kept reads import no
    module of the console."""
    return Path(os.environ.get(CONSOLE_HOME_ENV, Path.home() / ".claude-console"))


@state_cache(None)
def project_dirs() -> list[Path]:
    dirs: list[Path] = []
    for d in (config_dir() / "projects", console_home() / "projects"):
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
    """The path of each entry `walked_entries` gives."""
    return (os.path.join(d, e.name) for d, e in walked_entries(top, listing))


def walked_entries(top: str,
                   listing: Callable[[Path], tuple[Named, ...]]) -> Iterator[tuple[str, Named]]:
    """Each entry that is no directory in the tree of `top`, with the path
    of its directory, as `os.walk` gives the files of each directory, with
    `listing` as each directory's entries: a link to a directory is not
    descended."""
    for e in listing(Path(top)):
        if not e.is_dir:
            yield top, e
        elif not e.is_link:
            yield from walked_entries(os.path.join(top, e.name), listing)


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
    session's from `session_agent_transcripts`, so that a new transcript reads again
    only the agent ids of its session."""
    out: dict[str, list[Path]] = {}
    for s in sessions_under(dirs, listed):
        for agent, paths in session_agent_transcripts(s).items():
            out.setdefault(agent, []).extend(paths)
    return out


@state_cache(DERIVED)
def session_agent_transcripts(session: Path) -> dict[str, list[Path]]:
    """`by_agent` of `session_subagents` of `session`."""
    return by_agent(session_subagents(session))


def transcripts_of(agent: str) -> list[Path]:
    """The transcripts `agent_transcripts` gives the agent `agent`."""
    return agent_paths(tuple(project_dirs()), agent)


@state_cache(DERIVED, kept=Kept.VALUE)
def agent_paths(dirs: tuple[Path, ...], agent: str) -> list[Path]:
    """`transcripts_of` the agent `agent` under `dirs`, held so that a read
    derived from them sees a change only where they change."""
    return agent_shard(dirs, shard_of(agent)).get(agent, [])


SHARDS = 256
"""The count of the parts `agent_shards` splits the agent index into."""


def shard_of(agent: str) -> int:
    """The part of the agent index that holds the agent `agent`."""
    return zlib.crc32(agent.encode()) % SHARDS


@state_cache(DERIVED)
def agent_shards(dirs: tuple[Path, ...]) -> tuple[dict[str, list[Path]], ...]:
    """`agent_transcripts_in` of `dirs`, split by `shard_of` its agent ids."""
    out: tuple[dict[str, list[Path]], ...] = tuple({} for _ in range(SHARDS))
    for agent, paths in agent_transcripts_in(dirs).items():
        out[shard_of(agent)][agent] = paths
    return out


@state_cache(DERIVED)
def agent_shard(dirs: tuple[Path, ...], shard: int) -> dict[str, list[Path]]:
    """The part `shard` of `agent_shards` of `dirs`, held so that a new
    agent runs again only the `agent_paths` reads of its part."""
    return agent_shards(dirs)[shard]


def mains_named(name: str) -> list[Path]:
    """The transcripts `main_transcripts` gives `name`."""
    return main_paths(tuple(project_dirs()), name)


@state_cache(DERIVED, kept=Kept.VALUE)
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


def held_find(ident: str) -> Path | None:
    """The transcript `find` gives the session or agent id `ident`, of the
    agent index this state holds, or None where that index holds none."""
    for found in (sorted(mains_named(ident)), transcripts_of(bare_id(ident))):
        path = one_of(ident, found)
        if path:
            return path
    return None


def find(ident: str) -> Path:
    """The transcript `ident` names, and for a run of more than one
    transcript, its last. A miss reads the agent index of the directories
    as they stand then, before each refusal, for a transcript born after
    the held index was read."""
    if ident.endswith(".jsonl"):
        path = Path(ident).expanduser()
        if not is_file(path):
            raise Refused(mctx("no file `{path}`").format(path=path))
        return path
    path = held_find(ident)
    if path:
        return path
    fresh = agent_index(tuple(project_dirs()), listed.__wrapped__)
    path = one_of(ident, fresh.get(bare_id(ident), []))
    if path:
        return path
    raise Refused(mctx("no transcript of session or agent `{ident}` under "
                       "{dirs}").format(ident=ident, dirs=", ".join(
                           str(d) for d in project_dirs())))


def launched_find(aid: str) -> Path | None:
    """The transcript `find` gives the agent id `aid`, taken from a launch
    in a parent's transcript, or None where `find` refuses it. A launch's
    record in the parent's transcript is written before the launched
    agent's transcript, so None reads as an agent that has done nothing
    yet."""
    try:
        return find(aid)
    except Refused:
        return None


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
