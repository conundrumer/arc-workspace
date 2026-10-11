"""The payloads of the open-values check (`checker.open_values`): a stored
fact of a parameter, the fact no input exercises, and the check not
run."""

from dataclasses import dataclass

from engine import Row


@dataclass(frozen=True)
class Fact:
    """One stored fact of a parameter: the parameter, its column types
    (`solver.columns.column_types`), and the fact's row."""

    parameter: str
    types: tuple[str, ...]
    row: Row


@dataclass(frozen=True)
class UnexercisedPayload:
    """A stored fact whose removal changes no outcome of any case on any
    input of the task or of the witness file."""

    fact: Fact


@dataclass(frozen=True)
class TrainFailsPayload:
    """The check did not run: the stored program fails a train pair."""
