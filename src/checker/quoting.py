"""The handbook words each check and survey of the checker rests on, read
from the functions themselves: a check or survey carries `quotes` or a
`guard`, a `guard` stands on a hint or lint check alone, and a check that
is neither a hint nor a lint quotes `principles.md`. `python -m
controlled_markdown check` reports what `unquoted` gives.

A check quotes the principle it serves and, where it checks the solver's
form, the solver-file.md passage that states the form too; a hint or lint
quotes the nearest procedure or style line."""

import ast
import importlib
import inspect
import pkgutil
import textwrap
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from enum import StrEnum

import checker
import checker.lint
from checker.finding import FAILING, Kind
from engine.quotes import guarded, quoted

CHECK_PREFIX = "check_"
"""The start of a check's name: a check is `check_<rule>(solver, runs) ->
list[Finding]`. A function's kind, check or survey, is in its name."""
SURVEY_PREFIX = "survey_"
"""The start of a survey's name."""
PRINCIPLES = "principles.md"
"""The document a check whose findings are in `FAILING` quotes."""

type Function = Callable[..., object]


class Breach(StrEnum):
    """How a check or survey breaks the rule."""

    MISSING = "quote-missing"
    """It carries neither `quotes` nor a `guard`."""
    GUARD = "quote-guard"
    """It carries a `guard` and is no hint or lint check."""
    PRINCIPLE = "quote-principle"
    """It is a check that is neither a hint nor a lint, and carries no
    `quotes` from `principles.md`."""


@dataclass(frozen=True)
class Unquoted:
    """A check or survey that breaks the rule, and how."""

    function: Function
    breach: Breach


def checks_and_surveys() -> Iterator[tuple[Function, bool]]:
    """Each check and survey a module of the checker defines, with whether
    it is a lint: a function of a module of `checker.lint`."""
    lint = checker.lint.__name__
    for info in pkgutil.walk_packages(checker.__path__,
                                      checker.__name__ + "."):
        module = importlib.import_module(info.name)
        for name, value in vars(module).items():
            if inspect.isfunction(value) \
                    and value.__module__ == module.__name__ \
                    and name.startswith((CHECK_PREFIX, SURVEY_PREFIX)):
                yield value, (module.__name__ == lint
                              or module.__name__.startswith(lint + "."))


def _kinds(function: Function) -> frozenset[Kind] | None:
    """The finding kinds `function`'s text names as `Kind.<NAME>`; None
    where it makes a kind by calling `Kind`, so that which kinds it gives
    is not read."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    named: set[Kind] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                and n.func.id == Kind.__name__:
            return None
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) \
                and n.value.id == Kind.__name__:
            named.add(Kind[n.attr])
    return frozenset(named)


def gives_hints(function: Function) -> bool:
    """`function` names a finding kind, and every kind it names stands
    outside `FAILING`."""
    kinds = _kinds(function)
    return bool(kinds) and not kinds & FAILING


def unquoted(functions: Iterable[tuple[Function, bool]]
             ) -> list[Unquoted]:
    """Each of `functions`, checks and surveys each with whether it is a
    lint, that breaks the rule."""
    out: list[Unquoted] = []
    for function, lint in functions:
        words = quoted(function)
        guard = guarded(function)
        check = function.__name__.startswith(CHECK_PREFIX)
        hint_or_lint = check and (lint or gives_hints(function))
        if guard is not None and not hint_or_lint:
            out.append(Unquoted(function, Breach.GUARD))
        elif not words and guard is None:
            out.append(Unquoted(function, Breach.MISSING))
        elif words and check and not hint_or_lint \
                and all(q.document != PRINCIPLES for q in words):
            out.append(Unquoted(function, Breach.PRINCIPLE))
    return out
