"""The Recursion section: the cycles among the relations of each arclog
file of `gen/`, over every derivation merged, over the concept program,
and over each alt path."""

from collections import defaultdict
from dataclasses import dataclass

from controlled_markdown import mctx
from study.corpus_survey.bodies import CLAUSES, Body, Item, item_kind, parts
from study.corpus_survey.corpus import bodies_of, corpus
from study.corpus_survey.section import Section, body, ran, table
from study.corpus_survey.trees import Node

LISTED = 8
"""The most cycles of one kind the section lists, the largest first."""


@dataclass(frozen=True)
class Read:
    target: str
    negated: bool


def relation(name: str) -> str:
    """The relation a name stands for: `&x.out` is a part of `&x`."""
    return name.split(".")[0]


def reads(items: list[Node], negated: bool = False) -> list[Read]:
    """The `&` reads of `items`: one under `NOT`, under `ALL` or in an
    `IF` test is negated."""
    found: list[Read] = []
    for it in items:
        if not isinstance(it, list) or not it:
            continue
        k = item_kind(it)
        if k == Item.ATOM:
            if str(it[0]).startswith("&"):
                found.append(Read(relation(str(it[0])), negated))
        elif k == Item.LIST:
            found += reads(it, negated)
        elif k in (Item.NOT, Item.ALL):
            for p in parts(it):
                found += reads(p, True)
        elif k == Item.IF:
            for i, p in enumerate(parts(it)):
                found += reads(p, negated or i == 0)
        elif k == Item.OR:
            for p in parts(it):
                found += reads(p, negated)
    return found


def alt_path(b: Body) -> tuple[str, ...]:
    return tuple(f.name or "" for f in b.stack if f.head == "ALT")


type Graph = dict[str, set[Read]]


def graph(decls: list[tuple[str, list[Read]]]) -> Graph:
    g: Graph = defaultdict(set)
    for rel, rs in decls:
        g[rel] |= set(rs)
    return g


def cycles(g: Graph) -> list[list[str]]:
    """The strongly connected components of `g` that hold a cycle, each
    sorted, by Tarjan's algorithm."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on: set[str] = set()
    found: list[list[str]] = []

    def visit(v: str) -> None:
        work = [(v, iter(sorted({r.target for r in g.get(v, ())})))]
        index[v] = low[v] = len(index)
        stack.append(v)
        on.add(v)
        while work:
            u, it = work[-1]
            w = next(it, None)
            if w is None:
                work.pop()
                if work:
                    low[work[-1][0]] = min(low[work[-1][0]], low[u])
                if low[u] == index[u]:
                    comp = []
                    while True:
                        x = stack.pop()
                        on.discard(x)
                        comp.append(x)
                        if x == u:
                            break
                    if len(comp) > 1 or any(r.target == u for r in g.get(u, ())):
                        found.append(sorted(comp))
            elif w not in index:
                index[w] = low[w] = len(index)
                stack.append(w)
                on.add(w)
                work.append((w, iter(sorted({r.target for r in g.get(w, ())}))))
            elif w in on:
                low[u] = min(low[u], index[w])

    for v in sorted(g):
        if v not in index:
            visit(v)
    return found


def negated_edges(g: Graph, comp: list[str]) -> int:
    members = set(comp)
    return sum(1 for v in comp for r in g.get(v, ()) if r.negated and r.target in members)


def recursion() -> str:
    c = corpus()
    self_reads: list[tuple[str, str, bool]] = []
    clause_self = 0
    concept_cycles: list[tuple[str, list[str], int]] = []
    alt_cycles: list[tuple[str, tuple[str, ...], list[str], int]] = []
    for s in c.stems:
        decls: list[tuple[str, tuple[str, ...], list[Read]]] = []
        for b in bodies_of(c, s):
            rel = relation(b.name)
            rs = reads(b.items)
            decls.append((rel, alt_path(b), rs))
            if b.kind in CLAUSES and any(r.target == rel for r in rs):
                clause_self += 1
        merged = graph([(r, rs) for r, _, rs in decls])
        for rel in sorted(merged):
            loops = [r for r in merged[rel] if r.target == rel]
            if loops:
                self_reads.append((s, rel, any(r.negated for r in loops)))
        concept = graph([(r, rs) for r, p, rs in decls if not p])
        seen = {tuple(comp) for comp in cycles(concept)}
        concept_cycles += [(s, comp, negated_edges(concept, comp)) for comp in cycles(concept)]
        paths = sorted({p[:i] for _, p, _ in decls for i in range(1, len(p) + 1)})
        for path in paths:
            chosen: dict[str, tuple[int, list[list[Read]]]] = {}
            for rel, p, rs in decls:
                if path[:len(p)] != p:
                    continue
                depth = len(p)
                if rel not in chosen or chosen[rel][0] < depth:
                    chosen[rel] = (depth, [rs])
                elif chosen[rel][0] == depth:
                    chosen[rel][1].append(rs)
            g = graph([(rel, [r for rs in v[1] for r in rs]) for rel, v in chosen.items()])
            for comp in cycles(g):
                if tuple(comp) not in seen:
                    seen.add(tuple(comp))
                    alt_cycles.append((s, path, comp, negated_edges(g, comp)))
    concept_cycles.sort(key=lambda x: (-len(x[1]), x[0]))
    alt_cycles.sort(key=lambda x: (-len(x[2]), x[0]))
    rows: list[tuple[object, object]] = [
        ("relations that read themselves",
         f"{len(self_reads)}" + "".join(f"; {s} `{rel}`{', through a negation' if neg else ''}" for s, rel, neg in self_reads[:LISTED])),
        ("a clause that reads its own relation", clause_self),
        ("cycles in the concept program's graph", len(concept_cycles)),
    ]
    rows += [(f"{s}", f"{len(comp)} relations, {neg} negated edges: " + ", ".join(f"`{m}`" for m in comp))
             for s, comp, neg in concept_cycles[:LISTED]]
    rows.append(("cycles on an alt path and in no concept graph",
                 f"{len(alt_cycles)}; {sum(1 for x in alt_cycles if x[3])} through a negation"))
    rows += [(f"{s}, alt {' '.join(f'`{a}`' for a in path)}", f"{len(comp)} relations, {neg} negated edges")
             for s, path, comp, neg in alt_cycles[:LISTED]]
    return body(
        mctx("Each declaration's `&` reads, with `&x.out` counted as a read of `&x`; a read under `NOT`, under `ALL` or in an `IF` test is negated. Cycles are the strongly connected components over three graphs: every derivation merged, the concept program alone, and each alt path with its derivations in place of the concept program's. The cycles of one kind are listed up to {n}, the largest first.")
        .format(n=LISTED),
        table(("measure", "result"), rows),
        ran(c.files()))


RECURSION = Section("Recursion", 2, False, recursion)
