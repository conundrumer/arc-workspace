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
_request_check: ContextVar[Callable[[], None] | None] = ContextVar("read_request_check", default=None)
_transport_due: ContextVar[float] = ContextVar("read_transport_due", default=0.0)
_due: ContextVar[float] = ContextVar("read_inbox_due", default=0.0)
_deferred: ContextVar[int] = ContextVar("read_inbox_deferred", default=0)


def checkpoint(*, force: bool = False) -> None:
    if _deferred.get():
        return
    now = time.monotonic()
    if force or now >= _transport_due.get():
        if (check := _request_check.get()) is not None:
            check()
        _transport_due.set(now + 0.05)
    callback = _callback.get()
    if callback is None or _deferred.get() or (not force and time.monotonic() < _due.get()):
        return
    accepted = callback()
    _due.set(time.monotonic() + 1.0)
    if accepted:
        raise Accepted()


@contextmanager
def request_scope(check: Callable[[], None]) -> Iterator[None]:
    token = _request_check.set(check)
    due = _transport_due.set(0.0)
    try:
        yield
    finally:
        _request_check.reset(token)
        _transport_due.reset(due)


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


def deferred(function: Callable[P, R], *, force: bool = True) -> Callable[P, R]:
    """Finish a persistent operation before checking the inbox again.

    Issued work forces checks on both sides. A cache write uses `force=False`
    to share the normal poll interval with reads; keeping a result issues
    no work, and need not scan the whole inbox for every stored record.
    """
    @wraps(function)
    def run(*args: P.args, **kwargs: P.kwargs) -> R:
        checkpoint(force=force)
        token = _deferred.set(_deferred.get() + 1)
        try:
            result = function(*args, **kwargs)
        finally:
            _deferred.reset(token)
        checkpoint(force=force)
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
