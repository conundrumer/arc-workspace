"""The proposer probe."""

from collections.abc import Mapping
from dataclasses import dataclass

from arc.task import Task
from engine import (
    Engine,
    IndexedGrids,
    InputValue,
    Limits,
    ParseFailure,
    Program,
    RelationName,
    Rows,
    RunFailure,
    Tuples,
)
from engine.engine import CompileError
from engine.memo import ByIdentity
from engine.program import as_grid
from solver.readers import proposer_names, proposers_program
from solver.variant_limits import over_examples
from solver.vocabulary import EX_IN, EX_OUT, PROPOSE


@dataclass(frozen=True)
class Proposals:
    """The values each proposer of `programs/proposers.dl` gives over a
    task's examples, by proposer."""

    values: Mapping[str, Rows]


def example_inputs(task: Task) -> dict[RelationName, InputValue]:
    """`ex_in` over every example's input, train first, and `ex_out` over
    the train outputs, each with the example's index (lib.dl's runner
    contract; solver-file.md, under "Determination")."""
    return {
        EX_IN: IndexedGrids(tuple(as_grid(e.input)
                                  for e in (*task.train, *task.test))),
        EX_OUT: IndexedGrids(tuple(as_grid(e.output) for e in task.train)),
    }


type _ProbeProgram = tuple[Program, dict[str, RelationName]]


_PROBE_PROGRAMS: ByIdentity[Program, _ProbeProgram] = ByIdentity()
"""What `_probe_program` built, for each proposers program while it
lives."""


def _probe_program(engine: Engine) -> _ProbeProgram | CompileError:
    """The proposers program (`proposers_program`) with an instance of
    each proposer, and each proposer's `propose` in its instance, built
    once per proposers program; where the program does not parse, the
    probe's failure (`probe_failure`)."""
    parsed = proposers_program(engine)
    if isinstance(parsed, ParseFailure):
        return probe_failure(parsed)

    def build() -> _ProbeProgram:
        program = parsed
        outputs: dict[str, RelationName] = {}
        for name in proposer_names(parsed):
            inst = name.lower()
            program = engine.instantiate(program, name, inst)
            outputs[name] = RelationName((inst,), PROPOSE)
        return program, outputs

    return _PROBE_PROGRAMS.compute(parsed, build)


def probe_failure(parsed: ParseFailure) -> CompileError:
    """A proposers program that does not parse, as the failure of the
    probe that runs it."""
    return CompileError(parsed.line, parsed.message)


def probe(engine: Engine, task: Task, limits: Limits
          ) -> Proposals | RunFailure:
    """The proposers program run over the task's examples: each proposer
    of `programs/proposers.dl`, a component that declares `propose`, as an
    instance, with `ex_in` over every example's input and `ex_out` over
    the train outputs (proposers.dl's header). The run takes `limits`
    once per example."""
    built = _probe_program(engine)
    if isinstance(built, CompileError):
        return built
    program, outputs = built
    got = engine.run(program, example_inputs(task), list(outputs.values()),
                     over_examples(limits, task))
    if not isinstance(got, Tuples):
        return got
    return Proposals({name: got.relations[rel]
                      for name, rel in outputs.items()})
