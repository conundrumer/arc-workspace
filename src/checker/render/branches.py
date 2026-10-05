"""The sentences of the `@derive` and `@store` kinds, of the determination
check, and of the `derive` and `store` command blocks."""

from collections.abc import Sequence

from checker.finding import AtFile, Finding, Kind
from checker.judged import NO_TASK, NoResult, Swap
from checker.payloads.branches import (
    BranchEntryPayload,
    BranchName,
    BranchPayload,
    ColorAskPayload,
    DerivedDataPayload,
    DeriveFitPayload,
    DeterminationDiffPayload,
    DiffersOn,
    DuplicatePayload,
    ExcludedPayload,
    HomonymsPayload,
    IdleIgnorePayload,
    KeyedBy,
    MissingLinePayload,
    NoAnchor,
    NoRows,
    NoTaskPayload,
    NotBetween,
    NotCheckedPayload,
    NoValue,
    RelationPayload,
    RowCapPayload,
    StoreNoValuePayload,
    StoreValuesPayload,
    Unread,
)
from checker.render import (
    Hint,
    HintKind,
    LineForm,
    _no_sentence,
    _ticked,
    arg_text,
    cases_run_failed,
    failure_text,
    finding_lines,
    grid_lines,
    hint_line,
    in_line_order,
    line_list,
    line_text,
    resolution_lines,
    shifted,
    under_case,
    where_text,
)
from solver.names import name as case_name
from checker.runs import NoTask
from checker.store import (
    D4,
    POSITION_TYPES,
    ROW_CAP,
    Change,
    Found,
    StoreSurvey,
    ValueKind,
    corner,
    member_key,
    shown_case_names,
)
from controlled_markdown import mctx
from engine import AdtValue, RecordValue
from engine.program import dotted
from solver.annotations import DirectiveWord, IgnoreForm, at_word, derive_text, ignore_text
from solver.model import Case, DeriveBranch, Solver, StoreBranch
from solver.names import Denoted, branch_text, denote
from solver.solve import (
    Determined,
    DetermineResult,
    NoDetermine,
    PairId,
    TaskSection,
)
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

BRANCH_KINDS = frozenset({
    Kind.IDLE_BRANCH_IGNORE, Kind.MISSING_BRANCH_LINE,
    Kind.DUPLICATE_BRANCH_LINE,
    Kind.BRANCH_ENTRY, Kind.BRANCH_EXCLUDED, Kind.DERIVE_UNREAD,
    Kind.DERIVE_FIT,
    Kind.DERIVE_UNPLACED, Kind.STORE_PARAMETER_NAME, Kind.STORE_VALUES,
    Kind.STORE_NO_VALUE, Kind.STORE_UNTAKEN, Kind.STORE_HOMONYMS,
    Kind.STORE_IDENT_KEY,
    Kind.STORE_PARAMS_ASK, Kind.STORE_ROW_CAP,
    Kind.DETERMINATION_DIFF, Kind.DETERMINATION_OF_DERIVED, Kind.NO_TASK,
    Kind.NOT_CHECKED,
})
"""The kinds whose sentence this module writes."""

GROUP_WIDTH = 100
"""The widest a witness group's line of case names stands; a wider
group puts each name on a line of its own."""

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
    return at_word(DirectiveWord.DERIVE if isinstance(branch, DeriveBranch)
                   else DirectiveWord.STORE)


def _first(branch: BranchName) -> str:
    """The first branch of the branch's point, in words."""
    return (mctx("the stored value") if isinstance(branch, DeriveBranch)
            else mctx("the derived value"))


def transform_text(change: Change) -> str:
    """How a witness grid comes from a train input: a color swap, or a D4
    element in words."""
    match change:
        case Swap(stored=a, free=b):
            return mctx("with {a} and {b} swapped").format(a=a, b=b)
        case D4():
            return D4_TEXT[change]


def train_text(index: int) -> str:
    """The train input of `index`, as a pair is named
    (`solver.solve.PairId.text`)."""
    return PairId(TaskSection.TRAIN, index).text


def separates(branch: BranchName, train: int, change: Change) -> str:
    """The `separates` of a witness a survey builds: the branch, the
    point's first branch, and how the grid comes from the train input of
    index `train`."""
    return mctx("`{b}` from {first}: {grid} {change}").format(
        b=branch_text(branch), first=_first(branch), grid=train_text(train),
        change=transform_text(change))


def _entry_input(entry: Entry) -> str:
    """A recorded entry's input, at its assignment where it gives one."""
    return mctx("the input of `{id}`{at}").format(
        id=entry.id, at=" " + mctx("at its assignment") if entry.assign
        else "")


def _needs_witness(word: str, id: str) -> str:
    """The sentence asking for a branch's witness under the id `id`, said
    in the `derive` and `store` blocks; the audit reports the unseparated
    pair in its place."""
    return mctx("a `{word}` line needs a witness whose id is `{b}`").format(
        word=word, b=id)


def _diff_line(parameters: Sequence[str]) -> str:
    """The determination line naming the parameters whose rows differ."""
    return mctx("determination: DIFF on ") + ", ".join(parameters)


def _differing(solver: Solver, p: DeterminationDiffPayload) -> list[str]:
    """The parameter whose rows differ, and for a parameter that stores a
    value per case, each base at which they differ, or that the run that
    enumerates the cases failed."""
    param = p.diff.parameter
    if p.bases is None:
        return [param]
    if not isinstance(p.bases, tuple):
        return [mctx("{param} at cases not known, since {failed}").format(
            param=param, failed=cases_run_failed(p.bases))]
    if not p.bases:
        raise ValueError(f"a determination finding on {param} at no case")
    return [under_case(param, case_name(solver, b)) for b in p.bases]


def separates_recorded(branch: BranchName, entry: Entry) -> str:
    """The `separates` of a witness a survey builds from an input of the
    witness file: the branch, the point's first branch, and the entry
    whose input it takes."""
    return mctx("`{b}` from {first}: {input}").format(
        b=branch_text(branch), first=_first(branch), input=_entry_input(entry))


def _idle_text(p: IdleIgnorePayload) -> str:
    derive = p.ignore.form is IgnoreForm.DERIVE
    word = at_word(DirectiveWord.DERIVE if derive else DirectiveWord.STORE)
    if p.under is None:
        return (mctx("no `{word}` line stands above this line")
                if derive else
                mctx("no `{word}` line stands above the relation under "
                     "this line")).format(word=word)
    return mctx("this line excludes no case: no case of the solver takes "
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
            return mctx("`{rel}` {why}").format(rel=rel,
                                                why=_no_anchor_text())
        case KeyedBy(keys=keys):
            return mctx("`{rel}` {why}").format(rel=rel,
                                                why=_keyed_text(keys))
        case DiffersOn(pair=pair):
            return mctx("`{rel}` gives another value on {grid}").format(
                rel=rel, grid=pair.text)
        case NoRows():
            return mctx("`{rel}` gives no value the runner can store"
                        ).format(rel=rel)


def homonyms_text(p: HomonymsPayload) -> str:
    rels = [f"`{r.text}`" for r in sorted(p.relations, key=lambda r: r.text)]
    return mctx("`{b}` denotes the `@store` branches of {n} relations, "
                "{rels} and {last}").format(
        b=branch_text(p.branch), n=len(rels), rels=", ".join(rels[:-1]),
        last=rels[-1])


def _member_text(solver: Solver, types: Sequence[str],
                 member: Sequence[object]) -> str:
    def shown(t: str, v: object) -> str:
        if isinstance(v, tuple):
            return f"({', '.join(str(x) for x in v)})"
        if isinstance(v, (int, str, AdtValue, RecordValue)):
            return arg_text(v, t, solver.lib)
        return str(v)

    if len(member) == 1:
        return shown(types[0], member[0])
    return "(" + ", ".join(shown(t, v) for t, v in zip(types, member)) + ")"


def inline_text(solver: Solver, types: Sequence[str],
                members: Sequence[Sequence[object]]) -> str:
    """A value as one phrase: its members, each as the solver writes it,
    an orientation under the constant that denotes it."""
    return ", ".join(_member_text(solver, types, m)
                     for m in sorted(members, key=lambda m: member_key(tuple(m))))


def color_ask_text(solver: Solver, types: Sequence[str],
                   members: Sequence[Sequence[object]]) -> str:
    """The sentence that asks for a value of one color on every input to
    be a parameter (principles.md, under "Stored or derived"), its members as
    `inline_text` writes them."""
    return mctx("one color on every input: {value}; make it a "
                "parameter").format(value=inline_text(solver, types,
                                                      members))


def _branch_text(solver: Solver, f: Finding) -> str:
    """A finding's sentence, after its location."""
    p = f.payload
    match f.kind, p:
        case Kind.IDLE_BRANCH_IGNORE, IdleIgnorePayload():
            return _idle_text(p)
        case Kind.MISSING_BRANCH_LINE, MissingLinePayload(branch=DeriveBranch() as b):
            return mctx("`{b}` fits and has no `@derive` or `@ignore: derive` "
                        "line").format(b=branch_text(b))
        case Kind.MISSING_BRANCH_LINE, MissingLinePayload(branch=StoreBranch()):
            return mctx("one value on every input and no `@store` or "
                        "`@ignore: store` line") + _cases_suffix(p.cases)
        case Kind.DUPLICATE_BRANCH_LINE, DuplicatePayload(
                branch=DeriveBranch() as b, first_line=n):
            return mctx("a second `@derive` line of `{b}`; the first is "
                        "{line}").format(b=branch_text(b), line=line_text(n))
        case Kind.DUPLICATE_BRANCH_LINE, DuplicatePayload(
                branch=StoreBranch() as b, second_line=n):
            return mctx("`{rel}` has a second `@store` line at {line}, so "
                        "`{b}` denotes two branches").format(
                rel=b.spelled, line=line_text(n), b=branch_text(b))
        case Kind.BRANCH_ENTRY, BranchEntryPayload(branch=b):
            return mctx("at the witness's assignment, each case that takes "
                        "`{b}` gives the output of the case that takes "
                        "{first} there and the same branches elsewhere"
                        ).format(b=branch_text(b), first=_first(b))
        case Kind.BRANCH_EXCLUDED, ExcludedPayload(
                branch=b, ignores=lines, impl_choice=impl):
            by = ([mctx("the `@ignore` line at {lines}") if len(lines) == 1
                   else mctx("the `@ignore` lines at {lines}")] if lines
                  else []) + ([mctx("`impl_choice`")] if impl else [])
            one = len(by) == 1 and len(lines) <= 1
            return (mctx("no case of the solver takes `{b}`, so its verdict "
                         "is not judged; {by} excludes its cases") if one
                    else mctx("no case of the solver takes `{b}`, so its "
                              "verdict is not judged; {by} exclude its cases")
                    ).format(b=branch_text(b), by=(" " + mctx("and") + " ").join(by).format(
                        lines=line_list(lines)))
        case Kind.DERIVE_UNREAD, BranchPayload():
            return mctx("`@derive` stands above a parameter no case of the solver "
                        "reads")
        case Kind.DERIVE_FIT, DeriveFitPayload(branch=b, pair=pair):
            return mctx("`{b}` fails Fit at {pair}").format(
                b=branch_text(b),
                pair=pair.text)
        case Kind.DERIVE_UNPLACED, BranchPayload(branch=b):
            return unplaced_text(b)
        case Kind.STORE_PARAMETER_NAME, BranchPayload(
                branch=StoreBranch(spelled=r)):
            return mctx("the `@store` line is on `{r}`, which is also the "
                        "name of a parameter, so `{r}=stored` denotes two "
                        "branches").format(r=r)
        case Kind.STORE_VALUES, StoreValuesPayload(branch=b, values=n,
                                                    cases=cases):
            rel = b.spelled
            return mctx("`{r}` holds {n} values at {cases}, so `{b}` "
                        "denotes {n} branches there").format(
                r=rel, n=n, b=branch_text(b),
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
        case Kind.STORE_PARAMS_ASK, ColorAskPayload(
                types=types, value=value, cases=cases):
            return color_ask_text(solver, types, value) \
                + _cases_suffix(cases)
        case Kind.STORE_ROW_CAP, RowCapPayload(relations=rels, cap=cap):
            return row_cap_text(cap, [r.text for r in rels])
        case Kind.DETERMINATION_DIFF, DeterminationDiffPayload() as d:
            return _diff_line(_differing(solver, d))
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


def unplaced_text(b: BranchName) -> str:
    return mctx("whether `{b}` fits is not judged: the runner finds no "
                "`.decl` of the parameter in `Params`, and no `RIGID` call "
                "whose chart it is, to put its `@derive` line above"
                ).format(b=branch_text(b))


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
        return [mctx("determination: ") + _branch_text(solver, NO_TASK)]
    lines: list[str] = []
    if isinstance(result, Determined):
        scopes = {u.id: u.scope for u in solver.program.units}
        lines += [mctx("circular determination: ") + ", ".join(
            mctx("{param} reads params.{reads} ({comp} {line})").format(
                param=r.parameter, reads=r.reads,
                comp=dotted(scopes[r.unit].components),
                line=line_text(r.line))
            for r in cycle) for cycle in result.cycles]
    diffs = [n for f in findings
             if isinstance(f.payload, DeterminationDiffPayload)
             for n in _differing(solver, f.payload)]
    others = [f for f in findings
              if not isinstance(f.payload, DeterminationDiffPayload)]
    for f in in_line_order(others):
        lines += finding_lines(solver, f)
    if diffs:
        lines.append(_diff_line(diffs))
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


def record_lines(entry: Entry, solver: Solver, cases: Sequence[Case],
                 of: int) -> list[str]:
    """A built witness as `record` prints it: the input, each group of
    cases above the grid they give, or above why their cells describe no
    grid (`undefined_lines`), the cases that give none, and the
    count line (`checker.render.commands.COUNT_LINE`): how many `cases`,
    the witnessed cases the groups were built from, of the `of` cases of
    the solver, and the distinct grids."""
    lines = [mctx("input:"), *(shifted(r, "  ") for r in grid_lines(
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
        if len(joined) > GROUP_WIDTH:
            lines += [f"  {n}" for n in g.cases] + [":"]
        else:
            lines.append(f"{joined}:")
        if isinstance(out, Undefined):
            grids.add((Undefined, out.reason))
            lines += [f"  {ln}" for ln in why]
        elif isinstance(out, Resolutions):
            grids.update(out.grids)
            lines += [shifted(r, "  ") for r in resolution_lines(solver, out)]
        else:
            grids.add(out)
            lines += [shifted(r, "  ") for r in grid_lines(out)]
    if silent:
        lines.append("")
        lines += [mctx("{name}: emits nothing").format(name=n)
                  if isinstance(r, NoOutput) or (
                      r is None and not takes_branch(solver, n))
                  else mctx("{name}: undefined").format(name=n)
                  for n, r in silent]
    if of > 1:
        from checker.render.commands import COUNT_LINE
        lines += ["", COUNT_LINE.format(n=len(cases), m=of, g=len(grids))]
    return lines


# The `derive` block


def derive_lines(solver: Solver, survey: object) -> list[str]:
    """The `derive` command's output
    ([Develop](docs/handbook/procedure.md#develop)): one block per
    derivation whose model does not miss Fit, then each witness the
    command built, as `record` prints it."""
    from checker.branches import RecordedWitness, SwapWitness
    from checker.derive import DeriveSurvey, Excluded, Unplaced

    assert isinstance(survey, DeriveSurvey)
    if not survey.derivations:
        return [mctx("no built-in derivation fits")]
    lines: list[str] = []
    for d in survey.derivations:
        name = branch_text(d.name)
        lines.append(mctx("{param}: {proposer} — {comment}").format(
            param=d.parameter, proposer=d.proposer.name,
            comment=d.proposer.comment))
        if d.ignored:
            lines.append("  " + _ignored_text(IgnoreForm.DERIVE))
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
                "line exclude every case that takes the branch; "
                "`// @ignore: derive {proposer} — <reason>` in place of the "
                "`@derive` line excludes the derivation").format(
                    proposer=d.proposer.name))
            continue
        if isinstance(d.fit, NoResult):
            lines.append("  " + mctx(
                "whether `{b}` fits is not judged: the run gives no result "
                "on {pairs}").format(b=name, pairs=", ".join(
                    p.text for p, _f in d.fit.pairs)))
            continue
        w = d.witness
        if d.entry:
            lines.append("  " + _filed_witness(name))
        elif isinstance(w, SwapWitness):
            lines.append("  " + _moved_witness(w.swap.index, w.swap) + mctx(
                "; there `{case}` differs from `{other}`").format(
                case=case_name(solver, w.case),
                other=case_name(solver, w.other)))
        elif isinstance(w, RecordedWitness):
            lines.append("  " + mctx(
                "witness: {input}; there `{case}` differs from `{other}`"
            ).format(
                input=_entry_input(w.entry),
                case=case_name(solver, w.case),
                other=case_name(solver, w.other)))
        else:
            lines.append("  " + mctx("no witness: {reason}").format(
                reason=_no_witness_text(solver, w)))
            lines.append("  " + _needs_witness(at_word(DirectiveWord.DERIVE), name))
        if d.line is not None:
            lines.append("  " + mctx("{line}: {directive}").format(
                line=line_text(d.line.line), directive=derive_text(
                    d.proposer.name, d.line.plausibility,
                    d.line.verdict)))
            continue
        lines.append("  " + hint_line(Hint(HintKind.DERIVE, d.proposer.name,
                                           site=d.rigid)))
        lines.append("  " + hint_line(Hint(HintKind.IGNORE_DERIVE,
                                           d.proposer.name)))
    return lines


def _no_witness_text(solver: Solver, w: object) -> str:
    from checker.branches import FailedOn, NoWitness, Unwitnessed

    recorded = mctx("no input of the witness file shows the branch's model "
                    "defined and giving an output other than the output of "
                    "the stored value's model")
    if isinstance(w, Unwitnessed) and w.pair is not None:
        recorded = mctx(
            "no input of the witness file shows the branch's model `{case}` "
            "defined and giving an output other than `{other}`, the case "
            "that differs from it by this branch alone").format(
            case=case_name(solver, w.pair[0]),
            other=case_name(solver, w.pair[1]))
    match w:
        case Unwitnessed(swap=NoWitness.NOT_ONE_COLOR):
            return mctx("the parameter is not one color, and ") + recorded
        case Unwitnessed(swap=NoWitness.NO_FREE_COLOR):
            return mctx("no train input has a free color, and ") + recorded
        case Unwitnessed(swap=FailedOn(train=train, failure=failure)):
            return mctx("the run fails on {grid} with the stored color "
                        "swapped for a free color: {error}; and ").format(
                grid=train_text(train), error=failure_text(failure)) \
                + recorded
        case _:
            return mctx("no color swap of a train input and ") + recorded


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
    """The cell a member of the value stands for: a translated value's
    member holds its top and left from the set's corner; another value's,
    a Box value (`corner`)."""
    if f.kind is ValueKind.TRANSLATED:
        return x if isinstance(x, tuple) else None  # type: ignore[return-value]
    return corner(x)


def drawn(f: Found) -> list[str]:
    """A value's picture: its cells, its colored cells, or the offsets it
    stamps; no line where it draws none."""

    if f.rect:
        return [mctx("{h}x{w} rectangle").format(h=f.rect.height,
                                                 w=f.rect.width)]
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
        return mctx("{name}: @store at {line}").format(
            name=name, line=line_text(f.line.line.line))
    if f.kind is ValueKind.CONSTANT:
        keys = _ticked(f.keys) or mctx("the key")
        return mctx("{name}: {n} {noun}s, one per {keys}").format(
            name=name, n=len(f.family), noun=_noun(f), keys=keys)
    if f.kind is ValueKind.TRANSLATED:
        return mctx("{name}: one {noun} up to translation on every input"
                    ).format(name=name, noun=_noun(f))
    members = sorted(f.one, key=member_key)
    if f.colors:
        value = inline_text(solver, f.types, members)
        if f.asks_params:
            return f"{name}: {color_ask_text(solver, f.types, members)}"
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


def _filed_witness(name: str) -> str:
    """The witness line of a branch whose witness the witness file holds
    under its name."""
    return mctx("witness: `{case}` in the witness file").format(case=name)


def _moved_witness(train: int, change: Change) -> str:
    """The witness line of a branch whose witness is a train input under
    a change."""
    return mctx("witness: {grid} {change}").format(
        grid=train_text(train), change=transform_text(change))


def _witness_line(solver: Solver, f: Found) -> str:

    if f.homonyms:
        return homonyms_text(HomonymsPayload(f.name, (f.relation,
                                                      *f.homonyms)))
    if f.entry:
        return _filed_witness(f.case_id)
    if f.untaken:
        return untaken_text()
    ask = _needs_witness(at_word(DirectiveWord.STORE), f.case_id)
    if f.move is None:
        why = mctx("no D4 image or color swap of a train input changes the "
                   "value")
        if f.failed is not None:
            why = mctx("the run fails on {grid}: {error}").format(
                grid=f"{train_text(f.failed.index)} "
                     f"{transform_text(f.failed.change)}",
                error=failure_text(f.failed.failure))
        elif f.unseparated is not None:
            model, other = f.unseparated
            why = mctx("on no D4 image or color swap of a train input that "
                       "changes the value does the branch's model `{case}` "
                       "give an output other than `{other}`").format(
                case=case_name(solver, model),
                other=case_name(solver, other))
        return mctx("no witness: {why}; {ask}").format(why=why, ask=ask)
    line = _moved_witness(f.move.index, f.move.change)
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
        return _no_anchor_text()
    return _keyed_text(f.keys)


def _no_anchor_text() -> str:
    """Why a value that moves with the input is stored at no case."""
    return mctx("stands at another place on each input, and the runner "
                "picks no anchor")


def _keyed_text(keys: Sequence[str]) -> str:
    """Why a value keyed by an id is stored at no case."""
    return mctx("varies by {keys}, an id the runner stores nothing under"
                ).format(keys=_ticked(keys))


def _ignored_text(form: IgnoreForm) -> str:
    """A branch whose bare `@ignore` line of `form` stands in place of
    its directive line (`IgnoreForm.directive`)."""
    word = form.directive
    if word is None:
        raise ValueError(f"`@ignore: {form}` stands in place of no line")
    return mctx("`{ignore}` stands in place of its `{word}` line").format(
        ignore=ignore_text(None, form), word=at_word(word))


def store_lines(solver: Solver, survey: StoreSurvey) -> list[str]:
    """The `store` command's output
    ([Develop](docs/handbook/procedure.md#develop)): the inputs whose run
    fails, each `@store` line on a relation with an `Ident` column, one
    block per value some case reads, the relations over the row cap, then
    each witness the command built, as `record` prints it."""

    keyed = [f for f in survey.findings if f.kind == Kind.STORE_IDENT_KEY]
    if not survey.between:
        return [ln for f in in_line_order(keyed)
                for ln in finding_lines(solver, f)] \
            + [NOT_BETWEEN]
    lines: list[str] = []
    for f in in_line_order((*survey.failed, *keyed)):
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
        if f.reads_back and f.line is None:
            lines.append("  " + mctx(
                "stored already: the value reads back the stored rows of "
                "{params}").format(params=", ".join(
                    f"`{p}`" for p in f.reads_back)))
        elif f.ignored:
            lines.append("  " + _ignored_text(IgnoreForm.STORE))
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
