"""The sentences of faults, the sentences of an annotation line off its
form among them."""

from collections.abc import Sequence

from checker.finding import FaultPayload, Finding
from checker.render.locations import LineForm, line_list, line_text, where_text
from controlled_markdown import mctx
from engine import Engine, GridLayout, ParseFailure, RelationName
from solver import names
from solver.aggregate import Solver
from solver.annotations import (
    NESTS_UNDER,
    ClaimKind,
    DirectiveWord,
    HeaderWord,
    Plausibility,
    at_word,
    header_word_text,
)
from solver.model import DeriveBranch
from solver.problems import (
    AnchorWithoutStamp,
    AssignArity,
    AssignType,
    CaseColumnOffForm,
    Detail,
    Expected,
    FormPart,
    GridCellOffForm,
    GridOffLayout,
    Named,
    OffForm,
    OffFormType,
    OutputForm,
    OutputOffVerdict,
    ProblemKind,
    Quoted,
    ShapeFault,
    Storage,
    VerdictsDisagree,
)
from solver.problems import Undecided as UndecidedDetail

_ASSIGN_VALUE = mctx("the `assign` value of {text}")
"""The sentence of an `assign` value off its relation's columns, by
arity (`AssignArity`) or by type (`AssignType`)."""
NO_ASSIGN_VALUE = mctx("no lib constant and no constructor without "
                       "arguments of an ADT the solver or the lib declares")
"""What an `assign` string value that refers to nothing is not."""
SEE_WITNESS_FILE = mctx("{text}; see [Witness file]"
                        "(docs/handbook/solver-file.md#witness-file)")
"""A fault's text, then the handbook section that gives the witness
file's form."""
OTHER_HOLDS_JUDGED = mctx("the verdict `other`, whose witness holds the "
                          "judged output")

PROBLEM_TEXT: dict[ProblemKind, str] = {
    ProblemKind.PARSE_FAILURE: mctx("the solver does not parse: {text}"),
    ProblemKind.RETIRED_FORM: mctx(
        "`{text}` is an annotation form the handbook retired; see "
        "[File structure](docs/handbook/solver-file.md#file-structure)"),
    ProblemKind.UNKNOWN_FORM: mctx(
        "`{text}` is no annotation form; see "
        "[File structure](docs/handbook/solver-file.md#file-structure)"),
    ProblemKind.OFF_FORM: mctx(
        "{text}; see "
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
        "the witness file is off its shape: ") + SEE_WITNESS_FILE,
    ProblemKind.NAME_DENOTES_NO_CASE: mctx(
        "the name `{text}` denotes no case of the solver"),
    ProblemKind.NAME_FORM: mctx(
        "`{text}` is in no form [Witness file]"
        "(docs/handbook/solver-file.md#witness-file) lists"),
    ProblemKind.OUTPUT_OFF_VERDICT: SEE_WITNESS_FILE,
    ProblemKind.VERDICTS_DISAGREE: SEE_WITNESS_FILE,
    ProblemKind.ASSIGN_NAMES_NOTHING: mctx(
        "the `assign` key `{text}` is no parameter of the solver and no "
        "`@store` line's relation"),
    ProblemKind.ASSIGN_VALUE_UNKNOWN: mctx(
        "the `assign` value `{text}` is ") + NO_ASSIGN_VALUE,
    ProblemKind.ASSIGN_ARITY: _ASSIGN_VALUE,
    ProblemKind.ASSIGN_TYPE: _ASSIGN_VALUE,
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
    ProblemKind.CASE_COLUMN_OFF_FORM: mctx(
        "{text}; see [Params](docs/handbook/solver-file.md#params)"),
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


SLUG_FORM = mctx("lowercase letters and digits, in words joined by single "
                 "`-`")
"""The form of a slug, which a witness id takes too."""

OFF_PART_TEXT: dict[FormPart, str] = {
    FormPart.SLUG: mctx("the slug `{read}` is off its form, ") + SLUG_FORM,
    FormPart.ID: mctx("the id `{read}` is off a slug's form, ") + SLUG_FORM,
    FormPart.PROPOSER: mctx("the proposer `{read}` is off its form, one word "
                            "of letters, digits and `_`"),
    FormPart.RELATION: mctx("the relation `{read}` is off its form, letters, "
                            "digits, `_` and `.`"),
    FormPart.SPACING: mctx("`{read}` takes one space or more before it, and "
                           "none between it and the `:`"),
    FormPart.TRAILING: mctx("`{word}` takes no text after it, and `{read}` "
                            "follows it"),
    FormPart.PLAUSIBILITY: mctx("`{read}` is no plausibility, and a "
                                "plausibility is one of {plausibilities}"),
    FormPart.VERDICT: mctx("the verdict `{read}` is off its form, one word, "
                           "or names joined by `&`"),
    FormPart.VALUE: mctx("`{word}` takes one word, and `{read}` is more than "
                         "one"),
    FormPart.REPRESENTATIVE: mctx("`{read}` is not a task id with at most one "
                                  "case name after it"),
    FormPart.DERIVE_RELATION: mctx("an `@ignore: derive` line names no "
                                   "relation, and this one names `{read}`"),
}
"""The sentence of each part of an annotation line off its form, from the
part as the line writes it."""

MISSING_PART_TEXT: dict[FormPart, str] = {
    FormPart.INDENT: mctx("`{word}` is a nested line, with two spaces or more "
                          "after `//`"),
    FormPart.PARENT: mctx("`{word}` nests under {under} line that is in its "
                          "own form, and it stands under none"),
    FormPart.SLUG: mctx("the slug is missing"),
    FormPart.ID: mctx("the id is missing"),
    FormPart.PROPOSER: mctx("the proposer is missing"),
    FormPart.SPACING: mctx("the `:` takes no space before it"),
    FormPart.COLON: mctx("the `:` is missing"),
    FormPart.TEXT: mctx("no text follows the `:`"),
    FormPart.PLAUSIBILITY: mctx("the plausibility is missing"),
    FormPart.VERDICT: mctx("the verdict is missing"),
    FormPart.VALUE: mctx("`{word}` takes one word, and none follows it"),
    FormPart.DASH: mctx("the `—` before the reason is missing"),
    FormPart.REASON: mctx("no reason follows the `—`"),
}
"""The sentence of each part of an annotation line off its form that the
line does not write: missing, or a line's place."""


def _either(words: Sequence[str]) -> str:
    ticked = [f"`{w}`" for w in words]
    if len(ticked) == 1:
        return ticked[0]
    return mctx("{some} or {last}").format(some=", ".join(ticked[:-1]),
                                           last=ticked[-1])


def off_form_text(detail: OffForm) -> str:
    """An annotation line off its form, with each part of it that breaks
    the form."""
    word = (header_word_text(detail.word)
            if isinstance(detail.word, HeaderWord | ClaimKind)
            else at_word(detail.word))
    parts: list[str] = []
    for off in detail.parts:
        text = MISSING_PART_TEXT[off.part] if off.read is None \
            else OFF_PART_TEXT[off.part]
        under = None
        if off.part == FormPart.PARENT:
            assert isinstance(detail.word, DirectiveWord)
            parents = NESTS_UNDER[detail.word]
            article = "an" if parents[0].value[0] in "aeiou" else "a"
            under = f"{article} " + _either([at_word(w) for w in parents])
        parts.append(text.format(
            read=off.read, word=word, under=under,
            plausibilities=_either([p.value for p in Plausibility])))
    return mctx("`{text}` is off its annotation's form: {parts}").format(
        text=detail.text, parts="; ".join(parts))


def detail_text(engine: Engine, detail: Detail) -> str:
    """The part of a fault its sentence names."""
    match detail:
        case Quoted(text=text):
            return text
        case OffForm() as off:
            return off_form_text(off)
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
            stored = (mctx("in a `{form}` call").format(
                form=engine.text(storage))
                      if isinstance(storage, GridLayout) else STORAGE_TEXT[storage])
            return mctx("`{name}` a grid with an anchor, and the solver "
                        "stores `{name}` {stored}, not by one `GRID_STAMP` "
                        "call").format(name=name, stored=stored)
        case GridCellOffForm(name=name, layout=layout, cell=(r, c),
                             value=v):
            return mctx("`{name}` the value {v} at row {r}, column {c}, and "
                        "its `{form}` layout takes 1 for a member and 0 for "
                        "an empty cell").format(
                            name=name, v=v, r=r, c=c, form=engine.text(layout))
        case AssignArity(name=name, given=given, expected=expected,
                         per_case=per_case):
            text = mctx("`{name}` has facts of {got} arguments, and the "
                        "relation `{name}` takes {want}").format(
                name=name, want=expected,
                got=" and ".join(str(n) for n in given))
            return mctx("{text} outside its case part").format(
                text=text) if per_case else text
        case CaseColumnOffForm(relation=relation, column=column, type=t,
                               kind=off):
            kind = (mctx("a record with a field of an ADT in `Choice`")
                    if off is OffFormType.RECORD
                    else mctx("an ADT in `Choice`"))
            return mctx("the column `{column}` of `{relation}` is of type "
                        "`{t}`, {kind}, and the case column of a relation "
                        "in Params is in the form of `out`'s, of type "
                        "`Choice`").format(column=column, relation=relation,
                                           t=t.text, kind=kind)
        case AssignType(name=name, column=column, type=t, arg=arg):
            return SEE_WITNESS_FILE.format(text=mctx(
                "`{name}` gives `{arg}` in the column `{column}`, and that "
                "column takes a value of type `{t}`").format(
                name=name, arg=arg, column=column,
                t=t if isinstance(t, str) else f"[{', '.join(t)}]"))
        case GridOffLayout(name=name, layout=layout, given=(h, w)):
            if layout is None:
                return mctx("`{name}` a {h}x{w} grid, and the solver stores "
                            "`{name}` by no one GRID call whose layout "
                            "places it").format(name=name, h=h, w=w)
            return mctx("`{name}` a {h}x{w} grid with no anchor, and the "
                        "solver's `GRID_STAMP` layout for `{name}` is "
                        "{lh}x{lw}").format(name=name, h=h, w=w,
                                            lh=layout.height, lw=layout.width)
        case OutputOffVerdict() as off:
            return _output_off_verdict_text(off)
        case VerdictsDisagree(other=other, another=another):
            return mctx("{other} {verb} {judged}, and {another} {verb2} "
                        "another verdict, whose witness holds groups; make "
                        "these lines agree on whether the witness's output "
                        "is judged").format(
                other=line_list(other), verb=records(other),
                judged=OTHER_HOLDS_JUDGED, another=line_list(another),
                verb2=records(another))
        case ParseFailure():
            return parse_failure_text(detail)


def parse_failure_text(failure: ParseFailure) -> str:
    """Where parsing stopped, and the parser's message."""
    return f"{failure.line}:{failure.column}: {failure.message}"


def records(lines: Sequence[int]) -> str:
    """The verb of `lines` as the subject of a sentence."""
    return mctx("records") if len(lines) == 1 else mctx("record")


def _output_off_verdict_text(off: OutputOffVerdict) -> str:
    """A witness entry's `output` against the verdict that records it, and
    the form `record` writes in its place."""
    if off.held is OutputForm.GROUPS:
        if off.line is None:
            raise ValueError("groups where no line records a verdict are in "
                             "the form the witness file takes")
        return mctx("the `output` holds groups, and {line} records "
                    "{judged}; write the judged output into the entry with "
                    "`record`").format(line=line_text(off.line),
                                       judged=OTHER_HOLDS_JUDGED)
    against = (mctx("no line records a verdict for the entry")
               if off.line is None else
               mctx("{line} records another verdict").format(
                   line=line_text(off.line)))
    return mctx("the `output` is a bare grid, the judged output of the "
                "verdict `other`, and {against}; write the groups into the "
                "entry with `record`").format(against=against)


STORAGE_TEXT: dict[Storage, str] = {
    Storage.FACTS: mctx("as facts"),
    Storage.GRID_CALLS: mctx("in several GRID calls"),
    Storage.STORED_RELATION: mctx("as a `@store` relation"),
}
"""How a name with no one GRID call is stored, as the anchor fault says
it."""


def reading_lines(solver: Solver, f: Finding, p: FaultPayload,
                   form: LineForm) -> list[str]:
    text = PROBLEM_TEXT[p.problem.kind].format(
        text=detail_text(solver.engine, p.problem.detail))
    return [f"{where_text(solver, f.where, form)}: {text}"]
