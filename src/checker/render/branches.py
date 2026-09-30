"""The sentences of the `@derive` and `@store` kinds, of the determination
check, and of the `derive` and `store` command blocks."""

from collections.abc import Sequence

from checker.finding import AtFile, Finding, Kind, WholeFile
from checker.judged import NoResult, Swap
from checker.payloads.branches import (
    BranchEntryPayload,
    BranchName,
    BranchPayload,
    ColorAskPayload,
    DeriveFitPayload,
    DerivedDataPayload,
    DeterminationDiffPayload,
    DiffersOn,
    DuplicatePayload,
    HomonymsPayload,
    IdleIgnorePayload,
    KeyedBy,
    MarkerUnownedPayload,
    MissingLinePayload,
    NoAnchor,
    NoTaskPayload,
    NotCheckedPayload,
    NotBetween,
    NoRows,
    NoValue,
    RelationPayload,
    RowCapPayload,
    StoreNoValuePayload,
    StoreValuesPayload,
    Unread,
)
from checker.runs import NoTask
from checker.render import (
    Hint,
    HintKind,
    LineForm,
    _no_sentence,
    _ticked,
    branch_name,
    case_name,
    verdict_text,
    failure_text,
    finding_lines,
    in_line_order,
    grid_lines,
    hint_line,
    marker_text,
    value_text,
    where_text,
)
from controlled_markdown import mctx
from engine import AdtValue, RecordValue
from checker.store import (
    POSITION_TYPES,
    ROW_CAP,
    D4,
    Change,
    ColorSwap,
    Found,
    StoreSurvey,
    ValueKind,
    corner,
    shown_case_names,
)
from solver.model import Case, DeriveBranch, Solver, StoreBranch
from solver.solve import Determined, DetermineResult, NoDetermine
from solver.names import Denoted, denote
from solver.witness import (
    ConflictingCells,
    Entry,
    Groups,
    InconsistentBounds,
    MissingCells,
    NegativeEdges,
    NoOutput,
    Resolutions,
    Undefined,
    UndefinedReason,
)
from solver.vocabulary import TIEBREAK_RESOLUTION

BRANCH_KINDS = frozenset({
    Kind.IDLE_BRANCH_IGNORE, Kind.MISSING_BRANCH_LINE,
    Kind.DUPLICATE_BRANCH_LINE, Kind.BRANCH_WITNESS_MISSING,
    Kind.BRANCH_ENTRY, Kind.DERIVE_UNREAD, Kind.DERIVE_FIT,
    Kind.DERIVE_UNPLACED, Kind.STORE_PARAMETER_NAME, Kind.STORE_VALUES,
    Kind.STORE_NO_VALUE, Kind.STORE_UNTAKEN, Kind.STORE_HOMONYMS,
    Kind.STORE_IDENT_KEY,
    Kind.STORE_PARAMS_ASK, Kind.STORE_ROW_CAP, Kind.MARKER_UNOWNED,
    Kind.DETERMINATION_DIFF, Kind.DETERMINATION_OF_DERIVED, Kind.NO_TASK,
    Kind.NOT_CHECKED,
})
"""The kinds whose sentence this module writes."""

SHOWN_MEMBERS = 8
"""How many members of a value that draws no picture the `store` block
spells out; a larger value goes under its member count."""

DRAW_CAP = 30
"""How far a picture of the `store` block reaches along each axis; a
value whose cells spread further draws none."""

D4_TEXT: dict[D4, str] = {
    D4.CW: "turned a quarter turn clockwise",
    D4.HT: "turned a half turn",
    D4.CC: "turned a quarter turn counterclockwise",
    D4.LR: "mirrored left-right",
    D4.TB: "mirrored top-bottom",
    D4.DG: "mirrored across the main diagonal",
    D4.AD: "mirrored across the anti-diagonal",
}
"""How each D4 element other than the identity changes a grid, in
words."""


def _word(branch: BranchName) -> str:
    return "@derive" if isinstance(branch, DeriveBranch) else "@store"


def _first(branch: BranchName) -> str:
    """The first branch of the branch's point, in words."""
    return (mctx("the stored value") if isinstance(branch, DeriveBranch)
            else mctx("the derived value"))


def transform_text(change: Change | Swap) -> str:
    """How a witness grid comes from a train input: a color swap, or a D4
    element in words."""
    match change:
        case ColorSwap(stored=a, free=b) | Swap(stored=a, free=b):
            return mctx("with {a} and {b} swapped").format(a=a, b=b)
        case D4():
            return D4_TEXT[change]


def separates(branch: BranchName, label: str, change: Change | Swap) -> str:
    """The `separates` of a witness a survey builds: the branch, the
    point's first branch, and how the grid comes from a train input."""
    return mctx("`{b}` from {first}: {grid} {change}").format(
        b=branch_name(branch), first=_first(branch), grid=label,
        change=transform_text(change))


def _idle_text(p: IdleIgnorePayload) -> str:
    word = "@derive" if p.ignore.form.value == "derive" else "@store"
    if p.under is None:
        return (mctx("no `{word}` line stands above this line")
                if word == "@derive" else
                mctx("no `{word}` line stands above the relation under "
                     "this line")).format(word=word)
    return mctx("this line excludes no case: no case the runner holds takes "
                "the `{word}` line's branch and every branch whose name "
                "`{name}` contains").format(word=word, name=p.ignore.name)


def _cases_suffix(names: Sequence[str]) -> str:
    """`; case <name>` or `; cases <names>`, where a value is stored per
    case, the cases by the fewest names that denote exactly them."""
    if not names:
        return ""
    if len(names) == 1:
        return mctx("; case `{case}`").format(case=names[0])
    return mctx("; cases {cases}").format(cases=_ticked(names))


def _no_value_text(rel: str, why: NoValue) -> str:
    match why:
        case NotBetween():
            return mctx("`{rel}` is no program relation between `in` and "
                        "`out`").format(rel=rel)
        case Unread():
            return mctx("`{rel}` is no relation a case reads").format(rel=rel)
        case NoAnchor():
            return mctx("`{rel}` stands at another place on each input, and "
                        "the runner picks no anchor").format(rel=rel)
        case KeyedBy(keys=keys):
            return mctx("`{rel}` varies by {keys}, an id the runner stores "
                        "nothing under").format(rel=rel, keys=_ticked(keys))
        case DiffersOn(pair=pair):
            return mctx("`{rel}` gives another value on {grid}").format(
                rel=rel, grid=f"{pair.section} {pair.index}")
        case NoRows():
            return mctx("`{rel}` gives no value the runner can store"
                        ).format(rel=rel)


def homonyms_text(p: HomonymsPayload) -> str:
    rels = [f"`{r.text}`" for r in sorted(p.relations, key=lambda r: r.text)]
    return mctx("`{b}` denotes the `@store` branches of {n} relations, "
                "{rels} and {last}").format(
        b=branch_name(p.branch), n=len(rels), rels=", ".join(rels[:-1]),
        last=rels[-1])


def _member_text(solver: Solver, types: Sequence[str],
                 member: Sequence[object]) -> str:
    names = orientation_names(solver)
    orientation = solver.lib.orientation_types

    def shown(t: str, v: object) -> str:
        if isinstance(v, tuple):
            return f"({', '.join(str(x) for x in v)})"
        if isinstance(v, (int, str, AdtValue, RecordValue)):
            text = value_text(v)
            return names.get(v, text) if t in orientation \
                and isinstance(v, int) else text
        return str(v)

    if len(member) == 1:
        return shown(types[0], member[0])
    return "(" + ", ".join(shown(t, v) for t, v in zip(types, member)) + ")"


def orientation_names(solver: Solver) -> dict[int, str]:
    """Each orientation member's value under the constant that denotes
    it."""
    out: dict[int, str] = {}
    for members in solver.lib.orientation_types.values():
        for m in members:
            v = solver.lib.constants.get(m)
            if isinstance(v, int):
                out.setdefault(v, m)
    return out


def inline_text(solver: Solver, types: Sequence[str],
                members: Sequence[Sequence[object]]) -> str:
    """A value as one phrase: its members, each as the solver writes it,
    an orientation under the constant that denotes it."""
    return ", ".join(_member_text(solver, types, m)
                     for m in sorted(members, key=_printed))


def _printed(member: Sequence[object]) -> tuple[str, ...]:
    """A member as the run prints it, which orders the members of a value
    as the `store` block lists them."""
    return tuple(value_text(v) if isinstance(v, (int, str, AdtValue,
                                                  RecordValue)) else str(v)
                 for v in member)


def _branch_text(solver: Solver, f: Finding) -> str:
    """A finding's sentence, after its location."""
    p = f.payload
    match f.kind, p:
        case Kind.IDLE_BRANCH_IGNORE, IdleIgnorePayload():
            return _idle_text(p)
        case Kind.MISSING_BRANCH_LINE, MissingLinePayload(branch=DeriveBranch() as b):
            return mctx("`{b}` fits and has no `@derive` or `@ignore: derive` "
                        "line").format(b=branch_name(b))
        case Kind.MISSING_BRANCH_LINE, MissingLinePayload(branch=StoreBranch()):
            return mctx("one value on every input and no `@store` or "
                        "`@ignore: store` line") + _cases_suffix(p.cases)
        case Kind.DUPLICATE_BRANCH_LINE, DuplicatePayload(
                branch=DeriveBranch() as b, first_line=n):
            return mctx("a second `@derive` line of `{b}`; the first is line "
                        "{n}").format(b=branch_name(b), n=n)
        case Kind.DUPLICATE_BRANCH_LINE, DuplicatePayload(
                branch=StoreBranch() as b, second_line=n):
            return mctx("`{rel}` has a second `@store` line at line {n}, so "
                        "`{b}` denotes two branches").format(
                rel=b.spelled, n=n, b=branch_name(b))
        case Kind.BRANCH_WITNESS_MISSING, BranchPayload(branch=b):
            return mctx("a `{word}` line needs a witness whose id is `{b}`"
                        ).format(word=_word(b), b=branch_name(b))
        case Kind.BRANCH_ENTRY, BranchEntryPayload(branch=b):
            return mctx("at the witness's assignment, each case that takes "
                        "`{b}` gives the output of the case that takes "
                        "{first} there and the same branches elsewhere"
                        ).format(b=branch_name(b), first=_first(b))
        case Kind.DERIVE_UNREAD, BranchPayload():
            return mctx("`@derive` stands above a parameter no case of the solver "
                        "reads")
        case Kind.DERIVE_FIT, DeriveFitPayload(branch=b, pair=pair):
            return mctx("`{b}` fails Fit at {pair}").format(
                b=branch_name(b),
                pair=f"{pair.section} {pair.index}")
        case Kind.DERIVE_UNPLACED, BranchPayload(branch=b):
            return unplaced_text(b)
        case Kind.STORE_PARAMETER_NAME, RelationPayload(relation=r):
            return mctx("the `@store` line is on `{r}`, which is also the "
                        "name of a parameter, so `{r}=stored` denotes two "
                        "branches").format(r=r.name)
        case Kind.STORE_VALUES, StoreValuesPayload(branch=b, values=n,
                                                    cases=cases):
            rel = b.spelled
            return mctx("`{r}` holds {n} values at {cases}, so `{b}` "
                        "denotes {n} branches there").format(
                r=rel, n=n, b=branch_name(b),
                cases=_ticked(cases))
        case Kind.STORE_NO_VALUE, StoreNoValuePayload(relation=r, reason=why):
            return _no_value_text(r.text, why)
        case Kind.STORE_UNTAKEN, RelationPayload():
            return untaken_text()
        case Kind.STORE_IDENT_KEY, RelationPayload(relation=r):
            return mctx("`{r}` has an `Ident` column, whose ids each run "
                        "assigns anew, so a stored value of it names no "
                        "object on another input, and no case of "
                        "`{r}=stored` runs").format(r=r.text)
        case Kind.STORE_HOMONYMS, HomonymsPayload() as h:
            return homonyms_text(h)
        case Kind.STORE_PARAMS_ASK, ColorAskPayload(value=value, cases=cases):
            return mctx("one color on every input: {value}; store it in "
                        "Params").format(value=", ".join(sorted(
                            ", ".join(str(v) for v in m) if len(m) == 1
                            else "(" + ", ".join(str(v) for v in m) + ")"
                            for m in value))) + _cases_suffix(cases)
        case Kind.STORE_ROW_CAP, RowCapPayload(relations=rels, cap=cap):
            return row_cap_text(cap, [r.text for r in rels])
        case Kind.MARKER_UNOWNED, MarkerUnownedPayload(marker=m,
                                                        clause_lines=ls):
            return mctx("cases the marker `{m}` does not list read the "
                        "clauses under it at {at}").format(
                m=marker_text(m), at=_line_list(ls))
        case Kind.DETERMINATION_DIFF, DeterminationDiffPayload(diff=d):
            return mctx("determination: DIFF on ") + d.parameter
        case Kind.DETERMINATION_OF_DERIVED, DerivedDataPayload(relation=r):
            return mctx("determination: ERROR determination relation "
                        "'{name}' matches derived Params data, which carries "
                        "no determination relation; rename the helper or "
                        "store {name} as a parameter").format(name=r)
        case Kind.NO_TASK, NoTaskPayload():
            return mctx("not run: the task has no task file")
        case Kind.NOT_CHECKED, NotCheckedPayload():
            return NOT_BETWEEN
        case _:
            _no_sentence(f)


NOT_BETWEEN = mctx("no relation both reads `in` and feeds `out`")


def _line_list(lines: Sequence[int]) -> str:
    if len(lines) == 1:
        return mctx("line {n}").format(n=lines[0])
    return mctx("lines {ns}").format(ns=", ".join(str(n) for n in lines))


def unplaced_text(b: BranchName) -> str:
    return mctx("whether `{b}` fits is not judged: the runner finds no "
                "`.decl` of the parameter in `Params`, and no `RIGID` call "
                "whose chart it is, to put its `@derive` line above"
                ).format(b=branch_name(b))


def untaken_text() -> str:
    return mctx("no witness: the relation has the value at no case that "
                "reads it")


def row_cap_text(cap: int, rels: Sequence[str]) -> str:
    return mctx("not checked, over {cap} rows on an input, too many to be a "
                "stored value: {rels}").format(cap=cap, rels=_ticked(rels))


def branch_lines(solver: Solver, f: Finding,
                 form: LineForm = LineForm.LINE) -> list[str]:
    """A `@derive` or `@store` finding as `<where>: <text>`, a line of the
    solver written in `form`; a row cap finding, which stands on no one
    relation, and a determination finding, whose sentence names its
    parameter, as the text alone."""
    text = _branch_text(solver, f)
    if f.kind in (Kind.DETERMINATION_DIFF, Kind.DETERMINATION_OF_DERIVED,
                  Kind.NOT_CHECKED) \
            or (f.kind == Kind.STORE_ROW_CAP and isinstance(f.where, AtFile)):
        return [text]
    return [f"{where_text(solver, f.where, form)}: {text}"]


# The determination check


def determination_lines(solver: Solver, result: DetermineResult | NoTask,
                        findings: Sequence[Finding]) -> list[str]:
    """The determination section of `run`
    ([Determination](docs/handbook/solver-file.md#determination)): the
    cycles among the determined parameters, then each finding, and the
    `ok` line with the determined parameters where no finding stands."""
    if isinstance(result, NoDetermine):
        return [mctx("determination: no Determine comp")]
    if isinstance(result, NoTask):
        return [mctx("determination: ") + _branch_text(solver, Finding(
            Kind.NO_TASK, AtFile(WholeFile.SOLVER), NoTaskPayload()))]
    lines: list[str] = []
    if isinstance(result, Determined):
        scopes = {u.id: u.scope for u in solver.program.units}
        lines += [mctx("circular determination: ") + ", ".join(
            mctx("{param} reads params.{reads} ({comp} line {line})").format(
                param=r.parameter, reads=r.reads,
                comp=".".join(scopes[r.unit].components), line=r.line)
            for r in cycle) for cycle in result.cycles]
    diffs = [f.payload.diff.parameter for f in findings
             if isinstance(f.payload, DeterminationDiffPayload)]
    others = [f for f in findings
              if not isinstance(f.payload, DeterminationDiffPayload)]
    for f in in_line_order(others):
        lines += finding_lines(solver, f)
    if diffs:
        lines.append(mctx("determination: DIFF on ") + ", ".join(diffs))
    if isinstance(result, Determined) and not findings and not result.cycles:
        names = sorted(p.name for p in solver.params.parameters
                       if p.determined)
        lines.append(mctx("determination: ok ({params})").format(
            params=", ".join(names)))
    return lines


# The witness a block builds, as `record` prints one


def takes_branch(solver: Solver, name: str) -> bool:
    """Whether the case a witness file's name denotes takes a `@derive` or
    `@store` branch (`solver.names.denote`)."""
    d = denote(solver, name)
    return isinstance(d, Denoted) and bool(d.branches)


def undefined_lines(reason: UndefinedReason | None) -> list[str]:
    """Why a case's cells describe no grid, with the cells or the values
    at fault, as the old tool printed them under the case's name; nothing
    for a case with no cell or with no derived value, whose name says
    it."""
    match reason:
        case ConflictingCells(cells=cells):
            return [mctx("conflicts at: {cells}").format(cells=list(cells))]
        case MissingCells(cells=cells):
            return [mctx("missing cells at: {cells}").format(
                cells=list(cells))]
        case NegativeEdges(edges=edges):
            return [mctx("negative edge distances (top, bottom, left, "
                         "right) at: {edges}").format(edges=list(edges))]
        case InconsistentBounds(bounds=bounds):
            return [mctx("inconsistent grid bounds (height, width): "
                         "{bounds}").format(bounds=list(bounds))]
        case _:
            return []


def record_lines(entry: Entry, solver: Solver, cases: Sequence[Case]
                 ) -> list[str]:
    """A built witness as `record` prints it: the input, each group of
    cases above the grid they give, or above why their cells describe no
    grid (`undefined_lines`), the cases that give none, and the
    count line (`checker.render.commands.COUNT_LINE`): the bases and the
    cases among `cases`, the cases the groups were built from, a case's
    base its `Choice` value (solver-file.md:99), and the distinct
    grids."""
    lines = ["", mctx("input:"), *(f"  {r}" for r in grid_lines(
        entry.input))]
    groups = entry.output.groups if isinstance(entry.output, Groups) else ()
    silent: list[tuple[str, UndefinedReason | None]] = []
    grids: set[object] = set()
    for g in groups:
        out = g.grid
        why = undefined_lines(out.reason) if isinstance(out, Undefined) \
            else []
        if isinstance(out, Undefined) and not why:
            silent += [(n, out.reason) for n in g.cases]
            continue
        joined = ", ".join(g.cases)
        lines.append("")
        if len(joined) > 100:
            lines += [f"  {n}" for n in g.cases] + [":"]
        else:
            lines.append(f"{joined}:")
        if isinstance(out, Undefined):
            grids.add((Undefined, out.reason))
            lines += [f"  {ln}" for ln in why]
        elif isinstance(out, Resolutions):
            from checker.render.commands import souffle_text
            for i, grid in enumerate(out.grids):
                grids.add(grid)
                head = souffle_text(solver, out.values[i],
                                    TIEBREAK_RESOLUTION) \
                    if i < len(out.values) else f"grid {i + 1}"
                lines.append(f"  {head}:")
                lines += [f"    {r}" for r in grid_lines(grid)]
        else:
            grids.add(out)
            lines += [f"  {r}" for r in grid_lines(out)]
    bases = len({c.base for c in cases})
    if silent:
        lines.append("")
        lines += [mctx("{name}: emits nothing").format(name=n)
                  if isinstance(r, NoOutput) or (
                      r is None and not takes_branch(solver, n))
                  else mctx("{name}: undefined").format(name=n)
                  for n, r in silent]
    if len(cases) > 1:
        from checker.render.commands import COUNT_LINE
        lines += ["", COUNT_LINE.format(bases=bases, cases=len(cases),
                                        g=len(grids))]
    return lines


# The `derive` block


def derive_lines(solver: Solver, survey: object) -> list[str]:
    """The `derive` command's output
    ([Develop](docs/handbook/procedure.md#develop)): one block per
    derivation whose model does not miss Fit, then each witness the
    command built, as `record` prints it."""
    from checker.branches import SwapWitness
    from checker.derive import DeriveSurvey, Excluded, Unplaced

    assert isinstance(survey, DeriveSurvey)
    if not survey.derivations:
        return [mctx("no built-in derivation fits")]
    lines: list[str] = []
    for d in survey.derivations:
        name = branch_name(d.name)
        lines.append(mctx("{param}: {proposer} — {comment}").format(
            param=d.parameter, proposer=d.proposer.name,
            comment=d.proposer.comment))
        if d.ignored:
            lines.append("  " + mctx("`@ignore: derive` stands in place of "
                                     "its `@derive` line"))
            continue
        if isinstance(d.fit, Unplaced):
            lines.append("  " + unplaced_text(d.name))
            continue
        if isinstance(d.fit, Unread):
            lines.append("  " + mctx(
                "no branch: no case of the solver reads the parameter"))
            if d.concept is None:
                lines.append("  " + mctx(
                    "whether the derivation fits is not judged: no case of "
                    "the solver is the concept case"))
            continue
        if isinstance(d.fit, Excluded):
            lines.append("  " + mctx(
                "the `@ignore: derive <name>` lines under its `@derive` "
                "line exclude every case that takes the branch"))
            continue
        if isinstance(d.fit, NoResult):
            lines.append("  " + mctx(
                "whether `{b}` fits is not judged: the run gives no result "
                "on {pairs}").format(b=name, pairs=", ".join(
                    f"{p.section} {p.index}" for p, _f in d.fit.pairs)))
            continue
        w = d.witness
        if d.entry:
            lines.append("  " + mctx("witness: `{case}` in the witness file"
                                     ).format(case=name))
        elif isinstance(w, SwapWitness):
            lines.append("  " + mctx(
                "witness: train {i} with {stored} and {free} swapped; there "
                "`{case}` differs from `{other}`").format(
                i=w.swap.index, stored=w.swap.stored, free=w.swap.free,
                case=case_name(solver, w.case),
                other=case_name(solver, w.other)))
        else:
            lines.append("  " + mctx("no witness: {reason}").format(
                reason=_no_witness_text(w)))
            lines.append("  " + mctx(
                "a `@derive` line needs a witness whose id is `{case}`"
                ).format(case=name))
        if d.line is not None:
            lines.append("  " + mctx(
                "line {line}: @derive {proposer}: {plausibility} {verdict}"
            ).format(line=d.line.line, proposer=d.proposer.name,
                     plausibility=d.line.plausibility.value,
                     verdict=verdict_text(d.line.verdict)))
            continue
        lines.append("  " + hint_line(Hint(HintKind.DERIVE, d.proposer.name,
                                           site=d.rigid)))
        lines.append("  " + hint_line(Hint(HintKind.IGNORE_DERIVE)))
    return lines


def _no_witness_text(w: object) -> str:
    from checker.branches import FailedOn, NoWitness

    match w:
        case NoWitness.NOT_ONE_COLOR:
            return mctx("the parameter is not one color")
        case NoWitness.NO_FREE_COLOR:
            return mctx("no train input has a free color")
        case FailedOn(grid=grid, failure=failure):
            return mctx("the run fails on {grid} with the stored color "
                        "swapped for a free color: {error}").format(
                grid=grid, error=failure_text(failure))
        case _:
            return mctx("no color swap of a train input shows the branch's "
                        "model defined and giving an output other than the "
                        "model of the stored value")


# The `store` block


def _picture(marks: dict[tuple[int, int], str]) -> list[str]:
    """A cell map drawn as a grid, one row per line; a map of one cell, or
    one that reaches past `DRAW_CAP` along an axis, draws nothing."""
    if len(marks) < 2:
        return []
    ts = [t for t, _l in marks]
    ls = [l for _t, l in marks]
    if max(ts) - min(ts) >= DRAW_CAP or max(ls) - min(ls) >= DRAW_CAP:
        return []
    return [" ".join(marks.get((t, l), ".")
                     for l in range(min(ls), max(ls) + 1))
            for t in range(min(ts), max(ts) + 1)]


def _cell(f: Found, x: object) -> tuple[int, int] | None:

    if getattr(f, "kind") is ValueKind.TRANSLATED:
        return x if isinstance(x, tuple) else None  # type: ignore[return-value]
    return corner(x)


def drawn(f: Found) -> list[str]:
    """A value's picture: its cells, its colored cells, or the offsets it
    stamps; no line where it draws none."""

    if f.rect:
        return [mctx("{rect} rectangle").format(rect=f.rect)]
    if len(f.family) != 1:
        return []
    one = f.one
    if len(f.types) == 1 and f.types[0] in POSITION_TYPES:
        cells = [_cell(f, m[0]) for m in one]
        if all(c is not None for c in cells):
            return _picture({c: "#" for c in cells if c is not None})
        return []
    if len(f.types) == 2:
        pos = [i for i, t in enumerate(f.types) if t in POSITION_TYPES]
        col = [i for i, t in enumerate(f.types) if t == "Color"]
        if len(pos) == 1 and len(col) == 1:
            colored = {c: str(m[col[0]]) for m in one
                       if (c := _cell(f, m[pos[0]])) is not None}
            if len(colored) == len(one):
                return _picture(colored)
        return []
    if len(f.types) == 1 and f.types[0] == "Offset":
        marks = {c: "#" for m in one if (c := corner(m[0])) is not None}
        marks[(0, 0)] = "@"
        return _picture(marks)
    return []


def _noun(f: Found) -> str:

    one = len(f.family) == 1
    if f.rect or (one and len(f.types) == 1
                  and f.types[0] in POSITION_TYPES) or (
            one and len(f.types) == 2
            and any(t in POSITION_TYPES for t in f.types)
            and "Color" in f.types and drawn(f)):
        return mctx("cell set")
    if one and len(f.types) == 1 and f.types[0] == "Offset":
        return mctx("offset set")
    return mctx("value")


def _in_case(solver: Solver, f: Found) -> str:

    if f.read or not f.used_in:
        return ""
    return mctx("; under `{case}`").format(case=under_text(f.used_in))


def under_text(names: Sequence[str]) -> str:
    """The names after `; under`, in the order of their text."""
    return ", ".join(sorted(names))


def _headline(solver: Solver, f: Found) -> str:

    rel = f.relation.text
    name = f"{rel}[{', '.join(f.columns)}]" if f.sub else rel
    if f.line is not None and f.line.line is not None \
            and f.kind is ValueKind.OWNED:
        return mctx("{name}: @store at line {line}").format(
            name=name, line=f.line.line.line)
    if f.kind is ValueKind.CONSTANT:
        keys = _ticked(f.keys) or mctx("the key")
        return mctx("{name}: {n} {noun}s, one per {keys}").format(
            name=name, n=len(f.family), noun=_noun(f), keys=keys)
    if f.kind is ValueKind.TRANSLATED:
        return mctx("{name}: one {noun} up to translation on every input"
                    ).format(name=name, noun=_noun(f))
    members = sorted(f.one, key=_printed)
    if f.colors:
        value = inline_text(solver, f.types, members)
        if f.asks_params:
            return mctx("{name}: one color on every input: {value}; store "
                        "it in Params").format(name=name, value=value)
        return mctx("{name}: one color on every input: {value}").format(
            name=name, value=value) + _in_case(solver, f)
    if drawn(f):
        return mctx("{name}: one {noun} on every input").format(
            name=name, noun=_noun(f)) + _in_case(solver, f)
    if len(members) > SHOWN_MEMBERS:
        return mctx("{name}: one value set of {n} members on every input"
                    ).format(name=name, n=len(members)) + _in_case(solver, f)
    return mctx("{name}: one value on every input: {value}").format(
        name=name, value=inline_text(solver, f.types, members)) + _in_case(solver, f)


def _witness_line(solver: Solver, f: Found) -> str:

    if f.homonyms:
        return homonyms_text(HomonymsPayload(f.name, (f.relation,
                                                      *f.homonyms)))
    if f.entry:
        return mctx("witness: `{case}` in the witness file").format(
            case=f.case_id)
    if f.untaken:
        return untaken_text()
    ask = mctx("`{case}` needs a witness whose id is `{case}`").format(
        case=f.case_id)
    if f.move is None:
        why = mctx("no D4 image or color swap of a train input changes the "
                   "value")
        if f.failed is not None:
            why = mctx("the run fails on {grid}: {error}").format(
                grid=f"train {f.failed.index} "
                     f"{transform_text(f.failed.change)}",
                error=failure_text(f.failed.failure))
        return mctx("no witness: {why}; {ask}").format(why=why, ask=ask)
    line = mctx("witness: {grid} {change}").format(
        grid=f"train {f.move.index}", change=transform_text(f.move.change))
    if f.move.identity and f.read:
        line += mctx("; the concept case gives the input unchanged")
    elif f.move.identity:
        line += mctx("; the case under `{case}` gives the input unchanged"
                     ).format(case=under_text(f.used_in))
    return line


def _store_hints(f: Found, alone: bool = False) -> list[str]:

    named, site = f.named, f.site
    if alone:
        return [hint_line(Hint(HintKind.IGNORE_STORE, relation=named,
                               site=site, alone=True))]
    return [hint_line(Hint(HintKind.STORE, relation=named, site=site)),
            hint_line(Hint(HintKind.IGNORE_STORE, relation=named,
                           site=site))]


def _no_case_text(f: Found) -> str:

    if f.kind is ValueKind.TRANSLATED:
        return mctx("stands at another place on each input, and the runner "
                    "picks no anchor")
    return mctx("varies by {keys}, an id the runner stores nothing under"
                ).format(keys=_ticked(f.keys))


def store_lines(solver: Solver, survey: StoreSurvey) -> list[str]:
    """The `store` command's output
    ([Develop](docs/handbook/procedure.md#develop)): the markers under
    which cases they do not list read clauses and the inputs whose run
    fails, each `@store` line on a relation with an `Ident` column, one
    block per value some case reads, the relations over the row cap, then
    each witness the command built, as `record` prints it."""

    keyed = [f for f in survey.findings if f.kind == Kind.STORE_IDENT_KEY]
    if not survey.between:
        return [ln for f in in_line_order(keyed)
                for ln in finding_lines(solver, f)] \
            + [NOT_BETWEEN]
    lines: list[str] = []
    for f in in_line_order((*survey.markers, *survey.failed, *keyed)):
        lines += finding_lines(solver, f)
    shown = shown_case_names(survey.found)

    def rank(f: Found) -> tuple[object, ...]:
        """The old tool's order: the concept case's values first, where no
        column carries the case as the markers place the clauses that feed
        it; then those the concept case reads; the owned values before the
        others; then by relation and columns."""
        concept = f.concept if f.case_values else f.concept_section
        return (not concept, not f.read, f.kind is not ValueKind.OWNED,
                f.relation.text, f.columns)

    for f in sorted(survey.listed, key=rank):
        lines.append(_headline(solver, f) + _cases_suffix(shown(f)))
        if f.ignored:
            lines.append("  " + mctx("`@ignore: store` stands in place of "
                                     "its `@store` line"))
        elif f.store_branch and f.line is None:
            lines += ["  " + ln for ln in drawn(f)]
            lines.append("  " + _witness_line(solver, f))
            lines += ["  " + ln for ln in _store_hints(f)]
        elif f.store_branch:
            lines.append("  " + _witness_line(solver, f))
        elif f.asks_params:
            lines += ["  " + ln for ln in _store_hints(f, alone=True)]
        elif f.kind is not ValueKind.OWNED:
            lines += ["  " + ln for ln in drawn(f)]
            lines.append("  " + mctx("no case: the value {why}").format(
                why=_no_case_text(f)))
    if survey.capped:
        lines.append(row_cap_text(ROW_CAP, [r.text for r in survey.capped]))
    return lines or [mctx("no findings")]
