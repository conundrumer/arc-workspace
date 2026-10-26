"""The expansion config: each derived relation kept through an intermediate,
and each cell instance, that the lib of `docs/lib-spec.md` holds, expanded
like a macro into its definition, as a pass over a parsed Souffle solver, so
that a solver runs in either form.

The pass reads the solver's Souffle form, where the names are the present
lib's or, for a component only the signature holds, the signature's: `dist`
for `margin`, `corner_anchor` for `same_corner`, `Components` for
Connectivity. A definition is written in the same names.

- `RELATIONS`: each derived relation, by name, as a clause whose body is its
  definition over the algebra's signature, its tables and integer
  comparison, and the body that holds where the relation does not, for a
  negated site. A definition names no direction or axis: it reaches each
  of them through the tables. A site's columns are the head's; a body
  variable the head lacks is fresh at each site.
- `UNIVERSAL` and `MATERIALIZED`: the relations a top-level site reads
  through a relation over its own candidates or inputs, so that an
  expansion does no more work than the operation it expands.
- `SPECS`: each cell instance, as an `instances.Spec` over its members
  construction: Connectivity onto `Canon`, Flood onto `Propagation`,
  CellDistance onto `GraphDistance`, Ray onto `GraphDistance` per origin,
  Division onto `stride`, and Enclosure onto a Flood and a Connectivity,
  which the pass then expands in turn.

`nearer` and `same_line`, over a union type, take the branch of the member
type the site's first column has, read from the clause's other atoms; where
the clause fixes no member type, a site in the clause's body list splits the
clause into one clause per member type.

A site the pass cannot expand stays in place, with the reason: a negated
site with an unread column, whose negation is a universal over that column;
a site over a union type that the clause fixes no member type of, inside a
disjunction or an aggregate; and a site whose definition reads a name a
relation of the solver takes in the site's scope.
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass, replace
from itertools import count, product

from engine.program import (Aggregate, Atom, AtomLiteral, Comparison, ComparisonOperator, DeclId, DefinedName,
                            Disjunction, Qualifier, RecordTerm, RecordType, RelationName, Unit, UnitId,
                            Variable, Wildcard)

from arclog_convert.libmap.box import Types
from arclog_convert.libmap.division import TESTS, _lib_inline
from arclog_convert.libmap.instances import Spec, _parse, expand as expand_instances, term_vars

CONSTANTS = {"ZERO"}

# name: (head, the body where the relation holds, the body where it does not)
_RELATIONS: dict[str, tuple[str, str, str]] = {
    # a universal over the four margins
    "inside": ("inside(A, B)",
               "relative(B, A, R), axis_of(D1, A1), opposite(D1, O1), perp(A1, A2), axis_of(D2, A2), opposite(D2, O2), dist(R, D1, K1), K1 >= 0, dist(R, O1, K2), K2 >= 0,"
               " dist(R, D2, K3), K3 >= 0, dist(R, O2, K4), K4 >= 0",
               "dir_elem(D), relative(B, A, R), dist(R, D, K), K < 0"),
    "interior": ("interior(A, B)",
                 "relative(B, A, R), axis_of(D1, A1), opposite(D1, O1), perp(A1, A2), axis_of(D2, A2), opposite(D2, O2), dist(R, D1, K1), K1 > 0, dist(R, O1, K2), K2 > 0,"
                 " dist(R, D2, K3), K3 > 0, dist(R, O2, K4), K4 > 0",
                 "dir_elem(D), relative(B, A, R), dist(R, D, K), K <= 0"),
    # projections compared, through the projection
    "same_dist": ("same_dist(D, P1, P2)", "dist(P1, D, K), dist(P2, D, K)",
                  "dist(P1, D, K1), dist(P2, D, K2), K1 != K2"),
    "same_line": ("same_line(A, P, Q)",
                  "( perp(A, A2), axis_of(D, A2), dist(P, D, K), dist(Q, D, K) ;"
                  " diag_perp(A, A2), diag_axis_of(D, A2), corner_dist(P, D, K), corner_dist(Q, D, K) )",
                  "( perp(A, A2), axis_of(D, A2), opposite(D, O), dist(P, D, K1), dist(Q, D, K2), K1 != K2,"
                  " dist(P, O, K3), dist(Q, O, K4), K3 != K4 ;"
                  " diag_perp(A, A2), diag_axis_of(D, A2), diag_opposite(D, O), corner_dist(P, D, K1),"
                  " corner_dist(Q, D, K2), K1 != K2, corner_dist(P, O, K3), corner_dist(Q, O, K4), K3 != K4 )"),
    "corner_anchor": ("corner_anchor(Diag, P1, P2)",
                      "dir_of(Diag, A, D1), perp(A, A2), dir_of(Diag, A2, D2), dist(P1, D1, K1), dist(P2, D1, K1),"
                      " dist(P1, D2, K2), dist(P2, D2, K2)",
                      "dir_of(Diag, _, D), dist(P1, D, K1), dist(P2, D, K2), K1 != K2"),
    "slab_anchor": ("slab_anchor(D, P1, P2)",
                    "dist(P1, D, K), dist(P2, D, K), axis_of(D, A), perp(A, A2), axis_of(E, A2), opposite(E, E2),"
                    " dist(P1, E, K1), dist(P2, E, K1), dist(P1, E2, K2), dist(P2, E2, K2)",
                    "( dist(P1, D, K1), dist(P2, D, K2), K1 != K2 ;"
                    " axis_of(D, A), perp(A, A2), axis_of(E, A2), dist(P1, E, K1), dist(P2, E, K2), K1 != K2 )"),
    "nearer": ("nearer(D, P, Q)",
               "( dir_elem(D), dist(P, D, K1), dist(Q, D, K2), K1 < K2 ;"
               " diag_dir_elem(D), corner_dist(P, D, K1), corner_dist(Q, D, K2), K1 < K2 )",
               "( dir_elem(D), dist(P, D, K1), dist(Q, D, K2), K1 >= K2 ;"
               " diag_dir_elem(D), corner_dist(P, D, K1), corner_dist(Q, D, K2), K1 >= K2 )"),
    "centered": ("centered(P)",
                 "axis_of(D1, A1), opposite(D1, O1), perp(A1, A2), axis_of(D2, A2), opposite(D2, O2), dist(P, D1, K1), dist(P, O1, K1), dist(P, D2, K2), dist(P, O2, K2)",
                 "opposite(D, O), dist(P, D, K1), dist(P, O, K2), K1 != K2"),
    "dist_pair": ("dist_pair(P, D, K, K2)", "opposite(D, O), dist(P, D, K), dist(P, O, K2)",
                  "opposite(D, O), dist(P, D, X1), dist(P, O, X2), ( X1 != K ; X2 != K2 )"),
    "diag_dist": ("diag_dist(P, Diag, A, K1, K2)",
                  "diag_dirs(Diag, A, D1, D2), dist(P, D1, K1), dist(P, D2, K2)",
                  "diag_dirs(Diag, A, D1, D2), dist(P, D1, X1), dist(P, D2, X2), ( X1 != K1 ; X2 != K2 )"),
    "axis_dims": ("axis_dims(P, A, N1, N2)", "perp(A, A2), axis_dim(P, A, N1), axis_dim(P, A2, N2)",
                  "perp(A, A2), axis_dim(P, A, X1), axis_dim(P, A2, X2), ( X1 != N1 ; X2 != N2 )"),
    "box_extent": ("box_extent(B, P, A, N)", "axis_elem(A), relative(B, P, R), axis_dim(R, A, N)",
                   "relative(B, P, R), axis_dim(R, A, X), X != N"),
    # injections composed
    "axis_inset": ("axis_inset(D, K1, K2, B)",
                   "opposite(D, O), edge_inset(D, K1, B1), edge_inset(O, K2, B2), compose(B1, B2, B)",
                   "opposite(D, O), edge_inset(D, K1, B1), edge_inset(O, K2, B2), compose(B1, B2, X), X != B"),
    "uniform_inset": ("uniform_inset(K, B)",
                      "axis_of(D1, A1), perp(A1, A2), axis_of(D2, A2), axis_inset(D1, K, K, B1),"
                      " axis_inset(D2, K, K, B2), compose(B1, B2, B)",
                      "dir_elem(D), dist(B, D, X), X != K"),
    "corner_inset": ("corner_inset(Diag, K, B)",
                     "dir_of(Diag, A, D1), perp(A, A2), dir_of(Diag, A2, D2), edge_inset(D1, K, B1),"
                     " edge_inset(D2, K, B2), compose(B1, B2, B)",
                     "dir_of(Diag, A, D1), perp(A, A2), dir_of(Diag, A2, D2), edge_inset(D1, K, B1),"
                     " edge_inset(D2, K, B2), compose(B1, B2, X), X != B"),
    "edge_outset": ("edge_outset(D, K, B)", "edge_inset(D, K, I), relative(I, ZERO, B)",
                    "edge_inset(D, K, I), relative(I, ZERO, X), X != B"),
    "corner_outset": ("corner_outset(Diag, K, B)", "corner_inset(Diag, K, I), relative(I, ZERO, B)",
                      "corner_inset(Diag, K, I), relative(I, ZERO, X), X != B"),
    "axis_outset": ("axis_outset(D, K1, K2, B)", "axis_inset(D, K1, K2, I), relative(I, ZERO, B)",
                    "axis_inset(D, K1, K2, I), relative(I, ZERO, X), X != B"),
    "uniform_outset": ("uniform_outset(K, B)", "uniform_inset(K, I), relative(I, ZERO, B)",
                       "uniform_inset(K, I), relative(I, ZERO, X), X != B"),
    "jump_offset": ("jump_offset(D, K, V)",
                    "dir8_opposite(D, O), edge_inset(O, K, B1), edge_outset(D, K, B2), compose(B1, B2, V)",
                    "dir8_opposite(D, O), edge_inset(O, K, B1), edge_outset(D, K, B2), compose(B1, B2, X), X != V"),
    # an offset composed
    "jump": ("jump(P, D, K, Q)", "jump_offset(D, K, V), compose(P, V, Q)",
             "jump_offset(D, K, V), compose(P, V, X), X != Q"),
    "neighbor": ("neighbor(P, D, Q)", "step_offset(D, V), compose(P, V, Q)",
                 "step_offset(D, V), compose(P, V, X), X != Q"),
    "frame_offset": ("frame_offset(P, A, K, V)", "axis_of(D, A), sub_extent(P, A, K), jump_offset(D, K, V)", ""),
    # projections split by axis
    "split": ("split(P, A, Along, Across)",
              "axis_of(D, A), opposite(D, O), dist(P, D, K1), dist(P, O, K2), axis_inset(D, K1, K2, Along),"
              " relative(Along, P, Across)",
              "axis_of(D, A), opposite(D, O), dist(P, D, K1), dist(P, O, K2), axis_inset(D, K1, K2, X),"
              " relative(X, P, Y), ( X != Along ; Y != Across )"),
    # the orientation algebra's derived relations
    "perp_dir": ("perp_dir(D, D2)", "axis_of(D, A), perp(A, A2), axis_of(D2, A2)", "axis_of(D, A), axis_of(D2, A)"),
    "diag_dirs": ("diag_dirs(Diag, A, D1, D2)", "dir_of(Diag, A, D1), perp(A, A2), dir_of(Diag, A2, D2)",
                  "dir_of(Diag, A, X1), perp(A, A2), dir_of(Diag, A2, X2), ( X1 != D1 ; X2 != D2 )"),
    "apply_dir": ("apply_dir(T, D, D2)",
                  "d4_elem(T), dir_elem(D), dir_elem(D2), step_offset(D, S), apply(T, S, S2), step_offset(D2, S2)",
                  "step_offset(D, S), apply(T, S, S2), step_offset(D2, X), X != S2"),
    "apply_diag_dir": ("apply_diag_dir(T, D, D2)",
                       "d4_elem(T), diag_dir_elem(D), diag_dir_elem(D2), step_offset(D, S), apply(T, S, S2),"
                       " step_offset(D2, S2)",
                       "step_offset(D, S), apply(T, S, S2), step_offset(D2, X), X != S2"),
    "apply_dir8": ("apply_dir8(T, D, D2)",
                   "d4_elem(T), dir8_elem(D), dir8_elem(D2), step_offset(D, S), apply(T, S, S2), step_offset(D2, S2)",
                   "step_offset(D, S), apply(T, S, S2), step_offset(D2, X), X != S2"),
}


UNIVERSAL: dict[str, tuple[str, str]] = {
    "inside": ("", "dir_elem(D), relative(B, A, R), dist(R, D, K), K < 0"),
    "interior": ("", "dir_elem(D), relative(B, A, R), dist(R, D, K), K <= 0"),
    "centered": ("", "opposite(D, O), dist(P, D, K1), dist(P, O, K2), K1 != K2"),
    "corner_anchor": ("", "dir_of(Diag, _, D), dist(P1, D, K1), dist(P2, D, K2), K1 != K2"),
    "slab_anchor": ("dist(P1, D, K), dist(P2, D, K)",
                    "axis_of(D, A), perp(A, A2), axis_of(E, A2), dist(P1, E, K1), dist(P2, E, K2), K1 != K2"),
}
"""A relation whose definition holds a universal: the part of its body
before the universal, and the universal's defect. A site reads the defect
through a relation over the site's own candidates, which the converter
writes as `ALL`, so that each candidate costs one test per member."""
MATERIALIZED: dict[str, int] = {"uniform_inset": 1, "uniform_outset": 1, "corner_inset": 2, "corner_outset": 2,
                                "split": 2}
"""A relation whose definition reaches its result through symmetric choices
of the tables, each giving the same result, by its count of input columns.
A site reads the result through a relation over the site's own inputs, so
that the choices are made once per input and not once per row of the
clause."""


def _consts(x):
    """x with each variable a constant's name names as that constant."""
    if isinstance(x, Variable):
        return DefinedName(x.name) if x.name in CONSTANTS else x
    if isinstance(x, tuple):
        return tuple(_consts(y) for y in x)
    if is_dataclass(x) and not isinstance(x, type):
        ch = {f.name: _consts(getattr(x, f.name)) for f in fields(x) if f.name not in ("relation", "line", "span")}
        return replace(x, **ch)
    return x


def _macro(head: str, body: str) -> tuple[Atom, tuple]:
    u = _parse(f"{head} :- {body}.").units[0]
    lits = _consts(u.body or ())
    assert isinstance(lits, tuple)
    return u.head, lits


TYPE_CASES = {"nearer": {"Dir": 0, "DiagDir": 1}, "same_line": {"Axis": 0, "DiagAxis": 1}}
"""A relation over a union type whose definition is one branch per member
type: the branch of each member type, by the first column's type at the
site."""

_UNIVERSAL = {n: (_macro(_RELATIONS[n][0], pre)[1] if pre else (), _macro(_RELATIONS[n][0], d)[1])
              for n, (pre, d) in UNIVERSAL.items()}

RELATIONS: dict[str, tuple[Atom, tuple, tuple | None]] = {
    name: (*_macro(h, pos), _macro(h, neg)[1] if neg else None) for name, (h, pos, neg) in _RELATIONS.items()}
"""Each derived relation: its head, its definition, and the body where it
does not hold, or None where a negated site keeps the name."""


# ---- the cell instances


def _steps(x: str = "{x}") -> str:
    """The clause of a cell instance's steps: the cardinals, its default rows."""
    return f"{x}_steps(S) :- dir_elem(D), step_offset(D, S)."


def connectivity(inst, ex):
    return Spec(".type {x}_member = [key: {Key}, p: Position]\n.init {x} = Canon<{x}_member>\n"
                ".decl {x}_steps(delta: Offset)\n.decl {x}_component(key: {Key}, p: Position, id: Ident)",
                {"step(S)": ["{x}_steps(S)"]},
                {"label(Ky, P, I)": "{x}_component(Ky, P, I)",
                 "node(Ky, P)": "in_node(Ky, P)", "step(S)": "{x}_steps(S)"},
                _steps() + "\n{x}_component(Ky, P, I) :- {x}.id([Ky, P], I).\n"
                "{x}.edge([Ky, P], [Ky, P]) :- in_node(Ky, P).\n"
                "{x}.edge([Ky, P], [Ky, Q]) :- in_node(Ky, P), {x}_steps(S), compose(P, S, Q), in_node(Ky, Q).")


def flood(inst, ex):
    return Spec(".init {x} = Propagation<{Key}, Position>\n.decl {x}_steps(delta: Offset)",
                {"step(S)": ["{x}_steps(S)"]},
                {"reach(Ky, P)": "{x}.reached(Ky, P)", "node(Ky, P)": "in_node(Ky, P)",
                 "seed(Ky, P)": "in_seed(Ky, P)", "step(S)": "{x}_steps(S)"},
                _steps() + "\n{x}.source(Ky, P) :- in_seed(Ky, P), in_node(Ky, P).\n"
                "{x}.edge(Ky, P, Q) :- in_node(Ky, P), {x}_steps(S), compose(P, S, Q), in_node(Ky, Q).")


def enclosure(inst, ex):
    return Spec(".init {x}_flood = Reach<{Key}>\n.init {x} = Components<{Key}>",
                {"cell(Ky, P)": ["{x}_flood.node(Ky, P)"]},
                {"region(Ky, P, I)": "{x}.label(Ky, P, I)", "cell(Ky, P)": "in_cell(Ky, P)"},
                "{x}_flood.seed(Ky, P) :- in_cell(Ky, P), dir_elem(D), dist(P, D, 0).\n"
                "{x}.node(Ky, P) :- in_cell(Ky, P), !{x}_flood.reach(Ky, P).",
                derive=frozenset({"cell"}))


def cell_distance(inst, ex):
    return Spec(".init {x} = GraphDistance<{Key}, Position>\n.decl {x}_steps(delta: Offset)",
                {"source(Ky, P)": ["{x}.seed(Ky, P)"], "step(S)": ["{x}_steps(S)"]},
                {"distance(Ky, P, K)": "{x}.distance(Ky, P, K)", "predecessor(Ky, Q, P)": "{x}.pred(Ky, Q, P)",
                 "node(Ky, P)": "in_node(Ky, P)", "source(Ky, P)": "in_source(Ky, P)", "step(S)": "{x}_steps(S)"},
                _steps() + "\n"
                "{x}.edge(Ky, P, Q) :- in_node(Ky, P), {x}_steps(S), compose(P, S, Q), in_node(Ky, Q).")


def ray(inst, ex):
    if any(ex.inputs(inst, n) for n in ("mark", "cell", "blocked")):
        return None   # an instance of the present Ray, which no expansion wrote
    # one distance per key, direction and origin, over the edges of the origin's line ahead of it: the
    # work is the rays' cells, where a walk from every node would cost every node's run
    return Spec(".type {x}_line = [key: {Key}, d: Dir8, origin: Position]\n"
                ".init {x} = GraphDistance<{x}_line, Position>\n"
                ".decl {x}_ray(key: {Key}, p: Position, d: Dir8, k: number, origin: Position)\n"
                ".decl {x}_end(key: {Key}, p: Position, d: Dir8, k: number, origin: Position)",
                {},
                {"ray(Ky, P, D, K, O)": "{x}_ray(Ky, P, D, K, O)", "end(Ky, P, D, K, O)": "{x}_end(Ky, P, D, K, O)",
                 "source(Ky, P)": "in_source(Ky, P)", "node(Ky, P)": "in_node(Ky, P)",
                 "dir(Ky, D)": "in_dir(Ky, D)"},
                "{x}.seed([Ky, D, O], O) :- in_source(Ky, O), in_dir(Ky, D).\n"
                "{x}.edge([Ky, D, O], O, Q) :- in_source(Ky, O), in_dir(Ky, D), neighbor(O, D, Q), in_node(Ky, Q).\n"
                "{x}.edge([Ky, D, O], P, Q) :- in_source(Ky, O), in_dir(Ky, D), axis_of(D, A), sub_extent(O, A, K),"
                " jump(O, D, K, P), in_node(Ky, P), neighbor(P, D, Q), in_node(Ky, Q).\n"
                "{x}.edge([Ky, D, O], P, Q) :- in_source(Ky, O), in_dir(Ky, D), diag_dir_elem(D), axis_elem(A),"
                " sub_extent(O, A, K), jump(O, D, K, P), in_node(Ky, P), neighbor(P, D, Q), in_node(Ky, Q).\n"
                "{x}_ray(Ky, P, D, K, O) :- {x}.distance([Ky, D, O], P, K).\n"
                "{x}_end(Ky, P, D, K, O) :- {x}_ray(Ky, P, D, K, O), neighbor(P, D, Q), !{x}_ray(Ky, Q, D, _, O).",
                derive=frozenset({"source", "node", "dir"}))


def division(inst, ex):
    has = {n for n in ("parts", "side", "gap") if ex.inputs(inst, n)}
    # an axis with no `gap` row has gap 0
    gaps = ([" in_gap(Ky, A, G),"] if "gap" in has else []) + \
        [(" !in_gap(Ky, A, _)," if "gap" in has else "") + "{0}"]

    def tail(g: str) -> str:
        return (f" axis_of(D, A), opposite(D, O), dist(P, D, T), dist(P, O, T2),"
                f" stride(T, K, {g}, I, R), stride(T2, K, {g}, I2, R2),"
                f" axis_inset(D, I, I2, Po), axis_inset(D, R, R2, Pi), axis_dim(Pi, A, K)")
    clauses = []
    for gl in gaps:
        g, gl = ("0", gl.replace("{0}", "")) if "{0}" in gl else ("G", gl)
        if "side" in has:
            clauses.append("{x}_axis(Ky, P, A, Po, Pi) :- in_cell(Ky, P), in_side(Ky, A, K)," + gl + tail(g) + ".")
        if "parts" in has:   # the side the count gives, read once per key off the extent; one part spans it
            clauses.append("{x}_axis(Ky, P, A, Po, Pi) :- in_cell(Ky, P), in_parts(Ky, A, N)," + gl
                           + f" {{x}}_sides.division(Ky, A, N, K, {g})," + tail(g) + ".")
            clauses.append("{x}_axis(Ky, P, A, Po, Pi) :- in_cell(Ky, P), in_parts(Ky, A, N)," + gl
                           + " axis_dim(P, A, K)," + tail(g) + ", axis_dim(Po, A, N).")
    clauses += ["{x}_axis(Ky, P, A, Po, Pi) :- in_cell(Ky, P), axis_elem(A)"
                + "".join(f", !in_{n}(Ky, A, _)" for n in ("parts", "side") if n in has)
                + ", split(P, A, Pi, _), relative(Pi, Pi, Po).",
                "{x}_tile(Ky, P, Po, Pi) :- {x}_axis(Ky, P, A1, Po1, Pi1), perp(A1, A2), {x}_axis(Ky, P, A2, Po2, Pi2),"
                " compose(Po1, Po2, Po), compose(Pi1, Pi2, Pi)."]
    if "parts" in has:
        clauses.append("{x}_sides.frame(Ky, P) :- in_cell(Ky, P).")
    return Spec((".init {x}_sides = ExtentDivisions<{Key}>\n" if "parts" in has else "") +
                ".decl {x}_axis(key: {Key}, p: Position, a: Axis, p_outer: Position, p_inner: Position)\n"
                ".decl {x}_tile(key: {Key}, p: Position, p_outer: Position, p_inner: Position)",
                {},
                {"tile(Ky, P, Po, Pi)": "{x}_tile(Ky, P, Po, Pi)", "cell(Ky, P)": "in_cell(Ky, P)",
                 "parts(Ky, A, N)": "in_parts(Ky, A, N)", "side(Ky, A, K)": "in_side(Ky, A, K)",
                 "gap(Ky, A, G)": "in_gap(Ky, A, G)"},
                "\n".join(c for c in clauses if c))


def _apart(spec_fn, roles: tuple[str, ...]):
    """The spec, each name `{x}_<role>` of its shape that a relation, type or
    instance of the solver takes in the instance's scope given a suffix."""
    def fn(inst, ex):
        spec = spec_fn(inst, ex)
        if spec is None:
            return None
        scope = inst.scope.components
        types = {(t.scope.components, t.name) for t in ex.prog.types}
        for role in roles:
            name, n = f"{inst.name}_{role}", 2
            while ex.taken(name, scope) or any((scope[:i], name) in types for i in range(len(scope) + 1)):
                name, n = f"{inst.name}_{role}{n}", n + 1
            if name != f"{inst.name}_{role}":
                old = "{x}_" + role
                spec = replace(spec, decls=spec.decls.replace(old, name), clauses=spec.clauses.replace(old, name),
                               reads={k: v.replace(old, name) for k, v in spec.reads.items()},
                               inputs={k: [h.replace(old, name) for h in v] for k, v in spec.inputs.items()})
        return spec
    return fn


SPECS = {"Components": _apart(connectivity, ("member", "steps", "component")), "Reach": _apart(flood, ("steps",)),
         "Closed": _apart(enclosure, ("flood",)), "CellDistance": _apart(cell_distance, ("steps",)),
         "Ray": _apart(ray, ("line", "ray", "end")), "Division": _apart(division, ("axis", "tile", "sides"))}
"""Each cell instance's spec, by its component's name in the Souffle form."""


# ---- the pass


class _Fresh:
    def __init__(self, taken: set[str]) -> None:
        self.taken = taken
        self.n = count(1)

    def __call__(self, base: str) -> Variable:
        while True:
            v = f"{base}_m{next(self.n)}"
            if v not in self.taken:
                self.taken.add(v)
                return Variable(v)


class _Types(Types):
    """Column types read through the solver's aliases and subtypes only as
    far as a type of `stop`."""
    stop: set[str] = set()

    def base(self, name: str, scope: tuple[str, ...]) -> str:
        return _base(self, name, scope, self.stop)


def _base(types, name: str, scope: tuple[str, ...], stop: set[str]) -> str:
    """The type a solver type name stands for, read through its aliases and
    subtypes until a name of `stop`."""
    from engine.program import AliasType, SubtypeType
    for _ in range(16):
        if name in stop:
            return name
        t = next((types.types[(scope[:i], name)] for i in range(len(scope), -1, -1)
                  if (scope[:i], name) in types.types), None)
        if isinstance(t, AliasType):
            name = t.target.name
        elif isinstance(t, SubtypeType):
            name = t.base.name
        else:
            return name
    return name


def _holds(d: Disjunction, ids: set[int]) -> bool:
    """A literal of `ids` stands in one of the disjunction's branches."""
    return any(id(x) in ids or (isinstance(x, Disjunction) and _holds(x, ids)) for br in d.branches for x in br)


def columns(name: str, lib) -> list[tuple[str, str]]:
    """The relation's columns, as the present lib or the signature declares them."""
    return lib.top.get(name) or lib.sig_top[name]


def _branch(body: tuple, k: int) -> tuple:
    """The k-th branch of a definition that is one disjunction."""
    (d,) = body
    assert isinstance(d, Disjunction)
    return d.branches[k]


def _site(a: Atom) -> bool:
    return not a.relation.instances and a.relation.name in RELATIONS and \
        len(a.args) == len(RELATIONS[a.relation.name][0].args)


def _instance(head: Atom, body: tuple, a: Atom, fresh: _Fresh, wild: bool) -> tuple:
    """The body at the site a: each head variable as the site's term, a
    wildcard at the site as a fresh variable where `wild`, and each other
    variable fresh."""
    from arclog_convert.libmap.instances import subst
    m = {}
    for p, t in zip(head.args, a.args):
        assert isinstance(p, Variable)
        m[p.name] = fresh(p.name) if isinstance(t, Wildcard) and wild else t
    for v in term_vars(body, []):
        if v not in m:
            m[v] = fresh(v)
    out = _relined(subst(body, m, False), a.line)
    assert isinstance(out, tuple)
    return out


def _relined(x, line: int):
    if isinstance(x, tuple):
        return tuple(_relined(y, line) for y in x)
    if isinstance(x, Atom):
        return replace(x, args=_relined(x.args, line), line=line)
    if is_dataclass(x) and not isinstance(x, type) and hasattr(x, "line"):
        ch = {f.name: _relined(getattr(x, f.name), line) for f in fields(x) if f.name not in ("relation", "span")}
        ch["line"] = line
        return replace(x, **ch)
    if is_dataclass(x) and not isinstance(x, type) and not isinstance(x, (DefinedName,)):
        ch = {f.name: _relined(getattr(x, f.name), line) for f in fields(x) if f.name not in ("relation", "span")}
        return replace(x, **ch)
    return x


def expand_relations(prog, lib, names: set[str] | None = None) -> tuple[object, dict[Atom, str]]:
    """The program with each site of a derived relation of `RELATIONS`, or of
    `names`, in the solver's own clauses replaced by its definition, in turn
    until no site is left; and each site left in place, with the reason.
    `lib` gives the column types that choose a branch of `TYPE_CASES`."""
    from arclog_convert.libmap.box import atoms
    judgment: dict[Atom, str] = {}
    types = _Types(prog, lib)

    def column(b: Atom, i: int, scope: tuple[str, ...], stop: set[str]) -> str | None:
        """The column's type, read through the solver's aliases as far as a
        type of `stop`: the lib's declared name, where `Types` reads the
        number type it stands on."""
        rn = b.relation
        if not rn.instances and rn.name in lib.top and not clash(rn.name, scope):
            cols = lib.top[rn.name]
            return cols[i][1] if i < len(cols) else None
        types.stop = stop
        return types.column(b, i, scope)

    def member_type(a: Atom, u: Unit, ctx: tuple | None = None) -> str | None:
        """The member type of the site's first column: a constant's, or the
        one column type of the clause's other atoms that its variable
        fills: each atom of `ctx`, the lists the site stands in, or else of
        the clause."""
        cases = TYPE_CASES[a.relation.name]
        t = a.args[0]
        if isinstance(t, DefinedName):
            return {"DIR_": "Dir", "DIAG_": "DiagDir", "AXIS_": "Axis", "DAXIS_": "DiagAxis"}.get(
                next((p for p in ("DIR_", "DIAG_", "AXIS_", "DAXIS_") if t.name.startswith(p)), ""))
        found: set[str] = set()
        scope = u.scope.components

        def visit(x, ty: str | None) -> None:
            """The variable's type where x, of type ty, holds it, a record's
            fields included."""
            if ty is None:
                return
            if isinstance(x, Variable) and x.name == tname and ty in cases:
                found.add(ty)
            elif isinstance(x, RecordTerm):
                rt = next((types.types[(scope[:i], ty)] for i in range(len(scope), -1, -1)
                           if (scope[:i], ty) in types.types), None)
                if isinstance(rt, RecordType) and len(rt.fields) == len(x.args):
                    for y, f in zip(x.args, rt.fields):
                        visit(y, _base(types, f.type.name, scope, set(cases)))

        if not isinstance(t, Variable):
            return None
        tname = t.name
        for b in [u.head, *(atoms(u.body or ()) if ctx is None else ctx)]:
            if b is not a:
                for i, x in enumerate(b.args):
                    visit(x, column(b, i, scope, set(cases)))
        return found.pop() if len(found) == 1 else None

    own_names = {(r.scope.components, r.name) for r in prog.relations if r.span is None or r.span.file is None}

    def clash(name: str, scope: tuple[str, ...]) -> bool:
        return any((scope[:i], name) in own_names for i in range(len(scope) + 1))

    def lits(body: tuple, fresh: _Fresh, scope, u: Unit, ctx: tuple | None = None) -> tuple:
        here = None if ctx is None else ctx + tuple(atoms(tuple(l for l in body if not isinstance(l, Disjunction))))
        out: list = []
        for lit in body:
            if isinstance(lit, Disjunction):
                out.append(replace(lit, branches=tuple(lits(b, fresh, scope, u, here) for b in lit.branches)))
                continue
            lit = terms(lit, fresh, scope, u)
            if not (isinstance(lit, AtomLiteral) and _site(lit.atom)) or \
                    (names is not None and lit.atom.relation.name not in names):
                out.append(lit)
                continue
            a = lit.atom
            head, pos, neg = RELATIONS[a.relation.name]
            body_names = {b.relation.name for b in atoms(pos + (neg or ()))}
            if any(clash(n, scope) for n in body_names):
                judgment[a] = f"{a.relation.name}: its definition reads a name a relation of the solver takes"
                out.append(lit)
                continue
            if a.relation.name in TYPE_CASES:
                t = member_type(a, u, here)
                if id(a) in forced:
                    t = forced[id(a)]
                if t is None:
                    judgment[a] = f"{a.relation.name}: the first column's type at the site is no one member type"
                    out.append(lit)
                    continue
                k = TYPE_CASES[a.relation.name][t]
                pos = _branch(pos, k)
                neg = _branch(neg, k) if neg is not None else None
            if not lit.negated and ctx == () and id(u) not in helpers and \
                    (a.relation.name in UNIVERSAL or a.relation.name in MATERIALIZED):
                got = helper(a, u, fresh)
                if got is not None:
                    out.extend(got)
                    continue
            if not lit.negated:
                out.extend(lits(_instance(head, pos, a, fresh, True), fresh, scope, u, here))
            elif neg is None:
                judgment[a] = f"{a.relation.name}: a negated site, whose definition has no negated body"
                out.append(lit)
            elif any(isinstance(t, Wildcard) for t in a.args):
                judgment[a] = f"{a.relation.name}: a negated site with an unread column"
                out.append(lit)
            else:
                body = lits(_instance(head, neg, a, fresh, False), fresh, scope, u, here)
                if ctx:   # inside a disjunction: its positive atoms read what the clause may make later
                    branch_neg.update(id(x) for x in body)
                out.extend(body)
        return tuple(out)

    def terms(x, fresh, scope, u):
        """x with the body of each aggregate inside it expanded."""
        if isinstance(x, Aggregate):
            return replace(x, expr=terms(x.expr, fresh, scope, u), body=lits(x.body, fresh, scope, u))
        if isinstance(x, tuple):
            return tuple(terms(y, fresh, scope, u) for y in x)
        if is_dataclass(x) and not isinstance(x, type) and not isinstance(x, (Atom, RelationName)):
            ch = {f.name: terms(getattr(x, f.name), fresh, scope, u) for f in fields(x)}
            return replace(x, **ch) if any(ch[k] is not getattr(x, k) for k in ch) else x
        return x

    next_id = count(1 + max((x.id.index for x in prog.units), default=0))
    inline = _lib_inline() | {r.name for r in prog.relations if Qualifier.INLINE in r.qualifiers}
    helpers: set[int] = set()   # a clause the pass made for a site's candidates
    made: list[Unit] = []
    decls: list = []
    helper_names: set[tuple] = set()

    def grounding(vs: list[str], u: Unit) -> list | None:
        """The top-level positive literals of the clause that ground each
        variable of vs: an atom of a stored or derived relation, or an inline
        atom or `=` comparison whose other variables they ground."""
        top = [l for l in u.body or () if (isinstance(l, AtomLiteral) and not l.negated)
               or (isinstance(l, Comparison) and l.op == ComparisonOperator.EQ)]
        out: list = []

        def one(v: str, avoid: frozenset) -> bool:
            if v in avoid:
                return False
            for l in top:
                if isinstance(l, AtomLiteral) and (l.atom.relation.instances or l.atom.relation.name not in inline) \
                        and v in term_vars(l.atom.args, []):
                    if l not in out:
                        out.append(l)
                    return True
            for l in top:
                if isinstance(l, AtomLiteral):
                    n = l.atom.relation.name
                    if l.atom.relation.instances or n not in inline or n in TESTS or v not in term_vars(l.atom.args, []):
                        continue
                    others = [w for w in term_vars(l.atom.args, []) if w != v]
                else:
                    sides = [(l.lhs, l.rhs), (l.rhs, l.lhs)]
                    pick = next((o for x, o in sides if isinstance(x, Variable) and x.name == v), None)
                    if pick is None or v in term_vars(pick, []):
                        continue
                    others = term_vars(pick, [])
                if all(one(w, avoid | {v}) for w in others):
                    if l not in out:
                        out.append(l)
                    return True
            return False
        return out if all(one(v, frozenset()) for v in vs) else None

    def helper(a: Atom, u: Unit, fresh: _Fresh) -> tuple | None:
        """A site's literals that read a relation over its own candidates, or
        None where the clause grounds them only past its top level."""
        name = a.relation.name
        n_in = MATERIALIZED.get(name, len(a.args))
        if not all(isinstance(t, Variable) for t in a.args[:n_in]) or \
                any(not isinstance(t, (Variable, Wildcard)) for t in a.args[n_in:]):
            return None
        ins = list(dict.fromkeys(t.name for t in a.args[:n_in] if isinstance(t, Variable)))
        g = grounding(ins, u)
        if g is None:
            return None
        cols = columns(name, lib)
        k = 1
        while True:
            hname = f"{u.head.relation.name}_{name}{k}"
            if (u.scope.components, hname) not in helper_names and not clash(hname, u.scope.components):
                break
            k += 1
        helper_names.add((u.scope.components, hname))
        head0, pos, _ = RELATIONS[name]
        if name in UNIVERSAL:
            pre, defect = _UNIVERSAL[name]
            hargs = tuple(Variable(v) for v in ins)
            hcols = [(v, next(t for x, (_, t) in zip(a.args, cols) if isinstance(x, Variable) and x.name == v))
                     for v in ins]
            body = (*g, *_instance(head0, defect, a, _Fresh(set(term_vars((u.head, u.body), []))), True))
            site = (*(_instance(head0, pre, a, fresh, True) if pre else ()),
                    AtomLiteral(Atom(RelationName((), hname), hargs, a.line), True))
        else:
            outs = [t if isinstance(t, Variable) else fresh("X") for t in a.args[n_in:]]
            site_atom = replace(a, args=(*a.args[:n_in], *outs))
            hargs = tuple(Variable(v) for v in ins) + tuple(outs)
            hcols = [(v, cols[i][1]) for i, v in enumerate(ins)] + [(o.name, t) for o, (_, t) in zip(outs, cols[n_in:])]
            body = (*g, *_instance(head0, pos, site_atom, _Fresh(set(term_vars((u.head, u.body), [])) | {o.name for o in outs}), False))
            site = (AtomLiteral(Atom(RelationName((), hname), hargs, a.line), False),)
        decl = _parse(f".decl {hname}({', '.join(f'{v.lower()}_: {t}' for v, t in hcols)})").relations[0]
        decls.append(replace(decl, scope=u.scope, span=None))
        hu = replace(u, id=UnitId(next(next_id)), head=Atom(RelationName((), hname), hargs, a.line), body=body,
                     span=None, plan=None, subsumptive=False)
        helpers.add(id(hu))
        made.append(hu)
        return site

    branch_neg: set[int] = set()   # the literals of a negated site's definition inside a disjunction
    forced: dict[int, str] = {}   # a site over a union type: the member type of this copy of its clause

    def unit(u: Unit) -> list[Unit]:
        """The clause expanded: where a site in its body's list holds a
        column of a union type, one clause per member type, which together
        hold where the site does."""
        if not u.body or (u.span is not None and u.span.file is not None) or not any(_site(a) for a in atoms(u.body)):
            return [u]
        top = tuple(atoms(tuple(l for l in u.body if not isinstance(l, Disjunction))))
        union = [lit.atom for lit in u.body if isinstance(lit, AtomLiteral) and _site(lit.atom)
                 and lit.atom.relation.name in TYPE_CASES and member_type(lit.atom, u, top) is None
                 and not any(isinstance(t, Wildcard) for t in lit.atom.args[:1])
                 and not u.subsumptive][:3]
        out = []
        for k, choice in enumerate(product(*(list(TYPE_CASES[a.relation.name]) for a in union))):
            forced.clear()
            forced.update({id(a): t for a, t in zip(union, choice)})
            fresh = _Fresh(set(term_vars((u.head, u.body), [])))
            branch_neg.clear()
            body = lits(u.body, fresh, u.scope.components, u, ())
            # a disjunction that holds a negated site's definition goes last, so that the variables the
            # definition reads are the clause's own before it
            late = [l for l in body if isinstance(l, Disjunction) and _holds(l, branch_neg)]
            v = replace(u, body=tuple(l for l in body if l not in late) + tuple(late))
            out.append(v if k == 0 else replace(v, id=UnitId(next(next_id))))
        forced.clear()
        return out

    units = [v for u in prog.units for v in unit(u)]
    done = 0
    while done < len(made):   # a clause made for a site's candidates holds sites in turn
        units += unit(made[done])
        done += 1
    rels = tuple(prog.relations) + tuple(replace(d, id=DeclId(9_000_000 + i)) for i, d in enumerate(decls))
    return replace(prog, relations=rels, units=tuple(units)), judgment


def expand(prog, lib, names: set[str] | None = None) -> tuple[object, dict[Atom, str]]:
    """The program with each cell instance and each derived relation of the
    config, or of `names`, expanded; and each site left in place, with the
    reason. `lib` reads each component of `SPECS` with the relations of its
    Souffle form."""
    specs = {k: v for k, v in SPECS.items() if names is None or k in names}
    judgment: dict[Atom, str] = {}
    for _ in range(4):   # an instance's shape may hold a cell instance, which expands in turn
        if not any((i.span is None or i.span.file is None) and i.component in specs for i in prog.instances):
            break
        prog, j, _, _ = expand_instances(prog, _SouffleLib(lib), specs)
        judgment |= j
    prog, j = expand_relations(prog, lib, names)
    return prog, judgment | j


class _SouffleLib:
    """The lib as the Souffle form reads it: a component the expansions
    write in its signature shape, `Ray`, with the signature's relations."""

    def __init__(self, lib) -> None:
        self.lib = lib

    def __getattr__(self, name):
        return getattr(self.lib, name)

    def present(self, comp: str):
        if comp in self.lib.replaced:
            return self.lib.relations(comp)
        return self.lib.present(comp)
