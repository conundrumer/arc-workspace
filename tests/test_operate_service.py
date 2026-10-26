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


def test_first_state_read_that_does_not_end_is_cut_at_the_carry_bound(tmp_path, monkeypatch):
    import os
    kept, assembly = script("kept_reads"), script("state_assembly")
    monkeypatch.setattr(kept, "_store", None)
    kept.open_store(tmp_path / "reads.sqlite")
    monkeypatch.setattr(service, "read_first", True)
    monkeypatch.setattr(service, "CARRY_SECONDS", 0.3)
    monkeypatch.setattr(service, "CHILD_POLL_SECONDS", 0.01)
    pids = tmp_path / "pids"

    def read(operator):
        pids.write_text(str(os.getpid()))
        time.sleep(60)

    monkeypatch.setattr(assembly, "read_state", read)
    current, sockets = request_for_child_read()
    try:
        with pytest.raises(service.Unavailable, match="did not finish within"):
            service.child_read(current)
    finally:
        for s in sockets:
            s.close()
    child = int(pids.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(child, 0)


def test_a_request_check_ends_the_request_past_the_carry_bound(monkeypatch):
    """The check holds the bound where nothing runs the alarm `arm` sets."""
    current, sockets = request_for_child_read()
    try:
        monkeypatch.setattr(service, "CARRY_SECONDS", 0.05)
        time.sleep(0.06)
        with pytest.raises(service.Unavailable, match="did not finish within"):
            current.check()
    finally:
        for s in sockets:
            s.close()


def test_wait_reply_carries_the_cpu_of_its_read():
    import json
    a, b = socket.socketpair()
    with a, b:
        b.sendall((json.dumps({"status": 0, "stdout": "", "stderr": "", "retry": False, "ended": False,
                               "pace": None, "cpu": 1.5}) + "\n").encode())
        reply = service.exchange(a, "op", 1.0, time.monotonic() + 5, service.Kind.WAIT, None)
    assert reply == service.WaitReply(True, False, None, 1.5)


def test_a_residents_final_line_gives_its_reason_and_read_leaves_it_out(tmp_path):
    import script_calls
    script_calls.start_request(str(tmp_path), "operate_service.py", ["next"])
    script_calls.record()
    script_calls.record_end(str(tmp_path), script_calls.End.LOCK_HELD)
    records = str(tmp_path / script_calls.RECORDS)
    assert [c.reason for c in script_calls.ends(records, 0.0)] == ["lock held"]
    assert [c.reason for c in script_calls.read(records, 0.0)] == [""]


def test_journaled_reply_survives_refresh_exclusion(tmp_path):
    """Refresh preserves a committed reply and refuses uncommitted output."""
    import io
    import json
    refresh_locks = script("refresh_locks")
    step_journal = script("step_journal")
    from operations.steps import Send

    a, b = socket.socketpair()
    c, d = socket.socketpair()
    with a, b, c, d:
        current = service.Request("operator", time.time(), time.monotonic() + 10,
                                  a, c, "code", io.StringIO(), io.StringIO())
        token = service.CURRENT.set(current)
        response = {"status": 0, "stdout": "journaled reply", "stderr": "", "retry": False}
        try:
            with refresh_locks.hold("isolated-service"):
                with pytest.raises(service.Replaced):
                    service.publish_response(current, response)
            step_journal.give(tmp_path, [Send("recipient", "message", "subject")], "operator", time.time())
            service.commit()
            with refresh_locks.hold("isolated-service"):
                service.publish_response(current, response)
            b.settimeout(1)
            assert json.loads(b.recv(65536)) == response
            assert len(step_journal.records(tmp_path)) == 1
        finally:
            service.CURRENT.reset(token)


@pytest.fixture
def running_request(monkeypatch):
    """A request that runs, with the directory of the socket of its listener, which
    holds a queue, and the socket of its waiting client."""
    import io
    import tempfile
    with tempfile.TemporaryDirectory(dir="/tmp") as directory:
        listener = socket.socket(socket.AF_UNIX)
        listener.bind(f"{directory}/s.sock")
        listener.listen()
        a, b = socket.socketpair()
        pending = service.Pending(listener)
        current = service.Request("op", time.time(), time.monotonic() + 60, a, listener, "code",
                                  io.StringIO(), io.StringIO(), pending=pending)
        pending.running = current
        monkeypatch.setattr(service, "_beaten", 0.0)
        try:
            yield current, directory, b
        finally:
            current.alarm.clear()
            pending.close()
            listener.close()
            a.close()
            b.close()


def queue_call(directory: str, seconds: float) -> socket.socket:
    """The socket of a call of another subject that queues, with a bound `seconds` away."""
    import json
    queued = socket.socket(socket.AF_UNIX)
    queued.connect(f"{directory}/s.sock")
    queued.sendall((json.dumps({"kind": "next", "subject": "other", "started": time.time(),
                                "deadline": time.monotonic() + seconds}) + "\n").encode())
    return queued


def spin_until(condition, seconds: float = 10.0) -> None:
    end = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < end


def test_a_queued_call_is_answered_at_its_bound_and_the_beat_touched_while_the_read_reaches_no_checkpoint(
        running_request):
    """The read runs a `bounded` block, as a pace script and the script of a run do."""
    import json
    import select
    current, directory, _ = running_request
    run_scripts = script("run_scripts")
    service.arm(current)
    queued = queue_call(directory, service.FINISH_SECONDS + 0.3)
    with queued:
        with run_scripts.bounded(20, "the pace script"):
            spin_until(lambda: select.select([queued], [], [], 0.01)[0])
        answer = json.loads(queued.recv(65536))
    assert answer["stdout"] == service.read_running(current)
    assert service.beat_path(service.Path(current.listener.getsockname())).exists()


def test_the_end_of_a_run_at_the_carry_bound_comes_through_a_bounded_block(running_request, monkeypatch):
    current, _, _ = running_request
    run_scripts = script("run_scripts")
    monkeypatch.setattr(service, "CARRY_SECONDS", 0.3)
    current.begun = time.monotonic()
    service.arm(current)
    with pytest.raises(service.Unavailable, match="did not finish within"):
        with run_scripts.bounded(20, "the pace script"):
            spin_until(lambda: False)


def test_nothing_ends_a_request_whose_run_ended_past_the_carry_bound(running_request, monkeypatch):
    """The alarm comes during the flush and the response, and the response goes to the client."""
    import json
    current, _, client = running_request
    monkeypatch.setattr(service, "CARRY_SECONDS", 0.05)
    monkeypatch.setattr(service, "BEAT_EVERY", 0.05)
    current.begun = time.monotonic() - 1
    current.deadline = time.monotonic() + service.FINISH_SECONDS + 0.1
    with service.run_scope(current):
        pass
    service.arm(current)
    time.sleep(0.3)
    current.check()
    response = {"status": 0, "stdout": "done", "stderr": "", "retry": False}
    service.publish_response(current, response)
    client.settimeout(1)
    assert json.loads(client.recv(65536)) == response


def test_the_watchdog_of_a_call_with_no_resident_ends_it_though_a_bounded_block_ran(tmp_path):
    import os
    import subprocess
    source = '''
import time
import operate_loop
import run_scripts
import script_calls
script_calls.RECORDS = "records"
operate_loop.LIMIT_SECONDS = 1
operate_loop.arm_watchdog("fixture", lambda me: 7)
with run_scripts.bounded(1, "the call"):
    pass
time.sleep(30)
'''
    done = subprocess.run(
        [sys.executable, "-u", "-c", source], cwd=tmp_path, timeout=30,
        env={"PATH": os.defpath, "HOME": str(tmp_path), "CLAUDE_CONFIG_DIR": str(tmp_path),
             "CLAUDE_CODE_SESSION_ID": "watchdog-test", "PYTHONPATH":
             os.pathsep.join((str(SCRIPTS), str(SCRIPTS.parent / "src")))})
    assert done.returncode == 7


def test_a_yielding_request_whose_run_ended_still_publishes_with_a_client_call_queued(running_request):
    import json
    current, directory, client = running_request
    current.kind = service.Kind.WAIT
    with service.run_scope(current):
        pass
    queued = queue_call(directory, 30)
    with queued:
        response = {"status": 0, "stdout": "done", "stderr": "", "retry": False}
        service.publish_response(current, response)
        client.settimeout(1)
        assert json.loads(client.recv(65536)) == response
