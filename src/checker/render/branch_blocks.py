"""The `derive` and `store` command blocks, and the witness such a block
builds, as `record` prints one."""

from collections.abc import Sequence

from checker.finding import Kind
from checker.judged import NoResult
from checker.payloads.branches import HomonymsPayload, Unread
from checker.render import (
    _ticked,
    failure_text,
    finding_lines,
    in_line_order,
    line_text,
    resolution_lines,
)
from checker.render.branches import (
    NOT_BETWEEN,
    cases_suffix,
    color_ask_text,
    entry_input,
    homonyms_text,
    inline_text,
    keyed_text,
    needs_witness,
    no_anchor_text,
    row_cap_text,
    train_text,
    transform_text,
    unplaced_text,
    untaken_text,
)
from checker.render.grids import grid_lines, shifted
from checker.render.hints import Hint, HintKind, hint_line
from solver.names import name as case_name
from checker.store import (
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
from solver.annotations import DirectiveWord, IgnoreForm, at_word, derive_text, ignore_text
from solver.model import Case
from solver.aggregate import Solver
from solver.names import Denoted, branch_text, denote
from solver.witness import (
    ConflictingCells,
    Entry,
    Groups,
    InconsistentBounds,
    MissingCells,
    NegativeEdges,
    NoDerivedValue,
    NoOutput,
    Resolutions,
    Undefined,
    UndefinedReason,
)

GROUP_WIDTH = 100
"""The widest a witness group's line of case names stands; a wider
group puts each name on a line of its own."""

SHOWN_MEMBERS = 8
"""How many members of a value that draws no picture the `store` block
spells out; a larger value goes under its member count."""

DRAW_CAP = 30
"""How far a picture of the `store` block reaches along each axis; a
value whose cells spread further draws none."""


# The witness a block builds, as `record` prints one


def takes_branch(solver: Solver, name: str) -> bool:
    """Whether the case a witness file's name denotes takes a `@derive` or
    `@store` branch (`solver.names.denote`)."""
    d = denote(solver, name)
    return isinstance(d, Denoted) and bool(d.branches)


def undefined_text(reason: UndefinedReason | None,
                   counted: bool = False) -> str:
    """Why a case is undefined on an input, with the cells or the values
    at fault listed, or counted where `counted`; `undefined` for a reason
    not known."""
    match reason:
        case NoOutput():
            return mctx("emits nothing")
        case ConflictingCells(cells=cells):
            return mctx("conflicts at: {cells}").format(
                cells=_items(cells, counted, "cell", "cells"))
        case MissingCells(cells=cells):
            return mctx("missing cells at: {cells}").format(
                cells=_items(cells, counted, "cell", "cells"))
        case NegativeEdges(edges=edges):
            return mctx("negative edge distances (top, bottom, left, "
                        "right) at: {edges}").format(
                edges=_items(edges, counted, "cell", "cells"))
        case InconsistentBounds(bounds=bounds):
            return mctx("inconsistent grid bounds (height, width): "
                        "{bounds}").format(
                bounds=_items(bounds, counted, "frame size", "frame sizes"))
        case NoDerivedValue(parameter=parameter, proposer=proposer):
            return mctx("{proposer} derives no {parameter}").format(
                proposer=proposer, parameter=parameter)
        case None:
            return mctx("undefined")


def _items(items: Sequence[object], counted: bool, one: str, many: str
           ) -> str:
    if not counted:
        return str(list(items))
    return f"{len(items)} {one if len(items) == 1 else many}"


def undefined_lines(reason: UndefinedReason | None) -> list[str]:
    """Why a case's cells describe no grid (`undefined_text`), as the old
    tool printed it under the case's name; nothing for a case with no cell
    or with no derived value, whose name says it."""
    if reason is None or isinstance(reason, NoOutput | NoDerivedValue):
        return []
    return [undefined_text(reason)]


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
        lines += [mctx("{name}: {why}").format(name=n, why=undefined_text(
            NoOutput() if isinstance(r, NoOutput)
            or (r is None and not takes_branch(solver, n)) else None))
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
                input=entry_input(w.entry),
                case=case_name(solver, w.case),
                other=case_name(solver, w.other)))
        else:
            lines.append("  " + mctx("no witness: {reason}").format(
                reason=_no_witness_text(solver, w)))
            lines.append("  " + needs_witness(at_word(DirectiveWord.DERIVE), name))
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
    ask = needs_witness(at_word(DirectiveWord.STORE), f.case_id)
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
        return no_anchor_text()
    return keyed_text(f.keys)




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
        lines.append(_headline(solver, f) + cases_suffix(shown(f)))
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
