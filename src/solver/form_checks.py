"""The checks of the solver's form that `load` runs: the faults of the
instance tree the model walks, the names the solver and its witness file
hold that denote nothing, and the witness entries whose `output` is in
another form than the verdict that records them takes."""

from collections.abc import Iterator

from engine import Program, Span
from engine.program import RigidCall, dotted, first_line, own
from engine.quotes import quotes
from solver.aggregate import Solver, assignable, lists_case
from solver.annotations import NamedVerdict, VerdictWord
from solver.columns import unknown_strings
from solver.graph import MAX_DEPTH, by_innermost, component_chain
from solver.names import denote, names_a_constructor, verdict_lines
from solver.problems import (
    Fault,
    InSolver,
    InWitnessFile,
    Named,
    NameFault,
    OutputForm,
    OutputOffVerdict,
    ProblemKind,
    VerdictsDisagree,
    WitnessFileRole,
)
from solver.vocabulary import PARAMS_SCOPE
from solver.witness import AssignRows, Groups


def instance_faults(program: Program) -> list[Fault]:
    """The faults of the instance tree the model walks (`Graph`), each at
    the solver's line it stands on, or, inside an included component, at
    the line of the solver's instance its path starts from: a path deeper
    than `MAX_DEPTH`; an instance of a component no file declares inside
    an included component (the solver's own are `load`'s); a component
    that extends one no file declares; and type arguments that are not
    one per type parameter, of an instance or of a component's base. A
    RIGID call in `Params` whose block's charts are not one per name it
    binds is a fault too (`solve._blocks`)."""
    comps = {c.name: c for c in program.components}
    by_scope = by_innermost(program.instances)
    out: list[Fault] = []

    def fault(kind: ProblemKind, span: Span | None, start: int,
              name: str) -> None:
        got = Fault(kind, InSolver(span.first if own(span) and span
                                   is not None else start), Named(name))
        if got not in out:
            out.append(got)

    def chain(comp: str | None, start: int) -> list[str | None]:
        seen = component_chain(comps, comp)
        for name, base in zip(seen, seen[1:], strict=False):
            if name is None or base is None:
                break
            c = comps[name]
            if base not in comps:
                fault(ProblemKind.BASE_OF_NOTHING, c.span, start, base)
                return seen[:-1]
            if len(c.base_type_args) != len(comps[base].type_params):
                fault(ProblemKind.TYPE_ARGUMENTS, c.span, start, base)
        return seen

    front: list[tuple[tuple[str, ...], str | None, int]] = [((), None, 0)]
    while front:
        at, here, start = front.pop(0)
        for scope in chain(here, start):
            for name, inst in by_scope.get(scope, {}).items():
                line = start if at else first_line(inst.span)
                path = (*at, name)
                comp = comps.get(inst.component)
                if comp is None:
                    if not own(inst.span):
                        fault(ProblemKind.INSTANCE_OF_NOTHING, inst.span,
                              line, inst.component)
                    continue
                if len(inst.type_args) != len(comp.type_params):
                    fault(ProblemKind.TYPE_ARGUMENTS, inst.span, line,
                          inst.component)
                if len(path) > MAX_DEPTH:
                    if not any(f.kind is ProblemKind.INSTANCE_UNFOLLOWED
                               and f.place == InSolver(line) for f in out):
                        fault(ProblemKind.INSTANCE_UNFOLLOWED, None, line,
                              dotted(path))
                    continue
                front.append((path, comp.name, line))
    params = PARAMS_SCOPE
    for m in program.macros:
        if isinstance(m, RigidCall) and m.scope == params \
                and program.bound_charts(m) is None:
            fault(ProblemKind.RIGID_CHARTS, m.span, 0, m.block)
    return out


def name_problems(solver: Solver) -> Iterator[Fault]:
    """The names the solver and its witness file hold that denote nothing:
    verdicts, markers, named `@ignore` lines, group names, and `assign`
    keys and the strings of `assign` values (`solver.columns.arg_value`)."""

    def check(name: str | tuple[str, ...], line: int
              ) -> Iterator[Fault]:
        got = denote(solver, name)
        if isinstance(got, NameFault):
            yield got.at(InSolver(line))

    a = solver.annotations
    for v in (*a.witnesses, *a.derives, *a.stores):
        if isinstance(v.verdict, NamedVerdict):
            yield from check(v.verdict.text, v.line)
    for m in a.markers:
        listing = lists_case(solver, m)
        for part in m.parts:
            if part.prose:
                continue
            got = denote(solver, part.name)
            if not isinstance(got, NameFault):
                continue
            if got.kind == ProblemKind.NAME_FORM \
                    and names_a_constructor(solver, part.name):
                yield Fault(ProblemKind.NAME_FORM, InSolver(m.line),
                            Named(part.name))
            elif listing:
                yield Fault(ProblemKind.MARKER_NAMES_NOTHING,
                            InSolver(m.line), Named(part.name))
    for i in a.ignores:
        if i.name is not None:
            yield from check(i.name, i.line)
    if solver.witness_file is None:
        return
    for e in solver.witness_file.entries:
        if isinstance(e.output, Groups):
            for g in e.output.groups:
                for name in g.cases:
                    got = denote(solver, name)
                    if isinstance(got, NameFault):
                        yield got.at(InWitnessFile(e.id, WitnessFileRole.TASK))
        for key, value in e.assign:
            if not assignable(solver, key):
                yield Fault(ProblemKind.ASSIGN_NAMES_NOTHING,
                            InWitnessFile(e.id, WitnessFileRole.TASK),
                            Named(key))
            if isinstance(value, AssignRows):
                for s in unknown_strings(solver, value.rows):
                    yield Fault(ProblemKind.ASSIGN_VALUE_UNKNOWN,
                                InWitnessFile(e.id, WitnessFileRole.TASK),
                                Named(s))


def split_verdict_lines(solver: Solver, id: str
                        ) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """The lines that record the verdict of the witness file's entry `id`
    (`solver.names.verdict_lines`), in file order: those that record
    `other`, and those that record another verdict."""
    lines = verdict_lines(solver, id)
    return (tuple(line.line for line in lines
                  if line.verdict == VerdictWord.OTHER),
            tuple(line.line for line in lines
                  if line.verdict != VerdictWord.OTHER))


@quotes("solver-file.md", "Witness file",
        "\"output\": Group[] // when the verdict is not other: one group per "
        "distinct output")
@quotes("solver-file.md", "Witness file",
        "when the verdict is other: the annotator's judged output")
def output_form_problems(solver: Solver) -> Iterator[Fault]:
    """Each entry of the task's witness file whose `output` is in another
    form than the verdict of a line that records it takes
    (`solver.names.verdict_lines`), one fault per such line: groups under
    the verdict `other`, and a bare grid under any other verdict. An entry
    that holds a bare grid where no line records a verdict for it is a
    fault too, and one that holds groups there is not. An entry whose
    lines record `other` and another verdict both has no form that fits
    them, and is one fault that names those lines, whatever its
    `output`."""
    if solver.witness_file is None:
        return
    for e in solver.witness_file.entries:
        held = OutputForm.GROUPS if isinstance(e.output, Groups) \
            else OutputForm.JUDGED
        place = InWitnessFile(e.id, WitnessFileRole.TASK)
        other, another = split_verdict_lines(solver, e.id)
        if other and another:
            yield Fault(ProblemKind.VERDICTS_DISAGREE, place,
                        VerdictsDisagree(other, another))
            continue
        if not other and not another and held is OutputForm.JUDGED:
            yield Fault(ProblemKind.OUTPUT_OFF_VERDICT, place,
                        OutputOffVerdict(held, None))
        off = another if held is OutputForm.JUDGED else other
        for line in off:
            yield Fault(ProblemKind.OUTPUT_OFF_VERDICT, place,
                        OutputOffVerdict(held, line))
