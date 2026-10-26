"""The CPU bounds a heavy command's grant gives the processes under it: the
environment of a bounded worker, and the Souffle processes one process has
going at once."""

import os

import pytest

from engine.pool import POOL_ENVS, SHARE_ENV, share_env
from souffle import run


def test_share_env_sets_the_grant_and_the_thread_variables():
    env = share_env(1)
    assert {name: env[name] for name in (SHARE_ENV, *POOL_ENVS)} == dict.fromkeys((SHARE_ENV, *POOL_ENVS), "1")
    assert env["PATH"] == os.environ["PATH"]


def _bound() -> int:
    """The Souffle processes `run._running` lets one process start at once."""
    semaphore = run._running()
    taken = 0
    while semaphore.acquire(blocking=False):
        taken += 1
    for _ in range(taken):
        semaphore.release()
    return taken


@pytest.mark.parametrize("granted", [1, 2, 64])
def test_souffle_processes_stay_within_the_grant_and_the_performance_cores(monkeypatch, granted):
    monkeypatch.setattr(run, "_RUNNING", [])
    monkeypatch.setenv(SHARE_ENV, str(granted))
    assert _bound() == min(run.performance_cores() or os.cpu_count() or 1, granted)


def test_souffle_processes_outside_the_gate_stay_within_the_performance_cores(monkeypatch):
    monkeypatch.setattr(run, "_RUNNING", [])
    monkeypatch.delenv(SHARE_ENV, raising=False)
    assert _bound() == min(run.performance_cores() or os.cpu_count() or 1, os.cpu_count() or 1)
