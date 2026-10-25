"""The Prefix sizes section: the row count of each written prefix of a
body's top-level items, against the body's, from the Souffle rows of its
solver on two train inputs; and, for the bodies over `REORDERED`, the
least largest prefix over every order the modes allow."""

import time
from multiprocessing import Pool
from typing import Any

from arclog_convert.lib import ALGEBRA_MODES
from controlled_markdown import mctx
from parity import name_map
from study.corpus_survey import kept
from study.corpus_survey.bodies import Body, deep_atoms, is_const, strip
from study.corpus_survey.corpus import bodies_of, corpus
from study.corpus_survey.section import Section, body, ran, table
from study.corpus_survey.simulation import (
    OVER,
    Classified,
    Entry,
    Eval,
    Mark,
    Status,
    Stem,
    build,
    classify,
    measured,
)
from study.corpus_survey.solver_runs import dump

LIMIT = 10.0
"""The seconds one count may take before it is `timeout`."""
REORDERED = 10_000
"""The largest prefix past which a body's other orders are searched."""
MOST_ATOMS = 12
REORDER_LIMIT = 120.0
"""The seconds the search of one body's orders may take."""
"""The most top-level items of a body whose orders are searched."""
BIG = OVER + 1
WORKERS = 6


def rows(stem: str) -> dict[str, Any]:
    """The kept dump of `stem` (`solver_runs.dump`)."""
    c = corpus()
    read = {str(a[0])[1:] for b in bodies_of(c, stem) for a in deep_atoms(b.items) if str(a[0]).startswith("&")}
    return kept.kept("prefix-sizes", {**kept.solver_key(stem, [c.gen / f"{stem}.arclog"]), "part": "rows"},
                     lambda: dump(stem, read))


def stem_of(name: str) -> Stem:
    names = name_map(name)
    if names is None:
        raise LookupError(f"the converter wrote no name map of {name}")
    return Stem(name, corpus().arclog[name], rows(name), dict(names.constructors))


def value(x: Any) -> int | None:
    return BIG if x == Mark.OVER else None if x == Mark.TIMEOUT else x


def measure_body(ev: Eval, st: Stem, b: Body) -> dict[str, Any]:
    c = classify(b.items, ev, st.pins(b), st)
    if c.unresolved:
        return dict(status=Status.UNRESOLVED, why=c.unresolved[:3])
    if not any(e[0] == Entry.STORED for e in c.ent):
        return dict(status=Status.NO_STORED)
    sizes: list[Any] = []
    prev_sql, prev = None, None
    skipped: set[str] = set()
    for u in range(1, len(c.ent) + 1):
        sql, sk = build(ev, c.ent, list(range(u)))
        if u == len(c.ent):
            skipped |= set(sk)
        if sql == prev_sql:
            sizes.append(prev)
            continue
        prev = ev.count(sql)
        sizes.append(prev)
        prev_sql = sql
    sql, sk = build(ev, c.ent, list(range(len(c.ent))), c.negs, c.neg_alg)
    skipped |= set(sk)
    full = ev.count(sql) if (c.negs or c.neg_alg) else sizes[-1]
    return dict(status=Status.OK, sizes=sizes, full=full, ign=dict(c.ignored), skipped=sorted(skipped),
                reorder=reorder(ev, b, c) if max((v for v in map(value, sizes) if v is not None), default=0) > REORDERED else None)


def labels(e: tuple[Any, ...]) -> set[str]:
    if e[0] == Entry.STORED:
        toks = [t for _, t in e[1]["sites"]]
    elif e[0] == Entry.ALGEBRA:
        toks = [t for _, t in e[3]]
    elif e[0] == Entry.EQUAL:
        toks = [e[1], e[2]]
    else:
        toks = [e[2], e[3]]
    return {strip(t) for t in toks if not is_const(t)}


def reorder(ev: Eval, b: Body, c: Classified) -> dict[str, Any]:
    """The least largest prefix over every order of the entries that the
    algebra modes allow, by dynamic programming over the sets of entries."""
    ent, n = c.ent, len(c.ent)
    if n > MOST_ATOMS:
        return dict(skip=f"{n} items")

    def placeable(i: int, placed: list[int]) -> bool:
        e = ent[i]
        bound = set(b.keycols).union(*(labels(ent[j]) for j in placed))
        if e[0] == Entry.STORED:
            return True
        if e[0] == Entry.ALGEBRA:
            rel = e[2]
            if rel not in ALGEBRA_MODES:
                return True
            cols: dict[str, list[str]] = {}
            for col, t in e[3]:
                cols.setdefault(col, []).append(t)
            return any(all(col in cols and all(is_const(t) or strip(t) in bound for t in cols[col]) for col in m)
                       for m in ALGEBRA_MODES[rel])
        if e[0] == Entry.EQUAL:
            return strip(e[2]) in bound or is_const(e[2]) or strip(e[1]) in bound
        return all(strip(x) in bound or is_const(x) for x in (e[2], e[3]))

    cache: dict[str, int] = {}
    deadline = time.time() + REORDER_LIMIT

    def size(mask: int) -> int:
        if time.time() > deadline:
            raise TimeoutError
        sql, _ = build(ev, ent, [k for k in range(n) if mask >> k & 1])
        if sql not in cache:
            r = ev.count(sql)
            cache[sql] = BIG if r == Mark.OVER else BIG * 10 if r == Mark.TIMEOUT else int(r)
        return cache[sql]

    try:
        return search(n, size, placeable)
    except TimeoutError:
        return dict(skip=f"over {REORDER_LIMIT:.0f} s")


def search(n: int, size, placeable) -> dict[str, Any]:
    """The largest written prefix, and the least largest prefix over the
    orders `placeable` allows, of `n` entries whose prefix counts `size`
    gives by the mask of the entries."""
    written = max(size((1 << (k + 1)) - 1) for k in range(n))
    inf = float("inf")
    best: dict[int, tuple[float, int | None]] = {0: (0, None)}
    for mask in range(1, 1 << n):
        bv: tuple[float, int | None] = (inf, None)
        sz = None
        for k in range(n):
            if not mask >> k & 1:
                continue
            pm = mask ^ (1 << k)
            if best[pm][0] == inf or not placeable(k, [j for j in range(n) if pm >> j & 1]):
                continue
            if sz is None:
                sz = size(mask)
            v = max(best[pm][0], sz)
            if v < bv[0]:
                bv = (v, k)
        best[mask] = bv
    full = (1 << n) - 1
    return dict(written_max=written, best_max=best[full][0] if best[full][0] != inf else None)


def measure_stem(name: str) -> list[dict[str, Any]]:
    """The measure of each measured body of `name` on each dumped input."""
    try:
        st = stem_of(name)
    except Exception as e:  # a solver that does not load or run
        return [dict(stem=name, status=Status.NO_ROWS, err=repr(e)[:200])]
    found: list[dict[str, Any]] = []
    for idx, inp in st.dump["inputs"].items():
        if "rel" not in inp:
            found.append(dict(stem=name, input=idx, status=Status.NO_RUN, err=inp.get("error")))
            continue
        ev = Eval(st, idx, LIMIT)
        for bi, b in enumerate(bodies_of(corpus(), name)):
            if not measured(b):
                continue
            r: dict[str, Any]
            try:
                r = measure_body(ev, st, b)
            except Exception as e:  # a body the simulation does not parse
                r = dict(status=Status.FAILED, err=repr(e)[:200])
            r.update(stem=name, input=idx, kind=b.kind.value, name=b.name, bi=bi)
            found.append(r)
        ev.close()
    return found


def kept_measure(name: str) -> list[dict[str, Any]]:
    c = corpus()
    return kept.kept("prefix-sizes", kept.solver_key(name, [c.gen / f"{name}.arclog"]),
                     lambda: measure_stem(name))


def measures() -> list[dict[str, Any]]:
    with Pool(WORKERS) as p:
        return [r for rs in p.imap(kept_measure, corpus().stems, chunksize=1) for r in rs]


def per_body(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each measured body on the input of its largest prefix."""
    per: dict[tuple[str, int], dict[str, Any]] = {}
    for r in results:
        if r.get("status") != Status.OK:
            continue
        ints = [v for v in map(value, r["sizes"]) if v is not None]
        if not ints:
            continue
        r = dict(r, maxp=max(ints), fullv=value(r["full"]))
        k = (r["stem"], r["bi"])
        if k not in per or r["maxp"] > per[k]["maxp"]:
            per[k] = r
    return list(per.values())


def prefix_section() -> str:
    results = measures()
    bs = per_body(results)
    with_full = [b for b in bs if b["fullv"] is not None]

    def over(t: float) -> list[dict[str, Any]]:
        return [b for b in bs if b["maxp"] > t]

    def shrinks(t: float) -> int:
        return sum(1 for b in with_full if b["maxp"] > t and b["fullv"] < b["maxp"] / 100)

    reached = [b for b in over(REORDERED) if b.get("reorder") and b["reorder"].get("best_max") is not None]
    brought = sorted((b for b in reached if b["reorder"]["best_max"] <= REORDERED), key=lambda b: -b["maxp"])
    example = (f", such as {brought[0]['stem']} `{brought[0]['name']}`, {brought[0]['maxp']} rows to {int(brought[0]['reorder']['best_max'])}"
               if brought else "")
    status: dict[str, int] = {}
    for r in results:
        status[r.get("status", "")] = status.get(r.get("status", ""), 0) + 1
    return body(
        mctx("The row count of each written prefix of a body's top-level items, against the body's. Each solver of `gen/` ran on Souffle on train input 0 and its largest train input, with every relation of its name map written out, and the prefixes were joined from those rows, with the orientation tables, the Box and number relations, the checks and the comparisons applied; the bodies measured are those of a `RULE`, `DET_OR_RULE` or `RULE_OR_DET` clause and an instance's key clause and inputs, each on the rows of the case its alts pin. `divide`, `frame_offset`, `OR`, `IF`, `ALL` and `ONE` are not applied, so a body that holds one has an upper bound for its count. A prefix's count is the product of its parts, so a prefix of two parts that share no label counts as their cross product. A body's largest prefix is taken on the input where it is largest."),
        table(("measure", "value"), [
            ("bodies measured", f"{len(bs)} of {len({b['stem'] for b in bs})} solvers; other outcomes: "
                                + ", ".join(f"{k} {v}" for k, v in sorted(status.items()) if k != Status.OK)),
            ("largest prefix", f"≤10^3 in {sum(1 for b in bs if b['maxp'] <= 1000)} bodies; over 10^4 in {len(over(1e4))}, "
                               f"over 10^5 in {len(over(1e5))}, over 10^6 in {len(over(1e6))}, over 10^7 in {len(over(1e7))}"),
            ("largest prefix over 100 times the full body", sum(1 for b in with_full if b["maxp"] > 100 * max(1, b["fullv"]))),
            ("prefix over 10^5 with the full body under 1/100 of it", shrinks(1e5)),
            ("prefix over 10^6 with the full body under 1/100 of it", shrinks(1e6)),
            ("bodies over 10^4 that another order the modes allow brings under it",
             f"{len(brought)} of the {len(reached)} of at most {MOST_ATOMS} items whose search ended within {REORDER_LIMIT:.0f} s{example}"),
        ]),
        ran(f"Souffle runs of the solvers of {corpus().files()}, on their tasks' train inputs, with the converter's name maps under `work/arclog/names/`"))


PREFIX_SIZES = Section("Prefix sizes", 2, True, prefix_section)

