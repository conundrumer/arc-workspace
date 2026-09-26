"""Program relations that hold one value on every input: the branches a
stored value states.

A relation between `in` and `out` whose projection onto some of its columns
is the same on every input of the task, train and test, states a model that
stores that value rather than reading it off the grid. That model's reading
is a branch of a choice point on the relation: the solver carries one
`// @store` line above the relation's declaration, and no constructor.

The witness tells the cases that take the branch from the same cases with
the relation derived. The tool builds one by turning or mirroring a train
input, or by swapping a stored color with a free one: the derivation
follows the grid, the stored value does not. The witness's id is the
branch's name, `<rel>=stored`; an entry of that id in the witness file is
kept, and a relation no such grid separates takes one built by hand.

A `@store` line is a branch `<rel>=stored` of a choice point on the
relation, which stands under each held case that reads the relation and
takes a value found for it (`value_cases`); `dl.models.enumeration` holds
the cases that take it. `stored_program` gives the program a case with one
or more store branches runs.
"""

import itertools
import random
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from arc.task import load as load_task
from controlled_markdown import mctx
from dl.annotations import (
    DECL_RE,
    INIT_RE,
    STORE,
    STORED,
    Store,
    ignore_lines,
    store_blocks,
    store_relation,
)
from dl.derived_constant import (
    SKIP,
    _build,
    _controls,
    _edges,
    _index as _merged_index,
    _instances,
    _reachable,
    _tuple_sets,
)
from dl.determination_plan import fact_params
from dl.dlparse import (
    TOP,
    Comp,
    Ctor,
    Decl,
    Field,
    Index,
    ParseError,
    TypeDecl,
    marker_cases,
    parse,
)
from dl.domains import _lib_defines
from dl.facts import grid_to_facts
from dl.lint import _subterms, choice_points
from dl.models import CaseId, Cases, Space, case_space, enumeration, held_choice
from dl.solve import (
    TASK_ID_RE,
    parse_output,
    res_out_stem,
    run_dl_source,
    solver_file,
)
from dl.souffle import _pool_workers, _run_source
from dl.source import (
    SOLVE_DIRECTIVES,
    assigned_source,
    comp_decls,
    expand_macros,
    with_line_above,
)
from dl.witness import (
    Witness,
    assign_findings,
    branch_diverges,
    concept_outcome,
    drop_findings,
    load_witness_file,
    load_witnesses,
    model_outcomes,
)

STORE_OK = "store: ok"
"""The pass line, printed when no finding stands."""

SHARED = "shared"
"""The case label of a finding that holds one value for every case."""

OTHER = "other"
"""The verdict that takes a judged output, which only an entry holds."""

POS_TYPES = frozenset({"Position", "Box"})
"""Types whose value is a cell of the frame."""

OFFSET_TYPE = "Offset"

COLOR_TYPE = "Color"

UNIT_TYPE = "Unit"

IDENT_TYPE = "Ident"

NO_COLUMN_TYPES = frozenset({UNIT_TYPE, IDENT_TYPE})
"""Types that label a row rather than hold a value. A column of one of
these, and a case column, is no column of the value the report names."""

FULL = {"Dir": 4, "Axis": 2, "DiagDir": 4, "DiagAxis": 2, "D4": 8, "C4": 4,
        "Sym": 10, "Sense": 2, "Dir8": 8, "Axis4": 4}
"""Each orientation type and how many elements it holds. A column that
ranges over all of them states the type, not a value."""

DATA_TYPES = POS_TYPES | {OFFSET_TYPE, "number", COLOR_TYPE} | set(FULL)
"""The column types a stored value can hold."""

MAX_COLS = 6
"""Relations wider than this take too many column subsets to test."""

ROW_CAP = 20000
"""Rows above which a relation is not checked. The cap stands well past the
largest stored picture of the corpus, so a relation over it is a structure
over the frame, not a value a solver would store."""

SWAP_SEED = 11

SHOWN_MEMBERS = 8
"""How many members of a value that draws no picture the report spells out.
A larger value goes under its member count."""

DRAW_CAP = 30
"""How far a picture reaches along each axis. A value whose cells spread
further goes under its member count."""

OWNED = "owned"
CONSTANT = "constant"
TRANSLATED = "translated"

# The D4 elements, each named as the report names it.
D4_NAMES = {
    "CW": "turned a quarter turn clockwise",
    "HT": "turned a half turn",
    "CC": "turned a quarter turn counterclockwise",
    "LR": "mirrored left-right",
    "TB": "mirrored top-bottom",
    "DG": "mirrored across the main diagonal",
    "AD": "mirrored across the anti-diagonal",
}

@lru_cache(maxsize=1)
def _orientation() -> tuple[dict[str, str], list[frozenset[str]]]:
    """Each orientation value under the lib's name for it, and the whole
    value set of each orientation type. The lib numbers the types apart, so
    a value names one element of one type."""
    names: dict[str, str] = {}
    groups: dict[str, set[str]] = {}
    for name, value in _lib_defines().items():
        prefix = name.split("_")[0]
        if prefix not in _ORIENTATION_PREFIXES:
            continue
        names[str(value)] = name
        groups.setdefault(prefix, set()).add(str(value))
    return names, [frozenset(g) for g in groups.values()]


_ORIENTATION_PREFIXES = frozenset(
    {"DIR", "AXIS", "DIAG", "DAXIS", "D4", "SENSE", "SYM"})


TWIN = "_store_twin"
VALUES = "_store_values"


@dataclass
class Move:
    """The grid on which a relation's value differs: the train input it
    comes from, and the transformation that made it. `identity` says the
    concept case gives that grid unchanged, and `input` is the grid."""

    grid: str
    change: str
    identity: bool = False
    input: list[list[int]] | None = None


@dataclass
class Found:
    """One column subset of one relation whose projected value repeats.

    `rel` is the relation's path, `cols` the names of the columns the value
    lives in, `sub` whether those are fewer than the relation's columns,
    and `keys` the names of the other columns. `kind` is `owned` for one
    value on every input, `constant` for one family of values, and
    `translated` for one value once each set is shifted to its own corner.
    `ref` is that value, as the run prints it.
    """

    rel: str
    cols: list[str]
    keys: list[str]
    types: list[str]
    sub: bool
    kind: str
    case: str
    concept: bool
    read: bool
    ref: frozenset
    rect: str = ""
    line: Store | None = None
    entry: str = ""
    move: Move | None = None
    facts: tuple = ()
    """The relation's whole rows, where no key column stands. The stored
    case puts these in place of the clauses that derive the relation."""
    used_in: str = ""
    """The cases whose markers hold the reads and the feeds."""
    under: list[str] = field(default_factory=list)
    """The relations that fold under this one, downstream of it."""
    folded: bool = False
    """The relation stands downstream of another the report names, so that
    one answers for it."""
    failed: str = ""
    """The error of the stored case's first run that failed."""
    site: str = ""
    """The instance whose `.init` a directive on the relation stands above,
    and empty where it stands above the relation's own `.decl`."""
    spelled: str = ""
    """The relation as its `@store` line names it: the instance joined to
    the named relation, or the declared name."""

    @property
    def case_id(self) -> CaseId:
        return CaseId(f"{self.spelled or self.rel}={STORED}")

    @property
    def colors(self) -> bool:
        return bool(self.types) and all(t == COLOR_TYPE for t in self.types)

    @property
    def held(self) -> bool:
        """Some case reads the relation: the concept case, or a case under
        the markers of its reads and feeds."""
        return self.read or bool(self.used_in)


@dataclass
class Finding:
    """One finding of the store report: where it stands, and what it
    says."""

    where: str
    text: str


@dataclass
class Report:
    found: list[Found] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    """Relations over `ROW_CAP` rows on some input, which the report does
    not check."""
    findings: list[Finding] = field(default_factory=list)
    error: str = ""


# --- candidates -------------------------------------------------------

def _index(source: str) -> Index:
    """The solver's index with the lib merged in, each rule under the
    section marker the solver's own text gives it. The lib's lines number
    another file, so a lib rule stands under no marker, and a lib comp's
    span hides no marker of the solver."""
    ix = _merged_index(source)
    own = Index(parse(source)).rules
    for i, info in enumerate(ix.rules):
        info.section = own[i].section if i < len(own) else None
    return ix


def _solver_scopes(source: str) -> set[str]:
    """The top level and the comps the solver declares as program code."""
    return {TOP} | {c for c in parse(source).comps()
                    if c not in ("Params", "Determine", "ParamsHelpers")}


def _candidates(ix: Index, scopes: set[str]
                ) -> dict[str, tuple[tuple[str, str], Decl]]:
    """Path -> (key, decl) for the relations between `in` and `out` that a
    clause of a solver scope reads or writes."""
    forward, backward = _edges(ix)
    wanted = (_reachable(forward, (TOP, "in"))
              & _reachable(backward, (TOP, "out")))
    out: dict[str, tuple[tuple[str, str], Decl]] = {}

    def add(name: str, key: tuple[str, str], decl: Decl) -> None:
        if key not in wanted or "inline" in decl.qualifiers or name in out:
            return
        if not any(r.scope in scopes for r in ix.refs_of(key)):
            return
        out[name] = (key, decl)

    for name, decl in ix.decls.get(TOP, {}).items():
        if name not in SKIP:
            add(name, (TOP, name), decl)
    for path, comp in _instances(ix):
        for scope in ix.chain(comp):
            for name, decl in ix.decls.get(scope, {}).items():
                add(f"{path}.{name}", (scope, name), decl)
    return out


def _site(ix: Index, rel: str, own: set[str]) -> tuple[str, str]:
    """The instance whose `.init` a directive on the relation stands above,
    and the relation as that directive names it. The instance is the
    innermost one on the relation's path that the solver's own text
    initializes, and empty where the solver's own text declares the
    relation, which the directive then names by its declared name."""
    parts = rel.split(".")
    scope, at = TOP, -1
    for i, inst in enumerate(parts[:-1]):
        holder = next((s for s in ix.chain(scope)
                       if inst in ix.inits.get(s, {})), None)
        if holder is None:
            break
        if holder in own:
            at = i
        scope = ix.inits[holder][inst].comp
    else:
        if any(s in own for s in ix.chain(scope)
               if parts[-1] in ix.decls.get(s, {})):
            return "", parts[-1]
    if at < 0:
        return "", rel
    return parts[at], ".".join(parts[at:])


def relation_site(source: str, spelled: str) -> str:
    """The site (`_site`) of the relation a `@store` line spells `spelled`
    (`Found.spelled`), and empty where no relation of the solver is spelled
    so."""
    expanded = expand_macros(source)
    try:
        ix = _index(expanded)
        own = {TOP} | set(parse(expanded).comps())
    except ParseError:
        return ""
    for rel, _key in _relation_keys(ix):
        site, named = _site(ix, rel, own)
        if named == spelled:
            return site
    return ""


def _uses(ix: Index, key: tuple, scopes: set[str], branches: set[str],
          concept: set[str]) -> tuple[bool, set[str]]:
    """Whether the concept case reads or feeds the relation, and the cases
    whose markers hold the uses. A feed counts: an instance's input is what
    the program puts into it. A clause under no marker runs on every case,
    so the concept case runs it."""
    cases: set[str] = set()
    by_concept = False
    for r in ix.refs_of(key):
        if r.scope not in scopes:
            continue
        section = ix.rules[r.rule].section
        marked = ({c.lstrip("$") for c in marker_cases(section)} & branches
                  if section else set())
        cases |= marked
        if not marked or marked & concept:
            by_concept = True
    return by_concept, cases


# --- cases ------------------------------------------------------------

def _case_types(ix: Index) -> set[str]:
    """`Choice` and every other ADT the program declares, bar the tiebreak
    resolution and the unit key. A column of one of these types carries the
    case."""
    out = {"Choice"}
    for it in ix.program.items:
        if (isinstance(it, TypeDecl) and it.branches
                and it.name not in ("TiebreakResolution", UNIT_TYPE)):
            out.add(it.name)
    return out


def _branch_names(source: str, ix: Index,
                  casetypes: set[str]) -> tuple[set[str], set[str], list]:
    """Every branch name, the concept branch names, and the branches of
    each choice type. A type declares its concept branch first."""
    every: set[str] = set()
    concept: set[str] = set()
    universes: list[frozenset[str]] = []
    for point in choice_points(source):
        for b in point.branches:
            every.add(b.name)
            if b.is_concept:
                concept.add(b.name)
    for it in ix.program.items:
        if not (isinstance(it, TypeDecl) and it.name in casetypes
                and it.branches):
            continue
        universes.append(frozenset(it.branches))
        every |= set(it.branches)
        concept.add(it.branches[0])
    return every, concept, universes


def _section_cases(ix: Index, key: tuple, branches: set[str]) -> set[str]:
    """The cases the section markers of the defining clauses name."""
    out: set[str] = set()
    for r in ix.refs_of(key):
        if r.scope != TOP or r.role != "head":
            continue
        section = ix.rules[r.rule].section
        if section:
            out |= {c.lstrip("$") for c in marker_cases(section)} & branches
    return out


def _ctor_names(value: str) -> set[str]:
    """The constructor names a printed case value holds: `$A` gives `A`,
    and `[$A, $B(1)]` gives `A` and `B`."""
    out = set()
    flat = value.replace("[", " ").replace("]", " ").replace(",", " ")
    for part in flat.split():
        if part.startswith("$"):
            out.add(part[1:].split("(", 1)[0])
    return out


def _spread(family: frozenset, subset: tuple, types: list[str]) -> bool:
    """Whether every set of the family holds two cells or more. One cell is
    the same up to translation whatever the other columns hold."""
    cells = [j for j, i in enumerate(subset) if types[i] in POS_TYPES]
    return all(len({tuple(m[j] for j in cells) for m in g}) >= 2
               for g in family)


def _full_set(family: frozenset) -> bool:
    """Whether every set of the family is the whole element set of one
    orientation type. Such a column states the type, not a value."""
    groups = _orientation()[1]
    return all(any(frozenset(m[0] for m in g) == whole for whole in groups)
               for g in family)


def _split_cases(rows: list[list[str]],
                 case_cols: list[int]) -> dict[str, list[list[str]]]:
    """The rows per case value, under one empty key where no column carries
    the case."""
    if not case_cols:
        return {"": rows}
    out: dict[str, list[list[str]]] = {}
    for row in rows:
        out.setdefault(", ".join(row[i] for i in case_cols), []).append(row)
    return out


# --- families ---------------------------------------------------------

def _point(text: str) -> tuple[int, int]:
    """The top and the left of a printed Box record."""
    t, _b, l, _r = (int(x) for x in text[1:-1].split(","))
    return t, l


def _normalize(members: set[tuple], pos_idx: list[int]) -> frozenset:
    """One set with its cells shifted to its own corner."""
    ps = [_point(m[j]) for m in members for j in pos_idx]
    t0 = min(p[0] for p in ps)
    l0 = min(p[1] for p in ps)
    return frozenset(
        tuple((_point(x)[0] - t0, _point(x)[1] - l0) if j in pos_idx else x
              for j, x in enumerate(m))
        for m in members)


def _families(rows: list[list[str]], types: list[str], cols: list[int],
              subsets=None) -> dict:
    """Subset -> (family, translated family). A family holds one projection
    per value of the other columns."""
    n = len(types)
    if subsets is None:
        subsets = [s for k in range(1, len(cols) + 1)
                   for s in itertools.combinations(cols, k)]
    out = {}
    for s in subsets:
        rest = [i for i in range(n) if i not in s]
        groups: dict[tuple, set] = {}
        for row in rows:
            groups.setdefault(tuple(row[i] for i in rest), set()).add(
                tuple(row[i] for i in s))
        fam = frozenset(frozenset(g) for g in groups.values())
        pos_idx = [j for j, i in enumerate(s) if types[i] in POS_TYPES]
        tfam = (frozenset(_normalize(g, pos_idx) for g in groups.values())
                if pos_idx else None)
        out[s] = (fam, tfam)
    return out


def _analyze(per_grid: list[dict], names: list[str], cands: dict,
             casetypes: set[str], resolved: dict[str, list[str]],
             skipped: list[str]) -> dict:
    """(path, case) -> (types, {subset: kind}, families of the first
    input)."""
    found: dict = {}
    for name in names:
        types = resolved[name]
        if not types or len(types) > MAX_COLS:
            continue
        if any(not g[name] for g in per_grid):
            continue
        rows_per = [[r.split("\t") for r in g[name]] for g in per_grid]
        if max(len(r) for r in rows_per) > ROW_CAP:
            skipped.append(name)
            continue
        case_cols = [i for i in range(len(types)) if types[i] in casetypes]
        by_case = [_split_cases(rows, case_cols) for rows in rows_per]
        cases = set(by_case[0])
        if any(set(b) != cases for b in by_case):
            continue
        data_cols = [i for i in range(len(types)) if types[i] in DATA_TYPES]
        for case in sorted(cases):
            crow = [b[case] for b in by_case]
            # A subset is the same on every input only when each of its
            # columns holds the same values on every input. A cell column
            # may still enter a translated subset.
            colsets = [[{r[i] for r in rows} for i in range(len(types))]
                       for rows in crow]
            cols = [i for i in data_cols
                    if all(cs[i] == colsets[0][i] for cs in colsets)
                    or types[i] in POS_TYPES]
            if not cols:
                continue
            fams = [_families(rows, types, cols) for rows in crow]
            hits: dict[tuple, str] = {}
            for s in fams[0]:
                fam0, tfam0 = fams[0][s]
                if len(s) == 1 and types[s[0]] in FULL and _full_set(fam0):
                    continue
                if all(f[s][0] == fam0 for f in fams):
                    hits[s] = OWNED if len(fam0) == 1 else CONSTANT
                elif (tfam0 is not None and _spread(tfam0, s, types)
                      and all(f[s][1] == tfam0 for f in fams)):
                    hits[s] = TRANSLATED
            keep = {
                s: k for s, k in hits.items()
                if not any(set(s) < set(s2)
                           and hits[s2] in (k, OWNED)
                           for s2 in hits)
            }
            if keep:
                found[(name, case)] = (types, keep, fams[0], crow[0])
    return found


# --- filters ----------------------------------------------------------

def _rect(points: set[tuple[int, int]]) -> str:
    """`HxW` when the cells fill their bounding rectangle, and empty
    otherwise."""
    if not points:
        return ""
    ts = [p[0] for p in points]
    ls = [p[1] for p in points]
    h, w = max(ts) - min(ts) + 1, max(ls) - min(ls) + 1
    return f"{h}x{w}" if h * w == len(points) else ""


def _is_frame(rect: str, grids: list[list[list[int]]]) -> bool:
    """Whether a filled rectangle covers the whole extent of every input."""
    height, width = (int(x) for x in rect.split("x"))
    return all(len(g) == height and len(g[0]) == width for g in grids)


def _value(text: str):
    if text.startswith("["):
        return tuple(int(x) for x in text[1:-1].split(","))
    return int(text) if text.lstrip("-").isdigit() else text


def _stored_sets(source: str, defines: dict[str, int]) -> dict:
    """Each stored fact parameter's value, exact and shifted to its own
    corner."""
    out = {}
    for param, (types, stored) in fact_params(source, defines).items():
        pos_idx = [i for i, t in enumerate(types) if t in POS_TYPES]
        trans = None
        if pos_idx and stored:
            t0 = min(row[i][0] for row in stored for i in pos_idx)
            l0 = min(row[i][2] for row in stored for i in pos_idx)
            trans = frozenset(
                tuple((v[0] - t0, v[2] - l0) if i in pos_idx else v
                      for i, v in enumerate(row))
                for row in stored)
        out[param] = (frozenset(stored), trans)
    return out


def _restates(kind: str, ref: frozenset, stored: dict) -> bool:
    """Whether the one set the finding holds is a stored parameter's
    value."""
    if len(ref) != 1:
        return False
    members = next(iter(ref))
    if kind == TRANSLATED:
        value = frozenset(
            tuple(_value(x) if isinstance(x, str) else x for x in m)
            for m in members)
        return any(trans is not None and trans == value
                   for _exact, trans in stored.values())
    value = frozenset(tuple(_value(x) for x in m) for m in members)
    return any(exact == value for exact, _trans in stored.values())


# --- grids ------------------------------------------------------------

def _count_source(source: str, cands: dict,
                  names: list[str]) -> tuple[str, dict[str, str]]:
    """The solve-mode program whose outputs are one row count per relation,
    and the count relation's name per relation.

    The counts and the tuples come from the same expanded source, so a count
    names the rows the base run would print.
    """
    parts: list[str] = []
    of_count: dict[str, str] = {}
    for i, name in enumerate(names):
        arity = len(cands[name][1].fields)
        if not arity:
            continue
        cname = f"_store_n{i}"
        of_count[cname] = name
        args = ", ".join("_" for _ in range(arity))
        parts.append(f".decl {cname}(n: number)\n"
                     f"{cname}(N) :- N = count : {{ {name}({args}) }}.\n"
                     f".output {cname}(IO=stdout)\n")
    return (f"{expand_macros(source)}\n{SOLVE_DIRECTIVES}" + "".join(parts),
            of_count)


def _d4_images(grid: list[list[int]]) -> dict[str, list[list[int]]]:
    """The seven other images of a grid under D4."""
    h, w = len(grid), len(grid[0])
    rot = [[grid[h - 1 - r][c] for r in range(h)] for c in range(w)]

    def lr(g):
        return [row[::-1] for row in g]

    def tb(g):
        return g[::-1]

    def tr(g):
        return [list(x) for x in zip(*g)]

    return {"CW": rot, "HT": tb(lr(grid)), "CC": tb(lr(rot)),
            "LR": lr(grid), "TB": tb(grid), "DG": tr(grid),
            "AD": tb(lr(tr(grid)))}


def _swap_grid(grid: list[list[int]], a: int, b: int) -> list[list[int]]:
    return [[b if c == a else a if c == b else c for c in row]
            for row in grid]


def _swaps(grids: list[list[list[int]]],
           held: set[int]) -> list[tuple[str, str, list[list[int]]]]:
    """One color swap per train input: a stored color the grid holds
    against a color no grid holds."""
    rng = random.Random(SWAP_SEED)
    out = []
    for i, grid in enumerate(grids):
        used = {c for row in grid for c in row}
        stored = sorted(held & used)
        free = [c for c in range(10) if c not in used | held]
        if not stored or not free:
            continue
        a = stored[0]
        b = free[rng.randrange(len(free))]
        out.append((f"train {i}",
                    mctx("with {a} and {b} swapped").format(a=a, b=b),
                    _swap_grid(grid, a, b)))
    return out


# --- the stored case --------------------------------------------------

def _paths(ix: Index) -> dict[str, list[str]]:
    """Each scope's instance paths, the top level's the empty path."""
    out: dict[str, list[str]] = {TOP: [""]}
    for path, comp in _instances(ix):
        out.setdefault(comp, []).append(path)
    return out


def _rule_refs(expanded: str, ix: Index, rel: str, roles: set[str],
               skip_shared: bool = False) -> list[tuple[int, str]] | None:
    """The rules of the solver's own text that reference the relation in
    one of `roles`, each as its index and the name it spells the relation
    by. None when a rule of the lib does, or a rule in a comp of more than
    one instance: an edit to its text would reach every instance. With
    `skip_shared`, such a rule is left out, and the others are returned."""
    own = len(Index(parse(expanded)).rules)
    paths = _paths(ix)
    out: list[tuple[int, str]] = []
    for r in ix.refs:
        if r.role not in roles:
            continue
        spelled = ".".join(x for x in (r.atom.qual or "", r.atom.name) if x)
        held = paths.get(r.scope, [])
        if not any(".".join(x for x in (p, spelled) if x) == rel
                   for p in held):
            continue
        if r.rule >= own or len(held) > 1:
            if skip_shared:
                continue
            return None
        out.append((r.rule, spelled))
    return out


def _rename(expanded: str, ix: Index, hits: list[tuple[int, str]],
            twin: str, body_only: bool) -> str:
    """The source with each rule of `hits` spelling `twin` where it spells
    the relation: in its body alone with `body_only`, and in its head and
    body otherwise."""
    lines = expanded.splitlines()
    for idx, spelled in sorted(set(hits)):
        rule = ix.rules[idx].rule
        pattern = re.compile(r"(?<![\w.])" + re.escape(spelled) + r"\s*\(")
        in_body = not body_only
        for i in range(rule.line - 1, min(rule.end_line, len(lines))):
            code, sep, comment = lines[i].partition("//")
            if in_body:
                code = pattern.sub(twin + "(", code)
            elif ":-" in code:
                head, arrow, body = code.partition(":-")
                code = head + arrow + pattern.sub(twin + "(", body)
                in_body = True
            lines[i] = code + sep + comment
    return "\n".join(lines) + "\n"


def _rename_reads(expanded: str, ix: Index, rel: str, twin: str) -> str:
    """The source with the solver's clause bodies reading `twin` where they
    read `rel`, a comp's clauses included. The lib's rules, and those of a
    comp of more than one instance, keep reading `rel`."""
    hits = _rule_refs(expanded, ix, rel, {"pos", "neg", "agg"},
                      skip_shared=True) or []
    return _rename(expanded, ix, hits, twin, body_only=True)


def _comp_params(ix: Index) -> dict[str, list[str]]:
    """Each comp's type parameters, by comp name."""
    out: dict[str, list[str]] = {}

    def walk(items) -> None:
        for it in items:
            if isinstance(it, Comp):
                out[it.name] = it.params
                walk(it.items)

    walk(ix.program.items)
    return out


def _type_args(ix: Index, path: str) -> dict[str, str]:
    """The type each parameter of the instance's comp stands for, read down
    the instance path."""
    params = _comp_params(ix)
    scope = TOP
    subst: dict[str, str] = {}
    for part in path.split("."):
        scopes = [TOP] if scope == TOP else list(ix.chain(scope))
        init = next((i for s in scopes
                     if (i := ix.inits.get(s, {}).get(part)) is not None),
                    None)
        if init is None:
            return subst
        args = [subst.get(a, a) for a in init.targs]
        subst = dict(zip(params.get(init.comp, []), args))
        scope = init.comp
    return subst


def _twin_text(rel: str, decl, cols: list[int], ref: frozenset,
               subst: dict[str, str], fed: bool = False,
               n: int = 0) -> str:
    """The twin relation: the keys of the derivation against the stored
    value set. With `fed`, the twin holds the derivation instead, and the
    relation takes the twin's keys against the stored value set."""

    def type_of(f: Field) -> str:
        return subst.get(f.type, f.type)

    fields = ", ".join(f"{f.name}: {type_of(f)}" for f in decl.fields)
    values = sorted(next(iter(ref)))
    value_fields = ", ".join(
        f"{decl.fields[i].name}: {type_of(decl.fields[i])}" for i in cols)
    head, body = [], []
    for i in range(len(decl.fields)):
        if i in cols:
            head.append(f"V{i}")
            body.append("_")
        else:
            head.append(f"K{i}")
            body.append(f"K{i}")
    take = ", ".join(f"V{i}" for i in cols)
    twin, stored = _twin(TWIN, n), _twin(VALUES, n)
    facts = "".join(f"{stored}({', '.join(row)}).\n" for row in values)
    into, source = (rel, twin) if fed else (twin, rel)
    return (f"\n.decl {stored}({value_fields})\n{facts}"
            f".decl {twin}({fields})\n"
            f"{into}({', '.join(head)}) :- "
            f"{source}({', '.join(body)}), {stored}({take}).\n")


def _fact_arg(text: str) -> str:
    """One printed argument as a fact writes it. The runner prints a
    constructor without its parentheses."""
    return f"{text}()" if text.startswith("$") and "(" not in text else text


def _stored_facts(rel: str, facts: tuple) -> str:
    """The relation's rows as facts, under the instance path."""
    return "".join(
        f"{rel}({', '.join(_fact_arg(a) for a in row)}).\n" for row in facts)


def _head_rules(expanded: str, ix: Index, rel: str) -> list | None:
    """The rules of the solver's own text whose head is the relation, each
    as its first and last line. None when a rule of the lib feeds it: the
    lib's line numbers count lines of another file."""
    hits = _rule_refs(expanded, ix, rel, {"head"})
    if hits is None:
        return None
    return [(ix.rules[i].rule.line, ix.rules[i].rule.end_line)
            for i, _spelled in hits]


def _feed_rules(expanded: str, ix: Index, rel: str) -> list | None:
    """The rules of the solver's own text that feed the relation, each as
    its index and the name it spells the relation by. None when a rule of
    the lib feeds it, or no rule does."""
    return _rule_refs(expanded, ix, rel, {"head"}) or None


def _replace_clauses(expanded: str, spans: list, found: Found) -> str:
    """The program with the clauses in `spans`, the ones that derive the
    relation, taken out and the stored facts put in their place."""
    lines = expanded.splitlines()
    for start, end in spans:
        for i in range(start - 1, min(end, len(lines))):
            lines[i] = ""
    return ("\n".join(lines) + "\n"
            + _stored_facts(found.rel, found.facts))


def _twin(name: str, n: int) -> str:
    """The name of a relation a stored program adds, for its `n`-th store
    branch."""
    return name if n == 0 else f"{name}_{n}"


def _twin_facts(found: Found, decl, subst: dict[str, str],
                n: int = 0) -> str:
    """The twin relation holding the stored facts."""
    fields = ", ".join(f"{f.name}: {subst.get(f.type, f.type)}"
                       for f in decl.fields)
    twin = _twin(TWIN, n)
    return f"\n.decl {twin}({fields})\n" + _stored_facts(twin, found.facts)


def store_case_program(expanded: str, ix: Index, found: Found, decl,
                       subst: dict[str, str], n: int = 0) -> str:
    """The program with one relation's value stored, for the `n`-th store
    branch a case takes, without the solve directives. A relation with no
    key column takes the stored facts in place of its clauses, and where a
    lib rule feeds it, the solver's reads read a twin that holds the stored
    facts. One with key columns keeps its keys and takes its values from
    the stored set.

    Where the solver's own rules feed the relation, those rules derive the
    twin instead, and the relation takes the twin's keys against the stored
    set, so every reader, a lib comp's included, reads the stored values.
    Otherwise the solver's reads read the twin, which takes the relation's
    keys against the stored set. A solver's read or feed counts at the top
    level and in a comp of one instance."""
    if not found.keys:
        spans = _head_rules(expanded, ix, found.rel)
        if spans is not None:
            text = _replace_clauses(expanded, spans, found)
        else:
            text = (_rename_reads(expanded, ix, found.rel, _twin(TWIN, n))
                    + _twin_facts(found, decl, subst, n))
    else:
        cols = [i for i, f in enumerate(decl.fields) if f.name in found.cols]
        feeds = _feed_rules(expanded, ix, found.rel)
        twin = _twin(TWIN, n)
        if feeds is not None:
            text = (_rename(expanded, ix, feeds, twin, body_only=False)
                    + _twin_text(found.rel, decl, cols, found.ref, subst,
                                 fed=True, n=n))
        else:
            text = (_rename_reads(expanded, ix, found.rel, twin)
                    + _twin_text(found.rel, decl, cols, found.ref, subst,
                                 n=n))
    return text


def _takes(case: CaseId, f: Found) -> bool:
    """The case takes the value `f` holds: `f` holds one value for every
    case, or the case takes each branch `f`'s case label names."""
    return (f.case == SHARED
            or _case_members(f.case) <= set(re.findall(r"\w+", case)))


def value_cases(source: str, found: list[Found], bases: list[CaseId],
                space: Cases) -> dict[int, list[CaseId]]:
    """For each owned finding, by `id`, the cases of `bases` that read its
    relation (`case_reads`) and take its value (`_takes`), the concept case
    first."""
    owned = [f for f in found if f.kind == OWNED]
    if not owned:
        return {}
    ordered = sorted(bases, key=lambda c: c != space.concept)
    reads = case_reads(source, space, ordered)
    return {id(f): [c for c in ordered
                    if _reads(f.rel, reads[c][0]) and _takes(c, f)]
            for f in owned}


def _reads(rel: str, read: set[str]) -> bool:
    """A case that reads the relations `read` reads `rel`: it reads `rel`,
    or a relation of the instance that holds `rel`, which the relations
    fed to that instance answer for."""
    inst = rel.rpartition(".")[0]
    return rel in read or bool(inst) and any(r.startswith(inst + ".")
                                             for r in read)


def _task_of(source: str) -> str | None:
    """The task the solver's header line `// <task_id>` names."""
    first = source.split("\n", 1)[0].removeprefix("//").strip()
    return first if TASK_ID_RE.fullmatch(first) else None


DIRECTIVE_LINE_RE = re.compile(r"^(\s*)//\s*@(?:store|derive|ignore)\b.*$",
                               re.M)
"""A `@store`, `@derive` or `@ignore` line, which states no value."""


def found_values(source: str) -> tuple[Found, ...]:
    """The owned findings of the store report on the inputs of the task the
    solver's header names, at the stored assignment, every relation
    counted whatever `@ignore: store` line stands on it: the values a store
    branch stores. Empty when the header names no task or no `@store` line
    stands. The `@store`, `@derive` and `@ignore` lines change no value, so
    two sources that differ in those lines alone share one report."""
    task_id = _task_of(source)
    if task_id is None or not store_blocks(source):
        return ()
    return _values(task_id, DIRECTIVE_LINE_RE.sub(r"\1//", source))


@lru_cache(maxsize=16)
def _values(task_id: str, source: str) -> tuple[Found, ...]:
    report = _report(source, solver_file(task_id)[0], task_id)
    return tuple(f for f in report.found if f.kind == OWNED)


def replaces_clauses(source: str, f: Found) -> bool:
    """The stored program gives the relation its facts in place of its
    clauses (`store_case_program`), so a case with the value stored reads
    nothing the relation derives from."""
    if f.keys:
        return False
    expanded = expand_macros(source)
    try:
        ix = _index(expanded)
    except ParseError:
        return False
    return _head_rules(expanded, ix, f.rel) is not None


def stored_program(source: str, found: list[Found]) -> str | None:
    """The solve-mode program of a case that takes a store branch for each
    finding of `found`, built off the solver's expanded source: each
    relation's value stored in turn. None when a relation is no program
    relation of the source."""
    text = expand_macros(source)
    for n, f in enumerate(found):
        try:
            ix = _index(text)
        except ParseError:
            return None
        hit = _candidates(ix, _solver_scopes(text)).get(f.rel)
        if hit is None:
            return None
        subst = _type_args(ix, f.rel.rpartition(".")[0])
        text = store_case_program(text, ix, f, hit[1], subst, n)
    return f"{text}\n{SOLVE_DIRECTIVES}"


def _case_program(source: str, found: Found) -> str | None:
    """The program of the case that takes one store branch."""
    return stored_program(source, [found])


def _decl_of(source: str, rel: str):
    """The declaration of a relation named by its instance path, and the
    type each parameter of its comp stands for."""
    expanded = expand_macros(source)
    try:
        ix = _index(expanded)
    except ParseError:
        return None, {}
    hit = _candidates(ix, _solver_scopes(expanded)).get(rel)
    if hit is None:
        return None, {}
    return hit[1], _type_args(ix, rel.rpartition(".")[0])


def _stored_run(built: str, grid: list[list[int]], path) -> list:
    """The run of a program assembled for a stored case on one grid. A
    failed run raises its error."""
    return parse_output(_run_source(built, grid_to_facts(grid),
                                    solver_path=path))


# --- the report -------------------------------------------------------

def _ignore_sites(source: str) -> set[str]:
    """The sites of the bare `@ignore: store` lines (`ignore_lines`): a
    relation a `.decl` declares, `<instance>.<relation>` for a line that
    names a relation above a `.init`, and `<instance>.` for one that names
    none there."""
    return {i.site for i in ignore_lines(source)
            if i.kind == STORE and not i.name and i.site}


def _names(spelled: str, rel: str) -> bool:
    """Whether a directive's relation names this one. A site inside a comp
    spells the path from that comp, so a suffix of the instance path
    answers for it."""
    return rel == spelled or rel.endswith("." + spelled)


def _ignored(sites: set[str], rel: str) -> bool:
    """Whether an `@ignore: store` line dismisses this relation."""
    return any(_names(s, rel) if not s.endswith(".")
               else _names(s + rel.rpartition(".")[2], rel)
               for s in sites)


def _run_all(built: str, grids: list[list[list[int]]],
             names: list[str]) -> list[dict] | None:
    out: list[dict] = []
    for g in _run_each(built, grids, names):
        if g is None:
            return None
        out.append(g)
    return out


def _run_each(built: str, grids: list[list[list[int]]],
              names: list[str]) -> list[dict | None]:
    """Each grid's tuples, with None where the run fails. A grid the solver
    refuses says nothing, and it leaves the other grids standing."""
    with ThreadPoolExecutor(max_workers=_pool_workers()) as pool:
        return list(pool.map(lambda g: _tuple_sets(built, g, names), grids))


def store_report(stem: str, witness_file: Path | None = None) -> Report:
    """Every column subset of the solver's program relations that holds one
    value on every input, with its witness and its `@store` line, and the
    findings that stand on them. `witness_file` stands in for the task's
    witness file."""
    path, task_id = solver_file(stem)
    return _report(path.read_text(), path, task_id, stem, witness_file)


def _report(source: str, path, task_id: str, stem: str = "",
            witness_file: Path | None = None) -> Report:
    """`store_report` on `source`, a solver of the task `task_id`. Without
    `stem`, the report holds the findings on the relations alone: no
    witness and no audit finding."""
    expanded = expand_macros(source)
    try:
        ix = _index(expanded)
    except ParseError as e:
        return Report(error=f"source does not parse: {e}")
    scopes = _solver_scopes(expanded)
    cands = _candidates(ix, scopes)
    names = list(cands)
    if not names:
        return Report(error="no relation both reads `in` and feeds `out`")
    casetypes = _case_types(ix)
    resolved = {
        name: [subst.get(f.type, f.type) for f in decl.fields]
        for name, (_k, decl) in cands.items()
        for subst in [_type_args(ix, name.rpartition(".")[0])]
    }
    branches, concept_branches, universes = _branch_names(
        source, ix, casetypes)
    stored = _stored_sets(expanded, _lib_defines())
    task = load_task(task_id)
    grids = [ex.input for ex in task.train] + [ex.input for ex in task.test]

    # Size pre-pass: count each relation's rows before any run prints them,
    # so a relation over the cap costs one count and no print.
    pre, of_count = _count_source(source, cands, names)
    per_count = _run_all(pre, grids, list(of_count))
    if per_count is None:
        return Report(error="the stored source fails an example")
    skipped: list[str] = []
    over: set[str] = set()
    for cname, name in of_count.items():
        got = [next(iter(g[cname]), None) for g in per_count]
        rows = [int(x) for x in got if x is not None]
        if len(rows) != len(got):
            continue
        if max(rows) <= ROW_CAP:
            continue
        over.add(name)
        types = resolved[name]
        if types and len(types) <= MAX_COLS and min(rows) > 0:
            skipped.append(name)

    run_names = [n for n in names if n not in over]
    per_grid = _run_all(_build(source, run_names), grids, run_names)
    if per_grid is None:
        return Report(error="the stored source fails an example")
    labels = ([f"train {i}" for i in range(len(task.train))]
              + [f"test {i}" for i in range(len(task.test))])
    differs = {
        n: next((labels[i] for i, g in enumerate(per_grid)
                 if g[n] != per_grid[0][n]), "")
        for n in run_names
    }
    raw = _analyze(per_grid, run_names, cands, casetypes, resolved, skipped)
    if not raw:
        return Report(skipped=sorted(skipped), findings=_findings(
            source, stem, [], cands, differs, ix, witness_file)
            if stem else [])

    flagged = sorted({name for name, _case in raw})
    probe = _build(source, flagged)
    # Two controls: the first palette redraw and the changed extent.
    controls = _controls(grids)
    ctrl = _run_each(probe, [controls[0], controls[-1]], flagged)

    cache: dict[tuple, dict] = {}

    def projection(g, name, case, subset, kind, types, case_cols):
        """The relation's value on one probe grid, and None when the
        relation is empty there."""
        if g is None or not g[name]:
            return None
        k = (id(g), name, case)
        if k not in cache:
            rows = _split_cases([r.split("\t") for r in g[name]],
                                case_cols).get(case, [])
            needed = [s2 for (n2, _c2), (_t, keep, _f, _r) in raw.items()
                      if n2 == name for s2 in keep]
            cache[k] = _families(rows, types, [], needed) if rows else {}
        fam = cache[k].get(subset)
        if fam is None:
            return None
        return fam[1] if kind == TRANSLATED else fam[0]

    # The case the input reading is taken on. A branch of its own may
    # derive what it reads, and that derivation is the branch's reading,
    # not the relation's, so the concept branch answers for the relation.
    concept_key: dict[str, str] = {}
    for name, case in raw:
        members = _ctor_names(case)
        if members and members <= concept_branches:
            concept_key[name] = case

    found: list[Found] = []
    pending: list[tuple] = []
    reading: set[str] = set()
    """The relations the controls left standing, whatever filter took them
    afterwards. A relation derived from one of these inherits its value
    from it."""
    sites = _ignore_sites(source)
    with_line = [rel for b in store_blocks(source)
                 if (rel := store_relation(source, b))]
    for (name, case), (types, keep, fam0, rows) in sorted(raw.items()):
        key, decl = cands[name]
        if _ignored(sites, name) and not any(_names(r, name)
                                             for r in with_line):
            continue
        case_cols = [i for i in range(len(types)) if types[i] in casetypes]
        members = (_ctor_names(case) if case
                   else _section_cases(ix, key, branches))
        label = ", ".join(sorted(members)) if members else SHARED
        is_concept = (not members) or bool(members & concept_branches)
        reads, use_cases = _uses(ix, key, scopes, branches,
                                 concept_branches)
        for subset, kind in keep.items():
            ref = fam0[subset][1] if kind == TRANSLATED else fam0[subset][0]
            args = (name, case, subset, kind, types, case_cols)
            read_case = concept_key.get(name, case)
            base = ref
            if read_case != case:
                base = projection(per_grid[0], name, read_case, subset, kind,
                                  types, case_cols)
                if base is None:
                    base, read_case = ref, case
            read_args = (name, read_case, subset, kind, types, case_cols)
            # A control grid gives evidence only where the relation stands
            # nonempty on it. A grid the solver leaves it empty on says
            # nothing, and the controls then hold the finding back on
            # nothing.
            palette, extent = (projection(g, *read_args) for g in ctrl)
            evidence = [r for r in (palette, extent) if r is not None]
            if evidence and all(r == base for r in evidence):
                continue  # the value does not read the input
            reading.add(name)
            sizes = sorted(len(s) for s in ref)
            if (len(subset) == 1 and len(ref) > 1
                    and all(n == 1 for n in sizes)):
                continue  # the column is a function of the key
            rect = ""
            if (len(subset) == 1 and types[subset[0]] == "Position"
                    and len(ref) == 1):
                one = next(iter(ref))
                points = ({m[0] for m in one} if kind == TRANSLATED
                          else {_point(m[0]) for m in one})
                rect = _rect(points)
            extent_only = (palette is not None and palette == base
                           and extent is not None and extent != base)
            if rect and _is_frame(rect, grids):
                continue  # the frame of every input
            positional = any(types[i] in POS_TYPES | {OFFSET_TYPE}
                             for i in subset)
            if extent_only and (rect or positional):
                continue  # the frame, a panel, a tile, or layout over them
            dir_cols = [i for i in subset if types[i] in FULL]
            pos_cols = [i for i in subset if types[i] in POS_TYPES]
            if (len(subset) == 2 and len(dir_cols) == 1 and len(pos_cols) == 1
                    and all(n == FULL[types[dir_cols[0]]] for n in sizes)):
                continue  # a neighborhood generated around a point
            if _restates(kind, ref, stored):
                continue  # a stored parameter's value under another name
            keys = [i for i in range(len(types)) if i not in subset
                    and types[i] not in casetypes | {UNIT_TYPE}]
            if kind == CONSTANT and not (
                    keys and all(types[i] == IDENT_TYPE for i in keys)):
                continue  # the owned relation over all its columns
            columns = [i for i in range(len(types))
                       if types[i] not in casetypes | NO_COLUMN_TYPES]
            facts = tuple(sorted(tuple(r) for r in rows)) if not keys else ()
            found.append(Found(
                rel=name,
                cols=[decl.fields[i].name for i in subset],
                keys=[decl.fields[i].name for i in keys],
                types=[types[i] for i in subset],
                sub=len(subset) < len(columns),
                kind=kind, case=label, concept=is_concept, read=reads,
                ref=ref, rect=rect, facts=facts,
                used_in=", ".join(sorted(use_cases))))
            pending.append((found[-1], args))

    bodies = _body_map(ix, scopes)
    kept = {id(f) for f in _inherited(bodies, ix, found, reading)}
    pending = [p for p in pending if id(p[0]) in kept]
    kept = {id(f) for f in _merge([f for f in found if id(f) in kept])}
    pending = [p for p in pending if id(p[0]) in kept]
    found = [p[0] for p in pending]
    _fold(found, _body_map(ix, scopes, deep=True),
          universes)
    _attach_lines(source, found)
    own = {TOP} | set(parse(expanded).comps())
    for f in found:
        f.site, f.spelled = _site(ix, f.rel, own)
        if f.line is not None:
            f.spelled = store_relation(source, f.line) or f.spelled
    if not stem:
        return Report(found=found, skipped=sorted(skipped))
    _attach_witnesses(stem, source, path, task, cands, pending, projection)
    return Report(found=found, skipped=sorted(skipped),
                  findings=_findings(source, stem, found, cands, differs, ix,
                                            witness_file))


def _relation_keys(ix: Index) -> list[tuple[str, tuple]]:
    """Every relation of the program under its instance path."""
    out = [(name, (TOP, name)) for name in ix.decls.get(TOP, {})]
    for path, comp in _instances(ix):
        for scope in ix.chain(comp):
            out += [(f"{path}.{name}", (scope, name))
                    for name in ix.decls.get(scope, {})]
    return out


def _body_map(ix: Index, scopes: set[str],
              deep: bool = False,
              rules: set[int] | None = None) -> dict[str, set[str]]:
    """Each relation's body relations, by instance path. A relation derived
    inside a lib comp takes the relations fed to its instance, and, where
    `deep` stands, the relations of that instance it derives from. Where
    `rules` stands, only the rules it names give edges. A relation of a
    solver scope that none of those rules derives has no body relations."""
    by_rule: dict[int, list] = {}
    for r in ix.refs:
        by_rule.setdefault(r.rule, []).append(r)
    prefixes: dict[str, list[str]] = {TOP: [""]}
    comp_of: dict[str, str] = {}
    for path, comp in _instances(ix):
        prefixes.setdefault(comp, []).append(path)
        comp_of[path] = comp
    backward = _edges(ix)[1]

    def full(prefix: str, atom, scope: str) -> str:
        # A name the comp does not hold is a top-level one, like `params`.
        head = (atom.qual or atom.name).split(".")[0]
        if prefix and not any(head in ix.decls.get(s, {})
                              or head in ix.inits.get(s, {})
                              for s in ix.chain(scope)):
            prefix = ""
        return ".".join(x for x in (prefix, atom.qual or "", atom.name) if x)

    keys = dict(_relation_keys(ix))

    def bodies(rel: str) -> set[str]:
        key = keys.get(rel)
        if key is None:
            return set()
        out: set[str] = set()
        seen = False
        for r in ix.refs_of(key):
            if r.role != "head" or r.scope not in scopes:
                continue
            if rules is not None and r.rule not in rules:
                continue
            for prefix in prefixes.get(r.scope, []):
                if full(prefix, r.atom, r.scope) != rel:
                    continue
                seen = True
                out |= {full(prefix, b.atom, b.scope) for b in by_rule[r.rule]
                        if b.role != "head"}
        if seen or key[0] in scopes:
            return out
        # Derived inside a lib comp. The instance holds what the top level
        # feeds it, so the feeds answer for every relation of it.
        inst = rel.rpartition(".")[0]
        for r in ix.refs:
            if r.role != "head" or r.scope not in scopes:
                continue
            if rules is not None and r.rule not in rules:
                continue
            for prefix in prefixes.get(r.scope, []):
                if not full(prefix, r.atom, r.scope).startswith(inst + "."):
                    continue
                out |= {full(prefix, b.atom, b.scope) for b in by_rule[r.rule]
                        if b.role != "head"}
        if out and not deep:
            return out
        chain = set(ix.chain(comp_of[inst])) if inst in comp_of else set()
        for k in backward.get(key, set()):
            if k[0] in chain:
                out.add(f"{inst}.{k[1]}")
                continue
            subs = [p for p, c in comp_of.items()
                    if p.startswith(inst + ".") and k[0] in set(ix.chain(c))]
            out |= {f"{p}.{k[1]}" for p in subs} or {k[1]}
        return out

    return {rel: bodies(rel) for rel in keys}


def _inherited(bodies: dict[str, set[str]], ix: Index, found: list[Found],
               reading: set[str]) -> list[Found]:
    """The findings left once the ones that inherit their constancy are
    out: a relation every body relation of which is constant states
    nothing of its own. A Params relation counts as constant, an inline lib
    relation is neutral, and `in` is not constant."""

    def body_constant(name: str) -> bool | None:
        if name == "in":
            return False
        if name.startswith("params.") or name in reading:
            return True
        decl = ix.decls.get(TOP, {}).get(name) if "." not in name else None
        if decl is not None and "inline" in decl.qualifiers:
            return None
        return False

    return [f for f in found
            if any(body_constant(n) is False
                   for n in bodies.get(f.rel, {"in"}))]


def _case_members(label: str) -> set[str]:
    return set(label.split(", "))


def _shares_case(a: set[str], b: set[str], universes: list) -> bool:
    """Whether two findings can stand in one case: no choice type has them
    on different branches. A finding under no marker runs on every case."""
    for whole in universes:
        pa, pb = a & whole, b & whole
        if pa and pb and not pa & pb:
            return False
    return True


def _ancestors(rel: str, bodies: dict[str, set[str]]) -> set[str]:
    """Every relation the relation derives from, `in` aside. The walk goes
    through a relation the report does not name, so a chain holds across
    one."""
    seen: set[str] = set()
    work = list(bodies.get(rel, ()))
    while work:
        name = work.pop()
        if name in seen or name == "in" or name == rel:
            continue
        seen.add(name)
        work += list(bodies.get(name, ()))
    return seen


def _concept_rules(ix: Index, others: set[str]) -> set[int]:
    """The rules whose tuples a case holds: the ones whose head carries no
    constructor of `others`, the branches the case does not take. A rule
    the case holds none of feeds it nothing, wherever it stands."""
    return {
        i for i, info in enumerate(ix.rules)
        if not any(isinstance(t, Ctor) and t.name in others
                   for arg in info.rule.head.args for t in _subterms(arg))
    }


def _params_read(holder: str, params: set[str], read: set[str]) -> set[str]:
    """The Params parameters among the relations `read`, by instance path:
    a parameter is read as `<holder>.<param>`, and a relation of another
    instance or of the top level that shares its name is not it."""
    return {p for p in params if f"{holder}.{p}" in read}


def _holder(ix: Index) -> str:
    """The instance of `Params`."""
    return next((name for name, init in ix.inits.get(TOP, {}).items()
                 if init.comp == "Params"), "params")


def case_reads(source: str, space: Cases, cases: list[CaseId],
               cut: frozenset[str] = frozenset()
               ) -> dict[CaseId, tuple[set[str], set[str]]]:
    """What each case of `cases` reads: the relations `out` derives from,
    by instance path, and the Params parameters among them. A case holds
    the rules whose head carries no constructor it does not take: of a
    `Space`, the constructors of every type; of another space, the
    non-concept branches. The relations of `cut` are ones whose facts a
    stored program puts in place of their clauses (`replaces_clauses`),
    and they derive from nothing."""
    expanded = expand_macros(source)
    params = set(fact_params(expanded, _lib_defines()))
    try:
        ix = _index(expanded)
    except ParseError:
        return {c: (set(), set()) for c in cases}
    holder = _holder(ix)
    scopes = _solver_scopes(expanded)
    if isinstance(space, Space):
        ctors = {c for branches in space.types.values() for c in branches}
        others = {c: ctors - set(re.findall(r"\w+", c)) for c in cases}
    else:
        rest = {b.name for p in choice_points(source) for b in p.branches
                if not b.is_concept}
        others = {c: rest for c in cases}
    out: dict[CaseId, tuple[set[str], set[str]]] = {}
    for case in cases:
        bodies = _body_map(ix, scopes, deep=True,
                           rules=_concept_rules(ix, others[case]))
        for rel in cut:
            bodies[rel] = set()
        read = _ancestors("out", bodies)
        out[case] = (read, _params_read(holder, params, read))
    return out


def _fold(found: list[Found], bodies: dict[str, set[str]],
          universes: list) -> None:
    """Fold each shown relation that stands downstream of another shown one
    under it. The upstream relation states the value; the rest restate it
    one step along."""
    cases: dict[str, set[str]] = {}
    for f in found:
        cases.setdefault(f.rel, set()).update(_case_members(f.case))
    shown = set(cases)
    above = {
        rel: sorted(a for a in _ancestors(rel, bodies) & shown
                    if _shares_case(cases[rel], cases[a], universes))
        for rel in shown
    }
    sources = {rel for rel, ups in above.items() if not ups}
    weight = {rel: sum(rel in ups for ups in above.values()) for rel in shown}
    under: dict[str, list[str]] = {}
    for rel, ups in sorted(above.items()):
        if not ups:
            continue
        roots = sorted((a for a in ups if a in sources),
                       key=lambda a: (-weight[a], a))
        src = roots[0] if roots else None
        if src is None:      # a cycle: its members answer for one another
            src = sorted({*ups, rel})[0]
            if src == rel:
                sources.add(rel)
                continue
        under.setdefault(src, []).append(rel)
    for f in found:
        f.folded = f.rel not in sources
    for src, rels in under.items():
        first = next((f for f in found if f.rel == src), None)
        if first is not None:
            first.under = sorted(set(rels))


def _merge(found: list[Found]) -> list[Found]:
    """One entry per finding, with the cases that give the same value on one
    line, and the rows of every one of those cases."""
    out: list[Found] = []
    by_sig: dict[tuple, Found] = {}
    for f in found:
        sig = (f.rel, tuple(f.cols), f.kind, f.ref)
        held = by_sig.get(sig)
        if held is None:
            by_sig[sig] = f
            out.append(f)
            continue
        cases = set(held.case.split(", ")) | set(f.case.split(", "))
        held.case = ", ".join(sorted(cases))
        held.concept = held.concept or f.concept
        held.facts = tuple(sorted(set(held.facts) | set(f.facts)))
    return out


def _attach_witnesses(stem, source, path, task, cands, pending,
                      projection) -> None:
    """Give each owned finding the first grid on which its value differs:
    a D4 image of a train input, then a color swap of one. A grid the
    relation stands empty on holds no value, and it is the witness where
    some held case that takes the value (`value_cases`) gives different
    outputs with the relation derived and with the value stored, or is
    defined in one and not in the other. A color value gets one where a
    `@store` line stands on it."""
    wanted = [(f, args) for f, args in pending if f.kind == OWNED
              and (not f.colors or f.line is not None)
              and f.held and not f.folded]
    if not wanted:
        return
    space = case_space(source)
    readers = value_cases(source, [f for f, _ in wanted],
                          held_choice(source, space), space)
    names = sorted({f.rel for f, _ in wanted})
    built = _build(source, names)
    held = _stored_colors(expand_macros(source), _lib_defines())
    trains = [ex.input for ex in task.train]
    batches: list[list[tuple[str, str, list[list[int]]]]] = []
    for i, grid in enumerate(trains):
        batches.append([(f"train {i}", D4_NAMES[d], g)
                        for d, g in _d4_images(grid).items()])
    batches.append(_swaps(trains, held))
    resolution = res_out_stem(stem)
    derived: dict[int, list] = {}
    programs: dict[int, str | None] = {}
    concept = space.concept

    def outcome(got, case):
        if case is None or case == concept:
            return concept_outcome(got, resolution, source)
        return model_outcomes(got, resolution).get(case)

    def at_derived(grid) -> list:
        """The run of the solver as it stands on the grid."""
        if id(grid) not in derived:
            derived[id(grid)] = run_dl_source(source, grid, solver_path=path)
        return derived[id(grid)]

    def first_reader(f, grid):
        """What the first held case that takes `f`'s value gives with the
        relation derived."""
        cases = readers.get(id(f)) or [None]
        return outcome(at_derived(grid), cases[0])

    def diverges(f, grid) -> bool:
        """Some held case that takes `f`'s value gives different outputs
        with the relation derived and with the value stored, or is defined
        in one and not in the other. A run with the value stored that
        fails gives no answer, and its error stands on `f`."""
        if id(f) not in programs:
            programs[id(f)] = _case_program(source, f)
        stored = programs[id(f)]
        if stored is None or f.failed:
            return False
        try:
            got = _stored_run(stored, grid, path)
        except RuntimeError as err:
            f.failed = str(err)
            return False
        base = at_derived(grid)
        return any(outcome(base, c) != outcome(got, c)
                   for c in readers.get(id(f)) or [None])

    for batch in batches:
        left = [(f, args) for f, args in wanted if f.move is None]
        if not left:
            return
        if not batch:
            continue
        got = _run_all(built, [g for _l, _c, g in batch], names)
        if got is None:
            continue
        for (label, change, grid), g in zip(batch, got):
            for f, args in left:
                if f.move is not None:
                    continue
                value = projection(g, *args)
                if value == f.ref:
                    continue
                if value is None and not diverges(f, grid):
                    continue
                f.move = Move(label, change, first_reader(f, grid) == grid,
                              grid)


def _stored_colors(source: str, defines: dict[str, int]) -> set[int]:
    """Every color a Params fact names."""
    return {
        v
        for types, stored in fact_params(source, defines).values()
        for row in stored
        for v, t in zip(row, types) if t == COLOR_TYPE
    }


def _attach_lines(source: str, found: list[Found]) -> None:
    """Give each finding the `@store` line that stands on its relation."""
    spelled = [(rel, block) for block in store_blocks(source)
               if (rel := store_relation(source, block))]
    for f in found:
        f.line = next((b for rel, b in spelled if _names(rel, f.rel)), None)


def _instance_holds(ix: Index, inst: str, path: str) -> bool:
    """Whether some instance named `inst` holds a relation at `path`."""
    for inits in ix.inits.values():
        if inst not in inits:
            continue
        scope, *hops = [inits[inst].comp, *path.split(".")]
        for hop in hops[:-1]:
            init = next((ix.inits[c][hop] for c in ix.chain(scope)
                         if hop in ix.inits.get(c, {})), None)
            if init is None:
                break
            scope = init.comp
        else:
            if any(hops[-1] in ix.decls.get(c, {}) for c in ix.chain(scope)):
                return True
    return False


def _unnamed(source: str, block: Store, ix: Index) -> str | None:
    """Why a named `@store` line names no relation of an instance, and None
    where it does."""
    if not block.rel:
        return None
    text = source.splitlines()[block.above - 1] if block.above else ""
    if DECL_RE.match(text):
        return mctx("`@store {rel}` stands above a `.decl`").format(
            rel=block.rel)
    m = INIT_RE.match(text)
    if m and not _instance_holds(ix, m[1], block.rel):
        return mctx("`{rel}` is no relation of the instance `{inst}`"
                    ).format(rel=block.rel, inst=m[1])
    return None


def _findings(source: str, stem: str, found: list[Found], cands: dict,
              differs: dict[str, str], ix: Index,
              witness_file: Path | None = None) -> list[Finding]:
    """The findings the audit prints. `witness_file` stands in for the
    task's witness file."""
    _path, task_id = solver_file(stem)
    witness = load_witnesses(task_id) if witness_file is None \
        else load_witness_file(witness_file) if witness_file.exists() \
        else None
    entries = {e.id: e for e in (witness or Witness(task_id)).entries}
    ids = set(entries)
    out: list[Finding] = []
    owned = {f.rel: f for f in found if f.kind == OWNED and f.held}
    unread = {f.rel for f in found if f.kind == OWNED and not f.held}
    held_back = {f.rel: f for f in found if f.kind != OWNED}
    params = comp_decls(source, "Params")
    for block in store_blocks(source):
        rel = store_relation(source, block)
        where = f"line {block.line}"
        if (why := _unnamed(source, block, ix)) is not None:
            out.append(Finding(where, why))
            continue
        if not rel:
            out.append(Finding(where, mctx(
                "`@store` stands above no `.decl` or `.init`")))
            continue
        if rel in params:
            out.append(Finding(where, mctx(
                "the `@store` line is on `{rel}`, which is also the name of a "
                "parameter, so `{rel}=stored` denotes two branches"
            ).format(rel=rel)))
            continue
        f = next((v for k, v in owned.items() if _names(rel, k)), None)
        if f is None:
            out.append(Finding(where, _no_finding(rel, cands, unread,
                                                  held_back, differs)))
            continue
        if f.case_id in ids:
            out += [Finding(f.case_id, text) for text in _entry_witness(
                stem, source, f.case_id, entries[f.case_id])]
            continue
        if block.verdict == OTHER or f.move is None:
            out.append(Finding(where, _witness_ask(
                f, block.verdict == OTHER)))
    out += [Finding(where, text)
            for where, text in drop_findings(enumeration(source), STORE)]
    for f in found:
        if f.failed:
            out.append(Finding(f.rel, mctx(
                "the case `{case}` failed: {error}").format(
                    case=f.case_id, error=f.failed)))
        if (f.kind == OWNED and f.held and not f.colors
                and f.line is None and not f.folded):
            out.append(Finding(f.rel, mctx(
                "one value on every input and no `@store` or "
                "`@ignore: store` line")))
        if _asks_params(f) and not f.folded:
            out.append(Finding(f.rel, _params_ask(f)))
        if f.case_id in ids:
            f.entry = f.case_id
    return out


def _entry_witness(stem: str, source: str, name: str, entry) -> list[str]:
    """Where the witness file's entry of a `@store` branch's name fails to
    witness it: its `assign` holds a fault `assign_findings` finds, or at
    its assignment no case that takes the branch gives an output other than
    the same case with the relation derived
    (`dl.witness.branch_diverges`). No finding where no held case takes
    the branch."""
    space = enumeration(source)
    branch = next((b for held in space.runner.values()
                   for b in held.branches if b.name == name), None)
    if branch is None:
        return []
    if bad := assign_findings(entry.assign, source):
        return bad
    if branch_diverges(stem, space, branch, entry.input,
                       assigned_source(source, entry.assign)) is not None:
        return []
    return [mctx("at the witness's assignment, each case that takes "
                 "`{case}` gives the output of the case that takes the "
                 "derived value there and the same branches elsewhere").format(
                     case=name)]


def _witness_ask(f: Found, other: bool) -> str:
    """What asks for a witness of the id `<rel>=stored`, where one is
    needed: for the verdict `other`, or where no built grid separates the
    cases that take the branch."""
    lead = (mctx("the verdict `{verdict}` needs").format(verdict=OTHER)
            if other else mctx("`{case}` needs").format(case=f.case_id))
    return mctx("{lead} a witness whose id is `{case}`").format(
        lead=lead, case=f.case_id)


def lined(source: str, f: Found) -> str | None:
    """`source` with a `@store` line on the finding's relation, as
    `store_hint` gives it: above the instance's `.init` where the finding
    has a site, and above the relation's `.decl` otherwise. None when
    neither stands."""
    text = f"// @store{_named(f.spelled, f.site)}: <plausibility> <verdict>"
    if f.site:
        return with_line_above(source, rf"^\s*\.init\s+{f.site}\s*=", text)
    return with_line_above(source, rf"^\s*\.decl\s+{f.spelled}\b", text)


def _no_finding(rel: str, cands: dict, unread: set[str],
                held_back: dict[str, Found],
                differs: dict[str, str]) -> str:
    """What the audit says of a `@store` line that stands on no owned
    finding of a relation the concept case reads."""
    if rel not in cands:
        return mctx("`{rel}` is no program relation between `in` and `out`"
                    ).format(rel=rel)
    if rel in unread:
        return mctx("`{rel}` is no relation a case reads").format(
            rel=rel)
    f = next((v for k, v in held_back.items() if _names(rel, k)), None)
    if f is not None:
        return mctx("`{rel}` {why}").format(rel=rel, why=_no_case(f))
    grid = differs.get(rel, "")
    if grid:
        return mctx("`{rel}` gives another value on {grid}").format(
            rel=rel, grid=grid)
    return mctx("`{rel}` gives no value the runner can store").format(
        rel=rel)


# --- rendering --------------------------------------------------------

def _enum_name(type_: str, value: str) -> str:
    """An orientation value under the name the lib gives it."""
    if type_ not in FULL:
        return value
    return _orientation()[0].get(value, value)


def _cells(f: Found) -> list[tuple[int, int]] | None:
    """The cells the value draws, and None when it draws no picture."""
    if len(f.cols) != 1 or f.types[0] not in POS_TYPES or len(f.ref) != 1:
        return None
    one = next(iter(f.ref))
    if f.kind == TRANSLATED:
        return sorted(m[0] for m in one)
    return sorted(_point(m[0]) for m in one)


def _colored(f: Found) -> dict[tuple[int, int], int] | None:
    """The colored cells the value draws, and None when it draws none."""
    if len(f.cols) != 2 or len(f.ref) != 1:
        return None
    pos = [i for i, t in enumerate(f.types) if t in POS_TYPES]
    col = [i for i, t in enumerate(f.types) if t == COLOR_TYPE]
    if len(pos) != 1 or len(col) != 1:
        return None
    one = next(iter(f.ref))
    if f.kind == TRANSLATED:
        return {m[pos[0]]: int(m[col[0]]) for m in one}
    return {_point(m[pos[0]]): int(m[col[0]]) for m in one}


def _offsets(f: Found) -> list[tuple[int, int]] | None:
    """The offsets the value stamps, and None when it stamps none."""
    if len(f.cols) != 1 or f.types[0] != OFFSET_TYPE or len(f.ref) != 1:
        return None
    return sorted(_point(m[0]) for m in next(iter(f.ref)))


def _picture(marks: dict[tuple[int, int], str]) -> list[str]:
    """A cell map drawn as a grid, one row per line. A map of one cell, and
    one that reaches past the draw cap along either axis, draws nothing: a
    record standing alone is a value, not a picture."""
    if len(marks) < 2:
        return []
    ts = [t for t, _l in marks]
    ls = [l for _t, l in marks]
    if (max(ts) - min(ts) >= DRAW_CAP) or (max(ls) - min(ls) >= DRAW_CAP):
        return []
    return [" ".join(marks.get((t, l), ".")
                     for l in range(min(ls), max(ls) + 1))
            for t in range(min(ts), max(ts) + 1)]


def _drawn(f: Found) -> list[str]:
    """The value's picture, and no line where it draws none."""
    if f.rect:
        return [mctx("{rect} rectangle").format(rect=f.rect)]
    cells = _cells(f)
    if cells is not None:
        return _picture({p: "#" for p in cells})
    colored = _colored(f)
    if colored is not None:
        return _picture({p: str(c) for p, c in colored.items()})
    offsets = _offsets(f)
    if offsets is not None:
        marks = {p: "#" for p in offsets}
        marks[(0, 0)] = "@"
        return _picture(marks)
    return []


def _inline(f: Found) -> str:
    """The value as one phrase, for a value that draws no picture."""
    one = next(iter(f.ref))
    return ", ".join(
        _enum_name(f.types[0], m[0]) if len(m) == 1
        else "(" + ", ".join(_enum_name(f.types[i], v)
                             for i, v in enumerate(m)) + ")"
        for m in sorted(one))


def _noun(f: Found) -> str:
    if _cells(f) is not None or _colored(f) is not None or f.rect:
        return mctx("cell set")
    if _offsets(f) is not None:
        return mctx("offset set")
    return mctx("value")


def _headline(f: Found) -> str:
    """The finding's first line."""
    name = f"{f.rel}[{', '.join(f.cols)}]" if f.sub else f.rel
    if f.line is not None and f.kind == OWNED:
        return mctx("{name}: @store at line {line}").format(
            name=name, line=f.line.line)
    if f.kind == CONSTANT:
        keys = ", ".join(f"`{k}`" for k in f.keys) or mctx("the key")
        return mctx("{name}: {n} {noun}s, one per {keys}").format(
            name=name, n=len(f.ref), noun=_noun(f), keys=keys)
    if f.kind == TRANSLATED:
        return mctx("{name}: one {noun} up to translation on every input"
                    ).format(name=name, noun=_noun(f))
    if f.colors:
        if _asks_params(f):
            return mctx("{name}: {ask}").format(name=name, ask=_params_ask(f))
        return (mctx("{name}: one color on every input: {value}").format(
            name=name, value=_inline(f)) + _in_case(f))
    if _drawn(f):
        return (mctx("{name}: one {noun} on every input").format(
            name=name, noun=_noun(f)) + _in_case(f))
    members = len(next(iter(f.ref)))
    if members > SHOWN_MEMBERS:
        return (mctx("{name}: one value set of {n} members on every input"
                     ).format(name=name, n=members) + _in_case(f))
    return (mctx("{name}: one value on every input: {value}").format(
        name=name, value=_inline(f)) + _in_case(f))


def _asks_params(f: Found) -> bool:
    """The value is a color the concept case reads, and the runner holds no
    case that stores it: its stored reading is a Params parameter."""
    return (f.kind == OWNED and f.colors and f.read and f.concept
            and f.line is None)


def _params_ask(f: Found) -> str:
    return mctx("one color on every input: {value}; store it in Params"
                ).format(value=_inline(f))


def _in_case(f: Found) -> str:
    """The marker a relation the concept case neither reads nor feeds
    stands under."""
    if f.read or not f.used_in:
        return ""
    return mctx("; under `{case}`").format(case=f.used_in)


def _witness_line(f: Found) -> str:
    if f.entry:
        return mctx("witness: `{case}` in the witness file").format(
            case=f.case_id)
    if f.move is None:
        return mctx("no witness: no D4 image or color swap of a train "
                    "input changes the value; {ask}").format(
                        ask=_witness_ask(f, False))
    line = mctx("witness: {grid} {change}").format(grid=f.move.grid,
                                                   change=f.move.change)
    if f.move.identity and f.read:
        line += mctx("; the concept case gives the input unchanged")
    elif f.move.identity:
        line += mctx("; the case under `{case}` gives the input unchanged"
                     ).format(case=f.used_in)
    return line


def _named(rel: str, site: str) -> str:
    """The name a directive above the instance's `.init` gives the relation:
    its path inside the instance, and nothing above the relation's own
    `.decl`. `rel` spells the relation from the site, and without a site
    from the path's first instance."""
    _root, _dot, path = rel.partition(".")
    return f" {path}" if path else ""


def _add(site: str) -> str:
    return f"add above `.init {site}`:" if site else "add:"


def store_hint(rel: str, site: str) -> str:
    """The line the session adds at the relation's site: the bare form above
    the relation's `.decl`, and the named form above an instance's
    `.init`."""
    return (f"{_add(site)} // @store{_named(rel, site)}: "
            "<plausibility> <verdict>")


def _no_case(f: Found) -> str:
    """Why the runner holds no case for a value that is not the same on
    every input: it stores a value as it stands, with no anchor to place
    it by and no id to key it by."""
    if f.kind == TRANSLATED:
        return mctx("stands at another place on each input, and the runner "
                    "picks no anchor")
    keys = ", ".join(f"`{k}`" for k in f.keys)
    return mctx("varies by {keys}, an id the runner stores nothing under"
                ).format(keys=keys)


def ignore_hint(rel: str, site: str, alone: bool = False) -> str:
    """The line the session adds instead when it judges the stored model
    no case, at the same site and in the same two forms. `alone` says no
    `@store` line stands above it in the report, so it names the site."""
    lead = f"{_add(site)} " if alone and site else "or:  "
    return f"{lead}// @ignore{_named(rel, site)}: store — <reason>"


def _rank(f: Found) -> tuple:
    return (not f.concept, not f.read, f.kind != OWNED, f.rel, tuple(f.cols))


def render_store(report: Report) -> list[str]:
    """The `store` command's output: one block per finding."""
    if report.error:
        return [report.error]
    lines: list[str] = []
    for f in sorted([f for f in report.found if not f.folded], key=_rank):
        lines.append(_headline(f))
        if (f.kind == OWNED and f.line is None and not f.colors and f.held):
            lines += ["  " + ln for ln in _drawn(f)]
            lines.append("  " + _witness_line(f))
            lines.append("  " + store_hint(f.spelled, f.site))
            lines.append("  " + ignore_hint(f.spelled, f.site))
        elif _asks_params(f):
            lines.append("  " + ignore_hint(f.spelled, f.site, alone=True))
        elif f.kind == OWNED and f.line is not None and f.held:
            # The witness the line's plausibility and verdict judge.
            lines.append("  " + _witness_line(f))
        elif f.kind != OWNED:
            lines += ["  " + ln for ln in _drawn(f)]
            lines.append("  " + mctx("no case: the value {why}").format(
                why=_no_case(f)))
        if f.under:
            lines.append("  " + mctx(
                "relations that derive from this one and hold one value "
                "too, which need no `@store` or `@ignore: store` line: "
                "{rels}").format(
                rels=", ".join(f"`{r}`" for r in f.under)))
    lines += _skipped_lines(report)
    return lines or [mctx("no findings")]


def _skipped_lines(report: Report) -> list[str]:
    """The relations the report did not check, under the cap that
    applied."""
    if not report.skipped:
        return []
    return [mctx("not checked, over {cap} rows on an input, too many to be a "
                 "stored value: {rels}").format(
        cap=ROW_CAP, rels=", ".join(f"`{n}`" for n in report.skipped))]


def render_findings(report: Report) -> list[str]:
    """The audit's section: one line per finding, or `store: ok` when none
    stands, then the relations the report did not check."""
    if report.error:
        return [report.error]
    return ([f"{f.where}: {f.text}" for f in report.findings] or [STORE_OK]
            ) + _skipped_lines(report)

