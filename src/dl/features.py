"""Per-case features of a solver: what each case of its `Choice` reaches.

A rule whose head holds only that case's
constructors belongs to it, and so does every rule the bodies of those rules
reach, transitively. What one case reaches and no other is its own weight;
what two cases reach is shared, and what no case reaches is counted apart
from every case. Section markers say nothing here.

The dynamic columns come from `dl.features_run`, which runs every pair of
the task, train and test alike; without a run they are None, and the
renderer writes them as `-`.
"""

import re
import subprocess
from dataclasses import asdict, dataclass, field, fields
from itertools import product

from controlled_markdown import mctx
from dl.corpus import rule_literals
from dl.dlparse import (
    EXTERN,
    TOP,
    Atom,
    Cmp,
    Comp,
    Decl,
    Disj,
    Index,
    Neg,
    ParseError,
    Program,
    RelKey,
    Rigid,
    Rule,
    TypeDecl,
    _aggs_in_terms,
    body_literals,
    parse,
)
from dl.facts import _parse_relations, grid_to_facts
from dl.features_run import Matrix, RunReport
from dl.models import (
    NO_CHOICE,
    CaseId,
    case_label,
    case_space,
    held_choice,
    model_label,
)
from dl.rewrite_lint import _ctor_names, _record_fields
from dl.solve import solver_file
from dl.souffle import _run_source
from dl.source import expand_macros

type Reach = dict[CaseId, set[int]]


@dataclass
class CaseFeatures:
    stem: str
    case: str
    case_index: int
    cases_in_file: int
    atoms: int
    shared_atoms: int
    rules: int
    shared_rules: int
    facts: int
    shared_facts: int
    reach_atoms: int
    reach_rules: int
    reach_facts: int
    unreached_atoms: int
    negations: int
    disjunctions: int
    aggregates: int
    comparisons: int
    lib_instances: int
    distinct_lib_units: int
    atoms_ratio_min: float | None
    facts_ratio_min: float | None
    reach_atoms_ratio_min: float | None
    reach_facts_ratio_min: float | None
    is_smallest_atoms: bool
    is_smallest_facts: bool
    is_smallest_reach_atoms: bool
    is_smallest_reach_facts: bool
    open_params: int | None
    pinned_params: int | None
    pairs_separating: int | None
    pairs_undefined: int | None
    separation_classes: int | None


FIELDS = tuple(f.name for f in fields(CaseFeatures))


@dataclass
class FileFeatures:
    stem: str
    cases: list[CaseFeatures] = field(default_factory=list)
    separates: Matrix | None = None


# --- cases ---

def _components(program: Program) -> list[list[str]]:
    """The branch sets `Choice` ranges over: its own branches, or the
    branches of each field type of a record `Choice`, in field order."""
    types = {it.name: it for it in program.items if isinstance(it, TypeDecl)}
    choice = types.get("Choice")
    if choice is None:
        return []
    if choice.branches:
        return [list(choice.branches)]
    return [list(t.branches)
            for name in _record_fields(program.items).get("Choice", [])
            if (t := types.get(name)) and t.branches]


def _case_names(components: list[list[str]]) -> list[CaseId]:
    if not components:
        return []
    if len(components) == 1:
        return [CaseId(c) for c in components[0]]
    return [CaseId(f"[{', '.join(combo)}]")
            for combo in product(*components)]


HELD_DIRECTIVES = ".input in(IO=stdin)\n.output impl_choice(IO=stdout)\n"


def _declares_held(program: Program) -> bool:
    return any(isinstance(it, Decl) and it.name == "impl_choice"
               for it in program.items)


def declares_held(source: str) -> bool:
    """`source` declares a top-level `impl_choice`, so the cases it holds
    are the ones that relation holds."""
    try:
        return _declares_held(parse(source))
    except ParseError:
        return False


def held_cases(program: Program, source: str,
               grid: list[list[int]] | None = None,
               full: bool = False) -> list[CaseId] | None:
    """The case labels `impl_choice` holds when `source` runs on `grid`, in
    the order Souffle writes them; None when the program declares no
    top-level `impl_choice`. `full` spells each case with its constructors'
    fields, as `dl.models.model_label` does, in place of the runner's label.

    The relation is read from a run, since a solver may state it by facts
    or by a rule over per-field enumerators, and a run gives its contents in
    either form. A case that emits nothing on the grid is still held.
    """
    if not _declares_held(program):
        return None
    stdout = _run_source(f"{expand_macros(source)}\n{HELD_DIRECTIVES}",
                         grid_to_facts(grid or []))
    rows = _parse_relations(stdout).get("impl_choice", [])
    spell = model_label if full else case_label
    cases: list[CaseId] = []
    for row in rows:
        if (label := spell(row)) not in cases:
            cases.append(label)
    return cases


HELD_INPUT_CAT = "held input"
"""The lint category of an `impl_choice` whose rows depend on the input."""


def held_input_findings(task_id: str,
                        source: str) -> list[tuple[str, int, str, str]]:
    """A lint finding, as `dl.lint.lint_program` gives one, when the rows
    `impl_choice` holds on the empty input differ from its rows on a train
    input of the task. `grid --all` and `features` read the rows on the
    empty input, and `run` reads them per pair. No finding stands when
    the program declares no `impl_choice`, when the task is not materialized,
    or when a run fails."""
    from arc.task import load as load_task

    try:
        program = parse(source)
        decl = next((it for it in program.items
                     if isinstance(it, Decl) and it.name == "impl_choice"),
                    None)
        if decl is None:
            return []
        task = load_task(task_id)
        empty = set(held_cases(program, source, full=True) or [])
        differ = [i for i, ex in enumerate(task.train)
                  if set(held_cases(program, source, ex.input, full=True)
                         or []) != empty]
    except (ParseError, FileNotFoundError, RuntimeError,
            subprocess.TimeoutExpired):
        return []
    if not differ:
        return []
    names = ", ".join(str(i) for i in differ)
    text = (mctx("`impl_choice` holds other cases on train input {inputs} "
                 "than on the empty input, which `grid --all` and "
                 "`features` read").format(inputs=names)
            if len(differ) == 1 else
            mctx("`impl_choice` holds other cases on train inputs {inputs} "
                 "than on the empty input, which `grid --all` and "
                 "`features` read").format(inputs=names))
    lines = source.splitlines()
    raw = lines[decl.line - 1] if 0 < decl.line <= len(lines) else ""
    return [(HELD_INPUT_CAT, decl.line, text, raw)]


def case_branches(stem: str, source: str | None = None,
                  grid: list[list[int]] | None = None) -> list[CaseId]:
    """The case names of one solver, empty for a solver with no `Choice`.

    `source` stands in for the solver's file, as a reassigned source does,
    and `grid` is the grid the run sees. A solver that declares
    `impl_choice` has the cases a run on `grid` finds it holding; another
    has the cases its `Choice` type states. A run is seeded with them, so a
    case that emits nothing is still reported; the grid command reads them
    the same way."""
    try:
        if source is None:
            source = solver_file(stem)[0].read_text()
        program = parse(source)
    except (OSError, ParseError):
        return []
    held = held_cases(program, source, grid)
    if held is not None:
        return held
    return _case_names(_components(program))


def _matches(case: CaseId, ctor: str) -> bool:
    """Whether `ctor` names `case`. A case named as a record (`[Table,
    Or]`) is named by any of its members, and a case spelled with its
    constructors' fields (`Recolor(Box, Size)`) by any constructor it
    takes."""
    if case == ctor:
        return True
    if case == NO_CHOICE:
        return False
    return ctor in re.findall(r"\w+", case)


# --- the rule graph ---

GRID_TARGET_RE = re.compile(r"GRID_\w+\(\s*(\w+)")


@dataclass
class RuleNode:
    """One rule of the file: where it stands, the relation it heads, and the
    relations it reads."""
    scope: str
    rule: Rule
    head: RelKey
    reads: set[RelKey]


def _ctors(terms) -> set[str]:
    """Every constructor name in a rule head's terms."""
    return {name for t in terms for name in _ctor_names(t)}


def _chart_rules(items, scope: str = TOP) -> list[tuple[str, str, Rule]]:
    """The fact rules inside RIGID blocks, each with its scope and its
    block name. The index leaves them out, and the placed relation carries
    the block name as a prefix."""
    out: list[tuple[str, str, Rule]] = []
    for it in items:
        if isinstance(it, Comp):
            out.extend(_chart_rules(it.items, it.name))
        elif isinstance(it, Rigid):
            out.extend((scope, it.name, r)
                       for r in it.items if isinstance(r, Rule))
    return out


def _nodes(index: Index, lines: list[str]) -> list[RuleNode]:
    """Every rule of the file as a node of the dependency graph.

    A GRID macro fact heads the relation its first argument names; the
    parser keeps the call opaque, so that name is read off the source line.
    A RIGID chart fact heads the placed relation its block exposes.
    """
    heads: dict[int, RelKey] = {}
    reads: list[set[RelKey]] = [set() for _ in index.rules]
    for ref in index.refs:
        if ref.role == "head":
            heads[ref.rule] = ref.key
        else:
            reads[ref.rule].add(ref.key)

    nodes: list[RuleNode] = []
    for i, info in enumerate(index.rules):
        key = heads.get(i, (EXTERN, info.rule.head.name))
        if info.rule.grid:
            found = GRID_TARGET_RE.search(lines[info.rule.line - 1])
            if found:
                key = index.resolve(info.scope, None, found.group(1))
        nodes.append(RuleNode(info.scope, info.rule, key, reads[i]))
    for scope, block, rule in _chart_rules(index.program.items):
        placed = index.resolve(scope, None, f"{block}_{rule.head.name}")
        nodes.append(RuleNode(scope, rule, placed, set()))
    return nodes


def _instance(key: RelKey) -> str | None:
    """The lib instance a relation key names, None for a relation the file
    declares. The instance's inputs feed all its outputs, so every relation
    of one instance stands for the instance as a whole."""
    scope, name = key
    if scope != EXTERN or "." not in name:
        return None
    return name.split(".", 1)[0]


def _reach(nodes: list[RuleNode], cases: list[CaseId]) -> Reach:
    """The rules each case reaches.

    A rule belongs to a case when its head holds only constructors that
    case owns: a top-level such rule seeds the case, and a reached one joins
    it, so a case never reaches another case's branch. From the seeds the
    reach follows the relations a rule reads to the rules that head them,
    across every scope the file declares, and a read of one lib instance
    reaches every rule that feeds the instance.
    """
    producers: dict[RelKey, list[int]] = {}
    by_instance: dict[str, list[int]] = {}
    for i, node in enumerate(nodes):
        producers.setdefault(node.head, []).append(i)
        if (inst := _instance(node.head)) is not None:
            by_instance.setdefault(inst, []).append(i)

    held = [{c for c in _ctors(n.rule.head.args)
             if any(_matches(case, c) for case in cases)} for n in nodes]
    seeded = any(held)

    def owns(case: CaseId, i: int) -> bool:
        return all(_matches(case, c) for c in held[i])

    out: Reach = {}
    for case in cases:
        if seeded:
            front = [i for i, n in enumerate(nodes)
                     if n.scope == TOP and held[i] and owns(case, i)]
        else:
            # No case constructor stands anywhere: the file is one case, and
            # what `out` reaches is the whole of it.
            front = [i for i, n in enumerate(nodes)
                     if n.scope == TOP and n.rule.head.name == "out"]
        found = set(front)
        while front:
            targets: list[int] = []
            for key in nodes[front.pop()].reads:
                targets.extend(producers.get(key, ()))
                if (inst := _instance(key)) is not None:
                    targets.extend(by_instance.get(inst, ()))
            for t in targets:
                if t not in found and owns(case, t):
                    found.add(t)
                    front.append(t)
        out[case] = found
    return out


# --- per-rule measures ---

def _shape_counts(rule: Rule) -> dict[str, int]:
    """The negations, disjunctions, aggregates and comparisons one rule
    holds, aggregate bodies and disjunction branches included."""
    counts = {"negations": 0, "disjunctions": 0,
              "aggregates": 0, "comparisons": 0}

    def walk_terms(terms) -> None:
        for agg in _aggs_in_terms(terms):
            counts["aggregates"] += 1
            walk_lits(agg.body)
            if agg.expr is not None:
                walk_terms((agg.expr,))

    def walk_lits(lits) -> None:
        for lit in lits:
            if isinstance(lit, Atom):
                walk_terms(lit.args)
            elif isinstance(lit, Neg):
                counts["negations"] += 1
                walk_terms(lit.atom.args)
            elif isinstance(lit, Cmp):
                counts["comparisons"] += 1
                walk_terms((lit.lhs, lit.rhs))
            elif isinstance(lit, Disj):
                counts["disjunctions"] += 1
                walk_lits([sub for b in lit.branches for sub in b])

    walk_lits(rule.body or ())
    walk_terms(rule.head.args)
    return counts


def _lib_hits(index: Index, node: RuleNode) -> set[tuple[str, str]]:
    """The lib instances one rule reaches, each as (instance, comp)."""
    atoms = [node.rule.head]
    for lit in body_literals(node.rule):
        if isinstance(lit, Atom):
            atoms.append(lit)
        elif isinstance(lit, Neg):
            atoms.append(lit.atom)
    return {found for atom in atoms
            if (found := index.instance_of(node.scope, atom.qual)) is not None}


# --- the report ---

def _ratio(value: int, smallest: int) -> float | None:
    """How this case stands against the smallest case of its file. A
    smallest of zero measures nothing, and gives no ratio."""
    if value == smallest:
        return 1.0
    if smallest == 0:
        return None
    return value / smallest


def _weigh(rules: list[Rule]) -> dict[str, int]:
    out = {
        "atoms": sum(rule_literals(r) for r in rules),
        "rules": sum(1 for r in rules if r.body is not None),
        "facts": sum(1 for r in rules if r.body is None),
        "negations": 0, "disjunctions": 0, "aggregates": 0, "comparisons": 0,
    }
    for r in rules:
        for k, v in _shape_counts(r).items():
            out[k] += v
    return out


def features_report(
    stem: str,
    params: tuple[int, int] | None = None,
    dynamic: RunReport | None = None,
) -> FileFeatures:
    """One solver's per-case features.

    `params` holds the open and pinned parameter counts a cached sweep
    reports, None when no fresh cache stands. `dynamic` holds a
    `dl.features_run.RunReport`, None when no run was asked for.
    """
    path = solver_file(stem)[0]
    name = path.stem
    source = path.read_text()
    program = parse(source)
    index = Index(program)
    nodes = _nodes(index, source.splitlines())
    cases = held_choice(source, case_space(source)) or [NO_CHOICE]
    reach = _reach(nodes, cases)

    reached = {i for found in reach.values() for i in found}
    shared_idx = {i for i in reached
                  if sum(i in found for found in reach.values()) > 1}

    def rules_at(idxs) -> list[Rule]:
        return [nodes[i].rule for i in idxs]

    whole = {c: _weigh(rules_at(found)) for c, found in reach.items()}
    own = {c: _weigh(rules_at(found - shared_idx))
           for c, found in reach.items()}
    shared = _weigh(rules_at(shared_idx))
    unreached = _weigh(rules_at(set(range(len(nodes))) - reached))

    libs = {c: {hit for i in found for hit in _lib_hits(index, nodes[i])}
            for c, found in reach.items()}

    smallest = {key: min(own[c][key] for c in cases)
                for key in ("atoms", "facts")}
    reach_smallest = {key: min(whole[c][key] for c in cases)
                      for key in ("atoms", "facts")}
    open_n, pinned_n = params if params is not None else (None, None)

    rows: list[CaseFeatures] = []
    for i, case in enumerate(cases):
        m, w = own[case], whole[case]
        rows.append(CaseFeatures(
            stem=name,
            case=case,
            case_index=i,
            cases_in_file=len(cases),
            atoms=m["atoms"],
            shared_atoms=shared["atoms"],
            rules=m["rules"],
            shared_rules=shared["rules"],
            facts=m["facts"],
            shared_facts=shared["facts"],
            reach_atoms=w["atoms"],
            reach_rules=w["rules"],
            reach_facts=w["facts"],
            unreached_atoms=unreached["atoms"],
            negations=w["negations"],
            disjunctions=w["disjunctions"],
            aggregates=w["aggregates"],
            comparisons=w["comparisons"],
            lib_instances=len(libs[case]),
            distinct_lib_units=len({comp for _, comp in libs[case]}),
            atoms_ratio_min=_ratio(m["atoms"], smallest["atoms"]),
            facts_ratio_min=_ratio(m["facts"], smallest["facts"]),
            reach_atoms_ratio_min=_ratio(w["atoms"], reach_smallest["atoms"]),
            reach_facts_ratio_min=_ratio(w["facts"], reach_smallest["facts"]),
            is_smallest_atoms=m["atoms"] == smallest["atoms"],
            is_smallest_facts=m["facts"] == smallest["facts"],
            is_smallest_reach_atoms=w["atoms"] == reach_smallest["atoms"],
            is_smallest_reach_facts=w["facts"] == reach_smallest["facts"],
            open_params=open_n,
            pinned_params=pinned_n,
            pairs_separating=dynamic.separating.get(case) if dynamic else None,
            pairs_undefined=dynamic.undefined.get(case) if dynamic else None,
            separation_classes=dynamic.classes if dynamic else None,
        ))
    return FileFeatures(stem=name, cases=rows,
                        separates=dynamic.separates if dynamic else None)


def _cell(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def render_features(files: list[FileFeatures]) -> list[str]:
    """The report as TSV, one header row and one row per case."""
    lines = ["\t".join(FIELDS)]
    for f in files:
        for row in f.cases:
            lines.append("\t".join(_cell(getattr(row, name)) for name in FIELDS))
    return lines


def features_json(files: list[FileFeatures],
                  skipped: list[dict[str, str]]) -> dict:
    """The report as JSON: the same rows per solver, each solver with the
    pairwise matrix of the pairs that separate two of its cases, and the
    solvers left out with the reason each was."""
    return {
        "solvers": [
            {"stem": f.stem,
             "cases": [asdict(row) for row in f.cases],
             "separates": f.separates}
            for f in files
        ],
        "skipped": skipped,
    }
