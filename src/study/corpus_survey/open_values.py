"""The Open values and constraint search section, from the files of `gen/`,
and its Models per case per input section, from Souffle runs of the
solvers of the most open values and of those whose `out` holds a
`TiebreakResolution` column."""

import math
from collections import Counter, defaultdict
from functools import cache

from arc.task import load as load_task
from controlled_markdown import mctx
from engine import RelationName
from study.corpus_survey import kept
from study.corpus_survey.bodies import DETERMINED
from study.corpus_survey.corpus import corpus
from study.corpus_survey.section import Section, body, dist, items, ran, table
from study.corpus_survey.solver_runs import columns, loaded, rows_on
from study.corpus_survey.trees import head, is_list

LARGEST = 5
"""The solvers of the largest products of open values the runs take."""
TIE = "TiebreakResolution"
MODEL_TYPES = ("OpenValue", TIE)
"""The types of the `out` columns whose distinct values per case are its
models."""
CASE_TYPE = "Choice"


@cache
def open_params() -> dict[str, dict[str, int]]:
    """Each parameter of a `DET` or `DET_OR_RULE` with `(ONE)` that has a
    `param` record, by stem, with the rows of that record."""
    c = corpus()
    found: dict[str, dict[str, int]] = {}
    for s in c.stems:
        ones = {str(n[1]) for n in c.nodes(s)
                if head(n) in DETERMINED and any(head(m) == "ONE" for m in n[2:])}
        if not ones:
            continue
        for f in c.arcdata(s):
            if head(f) == "param" and str(f[1]) in ones:
                assert isinstance(f, list)
                found.setdefault(s, {})[str(f[1])] = sum(1 for x in f[3:] if is_list(x))
    return found


def open_products() -> dict[str, int]:
    """The product of the rows of a file's open parameters, by stem."""
    return {s: math.prod(ps.values()) for s, ps in open_params().items()}


def largest(products: dict[str, int]) -> list[str]:
    return sorted(products, key=lambda s: (-products[s], s))[:LARGEST]


def open_values() -> str:
    c = corpus()
    params = open_params()
    rows = Counter(n for ps in params.values() for n in ps.values())
    picks: Counter[str] = Counter()
    one_files: set[str] = set()
    for s in c.stems:
        for n in c.nodes(s):
            h = head(n)
            if h in ("CHOOSE", "DEMONSTRATED"):
                picks[h] += 1
            elif h in ("RULE", "RULE_OR_DET") and any(head(m) == "ONE" for m in n[2:]):
                picks["RULE"] += 1
                one_files.add(s)
    products = open_products()
    top = largest(products)
    return body(items([
        mctx("{n} parameters of a `DET` or `DET_OR_RULE` with `(ONE)` have a `param` record: rows {rows}.")
        .format(n=sum(rows.values()), rows=dist(rows)),
        mctx("The largest products of those rows per file: {top}.").format(top=", ".join(f"{s} {products[s]}" for s in top)),
        mctx("`gen/` has {choose} `CHOOSE` forms, {rule} `RULE` clauses with `ONE` marks in {files} files, and {demo} `DEMONSTRATED` forms.")
        .format(choose=picks["CHOOSE"], rule=picks["RULE"], files=len(one_files), demo=picks["DEMONSTRATED"]),
    ]), ran(c.files() + " and `.arcdata` files"))


def models(stem: str) -> dict[str, object]:
    """The most models of a case of `out` on each train and test input, by
    the pair's name, or why the solver has none to count."""
    lo = loaded(stem)
    out = RelationName((), "out")
    cols = columns(lo, out)
    if cols is None:
        return {"none": "no out relation"}
    types = [t for _, t in cols]
    if CASE_TYPE not in types:
        return {"none": "no Choice column"}
    case = types.index(CASE_TYPE)
    model = [i for i, t in enumerate(types) if t in MODEL_TYPES]
    task = load_task(lo.solver.task_id)
    per: dict[str, int | str] = {}
    for section, pairs in (("train", task.train), ("test", task.test)):
        for i, ex in enumerate(pairs):
            got = rows_on(lo, ex.input, [out])
            if isinstance(got, str):
                per[f"{section} {i}"] = got
                continue
            by: dict[str, set[str]] = defaultdict(set)
            for row in got[out]:
                by[repr(row[case])].add(repr([row[j] for j in model]))
            per[f"{section} {i}"] = max((len(v) for v in by.values()), default=0)
    return {"tie": TIE in types, "inputs": per}


def stems_run() -> list[str]:
    """The solvers of the largest products of open values, then each other
    one whose `out` holds a `TiebreakResolution` column."""
    chosen = largest(open_products())
    for s in corpus().stems:
        if s not in chosen and kept.kept(SECTION, {**kept.solver_key(s), "part": "tie"}, lambda s=s: has_tie(s)):
            chosen.append(s)
    return chosen


def has_tie(stem: str) -> bool:
    cols = columns(loaded(stem), RelationName((), "out"))
    return cols is not None and any(t == TIE for _, t in cols)


SECTION = "models-per-case-per-input"


def models_section() -> str:
    got = {s: kept.kept(SECTION, kept.solver_key(s), lambda s=s: models(s)) for s in stems_run()}
    rows = []
    for s, r in got.items():
        per = r.get("inputs", {})
        counts = [v for v in per.values() if isinstance(v, int)]
        why = r["none"] if "none" in r else ", ".join(f"{k} {v}" for k, v in per.items() if not isinstance(v, int))
        rows.append((s, "yes" if r.get("tie") else "no", max(counts, default="none"), why or "none"))
    rows.sort(key=lambda r: (-(r[2] if isinstance(r[2], int) else -1), r[0]))
    return body(
        mctx("The models of a case on an input are the distinct values of the `OpenValue` and `TiebreakResolution` columns of the Souffle `out` relation under one value of its `Choice` column, on each train and test input, over the {n} solvers of the largest products of open values and each solver whose `out` holds a `TiebreakResolution` column.")
        .format(n=LARGEST),
        table(("stem", "tie column", "most models of a case on an input", "inputs with no count, and why"), rows),
        ran(f"Souffle runs of the {len(got)} solvers of `programs/solvers/` above, on the tasks of `data/tasks/`"))


OPEN_VALUES = Section("Open values and constraint search", 2, False, open_values)
MODELS = Section("Models per case per input", 3, True, models_section)
