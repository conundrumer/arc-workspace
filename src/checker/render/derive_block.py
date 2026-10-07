"""The `derive` command block."""

from checker.judged import NoResult
from checker.payloads.branches import Unread
from checker.render.branches import (
    COUNTERPART,
    entry_input,
    filed_witness,
    ignored_text,
    moved_witness,
    needs_witness,
    no_fit_text,
    train_text,
    unplaced_text,
)
from checker.render.hints import Hint, HintKind, hint_line
from checker.render.locations import line_text
from checker.render.no_result import failure_text
from controlled_markdown import mctx
from solver.aggregate import Solver
from solver.annotations import DirectiveWord, IgnoreForm, at_word, derive_text
from solver.names import branch_text
from solver.names import name as case_name


def derive_lines(solver: Solver, survey: object) -> list[str]:
    """The `derive` command's output
    ([Develop](docs/handbook/procedure.md#develop)): one block per
    derivation whose model does not miss Fit, then each witness the
    command built, as `record` prints it."""
    from checker.branches.witnesses import RecordedWitness, SwapWitness
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
            lines.append("  " + ignored_text(IgnoreForm.DERIVE))
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
            lines.append("  " + filed_witness(name))
        elif isinstance(w, SwapWitness):
            lines.append("  " + moved_witness(w.swap.index, w.swap) + mctx(
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
    from checker.branches.witnesses import (
        FailedOn,
        NoFit,
        NoWitness,
        Unwitnessed,
    )

    if not isinstance(w, Unwitnessed):
        raise ValueError(f"a branch with no witness holds {w!r}")
    if w.swap is NoFit.NO_FIT:
        return no_fit_text(mctx("branch"))
    if w.pair is None:
        raise ValueError("a witness search that looked with a case names "
                         "no case")
    recorded = mctx(
        "no input of the witness file shows the branch's model `{case}` "
        "defined and giving an output other than `{other}`, {counterpart}"
    ).format(case=case_name(solver, w.pair[0]),
             other=case_name(solver, w.pair[1]), counterpart=COUNTERPART)
    match w.swap:
        case NoWitness.NOT_ONE_COLOR:
            return mctx("the parameter is not one color, and ") + recorded
        case NoWitness.NO_FREE_COLOR:
            return mctx("no train input has a free color, and ") + recorded
        case FailedOn(train=train, failure=failure):
            return mctx("the run fails on {grid} with the stored color "
                        "swapped for a free color: {error}; and ").format(
                grid=train_text(train), error=failure_text(failure)) \
                + recorded
        case NoWitness.ONE_OUTPUT:
            return mctx("no color swap of a train input and ") + recorded
        case _:
            raise ValueError(f"a branch's witness search gives {w.swap!r}")
