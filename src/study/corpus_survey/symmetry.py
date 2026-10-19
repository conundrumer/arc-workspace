"""A body as a colored graph, its color refinement (1-dimensional
Weisfeiler–Leman) and the full search tree of individualization–refinement
over it, with no automorphism pruning."""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from study.corpus_survey.bodies import (
    Body,
    Item,
    exported,
    is_const,
    item_kind,
    item_labels,
    names,
    site_pairs,
    strip,
)
from study.corpus_survey.trees import Node, is_sym

NODE_CAP = 200_000
"""The search tree nodes past which a search stops, marked capped."""

type Adjacency = list[list[tuple[str, int]]]


class Graph:
    def __init__(self, kind: str):
        self.colors: list[str] = []
        self.adj: Adjacency = []
        self.atoms = 0
        self.vars = 0
        self.consts: dict[str, int] = {}
        self.depth = 0
        self.root = self.vertex(("root", kind))

    def vertex(self, color: tuple[object, ...]) -> int:
        self.colors.append(repr(color))
        self.adj.append([])
        return len(self.colors) - 1

    def edge(self, a: int, b: int, la: str, lb: str) -> None:
        self.adj[a].append((la, b))
        self.adj[b].append((lb, a))

    def var(self) -> int:
        self.vars += 1
        return self.vertex(("var",))

    def const(self, label: str) -> int:
        s = strip(label)
        if s not in self.consts:
            self.consts[s] = self.vertex(("const", s))
        return self.consts[s]

    def lookup(self, env: dict[str, int], label: str) -> int:
        if is_const(label):
            return self.const(label)
        n = strip(label)
        if n not in env:
            env[n] = self.var()
        return env[n]

    def add_item(self, it: list[Node], env: dict[str, int], parent: int, neg: bool = False) -> None:
        k = item_kind(it)
        if k == Item.OP:
            op, a, b = str(it[0]), str(it[1]), str(it[2])
            if op in (">", ">="):
                op, a, b = {">": "<", ">=": "<="}[op], b, a
            v = self.vertex(("op", op))
            la, lb = ("arg", "arg") if op in ("=", "!=") else ("lo", "hi")
            self.edge(v, self.lookup(env, a), la, la)
            self.edge(v, self.lookup(env, b), lb, lb)
        elif k == Item.ONE:
            v = self.vertex(("ONE",))
            for lab in it[1:]:
                if is_sym(lab):
                    self.edge(v, self.lookup(env, str(lab)), "one", "one")
        else:
            v = self.vertex(("atom", it[0], neg))
            for s in it[1:]:
                for path, lab in site_pairs(s):
                    self.edge(v, self.lookup(env, lab), path, path)
        self.atoms += 1
        self.edge(parent, v, "child", "parent")

    def child(self, parent: int, color: str) -> int:
        v = self.vertex((color,))
        self.edge(parent, v, "child", "parent")
        return v

    def process(self, items: list[Node], env: dict[str, int], parent: int, depth: int = 0) -> dict[str, int]:
        """Adds the items of a list under `parent`; the labels made at this
        level."""
        self.depth = max(self.depth, depth)
        its = [it for it in items if isinstance(it, list) and it and is_sym(it[0])]
        direct: set[str] = set()
        nested: list[list[Node]] = []
        made_here: set[str] = set()
        for it in its:
            if item_kind(it) in (Item.ATOM, Item.OP, Item.ONE):
                direct |= names(item_labels(it))
            else:
                nested.append(it)
                made_here |= exported(it)
        made = {n: self.var() for n in sorted(direct | made_here) if n not in env}
        env2 = {**env, **made}
        for it in its:
            if item_kind(it) in (Item.ATOM, Item.OP, Item.ONE):
                self.add_item(it, env2, parent)
        for it in nested:
            k = item_kind(it)
            if k == Item.NOT:
                inner = it[1:]
                if len(inner) == 1 and isinstance(inner[0], list) and item_kind(inner[0]) == Item.ATOM:
                    self.add_item(inner[0], dict(env2), parent, neg=True)
                else:
                    self.process(inner, dict(env2), self.child(parent, "NOT"), depth + 1)
            elif k == Item.OR:
                v = self.child(parent, "OR")
                for b in it[1:]:
                    if isinstance(b, list):
                        self.process(b, dict(env2), self.child(v, "branch"), depth + 1)
            elif k == Item.IF:
                v = self.child(parent, "IF")
                ps = [p for p in it[1:] if isinstance(p, list)]
                made_test = self.process(ps[0], dict(env2), self.child(v, "test"), depth + 1)
                self.process(ps[1], {**env2, **made_test}, self.child(v, "then"), depth + 1)
                if len(ps) > 2:
                    self.process(ps[2], dict(env2), self.child(v, "else"), depth + 1)
            elif k == Item.ALL:
                v = self.child(parent, "ALL")
                dom, rest = it[1], it[2]
                assert isinstance(dom, list) and isinstance(rest, list)
                made_dom = self.process(dom, dict(env2), self.child(v, "domain"), depth + 1)
                self.process(rest, {**env2, **made_dom}, self.child(v, "body"), depth + 1)
        return made


def build(b: Body) -> Graph:
    g = Graph(b.kind)
    env: dict[str, int] = {}
    for i, k in enumerate(b.keycols):
        v = g.var()
        env[k] = v
        g.edge(g.vertex(("keycol", i)), v, "key", "key")
    for col, lab in b.heads:
        g.edge(g.vertex(("head", col)), g.lookup(env, lab), "head", "head")
    g.process(b.items, env, g.root)
    return g


def ranked[T: (str, int)](values: list[T]) -> list[int]:
    """Each value's rank among the distinct values: the coloring that
    `values` give."""
    rank = {c: i for i, c in enumerate(sorted(set(values)))}
    return [rank[c] for c in values]


def refine(col: list[int], adj: Adjacency) -> list[int]:
    k = len(set(col))
    while True:
        sig = [(col[v], tuple(sorted((lab, col[u]) for lab, u in adj[v]))) for v in range(len(col))]
        u = sorted(set(sig))
        if len(u) == k:
            return col
        rank = {s: i for i, s in enumerate(u)}
        col = [rank[s] for s in sig]
        k = len(u)


def cells_of(col: list[int]) -> list[list[int]]:
    d: dict[int, list[int]] = defaultdict(list)
    for v, c in enumerate(col):
        d[c].append(v)
    return [d[c] for c in sorted(d)]


@dataclass
class Search:
    nodes: int = 0
    depth: int = 0
    leaves: int = 0
    aut: int = 0
    """The leaves whose certificate is the least: the order of the
    automorphism group."""
    capped: bool = False
    best: tuple[object, ...] | None = field(default=None, repr=False)


type Selector = Callable[[list[list[int]]], list[int]]

SELECTORS: dict[str, Selector] = {
    "first smallest": lambda nt: min(nt, key=len),
    "first largest": lambda nt: max(nt, key=len),
    "first": lambda nt: nt[0],
}
"""The cell selectors, each the non-singleton cell it individualizes."""


def search(g: Graph, base: list[int], select: Selector) -> Search:
    st = Search()
    edges = [(a, lab, b) for a in range(len(g.adj)) for lab, b in g.adj[a]]

    def cert(col: list[int]) -> tuple[object, ...]:
        vc: list[int] = [0] * len(col)
        for v, c in enumerate(col):
            vc[c] = base[v]
        return (tuple(vc), tuple(sorted((col[a], lab, col[b]) for a, lab, b in edges)))

    def rec(col: list[int], depth: int) -> None:
        if st.capped:
            return
        st.nodes += 1
        if st.nodes > NODE_CAP:
            st.capped = True
            return
        st.depth = max(st.depth, depth)
        nt = [c for c in cells_of(col) if len(c) > 1]
        if not nt:
            st.leaves += 1
            c = cert(col)
            if st.best is None or c < st.best:  # type: ignore[operator]
                st.best, st.aut = c, 1
            elif c == st.best:
                st.aut += 1
            return
        for v in select(nt):
            new = [2 * c + 1 for c in col]
            new[v] = 2 * col[v]
            rec(refine(ranked(new), g.adj), depth + 1)

    rec(refine(base, g.adj), 0)
    return st


@dataclass(frozen=True)
class Shape:
    """What refinement and the searches give of one body."""
    atoms: int
    vars: int
    vertices: int
    nest: int
    ties: int
    """The non-singleton cells refinement leaves."""
    largest_cell: int
    searches: dict[str, Search]


def shape(b: Body) -> Shape:
    g = build(b)
    base = ranked(g.colors)
    cells = cells_of(refine(base, g.adj))
    nt = [c for c in cells if len(c) > 1]
    searches = {name: search(g, base, sel) for name, sel in SELECTORS.items()} if nt else {}
    return Shape(g.atoms, g.vars, len(g.colors), g.depth, len(nt), max(map(len, cells)), searches)

