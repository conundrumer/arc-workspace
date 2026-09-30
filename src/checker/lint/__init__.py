"""The lint: one check per lint category, each reading the parsed program,
and their composition, which applies the solver's `@ignore` lines
(solver-file.md:134-136)."""

from collections.abc import Callable, Sequence
from dataclasses import replace

from checker.finding import (
    AtLine,
    Finding,
    Kind,
    LINT_SHAPES,
    LintIgnore,
    LintPayload,
    LintSentence,
)
from checker.lint import bans, form, idioms, names, rewrites
from checker.lint.view import TOP, View, lint, owned, spanned, view
from checker.runs import Runs
from engine import Resolved
from engine.program import Instance, RelationDecl, RelationName, Scope
from solver.annotations import IgnoreForm, IgnoreLine
from solver.category import Category
from solver.model import Solver
from solver.problems import ProblemKind

type Check = Callable[[Solver, Runs], list[Finding]]

PROGRAM_CHECKS: tuple[Check, ...] = (
    form.check_family_case, form.check_case_marker, form.check_witness,
    form.check_header, form.check_keyword, names.check_rigid_chart,
    bans.check_orientation_literal, bans.check_nonzero_literal,
    bans.check_arithmetic, bans.check_range, names.check_reserved_name,
    names.check_shadowed_type, names.check_lib_name,
    names.check_lib_internal, form.check_comp_without_entry,
    form.check_parse_unshared_with_determine, form.check_banned_type,
    form.check_gloss, form.check_unread_field, form.check_case_section,
    form.check_case_section_read,
    form.check_claim, form.check_one_case, bans.check_params_data,
)
"""The checks on the solver's form and its bans."""

REWRITE_CHECKS: tuple[Check, ...] = (
    rewrites.check_dead, rewrites.check_alias_inline,
    rewrites.check_negated_use, rewrites.check_choice_domain,
    rewrites.check_shared_read, rewrites.check_choice_tag,
    bans.check_typed_order, rewrites.check_cross_choice,
    bans.check_raw_aggregate, rewrites.check_subsumed_atom,
    rewrites.check_named_complement, rewrites.check_negated_value,
    bans.check_long_clause, rewrites.check_decl_placement, rewrites.check_pass_through,
    rewrites.check_chain_join, rewrites.check_single_consumer,
    rewrites.check_argmax, rewrites.check_const_join,
    rewrites.check_comp_idiom, idioms.check_domain_enumerator,
    rewrites.check_common_subexpr,
)
"""The checks on shapes the corpus's edits rewrite away."""

def _line(f: Finding) -> int:
    return f.where.line if isinstance(f.where, AtLine) else 0


def _category(f: Finding) -> Category:
    p = f.payload
    assert isinstance(p, LINT_SHAPES)
    return p.category


def _sorted(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: (_line(f), _category(f).value))


# `@ignore` lines


type Site = tuple[int, str | None]
"""A place an `@ignore` line on a relation stands above: the line of its
`.decl` with no name, and for a relation of an instance, the line
of the instance's `.init` with the relation's name in that instance."""


def _extends(v: View, comp: str, base: str) -> bool:
    seen: set[str] = set()
    while comp not in seen:
        if comp == base:
            return True
        seen.add(comp)
        c = v.components.get(comp)
        if c is None or c.base is None:
            return False
        comp = c.base
    return False


def _instance_sites(v: View, scope: Scope, rel: str, depth: int = 0
                    ) -> list[Site]:
    """The places an `@ignore` line above an `.init` stands on the
    relation `rel` of the component `scope` names: the `.init` of each
    instance of it, or of a component that extends it, and for an
    instance inside another component, that component's instances in
    turn."""
    if scope == TOP or depth > len(v.own_instances):
        return []
    comp = scope.components[-1]
    out: list[Site] = []
    for i in v.own_instances:
        if _extends(v, i.component, comp):
            out.append((spanned(i.span).first, rel))
            out += _instance_sites(v, i.scope, f"{i.name}.{rel}", depth + 1)
    return out


def owners(v: View) -> dict[int, list[frozenset[Site]]]:
    """Per solver line that belongs to a relation, the relations it
    belongs to, each as the places an `@ignore` line on it stands above.
    A line of a component's text belongs to the relation in each instance
    of the component; the `.init` line belongs to the instance."""
    memo = v.memo.get("owners")
    if isinstance(memo, dict):
        return memo  # type: ignore[return-value]
    out: dict[int, list[frozenset[Site]]] = {}

    def own(first: int, last: int, sites: list[Site]) -> None:
        for n in range(first, last + 1):
            out.setdefault(n, []).append(frozenset(sites))

    for d in v.own_relations:
        own(d.span.first, d.span.last, [(d.span.first, ""),
                                        *_instance_sites(v, d.scope, d.name)])
    for i in v.own_instances:
        own(spanned(i.span).first, spanned(i.span).first, [(spanned(i.span).first, "")])
    for u in v.own_units:
        if u.span is None:
            continue
        sites: list[Site] = []
        head = u.head.relation
        r = v.index.resolve(head, u.scope)
        d = v.decls.get(r.declaration) if isinstance(r, Resolved) else None
        if isinstance(d, RelationDecl) and d.span.file is None:
            sites.append((d.span.first, None))
            if not head.instances:
                sites += _instance_sites(v, d.scope, d.name)
        if head.instances and isinstance(r, Resolved) and r.through:
            inst = v.decls.get(r.through[0])
            if isinstance(inst, Instance) and owned(inst.span):
                sites.append((spanned(inst.span).first,
                              RelationName(head.instances[1:], head.name).text))
        if sites:
            own(u.span.first, u.span.last, sites)
    v.memo["owners"] = out
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
            and any(at == s_at and ig.relation in (None, rel)
                    for s_at, rel in sites)]


def _site(v: View, ig: IgnoreLine) -> RelationName | None:
    """The relation an `@ignore` line stands on: the `.decl`'s, or the
    instance's relation the line names, or the instance."""
    d = v.decls.get(ig.above) if ig.above is not None else None
    if isinstance(d, Instance):
        return RelationName((d.name,), ig.relation) if ig.relation \
            else RelationName((), d.name)
    return RelationName((), d.name) if isinstance(d, RelationDecl) else None


def _idle(v: View, ig: IgnoreLine) -> Finding:
    """The finding on an `@ignore` line that dismisses no finding."""
    if _at(v, ig) is not None:
        sentence = LintSentence.IDLE_IGNORE
    elif ig.above is not None and isinstance(v.decls.get(ig.above),
                                             RelationDecl):
        sentence = LintSentence.IGNORE_ON_DECL
    else:
        sentence = LintSentence.IGNORE_UNPLACED
    return lint(ig.line, LintIgnore(Category.IGNORE, sentence, ig,
                                    _site(v, ig)))


def _with_relation(f: Finding, on: bool) -> Finding:
    p = f.payload
    assert isinstance(p, LINT_SHAPES)
    payload: LintPayload = replace(p, on_relation=on)
    return replace(f, payload=payload)


def check_lint(solver: Solver, runs: Runs) -> list[Finding]:
    """Every lint finding and hint of the solver, less those an `@ignore`
    line of their category on their relation dismisses, with a finding
    on each `@ignore` line that dismisses none (solver-file.md:134 "A
    relation kept despite a finding has `// @ignore: <category> —
    <reason>` on the line immediately above its declaration", :135 "The
    finding does not fire on the relation", :136; history 1143, 1147). A
    finding on a line of more than one relation stays unless each of them
    carries such a line. The findings come in the old report's order:
    the form checks, the idle `@ignore` lines, the rewrite checks, then
    the hints. A solver that does not parse gives none: `check_faults`
    reports the failure, and no line of it is known to belong to a
    relation."""
    if any(p.kind == ProblemKind.PARSE_FAILURE for p in solver.problems):
        return []
    v = view(solver, runs)
    program = _sorted([f for c in PROGRAM_CHECKS for f in c(solver, runs)])
    rewrite = _sorted([f for c in REWRITE_CHECKS for f in c(solver, runs)])
    every = program + rewrite
    sites_at = owners(v)
    ignores = [ig for ig in solver.annotations.ignores
               if ig.form == IgnoreForm.LINT]
    used = {ig.line for f in every for sites in sites_at.get(_line(f), [])
            for ig in _matching(v, ignores, _category(f), sites)}
    idle = [_idle(v, ig) for ig in ignores
            if ig.line not in used]

    def dismissed(f: Finding) -> bool:
        sites = sites_at.get(_line(f), [])
        return bool(sites) and all(
            _matching(v, ignores, _category(f), s) for s in sites)

    def kept(fs: list[Finding]) -> list[Finding]:
        return [_with_relation(f, bool(sites_at.get(_line(f))))
                for f in fs if not dismissed(f)]

    lints = [f for f in program if f.kind == Kind.LINT] + idle \
        + [f for f in rewrite if f.kind == Kind.LINT]
    hints = [f for f in program if f.kind == Kind.HINT] \
        + [f for f in rewrite if f.kind == Kind.HINT]
    return kept(lints) + kept(hints)
