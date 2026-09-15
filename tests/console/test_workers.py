"""The worker process: its permission requests, its death, and its handoff
across a reload."""

import json
import os
import queue
import subprocess
import sys
import threading
import time
import uuid

import pytest

from .conftest import (
    FAKE_PACE,
    FAKE_WORKER,
    HOLD,
    SETTLE,
    TICK,
    item,
    worker,
)


def perm_request(srv, path, tool="Edit", subtype="can_use_tool"):
    return {"type": "control_request", "request_id": "r1",
            "request": {"subtype": subtype, "tool_name": tool,
                        "input": {"file_path": str(path), "old_string": "a",
                                  "new_string": "b"},
                        "decision_reason": f"{path} is a sensitive file.",
                        "tool_use_id": "tu1"}}


def test_every_other_request_keeps_the_cli_refusal(srv):
    for path, tool in ((srv.ROOT / ".claude" / "settings.json", "Edit"),
                       (srv.ROOT / "programs" / "lib.dl", "Bash"),
                       (srv.ROLE_DIR / "cleanup.md", "Bash"),
                       (srv.ROLE_DIR / "notes.txt", "Edit"),
                       (srv.ROLE_DIR / "sub" / "cleanup.md", "Edit"),
                       ("/tmp/note.txt", "Write")):
        req = perm_request(srv, path, tool=tool)["request"]
        decision = srv.permission_decision(req)
        assert decision["behavior"] == "deny"
        assert decision["message"] == req["decision_reason"]


def test_a_broken_policy_refuses_rather_than_hangs(srv, monkeypatch):
    def boom(req):
        raise RuntimeError("policy bug")
    monkeypatch.setattr(srv, "permission_decision", boom)
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    srv.handle_event(w, perm_request(srv, srv.ROOT / "programs" / "lib.dl"), None)
    decision = w["outbound"].get_nowait()["response"]["response"]
    assert decision["behavior"] == "deny"
    assert "policy bug" in decision["message"]


def fake_process(item_id="proto", phase="refine"):
    return subprocess.Popen([sys.executable, str(FAKE_WORKER), item_id, phase],
                            env={**os.environ, "CONSOLE_FAKE_PACE": FAKE_PACE},
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            text=True, bufsize=1)


def test_stop_escalation_holds_lock_through_terminate(srv, monkeypatch):
    monkeypatch.setattr(srv.time, "sleep", lambda _: None)
    it = item(srv, "a", srv.COMMENTED)
    entered = threading.Event()
    release = threading.Event()

    class Proc:
        def poll(self):
            return None

        def terminate(self):
            entered.set()
            assert release.wait(1)

    w = worker(srv, it, state="running", turn_seq=7)
    w["proc"] = Proc()
    assert srv.act_kill("a") == {"ok": True}
    assert entered.wait(1)
    acquired = threading.Event()

    def start_next_turn():
        with srv.LOCK:
            acquired.set()
            w["turn_seq"] += 1

    thread = threading.Thread(target=start_next_turn)
    thread.start()
    assert not acquired.wait(HOLD)
    release.set()
    thread.join(timeout=1)
    assert acquired.is_set()


def test_reader_death_stops_writer_before_removing_worker(srv):
    it = item(srv, "a", srv.RUNNING)

    class Proc:
        stdout = ()
        returncode = 1

        def wait(self):
            return 1

    class Outbound(queue.Queue):
        def put_nowait(self, value):
            if value is srv.STOP:
                assert srv.PROCS.get(("a", "refine")) is w
            super().put_nowait(value)

    w = worker(srv, it, state="idle")
    w.update(proc=Proc(), outbound=Outbound(), started=None,
             session_seen=True, seen=set())
    srv.reader(w)
    assert w["outbound"].get_nowait() is srv.STOP
    assert ("a", "refine") not in srv.PROCS


def test_deferred_drain_continues_after_job_failure(srv, monkeypatch):
    processed = []
    finished = threading.Event()

    def flaky_reap(w):
        if w == "bad":
            raise RuntimeError("stuck child")
        processed.append(w)
        finished.set()

    monkeypatch.setattr(srv, "reap", flaky_reap)
    srv.DEFERRED.put_nowait(("reap", "bad"))
    srv.DEFERRED.put_nowait(("reap", "good"))
    srv.ensure_drain()
    assert finished.wait(1)
    assert processed == ["good"]


def test_reap_tolerates_child_that_survives_kill(srv):
    class Proc:
        stdin = None
        stdout = None

        def __init__(self):
            self.waits = 0

        def poll(self):
            return None

        def terminate(self):
            pass

        def kill(self):
            pass

        def wait(self, timeout):
            self.waits += 1
            raise subprocess.TimeoutExpired("worker", timeout)

    class Thread:
        def join(self, timeout):
            pass

    w = {"item_id": "a", "proc": Proc(), "reader": Thread(), "writer": Thread()}
    srv.reap(w)
    assert w["proc"].waits == 2
    assert w["state"] == "dead"


def idle_fake(srv, item_id, phase="refine"):
    proc = fake_process(item_id, phase)
    it = item(srv, item_id, srv.NEEDS_REVIEW,
              sessions={"create": None, phase:
                        str(uuid.uuid5(uuid.NAMESPACE_URL,
                                      f"fake-worker/{item_id}/{phase}"))})
    w = worker(srv, it, phase=phase)
    w.update(proc=proc, started=None, trigger=None, handoff=False, seen=set(),
             got_result=False, session_seen=True)
    return it, w


def handoff_fds(manifest, swap=None):
    """Duplicate a manifest's descriptors so the adopting side owns them alone.
    A real handoff execs, which leaves the Popen objects behind; in-process
    they stay alive, and the second owner to close a number frees whatever the
    next test was handed in its place. `swap` replaces one entry's stdout with
    a descriptor of its own, for the tests that feed adoption a bad pipe."""
    for entry in manifest["workers"]:
        for name in ("stdin_fd", "stdout_fd"):
            entry[name] = os.dup(entry[name])
    if swap is not None:
        os.close(manifest["workers"][0]["stdout_fd"])
        manifest["workers"][0]["stdout_fd"] = os.dup(swap.fileno())
    return manifest


def test_quiesce_handoff_adopt_keeps_pid_and_sends(srv):
    it, old = idle_fake(srv, "handoff")
    pid = old["proc"].pid
    try:
        srv.quiesce_workers()
        manifest = srv.worker_manifest()
        srv.save()
        os.environ[srv.WORKER_HANDOFF_ENV] = json.dumps(manifest)
        adopted_manifest = handoff_fds(srv.read_worker_handoff())
        assert srv.WORKER_HANDOFF_ENV not in os.environ
        srv.PROCS.clear()
        srv.RELOADING = False
        srv.adopt_workers(adopted_manifest)
        adopted = srv.PROCS[("handoff", "refine")]
        assert adopted["proc"].pid == pid
        with srv.LOCK:
            it["state"] = srv.COMMENTED
            srv.launch(it, "after exec", "refine")
        deadline = time.time() + 4
        while adopted["state"] != "idle" and time.time() < deadline:
            time.sleep(TICK)
        assert adopted["state"] == "idle"
        assert it["state"] == srv.NEEDS_REVIEW
        assert any(m.get("kind") == "report" for m in it["feed"])
    finally:
        srv.shutdown_workers()


@pytest.mark.parametrize("action", ["drop", "shutdown"])
def test_adopted_worker_reaps_on_drop_and_shutdown(srv, action):
    it, old = idle_fake(srv, "reap-" + action)
    pid = old["proc"].pid
    manifest = handoff_fds(srv.worker_manifest())
    srv.PROCS.clear()
    srv.adopt_workers(manifest)
    if action == "drop":
        assert srv.act_drop(it["id"]) == {"ok": True}
        deadline = time.time() + 4
        while time.time() < deadline:
            try:
                os.kill(pid, 0)
            except OSError:
                break
            time.sleep(TICK)
    else:
        srv.shutdown_workers()
    with pytest.raises(OSError):
        os.kill(pid, 0)


def test_adoption_validation_failure_drops_only_bad_worker(srv, tmp_path):
    _, bad = idle_fake(srv, "bad")
    _, good = idle_fake(srv, "good")
    bad_pid, good_pid = bad["proc"].pid, good["proc"].pid
    regular = open(tmp_path / "not-a-pipe", "w")
    manifest = handoff_fds(srv.worker_manifest(), swap=regular)
    srv.PROCS.clear()
    try:
        srv.adopt_workers(manifest)
        assert ("bad", "refine") not in srv.PROCS
        assert srv.PROCS[("good", "refine")]["proc"].pid == good_pid
        with pytest.raises(OSError):
            os.kill(bad_pid, 0)
    finally:
        regular.close()
        srv.shutdown_workers()


def test_shutdown_ends_the_committer_session(srv):
    """The committer writes git from a process of its own. A Ctrl-C that left
    it running would leave a git write going with the console gone."""
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                            start_new_session=True)
    srv.COMMITTER.update(running=True, note=None, started=time.time(), feed=[])
    srv.COMMITTER_PROC = proc
    try:
        srv.shutdown_workers()
        assert proc.poll() is not None
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=3)


def test_concurrent_stagger_launches_launch_each_item_once(srv, monkeypatch):
    items = [item(srv, name, srv.QUEUED, phase="create")
             for name in ("a", "b", "c")]
    launched = []
    monkeypatch.setattr(srv, "STAGGER_TIMEOUT", SETTLE)
    monkeypatch.setattr(srv, "launch",
                        lambda it, *args, **kwargs: launched.append(it["id"]))
    threads = [threading.Thread(target=srv._test_stagger_launch,
                                args=([it["id"] for it in items],))
               for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=1)
    assert sorted(launched) == ["a", "b", "c"]


def test_reload_waits_for_running_turn(srv, monkeypatch):
    it = item(srv, "a", srv.COMMENTED)
    w = worker(srv, it, state="running")
    execed = threading.Event()

    def fail_exec(exe, argv):
        execed.set()
        raise OSError("no exec")

    monkeypatch.setattr(srv.os, "execv", fail_exec)
    thread = threading.Thread(target=srv.reload_server, daemon=True)
    thread.start()
    assert not execed.wait(HOLD)  # holds while the turn is in flight
    with srv.COND:
        w["state"] = "idle"
        srv.PROCS.clear()
        srv.COND.notify_all()
    assert execed.wait(2)
    thread.join(timeout=2)
    assert not srv.RELOADING
    assert "server still running" in it["feed"][-1]["text"]


def test_execv_failure_restores_handoff_and_server(srv, monkeypatch):
    it, worker = idle_fake(srv, "exec-failure")
    fds = [worker["proc"].stdin.fileno(), worker["proc"].stdout.fileno()]
    monkeypatch.setattr(srv.os, "execv",
                        lambda exe, argv: (_ for _ in ()).throw(OSError("no exec")))
    try:
        srv.reload_server()
        assert not srv.RELOADING
        assert srv.WORKER_HANDOFF_ENV not in os.environ
        assert all(not os.get_inheritable(fd) for fd in fds)
        assert (it["id"], "refine") in srv.PROCS
        assert "server still running" in it["feed"][-1]["text"]
    finally:
        srv.PROCS.clear()
        worker["proc"].terminate()
        worker["proc"].wait(timeout=3)


def test_manifest_build_failure_rolls_back_reload_and_descriptors(srv, monkeypatch):
    _, first = idle_fake(srv, "manifest-first")
    _, second = idle_fake(srv, "manifest-second")
    fds = [first["proc"].stdin.fileno(), first["proc"].stdout.fileno(),
           second["proc"].stdin.fileno(), second["proc"].stdout.fileno()]
    real_find = srv.find

    def fail_on_second(item_id):
        if item_id == "manifest-second":
            raise RuntimeError("manifest failed")
        return real_find(item_id)

    monkeypatch.setattr(srv, "find", fail_on_second)
    try:
        srv.reload_server()
        assert not srv.RELOADING
        assert srv.WORKER_HANDOFF_ENV not in os.environ
        assert all(not os.get_inheritable(fd) for fd in fds)
    finally:
        monkeypatch.setattr(srv, "find", real_find)
        srv.PROCS.clear()
        for worker_ in (first, second):
            worker_["proc"].terminate()
            worker_["proc"].wait(timeout=3)


def test_manifest_from_different_server_pid_is_refused(srv):
    it, worker = idle_fake(srv, "wrong-server")
    manifest = srv.worker_manifest()
    manifest["server_pid"] = os.getpid() + 1
    srv.PROCS.clear()
    srv.adopt_workers(manifest)
    assert (it["id"], "refine") not in srv.PROCS
    assert it["sessions"]["refine"] is None
    worker["proc"].terminate()
    worker["proc"].wait(timeout=3)


