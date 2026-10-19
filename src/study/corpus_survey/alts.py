"""The sections on the cases of each solver of `gen/`: Alts structure, from
the arclog files and the cases of the snapshot `.cache/parity/`, and Forms
per solver."""

from collections import defaultdict
from collections.abc import Iterator
from functools import cache

from controlled_markdown import mctx
from parity.snapshot import stored
from study.corpus_survey.bodies import BLOCKS, CLAUSES, Kind, columns
from study.corpus_survey.corpus import corpus
from study.corpus_survey.section import Section, body, items, median, most, ran, table
from study.corpus_survey.trees import Node, head, is_list

SPLITS = frozenset({"ALTS", "DET_OR_RULE", "RULE_OR_DET"})
"""The forms that split a file's cases: an `ALTS` form, and a
`DET_OR_RULE` or `RULE_OR_DET` line, an `ALTS` form on its relation."""

BINS = ((1, 1), (2, 2), (3, 4), (5, 8), (9, 16), (17, 64))
TOP = 8
"""The files the cases row lists past the largest."""
SOLVERS = 4
"""The files of the most cases that Forms per solver lists."""


def framed(forms: list[Node], frames: tuple[str, ...] = ()) -> Iterator[tuple[list[Node], tuple[str, ...]]]:
    """Each headed node of `forms` with the heads of the `ALTS` and `ALT`
    blocks it stands in, outermost first."""
    for f in forms:
        h = head(f)
        if h is None:
            continue
        assert isinstance(f, list)
        yield f, frames
        inner = (*frames, h) if h in ("ALTS", "ALT") else frames
        yield from framed([x for x in f[1:] if is_list(x)], inner)


@cache
def cases() -> dict[str, int]:
    """The number of cases of each solver of `gen/` that the snapshot holds
    a record of."""
    found: dict[str, int] = {}
    for s in corpus().stems:
        record = stored(s)
        if record is not None and "cases" in record:
            found[s] = len(record["cases"])
    return found


def alts_section() -> str:
    c = corpus()
    splits: dict[str, int] = {}
    depth: dict[str, int] = {}
    combos = 0
    excludes: dict[str, int] = {}
    for s in c.stems:
        splits[s] = depth[s] = 0
        for f, frames in framed(c.arclog[s]):
            h = head(f)
            if h in SPLITS:
                splits[s] += 1
                depth[s] = max(depth[s], 1 + frames.count("ALTS"))
            if h == "ALT" and frames and frames[-1] == "ALT":
                combos += 1
        excludes[s] = sum(1 for f in c.arcdata(s) if head(f) == "exclude")
    n = cases()
    by = sorted(n, key=lambda s: (-n[s], s))
    deepest, most_splits, most_excl = most(depth)[1], most(splits)[1], most(excludes)[1]
    bins = [(f"{lo}" if lo == hi else f"{lo}–{hi}", sum(1 for v in n.values() if lo <= v <= hi)) for lo, hi in BINS]
    bins.append((f"more than {BINS[-1][1]}", sum(1 for v in n.values() if v > BINS[-1][1])))
    return body(
        mctx("Here an `ALTS` form includes each `DET_OR_RULE` and `RULE_OR_DET` line, and its depth is one more than the `ALTS` forms it stands in. A combination block is an `ALT` that stands directly in an `ALT`. The cases of a file are the cases that the file's record in the snapshot `.cache/parity/` holds, as `docs/engine/cases.md#cases` gives them."),
        table(("measure", "value"), [
            ("files with an `ALTS` form", sum(1 for v in splits.values() if v)),
            ("`ALTS` forms per file, max", f"{splits[most_splits]} ({most_splits})"),
            ("ALTS nesting depth, max", f"{depth[deepest]} ({deepest}); {sum(1 for v in depth.values() if v >= 2)} files at depth 2 or more"),
            ("combination ALT blocks", combos),
            ("cases per file", f"median {median(list(n.values()))}; max {n[by[0]]} ({by[0]}), then "
                               + ", ".join(f"{s} {n[s]}" for s in by[1:TOP])),
            ("files with excludes", f"{sum(1 for v in excludes.values() if v)}; {sum(excludes.values())} excludes; "
                                    f"max {excludes[most_excl]} per file ({most_excl})"),
        ]),
        table(("cases", "files"), bins),
        ran(f"{c.files()} and their `.arcdata` files, and the records of `.cache/parity/` of the {len(n)} of them that have one"))


def declarations(forms: list[Node], found: dict[str, list[frozenset[str] | str | None]]) -> None:
    """Each declaration form of `forms` under its relation: a clause by its
    columns (`bodies.columns`), None for a clause with no body, any other
    form by its head."""
    for f in forms:
        h = head(f)
        if h is None:
            continue
        assert isinstance(f, list)
        if h in BLOCKS:
            declarations(f[1:], found)
        elif h in Kind.__members__ and Kind(h) in CLAUSES:
            its = [x for x in f[2:] if is_list(x)]
            found[str(f[1])].append(columns(its) if its else None)
        elif h in ("INIT", "DEMONSTRATED", "CHOOSE"):
            found[str(f[1])].append(h)


def forms_per_solver() -> str:
    c = corpus()
    rows: dict[str, tuple[int, int, int, int]] = {}
    for s in c.stems:
        found: dict[str, list[frozenset[str] | str | None]] = defaultdict(list)
        declarations(c.arclog[s], found)
        multi = {k: v for k, v in found.items() if len(v) > 1}
        rows[s] = (sum(len(v) for v in found.values()), len(found), len(multi),
                   sum(1 for v in multi.values() if len(set(v)) > 1))
    n = cases()
    shown = sorted(n, key=lambda s: (-n[s], s))[:SOLVERS]
    most_forms = most({s: r[0] for s, r in rows.items()})[1]
    if most_forms not in shown:
        shown.append(most_forms)
    return body(
        mctx("Declaration forms per file, a relation that more than one block derives, and such a relation whose clauses have more than one set of top-level labels, for the {n} files of the most cases and the file of the most forms.")
        .format(n=SOLVERS),
        table(("stem", "cases", "forms", "relations", "rederived", "with another column set"),
              ((s, n.get(s, ""), *rows[s]) for s in shown)),
        items([mctx("{n} files have a relation rederived with another column set.")
               .format(n=sum(1 for r in rows.values() if r[3]))]),
        ran(f"{c.files()}, and the records of `.cache/parity/`"))


ALTS = Section("Alts structure", 2, False, alts_section)
FORMS_PER_SOLVER = Section("Forms per solver", 2, False, forms_per_solver)
