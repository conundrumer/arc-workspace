"""The sections that count the forms of the arclog and arcdata files of
`gen/`: Forms, Instances, Arcdata, Columns and Rare constructs."""

import re
from collections import Counter, defaultdict
from functools import cache

from arclog_convert.lib import PROPOSER_COLS
from arclog_convert.lint import LIB
from controlled_markdown import mctx
from study.corpus_survey.bodies import (
    CLAUSES,
    DETERMINED,
    OPS,
    Item,
    deep_atoms,
    exported,
    item_kind,
    item_labels,
    key_labels,
    site_pairs,
    strip,
)
from study.corpus_survey.corpus import bodies_of, corpus
from study.corpus_survey.section import (
    Section,
    body,
    dist,
    items,
    median,
    most,
    named,
    quantile,
    ran,
    table,
)
from study.corpus_survey.trees import Node, head, is_list, nodes

ROWS: tuple[tuple[str, ...], ...] = (
    ("RULE",), ("NOT",), ("INIT",), ("DET",), ("OR",), ("ALT",), ("ALTS",),
    ("OUTPUT", "INPUT"), ("ALL",), ("IF",), ("DET_OR_RULE", "RULE_OR_DET"), ("ONE",),
    ("CHOOSE",), ("DEMO_RULE", "DEMONSTRATED"), ("APPROXIMATED",), ("RIGID_DET",))
"""The keywords of the Forms table, a pair of keywords to a row."""

DECLARATIONS = frozenset({*(k.value for k in CLAUSES), "INIT", "DEMONSTRATED", "CHOOSE"})
TODO = re.compile(r";;\s*TODO ([\w-]+):")
DEMONSTRATION = "DemonstrationConsistency"
VERDICTS = frozenset({"concept", "any", "other"})
"""The verdicts of a witness that name no alt."""


@cache
def heads() -> tuple[Counter[str], dict[str, set[str]]]:
    """The count of list nodes of each head, and the files that hold one."""
    c = corpus()
    count: Counter[str] = Counter()
    files: dict[str, set[str]] = defaultdict(set)
    for s in c.stems:
        for n in c.nodes(s):
            h = head(n)
            if h is not None:
                count[h] += 1
                files[h].add(s)
    return count, files


def forms() -> str:
    c = corpus()
    count, files = heads()

    def cell(ks: tuple[str, ...], f) -> str:
        return " / ".join(str(f(k)) for k in ks)

    rows = sorted(ROWS, key=lambda ks: -count[ks[0]])
    shapes: Counter[tuple[bool, str]] = Counter()
    decl: dict[str, int] = {}
    headed: dict[str, int] = {}
    todo: Counter[str] = Counter()
    for s in c.stems:
        decl[s] = headed[s] = 0
        for n in c.nodes(s):
            h = head(n)
            if h is None:
                continue
            headed[s] += 1
            decl[s] += h in DECLARATIONS
            if h in ("DET", "DET_OR_RULE", "RULE", "RULE_OR_DET"):
                for m in n[2:]:
                    if head(m) == "ONE":
                        assert isinstance(m, list)
                        shapes[(len(m) == 1, h)] += 1
        todo.update(TODO.findall(c.text[s]))
    shape = ", ".join(f"{n} {'bare `(ONE)`' if bare else 'with columns'} in a {h}"
                      for (bare, h), n in sorted(shapes.items(), key=lambda kv: -kv[1]))
    opened = sum(n for (bare, h), n in shapes.items() if bare and h in DETERMINED)
    d_most, h_most = most(decl), most(headed)
    return body(
        mctx("Count of list nodes with the head, and the number of files with at least one."),
        table(("form", "count", "files"),
              ((cell(ks, str), cell(ks, lambda k: count[k]), cell(ks, lambda k: len(files[k]))) for ks in rows)),
        items([
            mctx("`ONE` by shape: {shape}. The open parameters, a bare `(ONE)` in a DET or a DET_OR_RULE: {opened}.")
            .format(shape=shape, opened=opened),
            mctx("Declaration forms per file: median {m}, p90 {p}, max {x} ({s}). All headed nodes per file: median {hm}, p90 {hp}, max {hx} ({hs}).")
            .format(m=median(list(decl.values())), p=quantile(list(decl.values()), 90), x=d_most[0], s=d_most[1],
                    hm=median(list(headed.values())), hp=quantile(list(headed.values()), 90), hx=h_most[0], hs=h_most[1]),
            mctx("TODO markers: {n} in total; {kinds}.").format(n=sum(todo.values()), kinds=named(todo.most_common())),
        ]),
        ran(c.files()))


@cache
def instances() -> list[tuple[str, str, int]]:
    """(stem, component, key width) of each `INIT` form, a `DEMONSTRATED`
    form as `DemonstrationConsistency`."""
    c = corpus()
    found: list[tuple[str, str, int]] = []
    for s in c.stems:
        for n in c.nodes(s):
            h = head(n)
            if h in ("INIT", "DEMONSTRATED"):
                comp = str(n[2]) if h == "INIT" else DEMONSTRATION
                key = next((x for x in n[2:] if head(x) == "key"), None)
                width = len(key_labels(key[1])) if isinstance(key, list) and len(key) > 1 else 0
                found.append((s, comp, width))
    return found


def instances_section() -> str:
    c = corpus()
    found = instances()
    per: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for s, comp, w in found:
        per[comp].append((s, w))

    def widest(xs: list[tuple[str, int]]) -> str:
        w = max(x for _, x in xs)
        at = sorted({s for s, x in xs if x == w})
        return f"{w} ({at[0]})" if len(at) == 1 else f"{w} ({len(at)} files)"

    rows = [(comp, len(xs), " ".join(f"{k}:{v}" for k, v in sorted(Counter(w for _, w in xs).items())), widest(xs))
            for comp, xs in sorted(per.items(), key=lambda kv: (-len(kv[1]), kv[0]))]
    count, stem = most(Counter(s for s, _, _ in found))
    keyless = sorted(comp for comp, xs in per.items() if all(w == 0 for _, w in xs))
    choose: Counter[int] = Counter()
    for s in c.stems:
        for n in c.nodes(s):
            if head(n) == "CHOOSE":
                for x in n[2:]:
                    if head(x) == "for":
                        assert isinstance(x, list)
                        choose[len(key_labels(x[1]))] += 1
    return body(
        mctx("`INIT` forms per component; a `DEMONSTRATED` form counts as DemonstrationConsistency. The key width is the number of `^` labels in the key clause. Most instances in one file: {count} ({stem}).")
        .format(count=count, stem=stem),
        table(("component", "instances", "key widths {width: n}", "max width (stem)"), rows),
        items([
            mctx("The components no instance of which takes a key clause: {comps}.").format(comps=", ".join(keyless)),
            mctx("The `CHOOSE` `for` key widths {{width: n}}: {d}.").format(d=dist(choose)),
        ]),
        ran(c.files()))


def grid_rows(row: Node) -> int:
    """The rows a `param` row stands for: a `grid` value stands for one row
    per cell that is not `_`."""
    grids = [n for n in nodes(row) if head(n) == "grid"]
    if not grids:
        return 1
    return sum(1 for g in grids for line in g[1:] if isinstance(line, list) for cell in line if cell != "_")


def arcdata_section() -> str:
    c = corpus()
    params: dict[str, int] = {}
    largest: tuple[int, str, str] = (0, "", "")
    witnessed: dict[str, int] = {}
    backrefs = 0
    plaus: Counter[str] = Counter()
    verdict: Counter[str] = Counter()
    tops: Counter[str] = Counter()
    for s in c.stems:
        data = c.arcdata(s)
        params[s] = 0
        witnessed[s] = 0
        for f in data:
            h = head(f)
            if h is None:
                continue
            assert isinstance(f, list)
            tops[h] += 1
            if h == "param":
                params[s] += 1
                rows = sum(grid_rows(r) for r in f[3:] if is_list(r))
                if rows > largest[0]:
                    largest = (rows, s, str(f[1]))
            for n in nodes(f):
                if head(n) != "witness":
                    continue
                if len(n) <= 4:
                    backrefs += 1
                    continue
                witnessed[s] += 1
                plaus[str(n[2])] += 1
                v = str(n[3])
                verdict[v if v in VERDICTS else "an alt"] += 1
    p_most, w_most = most(params), most(witnessed)
    return body(
        table(("measure", "value"), [
            ("params, total / max per file", f"{sum(params.values())} / {p_most[0]} ({p_most[1]})"),
            ("largest param", f"{largest[0]} rows ({largest[1]} `{largest[2]}`)"),
            ("witnesses with a body", f"{sum(witnessed.values())}; max {w_most[0]} per file ({w_most[1]}); "
                                      f"{sum(1 for v in witnessed.values() if v)} files have one"),
            ("bodiless back-references", backrefs),
            ("plausibility", named(plaus.most_common())),
            ("verdict", named(verdict.most_common())),
            ("top-level heads", named(tops.most_common())),
        ]),
        mctx("A `grid` value of a param counts one row per cell that is not `_`."),
        ran(f"the {len(c.stems)} `.arcdata` files of `programs/arclog/`"))


def starred(items_: list[Node]) -> frozenset[str]:
    """A derived relation's columns: the top-level `*` labels of its body,
    with what its `OR` and `IF` forms export."""
    cols: set[str] = set()
    for it in items_:
        if not isinstance(it, list) or not it:
            continue
        if item_kind(it) in (Item.ATOM, Item.OP, Item.ONE):
            cols |= {strip(t) for t in item_labels(it) if t.startswith("*")}
        else:
            cols |= exported(it)
    return frozenset(cols)


def columns_section() -> str:
    c = corpus()
    widest: tuple[int, str, str] = (0, "", "")
    arity: Counter[int] = Counter()
    reads = projecting = lib_atoms = short = outputs = 0
    lib_widest: tuple[int, str] = (0, "")
    for s in c.stems:
        bs = bodies_of(c, s)
        derived: dict[str, set[str]] = defaultdict(set)
        for b in bs:
            if b.kind in CLAUSES and b.items:
                derived[b.name] |= starred(b.items)
        instances_ = {b.name for b in bs if b.form in ("INIT", "DEMONSTRATED")}
        for rel, cols in sorted(derived.items()):
            arity[min(len(cols), 10)] += 1
            if len(cols) > widest[0]:
                widest = (len(cols), s, rel)
        for b in bs:
            for a in deep_atoms(b.items):
                rel = str(a[0])
                sites = {p.split(".")[0] for x in a[1:] for p, _ in site_pairs(x)} - {"E"}
                if rel in derived:
                    reads += 1
                    projecting += sites < derived[rel]
                elif rel in LIB.top:
                    lib_atoms += 1
                    width = len(LIB.top[rel])
                    short += len(sites) < width
                    if width > lib_widest[0]:
                        lib_widest = (width, rel)
                elif rel.startswith("&") and rel.split(".")[0] in instances_ and "." in rel:
                    outputs += 1
    labels = [str(k) if k < 10 else "10+" for k in sorted(arity)]
    return body(
        mctx("A derived relation is one a clause with a body derives, and its columns are its body's top-level `*` labels plus what its `OR` and `IF` forms export, over every such clause. A read projects when the columns its sites select, `E` aside, are a strict subset of the relation's."),
        table(("measure", "value"), [
            ("widest derived relation", f"{widest[0]} columns ({widest[1]} `{widest[2]}`)"),
            ("widest lib relation read", f"{lib_widest[0]} (`{lib_widest[1]}`)"),
            ("arity distribution", ", ".join(f"{label}:{arity[k]}" for label, k in zip(labels, sorted(arity), strict=True))),
            ("derived-relation reads that project", f"{projecting} of {reads}"),
            ("lib atoms with fewer sites than the lib arity", f"{short} of {lib_atoms}"),
            ("instance-output atoms", outputs),
        ]),
        ran(c.files() + ", with the lib's columns from `src/arclog_convert/lib-signature.dl`"))


def rare_section() -> str:
    c = corpus()
    count, _ = heads()
    keywords = sorted((k for ks in ROWS for k in ks), key=lambda k: count[k])[:4]
    comps = Counter(comp for _, comp, _ in instances())
    proposers: Counter[str] = Counter()
    lib: Counter[str] = Counter()
    types: Counter[str] = Counter()
    ops: Counter[str] = Counter()
    for s in c.stems:
        for n in c.nodes(s):
            h = head(n)
            if h in DETERMINED:
                proposers.update(str(x) for x in n[2:] if isinstance(x, str) and x in PROPOSER_COLS)
            elif h in OPS:
                ops[h] += 1
            elif h is not None and h in LIB.top:
                lib[h] += 1
        for f in c.arcdata(s):
            if head(f) == "param":
                assert isinstance(f, list)
                t = f[2]
                types[" ".join(str(x) for x in t) if isinstance(t, list) else str(t)] += 1
    lib_names = [n for n in LIB.top if n not in ("in", "ex_in", "ex_out")]

    def under5(cnt: Counter[str]) -> str:
        return named(sorted(((k, v) for k, v in cnt.items() if v < 5), key=lambda kv: (kv[1], kv[0])))

    rare_types = sorted((k for k, v in types.items() if v < 5), key=lambda k: (types[k], k))
    top_proposer = proposers.most_common(1)[0] if proposers else ("", 0)
    return body(items([
        mctx("Keywords: the thinnest are {kws}.").format(kws=named((k, count[k]) for k in keywords)),
        mctx("Components under 5 instances: {comps}.").format(comps=under5(comps)),
        mctx("Proposers: {used} of the {all} proposers are named by a DET or a DET_OR_RULE; {top} has the most uses, {n}. Under 5: {few}.")
        .format(used=len(proposers), all=len(PROPOSER_COLS), top=top_proposer[0], n=top_proposer[1], few=under5(proposers)),
        mctx("Lib relations: {used} of {all} read. Under 5: {few}.")
        .format(used=sum(1 for n in lib_names if lib[n]), all=len(lib_names), few=under5(lib)),
        mctx("Param column-type tuples: {n} kinds under 5 uses, such as {some}.")
        .format(n=len(rare_types), some=", ".join(f"`{t}`" for t in rare_types[-5:])),
        mctx("Constraint operators: {ops}.").format(ops=named((f"`{k}`", v) for k, v in ops.most_common())),
    ]), ran(c.files() + " and `.arcdata` files, with the proposers of `src/arclog_convert/lib.py`"))


FORMS = Section("Forms", 2, False, forms)
INSTANCES = Section("Instances", 2, False, instances_section)
ARCDATA = Section("Arcdata", 2, False, arcdata_section)
COLUMNS = Section("Columns", 2, False, columns_section)
RARE = Section("Rare constructs", 2, False, rare_section)
