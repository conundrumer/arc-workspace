"""The part of `Solver` that plans the frames and the fields, and orders and
writes the parameters."""

from __future__ import annotations

import re
from engine.program import (
    Atom,
    AtomLiteral,
    ConstructorTerm,
    DefinedName,
    RigidCall,
    NumberTerm,
    RecordTerm,
    Unit,
    Variable,
    Wildcard,
)
from souffle.printer import term as souffle_term
from arclog_convert.literals import collect_vars
from solver.vocabulary import order_pairs
from arclog_convert.frame_reads import (
    FRAME_SUFFIX,
    INNER_SUFFIX,
    OUTER_SUFFIX,
    TILING_SUFFIX,
    Extent,
    FieldPlan,
    FrameRead,
    SingleAxisExtent,
    SquareExtent,
    helpers_read,
)
from arclog_convert import paths

from arclog_convert.clauses import ClauseWriter
from arclog_convert.forms import (
    Form,
    close,
    derived_param,
    directives,
    head_renames,
    mark_key,
    params_to_amp,
    quote,
)
from arclog_convert.leaves import Written
from arclog_convert.lib import KeyedTable, PROPOSER_COLS, keyed_row, pascal, takes_set_mark, require_exact_set
from arclog_convert.terms import name_of


def column_site(column: str, label: str) -> str:
    """The site of the column `column` that reads `label`, `label` alone where
    it is the column's name (`docs/arclog/arclog.md#sites`)."""
    return label if label.lstrip("*^") == column else f"(:{column} {label})"


def atom(relation: str, sites: list[str]) -> str:
    """The atom of `relation` with `sites`."""
    return "(" + " ".join([relation, *sites]) + ")"


def or_of(bodies: list[str]) -> str:
    """The body that holds each of `bodies`, a list of atoms, as the branches
    of an `OR`, or that body alone where there is one."""
    return bodies[0] if len(bodies) == 1 else "(OR " + " ".join(f"({b})" for b in bodies) + ")"


def nest(opening: str, lines: list[str]) -> list[str]:
    """The form that `opening` opens, with `lines` inside it, closed."""
    out = [opening, *("  " + x for x in lines)]
    close(out, ")")
    return out


class ParamsMixin:
    """The plans of a solver's frames and fields, its parameter order and its parameter lines."""

    def helper_derivation(self, amp: str, units: list[Unit], rows: list[list[str]]) -> tuple[str | None, str | None]:
        """The derivation that gives a table the helpers derive, by the
        converter's name for it, or None where the table's clauses read no
        tile or frame of the helpers or its rows are no derivation's; and
        the `param` form `derived_param` gives the table."""
        reads = [l for u in units for l in u.body or ()
                 if isinstance(l, AtomLiteral) and l.atom.relation.instances == ("helpers",)]
        # a decomposition cut by separator lines, or into touching tiles: SepTiles
        if any(l.atom.relation.name == "tile_pos" for l in reads):
            prop = "SepTiles"
        elif any(l.atom.relation.name == "frame_pos" for l in reads):
            prop = "Frame2D"
        else:
            prop = None
        record = derived_param(amp, rows, prop)
        return (prop if record is not None else None), record

    def frame_plan(self, us: list[Unit]):
        """(component, binders, rest) where the clauses read one
        `helpers.frame_pos` each: a square frame of a label's extent, one
        clause, as Frame2D; or a 1-wide frame along each axis, one clause per
        axis that names the axis in its head, as AxisFrame. None otherwise."""
        def split_unit(u):
            h = helpers_read(u)
            if h is None:
                return None
            a = u.body[h].atom
            if a.relation.name != "frame_pos" or not isinstance(a.args[0], RecordTerm) \
                    or len(a.args[0].args) != 2 or not isinstance(a.args[1], Variable):
                return None
            return h, list(a.args[0].args), a.args[1].name
        parts = [split_unit(u) for u in us]
        if not us or any(x is None for x in parts):
            return None

        def binders(u, i, n):
            rest = [l for j, l in enumerate(u.body) if j != i]
            bs = []
            for l in rest:
                vs: set[str] = set()
                collect_vars([l], vs)
                if isinstance(l, AtomLiteral) and not l.negated and vs == {n}:
                    bs.append(l)
            return bs, [l for l in rest if not any(l is b for b in bs)]
        if len(us) == 1:
            i, (x, y), p = parts[0]
            if isinstance(x, Variable) and isinstance(y, Variable) and x.name == y.name and x.name != p:
                bs, rest = binders(us[0], i, x.name)
                if bs:
                    return ("Frame2D", [(us[0], x.name, p, bs, rest)], None)
            return None
        if len(us) != 2:
            return None
        got = []
        for u, (i, (x, y), p) in zip(us, parts):
            one = [t for t in (x, y) if isinstance(t, NumberTerm) and t.value == 1]
            var = [t for t in (x, y) if isinstance(t, Variable)]
            if len(one) != 1 or len(var) != 1:
                return None
            axis = "AXIS_V" if isinstance(x, Variable) else "AXIS_H"
            heads = [k for k, t in enumerate(u.head.args) if isinstance(t, DefinedName) and t.name == axis]
            if len(heads) != 1:
                return None
            bs, rest = binders(u, i, var[0].name)
            if not bs:
                return None
            got.append((u, var[0].name, p, bs, rest, heads[0], axis))
        if {g[6] for g in got} != {"AXIS_V", "AXIS_H"} or got[0][5] != got[1][5]:
            return None
        return ("AxisFrame", got, got[0][5])

    def frame_forms(self, r, plan) -> list[Form]:
        """The instance that makes the frame, and the table's clause over its
        cells."""
        c = self.c
        comp, units, axis_col = plan
        amp = c.rel_name(("Params",), r.name)
        # the frame stands for the `helpers` instance whose `frame_pos` the clauses read
        c.made[(("Params",), r.name + "_frame")] = (Written(("Params",), "helpers", True),)
        inst = c.rel_name(("Params",), r.name + "_frame")
        c.wrote(f"{inst}.cell", Written(("Params",), "helpers.frame_pos", False))
        u, n, p, bs, rest = units[0][:5]
        cols = [pascal(col.name) for col in r.columns]
        ren = head_renames(u, r)
        N, P = ren.get(n, n), ren.get(p, p)
        A = cols[axis_col] if axis_col is not None else "A"
        taken = {N, P}
        while A in taken:
            A += "2"
        w = ClauseWriter(c, ("Params",), {}, ren)
        key = mark_key(w.lits(bs, set()), [N])
        reads = set(w.reads)
        # a 1-wide frame along each axis: a Frame keyed by the extent and the axis
        axis = comp == "AxisFrame"
        if axis:
            key.append(f"(axis_elem ^{A})")
        lines = [f"(INIT {inst} {'Frame' if axis else comp}"]
        lead = "  (key ("
        lines.append(lead + key[0])
        lines.extend(" " * len(lead) + l for l in key[1:])
        close(lines, ")" + ("))" if axis else ""))
        if not axis:
            lines.extend([f"    (extent ({A} {N})", f"      (axis_elem *{A}))))"])
        f1 = Form(lines, inst, reads, line=r.span.first if r.span else 0)
        w2 = ClauseWriter(c, ("Params",), {}, ren)
        cell = f"({inst}.cell (:key *{N} *{A}) *{P})" if axis else f"({inst}.cell (:key *{N}) *{P})"
        body = [cell] + w2.lits(rest, {N, P, A} if comp == "AxisFrame" else {N, P})
        dl = [f"(DET {amp}"] + ["  " + l for l in body]
        close(dl, ")")
        f2 = Form(dl, amp, set(w2.reads) | {inst}, line=r.span.first if r.span else 0)
        cm = self.comments_above(r.span.first) if r.span else []
        gloss = " ".join(t for d, t, _ in directives(cm) if d == "")
        f2.comments = [f";; {params_to_amp(gloss)}"] if gloss else []
        return [f1, f2]

    def field_forms(self, r, plan: FieldPlan) -> list[Form]:
        """The frame instance of each extent of the plan's read, the Tiling
        instance over the outer and the inner frame where it reads a tiled
        frame, and the table's DET over the cells; each extent reads the
        DETs of its parameters."""
        c = self.c
        u = plan.unit
        line = r.span.first if r.span else 0
        amp = c.rel_name(("Params",), r.name)
        forms: list[Form] = []
        instances, units = plan.souffle(r.name)
        c.plan_instances.update({(inst.scope.components, inst.name): inst for inst in instances})
        c.plan_units.extend(units)

        def instance(suffix: str) -> str:
            # each instance stands for the `helpers` instance the clause reads
            c.made[(("Params",), r.name + suffix)] = (Written(("Params",), "helpers", True),)
            return c.rel_name(("Params",), r.name + suffix)

        def extent(ext: Extent, value: str) -> tuple[list[str], set[str]]:
            # the rows (A <value>) of the extent, an axis and its value on that axis
            if isinstance(ext, (SquareExtent, SingleAxisExtent)):
                w = ClauseWriter(c, ("Params",), {}, {ext.label: value})
                if isinstance(ext, SquareExtent):
                    return ["(axis_elem *A)", *w.lits(ext.atoms, {"A"})], set(w.reads)
                # the axis the parameter holds; a Frame gives the other axis the extent 1
                at = Atom(ext.axis.atom.relation, (Variable("A"),), 0)
                return w.lits([AtomLiteral(at, False), *ext.atoms], set()), set(w.reads)
            w = ClauseWriter(c, ("Params",), {}, {})
            at = Atom(ext.atoms[0].atom.relation, (Variable("A"), Variable(value)), 0)
            return w.lits([AtomLiteral(at, False)], set()), set(w.reads)

        def frame(suffix: str, ext: Extent) -> str:
            inst = instance(suffix)
            body, reads = extent(ext, "N")
            lines = [f"(INIT {inst} Frame2D", "  (extent (A N)", *("    " + l for l in body)]
            close(lines, "))")
            forms.append(Form(lines, inst, reads, line=line))
            return inst

        if isinstance(plan.read, FrameRead):
            inst = frame(FRAME_SUFFIX, plan.read.extent)
            c.wrote(f"{inst}.cell", Written(("Params",), "helpers.frame_pos", False))
            read, cells = f"{inst}.cell", [("P", plan.read.cell)]
        else:
            outer, inner = frame(OUTER_SUFFIX, plan.read.outer), frame(INNER_SUFFIX, plan.read.inner)
            inst = instance(TILING_SUFFIX)
            lines = [f"(INIT {inst} Tiling", "  (outer (P)", f"    ({outer}.cell *P))",
                     "  (inner (P)", f"    ({inner}.cell *P))"]
            reads = {outer, inner}
            if plan.read.gap is not None:
                body, got = extent(plan.read.gap, "G")
                lines += ["  (gap (A G)", *("    " + l for l in body)]
                reads |= got
            close(lines, "))" if plan.read.gap is not None else ")")
            forms.append(Form(lines, inst, reads, line=line))
            c.wrote(f"{inst}.cell", Written(("Params",), "helpers.tile_pos", False))
            read = f"{inst}.cell"
            cells = list(zip(("P", "P_outer", "P_inner"), plan.read.cells))
        w = ClauseWriter(c, ("Params",), {}, head_renames(u, r))
        bound: set[str] = set()
        sites = []
        for col, t in cells:
            if isinstance(t, Wildcard):
                continue
            label = w.label(t.name)
            mark = "" if label in bound else "*"
            bound.add(label)
            sites.append(mark + label if label == col else f"(:{col} {mark}{label})")
        dl = [f"(DET {amp}", f"  ({read} {' '.join(sites)})", *("  " + l for l in w.lits(plan.rest, bound))]
        close(dl, ")")
        f = Form(dl, amp, set(w.reads) | {inst}, line=line)
        cm = self.comments_above(r.span.first) if r.span else []
        gloss = " ".join(t for d, t, _ in directives(cm) if d == "")
        f.comments = [f";; {params_to_amp(gloss)}"] if gloss else []
        return [*forms, f]

    def plan(self) -> dict[str, tuple[str, ...]]:
        """The determination plan's verdict on each parameter, from its
        output under plan/: ("covered", proposer, verdict),
        ("overlimit", candidate count, proposer, verdict), ("write",),
        ("determined",), or ("undecided",)."""
        if hasattr(self, "_plan"):
            return self._plan
        out: dict[str, tuple[str, ...]] = {}
        p = paths.PLANS / f"{self.stem}.txt"
        section = None
        if p.exists():
            for line in p.read_text().splitlines():
                if not line.startswith("  "):
                    section = ("covered" if line.startswith("the value is covered") else
                               "overlimit" if line.startswith("over the enumeration limit") else
                               "write" if line.startswith("write a determination") else
                               "determined" if line.startswith("determined") else
                               "undecided" if line.startswith("undecided") else None)
                    continue
                if section is None:
                    continue
                if section == "overlimit":
                    m2 = re.match(r"\s+(\w+)\((\d+)\) \((\S+) (\S+)\)", line)
                    if m2:
                        out.setdefault(m2.group(1), ("overlimit", *m2.groups()[1:]))
                    continue
                m = re.match(r"\s+(\S+)(?:\s+\((\S+?)[ )](.*))?", line)
                if not m:
                    continue
                name = m.group(1).split("@")[0]
                if section == "covered" and m.group(2):
                    out.setdefault(name, ("covered", m.group(2).rstrip(","), (m.group(3) or "").rstrip(")")))
                else:
                    out.setdefault(name, (section,))
        self._plan = out
        return out

    # ---- param lines

    def set_param_order(self, amp: str, r, made: list[Form]) -> None:
        """Record the order of the columns of the `param` of `r`, whose `DET`
        the forms `made` write: the order of the first `*` mark of each
        column's labels in the body, as the engine makes the `DET`'s columns.
        A parameter none of whose forms is a `DET` keeps the relation's
        order, and so does a form that holds an unresolved atom, which the
        text writes as the source reads it, with no mark at its columns."""
        orders = [self.column_order(r, f) for f in made
                  if f.side == "DET" and not any(c.startswith(";; TODO unresolved:") for c in f.comments)]
        if not orders:
            return
        if any(o != orders[0] for o in orders):
            raise ValueError(f"{amp}: its DET forms make their columns in different orders")
        if orders[0] != list(range(len(r.columns))):
            self.param_order[amp] = orders[0]

    @staticmethod
    def column_order(r, f: Form) -> list[int]:
        """The indices of `r`'s columns in the order the body of `f` makes
        their labels. A column with no label (a case or dropped column)
        keeps its place."""
        if len(f.col_labels) != len(r.columns):
            raise ValueError(f"{f.name}: the head gives {len(f.col_labels)} columns for the {len(r.columns)} of {r.name}")
        first: dict[str, int] = {}
        for i, m in enumerate(re.finditer(r"\*(\w+)", "\n".join(f.body or []))):
            first.setdefault(m.group(1), i)
        missing = [x for labels in f.col_labels for x in labels if x not in first]
        if missing:
            raise ValueError(f"{f.name}: no mark makes the labels {missing}")
        labelled = [i for i, labels in enumerate(f.col_labels) if labels]
        by_mark = sorted(labelled, key=lambda i: min(first[x] for x in f.col_labels[i]))
        order = list(range(len(r.columns)))
        for slot, i in zip(labelled, by_mark):
            order[slot] = i
        return order

    def ordered(self, amp: str, seq) -> list:
        """`seq`, one item per column of the parameter `amp` in its relation's
        order, in the order of the parameter's record."""
        order = self.param_order.get(amp)
        return list(seq) if order is None else [seq[i] for i in order]

    def grid_rows(self, g, r) -> list[list[str]]:
        """The rows, in the relation's order, that the grid call `g` of `r`
        states: for each cell that holds a value, the values before the
        position, the cell's position in the grid's frame, or, in a grid with
        an anchor, its offset from the anchor cell, and its value where the
        layout gives one."""
        pi = next((i for i, col in enumerate(r.columns) if col.type.name in ("Position", "Offset")), None)
        if pi is None or len(g.keys) != pi:
            raise ValueError(f"{r.name}: a grid call that no row form states")
        h, w = len(g.cells), len(g.cells[0])
        anchor = g.anchor
        rows = []
        for i, line in enumerate(g.cells):
            for j, cell in enumerate(line):
                text = souffle_term(cell.term)
                if text == "_":
                    continue
                if anchor is None:
                    place = f"({i} {h - 1 - i} {j} {w - 1 - j})"
                else:
                    di, dj = i - anchor[0], j - anchor[1]
                    place = f"({di} {-di} {dj} {-dj})"
                rows.append([*(self.value_text(k) for k in g.keys), place, *([text] if g.layout.valued else [])])
        return rows

    def param_rows(self, amp, r, facts, grids) -> tuple[list[str], list]:
        """The rows of `r`'s `param` form, with no column of an open type,
        each once, and the grids that stand as `grid` rows of their own."""
        kept = self.ordered(amp, [col.type.name not in self.c.open_types for col in r.columns])
        rows = list(dict.fromkeys(
            "(" + " ".join(self.value_text(a) for a, k in zip(self.ordered(amp, u.head.args), kept) if k) + ")"
            for u in facts))
        if amp in self.param_order:
            rows.extend(dict.fromkeys(
                "(" + " ".join(v for v, k in zip(self.ordered(amp, row), kept) if k) + ")"
                for g in grids for row in self.grid_rows(g, r)))
            grids = []
        return rows, grids

    def set_mark(self, amp, r, props, facts, grids) -> str:
        """` (SET)` for a `DET` or `DET_OR_RULE` of `r` with no body, by
        `props`, where each proposer has one column and is no type-domain
        proposer, and the parameter's `param` form holds several rows with
        an exact proposer verdict. Coverage alone raises a checked error:
        row count cannot establish equality with the proposer's whole set.
        Returns the empty string where no set mark is needed."""
        if not props or not all(takes_set_mark(p) for p in props):
            return ""
        rows, grids = self.param_rows(amp, r, facts, grids)
        if len(rows) + len(grids) <= 1:
            return ""
        # All callers (ordinary, rigid part, and @derive) use this checked
        # boundary. Cardinality never proves proposer-set equality.
        parameter = r.name.removeprefix("_rigid_")
        require_exact_set(amp, props, self.plan().get(parameter))
        return " (SET)"

    def param_line(self, amp, r, facts, grids) -> str:
        """The `param` form of `r`'s stored rows, with no column of an open
        type, each row once, the values of a row in the order of
        `Solver.ordered`."""
        rows, grids = self.param_rows(amp, r, facts, grids)
        if not grids:
            return f"(param {amp} " + " ".join(rows) + ")"
        lines = [f"(param {amp}"] + ["  " + r for r in rows]
        for g in grids:
            keys = "".join(self.value_text(k) + " " for k in g.keys)
            lines.append(f"  ({keys}(grid" if keys else "  (grid")
            lines.extend("    (" + " ".join(souffle_term(cell.term) if not cell.anchor else "@" + souffle_term(cell.term)
                                          for cell in row) + ")" for row in g.cells)
            close(lines, "))" if keys else ")")
        close(lines, ")")
        return "\n".join(lines)

    def order_form(self, r, amp: str, gloss: str) -> Form:
        """The `DET` of the order parameter `r`: the rows of its `Determine`
        relation of pairs (`solver.vocabulary.order_pairs`), and a `ONE` mark on
        each value column, so that each order is one model."""
        c = self.c
        o = c.orders[r.name]
        labels = [pascal(r.columns[i].name) for i in o.values]
        pairs = order_pairs(r.name)
        line = r.span.first if r.span else 0
        if (("Determine",), pairs) not in c.rels:
            f = Form([f"(DET {amp} (ONE))"], amp, set(), line=line)
            f.marks = ["(ONE)"]
            self.todo.add("no-det-order", f"{amp}: no Determine relation {pairs} gives the pairs of values "
                          "of the order")
            f.comments = [*(f";; {params_to_amp(g)}" for g in [gloss] if g), *self.todo.take()]
            return f
        name = c.rel_name(("Determine",), pairs)
        body = [f"({name} {' '.join('*' + lab for lab in labels)})"]
        marks = [f"(ONE {lab})" for lab in labels]
        f = Form([f"(DET {amp}"] + ["  " + x for x in body + marks], amp, {name}, line=line)
        close(f.lines, ")")
        f.body = body
        f.marks = marks
        f.cols = labels
        f.side = "DET"
        f.comments = [f";; {params_to_amp(gloss)}"] if gloss else []
        return f

    def keyed_param_line(self, amp, kt: KeyedTable, facts, grids) -> str:
        """The param of the set-keyed table `kt`: a row for each fact of its
        child, joined with its parent's fact at its id (`keyed_row`)."""
        if grids.get(kt.child) or grids.get(kt.parent):
            raise ValueError(f"{amp}: a grid of {kt.child} or {kt.parent}, which a set-keyed table's param does not take")
        parents = {}
        for u in facts.get(kt.parent, []):
            row = [self.value_text(a) for a in u.head.args]
            parents[row[0]] = row
        rows = []
        for u in facts.get(kt.child, []):
            row = [self.value_text(a) for a in u.head.args]
            rows.append("(" + " ".join(keyed_row(parents[row[0]], row)) + ")")
        return f"(param {amp} " + " ".join(rows) + ")"

    def type_text(self, name: str) -> str:
        """A column's type: a record of the solver's as its field types."""
        t = self.c.types.get(((), name)) or self.c.types.get((("Params",), name))
        fields = getattr(t, "fields", None)
        if fields:
            return "(" + " ".join(self.type_text(f.type.name) for f in fields) + ")"
        return name

    def value_text(self, a) -> str:
        if isinstance(a, ConstructorTerm):
            return "$" + a.name if not a.args else "($" + a.name + " " + " ".join(self.value_text(x) for x in a.args) + ")"
        if isinstance(a, RecordTerm):
            return "(" + " ".join(self.value_text(x) for x in a.args) + ")"
        return souffle_term(a)

    def ignore_line(self, rel: str, rest: str, concept, under: str | None) -> list[str]:
        """The excludes of an `@ignore: derive` or `@ignore: store` line: the
        cases of the names it gives that take the side it dismisses, the
        side of the @derive line it stands under where it stands under one.
        A line that dismisses a side no form declares has none: no case
        takes that side."""
        m = re.match(r"(\w+)\s*(.*?)\s*—\s*(.*)", rest)
        if not m:
            return [f";; TODO ignore: {rest}"]
        cat, name, reason = m.groups()
        if cat not in ("derive", "store"):
            return []
        why = quote(params_to_amp(reason))
        if cat == "store":
            names = [name_of(n, self.many) for n in re.split(r"\s*&\s*", name)] if name else []
            return [f"(exclude ({' '.join([*names, f'&{rel}=$Stored'])}) {why})"] if under else []
        props = self.derive_props.get(rel, [])
        if name in props or name in PROPOSER_COLS:
            sides, names = [name] if name in props else [], []
        else:
            sides = [under] if under else props
            names = (["$" + n for n in sorted(concept)] if name == "concept" else
                     [name_of(n, self.many) for n in re.split(r"\s*&\s*", name)] if name else [])
        amp = self.c.rel_name(("Params",), rel)
        return [f"(exclude ({' '.join([*names, f'{amp}={p}' if rel in self.many else f'{amp}=$Derived'])}) {why})"
                for p in sides]

    # ---- clauses

    def rigid_forms(self, det_units) -> list[Form]:
        """One RIGID_DET form per block: a part per placed relation, reading the
        determination's table of that name, or the proposer's table where the
        plan finds the part's value covered. Where the determination relations
        lead with key columns, the parts stand in an `instance` clause over
        those columns, and a part with a determination relation reads them
        bare, then the columns of its stored `param` record. Where the block
        is an id-keyed chart (`Converter.rigid_keyed`), a `key` clause over the
        parts' id holds the rest, each part reads the id bare, and each id is
        an assembly of its own."""
        c = self.c
        out: list[Form] = []
        for m in c.prog.macros:
            if not (isinstance(m, RigidCall) and m.scope.components == ("Params",)):
                continue
            amp = c.wrote("&" + m.block, Written(("Params",), m.block, True))
            reads = set()
            parts: list[tuple[str, list[str], int, list[str]]] = []   # part, determination columns, key width, stored columns
            for n in m.names:
                part = c.rel_name(("Determine",), n)
                det = c.rels.get((("Determine",), n))
                if not det_units.get(n) and n not in self.rigid_proposed:
                    self.todo.add("rigid-part", f"{part}: the determination derives no table")
                stored = [pascal(col.name) for col in c.rels[(("Params",), n)].columns[1:]]
                dets = [pascal(col.name) for col in det.columns] if det else stored
                parts.append((part, dets, len(dets) - len(stored) if det else 0, stored))
                reads.add(part)
            keyed = m.block in c.rigid_keyed
            instance_key = next((d[:w] for _, d, w, _ in parts if w > 0), None)
            label = parts[0][3][0] if keyed else ""   # the label of the id that the `key` clause makes

            def id_sites(stored: list[str], mark: str = "") -> list[str]:
                """The site of a part's id at the key's label, in a keyed block."""
                return [column_site(stored[0], mark + label)] if keyed else []

            atoms = [atom(part, [*(instance_key if w > 0 else []), *id_sites(stored),
                                 *(f"*{l}" for l in (stored[1:] if keyed else stored))])
                     for part, _, w, stored in parts]
            if instance_key is not None:
                branches = [atom(part, [*(("^" if i == 0 else "") + l for l in d[:w]), *id_sites(stored)])
                            for i, (part, d, w, stored) in enumerate(p for p in parts if p[2] > 0)]
                atoms = nest(f"(instance ({or_of(branches)})", atoms)
            if keyed:
                ids = [atom(part, id_sites(stored, "^" if i == 0 else "")) for i, (part, _, _, stored) in enumerate(parts)]
                atoms = nest(f"(key ({or_of(ids)})", atoms)
            head = nest(f"(RIGID_DET {amp}", atoms)
            f = Form(head, amp, reads, line=m.span.first)
            f.comments = [*(";; " + t for t in self.plain_comments(m.span.first)), *self.todo.take()]
            out.append(f)
        return out

