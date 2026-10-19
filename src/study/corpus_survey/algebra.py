"""The algebra of the lib as the slow body sections simulate it in sqlite:
the orientation tables, the box functors as sqlite functions, and for each
algebra relation the columns it enumerates, its modes, each the template of
the outputs it computes from the inputs it needs, or the template of the
check it applies.

A box is the JSON text `[t, b, l, r]`; an orientation is its code in the
lib, read from the `#define` lines of `programs/lib.dl` by the Souffle
parser."""

import json
from functools import cache
from typing import Any

from engine import checkout
from engine.program import DefinedName, NumberTerm
from souffle.parser import ParseFailure, parse


@cache
def lib():
    got = parse((checkout.programs() / "lib.dl").read_text(), checkout.programs())
    if isinstance(got, ParseFailure):
        raise ValueError(f"programs/lib.dl does not parse: {got}")
    return got


@cache
def codes() -> dict[str, int]:
    """The value of each number `#define` of the lib."""
    found: dict[str, int] = {}
    for d in lib().defines:
        v = d.value
        if isinstance(v, NumberTerm):
            found[d.name] = int(v.value)
    return found


def facts(relation: str) -> list[tuple[int, ...]]:
    """The rows of the facts of a top-level lib relation, each argument a
    defined name or a number."""
    rows: list[tuple[int, ...]] = []
    for u in lib().units:
        if u.body is None and not u.scope.components and u.head.relation.name == relation:
            args = [codes()[a.name] if isinstance(a, DefinedName) else a.value if isinstance(a, NumberTerm) else None
                    for a in u.head.args]
            if all(isinstance(a, int) for a in args):
                rows.append(tuple(int(a) for a in args if a is not None))
    return rows


def _c(name: str) -> int:
    return codes()[name]


T, B_, L, R = (_c(n) for n in ("DIR_T", "DIR_B", "DIR_L", "DIR_R"))
V, H = _c("AXIS_V"), _c("AXIS_H")
TL, TR, BL, BR = (_c(n) for n in ("DIAG_TL", "DIAG_TR", "DIAG_BL", "DIAG_BR"))
DG, AD = _c("DAXIS_DG"), _c("DAXIS_AD")
ID, CW, HT, CC, LR, TB, D4DG, D4AD = (_c(n) for n in ("D4_ID", "D4_CW", "D4_HT", "D4_CC", "D4_LR", "D4_TB", "D4_DG", "D4_AD"))
SCW, SCC = _c("SENSE_CW"), _c("SENSE_CC")
D4 = (ID, CW, HT, CC, LR, TB, D4DG, D4AD)
SYMS = tuple(sorted(v for k, v in codes().items() if k.startswith("SYM_")))
SYM_C4, SYM_D4 = _c("SYM_C4"), _c("SYM_D4")
DIRS, DIAGS = (T, B_, L, R), (TL, TR, BL, BR)


@cache
def bx(s: str) -> tuple[int, ...]:
    return tuple(json.loads(s))


def fb(m) -> str:
    return "[%d,%d,%d,%d]" % tuple(m)


def near(m, a):
    return m[0] if a == V else m[2]


def far(m, a):
    return m[1] if a == V else m[3]


def axis_only(a, n, f):
    return (n, f, 0, 0) if a == V else (0, 0, n, f)


def has_edge(d, e):
    return {TL: e in (T, L), TR: e in (T, R), BL: e in (B_, L), BR: e in (B_, R)}.get(d, d == e)


def edge_inset_t(d, k):
    return tuple(k if has_edge(d, e) else 0 for e in DIRS)


def box_compose(a, b):
    if a is None or b is None:
        return None
    x, y = bx(a), bx(b)
    return fb([x[i] + y[i] for i in range(4)])


def box_relative(base, x):
    if base is None or x is None:
        return None
    b, p = bx(base), bx(x)
    return fb([p[i] - b[i] for i in range(4)])


def dist(p, d):
    m = bx(p)
    return {T: m[0], B_: m[1], L: m[2], R: m[3]}.get(d, 0)


def cdist(p, d):
    m = bx(p)
    return {TL: m[0] + m[2], TR: m[0] + m[3], BL: m[1] + m[2], BR: m[1] + m[3]}.get(d, 0)


def axis_dim(p, a):
    m = bx(p)
    return near(m, a) + far(m, a) + 1


def along(p, a):
    m = bx(p)
    return fb(axis_only(a, near(m, a), far(m, a)))


def across(p, a):
    m = bx(p)
    o = H if a == V else V
    return fb(axis_only(o, near(m, o), far(m, o)))


def centered(p):
    m = bx(p)
    return int(m[0] == m[1] and m[2] == m[3])


def anchor(d, p1, p2):
    a, b = bx(p1), bx(p2)
    return int({TL: a[0] == b[0] and a[2] == b[2], TR: a[0] == b[0] and a[3] == b[3],
                BL: a[1] == b[1] and a[2] == b[2], BR: a[1] == b[1] and a[3] == b[3]}.get(d, False))


def edge_inset(d, k):
    return fb(edge_inset_t(d, k))


def axis_inset(d, k1, k2):
    o = {T: B_, B_: T, L: R, R: L}.get(d, L)
    a, b = edge_inset_t(d, k1), edge_inset_t(o, k2)
    return fb([a[i] + b[i] for i in range(4)])


def jump_offset(d, k):
    e = edge_inset_t(d, k)
    return fb([e[1] - e[0], e[0] - e[1], e[3] - e[2], e[2] - e[3]])


def apply(d, p):
    if p is None:
        return None
    m = bx(p)
    return fb({ID: m, CW: (m[2], m[3], m[1], m[0]), HT: (m[1], m[0], m[3], m[2]), CC: (m[3], m[2], m[0], m[1]),
               LR: (m[0], m[1], m[3], m[2]), TB: (m[1], m[0], m[2], m[3]), D4DG: (m[2], m[3], m[0], m[1]),
               D4AD: (m[3], m[2], m[1], m[0])}.get(d, m))


def d4inv(d: int) -> int:
    return {CW: CC, CC: CW}.get(d, d)


def inside(a, b, strict=0):
    x, y = bx(a), bx(b)
    return int(all((i > j) if strict else (i >= j) for i, j in zip(x, y, strict=True)))


def same_line(a, p, q):
    if a in (V, H):
        d = L if a == V else T
        return int(dist(p, d) == dist(q, d))
    ds = (TR, BL) if a == DG else (TL, BR)
    return int(any(cdist(p, d) == cdist(q, d) for d in ds))


def nearer(d, p, q):
    return int(dist(p, d) < dist(q, d)) if d in DIRS else int(cdist(p, d) < cdist(q, d))


def same_slab(d, p1, p2):
    a = V if d in (T, B_) else H
    return int(dist(p1, d) == dist(p2, d) and across(p1, a) == across(p2, a))


def boxext(b, p, a):
    m = bx(b)
    return axis_dim(p, a) - (near(m, a) + far(m, a))


def uniform(k):
    return fb([k, k, k, k])


GAP_LIMIT = 60
"""The gaps `gapk` tries."""


def gapk(d, p, q):
    for k in range(GAP_LIMIT):
        if box_compose(p, jump_offset(d, k + 1)) == q:
            return k
    return None


def opp(d):
    return {T: B_, B_: T, L: R, R: L}.get(d, d)


def perpax(a):
    return H if a == V else V if a == H else None


FUNCTIONS: dict[str, tuple[int, Any]] = {
    "box_compose": (2, box_compose), "box_relative": (2, box_relative), "dist": (2, dist), "cdist": (2, cdist),
    "axis_dim": (2, axis_dim), "along": (2, along), "across": (2, across), "centered": (1, centered),
    "anchor": (3, anchor), "edge_inset": (2, edge_inset), "axis_inset": (3, axis_inset), "joff": (2, jump_offset),
    "apply": (2, apply), "d4inv": (1, d4inv), "inside": (2, lambda a, b: inside(a, b, 0)),
    "interior": (2, lambda a, b: inside(a, b, 1)), "same_line": (3, same_line), "nearer": (3, nearer),
    "same_slab": (3, same_slab), "boxext": (3, boxext), "uniform": (1, uniform), "gapk": (3, gapk), "opp": (1, opp),
    "perpax": (1, perpax),
}
"""The sqlite functions the templates call, each with its arity."""


@cache
def tables() -> dict[str, list[tuple[int, ...]]]:
    """The rows of each orientation table, by its arclog name."""
    t: dict[str, list[tuple[int, ...]]] = {}
    t["dir_elem"] = [(d,) for d in DIRS]
    t["axis_elem"] = [(V,), (H,)]
    t["diag_dir_elem"] = [(d,) for d in DIAGS]
    t["diag_axis_elem"] = [(DG,), (AD,)]
    t["dir8_elem"] = [(d,) for d in DIRS + DIAGS]
    t["axis4_elem"] = [(V,), (H,), (DG,), (AD,)]
    t["d4_elem"] = [(d,) for d in D4]
    t["c4_elem"] = [(d,) for d in (ID, CW, HT, CC)]
    t["sense_elem"] = [(SCW,), (SCC,)]
    t["sym_elem"] = [(d,) for d in SYMS]
    ao = [(T, V), (B_, V), (L, H), (R, H)]
    dao = [(TL, DG), (BR, DG), (TR, AD), (BL, AD)]
    t["axis_of"], t["diag_axis_of"], t["axis4_of"] = ao, dao, ao + dao
    cd = [(TL, V, T), (TL, H, L), (TR, V, T), (TR, H, R), (BL, V, B_), (BL, H, L), (BR, V, B_), (BR, H, R)]
    t["corner_dir"] = cd
    t["diag_dirs"] = [(dg, a, d1, d2) for (dg, a, d1) in cd for (dg2, a2, d2) in cd if dg2 == dg and a2 != a]
    t["opposite"] = [(T, B_), (B_, T), (L, R), (R, L)]
    t["diag_opposite"] = [(TL, BR), (BR, TL), (TR, BL), (BL, TR)]
    t["dir8_opposite"] = t["opposite"] + t["diag_opposite"]
    t["perp"], t["diag_perp"] = [(V, H), (H, V)], [(DG, AD), (AD, DG)]
    t["perp_dir"] = [(d, d2) for (d, a) in ao for (d2, a2) in ao if a2 != a]
    t["axis_inversion"], t["reflection"] = [(V, TB), (H, LR)], [(DG, D4DG), (AD, D4AD)]
    cw = [(T, R), (R, B_), (B_, L), (L, T)]
    t["turn"] = [(SCW, a, b) for a, b in cw] + [(SCC, b, a) for a, b in cw]
    t["c4_turn"] = [(SCW, CW), (SCC, CC)]
    t["d4_inverse"] = [(d, d4inv(d)) for d in D4]
    t["d4_identity"] = [(ID,)]
    t["d4_compose"] = facts("d4_compose")
    t["sym_member"] = facts("sym_member") + [(SYM_C4, d) for d in (ID, CW, HT, CC)] + [(SYM_D4, d) for d in D4]
    for name, dl in (("apply_dir", DIRS), ("apply_diag_dir", DIAGS), ("apply_dir8", DIRS + DIAGS)):
        t[name] = [(D, d, d2) for D in D4 for d in dl for d2 in dl if jump_offset(d2, 1) == apply(D, jump_offset(d, 1))]
    return t


DOMAINS = {"dir": list(DIRS), "dir8": list(DIRS + DIAGS), "axis": [V, H], "axis4": [V, H, DG, AD],
           "diag": list(DIAGS), "d4": list(D4), "nums": list(range(GAP_LIMIT + 1))}
"""The values an enumerated column takes, by the name of its domain."""

SPEC: dict[str, dict[str, Any]] = {
    "compose": dict(modes=[({"c": "box_compose({a},{b})"}, ["a", "b"]), ({"b": "box_relative({a},{c})"}, ["a", "c"]),
                           ({"a": "box_relative({b},{c})"}, ["b", "c"])]),
    "relative": dict(modes=[({"x_rel": "box_relative({base},{x})"}, ["base", "x"]),
                            ({"x": "box_compose({base},{x_rel})"}, ["base", "x_rel"]),
                            ({"base": "box_relative({x_rel},{x})"}, ["x_rel", "x"])]),
    "inside": dict(check="inside({a},{b})"), "interior": dict(check="interior({a},{b})"),
    "margin": dict(enum={"d": "dir"}, modes=[({"k": "dist({b},{d})"}, ["b", "d"])]),
    "dist_pair": dict(enum={"d": "dir"}, modes=[({"k": "dist({p},{d})", "k2": "dist({p},opp({d}))"}, ["p", "d"])]),
    "corner_dist": dict(enum={"diag": "diag"}, modes=[({"k": "cdist({p},{diag})"}, ["p", "diag"])]),
    "split": dict(enum={"a": "axis"}, modes=[({"along": "along({p},{a})", "across": "across({p},{a})"}, ["p", "a"])]),
    "frame_extent": dict(enum={"a": "axis"}, modes=[({"n": "axis_dim({p},{a})"}, ["p", "a"])]),
    "axis_extents": dict(enum={"a": "axis"}, modes=[({"n1": "axis_dim({p},{a})", "n2": "axis_dim({p},perpax({a}))"}, ["p", "a"])]),
    "box_extent": dict(enum={"a": "axis"}, modes=[({"n": "boxext({b},{p},{a})"}, ["b", "p", "a"])]),
    "edge_inset": dict(enum={"d": "dir"}, modes=[({"b": "edge_inset({d},{k})"}, ["d", "k"])]),
    "corner_inset": dict(enum={"diag": "diag"}, modes=[({"b": "edge_inset({diag},{k})"}, ["diag", "k"])]),
    "axis_inset": dict(enum={"d": "dir"}, modes=[({"b": "axis_inset({d},{k1},{k2})"}, ["d", "k1", "k2"])]),
    "uniform_inset": dict(modes=[({"b": "uniform({k})"}, ["k"])]),
    "edge_outset": dict(enum={"d": "dir"}, modes=[({"b": "edge_inset({d},-({k}))"}, ["d", "k"])]),
    "corner_outset": dict(enum={"diag": "diag"}, modes=[({"b": "edge_inset({diag},-({k}))"}, ["diag", "k"])]),
    "axis_outset": dict(enum={"d": "dir"}, modes=[({"b": "axis_inset({d},-({k1}),-({k2}))"}, ["d", "k1", "k2"])]),
    "uniform_outset": dict(modes=[({"b": "uniform(-({k}))"}, ["k"])]),
    "jump_offset": dict(enum={"d": "dir8"}, modes=[({"v": "joff({d},{k})"}, ["d", "k"])]),
    "step_offset": dict(enum={"d": "dir8"}, modes=[({"v": "joff({d},1)"}, ["d"])]),
    "neighbor": dict(enum={"d": "dir8"}, modes=[({"q": "box_compose({p},joff({d},1))"}, ["p", "d"])]),
    "jump": dict(enum={"d": "dir8"}, modes=[({"q": "box_compose({p},joff({d},{k}))"}, ["p", "d", "k"])]),
    "apply": dict(enum={"d": "d4"}, modes=[({"p_out": "apply({d},{p})"}, ["d", "p"]),
                                           ({"p": "apply(d4inv({d}),{p_out})"}, ["d", "p_out"])]),
    "gap": dict(enum={"d": "dir8"}, modes=[({"q": "box_compose({p},joff({d},{k}+1))"}, ["p", "d", "k"]),
                                           ({"k": "gapk({d},{p},{q})"}, ["p", "d", "q"])]),
    "same_dist": dict(enum={"d": "dir"}, check="dist({p1},{d})=dist({p2},{d})"),
    "same_line": dict(enum={"a": "axis4"}, check="same_line({a},{p},{q})"),
    "nearer": dict(enum={"d": "dir8"}, check="nearer({d},{p},{q})"),
    "same_corner": dict(enum={"diag": "diag"}, check="anchor({diag},{p1},{p2})"),
    "same_slab": dict(enum={"d": "dir"}, check="same_slab({d},{p1},{p2})"),
    "centered": dict(check="centered({p})"),
    "sub_extent": dict(enum={"a": "axis", "k": "nums"}, check="({k}>=1 AND {k}<axis_dim({p},{a}))"),
    "diag_dist": dict(enum={"diag": "diag", "a": "axis"},
                      modes=[({"k1": "dist({p},(SELECT c2 FROM o_diag_dirs WHERE c0={diag} AND c1={a}))",
                               "k2": "dist({p},(SELECT c3 FROM o_diag_dirs WHERE c0={diag} AND c1={a}))"},
                              ["p", "diag", "a"])]),
}
"""Each algebra relation the simulation applies; `divide` and
`frame_offset` it does not."""
