"""Every command's text, each module of the package one subject of it.
This module holds the sections of a command's report: each section's
lines, its pass line, and the lines of one finding of any kind.

Each survey result type gets one render function of its own; a survey's
result is a typed value of its own, not findings, holds its own timed-out
and failed runs, and its render function prints them, so that the pass
line and the exit code come from findings alone. A section's lines are
ordered as typed values before they print, never by a match over printed
text, and every printed case name goes through `solver.names`."""

from collections.abc import Sequence
from enum import StrEnum
from typing import NoReturn

from checker.finding import (
    FAILING,
    LINT_SHAPES,
    AtLine,
    FaultPayload,
    Finding,
    Kind,
    NoResultPayload,
    UndecidedPayload,
    TrainFailsPayload,
    UnexercisedPayload,
    is_hint,
)
from checker.render.faults import reading_lines
from checker.render.lint import lint_line
from checker.render.locations import LineForm, where_text
from checker.render.no_result import no_result_lines
from controlled_markdown import mctx
from engine.quotes import quoted
from solver.aggregate import Solver


class Section(StrEnum):
    """A section of a command's report."""

    WITNESS = "witness"
    DERIVE = "derive"
    STORE = "store"
    LINT = "lint"
    DROPPED_CASES = "dropped cases"
    PAIRS = "pairs"
    DETERMINATION = "determination"
    OPEN_VALUES = "open values"


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


def verb_s(n: int) -> str:
    """The ending of a present-tense verb whose subject is `n` things:
    `s` for one, else none."""
    return "s" if n == 1 else ""


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


# Sections


def header_line(title: str) -> str:
    """A section's header line."""
    return f"--- {title} ---"


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
        case UnexercisedPayload():
            from checker.render.surveys import unexercised_line
            return [unexercised_line(solver, at, p)]
        case TrainFailsPayload():
            from checker.render.surveys import UNCHECKED_TRAIN_FAILS
            return [UNCHECKED_TRAIN_FAILS.format(at=at)]
        case _ if isinstance(p, LINT_SHAPES):
            return [lint_line(solver, f)]
        case FaultPayload():
            return reading_lines(solver, f, p, form)
        case NoResultPayload():
            return no_result_lines(solver, f, p, form)
        case UndecidedPayload(relation=rel):
            words = "; ".join(f"\"{q.words}\"" for q in quoted(p))
            return [mctx("{at}: undecided: `{rel}` holds one set of rows on "
                         "every input and no value the survey reads; the "
                         "check rests on {words}").format(
                             at=at, rel=rel.text, words=words)]
        case _:
            _no_sentence(f)


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
