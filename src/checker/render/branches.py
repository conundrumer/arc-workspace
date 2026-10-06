"""The sentences of the `@derive` and `@store` kinds: each finding's
sentence, and the phrases the `derive` and `store` blocks and the
determination section build from them."""

from collections.abc import Sequence

from checker.finding import AtFile, Finding, Kind
from checker.judged import Swap
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
    LineForm,
    _no_sentence,
    _ticked,
    arg_text,
    cases_run_failed,
    line_list,
    line_text,
    under_case,
    where_text,
)
from solver.names import name as case_name
from checker.store import (
    D4,
    Change,
    member_key,
)
from controlled_markdown import mctx
from engine import AdtValue, RecordValue
from solver.annotations import DirectiveWord, IgnoreForm, at_word
from solver.model import DeriveBranch, StoreBranch
from solver.aggregate import Solver
from solver.names import branch_text
from solver.solve import (
    PairId,
    TaskSection,
)
from solver.witness import (
    Entry,
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


def entry_input(entry: Entry) -> str:
    """A recorded entry's input, at its assignment where it gives one."""
    return mctx("the input of `{id}`{at}").format(
        id=entry.id, at=" " + mctx("at its assignment") if entry.assign
        else "")


def needs_witness(word: str, id: str) -> str:
    """The sentence asking for a branch's witness under the id `id`, said
    in the `derive` and `store` blocks; the audit reports the unseparated
    pair in its place."""
    return mctx("a `{word}` line needs a witness whose id is `{b}`").format(
        word=word, b=id)


def diff_line(parameters: Sequence[str]) -> str:
    """The determination line naming the parameters whose rows differ."""
    return mctx("determination: DIFF on ") + ", ".join(parameters)


def differing(solver: Solver, p: DeterminationDiffPayload) -> list[str]:
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
        b=branch_text(branch), first=_first(branch), input=entry_input(entry))


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


def cases_suffix(names: Sequence[str]) -> str:
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
                                                why=no_anchor_text())
        case KeyedBy(keys=keys):
            return mctx("`{rel}` {why}").format(rel=rel,
                                                why=keyed_text(keys))
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


def finding_text(solver: Solver, f: Finding) -> str:
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
                        "`@ignore: store` line") + cases_suffix(p.cases)
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
                + cases_suffix(cases)
        case Kind.STORE_ROW_CAP, RowCapPayload(relations=rels, cap=cap):
            return row_cap_text(cap, [r.text for r in rels])
        case Kind.DETERMINATION_DIFF, DeterminationDiffPayload() as d:
            return diff_line(differing(solver, d))
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
    text = finding_text(solver, f)
    if f.kind in (Kind.DETERMINATION_DIFF, Kind.DETERMINATION_OF_DERIVED,
                  Kind.NOT_CHECKED) \
            or (f.kind == Kind.STORE_ROW_CAP and isinstance(f.where, AtFile)):
        return [text]
    return [f"{where_text(solver, f.where, form)}: {text}"]


def no_anchor_text() -> str:
    """Why a value that moves with the input is stored at no case."""
    return mctx("stands at another place on each input, and the runner "
                "picks no anchor")


def keyed_text(keys: Sequence[str]) -> str:
    """Why a value keyed by an id is stored at no case."""
    return mctx("varies by {keys}, an id the runner stores nothing under"
                ).format(keys=_ticked(keys))
