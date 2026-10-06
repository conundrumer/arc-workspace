"""The checks and surveys over the solver model, and the findings they
give and their rendering.

A check answers whether the solver meets a principle, and there is one
check per principle. A question that no run of one task answers, as one
that needs every variant task, the generator's inputs or a model outside
the solver, is no check. A check's or survey's docstring says what it
computes."""

from checker.finding import FAILING, Finding, Kind, Where
from checker.lint import check_lint
from checker.readable import fault_findings
from checker.render import Section, exit_code, passes, render
from checker.runs import Runs

__all__ = ["FAILING", "Finding", "Kind", "Runs", "Section", "Where",
           "check_lint", "fault_findings", "exit_code", "passes", "render"]
