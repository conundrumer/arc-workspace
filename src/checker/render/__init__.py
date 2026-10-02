"""The one rendering module: every command's text. Each survey result type
gets one render function of its own here, beside `render`; a survey's
result holds its own timed-out and failed runs, and its render function
prints them."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import NoReturn

from checker.finding import (
    FAILING,
    LINT_SHAPES,
    AtCase,
    AtEntry,
    AtFile,
    AtLine,
    AtPair,
    AtParameter,
    AtRelation,
    Code,
    FaultPayload,
    Finding,
    Kind,
    LintBranchForm,
    LintCode,
    LintCounted,
    LintFamily,
    LintFragment,
    LintIgnore,
    LintLabeled,
    LintMarked,
    LintNamed,
    LintPayload,
    LintRun,
    LintSentence,
    NoResultPayload,
    RunKind,
    UndecidedPayload,
    Where,
    WholeFile,
    is_hint,
)
from checker.judged import is_timeout
from controlled_markdown import mctx
from engine import (
    CompileError,
    CpuLimit,
    Exited,
    Grid,
    GridLayout,
    ParseFailure,
    RelationName,
    RunFailure,
    UndefinedOutput,
    UngroundedVariable,
    Value,
    WallLimit,
    checkout,
)
from engine.text import text as code_text
from engine.quotes import quoted
from solver import names
from solver.annotations import (
    HEADER_RANK,
    REVIEW_WORD,
    SIBLING_DROPS,
    CaseMarker,
    DirectiveWord,
    IgnoreForm,
    MarkerPart,
    Slot,
    at_word,
    comment_text,
    derive_text,
    header_word_text,
    ignore_text,
    store_text,
)
from solver.category import HINTS, Category
from solver.model import (
    Case,
    DeriveBranch,
    Lib,
    Solver,
    solver_file,
)
from solver.problems import (
    Detail,
    AnchorWithoutStamp,
    Expected,
    GridCellOffForm,
    GridOffLayout,
    Named,
    ProblemKind,
    Quoted,
    ShapeFault,
    Storage,
    WitnessFileRole,
)
from solver.problems import (
    Undecided as UndecidedDetail,
)
from solver.solve import Grids, Outcome, PairId
from solver.witness import GroupGrid, RejectedOutput, Resolutions, Undefined


class Section(StrEnum):
    """A section of a command's report."""

    WITNESS = "witness"
    DERIVE = "derive"
    STORE = "store"
    LINT = "lint"
    DROPPED_CASES = "dropped cases"
    PAIRS = "pairs"
    DETERMINATION = "determination"


class LineForm(StrEnum):
    """How a section writes a line of the solver, as the old tool wrote it
    there."""

    FILE = "file"
    """`<stem>.dl:N`, the lint section's form."""
    LINE = "line"
    """`line N`, the form of the audit, witness, derive and store
    sections."""


def line_form(section: Section) -> LineForm:
    """The form `section` writes a line of the solver in."""
    return LineForm.FILE if section == Section.LINT else LineForm.LINE


# The pass rule


def passes(findings: Sequence[Finding]) -> bool:
    """No finding's kind is in `FAILING`: the one rule every command's
    pass line and exit code come from."""
    return not any(f.kind in FAILING for f in findings)


def exit_code(findings: Sequence[Finding]) -> int:
    """The exit code the findings give a command: 0 where they pass
    (`passes`), 1 otherwise."""
    return 0 if passes(findings) else 1


def noun(n: int, singular: str, plural: str | None = None) -> str:
    """The noun for `n` things: `singular` for one, else `plural`, which
    is `singular` with an `s` where it is not given."""
    return singular if n == 1 else (plural or f"{singular}s")


def counted(n: int, singular: str, plural: str | None = None) -> str:
    """`n` and its noun (`noun`): `1 hint`, `2 hints`."""
    return f"{n} {noun(n, singular, plural)}"


def pass_line(section: Section, findings: Sequence[Finding]) -> str | None:
    """The section's pass line, None where the findings fail (`passes`)
    and for the pairs and determination sections, which have none.
    The lint's names the hints that stand, and the witness section's the
    findings that stand and fail nothing. A section with a check that did
    not run (`NOT_CHECKED`) has none: its finding's line stands alone."""
    if not passes(findings) or section in (Section.PAIRS,
                                           Section.DETERMINATION) \
            or any(f.kind == Kind.NOT_CHECKED for f in findings):
        return None
    ok = f"{section.value}: ok"
    if section == Section.LINT:
        hints = sum(1 for f in findings if is_hint(f))
        return f"{ok}, {counted(hints, 'hint')}" if hints else ok
    if section == Section.WITNESS and findings:
        return f"{ok}, {counted(len(findings), 'non-failing finding')}"
    return ok


# Grids, values and code


class GridRow(str):
    """A line that draws a row of a grid (`grid_lines`), so that an order
    of a section's lines reads what a line draws from its type."""


def grid_lines(grid: Grid) -> list[str]:
    """A grid drawn: one row per line, cells separated by spaces."""
    if not grid or not grid[0]:
        return ["(empty)"]
    return [GridRow(" ".join(str(c) for c in row)) for row in grid]


def shifted(line: str, by: str) -> str:
    """`line` indented by `by`, a grid's row still a row (`GridRow`)."""
    return GridRow(by + line) if isinstance(line, GridRow) else by + line


def _codes(codes: Sequence[Code]) -> str:
    return ", ".join(code_text(c) for c in codes)


def _ticked(names: Sequence[str]) -> str:
    return ", ".join(f"`{n}`" for n in names)


# Cases and branches


def joined(parts: Sequence[str]) -> str:
    """The parts of one name joined as a witness file joins them,
    `<name> & <name>`
    ([Witness file](docs/handbook/solver-file.md#witness-file))."""
    return names.SEPARATOR.join(parts)


def arg_text(value: Value, type_name: str, lib: Lib) -> str:
    """One column's value: an orientation member by the constant that
    names it, any other value as the solver writes it."""
    if type_name in lib.orientation_types:
        for member in lib.orientation_types.get(type_name, ()):
            if lib.constants.get(member) == value:
                return member
    return code_text(value)



def header_line(title: str) -> str:
    """A section's header line."""
    return f"--- {title} ---"


def cases_text(solver: Solver, cases: Sequence[Case],
               among: Sequence[Case]) -> str:
    """A set of cases as every report prints one: the fewest names whose
    cases among `among` are exactly them (`solver.names.cover`)."""
    return names_text(names.cover(solver, cases, among))


def names_text(names: Sequence[str]) -> str:
    """The names that denote a set of cases, as every report prints
    them."""
    return ", ".join(names)


def case_name(solver: Solver, case: Case) -> str:
    """A case by its name for a place that asks for a model: the points
    at which it differs from the concept case (`solver.names.name`)."""
    return names.name(solver, case)


# Runs that gave no result


def failure_text(failure: RunFailure) -> str:
    """What a failed run reports, in one line."""
    match failure:
        case CompileError(line=line, message=message):
            at = "" if line is None else mctx("line {line}: ").format(
                line=line)
            return at + message
        case UngroundedVariable(variable=v, line=line):
            at = "" if line is None else mctx(" at line {line}").format(
                line=line)
            return mctx("the variable `{v}` is ungrounded{at}").format(
                v=v, at=at)
        case CpuLimit(seconds=s) | WallLimit(seconds=s):
            return mctx("the run reached its limit of {s:g}s").format(s=s)
        case UndefinedOutput(relations=rels):
            return mctx("the program declares no {rels}").format(
                rels=_ticked([r.text for r in rels]))
        case Exited(code=code, message=message):
            return mctx("the run exits with {code}: {message}").format(
                code=code, message=message)


def _limit(failure: RunFailure) -> float:
    """The limit a run reached, which a `TIMEOUT` finding's failure
    holds."""
    if not is_timeout(failure):
        raise ValueError("a run that reached no limit has no limit's seconds")
    return failure.seconds


def _no_result_lines(solver: Solver, f: Finding, p: NoResultPayload,
                     form: LineForm) -> list[str]:
    """The line of a run that gave no result: a timeout, which every
    command prints for a run a limit ended, or a failure."""
    at = where_text(solver, f.where, form)
    if f.kind == Kind.TIMEOUT:
        limit = f"{_limit(p.failure):g}"
        if p.run not in (RunKind.CASE, RunKind.PAIR, RunKind.WITNESS):
            return [mctx("{entry}: the {run} run timed out after {limit}s, "
                         "so no finding rests on its outcome").format(
                entry=at, run=p.run.value, limit=limit)]
        if p.case is not None:
            return [mctx("{entry}: case `{case}` timed out after {limit}s, "
                         "so no finding rests on its outcome there").format(
                entry=at, case=case_name(solver, p.case), limit=limit)]
        return [mctx("{entry}: the run of the solver's cases timed out "
                     "after {limit}s, so no finding rests on their outcomes "
                     "there").format(entry=at, limit=limit)]
    error = failure_text(p.failure)
    if p.run == RunKind.DROPPED_CASE:
        return [mctx("{at}: the {run} run failed: {error}").format(
            at=at, run=p.run.value, error=error)]
    if isinstance(f.where, AtEntry):
        return [mctx("the entry `{entry}` failed: {error}").format(
            entry=at, error=error)]
    if p.case is not None:
        return [mctx("{at}: case `{case}` failed: {error}").format(
            at=at, case=case_name(solver, p.case), error=error)]
    if p.run == RunKind.CASE:
        return [mctx("{at}: the run that enumerates the solver's cases "
                     "failed: {error}").format(at=at, error=error)]
    return [mctx("{at}: the {run} run failed: {error}").format(
        at=at, run=p.run.value, error=error)]


# Locations


def file_name(stem: str) -> str:
    """A solver's file by its name (`solver.model.solver_file`), as every
    line gives it."""
    return solver_file(stem).name


def file_line(stem: str, line: int) -> str:
    """A line of a solver's file, as a lint line gives it."""
    return f"{file_name(stem)}:{line}"


def solver_name(solver: Solver) -> str:
    """The solver's file, as a finding line gives it."""
    return file_name(solver.stem)


def where_text(solver: Solver, where: Where,
               form: LineForm = LineForm.LINE) -> str:
    """A finding's location as its line states it; a line of the solver
    in `form`, which is `line N` in every section but the lint's."""
    match where:
        case AtLine(line=line) if form == LineForm.FILE:
            return file_line(solver.stem, line)
        case AtLine(line=line):
            return mctx("line {n}").format(n=line)
        case AtEntry(entry=entry, assigned=False):
            return entry
        case AtEntry(entry=entry, file=role):
            return entry_label(solver, entry, role)
        case AtCase(case=case):
            return case_name(solver, case)
        case AtRelation(relation=rel):
            return rel.text
        case AtParameter(parameter=p):
            return p
        case AtPair(pair=pair):
            return pair.text
        case AtFile(file=WholeFile.SOLVER):
            return solver_name(solver)
        case AtFile():
            return mctx("the witness file")


def entry_label(solver: Solver, entry: str, role: WitnessFileRole) -> str:
    """A witness entry by its id, followed by the parameters and relations
    its `assign` reassigns, as `<id> [<name>, ...]`. An entry of a given
    file is by its id alone: the location does not hold its `assign`."""
    file = solver.witness_file
    if role != WitnessFileRole.TASK or file is None:
        return entry
    found = next((e for e in file.entries if e.id == entry), None)
    if found is None or not found.assign:
        return entry
    return f"{entry} [{', '.join(k for k, _v in found.assign)}]"


# Lint


FORM_RULE = "`// @rule <slug>: <text>`"
FORM_CLAIM = "`// @claim <slug> [<slug> ...]`"
HEADER_ORDER = ", ".join([*(header_word_text(w) for w in HEADER_RANK),
                          REVIEW_WORD])
"""The header lines' order, as the header-order sentence states it."""
SIBLING_DROPS_TEXT = ", ".join(f"`{header_word_text(w)}:`"
                               for w in HEADER_RANK if w in SIBLING_DROPS)
"""The fields a sibling leaves out, as the sibling sentence names them."""

LINT_TEXT: dict[LintSentence, Callable[[tuple[str, ...], tuple[str, ...]],
                                       str]] = {
    LintSentence.RESERVED_WORD: lambda n, _: mctx(
        "`{0}` is a Souffle reserved word; rename it").format(*n),
    LintSentence.SHADOWED_TYPE: lambda n, _: mctx(
        "`{0}` is also a type name inside `{1}`, so the instance takes that "
        "name for its own type; rename it").format(*n),
    LintSentence.LIB_NAME: lambda n, _: mctx(
        "`{0}` is a lib {1}; rename it").format(*n),
    LintSentence.LIB_PRIVATE: lambda n, _: mctx(
        "`{0}` is private to {1}; read one of its public relations"
    ).format(*n),
    LintSentence.LIB_INTERNAL_COMP: lambda n, _: mctx(
        "`{0}` is internal to the lib; instantiate a public component"
    ).format(*n),
    LintSentence.NO_PROPOSAL_ENTRY: lambda n, _: mctx(
        "`{0}` is a proposal comp with no entry {entry}; report the "
        "operation, or fold the comp into the program").format(
            *n, entry=checkout.proposal_entry(n[0]).relative_to(
                checkout.ROOT).as_posix()),
    LintSentence.PROPOSAL_UNREAD: lambda n, _: (mctx(
        "`{comp}` is a proposal comp, and the concept case reads none of "
        "its relations; the cases that read them: {cases} "
        "([In the pass](docs/handbook/lib-protocol.md#in-the-pass))").format(
            comp=n[0], cases=_ticked(n[1:])) if n[1:] else mctx(
        "`{comp}` is a proposal comp, and no case reads its relations "
        "([In the pass]"
        "(docs/handbook/lib-protocol.md#in-the-pass))").format(comp=n[0])),
    LintSentence.PARSE_UNREAD: lambda n, _: mctx(
        "no Determine comp reads this Parse comp; read it in Determine, or "
        "fold it into the program"),
    LintSentence.MARKER_SLASH: lambda n, _: mctx(
        "the marker separates its cases with `/`; see the case markers in "
        "[Cases](docs/handbook/solver-file.md#cases)"),
    LintSentence.NO_TASK_ID: lambda n, _: mctx(
        "the file does not open with `// <task_id>`"),
    LintSentence.HEADER_ORDER: lambda n, _: mctx(
        "header lines go in the order {order}").format(order=HEADER_ORDER),
    LintSentence.HEADER_PROSE: lambda n, _: mctx(
        "no prose in the header; a remark about a case goes at its "
        "constructor, and a remark about a clause at the clause"),
    LintSentence.DRAFT_PLACE: lambda n, _: mctx(
        "`@draft` goes under the task id"),
    LintSentence.REVIEW_KIND: lambda n, _: mctx(
        "`review` takes a kind: `// review <kind>: <text>`"),
    LintSentence.FIELD_TWICE: lambda n, _: mctx(
        "`{0}` stands once in the header").format(*n),
    LintSentence.SIBLING_DROPS: lambda n, _: mctx(
        "a sibling carries `@representative:` in place of {drops}").format(
        drops=SIBLING_DROPS_TEXT),
    LintSentence.SLUG_TWICE: lambda n, _: mctx(
        "`{0}` repeats the slug of an earlier claim; a slug stands once "
        "across `@scene` and `@rule`").format(*n),
    LintSentence.UNKNOWN_KEYWORD: lambda n, _: mctx(
        "`{0}` is not in keywords.md; propose it in the review").format(*n),
    LintSentence.NO_KEYWORDS: lambda n, _: mctx(
        "the header carries `@keywords:` or `@representative:`"),
    LintSentence.NO_RULE: lambda n, _: mctx(
        "the header has no `@rule` line; a rule is {form}").format(
        form=FORM_RULE),
    LintSentence.GLOSS_ABOVE: lambda n, _: mctx(
        "a gloss stands above `{0}`: what the choice is").format(*n),
    LintSentence.OWN_LINE: lambda n, _: mctx(
        "`{0}` opens its own line").format(*n),
    LintSentence.CONCEPT_WITNESS: lambda n, _: mctx(
        "`{0}` is the concept branch; drop its `@witness` line").format(*n),
    LintSentence.WITNESS_PLACE: lambda n, _: mctx(
        "a witness line stands in a branch's comment block or under "
        "`@approximated:`"),
    LintSentence.UNREAD_FIELD: lambda n, _: mctx(
        "case `{0}` never reads field `{1}`, so the choice point `{1}` "
        "encodes stands under the other branches").format(*n),
    LintSentence.CASE_SECTION_BEFORE: lambda n, _: mctx(
        "the clause contains the constructor `{0}` and stands before the "
        "first marker").format(*n),
    LintSentence.BRANCH_APPROXIMATED: lambda n, _: mctx(
        "`@{0} {1}` stands in a branch and carries `@approximated:`; a "
        "branch's `@rule` states the rule it runs").format(*n),
    LintSentence.CLAIM_UNSTATED: lambda n, _: mctx(
        "`{0}` denotes no claim in the header").format(*n),
    LintSentence.INSTANCE_UNCLAIMED: lambda n, _: mctx(
        "`{name}` carries no `@claim` line; the claims the instance serves "
        "stand above it as {form}").format(name=n[0], form=FORM_CLAIM),
    LintSentence.CONCEPT_UNCLAIMED: lambda n, _: mctx(
        "`{name}` is the concept branch; the claim the choice answers "
        "stands above it as {form}").format(name=n[0], form=FORM_CLAIM),
    LintSentence.BANNED_TYPE: lambda n, _: mctx(
        "`{0}` is none of the types "
        "[Types](docs/handbook/solver-file.md#types) lists; re-encode it or "
        "propose it").format(*n),
    LintSentence.DEAD: lambda n, _: mctx("`{0}` has no uses").format(*n),
    LintSentence.CHOICE_DOMAIN: lambda n, m: mctx(
        "`{name}` keeps one arbitrary tuple per `{over}`; state what picks "
        "it").format(name=n[0], over=", ".join(m)),
    LintSentence.RAW_AGGREGATE: lambda n, _: mctx(
        "`{0}` in the program; read it through a lib component").format(*n),
    LintSentence.PASS_THROUGH: lambda n, _: mctx(
        "`{0}` only feeds `{1}`").format(*n),
    LintSentence.CHAIN_JOIN: lambda n, _: mctx(
        "`{0}.{1}` only joins `{2}`").format(*n),
    LintSentence.ARGMAX: lambda n, _: mctx(
        "`{0}` is max/min via self-join; read it through a lib component"
    ).format(*n),
    LintSentence.CONST_PRODUCT: lambda n, _: mctx(
        "{rels} share no variable; one Params relation over their columns "
        "replaces them").format(rels=_ticked(n)),
    LintSentence.CONST_JOIN: lambda n, m: mctx(
        "{rels} join on `{vars}`; name the derived constant in Params"
    ).format(rels=_ticked(n), vars=", ".join(m)),
    LintSentence.TYPED_ORDER_COMPARES: lambda n, _: mctx(
        "`{0}` compares `{1}`, a `{2}`, which has no order; store the order "
        "as a parameter").format(*n),
    LintSentence.TYPED_ORDER_ORDERS: lambda n, _: mctx(
        "`{0}` orders `{1}`, a `{2}`, which has no order; store the order "
        "as a parameter").format(*n),
    LintSentence.TYPED_ORDER_RANKS: lambda n, _: mctx(
        "`{0}` ranks `{1}`, a `{2}`, which has no order; store the order as "
        "a parameter").format(*n),
}
"""The sentence of each `LintNamed` finding, from its names and its
second list."""

COUNTED_TEXT: dict[LintSentence, Callable[[LintCounted], str]] = {
    LintSentence.LONG_CLAUSE: lambda p: mctx(
        "{width} > {limit} chars of code on one line; wrap the body").format(
        width=p.count, limit=p.other),
    LintSentence.SINGLE_CONSUMER: lambda p: mctx(
        "`{name}` has one clause and one use (line {line})").format(
        name=p.names[0], line=p.other),
    LintSentence.COMMON_SUBEXPR: lambda p: mctx(
        "{width} literals shared with `{name}` (line {line})").format(
        width=p.count, name=p.names[0], line=p.other),
    LintSentence.COMMON_SUBEXPR_MERGE: lambda p: mctx(
        "{width} literals shared with `{name}` (line {line}); merge the "
        "tails into a disjunction").format(
        width=p.count, name=p.names[0], line=p.other),
}
"""The sentence of each `LintCounted` finding."""

CODE_TEXT: dict[LintSentence, Callable[[LintCode], str]] = {
    LintSentence.ALIAS: lambda p: mctx("`{head}` is `{atom}` renamed").format(
        head=code_text(p.code[0]), atom=code_text(p.code[1])),
    LintSentence.NEGATED_USE: lambda p: mctx(
        "`{code}` ⇒ `{parts}`").format(
        code=_codes(p.code), parts=_codes(p.rewritten)),
    LintSentence.SHARED_UNREAD: lambda p: mctx(
        "`{name}` is shared, and {cases} never reads it; move it under the "
        "marker of the cases that read it").format(
        name=p.names[0], cases=", ".join(f"`{code_text(c)}`"
                                         for c in p.code)),
    LintSentence.CHOICE_TAG: lambda p: mctx(
        "same body under `{one}` and `{other}`; one clause ranges over the "
        "tags").format(one=code_text(p.code[0]), other=code_text(p.code[1])),
    LintSentence.CROSS_CHOICE: lambda p: mctx(
        "branches bind {tags}; see "
        "[Disjunction](docs/handbook/style.md#disjunction)").format(
        tags=", ".join(f"`{code_text(c)}`" for c in p.code)),
    LintSentence.ATOM_TWICE: lambda p: mctx(
        "`{atom}` appears twice in the body").format(atom=code_text(p.code[0])),
    LintSentence.ATOM_ADDS_NOTHING: lambda p: mctx(
        "`{atom}` adds nothing next to `{other}`").format(
        atom=code_text(p.code[0]), other=code_text(p.code[1])),
    LintSentence.NEGATED_VALUE: lambda p: mctx(
        "`{code}` ⇒ `{rewritten}`").format(
        code=_codes(p.code), rewritten=_codes(p.rewritten)),
    LintSentence.NAMED_COMPLEMENT: lambda p: mctx(
        "`{code}` ⇒ `{rewritten}`").format(
        code=_codes(p.code), rewritten=_codes(p.rewritten)),
    LintSentence.LIB_IDIOM: lambda p: mctx(
        "`{code}` ⇒ `{rewritten}`").format(
        code=_codes(p.code), rewritten=_codes(p.rewritten)),
    LintSentence.COMP_IDIOM_MEMBER: lambda p: mctx(
        "`{code}` states the other member of a two-member type; write "
        "`{rewritten}`").format(code=_codes(p.code),
                                rewritten=_codes(p.rewritten)),
    LintSentence.COMP_IDIOM_IMAGE: lambda p: mctx(
        "`{code}` through `{link}` is `{comp}`").format(
        code=_codes(p.code), link=p.names[0], comp=p.names[1]),
    LintSentence.DOMAIN_ENUMERATOR: lambda p: mctx(
        "`{atom}`; `{var}` is already bound by `{binder}`").format(
        atom=code_text(p.code[0]), var=code_text(p.code[1]),
        binder=p.names[0]),
}
"""The sentence of each `LintCode` finding."""

FRAGMENT_CATEGORIES = frozenset({
    Category.RIGID_CHART, Category.ORIENTATION_LITERAL,
    Category.NONZERO_LITERAL, Category.ARITHMETIC, Category.RANGE,
    Category.PARAMS_DATA,
})
"""The categories whose message is the code fragment that fires."""


def part_text(part: MarkerPart) -> str:
    """One name of a case marker as the marker writes it."""
    return part.name


def marker_text(m: CaseMarker) -> str:
    """A case marker's text between its dashes."""
    parts = ", ".join(part_text(p) for p in m.parts)
    return parts + (f": {m.gloss}" if m.gloss else "")


def _marked_text(p: LintMarked) -> str:
    match p.sentence:
        case LintSentence.CASE_SECTION_UNDER:
            return mctx("the clause contains the constructor `{name}` and "
                        "stands under `// --- {marker} ---`").format(
                name=p.name, marker=_marker_or_none(p.marker))
        case LintSentence.CASE_SECTION_READ:
            return mctx("{cases} read `{rel}`, which the clause feeds, and "
                        "the marker `// --- {marker} ---` above it does not "
                        "list them").format(
                cases=_ticked(p.cases), rel=p.name,
                marker=_marker_or_none(p.marker))
        case LintSentence.MARKER_LISTS_NO_CASE:
            return mctx("`{name}` is under the marker `{marker}`, which "
                        "lists no case; see "
                        "[Cases](docs/handbook/solver-file.md#cases)").format(
                name=p.name, marker=_marker_or_none(p.marker))
        case LintSentence.DECL_PLACEMENT:
            spot = p.comp if p.comp is not None else \
                _marker_or_none(p.marker)
            return mctx("all uses of `{name}` are in {spot}").format(
                name=p.name, spot=spot)
        case _:
            raise ValueError(f"no sentence for {p.sentence}")


def _marker_or_none(m: CaseMarker | None) -> str:
    if m is None:
        raise ValueError("a marked lint finding without its marker")
    return marker_text(m)


def _labeled_text(p: LintLabeled) -> str:
    if p.sentence != LintSentence.ORDINARY_RELAXED:
        raise ValueError(f"no sentence for {p.sentence}")
    what = at_word(p.word) + (f" {p.name}" if p.name is not None else "")
    return mctx("`{what}` is `ordinary` and carries {relaxed}; see "
                "plausibility in "
                "[Witnesses](docs/handbook/principles.md#witnesses)").format(
        what=what, relaxed=", ".join(f"`@relaxed {s}`" for s in p.relaxed))


def _run_text(solver: Solver, p: LintRun) -> str:
    match p.sentence, p.outcome:
        case LintSentence.ONE_CASE_UNKNOWN_TIMEOUT, CpuLimit(seconds=t) \
                | WallLimit(seconds=t):
            return mctx("the run that gives the solver's cases "
                        "timed out after {seconds}s, so whether it has one "
                        "case is unknown").format(seconds=f"{t:g}")
        case LintSentence.ONE_CASE_UNKNOWN_FAILED, Case():
            raise ValueError("a failed run of the solver's cases without its failure")
        case LintSentence.ONE_CASE_UNKNOWN_FAILED, failure:
            return mctx("the run that gives the solver's cases "
                        "fails, so whether it has one case is unknown: "
                        "{failure}").format(failure=failure_text(failure))
        case LintSentence.CASE_SECTION_UNJUDGED, Case():
            raise ValueError("an unjudged case section without its failure")
        case LintSentence.CASE_SECTION_UNJUDGED, failure:
            return mctx("the run that gives the solver's cases gave "
                        "no result, so no clause under a case marker was "
                        "judged against the cases its marker lists: "
                        "{failure}").format(failure=failure_text(failure))
        case LintSentence.CASE_SECTION_READ_UNJUDGED, Case():
            raise ValueError("an unjudged case section without its failure")
        case LintSentence.CASE_SECTION_READ_UNJUDGED, failure:
            return mctx("the run that gives the solver's cases gave "
                        "no result, so no marker was judged against the "
                        "cases that read its clauses: {failure}").format(
                failure=failure_text(failure))
        case LintSentence.ONE_CASE, Case() as case:
            return mctx("the solver has one case, `{case}`, and "
                        "declares `Choice`; see "
                        "[Cases](docs/handbook/solver-file.md#cases)").format(
                case=case_name(solver, case))
        case _:
            raise ValueError(f"no sentence for {p.sentence}")


def _family_text(p: LintFamily) -> str:
    match p.sentence, p.failure:
        case LintSentence.FAMILY_NOT_PARSED, ParseFailure() as failure:
            return mctx("`{task}` does not parse ({error}), so `{case}` "
                        "cannot be checked against its `Choice`").format(
                task=p.task_id, case=p.case, error=detail_text(failure))
        case LintSentence.FAMILY_RECORD, None:
            return mctx("`{task}`'s `Choice` is a record, so the line takes "
                        "no case").format(task=p.task_id)
        case LintSentence.FAMILY_NO_CASE, None:
            return mctx("`{case}` is no case of `{task}`'s `Choice`; give a "
                        "case the representative holds").format(
                task=p.task_id, case=p.case)
        case LintSentence.FAMILY_NO_CHOICE, None:
            return mctx("`{task}` declares no `Choice`, so the line takes "
                        "no case").format(task=p.task_id)
        case _:
            raise ValueError(f"no sentence for {p.sentence}")


def _ignore_text(p: LintIgnore) -> str:
    ig = p.ignore
    if ig.category is None:
        raise ValueError("an `@ignore` line of the lint form has a category")
    category = ig.category.value
    match p.sentence:
        case LintSentence.IDLE_IGNORE:
            if p.site is None:
                raise ValueError("an idle `@ignore` line stands on a site")
            site = p.site.text
            return mctx("no finding or hint with the category `{category}` "
                        "fires on `{site}`").format(category=category,
                                                   site=site)
        case LintSentence.IGNORE_ON_LINT:
            return mctx("`{category}` gives a lint finding, which an "
                        "`@ignore` line does not dismiss; it dismisses a "
                        "hint alone").format(category=category)
        case LintSentence.IGNORE_ON_DECL | LintSentence.IGNORE_UNPLACED:
            directive = ignore_text(ig.relation, ig.category)
            if p.sentence == LintSentence.IGNORE_ON_DECL:
                return mctx("`{d}` states a relation above a `.decl`"
                            ).format(d=directive)
            return mctx("`{d}` stands immediately above no `.decl` or "
                        "`.init`").format(d=directive)
        case _:
            raise ValueError(f"no sentence for {p.sentence}")


def lint_message(solver: Solver, p: LintPayload) -> str:
    """A lint finding's message, the part after its category."""
    match p:
        case LintFragment(fragment=fragment):
            return f"`{fragment}`"
        case LintNamed(sentence=s, names=names, more=more):
            return LINT_TEXT[s](names, more)
        case LintCounted(sentence=s):
            return COUNTED_TEXT[s](p)
        case LintCode(sentence=s):
            return CODE_TEXT[s](p)
        case LintMarked():
            return _marked_text(p)
        case LintLabeled():
            return _labeled_text(p)
        case LintRun():
            return _run_text(solver, p)
        case LintFamily():
            return _family_text(p)
        case LintIgnore():
            return _ignore_text(p)
        case LintBranchForm(finding=inner, relations=rels, cases=cases):
            return lint_message(solver, inner) + mctx(
                "; no derivation of the concept case reads {rels}, and the "
                "cases that read {them}: {cases}; a branch whose claim needs "
                "this form fails [Relational form]"
                "(docs/handbook/principles.md#relational-form)").format(
                rels=_ticked([r.text for r in rels]),
                them="it" if len(rels) == 1 else "them",
                cases=_ticked(cases))


def lint_line(solver: Solver, f: Finding) -> str:
    """One lint finding or hint as a line: where, the category an `@ignore`
    line takes, and the message; on a hint that stands on a relation, the
    directive that keeps it
    ([Program](docs/handbook/solver-file.md#program))."""
    p = f.payload
    assert isinstance(p, LINT_SHAPES)
    line = f"{where_text(solver, f.where, LineForm.FILE)}: " \
           f"{p.category.value}: " \
           f"{lint_message(solver, p)}"
    if p.category in HINTS and p.on_relation:
        line += mctx("; an `@ignore` directive can keep the relation it "
                     "fires on")
    return line


def _lint_lines(solver: Solver, findings: Sequence[Finding]) -> list[str]:
    lines: list[str] = []
    lints = [f for f in findings if f.kind == Kind.LINT]
    hints = [f for f in findings if is_hint(f)]
    for shown, one in ((lints, "finding"), (hints, "hint")):
        if not shown:
            continue
        lines += ["", header_line(f"{len(shown)} {one}(s)"),
                  *(f"  {lint_line(solver, f)}" for f in shown)]
    others = [f for f in findings if f.kind != Kind.LINT and not is_hint(f)]
    lines += [ln for f in others
              for ln in finding_lines(solver, f, LineForm.FILE)]
    return lines


# Faults


PROBLEM_TEXT: dict[ProblemKind, str] = {
    ProblemKind.PARSE_FAILURE: mctx("the solver does not parse: {text}"),
    ProblemKind.RETIRED_FORM: mctx(
        "`{text}` is an annotation form the handbook retired; see "
        "[File structure](docs/handbook/solver-file.md#file-structure)"),
    ProblemKind.UNKNOWN_FORM: mctx(
        "`{text}` is no annotation form; see "
        "[File structure](docs/handbook/solver-file.md#file-structure)"),
    ProblemKind.OFF_FORM: mctx(
        "`{text}` is off its annotation's form; see "
        "[File structure](docs/handbook/solver-file.md#file-structure)"),
    ProblemKind.UNKNOWN_IGNORE_CATEGORY: mctx(
        "`{text}` is no category a finding gives; see "
        "[Program](docs/handbook/solver-file.md#program)"),
    ProblemKind.DIRECTIVE_UNPLACED: mctx(
        "`{text}` stands above no `.decl` or `.init` it can stand on"),
    ProblemKind.STORE_NAMES_NOTHING: mctx(
        "`{text}` is no relation of the instance below it"),
    ProblemKind.UNKNOWN_PROPOSER: mctx(
        "`{text}` is no proposer of `programs/proposers.dl`"),
    ProblemKind.TWO_LINES_ON_DERIVATION: mctx(
        "`{text}` has both a `@derive` line and an `@ignore: derive` line; "
        "remove one"),
    ProblemKind.WITNESS_FILE_SHAPE: mctx(
        "the witness file is off its shape: {text}; see "
        "[Witness file](docs/handbook/solver-file.md#witness-file)"),
    ProblemKind.NAME_DENOTES_NO_CASE: mctx(
        "the name `{text}` denotes no case of the solver"),
    ProblemKind.NAME_FORM: mctx(
        "`{text}` is in no form [Witness file]"
        "(docs/handbook/solver-file.md#witness-file) lists"),
    ProblemKind.ASSIGN_NAMES_NOTHING: mctx(
        "the `assign` name `{text}` names no parameter, stored relation or "
        "lib constant"),
    ProblemKind.GRID_OFF_LAYOUT: mctx("the entry gives {text}"),
    ProblemKind.ANCHOR_WITHOUT_STAMP: mctx("the entry gives {text}"),
    ProblemKind.GRID_CELL_OFF_FORM: mctx("the entry gives {text}"),
    ProblemKind.MARKER_NAMES_NOTHING: mctx(
        "the marker name `{text}` denotes no case of the solver"),
    ProblemKind.REPRESENTATIVE_MISSING: mctx(
        "`{text}` has no solver file, so the representative's `Choice` and "
        "claims are unknown"),
    ProblemKind.INSTANCE_OF_NOTHING: mctx(
        "`{text}` is a component that neither the solver nor a file it "
        "includes declares"),
    ProblemKind.INSTANCE_UNFOLLOWED: mctx(
        "the instance path `{text}` is deeper than the model follows, so "
        "the relations under it are not read"),
    ProblemKind.BASE_OF_NOTHING: mctx(
        "a component here extends `{text}`, which neither the solver nor a "
        "file it includes declares"),
    ProblemKind.TYPE_ARGUMENTS: mctx(
        "`{text}` is given another number of type arguments than it "
        "declares type parameters"),
    ProblemKind.RIGID_CHARTS: mctx(
        "the RIGID call of block `{text}` binds another number of "
        "relations than its block has charts, so its relations compare as "
        "stored, not up to the block's pose"),
    ProblemKind.UNDECIDED: mctx(
        "`{text}` is a form the handbook does not say how to read"),
}
"""The sentence of each fault, from the text read there."""


SHAPE_TEXT: dict[Expected, str] = {
    Expected.JSON: mctx("the file is no JSON"),
    Expected.OBJECT: mctx("`{field}` is no object"),
    Expected.STRING: mctx("`{field}` is no string"),
    Expected.LIST: mctx("`{field}` is no list"),
    Expected.GRID: mctx(
        "`{field}` is no rectangular grid of integers 0 to 9"),
    Expected.GROUPS_OR_GRID: mctx(
        "`{field}` is neither a list of groups nor a rectangular grid of "
        "integers 0 to 9"),
    Expected.GROUP_GRID: mctx(
        "`{field}` holds something other than rectangular grids of "
        "integers 0 to 9"),
    Expected.FACTS_OR_GRID: mctx(
        "`{field}` is neither a list of facts nor a grid"),
    Expected.ANCHORED_GRID: mctx(
        "`{field}` is no object of a `grid` and an `anchor`, the row and "
        "column of a cell of that grid"),
    Expected.PRESENT: mctx("missing field `{field}`"),
    Expected.ABSENT: mctx("unknown field `{field}`"),
    Expected.UNIQUE: mctx("`{field}` stands twice"),
    Expected.NONEMPTY: mctx("`{field}` lists no case"),
}
"""The sentence of each witness file shape fault, from the field's path."""


def detail_text(detail: Detail) -> str:
    """The part of a fault its sentence names."""
    match detail:
        case Quoted(text=text):
            return text
        case Named(name=RelationName() as relation):
            return relation.text
        case Named(name=DeriveBranch() as branch):
            return names.branch_text(branch)
        case Named(name=DirectiveWord() as word):
            return word.value
        case Named(name=name):
            assert isinstance(name, str)
            return name
        case ShapeFault(field=path, expected=expected):
            field = "/".join(str(k) for k in path) or mctx("the file")
            return SHAPE_TEXT[expected].format(field=field)
        case UndecidedDetail(form=form, name=name):
            return name if name is not None else form.value
        case AnchorWithoutStamp(name=name, storage=storage):
            stored = (mctx("in a `{form}` call").format(form=code_text(storage))
                      if isinstance(storage, GridLayout) else STORAGE_TEXT[storage])
            return mctx("`{name}` a grid with an anchor, and the solver "
                        "stores `{name}` {stored}, not by one `GRID_STAMP` "
                        "call").format(name=name, stored=stored)
        case GridCellOffForm(name=name, layout=layout, cell=(r, c),
                             value=v):
            return mctx("`{name}` the value {v} at row {r}, column {c}, and "
                        "its `{form}` layout takes 1 for a member and 0 for "
                        "an empty cell").format(
                            name=name, v=v, r=r, c=c, form=code_text(layout))
        case GridOffLayout(name=name, layout=layout, given=(h, w)):
            if layout is None:
                return mctx("`{name}` a {h}x{w} grid, and the solver stores "
                            "`{name}` by no one GRID call whose layout "
                            "places it").format(name=name, h=h, w=w)
            return mctx("`{name}` a {h}x{w} grid with no anchor, and the "
                        "solver's `GRID_STAMP` layout for `{name}` is "
                        "{lh}x{lw}").format(name=name, h=h, w=w,
                                            lh=layout.height, lw=layout.width)
        case ParseFailure(line=line, column=column, message=message):
            return f"{line}:{column}: {message}"


STORAGE_TEXT: dict[Storage, str] = {
    Storage.FACTS: mctx("as facts"),
    Storage.GRID_CALLS: mctx("in several GRID calls"),
    Storage.STORED_RELATION: mctx("as a `@store` relation"),
}
"""How a name with no one GRID call is stored, as the anchor fault says
it."""


def _reading_lines(solver: Solver, f: Finding, p: FaultPayload,
                   form: LineForm) -> list[str]:
    text = PROBLEM_TEXT[p.problem.kind].format(
        text=detail_text(p.problem.detail))
    return [f"{where_text(solver, f.where, form)}: {text}"]


def _no_sentence(f: Finding) -> NoReturn:
    """A finding the renderer has no sentence for: a kind and payload
    that do not go together, or a kind no sentence covers yet."""
    raise ValueError(f"no sentence for a `{f.kind.value}` finding with "
                     f"{type(f.payload).__name__}")


def finding_lines(solver: Solver, f: Finding,
                  form: LineForm = LineForm.LINE) -> list[str]:
    """The lines of one finding of any kind, a line of the solver written
    in `form` (`line_form` of the section they stand in)."""
    p = f.payload
    at = where_text(solver, f.where, form)
    from checker.render.branches import BRANCH_KINDS, branch_lines
    if f.kind in BRANCH_KINDS:
        return branch_lines(solver, f, form)
    from checker.render.witness import WITNESS_KINDS, witness_lines
    if f.kind in WITNESS_KINDS:
        return witness_lines(solver, f)
    match p:
        case _ if isinstance(p, LINT_SHAPES):
            return [lint_line(solver, f)]
        case FaultPayload():
            return _reading_lines(solver, f, p, form)
        case NoResultPayload():
            return _no_result_lines(solver, f, p, form)
        case UndecidedPayload(relation=rel):
            words = "; ".join(f"\"{q.words}\"" for q in quoted(p))
            return [mctx("{at}: undecided: `{rel}` holds one set of rows on "
                         "every input and no value the survey reads; the "
                         "check rests on {words}").format(
                             at=at, rel=rel.text, words=words)]
        case _:
            _no_sentence(f)


# Sections


def in_line_order(findings: Sequence[Finding]) -> list[Finding]:
    """`findings` with those located at a solver line in line order, in
    the places those findings hold; every other finding keeps its place.
    Findings at one line keep the order they come in."""
    at = [i for i, f in enumerate(findings) if isinstance(f.where, AtLine)]
    ordered = sorted((findings[i] for i in at),
                     key=lambda f: f.where.line
                     if isinstance(f.where, AtLine) else 0)
    out = list(findings)
    for i, f in zip(at, ordered):
        out[i] = f
    return out


def render(solver: Solver, section: Section,
           findings: Sequence[Finding]) -> list[str]:
    """The lines of `section` that state `findings` of `solver`,
    the section's pass line included: one function per kind, grids drawn
    by one grid function. A section prints its findings in the order it
    gets them, those located at a solver line in line order
    (`in_line_order`)."""
    form = line_form(section)
    findings = in_line_order(findings)
    if section == Section.LINT:
        lines = _lint_lines(solver, findings)
    elif section == Section.DROPPED_CASES:
        lines = [f"  {ln}" for f in findings
                 for ln in finding_lines(solver, f, form)]
    else:
        lines = [ln for f in findings
                 for ln in finding_lines(solver, f, form)]
    verdict = pass_line(section, findings)
    if verdict is not None:
        lines += ([""] if section == Section.LINT else []) + [verdict]
    return lines


# Directive hints


class HintKind(StrEnum):
    """The line a `derive` or `store` report tells the session to add."""

    DERIVE = "derive"
    STORE = "store"
    IGNORE_DERIVE = "ignore derive"
    IGNORE_STORE = "ignore store"


@dataclass(frozen=True)
class Hint:
    """A directive line to add: its kind, the proposer of a `@derive`
    or `@ignore: derive <Proposer>` line, the relation a line on an instance names, and the site it goes
    above: the instance of an `.init`, or the block of a `RIGID` call;
    None for the relation's own `.decl`. `alone` says no `@derive` or
    `@store` line stands above it in the report, so it states the
    site."""

    kind: HintKind
    proposer: str | None = None
    relation: str | None = None
    site: str | None = None
    alone: bool = False


def derive_line_to_add(proposer: str) -> str:
    """The `@derive` line of `proposer` for the agent to add, its
    plausibility and verdict left as slots."""
    return comment_text(derive_text(proposer, Slot.PLAUSIBILITY,
                                    Slot.VERDICT))


def hint_line(h: Hint) -> str:
    """The line the session adds, as the `derive` and `store` reports
    print it ([Program](docs/handbook/solver-file.md#program))."""
    if h.kind == HintKind.DERIVE:
        add = "add:" if h.site is None \
            else f"add above `RIGID({h.site}, …)`:"
        assert h.proposer is not None
        return f"{add} " + derive_line_to_add(h.proposer)
    named = h.relation if h.site is not None else None
    add = "add:" if h.site is None else f"add above `.init {h.site}`:"
    if h.kind == HintKind.STORE:
        return f"{add} " + comment_text(store_text(
            named, Slot.PLAUSIBILITY, Slot.VERDICT))
    lead = f"{add} " if h.alone and h.site is not None else "or:  "
    if h.kind == HintKind.IGNORE_DERIVE:
        return lead + comment_text(ignore_text(
            named, IgnoreForm.DERIVE, Slot.REASON, h.proposer))
    return lead + comment_text(ignore_text(named, IgnoreForm.STORE,
                                           Slot.REASON))
