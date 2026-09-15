"""What a solver's cases do on its own pairs: which pairs tell two cases
apart, and which pairs a case is ill-formed on.

Every pair of the task counts, train and test alike. A case's key on a pair
is the set of grids it emits there, each grid or `ILL` when the grid is not
readable, and the stored output never enters the key. Two cases are separated by a pair when their keys there
differ, and the key tuples over all pairs partition the cases into
separation classes.
"""

import sys
from dataclasses import dataclass, field

from dl.solve import PairResult, res_out_stem, run_task

ILL = "ILL"
"""The key of a case that emits no readable grid on a pair."""

ABSENT = "ABSENT"
"""The key of a case that emits nothing at all on a pair."""

NO_CHOICE = "(out)"
"""The case name of a solver without a `Choice`: `out` carries no case
column, and the whole file is one case."""

type Grid = str | tuple[tuple[int, ...], ...]
type Key = frozenset[Grid] | str
type Matrix = dict[str, dict[str, int]]


@dataclass
class RunReport:
    cases: list[str] = field(default_factory=list)
    separating: dict[str, int] = field(default_factory=dict)
    illformed: dict[str, int] = field(default_factory=dict)
    separates: Matrix = field(default_factory=dict)
    classes: int = 0


def _ctor(text: str) -> str:
    """One constructor of a case name, without its `$` and its arguments."""
    return text.strip().removeprefix("$").split("(", 1)[0]


def _split(body: str) -> list[str]:
    """A record body split at the commas between its members. A comma inside
    a constructor's arguments stands inside that member."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in body:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


def case_members(case: str) -> list[str]:
    """The constructors one case label stands for: the members of a record
    label, and otherwise the label itself."""
    if case.startswith("[") and case.endswith("]"):
        body = case[1:-1].strip()
        return [_ctor(m) for m in _split(body)] if body else []
    return [case]


def case_label(name: str, resolution: bool = False) -> str:
    """The case a variant name stands for.

    `out` may carry columns past the case, tab-joined into the name. A
    resolution solver carries its `TiebreakResolution` term last, and that
    term is no case; what leads the name is. Every constructor of the name
    drops its `$` and its arguments: `$Ctor` and `$Ctor(args)` stand for
    `Ctor`, and a record case keeps its brackets and commas around the
    constructors it holds, `[Table, Lookup]`. A name with nothing left is
    the one case of a solver without a `Choice`.
    """
    parts = name.split("\t")
    if resolution:
        parts = parts[:-1]
    head = parts[0] if parts else ""
    if not head:
        return NO_CHOICE
    if head.startswith("[") and head.endswith("]"):
        return f"[{', '.join(case_members(head))}]"
    return _ctor(head)


def _grid(variant) -> Grid:
    if variant.error or variant.conflicts or variant.missing:
        return ILL
    return tuple(tuple(row) for row in variant.actual)


def _pair_keys(
    pairs: list[PairResult], cases: list[str] | None, resolution: bool,
) -> tuple[list[str], list[dict[str, Key]]]:
    """The cases in the order the pairs produce them, and each pair's key
    per case. `cases` leads that order, so a case silent on every pair is
    still reported. A pair that fails outright produces no case."""
    order: list[str] = list(cases or [])
    per_pair: list[dict[str, Key]] = []
    for p in pairs:
        emitted: dict[str, set[Grid]] = {}
        for v in p.variants:
            name = case_label(v.name, resolution)
            if name not in order:
                order.append(name)
            emitted.setdefault(name, set()).add(_grid(v))
        per_pair.append({n: frozenset(g) for n, g in emitted.items()})
    return order, per_pair


def report_of(pairs: list[PairResult], cases: list[str] | None = None,
              resolution: bool = False) -> RunReport:
    """The separation report over one solver's pair results."""
    cases, per_pair = _pair_keys(pairs, cases, resolution)
    separates = {
        a: {b: sum(1 for keys in per_pair
                   if keys.get(a, ABSENT) != keys.get(b, ABSENT))
            for b in cases if b != a}
        for a in cases
    }
    separating = {
        a: sum(1 for keys in per_pair
               if any(keys.get(a, ABSENT) != keys.get(b, ABSENT)
                      for b in cases if b != a))
        for a in cases
    }
    illformed = {a: sum(1 for keys in per_pair if ILL in keys.get(a, ()))
                 for a in cases}
    tuples = {tuple(keys.get(a, ABSENT) for keys in per_pair) for a in cases}
    return RunReport(cases=cases, separating=separating, illformed=illformed,
                     separates=separates, classes=len(tuples))


def run_features(stem: str, cases: list[str] | None = None) -> RunReport:
    """Run every pair of `stem`, train and test, and report how its cases
    separate. `cases` names the cases the source declares, so one that emits
    nothing on every pair is reported rather than dropped."""
    pairs = run_task(stem).pairs
    print(f"{stem}: {len(pairs)} pairs", file=sys.stderr)
    return report_of(pairs, cases, res_out_stem(stem))
