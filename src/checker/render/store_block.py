"""The `store` command block."""

from collections.abc import Sequence

from checker.branches.witnesses import NoFit
from checker.finding import Kind
from checker.payloads.branches import HomonymsPayload
from checker.render import finding_lines, in_line_order
from checker.render.branches import (
    NOT_BETWEEN,
    cases_suffix,
    color_ask_text,
    filed_witness,
    homonyms_text,
    ignored_text,
    inline_text,
    keyed_text,
    moved_witness,
    needs_witness,
    no_anchor_text,
    no_fit_text,
    row_cap_text,
    train_text,
    transform_text,
    unfit_text,
    untaken_text,
)
from checker.render.hints import Hint, HintKind, hint_line
from checker.render.locations import line_text
from checker.render.no_result import CASES_RUN_FAILED, failure_text
from checker.render.values import _ticked
from checker.store.lines import shown_case_names
from checker.store.survey import (
    POSITION_TYPES,
    ROW_CAP,
    Found,
    SearchEnd,
    StoreSurvey,
    ValueKind,
    corner,
    member_key,
)
from controlled_markdown import mctx
from engine import Engine
from solver.aggregate import Solver
from solver.annotations import DirectiveWord, IgnoreForm, at_word
from solver.names import name as case_name

SHOWN_MEMBERS = 8
"""How many members of a value that draws no picture the `store` block
spells out; a larger value goes under its member count."""

DRAW_CAP = 30
"""How far a picture of the `store` block reaches along each axis; a
value whose cells spread further draws none."""



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


def _value_name(f: Found) -> str:
    rel = f.name.spelled
    return f"{rel}[{', '.join(f.columns)}]" if f.sub else rel


def _headline(solver: Solver, f: Found) -> str:

    name = _value_name(f)
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


def _witness_line(solver: Solver, f: Found) -> str:

    if f.homonyms:
        return homonyms_text(HomonymsPayload(f.name, (f.relation,
                                                      *f.homonyms)))
    if f.entry:
        return filed_witness(f.case_id)
    if f.ended is SearchEnd.UNTAKEN:
        return untaken_text()
    if f.ended is SearchEnd.CASES_FAILED:
        return CASES_RUN_FAILED
    if f.ended is not SearchEnd.FOUND:
        return mctx("no witness: {why}; {ask}").format(
            why=_no_witness_why(solver, f),
            ask=needs_witness(at_word(DirectiveWord.STORE), f.case_id))
    if f.move is None:
        raise ValueError(f"a witness search of {f.case_id} found no grid")
    line = moved_witness(f.move.index, f.move.change)
    if f.move.identity and f.read:
        line += mctx("; the concept case gives the input unchanged")
    elif f.move.identity:
        line += mctx("; the case under `{case}` gives the input unchanged"
                     ).format(case=under_text(f.used_in))
    return line


def _no_witness_why(solver: Solver, f: Found) -> str:
    """Why the witness search of a value found no witness, by how it
    ended (`Found.ended`)."""
    match f.ended, f.failed, f.unseparated:
        case NoFit.NO_FIT, _, _:
            return no_fit_text(mctx("value"))
        case SearchEnd.UNFIT, _, _:
            return unfit_text(mctx("value"))
        case SearchEnd.FAILED, failed, _ if failed is not None:
            return mctx("the run fails on {grid}: {error}").format(
                grid=f"{train_text(failed.index)} "
                     f"{transform_text(failed.change)}",
                error=failure_text(failed.failure))
        case SearchEnd.UNSEPARATED, _, (model, other):
            return mctx("on no D4 image or color swap of a train input that "
                        "changes the value does the branch's model `{case}` "
                        "give an output other than `{other}`").format(
                case=case_name(solver, model),
                other=case_name(solver, other))
        case SearchEnd.UNCHANGED, _, _:
            return mctx("no D4 image or color swap of a train input changes "
                        "the value")
        case _:
            raise ValueError(f"the witness search of {f.case_id} ended "
                             f"{f.ended!r} with no reason it found no witness")


def _store_hints(engine: Engine, f: Found, alone: bool = False,
                 asked: bool = False) -> list[str]:
    """`asked` says an ask stands above the `@ignore: store` line, so it
    leads with `or:`."""
    named, site = f.named, f.site
    if alone:
        return [hint_line(engine, Hint(HintKind.IGNORE_STORE, relation=named,
                               site=site, alone=not asked))]
    return [hint_line(engine, Hint(HintKind.STORE, relation=named, site=site)),
            hint_line(engine, Hint(HintKind.IGNORE_STORE, relation=named,
                           site=site))]


def _product(params: Sequence[str]) -> str:
    names = " and ".join(f"`{p}`" for p in params)
    if len(params) == 1:
        return mctx("the stored rows of {params}").format(params=names)
    return mctx("the product of the stored rows of {params}").format(
        params=names)


def _no_case_text(f: Found) -> str:

    if f.kind is ValueKind.TRANSLATED:
        return no_anchor_text()
    return keyed_text(f.keys)


def store_lines(solver: Solver, survey: StoreSurvey) -> list[str]:
    """The `store` command's output
    ([Develop](docs/handbook/procedure.md#develop)): the inputs whose run
    fails, each `@store` line on a relation with an `Ident` column, one
    block per value some case reads, the relations over the row cap, then
    each witness the command built, as `record` prints it. A value with no
    `@store` line where `Found.no_witness` holds, so that the survey asks
    for no `@store` line on it (`Found.asks_line`), takes one line, which
    names the value and says why no witness was found, with no drawn value
    and no hint."""

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
        concept = f.concept if f.case_values else f.concept_section
        return (not concept, not f.read, f.kind is not ValueKind.OWNED,
                f.relation.text, f.columns)

    for f in sorted(survey.listed, key=rank):
        if f.no_witness and f.line is None:
            lines.append(mctx("{name}: no witness: {why}").format(
                name=_value_name(f), why=_no_witness_why(solver, f))
                + cases_suffix(shown(f)))
            continue
        lines.append(_headline(solver, f) + cases_suffix(shown(f)))
        if f.reads_back and f.line is None:
            lines.append("  " + mctx(
                "stored already: on every input the value equals "
                "{params}").format(params=" or ".join(
                    _product(ps) for ps in f.reads_back)))
        elif f.ignored:
            lines.append("  " + ignored_text(IgnoreForm.STORE))
        elif f.asks_line:
            lines += ["  " + ln for ln in drawn(f)]
            lines.append("  " + _witness_line(solver, f))
            lines += ["  " + ln for ln in _store_hints(
                solver.engine, f, alone=f.ended is SearchEnd.UNTAKEN)]
        elif f.store_branch:
            lines.append("  " + _witness_line(solver, f))
        elif f.asks_params:
            # At the relation's own `.decl` the headline's ask to make the
            # value a parameter stands above the hint.
            lines += ["  " + ln for ln in _store_hints(
                solver.engine, f, alone=True, asked=f.site is None)]
        elif f.kind is not ValueKind.OWNED:
            lines += ["  " + ln for ln in drawn(f)]
            lines.append("  " + mctx("no case: the value {why}").format(
                why=_no_case_text(f)))
    if survey.capped:
        lines.append(row_cap_text(ROW_CAP, [r.text for r in survey.capped]))
    return lines or [mctx("no findings")]
