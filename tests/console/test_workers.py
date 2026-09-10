"""The worker process: the requests it raises, the protocol it speaks, and
its handoff across a reload."""

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
    codex_item,
    idle_worker,
    item,
    night_workers,
    worker,
)

# ---------- permission requests ----------

def perm_request(srv, path, tool="Edit", subtype="can_use_tool"):
    return {"type": "control_request", "request_id": "r1",
            "request": {"subtype": subtype, "tool_name": tool,
                        "input": {"file_path": str(path), "old_string": "a",
                                  "new_string": "b"},
                        "decision_reason": f"{path} is a sensitive file.",
                        "tool_use_id": "tu1"}}


def test_an_agent_file_is_the_worker_s_to_edit(srv):
    for tool in ("Edit", "Write"):
        req = perm_request(srv, srv.AGENT_DIR / "cleanup.md", tool=tool)["request"]
        assert srv.permission_decision(req) == {
            "behavior": "allow", "updatedInput": req["input"]}


def test_every_other_request_keeps_the_cli_refusal(srv):
    for path, tool in ((srv.ROOT / ".claude" / "settings.json", "Edit"),
                       (srv.ROOT / "programs" / "lib.dl", "Bash"),
                       (srv.AGENT_DIR / "cleanup.md", "Bash"),
                       (srv.AGENT_DIR / "notes.txt", "Edit"),
                       (srv.AGENT_DIR / "sub" / "cleanup.md", "Edit"),
                       ("/tmp/note.txt", "Write")):
        req = perm_request(srv, path, tool=tool)["request"]
        decision = srv.permission_decision(req)
        assert decision["behavior"] == "deny"
        assert decision["message"] == req["decision_reason"]


def test_an_agent_file_edit_lands_as_a_shared_write(srv):
    assert any(rel.startswith(".claude/agents/") and rel.endswith(".md")
               for rel in srv.watched_paths("a"))


def test_a_permission_request_is_answered_on_the_stream(srv):
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    lib = srv.ROOT / "programs" / "lib.dl"
    srv.handle_event(w, perm_request(srv, lib), None)
    assert w["outbound"].get_nowait() == {
        "type": "control_response",
        "response": {"subtype": "success", "request_id": "r1",
                     "response": {"behavior": "deny",
                                  "message": f"{lib} is a sensitive file.",
                                  "toolUseID": "tu1"}}}
    assert it["feed"][-1]["text"] == "permission denied: Edit programs/lib.dl"


def test_a_denial_says_which_file_it_was(srv):
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    srv.handle_event(w, perm_request(srv, srv.ROOT / "programs" / "lib.dl",
                                     tool="Write"), None)
    assert w["outbound"].get_nowait()["response"]["response"]["behavior"] == "deny"
    assert it["feed"][-1]["text"] == "permission denied: Write programs/lib.dl"


def test_an_unknown_control_request_still_gets_a_response(srv):
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    srv.handle_event(w, perm_request(srv, srv.ROOT / "programs" / "lib.dl", subtype="elicitation"), None)
    reply = w["outbound"].get_nowait()
    assert reply["response"]["subtype"] == "error"
    assert reply["response"]["request_id"] == "r1"


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


def test_comment_routes_to_the_chosen_session(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, trigger=None, handoff=False:
                        sent.append(phase))
    item(srv, "a", srv.NEEDS_REVIEW, sessions={"create": "cs", "refine": "rs"})
    worker(srv, srv.find("a"), phase="create")
    srv.act_comment("a", "why rank over area?", "create")
    assert sent == ["create"]


# ---------- persistent worker protocol ----------

def fake_process(item_id="proto", phase="refine"):
    return subprocess.Popen([sys.executable, str(FAKE_WORKER), item_id, phase],
                            env={**os.environ, "CONSOLE_FAKE_PACE": FAKE_PACE},
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            text=True, bufsize=1)


def test_init_records_the_session_and_flags_a_tool_outside_the_set(srv):
    it = item(srv, "a", srv.RUNNING, sessions={"create": None, "refine": None})
    w = worker(srv, it, state="sending")
    w["session_seen"] = False
    srv.handle_event(w, {"type": "system", "subtype": "init", "session_id": "s9",
                         "tools": sorted(srv.WORKER_TOOLS) + ["WebFetch"]}, None)
    assert it["sessions"]["refine"] == "s9"
    assert "WebFetch" in it["feed"][-1]["text"]
    assert w["state"] == "running"


def test_post_restart_comment_respawns_into_the_session(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, trigger=None, handoff=False:
                        sent.append((msg, phase)))
    item(srv, "a", srv.NEEDS_REVIEW)
    assert srv.act_comment("a", "continue") == {"ok": True}
    assert sent == [("continue", "refine")]


def test_worker_cmd_resumes_a_recorded_session(srv, tmp_path, monkeypatch):
    monkeypatch.setattr(srv, "FAKE", False)
    append = tmp_path / "append.md"
    append.write_text("brief")
    it = item(srv, "a", srv.NEEDS_REVIEW, append=str(append))
    cmd = srv.worker_cmd(it, "refine")
    assert cmd[cmd.index("--resume") + 1] == "sess-a"
    it["sessions"]["refine"] = None
    assert "--resume" not in srv.worker_cmd(it, "refine")


def test_dead_worker_relaunch_resumes_and_lands(srv, monkeypatch):
    monkeypatch.setattr(srv, "FAKE", True)
    it = item(srv, "rs", srv.NEEDS_REVIEW)
    assert srv.act_comment("rs", "carry on") == {"ok": True}
    deadline = time.time() + 8
    while it["state"] != srv.NEEDS_REVIEW and time.time() < deadline:
        time.sleep(TICK)
    try:
        assert it["state"] == srv.NEEDS_REVIEW
        assert any("resuming its session" in m.get("text", "")
                   for m in it["feed"] if m["kind"] == "event")
        assert any(m["kind"] == "report" for m in it["feed"])
    finally:
        srv.shutdown_workers()


def test_an_idle_session_takes_comments_while_another_runs(srv):
    it = item(srv, "a", srv.RUNNING,
              sessions={"create": "cs", "refine": "rs"})
    worker(srv, it, phase="refine", state="running")
    cw = worker(srv, it, phase="create", state="idle")
    assert srv.act_comment("a", "why rank over area?", "create") == {"ok": True}
    assert cw["state"] == "sending"
    assert it["state"] == srv.RUNNING      # the running pass keeps the state
    assert "pre" not in it                 # and the revert snapshot
    rw = srv.PROCS[("a", "refine")]
    assert srv.act_comment("a", "hurry", "refine") == {"ok": True}
    assert rw["state"] == "running"        # the running pass takes it as a steer
    assert rw["turn_seq"] == 1


def test_a_side_landing_leaves_the_state_to_the_running_pass(srv):
    it = item(srv, "a", srv.RUNNING, sessions={"create": "cs", "refine": "rs"})
    worker(srv, it, phase="refine", state="running")
    worker(srv, it, phase="create", state="running")
    srv.finish_turn(it, {"result": "an answer"}, None, time.time(),
                    "create", False)
    assert it["state"] == srv.RUNNING


def test_drop_detaches_all_idle_phase_workers(srv, monkeypatch):
    reaped = []
    monkeypatch.setattr(srv, "queue_reap", reaped.append)
    it = item(srv, "a", srv.NEEDS_REVIEW,
              sessions={"create": "cs", "refine": "rs"})
    create = worker(srv, it, phase="create")
    refine = worker(srv, it, phase="refine")
    assert srv.act_drop("a") == {"ok": True}
    assert srv.find("a") is None
    assert reaped == [create, refine]
    assert create["state"] == refine["state"] == "dying"


def test_cancelled_handoff_does_not_target_recreated_id(srv, monkeypatch):
    called = []
    monkeypatch.setattr(srv, "advance_stage", lambda it: called.append(it))
    old = item(srv, "a", srv.RUNNING, phase="create", handoff_pending=True)
    old_worker = worker(srv, old, phase="create", state="idle", turn_seq=3)
    srv.STATE["items"].remove(old)
    srv.PROCS.pop(("a", "create"))
    item(srv, "a", srv.QUEUED, phase="create", handoff_pending=True)
    srv.DEFERRED.put_nowait(("handoff", "a", "create", old_worker["turn_seq"]))
    srv.ensure_drain()
    deadline = time.time() + 1
    while srv.find("a").get("handoff_pending") and time.time() < deadline:
        time.sleep(TICK)
    assert called == []
    assert "handoff_pending" not in srv.find("a")


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


def test_idle_reap_drops_a_worker_past_the_ttl(srv, monkeypatch):
    reaped = []
    monkeypatch.setattr(srv, "queue_reap", reaped.append)
    it = item(srv, "a", srv.NEEDS_REVIEW)
    w = idle_worker(srv, it, idle_for=srv.IDLE_TTL + 1)
    srv.reap_idle()
    assert ("a", "refine") not in srv.PROCS
    assert reaped == [w]
    assert w["state"] == "dying"
    assert w["outbound"].get_nowait() is srv.STOP
    assert it["feed"][-1]["sess"] == "refine"
    # the session survives, so a later comment resumes the phase
    assert it["sessions"]["refine"] == "sess-a"


def test_idle_reap_keeps_a_worker_inside_the_ttl(srv, monkeypatch):
    monkeypatch.setattr(srv, "queue_reap", lambda w: pytest.fail("reaped"))
    it = item(srv, "a", srv.NEEDS_REVIEW)
    idle_worker(srv, it, idle_for=srv.IDLE_TTL - 60)
    srv.reap_idle()
    assert ("a", "refine") in srv.PROCS


def test_idle_reap_is_silent_when_it_takes_nothing(srv, monkeypatch):
    """The poll runs every minute and save() rewrites the whole state file."""
    monkeypatch.setattr(srv, "bump", lambda: pytest.fail("bumped"))
    it = item(srv, "a", srv.NEEDS_REVIEW)
    idle_worker(srv, it, idle_for=0)
    srv.reap_idle()
    assert it["feed"] == []


@pytest.mark.parametrize("pending", ["callout_wait", "handoff_pending"])
def test_idle_reap_spares_a_worker_with_a_deferred_job(srv, monkeypatch, pending):
    """drain_deferred skips the callout turn and the stage advance when the
    worker is gone, so a pending job has to outrank the TTL."""
    monkeypatch.setattr(srv, "queue_reap", lambda w: pytest.fail("reaped"))
    it = item(srv, "a", srv.NEEDS_REVIEW,
              **{pending: "refine" if pending == "callout_wait" else True})
    idle_worker(srv, it, idle_for=srv.IDLE_TTL * 2)
    srv.reap_idle()
    assert ("a", "refine") in srv.PROCS


@pytest.mark.parametrize("state", ["spawning", "sending", "running", "dying"])
def test_idle_reap_leaves_a_worker_that_is_not_idle(srv, monkeypatch, state):
    monkeypatch.setattr(srv, "queue_reap", lambda w: pytest.fail("reaped"))
    it = item(srv, "a", srv.RUNNING)
    idle_worker(srv, it, idle_for=srv.IDLE_TTL * 2, state=state)
    srv.reap_idle()
    assert ("a", "refine") in srv.PROCS


def test_launch_clears_the_idle_clock(srv, monkeypatch):
    monkeypatch.setattr(srv, "queue_reap", lambda w: pytest.fail("reaped"))
    it = item(srv, "a", srv.NEEDS_REVIEW)
    w = idle_worker(srv, it, idle_for=srv.IDLE_TTL * 2)
    srv.launch(it, "look again", "refine")
    assert w["idle_since"] is None
    srv.reap_idle()
    assert ("a", "refine") in srv.PROCS


def test_night_cap_drops_the_oldest_idle_workers(srv, monkeypatch):
    """A landed phase leaves its process resident, so the count climbs with
    every handoff until the cap pulls it back."""
    monkeypatch.setattr(srv, "NIGHT_WORKER_CAP", 2)
    reaped = []
    monkeypatch.setattr(srv, "queue_reap", reaped.append)
    night_workers(srv, [300, 100, 200, 50])
    srv.reap_idle()
    assert [w["item_id"] for w in reaped] == ["n0", "n2"]
    assert sorted(key[0] for key in srv.PROCS) == ["n1", "n3"]
    for item_id in ("n0", "n2"):
        assert srv.find(item_id)["feed"][-1]["sess"] == "refine"


def test_night_cap_counts_the_running_workers(srv, monkeypatch):
    """The cap is a ceiling on what the machine holds, so a turn in flight
    takes a slot from the idle leftovers."""
    monkeypatch.setattr(srv, "NIGHT_WORKER_CAP", 2)
    reaped = []
    monkeypatch.setattr(srv, "queue_reap", reaped.append)
    worker(srv, item(srv, "busy", srv.RUNNING, night=True), state="running")
    night_workers(srv, [100, 200])
    srv.reap_idle()
    assert [w["item_id"] for w in reaped] == ["n1"]
    assert ("busy", "refine") in srv.PROCS


def test_night_cap_holds_after_the_mode_is_off(srv, monkeypatch):
    """The mark rides on the item, so the workers autopilot started stay
    capped once it is switched off."""
    monkeypatch.setattr(srv, "NIGHT_WORKER_CAP", 1)
    reaped = []
    monkeypatch.setattr(srv, "queue_reap", reaped.append)
    assert srv.night()["on"] is False
    night_workers(srv, [100, 200])
    srv.reap_idle()
    assert [w["item_id"] for w in reaped] == ["n1"]


def test_night_cap_leaves_a_hand_started_item_alone(srv, monkeypatch):
    monkeypatch.setattr(srv, "NIGHT_WORKER_CAP", 1)
    monkeypatch.setattr(srv, "queue_reap", lambda w: pytest.fail("reaped"))
    for n in range(3):
        idle_worker(srv, item(srv, f"h{n}", srv.NEEDS_REVIEW), idle_for=100)
    srv.reap_idle()
    assert len(srv.PROCS) == 3


def test_night_cap_is_silent_under_the_ceiling(srv, monkeypatch):
    monkeypatch.setattr(srv, "NIGHT_WORKER_CAP", 3)
    monkeypatch.setattr(srv, "bump", lambda: pytest.fail("bumped"))
    monkeypatch.setattr(srv, "queue_reap", lambda w: pytest.fail("reaped"))
    night_workers(srv, [100, 200, 300])
    srv.reap_idle()
    assert len(srv.PROCS) == 3


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


# ---------- hot-reload worker handoff ----------

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


def test_a_comment_takes_the_flag_back_from_a_pending_reload(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW)
    worker(srv, it)
    srv.quiesce_workers()
    assert srv.act_comment("a", "one more") == {"ok": True}
    assert not srv.RELOADING


def test_a_running_turn_counts_against_the_reload(srv):
    it = item(srv, "a", srv.COMMENTED)
    w = worker(srv, it, state="running")
    with srv.LOCK:
        assert srv.turns_in_flight()
        w["state"] = "idle"
        it["state"] = srv.NEEDS_REVIEW
        assert not srv.turns_in_flight()


def test_a_running_committer_counts_against_the_reload(srv):
    """The committer writes git from a process of its own, which an exec
    would leave running with nothing reading it."""
    with srv.LOCK:
        assert not srv.turns_in_flight()
        srv.COMMITTER.update(running=True, note=None, started=time.time(), feed=[])
        assert srv.turns_in_flight()
        srv.COMMITTER["running"] = False
        assert not srv.turns_in_flight()


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


def run_deferred(srv):
    """Run the queued jobs on this thread, the way the drain would."""
    srv.DEFERRED.put_nowait(srv.STOP)
    srv.drain_deferred()


@pytest.mark.parametrize("kind", ["callout", "rehandoff", "handoff"])
def test_an_owed_turn_that_meets_the_reload_is_sent_after_it(srv, monkeypatch, kind):
    launched = []
    monkeypatch.setattr(srv, "ensure_drain", lambda: None)
    monkeypatch.setattr(srv, "launch", lambda it, msg, phase, **kw:
                        launched.append((phase, kw.get("trigger"), bool(kw.get("handoff")))))
    it = item(srv, "a", srv.RUNNING, phase="create", landed=["create"],
              sessions={"create": "cs", "refine": None}, auto_advance=True,
              **({"callout_wait": "create"} if kind == "callout" else
                 {"handoff_pending": True} if kind == "handoff" else {}))
    it["reports"] = {"create": "the report"}
    w = worker(srv, it, phase="create")
    with srv.LOCK:
        srv.owe(it, kind, "create", w)
        assert srv.turns_in_flight()
    srv.RELOADING = True
    run_deferred(srv)
    assert launched == []
    assert it["reload_ask"] == {"kind": kind, "phase": "create"}
    assert it["state"] == srv.NEEDS_REVIEW
    assert not srv.turns_in_flight()
    srv.RELOADING = False
    with srv.LOCK:
        srv.resume_paused()
    assert "reload_ask" not in it
    assert launched == [{"callout": ("create", "callout", False),
                         "rehandoff": ("create", "handoff", True),
                         "handoff": ("refine", None, False)}[kind]]
    assert it["state"] == srv.RUNNING


def test_a_landing_compact_that_meets_the_reload_runs_after_it(srv, monkeypatch):
    monkeypatch.setattr(srv, "ensure_drain", lambda: None)
    launched = []
    monkeypatch.setattr(srv, "launch", lambda it, msg, phase, **kw: launched.append(msg))
    srv.auto()["compact_landing"] = True
    it = item(srv, "a", srv.NEEDS_REVIEW)
    w = worker(srv, it)
    srv.DEFERRED.put_nowait(("compact", "a", "refine", w["turn_seq"]))
    srv.RELOADING = True
    run_deferred(srv)
    assert launched == [] and it["reload_ask"] == {"kind": "compact", "phase": "refine"}
    srv.RELOADING = False
    with srv.LOCK:
        srv.resume_paused()
    assert launched == ["/compact"]


def test_a_called_off_reload_sends_the_turns_it_set_aside(srv, monkeypatch):
    launched = []
    monkeypatch.setattr(srv, "launch", lambda it, msg, phase, **kw: launched.append(phase))
    it = item(srv, "a", srv.NEEDS_REVIEW, reload_ask={"kind": "callout", "phase": "refine"})
    it["reports"] = {"refine": "the report"}
    worker(srv, it)
    monkeypatch.setattr(srv, "quiesce_workers", lambda: False)
    assert srv.reload_server() == "deferred"
    assert launched == ["refine"]


def test_a_deferred_quiesce_leaves_the_workers_alone(srv, monkeypatch):
    it = item(srv, "a", srv.QUEUED)
    worker(srv, it)
    monkeypatch.setattr(srv.os, "execv",
                        lambda exe, argv: pytest.fail("exec during a deferral"))
    out = []
    thread = threading.Thread(target=lambda: out.append(srv.reload_server()),
                              daemon=True)
    thread.start()
    deadline = time.time() + 2
    while not srv.RELOADING and time.time() < deadline:
        time.sleep(TICK)
    assert srv.RELOADING
    with srv.LOCK:
        srv.defer_reload()
    thread.join(timeout=2)
    assert out == ["deferred"]
    assert not srv.RELOADING
    assert (it["id"], "refine") in srv.PROCS


def test_an_action_after_the_quiesce_calls_the_exec_off(srv, monkeypatch):
    item(srv, "a", srv.NEEDS_REVIEW)
    monkeypatch.setattr(srv.os, "execv",
                        lambda exe, argv: pytest.fail("exec after a deferral"))
    quiesce = srv.quiesce_workers

    def act_in_the_window():
        held = quiesce()
        with srv.LOCK:
            srv.defer_reload()   # an action lands between the wait and the exec
        return held

    monkeypatch.setattr(srv, "quiesce_workers", act_in_the_window)
    assert srv.reload_server() == "deferred"
    assert not srv.RELOADING


def test_stagger_launch_finishes_admitted_wave_during_reload(srv, monkeypatch):
    it = item(srv, "a", srv.QUEUED, phase="create")
    srv.RELOADING = True
    launched = []
    monkeypatch.setattr(srv, "STAGGER_TIMEOUT", 0)
    monkeypatch.setattr(srv, "launch", lambda *args, **kwargs: launched.append(kwargs))
    srv._test_stagger_launch([it["id"]])
    assert it["state"] == srv.RUNNING
    assert launched == [{"handoff": True, "admitted": True}]


def test_codex_items_launch_without_the_cache_seeder(srv, monkeypatch):
    items = [codex_item(srv, name, srv.QUEUED) for name in ("a", "b")]
    launched = []
    monkeypatch.setattr(srv, "STAGGER_TIMEOUT", 30)   # long enough to hang on
    monkeypatch.setattr(srv, "launch",
                        lambda it, *args, **kwargs: launched.append(it["id"]))
    srv._test_stagger_launch([it["id"] for it in items])
    assert launched == ["a", "b"]
    assert srv.FIRST_RESPONSE == {}
    assert not any("seeder" in m["text"] for m in items[0]["feed"])


def test_a_mixed_wave_seeds_on_its_claude_item(srv, monkeypatch):
    codex_item(srv, "a", srv.QUEUED)
    item(srv, "b", srv.QUEUED, phase="create", landed=[],
         sessions={"create": None, "refine": None})
    launched = []
    monkeypatch.setattr(srv, "STAGGER_TIMEOUT", SETTLE)
    monkeypatch.setattr(srv, "launch",
                        lambda it, *args, **kwargs: launched.append(it["id"]))
    srv._test_stagger_launch(["a", "b"])
    assert launched == ["b", "a"]   # the claude item goes first, alone
    assert any("seeder" in m["text"] for m in srv.find("b")["feed"])


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


@pytest.mark.parametrize("change", ["active", "dropped"])
def test_stagger_launch_skips_item_changed_while_waiting(srv, monkeypatch, change):
    first = item(srv, "a", srv.QUEUED, phase="create")
    second = item(srv, "b", srv.QUEUED, phase="create")
    seeded = threading.Event()
    launched = []

    def fake_launch(it, *args, **kwargs):
        launched.append(it["id"])
        if it is first:
            seeded.set()

    monkeypatch.setattr(srv, "STAGGER_TIMEOUT", 1)
    monkeypatch.setattr(srv, "launch", fake_launch)
    thread = threading.Thread(target=srv._test_stagger_launch,
                              args=([first["id"], second["id"]],))
    thread.start()
    assert seeded.wait(1)
    with srv.LOCK:
        if change == "active":
            worker(srv, second, phase="create", state="running")
        else:
            srv.STATE["items"].remove(second)
        release = srv.FIRST_RESPONSE[first["id"]]
    release.set()
    thread.join(timeout=1)
    assert launched == ["a"]


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


def test_rejected_worker_clears_session_and_posts_feed(srv, tmp_path):
    it, _ = idle_fake(srv, "rejected")
    lost_session = it["sessions"]["refine"]
    regular = open(tmp_path / "not-a-pipe", "w")
    manifest = handoff_fds(srv.worker_manifest(), swap=regular)
    srv.PROCS.clear()
    try:
        srv.adopt_workers(manifest)
        assert it["sessions"]["refine"] is None
        assert "session lost on reload" in it["feed"][-1]["text"]
        assert lost_session in it["feed"][-1]["text"]
    finally:
        regular.close()
