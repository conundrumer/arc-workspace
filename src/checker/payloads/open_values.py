"""The payloads of the open-values check (`checker.open_values`): a stored
fact of a parameter, the fact no input exercises, and the stored program
failing a train pair."""

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
    """The payload of an `unexercised` finding
    (`checker.finding.Kind.UNEXERCISED`): the fact."""

    fact: Fact


@dataclass(frozen=True)
class TrainFails:
    """The stored program fails a train pair, so the drop-one survey
    (`checker.drop_one.survey_drop_one`), and the open-values check that
    reads it, do not run."""
