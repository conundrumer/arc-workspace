"""The launches that only an operator of the main session makes: each
procedure `main_only` decorates."""

from collections.abc import Callable
from functools import wraps

from operations.state import State
from operations.steps import Step


def main_only(procedure: Callable[[State], Step | None]) -> Callable[[State], Step | None]:
    """`procedure`, whose launch only an operator of the main session, as
    `file_ticket.py main --help-all` gives it, makes, so that concurrent
    sessions make it once."""
    @wraps(procedure)
    def guarded(state: State) -> Step | None:
        return procedure(state) if state.sessions.main else None
    return guarded
