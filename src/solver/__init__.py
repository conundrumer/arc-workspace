"""The model of a solver as the handbook defines it, with no Datalog in it,
and solving over an engine.

Each type of the model carries the handbook words that define it
(`engine.quotes`). The package has no private module: every module that
`checker` reads is public, with a docstring, and no module is kept only to
re-export another."""

from solver.annotations import Annotations, ClaimLine, HeaderField, WitnessLine
from solver.model import (
    Branch,
    Case,
    Choice,
    Lib,
    Params,
    Solver,
    cases,
    load,
)
from solver.problems import ProblemKind, Fault
from solver.witness import Entry, WitnessFile

__all__ = [
    "Annotations", "Branch", "Case", "Choice", "ClaimLine", "Entry",
    "HeaderField", "Lib", "Params", "ProblemKind", "Fault", "Solver",
    "WitnessFile", "WitnessLine", "cases", "load",
]
