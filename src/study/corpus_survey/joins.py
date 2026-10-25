"""The join shape of a body's top-level positive atoms: its components, its
acyclicity, its self-joins; the algebra atoms it joins on a computed key;
and whether it is cyclic through its stored relations alone."""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from arclog_convert.lib import ALGEBRA_MODES
from arclog_convert.libmap.division import ORIENTATION
from arclog_convert.lint import LIB
from study.corpus_survey.bodies import (
    Body,
    Item,
    atom_labels,
    deep_labels,
    flat,
    is_const,
    item_kind,
    names,
    parts,
    site_pairs,
    stored,
    strip,
)
from study.corpus_survey.trees import Node, is_sym


def gyo_acyclic(edges: list[set[str]]) -> bool:
    """Whether the hypergraph of `edges` is acyclic, by GYO reduction."""
    hs = [set(e) for e in edges if e]
    changed = True
    while changed and len(hs) > 1:
        changed = False
        cnt = Counter(v for e in hs for v in e)
        for e in hs:
            lone = {v for v in e if cnt[v] == 1}
            if lone:
                e -= lone
                changed = True
        kept = []
        for i, e in enumerate(hs):
            if not e or any(j != i and e <= f and (e != f or j < i) for j, f in enumerate(hs)):
                changed = True
                continue
            kept.append(e)
        hs = kept
    return len(hs) <= 1


def top_items(items: list[Node]) -> list[list[Node]]:
    return [it for it in items if isinstance(it, list) and it and is_sym(it[0])]


@dataclass(frozen=True)
class Join:
    pos_atoms: int
    components: int
    acyclic: bool
    self_join: int
    """The most reads of one relation."""
    lib_atoms: int
    stored_cyclic: bool
    """Cyclic with the algebra atoms and the orientation tables removed."""


def join(items: list[Node]) -> Join:
    its = top_items(items)
    atoms = [it for it in its if item_kind(it) == Item.ATOM]
    eqs = [it for it in its if it[0] == "="]

    def edges(keep) -> list[set[str]]:
        es = [names(atom_labels(a)) for a in atoms if keep(str(a[0]))]
        es += [vs for e in eqs if len(vs := names(flat(e[1:]))) == 2]
        return [e for e in es if e]

    every = edges(lambda rel: True)
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for e in every:
        es = sorted(e)
        for y in es[1:]:
            parent[find(y)] = find(es[0])
    rels = Counter(str(a[0]) for a in atoms)
    acyclic = gyo_acyclic(every)
    return Join(len(atoms), len({find(v) for e in every for v in e}), acyclic,
                max(rels.values(), default=0),
                sum(1 for a in atoms if not stored(str(a[0]))),
                not acyclic and not gyo_acyclic(edges(stored)))


def out_columns(rel: str) -> list[str]:
    """The columns of an algebra relation that no mode holds, orientation
    columns aside: those an atom computes."""
    moded = set().union(*ALGEBRA_MODES[rel])
    return [n for n, t in LIB.top[rel] if n not in moded and t not in ORIENTATION]


class By(StrEnum):
    """What binds a label."""
    KEY = "key"
    STORED = "stored"
    TABLE = "table"
    FUNCTION = "function"
    CONSTRAINT = "constraint"


type Binder = dict[str, tuple[int, By, frozenset[str]]]
"""Each label bound so far: the position of the atom that binds it, what
binds it, and the stored labels it is computed from."""


def computed_keys(b: Body) -> list[str]:
    """The algebra relation of each atom of `b` that is checked against an
    output already bound while its input comes from a stored atom written
    after the binding of that output."""
    found: list[str] = []
    binder: Binder = {k: (0, By.KEY, frozenset()) for k in b.keycols}
    pos = [0]

    def scan(items: Sequence[Node], binder: Binder) -> None:
        for it in items:
            if not isinstance(it, list) or not it:
                continue
            k = item_kind(it)
            if k == Item.ATOM:
                pos[0] += 1
                rel = str(it[0])
                ls = names(atom_labels(it))
                if rel in ALGEBRA_MODES:
                    cols: dict[str, list[str]] = {}
                    for s in it[1:]:
                        for path, tok in site_pairs(s):
                            cols.setdefault(path.split(".")[0].lower(), []).append(tok)
                    outs = {strip(t) for c in out_columns(rel) for t in cols.get(c, []) if not is_const(t)}
                    ins = {strip(t) for m in ALGEBRA_MODES[rel] for c in m for t in cols.get(c, []) if not is_const(t)}
                    pre = [o for o in outs if o in binder]
                    if pre:
                        first = min(binder[o][0] for o in pre)
                        late = {r for i in ins if i in binder for r in binder[i][2]
                                if r in binder and binder[r][1] == By.STORED and binder[r][0] > first}
                        if late:
                            found.append(rel)
                    roots = frozenset(r for i in ins if i in binder for r in binder[i][2])
                    for lab in ls:
                        binder.setdefault(lab, (pos[0], By.FUNCTION, roots))
                else:
                    kind = By.STORED if stored(rel) else By.TABLE
                    for lab in ls:
                        binder.setdefault(lab, (pos[0], kind, frozenset([lab])))
            elif k == Item.OP:
                for lab in names(flat(it[1:])):
                    binder.setdefault(lab, (pos[0], By.CONSTRAINT, frozenset()))
            elif k == Item.OR:
                for p in parts(it):
                    scan(p, dict(binder))
                sets = [names(deep_labels(p)) for p in parts(it)]
                if sets:
                    for lab in set.intersection(*sets):
                        binder.setdefault(lab, (pos[0], By.STORED, frozenset([lab])))
            elif k in (Item.IF, Item.ALL, Item.NOT):
                for p in parts(it):
                    scan(p, dict(binder))

    scan(top_items(b.items), binder)
    return found
