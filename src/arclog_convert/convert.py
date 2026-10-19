"""Convert the Souffle solvers under programs/solvers/ to arclog and arcdata
files under gen/, and, with the expansion config `libmap.macros`, under
gen_macros/, of `arclog_convert.out`: `work/arclog/` of the main
worktree, or the directory `--out` gives.

    uv run python -m arclog_convert.convert [--out <dir>] [<stem> ...]

Each run writes both outputs for the same solvers, every solver where no
stem is given, and prints the summary of each.
A solver's plan file under plan/ records the hash of the solver
file it was written from, and the runner and lib stamp of the run; where it
is missing or records another hash or stamp, the script first reruns
`scripts/run_dl.py determination-plan <stem>`.
A form the script cannot translate is written literally, under a
`;; TODO <kind>: ...` comment.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from engine.program import (  # noqa: E402
    AdtType,
    Aggregate,
    AliasType,
    Atom,
    AtomLiteral,
    BoolLiteral,
    Comparison,
    ConstructorTerm,
    DefinedName,
    Disjunction,
    GridCall,
    Qualifier,
    RigidCall,
    NumberTerm,
    RecordTerm,
    RecordType,
    RelationName,
    SubtypeType,
    UnionType,
    Unit,
    Variable,
    Wildcard,
)
from dataclasses import fields as dc_fields, is_dataclass, replace as dc_replace  # noqa: E402
from engine.program import ComparisonOperator  # noqa: E402
from souffle.parser import parse  # noqa: E402
from souffle.printer import term as souffle_term  # noqa: E402
from souffle.printer import unit as souffle_unit  # noqa: E402
from arclog_convert.literals import collect_vars  # noqa: E402
from solver.vocabulary import order_pairs  # noqa: E402
from arclog_convert.open_orders import keys_retyped as order_keys_retyped, orders as open_orders  # noqa: E402
from arclog_convert.frame_reads import (  # noqa: E402
    Extent, FieldPlan, FrameRead, SingleAxisExtent, SquareExtent, field_plan, helpers_read)
from arclog_convert.picks import rewrite as rewrite_picks  # noqa: E402
from arclog_convert import libmap  # noqa: E402
from arclog_convert.libmap import box as libmap_box, rename as libmap_rename, rewrite as libmap_rewrite  # noqa: E402
from arclog_convert.helper_rows import helper_rels, rows as helper_rows_of  # noqa: E402
from arclog_convert import OUT_ENV, out as arclog_out, signature as arclog_signature  # noqa: E402

SOLVERS = ROOT / "programs" / "solvers"
WITNESSES = ROOT / "programs" / "witnesses"


def out_dirs() -> tuple[Path, Path, Path, Path]:
    """`gen/`, `gen_macros/`, `plan/` and `names/` of `arclog_out`.
    `convert_one` writes each solver's name map (`name_map`) to `names/`,
    beside `gen/`, whose globs read only arclog and arcdata files."""
    root = arclog_out()
    return root / "gen", root / "gen_macros", root / "plan", root / "names"


OUT_DIR, MACROS_DIR, PLANS, NAMES_DIR = out_dirs()
MACROS_ENV = "ARCLOG_MACROS"
"""Set, the expansion config applies: the pool's workers read it."""
FACTS = {"in", "ex_in", "ex_out"}
ELEM = {"Dir": ("dir_elem", "D"), "Axis": ("axis_elem", "A"), "DiagDir": ("diag_dir_elem", "D"),
        "DiagAxis": ("diag_axis_elem", "Da"), "D4": ("d4_elem", "D"), "C4": ("c4_elem", "D"),
        "Sense": ("sense_elem", "S"), "Sym": ("sym_elem", "S"), "Dir8": ("dir8_elem", "D"),
        "Axis4": ("axis4_elem", "A")}


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


REGISTRY = ROOT / "engine" / "lib" / "registry.sexpr"


def proposer_columns() -> dict[str, list[Col]]:
    """The columns each proposer gives: a native proposer's, as its form in
    engine/lib/registry.sexpr gives them, and each other proposer's, its
    `propose` relation's in programs/proposers.dl, in arclog case."""
    out: dict[str, list[Col]] = {}
    cur = None
    for line in (ROOT / "programs" / "proposers.dl").read_text().splitlines():
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


PROPOSER_COLS = proposer_columns()   # each proposer's columns
DERIVATION_COLS = registry_columns("derivation", r"\(fields(?: \(\w+ \w+\))*\)")   # each fixed derivation's columns
# the columns of each name a one-name DET can name: a proposer or a fixed derivation
DET_COLS = PROPOSER_COLS | DERIVATION_COLS
# each parameter whose columns do not map onto those of the proposer or the
# derivation its DET names, by its arclog name: its kept columns and the named one's
type ColMismatch = dict[str, tuple[list[Col], list[Col]]]


def derive_proposer(rest: str) -> str:
    """The proposer an `@derive` line gives, from the text after its directive."""
    return rest.split(":")[0].strip()


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


def plan_proposer(verdict: tuple[str, ...] | None, types: list[str], open_value: bool) -> str | None:
    """The proposer a parameter's DET names by its plan verdict: the one
    `covered_proposer` gives; or, for an open parameter the plan leaves
    `undecided`, the type-domain proposer of `types` where one is defined, whose
    values the fit keeps as the parameter's open values."""
    if verdict and verdict[0] == "undecided":
        prop = domain_proposer(types)
        return prop if open_value and prop in PROPOSER_COLS else None
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


LIB_DL = ROOT / "programs" / "lib.dl"
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
    "divide": [{"t", "side", "gap"}], "frame_offset": [{"p"}], "same_dist": [{"p1", "p2"}],
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
        inputs = {(c.file, c.line) for c in prog.comments
                  if not c.own_line and ("@input" in c.text or "@extensional" in c.text)}
        self.comp_rels: dict[str, list[tuple[str, list[tuple[str, str]], bool]]] = defaultdict(list)
        self.order: dict[str, list[str]] = {}   # a component's inputs in the order its target declares them
        self.replaced: dict[str, tuple] = {}   # a component of `libmap.REPLACED`: its present relations
        self.top: dict[str, list[tuple[str, str]]] = {}
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


# --------------------------------------------------------------------------
# Output forms


def wrap_param(head: str, rest: str) -> str:
    """A one-line param over 80 columns, one row per line."""
    if "\n" in rest or len(head) + len(rest) <= 80:
        return head + rest
    body = rest.strip()
    assert body.endswith(")")
    body = body[:-1].strip()
    rows, depth, start = [], 0, None
    for j, ch in enumerate(body):
        if ch == "(":
            if depth == 0:
                start = j
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                rows.append(body[start:j + 1])
    return "\n".join([head, *("  " + r for r in rows)]) + ")"


def grid_param(head: str, types: list[str], rest: str) -> str | None:
    """A relation with a Position column, its rows given as grids of the
    first such column: the
    rows that agree on the columns before the position are one grid, each
    cell its position's value after it, `1` where it has none, `_` where no
    row holds the position. None where the rows are not grids so: a row
    that gives several values after its position, two rows at one cell, or
    positions of different frames in one grid."""
    from arclog_convert.lint import L, read, flat
    if "Position" not in types:
        return None
    pi = types.index("Position")
    try:
        rows = read("(x" + rest)[0].items[1:]
    except (SyntaxError, IndexError):
        return None
    groups: dict[tuple, dict[tuple[int, int], str]] = {}
    frames: dict[tuple, set] = defaultdict(set)
    for row in rows:
        if not isinstance(row, L) or len(row.items) != len(types) or len(types) - pi > 2:
            return None
        b = (0, 0, 0, 0) if flat(row.items[pi]) == "ZERO" else box(flat(row.items[pi]))
        after = row.items[pi + 1:]
        if b is None or min(b) < 0:
            return None
        key = tuple(flat(x) for x in row.items[:pi])
        cells = groups.setdefault(key, {})
        if (b[0], b[2]) in cells:
            return None
        cells[(b[0], b[2])] = flat(after[0]) if after else "1"
        frames[key].add(extent(b))
    if not groups or any(len(f) != 1 for f in frames.values()):
        return None
    lines = [head]
    for key, cells in groups.items():
        (v, h), = frames[key]
        lines.append("  (" + " ".join(key) + " (grid" if key else "  (grid")
        lines += ["    (" + " ".join(cells.get((i, j), "_") for j in range(h)) + ")" for i in range(v)]
        lines[-1] += "))" if key else ")"
    lines[-1] += ")"
    return "\n".join(lines)


def box(text: str) -> tuple[int, int, int, int] | None:
    m = re.fullmatch(r"\((-?\d+) (-?\d+) (-?\d+) (-?\d+)\)", text)
    return tuple(int(x) for x in m.groups()) if m else None


def extent(b) -> tuple[int, int]:
    t, bo, l, r = b
    return t + bo + 1, l + r + 1


def tile_frames_split(prog):
    """The program with each Params clause that places a tiled frame
    (`helpers.tile_pos`) in a larger one, by `compose` with a box the
    parameters give, as two clauses: the tiled frame, a table of its own
    named `<relation>_tiles`, and the clause that places it, which reads
    that table; and each such table's name with the relation it was split
    from."""
    from engine.program import DeclId, Scope, UnitId
    units, rels, split = list(prog.units), list(prog.relations), {}
    next_unit = 1 + max((u.id.index for u in units), default=0)
    next_decl = 1 + max((d.id.index for d in prog.declarations), default=0)
    for k, u in enumerate(units):
        if u.scope.components != ("Params",) or not u.body or u.head.relation.instances:
            continue
        tp = [i for i, l in enumerate(u.body) if isinstance(l, AtomLiteral) and not l.negated
              and l.atom.relation == RelationName(("helpers",), "tile_pos")]
        if len(tp) != 1:
            continue
        lit = u.body[tp[0]]
        frame = lit.atom.args[3]
        head_vars = {t.name for t in u.head.args if isinstance(t, Variable)}
        if not isinstance(frame, Variable) or frame.name in head_vars:
            continue
        places = [l for l in u.body if isinstance(l, AtomLiteral) and l.atom.relation == RelationName((), "compose")
                  and l.atom.args[0] == frame and isinstance(l.atom.args[2], Variable)
                  and l.atom.args[2].name in head_vars]
        if len(places) != 1:
            continue
        ins = {v for t in lit.atom.args[:3] for v in term_vars(t)}
        mine = [l for i, l in enumerate(u.body) if i == tp[0] or (
            set(term_vars(l)) and set(term_vars(l)) <= ins)]
        rest = [l for l in u.body if not any(l is m for m in mine)]
        name = u.head.relation.name + "_tiles"
        if any(r.name == name and r.scope.components == ("Params",) for r in rels):
            continue
        decl = next(r for r in rels if r.name == u.head.relation.name and r.scope.components == ("Params",))
        pos = decl.columns[0].type
        cols = tuple(dc_replace(decl.columns[0], name=n, type=pos) for n in ("p_frame", "p_tile", "p_intile"))
        rels.append(dc_replace(decl, id=DeclId(next_decl), name=name, columns=cols))
        next_decl += 1
        tiles_head = Atom(RelationName((), name), (frame, lit.atom.args[4], lit.atom.args[5]), lit.atom.line)
        units.append(dc_replace(u, id=UnitId(next_unit), head=tiles_head, body=tuple(mine)))
        next_unit += 1
        units[k] = dc_replace(u, body=(AtomLiteral(tiles_head, False), *rest))
        split[name] = u.head.relation.name
    if not split:
        return prog, split
    return dc_replace(prog, units=tuple(units), relations=tuple(rels)), split


def term_vars(t) -> list[str]:
    from arclog_convert.libmap.instances import term_vars as tv
    return tv(t, [])


def unplaced_rows(rows: list[list[str]]) -> list[list[str]]:
    """The rows of a placed tiled frame with each placed position taken back
    to the tiled frame: its margins less the least margin on each side,
    since the tiled frame's cells reach each of its edges."""
    boxes = [box(r[0]) for r in rows]
    if not rows or any(b is None for b in boxes):
        return []
    least = [min(b[i] for b in boxes if b) for i in range(4)]
    return [["(" + " ".join(str(x - m) for x, m in zip(b, least)) + ")", *r[1:]]
            for b, r in zip(boxes, rows) if b]


def derived_param(amp: str, rows: list[list[str]], proposer: str | None) -> str | None:
    """The values a helper table derives from, where the table is every
    cell of one frame, or that frame cut into equal tiles: the extent on
    each axis, or the tile count, tile size and gap on each axis; None
    otherwise."""
    boxes = [[box(x) for x in row] for row in rows]
    if not boxes or any(b is None for row in boxes for b in row):
        return None
    width = len(boxes[0])
    if any(len(row) != width for row in boxes):
        return None
    frames = [{extent(row[i]) for row in boxes} for i in range(width)]
    if any(len(f) != 1 for f in frames):
        return None
    dims = [next(iter(f)) for f in frames]
    if width == 1:
        v, h = dims[0]
        if len({row[0] for row in boxes}) != v * h:
            return None
        vals = [("AXIS_V", (f"(:N {v})",)), ("AXIS_H", (f"(:N {h})",))]
    elif width in (2, 3):
        (gv, gh), (iv, ih) = dims[0], dims[-1]
        # the tiles reach each edge of the frame
        if any(min(row[0][i] for row in boxes) for i in range(4)):
            return None
        # the tile count on an axis: the lines the cells cover over the tile size
        lines_v, lines_h = len({row[0][0] for row in boxes}), len({row[0][2] for row in boxes})
        if lines_v % iv or lines_h % ih:
            return None
        ov, oh = lines_v // iv, lines_h // ih
        if width == 3 and dims[1] != (ov, oh):
            return None
        if len({row[0] for row in boxes}) != ov * oh * iv * ih:
            return None
        vals = []
        for a, g, o, i in (("AXIS_V", gv, ov, iv), ("AXIS_H", gh, oh, ih)):
            gap = 0 if o == 1 else (g - o * i) // (o - 1)
            if o * i + (o - 1) * gap != g or gap < 0:
                return None
            vals.append((a, (f"(:Count {o})", f"(:Size {i})", f"(:Gap {gap})")))
    else:
        return None
    rows_text = ["(" + " ".join([f"(:A {a})", *map(str, xs)]) + ")" for a, xs in vals]
    if proposer is None and width == 1:
        proposer = "Frame2D"
    if proposer == "Frame2D" and width != 1:
        return None
    if proposer:
        return "\n".join([f"(param {amp} ({proposer}", *("  " + r for r in rows_text)]) + "))"
    return f"(param {amp} " + " ".join(rows_text) + ")"


def head_renames(u: Unit, r) -> dict[str, str]:
    """Each variable of `u`'s head renamed to the column of `r`, its
    relation's declaration, that it stands at, where the names differ."""
    cols = [pascal(col.name) for col in r.columns]
    return {t.name: cols[k] for k, t in enumerate(u.head.args) if isinstance(t, Variable) and t.name != cols[k]}


def mask_param(amp: str, rows: list[list[str]]) -> str | None:
    """A cell set as a mask grid: `1` at each cell, `_` elsewhere, in the
    frame the cells give; None where the rows are not the cells of one
    frame."""
    cells = []
    for row in rows:
        m = re.fullmatch(r"\((-?\d+) (-?\d+) (-?\d+) (-?\d+)\)", row[0]) if len(row) == 1 else None
        if not m:
            return None
        cells.append(tuple(int(x) for x in m.groups()))
    frames = {(t + b + 1, l + r + 1) for t, b, l, r in cells}
    if len(frames) != 1 or any(min(c) < 0 for c in cells):
        return None
    (v, h), = frames
    on = {(t, l) for t, _, l, _ in cells}
    lines = [f"(param {amp}", "  (grid"]
    lines += ["    (" + " ".join("1" if (i, j) in on else "_" for j in range(h)) + ")" for i in range(v)]
    lines[-1] += "))"
    return "\n".join(lines)


@dataclass
class Form:
    """One arclog form: its lines, the relation it derives, the relations it
    reads, and the comments above it."""
    lines: list[str]
    name: str
    reads: set[str]
    comments: list[str] = field(default_factory=list)
    branches: tuple[str, ...] = ()   # the constructors its head fixes
    line: int = 0
    claim_slugs: list[str] = field(default_factory=list)  # from @claim
    src: tuple | None = None          # (unit, side, scope, sub, name_scope) of a clause
    top_pos: set[str] = field(default_factory=set)
    top_neg: set[str] = field(default_factory=set)
    nested: set[str] = field(default_factory=set)
    src_inst: tuple | None = None
    body: list[str] | None = None     # a clause's body lines, for a merge
    cols: list[str] = field(default_factory=list)   # a clause's head columns
    side: str = ""
    concept_dead: bool = False        # reads at its top level a relation only alts derive
    concept_form: "Form | None" = None   # an instance without its inputs that are dead in the concept
    dead_reads: frozenset = frozenset()
    demo: list = field(default_factory=list)   # a DEMONSTRATED form's (rule, text, &prediction lines, reads)
    demo_head: list = field(default_factory=list)
    demo_input_reads: set = field(default_factory=set)
    marks: list[str] = field(default_factory=list)   # a clause's ONE marks, after its body
    head_repeat: list = field(default_factory=list)   # (column, the column its head repeats)
    demo_rule: str = ""               # the demonstrated rule a clause's head names

    def __setattr__(self, key, value):
        # `&output` is the tail's: no claim holds it
        if key == "claim_slugs" and getattr(self, "name", None) == "&out":
            value = []
        super().__setattr__(key, value)


class Dead(Exception):
    """A clause that reads a relation the current alt leaves empty."""


class Todo:
    def __init__(self) -> None:
        self.kinds: Counter[str] = Counter()
        self.pending: list[str] = []

    def add(self, kind: str, detail: str) -> None:
        self.kinds[kind] += 1
        self.pending.append(f";; TODO {kind}: {detail}")

    def take(self) -> list[str]:
        out, self.pending = self.pending, []
        return out


# --------------------------------------------------------------------------
# Leaves: a column's term split into the parts arclog keeps


@dataclass
class Leaf:
    name: str     # the column or field name
    kind: str     # keep | case | drop | example
    tparam: bool
    path: tuple[int, ...] = ()
    field: tuple[str, ...] = ()   # the record field names along the path


@dataclass(frozen=True)
class Written:
    """The Souffle relation, or instance, an arclog name was written from:
    the solver component path it is declared under, and its name there."""

    scope: tuple[str, ...]
    relation: str
    instance: bool


class Converter:
    def __init__(self, stem: str, lib: Lib, sig: Lib, todo: Todo, inline: frozenset[str] = frozenset()) -> None:
        self.stem = stem
        # each relation or instance this pass makes that the Souffle program
        # does not declare, by its scope and name, with what it stands for
        self.made: dict[tuple[tuple[str, ...], str], Written] = {}
        # each arclog name this pass writes, with each thing it was written from
        self.written: dict[str, list[Written]] = {}
        self.unsafe: set[str] = set()   # the relations with a clause whose body no order makes safe
        self.col_mismatch: ColMismatch = {}
        self.lib = lib
        self.sig = sig   # the lib the output is written in: a name the expansions write that `lib` lacks
        self.todo = todo
        path = SOLVERS / f"{stem}.dl"
        self.text = path.read_text()
        self.src_lines = self.text.splitlines()
        prog = parse(f'#include "lib.dl"\n#line 1\n{self.text}', path.parent.parent)
        if not hasattr(prog, "units"):
            raise ValueError(f"parse failed: {prog}")
        own = lambda x: x.span is None or x.span.file is None  # noqa: E731
        prog = dc_replace(prog, types=tuple(filter(own, prog.types)),
                          relations=tuple(filter(own, prog.relations)),
                          components=tuple(filter(own, prog.components)),
                          instances=tuple(filter(own, prog.instances)),
                          functors=tuple(filter(own, prog.functors)),
                          units=tuple(filter(own, prog.units)),
                          macros=tuple(filter(own, prog.macros)))
        prog = inlined(prog, inline, lib)
        prog, self.tile_frames = tile_frames_split(prog)
        prog, self.picks = rewrite_picks(prog)
        prog, self.lib_judgment = libmap_box.typed(prog, lib)
        prog, judgment, self.lib_moved = libmap_rewrite(prog, lib, macros=MACROS_ENV in os.environ)
        MOVED_RELS.clear()
        MOVED_RELS.update({f"{was}.{r}": new for was, moves in self.lib_moved.values() for r, new in moves.items()})
        self.lib_judgment |= judgment
        # a folded ONE pick: its relation's clauses end in its marks
        self.one_marks = {(p.scope, p.name): p for p in self.picks.values() if p.ones is not None and p.fold}
        self.prog = prog
        self.types: dict[tuple[tuple[str, ...], str], object] = {
            (t.scope.components, t.name): t for t in prog.types}
        self.rels = {(r.scope.components, r.name): r for r in prog.relations}
        self.insts = {(i.scope.components, i.name): i for i in prog.instances}
        # each relation the lib rewrite moves an instance's relation to
        for inst, (was, moves) in self.lib_moved.items():
            for sc in [sc for sc, n in self.insts if n == inst]:
                for r, new in moves.items():
                    self.made[(sc, new)] = Written(sc, f"{was}.{r}", False)
        self.comps = {c.name: c for c in prog.components}
        self.case_types = self._case_types()
        self.open_params = self._open_params()
        self.open_types = self._open_types()
        self.orders = open_orders(prog, self.open_params, self.types)
        self.prog = prog = order_keys_retyped(prog, self.orders)
        self.rels = {(r.scope.components, r.name): r for r in prog.relations}
        self.prog = prog = dc_replace(prog, units=tuple(self.open_eqs_dropped(u) for u in prog.units))
        self.prog = prog = self.open_carriers_dropped(prog)
        self.prog = prog = dc_replace(prog, units=tuple(u2 for u in prog.units for u2 in self.case_tested(u)))
        self.prog = prog = dc_replace(prog, units=tuple(record_eqs(u, self.record_fields) for u in prog.units))
        self.prog = prog = self.split_read_inputs(prog)
        self.prog = prog = self.split_det_parse(prog)
        self.rels = {(r.scope.components, r.name): r for r in prog.relations}
        self.prog = prog = self.candidate_parse(prog)
        self.prog = prog = self.demonstrated(prog)
        self.alias: dict[tuple[tuple[str, ...], str], dict[int, int]] = {}
        self.prog = prog = self.same_columns(prog)
        self.names: dict[tuple[tuple[str, ...], str], str] = {}
        self.used_names: set[str] = {"output"}   # `out` becomes `&output`
        self.key_names: dict[tuple[tuple[str, ...], str], list[str]] = {}
        self.key_paths: dict[tuple[tuple[str, ...], str], list[tuple[int, ...]]] = {}   # each key name's leaf path
        # Souffle RIGID blocks: each placed relation is read as a part of its block,
        # `&<block>.<part>`, with a Pose column; the determination's relation
        # of the same name is the part's table, `&<part>`. The program reads a
        # part under its table's name, so the table takes the part's name, and
        # another relation of that name takes a digit when it is named.
        self.rigid: dict[str, tuple[str, str]] = {}
        for m in prog.macros:
            if isinstance(m, RigidCall) and m.scope.components == ("Params",):
                for n in m.names:
                    self.rigid[n] = (m.block, n[len(m.block) + 1:])
        for n, (block, part) in self.rigid.items():
            self.used_names.add(block)
            self.used_names.add("pose")   # `&<block>.pose` is the form's own output
        for n, (block, part) in self.rigid.items():
            cand, k = part, 2
            while cand in self.used_names:
                cand, k = f"{part}{k}", k + 1
            self.used_names.add(cand)
            self.names[(("Determine",), n)] = cand
            self.names[(("Params",), n)] = f"{block}.{cand}"

    # ---- types

    @property
    def parse_sub(self) -> dict[str, str]:
        """The type parameters of a clause inside `.comp Parse`: `Key` lifted,
        each other parameter the type the program's instance gives it."""
        out = {"Key": "@lift"}
        comp = self.comps.get("Parse")
        inst = next((i for (sc, _), i in self.insts.items() if sc == () and i.component == "Parse"), None)
        if comp is not None and inst is not None:
            for p_, a in zip(comp.type_params, inst.type_args):
                if p_ != "Key" or a.name not in ("Unit", "Example"):
                    out[p_] = a.name
        return out

    def record_fields(self, u: Unit, v: str) -> list[str] | None:
        """The field names of the record type of variable v, from a column
        of the clause's head or of an atom of its body that v fills."""
        def col_type(rn: RelationName, i: int, scope) -> str | None:
            if not rn.instances:
                for k in range(len(scope), -1, -1):
                    r = self.rels.get((scope[:k], rn.name))
                    if r is not None:
                        return r.columns[i].type.name if i < len(r.columns) else None
                return None
            if rn.instances == ("params",):
                r = self.rels.get((("Params",), rn.name))
                return r.columns[i].type.name if r and i < len(r.columns) else None
            inst = None
            for k in range(len(scope), -1, -1):
                inst = self.insts.get((scope[:k], rn.instances[0]))
                if inst is not None:
                    break
            if inst is None or len(rn.instances) != 1 or inst.component not in self.lib.comps:
                return None
            tps, rels = self.lib.relations(inst.component)
            lr = next((r for r in rels if r.name == rn.name), None)
            if lr is None or i >= len(lr.cols):
                return None
            t = lr.cols[i].type
            return dict(zip(tps, (a.name for a in inst.type_args))).get(t, t)

        atoms = [u.head]

        def walk(lits):
            for l in lits:
                if isinstance(l, AtomLiteral):
                    atoms.append(l.atom)
                elif isinstance(l, Disjunction):
                    for b in l.branches:
                        walk(b)
        walk(u.body or ())
        for a in atoms:
            for i, x in enumerate(a.args):
                if x == Variable(v):
                    t = col_type(a.relation, i, u.scope.components)
                    decl = self.find_type(t, u.scope.components) if t else None
                    if isinstance(decl, RecordType):
                        return [f.name for f in decl.fields]
        return None

    def alias_base(self, name: str, scope: tuple[str, ...]) -> str:
        """The type `name` stands for once each alias `.type A = B` it
        names is followed to its target."""
        t = self.find_type(name, scope)
        while isinstance(t, AliasType):
            name = t.target.name
            t = self.find_type(name, scope)
        return name

    def find_type(self, name: str, scope: tuple[str, ...]):
        for i in range(len(scope), -1, -1):
            t = self.types.get((scope[:i], name))
            if t is not None:
                return t
        return None

    def _case_types(self) -> set[str]:
        choice = self.find_type("Choice", ())
        out: set[str] = set()
        if choice is None:
            return out
        out.add("Choice")
        todo = [f.type.name for f in choice.fields] if isinstance(choice, RecordType) else []
        if isinstance(choice, AdtType):
            todo += [f.type.name for k in choice.constructors for f in k.fields]
        while todo:
            t = todo.pop()
            if t in out:
                continue
            decl = self.find_type(t, ())
            if isinstance(decl, AdtType):
                out.add(t)
                todo += [f.type.name for k in decl.constructors for f in k.fields]
        return out

    def case_adt(self, ctor: str) -> AdtType | None:
        """The case type a constructor belongs to."""
        for t in self.prog.types:
            if isinstance(t, AdtType) and t.name in self.case_types and any(k.name == ctor for k in t.constructors):
                return t
        return None

    def case_complement(self, adt: AdtType, pat) -> list | None:
        """The values of `adt` that `pat` does not match, as patterns: each
        other constructor whole, and the matched constructor with its one
        case field's complement; None where the pattern tests several
        fields."""
        if not isinstance(pat, ConstructorTerm):
            return []
        out = []
        for k in adt.constructors:
            if k.name != pat.name:
                out.append(ConstructorTerm(k.name, tuple(Wildcard() for _ in k.fields)))
                continue
            tested = [i for i, a in enumerate(pat.args) if not isinstance(a, Wildcard)]
            if not tested:
                continue
            if len(tested) > 1:
                return None
            i = tested[0]
            sub = self.find_type(k.fields[i].type.name, ())
            if not isinstance(sub, AdtType) or sub.name not in self.case_types:
                return None
            rest = self.case_complement(sub, pat.args[i])
            if rest is None:
                return None
            for r in rest:
                out.append(ConstructorTerm(k.name, tuple(r if j == i else Wildcard() for j in range(len(k.fields)))))
        return out

    def case_tested(self, u: Unit) -> list[Unit]:
        """A clause whose body tests a case variable against a constructor,
        `X = $K(..)` or `X != $K(..)`, as one clause per value the test
        admits, with the value in place of the variable and the test gone:
        each is then a clause of its case, as one whose head names the
        constructor."""
        if u.body is None or u.head.relation.name == "impl_choice":
            return [u]
        for i, l in enumerate(u.body):
            if not (isinstance(l, Comparison) and l.op.value in ("=", "!=")):
                continue
            var, pat = (l.lhs, l.rhs) if isinstance(l.rhs, ConstructorTerm) else (l.rhs, l.lhs)
            if not (isinstance(var, Variable) and isinstance(pat, ConstructorTerm)):
                continue
            adt = self.case_adt(pat.name)
            if adt is None:
                continue
            vals = [pat] if l.op.value == "=" else self.case_complement(adt, pat)
            if vals is None:
                continue
            rest = u.body[:i] + u.body[i + 1:]
            out = []
            for v in vals:
                head = subst_terms(u.head, {var.name: v})
                body = tuple(subst_terms(x, {var.name: v}) for x in rest)
                out.extend(self.case_tested(dc_replace(u, head=head, body=body)))
            return out
        return [u]

    def _open_params(self) -> set[str]:
        """The Params relations under an `// @open` line."""
        out = set()
        for r in self.prog.relations:
            if r.scope.components != ("Params",) or not r.span:
                continue
            i = r.span.first - 2
            while i >= 0 and (t := comment_text(self.src_lines[i])) is not None:
                if t.strip() == "@open":
                    out.add(r.name)
                i -= 1
        return out

    def open_eqs_dropped(self, u: Unit) -> Unit:
        """The unit without its comparisons on an open value: a variable at a
        column or field of an open type is dropped with it, so a comparison
        that names one goes too."""
        if not self.open_types or u.body is None:
            return u
        open_vars: set[str] = set()

        def typed(term, tname: str) -> None:
            if tname in self.open_types:
                collect_vars([Comparison(ComparisonOperator.EQ, term, term, 0)], open_vars)
                return
            t = self.types.get(((), tname)) or self.types.get((u.scope.components, tname))
            if isinstance(t, RecordType) and isinstance(term, RecordTerm) and len(term.args) == len(t.fields):
                for a, f in zip(term.args, t.fields):
                    typed(a, f.type.name)

        def atom(a: Atom) -> None:
            if a.relation.instances:
                return
            r = self.rels.get((u.scope.components, a.relation.name)) or self.rels.get(((), a.relation.name))
            if r is not None and len(r.columns) == len(a.args):
                for arg, col in zip(a.args, r.columns):
                    typed(arg, col.type.name)

        def scan(lits) -> None:
            for l in lits:
                if isinstance(l, AtomLiteral):
                    atom(l.atom)
                elif isinstance(l, Disjunction):
                    for b in l.branches:
                        scan(b)

        atom(u.head)
        scan(u.body)
        if not open_vars:
            return u

        def names(l) -> bool:
            vs: set[str] = set()
            collect_vars([l], vs)
            return bool(vs & open_vars)

        def drop(lits):
            out = []
            for l in lits:
                if isinstance(l, Comparison) and names(l):
                    continue
                if isinstance(l, Disjunction):
                    l = dc_replace(l, branches=tuple(tuple(drop(b)) for b in l.branches))
                out.append(l)
            return out
        return dc_replace(u, body=tuple(drop(u.body)))

    def open_carriers_dropped(self, prog):
        """A relation whose columns are a case's and an open value's, with
        at least one of the latter, dropped with its positive reads: in a
        model it holds the one open value, so a read of it tells nothing."""
        if not self.open_types:
            return prog
        gone = set()
        cases = {"impl_choice"}   # the relations of a case's columns alone
        for r in prog.relations:
            if r.scope.components or not r.columns:
                continue
            kinds = {lf.kind for col in r.columns for lf in self.leaves(col.name, col.type.name, False, (), {})}
            if not any(col.type.name in self.open_types for col in r.columns):
                if kinds == {"case"}:
                    cases.add(r.name)
            elif kinds <= {"case", "drop"}:
                gone.add(r.name)

        # it reads only the case, a parameter, and other such relations
        def plain(lits) -> bool:
            for l in lits:
                if isinstance(l, AtomLiteral):
                    rn = l.atom.relation
                    if l.negated or not (rn.instances == ("params",) or not rn.instances
                                         and (rn.name in cases or rn.name in gone)):
                        return False
                elif isinstance(l, Disjunction):
                    if not all(plain(b) for b in l.branches):
                        return False
                elif not isinstance(l, Comparison):
                    return False
            return True
        while True:
            bad = {u.head.relation.name for u in prog.units
                   if not u.scope.components and not u.head.relation.instances
                   and u.head.relation.name in gone and not plain(u.body or ())}
            if not bad:
                break
            gone -= bad

        def negated(lits) -> set[str]:
            out = set()
            for l in lits:
                if isinstance(l, AtomLiteral) and l.negated and not l.atom.relation.instances:
                    out.add(l.atom.relation.name)
                elif isinstance(l, Disjunction):
                    for b in l.branches:
                        out |= negated(b)
            return out
        for u in prog.units:
            if u.body:
                gone -= negated(u.body)
        if not gone:
            return prog

        def drop(lits):
            out = []
            for l in lits:
                if isinstance(l, AtomLiteral) and not l.atom.relation.instances and l.atom.relation.name in gone:
                    continue
                if isinstance(l, Disjunction):
                    l = dc_replace(l, branches=tuple(tuple(drop(b)) for b in l.branches))
                out.append(l)
            return out
        units = tuple(u if u.body is None else dc_replace(u, body=tuple(drop(u.body)))
                      for u in prog.units
                      if not (not u.scope.components and not u.head.relation.instances and u.head.relation.name in gone))
        self.open_carriers = gone
        return dc_replace(prog, units=units,
                          relations=tuple(r for r in prog.relations if r.scope.components or r.name not in gone))

    def _open_types(self) -> set[str]:
        """The types that tell one open value from another: `OpenValue`, and
        the record type of each of its fields. A column or field of one of
        them is dropped, since a model of an open relation's `ONE` mark holds
        one value."""
        t = self.types.get(((), "OpenValue"))
        if not isinstance(t, RecordType):
            return set()
        return {"OpenValue"} | {f.type.name for f in t.fields}

    def demonstrated(self, prog):
        """Each DemonstrationConsistency instance that a DEMONSTRATED form
        states, with its reads rewritten as reads of the form's relation.

        A prediction clause that names its rule by a variable is written once
        per rule, with the rule's constructor in place of the variable. The
        reads the form states are `consistent(K, R, A, B), prediction(K, R,
        O, I, V)` with a Unit key, a rule consistent on the one pair A, B,
        which the form keys by the pair, and `prediction(K, R, O, I, V),
        !refuted(.., R)`, where `refuted` holds the rules some demonstration
        of K does not confirm. An instance whose program reads a rule, or
        reads the instance otherwise, is no DEMONSTRATED form."""
        self.demo_insts: set[tuple[tuple[str, ...], str]] = set()
        self.demo_mode: dict[tuple[tuple[str, ...], str], str] = {}
        self.demo_pair: dict[tuple[tuple[str, ...], str], list[str]] = {}
        self.demo_rule_types: set[str] = set()
        self.demo_rule_records: set[str] = set()
        self.demo_dropped: set[str] = set()
        self.demo_select: set[tuple[tuple[str, ...], str]] = set()
        for key, inst in list(self.insts.items()):
            if inst.component != "DemonstrationConsistency":
                continue
            got = self._demonstrated(prog, key, inst)
            if got is None:
                self.demo_select.add(key)
                continue
            prog = got
            self.demo_insts.add(key)
            self.demo_rule_types.add(inst.type_args[1].name)
            self.demo_rule_records |= {t.name for t in prog.types if isinstance(t, RecordType)
                                       and any(f.type.name == inst.type_args[1].name for f in t.fields)}
        self.select_ctors = {k.name for sc_, n in self.demo_select
                             for t in [self.find_type(self.insts[(sc_, n)].type_args[1].name, ())]
                             if isinstance(t, AdtType) for k in t.constructors}
        return prog

    def _demonstrated(self, prog, key, inst):
        sc, name = key
        rn = lambda r: RelationName((name,), r)  # noqa: E731
        adt = self.find_type(inst.type_args[1].name, ())
        if not isinstance(adt, AdtType):
            return None
        # an input that a prediction reads is a relation of its own, which
        # the form's DEMO_RULE bodies read
        if sc == ():
            _, lrels = self.lib.relations(inst.component)
            for lr in lrels:
                if not lr.is_input or not any(
                        u.scope.components == sc and u.head.relation == rn("prediction")
                        and any(isinstance(l, AtomLiteral) and l.atom.relation == rn(lr.name)
                                for l in walk_lits(u.body or ())) for u in prog.units):
                    continue
                own = [u for u in prog.units if u.scope.components == sc and u.head.relation == rn(lr.name)]
                bridge = own[0].body if len(own) == 1 and own[0].body and len(own[0].body) == 1 else None
                if bridge and isinstance(bridge[0], AtomLiteral) and not bridge[0].negated \
                        and not bridge[0].atom.relation.instances and bridge[0].atom.args == own[0].head.args:
                    new = bridge[0].atom.relation.name   # split already
                else:
                    prog = self._split_input(prog, inst, lr)
                    new = prog.relations[-1].name
                    self.rels[((), new)] = prog.relations[-1]
                prog = dc_replace(prog, units=tuple(
                    rename_rel(u, rn(lr.name), RelationName((), new))
                    if u.scope.components == sc and u.head.relation == rn("prediction") else u
                    for u in prog.units))
        units = []
        for u in prog.units:
            if u.scope.components == sc and u.head.relation == rn("prediction") and len(u.head.args) == 5 \
                    and isinstance(u.head.args[1], Variable):
                if any(k.fields for k in adt.constructors):
                    return None
                r = u.head.args[1].name
                for k in adt.constructors:
                    m = {r: ConstructorTerm(k.name, ())}
                    units.append(dc_replace(u, head=subst_terms(u.head, m),
                                            body=tuple(subst_terms(x, m) for x in u.body or ())))
            else:
                units.append(u)
        preds = [u for u in units if u.scope.components == sc and u.head.relation == rn("prediction")]
        if not preds or not all(len(u.head.args) == 5 and isinstance(u.head.args[1], ConstructorTerm)
                                and all(isinstance(a, Variable) for a in u.head.args[1].args) for u in preds):
            return None
        # the relations that hold the rules some demonstration refutes
        refuted: dict[str, Unit] = {}
        for u in units:
            b = u.body or ()
            if u.head.relation.instances or len(b) != 3 or not all(isinstance(a, Variable) for a in u.head.args):
                continue
            p_, d_, c_ = (next((l for l in b if isinstance(l, AtomLiteral) and l.atom.relation == rn(x)), None)
                          for x in ("prediction", "demonstration", "consistent"))
            if p_ is None or d_ is None or c_ is None or p_.negated or d_.negated or not c_.negated:
                continue
            k_, r_, o_ = p_.atom.args[:3]
            if d_.atom.args[0] == k_ and (isinstance(o_, Wildcard) or d_.atom.args[1] == o_) \
                    and c_.atom.args == (k_, r_, *d_.atom.args[1:]) and isinstance(r_, Variable):
                refuted[u.head.relation.name] = u
        pair_names = []
        dems = [u for u in units if u.scope.components == sc and u.head.relation == rn("demonstration")]
        if dems:
            pair_names = [a.name if isinstance(a, Variable) else n for a, n in zip(dems[0].head.args[1:], ("O", "O2"))]
            if pair_names[0] == pair_names[1]:
                pair_names = ["O", "O2"]
        modes: set[str] = set()
        # the records that pair a key with a rule: a column of one names the
        # rule a row is derived at, which the form's relation leaves out
        rule_records = {adt.name} | {t.name for t in self.prog.types if isinstance(t, RecordType)
                                     and any(f.type.name == adt.name for f in t.fields)}

        def read(u: Unit) -> Unit:
            if u.body is None or u.head.relation.instances[:1] == (name,) or u.head.relation.name in refuted:
                return u
            body = list(u.body)
            changed = True
            while changed:
                changed = False
                for j, m in enumerate(body):
                    if not (isinstance(m, AtomLiteral) and not m.negated and m.atom.relation == rn("prediction")
                            and isinstance(m.atom.args[1], Variable)):
                        continue
                    k, r = m.atom.args[:2]
                    o, i_, v = m.atom.args[2:]
                    for i, l in enumerate(body):
                        if i == j or not isinstance(l, AtomLiteral):
                            continue
                        if not l.negated and l.atom.relation == rn("confirmed") and l.atom.args == (k, r):
                            mode, args = "all", (k, o, i_, v)
                        elif not l.negated and l.atom.relation == rn("consistent") and l.atom.args[:2] == (k, r) \
                                and inst.type_args[0].name == "Unit":
                            mode, args = "pair", (RecordTerm(l.atom.args[2:]), o, i_, v)
                        elif l.negated and not l.atom.relation.instances and l.atom.relation.name in refuted:
                            ru = refuted[l.atom.relation.name]
                            mp = {h.name: a for h, a in zip(ru.head.args, l.atom.args)}
                            rp = next(x for x in ru.body if isinstance(x, AtomLiteral)
                                      and x.atom.relation == rn("prediction"))
                            if subst_terms(rp.atom.args[0], mp) != k or subst_terms(rp.atom.args[1], mp) != r:
                                continue
                            mode, args = "all", (k, o, i_, v)
                        else:
                            continue
                        rest = [x for n_, x in enumerate(body) if n_ not in (i, j)]
                        vs: set[str] = set()
                        collect_vars(rest, vs)
                        hr = self.rels.get((u.scope.components, u.head.relation.name))
                        collect_vars([AtomLiteral(dc_replace(u.head, args=tuple(
                            a for n_, a in enumerate(u.head.args)
                            if hr is None or n_ >= len(hr.columns)
                            or hr.columns[n_].type.name not in rule_records)), False)], vs)
                        if r.name in vs:
                            continue
                        modes.add(mode)
                        atom = Atom(rn("@demonstrated"), args, m.atom.line)
                        lo, hi = sorted((i, j))
                        body = body[:lo] + [AtomLiteral(atom, False)] + body[lo + 1:hi] + body[hi + 1:]
                        changed = True
                        break
                    if changed:
                        break
            return dc_replace(u, body=tuple(body)) if changed or body != list(u.body) else u

        units = [read(u) for u in units]
        if len(modes) != 1:
            return None
        # the refuted relations no rewritten unit reads drop out
        def reads(lits):
            for l in lits:
                if isinstance(l, AtomLiteral):
                    yield l.atom.relation
                elif isinstance(l, Disjunction):
                    for b in l.branches:
                        yield from reads(b)
                elif isinstance(l, Comparison):
                    for t in (l.lhs, l.rhs):
                        if isinstance(t, Aggregate):
                            yield from reads(t.body)
        read_rels = {x for u in units if u.head.relation.name not in refuted for x in reads(u.body or ())}
        dropped = {n for n in refuted if RelationName((), n) not in read_rels}
        for u in units:
            if u.head.relation.instances[:1] == (name,) or u.head.relation.name in dropped:
                continue
            if any(x.instances[:1] == (name,) and x.name != "@demonstrated" for x in reads(u.body or ())):
                return None   # the program reads a rule or an input of the instance
        self.demo_mode[key] = modes.pop()
        if self.demo_mode[key] == "pair":
            self.demo_pair[key] = [pascal(n) for n in pair_names]
        self.demo_dropped |= dropped
        return dc_replace(prog, units=tuple(u for u in units if u.head.relation.name not in dropped
                                            or u.head.relation.instances))

    def candidate_parse(self, prog):
        """A determination that runs the program's parse at each candidate
        value of a parameter and keeps the values a test of its own passes:
        the parameter's DET offers the candidates, the engine keeps those
        that the program's fit passes, and the determination's clauses that
        only that test reads drop out. A determination clause that reads the
        parse at the kept value reads the program's parse, lifted, with the
        parameter in place of the candidate."""
        self.cand_params: set[str] = set()
        self.cand_insts: dict[str, str] = {}   # a Determine parse instance -> its key type
        self.cand_key_fields: dict[str, set[int]] = {}   # its key type -> the fields that hold a candidate
        det = ("Determine",)
        comp_insts = {n: i for (sc, n), i in self.insts.items() if sc == det and i.component in self.comps}
        if not comp_insts:
            return prog
        prog_inst = {i.component: n for (sc, n), i in self.insts.items() if sc == () and i.component in self.comps}

        def atoms(lits):
            for l in lits:
                if isinstance(l, AtomLiteral):
                    yield l.atom
                elif isinstance(l, Disjunction):
                    for b in l.branches:
                        yield from atoms(b)
                elif isinstance(l, Comparison):
                    for t in (l.lhs, l.rhs):
                        if isinstance(t, Aggregate):
                            yield from atoms(t.body)
        params = {r.name for r in prog.relations if r.scope.components == ("Params",)}
        # each Parse input the program fills from a parameter: name -> params
        fed: dict[tuple[str, str], set[str]] = defaultdict(set)
        for u in prog.units:
            rn = u.head.relation
            if u.scope.components == () and len(rn.instances) == 1 and rn.instances[0] in prog_inst.values():
                comp = self.insts[((), rn.instances[0])].component
                for a in atoms(u.body or ()):
                    if a.relation.instances == ("params",):
                        fed[(comp, rn.name)].add(a.relation.name)
        cand_fields: dict[str, dict[int, str]] = {}   # instance -> key field index -> parameter
        for n, inst in comp_insts.items():
            for u in prog.units:
                rn = u.head.relation
                if u.scope.components != det or rn.instances != (n,) or (inst.component, rn.name) not in fed:
                    continue
                read = {a.relation.name for a in atoms(u.body or ())
                        if not a.relation.instances or a.relation.instances == ("params",)}
                for p_ in fed[(inst.component, rn.name)]:
                    if p_ not in read:
                        self.cand_params.add(p_)
                        # the key field that holds the candidate
                        k = u.head.args[0] if u.head.args else None
                        if isinstance(k, RecordTerm):
                            pu = next((x for x in prog.units if x.scope.components == () and
                                       x.head.relation == RelationName((prog_inst[inst.component],), rn.name)), None)
                            for j, (hk, ha) in enumerate(zip(u.head.args[1:], pu.head.args[1:] if pu else ())):
                                if isinstance(hk, Variable):
                                    for fi, f_ in enumerate(k.args):
                                        if f_ == hk and isinstance(ha, Variable):
                                            cand_fields.setdefault(n, {})[fi] = p_
        if not self.cand_params:
            return prog
        # a candidate stands where the parameter's determination refutes it:
        # a clause of it negates, at its own value, a relation that reads
        # the parse it runs per candidate
        dheads: dict[str, list] = defaultdict(list)
        for u in prog.units:
            if u.scope.components == det and not u.head.relation.instances:
                dheads[u.head.relation.name].append(u)
        reads_parse: dict[str, bool] = {}

        def reads(x: str, seen=frozenset()) -> bool:
            if x in reads_parse:
                return reads_parse[x]
            if x in seen:
                return False
            got = any(a.relation.instances[:1] and a.relation.instances[0] in comp_insts
                      or (not a.relation.instances and a.relation.name in dheads
                          and reads(a.relation.name, seen | {x}))
                      for u in dheads.get(x, ()) for a in atoms(u.body or ()))
            reads_parse[x] = got
            return got

        def refuted(x: str, seen=frozenset()) -> bool:
            for u in dheads.get(x, ()):
                hv = {a.name for a in u.head.args if isinstance(a, Variable)}
                for l in u.body or ():
                    if isinstance(l, AtomLiteral) and not l.atom.relation.instances:
                        n = l.atom.relation.name
                        av = {a.name for a in l.atom.args if isinstance(a, Variable)}
                        if l.negated and av & hv and reads(n):
                            return True
                        if not l.negated and n in dheads and n not in seen and n != x and refuted(n, seen | {x}):
                            return True
            return False
        # a parameter a Params clause derives: the stored ones it reads
        rules = defaultdict(set)
        for u in prog.units:
            if u.scope.components == ("Params",) and u.body:
                rules[u.head.relation.name] |= {a.relation.name for a in atoms(u.body)
                                                if not a.relation.instances and a.relation.name in params}
        todo = list(self.cand_params)
        self.cand_params = set()
        while todo:
            x = todo.pop()
            if rules.get(x):
                todo += [y for y in rules[x] if y not in self.cand_params]
            else:
                self.cand_params.add(x)
        rigid = {n for m in prog.macros if isinstance(m, RigidCall) for n in m.names}
        # a parameter the program also derives (@derive) keeps its determination
        derived = set()
        for r in prog.relations:
            if r.scope.components == ("Params",) and r.span:
                i = r.span.first - 2
                while i >= 0 and self.src_lines[i].strip().startswith("//"):
                    if "@derive" in self.src_lines[i]:
                        derived.add(r.name)
                    i -= 1
        one_color = {r.name for r in prog.relations if r.scope.components == ("Params",)
                     and [c.type.name for c in r.columns] == ["Color"]}
        # (a derived parameter's stored reading lists the candidates, where they are the task's colors)
        self.cand_params = {x for x in self.cand_params if refuted(x) and x not in rigid
                            and (x not in derived or x in one_color)}
        if not self.cand_params:
            return prog
        for n, inst in comp_insts.items():
            k = inst.type_args[0].name
            if k not in ("Unit", "Example"):
                self.cand_insts[n] = k
                self.cand_key_fields[k] = set(cand_fields.get(n, {}))
        # the determination clauses the other parameters read
        dunits = [u for u in prog.units if u.scope.components == det]
        heads: dict[str, list] = defaultdict(list)
        for u in dunits:
            rn = u.head.relation
            heads[rn.instances[0] if rn.instances else rn.name].append(u)
        need: set[str] = set()
        rigid = {n for m in prog.macros if isinstance(m, RigidCall) for n in m.names}
        todo = [x for x in heads if (x in params and x not in self.cand_params) or x in rigid]
        while todo:
            x = todo.pop()
            if x in need:
                continue
            need.add(x)
            for u in heads.get(x, ()):
                for a in atoms(u.body or ()):
                    rn = a.relation
                    y = rn.instances[0] if rn.instances else rn.name
                    if y in heads and y not in need and not (y in params and y in self.cand_params):
                        todo.append(y)
        drop = {x for x in heads if x not in need}
        for x in drop:
            self.insts.pop((det, x), None)
        units = []
        for u in prog.units:
            if u.scope.components == det:
                rn = u.head.relation
                x = rn.instances[0] if rn.instances else rn.name
                if x in drop or (rn.instances and rn.instances[0] in comp_insts):
                    continue
                # a read of the candidate parse binds its candidate to the parameter
                extra = []
                for a in atoms(u.body or ()):
                    fs = cand_fields.get(a.relation.instances[0] if a.relation.instances else "")
                    key = a.args[0] if a.args else None
                    while isinstance(key, RecordTerm) and fs and len(key.args) and isinstance(key.args[0], RecordTerm):
                        key = key.args[0]
                    if fs and isinstance(key, RecordTerm):
                        for fi, p_ in fs.items():
                            v = key.args[fi] if fi < len(key.args) else None
                            if isinstance(v, Variable):
                                lit = AtomLiteral(Atom(RelationName(("params",), p_), (v,), a.line), False)
                                own = AtomLiteral(Atom(RelationName((), p_), (v,), a.line), False)
                                if lit not in extra and not any(isinstance(b, AtomLiteral) and not b.negated
                                                                and b.atom.relation in (lit.atom.relation, own.atom.relation)
                                                                and b.atom.args == (v,) for b in u.body or ()):
                                    extra.append(lit)
                if extra:
                    u = dc_replace(u, body=tuple(u.body) + tuple(extra))
            units.append(u)
        return dc_replace(prog, units=tuple(units),
                          relations=tuple(r for r in prog.relations
                                          if not (r.scope.components == det and r.name in drop)),
                          instances=tuple(i for i in prog.instances
                                          if not (i.scope.components == det and i.name in drop | set(comp_insts))))

    def same_columns(self, prog):
        """A column that every clause of its relation fills with the variable
        of another column, dropped: the relation keeps the other column, and
        each read of it reads the dropped column's variable as the other's."""
        def leaves_of(scope, rel):
            sub = self.parse_sub if scope == ("Parse",) else {}
            out = []
            for i, c_ in enumerate(rel.columns):
                for l in self.leaves(pascal(c_.name), c_.type.name, False, scope, sub):
                    out.append((i, l))
            return out

        def flat(a: Atom, scope, rel):
            sub = self.parse_sub if scope == ("Parse",) else {}
            w = ClauseWriter(self, scope, sub, {})
            out = []
            for c_, t in zip(rel.columns, a.args):
                ls = self.leaves(pascal(c_.name), c_.type.name, False, scope, sub)
                saved = list(self.todo.pending), Counter(self.todo.kinds)
                ts = w.split(t, ls)
                self.todo.pending, self.todo.kinds = saved
                out += [t_ if l.kind == "keep" else None for l, t_ in zip(ls, ts)]
            return out

        def find(rn: RelationName, scope):
            if rn.instances or rn.name in FACTS:
                return None
            for k in range(len(scope), -1, -1):
                if (scope[:k], rn.name) in self.rels:
                    return (scope[:k], rn.name)
            return None

        def put(t, path, x):
            if not path:
                return x
            if isinstance(t, RecordTerm):
                args = list(t.args)
                args[path[0]] = put(args[path[0]], path[1:], x)
                return RecordTerm(tuple(args))
            return t

        def fix(a: Atom, scope, m: dict) -> Atom:
            """The read with each dropped column's variable at the column it
            repeats, where the read leaves that column out; the renames of
            the variables it names at both columns go to `m`."""
            key = find(a.relation, scope)
            if key is None or key not in self.alias:
                return a
            rel = self.rels[key]
            r = flat(a, key[0], rel)
            pos = leaves_of(key[0], rel)
            args = list(a.args)
            for k, j in self.alias[key].items():
                tk, tj = r[k], r[j]
                ck, lk = pos[k]
                if isinstance(tk, Variable) and isinstance(tj, Variable) and tk != tj:
                    whole = a.args[ck]
                    if isinstance(whole, Variable) and lk.path:
                        # the record variable spelled out, with the repeated
                        # column's variable at the dropped leaf
                        cls = [l for i_, l in pos if i_ == ck]
                        ts = [t_ if t_ is not None else Wildcard() for (i_, _), t_ in zip(pos, r) if i_ == ck]
                        rec = None
                        for l, t_ in zip(cls, ts):
                            rec = put(rec if rec is not None else build(cls), l.path, tj if l is lk else t_)
                        m.setdefault(whole.name, rec)
                    else:
                        m.setdefault(tk.name, tj)
                elif isinstance(tk, Variable) and isinstance(tj, Wildcard):
                    ci, leaf = pos[j]
                    args[ci] = put(args[ci], leaf.path, tk)
            return dc_replace(a, args=tuple(args))

        def build(cls):
            """A record term of wildcards with the leaves' structure."""
            def node(depth, ls):
                if len(ls) == 1 and len(ls[0].path) == depth:
                    return Wildcard()
                groups: dict[int, list] = defaultdict(list)
                for l in ls:
                    groups[l.path[depth]].append(l)
                return RecordTerm(tuple(node(depth + 1, groups[i]) for i in sorted(groups)))
            return node(0, cls)

        def same_of(rows) -> dict[int, int]:
            same: dict[int, int] = {}
            for k in range(len(rows[0])):
                for j in range(k):
                    if j not in same and k not in same and \
                            all(isinstance(r[k], Variable) and r[k] == r[j] for r in rows):
                        same[k] = j
            return same

        for (scope, name), rel in self.rels.items():
            if scope not in ((), ("Parse",)):
                continue
            us = [u for u in prog.units if u.scope.components == scope and u.head.relation == RelationName((), name)]
            if not us or any(u.body is None for u in us):
                continue
            same = same_of([flat(u.head, scope, rel) for u in us])
            if same:
                self.alias[(scope, name)] = same
        if not self.alias:
            return prog
        # a chosen relation whose candidate repeats a column repeats it too
        for p_ in self.picks.values():
            key = (p_.scope, p_.name)
            rel = self.rels.get(key)
            vars_ = p_.fold or p_.cvars
            if rel is None or p_.ones is not None or len(vars_) != len(rel.columns):
                continue
            ck = find(p_.item.relation, p_.scope)
            if ck in self.alias and p_.item.args == tuple(Variable(v) for v in vars_ if v) \
                    and [c_.type for c_ in self.rels[ck].columns] == [c_.type for c_ in rel.columns]:
                self.alias[key] = dict(self.alias[ck])

        def lits_fix(lits, scope, m):
            out = []
            for l in lits:
                if isinstance(l, AtomLiteral):
                    out.append(dc_replace(l, atom=fix(l.atom, scope, m)))
                elif isinstance(l, Disjunction):
                    out.append(dc_replace(l, branches=tuple(tuple(lits_fix(b, scope, m)) for b in l.branches)))
                else:
                    out.append(l)
            return out
        units = []
        for u in prog.units:
            if u.body is None:
                units.append(u)
                continue
            m: dict[str, object] = {}
            body = lits_fix(list(u.body), u.scope.components, m)
            head = u.head
            if m:
                head = subst_terms(head, m)
                body = [subst_terms(x, m) for x in body]
            units.append(dc_replace(u, head=head, body=tuple(body)) if m or body != list(u.body) else u)
        for p_ in self.picks.values():
            parts = []
            for b in p_.aparts:
                m = {}
                b2 = lits_fix(list(b), p_.scope, m)
                parts.append(tuple(subst_terms(x, m) for x in b2) if m else tuple(b2))
            p_.aparts = parts
        return dc_replace(prog, units=tuple(units))

    def split_read_inputs(self, prog):
        """An instance input that a clause the instance depends on reads, as
        a relation of its own that the input and its readers read. The
        arclog form of an instance is one node, so such a read would make
        the instance and its reader read each other, where the Souffle has
        no recursion: an input does not depend on the instance's outputs."""
        def node(rn: RelationName, scope):
            if rn.instances:
                if len(rn.instances) == 1 and ((), rn.instances[0]) in self.insts and scope == ():
                    return ("inst", rn.instances[0])
                return None
            if rn.name in FACTS:
                return None
            return ("rel", rn.name) if ((), rn.name) in self.rels else None

        def atoms(lits):
            for l in lits:
                if isinstance(l, AtomLiteral):
                    yield l.atom
                elif isinstance(l, Disjunction):
                    for b in l.branches:
                        yield from atoms(b)
                elif isinstance(l, Comparison):
                    for t in (l.lhs, l.rhs):
                        if isinstance(t, Aggregate):
                            yield from atoms(t.body)

        def input_rel(rn: RelationName):
            """(instance, LibRel) where `rn` names an input of a top-level
            lib instance."""
            if len(rn.instances) != 1:
                return None
            inst = self.insts.get(((), rn.instances[0]))
            if inst is None or inst.component not in self.lib.comps:
                return None
            _, rels = self.lib.relations(inst.component)
            lr = next((r for r in rels if r.name == rn.name), None)
            return (inst, lr) if lr is not None and lr.is_input else None

        done: set[tuple[str, str]] = set()
        while True:
            edges: dict[tuple, set] = defaultdict(set)
            for u in prog.units:
                if u.scope.components != ():
                    continue
                h = node(u.head.relation, ())
                if h is None:
                    continue
                for a in atoms(u.body or ()):
                    n = node(a.relation, ())
                    if n is not None:
                        edges[h].add(n)

            def reaches(a, b) -> bool:
                seen, todo = set(), [a]
                while todo:
                    x = todo.pop()
                    if x == b:
                        return True
                    if x in seen:
                        continue
                    seen.add(x)
                    todo.extend(edges.get(x, ()))
                return False

            target = None
            for u in prog.units:
                if u.scope.components != () or u.body is None:
                    continue
                h = node(u.head.relation, ())
                for a in atoms(u.body):
                    got = input_rel(a.relation)
                    if got is None or h is None or (a.relation.instances[0], a.relation.name) in done:
                        continue
                    x = ("inst", a.relation.instances[0])
                    # an input that another input of its instance reads
                    sibling = x == h and a.relation != u.head.relation and any(
                        v.scope.components == () and v.head.relation == a.relation for v in prog.units)
                    if sibling or (x != h and reaches(x, h)):
                        target = got
                        break
                if target:
                    break
            if target is None:
                # an input that a sibling input reads, in a component's scope
                for u in prog.units:
                    sc = u.scope.components
                    rn_ = u.head.relation
                    if sc == () or u.body is None or len(rn_.instances) != 1:
                        continue
                    inst_ = self.insts.get((sc, rn_.instances[0]))
                    if inst_ is None or inst_.component not in self.lib.comps:
                        continue
                    _, rels_ = self.lib.relations(inst_.component)
                    for a in atoms(u.body):
                        lr_ = next((r for r in rels_ if r.name == a.relation.name), None)
                        if a.relation.instances == rn_.instances and a.relation != rn_ and lr_ is not None \
                                and lr_.is_input and (sc, inst_.name, lr_.name) not in done \
                                and any(v.scope.components == sc and v.head.relation == a.relation
                                        for v in prog.units):
                            target = (inst_, lr_)
                            break
                    if target:
                        break
            if target is None:
                return prog
            inst, lr = target
            if inst.scope.components:
                done.add((inst.scope.components, inst.name, lr.name))
                prog = self._split_input(prog, inst, lr)
                self.rels = {(r.scope.components, r.name): r for r in prog.relations}
                continue
            done.add((inst.name, lr.name))
            prog = self._split_input(prog, inst, lr)

    def _split_input(self, prog, inst, lr):
        from engine.program import Column, DeclId, RelationDecl, Scope, TypeName, UnitId
        sc = inst.scope.components
        rn = RelationName((inst.name,), lr.name)
        own = [u for u in prog.units if u.scope.components == sc and u.head.relation == rn]
        tparams, _ = self.lib.relations(inst.component)
        isub = {p: a.name for p, a in zip(tparams, inst.type_args)}
        taken = {r.name for r in prog.relations}
        name, n = f"{inst.name}_{lr.name}", 2
        while name in taken:
            name, n = f"{inst.name}_{lr.name}{n}", n + 1
        # a column every clause's head repeats from an earlier one is that
        # column again, and the relation leaves it out, where every reader
        # reads it as the earlier one or not at all
        def reader_atoms(lits):
            for l in lits:
                if isinstance(l, AtomLiteral) and l.atom.relation == rn:
                    yield l.atom
                elif isinstance(l, Disjunction):
                    for b in l.branches:
                        yield from reader_atoms(b)
        readers = [a for u in prog.units if u.scope.components == sc and u.head.relation != rn
                   for a in reader_atoms(u.body or ())]
        dup: dict[int, int] = {}
        for i in range(1, len(lr.cols)):
            j = next((j for j in range(i) if j not in dup and own and all(
                len(u.head.args) > i and u.head.args[i] == u.head.args[j] for u in own)), None)
            if j is not None and all(isinstance(a.args[i], Wildcard) or a.args[i] == a.args[j] for a in readers):
                dup[i] = j
        first = own[0].head.args if own else ()
        cols, args = [], []
        for i, c in enumerate(lr.cols):
            if i in dup:
                continue
            a = first[i] if i < len(first) else None
            t = isub.get(c.type, c.type)
            cn = a.name if isinstance(a, Variable) else c.name
            decl_t = self.find_type(t, sc)
            if isinstance(a, RecordTerm) and isinstance(decl_t, RecordType):
                # a record with one field outside the cases: that field's name
                kept = [x for x, f_ in zip(a.args, decl_t.fields)
                        if isinstance(x, Variable) and f_.type.name not in self.case_types]
                if len(kept) == 1 and len(self.leaves("k", t, False, (), {})) - \
                        sum(1 for l in self.leaves("k", t, False, (), {}) if l.kind != "keep") == 1:
                    cn = kept[0].name
            if cn in [x.name for x in cols]:
                cn = f"{cn}{i}"
            cols.append(Column(cn, TypeName((), t)))
            args.append(Variable(pascal(cn)))
        decl = RelationDecl(DeclId(prog.next_decl_index()), name, Scope(sc), tuple(cols), (), (), None)
        self.made[(sc, name)] = Written(sc, f"{inst.name}.{lr.name}", False)
        new_rn = RelationName((), name)
        kept_idx = [i for i in range(len(lr.cols)) if i not in dup]
        full = [args[kept_idx.index(dup.get(i, i))] for i in range(len(lr.cols))]

        def rename(x):
            if isinstance(x, Atom) and x.relation == rn and dup:
                return dc_replace(x, relation=new_rn, args=tuple(rename(x.args[i]) for i in kept_idx))
            if isinstance(x, RelationName):
                return new_rn if x == rn else x
            if isinstance(x, tuple):
                return tuple(rename(y) for y in x)
            if is_dataclass(x) and not isinstance(x, type):
                ch = {}
                for f_ in dc_fields(x):
                    v = getattr(x, f_.name)
                    if isinstance(v, (tuple, RelationName)) or (is_dataclass(v) and not isinstance(v, type)):
                        ch[f_.name] = rename(v)
                return dc_replace(x, **ch) if ch else x
            return x
        units = []
        bridged = False
        for u in prog.units:
            if u.scope.components != sc:
                units.append(u)
            elif u.head.relation == rn:
                if not bridged:
                    bridged = True
                    units.append(Unit(UnitId(prog.next_unit_index()), u.scope,
                                      Atom(rn, tuple(full), u.head.line),
                                      (AtomLiteral(Atom(new_rn, tuple(args), u.head.line), False),),
                                      None, u.span))
                units.append(dc_replace(u, head=dc_replace(u.head, relation=new_rn,
                                                           args=tuple(u.head.args[i] for i in kept_idx)),
                                        body=rename(u.body)))
            elif u.head.relation.instances[:1] == rn.instances:
                units.append(rename(u) if u.head.relation != rn else u)
            else:
                units.append(rename(u))
        return dc_replace(prog, relations=prog.relations + (decl,), units=tuple(units))

    def split_det_parse(self, prog):
        """A determination's parse keyed on Example is the program's parse,
        lifted, where the determination feeds each of its inputs as the
        program does. Each relation and instance of the parse that reads an
        input fed otherwise is the determination's own: a copy keyed on
        Example, which the determination's readers read."""
        from engine.program import Column, DeclId, Scope, Span, TypeName, UnitId
        det = ("Determine",)
        self.det_parse_copies: dict[tuple[tuple[str, ...], str], str] = {}   # a copy -> the name it is a copy of
        prog_inst = {i.component: i.name for i in prog.instances if i.scope.components == () and i.component in self.comps}
        parse_rels = {r.name: r for r in prog.relations if r.scope.components == ("Parse",)}
        parse_insts = {i.name: i for i in prog.instances if i.scope.components == ("Parse",)}
        parse_units = [u for u in prog.units if u.scope.components == ("Parse",)]
        E = Variable("@E")

        def node(rn: RelationName):
            if rn.instances:
                return rn.instances[0] if rn.instances[0] in parse_insts else None
            return rn.name if rn.name in parse_rels else None

        def walk_vars(x, out: list[str]) -> None:
            if isinstance(x, Variable):
                if x.name not in out:
                    out.append(x.name)
            elif isinstance(x, tuple):
                for y in x:
                    walk_vars(y, out)
            elif is_dataclass(x) and not isinstance(x, type):
                for f_ in dc_fields(x):
                    walk_vars(getattr(x, f_.name), out)

        def canon(u: Unit) -> str:
            names: list[str] = []
            walk_vars((u.head, u.body), names)
            return souffle_unit(subst(dc_replace(u, scope=Scope(det)), {n: f"V{i}" for i, n in enumerate(names)}))

        def rel_map(x, fn):
            if isinstance(x, RelationName):
                return fn(x)
            if isinstance(x, tuple):
                return tuple(rel_map(y, fn) for y in x)
            if is_dataclass(x) and not isinstance(x, type):
                ch = {f_.name: rel_map(getattr(x, f_.name), fn) for f_ in dc_fields(x)
                      if isinstance(getattr(x, f_.name), (tuple, RelationName))
                      or (is_dataclass(getattr(x, f_.name)) and not isinstance(getattr(x, f_.name), type))}
                return dc_replace(x, **ch) if ch else x
            return x

        def key_at(rn: RelationName) -> int | None:
            r = parse_rels.get(rn.name) if not rn.instances else None
            return next((i for i, c_ in enumerate(r.columns) if c_.type.name == "Key"), None) if r else None

        case_rels = {r.name for r in prog.relations if r.scope.components == () and r.columns
                     and all(c_.type.name in self.case_types for c_ in r.columns)} | {"impl_choice"}

        def feed(u: Unit, iname: str, det_side: bool, case_key: bool = False) -> str:
            # the clause as the lifted parse reads it: the example at each
            # key column of the parse, `in` that example's input, and no atom
            # that only tests that the example or the case exists; in the
            # determination, a relation of a parameter's name is the
            # parameter's determination
            def fix(x):
                if isinstance(x, Atom):
                    rn = x.relation
                    if rn == RelationName((), "in"):
                        return dc_replace(x, relation=RelationName((), "ex_in"), args=(E,) + x.args)
                    if rn.instances[:1] == (iname,):
                        i = key_at(RelationName(rn.instances[1:], rn.name))
                        args = x.args if i is None or i >= len(x.args) else x.args[:i] + (E,) + x.args[i + 1:]
                        return dc_replace(x, relation=RelationName(("@parse",) + rn.instances[1:], rn.name), args=args)
                    if det_side and not rn.instances and (det, rn.name) in self.rels and (("Params",), rn.name) in self.rels:
                        return dc_replace(x, relation=RelationName(("params",), rn.name))
                    return x
                if isinstance(x, tuple):
                    return tuple(fix(y) for y in x)
                if is_dataclass(x) and not isinstance(x, type):
                    ch = {f_.name: fix(getattr(x, f_.name)) for f_ in dc_fields(x)
                          if isinstance(getattr(x, f_.name), tuple) or
                          (is_dataclass(getattr(x, f_.name)) and not isinstance(getattr(x, f_.name), type))}
                    return dc_replace(x, **ch) if ch else x
                return x
            hk = key_at(RelationName(u.head.relation.instances[1:], u.head.relation.name))
            k = u.head.args[hk] if hk is not None and hk < len(u.head.args) else None
            kn = k.name if isinstance(k, Variable) else None
            u = dc_replace(u, head=fix(u.head), body=fix(u.body))
            uses: Counter[str] = Counter()

            def count(x) -> None:
                if isinstance(x, Variable):
                    uses[x.name] += 1
                elif isinstance(x, tuple):
                    for y in x:
                        count(y)
                elif is_dataclass(x) and not isinstance(x, type):
                    for f_ in dc_fields(x):
                        count(getattr(x, f_.name))
            count((u.head, u.body))

            def test_only(l) -> bool:
                if not isinstance(l, AtomLiteral) or l.negated or l.atom.relation.instances:
                    return False
                a = l.atom
                if a.relation.name in ("ex_in", "ex_out"):
                    return bool(a.args) and (a.args[0] == E or a.args[0] == k) \
                        and all(isinstance(t, Wildcard) for t in a.args[1:])
                # a case the key holds is the case the lifted parse runs in
                return a.relation.name in case_rels and all(
                    isinstance(t, Wildcard) or isinstance(t, Variable) and (uses[t.name] == 1 or t.name == kn and case_key)
                    for t in a.args)
            u = dc_replace(u, body=tuple(l for l in u.body or () if not test_only(l)))
            return canon(subst(u, {kn: E.name}) if kn else u)

        for inst in [i for i in prog.instances if i.scope.components == det and i.component in prog_inst]:
            comp = self.comps[inst.component]
            tsub = {p: a.name for p, a in zip(comp.type_params, inst.type_args)}
            if tsub.get("Key") != "Example":
                continue
            n, pname = inst.name, prog_inst[inst.component]
            pinst = next(i for i in prog.instances if i.scope.components == () and i.name == pname)
            case_key = dict(zip(comp.type_params, (a.name for a in pinst.type_args))).get("Key") in self.case_types
            feeds: dict[str, tuple[list[str], list[str]]] = defaultdict(lambda: ([], []))
            for u in prog.units:
                rn = u.head.relation
                if u.scope.components == () and rn.instances == (pname,) and u.head.args:
                    feeds[rn.name][0].append(feed(u, pname, False, case_key))
                elif u.scope.components == det and rn.instances == (n,) and u.head.args:
                    feeds[rn.name][1].append(feed(u, n, True))
            differ = {x for x, (a, b) in feeds.items() if sorted(a) != sorted(b)}
            if not differ:
                continue
            # the parse's nodes that read an input fed otherwise
            tainted = set(differ)
            grew = True
            while grew:
                grew = False
                for u in parse_units:
                    h = node(u.head.relation)
                    if h is not None and h not in tainted and any(
                            node(a.relation) in tainted for a in self._atoms(u.body or ())):
                        tainted.add(h)
                        grew = True
            # those the determination reads
            deps: dict[str, set[str]] = defaultdict(set)
            for u in parse_units:
                h = node(u.head.relation)
                if h is not None:
                    deps[h] |= {x for a in self._atoms(u.body or ()) if (x := node(a.relation)) is not None}
            todo = [x for u in prog.units if u.scope.components == det
                    and not (u.head.relation.instances == (n,) and u.head.relation.name not in differ)
                    for a in self._atoms(u.body or ()) if a.relation.instances[:1] == (n,)
                    and (x := node(RelationName(a.relation.instances[1:], a.relation.name))) is not None]
            read: set[str] = set()
            while todo:
                x = todo.pop()
                if x not in read:
                    read.add(x)
                    todo += deps.get(x, ())
            copy = tainted & read
            if not copy:
                continue
            taken = {r.name for r in prog.relations if r.scope.components == det} | \
                    {i.name for i in prog.instances if i.scope.components == det}
            own: dict[str, str] = {}
            for x in sorted(copy):
                cand, k = f"{n}__{x}", 2
                while cand in taken:
                    cand, k = f"{n}__{x}{k}", k + 1
                taken.add(cand)
                own[x] = cand
                self.det_parse_copies[(det, cand)] = x

            def to_det(rn: RelationName, from_parse: bool):
                if from_parse:
                    if rn.instances and rn.instances[0] in parse_insts:
                        i0 = rn.instances[0]
                        return RelationName((own[i0],) + rn.instances[1:], rn.name) if i0 in own \
                            else RelationName((n,) + rn.instances, rn.name)
                    if not rn.instances and rn.name in parse_rels:
                        return RelationName((), own[rn.name]) if rn.name in own else RelationName((n,), rn.name)
                    return rn
                if rn.instances[:1] == (n,):
                    return to_det(RelationName(rn.instances[1:], rn.name), True)
                return rn
            # the parse's types the copies read, each a copy keyed on Example
            parse_types = {t.name: t for t in prog.types if t.scope.components == ("Parse",)}
            det_types = {t.name for t in prog.types if t.scope.components == det}

            def type_refs(x, out: set[str]) -> None:
                if isinstance(x, TypeName):
                    if not x.instances and x.name in parse_types and x.name not in out:
                        out.add(x.name)
                        type_refs(parse_types[x.name], out)
                elif isinstance(x, tuple):
                    for y in x:
                        type_refs(y, out)
                elif is_dataclass(x) and not isinstance(x, type):
                    for f_ in dc_fields(x):
                        type_refs(getattr(x, f_.name), out)
            refs: set[str] = set()
            type_refs(tuple(parse_rels[x] for x in copy if x in parse_rels), refs)
            type_refs(tuple(parse_insts[x] for x in copy if x in parse_insts), refs)
            type_refs(tuple(u for u in parse_units if node(u.head.relation) in copy), refs)
            tmap = dict(tsub)
            for t in sorted(refs):
                cand, k = f"{n}__{t}", 2
                while cand in det_types:
                    cand, k = f"{n}__{t}{k}", k + 1
                det_types.add(cand)
                tmap[t] = cand

            def retype(x):
                if isinstance(x, TypeName):
                    return TypeName((), tmap[x.name]) if not x.instances and x.name in tmap else x
                if isinstance(x, tuple):
                    return tuple(retype(y) for y in x)
                if is_dataclass(x) and not isinstance(x, type) and not isinstance(x, (RelationName, Span)):
                    ch = {f_.name: retype(getattr(x, f_.name)) for f_ in dc_fields(x)
                          if isinstance(getattr(x, f_.name), tuple) or
                          (is_dataclass(getattr(x, f_.name)) and not isinstance(getattr(x, f_.name), type))}
                    return dc_replace(x, **ch) if ch else x
                return x
            new_rels, new_insts, new_types, new_units = [], [], [], []

            def next_id() -> DeclId:
                return DeclId(prog.next_decl_index() + len(new_rels) + len(new_insts) + len(new_types))
            for t in sorted(refs):
                new_types.append(dc_replace(retype(parse_types[t]), id=next_id(), name=tmap[t], scope=Scope(det)))
            for x in sorted(copy):
                if x in parse_rels:
                    r = parse_rels[x]
                    names = [c_.name for c_ in r.columns]
                    cols = tuple(Column("e" if c_.type.name == "Key" and "e" not in names else c_.name, retype(c_.type))
                                 for c_ in r.columns)
                    new_rels.append(dc_replace(r, id=next_id(), name=own[x], scope=Scope(det), columns=cols))
                else:
                    i = parse_insts[x]
                    new_insts.append(dc_replace(i, id=next_id(), name=own[x], scope=Scope(det),
                                                type_args=retype(i.type_args)))
            base = prog.next_unit_index()
            for u in parse_units:
                if node(u.head.relation) in copy:
                    # the key is the example, E
                    hk = 0 if u.head.relation.instances else key_at(u.head.relation)
                    k0 = u.head.args[hk] if hk is not None and hk < len(u.head.args) else None
                    used: list[str] = []
                    walk_vars((u.head, u.body), used)
                    m: dict[str, str] = {}
                    if "E" in used and k0 != Variable("E"):
                        # another E: a lifted read's Example column takes that name
                        j = 1
                        while f"E{j}" in used:
                            j += 1
                        m["E"] = f"E{j}"
                    if isinstance(k0, Variable) and k0.name != "E":
                        m[k0.name] = "E"
                    new_units.append(subst(retype(Unit(UnitId(base + len(new_units)), Scope(det),
                                                       rel_map(u.head, lambda rn: to_det(rn, True)),
                                                       rel_map(u.body, lambda rn: to_det(rn, True)), u.plan, u.span)), m))
            units = []
            for u in prog.units:
                if u.scope.components == det:
                    rn = u.head.relation
                    if rn.instances == (n,) and rn.name in copy:
                        u = dc_replace(u, head=dc_replace(u.head, relation=RelationName((), own[rn.name])))
                    u = dc_replace(u, body=rel_map(u.body, lambda rn: to_det(rn, False)))
                units.append(u)
                if parse_units and u is parse_units[-1]:
                    units += new_units
            if not parse_units:
                units += new_units
            # a copy no clause derives is empty, and so is an instance copy
            # no input clause feeds: a clause that reads it holds nowhere,
            # and a negation of it holds everywhere
            copies = {r.name for r in new_rels} | {i.name for i in new_insts}

            def of(a: Atom) -> str:
                return a.relation.instances[0] if a.relation.instances else a.relation.name
            while True:
                heads = {of(u.head) for u in units if u.scope.components == det}
                empty = copies - heads
                kept = []
                for u in units:
                    if u.scope.components == det and any(
                            isinstance(l, AtomLiteral) and of(l.atom) in empty and not l.negated for l in u.body or ()):
                        continue
                    if u.scope.components == det and u.body:
                        u = dc_replace(u, body=tuple(l for l in u.body if not (
                            isinstance(l, AtomLiteral) and l.negated and of(l.atom) in empty)))
                    kept.append(u)
                if len(kept) == len(units):
                    units = kept
                    break
                units = kept
            new_rels = [r for r in new_rels if r.name not in empty]
            new_insts = [i for i in new_insts if i.name not in empty]
            for key_ in [k_ for k_ in self.det_parse_copies if k_[1] in empty]:
                del self.det_parse_copies[key_]
            prog = dc_replace(prog, types=prog.types + tuple(new_types), relations=prog.relations + tuple(new_rels),
                              instances=prog.instances + tuple(new_insts), units=tuple(units))
            for i in new_insts:
                self.insts[(det, i.name)] = i
            for t in new_types:
                self.types[(det, t.name)] = t
            self.rels = {(r.scope.components, r.name): r for r in prog.relations}
        return prog

    @staticmethod
    def _atoms(lits):
        for l in lits:
            if isinstance(l, AtomLiteral):
                yield l.atom
            elif isinstance(l, Disjunction):
                for b in l.branches:
                    yield from Converter._atoms(b)
            elif isinstance(l, Comparison):
                for t in (l.lhs, l.rhs):
                    if isinstance(t, Aggregate):
                        yield from Converter._atoms(t.body)

    def point_fields(self) -> list[tuple[str, AdtType]]:
        """Each point: its name and its ADT, the Choice's fields and every ADT
        a constructor's field reaches, in declaration order."""
        choice = self.find_type("Choice", ())
        if choice is None:
            return []
        named: dict[str, str] = {}
        if isinstance(choice, RecordType):
            for f in choice.fields:
                named.setdefault(f.type.name, f.name)
        else:
            named["Choice"] = "choice"
        for t in self.prog.types:
            if isinstance(t, AdtType) and t.name in self.case_types:
                for k in t.constructors:
                    for f in k.fields:
                        named.setdefault(f.type.name, f.name)
        out = []
        for t in sorted((t for t in self.prog.types if isinstance(t, AdtType) and t.name in self.case_types
                         and not t.scope.components), key=lambda t: t.span.first):
            out.append((named.get(t.name, t.name[:1].lower() + t.name[1:]), t))
        return out

    def leaves(self, name: str, type_name: str, tparam: bool, scope: tuple[str, ...],
               sub: dict[str, str], outer: dict[str, str] | None = None, lift_ex: bool = False) -> list[Leaf]:
        """The leaves of a column of `type_name`; a record expands only when
        it holds a case, a key-lift or a Unit leaf."""
        t = sub.get(type_name, type_name)
        if outer is not None and t in outer and isinstance(self.find_type(outer[t], ()), RecordType):
            t = outer[t]   # the Parse comp's key parameter, a record
        if t in self.case_types:
            return [Leaf(name, "case", tparam)]
        if t == "TiebreakResolution":
            return [Leaf(name, "drop", tparam)]   # the picks drop every such column
        if t in getattr(self, "demo_rule_types", ()):
            return [Leaf(name, "rule", tparam)]
        if t in getattr(self, "demo_rule_records", ()):
            return [Leaf(name, "drop", tparam)]
        if t == "Unit" or t in self.open_types:
            return [Leaf(name, "drop", tparam)]
        if t == "@lift":
            return [Leaf(name, "drop", tparam)]
        if t == "@example":
            return [Leaf("E", "example", False)]
        if t.startswith("@cand:"):
            # a candidate parse's key: its example, and the candidate, which
            # the parameter the read binds stands for
            decl = self.find_type(t[len("@cand:"):], ("Determine",))
            cand = self.cand_key_fields.get(t[len("@cand:"):], set())
            if isinstance(decl, RecordType):
                return [Leaf("E", "example", False, (i,), (f.name,)) if f.type.name == "Example"
                        else Leaf(f.name, "drop" if i in cand else "keep", tparam, (i,), (f.name,))
                        for i, f in enumerate(decl.fields)]
            return [Leaf("E", "example", False)]
        decl = self.find_type(t, scope)
        if isinstance(decl, RecordType):
            fsub = sub if outer is None else outer
            # a record the Parse comp's key parameter stands for: its Example
            # field is the lifted read's Example column
            lifted = lift_ex or (scope == ("Parse",) and type_name in sub)
            out = []
            for i, f in enumerate(decl.fields):
                if lifted and f.type.name == "Example":
                    out.append(Leaf("E", "example", False, (i,), (f.name,)))
                    continue   # an example field: the lifted read's Example column
                for leaf in self.leaves(f.name, f.type.name, tparam, decl.scope.components, fsub, lift_ex=lifted):
                    out.append(Leaf(leaf.name, leaf.kind, leaf.tparam, (i,) + leaf.path,
                                    (f.name,) + leaf.field))
            return out
        return [Leaf(name, "keep", tparam)]

    # ---- names

    def rel_name(self, scope: tuple[str, ...], name: str) -> str:
        key = (scope, name)
        if scope == ("Determine",) and key not in self.names and (("Params",), name) in self.rels \
                and key not in self.insts:
            key = (("Params",), name)   # the determination of the parameter
        if key not in self.names:
            base = name
            cand = base
            n = 2
            while cand in self.used_names:
                cand = f"{base}{n}"
                n += 1
            self.used_names.add(cand)
            self.names[key] = cand
        inst = self.insts.get(key)
        souffle = self.souffle_of(key[0], key[1], inst is not None and inst.component in self.lib.comps)
        return self.wrote("in" if self.names[key] == "__in__" else "&" + self.names[key], souffle)

    def souffle_of(self, scope: tuple[str, ...], name: str, instance: bool) -> Written:
        """What the relation, or instance, `name` of `scope` in the program
        this pass converts stands for in the Souffle program: itself, where
        the pass did not make it."""
        return self.made.get((scope, name)) or Written(scope, name, instance)

    def wrote(self, arc: str, souffle: Written) -> str:
        """`arc`, an arclog name this pass writes, recorded with what it was
        written from, once each (`name_map`)."""
        got = self.written.setdefault(arc, [])
        if souffle not in got:
            got.append(souffle)
        return arc

    # ---- resolving an atom's relation

    def resolve(self, rel, scope: tuple[str, ...], sub: dict[str, str]):
        """(arclog name, [(Col, leaves)], kind, instance key) for a relation
        name read in `scope`; kind is fact, lib, param, derived, inst."""
        parts = rel.instances
        name = rel.name
        if not parts:
            if name in FACTS:
                cols = self.lib.top[name]
                out = [(Col(pascal(n), t, False), [Leaf(pascal(n), "keep", False)]) for n, t in cols]
                if name != "in":
                    out[0] = (out[0][0], [Leaf("E", "example", False)])
                return self.wrote(name, Written((), name, False)), out, "fact", None
            for i in range(len(scope), -1, -1):
                r = self.rels.get((scope[:i], name))
                if r is not None:
                    return self._derived(r, sub)
            if name in self.lib.top:
                self.wrote(name, Written((), name, False))
            if name in self.lib.top or name in self.sig.top:
                cols = self.lib.top.get(name) or self.sig.top[name]
                return name, [(Col(pascal(n), t, False), [Leaf(pascal(n), "keep", False)]) for n, t in cols], "lib", None
            return name, None, "unknown", None
        head, rest = parts[0], parts[1:]
        if head == "@lib" and not rest:   # a lib relation an expansion wrote, whose name the solver takes
            cols = self.lib.top.get(name) or self.sig.top.get(name)
            if cols is None:
                return name, None, "unknown", None
            return name, [(Col(pascal(n), t, False), [Leaf(pascal(n), "keep", False)]) for n, t in cols], "lib", None
        if head == "params" and not rest:
            r = self.rels.get((("Params",), name))
            if r is None:
                return self.wrote("&" + name, Written(("Params",), name, False)), None, "unknown", None
            name_out, cols, _, _ = self._derived(r, sub)
            return name_out, cols, "param", None
        if head == "helpers":
            _, hrels = self.lib.relations("ParamsHelpers")
            lr = next((r for r in hrels if r.name == name), None)
            if lr is None:
                return name, None, "unknown", None
            return name, [(Col(pascal(c.name), c.type, False), [Leaf(pascal(c.name), "keep", False)]) for c in lr.cols], "lib", None
        inst = None
        for i in range(len(scope), -1, -1):
            inst = self.insts.get((scope[:i], head))
            if inst is not None:
                break
        if inst is None:
            return ".".join(parts + (name,)), None, "unknown", None
        if inst.component in self.comps:   # a solver comp: Parse
            comp = self.comps[inst.component]
            inner_sub = dict(sub)
            for p, a in zip(comp.type_params, inst.type_args):
                inner_sub[p] = "@example" if a.name == "Example" else "@lift" if a.name in ("Unit",) else a.name
                if inst.scope.components == ("Determine",) and inst.name in getattr(self, "cand_insts", {}) \
                        and p == "Key":
                    inner_sub[p] = "@cand:" + a.name   # the program's parse, lifted
            from engine.program import RelationName
            return self.resolve(RelationName(rest, name), (inst.component,), inner_sub)
        if rest:
            return ".".join(parts + (name,)), None, "unknown", None
        if inst.component not in self.lib.comps:
            return ".".join(parts + (name,)), None, "unknown", None
        tparams, rels = self.lib.relations(inst.component)
        isub = dict(sub)
        for p, a in zip(tparams, inst.type_args):
            isub[p] = sub.get(a.name, a.name)
        if name == "@demonstrated" and inst.component == "DemonstrationConsistency":
            # the key, then the prediction's columns; a form keyed by its
            # demonstrated pair has the pair as its key
            ikey = (inst.scope.components, inst.name)
            con = next(r for r in rels if r.name == "consistent")
            pred = next(r for r in rels if r.name == "prediction")
            cols = [(c_, self.leaves(c_.name, c_.type, c_.tparam, inst.scope.components, isub, outer=sub))
                    for c_ in [con.cols[0], *pred.cols[2:]]]
            if self.demo_mode.get(ikey) == "pair":
                obj = con.cols[2]
                cols[0] = (Col("key", obj.type, True),
                           [Leaf(n, "keep", True, (i,), (n,)) for i, n in enumerate(self.demo_pair[ikey])])
            return self.rel_name(inst.scope.components, inst.name), cols, "inst", ikey
        lr = next((r for r in rels if r.name == name), None)
        if lr is None:
            return ".".join(parts + (name,)), None, "unknown", None
        cols = []
        for c in lr.cols:
            cols.append((c, self.leaves(c.name, c.type, c.tparam, inst.scope.components, isub, outer=sub)))
        iname = self.rel_name(inst.scope.components, inst.name)
        return (self.wrote(f"{iname}.{name}", self.souffle_of(inst.scope.components, f"{inst.name}.{name}", False)),
                cols, "inst", (inst.scope.components, inst.name))

    def leaf_type(self, type_name: str, path: tuple[int, ...], scope: tuple[str, ...], sub: dict[str, str]) -> str:
        """The type of the leaf at `path` of a column of `type_name`, as
        `leaves` gives the path, with each alias followed to its target."""
        t = sub.get(type_name, type_name)
        for i in path:
            decl = self.find_type(t, scope)
            assert isinstance(decl, RecordType), (t, path)
            scope, t = decl.scope.components, sub.get(decl.fields[i].type.name, decl.fields[i].type.name)
        return self.alias_base(t, scope)

    def _derived(self, r, sub):
        cols = []
        placed = r.scope.components == ("Params",) and r.name in self.rigid
        same = getattr(self, "alias", {}).get((r.scope.components, r.name), {})
        n = 0
        for i, c in enumerate(r.columns):
            col = Col("Pose" if placed and i == 0 else pascal(c.name), c.type.name, False)
            ls = self.leaves(col.name, c.type.name, False, r.scope.components, sub)
            if len(ls) > 1:
                ls = [dc_replace(l, name=pascal(l.name)) if l.kind == "keep" else l for l in ls]
            out_ls = []
            for l in ls:
                if l.kind == "keep" and n in same:
                    l = dc_replace(l, kind="drop")   # the same as another column
                out_ls.append(l)
                n += 1
            cols.append((col, out_ls))
        pcols = getattr(self, "proposer_cols", {}).get(r.name) if r.scope.components == ("Params",) else None
        mismatch = None
        if pcols is not None:
            # a parameter a proposer gives has the proposer's columns, where
            # its kept columns map onto them by count and by type
            kept = [(i, dc_replace(col, type=sub.get(col.type, col.type)))
                    for i, (col, ls) in enumerate(cols) if any(l.kind == "keep" for l in ls)]
            if len(kept) == len(pcols) and all(
                    [l.path for l in cols[i][1] if l.kind == "keep"] == [()]
                    and self.alias_base(col.type, r.scope.components) == self.alias_base(pc.type, ())
                    for (i, col), pc in zip(kept, pcols)):
                for (i, _), pc in zip(kept, pcols):
                    cols[i] = (dc_replace(cols[i][0], name=pc.name),
                               [dc_replace(l, name=pc.name) if l.kind == "keep" else l for l in cols[i][1]])
            else:
                mismatch = ([col for _, col in kept], pcols)
        def own_e(col, l):
            """Whether `l` of `col` is a column E that holds no Example."""
            return l.name == "E" and l.kind == "keep" \
                and self.leaf_type(col.type, l.path, r.scope.components, sub) != "Example"

        if any(own_e(col, l) for col, ls in cols for l in ls):
            # a lifted read's Example column is E, so the relation's own E takes a digit
            names = {l.name for _, ls in cols for l in ls}
            e = next(f"E{j}" for j in range(1, len(names) + 2) if f"E{j}" not in names)
            cols = [(dc_replace(col, name=e) if col.name == "E" and any(own_e(col, l) for l in ls) else col,
                     [dc_replace(l, name=e) if own_e(col, l) else l for l in ls])
                    for col, ls in cols]
        seen = Counter(l.name for _, ls in cols for l in ls if l.kind == "keep")
        if any(n > 1 for n in seen.values()):
            cols = [(col, [dc_replace(l, name=f"{col.name}_{l.name.lower()}") if len(ls) > 1 and l.kind == "keep" and seen[l.name] > 1 else l for l in ls]) for col, ls in cols]
            # leaves that still share a name take their path of fields
            seen = Counter(l.name for _, ls in cols for l in ls if l.kind == "keep")
            if any(n > 1 for n in seen.values()):
                cols = [(col, [dc_replace(l, name="_".join([col.name, *(f.lower() for f in l.field)]))
                               if l.kind == "keep" and seen[l.name] > 1 and l.field else l for l in ls])
                        for col, ls in cols]
        name = self.rel_name(r.scope.components, r.name)
        if mismatch is not None:
            self.col_mismatch[name] = mismatch
        if name == "in" and sum(l.kind == "keep" for _, ls in cols for l in ls) > len(self.lib.top["in"]):
            # a read of the parse at a key that holds more than the example is no read of `in`
            self.todo.add("parse-key", f"{r.name}: the program's parse is `in`, and this read's key holds a column "
                          "beyond the example")
            name = self.wrote("&" + r.name, Written(r.scope.components, r.name, False))
        if name == "in":
            in_cols = iter(pascal(n) for n, _ in self.lib.top["in"])
            out = []
            for col, ls in cols:
                ls = [dc_replace(l, name=next(in_cols)) if l.kind == "keep" else l for l in ls]
                kept = [l for l in ls if l.kind == "keep"]
                out.append((dc_replace(col, name=kept[0].name) if len(kept) == 1 else col, ls))
            cols = out
            if any(l.kind == "example" for _, ls in cols for l in ls):
                name = "ex_in"   # the parse at each example reads that example's input
        return name, cols, "derived", None


# --------------------------------------------------------------------------
# Clause conversion


class ClauseWriter:
    """Writes one clause body as arclog lines."""

    def __init__(self, conv: Converter, scope: tuple[str, ...], sub: dict[str, str],
                 rename: dict[str, str], own_inst=None) -> None:
        self.c = conv
        self.scope = scope
        self.sub = sub
        self.rename = rename
        self.reads: set[str] = set()
        self.branches: set[str] = set()
        self.own_inst = own_inst
        self.depth = 0
        self.top_pos: set[str] = set()
        self.top_neg: set[str] = set()
        self.nested: set[str] = set()
        self.drop_neg: frozenset[str] = getattr(conv, "cur_empty", frozenset())
        self.clause_vars: set[str] = set()   # the labels of the lists written so far
        self.stuck = False   # a top-level body whose algebra atoms no order makes safe

    def label(self, v: str) -> str:
        return self.rename.get(v, v)

    def term_text(self, t) -> str:
        if isinstance(t, Variable):
            return self.label(t.name)
        if isinstance(t, NumberTerm) and t.value == 0:
            return "0"
        if isinstance(t, DefinedName) and t.name == "ZERO":
            return "0"
        if isinstance(t, DefinedName):
            self.c.todo.add("literal", t.name)
            return t.name
        if isinstance(t, NumberTerm):
            self.c.todo.add("literal", str(t.value))
            return str(t.value)
        if isinstance(t, ConstructorTerm):
            if t.name in self.c.select_ctors:
                return "$" + t.name   # a selected rule: the instance's TODO names it
            self.c.todo.add("constructor", souffle_term(t))
            return "$" + t.name
        if isinstance(t, Aggregate):
            self.c.todo.add("aggregate", souffle_term(t))
            return "{" + souffle_term(t) + "}"
        self.c.todo.add("term", souffle_term(t))
        return "{" + souffle_term(t) + "}"

    def split(self, term, leaves: list[Leaf]):
        """The terms of a column's leaves, matched by the record structure."""
        if len(leaves) == 1 and not leaves[0].path:
            return [term]
        return self._split(term, leaves, 0)

    def _split(self, term, leaves: list[Leaf], depth: int):
        if len(leaves) == 1 and len(leaves[0].path) == depth:
            return [term]
        if all(l.kind == "drop" for l in leaves):
            return [Wildcard()] * len(leaves)
        if isinstance(term, Wildcard):
            return [Wildcard()] * len(leaves)
        if isinstance(term, Variable):
            if sum(l.kind in ("keep", "example") for l in leaves) == 1:
                # one leaf kept: the leaf is the variable
                return [term if l.kind in ("keep", "example") else Wildcard() for l in leaves]
            inner = [l.field[depth:] for l in leaves]
            last = [f[-1] if f else l.name.lower() for f, l in zip(inner, leaves)]
            tags = last if len(set(last)) == len(last) else \
                ["_".join(f) if f else l.name.lower() for f, l in zip(inner, leaves)]
            return [Variable(f"{term.name}_{t}") if l.kind in ("keep", "example") else Wildcard()
                    for l, t in zip(leaves, tags)]
        if isinstance(term, RecordTerm):
            groups: dict[int, list[Leaf]] = defaultdict(list)
            for l in leaves:
                groups[l.path[depth] if len(l.path) > depth else -1].append(l)
            if len(groups) == len(term.args) and -1 not in groups:
                out = []
                for i, a in enumerate(term.args):
                    out.extend(self._split(a, groups[i], depth + 1))
                return out
        if isinstance(term, ConstructorTerm) and term.name == "U" and all(l.kind == "drop" for l in leaves):
            return [Wildcard()] * len(leaves)
        self.c.todo.add("record-shape", souffle_term(term))
        return [Wildcard()] * len(leaves)

    def sites(self, atom: Atom, bound: set[str] | None, key_join: bool = True) -> tuple[str, list[str]]:
        name, cols, kind, inst = self.c.resolve(atom.relation, self.scope, self.sub)
        if atom in self.c.lib_judgment:
            self.c.todo.add("lib-judgment", self.c.lib_judgment[atom])
        if cols is None:
            self.c.todo.add("unresolved", atom.relation.text)
            return name, [souffle_term(a) for a in atom.args]
        if kind in ("derived", "param", "inst"):
            self.reads.add(name.split(".")[0])
        if kind == "inst" and inst in self.c.demo_insts and atom.relation.name != "@demonstrated" \
                and self.own_inst != inst:
            self.c.todo.add("demonstrated-read", f"{name}: a read of a rule or an input "
                            "of a DEMONSTRATED form, whose relation has no rule column; the doc gives no form")
        if name == "in" and any(l.kind == "example" for _, ls in cols for l in ls):
            name = "ex_in"
        if len(cols) != len(atom.args):
            self.c.todo.add("arity", f"{atom.relation.text}")
            return name, [souffle_term(a) for a in atom.args]
        out: list[str] = []
        for i, ((col, leaves), arg) in enumerate(zip(cols, atom.args)):
            terms = self.split(arg, leaves)
            kept: list[tuple[Leaf, object]] = []
            for leaf, t in zip(leaves, terms):
                if leaf.kind == "case":
                    self.branches.update(ctor_names(t))
                    continue
                if leaf.kind in ("drop", "rule"):
                    continue
                kept.append((leaf, t))
            if not kept:
                continue
            is_key = inst is not None and i == 0 and col.name == "key"
            if is_key:
                kn_all = self.c.key_names.get(inst) or []
                nonex = [l for l, _ in kept if l.kind != "example"]
                by_path = dict(zip(self.c.key_paths.get(inst, []), kn_all))
                names_by_leaf = dict(zip(map(id, (l for l, _ in kept)), kn_all)) if len(kn_all) == len(kept) else \
                    dict(zip(map(id, nonex), kn_all)) if len(kn_all) == len(nonex) else \
                    {id(l): by_path[l.path] for l in nonex} if all(l.path in by_path for l in nonex) else {}
                for leaf, t in kept:
                    if leaf.kind == "example" and not isinstance(t, Wildcard):
                        s_ = self.one(t, bound)
                        out.append(s_ if s_.lstrip("*^") == "E" else f"(:E {s_})")
                kept = [(l, t) for l, t in kept if l.kind != "example"]
                if not kept:
                    continue
                names = [names_by_leaf[id(l)] for l, _ in kept] if names_by_leaf else \
                    [n for n in kn_all if n != "E"] or [pascal(l.name) for l, _ in kept]
                if len(names) != len(kept):
                    names = [pascal(l.name) for l, _ in kept]
                if key_join and inst == self.own_inst and all(
                        isinstance(t, Variable) and self.label(t.name) == n for (l, t), n in zip(kept, names)):
                    continue
                inner = []
                for (leaf, t), n in zip(kept, names):
                    if isinstance(t, Wildcard):
                        continue
                    s = self.one(t, bound)
                    lab = s.lstrip("*^")
                    inner.append(s if lab == n else f"(:{n} {s})")
                if inner:
                    out.append("(:key " + " ".join(inner) + ")")
                continue
            if col.tparam and len(kept) > 1:
                fnames = field_names([l for l, _ in kept])
                inner = field_sites([n for n, (_, t) in zip(fnames, kept) if not isinstance(t, Wildcard)],
                                    [self.one(t, bound) for _, t in kept if not isinstance(t, Wildcard)])
                if inner:
                    out.append(f"(:{col.name} " + " ".join(inner) + ")")
                continue
            nkeep = sum(1 for l, _ in kept if l.kind == "keep")
            for leaf, t in kept:
                if isinstance(t, Wildcard):
                    continue
                s = self.one(t, bound)
                lab = s.lstrip("*^")
                colname = "E" if leaf.kind == "example" else leaf.name if nkeep > 1 else col.name
                if not col.tparam and lab == colname:
                    out.append(s)
                else:
                    out.append(f"(:{colname} {s})")
        return name, out

    def one(self, t, bound: set[str] | None) -> str:
        if isinstance(t, Variable):
            lab = self.label(t.name)
            if bound is not None and lab not in bound:
                bound.add(lab)
                return "*" + lab
            return lab
        return self.term_text(t)

    def lit(self, l, bound: set[str]) -> list[str]:
        if isinstance(l, AtomLiteral):
            if l.atom.relation.name in self.c.skip_rels and (not l.atom.relation.instances or
                                                              l.atom.relation.instances[0] in ("parse", "ex")):
                if l.atom.relation.name in getattr(self.c, "case_sets", ()):
                    self.note("%" + l.atom.relation.name, l.negated)
                    self.reads.add("%" + l.atom.relation.name)
                    if "%" + l.atom.relation.name in self.drop_neg and not l.negated:
                        raise Dead
                return []
            if l.negated and not l.atom.relation.instances and self.defect(l.atom.relation.name):
                return self.universal(l.atom, bound)
            if l.negated:
                name, s = self.sites(l.atom, None)
                self.note(name, True)
                if name.split(".")[0] in self.drop_neg:
                    return []
                return [f"(NOT ({name}{''.join(' ' + x for x in s)}))"]
            name, s = self.sites(l.atom, bound)
            self.note(name, False)
            if name.split(".")[0] in self.drop_neg:
                raise Dead
            return [f"({name}{''.join(' ' + x for x in s)})"]
        if isinstance(l, Comparison):
            lhs, rhs = l.lhs, l.rhs
            if l.op.value in ("=", "!=") and isinstance(lhs, Variable) and isinstance(rhs, Variable):
                a, b = self.label(lhs.name), self.label(rhs.name)
                if a not in bound and b not in bound:
                    fa = {x[len(a) + 1:] for x in bound if x.startswith(a + "_")}
                    fb = {x[len(b) + 1:] for x in bound if x.startswith(b + "_")}
                    common = sorted(fa & fb)
                    if common and fa == fb:
                        if l.op.value == "=":
                            return [f"(= {a}_{x} {b}_{x})" for x in common]
                        if len(common) == 1:
                            return [f"(!= {a}_{common[0]} {b}_{common[0]})"]
                        return wrap("(OR ", [[f"(!= {a}_{x} {b}_{x})"] for x in common])
            if l.op.value == "=" and isinstance(lhs, RecordTerm) and isinstance(rhs, RecordTerm) \
                    and agrees_but_wildcards(lhs, rhs):
                # two records that differ only where one holds `_`: the test names the
                # constructors they share, the case the clause stands in
                self.branches.update(ctor_names(lhs))
                return []
            if l.op.value == "=":
                # `=` makes its first label: `(= *X Y)`, the made label first
                lfree = isinstance(lhs, Variable) and self.label(lhs.name) not in bound
                rfree = isinstance(rhs, Variable) and self.label(rhs.name) not in bound
                if rfree and not lfree:
                    lhs, rhs = rhs, lhs
                parts = [self.one(lhs, bound) if isinstance(lhs, Variable) else self.term_text(lhs),
                         self.one(rhs, bound) if isinstance(rhs, Variable) else self.term_text(rhs)]
                return [f"(= {parts[0]} {parts[1]})"]
            parts = [self.term_text(t) for t in (lhs, rhs)]
            op = l.op.value
            if parts[0] == "0" and parts[1] != "0":
                # `0` stands second: the constraint mirrored
                parts.reverse()
                op = {"<": ">", ">": "<", "<=": ">=", ">=": "<="}.get(op, op)
            return [f"({op} {parts[0]} {parts[1]})"]
        if isinstance(l, Disjunction):
            return self.disj(l, bound)
        if isinstance(l, BoolLiteral):
            self.c.todo.add("bool", str(l.value))
            return [f"({'true' if l.value else 'false'})"]
        self.c.todo.add("literal-kind", type(l).__name__)
        return [repr(l)]

    def defect(self, name: str) -> bool:
        """The relation `name` read in this scope is a defect relation."""
        got = getattr(self.c, "all_inline", {}).get(name)
        if got is None:
            return False
        for i in range(len(self.scope), -1, -1):
            if (self.scope[:i], name) in self.c.rels:
                return self.scope[:i] == got[0].scope.components
        return False

    def universal(self, atom: Atom, bound: set[str]) -> list[str]:
        """`!R(args)` where R is a defect relation: ALL over R's domain."""
        u, test_i = self.c.all_inline[atom.relation.name]
        m: dict[str, str] = {}
        taken = set(bound) | set(self.rename) | set(self.rename.values()) | self.clause_vars
        for h, a in zip(u.head.args, atom.args):
            if isinstance(a, Variable):
                m[h.name] = a.name
        inner: set[str] = set()
        collect_vars(list(u.body), inner)
        for v in sorted(inner):
            if v not in m:
                n = v
                while n in taken or n in m.values():
                    n += "m"
                m[v] = n
        key_vars = {m[h.name] for h, a in zip(u.head.args, atom.args) if isinstance(a, Variable)}
        body = [subst(l, m) for l in u.body]
        test = body[test_i]
        dom = []
        for i, l in enumerate(body):
            if i == test_i:
                continue
            if isinstance(l, AtomLiteral) and not l.negated:
                vs: set[str] = set()
                collect_vars([l], vs)
                if vs and vs <= key_vars:
                    continue   # the key's own guard
            dom.append(l)
        if isinstance(test, AtomLiteral):
            flipped = AtomLiteral(test.atom, False)
        else:
            flipped = Comparison(NEG_OP[test.op], test.lhs, test.rhs, test.line)
        bb = set(bound)
        self.depth += 1
        try:
            dl = self.lits(dom, bb)
        except Dead:
            return []    # the defect relation is empty, so its negation holds
        finally:
            self.depth -= 1
        self.depth += 1
        try:
            tl = self.lits([flipped], bb)
        finally:
            self.depth -= 1
        return wrap("(ALL ", [dl, tl])

    def note(self, name: str, negated: bool) -> None:
        n = name.split(".")[0]
        if self.depth:
            self.nested.add(n)
        else:
            (self.top_neg if negated else self.top_pos).add(n)

    def lits(self, lits, bound: set[str], bound_before: set[str] | None = None) -> list[str]:
        """`bound` holds the labels already written, which a later site names
        without `*`; `bound_before` holds the labels the atoms before bind, where
        that is fewer, as in a later branch of an `OR`."""
        vs: set[str] = set()
        collect_vars(list(lits), vs)
        self.clause_vars |= {self.label(v) for v in vs}
        out: list[str] = []
        for l in self.reorder(list(lits), bound if bound_before is None else bound_before):
            out.extend(self.lit(l, bound))
        return out

    def reorder(self, lits, bound: set[str]):
        """The literals with each test after the literals that bind its
        labels: a comparison or a negation waits for its last binder."""
        def vs(t) -> set[str]:
            out: set[str] = set()
            collect_vars([AtomLiteral(Atom(RelationName((), "_"), (t,), 0), False)], out)
            return {self.label(v) for v in out}

        def binds(l) -> set[str]:
            if isinstance(l, AtomLiteral) and not l.negated:
                return set().union(*(vs(a) for a in l.atom.args)) if l.atom.args else set()
            if isinstance(l, Comparison) and l.op.value == "=":
                return vs(l.lhs) | vs(l.rhs)
            if isinstance(l, Disjunction):
                sets = []
                for b in l.branches:
                    bb: set[str] = set()
                    for x in b:
                        bb |= binds(x)
                    sets.append(bb)
                return set.intersection(*sets) if sets else set()
            return set()

        def ready(l, B: set[str]) -> bool:
            if isinstance(l, Comparison):
                if isinstance(l.lhs, Aggregate) or isinstance(l.rhs, Aggregate):
                    return True
                lv, rv = vs(l.lhs), vs(l.rhs)
                if lv | rv <= B:
                    return True
                if l.op.value == "=":
                    return (isinstance(l.lhs, Variable) and rv <= B) or (isinstance(l.rhs, Variable) and lv <= B)
                return False
            if isinstance(l, AtomLiteral) and l.negated:
                return set().union(*(vs(a) for a in l.atom.args)) <= B if l.atom.args else True
            if isinstance(l, Disjunction):
                return all(placeable(b, B) for b in l.branches)
            got = algebra_modes(l)
            if got is not None:
                name, cols, args = got
                return any(all(pascal(c) in cols and is_bound(args[cols.index(pascal(c))], B) for c in m)
                           for m in ALGEBRA_MODES[name])
            return True

        def placeable(branch, B0: set[str]) -> bool:
            """Every literal of a branch has its turn, given the labels B0."""
            B2, rem = set(B0), list(branch)
            while rem:
                for x in rem:
                    if ready(x, B2):
                        rem.remove(x)
                        B2 |= binds(x)
                        break
                else:
                    return False
            return True

        def is_bound(t, B: set[str]) -> bool:
            return not isinstance(t, Wildcard) and vs(t) <= B

        def algebra_modes(l):
            """(column names, args) of a positive atom of an algebra relation."""
            if not isinstance(l, AtomLiteral) or l.negated or l.atom.relation.instances not in ((), ("@lib",)):
                return None
            name, cols, kind, _ = self.c.resolve(l.atom.relation, self.scope, self.sub)
            if kind != "lib" or cols is None or len(cols) != len(l.atom.args):
                return None
            # the atom still reads the lib's own names, which the emission renames
            ren = libmap.REL.get(name)
            if ren is not None:
                name, cols = ren.name, [(Col(ren.parts.get(c.name, c.name), c.type, c.tparam), x) for c, x in cols]
            if name not in ALGEBRA_MODES:
                return None
            return name, [c.name for c, _ in cols], l.atom.args

        B = set(bound)
        everything: set[str] = set(B)
        for l in lits:
            everything |= binds(l)
        # A label no literal binds, such as a stripped case label, waits for
        # nothing.
        mentioned: set[str] = set()
        for l in lits:
            if isinstance(l, AtomLiteral):
                for a in l.atom.args:
                    mentioned |= vs(a)
            elif isinstance(l, Comparison):
                mentioned |= vs(l.lhs) | vs(l.rhs)
        unbound = mentioned - everything
        B |= unbound
        everything |= unbound
        # A body whose algebra atoms no order makes safe, such as an `inline`
        # helper's, keeps its written order.
        rem, B3, moved = list(lits), set(B), True
        while moved:
            moved = False
            for x in list(rem):
                if isinstance(x, Comparison) and not ready(x, B3):
                    continue
                if (algebra_modes(x) is not None or isinstance(x, Disjunction)) and not ready(x, B3):
                    continue
                rem.remove(x)
                B3 |= binds(x)
                moved = True
        orderable = not any(algebra_modes(x) is not None or isinstance(x, Disjunction) for x in rem)
        if not orderable and self.depth == 0:
            self.stuck = True
        out, pending = [], []
        for i, l in enumerate(lits):
            if orderable and (algebra_modes(l) is not None or isinstance(l, Disjunction)):
                # an algebra atom or an `OR` waits for the other literals' labels, never its own
                others = set(bound) | unbound
                for j, m in enumerate(lits):
                    if j != i:
                        others |= binds(m)
                wait = not ready(l, B) and ready(l, others)
            else:
                wait = (isinstance(l, Comparison) or isinstance(l, AtomLiteral) and l.negated) \
                    and not ready(l, B) and ready(l, everything)
            if wait:
                pending.append(l)
                continue
            out.append(l)
            B |= binds(l)
            moved = True
            while moved:
                moved = False
                for p_ in list(pending):
                    if ready(p_, B):
                        out.append(p_)
                        B |= binds(p_)
                        pending.remove(p_)
                        moved = True
        return out + pending

    def disj(self, d: Disjunction, bound: set[str]) -> list[str]:
        self.depth += 1
        try:
            return self._disj(d, bound)
        finally:
            self.depth -= 1

    def _disj(self, d: Disjunction, bound: set[str]) -> list[str]:
        if len(d.branches) == 2:
            iff = self.as_if(d, bound)
            if iff is not None:
                return iff
        # A first pass finds each branch's labels; the exported ones, made in
        # every branch, are made in the first branch, at a site where some
        # branch makes them all at sites, else by `(= *X Y)`, and the later
        # branches name them.
        live = []
        for b in d.branches:
            bb = set(bound)
            saved = list(self.c.todo.pending), Counter(self.c.todo.kinds)
            try:
                text = self.lits(b, bb)
            except Dead:
                continue
            finally:
                self.c.todo.pending, self.c.todo.kinds = saved
            live.append((b, bb - bound, " ".join(text)))
        if not live:
            raise Dead
        shared = set.intersection(*(a for _, a, _ in live))
        def at_sites(t: str) -> int:
            return sum(1 for v in shared if re.search(rf"(?<!\(= )\*{re.escape(v)}(?![\w])", t))
        first = max(range(len(live)), key=lambda k: (at_sites(live[k][2]), -k))
        order = [live[first], *(x for k, x in enumerate(live) if k != first)]
        groups = []
        for k, (b, _, _) in enumerate(order):
            bb = set(bound) | (shared if k else set())
            groups.append(self.lits(b, bb, set(bound)))
        bound |= shared
        if len(groups) == 1:
            return groups[0]
        return wrap("(OR ", groups)

    def as_if(self, d: Disjunction, bound: set[str]):
        b1, b2 = d.branches
        for i, l in enumerate(b1):
            if not isinstance(l, AtomLiteral) or l.negated:
                continue
            for j, m in enumerate(b2):
                if isinstance(m, AtomLiteral) and m.negated and m.atom.relation == l.atom.relation \
                        and m.atom.args == l.atom.args:
                    eb = set(bound)
                    tb = set(bound)
                    try:
                        test = self.lits([l], tb)
                    except Dead:      # the test never holds: the else alone
                        return self.lits(b2[:j] + b2[j + 1:], bound)
                    try:
                        then = self.lits(b1[:i] + b1[i + 1:], tb)
                    except Dead:      # the then never holds: the else under the negated test
                        return self.lits(list(b2), bound)
                    try:
                        els = self.lits(b2[:j] + b2[j + 1:], eb)
                    except Dead:      # the else never holds: the test and the then
                        return self.lits(list(b1), bound)
                    made_in_test = set()
                    collect_vars([l], made_in_test)
                    made_in_test = {self.label(v) for v in made_in_test} - bound
                    else_vars: set[str] = set()
                    collect_vars(list(b2[:j] + b2[j + 1:]), else_vars)
                    if made_in_test & {self.label(v) for v in else_vars}:
                        return None   # the else reads the test's labels: no IF
                    exported = (tb & eb) - bound
                    then_text, els_text = " ".join(then), " ".join(els)
                    if any(re.search(rf"\(= \*{re.escape(v)} ", then_text) and re.search(rf"(?<!\(= )\*{re.escape(v)}(?!\w)", els_text)
                           for v in exported):
                        return None   # the export is made at the else's site: an OR puts it first
                    bound |= exported
                    return wrap("(IF ", [test, then, els])
        return None


def demo_lines(rules, helpers: dict[str, list["Form"]]) -> list[str]:
    """A DEMONSTRATED form's DEMO_RULE blocks, each with the forms that only
    its `&prediction` reads, and the form's closing parenthesis."""
    out: list[str] = []
    for rule, text, rule_lines, _, head in rules:
        block = [f"  (DEMO_RULE {head}" + (f" {quote(text)}" if text else "")]
        body = render_forms(topo(helpers.get(rule, [])), "    ")
        block += body
        if body:
            block.append("")
        block += ["    " + l for l in rule_lines]
        close(block, ")")
        out += block
    close(out, ")")
    return out


def nest_keyed(key_body: list[str] | None, blocks: list[list[str]], knames, head: str,
               own: str | None = None, broadcast: set[int] | frozenset[int] = frozenset()) -> list[str]:
    """The key clause with the inputs that read a key label or the instance's
    own outputs inside it, then the inputs that read neither, and the blocks
    at the `broadcast` indices, whose inputs have no key column."""
    if key_body is None or "^" not in " ".join(key_body):
        return [l for b in blocks for l in b]
    pats = [re.compile(rf"(?<![\w:&.*^]){re.escape(k)}(?!\w)") for k in knames]
    lead = f"  ({head} ("
    out = [lead + key_body[0]] + [" " * len(lead) + l for l in key_body[1:]]
    close(out, ")")
    broad = []
    for bi, b in enumerate(blocks):
        text = " ".join(l for l in b if not l.lstrip().startswith(";;"))
        if bi not in broadcast and (any(p.search(text) for p in pats) or (own and f"({own}." in text)):
            out.extend("  " + l for l in b)
        else:
            broad.append(b)
    close(out, ")")
    return out + [l for b in broad for l in b]


def close(lines: list[str], parens: str) -> None:
    """Append `parens` to the last line that is no comment, and to the
    form's line when a comment ends the form."""
    for i in range(len(lines) - 1, -1, -1):
        if not lines[i].lstrip().startswith(";;"):
            j = lines[i].find(" ;;")
            lines[i] += parens
            return
    lines.append(parens)


def wrap(head: str, groups: list[list[str]]) -> list[str]:
    """`head` then each group in parentheses, one group per line, aligned."""
    pad = " " * len(head)
    out: list[str] = []
    for gi, g in enumerate(groups):
        if not g:
            g = []
        lines = []
        for li, line in enumerate(g):
            lines.append(("(" if li == 0 else " ") + line)
        if not lines:
            lines = ["("]
        close(lines, ")")
        prefix = head if gi == 0 else pad
        out.append(prefix + lines[0])
        out.extend(pad + l for l in lines[1:])
    close(out, ")")
    return out


# --------------------------------------------------------------------------
# Per solver


HEADER_RE = re.compile(r"^\s*@(scene|rule|approximated|representative|witness|keywords|draft|claim|store|derive|ignore|relaxed|reassigned)\b:?\s*(.*)$")


@dataclass
class Claim:
    kind: str     # INPUT | OUTPUT
    slug: str
    text: str
    approx: str | None = None


def directives(comment_lines: list[str]) -> list[tuple[str, str, int]]:
    """(directive, rest, indent) per directive line, continuation lines
    joined: a continuation is a line that opens with two spaces and no `@`."""
    out: list[list] = []
    for raw in comment_lines:
        m = re.match(r"^(\s*)@(\w[\w-]*)(.*)$", raw)
        if m and m.group(2) in ("relaxed", "reassigned") and out:
            out[-1][1] += f" @{m.group(2)} {m.group(3).strip()}"
        elif m:
            out.append([m.group(2), m.group(3).lstrip(":").strip() if m.group(2) not in ("scene", "rule") else m.group(3).strip(), len(m.group(1))])
        elif out and raw.startswith(" ") and raw.strip():
            out[-1][1] += " " + raw.strip()
        elif raw.strip().startswith("---"):
            continue
        else:
            out.append(["", raw.strip(), 0])
    return [(a, b, c) for a, b, c in out]


def comment_text(line: str) -> str | None:
    s = line.strip()
    if s.startswith("//"):
        return s[2:][1:] if s[2:3] == " " else s[2:]
    return None


def params_to_amp(text: str) -> str:
    return re.sub(r"params\.(\w+)", r"&\1", text)


def or_gloss(gloss: str) -> str:
    """The gloss of a DET_OR_RULE or RULE_OR_DET line, a space then the
    quoted prose above the declaration, or nothing where it has none."""
    return f" {quote(params_to_amp(gloss))}" if gloss.strip() else ""


def quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


class Solver:
    def __init__(self, stem: str, lib: Lib, sig: Lib, todo: Todo, inline: frozenset[str] = frozenset()) -> None:
        self.stem = stem
        self.todo = todo
        self.c = Converter(stem, lib, sig, todo, inline)
        self.lines = self.c.src_lines
        self.c.skip_rels = {"impl_choice"}

    # ---- header

    def header(self):
        lines = []
        for raw in self.lines:
            t = comment_text(raw)
            if t is None:
                if raw.strip():
                    break
                continue
            lines.append(t)
        claims: list[Claim] = []
        rep = None
        approx_witness: dict[str, list[str]] = defaultdict(list)
        for d, rest, ind in directives(lines[1:]):
            if d in ("scene", "rule"):
                m = re.match(r"([\w-]+):\s*(.*)", rest)
                if m:
                    claims.append(Claim("INPUT" if d == "scene" else "OUTPUT", m.group(1), params_to_amp(m.group(2))))
            elif d == "approximated" and claims:
                claims[-1].approx = params_to_amp(rest)
            elif d == "witness" and claims:
                approx_witness[claims[-1].slug].append(rest)
            elif d == "representative":
                rep = rest
        return claims, rep, approx_witness

    # ---- comments above a line

    def derives_from_params(self, u: Unit) -> bool:
        """A Params clause that reads only parameters and the lib, and no
        evidence: derived data, a RULE."""
        params = {r.name for r in self.c.prog.relations if r.scope.components == ("Params",)}

        def ok(lits) -> bool:
            for l in lits:
                if isinstance(l, AtomLiteral):
                    rn = l.atom.relation
                    if rn.instances or not (rn.name in params or rn.name in self.c.lib.top
                                            or rn.name in self.c.sig.top):
                        return False
                elif isinstance(l, Disjunction):
                    if not all(ok(b) for b in l.branches):
                        return False
                elif isinstance(l, Comparison) and any(isinstance(t, Aggregate) for t in (l.lhs, l.rhs)):
                    return False
            return True
        return ok(u.body or ())

    def open_amps(self) -> set[str]:
        return {self.c.rel_name(("Params",), n) for n in self.c.open_params}

    def comments_above(self, line: int) -> list[str]:
        out = []
        i = line - 2
        while i >= 0:
            t = comment_text(self.lines[i])
            if t is None:
                break
            out.append(t)
            i -= 1
        return list(reversed(out))

    def gloss_at(self, line: int) -> str:
        """The gloss of the declaration at `line`: its comment lines that
        are no directive."""
        return " ".join(rest for d, rest, _ in directives(self.comments_above(line)) if d == "")

    # ---- main

    def run(self) -> tuple[str, str]:
        c = self.c
        prog = c.prog
        claims, rep, approx_w = self.header()
        points = c.point_fields()
        concept = {adt.constructors[0].name for _, adt in points}
        all_ctors = {k.name: f for f, adt in points for k in adt.constructors}

        self.case_sets = c.case_sets = set()
        self.case_set_rows: dict[str, list[dict[str, str]]] = {}
        self.case_set_types: dict[str, set[str]] = {}
        c.case_set_unread = set()
        for r in prog.relations:
            if r.scope.components in ((), ("Parse",)) and r.columns and all(col.type.name in c.case_types for col in r.columns) \
                    and (r.name == "impl_choice" or not [u for u in prog.units if u.head.relation.name == r.name
                                                         and u.body is not None and u.scope.components == r.scope.components]):
                c.skip_rels.add(r.name)
                facts = [u for u in prog.units if u.head.relation.name == r.name and u.body is None]
                full = len(r.columns) == 1 and not [u for u in prog.units if u.head.relation.name == r.name
                                                     and u.body is not None] and \
                    {frozenset(ctor_names(u.head.args[0])) for u in facts} == \
                    {frozenset(v) for v in self.type_values(r.columns[0].type.name)}
                if not full and r.name != "impl_choice":
                    self.case_sets.add(r.name)
                    rows = []
                    for u in facts:
                        row = {}
                        def walk(t):
                            if isinstance(t, ConstructorTerm):
                                for f_, adt_ in self.c.point_fields():
                                    if any(k.name == t.name for k in adt_.constructors):
                                        row[f_] = t.name
                                for a in t.args:
                                    walk(a)
                            elif isinstance(t, RecordTerm):
                                for a in t.args:
                                    walk(a)
                        for a in u.head.args:
                            walk(a)
                        rows.append(row)
                    self.case_set_rows[r.name] = rows
                    self.case_set_types[r.name] = set().union(*(self.reached_types(col.type.name) for col in r.columns))
        c.skip_rels.discard("out")
        concept_of = {f_: adt_.constructors[0].name for f_, adt_ in c.point_fields()}
        for name, rows in self.case_set_rows.items():
            if not any(all(row.get(f_, k) == k for f_, k in concept_of.items()) for row in rows):
                c.case_set_unread.add(name)
        self.concept_of = concept_of
        # enumerators feeding impl_choice
        for u in prog.units:
            if not u.scope.components and u.head.relation.name == "impl_choice" and u.body:
                for l in u.body:
                    if isinstance(l, AtomLiteral):
                        c.skip_rels.add(l.atom.relation.name)

        # instance key names from the first input clause of each instance
        for u in prog.units:
            if u.head.relation.instances and u.body is not None:
                inst_path = u.head.relation.instances
                scope = u.scope.components
                key = None
                for i in range(len(scope), -1, -1):
                    if (scope[:i], inst_path[0]) in c.insts:
                        key = (scope[:i], inst_path[0])
                        break
                if key is None or len(inst_path) != 1 or key in c.key_names:
                    continue
                inst = c.insts[key]
                if inst.component not in c.lib.comps or not u.head.args:
                    continue
                tparams, lrels = c.lib.relations(inst.component)
                lr0 = next((r for r in lrels if r.name == u.head.relation.name), None)
                if lr0 is None or not lr0.cols or lr0.cols[0].name != "key":
                    continue
                sub = {p: a.name for p, a in zip(tparams, inst.type_args)}
                leaves = c.leaves("key", "Key", True, key[0], sub,
                                  outer=c.parse_sub if key[0] == ("Parse",) else {})
                ws = ClauseWriter(c, scope, {}, {})
                saved = list(self.todo.pending), Counter(self.todo.kinds)
                terms = ws.split(u.head.args[0], leaves)
                self.todo.pending, self.todo.kinds = saved
                spans = isinstance(u.head.args[0], Variable) and len(leaves) > 1
                names = [t.name if isinstance(t, Variable) and not spans else pascal(l.name)
                         for l, t in zip(leaves, terms) if l.kind in ("keep", "example")]
                c.key_names[key] = names
                c.key_paths[key] = [l.path for l in leaves if l.kind in ("keep", "example")]

        forms: list[Form] = []
        # a Parse relation the program fills from `in` is `in`, in every
        # form that reads it, the determination's included
        # (a relation with a clause that is no copy of `in` is no alias of it)
        not_copy: set[str] = set()
        for u in prog.units:
            path = u.head.relation.instances
            inst = c.insts.get(((), path[0])) if path and u.scope.components == () else None
            if inst is not None and inst.component in c.comps and len(path) == 1 and not (
                    u.body and len(u.body) == 1 and isinstance(u.body[0], AtomLiteral)
                    and u.body[0].atom.relation.name == "in"):
                not_copy.add(u.head.relation.name)
        for u in prog.units:
            path = u.head.relation.instances
            inst = c.insts.get(((), path[0])) if path and u.scope.components == () else None
            if inst is not None and inst.component in c.comps and len(path) == 1 and u.body \
                    and len(u.body) == 1 and isinstance(u.body[0], AtomLiteral) \
                    and u.body[0].atom.relation.name == "in" and u.head.relation.name not in not_copy:
                c.names[(("Parse",), u.head.relation.name)] = "__in__"
        # a copy of the program's parse in the determination takes the name
        # of what it copies, after the program's parse
        for key, x in c.det_parse_copies.items():
            c.rel_name(("Parse",), x)
            cand, k = x, 2
            while cand in c.used_names:
                cand, k = f"{x}{k}", k + 1
            c.used_names.add(cand)
            c.names[key] = cand

        # defect relations: read only under negation, one clause, one test
        reads_pos: Counter[str] = Counter()
        reads_neg: Counter[str] = Counter()
        reads_inst: Counter[str] = Counter()   # a read through an instance path

        def scan_reads(lits):
            for l in lits:
                if isinstance(l, AtomLiteral) and not l.atom.relation.instances:
                    (reads_neg if l.negated else reads_pos)[l.atom.relation.name] += 1
                elif isinstance(l, AtomLiteral):
                    reads_inst[l.atom.relation.name] += 1
                elif isinstance(l, Disjunction):
                    for b in l.branches:
                        scan_reads(b)
                elif isinstance(l, Comparison):
                    for t in (l.lhs, l.rhs):
                        if isinstance(t, Aggregate):
                            scan_reads(t.body)
        for u in prog.units:
            scan_reads(u.body or [])
        defs: dict[str, list[Unit]] = defaultdict(list)
        for u in prog.units:
            if not u.head.relation.instances and u.scope.components in ((), ("Parse",)):
                defs[u.head.relation.name].append(u)
        c.all_inline = {}
        for name, us in defs.items():
            if len(us) != 1 or reads_pos[name] or reads_inst[name] or not reads_neg[name] or name in c.skip_rels:
                continue
            u = us[0]
            if not u.body or any(isinstance(l, Disjunction) for l in u.body):
                continue
            if not all(isinstance(a, Variable) for a in u.head.args):
                continue
            r = c.rels.get((u.scope.components, name))
            if r is None or any(col.type.name in c.case_types for col in r.columns):
                continue
            negs = [i for i, l in enumerate(u.body) if isinstance(l, AtomLiteral) and l.negated]
            cmps = [i for i, l in enumerate(u.body) if isinstance(l, Comparison) and l.op in NEG_OP
                    and not isinstance(l.lhs, Aggregate) and not isinstance(l.rhs, Aggregate)]
            if len(negs) == 1:
                c.all_inline[name] = (u, negs[0])
            elif not negs and cmps:
                c.all_inline[name] = (u, cmps[-1])
        # a defect relation whose test negates another: the universal reads
        # that other relation positively, so it is declared
        for name, (u, i) in list(c.all_inline.items()):
            t = u.body[i]
            if isinstance(t, AtomLiteral) and not t.atom.relation.instances:
                c.all_inline.pop(t.atom.relation.name, None)
        self.all_count = len(c.all_inline)

        # params and determine
        params_decls = [r for r in prog.relations if r.scope.components == ("Params",)]
        # the proposers of each parameter's @derive lines
        self.derive_props = {r.name: list(dict.fromkeys(
            derive_proposer(rest) for d, rest, _ in directives(self.comments_above(r.span.first)) if d == "derive"))
            for r in params_decls if r.span}
        self.many = {n for n, ps in self.derive_props.items() if len(ps) > 1}

        det_units = defaultdict(list)
        for u in prog.units:
            if u.scope.components == ("Determine",) and not u.head.relation.instances:
                det_units[u.head.relation.name].append(u)
        det_units_all = {k: list(v) for k, v in det_units.items()}
        self.rigid_proposed: set[str] = set()   # the rigid parts a proposer's table gives
        param_facts: dict[str, list] = defaultdict(list)
        param_rules: dict[str, list] = defaultdict(list)
        for u in prog.units:
            if u.scope.components == ("Params",):
                if u.body is None:
                    param_facts[u.head.relation.name].append(u)
                else:
                    param_rules[u.head.relation.name].append(u)
        grid_params = defaultdict(list)
        for m in prog.macros:
            if isinstance(m, GridCall) and m.scope.components == ("Params",):
                grid_params[m.relation.name].append(m)

        arcdata_params: list[str] = []
        arcdata_excludes: list[str] = []
        derive_points: list[tuple[str, list]] = []
        # A Params relation the helpers derive is a parameter, its rows a
        # run's; a stored relation only those clauses read drops out.
        helper_derived = set(helper_rels(prog))
        helper_rows = helper_rows_of(c.stem) if helper_derived else {}
        for tiles, table in c.tile_frames.items():
            helper_rows[tiles] = unplaced_rows(helper_rows.get(table, []))
        param_names = {r.name for r in params_decls}
        read_elsewhere: set[str] = set()

        def collect(lits, in_params):
            for l in lits:
                if isinstance(l, AtomLiteral):
                    rn = l.atom.relation
                    if (in_params and not rn.instances) or rn.instances == ("params",):
                        read_elsewhere.add(rn.name)
                elif isinstance(l, Disjunction):
                    for b in l.branches:
                        collect(b, in_params)
                elif isinstance(l, Comparison):
                    for t in (l.lhs, l.rhs):
                        if isinstance(t, Aggregate):
                            collect(t.body, in_params)
        for u in prog.units:
            if u.scope.components == ("Params",) and u.head.relation.name in helper_derived:
                continue
            collect(u.body or (), u.scope.components == ("Params",))
        # a table whose clauses `field_plan` takes, a frame or a tiled frame of extents
        # that parameters give: instances over those parameters' DETs; else
        # one whose clauses read a frame of a stored extent: a Frame2D or
        # AxisFrame instance; and the sources of each stay
        fielded: dict[str, FieldPlan] = {}
        framed: dict[str, tuple[str, list, list]] = {}
        for name in helper_derived:
            fields = field_plan(param_rules.get(name, []), param_names)
            if fields is not None:
                fielded[name] = fields
                continue
            got = self.frame_plan(param_rules.get(name, []))
            if got is not None:
                framed[name] = got
        instanced = framed.keys() | fielded.keys()
        helper_inputs: set[str] = set()
        for u in prog.units:
            if u.scope.components == ("Params",) and u.head.relation.name in helper_derived \
                    and u.head.relation.name not in instanced:
                collect_into = set()
                for l in u.body or ():
                    if isinstance(l, AtomLiteral) and not l.atom.relation.instances:
                        collect_into.add(l.atom.relation.name)
                helper_inputs |= collect_into & param_names
        dropped = helper_inputs - read_elsewhere - helper_derived
        # the name a parameter's DET writes, where no stored side stands: the
        # derivation of a table the helpers derive, the proposer the plan
        # covers the parameter with, or the one whose domain the DET tests
        c.proposer_cols = {}
        covered: dict[str, str] = {}   # each parameter the plan covers with a proposer, its proposer
        helper_det: dict[str, tuple[str | None, str | None]] = {}   # each helper table: its derivation and its param
        for r in params_decls:
            ds = directives(self.comments_above(r.span.first)) if r.span else []
            types = [col.type.name for col in r.columns]
            if r.name in helper_derived and r.name not in dropped and r.name not in instanced:
                helper_det[r.name] = self.helper_derivation(
                    c.rel_name(("Params",), r.name), param_rules.get(r.name, []), helper_rows.get(r.name, []))
                prop = helper_det[r.name][0]
                name = libmap.DERIVATIONS[prop] if prop else None
            elif any(d == "derive" for d, _, _ in ds):
                if r.name in c.cand_params:
                    continue   # a DET_OR_RULE with a body: the columns its body's labels give
                # a DET_OR_RULE with no body: its first proposer's columns
                name = self.derive_props[r.name][0]
            elif r.name in c.cand_params:
                name = domain_proposer(types)
            else:
                name = plan_proposer(self.plan().get(r.name), types, r.name in c.open_params)
                if name in PROPOSER_COLS:
                    covered[r.name] = name
            if name in DET_COLS:
                c.proposer_cols[r.name] = DET_COLS[name]
        # each set-keyed table: its two parameters, one relation of its name
        decls = {r.name: r for r in params_decls}
        keyed: dict[str, KeyedTable] = {}
        for kt in keyed_tables({n: [col.type.name for col in r.columns] for n, r in decls.items()}, covered):
            if kt.name in c.used_names or any((("Params",), n) in c.names for n in (kt.child, kt.parent)):
                raise ValueError(f"{kt.child}, {kt.parent}: the name {kt.name} of their table is taken")
            c.used_names.add(kt.name)
            for n, cols in ((kt.child, kt.child_cols()), (kt.parent, kt.parent_cols())):
                c.names[(("Params",), n)] = kt.name
                c.proposer_cols[n] = cols
                keyed[n] = kt
        for r in params_decls:
            if r.name in dropped:
                det_units.pop(r.name, None)
                continue
            if r.name in fielded:
                forms.extend(self.field_forms(r, fielded[r.name]))
                continue
            if r.name in framed:
                forms.extend(self.frame_forms(r, framed[r.name]))
                continue
            if r.name in helper_derived:
                amp = c.rel_name(("Params",), r.name)
                cm = self.comments_above(r.span.first) if r.span else []
                gloss = " ".join(rest for d, rest, _ in directives(cm) if d == "")
                prop, record = helper_det[r.name]
                rows = helper_rows.get(r.name, [])
                f = Form([f"(DET {amp}{' ' + prop if prop else ''})"], amp, set(), line=r.span.first if r.span else 0)
                if prop is None:
                    self.todo.add("no-det-proposer", f"{amp}: no proposer gives the table")
                else:
                    self.todo.add("stored-fields", f"{amp}: the {libmap.DERIVATIONS[prop]} fields are stored")
                f.comments = [*(f";; {params_to_amp(g)}" for g in [gloss] if g), *self.todo.take()]
                forms.append(f)
                arcdata_params.append(record or mask_param(amp, rows) or
                                      "\n".join([f"(param {amp}"] + ["  (" + " ".join(row) + ")" for row in rows]) + ")")
                continue
            if r.name.startswith("_rigid_"):
                placed = r.name[len("_rigid_"):]
                if placed in c.rigid and (r.name in param_facts or r.name in grid_params):
                    arcdata_params.append(self.param_line(c.rel_name(("Params",), placed), r,
                                                          param_facts.get(r.name, []), grid_params.get(r.name, [])))
                continue
            if r.name in c.rigid:
                us = det_units.pop(r.name, [])
                for u in us:
                    forms.append(self.clause(u, "DET", ("Determine",), {}))
                verdict = self.plan().get(r.name)
                prop = covered_proposer(verdict, [col.type.name for col in r.columns[1:]])
                if not us and prop:
                    # a part whose value a proposer covers: its table is the proposer's
                    part = c.rel_name(("Determine",), r.name)
                    forms.append(Form([f"(DET {part} {prop})"], part, set(), line=r.span.first if r.span else 0))
                    self.rigid_proposed.add(r.name)
                continue
            cm = self.comments_above(r.span.first) if r.span else []
            ds = directives(cm)
            gloss = " ".join(rest for d, rest, _ in ds if d == "")
            derives = [rest for d, rest, _ in ds if d == "derive"]
            under = None   # the proposer of the @derive line an @ignore line stands under
            for d, rest, _ in ds:
                if d == "derive":
                    under = derive_proposer(rest)
                elif d == "ignore":
                    arcdata_excludes.extend(self.ignore_line(r.name, rest, concept, under))
                else:
                    under = None
            amp = c.rel_name(("Params",), r.name)
            kt = keyed.get(r.name)
            if kt is not None:
                # a set-keyed table: one DET and one param, at its child
                if r.name == kt.child:
                    f = Form([f"(DET {amp} {kt.proposer})"], amp, set(), line=r.span.first if r.span else 0)
                    parent = decls[kt.parent]
                    glosses = (gloss, self.gloss_at(parent.span.first) if parent.span else "")
                    f.comments = [f";; {params_to_amp(g)}" for g in glosses if g]
                    forms.append(f)
                    arcdata_params.append(self.keyed_param_line(amp, kt, param_facts, grid_params))
                continue
            if derives:
                props = self.derive_props[r.name]
                if r.name in c.cand_params:
                    # the stored reading: the candidates the examples show, kept by the program's fit
                    lab = pascal(r.columns[0].name)
                    f = Form([f"(DET_OR_RULE {amp}{or_gloss(gloss)} {' '.join(props)}", f"  (ex_input (:Col *{lab})))"],
                             amp, set(), line=r.span.first)
                else:
                    f = Form([f"(DET_OR_RULE {amp}{or_gloss(gloss)} {' '.join(props)})"], amp, set(),
                             line=r.span.first)
                forms.append(f)
                derive_points.append((amp, derives, "Derived", r.name))
            elif r.name in c.cand_params:
                # the candidates the determination tested: every value, kept by the fit
                types = [col.type.name for col in r.columns]
                f = Form([f"(DET {amp} {domain_proposer(types)})"], amp, set(),
                         line=r.span.first if r.span else 0)
                f.comments = [f";; {params_to_amp(gloss)}"] if gloss else []
                forms.append(f)
            elif r.name in param_rules:
                for u in param_rules[r.name]:
                    forms.append(self.clause(u, "RULE" if self.derives_from_params(u) else "DET", ("Params",), {}))
            elif r.name in det_units:
                for u in det_units.pop(r.name):
                    f = self.clause(u, "DET", ("Determine",), {}, name_scope=("Params",))
                    forms.append(f)
            elif r.name in c.orders:
                forms.append(self.order_form(r, amp, gloss))
            else:
                verdict = self.plan().get(r.name)
                types = [col.type.name for col in r.columns]
                prop = plan_proposer(verdict, types, r.name in c.open_params)
                if prop:
                    f = Form([f"(DET {amp} {prop})"], amp, set(), line=r.span.first if r.span else 0)
                    f.comments = [f";; {params_to_amp(gloss)}"] if gloss else []
                else:
                    f = Form([f"(DET {amp})"], amp, set(), line=r.span.first if r.span else 0)
                    kind = "no-det-rigid" if r.name.startswith("_rigid_") else \
                        "no-det-relation" if verdict and verdict[0] == "write" else \
                        "no-det-plan" if verdict is None or verdict[0] == "undecided" else "no-det-" + verdict[0]
                    why = "the plan gives no verdict" if verdict is None else \
                        "the plan leaves it undecided, and no type-domain proposer gives its value" \
                        if verdict[0] == "undecided" else " ".join(verdict[1:])
                    self.todo.add(kind, f"{amp}: {why}")
                    f.comments = [*(f";; {params_to_amp(g)}" for g in [gloss] if g), *self.todo.take()]
                forms.append(f)
            if r.name in param_facts or r.name in grid_params:
                arcdata_params.append(self.param_line(amp, r, param_facts.get(r.name, []), grid_params.get(r.name, [])))

        # each parameter's types, after its name
        self.param_types: dict[str, list[str]] = {}
        decl_of = {c.rel_name(("Params",), r.name): r for r in params_decls}
        for r in params_decls:
            if r.name.startswith("_rigid_") and r.name[len("_rigid_"):] in c.rigid:
                decl_of[c.rel_name(("Params",), r.name[len("_rigid_"):])] = r
        for i, text in enumerate(arcdata_params):
            m = re.match(r"\(param (\S+)", text)
            r = decl_of.get(m.group(1)) if m else None
            if r is None:
                continue
            kt = keyed.get(r.name)
            columns = r.columns if kt is None else keyed_row(decls[kt.parent].columns, decls[kt.child].columns)
            ts = [self.type_text(col.type.name) for col in columns
                  if col.type.name not in c.case_types and col.type.name not in c.open_types]
            self.param_types[m.group(1)] = ts
            types = ts[0] if len(ts) == 1 else "(" + " ".join(ts) + ")"
            arcdata_params[i] = grid_param(text[:m.end()] + " " + types, ts, text[m.end():]) or \
                wrap_param(text[:m.end()] + " " + types, text[m.end():])

        forms.extend(self.rigid_forms(det_units_all))

        for name, us in det_units.items():
            for u in us:
                if u.head.relation.instances and u.head.relation.instances[0] in ("ex",) and \
                        c.insts.get((("Determine",), u.head.relation.instances[0])) and \
                        c.insts[(("Determine",), u.head.relation.instances[0])].component in c.comps:
                    continue
        det_inst_units = defaultdict(list)
        for u in prog.units:
            if u.scope.components == ("Determine",):
                if u.head.relation.instances:
                    det_inst_units[u.head.relation.instances].append(u)
                elif u.head.relation.name in det_units:
                    forms.append(self.clause(u, "DET", ("Determine",), {}))

        # instances and clauses, in program order
        inst_units = defaultdict(list)
        for u in prog.units:
            sc = u.scope.components
            if sc in (("Params",), ("Determine",)):
                continue
            if u.head.relation.instances and sc == ():
                inst_units[u.head.relation.instances].append(u)
            elif u.head.relation.instances and sc == ("Parse",):
                inst_units[("Parse",) + u.head.relation.instances].append(u)

        # Parse inputs fed from `in`: alias
        parse_alias: dict[str, str] = {}
        for path, us in list(inst_units.items()):
            inst = c.insts.get(((), path[0]))
            if inst is not None and inst.component in c.comps and len(path) == 1:
                for u in us:
                    if u.body and len(u.body) == 1 and isinstance(u.body[0], AtomLiteral) \
                            and u.body[0].atom.relation.name == "in" and u.head.relation.name not in not_copy:
                        parse_alias[u.head.relation.name] = "in"
                    else:
                        forms.append(self.clause(u, "RULE", (), {}))
                del inst_units[path]
        for k in [k for k in det_inst_units if c.insts.get((("Determine",), k[0])) and
                  c.insts[(("Determine",), k[0])].component in c.comps]:
            del det_inst_units[k]
        self.parse_alias = parse_alias
        for n in parse_alias:
            c.names[(("Parse",), n)] = "__in__"


        # local clauses
        for u in prog.units:
            sc = u.scope.components
            if u.head.relation.instances:
                continue
            if sc not in ((), ("Parse",)):
                continue
            hn = u.head.relation.name
            if hn in c.skip_rels or hn in parse_alias and sc == ("Parse",):
                continue
            if hn == "impl_choice" or hn in c.all_inline or hn in c.demo_dropped:
                continue
            forms.append(self.clause(u, "RULE", sc, c.parse_sub if sc == ("Parse",) else {}))

        # instances
        for (sc, name), inst in c.insts.items():
            if inst.component not in c.lib.comps:
                continue
            if sc == ("Parse",):
                us = inst_units.get(("Parse", name), [])
                side = "RULE"
            elif sc == ("Determine",):
                us = det_inst_units.get((name,), [])
                side = "DET"
            elif sc == ():
                us = inst_units.get((name,), [])
                side = "RULE"
            elif sc == ("Params",) and inst.component != "ParamsHelpers":
                us = [u for u in prog.units if u.scope.components == sc and u.head.relation.instances == (name,)]
                side = "DET"
            else:
                continue
            forms.extend(self.instance(inst, us, side))
        for p in c.picks.values():
            pf = self.pick_form(p)
            if pf is not None:
                forms.append(pf)

        self.store_points = []
        decl_lines = [(r.span.first, r.name, None, r.scope.components) for r in prog.relations
                      if r.span and r.span.file is None and r.scope.components in ((), ("Parse",))]
        decl_lines += [(i.span.first, None, i, i.scope.components) for i in prog.instances
                       if i.span and i.span.file is None and i.scope.components in ((), ("Parse",))]
        for line, rname, inst, rscope in decl_lines:
            ds = directives(self.comments_above(line))
            gloss = " ".join(rest for d, rest, _ in ds if d == "")
            for d, rest, _ in ds:
                if d == "store":
                    m = re.match(r"(?:(\w+)\s*:)?\s*(.*)", rest)
                    sub_rel, more = m.groups()
                    sub_rel = sub_rel or ""
                    if inst is not None and inst.name in c.lib_moved:
                        # an expanded instance's directive: the relation of the shape that stands for its relation
                        was, moves = c.lib_moved[inst.name]
                        to = moves.get(sub_rel, inst.name).split(".")
                        amp = ".".join([c.rel_name(inst.scope.components, to[0]), *to[1:]])
                        wid = was + ("." + sub_rel if sub_rel else "")
                    elif inst is not None:
                        amp = c.rel_name(inst.scope.components, inst.name) + ("." + sub_rel if sub_rel else "")
                        wid = inst.name + ("." + sub_rel if sub_rel else "")
                    else:
                        amp = c.rel_name(rscope, rname)
                        wid = rname
                    if inst is not None:
                        c.wrote(amp, Written(inst.scope.components, wid, False))
                    self.store_points.append((amp, [":" + more], "Stored", wid))
                    forms.append(Form([f"(RULE_OR_DET {amp}{or_gloss(gloss)})"],
                                      amp.split(".")[0] if inst else amp, set(), line=line))
                elif d == "ignore" and re.match(r"\w*\s*:?\s*(store|derive)\b", rest):
                    m = re.match(r"(?:(\w+)\s*:)?\s*(.*)", rest)
                    sub_rel, more = m.groups()
                    sub_rel = sub_rel or ""
                    target = (inst.name + ("." + sub_rel if sub_rel else "")) if inst is not None else rname
                    stored = any(d_ == "store" and (re.match(r"(?:(\w+)\s*:)?", r_).group(1) or "") == sub_rel
                                 for d_, r_, _ in ds)
                    arcdata_excludes.extend(self.ignore_line(target, more, concept, "store" if stored else None))

        for f in forms:
            if not f.claim_slugs and f.line:
                for d, rest, _ in directives(self.comments_above(f.line)):
                    if d == "claim":
                        f.claim_slugs = rest.split()

        forms = [f for f in forms if f is not None]
        # an open parameter's determination by a proposer, or with no body,
        # and its DET_OR_RULE line end in `(ONE)`, as its clauses do
        for f in forms:
            m = re.match(r"\((DET|DET_OR_RULE) (&[^\s)]+)", f.lines[0]) if len(f.lines) == 1 else None
            if not m or m.group(2) not in self.open_amps() or "(ONE)" in f.marks:
                continue
            f.marks.append("(ONE)")
            f.lines[0] = f.lines[0][:-1] + " (ONE))"
        arclog = self.render(forms, claims, points, concept, all_ctors)
        arcdata = self.arcdata(rep, arcdata_params, arcdata_excludes, points, concept, derive_points, approx_w)
        return arclog, arcdata

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
        c.made[(("Params",), r.name + "_frame")] = Written(("Params",), "helpers", True)
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

        def instance(suffix: str) -> str:
            # each instance stands for the `helpers` instance the clause reads
            c.made[(("Params",), r.name + suffix)] = Written(("Params",), "helpers", True)
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
            inst = frame("_frame", plan.read.extent)
            c.wrote(f"{inst}.cell", Written(("Params",), "helpers.frame_pos", False))
            read, cells = f"{inst}.cell", [("P", plan.read.cell)]
        else:
            outer, inner = frame("_outer", plan.read.outer), frame("_inner", plan.read.inner)
            inst = instance("_tiling")
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
        ("write",), ("determined",), or ("undecided",)."""
        if hasattr(self, "_plan"):
            return self._plan
        out: dict[str, tuple[str, ...]] = {}
        p = PLANS / f"{self.stem}.txt"
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
                    m2 = re.match(r"\s+(\w+)\((\d+)\)", line)
                    if m2:
                        out.setdefault(m2.group(1), ("overlimit", m2.group(2)))
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

    def param_line(self, amp, r, facts, grids) -> str:
        """The `param` form of `r`'s stored rows, with no column of an open
        type, each row once."""
        kept = [col.type.name not in self.c.open_types for col in r.columns]
        rows = list(dict.fromkeys(
            "(" + " ".join(self.value_text(a) for a, k in zip(u.head.args, kept) if k) + ")" for u in facts))
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
        plan finds the part's value covered."""
        c = self.c
        out: list[Form] = []
        for m in c.prog.macros:
            if not (isinstance(m, RigidCall) and m.scope.components == ("Params",)):
                continue
            amp = c.wrote("&" + m.block, Written(("Params",), m.block, True))
            lines, reads = [], set()
            for n in m.names:
                part = c.rel_name(("Determine",), n)
                det = c.rels.get((("Determine",), n))
                if not det_units.get(n) and n not in self.rigid_proposed:
                    self.todo.add("rigid-part", f"{part}: the determination derives no table")
                labs = [pascal(col.name) for col in
                        (det.columns if det else c.rels[(("Params",), n)].columns[1:])]
                lines.append(f"  ({part}" + "".join(f" *{l}" for l in labs) + ")")
                reads.add(part)
            head = [f"(RIGID_DET {amp}"] + lines
            close(head, ")")
            f = Form(head, amp, reads, line=m.span.first)
            f.comments = [*(";; " + t for t in self.plain_comments(m.span.first)), *self.todo.take()]
            out.append(f)
        return out

    def clause(self, u: Unit, side: str, scope, sub, name_scope=None, drop_neg=frozenset()) -> Form:
        c = self.c
        src = (u, side, scope, dict(sub), name_scope)
        sub = dict(sub)
        hname, hcols, kind, inst = c.resolve(u.head.relation, name_scope or scope, sub)
        rename: dict[str, str] = {}
        extra: list[str] = []
        branches: set[str] = set()
        rules: set[str] = set()   # the demonstrated rule the head names
        # unify var = var at top level
        body = list(u.body or [])
        eqs = [l for l in body if isinstance(l, Comparison) and l.op.value == "="
               and isinstance(l.lhs, Variable) and isinstance(l.rhs, Variable)]
        head_cols: list[tuple[str, object]] = []
        col_names: list[list[str]] = []   # per head column, the names of its kept leaves
        if hcols is not None and len(hcols) == len(u.head.args):
            w = ClauseWriter(c, scope, sub, {})
            for (col, leaves), arg in zip(hcols, u.head.args):
                col_names.append([])
                kept = []
                for leaf, t in zip(leaves, w.split(arg, leaves)):
                    if leaf.kind == "case":
                        branches.update(ctor_names(t))
                        continue
                    if leaf.kind == "rule":
                        rules.update(ctor_names(t))
                        continue
                    if leaf.kind == "drop":
                        continue
                    kept.append((leaf, t))
                nkeep = sum(1 for l, _ in kept if l.kind == "keep")
                for leaf, t in kept:
                    head_cols.append(("E" if leaf.kind == "example" else leaf.name if nkeep > 1 else col.name, t))
                    col_names[-1].append(head_cols[-1][0])
        else:
            self.todo.add("head", souffle_term(u.head))
        head_vars = {t.name for _, t in head_cols if isinstance(t, Variable)}
        for e in eqs:
            a, b = e.lhs.name, e.rhs.name
            if b in head_vars and a not in head_vars:
                a, b = b, a
            rename[b] = a
            body.remove(e)
        given: dict[str, str] = {}   # a head variable -> the column it names
        repeats: list[tuple[str, str]] = []
        eqmap = dict(rename)
        for colname, t in head_cols:
            if isinstance(t, Variable):
                v = eqmap.get(t.name, t.name)
                if v in given:
                    extra.append(f"(= {colname} {given[v]})")
                    repeats.append((colname, given[v]))
                    continue
                given[v] = colname
                for k, val in eqmap.items():
                    if val == v:
                        rename[k] = colname
                rename[v] = colname
            elif (isinstance(t, NumberTerm) and t.value == 0) or (isinstance(t, DefinedName) and t.name == "ZERO"):
                extra.append(f"(= {colname} 0)")
            elif isinstance(t, DefinedName):
                self.todo.add("literal", t.name)
                extra.append(f"(= {colname} {t.name})")
            else:
                if not set(ctor_names(t)) & c.select_ctors:
                    self.todo.add("head-term", f"{colname} = {souffle_term(t)}")
                extra.append(f"(= {colname} {souffle_term(t)})")
        # avoid capturing: a body variable whose name a head column took
        targets = set(rename.values())
        vars_ = set()
        collect_vars(body, vars_)
        for v in vars_:
            if v not in rename and v in targets:
                n = 2
                while f"{v}{n}" in targets or f"{v}{n}" in vars_:
                    n += 1
                rename[v] = f"{v}{n}"
        w = ClauseWriter(c, scope, sub, rename)
        w.drop_neg = frozenset(drop_neg)
        bound: set[str] = set()
        try:
            lines = w.lits(body, bound)
        except Dead:
            return None
        if w.stuck:
            c.unsafe.add(u.head.relation.name)
        # a top-level `(= *X Y)` left where a disjunction kept one branch is
        # a rename: Y's site makes X
        cols_here = {n for n, _ in head_cols}
        for line in list(lines):
            m = re.fullmatch(r"\(= \*(\w+) ([A-Z]\w*)\)", line)
            if m and m.group(2) not in cols_here and m.group(2) != m.group(1):
                x, y = m.groups()
                lines.remove(line)
                lines = relabel(lines, lambda mark, v: mark + (x if v == y else v))
            elif m and m.group(1) in cols_here and m.group(2) in cols_here and m.group(2) != m.group(1):
                repeats.append(m.groups())   # the kept branch makes one head column the other's
        for e in extra:
            m = re.match(r"\(= (\w+) ", e)
            if m and m.group(1) not in bound:
                bound.add(m.group(1))
                e = f"(= *{e[3:]}"
            lines.append(e)
        branches |= w.branches
        marks = self.one_lines(u, col_names)
        if side == "DET" and hname in self.open_amps() and "(ONE)" not in marks:
            marks.append("(ONE)")   # an open parameter: each of its values is a model
        todos = self.todo.take()
        name = hname
        head_line = f"({side} {name}"
        f = Form([head_line] + ["  " + l for l in lines + marks], name, w.reads, line=u.span.first if u.span else 0)
        close(f.lines, ")")
        f.body = list(lines)
        f.marks = marks
        f.cols = [n for n, _ in head_cols]
        f.side = side
        if len(f.lines) == 1:
            pass
        f.branches = tuple(sorted(branches))
        f.comments = [*(";; " + t for t in self.plain_comments(f.line)), *todos]
        p = None if u.head.relation.instances else c.one_marks.get((u.scope.components, u.head.relation.name))
        if p is not None and u.span and u.span.first == min(
                x.span.first for x in c.prog.units if x.span and x.head.relation == u.head.relation
                and x.scope == u.scope):
            # the pick's own comments, on its first clause
            f.comments[:0] = [";; " + t for t in self.plain_comments(p.line)]
            for d, rest, _ in directives(self.comments_above(p.line)):
                if d == "claim":
                    f.claim_slugs = rest.split()
        f.src = src
        f.head_repeat = repeats
        f.top_pos, f.top_neg, f.nested = w.top_pos, w.top_neg, w.nested
        if len(rules) == 1:
            f.demo_rule = next(iter(rules))
        return f

    def one_lines(self, u: Unit, col_names: list[list[str]]) -> list[str]:
        """The ONE marks of a clause of a folded pick, over its column labels."""
        p = None if u.head.relation.instances else self.c.one_marks.get((u.scope.components, u.head.relation.name))
        if p is None:
            return []
        for note in p.notes:
            self.todo.add("pick-read", note)
        if len(col_names) != len(p.fold):
            self.todo.add("one", "the picked relation's columns")
            return []
        name = {}
        gone = set()   # a column the clause drops: a case's or a lifted key
        for v, ns in zip(p.fold, col_names):
            if v is not None and len(ns) == 1:
                name[v] = ns[0]
            elif v is not None and not ns:
                gone.add(v)
        out = []
        for key in p.ones:
            key = [v for v in key if v not in gone]
            if any(v not in name for v in key):
                self.todo.add("one", f"a key column of {' '.join(key)}")
                continue
            out.append("(" + " ".join(["ONE"] + [name[v] for v in key]) + ")")
        return out

    def plain_comments(self, line: int) -> list[str]:
        out = []
        for d, rest, _ in directives(self.comments_above(line)):
            if d == "" and rest and not rest.startswith("---"):
                out.append(params_to_amp(rest))
        return out

    # ---- instances

    def instance(self, inst, us: list[Unit], side: str, empty: frozenset[str] = frozenset(),
                 split: frozenset[str] = frozenset()) -> list[Form]:
        c = self.c
        # input clauses whose heads name branches of one point: one instance
        # per named branch, which holds that branch's clauses and the clauses
        # that name no branch of the point, and one of the latter alone for
        # the branches no clause names
        points = list(c.point_fields())
        point_of = {k.name: f_ for f_, adt_ in points for k in adt_.constructors}
        _, lrs = c.lib.relations(inst.component) if inst.component in c.lib.comps else (None, [])
        keyed = {lr.name for lr in lrs if lr.cols and lr.cols[0].name == "key"}
        named = [{k for k in ctor_names(u.head.args[0]) if k in point_of}
                 if u.head.args and u.head.relation.name in keyed else set() for u in us]
        for f_, adt_ in points:
            if f_ in split:
                continue   # split already
            ks = [k.name for k in adt_.constructors if any(k.name in ns for ns in named)]
            free = [u for u, ns in zip(us, named) if not any(point_of[x] == f_ for x in ns)]
            if not ks or (len(ks) == 1 and not free):
                continue
            out: list[Form] = []
            for k in ks:
                part = [u for u, ns in zip(us, named) if not any(point_of[x] == f_ and x != k for x in ns)]
                # a form of the branch's instance holds in that branch alone,
                # also where none of its clauses names the branch
                for g in self.instance(inst, part, side, empty, split | {f_}):
                    g.branches = tuple(sorted(set(g.branches) | {k}))
                    out.append(g)
            c0 = adt_.constructors[0].name
            rest = {k.name for k in adt_.constructors} - set(ks)
            # an input that reads the instance's outputs makes no row alone
            gen = [u for u in free if u.body is None or not any(
                isinstance(l, AtomLiteral) and l.atom.relation.instances[:1] == (inst.name,) for l in u.body)]
            if gen and rest:
                gs = self.instance(inst, free, side, empty, split | {f_})
                if c0 in ks:
                    for g in gs:
                        g.branches = tuple(sorted(set(g.branches) | rest))
                out.extend(gs)
            # a form that writes what a form of fewer branches writes repeats
            # it: the latter holds wherever the former does
            concept = {adt.constructors[0].name for _, adt in points}
            kept: list[Form] = []
            for g in sorted(out, key=lambda g: len(set(g.branches) - concept)):
                if not any(h.lines == g.lines and set(h.branches) - concept <= set(g.branches) for h in kept):
                    kept.append(g)
            return [g for g in out if any(g is h for h in kept)]
        c.cur_empty = empty
        try:
            return self._instance(inst, us, side, empty)
        finally:
            c.cur_empty = frozenset()

    def _instance(self, inst, us: list[Unit], side: str, empty: frozenset[str]) -> list[Form]:
        c = self.c
        if empty:
            scope0 = inst.scope.components
            lsub0 = c.parse_sub if scope0 == ("Parse",) else {}
            live = []
            saved = list(self.todo.pending), Counter(self.todo.kinds)
            for u in us:
                if u.body is None:
                    live.append(u)
                    continue
                try:
                    ClauseWriter(c, scope0, lsub0, {}).lits(list(u.body), set())
                    live.append(u)
                except Dead:
                    pass
            self.todo.pending, self.todo.kinds = saved
            # an instance whose every input is empty, or reads its own
            # outputs alone, holds no row
            if us and not any(u.body is not None and not all(
                    isinstance(l, AtomLiteral) and l.atom.relation.instances[:1] == (inst.name,)
                    for l in u.body if isinstance(l, AtomLiteral) and not l.negated) for u in live):
                return []
            us = live
        if (inst.scope.components, inst.name) in c.demo_insts and any(
                u.head.relation.name == "prediction" for u in us):
            return self.demonstrated_form(inst, us, side)
        orig_us = us
        scope = inst.scope.components
        key = (scope, inst.name)
        amp = c.rel_name(scope, inst.name)
        tparams, rels = c.lib.relations(inst.component)
        sub = {p: a.name for p, a in zip(tparams, inst.type_args)}
        if scope == ("Parse",):
            sub = {p: c.parse_sub.get(a.name, a.name) for p, a in zip(tparams, inst.type_args)}
        lsub = c.parse_sub if scope == ("Parse",) else {}
        knames = c.key_names.get(key, [])
        # the inputs the lib declares with no key column: broadcasts, which
        # read no key label and add no branch to the key clause
        unkeyed = {lr.name for lr in rels if lr.is_input and not (lr.cols and lr.cols[0].name == "key")}
        kn = knames   # the key labels in scope in the input at hand

        def kren(u):
            return {} if u.head.relation.name in unkeyed else self.key_rename(u, key_leaves, knames)
        by_rel: dict[str, list[Unit]] = defaultdict(list)
        for u in us:
            by_rel[u.head.relation.name].append(u)
        lines = [f"(INIT {amp} {inst.component}"]
        reads: set[str] = set()
        branches: set[str] = set()
        # the branches the key columns of the input heads name
        case_ctors = {k.name for _, adt_ in c.point_fields() for k in adt_.constructors}
        for u in us:
            if u.head.relation.name not in unkeyed and u.head.args:
                branches.update(x for x in ctor_names(u.head.args[0]) if x in case_ctors)
        key_leaves = c.leaves("key", "Key", True, scope, sub, outer=lsub)
        has_key = any(l.kind in ("keep", "example") for l in key_leaves)
        # the key clause: the atoms over key labels alone, where every input
        # clause shares them; else the union of the generators' bodies
        residual: dict[int, list] = {}
        key_body: list[str] | None = None
        blocks: list[list[str]] = []
        if has_key:
            kset = set(knames)

            def key_atoms(u):
                ren = kren(u)
                idx = []
                for i, l in enumerate(u.body or []):
                    if not isinstance(l, AtomLiteral) or l.negated:
                        continue
                    if l.atom.relation.instances[:1] == (inst.name,):
                        continue
                    probe = ClauseWriter(c, scope, lsub, ren, own_inst=key)
                    saved = list(self.todo.pending), Counter(self.todo.kinds)
                    text = " ".join(probe.lits([l], set()))
                    self.todo.pending, self.todo.kinds = saved
                    vs = set(re.findall(r"(?<![(:\w&.])[*^]?([A-Z]\w*)", text))
                    if vs and vs <= kset:
                        idx.append(i)
                # an algebra atom whose labels the other key atoms do not all
                # bind stays with the member atoms
                texts = {}
                for i in idx:
                    probe = ClauseWriter(c, scope, lsub, ren, own_inst=key)
                    saved = list(self.todo.pending), Counter(self.todo.kinds)
                    texts[i] = " ".join(probe.lits([u.body[i]], set()))
                    self.todo.pending, self.todo.kinds = saved

                def labels(t: str) -> set[str]:
                    return set(re.findall(r"(?<![(:\w&.])[*^]?([A-Z]\w*)", t))
                algebra = {i for i in idx if (m := re.match(r"\((\w+)", texts[i])) and m.group(1) in ALGEBRA_MODES}
                bound_by_members = set().union(set(), *(labels(texts[i]) for i in idx if i not in algebra))
                idx = [i for i in idx if i not in algebra or labels(texts[i]) <= bound_by_members]
                return ren, idx

            groups = {}
            for u in us:
                if u.body is None or u.head.relation.name in unkeyed:
                    continue
                ren, idx = key_atoms(u)
                if not idx:
                    continue
                w = ClauseWriter(c, scope, lsub, ren, own_inst=key)
                ls = mark_key(w.lits([u.body[i] for i in idx], set()), knames)
                groups[id(u)] = (ls, idx, w)
            gens = [u for u in us if u.body is not None and u.head.relation.name not in unkeyed and not any(
                isinstance(l, AtomLiteral) and l.atom.relation.instances[:1] == (inst.name,) for l in u.body)]
            shared = None
            if gens and all(id(u) in groups for u in gens):
                cands = {tuple(groups[id(u)][0]) for u in gens}
                if len(cands) == 1:
                    shared = list(next(iter(cands)))
            if shared is not None and all(set(knames) <= {x.lstrip("^") for x in re.findall(r"\^\w+", " ".join(shared))} for _ in [0]):
                key_body = list(shared)
                for u in us:
                    g = groups.get(id(u))
                    if g and g[0] == shared:
                        residual[id(u)] = [l for i, l in enumerate(u.body) if i not in g[1]]
                        reads |= g[2].reads
            elif gens:
                uniq = []
                for u in gens:
                    ren = kren(u)
                    w = ClauseWriter(c, scope, lsub, ren, own_inst=key)
                    ls = mark_key(w.lits(list(u.body), set()), knames)
                    reads |= w.reads
                    branches |= w.branches
                    if ls not in uniq:
                        uniq.append(ls)
                uniq = drop_implied(uniq)
                key_body = list(uniq[0] if len(uniq) == 1 else wrap("(OR ", share_labels(uniq)))
        def head_terms(u, lr, ren):
            """Each non-key column of the input's head: (col, [(leaf, term)])."""
            out = []
            for i, (col, arg) in enumerate(zip(lr.cols, u.head.args)):
                if i == 0 and col.name == "key":
                    continue
                leaves = c.leaves(col.name, col.type, col.tparam, scope, sub, outer=lsub)
                terms = ClauseWriter(c, scope, lsub, ren).split(arg, leaves)
                for l, t in zip(leaves, terms):
                    if l.kind == "case":
                        branches.update(ctor_names(t))
                kept = [(l, t) for l, t in zip(leaves, terms) if l.kind in ("keep", "example")]
                if kept:
                    out.append((col, kept))
            return out

        def is_zero(t) -> bool:
            return (isinstance(t, NumberTerm) and t.value == 0) or (isinstance(t, DefinedName) and t.name == "ZERO")

        def lab_of(t, ren) -> str:
            if isinstance(t, Variable):
                return ren.get(t.name, t.name)
            if is_zero(t):
                return "0"
            if isinstance(t, DefinedName):
                self.todo.add("literal", t.name)
                return t.name
            if not set(ctor_names(t)) & c.select_ctors:
                self.todo.add("head-term", souffle_term(t))
            return souffle_term(t)

        def site_text(col, labs: list[str], leaves) -> str:
            if col.tparam and len(labs) > 1:
                return f"(:{col.name} {' '.join(field_sites(field_names(leaves), labs))})"
            if col.tparam:
                return f"(:{col.name} {' '.join(labs)})"
            if labs[0] == col.name and len(labs) == 1:
                return labs[0]
            return f"(:{col.name} {' '.join(labs)})"

        def fresh(base: str, taken: set[str]) -> str:
            lab, n = base, 2
            while lab in taken:
                lab, n = f"{base}{n}", n + 1
            taken.add(lab)
            return lab

        def zero_sites(hts, ren, taken: set[str]) -> tuple[list[str], list[str]]:
            """The head sites, each zero term a label named after its leaf,
            and the `(= *X 0)` that makes each such label."""
            sites_, eqs = [], []
            for col, kept in hts:
                labs = []
                for leaf, t in kept:
                    if is_zero(t):
                        lab = fresh(pascal(leaf.name), taken)
                        eqs.append(f"(= *{lab} 0)")
                        labs.append(lab)
                    else:
                        labs.append(lab_of(t, ren))
                sites_.append(site_text(col, labs, [l for l, _ in kept]))
            return sites_, eqs

        def fact_block(u, lr):
            key_arg = u.head.args[0] if u.head.args and lr.cols and lr.cols[0].name == "key" else None
            hts = head_terms(u, lr, {})
            if (key_arg is None or (isinstance(key_arg, ConstructorTerm) and key_arg.name == "U")) \
                    and all(is_zero(t) for _, kept in hts for _, t in kept):
                sites_, eqs = zero_sites(hts, {}, set(kn))
                block = [f"  ({lr.name} ({' '.join(sites_)})"] + ["    " + e for e in eqs]
                close(block, ")")
                return block
            self.todo.add("input-fact", souffle_term(u.head))
            return [f"  ;; TODO input-fact: {souffle_term(u.head)}"]

        def skipped(u, lr) -> bool:
            """An input clause the engine fills from the key."""
            ren = kren(u)
            saved = list(self.todo.pending), Counter(self.todo.kinds)
            labs = [lab_of(t, ren) for _, kept in head_terms(u, lr, ren) for _, t in kept]
            self.todo.pending, self.todo.kinds = saved
            skip = all(lab in kn for lab in labs)
            own_read = any(isinstance(l, AtomLiteral) and l.atom.relation.instances[:1] == (inst.name,)
                           for l in u.body)
            return skip and ((own_read and len(u.body) == 1) or not residual.get(id(u), list(u.body)))

        def single(u, lr) -> list[str]:
            ren = kren(u)
            hts = head_terms(u, lr, ren)
            w = ClauseWriter(c, scope, lsub, ren, own_inst=key)
            body = w.lits(residual.get(id(u), list(u.body)), set(kn))
            taken = set(kn) | label_names(body) | {
                ren.get(t.name, t.name) for _, kept in hts for _, t in kept if isinstance(t, Variable)}
            head_sites, eqs = zero_sites(hts, ren, taken)
            body = body + eqs
            reads.update(w.reads)
            branches.update(w.branches)
            block = ["  " + p for p in self.todo.take()]
            block.append(f"  ({lr.name} ({' '.join(head_sites)})")
            block.extend("    " + l for l in body)
            close(block, ")")
            return block

        def merged(us_, lr) -> list[str] | None:
            """The input's clauses as one input whose body is an OR, one
            branch per clause; None where the heads do not line up."""
            rens = [kren(u) for u in us_]
            saved = list(self.todo.pending), Counter(self.todo.kinds)
            hts = [head_terms(u, lr, r) for u, r in zip(us_, rens)]
            self.todo.pending, self.todo.kinds = saved
            shape = [(col.name, len(kept)) for col, kept in hts[0]]
            if any([(col.name, len(kept)) for col, kept in h] != shape for h in hts):
                return None
            terms = [[t for _, kept in h for _, t in kept] for h in hts]
            if any(not isinstance(t, Variable) and not is_zero(t) for ts in terms for t in ts):
                return None
            for u in us_:
                if u.body is None and u.head.args and lr.cols[0].name == "key" and \
                        not (isinstance(u.head.args[0], ConstructorTerm) and u.head.args[0].name == "U"):
                    return None
            taken: set[str] = set(kn)
            for u, r in zip(us_, rens):
                vs: set[str] = set()
                collect_vars(list(u.body or []), vs)
                collect_vars([AtomLiteral(u.head, False)], vs)
                taken |= {r.get(v, v) for v in vs}
            leaf_names = [l.name for _, kept in hts[0] for l, _ in kept]
            common: list[str] = []
            for p in range(len(terms[0])):
                cands: list[str] = [str(r.get(ts[p].name, ts[p].name)) for ts, r in zip(terms, rens) if isinstance(ts[p], Variable)]
                if not cands:
                    base, n = pascal(leaf_names[p]), 2
                    lab = base
                    while lab in taken or lab in common:
                        lab, n = f"{base}{n}", n + 1
                    taken.add(lab)
                    common.append(lab)
                    continue
                lab = cands[0]
                if lab in common:
                    q = common.index(lab)
                    if all(isinstance(ts[p], Variable) and isinstance(ts[q], Variable) and ts[p].name == ts[q].name
                           for ts in terms):
                        common.append(lab)   # every clause repeats the label in its head
                        continue
                if lab in common or (lab in kn and any(x != lab for x in cands)):
                    base = pascal(leaf_names[p])
                    lab, n = base, 2
                    while lab in taken or lab in common:
                        lab, n = f"{base}{n}", n + 1
                    taken.add(lab)
                common.append(lab)
            cols_ = {x for x in common if x != "0" and x not in kn}
            bodies = []
            for u, r, ts in zip(us_, rens, terms):
                ren = dict(r)
                assigned: dict[str, str] = {}
                extras: list[str] = []
                for p, t in enumerate(ts):
                    if isinstance(t, Variable):
                        lab = ren.get(t.name, t.name)
                        if t.name in assigned:
                            if assigned[t.name] != common[p]:
                                extras.append(f"(= *{common[p]} {assigned[t.name]})")
                        elif lab == common[p]:
                            assigned[t.name] = lab
                        elif lab in kn or common[p] in kn:
                            extras.append(f"(= *{common[p]} {lab})")
                        else:
                            ren[t.name] = common[p]
                            assigned[t.name] = common[p]
                    elif common[p] != "0":
                        extras.append(f"(= *{common[p]} 0)")
                vs = set()
                collect_vars(list(u.body or []), vs)
                for v in sorted(vs):
                    if v not in assigned and ren.get(v, v) in cols_:
                        base, n = ren.get(v, v), 2
                        while f"{base}{n}" in taken:
                            n += 1
                        ren[v] = f"{base}{n}"
                        taken.add(ren[v])
                lines_ = []
                if u.body is not None:
                    w = ClauseWriter(c, scope, lsub, ren, own_inst=key)
                    lines_ = w.lits(residual.get(id(u), list(u.body)), set(kn))
                    reads.update(w.reads)
                    branches.update(w.branches)
                bodies.append((self.todo.take(), lines_ + extras))
            head_sites, p = [], 0
            for col, kept in hts[0]:
                head_sites.append(site_text(col, common[p:p + len(kept)], [l for l, _ in kept]))
                p += len(kept)
            MERGES["input"] += 1
            block = [f"  ({lr.name} ({' '.join(head_sites)})"]
            block.extend("    " + l for l in or_body(bodies, cols_, set(kn)))
            close(block, ")")
            return block

        broadcast: set[int] = set()
        for lr in rels:
            if not lr.is_input or lr.name not in by_rel:
                continue
            kn = [] if lr.name in unkeyed else knames
            first = len(blocks)
            us_ = [u for u in by_rel[lr.name] if u.body is None or not skipped(u, lr)]
            facts = [u for u in us_ if u.body is None]
            if len(us_) > 1:
                block = merged(us_, lr)
                if block is not None:
                    blocks.append(block)
                    if lr.name in unkeyed:
                        broadcast.add(first)
                    continue
                MERGES["input-unmerged"] += 1
                if key not in c.demo_select:
                    self.todo.add("input-unmerged", f"{lr.name}: the clauses' heads do not line up")
            for u in us_:
                blocks.append(fact_block(u, lr) if u.body is None else single(u, lr))
            if lr.name in unkeyed:
                broadcast.update(range(first, len(blocks)))
        lines.extend(nest_keyed(key_body, blocks, knames, "key", amp, broadcast=broadcast))
        close(lines, ")")
        reads.discard(amp)
        f = Form(lines, amp, reads, line=inst.span.first if inst.span else 0)
        f.branches = tuple(sorted(branches))
        f.comments = [";; " + t for t in self.plain_comments(f.line)]
        f.src_inst = (inst, orig_us, side)
        cm = directives(self.comments_above(f.line))
        for d, rest, _ in cm:
            if d == "claim":
                f.claim_slugs = rest.split()
        return [f]

    def demonstrated_form(self, inst, us: list[Unit], side: str) -> list[Form]:
        """A DemonstrationConsistency instance as a DEMONSTRATED form: its
        `value` and `demonstration` inputs as an instance's, then a DEMO_RULE
        per rule, whose `&prediction` clause has the columns the `value`
        head names."""
        c = self.c
        preds = [u for u in us if u.head.relation.name == "prediction"]
        gs = self._instance(inst, [u for u in us if u not in preds], side, frozenset())
        if not gs:
            return gs
        f = gs[0]
        scope = inst.scope.components
        key = (scope, inst.name)
        tparams, _ = c.lib.relations(inst.component)
        sub = {p: a.name for p, a in zip(tparams, inst.type_args)}
        if scope == ("Parse",):
            sub = {p: c.parse_sub.get(a.name, a.name) for p, a in zip(tparams, inst.type_args)}
        lsub = c.parse_sub if scope == ("Parse",) else {}
        knames = c.key_names.get(key, [])
        key_leaves = c.leaves("key", "Key", True, scope, sub, outer=lsub)

        def head_labels(input_name: str) -> list[list[str]]:
            """The labels of each head site of the input, as the lines give them."""
            for line in f.lines:
                s = line.strip()
                if s.startswith(f"({input_name} (("):
                    inner = s[len(input_name) + 3:]
                    out, depth, cur = [], 0, ""
                    for ch in inner:
                        if ch == "(":
                            depth += 1
                            if depth == 1:
                                cur = ""
                                continue
                        elif ch == ")":
                            depth -= 1
                            if depth == 0:
                                out.append(cur.split()[1:])
                                continue
                            if depth < 0:
                                break
                        if depth >= 1:
                            cur += ch
                    return out
            return []
        vlabs = head_labels("value")
        flat_v = [x for ls in vlabs for x in ls]
        # the rules, in the order the type declares them
        order = []
        dem = c.find_type(inst.type_args[1].name, ())
        if isinstance(dem, AdtType):
            order = [k.name for k in dem.constructors]
        groups: dict[str, list[Unit]] = defaultdict(list)
        for u in preds:
            groups[u.head.args[1].name].append(u)
        reads: set[str] = set(f.reads)
        rules = []
        case_ctors = {k.name for _, adt_ in c.point_fields() for k in adt_.constructors}
        pred_branches: set[str] = set()
        fields_of: dict[str, list[str]] = {}
        for rule in sorted(groups, key=lambda r: order.index(r) if r in order else len(order)):
            rule_reads: set[str] = set()
            bodies = []
            texts: list[str] = []
            for u in groups[rule]:
                ren = self.key_rename(u, key_leaves, knames)
                targets = []
                for t, labs in zip(u.head.args[2:], vlabs):
                    if isinstance(t, Variable) and len(labs) == 1:
                        targets.append((t.name, labs[0]))
                vs: set[str] = set()
                collect_vars(list(u.body or ()), vs)
                given = {tl for _, tl in targets}
                for v, tl in targets:
                    ren[v] = tl
                for v in sorted(vs):
                    if v not in dict(targets) and ren.get(v, v) in given:
                        n = 2
                        while f"{ren.get(v, v)}{n}" in vs or f"{ren.get(v, v)}{n}" in given:
                            n += 1
                        ren[v] = f"{ren.get(v, v)}{n}"
                # the rule's fields, under the labels its first clause gives them
                fv = [a.name for a in u.head.args[1].args]
                if rule not in fields_of:
                    fields_of[rule] = [ren.get(v, v) for v in fv]
                ren.update(zip(fv, fields_of[rule]))
                w = ClauseWriter(c, scope, c.parse_sub if scope == ("Parse",) else {}, ren, own_inst=key)
                body = w.lits(list(u.body or ()), set())
                reads |= w.reads
                rule_reads |= w.reads
                pred_branches |= w.branches | {x for x in ctor_names(u.head.args[0]) if x in case_ctors}
                todos = self.todo.take()
                if len(targets) != len(vlabs):
                    self.todo.add("head-term", f"{rule}: a prediction head site that is no label")
                    todos += self.todo.take()
                texts += self.plain_comments(u.span.first if u.span else 0)
                bodies.append((todos, body))
            if not texts and isinstance(dem, AdtType):
                # the rule's text: the comments above its constructor
                ks = list(dem.constructors)
                at = next((n for n, k in enumerate(ks) if k.name == rule), None)
                if at is not None:
                    lo = ks[at - 1].span.first if at else dem.span.first
                    cm = [comment_text(self.lines[ln]) for ln in range(lo, ks[at].span.first - 1)]
                    texts = [params_to_amp(t) for d, t, _ in directives([x for x in cm if x is not None])
                             if d == "" and t]
            cols = set(flat_v) | set(knames) | set(fields_of[rule])
            lines = or_body(bodies, cols, set()) if len(bodies) > 1 else [*bodies[0][0], *bodies[0][1]]
            # the header makes each field's label, so the body joins it
            for x in fields_of[rule]:
                lines = [re.sub(rf"\*{re.escape(x)}(?!\w)", x, l) for l in lines]
            pred = c.wrote("&prediction", Written(scope, f"{inst.name}.prediction", False))
            rule_lines = [f"({side} {pred}"] + ["  " + l for l in lines]
            close(rule_lines, ")")
            head = f"(${rule} {' '.join('*' + x for x in fields_of[rule])})" if fields_of[rule] else f"${rule}"
            rules.append((rule, " ".join(texts), rule_lines, rule_reads, head))
        lines = list(f.lines)
        lines[0] = f"(DEMONSTRATED {c.rel_name(scope, inst.name)}"
        last = max(i for i, l in enumerate(lines) if not l.lstrip().startswith(";;"))
        assert lines[last].endswith(")")
        lines[last] = lines[last][:-1]
        if c.demo_mode.get(key) == "pair":
            lines = [lines[0], *self.pair_key(lines[1:], head_labels("demonstration"))]
        f.branches = tuple(sorted(set(f.branches) | pred_branches))
        f.demo = rules
        f.demo_head = lines
        f.demo_input_reads = set(f.reads)
        f.lines = lines + demo_lines(rules, {})
        f.reads = reads - {f.name}
        f.src_inst = (inst, us, side)
        return [f]

    def pair_key(self, lines: list[str], dlabs: list[list[str]]) -> list[str]:
        """A DEMONSTRATED form's inputs keyed by the demonstrated pair: the
        demonstration's body as the key clause, with the demonstration
        inside it, then the other inputs."""
        blocks: list[list[str]] = []
        pending: list[str] = []
        for l in lines:
            if l.startswith("  ;;"):
                pending.append(l)
            elif l.startswith("  (") or not blocks:
                blocks.append(pending + [l])
                pending = []
            else:
                blocks[-1].append(l)
        dem = next((b for b in blocks if any(x.startswith("  (demonstration (") for x in b)), None)
        knames = [ls[0] for ls in dlabs[:2] if ls]
        if dem is None or len(knames) != 2:
            self.todo.add("demonstrated-pair", "the demonstration's head")
            return [*self.todo.take(), *lines]
        i = next(k for k, x in enumerate(dem) if x.startswith("  (demonstration ("))
        head = dem[i].strip()
        body = [x[4:] for x in dem[i + 1:]]
        if not body:
            self.todo.add("demonstrated-pair", "the demonstration has no body")
            return [*self.todo.take(), *lines]
        assert body[-1].endswith(")")
        body[-1] = body[-1][:-1]
        body = mark_key(body, knames)
        lead = "  (key ("
        out = dem[:i] + [lead + body[0]] + [" " * len(lead) + x for x in body[1:]]
        close(out, ")")
        out.append(f"    {head})")
        close(out, ")")
        return out + [x for b in blocks if b is not dem for x in b]

    def pick_form(self, p) -> Form | None:
        c = self.c
        if p.ones is not None and p.fold:
            return None
        amp = c.rel_name(p.scope, p.name)
        sub = c.parse_sub if p.scope == ("Parse",) else {}
        lines = [f"(CHOOSE {amp}"]
        reads: set[str] = set()
        for note in p.notes:
            self.todo.add("pick-read", note)
        lines.extend("  " + t for t in self.todo.take())
        if p.ones is not None:
            # a clause of the item atom, with the pick's marks
            w = ClauseWriter(c, p.scope, sub, {})
            body = w.lits([AtomLiteral(p.item, False)], set())
            lines[0] = f"(RULE {amp}"
            lines.extend("  " + l for l in body)
            made = label_names(body)   # a case's or a lifted key is not written
            lines.extend("  (" + " ".join(["ONE"] + [v for v in key if v in made]) + ")" for key in p.ones)
            close(lines, ")")
            f = Form(lines, amp, w.reads - {amp}, line=p.line)
            f.comments = [";; " + t for t in self.plain_comments(f.line)]
            for d, rest, _ in directives(self.comments_above(f.line)):
                if d == "claim":
                    f.claim_slugs = rest.split()
            return f
        drop = {n: Wildcard() for n in p.items}
        w = ClauseWriter(c, p.scope, sub, {})
        slot = [l.replace("*", "^") for l in w.lits([AtomLiteral(subst_terms(p.item, drop), False)], set())]
        reads |= w.reads
        heads = set(re.findall(r"\^(\w+)", " ".join(slot)))
        w = ClauseWriter(c, p.scope, sub, {})
        item = w.lits([AtomLiteral(p.item, False)], set(heads))
        reads |= w.reads
        # the candidate's labels named as the chosen relation's columns
        _, pcols, _, _ = c.resolve(RelationName((), p.name), p.scope, sub)
        vars_ = p.fold or p.cvars
        if pcols is not None and len(pcols) == len(vars_):
            ren: dict[str, str] = {}
            for (col, leaves), v in zip(pcols, vars_):
                if v is None:
                    continue
                terms = w.split(Variable(v), leaves)
                nkeep = sum(1 for l in leaves if l.kind == "keep")
                for l, t in zip(leaves, terms):
                    if l.kind == "keep" and isinstance(t, Variable):
                        ren[w.label(t.name)] = l.name if nkeep > 1 else col.name
            made = label_names(item)
            ren = {a: b for a, b in ren.items() if a != b and a not in heads and b not in made
                   and list(ren.values()).count(b) == 1}
            if ren:
                item = relabel(item, lambda mark, x: mark + ren.get(x, x))
                item = [re.sub(r"\(:([A-Z]\w*) (\*?)\1\)", r"\2\1", l) for l in item]
        lines.extend(nest_keyed(slot if heads else None, [["  (@@in " + " ".join(item) + ")"]],
                                sorted(heads), "for"))
        for body in p.aparts:
            w = ClauseWriter(c, p.scope, sub, {})
            ls = w.lits(list(body), set())
            reads |= w.reads
            lines.extend("  " + t for t in self.todo.take())
            lines.append("  (never")
            lines.extend("    " + l for l in ls)
            close(lines, ")")
        close(lines, ")")
        reads.discard(amp)
        f = Form(lines, amp, reads, line=p.line)
        f.comments = [";; " + t for t in self.plain_comments(f.line)]
        for d, rest, _ in directives(self.comments_above(f.line)):
            if d == "claim":
                f.claim_slugs = rest.split()
        return f

    def key_rename(self, u: Unit, key_leaves, knames) -> dict[str, str]:
        if not u.head.args:
            return {}
        w = ClauseWriter(self.c, (), {}, {})
        terms = w.split(u.head.args[0], key_leaves)
        kept = [t for l, t in zip(key_leaves, terms) if l.kind in ("keep", "example")]
        ren = {}
        for t, n in zip(kept, knames):
            if isinstance(t, Variable) and t.name != n:
                ren[t.name] = n
        vars_: set[str] = set()
        collect_vars(list(u.body or []), vars_)
        for t in u.head.args[1:]:
            collect_vars([AtomLiteral(Atom(u.head.relation, (t,), 0), False)], vars_)
        taken = set(ren.values())
        for v in sorted(vars_):
            if v in taken and v not in ren:
                n = 2
                while f"{v}{n}" in vars_ or f"{v}{n}" in taken:
                    n += 1
                ren[v] = f"{v}{n}"
                taken.add(ren[v])
        return ren

    # ---- placement and rendering

    def render(self, forms: list[Form], claims: list[Claim], points, concept, all_ctors) -> str:
        slugs = [cl.slug for cl in claims]
        idx = {s: i for i, s in enumerate(slugs)}
        # An instance whose inputs fix the constructors of several cases
        # stands in the concept with the inputs the concept's case admits.
        extra: list[Form] = []
        for f in forms:
            if f.src_inst is None or not (set(f.branches) - concept):
                continue
            inst, us, side = f.src_inst

            def unit_ctors(u) -> set[str]:
                args = list(u.head.args) + [a for l in u.body or () if isinstance(l, AtomLiteral) and not l.negated
                                            for a in l.atom.args]
                return {n for a in args for n in ctor_names(a) if n in all_ctors}
            mine_us = [u for u in us if unit_ctors(u) <= concept]
            if not any(u.body is not None and unit_ctors(u) for u in mine_us):
                continue   # no input of the concept's own case: the instance is the alts'
            if not mine_us or len(mine_us) == len(us):
                continue
            saved = list(self.todo.pending), Counter(self.todo.kinds)
            gs = self.instance(inst, mine_us, side)
            self.todo.pending, self.todo.kinds = saved
            if gs:
                g = gs[0]
                g.comments, g.claim_slugs = f.comments, f.claim_slugs
                g.branches = tuple(sorted(set(g.branches) & concept))
                g.src_inst = (inst, mine_us, side)
                extra.append(g)
        forms = forms + extra
        main = [f for f in forms if not (set(f.branches) - concept)]
        branch_forms = [f for f in forms if set(f.branches) - concept]
        main, branch_forms = self.sink(main, branch_forms, claims, concept)
        main, branch_forms = self.drop_repeats(main, branch_forms, concept)
        # a concept clause that reads a relation only alts derive holds in no
        # concept model
        derived = {f.name for f in main}
        # only clauses whose heads fix an alt's constructor; an instance, a
        # parameter or a form the concept shares is not alt-only
        def form_scope(f: Form):
            if f.src is not None:
                return f.src[2]
            return f.src_inst[0].scope.components if f.src_inst is not None else None
        alt_only = {f.name for f in branch_forms} - derived - \
            {f.name for f in branch_forms if form_scope(f) in (None, ("Params",))}
        # a parameter with stored values has them in the concept, whatever the
        # determination derives it as under an alt
        stored = {m.relation.name for m in self.c.prog.macros
                  if isinstance(m, GridCall) and m.scope.components == ("Params",)}
        stored |= {u.head.relation.name for u in self.c.prog.units if u.scope.components == ("Params",)
                   and not u.head.relation.instances and not u.body}
        stored_names = {self.c.rel_name(("Determine",), n) for n in stored}
        alt_only -= stored_names
        # a set of cases that holds no concept case is empty in the concept
        alt_only |= {"%" + n for n in self.c.case_set_unread}
        # Each clause and instance that reads such a relation is written again
        # with that relation empty: a positive read kills its list, a NOT of
        # it is dropped, and a form left with nothing holds no concept row.
        # The emptiness spreads to the relations whose every form is dead.
        changed = True
        while changed:
            changed = False
            for f in main:
                if f.concept_dead or (f.src is None and f.src_inst is None):
                    continue
                dr = frozenset((f.reads | f.top_pos | f.top_neg | f.nested) & alt_only)
                if dr == f.dead_reads:
                    continue
                f.dead_reads = dr
                changed = True
                saved = list(self.todo.pending), Counter(self.todo.kinds)
                if f.src_inst is not None:
                    inst, us, side = f.src_inst
                    gs = self.instance(inst, us, side, dr)
                    g = gs[0] if gs else None
                else:
                    u, side, scope, sub, ns = f.src
                    g = self.clause(u, side, scope, sub, ns, drop_neg=dr)
                self.todo.pending, self.todo.kinds = saved
                if g is None and f.name in stored_names and f.side == "DET":
                    # the concept's values are the stored ones, which no determination derives
                    one = " (ONE)" if f.name in self.open_amps() else ""
                    g = Form([f"(DET {f.name}{one})"], f.name, set(), line=f.line)
                    g.marks = ["(ONE)"] if one else []
                if g is None:
                    f.concept_dead, f.concept_form = True, None
                    continue
                g.comments, g.claim_slugs = f.comments, f.claim_slugs
                f.concept_form = g if g.lines != f.lines else None
            gone = {n for n in derived if all(g.concept_dead for g in main if g.name == n)} - alt_only - stored_names
            if gone:
                alt_only |= gone
                changed = True
        self.concept_empty = alt_only
        self.drop_concept_repeats(main)
        self.render_main = main
        main = [f.concept_form or f for f in main if not f.concept_dead]
        main = self.sink_demo(main, branch_forms, claims)
        # dependency closure: each relation goes under the first claim among its readers' claims
        by_name: dict[str, list[Form]] = defaultdict(list)
        for f in main:
            by_name[f.name].append(f)
        claim_of: dict[str, int] = {}
        for f in main:
            ks = [idx[s] for s in f.claim_slugs if s in idx]
            if ks:
                claim_of[f.name] = min(min(ks), claim_of.get(f.name, 99))
        # params named in claim text
        for i, cl in enumerate(claims):
            for m in re.finditer(r"&(\w+)", cl.text):
                n = "&" + m.group(1)
                claim_of[n] = min(i, claim_of.get(n, 99))
        def close_claims() -> None:
            changed = True
            while changed:
                changed = False
                for f in main:
                    if f.name not in claim_of:
                        continue
                    for r in f.reads:
                        if r in by_name and claim_of.get(r, 99) > claim_of[f.name]:
                            claim_of[r] = claim_of[f.name]
                            changed = True
        close_claims()
        # a relation no claim reads, and that an alt's form reads, stands
        # under the claim the reading form serves, or else the last claim:
        # the tail stands after the ALTS forms
        if claims:
            for f in main:
                if f.name in claim_of:
                    continue
                readers = [g for g in branch_forms if f.name in g.reads and g.name != f.name]
                if not readers:
                    continue
                ks = [idx[s] for g in readers for s in g.claim_slugs if s in idx] + \
                     [claim_of[g.name] for g in readers if g.name in claim_of]
                claim_of[f.name] = min(ks) if ks else len(claims) - 1
            close_claims()
        # a relation stands under the first claim that reads it: one that the
        # solver's @claim puts before every claim reading it moves to the first
        named_ = {"&" + m.group(1) for cl in claims for m in re.finditer(r"&(\w+)", cl.text)}
        # a parameter stands under the first claim whose text names it, or
        # under the first claim that reads it where that claim comes earlier
        changed = True
        while changed:
            changed = False
            for n in named_ & set(by_name):
                namer = min(i for i, cl in enumerate(claims) if re.search(rf"{re.escape(n)}(?!\w)", cl.text))
                rs = [claim_of[g.name] for g in main if n in g.reads and g.name != n and g.name in claim_of]
                if claim_of.get(n) != min([namer, *rs]):
                    claim_of[n] = min([namer, *rs])
                    changed = True
            for f in main:
                if f.name not in claim_of or f.name in named_:
                    continue
                rs = [claim_of[g.name] for g in main if f.name in g.reads and g.name != f.name and g.name in claim_of]
                if rs and min(rs) > claim_of[f.name]:
                    claim_of[f.name] = min(rs)
                    changed = True
        self.claim_of_name = {n: claims[i].slug for n, i in claim_of.items() if i < len(claims)}
        # a relation's dependencies come before it
        order = topo(main)
        blocks: dict[int, list[Form]] = defaultdict(list)
        tail: list[Form] = []
        for f in order:
            if f.name in claim_of:
                blocks[claim_of[f.name]].append(f)
            else:
                tail.append(f)
        self.tail_names = {f.name for f in tail}
        out = [f";; {self.stem}", ""]
        if self.c.demo_select:
            self.todo.kinds["demonstrated-select"] += 1
            out += [";; TODO demonstrated-select: the program reads a demonstrated rule by its constructor, so it",
                    ";; selects a rule, and a DEMONSTRATED form names no rule", ""]
        for i, cl in enumerate(claims):
            fs = blocks.get(i, [])
            out.append(f"({cl.kind} {cl.slug} {quote(cl.text)}")
            if cl.approx:
                out.append(f"  (APPROXIMATED {quote(cl.approx)})")
            body = render_forms(fs, "  ")
            if body:
                out.append("")
                out.extend(body)
            close(out, ")")
            out.append("")
        # ALTS forms
        choice_at = len(out)
        self.render_args = (branch_forms, concept, claims, self.render_main)
        for fname, adt in points:
            anc = self.ancestors(fname)
            if anc:
                continue      # rendered inside its branch
            out.extend(self.render_choice(fname, adt, branch_forms, concept, claims, self.render_main))
        branch_names = {f.name for f in branch_forms}
        late: set[str] = set()
        changed = True
        while changed:
            changed = False
            for f in tail:
                if f.name not in late and (f.name == "&out" or f.reads & (branch_names | late)):
                    late.add(f.name)
                    changed = True
        if claims:
            out.extend(render_forms(tail, ""))
        else:
            out = out[:choice_at] + render_forms([f for f in tail if f.name not in late], "") + \
                ([""] if any(f.name not in late for f in tail) else []) + out[choice_at:]
            out.extend(render_forms([f for f in tail if f.name in late], ""))
        return self.state_combinations("\n".join(out).rstrip() + "\n", points)

    def state_combinations(self, text: str, points) -> str:
        """The text with a nested ALT for each combination of alts of
        different points that each rederive a relation: the nested ALT
        states the relation as the combination's case derives it."""
        from arclog_convert.lint import L as LintL, Sym as LintSym, alt_points, placements, read as lint_read, \
            unstated_combinations
        branch_forms, concept, _, main = self.render_args
        main_text: dict[str, list] = defaultdict(list)
        for f in main:
            if not f.concept_dead:
                main_text[f.name].append((f.concept_form or f).lines)
        saved = list(self.todo.pending), Counter(self.todo.kinds)
        excludes = self.choice_excludes(points)
        self.todo.pending, self.todo.kinds = saved
        excluded = [frozenset(re.findall(r"\$\w+", m.group(1)))
                    for x in excludes if (m := re.match(r"\(exclude \(([^)]*)\)", x))]
        tail_names = getattr(self, "tail_names", set()) | {"&out"}
        done: set[frozenset] = set()
        while True:
            forms = lint_read(text)
            point, under = alt_points(forms)
            sites: dict[frozenset, set[str]] = defaultdict(set)
            for n, case, _ in unstated_combinations(placements(forms), forms, excluded):
                if case not in done:
                    sites[case].add(n)
            if not sites:
                return text
            # each alt's own block, a direct child of its ALTS form
            top: dict[str, LintL] = {}

            def find(xs) -> None:
                for f in xs:
                    if not isinstance(f, LintL):
                        continue
                    if f.head == "ALTS":
                        for a in f.items[2:]:
                            if isinstance(a, LintL) and a.head == "ALT" and isinstance(a.items[1], LintSym):
                                top.setdefault(a.items[1].text, a)
                    find(f.items)
            find(forms)
            # the combinations in the order of their alts' blocks
            case = min(sites, key=lambda c: (len(c), sorted(top[a].start if a in top else -1 for a in c)))
            done.add(case)
            if not all(a in top for a in case):
                continue

            def ancestors_of(a: str) -> set[str]:
                got, pt = set(), point[a]
                while (up := under.get(pt)) is not None:
                    got.add(up)
                    pt = point[up]
                return got
            implied = set().union(*(ancestors_of(a) for a in case))
            first = min((a for a in case if a not in implied), key=lambda a: top[a].start)
            chain = sorted(case - {first} - ancestors_of(first), key=lambda a: top[a].start)
            alts = [(point[a][1:], a[1:]) for a in case]
            todo_out: list[str] = []
            fs, _ = self.alt_case(alts, branch_forms, concept, main, main_text, todo_out)
            rels = sites[case]
            new = [f for f in fs if f.name in rels]
            new += [f for f in main if f.name in rels - {g.name for g in fs} and not f.concept_dead]
            if not new:
                continue
            # a form of the case that the new forms read, and that no block
            # the case sees states, joins them
            seen = {p.name.partition(".")[0] for p in placements(forms) if p.name and set(p.alts) <= case}
            want = set().union(*(f.reads for f in new))
            while more := [g for g in fs if g.name in want and g.name not in seen and not any(g is h for h in new)]:
                new += more
                want |= set().union(*(g.reads for g in more))
            # the deepest block of the chain that the file holds
            block, rest = top[first], list(chain)
            while rest:
                nxt = next((x for x in block.items[2:] if isinstance(x, LintL) and x.head == "ALT"
                            and isinstance(x.items[1], LintSym) and x.items[1].text == rest[0]), None)
                if nxt is None:
                    break
                block, rest = nxt, rest[1:]
            col = block.start - text.rfind("\n", 0, block.start) - 1
            ind = " " * (col + 2)
            # the combination's forms serve the innermost alt's claims, and
            # stand in its first output block
            cl = self.ctor_claims((chain[-1] if chain else first)[1:])
            home = next((x for x in cl if x[0] == "OUTPUT"), cl[0] if cl else None)
            inner = [g for g in new if g.name not in tail_names] if home is not None else []
            bare = [g for g in new if not any(g is h for h in inner)]
            if not rest:
                # the file holds the combination's block: its forms join it
                claim = next((x for x in block.items[2:] if isinstance(x, LintL) and x.head in ("INPUT", "OUTPUT")
                              and home is not None and isinstance(x.items[1], LintSym)
                              and x.items[1].text == home[1]), None)
                edits = []
                if bare:
                    edits.append((block.end - 1, render_forms(topo(bare), ind)))
                if inner and claim is not None:
                    edits.append((claim.end - 1, render_forms(topo(inner), ind + "  ")))
                elif inner and home is not None:
                    lines = [f"{ind}({home[0]} {home[1]} {quote(home[2])}"] + \
                        render_forms(topo(inner), ind + "  ")
                    close(lines, ")")
                    nm = block.items[1]
                    edits.append((nm.pos + len(nm.text), lines))
                for at, lines in sorted(edits, reverse=True):
                    text = text[:at] + "\n" + "\n".join(lines) + text[at:]
                continue
            lines = []
            for b in rest:
                lines.append(f"{ind}(ALT {b}")
                ind += "  "
            lines.extend(ind + x for x in todo_out if x.strip().startswith(";;"))
            if inner and home is not None:
                lines.append(f"{ind}({home[0]} {home[1]} {quote(home[2])}")
                lines.extend(render_forms(topo(inner), ind + "  "))
                close(lines, ")")
            lines.extend(render_forms(topo(bare), ind))
            close(lines, ")" * len(rest))
            at = block.end - 1
            text = text[:at] + "\n" + "\n".join(lines) + text[at:]

    def sink_demo(self, main: list[Form], branch_forms: list[Form], claims) -> list[Form]:
        """Each form that only one DEMO_RULE reads, moved into it."""
        named = {m.group(1) for cl in claims for m in re.finditer(r"&(\w+)", cl.text)}
        for d in [f for f in main if f.demo]:
            rule_reads = {rule: reads for rule, _, _, reads, _ in d.demo}
            # a clause whose head names a rule is that rule's
            own = {id(g): g.demo_rule for g in main if g.demo_rule in rule_reads}
            assign: dict[str, str] = {}
            changed = True
            while changed:
                changed = False
                for g in main:
                    if g is d or g.demo or g.name in assign or g.name == "&out" or g.name[1:] in named \
                            or g.claim_slugs or id(g) in own:
                        continue
                    if any(h.name == g.name and h is not g for h in main):
                        continue
                    who: set[str] = set()
                    for h in main + branch_forms:
                        if h is d:
                            if g.name in d.demo_input_reads:
                                who.add("")
                            who |= {r for r, rs in rule_reads.items() if g.name in rs}
                        elif h.name != g.name and g.name in h.reads:
                            who.add(own.get(id(h)) or assign.get(h.name, ""))
                    if len(who) == 1 and "" not in who:
                        assign[g.name] = next(iter(who))
                        changed = True
            if not assign and not own:
                continue
            helpers: dict[str, list[Form]] = defaultdict(list)
            moved = [g for g in main if g.name in assign or id(g) in own]
            for g in moved:
                helpers[own.get(id(g)) or assign[g.name]].append(g)
            d.lines = d.demo_head + demo_lines(d.demo, helpers)
            d.reads = (d.reads | set().union(*(g.reads for g in moved))) - {g.name for g in moved}
            main = [g for g in main if not any(g is x for x in moved)]
        return main

    def drop_repeats(self, main: list[Form], branch_forms: list[Form], concept):
        """A concept relation whose head repeats a column that an alt's
        clause varies leaves the repeat out: the concept's readers read the
        column it repeats, and the alt rederives them with its own columns."""
        for f in list(main):
            if not f.head_repeat or f.side != "RULE" or sum(g.name == f.name for g in main) != 1:
                continue
            alts = [g for g in branch_forms if g.name == f.name]
            if not alts:
                continue
            bs = set().union(*(set(g.branches) - concept for g in alts))
            drop = dict(f.head_repeat)   # the dropped column -> the column it repeats
            new = without_repeats(f, drop)
            main[main.index(f)] = new
            for g in list(main):
                if g is new or not any(f"({f.name} " in l or f"({f.name})" in l for l in g.lines):
                    continue
                lines = read_without(g.lines, f.name, drop)
                if lines is None or lines == g.lines:
                    continue
                main[main.index(g)] = dc_replace(g, lines=lines)
                branch_forms.append(dc_replace(g, branches=tuple(sorted(set(g.branches) | bs))))
            # an alt's reader that the rederiving alts leave alone reads the
            # concept's columns, and their combination rederives it
            for g in list(branch_forms):
                if g.name == f.name or set(g.branches) & bs or \
                        not any(f"({f.name} " in l or f"({f.name})" in l for l in g.lines):
                    continue
                lines = read_without(g.lines, f.name, drop)
                if lines is None or lines == g.lines:
                    continue
                branch_forms[branch_forms.index(g)] = dc_replace(g, lines=lines)
                branch_forms.append(dc_replace(g, branches=tuple(sorted(set(g.branches) | bs))))
        return main, branch_forms

    def drop_concept_repeats(self, main: list[Form]) -> None:
        """A concept form whose head repeats a column where the full form,
        with the alts' reads, varies it leaves the repeat out: the concept's
        readers read the column it repeats, and each alt that revives the
        form rederives them with its own columns."""
        self.concept_repeats: dict[str, dict[str, str]] = {}   # relation -> the dropped column -> the one it repeats
        for f in main:
            g = f.concept_form
            if f.concept_dead or g is None or f.side != "RULE" or sum(h.name == f.name for h in main) != 1:
                continue
            drop = {x: y for x, y in g.head_repeat if (x, y) not in f.head_repeat}
            if not drop:
                continue
            f.concept_form = without_repeats(g, drop)
            self.concept_repeats[f.name] = drop
            for r in main:
                if r is f or r.concept_dead:
                    continue
                base = r.concept_form or r
                if not any(f"({f.name} " in l or f"({f.name})" in l for l in base.lines):
                    continue
                lines = read_without(base.lines, f.name, drop)
                if lines is None or lines == base.lines:
                    continue
                r.concept_form = dc_replace(base, lines=lines)
                r.dead_reads = r.dead_reads | {f.name}

    def sink(self, main: list[Form], branch_forms: list[Form], claims, concept):
        """Each concept form that only one alt's forms read, moved into
        that alt."""
        named = {m.group(1) for cl in claims for m in re.finditer(r"&(\w+)", cl.text)}
        moved: dict[str, frozenset[str]] = {}
        changed = True
        while changed:
            changed = False
            names = defaultdict(list)
            for f in main:
                names[f.name].append(f)
            for name, fs in names.items():
                if name in moved or name == "&out" or name[1:] in named:
                    continue
                if any(f.claim_slugs for f in fs):
                    continue
                readers = [f for f in main + branch_forms if name in f.reads and f.name != name]
                if not readers:
                    continue
                sets = []
                for r in readers:
                    if r.name in moved:
                        sets.append(moved[r.name])
                    elif set(r.branches) - concept:
                        sets.append(frozenset(set(r.branches) - concept))
                    else:
                        sets = []
                        break
                if not sets:
                    continue
                common = frozenset.intersection(*sets)
                if common:
                    moved[name] = common
                    changed = True
        if not moved:
            return main, branch_forms
        # a concept form that the branch derives again is read nowhere
        dead = {n for n, k in moved.items()
                if any(g.name == n and k <= set(g.branches) - concept for g in branch_forms)}
        main = [f for f in main if f.name not in dead]
        for f in main:
            if f.name in moved:
                f.branches = tuple(sorted(set(f.branches) | moved[f.name]))
        return [f for f in main if f.name not in moved], branch_forms + [f for f in main if f.name in moved]

    def ctor_claims(self, name: str) -> list[tuple[str, str, str]]:
        """The claim readings the @scene and @rule lines under a
        constructor give: (kind, slug, text)."""
        for _, adt in self.c.point_fields():
            prev = adt.span.first
            for k in adt.constructors:
                if k.name == name:
                    cm = [t for ln in range(prev, k.span.first - 1)
                          if (t := comment_text(self.lines[ln])) is not None]
                    out = []
                    for d, rest, _ in directives(cm):
                        m = re.match(r"([\w-]+):\s*(.*)", rest) if d in ("scene", "rule") else None
                        if m:
                            out.append(("INPUT" if d == "scene" else "OUTPUT", m.group(1), params_to_amp(m.group(2))))
                    return out
                prev = k.span.first
        return []

    def render_choice(self, fname, adt: AdtType, branch_forms, concept, claims, main,
                      inherited: dict[str, list] | None = None) -> list[str]:
        """The ALTS form of the point `fname`. `inherited` holds, for a point
        that exists only under an alt, each relation's lines as that alt's
        case derives them."""
        all_ctors_field = {k.name: fname for k in adt.constructors}
        decl_line = adt.span.first
        gloss = self.gloss_at(decl_line)
        ctors = adt.constructors
        out = [f"(ALTS ${fname} {quote(params_to_amp(gloss))} ${ctors[0].name}"]
        prev_end = decl_line
        ctor_comments = {}
        for k in ctors:
            # comments between the previous constructor and this one
            cm = []
            for ln in range(prev_end, k.span.first - 1):
                t = comment_text(self.lines[ln])
                if t is not None:
                    cm.append(t)
            ctor_comments[k.name] = cm
            prev_end = k.span.first
        main_text: dict[str, list] = defaultdict(list)
        for f in main:
            if not f.concept_dead:
                main_text[f.name].append((f.concept_form or f).lines)
        if inherited is not None:
            main_text = defaultdict(list, inherited)
        # the points that exist only with the concept's branch stand in its block
        subs = [(f2, adt2) for f2, adt2 in self.c.point_fields()
                if (a2 := self.ancestors(f2)) and a2[0] == (fname, ctors[0].name)]
        if subs:
            out.append(f"  (ALT ${ctors[0].name}")
            for f2, adt2 in subs:
                sub_lines = self.render_choice(f2, adt2, *self.render_args, inherited=inherited)
                out.extend("    " + l if l else l for l in sub_lines if l)
            close(out, ")")
        for k in ctors[1:]:
            ds = directives(ctor_comments[k.name])
            bclaims = []
            for d, rest, _ in ds:
                if d in ("scene", "rule"):
                    m = re.match(r"([\w-]+):\s*(.*)", rest)
                    if m:
                        bclaims.append(("INPUT" if d == "scene" else "OUTPUT", m.group(1), params_to_amp(m.group(2))))
            # a form that this branch shares with other branches of this point
            # is this branch's, and stands in each of their blocks
            # the constructors this point stands under are fixed in its blocks
            sib = {kk.name for kk in ctors} | {ck for _, ck in self.ancestors(fname)}
            nested = [f for f in branch_forms if k.name in f.branches and (set(f.branches) - concept - sib)]
            out.append(f"  (ALT ${k.name}")
            fs, case_text = self.alt_case([(fname, k.name)], branch_forms, concept, main, main_text, out)
            claim_slugs = {s for _, s, _ in bclaims}
            placed: dict[str, list[Form]] = defaultdict(list)
            rest_forms = []
            tgt_of: dict[str, str | None] = {}
            for f in fs:
                if f.name in tgt_of:
                    tgt = tgt_of[f.name]
                    (placed[tgt] if tgt else rest_forms).append(f)
                    continue
                tgt = next((s for s in f.claim_slugs if s in claim_slugs), None)
                if tgt is None:
                    # the claim block of the concept form with this name
                    tgt = self.claim_of_name.get(f.name) if hasattr(self, "claim_of_name") else None
                    if tgt not in claim_slugs:
                        tgt = None
                tgt_of[f.name] = tgt
                if tgt:
                    placed[tgt].append(f)
                else:
                    rest_forms.append(f)
            # a form that a claim block's form reads stands in the first such block
            tail_names = getattr(self, "tail_names", set()) | {"&out"}
            moved_ = True
            while moved_:
                moved_ = False
                for f in list(rest_forms):
                    if f.name in tail_names:
                        continue
                    tgt = next((sl for _, sl, _ in bclaims
                                if any(f.name in g.reads for g in placed.get(sl, []))), None)
                    if tgt is not None:
                        rest_forms = [g for g in rest_forms if g.name != f.name]
                        placed[tgt].extend(g for g in fs if g.name == f.name and g not in placed[tgt])
                        tgt_of[f.name] = tgt
                        moved_ = True
            # any other form that is no tail form serves the claims the alt
            # reads: it stands in the alt's first output block
            home = next((sl for kd, sl, _ in bclaims if kd == "OUTPUT"), bclaims[0][1] if bclaims else None)
            if home is not None:
                for f in [g for g in rest_forms if g.name not in tail_names]:
                    placed[home].append(f)
                    tgt_of[f.name] = home
                rest_forms = [g for g in rest_forms if g.name in tail_names]
            for kind, slug, text in bclaims:
                out.append(f"    ({kind} {slug} {quote(text)}")
                body = render_forms(topo(placed.get(slug, [])), "      ")
                if body:
                    out.extend(body)
                close(out, ")")
            body = render_forms(rest_forms, "    ")
            out.extend(body)
            # a combination with a later point's branch stands nested under this branch
            order = {kk.name: i for _, a_ in self.c.point_fields() for i, kk in enumerate(a_.constructors)}
            field_of = {kk.name: f_ for f_, a_ in self.c.point_fields() for kk in a_.constructors}
            pidx = {f_: i for i, (f_, _) in enumerate(self.c.point_fields())}
            combos: dict[tuple[str, ...], list[Form]] = defaultdict(list)
            under_k = {f2 for f2, _ in self.c.point_fields() if (fname, k.name) in self.ancestors(f2)}
            for f in nested:
                others = tuple(sorted(set(f.branches) - concept - sib, key=lambda b: (pidx[field_of[b]], order[b])))
                if all(field_of[b] in under_k for b in others):
                    continue   # a point that exists only with this branch renders it
                # the combination stands under the branch of its first point
                if all(pidx[field_of[b]] > pidx[fname] for b in others):
                    combos[others].append(f)
                elif not any(pidx[field_of[b]] < pidx[fname] for b in others):
                    out.append(f"    ;; TODO combination: {' & '.join('$' + b for b in f.branches)}")
                    self.todo.kinds["combination"] += 1
                    out.extend(render_forms([f], "    "))
            for others, cfs in combos.items():
                # a relation the combination derives as the other branch
                # alone does is no rederivation
                alone: dict[str, list] = defaultdict(list)
                for g in branch_forms:
                    if set(g.branches) - concept == set(others):
                        alone[g.name].append(g.lines)
                here_: dict[str, list] = defaultdict(list)
                for g in cfs:
                    here_[g.name].append(g.lines)
                cfs = [g for g in cfs if alone.get(g.name) != here_[g.name]]
                # nor one it derives as this branch alone does, where the
                # other branch alone derives none of its name
                cfs = [g for g in cfs if g.name in alone or case_text.get(g.name) != here_[g.name]]
                if not cfs:
                    continue
                ind = "    "
                for b in others:
                    out.append(f"{ind}(ALT ${b}")
                    ind += "  "
                # the combination's forms serve the innermost alt's claims,
                # and stand in its first output block
                cl = self.ctor_claims(others[-1])
                home = next((x for x in cl if x[0] == "OUTPUT"), cl[0] if cl else None)
                tail_cfs = [g for g in cfs if g.name in tail_names | {"&out"}]
                if home is not None and len(tail_cfs) < len(cfs):
                    out.append(f"{ind}({home[0]} {home[1]} {quote(home[2])}")
                    out.extend(render_forms(topo([g for g in cfs if g.name not in tail_names | {"&out"}]), ind + "  "))
                    close(out, ")")
                    cfs = tail_cfs
                out.extend(render_forms(topo(cfs), ind))
                close(out, ")" * len(others))
            # the points that exist only with this branch
            for f2, adt2 in self.c.point_fields():
                a2 = self.ancestors(f2)
                if a2 and a2[0] == (fname, k.name):
                    sub_lines = self.render_choice(f2, adt2, *self.render_args, inherited=case_text)
                    out.extend("    " + l if l else l for l in sub_lines if l)
            close(out, ")")
        close(out, ")")
        out.append("")
        return out

    def alt_case(self, alts: list[tuple[str, str]], branch_forms, concept, main, main_text, out: list[str]
                 ) -> tuple[list["Form"], dict[str, list]]:
        """The forms of the case that takes each (point, constructor) of
        `alts`, where they differ from `main_text`, and each relation's lines
        as that case derives them."""
        adts = dict(self.c.point_fields())
        field_of = {kk.name: f_ for f_, a_ in adts.items() for kk in a_.constructors}
        pts = {f_ for f_, _ in alts}
        ks = {k for _, k in alts}
        anc = list(dict.fromkeys(a for f_, _ in alts for a in self.ancestors(f_)))
        anc_ctors = {ck for _, ck in anc}
        sib = {kk.name for f_ in pts for kk in adts[f_].constructors} | anc_ctors

        def holds(f: "Form") -> bool:
            # a form names its points' constructors as alternatives, and each
            # point of the case that it names takes the case's constructor
            bs = set(f.branches)
            return bool(bs & ks) and not (bs - concept - sib) and all(
                k in bs or not bs & {kk.name for kk in adts[f_].constructors} for f_, k in alts)
        fs = [f for f in branch_forms if holds(f)]
        fs = topo(fs)
        # drop forms identical to the concept's
        all_mine = {f.name for f in fs}
        mine_text: dict[str, list] = defaultdict(list)
        for f in fs:
            mine_text[f.name].append(f.lines)
        fs = [f for f in fs if main_text.get(f.name) != mine_text[f.name]]
        mine = all_mine | {f.name for f in branch_forms if set(f.branches) & ks}
        # what a point this one stands under derives, its alt's case derives
        mine |= {f.name for f in branch_forms if set(f.branches) - concept
                 and set(f.branches) - concept <= anc_ctors}

        def fixed(f: "Form") -> bool:
            return any(b in concept and field_of.get(b) in pts for b in f.branches)
        fixed_names = defaultdict(list)
        for f in main:
            fixed_names[f.name].append(fixed(f))
        # a determination runs once, under the concept's case, so a
        # relation it derives holds in every branch
        empty = {f.name for f in main
                 if all(fixed_names[f.name]) and f.name not in mine and f.side != "DET" and fixed(f)}
        at = dict(anc) | dict(alts)
        for name, rows in self.case_set_rows.items():
            # a set whose values hold no value of a point holds in the
            # alt's case as it holds in the concept's
            if not any(all(row.get(f_, ck) == ck for f_, ck in at.items())
                       and all(row.get(f_, v) == v for f_, v in self.concept_of.items() if f_ not in at)
                       for row in rows):
                empty.add("%" + name)
        # a concept clause whose head fixes another constructor of this
        # point, or of a point this one stands under, holds no row here
        others_k = {kk.name for f_, ck in at.items() for kk in adts[f_].constructors if kk.name != ck}
        # a concept clause that fixes no constructor of the case's points
        # holds beside the case's own clauses of its relation
        reps = getattr(self, "concept_repeats", {})
        adds = {f.name for f in fs if f.side == "RULE" and f.lines[0].startswith("(RULE ") and f.name not in reps
                and all(g.side == "RULE" and g.lines[0].startswith("(RULE ") and g.cols == f.cols
                        for g in main if g.name == f.name)}
        redo = self.dead_clauses(main, empty, mine, out, others_k, adds)
        fs = fs + redo
        # a relation that no form of this case derives is empty in it: a
        # form of the alt that reads one is written again without it
        in_case = concept | ks | anc_ctors
        known = {f.name for f in main} | {f.name for f in branch_forms}
        fs2 = fs
        dropped_any = True
        while dropped_any:
            fs = fs2
            here_names = {f.name for f in main if not f.concept_dead} | {f.name for f in fs} | \
                {f.name for f in branch_forms if set(f.branches) <= in_case and f.name not in all_mine}
            dropped_any = False
            fs2 = []
            for f in fs:
                gone = (f.top_pos | f.top_neg | f.nested | f.reads) & (known - here_names)
                if gone and (f.src is not None or f.src_inst is not None):
                    saved = list(self.todo.pending), Counter(self.todo.kinds)
                    if f.src is not None:
                        u_, side_, scope_, sub_, ns_ = f.src
                        g = self.clause(u_, side_, scope_, sub_, ns_, drop_neg=frozenset(gone))
                    else:
                        inst_, us_, side_ = f.src_inst
                        gs_ = self.instance(inst_, us_, side_, frozenset(gone))
                        g = gs_[0] if gs_ else None
                    self.todo.pending, self.todo.kinds = saved
                    if g is None:
                        dropped_any = True
                        continue
                    g.comments, g.claim_slugs, g.branches = f.comments, f.claim_slugs, f.branches
                    fs2.append(g)
                else:
                    fs2.append(f)
        fs = fs2
        # a form written again without an empty relation can come out as the
        # concept's, and so can the clauses of a relation, merged into one
        mine_text = defaultdict(list)
        for f in fs:
            mine_text[f.name].append(f.lines)
        concept_forms: dict[str, list] = defaultdict(list)
        for f in main:
            if not f.concept_dead:
                concept_forms[f.name].append(f.concept_form or f)
        saved = Counter(MERGES), list(MERGES_UNMERGED)

        def merged(forms_) -> list:
            return [g.lines for g in merge_forms(forms_)]
        same = {n for n in mine_text if main_text.get(n) in (mine_text[n], merged([f for f in fs if f.name == n]))
                or (main_text.get(n) == [g.lines for g in concept_forms[n]]
                    and merged([f for f in fs if f.name == n]) == merged(concept_forms[n]))}
        MERGES.clear()
        MERGES.update(saved[0])
        MERGES_UNMERGED[:] = saved[1]
        fs = [f for f in fs if f.name not in same]
        # each relation as this case derives it
        case_text = defaultdict(list, main_text)
        for name in {f.name for f in fs}:
            case_text[name] = [f.lines for f in fs if f.name == name]
        return fs, case_text

    def type_values(self, tname: str) -> list[tuple[str, ...]]:
        """Every value of a case type, as the constructor names it holds."""
        import itertools
        t = self.c.find_type(tname, ())
        if isinstance(t, RecordType):
            return [sum(p, ()) for p in itertools.product(*(self.type_values(f.type.name) for f in t.fields))]
        if isinstance(t, AdtType) and tname in self.c.case_types:
            out = []
            for k in t.constructors:
                for p in itertools.product(*(self.type_values(f.type.name) for f in k.fields)):
                    out.append((k.name,) + sum(p, ()))
            return out
        return [()]

    def reached_types(self, tname: str) -> set[str]:
        """The case types a value of `tname` holds, itself included."""
        out: set[str] = set()
        todo = [tname]
        while todo:
            t = todo.pop()
            if t in out:
                continue
            decl = self.c.find_type(t, ())
            if isinstance(decl, RecordType):
                todo += [f.type.name for f in decl.fields]
            elif isinstance(decl, AdtType) and t in self.c.case_types:
                out.add(t)
                todo += [f.type.name for k in decl.constructors for f in k.fields]
        return out

    def ancestors(self, fname: str) -> list[tuple[str, str]]:
        """The points a nested point stands under, each with the
        constructor whose field holds it."""
        pts = self.c.point_fields()
        adt_of = {f_: adt_ for f_, adt_ in pts}
        out = []
        cur = fname
        while True:
            t = adt_of[cur].name
            parent = next(((f_, k.name) for f_, adt_ in pts for k in adt_.constructors
                           if any(fl.type.name == t for fl in k.fields)), None)
            if parent is None or parent in out:
                return out
            out.append(parent)
            cur = parent[0]

    def dead_clauses(self, main: list[Form], empty: set[str], mine: set[str], out: list[str],
                     others: set[str] = frozenset(), adds: set[str] | frozenset[str] = frozenset()) -> list[Form]:
        """The alt's rederivations of the concept relations whose clauses
        read a relation the alt derives no rows of: a clause that reads
        one positively is dead, a `NOT` of one holds and is dropped, and a
        relation all of whose clauses are dead is empty too. A clause whose
        head fixes one of `others`, the point's other constructors, holds
        no row in the alt, and its relation is rederived without it."""
        groups: dict[str, list[Form]] = defaultdict(list)
        fixed: set[str] = set()
        for f in main:
            if f.side != "DET" and set(f.branches) & others:
                fixed.add(f.name)
                continue
            groups[f.name].append(f)

        def touched(f: Form) -> bool:
            return bool((f.top_pos | f.top_neg | f.nested | f.reads) & empty)

        def rerender(f: Form):
            if f.src is None:
                inst, us, side = f.src_inst
                saved = list(self.todo.pending), Counter(self.todo.kinds)
                gs = self.instance(inst, us, side, frozenset(empty))
                self.todo.pending, self.todo.kinds = saved
                if gs:
                    gs[0].comments = f.comments
                    gs[0].claim_slugs = f.claim_slugs
                return gs[0] if gs else None
            u, side, scope, sub, ns = f.src
            saved = list(self.todo.pending), Counter(self.todo.kinds)
            g = self.clause(u, side, scope, sub, ns, drop_neg=frozenset(empty))
            self.todo.pending, self.todo.kinds = saved
            if g is not None:
                g.comments = f.comments
            return g

        # what this branch derives, with the concept's dead forms it revives;
        # a set of cases that holds this branch and no concept case revives
        # what it killed in the concept
        here = set(mine) | {"%" + n for n in self.c.case_set_unread if "%" + n not in empty}

        def revived(f: Form) -> bool:
            return (f.concept_dead or f.concept_form is not None) and bool(f.dead_reads & here)
        grew = True
        while grew:
            grew = False
            for f in main:
                if f.name not in here and revived(f):
                    here.add(f.name)
                    grew = True

        # what the concept leaves empty stays empty here unless this branch
        # derives it
        empty |= getattr(self, "concept_empty", set()) - here
        # a clause dead in the concept holds here only where this branch
        # derives what it reads
        groups = {n: [f for f in fs if not f.concept_dead or revived(f)] for n, fs in groups.items()}
        for name, fs in groups.items():
            if not fs and name not in mine:
                empty.add(name)

        def redone(fs: list[Form]) -> bool:
            return any(touched(f) or revived(f) for f in fs)

        changed = True
        while changed:
            changed = False
            for name, fs in groups.items():
                if name in empty or name in mine or not (redone(fs) or name in fixed):
                    continue
                if all(f.src is not None or f.src_inst is not None for f in fs) \
                        and all(touched(f) for f in fs) and all(rerender(f) is None for f in fs):
                    empty.add(name)
                    changed = True
        redo: list[Form] = []
        for name, fs in groups.items():
            if name in adds and name not in empty:
                # the case's own clauses of the relation stand beside these
                for f in fs:
                    g = rerender(f) if touched(f) and (f.src is not None or f.src_inst is not None) else f
                    if g is not None:
                        redo.append(g)
                continue
            if name in empty or name in mine or not (redone(fs) or name in fixed):
                continue
            for f in fs:
                if f.src is None and f.src_inst is None:
                    continue    # not rerendered: the concept's form stands
                elif touched(f):
                    g = rerender(f)
                    if g is not None:
                        redo.append(g)
                else:
                    redo.append(f)
        # a rederivation that repeats the column the concept leaves out
        # leaves it out too, and its readers read the concept's columns
        reps = getattr(self, "concept_repeats", {})
        narrow = {n for n in reps if n not in mine and not any(g.name == n for g in redo)}
        for i, g in enumerate(redo):
            if g.name in reps and all(x in g.head_repeat for x in reps[g.name].items()):
                redo[i] = without_repeats(g, reps[g.name])
                narrow.add(g.name)
        for i, g in enumerate(redo):
            for n in narrow & g.reads:
                lines = read_without(redo[i].lines, n, reps[n])
                if lines is not None:
                    redo[i] = dc_replace(redo[i], lines=lines)
        # a rederivation the same as the concept's is no rederivation
        concept_lines: dict[str, list] = defaultdict(list)
        for f in main:
            if not f.concept_dead:
                concept_lines[f.name].append((f.concept_form or f).lines)
        redo_lines: dict[str, list] = defaultdict(list)
        for g in redo:
            redo_lines[g.name].append(g.lines)
        redo = [g for g in redo if g.name in adds or redo_lines[g.name] != concept_lines.get(g.name)]
        if "&out" in empty:
            out.append("    ;; TODO alt-undefined: every &output clause reads a relation this alt leaves empty")
            self.todo.kinds["alt-undefined"] += 1
        return redo

    # ---- arcdata

    def arcdata(self, rep, params, excludes, points, concept, derive_points, approx_w) -> str:
        out = [f";; {self.stem}", ""]
        if rep:
            parts = rep.split()
            out.append(f"(representative {parts[0]}" + (f" ${parts[1]}" if len(parts) > 1 else "") + ")")
            out.append("")
        out.extend(params)
        if params:
            out.append("")
        ex = self.choice_excludes(points)
        out.extend(ex + excludes)
        if ex or excludes:
            out.append("")
        wit = self.witness_file()
        used: set[str] = set()
        for slug, ws in approx_w.items():
            out.append(f"(approximated {slug}")
            for line in ws:
                out.extend(self.witness_form(line, wit, used, "  "))
            close(out, ")")
            out.append("")
        for fname, adt in points:
            prev_end = adt.span.first
            branches = []
            for k in adt.constructors:
                cm = []
                for ln in range(prev_end, k.span.first - 1):
                    t = comment_text(self.lines[ln])
                    if t is not None:
                        cm.append(t)
                prev_end = k.span.first
                ws = [(rest, ind) for d, rest, ind in directives(cm) if d == "witness"]
                if ws and k.name not in concept:
                    branches.append((k.name, ws))
            if not branches:
                continue
            out.append(f"(alts ${fname}")
            for bname, ws in branches:
                out.append(f"  (alt ${bname}")
                for rest, _ in ws:
                    out.extend(self.witness_form(rest, wit, used, "    "))
                close(out, ")")
            close(out, ")")
            out.append("")
        for amp, derives, side, dl_name in derive_points + self.store_points:
            out.append(f"(alts {amp}")
            # one derived side per proposer where the line gives several
            props = list(dict.fromkeys(map(derive_proposer, derives)))
            many = side == "Derived" and len(props) > 1
            for p_ in (props if many else [None]):
                alt = f"{amp}={p_}" if many else f"{amp}=${side}"
                out.append(f"  (alt {alt}")
                for d in derives:
                    prop = derive_proposer(d)
                    if many and prop != p_:
                        continue
                    rest = d.split(":", 1)[1].strip() if ":" in d else ""
                    rest = re.sub(r"^(\S+)\s+(derived|stored)\b", lambda m: f"{m.group(1)} {alt}", rest)
                    wid = f"{dl_name}={prop or 'stored'}"
                    out.extend(self.witness_form(f"{wid}: {rest}", wit, used, "    "))
                close(out, ")")
            close(out, ")")
            out.append("")
        return "\n".join(out).rstrip() + "\n"

    def choice_cases(self) -> set | None:
        """The value of each case impl_choice holds, as a nested tuple: a
        constructor `("$", name, args...)`, a record `("[]", fields...)`.
        Its clauses run over the relations whose own clauses run so, down
        to facts; None where a clause reads anything else."""
        prog = self.c.prog
        units: dict[str, list] = defaultdict(list)
        for u in prog.units:
            if not u.scope.components and not u.head.relation.instances:
                units[u.head.relation.name].append(u)

        class Unknown(Exception):
            pass

        def val(t, env):
            if isinstance(t, Variable):
                return env.get(t.name)
            if isinstance(t, ConstructorTerm):
                args = tuple(val(a, env) for a in t.args)
                return None if any(a is None for a in args) else ("$", t.name) + args
            if isinstance(t, RecordTerm):
                args = tuple(val(a, env) for a in t.args)
                return None if any(a is None for a in args) else ("[]",) + args
            if isinstance(t, NumberTerm):
                return ("#", t.value)
            if isinstance(t, DefinedName):
                return ("@", t.name)
            return None

        def unbound(t, env) -> bool:
            if isinstance(t, Variable):
                return t.name not in env
            if isinstance(t, (ConstructorTerm, RecordTerm)):
                return any(unbound(a, env) for a in t.args)
            return False

        def match(t, v, env):
            """env extended so that t is v, or None; `_` matches anything."""
            if isinstance(t, Wildcard):
                return env
            if isinstance(t, Variable):
                if t.name in env:
                    return env if env[t.name] == v else None
                return {**env, t.name: v}
            if isinstance(t, (ConstructorTerm, RecordTerm)):
                tag = ("$", t.name) if isinstance(t, ConstructorTerm) else ("[]",)
                if v[:len(tag)] != tag or len(v) != len(tag) + len(t.args):
                    return None
                for a, x in zip(t.args, v[len(tag):]):
                    env = match(a, x, env)
                    if env is None:
                        return None
                return env
            w = val(t, env)
            if w is None:
                raise Unknown
            return env if w == v else None

        memo: dict[str, list[tuple]] = {}
        busy: set[str] = set()

        def rows(name: str) -> list[tuple]:
            if name in memo:
                return memo[name]
            if name in busy or name not in units:
                raise Unknown
            busy.add(name)
            out_: list[tuple] = []
            for u in units[name]:
                for env in solve(u.body or (), [{}]):
                    r = tuple(val(a, env) for a in u.head.args)
                    if None in r:
                        raise Unknown
                    out_.append(r)
            busy.discard(name)
            memo[name] = out_
            return out_

        def solve(lits, envs):
            pending = list(lits)
            while pending:
                # a positive atom first, so the filters find their labels bound
                k = next((i for i, l in enumerate(pending) if isinstance(l, AtomLiteral) and not l.negated), 0)
                l = pending.pop(k)
                out = []
                if isinstance(l, AtomLiteral):
                    if l.atom.relation.instances:
                        raise Unknown
                    rs = rows(l.atom.relation.name)
                    for env in envs:
                        if l.negated and any(unbound(a, env) for a in l.atom.args):
                            raise Unknown
                        hits = []
                        for r in rs:
                            e = env
                            for a, v in zip(l.atom.args, r):
                                e = match(a, v, e) if e is not None else None
                            if e is not None:
                                hits.append(e)
                        if l.negated:
                            if not hits:
                                out.append(env)
                        else:
                            out.extend(hits)
                elif isinstance(l, Comparison) and l.op in (ComparisonOperator.EQ, ComparisonOperator.NE):
                    for env in envs:
                        a, b = val(l.lhs, env), val(l.rhs, env)
                        if a is None and b is None:
                            raise Unknown
                        g, t = (a, l.rhs) if a is not None else (b, l.lhs)
                        if l.op == ComparisonOperator.EQ:
                            e = match(t, g, env)
                            if e is not None:
                                out.append(e)
                        else:
                            if unbound(t, env):
                                raise Unknown
                            if match(t, g, env) is None:
                                out.append(env)
                elif isinstance(l, Disjunction):
                    for env in envs:
                        for br in l.branches:
                            out.extend(solve(br, [env]))
                else:
                    raise Unknown
                envs = out
            return envs

        try:
            return {r[0] for r in rows("impl_choice")}
        except Unknown:
            return None

    def choice_excludes(self, points) -> list[str]:
        if not points:
            return []
        facts = [u for u in self.c.prog.units if u.head.relation.name == "impl_choice" and not u.scope.components]
        if not facts:
            return []
        choice = self.c.find_type("Choice", ())
        direct = len(points) == 1 if isinstance(choice, AdtType) else len(points) == len(choice.fields)
        held = self.choice_cases()
        if held is None:
            self.todo.kinds["cases"] += 1
            return [";; TODO cases: impl_choice by a rule the script does not read"]
        import itertools

        def flat_names(v) -> tuple[str, ...]:
            if v[0] == "$":
                return (v[1],) + sum((flat_names(a) for a in v[2:]), ())
            if v[0] == "[]":
                return sum((flat_names(a) for a in v[1:]), ())
            return ()
        decl = next((r for r in self.c.prog.relations if r.name == "impl_choice" and not r.scope.components), None)
        lines = (self.comments_above(decl.span.first) if decl and decl.span else []) + self.comments_above(facts[0].span.first)
        reason = params_to_amp(" ".join(rest for d, rest, _ in directives(lines) if d == ""))
        if not reason:
            # the prose above a relation whose rows impl_choice's clauses leave out
            negs = [l.atom.relation.name for u in self.c.prog.units if u.head.relation.name == "impl_choice"
                    and not u.scope.components for l in u.body or ()
                    if isinstance(l, AtomLiteral) and l.negated and not l.atom.relation.instances]
            for n in dict.fromkeys(negs):
                r = self.c.rels.get(((), n))
                if r is not None and r.span:
                    reason += " ".join(rest for d, rest, _ in directives(self.comments_above(r.span.first)) if d == "")
            reason = params_to_amp(reason)
        why = f" {quote(reason)}" if reason else ""
        if not direct:

            parent: dict[str, str] = {}

            def values(tname: str, up: str | None = None) -> list[tuple[str, ...]]:
                t = self.c.find_type(tname, ())
                if isinstance(t, RecordType):
                    return [sum(p, ()) for p in itertools.product(*(values(f.type.name, up) for f in t.fields))]
                if isinstance(t, AdtType) and tname in self.c.case_types:
                    out_ = []
                    for k in t.constructors:
                        if up:
                            parent[k.name] = up
                        for p in itertools.product(*(values(f.type.name, k.name) for f in k.fields)):
                            out_.append((k.name,) + sum(p, ()))
                    return out_
                return [()]

            def closure(q: frozenset) -> frozenset:
                got_ = set(q)
                for n in q:
                    while n in parent:
                        n = parent[n]
                        got_.add(n)
                return frozenset(got_)
            got = {frozenset(flat_names(v)) for v in held}
            full_n = values("Choice")
            gone_n = [v for v in full_n if frozenset(v) not in got]
            # the fewest alts that fix each excluded case: a set of alts
            # stands where every case that takes them all is excluded
            order = {n: i for i, n in enumerate(dict.fromkeys(n for v in full_n for n in v))}
            full_s = [frozenset(v) for v in full_n]
            gone_s = {frozenset(v) for v in gone_n}
            parts = sorted({frozenset(sub) for g in gone_s for k in range(1, len(g) + 1)
                            for sub in itertools.combinations(sorted(g, key=order.__getitem__), k)},
                           key=lambda q: (len(q), sorted(order[n] for n in q)))
            cl = {q: closure(q) for q in parts}
            shortest: dict[frozenset, int] = {}   # each closure: the fewest alts of a part that has it
            for q in parts:
                shortest[cl[q]] = min(shortest.get(cl[q], len(q)), len(q))
            chosen: list[frozenset] = []
            for q in parts:
                if cl[q] != q and shortest[cl[q]] < len(q):
                    continue
                if any(cl[c] <= cl[q] for c in chosen):
                    continue
                if all(c in gone_s for c in full_s if q <= c):
                    chosen.append(q)
            return [f"(exclude ({' '.join('$' + n for n in sorted(q, key=order.__getitem__))}){why})"
                    for q in chosen]
        cases = {tuple(p[1] for p in (v[1:] if v[0] == "[]" else (v,))) for v in held}
        ctors = [[k.name for k in adt.constructors] for _, adt in points]
        full = set(itertools.product(*ctors))
        gone = full - cases
        if not gone:
            return []
        # the fewest alts that fix each excluded combination: a partial
        # choice stands where every completion of it is excluded
        n = len(ctors)
        picks: list[dict[int, str]] = []
        for size in range(1, n + 1):
            for idx in itertools.combinations(range(n), size):
                for vals in itertools.product(*(ctors[i] for i in idx)):
                    part = dict(zip(idx, vals))
                    if any(all(part.get(i) == p[i] for i in p) for p in picks):
                        continue
                    if all(c in gone for c in full if all(c[i] == v for i, v in part.items())):
                        picks.append(part)
        return [f"(exclude ({' '.join('$' + p[i] for i in sorted(p))}){why})" for p in picks]

    def witness_file(self) -> list[dict]:
        p = WITNESSES / f"{self.stem}.wit.json"
        if not p.exists():
            return []
        return json.loads(p.read_text())["witnesses"]

    def assign_form(self, amp: str, v) -> str:
        """A witness's reassignment of a relation, its rows in the form a
        param form takes: a picture as a grid, facts as rows, and the rows
        of a relation with a Position column as grids."""
        def arg(a) -> str:
            return "(" + " ".join(map(arg, a)) + ")" if isinstance(a, list) else str(a)
        ts = self.param_types.get(amp, [])
        head = f"(assign {amp}"
        if isinstance(v, dict) and "grid" in v:
            ar, ac = v.get("anchor", [-1, -1])
            rows = ["(" + " ".join(("@" if (i, j) == (ar, ac) else "") + str(x) for j, x in enumerate(r)) + ")"
                    for i, r in enumerate(v["grid"])]
            return "\n".join([head, "  (grid", *("    " + r for r in rows)]) + "))"
        if "Position" in ts and v and all(isinstance(r, list) and not any(isinstance(x, list) for x in r) for r in v) \
                and not all(len(r) == len(ts) for r in v):
            # a picture of the relation's frame
            return "\n".join([head, "  (grid", *("    " + arg(r) for r in v)]) + "))"
        rest = " " + " ".join(arg(r) for r in v) + ")"
        return grid_param(head, ts, rest) or head + rest

    def witness_form(self, rest: str, wit, used: set[str], ind: str) -> list[str]:
        """A witness from its @witness line `<id>: <plausibility> <verdict>`
        and nested lines, with its grids from the witness file."""
        m = re.match(r"([\w=.-]+):\s*(\S+)\s+(\S+)\s*(.*)", rest)
        if not m:
            return [f"{ind};; TODO witness-line: {rest}"]
        wid, plaus, verdict, more = m.groups()
        verdict = name_of(verdict, self.many)
        head = f"{ind}(witness {wid} {plaus} {verdict}"
        if wid in used:
            return [head + ")"]
        used.add(wid)
        lines = [head]
        for rel in re.findall(r"@relaxed\s+([\w-]+)", more):
            lines.append(f"{ind}  (relaxed {rel})")
        w = next((x for x in wit if x["id"] == wid), None)
        if w is None:
            self.todo.add("witness-missing", f"{wid}: the witness file holds no witness of this id")
            close(lines, ")")
            return [ind + t for t in self.todo.take()] + lines
        lines.append(f"{ind}  (separates {quote(params_to_amp(w.get('separates', '')))})")
        for k, v in (w.get("assign") or {}).items():
            at = self.c.names.get((("Params",), k)) if k in self.c.rigid else None   # a placed relation: `block.part`
            amp = self.c.wrote(f"&{at or k}", Written(("Params",), k, False))
            lines.extend(f"{ind}  {l}" for l in self.assign_form(amp, v).split("\n"))
        lines.append(f"{ind}  (input (grid")
        lines.extend(f"{ind}    ({' '.join(map(str, r))})" for r in w["input"])
        close(lines, "))")
        outs = w["output"]
        if isinstance(outs, list) and outs and isinstance(outs[0], dict):
            for g in outs:
                names = " ".join(name_of(n, self.many) for n in g["cases"])
                grid = g["grid"]
                if grid is None:
                    lines.append(f"{ind}  (output {names} undefined)")
                elif grid and isinstance(grid[0][0], list):
                    lines.append(f"{ind}  (output {names}")
                    for gr in grid:
                        lines.append(f"{ind}    (grid")
                        lines.extend(f"{ind}      ({' '.join(map(str, r))})" for r in gr)
                        close(lines, ")")
                    close(lines, ")")
                else:
                    lines.append(f"{ind}  (output {names} (grid")
                    lines.extend(f"{ind}    ({' '.join(map(str, r))})" for r in grid)
                    close(lines, "))")
        else:
            lines.append(f"{ind}  (output (grid")
            lines.extend(f"{ind}    ({' '.join(map(str, r))})" for r in outs)
            close(lines, "))")
        close(lines, ")")
        return lines


def agrees_but_wildcards(a, b) -> bool:
    """Whether the terms `a` and `b` are the same wherever neither is `_`,
    and a variable stands only against `_` or itself."""
    if isinstance(a, Wildcard) or isinstance(b, Wildcard):
        return True
    if isinstance(a, RecordTerm) and isinstance(b, RecordTerm):
        return len(a.args) == len(b.args) and all(agrees_but_wildcards(x, y) for x, y in zip(a.args, b.args))
    if isinstance(a, ConstructorTerm) and isinstance(b, ConstructorTerm):
        return a.name == b.name and len(a.args) == len(b.args) and all(
            agrees_but_wildcards(x, y) for x, y in zip(a.args, b.args))
    return False


def ctor_names(t) -> tuple[str, ...]:
    if isinstance(t, ConstructorTerm):
        return (t.name,) + sum((ctor_names(a) for a in t.args), ())
    if isinstance(t, RecordTerm):
        return sum((ctor_names(a) for a in t.args), ())
    return ()


MOVED_RELS: dict[str, str] = {}
"""The solver at hand's relations of an expanded instance that a witness
name spells, `lattice.divider`, by the relation of the shape that stands
for each, `lattice_divider`."""


def name_of(n: str, many: set[str] = frozenset()) -> str:
    """A witness-file case name in arcdata's spelling; `many` holds the
    parameters whose @derive lines give several proposers, a derived side
    per proposer."""
    if n.startswith("&"):
        return n
    parts = [p.strip() for p in n.split("&")]
    out = []
    for p in parts:
        m = re.match(r"([\w.]+)=(\w+)", p)
        if m:
            rel, side = m.groups()
            side = {"stored": "$Stored", "derived": "$Derived"}.get(side, side if rel in many else "$Derived")
            rel = MOVED_RELS.get(rel, rel)
            out.append(f"&{rel}={side}")
        elif p in ("concept", "any", "other", "derived", "stored"):
            out.append(p)
        else:
            out.append(p if p.startswith("$") else "$" + p)
    return out[0] if len(out) == 1 else "(" + " ".join(out) + ")"


NEG_OP = {ComparisonOperator.LT: ComparisonOperator.GE, ComparisonOperator.GE: ComparisonOperator.LT,
          ComparisonOperator.LE: ComparisonOperator.GT, ComparisonOperator.GT: ComparisonOperator.LE,
          ComparisonOperator.EQ: ComparisonOperator.NE, ComparisonOperator.NE: ComparisonOperator.EQ}


def record_eqs(u: Unit, fields_of=None) -> Unit:
    """The clause with each `V = [..]` resolved: at the body's top level V
    is the record in every other place, and where each branch of a
    disjunction gives V a record of one width, V is a record of one variable
    per component, `V_1`, `V_2`, ..., each branch gives the components, and
    a component that a branch alone makes is that component's variable."""
    if u.body is None:
        return u
    taken: set[str] = set()
    collect_vars(list(u.body), taken)
    collect_vars([AtomLiteral(u.head, False)], taken)

    def fresh(base: str) -> Variable:
        n = base
        k = 2
        while n in taken:
            n, k = f"{base}{k}", k + 1
        taken.add(n)
        return Variable(n)

    def eq_of(l):
        if not (isinstance(l, Comparison) and l.op == ComparisonOperator.EQ):
            return None
        for v, t in ((l.lhs, l.rhs), (l.rhs, l.lhs)):
            if isinstance(v, Variable) and isinstance(t, RecordTerm):
                vs: set[str] = set()
                collect_vars([AtomLiteral(Atom(RelationName((), "_"), (t,), 0), False)], vs)
                if v.name not in vs:
                    return v.name, t
        return None

    def uses(lits, head, v: str) -> int:
        n = 0
        for l in lits:
            if isinstance(l, AtomLiteral) and not (not l.atom.relation.instances and l.atom.relation.name == "impl_choice"):
                vs: list[str] = []
                def walk(t):
                    if isinstance(t, Variable):
                        vs.append(t.name)
                    for a in getattr(t, "args", ()) or ():
                        walk(a)
                for a in l.atom.args:
                    walk(a)
                n += vs.count(v)
            elif isinstance(l, (Comparison, Disjunction)):
                vs2: set[str] = set()
                collect_vars([l], vs2)
                n += v in vs2
        hv: set[str] = set()
        collect_vars([AtomLiteral(head, False)], hv)
        return n + (v in hv)

    def fill(t, v: str, top: bool = True):
        """The record with each wildcard a fresh variable, named after its
        field where the record's type is known."""
        if isinstance(t, Wildcard):
            return fresh(f"{v}_w")
        if isinstance(t, RecordTerm):
            names = (fields_of(u, v) if fields_of and top else None) or []
            return RecordTerm(tuple(fresh(f"{v}_{names[k]}") if isinstance(a, Wildcard) and k < len(names)
                                    and len(names) == len(t.args) else fill(a, v, False)
                                    for k, a in enumerate(t.args)))
        return t

    head, body = u.head, list(u.body)
    changed = True
    while changed:
        changed = False
        for i, l in enumerate(body):
            got = eq_of(l)
            if got is None:
                continue
            v, t = got
            rest = body[:i] + body[i + 1:]
            if uses(rest, head, v) > 1:
                t = fill(t, v)
            m = {v: t}
            head = subst_terms(head, m)
            body = [subst_terms(x, m) for x in rest]
            changed = True
            break
    # a record a disjunction's branches give
    out = []
    for i, l in enumerate(body):
        if not isinstance(l, Disjunction):
            out.append(l)
            continue
        outside: set[str] = set()
        collect_vars(body[:i] + body[i + 1:], outside)
        collect_vars([AtomLiteral(head, False)], outside)
        per = [[(j, eq_of(x)) for j, x in enumerate(b) if eq_of(x) is not None] for b in l.branches]
        cands = {v for b in per for _, (v, _) in b if v in outside}
        for v in sorted(cands):
            got = [[(j, t) for j, (w, t) in b if w == v] for b in per]
            if any(len(g) > 1 for g in got) or len({len(g[0][1].args) for g in got if g}) != 1:
                continue
            width = next(len(g[0][1].args) for g in got if g)
            names = fields_of(u, v) if fields_of else None
            if names is None or len(names) != width:
                names = [str(k + 1) for k in range(width)]
            comps = [fresh(f"{v}_{n}") for n in names]
            rec = RecordTerm(tuple(comps))
            branches = []
            for b, g in zip(l.branches, got):
                if not g:
                    branches.append(tuple(subst_terms(x, {v: rec}) for x in b))
                    continue
                j, t = g[0]
                lits = list(b[:j] + b[j + 1:])
                mine: set[str] = set()
                collect_vars(lits, mine)
                ren: dict[str, object] = {}
                eqs = []
                for c_, a in zip(comps, t.args):
                    if isinstance(a, Variable) and a.name not in outside and a.name not in ren \
                            and a.name not in {x.name for x in comps}:
                        ren[a.name] = c_
                    else:
                        eqs.append(Comparison(ComparisonOperator.EQ, c_, ren.get(a.name, a) if isinstance(a, Variable) else a, l.line))
                lits = [subst_terms(x, ren) for x in lits] + eqs
                branches.append(tuple(lits))
            l = dc_replace(l, branches=tuple(branches))
            m = {v: rec}
            head = subst_terms(head, m)
            body = [subst_terms(x, m) if k != i else x for k, x in enumerate(body)]
            per = [[(j, eq_of(x)) for j, x in enumerate(b) if eq_of(x) is not None] for b in l.branches]
        # a record a branch alone gives: the record in the branch's other places
        branches = []
        for b in l.branches:
            b = list(b)
            again = True
            while again:
                again = False
                for j, x in enumerate(b):
                    got = eq_of(x)
                    if got is None or got[0] in outside:
                        continue
                    v, t = got
                    rest = b[:j] + b[j + 1:]
                    if uses(rest, Atom(RelationName((), "_"), (), 0), v) > 1:
                        t = fill(t, v)
                    b = [subst_terms(y, {v: t}) for y in rest]
                    again = True
                    break
            branches.append(tuple(b))
        l = dc_replace(l, branches=tuple(branches))
        out.append(l)
    if head == u.head and out == list(u.body):
        return u
    return dc_replace(u, head=head, body=tuple(out))


def walk_lits(lits):
    """Each literal of a body, those inside a disjunction's branches included."""
    for l in lits:
        yield l
        if isinstance(l, Disjunction):
            for b in l.branches:
                yield from walk_lits(b)


def rename_rel(x, old: RelationName, new: RelationName):
    """`x` with each read of relation `old` a read of `new`."""
    if isinstance(x, RelationName):
        return new if x == old else x
    if isinstance(x, tuple):
        return tuple(rename_rel(y, old, new) for y in x)
    if is_dataclass(x) and not isinstance(x, type):
        ch = {}
        for f_ in dc_fields(x):
            v = getattr(x, f_.name)
            if isinstance(v, (tuple, RelationName)) or (is_dataclass(v) and not isinstance(v, type)):
                ch[f_.name] = rename_rel(v, old, new)
        return dc_replace(x, **ch) if ch else x
    return x


def subst(x, m: dict[str, str]):
    """`x` with each variable renamed by `m`."""
    if isinstance(x, Variable):
        return Variable(m.get(x.name, x.name))
    if isinstance(x, tuple):
        return tuple(subst(y, m) for y in x)
    if is_dataclass(x) and not isinstance(x, type):
        changes = {}
        for f in dc_fields(x):
            v = getattr(x, f.name)
            if isinstance(v, (tuple, Variable)) or (is_dataclass(v) and not isinstance(v, type)):
                changes[f.name] = subst(v, m)
        return dc_replace(x, **changes) if changes else x
    return x


def subst_terms(x, m: dict):
    """`x` with each variable named in `m` replaced by its term."""
    if isinstance(x, Variable):
        return m.get(x.name, x)
    if isinstance(x, tuple):
        return tuple(subst_terms(y, m) for y in x)
    if is_dataclass(x) and not isinstance(x, type):
        changes = {}
        for f in dc_fields(x):
            v = getattr(x, f.name)
            if isinstance(v, (tuple, Variable)) or (is_dataclass(v) and not isinstance(v, type)):
                changes[f.name] = subst_terms(v, m)
        return dc_replace(x, **changes) if changes else x
    return x


def var_uses(x, counts: Counter) -> None:
    """Count each variable's occurrences in a term, a literal or a tuple of them."""
    if isinstance(x, Variable):
        counts[x.name] += 1
    elif isinstance(x, tuple):
        for y in x:
            var_uses(y, counts)
    elif is_dataclass(x) and not isinstance(x, type):
        for f_ in dc_fields(x):
            var_uses(getattr(x, f_.name), counts)


def inlined(prog, names: frozenset[str], lib: Lib):
    """`prog` with each relation of `names` written no relation: its clauses'
    bodies stand at each call, the head's variables replaced by the call's
    terms and the other variables by fresh ones, an `OR` of the bodies where
    it has several clauses."""
    if not names:
        return prog
    defs: dict[str, list[Unit]] = defaultdict(list)
    for u in prog.units:
        if u.head.relation.name in names and not u.head.relation.instances and u.body is not None:
            defs[u.head.relation.name].append(u)
    for n in names:
        assert n in defs and n not in lib.top, n
        for u in defs[n]:
            hs = [a.name for a in u.head.args if isinstance(a, Variable)]
            assert len(hs) == len(u.head.args) == len(set(hs)), (n, u.head)

    def instance(h: Unit, args, taken: set[str]) -> list:
        uses: Counter = Counter()
        var_uses(h.body, uses)
        m: dict[str, object] = {}
        hv = {a.name for a in h.head.args}

        def fresh(v: str) -> Variable:
            k, w = 1, v
            while w in taken:
                k += 1
                w = f"{v}{k}"
            taken.add(w)
            return Variable(w)
        for a, t in zip(h.head.args, args):
            m[a.name] = fresh(a.name) if isinstance(t, Wildcard) and uses[a.name] > 1 else t
        for v in uses:
            if v not in hv:
                m[v] = fresh(v)
        return expand([subst_terms(x, m) for x in h.body], taken, 0)

    def expand(lits, taken: set[str], depth: int) -> list:
        assert depth < 8
        out: list = []
        for l in lits:
            if isinstance(l, AtomLiteral) and not l.atom.relation.instances and l.atom.relation.name in defs:
                assert not l.negated, l
                bodies = [instance(h, l.atom.args, taken) for h in defs[l.atom.relation.name]]
                if len(bodies) == 1:
                    out.extend(bodies[0])
                else:
                    out.append(Disjunction(tuple(tuple(b) for b in bodies), l.atom.line))
            elif isinstance(l, Disjunction):
                out.append(dc_replace(l, branches=tuple(tuple(expand(b, taken, depth)) for b in l.branches)))
            else:
                out.append(l)
        return out

    units = []
    for u in prog.units:
        if u.head.relation.name in names and not u.head.relation.instances:
            continue
        if u.body is not None:
            taken: set[str] = set()
            collect_vars([*u.body, AtomLiteral(u.head, False)], taken)
            u = dc_replace(u, body=tuple(expand(u.body, taken, 0)))
        units.append(u)
    rels = tuple(r for r in prog.relations if r.name not in names)
    return dc_replace(prog, units=tuple(units), relations=rels)


MERGES: Counter[str] = Counter()


def label_names(lines: list[str]) -> set[str]:
    """The labels the lines name, comment lines aside."""
    out: set[str] = set()

    def note(mark: str, x: str) -> str:
        out.add(x)
        return mark + x
    relabel(lines, note)
    return out


def made_at_site(lines: list[str], x: str) -> bool:
    return any(re.search(rf"(?<!\(= )\*{re.escape(x)}(?!\w)", l) for l in lines if not l.lstrip().startswith(";;"))


OPS_ = {"=", "!=", "<", "<=", ">", ">="}


def without_repeats(f: "Form", drop: dict[str, str]) -> "Form":
    """The form without the `(= *X Y)` lines that repeat a dropped column
    X, and without those columns, its body reading Y for X."""
    lines: list[str] = []
    for l in f.lines:
        m = next((re.fullmatch(rf"\s*\(= \*{x} {y}\)(\)*)", l) for x, y in drop.items()
                  if re.fullmatch(rf"\s*\(= \*{x} {y}\)(\)*)", l)), None)
        if m is None:
            lines.append(l)
        elif m.group(1):
            lines[-1] += m.group(1)   # the form's closers move to the line before
    # the body reads the column the dropped one repeats
    lines = relabel(lines, lambda mark, v: drop[v] if v in drop else mark + v)
    new = dc_replace(f, lines=lines)
    new.cols = [c_ for c_ in f.cols if c_ not in drop]
    return new


def read_without(lines: list[str], rel: str, drop: dict[str, str]) -> list[str] | None:
    """The lines with each one-line read of `rel` leaving out the dropped
    columns, and the label each named relabeled to the label at the column
    it repeats, or, where the read names no label there, standing at that
    column; None where a read is not one line."""
    ren: dict[str, str] = {}
    out = []
    for l in lines:
        i = l.find(f"({rel} ")
        if i < 0:
            out.append(l)
            continue
        depth, j = 0, i
        while j < len(l):
            depth += {"(": 1, ")": -1}.get(l[j], 0)
            if depth == 0:
                break
            j += 1
        if depth:
            return None
        atom = l[i + 1:j]
        items, k, d, cur = [], len(rel) + 1, 0, ""
        for ch in atom[k:]:
            if ch == "(":
                d += 1
            elif ch == ")":
                d -= 1
            if ch == " " and d == 0:
                if cur:
                    items.append(cur)
                cur = ""
            else:
                cur += ch
        if cur:
            items.append(cur)

        def col_lab(it):
            m = re.fullmatch(r"\(:(\w+) ([*^]?)(\w+)\)", it)
            if m:
                return m.group(1), m.group(3), m.group(2)
            m = re.fullmatch(r"([*^]?)(\w+)", it)
            return (m.group(2), m.group(2), m.group(1)) if m else (None, None, "")
        labs = {col_lab(it)[0]: col_lab(it)[1] for it in items}
        kept = []
        for it in items:
            col, lab, mark = col_lab(it)
            if col in drop:
                if drop[col] not in labs:
                    # the read takes the label at the column the dropped one repeats
                    kept.append(f"(:{drop[col]} {mark}{lab})")
                    continue
                ren[lab] = labs[drop[col]]
                continue
            kept.append(it)
        out.append(l[:i] + "(" + " ".join([rel] + kept) + l[j:])
    if not ren:
        return out
    return relabel(out, lambda mark, v: (mark if v not in ren else "") + ren.get(v, v))


def relabel(lines: list[str], fn) -> list[str]:
    """The lines with each label `[*^]X` replaced by `fn(mark, X)`; a bare
    site whose label changes keeps its column, `(:X new)`, and a record's
    field elided to its label keeps its field the same way."""
    stack: list[str | None] = []
    out = []
    for l in lines:
        if l.lstrip().startswith(";;"):
            out.append(l)
            continue
        parts, i = [], 0
        for m in re.finditer(r"[()]|[^\s()]+", l):
            tok = m.group()
            if tok == "(":
                stack.append(None)
                continue
            if tok == ")":
                if stack:
                    stack.pop()
                continue
            if stack and stack[-1] is None:
                stack[-1] = tok
                continue
            lm = re.fullmatch(r"([*^]?)([A-Z]\w*)", tok)
            if not lm:
                continue
            new = fn(lm.group(1), lm.group(2))
            if new == tok:
                continue
            head = stack[-1] if stack else None
            bare = head is not None and not head.startswith(":") and head not in OPS_
            field_ = head is not None and re.fullmatch(r":[a-z]\w*", head) is not None
            if bare and new.lstrip("*^") != lm.group(2):
                new = f"(:{lm.group(2)} {new})"
            elif field_ and new.lstrip("*^") != lm.group(2):
                new = f"(:\0{lm.group(2)} {new})"
            parts.append(l[i:m.start()])
            parts.append(new)
            i = m.end()
        parts.append(l[i:])
        # a site of one label on a type-parameter column is no record, a key's aside
        line = re.sub(r"\((:(?!key\b)[a-z]\w*) \(:\0\w+ ([^()\s]+)\)\)", r"(\1 \2)", "".join(parts))
        out.append(line.replace(":\0", ":"))
    return out


def or_body(bodies: list[tuple[list[str], list[str]]], cols: set[str], outer: set[str]) -> list[str]:
    """The lines of one OR with a branch per (comments, body lines): first
    a branch that makes every column at a site, where one does; each later
    branch names the columns, and its other labels that an earlier branch
    names are renamed with a digit. Each branch's comments stand above it.
    A body that an earlier branch already holds is no branch."""
    uniq: list[tuple[list[str], list[str]]] = []
    for cm, ls in bodies:
        if not any(ls == ls2 for _, ls2 in uniq):
            uniq.append((cm, ls))
    kept = drop_implied([ls for _, ls in uniq])
    bodies = [b for b in uniq if any(b[1] is k for k in kept)]
    if len(bodies) == 1:
        return [*bodies[0][0], *bodies[0][1]]

    def rank(k: int):
        ls = bodies[k][1]
        # a `(= *X Y)` whose Y the branch makes: Y's site could make X
        same = sum(1 for l in ls for m in re.finditer(r"\(= \*(\w+) ([A-Z]\w*)\)", l)
                   if m.group(1) in cols and m.group(2) not in outer)
        return (same, -sum(made_at_site(ls, x) for x in cols), k)
    k0 = min(range(len(bodies)), key=rank)
    bodies = [bodies[k0], *(b for k, b in enumerate(bodies) if k != k0)]
    taken = set(outer) | set(cols)
    for _, ls in bodies:
        taken |= label_names(ls)
    seen = label_names(bodies[0][1])
    groups = [bodies[0]]
    for cm, ls in bodies[1:]:
        ren: dict[str, str] = {}
        for x in sorted(label_names(ls) - cols - outer):
            if x in seen:
                n = 2
                while f"{x}{n}" in taken:
                    n += 1
                ren[x] = f"{x}{n}"
                taken.add(ren[x])

        def sub(mark: str, x: str) -> str:
            return x if x in cols else mark + ren.get(x, x)
        ls = relabel(ls, sub)
        seen |= label_names(ls)
        groups.append((cm, ls))
    head, pad = "(OR ", "    "
    out: list[str] = []
    for gi, (cm, g) in enumerate(groups):
        lines = [("(" if li == 0 else " ") + l for li, l in enumerate(g)] or ["("]
        close(lines, ")")
        out.extend(cm if gi == 0 else [pad + x for x in cm])
        out.append((head if gi == 0 else pad) + lines[0])
        out.extend(pad + l for l in lines[1:])
    close(out, ")")
    return out


def drop_implied(bodies: list[list[str]]) -> list[list[str]]:
    """The union's bodies less each that holds only where another holds,
    the earlier of two that each imply the other kept."""
    from arclog_convert.lint import implies, read
    try:
        parsed = [read("\n".join(b)) for b in bodies]
    except SyntaxError:
        return bodies
    gone: set[int] = set()
    for i in range(len(bodies)):
        for j in range(len(bodies)):
            if i == j or j in gone:
                continue
            if implies(parsed[i], parsed[j]) and not (implies(parsed[j], parsed[i]) and j > i):
                gone.add(i)
                break
    return [b for k, b in enumerate(bodies) if k not in gone]


def merge_forms(forms: list[Form]) -> list[Form]:
    """Each relation's clauses in one block as one clause whose body is an OR,
    a branch per clause."""
    names: dict[str, list[Form]] = defaultdict(list)
    for f in forms:
        names[f.name].append(f)
    out: list[Form] = []
    done: set[str] = set()
    for f in forms:
        if f.name in done:
            continue
        done.add(f.name)
        out.extend(g for g in names[f.name] if g.body is None)
        fs = [g for g in names[f.name] if g.body is not None]
        if len(fs) <= 1:
            out.extend(fs)
            continue
        if len({g.side for g in fs}) != 1 or len({tuple(g.cols) for g in fs}) != 1:
            MERGES["unmerged"] += 1
            MERGES_UNMERGED.append(f.name)
            out.extend(fs)
            continue
        MERGES["relation"] += 1
        body = or_body([(g.comments, g.body or []) for g in fs], set(fs[0].cols), set())
        g = Form([f"({fs[0].side} {f.name}"] + ["  " + l for l in body + fs[0].marks], f.name,
                 set().union(*(x.reads for x in fs)), line=min(x.line for x in fs))
        close(g.lines, ")")
        g.claim_slugs = [s for x in fs for s in x.claim_slugs]
        g.branches = tuple(sorted(set().union(*(x.branches for x in fs))))
        g.cols, g.side = list(fs[0].cols), fs[0].side
        g.marks = list(fs[0].marks)
        out.append(g)
    return out


MERGES_UNMERGED: list[str] = []


def exported(lines: list[str]) -> set[str]:
    """The labels a list of atoms makes in its own scope: at its sites, and
    those an OR or IF in it exports."""
    from arclog_convert.lint import L, Sym, leaves as lint_leaves, read
    try:
        items = read("\n".join(lines))
    except SyntaxError:
        return set(re.findall(r"[*^](\w+)", " ".join(lines)))

    def named(x) -> set[str]:
        return {t.text.lstrip("*^") for t in lint_leaves(x) if isinstance(t, Sym)} if isinstance(x, L) else set()

    def made(items) -> set[str]:
        out: set[str] = set()
        for a in items:
            if not isinstance(a, L):
                continue
            if a.head == "OR":
                brs = [b for b in a.items[1:] if isinstance(b, L)]
                if brs:
                    first = made(brs[0].items)
                    out |= {x for x in first if all(x in named(b) for b in brs[1:])}
            elif a.head == "IF":
                parts = [p_ for p_ in a.items[1:] if isinstance(p_, L)]
                if len(parts) == 3:
                    out |= made(parts[1].items) & named(parts[2])
            elif a.head in ("ALL", "NOT"):
                continue
            elif a.head == "=":
                if len(a.items) == 3 and isinstance(a.items[1], Sym) and a.items[1].text[:1] == "*":
                    out.add(a.items[1].text[1:])
            else:
                out |= {t.text[1:] for t in lint_leaves(a) if isinstance(t, Sym) and t.text[:1] in "*^"}
        return out
    return made(items)


def fold_or_lines(text: str) -> str:
    """Each RULE_OR_DET or DET_OR_RULE line on a relation that a clause of
    the same block derives, folded into that clause: the clause takes the
    line's head, gloss and proposers, and the line goes, so one form
    derives the relation."""
    from arclog_convert.lint import L, Str, Sym, read, flat
    try:
        items = read(text)
    except SyntaxError:
        return text
    lines_: list[tuple[object, L]] = []
    clauses: dict[tuple, list[L]] = defaultdict(list)
    side_of = {"RULE_OR_DET": "RULE", "DET_OR_RULE": "DET"}

    def walk_(xs, block) -> None:
        for x in xs:
            if not isinstance(x, L):
                continue
            named = len(x.items) >= 2 and isinstance(x.items[1], Sym)
            after = x.items[3:] if named and isinstance(x.items[2:3] and x.items[2], Str) else x.items[2:]
            if x.head in side_of and named and all(isinstance(y, Sym) or y.head == "ONE" for y in after):
                lines_.append((block, x))
            elif x.head in ("RULE", "DET") and named and any(isinstance(y, L) and y.head != "ONE" for y in x.items[2:]):
                clauses[(block, x.head, x.items[1].text)].append(x)
            elif x.head in ("INPUT", "OUTPUT", "ALTS"):
                walk_(x.items[1:], block)
            elif x.head == "ALT":
                walk_(x.items[1:], id(x))
    walk_(items, None)
    edits: list[tuple[int, int, str]] = []
    for block, f in lines_:
        cs = clauses.get((block, side_of[f.head], f.items[1].text), [])
        if len(cs) != 1:
            continue
        g = cs[0]
        glossed = len(f.items) > 2 and isinstance(f.items[2], Str)
        rest_ = f.items[2 + glossed:]
        props = [y.text for y in rest_ if isinstance(y, Sym)]
        marks = {flat(y) for y in rest_ if isinstance(y, L)}
        if not marks <= {flat(y) for y in g.items[2:] if isinstance(y, L) and y.head == "ONE"}:
            continue
        a = text.rfind("\n", 0, f.start) + 1
        b = text.find("\n", f.end)
        b = len(text) if b < 0 else b
        tail = text[f.end:b]
        prev = text[text.rfind("\n", 0, max(a - 1, 0)) + 1:max(a - 1, 0)]
        if text[a:f.start].strip() or tail.strip(" )") or (tail.strip() and prev.lstrip().startswith(";;")):
            continue
        head_end = g.items[1].pos + len(g.items[1].text)
        edits.append((g.start, head_end, " ".join([f"({f.head} {f.items[1].text}",
                                                     *([f.items[2].text] if glossed else []), *props])))
        # the line goes with its own line break and a blank line after it;
        # parens after it on its line close an enclosing form
        if tail.strip():
            p_ = a - 1
            while p_ > 0 and text[p_ - 1] == "\n":
                p_ -= 1
            edits.append((p_, b, tail.strip()))
        else:
            end = b + 1
            if text[end:end + 1] == "\n":
                end += 1
            elif text[a - 2:a] == "\n\n":
                a -= 1
            edits.append((a, end, ""))
    for a, b, new in sorted(edits, reverse=True):
        text = text[:a] + new + text[b:]
    return text


def drop_key_sites(text: str) -> str:
    """Each key site, inside an instance's keyed inputs, on a read of an
    instance keyed by the same labels at those labels, dropped: such a read
    joins on the key in scope."""
    from arclog_convert.lint import L, Sym, read, walk
    try:
        items = read(text)
    except SyntaxError:
        return text
    keys: dict[str, list[str]] = {}
    inits = [a for f in items for a in walk(f) if isinstance(a, L) and a.head == "INIT" and len(a.items) > 2
             and isinstance(a.items[1], Sym)]
    for a in inits:
        for c in a.items[3:]:
            if isinstance(c, L) and c.head == "key" and len(c.items) > 1:
                ks: list[str] = []
                for t in walk(c.items[1]):
                    if isinstance(t, Sym) and t.text[:1] == "^" and t.text[1:] not in ks:
                        ks.append(t.text[1:])
                keys[a.items[1].text] = ks
    cuts: list[tuple[int, int]] = []
    for a in inits:
        ks = keys.get(a.items[1].text)
        if not ks:
            continue
        for c in a.items[3:]:
            if not (isinstance(c, L) and c.head == "key"):
                continue
            for x in c.items[2:]:
                for at in walk(x):
                    if not (isinstance(at, L) and at.head and at.head.startswith("&") and "." in at.head):
                        continue
                    if keys.get(at.head.partition(".")[0]) != ks:
                        continue
                    for site in at.items[1:]:
                        if isinstance(site, L) and site.head == ":key" and site.start >= 0 and \
                                [t.text if isinstance(t, Sym) else None for t in site.items[1:]] == ks:
                            cuts.append((site.start, site.end))
    for a, b in sorted(set(cuts), reverse=True):
        while a > 0 and text[a - 1] == " ":
            a -= 1
        text = text[:a] + text[b:]
    return text


def share_labels(branches: list[list[str]]) -> list[list[str]]:
    """OR branches with the labels the first branch makes named, not made,
    in each later branch that makes them, so they are exported."""
    made = exported(branches[0])
    out = [branches[0]]
    for br in branches[1:]:
        out.append([re.sub(r"[*^](\w+)", lambda m: m.group(1) if m.group(1) in made else m.group(0), l)
                    for l in br])
    return out


def mark_key(lines: list[str], knames: list[str]) -> list[str]:
    """Turn the first `*K` of each key label into `^K`."""
    out = []
    left = set(knames)
    for line in lines:
        for k in list(left):
            pat = re.compile(r"\*" + re.escape(k) + r"(?![\w])")
            if pat.search(line):
                line = pat.sub("^" + k, line, count=1)
                left.discard(k)
        out.append(line)
    return out


def topo(forms: list[Form]) -> list[Form]:
    """The forms with each relation's forms together, after the relations
    they read."""
    names: dict[str, list[Form]] = defaultdict(list)
    for f in forms:
        names[f.name].append(f)
    done: set[str] = set()
    visiting: set[str] = set()
    out: list[Form] = []

    def visit(name: str) -> None:
        if name in done or name in visiting:
            return
        visiting.add(name)
        for f in names[name]:
            for r in sorted(f.reads):
                if r != name and r in names:
                    visit(r)
        visiting.discard(name)
        done.add(name)
        out.extend(names[name])

    for f in sorted(forms, key=lambda f: f.line):
        visit(f.name)
    return out


def render_forms(forms: list[Form], ind: str) -> list[str]:
    out = []
    forms = merge_forms(forms)
    for i, f in enumerate(forms):
        if i:
            out.append("")
        out.extend(ind + c for c in f.comments)
        out.extend(ind + l if l else l for l in f.lines)
    return out


RENAMED = {"in": "input", "ex_in": "ex_input", "ex_out": "ex_output"}


def renamed(text: str) -> str:
    """The grid relations under arclog's names, `input`, `ex_input`,
    `ex_output` and `&output`, and a choice's candidates clause as `from`."""
    text = re.sub(r"(?<=\()(in|ex_in|ex_out)(?=[\s)])", lambda m: RENAMED[m.group(1)], text)
    text = re.sub(r"&out(?![\w.])", "&output", text)
    return text.replace("(@@in ", "(from ")


PLAN_HASH = "solver file sha256: "


def solver_hash(stem: str) -> str:
    return hashlib.sha256((SOLVERS / f"{stem}.dl").read_bytes()).hexdigest()


def stale_plans(stems: list[str]) -> list[str]:
    """The solvers whose plan file is missing, or records a hash other than
    their solver file's, or a runner and lib stamp other than the current
    one."""
    from cli.common import stamp
    lib_line = f"runner and lib: {stamp()}"
    out = []
    for stem in stems:
        p = PLANS / f"{stem}.txt"
        lines = p.read_text().splitlines() if p.exists() else []
        if PLAN_HASH + solver_hash(stem) not in lines or lib_line not in lines:
            out.append(stem)
    return out


def write_plan(stem: str) -> str | None:
    """Run the determination plan of one solver and write its output, with
    the solver file's hash, to its plan file; None, or the error."""
    digest = solver_hash(stem)
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_dl.py"), "determination-plan", stem],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        lines = (r.stderr or r.stdout).strip().splitlines()
        return lines[-1] if lines else f"exit {r.returncode}"
    text = r.stdout + r.stderr
    PLANS.mkdir(parents=True, exist_ok=True)
    (PLANS / f"{stem}.txt").write_text(text + ("" if text.endswith("\n") else "\n") + PLAN_HASH + digest + "\n")
    return None


def refresh_plans(stems: list[str]) -> None:
    stale = stale_plans(stems)
    if not stale:
        return
    print(f"rerunning the determination plan of {len(stale)} solvers")
    with ThreadPoolExecutor(max_workers=8) as pool:
        for stem, err in zip(stale, pool.map(write_plan, stale)):
            if err is not None:
                print(f"  {stem}: the plan failed: {err}")


_LIBS: tuple[Lib, Lib] | None = None


def hoist_shared(text: str) -> str:
    """The text with each form that several alts state with one meaning,
    and that only their cases read, stated once in the concept: at the end
    of the concept's block of the slug it stands under, or of a later block
    that declares a relation it reads."""
    from arclog_convert.lint import alt_repeats, placements, read, reads
    forms = read(text)
    pl = placements(forms)
    groups: dict[int, tuple] = {}
    for kind, p, ref, shared in alt_repeats(pl):
        if kind == "shared" and not shared:
            groups.setdefault(id(ref), (ref, []))[1].append(p)
    if not groups:
        return text
    lines = text.split("\n")
    blocks = {f.items[1].text: f for f in forms if f.head in ("INPUT", "OUTPUT")}
    order = list(blocks)
    block_of = {p.name: p.slug for p in pl if p.name and not p.alts}
    own_end: dict[int, str] = {}   # a form's last line, less the parens after it

    def span(f) -> tuple[int, int, str] | None:
        """The form's first line, with the comments above it, its last
        line, and the closing parens after it there, where only those
        follow it."""
        a, b = f.line - 1, text.count("\n", 0, f.end)
        tail = text[f.end:].split("\n", 1)[0]
        if tail.strip(")") or text[:f.start].rsplit("\n", 1)[-1].strip():
            return None
        while a > 0 and lines[a - 1].strip().startswith(";;"):
            a -= 1
        own_end[b] = lines[b][:len(lines[b]) - len(tail)]
        return a, b, tail

    moves: dict[str, list[list[str]]] = defaultdict(list)   # a block's slug -> the forms it takes
    cuts = []
    for ref, reps in sorted(groups.values(), key=lambda g: g[0].form.line):
        spans = [span(x.form) for x in [ref, *reps]]
        rs = reads(ref.form, ref.name.partition(".")[0])
        if any(x is None for x in spans) or any(block_of.get(r, "") is None for r in rs) \
                or any(r not in block_of and any(r == p.name for p in pl) for r in rs):
            continue   # it reads a form of the tail, which stands after the ALTS forms, or one of an alt
        at = [order.index(sl) for sl in [ref.slug, *(block_of.get(r) for r in rs)] if sl in order]
        slug = order[max(at)] if at else order[-1]
        a, b, tail = spans[0] or (0, 0, "")
        ind = len(lines[ref.form.line - 1]) - len(lines[ref.form.line - 1].lstrip())
        body = [l[ind:] for l in lines[a:b + 1]]
        body[-1] = body[-1][:len(body[-1]) - len(tail)]
        moves[slug].append(["  " + l if l else l for l in body])
        block_of[ref.name] = slug
        cuts += [x for x in spans if x is not None]
    # each alt's copy, bottom up; the parens after it close the blocks above it
    for a, b, tail in sorted(cuts, reverse=True):
        tail = lines[b][len(own_end[b]):]   # a later copy's parens may have come up to it
        del lines[a:b + 1]
        k = a - 1
        while k > 0 and not lines[k].strip():
            k -= 1
        if tail:
            lines[k] += tail
            del lines[k + 1:a]
        elif a < len(lines) and not lines[a].strip():
            del lines[a]   # the blank line that parted it from the next form
        elif not lines[a - 1].strip():
            del lines[a - 1]
    for slug in sorted(moves, key=order.index, reverse=True):
        e = text.count("\n", 0, blocks[slug].end)
        lines[e] = lines[e][:-1]
        new = [""]
        for body in moves[slug]:
            new += body + [""]
        new[-2] += ")"
        lines[e + 1:e + 1] = new[:-1]
    return "\n".join(lines)


_ARC_TOKEN = re.compile(r"[&$]?[A-Za-z_][\w]*(?:\.[\w]+)*")
_ALTS_CONCEPT = re.compile(r'\(ALTS \$\w+ "(?:[^"\\]|\\.)*" \$(\w+)')
"""The constructor an `ALTS` form gives as its concept alt."""


def _souffle_relation(c: "Converter", w: Written) -> dict:
    """The Souffle relation, or instance, `w`: the component path, its name
    there, and its name from the top level of the solver's program, null
    where no instance at the top level is of the scope's component."""
    path: str | None = w.relation
    if w.scope:
        at = [n for (sc, n), i in c.insts.items() if sc == () and i.component == w.scope[-1]]
        path = f"{at[0]}.{w.relation}" if len(w.scope) == 1 and len(at) == 1 else None
    return {"component": list(w.scope), "relation": w.relation, "path": path}


def _renamed_name(name: str, insts: dict[str, str]) -> str:
    """The arclog name `name` the converter writes, as the renames
    `convert_one` applies after it leave it: `renamed`, then
    `libmap_rename.rename` with `insts`."""
    return libmap_rename.rename(renamed(f"({name})"), insts)[1:-1]


def _relations_read(text: str) -> set[str]:
    """Each name the arclog or arcdata `text` reads as a relation or an
    instance: a name with `&` outside a quoted text, and the head of a
    form."""
    from arclog_convert.lint import L, Sym, read
    out: set[str] = set()

    def scan(xs: list) -> None:
        for x in xs:
            if not isinstance(x, L):
                continue
            for i, it in enumerate(x.items):
                if isinstance(it, Sym):
                    t = it.text.lstrip("^*")
                    if _ARC_TOKEN.fullmatch(t) and (t.startswith("&") or i == 0):
                        out.add(t)
            scan(x.items)
    scan(read(text))
    return out


def name_map(s: "Solver", insts: dict[str, str], arclog: str, arcdata: str) -> dict:
    """Each arclog relation name the written files read, with each Souffle
    relation it was written from, in the order the pass wrote them; each
    instance they read, with each Souffle instance; each `ALT` name, with the Souffle `Choice` constructor; and
    each arclog name with `&` the files read that the renames of this pass
    give no Souffle relation, under `unmapped`. Each name is the one the
    converter recorded as it wrote it (`Converter.wrote`), or a top-level
    lib relation it writes under its own name that the solver declares no
    relation of, under the renames
    `convert_one` applies after it (`_renamed_name`)."""
    c = s.c
    named = dict(c.written)
    for own in (*sorted(FACTS), *c.lib.top, *c.sig.top):
        if ((), own) not in c.rels:   # else the Souffle name is the solver's own relation
            named.setdefault(own, [Written((), own, False)])
    rels: dict[str, list[dict]] = {}
    instances: dict[str, list[dict]] = {}
    for arc, ws in named.items():
        for w in ws:
            got = (instances if w.instance else rels).setdefault(_renamed_name(arc, insts), [])
            if (r := _souffle_relation(c, w)) not in got:
                got.append(r)
    read = _relations_read(arclog + "\n" + arcdata)
    relations = {n: rels[n] for n in sorted(read) if n in rels}
    ctors = {f"${m}": m for m in sorted(set(re.findall(r"\(ALT \$(\w+)", arclog))
                                        | set(_ALTS_CONCEPT.findall(arclog)))}
    insts_read = {n: instances[n] for n in sorted(read) if n in instances}
    unmapped = sorted(n for n in read if n.startswith("&") and n not in relations
                      and n not in insts_read)
    return {"relations": relations, "instances": insts_read, "constructors": ctors,
            "unmapped": unmapped}


def convert_one(stem: str) -> tuple[str, str | None, str | None, Counter, Counter, list[str], ColMismatch, str | None]:
    """One solver's arclog and arcdata, its TODO kinds, its merge counts and
    its parameters whose columns do not map onto their proposer's, or the
    error that stopped it: a pool worker's unit of work."""
    global _LIBS, fix_labels
    if _LIBS is None:
        from arclog_convert.lint import fix_labels
        lib, sig = Lib(LIB_DL), Lib(SIGNATURE)
        lib.extend(sig)
        _LIBS = lib, sig
    lib, sig = _LIBS
    MERGES.clear()
    MERGES_UNMERGED.clear()
    todo = Todo()
    try:
        s = Solver(stem, lib, sig, todo)
        arclog, arcdata = s.run()
        # an `inline` helper whose body no order makes safe is no relation: its
        # body stands at each call
        stuck = frozenset(r.name for r in s.c.prog.relations if Qualifier.INLINE in r.qualifiers) & s.c.unsafe
        if stuck:
            MERGES.clear()
            MERGES_UNMERGED.clear()
            todo = Todo()
            s = Solver(stem, lib, sig, todo, stuck)
            arclog, arcdata = s.run()
        arclog = drop_key_sites(fold_or_lines(renamed(arclog)))
        insts = libmap_rename.renamed_instances(libmap_rename.instances(arclog),
                                                libmap_rename.reads(arclog + arcdata))
        arclog = hoist_shared(fix_labels(libmap_rename.rename(arclog, insts)))
        arcdata = libmap_rename.rename(arcdata, insts)
        if MACROS_ENV not in os.environ:
            NAMES_DIR.mkdir(parents=True, exist_ok=True)
            (NAMES_DIR / f"{stem}.json").write_text(
                json.dumps(name_map(s, insts, arclog, arcdata), indent=1, sort_keys=True) + "\n")
    except Exception as e:  # noqa: BLE001
        return stem, None, None, Counter(), Counter(), [], {}, f"{type(e).__name__}: {e}"
    return stem, arclog, arcdata, todo.kinds, Counter(MERGES), list(MERGES_UNMERGED), s.c.col_mismatch, None


def main(argv: list[str]) -> None:
    global OUT_DIR, MACROS_DIR, PLANS, NAMES_DIR
    import argparse
    parser = argparse.ArgumentParser(prog="python -m arclog_convert.convert")
    parser.add_argument("--out", type=Path, help="the directory to write under, in place of `arclog_out`")
    parser.add_argument("stems", nargs="*", help="the solvers to convert; every solver where none is given")
    args = parser.parse_args(argv)
    if args.out is not None:
        # set before the pools start, so that their workers read it
        os.environ[OUT_ENV] = str(args.out.resolve())
        OUT_DIR, MACROS_DIR, PLANS, NAMES_DIR = out_dirs()
    stems = args.stems or sorted(p.stem for p in SOLVERS.glob("*.dl"))
    refresh_plans(stems)
    print(f"{OUT_DIR}:")
    convert_into(stems, OUT_DIR)
    # set before the second pool starts, so that its workers read it
    os.environ[MACROS_ENV] = "1"
    print(f"{MACROS_DIR}:")
    convert_into(stems, MACROS_DIR)


def convert_into(stems: list[str], out: Path) -> None:
    """Convert `stems` into `out` over a process pool, and print the
    summary."""
    from concurrent.futures import ProcessPoolExecutor
    out.mkdir(parents=True, exist_ok=True)
    total = Counter()
    per_kind_solvers = Counter()
    merges: Counter[str] = Counter()
    unmerged: list[str] = []
    mismatched: list[tuple[str, str, list[Col], list[Col]]] = []
    failed = []
    clean = 0
    workers = min(len(stems), os.cpu_count() or 4)
    if workers > 1:
        pool = ProcessPoolExecutor(workers)
        # the largest solvers first, so that no long one starts last
        order = sorted(stems, key=lambda t: -(SOLVERS / f"{t}.dl").stat().st_size)
        results = pool.map(convert_one, order)
    else:
        pool, results = None, map(convert_one, stems)
    for stem, arclog, arcdata, kinds, m, um, mis, err in results:
        if err is not None:
            failed.append((stem, err))
            continue
        (out / f"{stem}.arclog").write_text(arclog)
        (out / f"{stem}.arcdata").write_text(arcdata)
        merges += m
        unmerged += um
        mismatched += [(stem, name, own, prop) for name, (own, prop) in mis.items()]
        total += kinds
        for k in kinds:
            per_kind_solvers[k] += 1
        if not kinds:
            clean += 1
    if pool is not None:
        pool.shutdown()
    print(f"converted {len(stems) - len(failed)} of {len(stems)}; {clean} with no TODO")
    print(f"merged {merges['relation']} relations and {merges['input']} inputs; "
          f"unmerged {merges['unmerged']} relations ({', '.join(sorted(set(unmerged)))}) "
          f"and {merges['input-unmerged']} inputs")
    if mismatched:
        print(f"{len(mismatched)} parameters keep their own columns, which do not map onto those of the proposer or the derivation their DET names:")
        for stem, name, own, prop in sorted(mismatched, key=lambda u: u[:2]):
            print(f"  {stem} {name}: ({', '.join(f'{c.name} {c.type}' for c in own)}) "
                  f"onto ({', '.join(f'{c.name} {c.type}' for c in prop)})")
    for k, n in total.most_common():
        print(f"  {k:20} {n:6} in {per_kind_solvers[k]} solvers")
    if failed:
        print(f"failed {len(failed)}:")
        for stem, err in failed[:30]:
            print(f"  {stem}: {err}")
        errs = Counter(e.split(":")[0] + ":" + e.split(":")[1][:60] for _, e in failed)
        for e, n in errs.most_common(10):
            print(f"  {n:4} {e}")

if __name__ == "__main__":
    main(sys.argv[1:])
