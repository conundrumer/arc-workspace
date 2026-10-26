"""The expansions of the division and frame names: each site of a division
relation, a concat relation or `divide_gap` hoisted into a `Division`,
`Tiling` or `ExtentDivisions` instance, as a pass over a parsed Souffle
solver; and `Divide2D` and `Tile2D` onto `Division`, `AxisFrame` onto
`Frame`, and `DirFrame` and `DirPack` onto derived relations, as
`instances.Spec` shapes.

The hoist of a site:

- Each input of the instance takes the atoms of the clause that ground its
  site arguments, under the clause's grounding rule: an atom of a stored or
  derived relation grounds each of its variables, and an inline atom other
  than a test of `TESTS`, or an `=` comparison, grounds one variable once
  the others are grounded. Where no atom grounds a variable so, an inline
  lib atom grounds it once the variables of one of its modes are grounded
  (`_modes`); a variable of an orientation type there counts as grounded,
  since arclog binds each label of a positive atom, and the `ground`
  form adds its `*_elem` atom.
- An elem atom an input's body copies, such as `axis_elem(A)`, leaves the
  instance's inputs where, in each input that holds it, another positive
  atom holds its variable at a column of the elem's own type, since arclog
  binds each label of a positive atom; the `ground` form keeps it.
- A position input, `cell`, `outer` or `inner`, takes a projection of its
  atoms: the read gives the position, and a position input may hold more
  positions than the clause reads for one key, since the instance's output
  at a position is a function of that position. An atom the projection keeps
  whole leaves the clause, unless one of its variables is read elsewhere.
- The atoms that ground a position or a key column take the clause's
  further top-level atoms over their variables, its tests among them, so
  that the instance holds only the positions and keys the clause reads.
- Every other input, the axis, count, side and gap, and `ExtentDivisions`'
  frame, takes its atoms whole, and they leave the clause. A variable they
  share with the rest of the clause is a key column; so is an axis of an
  axis form, and a count, side or gap of a 2D form, that its atoms do not
  fix to one value, which the stored parameters and the orientation
  tables over them do.
- A variable that the atoms of two inputs share, other than their head
  terms, is a key column, unless it is a Position that one of the two
  inputs, a position input, shares: the pair of positions is what the
  instance holds.
- A gap of 0 has no `gap` row, and a concat site's axis then has no use.
- A clause whose site stands in a top-level disjunction, or whose site's
  arguments only a top-level disjunction grounds, is one clause per branch
  of that disjunction, each hoisted on its own: the clauses hold what the
  clause holds, as Souffle reads a disjunction. A branch's `=` that binds a
  variable other than the head's to a constant or another variable is
  substituted, so that a gap the branch makes 0 has no `gap` row.
- A site under negation, or one whose axis, count, side or gap is grounded
  through the instance's outputs, is judgment.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from typing import Any

from engine.program import (
    Atom,
    Scope,
    AtomLiteral,
    Comparison,
    ComparisonOperator,
    ConstructorTerm,
    Disjunction,
    NumberTerm,
    Qualifier,
    RecordTerm,
    RecordType,
    RelationName,
    Unit,
    UnitId,
    Variable,
    Wildcard,
)
from arclog_convert import signature
from arclog_convert.libmap.instances import ROOT, Spec, _parse, term_vars

# ---- the instance specs


def _zero_gap(ex, inst) -> bool:
    """The gap input's clauses are the fact 0 alone, or none."""
    cs = ex.inputs(inst, "gap")
    return all(c.body is None and isinstance(c.head.args[-1], NumberTerm) and c.head.args[-1].value == 0
               for c in cs)


def divide2d(by: str):
    def spec(inst, ex):
        unit = inst.type_args[0].text == "Unit"
        ky = "$U()" if unit else "Ky"
        cell = "{x}.cell($U(), P) :- in_cell(P)." if unit else "{x}.cell(Ky, P) :- in_dim(Ky, _, _), in_cell(P)."
        clauses = [cell, f"{{x}}.{by}(Ky, A, N) :- in_dim(Ky, A, N)."]
        if not _zero_gap(ex, inst):
            clauses.append(f"{{x}}.gap({ky}, A, G) :- in_dim({ky}, A, _), in_gap(G).")
        return Spec(".init {x} = Division<{Key}>", {},
                    {"tile(Ky, P, Q, R)": "{x}.tile(Ky, P, Q, R)", "cell(P)": "in_cell(P)",
                     "dim(Ky, A, N)": "in_dim(Ky, A, N)", "gap(G)": "in_gap(G)"},
                    "\n".join(clauses))
    return spec


def axis_frame(inst, ex):
    if inst.type_args[0].text == "Unit":
        return Spec(".init {x} = Frame<Axis>", {},
                    {"cell(Ky, A, P)": "{x}.cell(A, P)", "extent(Ky, A, N)": "in_extent(Ky, A, N)"},
                    "{x}.extent(A, A, N) :- in_extent($U(), A, N).")
    return Spec(".type {x}_axis = [key: {Key}, a: Axis]\n.init {x} = Frame<{x}_axis>", {},
                {"cell(Ky, A, P)": "{x}.cell([Ky, A], P)", "extent(Ky, A, N)": "in_extent(Ky, A, N)"},
                "{x}.extent([Ky, A], A, N) :- in_extent(Ky, A, N).")


def dir_frame(inst, ex):
    return Spec(".init {x}_size = Tally<{Key}, number>\n.init {x}_frame = Frame<{Key}>\n"
                ".decl {x}_pos(key: {Key}, k: number, p: Position)", {},
                {"pos(Ky, K, P)": "{x}_pos(Ky, K, P)", "extent(Ky, N)": "{x}_size.tally(Ky, N)",
                 "dir(D)": "in_dir(D)", "dist_set(Ky, K)": "in_dist_set(Ky, K)"},
                "{x}_size.item(Ky, K) :- in_dist_set(Ky, K).\n"
                "{x}_frame.extent(Ky, A, N) :- in_dir(D), axis_of(D, A), {x}_size.tally(Ky, N).\n"
                "{x}_pos(Ky, K, P) :- {x}_frame.cell(Ky, P), in_dir(D), dist(P, D, K), in_dist_set(Ky, K).")


def dir_pack(inst, ex):
    return Spec(".decl {x}_axis(key: {Key}, a: Axis, b: Box)\n.decl {x}(key: {Key}, b: Box)", {},
                {"box(Ky, B)": "{x}(Ky, B)", "axis_pos(Ky, A, B)": "{x}_axis(Ky, A, B)",
                 "edge(Ky, D, K)": "in_edge(Ky, D, K)"},
                "{x}_axis(Ky, A, B) :- axis_of(D, A), opposite(D, D2), in_edge(Ky, D, K1), in_edge(Ky, D2, K2),"
                " axis_inset(D, K1, K2, B).\n"
                "{x}(Ky, B) :- {x}_axis(Ky, A, B1), perp(A, A2), {x}_axis(Ky, A2, B2), compose(B1, B2, B).",
                moved={"box": "{x}", "axis_pos": "{x}_axis", "edge": "{x}_edge"})


SPECS = {"Divide2D": divide2d("parts"), "Tile2D": divide2d("side"), "AxisFrame": axis_frame,
         "DirFrame": dir_frame, "DirPack": dir_pack}
"""Each component's spec, by the present component's name."""

RUNNABLE = {"DirPack"}
"""The components whose shape holds only present-lib names."""


# ---- the hoist

AXIS = "axis"   # a role: the site's axis argument
FUNCTIONAL = {"axis_of", "perp", "opposite", "diag_axis_of", "diag_opposite", "diag_perp", "dir_of",
              "corner_dir", "turn", "flip_of", "axis_inversion", "rotation", "c4_turn", "d4_inverse"}
"""The orientation tables whose other columns one column fixes."""


@dataclass
class Form:
    comp: str
    position: list[tuple[str, int]]       # each position input, by the site argument it takes
    other: list[tuple[str, list]]          # each other input, by its head: a site argument's index, or AXIS
    outputs: list[int]                     # the site arguments the read gives
    read: str                              # the output the site reads
    read_args: list                        # the read's columns after the key: an argument's index, or "full"
    axis: int | None = None                # the axis argument of an axis form
    gap: int | None = None                 # the gap argument
    single: tuple[int, ...] = ()           # the arguments one value per key must take
    slice_axis: bool = False               # the read's inner position is the axis component


TESTS = frozenset({"inside", "interior", "same_dist", "same_line", "corner_anchor", "slab_anchor", "nearer",
                   "centered"})
"""The inline relations that test their arguments and ground none of them."""


def _forms() -> dict[str, Form]:
    out = {}
    for by, rel in (("parts", ""), ("side", "_by_size")):
        out[f"divide{rel}"] = Form("Division", [("cell", 0)], [(by, [1, 2]), ("gap", [1, 3])], [4, 5],
                                   "tile", [0, 4, "full"], axis=1, gap=3, single=(1,), slice_axis=True)
        out[f"divide{rel}_slab"] = Form("Division", [("cell", 0)], [(by, [1, 2]), ("gap", [1, 3])], [4, 5],
                                        "tile", [0, 4, 5], axis=1, gap=3, single=(1,))
        out[f"divide{rel}_2d"] = Form("Division", [("cell", 0)], [(by, [AXIS, 1]), ("gap", [AXIS, 2])], [3, 4],
                                      "tile", [0, 3, 4], gap=2, single=(1, 2))
    for rel in ("concat", "concat_slab"):
        out[rel] = Form("Tiling", [("outer", 0), ("inner", 1)], [("gap", [2, 3])], [4], "cell", [0, 1, 4],
                        axis=2, gap=3)
    out["concat_2d"] = Form("Tiling", [("outer", 0), ("inner", 1)], [("gap", [AXIS, 2])], [3], "cell", [0, 1, 3],
                            gap=2, single=(2,))
    out["divide_gap"] = Form("ExtentDivisions", [], [("frame", [0])], [], "division", [1, 2, 3, 4])
    return out


FORMS = _forms()
HOISTED = frozenset(FORMS)
SUFFIX = {"Division": "division", "Tiling": "tiling", "ExtentDivisions": "divisions"}


@lru_cache(maxsize=1)
def _lib_inline() -> frozenset[str]:
    from souffle.parser import parse
    names = set()
    for path in (ROOT / "programs" / "lib.dl", signature()):
        prog: Any = parse(path.read_text(), path.parent)
        names |= {r.name for r in prog.relations if not r.scope.components and Qualifier.INLINE in r.qualifiers}
    return frozenset(names)


ORIENTATION = {"Dir": "dir_elem", "Axis": "axis_elem", "DiagDir": "diag_dir_elem", "DiagAxis": "diag_axis_elem",
               "D4": "d4_elem", "C4": "c4_elem", "Dir8": "dir8_elem", "Axis4": "axis4_elem",
               "Sense": "sense_elem", "Sym": "sym_elem"}
"""Each orientation type, a finite set, with the table of its members."""
ELEMS = {v: k for k, v in ORIENTATION.items()}


@lru_cache(maxsize=1)
def _modes() -> dict[str, tuple[list[frozenset[int]], dict[int, str]]]:
    """Each inline relation of the present lib: its modes, the minimal sets
    of columns other than an orientation type's whose binding grounds every
    column under Souffle's reading of its rules, each orientation column
    enumerated over its type; and its orientation columns with their
    types."""
    from itertools import combinations

    from souffle.grounding import _first_ungrounded, _Inline
    from souffle.parser import parse
    path = ROOT / "programs" / "lib.dl"
    prog: Any = parse(path.read_text(), path.parent)
    inline = _Inline(prog)
    out = {}
    for r in prog.relations:
        if r.scope.components or Qualifier.INLINE not in r.qualifiers:
            continue
        xs = [Variable(f"X{i}") for i in range(len(r.columns))]
        orient = {i: c.type.name for i, c in enumerate(r.columns) if c.type.name in ORIENTATION}
        free = [i for i in range(len(r.columns)) if i not in orient]
        modes: list[frozenset[int]] = []
        for k in range(len(free) + 1):
            for cols in combinations(free, k):
                if any(m <= set(cols) for m in modes):
                    continue
                body = [AtomLiteral(Atom(RelationName((), "_bound"), tuple(xs[i] for i in cols), 0), False)] \
                    if cols else []
                body += [AtomLiteral(Atom(RelationName((), ORIENTATION[t]), (xs[i],), 0), False)
                         for i, t in orient.items()]
                body.append(AtomLiteral(Atom(RelationName((), r.name), tuple(xs), 0), False))
                u = Unit(UnitId(0), Scope(()), Atom(RelationName((), "_t"), tuple(xs), 0), tuple(body), None, None)
                if _first_ungrounded(u, inline) is None:
                    modes.append(frozenset(cols))
        out[r.name] = (modes, orient)
    return out


class Judgment(Exception):
    pass


SPLIT = "grounded through the clause's disjunctions or negations"
"""The reason's end where a top-level disjunction may ground the site."""


def _vars(x) -> list[str]:
    return term_vars(x, [])


def _unit_term():
    return ConstructorTerm("U", ())


def _zero(t) -> bool:
    return isinstance(t, NumberTerm) and t.value == 0


def _const(t) -> bool:
    return not _vars(t) and not isinstance(t, Wildcard)


class Hoist:
    def __init__(self, prog, lib, ground: bool = False) -> None:
        from arclog_convert.libmap.box import Types
        self.prog = prog
        self.lib = lib
        self.ground_form = ground
        self.Types = Types
        self.inline = _lib_inline() | {r.name for r in prog.relations if Qualifier.INLINE in r.qualifiers}
        self.next_decl = 1 + max((d.id.index for d in prog.declarations), default=0)
        self.next_unit = 1 + max((u.id.index for u in prog.units), default=0)
        self.judgment: dict[Atom, str] = {}
        self.names: set[tuple[tuple[str, ...], str]] = {(d.scope.components, d.name)
                                                        for d in (*prog.relations, *prog.instances, *prog.types)}

    def did(self):
        from engine.program import DeclId
        self.next_decl += 1
        return DeclId(self.next_decl)

    def uid(self) -> UnitId:
        self.next_unit += 1
        return UnitId(self.next_unit)

    # -- the grounding rule

    def table(self, a: Atom) -> bool:
        return bool(a.relation.instances and a.relation.instances != ("@lib",)) or a.relation.name not in self.inline

    use_modes = False
    local_banned = False
    relaxed_used = False   # a grounding held a banned variable of the key's body alone

    def ground(self, v: str, banned: set[str], project: bool, avoid: frozenset = frozenset()) -> list[int] | None:
        """The body literals that ground v: one stored or derived atom, or an
        inline atom or `=` comparison with the literals that ground its other
        variables; where none does, the same search with the inline lib
        atoms' modes (`ground_by_mode`). With `project`, a stored atom may
        hold a banned variable, which the projection drops."""
        if self.use_modes:
            return self._ground(v, banned, project, avoid)
        g = self._ground(v, banned, project, avoid)
        if g is None:
            self.use_modes = True
            try:
                g = self._ground(v, banned, project, avoid)
            finally:
                self.use_modes = False
        if g is None and project and not self.local_banned:
            # a projection may hold a banned variable that a stored atom grounds:
            # it is a variable of the key's body alone
            self.local_banned = True
            try:
                g = self.ground(v, banned, project, avoid)
            finally:
                self.local_banned = False
            if g is not None:
                self.relaxed_used = True
        return g

    def _ground(self, v: str, banned: set[str], project: bool, avoid: frozenset) -> list[int] | None:
        if v in avoid:
            return None
        for i, lit in self.lits():
            if isinstance(lit, AtomLiteral) and self.table(lit.atom):
                vs = set(_vars(lit.atom.args))
                if v in vs and (project or not vs & banned):
                    return [i]
        for i, lit in self.lits():
            if isinstance(lit, AtomLiteral) and not self.table(lit.atom):
                vs = _vars(lit.atom.args)
                if v not in vs or (not lit.atom.relation.instances and lit.atom.relation.name in TESTS):
                    continue
                others = [w for w in vs if w != v]
            elif isinstance(lit, Comparison) and lit.op == ComparisonOperator.EQ:
                sides = [(lit.lhs, lit.rhs), (lit.rhs, lit.lhs)]
                pick = next((o for s, o in sides if isinstance(s, Variable) and s.name == v), None)
                if pick is None or v in _vars(pick):
                    continue
                others = _vars(pick)
            else:
                continue
            if set(others) & banned and not self.local_banned:
                continue
            need = [i]
            for w in others:
                g = self.ground(w, banned, project, avoid | {v})
                if g is None:
                    break
                need += [j for j in g if j not in need]
            else:
                return need
        return self.ground_by_mode(v, banned, project, avoid) if self.use_modes else None

    def ground_by_mode(self, v: str, banned: set[str], project: bool, avoid: frozenset) -> list[int] | None:
        """The body literals that ground v through an inline lib atom, once
        the variables of one of its modes are grounded; an orientation
        variable of the atom that nothing else grounds is enumerated, and
        the `ground` form adds its elem atom to the body."""
        modes = _modes()
        for i, lit in list(self.lits()):
            if not isinstance(lit, AtomLiteral) or self.table(lit.atom) or lit.atom.relation.instances \
                    or lit.atom.relation.name not in modes:
                continue
            args = lit.atom.args
            if v not in _vars(args):
                continue
            ms, orient = modes[lit.atom.relation.name]
            for m in ms:
                ins = {w for k in m for w in _vars(args[k])}
                if v in ins or ins & banned:
                    continue
                need = [i]
                for w in ins:
                    g = self.ground(w, banned, project, avoid | {v})
                    if g is None:
                        break
                    need += [j for j in g if j not in need]
                else:
                    if self.ground_form:
                        for k, t in orient.items():
                            x = args[k]
                            if isinstance(x, Variable) and self.ground(x.name, banned, project, avoid | {v} | ins) is None:
                                need.append(self.elem(x.name, t))
                    return need
        return None

    def elem(self, v: str, t: str) -> int:
        """The index of the body's elem atom over v, added where the body
        has none."""
        for j, lit in enumerate(self.body):
            if isinstance(lit, AtomLiteral) and not lit.negated and lit.atom.relation == RelationName((), ORIENTATION[t]) \
                    and lit.atom.args == (Variable(v),):
                return j
        self.body.append(AtomLiteral(Atom(RelationName((), ORIENTATION[t]), (Variable(v),), 0), False))
        return len(self.body) - 1

    def elems_dropped(self, units: list[Unit], scope, types) -> list[Unit]:
        """The instance's input clauses less each elem atom over a variable
        that, in every input body that holds the atom, another positive atom
        holds at a column of the elem's type; all of them in the `ground`
        form. The inputs drop it together, so that the bodies keep the
        grounding of a key column they share."""
        if self.ground_form:
            return units

        def elem_var(lit) -> tuple[str, str] | None:
            if isinstance(lit, AtomLiteral) and not lit.negated and not lit.atom.relation.instances \
                    and lit.atom.relation.name in ELEMS and len(lit.atom.args) == 1 \
                    and isinstance(lit.atom.args[0], Variable):
                return lit.atom.args[0].name, ELEMS[lit.atom.relation.name]
            return None

        def redundant(lit, body) -> bool:
            v, t = elem_var(lit) or ("", "")
            return any(o is not lit and isinstance(o, AtomLiteral) and not o.negated and elem_var(o) is None
                       and any(isinstance(x, Variable) and x.name == v and self.type_text(o.atom, k, scope, types) == t
                               for k, x in enumerate(o.atom.args))
                       for o in body)
        keep: set[tuple[str, str]] = set()
        for un in units:
            for lit in un.body or ():
                ev = elem_var(lit)
                if ev is not None and not redundant(lit, un.body):
                    keep.add(ev)
        out = []
        for un in units:
            body = tuple(lit for lit in un.body or () if (ev := elem_var(lit)) is None or ev in keep)
            if un.body and len(body) < len(un.body):
                un = replace(un, body=_singletons(un.head, body, None) or None)
            out.append(un)
        return out

    def closed(self, g: list[int]) -> list[int]:
        """g with each top-level positive literal whose variables g holds:
        the clause's further tests on them."""
        g = list(g)
        while True:
            vs = set(_vars(tuple(self.body[j] for j in g)))
            more = [j for j, lit in self.lits() if j not in g and set(_vars(lit)) and set(_vars(lit)) <= vs]
            if not more:
                return sorted(g)
            g += more

    def lits(self):
        """The top-level positive literals of the clause other than the site."""
        for i, lit in enumerate(self.body):
            if i == self.site_i:
                continue
            if isinstance(lit, AtomLiteral) and not lit.negated:
                yield i, lit
            elif isinstance(lit, Comparison):
                yield i, lit

    def single(self, v: str, key: set[str], avoid: frozenset = frozenset()) -> bool:
        """v takes one value per key: its grounding literals are stored
        parameters, orientation tables and `=` comparisons over a key column,
        a constant, or another such variable."""
        if v in key:
            return True
        if v in avoid:
            return False
        g = self.ground(v, self.banned, False)
        if g is None:
            return False
        for i in g:
            lit = self.body[i]
            if isinstance(lit, AtomLiteral):
                rel = lit.atom.relation
                if rel.instances != ("params",) and not (not rel.instances and rel.name in FUNCTIONAL):
                    return False
            others = [w for w in _vars(lit) if w != v]
            if isinstance(lit, AtomLiteral) and lit.atom.relation.instances == ("params",):
                continue
            if not all(self.single(w, key, avoid | {v}) for w in others):
                return False
        return True

    # -- types

    def var_type(self, u: Unit, v: str, types) -> str | None:
        scope = u.scope.components
        from arclog_convert.libmap.box import atoms
        for a in [u.head, *atoms(u.body or ())]:
            for i, t in enumerate(a.args):
                if isinstance(t, Variable) and t.name == v:
                    ty = types.column(a, i, scope)
                    if ty is not None:
                        return self.type_text(a, i, scope, types) or ty
                if isinstance(t, RecordTerm) and v in _vars(t):
                    ty = self.type_text(a, i, scope, types)
                    got = self.field_type(ty, t, v, scope, types) if ty else None
                    if got:
                        return got
        return None

    def type_text(self, a: Atom, i: int, scope, types) -> str | None:
        """The column's type as the solver names it."""
        rn = a.relation
        if not rn.instances:
            r = next((types.rels[(scope[:k], rn.name)] for k in range(len(scope), -1, -1)
                      if (scope[:k], rn.name) in types.rels), None)
            if r is not None and i < len(r.columns):
                return r.columns[i].type.text
            cols = self.lib.top.get(rn.name)
            return cols[i][1] if cols and i < len(cols) else None
        inst = next((types.insts[(scope[:k], rn.instances[0])] for k in range(len(scope), -1, -1)
                     if (scope[:k], rn.instances[0]) in types.insts), None) if len(rn.instances) == 1 else None
        if rn.instances == ("params",):
            r = types.rels.get((("Params",), rn.name))
            return r.columns[i].type.text if r and i < len(r.columns) else None
        if inst is None or inst.component not in self.lib.comps:
            return None
        tparams, rels = self.lib.relations(inst.component)
        lr = next((r for r in rels if r.name == rn.name), None)
        if lr is None or i >= len(lr.cols):
            return None
        sub = {p: ta.text for p, ta in zip(tparams, inst.type_args)}
        return sub.get(lr.cols[i].type, lr.cols[i].type)

    def field_type(self, ty: str, t: RecordTerm, v: str, scope, types) -> str | None:
        rt = next((types.types[(scope[:k], ty)] for k in range(len(scope), -1, -1)
                   if (scope[:k], ty) in types.types), None)
        if not isinstance(rt, RecordType) or len(rt.fields) != len(t.args):
            return None
        for f, x in zip(rt.fields, t.args):
            if isinstance(x, Variable) and x.name == v:
                return f.type.text
            if isinstance(x, RecordTerm) and v in _vars(x):
                return self.field_type(f.type.text, x, v, scope, types)
        return None

    # -- one site

    def name(self, u: Unit, comp: str) -> str:
        h = u.head.relation
        base = "_".join(h.instances) if h.instances else ("output" if h.name == "out" else h.name)
        base = base.replace("@lib_", "")
        n, name = 2, f"{base}_{SUFFIX[comp]}"
        while (u.scope.components, name) in self.names or any(
                (u.scope.components[:k], name) in self.names for k in range(len(u.scope.components))):
            name, n = f"{base}_{SUFFIX[comp]}{n}", n + 1
        self.names.add((u.scope.components, name))
        return name

    def fresh(self, base: str, taken: set[str]) -> str:
        n, w = 2, base
        while w in taken:
            w, n = f"{base}{n}", n + 1
        taken.add(w)
        return w

    def site(self, u: Unit, i: int, types):
        """The clause with its site i hoisted, and the instance's new
        declarations and clauses."""
        self.body: list[Any] = list(u.body or ())
        self.site_i = i
        self.relaxed_used = False
        a = self.body[i].atom
        form = FORMS[a.relation.name]
        args: list[Any] = list(a.args)
        taken = set(_vars((u.head, u.body)))
        out_vars = {w for k in form.outputs for w in _vars(args[k])}
        pos_vars = {w for _, k in form.position for w in _vars(args[k])}
        for k in range(len(args)):
            t = args[k]
            if not isinstance(t, (Variable, Wildcard)) and not _const(t):
                raise Judgment(f"{a.relation.name}: an argument is a compound term")
        gap_zero = form.gap is not None and _zero(args[form.gap])
        # the other inputs: each head, and the literals that ground it
        ax = self.fresh("A", taken) if any(AXIS in h for _, h in form.other) else None
        others = []
        proj_roles: set[str] = set()   # a role grounded through a position: a key column
        for inp, head in form.other:
            if inp == "gap" and gap_zero:
                continue
            terms, groups, proj = [], [], []
            for h in head:
                t = Variable(str(ax)) if h == AXIS else args[h]
                terms.append(t)
                if h != AXIS and isinstance(t, Variable):
                    g = self.ground(t.name, out_vars | pos_vars, False)
                    if g is not None:
                        g = self.closed(g)
                        groups += [j for j in g if j not in groups]
                        continue
                    g = self.ground(t.name, out_vars, True)
                    if g is None:
                        raise Judgment(f"{a.relation.name}: {t.name} is "
                                       + ("grounded through the outputs" if self.ground(t.name, set(), True)
                                          is not None else SPLIT))
                    proj += [j for j in g if j not in proj]
                    proj_roles.add(t.name)
            others.append((inp, terms, groups, proj))
        self.banned = out_vars | pos_vars
        nc = sorted({j for _, _, g, _ in others for j in g})
        # the position inputs: each projected group
        positions = []
        for inp, k in form.position:
            t = args[k]
            g = []
            if isinstance(t, Variable):
                g = self.ground(t.name, out_vars, True)
                if g is None:
                    raise Judgment(f"{a.relation.name}: {t.name} is {SPLIT}")
                g = self.closed(g)
            positions.append((inp, t, g))
        # the key
        read_extra = {args[int(form.axis or 0)].name} if form.slice_axis and isinstance(args[int(form.axis or 0)], Variable) \
            and not isinstance(args[5], Wildcard) else set()
        rest = [lit for j, lit in enumerate(self.body) if j != i and j not in nc]
        rest_vars = set(_vars(u.head)) | set(_vars(tuple(rest))) | read_extra
        nc_vars = set(_vars(tuple(self.body[j] for j in nc))) | {w for _, ts, _, _ in others for w in _vars(tuple(ts))}
        if ax:
            nc_vars.discard(ax)
        key = ((nc_vars & rest_vars) | proj_roles) - out_vars - pos_vars
        shared = set()   # a variable two inputs' literals share, and not both heads
        every = [(ts, g, False) for _, ts, g, _ in others] + [((t,), g, True) for _, t, g in positions]
        for x, (ts1, g1, p1) in enumerate(every):
            for ts2, g2, p2 in every[x + 1:]:
                v1 = set(_vars(tuple(self.body[j] for j in g1)))
                v2 = set(_vars(tuple(self.body[j] for j in g2)))
                h = set(_vars(tuple(ts1))) & set(_vars(tuple(ts2)))
                found = (v1 & v2) - h
                if p1 or p2:   # a position that two position inputs share pairs them, and keys nothing
                    found = {w for w in found if self.var_type(u, w, types) != "Position"}
                shared |= found
        while True:
            checked = (*form.single, *((form.axis,) if form.comp == "Division" and form.axis is not None else ()))
            more = {args[k].name for k in checked
                    if isinstance(args[k], Variable) and args[k].name not in key
                    and not (form.comp == "Tiling" and k == form.axis)
                    and not self.single(args[k].name, key)}
            more |= {w for w in shared if w not in key and not self.single(w, key)}
            more -= out_vars | pos_vars
            if not more:
                break
            key |= more
        order = [w for w in _vars((u.head, tuple(self.body))) if w in key]
        scope = u.scope.components
        if not order:
            kt, ktype, decls = _unit_term(), "Unit", []
        else:
            tys = [self.var_type(u, w, types) for w in order]
            if any(t is None for t in tys):
                raise Judgment(f"{a.relation.name}: the type of key column {order[tys.index(None)]} is unknown")
            if len(order) == 1:
                kt, ktype, decls = Variable(order[0]), tys[0], []
            else:
                kt, ktype, decls = RecordTerm(tuple(Variable(w) for w in order)), None, []
        x = self.name(u, form.comp)
        if ktype is None:
            ktype = f"{x}_key"
            fields = ", ".join(f"{w.lower()}: {t}" for w, t in zip(order, tys))
            decls.append(f".type {ktype} = [{fields}]")
        decls.append(f".init {x} = {form.comp}<{ktype}>")
        # the input clauses
        new_units = []

        def keyed(body_idx: list[int], project_keep: set[str] | None, extra: list, proj: Any = ()) -> tuple:
            """The input's body: its literals, a projection where
            `project_keep` names the variables to keep, or of the literals
            `proj` names, and the literals that ground each key column the
            body lacks."""
            proj = list(proj)
            idx = list(body_idx) + [j for j in proj if j not in body_idx]
            have = set(_vars(tuple(self.body[j] for j in idx)))
            for w in order:
                if w not in have:
                    g = self.ground(w, out_vars | (pos_vars if project_keep is None else set()), True)
                    if g is None and project_keep is None:
                        g = self.ground(w, out_vars, True)
                        proj += [j for j in g or () if j not in proj]
                    if g is None:
                        raise Judgment(f"{a.relation.name}: key column {w} is {SPLIT}")
                    g = self.closed(g)
                    idx += [j for j in g if j not in idx]
                    have |= set(_vars(tuple(self.body[j] for j in g)))
            idx.sort()
            loc = self.relaxed_used
            if project_keep is not None:
                lits = [project(self.body[j], project_keep | set(order) | needed(idx), loc) for j in idx]
            else:
                whole = set(_vars(tuple(self.body[j] for j in idx if j not in proj or j in body_idx)))
                keep = whole | set(order) | needed(idx) | set(_vars(tuple(extra)))
                lits = [self.body[j] if j not in proj or j in body_idx else project(self.body[j], keep, loc)
                        for j in idx]
            return tuple(extra) + tuple(lits)

        def needed(idx: list[int]) -> set[str]:
            """The variables a projection keeps: those of inline atoms and
            comparisons, and those two literals share."""
            out, seen = set(), {}
            for j in idx:
                lit = self.body[j]
                vs = set(_vars(lit))
                if not (isinstance(lit, AtomLiteral) and self.table(lit.atom)):
                    out |= vs
                for w in vs:
                    seen[w] = seen.get(w, 0) + 1
            return out | {w for w, n in seen.items() if n > 1}

        def project(lit, keep: set[str], local: bool = False):
            """`local`: an input's body keeps a banned variable that it holds
            in more than one literal."""
            if not isinstance(lit, AtomLiteral):
                return lit
            args2 = tuple(t if not isinstance(t, Variable) or (t.name in keep and (local or t.name not in out_vars))
                          else Wildcard() for t in lit.atom.args)
            return AtomLiteral(Atom(lit.atom.relation, args2, lit.atom.line), lit.negated)

        exact: dict[int, str | None] = {}   # a position input's literal its projection keeps whole, by input
        for inp, t, g in positions:
            keep = set(_vars(t))
            body = keyed(g, keep, [])
            for j in g:
                if project(self.body[j], keep | set(order) | needed(g)) == self.body[j]:
                    exact.setdefault(j, inp)
                else:
                    exact[j] = None
            new_units.append(self.input(u, x, inp, [kt, t], body))
        for inp, terms, g, proj in others:
            extra = [AtomLiteral(Atom(RelationName((), "axis_elem"), (Variable(str(ax)),), 0), False)] \
                if any(isinstance(t, Variable) and t.name == ax for t in terms) else []
            new_units.append(self.input(u, x, inp, [kt, *terms], keyed(g, None, extra, self.closed(proj) if proj else proj)))
            keep = set(_vars(tuple(terms))) | set(_vars(tuple(self.body[j] for j in g)))
            for j in proj:
                if j in nc:
                    continue
                if project(self.body[j], keep | set(order) | needed(sorted(set(g) | set(proj)))) == self.body[j]:
                    exact.setdefault(j, inp)
                else:
                    exact[j] = None
        # the clause: the read in place of the site, less the literals the instance now holds
        dropped = set(nc)
        cand = {j for j, inp in exact.items() if inp is not None and j not in nc}
        carried = out_vars | pos_vars | key
        while True:
            kept = [lit for j, lit in enumerate(self.body) if j != i and j not in dropped and j not in cand]
            outside = set(_vars(u.head)) | set(_vars(tuple(kept))) | read_extra
            bad = {j for j in cand if any(w in outside and w not in carried for w in _vars(self.body[j]))}
            for j in cand:   # a variable two inputs' literals share
                for k2 in cand:
                    if k2 != j and exact[j] != exact[k2] and \
                            (set(_vars(self.body[j])) & set(_vars(self.body[k2]))) - carried:
                        bad.add(j)
            if not bad:
                break
            cand -= bad
        dropped |= cand
        read_terms = []
        full: Any = None
        for r in form.read_args:
            if r == "full":
                full = Variable(self.fresh("P_slab", taken)) if not isinstance(args[5], Wildcard) else Wildcard()
                read_terms.append(full)
            else:
                read_terms.append(args[r])
        read = [AtomLiteral(Atom(RelationName((x,), form.read), (kt, *read_terms), a.line), False)]
        if form.slice_axis and not isinstance(args[5], Wildcard):
            read.append(AtomLiteral(Atom(RelationName((), "split"), (full, args[int(form.axis or 0)], args[5], Wildcard()),
                                         a.line), False))
        body = []
        at = min(dropped | {i})   # the read binds what the literals it replaces bound, where they stood
        for j, lit in enumerate(self.body):
            if j == at:
                body += read
            if j != i and j not in dropped:
                body.append(lit)
        clause = replace(u, body=_singletons(u.head, tuple(body), u))
        return clause, decls, self.elems_dropped(new_units, u.scope.components, types)

    def input(self, u: Unit, x: str, inp: str, head: list, body: tuple) -> Unit:
        head_atom = Atom(RelationName((x,), inp), tuple(head), 0)
        b = _singletons(head_atom, body, None) if body else None
        return Unit(self.uid(), u.scope, head_atom, b or None, None, None)

    def run(self):
        prog = self.prog
        own = lambda x: x.span is None or x.span.file is None  # noqa: E731
        units = list(prog.units)
        types_, rels, insts = list(prog.types), list(prog.relations), list(prog.instances)
        out = []
        changed = False
        for u0 in units:
            if not own(u0) or not u0.body:
                out.append(u0)
                continue
            work = [u0]
            while work:
                u = work.pop(0)
                while True:
                    site = self.next_site(u)
                    if site is None:
                        break
                    if isinstance(site, tuple):   # a site inside a top-level disjunction
                        work[0:0] = self.split(u, site[1])
                        changed = True
                        u = None
                        break
                    prog_now = replace(prog, types=tuple(types_), relations=tuple(rels), instances=tuple(insts))
                    try:
                        u2, decls, new = self.site(u, site, self.Types(prog_now, self.lib))
                    except Judgment as e:
                        lit: Any = (u.body or ())[site]
                        d = self.grounding_disjunction(u, site) if e.args and e.args[0].endswith(SPLIT) else None
                        if d is not None:
                            work[0:0] = self.split(u, d)
                            changed = True
                            u = None
                            break
                        self.judgment[lit.atom] = str(e)
                        self.skip.add((u.id.index, id(lit)))
                        continue
                    changed = True
                    d: Any = _parse("\n".join(decls))
                    for t in d.types:
                        types_.append(replace(t, id=self.did(), scope=u.scope))
                    for inst in d.instances:
                        insts.append(replace(inst, id=self.did(), scope=u.scope, span=None))
                    out += new
                    u = u2
                if u is not None:
                    out.append(u)
        if not changed:
            return prog, self.judgment
        return replace(prog, types=tuple(types_), relations=tuple(rels), instances=tuple(insts),
                       units=tuple(out)), self.judgment

    skip: set[tuple[int, int]] = set()

    def split(self, u: Unit, j: int) -> list[Unit]:
        """The clause as one clause per branch of its top-level disjunction j,
        the branch's literals in the disjunction's place."""
        from arclog_convert.libmap.instances import subst
        body = list(u.body or ())
        d = body[j]
        assert isinstance(d, Disjunction)
        head_vars = set(_vars(u.head))
        out = []
        for k, b in enumerate(d.branches):
            m: dict[str, Any] = {}
            kept = []
            for lit in b:
                got = self.equated(lit, head_vars) if isinstance(lit, Comparison) else None
                if got is None or got[0] in m:
                    kept.append(lit)
                else:
                    m[got[0]] = got[1]
            nb = tuple(body[:j]) + tuple(kept) + tuple(body[j + 1:])
            head = u.head
            if m:
                nb, head = subst(nb, m), subst(u.head, m)
            out.append(replace(u, id=self.uid() if k else u.id, head=head, body=nb))
        return out

    @staticmethod
    def equated(lit: Comparison, head_vars: set[str]) -> tuple[str, Any] | None:
        """The variable a branch's `=` binds and the term it takes, where the
        variable is not the head's: a constant, or another variable."""
        if lit.op != ComparisonOperator.EQ:
            return None
        for x, y in ((lit.lhs, lit.rhs), (lit.rhs, lit.lhs)):
            if isinstance(x, Variable) and x.name not in head_vars and (isinstance(y, Variable) or _const(y)) \
                    and x.name not in _vars(y):
                return x.name, y
        return None

    def grounding_disjunction(self, u: Unit, site: int) -> int | None:
        """The first top-level disjunction that holds a variable the site's
        arguments reach through the clause's other top-level literals."""
        body = list(u.body or ())
        reach = set(_vars(body[site]))
        while True:
            more = set()
            for j, lit in enumerate(body):
                if j != site and not isinstance(lit, Disjunction) and set(_vars(lit)) & reach:
                    more |= set(_vars(lit))
            if more <= reach:
                break
            reach |= more
        return next((j for j, lit in enumerate(body) if isinstance(lit, Disjunction) and set(_vars(lit)) & reach), None)

    def next_site(self, u: Unit) -> int | tuple[str, int] | None:
        """The first site of the clause the pass has not tried, at the top
        level, or `("split", j)` for a top-level disjunction j that holds
        one; a negated site is judgment."""
        from arclog_convert.libmap.box import atoms
        for j, lit in enumerate(u.body or ()):
            if (u.id.index, id(lit)) in self.skip:
                continue
            if isinstance(lit, AtomLiteral) and not lit.atom.relation.instances and lit.atom.relation.name in FORMS:
                if lit.negated:
                    self.judgment[lit.atom] = f"{lit.atom.relation.name}: a negated site"
                    self.skip.add((u.id.index, id(lit)))
                    continue
                return j
            if isinstance(lit, Disjunction):
                if any(not b.relation.instances and b.relation.name in FORMS for b in atoms(lit)):
                    return ("split", j)
        return None


def _singletons(head: Atom, body: tuple, before: Unit | None) -> tuple:
    """The body with each variable that occurs once in the clause, and more
    than once in `before` where it is given, read as `_`."""
    from arclog_convert.libmap.box import mapped
    from arclog_convert.libmap.instances import _vars_all
    counts: dict[str, int] = {}
    for w in _vars_all((head, body)):
        counts[w] = counts.get(w, 0) + 1
    was: dict[str, int] = {}
    if before is not None:
        for w in _vars_all((before.head, before.body)):
            was[w] = was.get(w, 0) + 1
    lone = {w for w, n in counts.items() if n == 1 and (before is None or was.get(w, 0) > 1)}
    if not lone:
        return body

    def fn(a: Atom) -> Atom:
        return Atom(a.relation, tuple(_wild(t, lone) for t in a.args), a.line)
    return tuple(mapped(lit, fn) if isinstance(lit, (AtomLiteral, Disjunction)) else lit for lit in body)


def _wild(t, lone: set[str]):
    if isinstance(t, Variable) and t.name in lone:
        return Wildcard()
    if isinstance(t, RecordTerm):
        return RecordTerm(tuple(_wild(x, lone) for x in t.args))
    if isinstance(t, ConstructorTerm):
        return ConstructorTerm(t.name, tuple(_wild(x, lone) for x in t.args))
    return t


def hoist(prog, lib, ground: bool = False):
    """The program with each division, concat and `divide_gap` site hoisted
    into its instance, and each site left in place, with the reason. With
    `ground`, the inputs hold the elem atoms the Souffle engine needs."""
    h = Hoist(prog, lib, ground)
    h.skip = set()
    return h.run()
