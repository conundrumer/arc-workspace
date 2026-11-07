"""The lib the converter writes against: its relations, their columns and keyed
tables, the modes of the algebra relations, the proposers' columns and the
lib signature."""

from __future__ import annotations

import os
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from engine.program import AtomLiteral, Component, Unit
from souffle.parser import parse
from arclog_convert import signature as arclog_signature, paths

from arclog_convert.terms import walk_lits


def pascal(name: str) -> str:
    return name[:1].upper() + name[1:]


def field_names(leaves) -> list[str]:
    """The field names of a record-valued column, one per leaf, in the
    column-name form: each field's own name, or its path of names where two
    fields share one."""
    names = [pascal(l.name) for l in leaves]
    if len(set(names)) < len(names):
        names = ["_".join(pascal(f) for f in l.field) if l.field else pascal(l.name) for l in leaves]
    return names


def field_sites(names: list[str], labs: list[str]) -> list[str]:
    """Each field's site, `(:<Field> <label>)`, elided to the bare label
    where the label is the field's name."""
    return [s if s.lstrip("*^") == n else f"(:{n} {s})" for n, s in zip(names, labs)]


# --------------------------------------------------------------------------
# The lib


@dataclass
class Col:
    name: str        # the column's name as arclog writes it
    type: str        # the type name, after substitution
    tparam: bool     # typed by a type parameter of the component


REGISTRY = paths.ROOT / "engine" / "lib" / "registry.sexpr"


def proposer_columns() -> dict[str, list[Col]]:
    """The columns each proposer gives: a native proposer's, as its form in
    engine/lib/registry.sexpr gives them, and each other proposer's, its
    `propose` relation's in programs/proposers.dl, in arclog case."""
    out: dict[str, list[Col]] = {}
    cur = None
    for line in (paths.ROOT / "programs" / "proposers.dl").read_text().splitlines():
        m = re.match(r"\.comp (\w+)", line)
        if m:
            cur = m.group(1)
        m = re.match(r"\s*\.decl propose\((.*)\)", line)
        if m and cur:
            out[cur] = [Col(pascal(n.strip()), t.strip(), False) for n, t in (x.split(":") for x in m.group(1).split(","))]
    return out | registry_columns("proposer", r"native(?: domain)?")


def registry_columns(kind: str, between: str) -> dict[str, list[Col]]:
    """The columns of each `(<kind> <Name> <between> (columns ...))` form of
    engine/lib/registry.sexpr, by its name; `between` is a regex."""
    form = rf"^\({kind} (\w+) {between} \(columns((?: \(\w+ \w+\))*)\)\)$"
    return {m.group(1): [Col(n, t, False) for n, t in re.findall(r"\((\w+) (\w+)\)", m.group(2))]
            for m in re.finditer(form, REGISTRY.read_text(), re.M)}


def from_key_inputs() -> dict[str, set[str]]:
    """The inputs engine/lib/registry.sexpr marks `from-key`, by component:
    those the engine fills from the key where an instance writes no clause
    for them."""
    out: dict[str, set[str]] = {}
    for name, inputs in component_inputs().items():
        marked = {i[0] for i in inputs if "from-key" in i[1:]}
        if marked:
            out[name] = marked
    return out


def needed_inputs() -> dict[str, tuple[frozenset[str], frozenset[str]]]:
    """The inputs engine/lib/registry.sexpr marks `required`, and those it
    marks `one-of`, by component: the component gives no output while a
    required input holds no row, or while no input of its `one-of` group
    holds one."""
    out: dict[str, tuple[frozenset[str], frozenset[str]]] = {}
    for name, inputs in component_inputs().items():
        required = frozenset(i[0] for i in inputs if "required" in i[1:])
        one_of = frozenset(i[0] for i in inputs if "one-of" in i[1:])
        if required or one_of:
            out[name] = (required, one_of)
    return out


def component_inputs() -> dict[str, list]:
    """The input forms of each `(component ...)` form of
    engine/lib/registry.sexpr, by component, each a nested list of words:
    the input's name, its columns, then its marks."""
    out: dict[str, list] = {}
    for m in re.finditer(r"^\(component (\w+) .*?(?=^\(component |^;;|\Z)", REGISTRY.read_text(), re.M | re.S):
        out[m.group(1)] = next((x[1:] for x in sexpr(m.group(0)) if isinstance(x, list) and x[0] == "inputs"), [])
    return out


def sexpr(text: str) -> list:
    """The first list of `text`, as nested lists of words."""
    stack: list[list] = [[]]
    for word in re.findall(r"[()]|[^\s()]+", text):
        if word == "(":
            stack.append([])
        elif word == ")":
            done = stack.pop()
            stack[-1].append(done)
            if len(stack) == 1:
                return done
        else:
            stack[-1].append(word)
    raise ValueError("no closed list")


def copied_inputs() -> dict[str, set[str]]:
    """The inputs that some output of each component copies, by component, as its `copies` forms in
    engine/lib/registry.sexpr give them. A component with an output that has no such form is left out, since that
    output may take a row from any input."""
    def heads(sources: list) -> set[str]:
        return {n for s in sources for n in (heads(s[1:]) if s[0] == "either" else {s[0]})}
    out: dict[str, set[str]] = {}
    for m in re.finditer(r"^\(component (\w+) .*?(?=^\(component |^;;|\Z)", REGISTRY.read_text(), re.M | re.S):
        outputs = next((x[1:] for x in sexpr(m.group(0)) if isinstance(x, list) and x[0] == "outputs"), [])
        copies = [[c[1:] for c in o if isinstance(c, list) and c[0] == "copies"] for o in outputs]
        if outputs and all(copies):
            out[m.group(1)] = {n for c in copies for n in heads(c[0])}
    return out


FROM_KEY = from_key_inputs()   # the inputs the engine fills from the key, by component
NEEDED_INPUTS = needed_inputs()   # the required inputs and the one-of group, by component
COPIED_INPUTS = copied_inputs()   # the inputs that the outputs copy, by component
PROPOSER_COLS = proposer_columns()   # each proposer's columns
DOMAIN_PROPOSERS = registry_columns("proposer", r"native domain")   # the type-domain proposers, which give one value per row
DERIVATION_COLS = registry_columns("derivation", r"\(fields(?: \(\w+ \w+\))*\)")   # each fixed derivation's columns
# the columns of each name a one-name DET can name: a proposer or a fixed derivation
DET_COLS = PROPOSER_COLS | DERIVATION_COLS
# each parameter whose columns do not map onto those of the proposer or the
# derivation its DET names, by its arclog name: its kept columns and the named one's
type ColMismatch = dict[str, tuple[list[Col], list[Col]]]


def derive_proposer(rest: str) -> str:
    """The proposer an `@derive` line gives, from the text after its directive."""
    return rest.split(":")[0].strip()


def takes_set_mark(proposer: str) -> bool:
    """Whether a `(SET)` mark may follow `proposer`: it has one column and is
    no type-domain proposer."""
    return len(PROPOSER_COLS.get(proposer, ())) == 1 and proposer not in DOMAIN_PROPOSERS


def domain_proposer(types: list[str]) -> str:
    """The type-domain proposer of a value of `types`."""
    return "".join(pascal(t) for t in types) + "Domain"


def covered_proposer(verdict: tuple[str, ...] | None, types: list[str]) -> str | None:
    """The proposer whose table a `covered` plan verdict gives a value of
    `types`: the verdict's own, or for a `domain` verdict the type-domain
    proposer of those types."""
    if not verdict or verdict[0] != "covered":
        return None
    return domain_proposer(types) if verdict[1] in ("domain", "position-domain") else verdict[1]


def require_exact_set(parameter: str, proposers: list[str], verdict: tuple[str, ...] | None) -> None:
    """A whole-set value needs equality, not coverage or a subset verdict.

    The plan's proposer name supplies a column interface even when its value
    is only narrowed. It is not evidence for the semantics of a SET mark.
    """
    if verdict and len(verdict) >= 3 and verdict[0] == "covered" \
            and proposers == [verdict[1]] and verdict[2] == "exact":
        return
    proof = " ".join(verdict) if verdict else "no exact proposer verdict"
    raise ValueError(f"{parameter}: multi-row parameter has only proposer coverage ({proof}); "
                     "a source determination is required; (SET) would select the whole proposal, "
                     "not the stored value")


def plan_proposer(verdict: tuple[str, ...] | None, types: list[str], open_value: bool) -> str | None:
    """The proposer a parameter's DET names by its plan verdict: the one
    `covered_proposer` gives; or, for an open parameter the plan leaves
    `undecided`, the type-domain proposer of `types` where one is defined, whose
    values the fit keeps as the parameter's open values; or, for a parameter
    the plan puts `overlimit`, the proposer of its cover where one is defined:
    the plan's enumeration limit bounds the Souffle tooling, and the engine's
    assignment cap bounds the product of the `DET`s' domains."""
    if verdict and verdict[0] == "undecided":
        prop = domain_proposer(types)
        return prop if open_value and prop in PROPOSER_COLS else None
    if verdict and verdict[0] == "overlimit":
        prop = covered_proposer(("covered", *verdict[2:]), types)
        return prop if prop in PROPOSER_COLS else None
    return covered_proposer(verdict, types)


@dataclass(frozen=True)
class KeyedTable:
    """A set-keyed table, held in Souffle as two parameters joined by an id
    (`checker.determination_plan.KeyedTable`): `child` holds `(id, member
    fields)`, `parent` holds `(id, out fields)`. In arclog it is one
    relation `name` of `proposer`'s columns, the id, the out fields, then
    the member fields, a row for each member of each id."""

    name: str
    proposer: str
    child: str
    parent: str
    outs: int   # the count of out fields

    def parent_cols(self) -> list[Col]:
        """The proposer's columns a read of the parent names."""
        return PROPOSER_COLS[self.proposer][:self.outs + 1]

    def child_cols(self) -> list[Col]:
        """The proposer's columns a read of the child names."""
        cols = PROPOSER_COLS[self.proposer]
        return [cols[0], *cols[self.outs + 1:]]


def keyed_row[T](parent: list[T], child: list[T]) -> list[T]:
    """The row of a set-keyed table, or its columns, from those of its
    parent at an id and of one child at that id: the id, the parent's out
    fields, then the child's member fields."""
    return [*parent, *child[1:]]


def keyed_tables(types: dict[str, list[str]], proposers: dict[str, str]) -> list[KeyedTable]:
    """Each two parameters, of `types` by name, that the plan covers with
    one proposer (`proposers`), both with an `Ident` first, where the
    proposer's columns are `keyed_row` of the one, the parent, and the
    other, the child: a set-keyed table, named by the prefix the two names
    share."""
    by_prop: dict[str, list[str]] = defaultdict(list)
    for name, prop in proposers.items():
        by_prop[prop].append(name)
    out = []
    for prop, names in by_prop.items():
        if len(names) != 2:
            continue
        ptypes = [c.type for c in PROPOSER_COLS[prop]]
        fits = [(p, ch) for p, ch in (names, names[::-1])
                if types[p][:1] == types[ch][:1] == ["Ident"] and ptypes == keyed_row(types[p], types[ch])]
        if not fits:
            continue
        if len(fits) > 1:
            raise ValueError(f"{prop}: {names[0]} and {names[1]} each fit as the parent of its table")
        (parent, child), = fits
        name = os.path.commonprefix([parent, child]).rstrip("_")
        if not name:
            raise ValueError(f"{prop}: {parent} and {child} share no prefix to name their table")
        out.append(KeyedTable(name, prop, child, parent, len(types[parent]) - 1))
    return out


@dataclass
class LibRel:
    name: str
    cols: list[Col]
    is_input: bool


LIB_DL = paths.ROOT / "programs" / "lib.dl"
SIGNATURE = arclog_signature()

# The modes of the algebra relations, each a set of columns whose labels must
# be bound before an atom of the relation binds the rest. A column of an
# orientation type is in no mode: an atom enumerates it.
ALGEBRA_MODES: dict[str, list[set[str]]] = {
    "compose": [{"a", "b"}], "relative": [{"base", "x"}], "inside": [{"a", "b"}], "interior": [{"a", "b"}],
    "margin": [{"b"}], "dist_pair": [{"p"}], "diag_dist": [{"p"}], "corner_dist": [{"p"}], "split": [{"p"}],
    "frame_extent": [{"p"}], "axis_extents": [{"p"}], "sub_extent": [{"p"}], "box_extent": [{"b", "p"}],
    "edge_inset": [{"k"}], "corner_inset": [{"k"}], "axis_inset": [{"k1", "k2"}],
    "uniform_inset": [{"k"}, {"b"}], "edge_outset": [{"k"}], "corner_outset": [{"k"}],
    "axis_outset": [{"k1", "k2"}], "uniform_outset": [{"k"}], "jump_offset": [{"k"}], "step_offset": [set()],
    "neighbor": [{"p"}], "jump": [{"p", "k"}], "apply": [{"p"}], "gap": [{"p", "q"}],
    "divide": [{"t", "side", "gap"}], "tile_size": [{"ext", "n", "g"}, {"k", "n", "g"}],
    "frame_offset": [{"p"}], "same_dist": [{"p1", "p2"}],
    "same_line": [{"p", "q"}], "nearer": [{"p", "q"}], "same_corner": [{"p1", "p2"}],
    "same_slab": [{"p1", "p2"}], "centered": [{"p"}],
}


class Lib:
    """The declarations of a lib file: the present lib, whose callers'
    relations are marked `// @input`, or the signature of the lib the
    converter emits, whose are marked `// @extensional`."""

    def __init__(self, path: Path) -> None:
        prog = parse(path.read_text(), path.parent)
        assert not hasattr(prog, "line"), prog
        self.comps = {c.name: c for c in prog.components}
        self.types = {t.name: t for t in prog.types if not t.scope.components}   # the top-level type declarations
        inputs = {(c.file, c.line) for c in prog.comments
                  if not c.own_line and ("@input" in c.text or "@extensional" in c.text)}
        self.comp_rels: dict[str, list[tuple[str, list[tuple[str, str]], bool]]] = defaultdict(list)
        self.order: dict[str, list[str]] = {}   # a component's inputs in the order its target declares them
        self.replaced: dict[str, tuple] = {}   # a component of `libmap.REPLACED`: its present relations
        self.extension: dict[str, set[str]] = defaultdict(set)   # each component, by the relations `extend` added to it
        self.top: dict[str, list[tuple[str, str]]] = {}
        self.clauses: dict[str, list[Unit]] = defaultdict(list)   # a component's own clauses
        for u in prog.units:
            if u.scope.components:
                self.clauses[u.scope.components[-1]].append(u)
        for r in prog.relations:
            cols = [(c.name, c.type.name) for c in r.columns]
            if r.name.startswith("_"):
                continue
            if r.scope.components:
                is_in = (r.span.file, r.span.first) in inputs if r.span else False
                self.comp_rels[r.scope.components[-1]].append((r.name, cols, is_in))
            else:
                self.top[r.name] = cols

    def extend(self, sig: "Lib") -> None:
        """Add to each component the relations its target in `sig` holds and
        it lacks, by name under `libmap.COMP`'s renames, so that a site the
        expansion pass writes in a present component reads a relation only
        the target has. Each relation comes after the component's own."""
        from arclog_convert.libmap import COMP, REPLACED
        self.sig_top = {n: c for n, c in sig.top.items() if n not in self.top}
        for name, c in sig.comps.items():
            if name not in self.comps:   # a component only the signature holds: one the expansions write
                self.comps[name] = c
                self.comp_rels[name] = list(sig.comp_rels.get(name, []))
        for name in REPLACED:   # a component whose every instance the expansions write in its new shape
            self.replaced[name] = self.relations(name)
            self.comp_rels[name] = list(sig.comp_rels.get(name, []))
        for comp, c in list(self.comps.items()):
            if comp in sig.comps and self.comps[comp] is sig.comps[comp]:
                continue
            ren = COMP.get(comp)
            target = ren.name if ren else comp
            if target not in sig.comps or comp.startswith("_"):
                continue
            inverse = {v: k for k, v in (ren.parts.items() if ren else ())}
            self.order[comp] = [inverse.get(n, n) for n, _, is_in in sig.comp_rels.get(target, []) if is_in]
            have = {r.name for r in self.relations(comp)[1]} | set(ren.parts.values() if ren else ())
            sub = dict(zip(sig.comps[target].type_params, c.type_params))
            for name, cols, is_in in sig.comp_rels.get(target, []):
                if name not in have:
                    self.comp_rels[comp].append((name, [(n, sub.get(t, t)) for n, t in cols], is_in))
                    self.extension[comp].add(name)

    def input_clauses(self, comp: str) -> list[Unit]:
        """The clauses of the component's body, and of the bases it extends,
        whose head is one of its `@input` relations and whose body reads no
        relation of the component: the rows the input holds beside the rows
        a caller's clauses give it. A clause that reads a relation of the
        component is left out, as arclog has no name for that relation."""
        _, rels = self.relations(comp)
        inputs = {r.name for r in rels if r.is_input}
        own = {r.name for r in rels}
        out: list[Unit] = []
        c: Component | None = self.comps[comp]
        while c is not None:
            out = [u for u in self.clauses.get(c.name, [])
                   if u.head.relation.name in inputs and not u.head.relation.instances
                   and not any(isinstance(l, AtomLiteral) and (l.atom.relation.instances
                                                               or l.atom.relation.name in own)
                               for l in walk_lits(u.body or ()))] + out
            c = self.comps[c.base] if c.base else None
        return out

    def present(self, comp: str) -> tuple[list[str], list[LibRel]]:
        """The component's relations as the present lib declares them, for
        an expansion that reads its inputs."""
        if comp in self.replaced:
            return self.replaced[comp]
        c = self.comps[comp]
        if c.base in self.replaced:
            tp, base = self.replaced[c.base]
            _, own = self.relations(comp)
            names = {r.name for r in self.relations(c.base)[1]}
            return list(c.type_params), base + [r for r in own if r.name not in names]
        return self.relations(comp)

    def relations(self, comp: str) -> tuple[list[str], list[LibRel]]:
        """The component's own type parameters and its relations, the base's
        first, each column's type with the base's type arguments put in."""
        c = self.comps[comp]
        rels: list[LibRel] = []
        if c.base:
            _, base_rels = self.relations(c.base)
            base_params = self.comps[c.base].type_params
            sub = {p: a.name for p, a in zip(base_params, c.base_type_args)}
            for br in base_rels:
                cols = []
                for col in br.cols:
                    t = sub.get(col.type, col.type)
                    cols.append(Col(col.name if t in c.type_params else pascal(col.name.lower()) if col.tparam else col.name,
                                    t, t in c.type_params))
                rels.append(LibRel(br.name, cols, br.is_input))
        for name, cols, is_in in self.comp_rels.get(comp, []):
            rels = [r for r in rels if r.name != name]
            rels.append(LibRel(name, [Col(n if t in c.type_params else pascal(n), t, t in c.type_params)
                                      for n, t in cols], is_in))
        order = self.order.get(comp)
        if order:
            ins = sorted((r for r in rels if r.is_input), key=lambda r: order.index(r.name) if r.name in order
                         else len(order))
            rels = ins + [r for r in rels if not r.is_input]
        return list(c.type_params), rels


