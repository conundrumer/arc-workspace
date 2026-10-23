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


def test_wait_request_gives_its_pace_and_other_kinds_give_none():
    base = {"subject": "editor", "started": 1, "deadline": 2.0}
    assert service.request_message({**base, "kind": "wait", "pace": []})[0] is service.Kind.WAIT
    with pytest.raises(ValueError):
        service.request_message({**base, "kind": "wait"})
    with pytest.raises(ValueError):
        service.request_message({**base, "kind": "waits", "pace": []})
    assert service.known_pace({"pace": []}) is None
    assert service.known_pace({"pace": [None]}) == (None,)


@pytest.mark.parametrize("pace", [None, "until", "capped", "scripted", "uncomputed"])
def test_pace_survives_the_request_form(pace):
    import json
    from operations import pacing
    from operations.state import NotComputed
    given = {None: None, "until": pacing.Until(5.0, 2), "capped": pacing.Capped(3),
             "scripted": pacing.Scripted(Path("/x/paces.py"), True),
             "uncomputed": NotComputed("why")}[pace]
    assert pacing.pace_of(json.loads(json.dumps(pacing.pace_fields(given)))) == given


def test_queue_serves_waits_before_wait_and_refresh():
    listener = socket.socket(socket.AF_UNIX)
    pending = service.Pending(listener)
    base = {"subject": "s", "started": 1.0, "deadline": 9.0}
    kept = []
    for message in ({**base, "kind": "wait", "pace": []}, {**base, "kind": "refresh"},
                    {**base, "kind": "waits"}):
        a, b = socket.socketpair()
        kept += [a, b]
        pending.connections[a] = time.monotonic(), message
    assert pending.client_queued()
    order = []
    while (connection := pending.take()) is not None:
        order.append(connection)
    assert order[0] is kept[4]
    for c in kept:
        c.close()
    listener.close()


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


def test_call_lines_read_the_footprint_and_default_it_to_zero(tmp_path):
    import json
    import script_calls
    line = {"key": "operate.py next", "start": 5.0, "wall": 1.0, "cpu": 1.0, "peak": 7, "session": "s",
            "lifts": [], "retained": True, "queued": 0.5, "reads": 2}
    with_footprint = {**line, "start": 6.0, "footprint": 123}
    path = tmp_path / script_calls.day_file(str(tmp_path), 5.0).rsplit("/", 1)[-1]
    path.write_text(json.dumps(line) + "\n" + json.dumps(with_footprint) + "\n")
    calls = script_calls.read(str(tmp_path), 0.0)
    assert [c.footprint for c in calls] == [0, 123]


def test_release_free_memory_gives_a_byte_count_and_leaves_the_footprint_readable():
    import script_calls
    assert script_calls.release_free_memory() >= 0
    assert script_calls.footprint() > 0


def test_call_lines_read_first_and_high_and_default_them(tmp_path):
    import json
    import script_calls
    line = {"key": "operate.py next", "start": 5.0, "wall": 1.0, "cpu": 1.0, "peak": 7, "session": "s",
            "lifts": [], "retained": True, "queued": 0.5, "reads": 2, "footprint": 9}
    marked = {**line, "start": 6.0, "first": True, "high": 456}
    path = tmp_path / script_calls.day_file(str(tmp_path), 5.0).rsplit("/", 1)[-1]
    path.write_text(json.dumps(line) + "\n" + json.dumps(marked) + "\n")
    calls = script_calls.read(str(tmp_path), 0.0)
    assert [(c.first, c.high) for c in calls] == [(False, 0), (True, 456)]


def test_a_resident_marks_only_its_first_request_and_its_highest_footprint_is_at_least_its_footprint(tmp_path, monkeypatch):
    import json
    import time
    import script_calls
    monkeypatch.setattr(script_calls, "_served", False)
    for args in (["next"], ["next"]):
        script_calls.start_request(str(tmp_path), "operate_service.py", args)
        script_calls.record()
    path = script_calls.day_file(str(tmp_path / script_calls.RECORDS), time.time())
    with open(path) as f:
        lines = [json.loads(text) for text in f]
    assert [l["first"] for l in lines] == [True, False]
    assert all(l["high"] >= l["footprint"] > 0 for l in lines)


def request_for_child_read():
    import io
    a, b = socket.socketpair()
    c, d = socket.socketpair()
    current = service.Request("op", 1, time.monotonic() + 30, a, c, "code",
                              io.StringIO(), io.StringIO())
    return current, (a, b, c, d)


def test_first_state_read_runs_in_a_child_and_its_reads_reach_the_store(tmp_path, monkeypatch):
    import os
    kept, assembly = script("kept_reads"), script("state_assembly")
    monkeypatch.setattr(kept, "_store", None)
    kept.open_store(tmp_path / "reads.sqlite")
    monkeypatch.setattr(service, "read_first", True)
    parent = os.getpid()

    def read(operator):
        kept.store().keep("fixture:read", operator, os.getpid())

    monkeypatch.setattr(assembly, "read_state", read)
    current, sockets = request_for_child_read()
    try:
        service.child_read(current)
        service.child_read(current)
    finally:
        for s in sockets:
            s.close()
    other = kept.Store(kept.store().path)
    found = other.held("fixture:read", "op")
    other.close()
    assert found is not None and found != parent


def test_failed_first_state_read_in_the_child_fails_the_request(tmp_path, monkeypatch):
    kept, assembly = script("kept_reads"), script("state_assembly")
    monkeypatch.setattr(kept, "_store", None)
    kept.open_store(tmp_path / "reads.sqlite")
    monkeypatch.setattr(service, "read_first", True)

    def read(operator):
        raise ValueError("fixture read failed")

    monkeypatch.setattr(assembly, "read_state", read)
    current, sockets = request_for_child_read()
    try:
        with pytest.raises(RuntimeError, match="fixture read failed"):
            service.child_read(current)
    finally:
        for s in sockets:
            s.close()


def test_child_retries_a_flush_that_fails_on_a_lock(tmp_path, monkeypatch):
    kept, assembly = script("kept_reads"), script("state_assembly")
    monkeypatch.setattr(kept, "_store", None)
    kept.open_store(tmp_path / "reads.sqlite")
    monkeypatch.setattr(service, "read_first", True)
    monkeypatch.setattr(service, "CHILD_POLL_SECONDS", 0.01)
    real = kept.Store.flush
    failed = []

    def flush(self):
        if not failed and self.new:
            failed.append(True)
            return False
        return real(self)

    monkeypatch.setattr(kept.Store, "flush", flush)
    monkeypatch.setattr(assembly, "read_state",
                        lambda operator: kept.store().keep("fixture:read", operator, "kept"))
    current, sockets = request_for_child_read()
    try:
        service.child_read(current)
    finally:
        for s in sockets:
            s.close()
    other = kept.Store(kept.store().path)
    found = other.held("fixture:read", "op")
    other.close()
    assert found == "kept"


def test_wait_reply_carries_the_cpu_of_its_read():
    import json
    a, b = socket.socketpair()
    with a, b:
        b.sendall((json.dumps({"status": 0, "stdout": "", "stderr": "", "retry": False, "ended": False,
                               "pace": None, "cpu": 1.5}) + "\n").encode())
        reply = service.exchange(a, "op", 1.0, time.monotonic() + 5, service.Kind.WAIT, None)
    assert reply == service.WaitReply(True, False, None, 1.5)
