"""The hunks of a change: the paths it touches as the record's commit
sees them, and the line numbers of each modified Python file moved between
its old and new texts."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from engine import checkout
from gating.edits import inert

PY_SUFFIXES = frozenset({".py", ".pyc"})
"""The suffixes of the files a command depends on through the lines it
runs alone. A command also reads Python files' bytes, to import them and
to key the run cache."""


class Hunk(NamedTuple):
    """A hunk of a `-U0` unified diff: the first line and the count of its
    old side, and of its new side, a count of 0 an insertion after, or a
    deletion after, the first line."""
    old_start: int
    old_count: int
    new_start: int
    new_count: int

    @property
    def old_end(self) -> int:
        """The last line of the old side, where its count is not 0."""
        return self.old_start + self.old_count - 1

    @property
    def new_end(self) -> int:
        """The last line of the new side, where its count is not 0."""
        return self.new_start + self.new_count - 1


@dataclass(frozen=True)
class Touched:
    """A path the change touches, how it touches it, and, for a modified
    Python file, the line ranges of its recorded text it replaces, each its
    first line and its count, a count of 0 an insertion after the first
    line, with the new side of each. `unrecorded` is a Python file that stands at the change's base
    and not at the recorded commit, whose lines no command's record
    holds. `passed` holds the index in `hunks` of each hunk `inert`
    passes."""
    path: str
    status: checkout.Change
    hunks: tuple[Hunk, ...] = ()
    unrecorded: bool = False
    passed: frozenset[int] = frozenset()

    @property
    def live(self) -> tuple[Hunk, ...]:
        return tuple(h for i, h in enumerate(self.hunks) if i not in self.passed)

    @property
    def inert(self) -> bool:
        """Whether the file has hunks and `inert` passes each of them. A
        file with no hunk is run whole (`runs_hunks`)."""
        return bool(self.hunks) and not self.live


_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.M)


def hunks_of(diff: str) -> tuple[Hunk, ...]:
    """Each hunk of the unified diff `diff`, a count git leaves out read as
    1."""
    return tuple(Hunk(int(a), int(b) if b else 1, int(c), int(d) if d else 1)
                 for a, b, c, d in _HUNK_RE.findall(diff))


def moved(ran: frozenset[int], hunks: Sequence[Hunk]) -> frozenset[int]:
    """The lines `ran` of an old text, each numbered as it stands in the
    new text that `hunks` give. A line outside every hunk's old side moves
    by the lines the hunks before it add. A line inside a hunk's old side
    stands for the lines that hunk wrote, or, where it wrote none, for the
    line that follows the hunk in the new text; in the other direction, a
    line a hunk wrote stands for the lines of the old text that hunk
    replaced, or for its point of insertion."""
    out: set[int] = set()
    for n in ran:
        shift = 0
        for h in hunks:
            end = h.old_end if h.old_count else h.old_start
            if h.old_count and h.old_start <= n <= end:
                out.update(range(h.new_start, h.new_end + 1) if h.new_count
                           else (h.new_start + 1,))
                break
            if n > end:
                shift += h.new_count - h.old_count
        else:
            out.add(n + shift)
    return frozenset(out)


def between(old: str, new: str, *flags: str) -> set[str]:
    """The paths whose content differs between the commits `old` and `new`,
    of the statuses that `flags` filter."""
    return set(filter(None, checkout.git_out(checkout.ROOT, "diff", "--name-only",
                                             "--no-renames", "-z", *flags, old, new,
                                             ).split("\0")))


def touched_from(base: str, recorded: str) -> list[Touched]:
    """Each path whose content in the checkout differs from the commit
    `base` (`checkout.changed_paths`), as the commit `recorded` sees it. A
    path that stands at `base` and not at `recorded` is `unrecorded` where
    it is a Python file, and is otherwise added, or deleted where the change
    deletes it; a path that stands at `recorded` and
    not at `base` is modified where the change adds it. The hunks of a
    modified Python file are those of its diff from `base` to the checkout,
    with the old side of each numbered in the recorded text; where the file
    differs between the two commits, `renumbered` numbers them. The hunks
    from `recorded` to `base` count only where a hunk of the change meets
    them: the commits that wrote them passed their own merge's gate, whose
    accepted outputs this gate compares against. Each hunk of a path that
    stands at `base` is classified by `inert` against the `base` text, since the rules it applies are
    properties of the change's own edit."""
    moved = between(recorded, base)
    absent = between(recorded, base, "--diff-filter=A")
    gone = between(recorded, base, "--diff-filter=D")
    out: list[Touched] = []
    for c in checkout.changed_paths(checkout.ROOT, base):
        status = c.change
        if c.path in absent:
            if Path(c.path).suffix in PY_SUFFIXES:
                out.append(Touched(c.path, status, unrecorded=True))
                continue
            if status is not checkout.Change.DELETED:
                status = checkout.Change.ADDED
        elif c.path in gone:
            status = checkout.Change.MODIFIED
        hunks: tuple[Hunk, ...] = ()
        passed: frozenset[int] = frozenset()
        if status is checkout.Change.MODIFIED and Path(c.path).suffix in PY_SUFFIXES:
            hunks = _diff_hunks(c.path, base)
            if c.change is checkout.Change.MODIFIED:
                old = text_at(base, c.path)
                new = (checkout.ROOT / c.path).read_text().splitlines(keepends=True)
                passed = frozenset(i for i, h in enumerate(hunks) if inert(
                    c.path, old, new[h.new_start - 1:h.new_start - 1 + h.new_count], h))
            if c.path in moved:
                hunks = renumbered(hunks, _diff_hunks(c.path, recorded, base))
        out.append(Touched(c.path, status, hunks, passed=passed))
    return out


def text_at(commit: str, path: str) -> str:
    return checkout.git_out(checkout.ROOT, "show", f"{commit}:{path}")


def _diff_hunks(path: str, *commits: str) -> tuple[Hunk, ...]:
    """The `-U0` hunks of `path` from the first of `commits` to the second,
    or to the checkout where `commits` give one."""
    return hunks_of(checkout.git_out(checkout.ROOT, "diff", "-U0", "--no-color",
                                     "--no-ext-diff", *commits, "--", path))


def _old_line(n: int, since: Sequence[Hunk]) -> int:
    """The line `n` of the new text of `since`, which stands outside the
    new side of each, numbered in the old text: the inverse of `moved` on
    such a line."""
    shift = 0
    for r in since:
        if n > (r.new_end if r.new_count else r.new_start):
            shift += r.new_count - r.old_count
    return n - shift


def renumbered(hunks: Sequence[Hunk], since: Sequence[Hunk]) -> tuple[Hunk, ...]:
    """The hunks `hunks` of a diff from a text B, each with its old side
    numbered in the text A that the hunks `since` change into B. A line of
    B that a hunk of `since` wrote stands for the lines of A that `moved`
    states, so a hunk whose old side meets the new side of a hunk of
    `since` takes in that hunk's old side. An
    insertion meets a hunk of `since` where the line it follows is one that
    hunk wrote."""
    out: list[Hunk] = []
    for h in hunks:
        lo, hi = (h.old_start, h.old_end) if h.old_count else (h.old_start, h.old_start)
        met = [r for r in since if r.new_count
               and r.new_start <= hi and lo <= r.new_end]
        lines = {n for r in met for n in range(r.old_start, r.old_end + 1)}
        points = [r.old_start for r in met if not r.old_count]
        if h.old_count:
            lines |= {_old_line(n, since) for n in range(lo, hi + 1)
                      if not any(r.new_start <= n <= r.new_end for r in met)}
        elif not met:
            points.append(_old_line(h.old_start, since))
        out.append(Hunk(min(lines), max(lines) - min(lines) + 1, h.new_start, h.new_count)
                   if lines else Hunk(min(points), 0, h.new_start, h.new_count))
    return tuple(out)
