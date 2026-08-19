"""Review console: wave admission, item actions, and state loading.

The console module is loaded fresh per test with CONSOLE_STATE_DIR pointed at a
tmp dir, so its module-level state and paths never touch the real workspace.
"""

import importlib.util
import json
import os
import queue
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER_PY = ROOT / "tools" / "console" / "server.py"
FAKE_WORKER = ROOT / "tools" / "console" / "fake_worker.py"


@pytest.fixture
def srv(tmp_path, monkeypatch):
    monkeypatch.setenv("CONSOLE_STATE_DIR", str(tmp_path / "state"))
    spec = importlib.util.spec_from_file_location("console_server", SERVER_PY)
    s = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(s)
    s.STATE_DIR.mkdir(parents=True)
    s.LOG_DIR.mkdir(parents=True)
    for name in ("SOLVERS", "DOCS"):
        d = tmp_path / name.lower()
        d.mkdir()
        monkeypatch.setattr(s, name, d)
    monkeypatch.setattr(s, "queue_pick",
                        lambda n, order: [(f"t{i:02d}", 10 + i) for i in range(n)])
    s._test_stagger_launch = s.stagger_launch
    monkeypatch.setattr(s, "stagger_launch", lambda ids: None)
    return s


def item(s, item_id, state, **kw):
    """Append an item the way start_wave does, then override for the test."""
    it = {"id": item_id, "est": 10, "wave": 1, "state": state,
          "sessions": {"create": None, "refine": "sess-" + item_id},
          "phase": "refine", "refined": True,
          "lastActive": {"create": None, "refine": None},
          "dirty": False, "updated": False, "rev": 1, "title": "",
          "feed": [], "append": "", "ver": 0}
    it.update(kw)
    s.STATE["items"].append(it)
    return it


def worker(s, it, phase="refine", state="idle", turn_seq=1):
    w = {"item_id": it["id"], "phase": phase, "state": state,
         "turn_seq": turn_seq, "outbound": queue.Queue()}
    s.PROCS[(it["id"], phase)] = w
    return w


# ---------- waves ----------

def test_wave_queues_k_items(srv):
    res = srv.start_wave(2)
    assert res["ids"] == ["t00", "t01"]
    assert srv.STATE["wave"] == 1
    assert [it["state"] for it in srv.STATE["items"]] == [srv.QUEUED, srv.QUEUED]


def test_wave_starts_while_earlier_wave_runs(srv):
    srv.start_wave(2)
    for it in srv.STATE["items"]:
        it["state"] = srv.RUNNING
    srv.LAST_WAVE_AT = 0.0
    res = srv.start_wave(2)
    assert res["ids"] == ["t02", "t03"]  # picks past the running items
    assert srv.STATE["wave"] == 2
    assert len(srv.STATE["items"]) == 4


def test_wave_leaves_queued_items_alone(srv):
    srv.start_wave(2)
    srv.LAST_WAVE_AT = 0.0
    srv.start_wave(1)
    assert [it["id"] for it in srv.STATE["items"]] == ["t00", "t01", "t02"]


def test_wave_drops_committed_items(srv):
    item(srv, "old", srv.COMMITTED)
    srv.start_wave(1)
    assert [it["id"] for it in srv.STATE["items"]] == ["t00"]


def test_second_wave_within_debounce_is_refused(srv):
    srv.start_wave(2)
    res = srv.start_wave(2)
    assert "error" in res
    assert len(srv.STATE["items"]) == 2


def test_refused_wave_does_not_arm_the_debounce(srv):
    assert "error" in srv.start_wave(2, order="bogus")
    assert srv.start_wave(2)["ids"] == ["t00", "t01"]


def test_queue_failure_reports_and_leaves_state_clean(srv, monkeypatch):
    def boom(n, order):
        raise srv.Reject("queue.sh failed: no bun")
    monkeypatch.setattr(srv, "queue_pick", boom)
    assert srv.start_wave(2)["error"] == "queue.sh failed: no bun"
    assert srv.STATE["items"] == []
    assert srv.STATE["wave"] == 0


# ---------- actions ----------

def test_unknown_item_is_reported(srv):
    assert srv.act_approve("nope")["error"] == "unknown item"


def test_approve_and_withdraw(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW, updated=True)
    assert srv.act_approve("a") == {"ok": True}
    assert it["state"] == srv.APPROVED
    assert it["updated"] is False
    assert srv.act_unapprove("a") == {"ok": True}
    assert it["state"] == srv.NEEDS_REVIEW


def test_approve_needs_a_reviewable_item(srv):
    item(srv, "a", srv.QUEUED)
    assert srv.act_approve("a")["error"] == "nothing to approve"


def test_actions_refuse_while_a_turn_is_in_flight(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW)
    worker(srv, it, state="running")
    assert "busy" in srv.act_comment("a", "tighten the join")["error"]
    assert "busy" in srv.act_approve("a")["error"]
    assert "busy" in srv.act_revert("a")["error"]


def test_compact_path_is_rejected_while_item_is_busy(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW)
    worker(srv, it, state="running")
    assert "busy" in srv.act_compact("a", "refine")["error"]


def test_comment_needs_a_session(srv):
    item(srv, "a", srv.NEEDS_REVIEW, sessions={"create": None, "refine": None})
    assert srv.act_comment("a", "hi")["error"] == "no session yet"


def test_console_actions_are_not_worker_messages(srv):
    item(srv, "a", srv.NEEDS_REVIEW)
    assert "console action" in srv.act_comment("a", "commit")["error"]


def test_comment_launches_a_follow_up_turn(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, trigger=None, handoff=False:
                        sent.append((msg, phase, trigger)))
    it = item(srv, "a", srv.NEEDS_REVIEW)
    worker(srv, it)
    assert srv.act_comment("a", "cleanup please") == {"ok": True}
    assert sent == [("cleanup please", "refine", "cleanup")]
    assert it["state"] == srv.COMMENTED
    assert it["feed"][-1] == {"kind": "you", "text": "cleanup please", "sess": "refine"}


def test_fit_is_a_clean_trigger(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, trigger=None, handoff=False:
                        sent.append((msg, trigger)))
    item(srv, "a", srv.NEEDS_REVIEW)
    worker(srv, srv.find("a"))
    srv.act_comment("a", "fit the consts")
    srv.act_comment("a", "benefit from this")
    assert sent == [("fit the consts", "fit"), ("benefit from this", None)]


def test_comment_routes_to_the_chosen_session(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, trigger=None, handoff=False:
                        sent.append(phase))
    item(srv, "a", srv.NEEDS_REVIEW, sessions={"create": "cs", "refine": "rs"})
    worker(srv, srv.find("a"), phase="create")
    srv.act_comment("a", "why rank over area?", "create")
    assert sent == ["create"]


# ---------- handoff ----------

def test_handoff_is_a_worker_turn_that_reports(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, trigger=None, handoff=False:
                        sent.append((msg, phase, handoff)))
    it = item(srv, "a", srv.NEEDS_REVIEW, phase="create",
              sessions={"create": "cs", "refine": None})
    worker(srv, it, phase="create")
    assert srv.act_comment("a", "handoff") == {"ok": True}
    assert sent == [(srv.HANDOFF_BRIEF, "create", True)]
    assert it["state"] == srv.COMMENTED


def test_handoff_refused_outside_the_create_phase(srv):
    item(srv, "a", srv.NEEDS_REVIEW)
    assert srv.act_comment("a", "handoff")["error"] == "already handed off"


def test_create_landing_defers_the_handoff(srv, monkeypatch):
    landed = threading.Event()
    monkeypatch.setattr(srv, "complete_handoff", lambda it: landed.set())
    it = item(srv, "a", srv.RUNNING, phase="create", refined=False, rev=0,
              sessions={"create": "cs", "refine": None})
    worker(srv, it, phase="create", state="running", turn_seq=4)
    srv.finish_turn(it, {"result": "the report"}, None, time.time(), "create", True)
    assert landed.wait(1)
    assert it["handoff_report"] == "the report"
    assert "handoff_pending" not in it
    assert it["dirty"] is False


def test_complete_handoff_launches_refine_with_the_report(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, trigger=None, handoff=False:
                        sent.append((msg, phase)))
    it = item(srv, "a", srv.RUNNING, phase="create",
              sessions={"create": "cs", "refine": None},
              handoff_report="tried X, discarded Y")
    srv.complete_handoff(it)
    assert it["phase"] == "refine"
    assert it["state"] == srv.RUNNING
    (msg, phase), = sent
    assert phase == "refine"
    assert "tried X, discarded Y" in msg


def test_refine_first_landing_clears_dirty(srv):
    it = item(srv, "a", srv.RUNNING, dirty=True, refined=False)
    srv.finish_turn(it, {"result": "review"}, None, time.time(), "refine", False)
    assert it["dirty"] is False
    assert it["refined"] is True
    assert it["state"] == srv.NEEDS_REVIEW


def usage_result(cache_read, cache_write=200, input_tokens=10, window=200000):
    return {"result": "", "total_cost_usd": .125,
            "usage": {"cache_read_input_tokens": 999999, "iterations": [{
                "input_tokens": input_tokens, "output_tokens": 5,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_write,
                "cache_creation": {"ephemeral_1h_input_tokens": cache_write}}]},
            "modelUsage": {"claude-fable-5": {
                "inputTokens": input_tokens, "cacheReadInputTokens": cache_read,
                "cacheCreationInputTokens": cache_write, "costUSD": .125,
                "contextWindow": window, "canonicalModel": "claude-fable-5"}}}


def test_turn_whose_cache_read_drops_is_marked_anomalous(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW)
    srv.finish_turn(it, usage_result(28000), None, time.time(), "refine", False)
    srv.finish_turn(it, usage_result(21000, 7000), None, time.time(), "refine", False)
    assert "⚠ DROP 28,000→21,000" in it["feed"][-1]["text"]


def test_turn_whose_cache_read_grows_is_not_marked_anomalous(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW)
    srv.finish_turn(it, usage_result(21000), None, time.time(), "refine", False)
    srv.finish_turn(it, usage_result(22000), None, time.time(), "refine", False)
    assert "DROP" not in it["feed"][-1]["text"]
    assert "cache r 22,000 w 200 in 10" in it["feed"][-1]["text"]


def test_context_percentage_uses_last_iteration_and_reported_window(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW)
    ev = usage_result(26343, 437, 8, 200000)
    ev["usage"]["iterations"].insert(0, {
        "input_tokens": 1, "cache_read_input_tokens": 100,
        "cache_creation_input_tokens": 20})
    srv.finish_turn(it, ev, None, time.time(), "refine", False)
    assert it["context"]["refine"]["used"] == 26788
    assert it["context"]["refine"]["percent"] == pytest.approx(13.394)


def test_compact_uses_normal_user_message_path(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch", lambda it, msg, phase, **kw:
                        sent.append((msg, phase)))
    it = item(srv, "a", srv.NEEDS_REVIEW)
    worker(srv, it)
    assert srv.act_compact("a", "refine") == {"ok": True}
    assert sent == [("/compact", "refine")]
    assert it["feed"][-1]["text"] == "/compact"


def test_dead_refine_turn_falls_back_to_create(srv):
    it = item(srv, "a", srv.RUNNING, phase="refine",
              sessions={"create": "cs", "refine": None})
    srv.turn_died(it, "refine")
    assert it["phase"] == "create"
    assert it["state"] == srv.NEEDS_REVIEW


def test_messages_share_the_task_prefix(srv, monkeypatch, tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "a.json").write_text('{"train": []}\n')
    monkeypatch.setattr(srv, "TASKS", tasks)
    cm = srv.create_message("a")
    rm = srv.refine_message({"id": "a", "handoff_report": "the report"})
    prefix = srv.task_block("a")
    assert cm.startswith(prefix) and rm.startswith(prefix)
    assert "the report" in rm


def test_task_ask_carries_the_subagent_brief(srv):
    assert srv.task_ask({"subagent_type": "Explore", "description": "find lib uses",
                         "prompt": "Look in programs/."}) == \
        "**Explore · find lib uses**\n\nLook in programs/."
    assert srv.task_ask({"prompt": "Look in programs/."}) == "Look in programs/."


def test_append_carries_the_skill_body_and_the_docs(srv):
    (srv.DOCS / "style.md").write_text("# Style\n\nEvery word of it.\n")
    out = srv.build_append(1).read_text()
    assert out.startswith("# Solver session")
    assert "# docs/wf-solver/style.md\n\n# Style\n\nEvery word of it.\n" in out


def test_commit_subject_names_added_and_changed_solvers(srv):
    assert srv.commit_subject(["a", "b"], []) == "Add a, b"
    assert srv.commit_subject([], ["a"]) == "Update a"
    assert srv.commit_subject(["a"], ["b", "c"]) == "Add a; update b, c"


def test_seen_clears_the_updated_badge(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW, updated=True)
    srv.act_seen("a")
    assert it["updated"] is False


# ---------- revert ----------

def write_solver(srv, item_id, text):
    srv.solver_path(item_id).write_text(text)


def test_revert_restores_the_pre_turn_solver(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW, dirty=True)
    it["pre"] = {"hash": "", "solver": "// before\n", "proposals": "",
                 "dirty": False, "files": {}}
    write_solver(srv, "a", "// after\n")
    assert srv.act_revert("a") == {"ok": True}
    assert srv.solver_text("a") == "// before\n"
    assert it["dirty"] is False
    assert it["reverted"] == {"files": ["programs/solvers/a.dl"], "phase": "refine"}


def test_revert_needs_a_change_to_undo(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW)
    it["pre"] = {"hash": "", "solver": "// same\n", "proposals": "",
                 "dirty": False, "files": {}}
    write_solver(srv, "a", "// same\n")
    assert srv.act_revert("a")["error"] == "nothing to revert"


def test_revert_restores_proposals_this_turn_wrote(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW, prop_after="A\nB\n")
    it["pre"] = {"hash": "", "solver": "// before\n", "proposals": "A\n",
                 "dirty": False, "files": {}}
    (srv.DOCS / "proposals.md").write_text("A\nB\n")
    write_solver(srv, "a", "// after\n")
    srv.act_revert("a")
    assert srv.prop_text() == "A\n"
    assert "docs/wf-solver/proposals.md" in it["reverted"]["files"]


def test_revert_leaves_proposals_another_worker_touched(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW, prop_after="A\nB\n")
    it["pre"] = {"hash": "", "solver": "// before\n", "proposals": "A\n",
                 "dirty": False, "files": {}}
    (srv.DOCS / "proposals.md").write_text("A\nB\nC\n")  # a later turn appended
    write_solver(srv, "a", "// after\n")
    srv.act_revert("a")
    assert srv.prop_text() == "A\nB\nC\n"
    assert it["reverted"]["files"] == ["programs/solvers/a.dl"]


# ---------- loading ----------

def test_load_folds_legacy_snapshot_keys_into_pre(srv):
    legacy = {"seq": 3, "wave": 9, "items": [{
        "id": "a", "state": srv.NEEDS_REVIEW, "session": "s", "dirty": True,
        "updated": False, "rev": 2, "feed": [], "ver": 1,
        "hash_before": "abc", "snap": "// old\n", "snap_prop": "A\n",
        "dirty_before": False, "turn_files": {"docs/wf-solver/proposals.md": "A\n"},
    }]}
    srv.STATE_FILE.write_text(json.dumps(legacy))
    srv.load()
    it = srv.STATE["items"][0]
    assert it["pre"] == {"hash": "abc", "solver": "// old\n", "proposals": "A\n",
                         "dirty": False,
                         "files": {"docs/wf-solver/proposals.md": "A\n"}}
    assert not {"hash_before", "snap", "snap_prop", "dirty_before", "turn_files"} & set(it)


def test_load_folds_a_single_session_item(srv):
    legacy = {"seq": 1, "wave": 1, "items": [{
        "id": "a", "state": srv.NEEDS_REVIEW, "session": "s", "dirty": False,
        "updated": False, "rev": 2, "lastActive": 123, "title": "",
        "feed": [{"kind": "worker", "text": "x"}], "ver": 0,
        "pre": {"hash": "", "solver": "", "proposals": "", "dirty": False, "files": {}},
        "reverted": ["programs/solvers/a.dl"],
    }]}
    srv.STATE_FILE.write_text(json.dumps(legacy))
    srv.load()
    it = srv.STATE["items"][0]
    assert it["sessions"] == {"create": None, "refine": "s"}
    assert it["phase"] == "refine" and it["refined"] is True
    assert it["lastActive"] == {"create": None, "refine": 123}
    assert it["feed"][0]["sess"] == "refine"
    assert it["reverted"] == {"files": ["programs/solvers/a.dl"], "phase": "refine"}


def test_load_ends_turns_a_restart_cut_short(srv):
    state = {"seq": 1, "wave": 1, "items": [
        {"id": "a", "state": srv.RUNNING, "session": "s", "feed": [], "ver": 0},
        {"id": "b", "state": srv.COMMENTED, "session": None, "feed": [], "ver": 0},
    ]}
    srv.STATE_FILE.write_text(json.dumps(state))
    srv.load()
    a, b = srv.STATE["items"]
    assert a["state"] == srv.NEEDS_REVIEW  # had a session to resume
    assert b["state"] == srv.QUEUED        # never reported one
    assert b["feed"][-1]["text"] == "interrupted by console restart"


# ---------- the active flag the UI reads ----------

def test_active_tracks_worker_state_and_pending_handoff(srv):
    a = item(srv, "a", srv.RUNNING)
    b = item(srv, "b", srv.NEEDS_REVIEW)
    c = item(srv, "c", srv.NEEDS_REVIEW, handoff_pending=True)
    worker(srv, a, state="running")
    worker(srv, b, state="idle")
    assert {i["id"]: i["active"] for i in srv.light_items()} == {
        "a": True, "b": False, "c": True}


# ---------- persistent worker protocol ----------

def fake_process(item_id="proto", phase="refine"):
    return subprocess.Popen([sys.executable, str(FAKE_WORKER), item_id, phase],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            text=True, bufsize=1)


def send_event(proc, event):
    proc.stdin.write(json.dumps(event) + "\n")
    proc.stdin.flush()


def read_until(proc, predicate, timeout=4):
    events = []
    done = threading.Event()

    def read():
        while not done.is_set():
            line = proc.stdout.readline()
            if not line:
                return
            event = json.loads(line)
            events.append(event)
            if predicate(event, events):
                done.set()
                return
    thread = threading.Thread(target=read, daemon=True)
    thread.start()
    assert done.wait(timeout), events
    return events


def test_fake_worker_orders_multiple_turns_with_one_session():
    proc = fake_process()
    try:
        for text in ("first", "second"):
            send_event(proc, {"type": "user",
                              "message": {"role": "user", "content": text}})
        events = read_until(proc, lambda ev, seen:
                            sum(x.get("type") == "result" for x in seen) == 2)
        inits = [e for e in events if e.get("subtype") == "init"]
        results = [e for e in events if e.get("type") == "result"]
        assert len(inits) == len(results) == 2
        assert len({e["session_id"] for e in inits + results}) == 1
        assert [e["terminal_reason"] for e in results] == ["completed", "completed"]
        init_positions = [i for i, e in enumerate(events) if e.get("subtype") == "init"]
        result_positions = [i for i, e in enumerate(events) if e.get("type") == "result"]
        assert init_positions[0] < result_positions[0] < init_positions[1]
    finally:
        proc.terminate()
        proc.wait(timeout=2)


def test_fake_worker_interrupts_and_remains_usable():
    proc = fake_process()
    try:
        send_event(proc, {"type": "user",
                          "message": {"role": "user", "content": "first"}})
        first = read_until(proc, lambda ev, seen: ev.get("subtype") == "init")
        request_id = "stop-1"
        send_event(proc, {"type": "control_request", "request_id": request_id,
                          "request": {"subtype": "interrupt"}})
        stopped = read_until(proc, lambda ev, seen:
                             ev.get("terminal_reason") == "aborted_streaming")
        response = next(e for e in stopped if e.get("type") == "control_response")
        assert response["response"] == {"subtype": "success", "request_id": request_id,
                                        "response": {"still_queued": []}}
        send_event(proc, {"type": "user",
                          "message": {"role": "user", "content": "again"}})
        landed = read_until(proc, lambda ev, seen: ev.get("terminal_reason") == "completed")
        assert next(e["session_id"] for e in landed if e.get("subtype") == "init") == \
            first[0]["session_id"]
    finally:
        proc.terminate()
        proc.wait(timeout=2)


def test_fake_worker_ignores_malformed_lines_and_exits_on_eof():
    proc = fake_process()
    proc.stdin.write("not json\n")
    send_event(proc, {"type": "user", "message": {"role": "user", "content": "ok"}})
    read_until(proc, lambda ev, seen: ev.get("terminal_reason") == "completed")
    proc.stdin.close()
    assert proc.wait(timeout=2) == 0


def test_fake_worker_emits_compact_boundary():
    proc = fake_process()
    try:
        send_event(proc, {"type": "user",
                          "message": {"role": "user", "content": "/compact"}})
        events = read_until(proc, lambda ev, seen: ev.get("type") == "result")
        boundary = next(e for e in events if e.get("subtype") == "compact_boundary")
        assert boundary["compact_metadata"] == {
            "trigger": "manual", "pre_tokens": 28260, "post_tokens": 1914,
            "cumulative_dropped_tokens": 26346, "duration_ms": 1200}
        assert events[-1]["usage"]["iterations"] == []
    finally:
        proc.terminate()
        proc.wait(timeout=2)


def test_post_restart_session_is_not_sendable(srv):
    item(srv, "a", srv.NEEDS_REVIEW)
    assert "no longer live" in srv.act_comment("a", "continue")["error"]


def test_other_phase_cannot_run_while_item_has_a_turn(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW,
              sessions={"create": "cs", "refine": "rs"})
    worker(srv, it, phase="create", state="running")
    worker(srv, it, phase="refine", state="idle")
    assert "busy" in srv.act_comment("a", "check this", "refine")["error"]


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
    monkeypatch.setattr(srv, "complete_handoff", lambda it: called.append(it))
    old = item(srv, "a", srv.RUNNING, phase="create", handoff_pending=True)
    old_worker = worker(srv, old, phase="create", state="idle", turn_seq=3)
    srv.STATE["items"].remove(old)
    srv.PROCS.pop(("a", "create"))
    item(srv, "a", srv.QUEUED, phase="create", handoff_pending=True)
    srv.DEFERRED.put_nowait(("handoff", "a", "create", old_worker["turn_seq"]))
    srv.ensure_drain()
    deadline = time.time() + 1
    while srv.find("a").get("handoff_pending") and time.time() < deadline:
        time.sleep(.01)
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
    assert not acquired.wait(.05)
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


def test_quiesce_handoff_adopt_keeps_pid_and_sends(srv):
    it, old = idle_fake(srv, "handoff")
    pid = old["proc"].pid
    try:
        assert srv.quiesce_workers(.1)
        manifest = srv.worker_manifest()
        srv.save()
        os.environ[srv.WORKER_HANDOFF_ENV] = json.dumps(manifest)
        adopted_manifest = srv.read_worker_handoff()
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
            time.sleep(.01)
        assert adopted["state"] == "idle"
        assert it["state"] == srv.NEEDS_REVIEW
        assert any(m.get("kind") == "report" for m in it["feed"])
    finally:
        srv.shutdown_workers()


@pytest.mark.parametrize("action", ["drop", "shutdown"])
def test_adopted_worker_reaps_on_drop_and_shutdown(srv, action):
    it, old = idle_fake(srv, "reap-" + action)
    pid = old["proc"].pid
    manifest = srv.worker_manifest()
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
            time.sleep(.01)
    else:
        srv.shutdown_workers()
    with pytest.raises(OSError):
        os.kill(pid, 0)


def test_adoption_validation_failure_drops_only_bad_worker(srv, tmp_path):
    _, bad = idle_fake(srv, "bad")
    _, good = idle_fake(srv, "good")
    bad_pid, good_pid = bad["proc"].pid, good["proc"].pid
    manifest = srv.worker_manifest()
    regular = open(tmp_path / "not-a-pipe", "w")
    manifest["workers"][0]["stdout_fd"] = os.dup(regular.fileno())
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


def test_quiesce_rejects_new_turns(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW)
    worker(srv, it)
    assert srv.quiesce_workers(.1)
    assert srv.act_comment("a", "one more")["error"] == \
        "server reload in progress — wait for it to finish"


def test_stagger_launch_finishes_admitted_wave_during_reload(srv, monkeypatch):
    it = item(srv, "a", srv.QUEUED, phase="create")
    srv.RELOADING = True
    launched = []
    monkeypatch.setattr(srv, "STAGGER_TIMEOUT", 0)
    monkeypatch.setattr(srv, "launch", lambda *args, **kwargs: launched.append(kwargs))
    srv._test_stagger_launch([it["id"]])
    assert it["state"] == srv.RUNNING
    assert launched == [{"handoff": True, "admitted": True}]


def test_concurrent_stagger_launches_launch_each_item_once(srv, monkeypatch):
    items = [item(srv, name, srv.QUEUED, phase="create")
             for name in ("a", "b", "c")]
    launched = []
    monkeypatch.setattr(srv, "STAGGER_TIMEOUT", .05)
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


def test_wave_committed_just_before_reload_still_launches(srv, monkeypatch):
    it = item(srv, "pending", srv.QUEUED, phase="create")
    launched = threading.Event()
    monkeypatch.setattr(srv, "launch", lambda *args, **kwargs: launched.set())
    monkeypatch.setattr(srv, "STAGGER_TIMEOUT", 0)
    monkeypatch.setattr(srv, "stagger_launch", srv._test_stagger_launch)
    monkeypatch.setattr(srv.os, "execv",
                        lambda exe, argv: (_ for _ in ()).throw(OSError("no exec")))
    srv.reload_server(timeout=0)
    assert launched.wait(1)
    assert it["state"] == srv.RUNNING
    assert not srv.RELOADING


def test_execv_failure_restores_handoff_and_server(srv, monkeypatch):
    it, worker = idle_fake(srv, "exec-failure")
    fds = [worker["proc"].stdin.fileno(), worker["proc"].stdout.fileno()]
    monkeypatch.setattr(srv.os, "execv",
                        lambda exe, argv: (_ for _ in ()).throw(OSError("no exec")))
    try:
        srv.reload_server(timeout=.1)
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
        srv.reload_server(timeout=.1)
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
    manifest = srv.worker_manifest()
    regular = open(tmp_path / "not-a-pipe", "w")
    manifest["workers"][0]["stdout_fd"] = os.dup(regular.fileno())
    srv.PROCS.clear()
    try:
        srv.adopt_workers(manifest)
        assert it["sessions"]["refine"] is None
        assert "session lost on reload" in it["feed"][-1]["text"]
        assert lost_session in it["feed"][-1]["text"]
    finally:
        regular.close()


def test_reload_timeout_exec_failure_keeps_workers_operational(srv, monkeypatch):
    it = item(srv, "a", srv.COMMENTED)
    worker(srv, it, state="running")
    calls = []
    monkeypatch.setattr(srv, "shutdown_workers", lambda: calls.append("shutdown"))
    def fail_exec(exe, argv):
        calls.append("execv")
        raise OSError("no exec")
    monkeypatch.setattr(srv.os, "execv", fail_exec)
    srv.reload_server(timeout=0)
    assert calls == ["execv"]
    assert not srv.RELOADING
    assert (it["id"], "refine") in srv.PROCS
    assert "server still running" in it["feed"][-1]["text"]
