"""Whether a change can affect a gate command, from what the command
depends on (`gating.deps.Deps`) and the hunks of the change
(`gating.hunks.Touched`)."""

import ast
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from engine import checkout
from gating.commands import ACCEPTED, GateCommand
from gating.deps import GATE_READS, Deps
from gating.hunks import PY_SUFFIXES, Hunk, Touched, lib_dl

COMMENT_READERS = {
    "src/handbook/lib.py": frozenset({"_doc_blocks", "_prose"}),
    "src/handbook/items.py": frozenset({"_view"}),
    "src/solver/annotations.py": frozenset({"input_mark_lines"}),
    "src/checker/lint/form/witnesses.py": frozenset({"_constructions"}),
}
"""By file, the functions that read the comment text of a Souffle file of
the lib. A command that runs none of them gives the same outputs for a
hunk `inert_dl` passes."""


@dataclass(frozen=True)
class Function:
    """A function of a Python text: its name, the first line of its header,
    its decorators included, the first line of its body, and its last line."""
    name: str
    first: int
    body: int
    last: int


def functions(source: str) -> list[Function]:
    return [Function(n.name, min([n.lineno, *(d.lineno for d in n.decorator_list)]),
                     n.body[0].lineno, n.end_lineno or n.lineno)
            for n in ast.walk(ast.parse(source))
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def runs_hunks(source: str, hunks: Sequence[Hunk], ran: frozenset[int]) -> bool:
    """Whether a command that ran the lines `ran` of the Python text
    `source` runs a part that `hunks` replace. A hunk inside the body of a
    function is run where a line of the innermost such function's body
    ran; a hunk elsewhere, a header among them, runs when the file is
    imported, so it is run where any line of the file ran. An insertion
    after a function's last line may stand in its body or after it, so it
    is taken to stand after it. A file with no
    hunk is run where any line ran."""
    if not ran:
        return False
    if not hunks:
        return True
    fs = functions(source)
    for h in hunks:
        lo, hi = (h.old_start, h.old_end) if h.old_count else (h.old_start, h.old_start + 1)
        inside = [f for f in fs if f.first <= lo and hi <= f.last]
        if not inside:
            return True
        f = max(inside, key=lambda f: f.first)
        header = lo < f.body if h.old_count else h.old_start < f.body - 1
        if header or any(f.body <= n <= f.last for n in ran):
            return True
    return False


def affects(cmd: GateCommand, stem: str, deps: Deps, touched: Sequence[Touched],
            recorded: dict[str, str]) -> bool:
    """Whether the changes `touched` can affect `cmd` on `stem`, which
    depends on `deps`, with `recorded` the recorded text of each Python file
    they modify or delete, and of each file of `COMMENT_READERS` that stands
    at the record's commit where they modify a Souffle file of the lib
    (`lib_dl`). A change affects it where it touches a
    file of `GATE_READS`, the command's accepted outputs, a file the gate
    copies for it (`copied`), or a file it opened to read; where it adds or
    deletes a file in a directory it listed; and where it changes a Python
    file part of which it runs, as `runs_hunks` decides. A Python file
    affects it through the lines it runs alone (`PY_SUFFIXES`), so a Python
    file the change adds affects it through the lines that import it. An
    `unrecorded` file affects every command, since the record cannot say
    which commands run it. A hunk `inert` passes affects no command, a
    Souffle file of the lib whose hunks `inert_dl` passes each affects only
    a command that ran a body line of a function of `COMMENT_READERS`, or
    every command where a file or function of `COMMENT_READERS` is absent
    from `recorded`, since the record cannot say which commands ran that
    reader under its old name or place, and a
    modified Python file of `GATE_READS` is run whole by every command
    through each other hunk."""
    accepted = ACCEPTED.relative_to(checkout.ROOT)
    own = {str(accepted / f"{cmd.key(stem)}.{e}") for e in cmd.exts}
    copied = [p.relative_to(checkout.ROOT) for p in cmd.copied(stem)]
    for t in touched:
        if t.unrecorded:
            return True
        if t.path in own or any(Path(t.path).is_relative_to(p) for p in copied):
            return True
        if t.inert and lib_dl(t.path):
            for p in COMMENT_READERS:
                lines = reader_lines(p, recorded[p]) if p in recorded else None
                if lines is None or lines & deps.lines.get(p, frozenset()):
                    return True
            continue
        if t.inert:
            continue
        if any(Path(t.path).is_relative_to(p) for p in GATE_READS):
            return True
        if Path(t.path).suffix not in PY_SUFFIXES:
            if t.path in deps.reads or ((t.status.added or t.status is checkout.Change.DELETED)
                                        and str(Path(t.path).parent) in deps.listed):
                return True
        elif t.path in deps.lines and not t.status.added:
            if runs_hunks(recorded[t.path],
                          t.live if t.status is checkout.Change.MODIFIED else (),
                          deps.lines[t.path]):
                return True
    return False


@cache
def reader_lines(path: str, source: str) -> frozenset[int] | None:
    """The body lines of the functions of `COMMENT_READERS` in `path`,
    whose text is `source`: a module-level line, a `def` line among them,
    runs when the file is imported, and reads no comment. None where
    `source` holds no function of some name `COMMENT_READERS` gives for
    `path`."""
    names = COMMENT_READERS[path]
    found = [f for f in functions(source) if f.name in names]
    if names - {f.name for f in found}:
        return None
    return frozenset(i for f in found for i in range(f.body, f.last + 1))
