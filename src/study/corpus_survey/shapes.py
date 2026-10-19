"""The sections on the bodies of `gen/`: Bodies, Body symmetry and Join
shapes."""

from collections import Counter
from functools import cache

from controlled_markdown import mctx
from study.corpus_survey.bodies import CLAUSES, Body, Kind
from study.corpus_survey.corpus import corpus
from study.corpus_survey.joins import Join, computed_keys, join
from study.corpus_survey.section import Section, body, dist, items, named, quantile, ran, table
from study.corpus_survey.symmetry import SELECTORS, Shape, shape


@cache
def shaped() -> list[tuple[Body, Shape]]:
    return [(b, shape(b)) for b in corpus().bodies()]


def where(b: Body) -> str:
    return f"{b.stem} `{b.name}`"


def kinds(bs: list[Body]) -> str:
    return named((f"`{k}`" if k in CLAUSES else k, n) for k, n in Counter(b.kind.value for b in bs).most_common())


def bodies_section() -> str:
    c = corpus()
    got = shaped()

    def row(label: str, f) -> tuple[object, ...]:
        xs = [f(s) for _, s in got]
        top = max(f(s) for _, s in got)
        at = [b for b, s in got if f(s) == top]
        return (label, quantile(xs, 50), quantile(xs, 90), quantile(xs, 99),
                f"{top} ({', '.join(where(b) for b in at[:2])}{'' if len(at) <= 2 else f', {len(at) - 2} more'})")

    return body(
        mctx("A body is the body of a `RULE`, `DET`, `DET_OR_RULE`, `RULE_OR_DET` or `RIGID_DET` form, an instance's key clause or input, or a `CHOOSE` form's `from` or `never` list: {n} bodies. An atom counts each atom, negated atom, constraint and `ONE` mark at every depth. A label counts each variable once, a label local to an `OR` branch, an `IF` test or an `ALL` once per form it is local to.")
        .format(n=len(got)),
        table(("measure", "p50", "p90", "p99", "max (stem, relation)"), [
            row("atoms", lambda s: s.atoms),
            row("labels", lambda s: s.vars),
            row("vertices of the atom–variable graph", lambda s: s.vertices),
            row("nesting depth of `OR`, `IF`, `ALL`, `NOT`", lambda s: s.nest),
        ]),
        ran(c.files()))


def symmetry_section() -> str:
    c = corpus()
    got = shaped()
    tied = [(b, s) for b, s in got if s.ties]
    first = "first smallest"

    def nodes_row(name: str) -> tuple[str, str]:
        ns = [s.searches[name].nodes for _, s in tied]
        top = max(tied, key=lambda bs: bs[1].searches[name].nodes)
        return (f"search tree nodes, {name}", f"p50 {quantile(ns, 50)}, p99 {quantile(ns, 99)}, max {max(ns)} ({where(top[0])})")

    differ = [b for b, s in tied if any(x.leaves != x.aut for x in s.searches.values())]
    capped = sum(1 for _, s in tied for x in s.searches.values() if x.capped)
    depths = {name: Counter(s.searches[name].depth for _, s in tied) for name in SELECTORS}
    order8 = sorted({where(b) for b, s in tied if s.searches[first].aut == max(x.searches[first].aut for _, x in tied)})
    rows: list[tuple[object, object]] = [
        ("bodies that refinement leaves discrete", f"{len(got) - len(tied)} of {len(got)}"),
        ("bodies with ties", f"{len(tied)}: {kinds([b for b, _ in tied])}"),
        ("non-singleton cells per tied body", dist(Counter(s.ties for _, s in tied))),
        ("largest cell after refinement", ", ".join(f"{k} in {v} bodies" for k, v in sorted(Counter(s.largest_cell for _, s in tied).items()))),
        ("automorphism group order", dist(Counter(s.searches[first].aut for _, s in tied))),
        ("bodies whose search leaves differ from the automorphism count", len(differ)),
        *(nodes_row(name) for name in SELECTORS),
        ("individualization depth", "; ".join(f"{name}: " + ", ".join(f"{d} in {n} bodies" for d, n in sorted(depths[name].items()))
                                              for name in SELECTORS)),
        ("searches stopped at the node cap", capped),
    ]
    return body(
        mctx("Each body is a graph: a vertex per atom, colored by its relation and its negation; a vertex per label; a vertex per constant; a vertex per `OR`, branch, `IF` part, `ALL` part and `NOT` group; an edge from an atom to each label it reads, labeled by the column path (`key.C` for a field); `>` and `>=` turned into `<` and `<=`, and `=`, `!=` with unordered sides; a head site, a key column by its index. The relation is colored by its name. Color refinement is 1-dimensional Weisfeiler–Leman over the labeled edges. Each body that refinement leaves with ties is searched in full by individualization–refinement, with no automorphism pruning, under three cell selectors: the first smallest non-singleton cell, the first largest, the first."),
        table(("measure", "value"), rows),
        items([mctx("The bodies of the largest automorphism group: {bodies}.").format(bodies=", ".join(order8))]) if order8 else "",
        ran(c.files()))


@cache
def joined() -> list[tuple[Body, Join]]:
    return [(b, join(b.items)) for b in corpus().bodies() if b.kind in CLAUSES or b.kind == Kind.INPUT]


def join_section() -> str:
    c = corpus()
    got = joined()
    pos = [j.pos_atoms for _, j in got]
    most = max(got, key=lambda bj: bj[1].pos_atoms)
    cyclic = [(b, j) for b, j in got if not j.acyclic]
    cyc_top = sorted(cyclic, key=lambda bj: -bj[1].pos_atoms)[:2]
    selfj = [(b, j) for b, j in got if j.self_join >= 2]
    comps = Counter(j.components for _, j in got)
    widest = max(got, key=lambda bj: bj[1].components)
    lib = [j.lib_atoms for _, j in got]
    keyed: Counter[str] = Counter()
    keyed_bodies: list[Body] = []
    for b, _ in got:
        found = computed_keys(b)
        if found:
            keyed_bodies.append(b)
            keyed.update(set(found))
    stored_cyc = [b for b, j in got if j.stored_cyclic]
    return body(
        mctx("The top-level positive atoms of each clause body and instance input, {n} bodies, with `(= X Y)` as an edge. Acyclic is GYO reducibility of the hypergraph of their labels. A self-join is a relation read by two or more of those atoms. An atom joined on a computed key is an algebra atom checked against an output already bound while its input comes from a stored atom written later. A body cyclic through stored relations is cyclic with its algebra atoms and orientation tables removed.")
        .format(n=len(got)),
        table(("measure", "value"), [
            ("top-level positive atoms", f"p50 {quantile(pos, 50)}, p90 {quantile(pos, 90)}, p99 {quantile(pos, 99)}, max {most[1].pos_atoms} ({where(most[0])})"),
            ("connected components", dist(comps) + f" ({where(widest[0])})"),
            ("cyclic bodies", f"{len(cyclic)}: {kinds([b for b, _ in cyclic])}; largest "
                              + ", ".join(f"{where(b)} {j.pos_atoms} atoms" for b, j in cyc_top)),
            ("bodies with a self-join", f"{len(selfj)}; {sum(1 for _, j in selfj if not j.acyclic)} of them cyclic; "
                                        f"most reads of one relation {max(j.self_join for _, j in got)}"),
            ("lib atoms per body", f"p90 {quantile(lib, 90)}, p99 {quantile(lib, 99)}, max {max(lib)}"),
            ("algebra outputs joined on a computed key", f"{len(keyed_bodies)} bodies: {kinds(keyed_bodies)}; by relation "
                                                         + named(keyed.most_common())),
            ("bodies cyclic through stored relations", len(stored_cyc)),
        ]),
        ran(c.files() + ", with the lib's columns from `src/arclog_convert/lib-signature.dl`"))


BODIES = Section("Bodies", 2, False, bodies_section)
SYMMETRY = Section("Body symmetry", 2, False, symmetry_section)
JOIN_SHAPES = Section("Join shapes", 2, False, join_section)
