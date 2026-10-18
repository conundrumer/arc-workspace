"""The reads of files that `state_reads.state_cache` holds: the stat of a
path, the text of a file, and the entries of a directory."""

import os
import stat
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from state_reads import in_read, state, state_cache

_stats: dict[str, os.stat_result | None] = {}
"""The stat `state_stat` read of each path at the state `_stats_at`, None
where there is no file."""

_stats_at = 0
"""The state whose stats `_stats` holds."""


def state_stat(path: str) -> os.stat_result | None:
    """`os.stat` of `path`, None where there is no file, read once for each
    state, as the reads of one state see one state."""
    global _stats_at
    if _stats_at != state():
        _stats.clear()
        _stats_at = state()
    if path in _stats:
        return _stats[path]
    try:
        found: os.stat_result | None = os.stat(path)
    except FileNotFoundError:
        found = None
    _stats[path] = found
    return found


def stat_of(path: Path) -> tuple[int, int] | None:
    """The modification time and size of the file at `path`, or None where
    there is none. Inside a `state_cache` read, each path is read once for
    each state (`state_stat`)."""
    if in_read():
        st = state_stat(str(path))
    else:
        try:
            st = path.stat()
        except FileNotFoundError:
            st = None
    return None if st is None else (st.st_mtime_ns, st.st_size)


@dataclass(frozen=True)
class FileStat:
    """What a stat that follows links gives of a file, as `stat_read` reads
    it: no time of last access, which a read of the file changes."""
    mtime: float
    mtime_ns: int
    size: int
    ino: int
    is_dir: bool
    is_file: bool


@state_cache(None)
def stat_read(path: Path) -> FileStat | None:
    """The stat of the file at `path`, or None where there is none."""
    st = state_stat(str(path))
    if st is None:
        return None
    return FileStat(st.st_mtime, st.st_mtime_ns, st.st_size, st.st_ino,
                    stat.S_ISDIR(st.st_mode), stat.S_ISREG(st.st_mode))


def is_file(path: Path) -> bool:
    """`Path.is_file`, from `stat_read`."""
    return stat_is(path, lambda found: found.is_file)


def is_dir(path: Path) -> bool:
    """`Path.is_dir`, from `stat_read`."""
    return stat_is(path, lambda found: found.is_dir)


def stat_is(path: Path, holds: Callable[[FileStat], bool]) -> bool:
    """Whether `holds` of the stat of the file at `path`, False where none
    reads, as `Path.is_file` takes a path under a file."""
    try:
        found = stat_read(path)
    except NotADirectoryError:
        return False
    return found is not None and holds(found)


def mtime(path: Path) -> float:
    """The time of the last write of the file at `path`, as `Path.stat`
    gives it, from `stat_read`; FileNotFoundError where there is none."""
    found = stat_read(path)
    if found is None:
        raise FileNotFoundError(path)
    return found.mtime


@state_cache(lambda path, errors=None: stat_of(path))
def file_text(path: Path, errors: str | None = None) -> str:
    """`Path.read_text` of the file at `path`, with `errors`."""
    return path.read_text(errors=errors)


@state_cache(None)
def resolved(path: Path) -> Path:
    """`Path.resolve` of `path`."""
    return path.resolve()


@dataclass(frozen=True)
class Named:
    """An entry of a directory, as `os.scandir` gives it: `is_dir` and
    `is_file` follow a link, and `is_link` says whether it is one."""
    name: str
    is_dir: bool
    is_file: bool
    is_link: bool


@state_cache(stat_of)
def listed(path: Path) -> tuple[Named, ...]:
    """The entries of the directory at `path`, or none where it is no
    directory that reads. Its stamp is the directory's stat, which an entry
    added, removed or renamed changes."""
    try:
        with os.scandir(path) as found:
            return tuple(Named(e.name, e.is_dir(), e.is_file(), e.is_symlink()) for e in found)
    except OSError:
        return ()


def names_in(path: Path) -> Iterator[str]:
    """The names of the entries `listed` gives of the directory at `path`."""
    return (e.name for e in listed(path))
