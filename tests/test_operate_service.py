"""Resident request races and source/code invalidation in isolated checkouts."""

import contextlib
import json
import os
import socket
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from unittest.mock import Mock

import pytest

from tests.conftest import script

service = script("operate_service")
assert service.__file__ is not None
SCRIPTS = Path(service.__file__).parent


def until(path: Path) -> None:
    deadline = time.monotonic() + 20
    while not path.exists():
        if time.monotonic() >= deadline:
            pytest.fail(f"fixture did not reach {path.name}")
        time.sleep(0.01)


@pytest.fixture
def resident(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    scripts = SCRIPTS
    monkeypatch.syspath_prepend(str(scripts))
    (tmp_path / "scripts").mkdir()
    (tmp_path / "code").write_text("old")
    (tmp_path / "source").write_text("ready")
    runner = tmp_path / "scripts/operate_service.py"
    runner.write_text(textwrap.dedent(f'''
        import sys, time
        from pathlib import Path
        sys.path.insert(0, {str(scripts)!r})
        from engine import checkout
        root = Path({str(tmp_path)!r})
        checkout.ROOT = root
        checkout.main_worktree = lambda _: root
        checkout.caches = lambda: root / ".cache"
        import script_calls
        script_calls.start(str(root), "operate_service.py", ["startup"])
        import operate_service as service
        import kept_reads, operate, state_assembly, state_reads, file_reads, step_journal
        from operations.steps import Bash
        kept_reads.fresh_code = lambda _: (root / "code").read_text()
        loaded = (root / "code").read_text()
        def main(argv):
            operator = argv[1]
            if operator in ("wait", "journal"):
                if operator == "journal" and not step_journal.records(root):
                    with service.side_effect():
                        step_journal.start_run(root, Bash("echo run >> executions", "fixture", occasion="once"),
                                               operator, root, time.time())
                (root / "entered").write_text(operator)
                while not (root / "release").exists():
                    service.pause(0.02)
            state_reads.new_state()
            text = file_reads.file_text(root / "source")
            print(loaded, operator, text, state_assembly.REQUEST_STARTED.get())
            return 0
        operate.main = main
        def refresh(operator):
            state_reads.new_state()
            file_reads.file_text(root / "source")
        state_assembly.read_state = refresh
        if (root / "idle").exists():
            service.IDLE_SECONDS = 0.05
        service.serve()
        import os
        os._exit(0)
    '''))
    processes: list[subprocess.Popen] = []
    popen = subprocess.Popen

    class Started(popen):
        def __init__(self, argv, **kwargs):
            kwargs["env"] = {"PATH": os.defpath, "CLAUDE_CODE_SESSION_ID": "isolated-service",
                             "ARC_OPERATE_CODE": (tmp_path / "code").read_text()}
            super().__init__(argv, **kwargs)
            if str(runner) in argv:
                processes.append(self)

    monkeypatch.setattr(service.subprocess, "Popen", Started)
    driver_started = service.script_calls.cpu_seconds()
    yield tmp_path, processes
    (tmp_path / "driver-cpu.json").write_text(json.dumps(
        {"cpu": service.script_calls.cpu_seconds() - driver_started}))
    for proc in processes:
        if proc.poll() is None:
            proc.terminate()
        proc.wait(timeout=20)
    path = service.endpoint(tmp_path, "isolated-service")
    for suffix in (".sock", ".owner", ".start"):
        path.with_suffix(suffix).unlink(missing_ok=True)


def call(root: Path, operator: str = "op", cutoff: float = 12.0):
    return service.request(root, "isolated-service", operator, cutoff,
                           time.monotonic() + 20, False)


def open_request(root: Path, operator: str) -> socket.socket:
    connection = service.ensure(root, "isolated-service", time.monotonic() + 20)
    connection.sendall((json.dumps({"operator": operator, "started": 10,
                                   "deadline": time.monotonic() + 20,
                                   "refresh": False}) + "\n").encode())
    return connection


def test_sources_and_operator_cutoff_are_current_without_events(resident):
    root, processes = resident
    assert call(root) == (0, "old op ready 12.0\n", "")
    assert call(root, "other", 23) == (0, "old other ready 23.0\n", "")
    (root / "source").write_text("changed without an event")
    assert call(root) == (0, "old op changed without an event 12.0\n", "")
    assert len(processes) == 1


def test_code_replacement_during_a_request_finishes_before_retirement(resident):
    root, processes = resident
    connection = open_request(root, "wait")
    until(root / "entered")
    (root / "code").write_text("new")
    (root / "release").write_text("")
    with connection, connection.makefile("rb") as response:
        out = json.loads(response.readline())
        assert out["retry"] is False
        assert out["status"] == 0
        assert out["stdout"].startswith("old wait ready ")
    result = call(root)
    assert result[0] == 0
    assert result[1].startswith("new op ready ")
    assert result[2] == ""
    assert len(processes) == 2


def test_first_request_after_code_replacement_uses_a_fresh_service(resident):
    root, processes = resident
    assert call(root)[0] == 0
    (root / "code").write_text("new")
    result = call(root)
    assert result[0] == 0
    assert result[1].startswith("new op ready ")
    assert len(processes) == 2


@pytest.mark.parametrize("cancel", [service.Replaced, service.Disconnected, service.Expired])
def test_request_cancellation_escapes_cache_validation(monkeypatch, cancel):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    reads = script("state_reads")

    def interrupted(*_):
        raise cancel

    monkeypatch.setattr(reads, "stamp_now", interrupted)
    with pytest.raises(cancel):
        reads.holds((reads.By.STAMP, "fixture", (), (), None))


def test_deadline_during_cache_validation_retires_the_service(monkeypatch):
    import io
    import signal
    monkeypatch.syspath_prepend(str(SCRIPTS))
    operate = script("operate")
    reads = script("state_reads")
    kept = script("kept_reads")
    files = script("file_reads")
    continued = []

    def slow_stamp(*_):
        time.sleep(0.2)

    def main(_):
        reads.holds((reads.By.STAMP, "fixture", (), (), None))
        continued.append(True)
        return 0

    monkeypatch.setattr(reads, "stamp_now", slow_stamp)
    monkeypatch.setattr(operate, "main", main)
    monkeypatch.setattr(service, "executor", contextlib.nullcontext)
    monkeypatch.setattr(service.select, "select", lambda *_: ([], [], []))
    monkeypatch.setattr(kept, "fresh_code", lambda _: "current")
    monkeypatch.setattr(kept, "flush", lambda: True)
    monkeypatch.setattr(files, "stats_stand_but", lambda _: None)
    monkeypatch.setattr(service.script_calls, "start_request", lambda *_: None)
    monkeypatch.setattr(service.script_calls, "record", lambda: None)
    monkeypatch.setattr(service, "timeout_output", lambda _: print("expired"))
    message = {"operator": "fixture", "started": time.time(),
               "deadline": time.monotonic() + 0.05, "refresh": False}
    connection = Mock()
    connection.makefile.return_value = io.BytesIO((json.dumps(message) + "\n").encode())
    handler = signal.getsignal(signal.SIGALRM)
    try:
        assert service.serve_request(connection, Mock(), "current") is False
    finally:
        signal.signal(signal.SIGALRM, handler)
    assert not continued
    response = json.loads(connection.sendall.call_args.args[0])
    assert response["status"] == 1
    assert response["stdout"] == "expired\n"


def test_disconnect_after_a_journaled_start_does_not_repeat_bash(resident):
    root, _ = resident
    connection = open_request(root, "journal")
    until(root / "entered")
    connection.close()
    (root / "release").write_text("")
    assert call(root, "journal")[0] == 0
    until(root / "executions")
    assert (root / "executions").read_text() == "run\n"


def test_replacement_request_cancels_waiting_operator(resident):
    root, _ = resident
    old = open_request(root, "wait")
    until(root / "entered")
    assert call(root, "replacement")[0] == 0
    with old, old.makefile("rb") as response:
        out = json.loads(response.readline())
    assert out["status"] == 1
    assert "old wait" not in out["stdout"]


def test_failed_journal_write_cannot_execute_bash(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    journal = script("step_journal")
    from operations.steps import Bash
    processes = []
    popen = subprocess.Popen

    def start(*args, **kwargs):
        proc = popen(*args, **kwargs)
        processes.append(proc)
        return proc

    def fail(*_):
        raise OSError("journal write failed")

    monkeypatch.setattr(journal.subprocess, "Popen", start)
    monkeypatch.setattr(journal, "append", fail)
    with pytest.raises(OSError):
        journal.start_run(tmp_path, Bash("touch executed", "fixture", occasion="once"), "operator", tmp_path, 1)
    for proc in processes:
        proc.wait(timeout=10)
    assert not (tmp_path / "executed").exists()


def test_simultaneous_starts_share_one_owner(resident):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    root, processes = resident
    barrier = threading.Barrier(3)

    def start():
        barrier.wait()
        service.ensure(root, "isolated-service", time.monotonic() + 20).close()

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda _: start(), range(3)))
    assert len(processes) == 1
    assert call(root)[0] == 0


def test_idle_shutdown_removes_endpoint(resident):
    root, processes = resident
    (root / "idle").write_text("")
    service.ensure(root, "isolated-service", time.monotonic() + 20).close()
    processes[0].wait(timeout=20)
    assert not service.endpoint(root, "isolated-service").exists()


def test_failed_service_restarts(resident):
    root, processes = resident
    assert call(root)[0] == 0
    processes[0].terminate()
    processes[0].wait(timeout=20)
    assert call(root, "new")[0] == 0
    assert len(processes) == 2


def test_merge_refresh_uses_the_resident_while_its_lock_is_held(resident, monkeypatch):
    root, processes = resident
    monkeypatch.syspath_prepend(str(SCRIPTS))
    locks = script("refresh_locks")
    monkeypatch.setattr(locks.checkout, "caches", lambda: root / ".cache")
    assert call(root)[0] == 0
    with locks.hold("isolated-service"):
        (root / "code").write_text("merged")
        assert service.refresh_resident(root, "isolated-service", "op")
    assert call(root)[1].startswith("merged op ready ")
    assert len(processes) == 2


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
    code = kept.fresh_code("operate")
    dependency.write_text("value = 2\n")
    a, b = socket.socketpair()
    c, d = socket.socketpair()
    with a, b, c, d:
        current = service.Request("op", 1, time.monotonic() + 10, a, c, code,
                                  io.StringIO(), io.StringIO())
        with pytest.raises(service.Replaced):
            current.check(code=True)


def test_cold_service_code_identity_survives_importing_operate(tmp_path):
    """Use real import resolution: the transport fixtures replace the digest."""
    done = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(f'''
            import sys
            from pathlib import Path
            sys.path.insert(0, {str(SCRIPTS)!r})
            import operate_service as service
            import kept_reads
            store = kept_reads.open_store
            kept_reads.open_store = lambda **kwargs: store(Path({str(tmp_path / "reads.sqlite")!r}))
            endpoint = service.endpoint
            path = endpoint(Path({str(tmp_path)!r}), "cold-code")
            service.endpoint = lambda *_: path
            service.IDLE_SECONDS = 0.001
            service.script_calls.start_service = lambda *_: None
            service.script_calls.record = lambda: None
            digests = []
            fresh = kept_reads.fresh_code
            def digest(module):
                value = fresh(module)
                digests.append(value)
                return value
            kept_reads.fresh_code = digest
            service.serve()
            path.with_suffix(".owner").unlink()
            assert len(digests) == 2
            assert digests[0] == digests[1], digests
        ''')], env={k: v for k, v in os.environ.items() if k != service.CODE_ENV},
        capture_output=True, text=True, timeout=20)
    assert done.returncode == 0, done.stdout + done.stderr


def test_resident_work_is_present_in_the_cost_records(resident):
    root, _ = resident
    for _ in range(4):
        assert call(root)[0] == 0
    calls = service.script_calls.read(str(root / ".cache/script-calls"), 0)
    startup = [c for c in calls if c.key == "operate_service.py startup"]
    requests = [c for c in calls if c.key == "operate.py next"]
    assert len(startup) == 1
    assert startup[0].cpu > 0
    assert len(requests) >= 3
    assert all(c.retained and c.cpu >= 0 and c.session == "isolated-service" for c in requests)


@pytest.mark.parametrize("outcome", ["change", "expiry", "disconnect", "read_budget"])
def test_inflight_code_change_responds_and_flushes_before_retiring(tmp_path, monkeypatch, outcome):
    """Force the merge between completed reads and response publication."""
    import io
    import signal
    monkeypatch.syspath_prepend(str(SCRIPTS))
    operate = script("operate")
    kept = script("kept_reads")
    files = script("file_reads")
    reads = script("state_reads")
    source = tmp_path / "source"
    source.write_text("completed")
    monkeypatch.setattr(kept, "_store", None)
    kept.open_store(tmp_path / "reads.sqlite")
    monkeypatch.setattr(service, "executor", contextlib.nullcontext)
    monkeypatch.setattr(service, "side_effect", contextlib.nullcontext)
    monkeypatch.setattr(service.select, "select", lambda *_: ([], [], []))
    code = ["old"]
    monkeypatch.setattr(kept, "fresh_code", lambda _: code[0])
    monkeypatch.setattr(files, "stats_stand_but", lambda _: None)
    monkeypatch.setattr(service.script_calls, "start_request", lambda *_: None)
    monkeypatch.setattr(service.script_calls, "record", lambda: None)

    @reads.state_cache(reads.DERIVED, kept=reads.Kept.DISK)
    def completed(path):
        return files.file_text(path)

    def main(_):
        reads.new_state()
        print(completed(source))
        if outcome == "read_budget":
            service.read_phase("budget history")
            with service.reading():
                signal.raise_signal(signal.SIGALRM)
        if outcome == "expiry":
            raise service.Expired
        if outcome == "disconnect":
            raise service.Disconnected
        code[0] = "new"
        service.check()
        return 0

    monkeypatch.setattr(operate, "main", main)
    monkeypatch.setattr(service, "timeout_output", lambda _: print("expired"))
    message = {"operator": "fixture", "started": time.time(),
               "deadline": time.monotonic() + 20, "refresh": False}
    connection = Mock()
    connection.makefile.return_value = io.BytesIO((json.dumps(message) + "\n").encode())
    handler = signal.getsignal(signal.SIGALRM)
    try:
        assert service.serve_request(connection, Mock(), "old") is (outcome == "disconnect")
    finally:
        signal.signal(signal.SIGALRM, handler)
    out = json.loads(connection.sendall.call_args.args[0])
    if outcome == "read_budget":
        assert out["retry"] is False and out["status"] == 1
        assert out["stdout"] == ""
        assert "budget history" in out["stderr"]
        assert "preserve completed reads" in out["stderr"]
    else:
        assert out == {"retry": False, "status": 0 if outcome == "change" else 1,
                       "stdout": "completed\n" if outcome == "change" else "expired\n", "stderr": ""}
    # Only the final flush makes the completed read visible to another store.
    other = kept.Store(kept.store().path)
    name = reads.name_of(completed)
    key = repr(reads.canonical(reads.split(reads.call_of((source,), ()))))
    assert other.held(name, key)[1] == "completed"
    other.close()


def test_failed_startup_reports_the_cause_without_retrying(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "connect", Mock(side_effect=FileNotFoundError))
    process = Mock(returncode=7)
    process.poll.return_value = 7

    def start(*_, **kwargs):
        kwargs["stderr"].write("fixture startup failure\n")
        kwargs["stderr"].flush()
        return process

    started = Mock(side_effect=start)
    monkeypatch.setattr(service.subprocess, "Popen", started)
    kept = script("kept_reads")
    monkeypatch.setattr(kept, "fresh_code", lambda _: "current")
    with pytest.raises(service.Unavailable, match="fixture startup failure"):
        call(tmp_path)
    assert started.call_count == 1


def test_read_without_time_for_flush_fails_before_reading(monkeypatch):
    import io
    current = service.Request("fixture", time.time(), time.monotonic() + 1,
                              Mock(), Mock(), "old", io.StringIO(), io.StringIO())
    token = service.CURRENT.set(current)
    try:
        service.read_phase("budget history")
        with pytest.raises(service.Unavailable, match="budget history"):
            with service.reading():
                pytest.fail("a read with no time to finish must not start")
    finally:
        service.CURRENT.reset(token)


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
