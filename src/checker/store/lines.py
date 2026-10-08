"""The findings the audit prints on the solver's `@store` lines and on
the values the `store` survey finds."""

from collections import Counter
from collections.abc import Callable, Mapping, Sequence

from checker.branches.cases import ordered, untaken
from checker.branches.ignores import excluded_finding, idle_ignores
from checker.branches.witnesses import entry_findings
from checker.finding import (
    AtLine,
    AtRelation,
    Finding,
    Kind,
    UndecidedPayload,
)
from checker.payloads.branches import (
    BranchPayload,
    ColorAskPayload,
    DiffersOn,
    DuplicatePayload,
    HomonymsPayload,
    KeyedBy,
    MissingLinePayload,
    NoAnchor,
    NoRows,
    NotBetween,
    NoValue,
    RelationPayload,
    StoreNoValuePayload,
    StoreValuesPayload,
    Unread,
)
from checker.runs import Runs
from checker.store.survey import Found, ValueKind
from engine import RelationName
from solver.aggregate import Solver
from solver.annotations import IgnoreForm
from solver.columns import ident_keyed
from solver.model import Case, StoreBranch
from solver.names import cover
from solver.problems import ProblemKind
from solver.pair_runs import PairId
from solver.value_order import row_key


def line_findings(runs: Runs, solver: Solver, rels: Sequence[RelationName],
                  found: Sequence[Found], capped: Sequence[RelationName],
                  empty: set[RelationName],
                  differs: Mapping[RelationName, PairId | None],
                  solver_cases: tuple[Case, ...]) -> list[Finding]:
    """The findings the audit prints: on each `@store` line, a second
    line on its relation, a relation that is also a parameter's name, a
    relation that gives no value the runner can store and why, cases
    that take two values of it, a name that denotes other relations too,
    an entry that witnesses nothing, and a value no case that reads the
    relation has; then the named `@ignore: store` lines that exclude no
    case; then each value the survey asks for a `@store` line
    (`Found.asks_line`), with a second finding where its name denotes
    other relations too, and each color the concept case reads that asks
    for a Params parameter."""
    out: list[Finding] = []
    unread = {f.relation for f in found
              if f.kind is ValueKind.OWNED and not f.depended}
    first: dict[RelationName, StoreBranch] = {}
    stores = sorted(((b, b.line.line) for b in solver.branches
                     if isinstance(b, StoreBranch) and b.line is not None),
                    key=lambda bl: bl[1])
    first_line: dict[RelationName, int] = {}
    for b, line in stores:
        at = AtLine(line)
        if b.relation in first:
            out.append(Finding(Kind.DUPLICATE_BRANCH_LINE,
                               AtLine(first_line[b.relation]),
                               DuplicatePayload(first[b.relation],
                                                first_line[b.relation],
                                                line)))
            continue
        first[b.relation] = b
        first_line[b.relation] = line
        if solver.params.parameter(b.spelled) is not None:
            out.append(Finding(Kind.STORE_PARAMETER_NAME, at,
                               BranchPayload(b)))
            continue
        if ident_keyed(solver.engine, solver.program, b.relation):
            out.append(Finding(Kind.STORE_IDENT_KEY, at,
                               RelationPayload(b.relation)))
            continue
        if untaken(runs, solver, b):
            excluded = excluded_finding(runs, solver, b, at)
            if excluded is not None:
                out.append(excluded)
                continue
        mine = [f for f in found if f.relation == b.relation]
        owned = [f for f in mine if f.store_branch]
        if not owned:
            if b.relation in capped:
                continue
            why = _no_value(b.relation, rels, unread, empty, mine, differs)
            if why is None:
                out.append(Finding(Kind(ProblemKind.UNDECIDED), at,
                                   UndecidedPayload(b.relation)))
            else:
                out += [Finding(Kind.STORE_NO_VALUE, at, StoreNoValuePayload(
                    b.relation, w)) for w in why]
            continue
        out += _two_values(solver, b, line, [
            f for f in mine if f.kind is ValueKind.OWNED], solver_cases)
        for f in owned:
            if f.homonyms:
                out.append(Finding(Kind.STORE_HOMONYMS, at, HomonymsPayload(
                    f.name, (f.relation, *f.homonyms))))
            elif f.entry:
                entry = runs.branch_entry(f.name)
                if entry is not None:
                    out += entry_findings(
                        runs, solver, b, f.name, f.case_id,
                        ordered(solver, solver_cases, b),
                        entry)
            elif f.untaken:
                out.append(Finding(Kind.STORE_UNTAKEN, at,
                                   RelationPayload(b.relation)))
    out += idle_ignores(runs, IgnoreForm.STORE)
    shown = shown_case_names(found)
    for f in found:
        if not f.depended or (f.stored and f.line is None):
            continue
        names = shown(f)
        where = AtRelation(f.relation)
        if f.asks_line:
            out.append(Finding(Kind.MISSING_BRANCH_LINE, where,
                               MissingLinePayload(f.name, names)))
        if f.homonyms and f.line is None:
            out.append(Finding(Kind.STORE_HOMONYMS, where, HomonymsPayload(
                f.name, (f.relation, *f.homonyms))))
        if f.asks_params:
            out.append(Finding(Kind.STORE_PARAMS_ASK, where, ColorAskPayload(
                f.relation, f.columns if f.sub else (), f.types,
                tuple(sorted((tuple(m) for m in f.one),  # type: ignore[misc]
                             key=row_key)),  # type: ignore[arg-type]
                names)))
    return out


def _no_value(path: RelationName, rels: Sequence[RelationName],
              unread: set[RelationName], empty: set[RelationName],
              mine: Sequence[Found],
              differs: Mapping[RelationName, PairId | None]
              ) -> list[NoValue] | None:
    """Why a `@store` line's relation gives no value the runner can
    store: one reason per value of it that is not the same on every
    input. None where no reason is known."""
    if path not in rels:
        return [NotBetween()]
    if path in unread:
        return [Unread()]
    held_back = [f for f in mine if f.kind is not ValueKind.OWNED]
    if held_back:
        return [NoAnchor() if f.kind is ValueKind.TRANSLATED
                else KeyedBy(f.keys) for f in held_back]
    pair = differs.get(path)
    if pair is not None:
        return [DiffersOn(pair)]
    if path in empty:
        return [NoRows()]
    return None


def _two_values(solver: Solver, b: StoreBranch, line: int,
                values: Sequence[Found], solver_cases: Sequence[Case]
                ) -> list[Finding]:
    """Where cases of the solver take two values or more of one relation: the
    branch of the line at `line` then denotes a branch per value there. One finding per
    number of values, with the cases that take that many."""
    if len(values) < 2:
        return []
    counts: dict[Case, int] = {}
    for f in values:
        for c in solver_cases:
            if c.branches or (f.case_values and c.base not in f.bases):
                continue
            counts[c] = counts.get(c, 0) + 1
    out: list[Finding] = []
    for n in sorted({k for k in counts.values() if k > 1}):
        out.append(Finding(Kind.STORE_VALUES, AtLine(line),
                           StoreValuesPayload(
                               b.relation, b, n, cover(
                                   solver, [c for c, k in counts.items()
                                            if k == n], solver_cases))))
    return out


def shown_case_names(found: Sequence[Found]
                     ) -> Callable[[Found], tuple[str, ...]]:
    """The case names a value of `found` prints with: its `case_names`
    where another value of `found` has its relation and columns, and
    none where the relation and columns tell it apart."""
    rows = Counter((f.relation, f.columns) for f in found)
    return lambda f: f.case_names if rows[(f.relation, f.columns)] >= 2 \
        else ()
