"""Scoped cooperative cancellation of reads, deferred across persistent writes."""

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from typing import ParamSpec, TypeVar


class Accepted(BaseException):
    """An inbox accepted a message while a foreground call was waiting."""


_callback: ContextVar[Callable[[], bool] | None] = ContextVar("read_inbox", default=None)
_due: ContextVar[float] = ContextVar("read_inbox_due", default=0.0)
_deferred: ContextVar[int] = ContextVar("read_inbox_deferred", default=0)


def checkpoint(*, force: bool = False) -> None:
    callback = _callback.get()
    if callback is None or _deferred.get() or (not force and time.monotonic() < _due.get()):
        return
    accepted = callback()
    _due.set(time.monotonic() + 1.0)
    if accepted:
        raise Accepted()


@contextmanager
def scope(callback: Callable[[], bool]) -> Iterator[None]:
    token = _callback.set(callback)
    due = _due.set(0.0)
    try:
        checkpoint()
        yield
    finally:
        _callback.reset(token)
        _due.reset(due)


P = ParamSpec("P")
R = TypeVar("R")


def deferred(function: Callable[P, R]) -> Callable[P, R]:
    """Finish a persistent operation before checking the inbox again."""
    @wraps(function)
    def run(*args: P.args, **kwargs: P.kwargs) -> R:
        checkpoint(force=True)
        token = _deferred.set(_deferred.get() + 1)
        try:
            result = function(*args, **kwargs)
        finally:
            _deferred.reset(token)
        checkpoint(force=True)
        return result
    return run


def sleep(seconds: float, wait: Callable[[float], None] = time.sleep) -> None:
    end = time.monotonic() + seconds
    while True:
        checkpoint()
        remaining = end - time.monotonic()
        if remaining <= 0:
            return
        wait(min(remaining, 1.0))
