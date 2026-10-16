"""The lint: one check per lint category, each reading the parsed program,
and their composition, which applies the solver's `@ignore` lines
(solver-file.md, under "Program")."""

from collections.abc import Callable, Sequence
from dataclasses import replace

from checker.finding import (
    LINT_SHAPES,
    AtLine,
    Finding,
    Kind,
    LintBranchForm,
    LintFragment,
    LintIgnore,
    LintNamed,
    LintPayload,
    LintSentence,
    is_hint,
    line_of,
)
from checker.judged import (
    concept_among,
    parse_failure,
    reading_names,
)
from checker.lint import (
    bans,
    constants,
    heads,
    idioms,
    names,
    recursion,
    rewrites,
    style,
)
from checker.lint.form import (
    case_type,
    components,
    declared_types,
    open_value_fields,
    header,
    prediction,
    sections,
    witnesses,
)
from checker.lint.view import TOP, View, lint, spanned, view
from checker.runs import Runs
from engine import Resolved
from engine.program import (
    Component,
    Instance,
    RelationDecl,
    RelationName,
    Scope,
    own,
)
from engine.quotes import quotes
from solver.annotations import IgnoreForm, IgnoreLine
from solver.category import HINTS, Category
from solver.model import bases_of
from solver.aggregate import Solver
from solver.dependence import dependence, dependent_bases

type Check = Callable[[Solver, Runs], list[Finding]]

PROGRAM_CHECKS: tuple[Check, ...] = (
    case_type.check_family_case, case_type.check_case_marker, witnesses.check_witness,
    header.check_header, header.check_keyword,
    header.check_demonstrated_choice, names.check_rigid_chart,
    bans.check_orientation_literal, bans.check_nonzero_literal,
    bans.check_arithmetic, bans.check_range, bans.check_ord,
    recursion.check_recursion,
    names.check_reserved_name,
    names.check_shadowed_type, names.check_lib_name,
    names.check_lib_internal, names.check_enumerator_name,
    components.check_lib_code,
    components.check_parse_unshared_with_determine,
    components.check_determine_schema, prediction.check_determine_prediction,
    declared_types.check_banned_type,
    open_value_fields.check_open_value_field,
    case_type.check_gloss, declared_types.check_unread_field, sections.check_case_section,
    sections.check_case_section_read,
    witnesses.check_claim, witnesses.check_one_case, bans.check_params_data,
)
"""The checks on the solver's form and its bans."""

REWRITE_CHECKS: tuple[Check, ...] = (
    rewrites.check_dead, rewrites.check_alias_inline,
    rewrites.check_negated_use, style.check_choice_domain,
    style.check_shared_read, rewrites.check_choice_tag,
    bans.check_typed_order, rewrites.check_cross_choice,
    bans.check_raw_aggregate, rewrites.check_subsumed_atom,
    rewrites.check_named_complement, rewrites.check_negated_value,
    bans.check_long_clause, style.check_decl_placement, rewrites.check_pass_through,
    rewrites.check_chain_join, rewrites.check_single_consumer,
    rewrites.check_argmax, constants.check_const_join,
    rewrites.check_comp_idiom, idioms.check_lib_idiom,
    idioms.check_domain_enumerator,
    rewrites.check_common_subexpr,
    heads.check_head_zero, heads.check_head_repeat,
)
"""The checks on shapes the corpus's edits rewrite away."""

def _category(f: Finding) -> Category:
    p = f.payload
    assert isinstance(p, LINT_SHAPES)
    return p.category


def _sorted(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: (line_of(f), _category(f).value))


# `@ignore` lines


type Site = tuple[int, RelationName | None]
"""A place an `@ignore` line on a relation stands above: the line of its
`.decl` with no name, and for a relation of an instance, the line
of the instance's `.init` with the relation's name in that instance."""


def _extends(v: View, inst: Instance, comp: Component | None) -> bool:
    """Whether `inst` is an instance of `comp` or of a component that
    extends it (`Index.chain`)."""
    of = v.index.component(inst.component, inst.scope)
    return comp is not None and of is not None and comp in v.index.chain(of)


def _instance_sites(v: View, scope: Scope, rel: RelationName,
                    depth: int = 0) -> list[Site]:
    """The places an `@ignore` line above an `.init` stands on the
    relation `rel` of the component `scope` names: the `.init` of each
    instance of it, or of a component that extends it, and for an
    instance inside another component, that component's instances in
    turn."""
    if scope == TOP or depth > len(v.own_instances):
        return []
    comp = v.index.component(scope.components[-1],
                             Scope(scope.components[:-1]))
    out: list[Site] = []
    for i in v.own_instances:
        if _extends(v, i, comp):
            out.append((spanned(i.span).first, rel))
            out += _instance_sites(v, i.scope, RelationName(
                (i.name, *rel.instances), rel.name), depth + 1)
    return out


def owners(v: View) -> dict[int, list[frozenset[Site]]]:
    """Per solver line that belongs to a relation, the relations it
    belongs to, each as the places an `@ignore` line on it stands above.
    A line of a component's text belongs to the relation in each instance
    of the component; the `.init` line belongs to the instance."""
    return v.held(_owners)


def _owners(v: View) -> dict[int, list[frozenset[Site]]]:
    out: dict[int, list[frozenset[Site]]] = {}

    def claim(first: int, last: int, sites: list[Site]) -> None:
        for n in range(first, last + 1):
            out.setdefault(n, []).append(frozenset(sites))

    for d in v.own_relations:
        claim(d.span.first, d.span.last, [(d.span.first, None), *_instance_sites(
            v, d.scope, d.scoped_name)])
    for i in v.own_instances:
        claim(spanned(i.span).first, spanned(i.span).first,
              [(spanned(i.span).first, None)])
    for u in v.own_units:
        if u.span is None:
            continue
        sites: list[Site] = []
        head = u.head.relation
        r = v.index.resolve(head, u.scope)
        d = v.decls.get(r.declaration) if isinstance(r, Resolved) else None
        if isinstance(d, RelationDecl) and own(d.span):
            sites.append((d.span.first, None))
            if not head.instances:
                sites += _instance_sites(v, d.scope, d.scoped_name)
        if head.instances and isinstance(r, Resolved) and r.through:
            inst = v.decls.get(r.through[0])
            if isinstance(inst, Instance) and own(inst.span):
                sites.append((spanned(inst.span).first,
                              RelationName(head.instances[1:], head.name)))
        if sites:
            claim(u.span.first, u.span.last, sites)
    return out


def _at(v: View, ig: IgnoreLine) -> int | None:
    """The line of the `.decl` or `.init` an `@ignore` line stands on;
    None where it stands on neither, or states a relation above a
    `.decl`."""
    if ig.above is None:
        return None
    d = v.decls.get(ig.above)
    if isinstance(d, RelationDecl):
        return None if ig.relation else d.span.first
    if isinstance(d, Instance):
        return d.span.first if d.span is not None else None
    return None


def _matching(v: View, ignores: Sequence[IgnoreLine], category: Category,
              sites: frozenset[Site]) -> list[IgnoreLine]:
    return [ig for ig in ignores
            if ig.category == category and (at := _at(v, ig)) is not None
            and any(at == s_at and (ig.relation is None or (
                rel is not None and ig.relation == rel.text))
                    for s_at, rel in sites)]


def _site(v: View, ig: IgnoreLine) -> RelationName | None:
    """The relation an `@ignore` line stands on: the `.decl`'s, or the
    instance's relation the line names, or the instance."""
    d = v.decls.get(ig.above) if ig.above is not None else None
    if isinstance(d, Instance):
        return RelationName((d.name,), ig.relation) if ig.relation \
            else RelationName((), d.name)
    return d.scoped_name if isinstance(d, RelationDecl) else None


def _idle(v: View, ig: IgnoreLine) -> Finding:
    """The finding on an `@ignore` line that dismisses no finding: one
    whose category gives lint findings, which no `@ignore` line dismisses,
    or one that stands where no hint of its category fires."""
    if ig.category not in HINTS:
        sentence = LintSentence.IGNORE_ON_LINT
    elif _at(v, ig) is not None:
        sentence = LintSentence.IDLE_IGNORE
    elif ig.above is not None and isinstance(v.decls.get(ig.above),
                                             RelationDecl):
        sentence = LintSentence.IGNORE_ON_DECL
    else:
        sentence = LintSentence.IGNORE_UNPLACED
    return lint(ig.line, LintIgnore(Category.IGNORE, sentence, ig,
                                    _site(v, ig)))


BANNED_FORMS = frozenset({
    Category.ARITHMETIC, Category.RAW_AGGREGATE, Category.RANGE,
    Category.ORD, Category.NONZERO_LITERAL, Category.ORIENTATION_LITERAL,
})
"""The categories of the banned forms (style.md, under "Bans")."""


def _branch_forms(solver: Solver, runs: Runs, findings: list[Finding]
                  ) -> list[Finding]:
    """Each banned-form finding whose units some case reads and
    no derivation of the concept case reads (`solver.dependence.dependence`),
    as a `LintBranchForm` naming the relations the line feeds and, through
    `cover`, the cases that read them; the others as given. Nothing is
    judged where the run that enumerates the solver's cases gives no
    result."""
    banned = [f for f in findings
              if f.kind == Kind.LINT and _category(f) in BANNED_FORMS
              and isinstance(f.payload, (LintFragment, LintNamed))]
    every = runs.solver_cases
    if not banned or not isinstance(every, tuple):
        return findings
    bases = bases_of(every)
    rd = dependence(runs.engine, solver, bases)
    by_id = {u.id: u for u in solver.program.units}
    out: list[Finding] = []
    for f in findings:
        p = f.payload
        if f not in banned or not isinstance(p, (LintFragment, LintNamed)) \
                or not isinstance(f.where, AtLine):
            out.append(f)
            continue
        units = [by_id[i] for i in f.where.units]
        reading = dependent_bases(rd, (u.id for u in units))
        if not reading or concept_among(solver, reading) is not None:
            out.append(f)
            continue
        rels = tuple(dict.fromkeys(u.head.relation for u in units))
        out.append(replace(f, payload=LintBranchForm(
            p.category, p, rels, reading_names(solver, every, reading))))
    return out


def _with_relation(f: Finding, on: bool) -> Finding:
    p = f.payload
    assert isinstance(p, LINT_SHAPES)
    payload: LintPayload = replace(p, on_relation=on)
    return replace(f, payload=payload)


@quotes("solver-file.md", "Program",
        "A relation kept despite a hint has `// @ignore: <category> — "
        "<reason>`, with the category the hint gives, in the run of "
        "`@ignore` lines directly above its declaration.")
@quotes("solver-file.md", "Program",
        "The hint does not fire on the relation.")
@quotes("style.md", "Program",
        "The gloss of a relation that carries an `@ignore` directive is in a "
        "separate comment immediately above its `@ignore` lines.")
def check_lint(solver: Solver, runs: Runs) -> list[Finding]:
    """Every lint finding and hint of the solver, less the hints an
    `@ignore` line of their category on their relation dismisses, with a
    finding on each `@ignore` line that dismisses none. An
    `@ignore` line of a category that gives lint findings dismisses
    nothing, and is a lint finding at its line. A hint on a line of more
    than one relation stays unless each of them carries such a line. A
    banned-form finding on a line no derivation of the concept case reads
    names the cases that read it (`_branch_forms`). The findings come in
    this order: the form checks, the idle `@ignore` lines, the rewrite
    checks, then the hints. A solver that does not parse gives none: `fault_findings`
    reports the failure, and no line of it is known to belong to a
    relation.
    It is the composition of the lint checks, each of which names what it
    serves."""
    if parse_failure(solver) is not None:
        return []
    v = view(solver, runs)
    program = _branch_forms(solver, runs, _sorted(
        [f for c in PROGRAM_CHECKS for f in c(solver, runs)]))
    rewrite = _branch_forms(solver, runs, _sorted(
        [f for c in REWRITE_CHECKS for f in c(solver, runs)]))
    every = program + rewrite
    sites_at = owners(v)
    lines = [ig for ig in solver.annotations.ignores
             if ig.form == IgnoreForm.LINT]
    ignores = [ig for ig in lines
               if ig.category is not None and ig.category in HINTS]
    used = {ig.line for f in every for sites in sites_at.get(line_of(f), [])
            for ig in _matching(v, ignores, _category(f), sites)}
    idle = [_idle(v, ig) for ig in lines
            if ig not in ignores or ig.line not in used]

    def dismissed(f: Finding) -> bool:
        sites = sites_at.get(line_of(f), [])
        return bool(sites) and all(
            _matching(v, ignores, _category(f), s) for s in sites)

    def kept(fs: list[Finding]) -> list[Finding]:
        return [_with_relation(f, bool(sites_at.get(line_of(f))))
                for f in fs if not dismissed(f)]

    lints = [f for f in program if f.kind == Kind.LINT] + idle \
        + [f for f in rewrite if f.kind == Kind.LINT]
    hints = [f for f in program if is_hint(f)] \
        + [f for f in rewrite if is_hint(f)]
    return kept(lints) + kept(hints)
