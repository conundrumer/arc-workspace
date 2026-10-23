"""The operate service refuses malformed requests; kept reads refuse a replaced dependency and flush on failure."""

import socket
import sys
import time
from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()

service = script("operate_service")
assert service.__file__ is not None
SCRIPTS = Path(service.__file__).parent


@pytest.fixture(autouse=True)
def refresh_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "isolated-service")
    monkeypatch.setattr(service.checkout, "caches", lambda: tmp_path / ".cache")


def test_fresh_import_closure_refuses_a_replaced_dependency(tmp_path, monkeypatch):
    import io
    kept = script("kept_reads")
    entry, dependency = tmp_path / "entry.py", tmp_path / "dependency.py"
    entry.write_text("import dependency\n")
    dependency.write_text("value = 1\n")
    files = {"operate": entry, "dependency": dependency}
    monkeypatch.setattr(kept, "module_file", files.get)
    monkeypatch.setattr(kept, "_store", None)
    monkeypatch.setattr(kept.checkout, "ROOT", tmp_path)
    monkeypatch.setattr(kept.checkout, "caches", lambda: tmp_path / "cache")
    code = kept.fresh_code("operate")
    dependency.write_text("value = 2\n")
    a, b = socket.socketpair()
    c, d = socket.socketpair()
    with a, b, c, d:
        current = service.Request("op", 1, time.monotonic() + 10, a, c, code,
                                  io.StringIO(), io.StringIO())
        with pytest.raises(service.Replaced):
            current.check(code=True)


def test_standalone_exception_flushes_completed_reads(tmp_path, monkeypatch):
    import argparse
    import gc
    import runpy
    kept = script("kept_reads")
    opened = kept.open_store
    monkeypatch.setattr(kept, "_store", None)
    monkeypatch.setattr(kept, "open_store", lambda: opened(tmp_path / "reads.sqlite"))
    monkeypatch.setattr(sys, "argv", ["operate.py", "wait", "fixture"])

    def interrupted(*_):
        kept.store().keep("fixture:read", "key", "completed")
        raise RuntimeError("fixture interrupted")

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", interrupted)
    collected = gc.isenabled()
    try:
        with pytest.raises(RuntimeError, match="fixture interrupted"):
            runpy.run_path(str(SCRIPTS / "operate.py"), run_name="__main__")
    finally:
        if collected:
            gc.enable()
    other = kept.Store(kept.store().path)
    assert other.held("fixture:read", "key") == "completed"
    other.close()


@pytest.mark.parametrize("payload", [None, {}, {"tag": "review-plan", "launch": {},
                                                "scratch": "/tmp", "code": "current"}])
def test_malformed_review_plan_is_refused(payload):
    with pytest.raises(ValueError):
        service.review_plan(payload)


@pytest.mark.parametrize("kind", ["review", "next", "refresh"])
def test_request_refuses_nonfinite_deadline(kind):
    with pytest.raises(ValueError):
        service.request_message({"kind": kind, "subject": "editor", "started": 1,
                                 "deadline": float("nan")})


def test_cutoff_closes_only_entries_of_the_operator_whose_next_it_bounds():
    state_assembly = script("state_assembly")
    from operations.journal import Entry
    from operations.state import Tool
    entry = Entry("k", "k", "d", "o", "parent", 100.0, Tool.SEND_MESSAGE, "main", "text", None, None, None)
    cutoff = state_assembly.Cutoff("parent", 150.0)
    open_work, ended_work = (lambda: True), (lambda: False)
    assert not state_assembly.may_still_call(entry, cutoff, open_work)
    assert state_assembly.may_still_call(entry, state_assembly.Cutoff("editor", 150.0), open_work)
    assert not state_assembly.may_still_call(entry, state_assembly.Cutoff("editor", 150.0), ended_work)
    assert state_assembly.may_still_call(entry, None, open_work)
    assert not state_assembly.may_still_call(entry, None, ended_work)
