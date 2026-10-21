"""Resident request races and source/code invalidation in isolated checkouts."""

import json
import os
import socket
import subprocess
import sys
import textwrap
import time
from pathlib import Path

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


def test_code_replacement_during_a_request_discards_the_old_step(resident):
    root, processes = resident
    connection = open_request(root, "wait")
    until(root / "entered")
    (root / "code").write_text("new")
    (root / "release").write_text("")
    with connection, connection.makefile("rb") as response:
        assert json.loads(response.readline())["retry"] is True
    result = call(root)
    assert result[0] == 0
    assert result[1].startswith("new op ready ")
    assert result[2] == ""
    assert len(processes) == 2


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
            current.check()


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
            kept_reads.open_store = lambda: store(Path({str(tmp_path / "reads.sqlite")!r}))
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
