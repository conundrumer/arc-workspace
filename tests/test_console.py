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
    # A worker thread outliving its test closes pipes on its way out, and the
    # next test's subprocess is handed those same descriptor numbers. Join them
    # before the test ends so the numbers stay claimed.
    threads = []
    start = s.start_worker_threads

    def start_and_track(worker):
        start(worker)
        threads.extend([worker["writer"], worker["reader"]])

    monkeypatch.setattr(s, "start_worker_threads", start_and_track)
    yield s
    for worker in list(s.PROCS.values()):
        proc = worker.get("proc")           # some tests stand in a stub here
        if callable(getattr(proc, "poll", None)) and proc.poll() is None:
            proc.terminate()
    for thread in threads:
        thread.join(timeout=3)


def item(s, item_id, state, **kw):
    """Append an item the way start_wave does, then override for the test."""
    it = {"id": item_id, "est": 10, "wave": 1, "state": state,
          "chain": s.two_phase_chain(), "auto_advance": False,
          "sessions": {"create": None, "refine": "sess-" + item_id},
          "phase": "refine", "landed": ["refine"],
          "lastActive": {"create": None, "refine": None},
          "dirty": False, "updated": False, "rev": 1, "title": "",
          "feed": [], "append": "", "ver": 0, "reports": {}}
    it.update(kw)
    s.STATE["items"].append(it)
    return it


def worker(s, it, phase="refine", state="idle", turn_seq=1):
    w = {"item_id": it["id"], "phase": phase, "state": state,
         "turn_seq": turn_seq, "outbound": queue.Queue(), "seen": set(),
         "session_seen": True, "handoff": False, "got_result": False,
         "started": None, "trigger": None, "think_run": 0, "reqs": {}}
    s.PROCS[(it["id"], phase)] = w
    return w


# ---------- waves ----------

def test_wave_queues_k_items(srv):
    res = srv.start_wave(2)
    assert res["ids"] == ["t00", "t01"]
    assert srv.STATE["wave"] == 1
    assert [it["state"] for it in srv.STATE["items"]] == [srv.QUEUED, srv.QUEUED]


def test_wave_carries_auto_stop(srv):
    res = srv.start_wave(1, auto_stop="finalize")
    assert res["ids"] == ["t00"]
    it = srv.STATE["items"][0]
    assert it["auto_advance"] is True
    assert it["auto_stop"] == "finalize"
    assert srv.auto_advances(it, "create")
    assert not srv.auto_advances(it, "refine")


def test_wave_rejects_unknown_auto_stop(srv):
    res = srv.start_wave(1, auto_stop="create")
    assert "error" in res
    assert srv.STATE["items"] == []


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


def test_cleanup_counts_anywhere_in_the_message(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, trigger=None, handoff=False:
                        sent.append((msg, trigger)))
    item(srv, "a", srv.NEEDS_REVIEW)
    worker(srv, srv.find("a"))
    srv.act_comment("a", "ok that reads fine. cleanup")
    srv.act_comment("a", "drop the alias, then cleanup, then report")
    srv.act_comment("a", "the cleanups list is stale")
    assert sent == [("ok that reads fine. cleanup", "cleanup"),
                    ("drop the alias, then cleanup, then report", "cleanup"),
                    ("the cleanups list is stale", None)]


def test_a_message_to_a_running_session_steers_the_turn(srv):
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    w["started"] = 100.0
    assert srv.act_comment("a", "drop the alias") == {"ok": True}
    assert w["outbound"].get_nowait() == {
        "type": "user", "message": {"role": "user", "content": "drop the alias"}}
    assert it["feed"][-1] == {"kind": "steer", "text": "drop the alias",
                              "sess": "refine"}
    assert w["turn_seq"] == 1        # the running turn keeps its count
    assert w["started"] == 100.0     # and its clock
    assert it["state"] == srv.RUNNING


def test_a_steer_carries_a_clean_cadence_into_the_turn(srv):
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    srv.act_comment("a", "then cleanup")
    assert w["trigger"] == "cleanup"


def test_a_steer_leaves_the_turns_own_cadence_alone(srv):
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    w["trigger"] = "callout"
    srv.act_comment("a", "then cleanup")
    assert w["trigger"] == "callout"


def test_a_slash_command_waits_for_the_turn_to_land(srv):
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    assert "busy" in srv.act_comment("a", "/compact")["error"]
    assert w["outbound"].empty()


# ---------- permission requests ----------

def perm_request(srv, path, tool="Edit", subtype="can_use_tool"):
    return {"type": "control_request", "request_id": "r1",
            "request": {"subtype": subtype, "tool_name": tool,
                        "input": {"file_path": str(path), "old_string": "a",
                                  "new_string": "b"},
                        "decision_reason": f"{path} is a sensitive file.",
                        "tool_use_id": "tu1"}}


def test_the_session_skill_is_the_worker_s_to_edit(srv):
    req = perm_request(srv, srv.SKILL_MD)["request"]
    assert srv.permission_decision(req) == {
        "behavior": "allow", "updatedInput": req["input"]}


def test_every_other_request_keeps_the_cli_refusal(srv):
    for path, tool in ((srv.ROOT / ".claude" / "settings.json", "Edit"),
                       (srv.SKILL_MD, "Bash"),
                       ("/tmp/note.txt", "Write")):
        req = perm_request(srv, path, tool=tool)["request"]
        decision = srv.permission_decision(req)
        assert decision["behavior"] == "deny"
        assert decision["message"] == req["decision_reason"]


def test_a_permission_request_is_answered_on_the_stream(srv):
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    srv.handle_event(w, perm_request(srv, srv.SKILL_MD), None)
    assert w["outbound"].get_nowait() == {
        "type": "control_response",
        "response": {"subtype": "success", "request_id": "r1",
                     "response": {"behavior": "allow",
                                  "updatedInput": {"file_path": str(srv.SKILL_MD),
                                                   "old_string": "a",
                                                   "new_string": "b"},
                                  "toolUseID": "tu1"}}}
    assert it["feed"][-1]["text"] == \
        "permission allowed: Edit .claude/skills/session/SKILL.md"


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
    srv.handle_event(w, perm_request(srv, srv.SKILL_MD, subtype="elicitation"), None)
    reply = w["outbound"].get_nowait()
    assert reply["response"]["subtype"] == "error"
    assert reply["response"]["request_id"] == "r1"


def test_a_broken_policy_refuses_rather_than_hangs(srv, monkeypatch):
    def boom(req):
        raise RuntimeError("policy bug")
    monkeypatch.setattr(srv, "permission_decision", boom)
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    srv.handle_event(w, perm_request(srv, srv.SKILL_MD), None)
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


def test_handoff_refused_on_the_final_stage(srv):
    item(srv, "a", srv.NEEDS_REVIEW)
    assert srv.act_comment("a", "handoff")["error"] == \
        "final stage — nothing to hand off to"


def test_create_landing_defers_the_handoff(srv, monkeypatch):
    asked = threading.Event()
    landed = threading.Event()
    monkeypatch.setattr(srv, "advance_stage", lambda it: landed.set())
    sent = []

    def fake_launch(it, msg, phase, trigger=None, **kw):
        sent.append((msg, phase, trigger))
        asked.set()
    monkeypatch.setattr(srv, "launch", fake_launch)
    it = item(srv, "a", srv.RUNNING, phase="create", landed=[], rev=0,
              auto_advance=True, sessions={"create": "cs", "refine": None})
    worker(srv, it, phase="create", state="running", turn_seq=4)
    srv.finish_turn(it, {"result": "the report"}, None, time.time(), "create", True)
    assert asked.wait(1)   # the callout ask goes out before any advance
    assert sent == [(srv.callout_brief(), "create", "callout")]
    assert not landed.is_set()
    srv.finish_turn(it, {"result": "## Callouts\n\n1. [P2] a call"}, None,
                    time.time(), "create", False)
    assert landed.wait(1)
    assert it["reports"]["create"] == "the report\n\n## Callouts\n\n1. [P2] a call"
    assert "handoff_pending" not in it
    assert "callout_wait" not in it
    assert it["dirty"] is False


def test_advance_launches_the_next_stage_with_the_report(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, trigger=None, handoff=False:
                        sent.append((msg, phase, handoff)))
    it = item(srv, "a", srv.RUNNING, phase="create",
              sessions={"create": "cs", "refine": None},
              reports={"create": "tried X, discarded Y"})
    srv.advance_stage(it)
    assert it["phase"] == "refine"
    assert it["state"] == srv.RUNNING
    (msg, phase, handoff), = sent
    assert phase == "refine"
    assert handoff is False  # the final stage has nobody to hand off to
    assert "tried X, discarded Y" in msg


def create_item(srv, item_id="a", **kw):
    """An item mid-create, the way a wave admits one."""
    return item(srv, item_id, srv.RUNNING, phase="create", landed=[], rev=0,
                sessions={"create": "cs", "refine": None}, **kw)


def land_report(srv, it, text="tried X, discarded Y"):
    srv.finish_turn(it, {"result": text}, None, time.time(), "create", True)


def test_a_landed_report_is_written_beside_the_state(srv):
    it = create_item(srv)
    land_report(srv, it)
    assert srv.report_path("a", "create").read_text() == "tried X, discarded Y"
    land_report(srv, it, "a second pass")
    assert srv.report_path("a", "create").read_text() == "a second pass"


def test_the_report_file_stands_in_when_state_has_none(srv):
    srv.save_report("a", "create", "from the file")
    it = item(srv, "a", srv.NEEDS_REVIEW, phase="create",
              sessions={"create": "cs", "refine": None})
    assert srv.report_of(it, "create") == "from the file"
    assert "the file" in srv.advance_message(it, "create", False)
    srv.seed_report(it)
    assert it["reports"]["create"] == "from the file"


def test_a_restart_seeds_the_report_from_the_file(srv):
    srv.save_report("a", "create", "what create found")
    srv.STATE_FILE.write_text(json.dumps({"seq": 1, "wave": 1, "items": [
        {"id": "a", "state": srv.NEEDS_REVIEW, "phase": "create", "session": None,
         "feed": [], "ver": 0}]}))
    srv.load()
    assert srv.STATE["items"][0]["reports"]["create"] == "what create found"


def test_a_readmitted_task_keeps_the_earlier_report(srv):
    srv.save_report("t00", "create", "the committed pass")
    srv.start_wave(1)
    assert srv.find("t00")["reports"]["create"] == "the committed pass"


# ---------- task-local comps ----------

def test_comps_beyond_the_stock_two_are_flagged_by_proposal(srv):
    write_solver(srv, "a", ".comp Consts {\n}\n.comp CornerDist {\n}\n"
                           ".comp Wallpaper<Key> {\n}\n.comp Fit {\n}\n")
    (srv.DOCS / "proposals.md").write_text("### CornerDist\n\nstaged here.\n")
    it = item(srv, "a", srv.RUNNING)
    srv.finish_turn(it, {"result": ""}, None, time.time(), "refine", False)
    assert it["comps"] == ["CornerDist", "Wallpaper"]
    assert it["comps_unproposed"] == ["Wallpaper"]
    light = srv.light_items()[0]
    assert light["comps"] == ["CornerDist", "Wallpaper"]
    assert light["comps_unproposed"] == ["Wallpaper"]


def test_a_stock_solver_flags_no_comps(srv):
    write_solver(srv, "a", ".comp Consts {\n}\n.comp Parse<Key> {\n}\n"
                           ".init c = Consts\n.comp Fit {\n}\n")
    it = item(srv, "a", srv.RUNNING)
    srv.finish_turn(it, {"result": ""}, None, time.time(), "refine", False)
    assert it["comps"] == []


# ---------- opt-in auto-advance ----------

def test_a_wave_carries_its_chain_choice(srv):
    srv.start_wave(1)
    plain = srv.find("t00")
    assert plain["auto_advance"] is False
    assert plain["chain"] == srv.default_chain()
    assert [st["name"] for st in plain["chain"]] == ["create", "refine", "finalize"]
    assert plain["sessions"] == {"create": None, "refine": None, "finalize": None}
    srv.LAST_WAVE_AT = 0.0
    srv.start_wave(1, auto_advance=True, chain=[
        {"name": "create", "backend": "codex", "model": "gpt-5.1-codex",
         "effort": "high"},
        {"name": "refine", "model": "claude-mythos-1"}])
    eager = srv.find("t01")
    assert eager["auto_advance"] is True
    assert eager["chain"] == [
        {"name": "create", "backend": "codex", "model": "gpt-5.1-codex",
         "effort": "high"},
        {"name": "refine", "backend": "claude", "model": "claude-mythos-1"}]


def test_a_wave_refuses_a_malformed_chain(srv):
    assert "non-empty" in srv.start_wave(1, chain=[])["error"]
    assert "unknown backend" in srv.start_wave(1, chain=[
        {"name": "create", "backend": "gemini"}])["error"]
    assert "duplicate" in srv.start_wave(1, chain=[
        {"name": "create"}, {"name": "create"}])["error"]
    assert "bad stage name" in srv.start_wave(1, chain=[
        {"name": "../escape"}])["error"]
    assert srv.STATE["items"] == []


def test_a_three_stage_wave_keys_its_state_by_stage(srv):
    chain = [{"name": "create", "backend": "codex"}, {"name": "refine"},
             {"name": "finalize"}]
    assert srv.start_wave(1, chain=chain)["ids"] == ["t00"]
    it = srv.find("t00")
    assert srv.stage_names(it) == ["create", "refine", "finalize"]
    assert it["sessions"] == {"create": None, "refine": None, "finalize": None}
    assert it["lastActive"] == {"create": None, "refine": None, "finalize": None}
    assert it["phase"] == "create"
    assert srv.light_items()[0]["chain"] == it["chain"]


def test_without_auto_advance_a_report_lands_for_review(srv, monkeypatch):
    launched = []
    monkeypatch.setattr(srv, "launch", lambda *a, **kw: launched.append(a))
    it = create_item(srv)
    land_report(srv, it)
    assert it["state"] == srv.NEEDS_REVIEW
    assert it["phase"] == "create"
    assert it["updated"] is True
    assert not it.get("handoff_pending")
    assert launched == []
    assert it["reports"]["create"] == "tried X, discarded Y"


def test_advance_launches_from_the_stored_report(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch", lambda it, msg, phase, **kw:
                        sent.append((msg, phase)))
    srv.save_report("a", "create", "the committed pass")
    it = item(srv, "a", srv.NEEDS_REVIEW, phase="create", landed=[],
              sessions={"create": "cs", "refine": None})
    assert srv.act_advance("a") == {"ok": True}
    assert it["phase"] == "refine"
    assert it["state"] == srv.RUNNING
    (msg, phase), = sent
    assert phase == "refine"
    assert "the committed pass" in msg


def test_advance_needs_an_idle_reported_non_final_stage(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW, phase="create",
              sessions={"create": "cs", "refine": None})
    assert "no handoff report" in srv.act_advance("a")["error"]
    it["reports"] = {"create": "a report"}
    it["state"] = srv.QUEUED
    assert srv.act_advance("a")["error"] == "wait for the turn to land"
    it["state"] = srv.NEEDS_REVIEW
    worker(srv, it, phase="create", state="running")
    assert "busy" in srv.act_advance("a")["error"]
    srv.PROCS.clear()
    it["phase"] = "refine"
    assert srv.act_advance("a")["error"] == "final stage — nothing to advance to"


def test_a_middle_stage_reports_and_hands_on(srv, monkeypatch):
    """The advance action walks a three-stage chain end to end."""
    sent = []
    monkeypatch.setattr(srv, "launch", lambda it, msg, phase, **kw:
                        sent.append((msg, phase, kw.get("handoff", False))))
    it = item(srv, "a", srv.NEEDS_REVIEW, phase="create", landed=[],
              chain=[{"name": "create", "backend": "codex", "model": "gpt-5.1-codex"},
                     {"name": "refine", "backend": "claude", "model": "claude-opus-5"},
                     {"name": "finalize", "backend": "claude", "model": "claude-fable-5"}],
              sessions={"create": "cs", "refine": None, "finalize": None},
              lastActive={"create": None, "refine": None, "finalize": None},
              reports={"create": "what create found"})
    assert srv.act_advance("a") == {"ok": True}
    msg, phase, handoff = sent[-1]
    assert (phase, handoff) == ("refine", True)  # a middle stage owes a report
    assert "what create found" in msg
    assert srv.HANDOFF_TAIL in msg
    # the middle stage lands its own report and stops for review
    it["sessions"]["refine"] = "rs"
    srv.finish_turn(it, {"result": "what refine changed"}, None, time.time(),
                    "refine", True)
    assert it["state"] == srv.NEEDS_REVIEW
    assert it["phase"] == "refine"
    assert srv.report_path("a", "refine").read_text() == "what refine changed"
    assert srv.act_advance("a") == {"ok": True}
    msg, phase, handoff = sent[-1]
    assert (phase, handoff) == ("finalize", False)
    assert "what refine changed" in msg
    assert srv.HANDOFF_TAIL not in msg
    assert srv.act_advance("a")["error"] == "final stage — nothing to advance to"


def test_auto_advance_runs_the_chain_without_the_user(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch", lambda it, msg, phase, **kw:
                        sent.append((phase, kw.get("handoff", False))))
    monkeypatch.setattr(srv, "ensure_drain", lambda: None)  # drive the queue here
    it = item(srv, "a", srv.RUNNING, phase="create", landed=[], auto_advance=True,
              chain=[{"name": "create", "backend": "claude", "model": "m1"},
                     {"name": "refine", "backend": "claude", "model": "m2"},
                     {"name": "finalize", "backend": "claude", "model": "m3"}],
              sessions={"create": "cs", "refine": None, "finalize": None},
              lastActive={"create": None, "refine": None, "finalize": None})
    for phase, session in (("create", "rs"), ("refine", "r2s")):
        worker(srv, it, phase=phase, state="running", turn_seq=1)
        srv.finish_turn(it, {"result": f"report from {phase}"}, None, time.time(),
                        phase, True)
        assert it["callout_wait"] == phase
        assert srv.DEFERRED.get_nowait() == ("callout", "a", phase, 1)
        srv.finish_turn(it, {"result": "## Callouts\n\nnone"}, None,
                        time.time(), phase, False)
        assert it["handoff_pending"] is True
        assert srv.DEFERRED.get_nowait() == ("handoff", "a", phase, 1)
        it.pop("handoff_pending")
        srv.advance_stage(it)
        it["sessions"][it["phase"]] = session
    assert [p for p, _ in sent] == ["refine", "finalize"]
    assert it["phase"] == "finalize"
    assert it["state"] == srv.RUNNING
    assert sorted(it["reports"]) == ["create", "refine"]


def test_a_dead_later_stage_falls_back_to_the_stage_before_it(srv):
    it = item(srv, "a", srv.RUNNING, phase="finalize",
              chain=[{"name": "create"}, {"name": "refine"}, {"name": "finalize"}],
              sessions={"create": "cs", "refine": "rs", "finalize": None})
    srv.turn_died(it, "finalize")
    assert it["phase"] == "refine"
    assert it["state"] == srv.NEEDS_REVIEW


def test_a_create_bail_without_auto_advance_lands_for_review(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch", lambda it, msg, phase, **kw:
                        sent.append((msg, phase, kw.get("handoff"))))
    it = create_item(srv)
    it["runaway"] = {"create": 2}
    srv.escalate_turn(it, "create", "bail", True)
    assert sent == [(srv.BAIL_BRIEF, "create", True)]
    assert "refine session" not in srv.BAIL_BRIEF
    land_report(srv, it, "where I got stuck")
    assert it["state"] == srv.NEEDS_REVIEW
    assert it["phase"] == "create"


def test_worker_cmd_uses_each_stages_model(srv, tmp_path, monkeypatch):
    monkeypatch.setattr(srv, "FAKE", False)
    append = tmp_path / "append.md"
    append.write_text("brief")
    it = item(srv, "a", srv.NEEDS_REVIEW, append=str(append),
              chain=[{"name": "create", "backend": "claude", "model": "claude-opus-5"},
                     {"name": "refine", "backend": "claude", "model": "claude-mythos-1"}],
              sessions={"create": "cs", "refine": "rs"})
    cmd = srv.worker_cmd(it, "refine")
    assert cmd[cmd.index("--model") + 1] == "claude-mythos-1"
    create = srv.worker_cmd(it, "create")
    assert create[create.index("--model") + 1] == "claude-opus-5"


def codex_item(srv, item_id, state, **kw):
    """An item whose first stage runs on codex."""
    kw.setdefault("sessions", {"create": None, "refine": None})
    return item(srv, item_id, state, phase="create", landed=[],
                chain=[{"name": "create", "backend": "codex",
                        "model": "gpt-5.1-codex", "effort": "high"},
                       {"name": "refine", "backend": "claude",
                        "model": "claude-fable-5"}],
                lastActive={"create": None, "refine": None}, **kw)


def test_worker_cmd_for_a_codex_stage_runs_the_adapter(srv, tmp_path, monkeypatch):
    monkeypatch.setattr(srv, "FAKE", False)
    append = tmp_path / "append.md"
    append.write_text("brief")
    it = codex_item(srv, "a", srv.NEEDS_REVIEW, append=str(append))
    cmd = srv.worker_cmd(it, "create")
    assert cmd[:2] == [sys.executable, str(srv.HERE / "codex_worker.py")]
    assert cmd[cmd.index("--append") + 1] == str(append)
    assert cmd[cmd.index("--add-dir") + 1] == str(srv.REF_DIR)
    assert cmd[cmd.index("--model") + 1] == "gpt-5.1-codex"
    assert cmd[cmd.index("--effort") + 1] == "high"
    assert "--resume" not in cmd
    assert "--append-system-prompt" not in cmd
    it["sessions"]["create"] = "thread-1"
    assert srv.worker_cmd(it, "create")[-2:] == ["--resume", "thread-1"]
    # the claude stage of the same item still runs the CLI
    assert srv.worker_cmd(it, "refine")[0] == srv.CLAUDE


def test_a_codex_session_leaves_the_cap_watch_with_nothing_to_read(
        srv, monkeypatch, tmp_path):
    """A codex thread is not a claude session, so the CLI wrote no transcript
    and the runaway machinery finds nothing to act on."""
    home = tmp_path / "projects"
    home.mkdir()
    monkeypatch.setattr(srv.quota, "PROJECTS", home)
    it = codex_item(srv, "a", srv.RUNNING, sessions={"create": "codex-thread-1",
                                                     "refine": None})
    w = worker(srv, it, phase="create", state="running")
    assert srv.transcript_of("codex-thread-1") is None
    assert srv.tail_turn(w, "codex-thread-1") is None
    srv.check_caps()
    assert "escalate" not in w
    assert it["feed"] == []


def test_first_landing_of_a_stage_clears_dirty(srv):
    it = item(srv, "a", srv.RUNNING, dirty=True, landed=[])
    srv.finish_turn(it, {"result": "review"}, None, time.time(), "refine", False)
    assert it["dirty"] is False
    assert it["landed"] == ["refine"]
    assert it["state"] == srv.NEEDS_REVIEW


def usage_result(cache_read, cache_write=200, input_tokens=10, window=200000,
                 total=.125):
    return {"result": "", "total_cost_usd": total,
            "usage": {"cache_read_input_tokens": 999999, "iterations": [{
                "input_tokens": input_tokens, "output_tokens": 5,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_write,
                "cache_creation": {"ephemeral_1h_input_tokens": cache_write}}]},
            "modelUsage": {"claude-fable-5": {
                "inputTokens": input_tokens, "cacheReadInputTokens": cache_read,
                "cacheCreationInputTokens": cache_write, "costUSD": total,
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
    assert "cache r 22,000 w 200" in it["feed"][-1]["text"]


def test_turn_note_reports_the_turn_share_not_the_session_total(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW)
    srv.finish_turn(it, usage_result(21000, total=4.44), None, time.time(),
                    "refine", False)
    srv.finish_turn(it, usage_result(22000, total=8.88), None, time.time(),
                    "refine", False)
    assert "5h 1.00%" in it["feed"][-1]["text"]
    assert "$" not in it["feed"][-1]["text"]


def test_cost_baseline_resets_when_the_running_total_restarts(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW)
    srv.finish_turn(it, usage_result(21000, total=8.88), None, time.time(),
                    "refine", False)
    srv.finish_turn(it, usage_result(22000, total=4.44), None, time.time(),
                    "refine", False)
    assert "5h 1.00%" in it["feed"][-1]["text"]


def test_cache_figures_sum_the_turn_requests(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW)
    ev = usage_result(26343, 437)
    ev["usage"]["iterations"].insert(0, {
        "input_tokens": 1, "cache_read_input_tokens": 100,
        "cache_creation_input_tokens": 20000})
    srv.finish_turn(it, ev, None, time.time(), "refine", False)
    assert "cache r 26,443 w 20,437" in it["feed"][-1]["text"]


def test_context_percentage_uses_last_iteration_and_reported_window(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW)
    ev = usage_result(26343, 437, 8, 200000)
    ev["usage"]["iterations"].insert(0, {
        "input_tokens": 1, "cache_read_input_tokens": 100,
        "cache_creation_input_tokens": 20})
    srv.finish_turn(it, ev, None, time.time(), "refine", False)
    assert it["context"]["refine"]["used"] == 26788
    assert it["context"]["refine"]["percent"] == pytest.approx(13.394)


def test_compact_estimate_prices_the_context_as_a_cache_read(srv, monkeypatch):
    monkeypatch.setattr(srv, "USAGE", [{"label": "5h", "pct": 40},
                                       {"label": "wk", "pct": 10}])
    it = item(srv, "a", srv.NEEDS_REVIEW)
    srv.finish_turn(it, usage_result(100000, 0, 0), None, time.time(),
                    "refine", False)
    # fable-5 reads at a tenth of $10/M, and the summary bills at $50/M
    dollars = 100000 * 10 * srv.CACHE_READ / 1e6 + srv.COMPACT_SUMMARY * 50 / 1e6
    assert it["context"]["refine"]["compactPct"] == pytest.approx(
        dollars / srv.QUOTA_RATE[it["context"]["refine"]["limiting"]])


def test_a_dated_model_id_still_prices(srv, monkeypatch):
    monkeypatch.setattr(srv, "USAGE", [{"label": "fbl", "pct": 40}])
    it = item(srv, "a", srv.NEEDS_REVIEW)
    ev = usage_result(1000)
    ev["modelUsage"]["claude-fable-5"]["canonicalModel"] = "claude-fable-5-20260214"
    srv.finish_turn(it, ev, None, time.time(), "refine", False)
    assert it["context"]["refine"]["compactPct"] is not None


def test_a_slash_command_reaches_the_worker_as_the_first_bytes(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW)
    w = worker(srv, it)
    it["seen_hash"] = {"refine": "hash-from-an-earlier-turn"}
    it["reverted"] = {"phase": "refine", "files": ["programs/solvers/a.dl"]}
    srv.act_compact("a", "refine")
    assert w["outbound"].get_nowait()["message"]["content"] == "/compact"
    # both notices wait for a turn that can carry them
    assert it["reverted"]["phase"] == "refine"
    srv.finish_turn(it, usage_result(1000), None, time.time(), "refine", False)
    assert it["seen_hash"]["refine"] == "hash-from-an-earlier-turn"


def test_a_slash_turn_leaves_the_items_state_alone(srv):
    it = item(srv, "a", srv.APPROVED)
    worker(srv, it)
    srv.act_compact("a", "refine")
    assert it["state"] == srv.APPROVED
    srv.finish_turn(it, usage_result(1000), None, time.time(), "refine", False)
    assert it["state"] == srv.APPROVED


def test_compact_boundary_reprices_the_button(srv, monkeypatch):
    monkeypatch.setattr(srv, "USAGE", [{"label": "5h", "pct": 40}])
    it = item(srv, "a", srv.NEEDS_REVIEW)
    srv.finish_turn(it, usage_result(120000), None, time.time(), "refine", False)
    before = dict(it["context"]["refine"])
    w = worker(srv, it, state="running")
    srv.handle_event(w, {"type": "system", "subtype": "compact_boundary",
                         "compact_metadata": {"pre_tokens": before["used"],
                                              "post_tokens": 9000,
                                              "cumulative_dropped_tokens": 111000}}, None)
    after = it["context"]["refine"]
    assert after["used"] == 9000
    assert after["percent"] == pytest.approx(9000 / before["window"] * 100)
    assert after["compactPct"] == pytest.approx(
        srv.compact_pct(9000, before["model"], before["limiting"]))
    assert after["compactPct"] < before["compactPct"]


def test_model_usage_with_null_counters_still_lands(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW)
    ev = usage_result(21000)
    ev["modelUsage"]["claude-opus-5"] = {
        "inputTokens": None, "cacheReadInputTokens": None,
        "cacheCreationInputTokens": None, "costUSD": 0,
        "contextWindow": 200000, "canonicalModel": "claude-opus-5"}
    srv.finish_turn(it, ev, None, time.time(), "refine", False)
    assert "cache r 21,000" in it["feed"][-1]["text"]


def assist_usage(mid, read, write, sub=False):
    ev = {"type": "assistant", "message": {"id": mid,
          "usage": {"input_tokens": 10, "cache_read_input_tokens": read,
                    "cache_creation_input_tokens": write},
          "content": [{"type": "tool_use", "name": "Bash",
                       "input": {"command": "true"}, "id": "tu-" + mid}]}}
    if sub:
        ev["parent_tool_use_id"] = "parent"
    return ev


def test_turn_figures_come_from_the_stream_not_the_result_event(srv):
    it = item(srv, "a", srv.COMMENTED)
    w = worker(srv, it, state="running")
    w["started"] = time.time()
    srv.handle_event(w, assist_usage("m1", 0, 30000), None)
    srv.handle_event(w, assist_usage("m1", 0, 30000), None)  # block repeat
    srv.handle_event(w, assist_usage("m2", 30000, 500), None)
    srv.handle_event(w, assist_usage("m3", 999999, 999999, sub=True), None)
    ev = dict(usage_result(30500, 500), type="result",
              terminal_reason="completed")
    srv.handle_event(w, ev, None)
    assert "cache r 30,000 w 30,500" in it["feed"][-1]["text"]
    assert w["reqs"] == {}


def test_cold_resume_first_request_is_a_drop(srv):
    it = item(srv, "a", srv.COMMENTED, cache_read={"refine": 211844})
    w = worker(srv, it, state="running")
    w["started"] = time.time()
    srv.handle_event(w, assist_usage("m1", 0, 214044), None)
    srv.handle_event(w, assist_usage("m2", 214044, 145), None)
    ev = dict(usage_result(214189, 145), type="result",
              terminal_reason="completed")
    srv.handle_event(w, ev, None)
    assert "⚠ DROP 211,844→0" in it["feed"][-1]["text"]


def test_respawn_keeps_the_cache_baseline_for_a_resumed_session(srv, monkeypatch):
    import types
    monkeypatch.setattr(srv, "FAKE", True)
    monkeypatch.setattr(srv, "start_worker_threads", lambda w: None)
    monkeypatch.setattr(srv.subprocess, "Popen",
                        lambda *a, **k: types.SimpleNamespace())
    it = item(srv, "a", srv.NEEDS_REVIEW,
              cache_read={"refine": 1000, "create": 500})
    srv.spawn_worker(it, "refine")  # sessions["refine"] is recorded
    assert it["cache_read"]["refine"] == 1000
    srv.spawn_worker(it, "create")  # no create session to resume
    assert "create" not in it["cache_read"]


def test_result_crash_still_frees_the_worker(srv, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("landing bug")

    monkeypatch.setattr(srv, "finish_turn", boom)
    it = item(srv, "a", srv.COMMENTED)
    w = worker(srv, it, state="running")
    w["started"] = time.time()
    with pytest.raises(RuntimeError):
        srv.handle_event(w, {"type": "result", "terminal_reason": "completed",
                             "result": ""}, None)
    assert w["state"] == "idle"
    assert not srv.active(it)


def test_compact_uses_normal_user_message_path(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch", lambda it, msg, phase, **kw:
                        sent.append((msg, phase)))
    it = item(srv, "a", srv.NEEDS_REVIEW)
    worker(srv, it)
    assert srv.act_compact("a", "refine") == {"ok": True}
    assert sent == [("/compact", "refine")]
    assert it["feed"][-1]["text"] == "/compact"


def test_runaway_first_nudges_then_bails_to_handoff(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, trigger=None, handoff=False,
                        admitted=False, escalated=False:
                        sent.append((msg, phase, handoff, escalated)))
    it = item(srv, "a", srv.RUNNING, phase="create",
              sessions={"create": "cs", "refine": None})
    w = worker(srv, it, phase="create", state="running")
    srv.runaway_detected(it, w, "40k thinking tokens with no actions")
    assert w["escalate"] == "nudge"
    assert it["runaway"]["create"] == 1
    interrupt = w["outbound"].get_nowait()
    assert interrupt["request"]["subtype"] == "interrupt"
    assert "⚠" in it["feed"][-1]["text"]
    srv.escalate_turn(it, "create", "nudge", True)
    assert sent[-1] == (srv.NUDGE_BRIEF, "create", True, True)
    srv.runaway_detected(it, w, "40k thinking tokens with no actions")
    assert w["escalate"] == "bail"
    srv.escalate_turn(it, "create", "bail", True)
    assert sent[-1] == (srv.BAIL_BRIEF, "create", True, True)


def test_refine_runaway_bail_lands_for_review(srv):
    it = item(srv, "a", srv.COMMENTED)
    srv.escalate_turn(it, "refine", "bail", False)
    assert it["state"] == srv.NEEDS_REVIEW


def test_runaway_turn_is_nudged_and_lands(srv, monkeypatch):
    monkeypatch.setattr(srv, "FAKE", True)
    it = item(srv, "rw", srv.COMMENTED,
              sessions={"create": None, "refine": None})
    with srv.LOCK:
        srv.launch(it, "runaway", "refine")
    deadline = time.time() + 8
    while it["state"] != srv.NEEDS_REVIEW and time.time() < deadline:
        time.sleep(.02)
    try:
        assert it["state"] == srv.NEEDS_REVIEW
        assert any("runaway" in m.get("text", "") for m in it["feed"]
                   if m["kind"] == "event")
        assert it["runaway"]["refine"] == 1
        assert any(m["kind"] == "report" for m in it["feed"])
    finally:
        srv.shutdown_workers()


def think(delta):
    return {"type": "system", "subtype": "thinking_tokens",
            "estimated_tokens_delta": delta}


def capped():
    """A generation that spent the whole output budget on thinking."""
    return {"type": "assistant", "message": {"id": "cap", "usage": {},
            "stop_reason": "max_tokens",
            "content": [{"type": "thinking", "thinking": ""}]}}


def test_long_thinking_warns_and_the_cap_escalates(srv):
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    srv.handle_event(w, think(25000), None)
    assert it["feed"] == []
    srv.handle_event(w, think(25000), None)
    # only reported: an interrupt here would throw the reasoning away unrecorded
    assert "escalate" not in w
    assert "long thinking" in it["feed"][-1]["text"]
    srv.handle_event(w, capped(), None)
    assert w["escalate"] == "nudge"
    assert it["runaway"]["refine"] == 1
    assert w["outbound"].get_nowait()["request"]["subtype"] == "interrupt"
    assert "⚠ runaway thinking" in it["feed"][-1]["text"]


def test_action_blocks_reset_the_thinking_run(srv):
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    srv.handle_event(w, think(25000), None)
    srv.handle_event(w, {"type": "assistant", "message": {"id": "m1", "content":
        [{"type": "tool_use", "name": "Bash", "input": {"command": "x"}}]}}, None)
    srv.handle_event(w, think(25000), None)
    assert "escalate" not in w
    assert it.get("runaway") in (None, {})


def test_a_cut_segment_reports_the_run_the_interrupt_destroyed(srv, monkeypatch):
    monkeypatch.setattr(srv, "launch", lambda *a, **kw: None)
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    w["started"] = time.time()
    srv.handle_event(w, capped(), None)
    assert w["escalate"] == "nudge"
    srv.handle_event(w, think(9000), None)   # in flight when the interrupt lands
    srv.handle_event(w, {"type": "result", "terminal_reason": "aborted_streaming"},
                     None)
    note = it["feed"][-1]["text"]
    assert note.startswith("turn cut")
    assert "lost ~9k think" in note
    assert w["think_run"] == 0


def test_a_third_runaway_lands_the_item_instead_of_bailing_again(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch", lambda *a, **kw: sent.append(a[1]))
    it = item(srv, "a", srv.RUNNING, phase="create",
              sessions={"create": "cs", "refine": None})
    it["runaway"] = {"create": 3}
    srv.escalate_turn(it, "create", "bail", True)
    assert sent == []
    assert it["state"] == srv.NEEDS_REVIEW


# ---------- the transcript tail ----------

def transcript(srv, monkeypatch, tmp_path, session, rows=()):
    """Stand in for the CLI's record of a session."""
    home = tmp_path / "projects"
    (home / "proj").mkdir(parents=True, exist_ok=True)
    path = home / "proj" / f"{session}.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    monkeypatch.setattr(srv.quota, "PROJECTS", home)
    return path


def cap_row(out=64000, **kw):
    """A transcript row for a generation the output cap cut off mid-thought."""
    row = {"type": "assistant",
           "message": {"id": "cap", "stop_reason": "max_tokens",
                       "usage": {"output_tokens": out},
                       "content": [{"type": "thinking", "thinking": ""}]}}
    row.update(kw)
    return row


def test_the_tail_catches_a_cap_the_stream_never_reports(srv, monkeypatch, tmp_path):
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    path = transcript(srv, monkeypatch, tmp_path, "sess-a")
    assert srv.tail_turn(w, "sess-a") is None      # first read marks the position
    with path.open("a") as fh:
        fh.write(json.dumps(cap_row()) + "\n")
    srv.check_caps()
    assert w["escalate"] == "nudge"
    assert it["runaway"]["refine"] == 1
    assert w["outbound"].get_nowait()["request"]["subtype"] == "interrupt"
    assert "64,000 output tokens" in it["feed"][-1]["text"]


def test_a_resumed_sessions_old_cap_stays_behind_the_tail(srv, monkeypatch, tmp_path):
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    transcript(srv, monkeypatch, tmp_path, "sess-a", [cap_row()])
    srv.check_caps()
    assert "escalate" not in w
    assert it["feed"] == []


def test_the_tail_leaves_a_half_written_row_for_the_next_read(srv, monkeypatch,
                                                              tmp_path):
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    path = transcript(srv, monkeypatch, tmp_path, "sess-a")
    srv.tail_turn(w, "sess-a")
    line = json.dumps(cap_row()) + "\n"
    with path.open("a") as fh:
        fh.write(line[:40])
    assert srv.tail_turn(w, "sess-a") is None
    with path.open("a") as fh:
        fh.write(line[40:])
    assert "64,000" in srv.tail_turn(w, "sess-a")


def test_patch_capped_turns_the_row_into_a_kept_message(srv, monkeypatch,
                                                        tmp_path):
    normal = {"type": "assistant", "message": {"id": "m1", "stop_reason":
              "end_turn", "content": [{"type": "text", "text": "hi"}]}}
    path = transcript(srv, monkeypatch, tmp_path, "sess-a",
                      [normal, cap_row(), cap_row(isSidechain=True)])
    assert srv.patch_capped(path) == 1
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows[0]["message"]["content"] == normal["message"]["content"]
    patched = rows[1]["message"]
    assert patched["stop_reason"] == "end_turn"
    assert [b["type"] for b in patched["content"]] == ["thinking", "text"]
    assert rows[2]["message"]["stop_reason"] == "max_tokens"  # subagent's own
    assert srv.patch_capped(path) == 0


def test_revive_repairs_the_transcript_then_relaunches(srv, monkeypatch,
                                                       tmp_path):
    sent = []
    monkeypatch.setattr(srv, "launch", lambda it, msg, phase, **kw:
                        sent.append((msg, phase)))
    it = item(srv, "a", srv.RUNNING)
    it["runaway"] = {"refine": 1}
    w = worker(srv, it, state="dying")
    path = transcript(srv, monkeypatch, tmp_path, "sess-a", [cap_row()])
    srv.PROCS.pop(("a", "refine"))
    srv.revive(w, "nudge", False)
    assert json.loads(path.read_text())["message"]["stop_reason"] == "end_turn"
    assert any("preserved" in m.get("text", "") for m in it["feed"])
    assert sent == [(srv.NUDGE_BRIEF, "refine")]


def test_a_runaway_result_hands_the_worker_to_revive(srv, monkeypatch):
    monkeypatch.setattr(srv, "ensure_drain", lambda: None)
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    w["started"] = time.time()
    w["escalate"] = "nudge"
    srv.handle_event(w, {"type": "result",
                         "terminal_reason": "aborted_streaming"}, None)
    assert srv.PROCS.get(("a", "refine")) is None
    assert w["state"] == "dying"
    assert srv.DEFERRED.get_nowait() == ("revive", w, "nudge", False)


def test_a_subagents_cap_is_not_the_turns(srv, monkeypatch, tmp_path):
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    path = transcript(srv, monkeypatch, tmp_path, "sess-a")
    srv.tail_turn(w, "sess-a")
    with path.open("a") as fh:
        fh.write(json.dumps(cap_row(isSidechain=True)) + "\n")
    assert srv.tail_turn(w, "sess-a") is None


def test_a_turn_reports_what_the_model_generated(srv):
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    w["started"] = time.time()
    srv.handle_event(w, {"type": "result", "terminal_reason": "completed",
                         "usage": {"output_tokens": 8194,
                                   "iterations": [{"cache_read_input_tokens": 100}]}},
                     None)
    assert "out 8,194" in it["feed"][-1]["text"]


def test_a_cut_segment_still_reports_its_output(srv):
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    w["started"] = time.time()
    srv.handle_event(w, {"type": "result", "terminal_reason": "aborted_streaming",
                         "usage": {"iterations": [{"output_tokens": 8373}]}}, None)
    assert "out 8,373" in it["feed"][-1]["text"]


def test_cut_segment_does_not_clobber_the_cost_baseline(srv):
    it = item(srv, "a", srv.RUNNING)
    it["cost_seen"] = {"refine": {"total": 4.0, "fable": 0}}
    w = worker(srv, it, state="running")
    w["started"] = time.time()
    srv.handle_event(w, {"type": "result", "terminal_reason": "aborted_streaming",
                         "total_cost_usd": 0}, None)
    assert it["cost_seen"]["refine"]["total"] == 4.0


def test_a_fresh_turn_starts_its_own_runaway_count(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW)
    worker(srv, it)
    it["runaway"] = {"refine": 2}
    with srv.LOCK:
        srv.launch(it, "keep going", "refine", escalated=True)
    assert it["runaway"]["refine"] == 2
    with srv.LOCK:
        srv.launch(it, "new work", "refine")
    assert it["runaway"].get("refine") is None


def test_self_invoked_turn_does_not_mark_a_turn_running(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW)
    w = worker(srv, it, state="idle")
    srv.handle_event(w, {"type": "system", "subtype": "init",
                         "session_id": "s2"}, None)
    assert w["state"] == "idle"
    assert not srv.active(it)
    srv.handle_event(w, {"type": "result", "terminal_reason": "completed",
                         "result": "self talk"}, None)
    assert w["state"] == "idle"
    assert it["state"] == srv.NEEDS_REVIEW
    w["state"] = "sending"
    srv.handle_event(w, {"type": "system", "subtype": "init",
                         "session_id": "s2"}, None)
    assert w["state"] == "running"


def test_a_steer_that_lands_late_runs_as_its_own_turn(srv):
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    w["started"] = time.time()
    srv.act_comment("a", "drop the alias")
    # the turn was already landing when the steer reached the worker
    srv.handle_event(w, {"type": "result", "terminal_reason": "completed",
                         "result": "done"}, None)
    assert w["state"] == "idle"
    srv.handle_event(w, {"type": "system", "subtype": "init",
                         "session_id": "sess-a"}, None)
    assert w["state"] == "running"
    assert w["turn_seq"] == 2
    assert srv.active(it)
    assert it["state"] == srv.COMMENTED
    srv.handle_event(w, {"type": "result", "terminal_reason": "completed",
                         "result": "alias gone"}, None)
    assert it["state"] == srv.NEEDS_REVIEW
    assert any(m["kind"] == "report" and m["text"] == "alias gone"
               for m in it["feed"])


def test_a_turn_that_absorbed_the_steer_adopts_nothing(srv):
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    w["started"] = time.time()
    srv.act_comment("a", "drop the alias")
    w["steer"]["at"] -= srv.STEER_RACE + 1
    srv.handle_event(w, {"type": "result", "terminal_reason": "completed",
                         "result": "done"}, None)
    assert "steer" not in w
    srv.handle_event(w, {"type": "system", "subtype": "init",
                         "session_id": "sess-a"}, None)
    assert w["state"] == "idle"      # a background turn is still the worker's own
    assert not srv.active(it)


def test_reader_survives_a_bad_event(srv, monkeypatch):
    it = item(srv, "a", srv.RUNNING)

    class Proc:
        stdout = iter([
            '{"type": "result", "terminal_reason": "completed", "result": "hi"}\n',
            '{"type": "assistant", "message": {"id": "m", "content":'
            ' [{"type": "text", "text": "after"}]}}\n'])
        returncode = 0

        def wait(self):
            return 0

    def boom(*args, **kwargs):
        raise RuntimeError("render bug")

    monkeypatch.setattr(srv, "finish_turn", boom)
    w = worker(srv, it, state="running")
    w.update(proc=Proc(), started=time.time())
    srv.reader(w)
    events = [m["text"] for m in it["feed"] if m["kind"] == "event"]
    assert any("reader error" in t for t in events)
    assert any(m["kind"] == "worker" and m["text"] == "after" for m in it["feed"])
    assert it["state"] == srv.NEEDS_REVIEW  # the cut turn still landed for review


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
    rm = srv.advance_message({"id": "a", "reports": {"create": "the report"}},
                             "create", False)
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


# ---------- shared-file writes ----------

def test_a_turn_that_changes_a_shared_file_gets_flagged(srv):
    (srv.DOCS / "concepts.md").write_text("enclose: the old sense\n")
    it = item(srv, "a", srv.RUNNING)
    it["pre"] = {"hash": "", "solver": "", "proposals": "", "dirty": False,
                 "files": {}, "watched": srv.watched_hashes("a")}
    (srv.DOCS / "concepts.md").write_text("enclose: a new sense\n")
    srv.finish_turn(it, {"result": ""}, None, time.time(), "refine", False)
    assert it["shared_writes"] == ["docs/wf-solver/concepts.md"]
    assert any(e["kind"] == "event" and "shared files changed" in e["text"]
               for e in it["feed"])
    assert srv.light_items()[0]["shared_writes"] == ["docs/wf-solver/concepts.md"]


def test_a_write_to_the_session_skill_is_flagged(srv):
    rel = str(srv.SKILL_MD.relative_to(srv.ROOT))
    assert rel in srv.watched_paths("a")
    it = item(srv, "a", srv.RUNNING)
    watched = srv.watched_hashes("a")
    watched[rel] = "the hash the turn started with"
    it["pre"] = {"hash": "", "solver": "", "proposals": "", "dirty": False,
                 "files": {}, "watched": watched}
    srv.finish_turn(it, {"result": ""}, None, time.time(), "refine", False)
    assert it["shared_writes"] == [rel]


def test_a_solver_only_turn_flags_no_shared_write(srv):
    (srv.DOCS / "concepts.md").write_text("stable\n")
    it = item(srv, "a", srv.RUNNING)
    write_solver(srv, "a", "// v1\n")
    it["pre"] = {"hash": "", "solver": "// v1\n", "proposals": "",
                 "dirty": False, "files": {"programs/solvers/a.dl": "// v1\n"},
                 "watched": srv.watched_hashes("a")}
    write_solver(srv, "a", "// v2\n")
    srv.finish_turn(it, {"result": ""}, None, time.time(), "refine", False)
    assert it.get("shared_writes", []) == []


def test_a_repeat_landing_reports_a_shared_write_once(srv):
    (srv.DOCS / "style.md").write_text("old\n")
    it = item(srv, "a", srv.RUNNING)
    snap = {"hash": "", "solver": "", "proposals": "", "dirty": False,
            "files": {}, "watched": srv.watched_hashes("a")}
    it["pre"] = dict(snap)
    (srv.DOCS / "style.md").write_text("new\n")
    srv.finish_turn(it, {"result": ""}, None, time.time(), "refine", False)
    it["pre"] = dict(snap)
    srv.finish_turn(it, {"result": ""}, None, time.time(), "refine", False)
    assert it["shared_writes"] == ["docs/wf-solver/style.md"]
    notes = [e for e in it["feed"]
             if e["kind"] == "event" and "shared files changed" in e["text"]]
    assert len(notes) == 1


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
    assert it["phase"] == "refine" and it["landed"] == ["refine"]
    assert it["lastActive"] == {"create": None, "refine": 123}
    assert it["feed"][0]["sess"] == "refine"
    assert it["reverted"] == {"files": ["programs/solvers/a.dl"], "phase": "refine"}


def test_load_folds_two_phase_state_into_a_chain(srv):
    srv.save_report("a", "create", "what create found")
    two_phase = {"seq": 1, "wave": 1, "items": [{
        "id": "a", "state": srv.NEEDS_REVIEW, "phase": "create", "rev": 1,
        "sessions": {"create": "cs", "refine": None}, "refined": False,
        "lastActive": {"create": 123, "refine": None},
        "auto_refine": True, "refine_model": "claude-mythos-1",
        "handoff_report": "from the old state", "dirty": False, "updated": False,
        "feed": [], "ver": 0, "title": "",
        "pre": {"hash": "", "solver": "", "proposals": "", "dirty": False,
                "files": {}},
    }]}
    srv.STATE_FILE.write_text(json.dumps(two_phase))
    srv.load()
    it = srv.STATE["items"][0]
    assert it["chain"] == [
        {"name": "create", "backend": "claude", "model": srv.MODELS["create"]},
        {"name": "refine", "backend": "claude", "model": "claude-mythos-1"}]
    assert it["auto_advance"] is True
    assert it["reports"] == {"create": "from the old state"}
    assert it["landed"] == ["create"]     # the create session reported
    assert not {"auto_refine", "refine_model", "handoff_report", "refined"} & set(it)
    # the stage names carry over, so the sessions and report files keep their keys
    assert it["sessions"] == {"create": "cs", "refine": None}
    assert srv.report_of(it, "create") == "from the old state"


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


def test_fake_worker_absorbs_a_message_sent_mid_turn():
    proc = fake_process()
    try:
        send_event(proc, {"type": "user",
                          "message": {"role": "user", "content": "first"}})
        read_until(proc, lambda ev, seen: ev.get("subtype") == "init")
        send_event(proc, {"type": "user",
                          "message": {"role": "user", "content": "also drop the alias"}})
        events = read_until(proc, lambda ev, seen: ev.get("type") == "result")
        assert sum(e.get("subtype") == "init" for e in events) == 0   # no second turn
        texts = [b.get("text", "") for e in events if e.get("type") == "assistant"
                 for b in e["message"]["content"] if b.get("type") == "text"]
        assert any("into the turn" in t for t in texts)
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
        time.sleep(.02)
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


def idle_worker(s, it, phase="refine", idle_for=0, **kw):
    """A worker parked in PROCS that went idle `idle_for` seconds ago."""
    w = worker(s, it, phase=phase)
    w.update(idle_since=time.time() - idle_for, **kw)
    return w


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


def test_idle_reap_reports_the_wait_on_the_item_feed(srv, monkeypatch):
    monkeypatch.setattr(srv, "queue_reap", lambda w: None)
    it = item(srv, "a", srv.NEEDS_REVIEW)
    idle_worker(srv, it, idle_for=srv.IDLE_TTL + 120)
    srv.reap_idle()
    note = it["feed"][-1]
    assert note["sess"] == "refine"
    assert "reaped after 62m idle" in note["text"]


def test_launch_clears_the_idle_clock(srv, monkeypatch):
    monkeypatch.setattr(srv, "queue_reap", lambda w: pytest.fail("reaped"))
    it = item(srv, "a", srv.NEEDS_REVIEW)
    w = idle_worker(srv, it, idle_for=srv.IDLE_TTL * 2)
    srv.launch(it, "look again", "refine")
    assert w["idle_since"] is None
    srv.reap_idle()
    assert ("a", "refine") in srv.PROCS


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
            time.sleep(.01)
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
        time.sleep(.01)
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
    monkeypatch.setattr(srv, "STAGGER_TIMEOUT", .05)
    monkeypatch.setattr(srv, "launch",
                        lambda it, *args, **kwargs: launched.append(it["id"]))
    srv._test_stagger_launch(["a", "b"])
    assert launched == ["b", "a"]   # the claude item goes first, alone
    assert any("seeder" in m["text"] for m in srv.find("b")["feed"])


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
    assert not execed.wait(.2)  # holds while the turn is in flight
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



# ---------- overnight mode ----------

WEEK = 7 * 86400
FIVE = 5 * 3600
AT = 1_700_000_000.0


def clock_at(srv, monkeypatch, at=AT):
    monkeypatch.setattr(srv, "now", lambda: at)
    return at


def set_usage(srv, monkeypatch, wk_pct=0.0, wk_elapsed=0.0, five_pct=0.0,
              five_left=FIVE, at=AT, five_reset=True):
    """Rate-limit rows placing each window where the test wants it."""
    five = {"label": "5h", "pct": five_pct, "window": FIVE,
            "reset": at + five_left if five_reset else None}
    monkeypatch.setattr(srv, "USAGE", [
        {"label": "wk", "pct": wk_pct, "window": WEEK,
         "reset": at + WEEK * (1 - wk_elapsed / 100)},
        five])


def night_on(srv, **dials):
    cfg = srv.night()
    cfg.update(on=True, since=0, **dials)
    return cfg


def test_night_config_starts_at_the_defaults(srv):
    cfg = srv.night()
    assert cfg["on"] is False
    assert (cfg["target"], cfg["reserve"], cfg["floor"], cfg["ceiling"]) == \
        (6, 10, 5, 75)
    assert cfg["catchup"] is True


def test_pacer_admits_below_the_pace_line(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=30, wk_elapsed=50)
    gate = srv.pacer()
    assert gate["open"] is True
    assert gate["line"] == 40  # elapsed 50 − reserve 10


def test_pacer_holds_once_the_week_reaches_its_pace(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=45, wk_elapsed=50)
    gate = srv.pacer()
    assert gate["open"] is False
    assert "wk at pace" in gate["why"]


def test_a_wider_reserve_holds_sooner(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=35, wk_elapsed=50)
    assert srv.pacer()["open"] is True
    srv.night()["reserve"] = 20
    assert srv.pacer()["open"] is False


def test_the_floor_keeps_the_start_of_a_week_spendable(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=3, wk_elapsed=1)
    gate = srv.pacer()
    assert gate["open"] is True
    assert gate["line"] == 5
    set_usage(srv, monkeypatch, wk_pct=6, wk_elapsed=1)
    assert srv.pacer()["open"] is False


def test_catchup_off_caps_spending_at_strict_pace(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    cfg = night_on(srv, catchup=False, wk_start=20, wk_start_at=AT - 3600)
    set_usage(srv, monkeypatch, wk_pct=22, wk_elapsed=60)
    gate = srv.pacer()
    assert gate["open"] is False           # +2 points in an hour's worth of week
    assert "strict pace" in gate["why"]
    cfg["catchup"] = True
    assert srv.pacer()["open"] is True     # the slack is there to be spent


def test_strict_pace_restarts_when_the_weekly_window_rolls(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    cfg = night_on(srv, catchup=False, wk_start=80, wk_start_at=AT - 3600)
    set_usage(srv, monkeypatch, wk_pct=2, wk_elapsed=1)
    assert srv.pacer()["open"] is True
    assert cfg["wk_start"] == 2


def test_the_five_hour_ceiling_holds_new_admissions(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50,
              five_pct=80, five_left=2 * 3600)
    gate = srv.pacer()
    assert gate["open"] is False
    assert "5h above ceiling" in gate["why"] and "squeeze zone opens at" in gate["why"]
    assert gate["next"] == AT + 2 * 3600 - srv.SQUEEZE


def test_the_squeeze_zone_admits_above_the_ceiling(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50,
              five_pct=95, five_left=1800)
    gate = srv.pacer()
    assert gate["open"] is True
    assert gate["squeeze"] is True


def test_a_five_hour_window_with_no_reset_reads_as_fresh(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50, five_pct=90,
              five_reset=False)
    gate = srv.pacer()
    assert gate["open"] is True
    assert gate["squeeze"] is False


def test_pacer_holds_without_a_weekly_reading(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    monkeypatch.setattr(srv, "USAGE", [])
    assert srv.pacer() == {"open": False, "why": "no weekly usage reading yet",
                           "next": None, "wk": None, "line": None,
                           "fiveh": None, "ceiling": 75, "squeeze": False,
                           "squeezeAt": None}


def test_the_admitter_fills_to_target_and_stops(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50)
    night_on(srv, target=2)
    assert srv.night_tick()["admitted"] == ["t00"]
    assert srv.night_tick()["admitted"] == ["t01"]
    assert srv.night_tick()["admitted"] == []
    assert [it["id"] for it in srv.STATE["items"]] == ["t00", "t01"]


def test_the_admitter_respects_the_gate(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=60, wk_elapsed=50)
    night_on(srv)
    out = srv.night_tick()
    assert out["admitted"] == [] and "wk at pace" in out["held"]
    assert srv.STATE["items"] == []
    assert "pacer holding" in srv.night()["log"][-1]["text"]


def test_a_held_pass_logs_its_reason_once(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=60, wk_elapsed=50)
    night_on(srv)
    srv.night_tick()
    srv.night_tick()
    assert len(srv.night()["log"]) == 1


def test_the_mode_off_admits_nothing(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50)
    assert srv.night_tick() == {"resumed": [], "admitted": [], "held": None}
    assert srv.STATE["items"] == []


def test_a_night_admission_looks_like_a_wave_item(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50)
    night_on(srv, target=2)
    srv.night_tick()
    srv.night_tick()
    first, second = srv.STATE["items"]
    assert first["state"] == srv.QUEUED
    assert first["auto_advance"] is True
    assert first["auto_stop"] == "finalize"
    assert first["chain"] == srv.default_chain()
    # one wave, one appendix: the night's stages share the cached prefix
    assert (first["wave"], first["append"]) == (second["wave"], second["append"])
    assert srv.STATE["wave"] == 1


def test_a_night_admission_clears_the_committed_items(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50)
    item(srv, "old", srv.COMMITTED)
    night_on(srv, target=1)
    srv.night_tick()
    assert [it["id"] for it in srv.STATE["items"]] == ["t00"]


def test_a_queue_failure_leaves_the_night_running(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50)
    night_on(srv)

    def boom(n, order):
        raise srv.Reject("queue.sh failed: no bun")
    monkeypatch.setattr(srv, "queue_pick", boom)
    assert srv.night_tick()["admitted"] == []
    assert "admission deferred" in srv.night()["log"][-1]["text"]
    assert srv.STATE["items"] == []


def night_item(srv, item_id="a", **kw):
    """An item admitted by the mode: the whole chain but the last stage."""
    chain = srv.default_chain()
    return item(srv, item_id, srv.RUNNING, chain=chain, auto_advance=True,
                auto_stop=chain[-1]["name"],
                sessions={"create": "cs", "refine": "rs", "finalize": None},
                phase="refine", landed=["create"], **kw)


def test_auto_advance_runs_up_to_the_stage_it_stops_before(srv):
    it = night_item(srv)
    assert srv.auto_advances(it, "create") is True
    assert srv.auto_advances(it, "refine") is False
    assert srv.auto_advances(it, "finalize") is False


def test_the_stage_before_the_last_lands_for_review_with_its_report(srv, monkeypatch):
    launched = []
    monkeypatch.setattr(srv, "launch", lambda *a, **kw: launched.append(a))
    it = night_item(srv)
    srv.finish_turn(it, {"result": "what refine found"}, None, time.time(),
                    "refine", True)
    assert it["state"] == srv.NEEDS_REVIEW
    assert it["phase"] == "refine"
    assert it["reports"]["refine"] == "what refine found"
    assert srv.report_path("a", "refine").read_text() == "what refine found"
    assert launched == []
    assert not it.get("handoff_pending")


def test_an_earlier_stage_still_hands_off_by_itself(srv, monkeypatch):
    landed = threading.Event()
    monkeypatch.setattr(srv, "advance_stage", lambda it: landed.set())
    monkeypatch.setattr(srv, "launch", lambda *a, **kw: None)
    chain = srv.default_chain()
    it = item(srv, "a", srv.RUNNING, chain=chain, auto_advance=True,
              auto_stop="finalize", phase="create", landed=[],
              sessions={"create": "cs", "refine": None, "finalize": None})
    worker(srv, it, phase="create", state="running", turn_seq=4)
    srv.finish_turn(it, {"result": "the report"}, None, time.time(), "create", True)
    srv.finish_turn(it, {"result": "## Callouts\n\nnone"}, None,
                    time.time(), "create", False)
    assert landed.wait(1)


def test_quota_death_is_read_from_the_status_then_the_wording(srv):
    assert srv.quota_death(429, "api_error", "") is True
    assert srv.quota_death("429", None, "") is True
    assert srv.quota_death(None, "rate_limit", "") is True
    assert srv.quota_death(None, None, "Claude AI usage limit reached") is True
    assert srv.quota_death(None, "api_error", "") is False
    assert srv.quota_death(500, "api_error", "overloaded") is False
    assert srv.quota_death(None, None, "souffle exceeded the 5s CPU limit") is False


def quota_result(srv, it, phase="refine", handoff=False):
    w = worker(srv, it, phase=phase, state="running")
    w["started"] = time.time()
    w["handoff"] = handoff
    srv.handle_event(w, {"type": "result", "terminal_reason": "api_error",
                         "api_error_status": 429,
                         "result": "Claude AI usage limit reached"}, None)
    return w


def test_a_quota_death_schedules_a_resume_after_the_reset(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50, five_pct=100,
              five_left=1200)
    monkeypatch.setattr(srv.random, "uniform", lambda lo, hi: 60)
    night_on(srv)
    it = item(srv, "a", srv.RUNNING)
    quota_result(srv, it, handoff=True)
    assert it["state"] == srv.NEEDS_REVIEW
    assert it["resume_at"] == AT + 1200 + 60
    assert it["resume_phase"] == "refine"
    assert it["resume_handoff"] is True
    assert it["quota_retry"] == "refine"
    assert "usage limit" in it["feed"][-2]["text"]


def test_a_quota_death_with_the_mode_off_just_lands(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, five_left=1200)
    it = item(srv, "a", srv.RUNNING)
    quota_result(srv, it)
    assert it["state"] == srv.NEEDS_REVIEW
    assert "resume_at" not in it


def test_a_second_quota_death_lands_for_review(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, five_left=1200)
    night_on(srv)
    it = item(srv, "a", srv.RUNNING, quota_retry="refine")
    quota_result(srv, it)
    assert "resume_at" not in it
    assert "second usage limit" in it["feed"][-1]["text"]


def test_a_turn_that_lands_clears_the_retry(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    it = item(srv, "a", srv.RUNNING, quota_retry="refine")
    srv.finish_turn(it, {"result": "done"}, None, time.time(), "refine", False)
    assert "quota_retry" not in it


def test_a_worker_that_dies_of_quota_is_scheduled_too(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, five_left=600)
    monkeypatch.setattr(srv.random, "uniform", lambda lo, hi: 0)
    night_on(srv)
    it = item(srv, "a", srv.RUNNING)

    class Proc:
        stdout = iter([])
        returncode = 1

        def wait(self):
            return 1
    w = worker(srv, it, state="running")
    w["proc"] = Proc()
    w["started"] = time.time()
    (srv.LOG_DIR / "a.log").write_text("Claude AI usage limit reached|1700000000")
    srv.reader(w)
    assert it["resume_at"] == AT + 600


def test_a_scheduled_resume_holds_a_slot(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    it = item(srv, "a", srv.NEEDS_REVIEW, resume_at=AT + 600)
    assert srv.live_items() == [it]


def test_a_due_resume_relaunches_the_same_stage(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, **kw: sent.append((msg, phase, kw)))
    night_on(srv, target=1)
    it = item(srv, "a", srv.NEEDS_REVIEW, resume_at=AT - 1,
              resume_phase="refine", resume_handoff=True)
    out = srv.night_tick()
    assert out["resumed"] == ["a"]
    assert sent == [(srv.RESUME_BRIEF, "refine",
                     {"trigger": "resume", "handoff": True, "admitted": True})]
    assert it["state"] == srv.COMMENTED
    assert "resume_at" not in it and "resume_phase" not in it
    assert it["feed"][-1] == {"kind": "you", "text": srv.RESUME_BRIEF,
                              "sess": "refine"}


def test_a_resume_that_is_not_due_waits(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    night_on(srv, target=1)
    it = item(srv, "a", srv.NEEDS_REVIEW, resume_at=AT + 60,
              resume_phase="refine")
    assert srv.night_tick()["resumed"] == []
    assert it["state"] == srv.NEEDS_REVIEW


def test_a_resume_without_a_session_lands_for_review(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    night_on(srv, target=1)
    it = item(srv, "a", srv.NEEDS_REVIEW, resume_at=AT - 1,
              resume_phase="create", sessions={"create": None, "refine": "rs"})
    assert srv.night_tick()["resumed"] == ["a"]
    assert it["state"] == srv.NEEDS_REVIEW
    assert "no session to resume" in it["feed"][-1]["text"]


def test_the_night_counts_what_landed_unreviewed(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    night_on(srv)
    srv.night()["since"] = AT - 10
    item(srv, "old", srv.NEEDS_REVIEW, landed_at=AT - 100)
    item(srv, "new", srv.NEEDS_REVIEW, landed_at=AT - 1)
    item(srv, "run", srv.RUNNING, landed_at=AT - 1)
    assert srv.night_landed() == 1


def test_the_mode_and_its_dials_survive_a_restart(srv):
    assert srv.act_night({"on": True, "target": 3, "catchup": False,
                          "ceiling": 60}) == {"ok": True}
    srv.STATE.clear()
    srv.STATE.update({"seq": 0, "wave": 0, "items": []})
    srv.load()
    cfg = srv.night()
    assert (cfg["on"], cfg["target"], cfg["ceiling"]) == (True, 3, 60)
    assert cfg["catchup"] is False


def test_the_dials_are_held_to_their_range(srv):
    srv.act_night({"target": 999, "reserve": -5})
    cfg = srv.night()
    assert (cfg["target"], cfg["reserve"]) == (40, 0)
    assert srv.act_night({"target": "lots"})["error"] == "target must be a number"


def test_turning_the_mode_on_starts_a_fresh_night(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=42, wk_elapsed=50)
    srv.night()["wave"] = 7
    srv.act_night({"on": True})
    cfg = srv.night()
    assert cfg["since"] == AT
    assert cfg["wave"] is None       # the night gets its own wave when it admits
    assert cfg["wk_start"] == 42     # where strict pace measures from
    srv.act_night({"on": False})
    assert srv.night()["wave"] is None


def test_the_console_payload_carries_the_night(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50)
    night_on(srv, target=4)
    view = srv.night_view()
    assert (view["on"], view["target"], view["live"], view["landed"]) == \
        (True, 4, 0, 0)
    assert view["gate"]["open"] is True
    assert view["next"]["what"] == "admitter pass"


# ---------- callouts ----------

REPORT = """The model claim stands.

## Callouts

- rank ties are broken by position; the data does not say so
- `rank_of` reads like lib material
"""


def test_callouts_are_read_off_the_report(srv):
    assert srv.parse_callouts(REPORT) == [
        "rank ties are broken by position; the data does not say so",
        "`rank_of` reads like lib material"]


def test_a_stage_with_nothing_to_raise_reads_as_no_callouts(srv):
    assert srv.parse_callouts("body\n\n## Callouts\n\nnone\n") == []
    assert srv.parse_callouts("body\n\n### callouts\n\n- none\n") == []


def test_a_report_without_the_section_has_no_callouts(srv):
    assert srv.parse_callouts("just a report\n\n## Findings\n\n- one\n") == []
    assert srv.parse_callouts("") == []


def test_callouts_stop_at_the_next_heading(srv):
    text = "## Callouts\n\n- one\n\n## Next steps\n\n- two\n- three\n"
    assert srv.parse_callouts(text) == ["one"]


def test_a_section_written_as_prose_counts_its_lines(srv):
    text = "## Callouts\nthe const shape is a guess\nthe audit left one case open\n"
    assert srv.parse_callouts(text) == ["the const shape is a guess",
                                        "the audit left one case open"]


def test_a_landing_puts_the_callouts_on_the_item(srv):
    it = item(srv, "a", srv.RUNNING)
    srv.finish_turn(it, {"result": REPORT}, None, time.time(), "refine", False)
    assert it["callout_n"] == 2
    light = srv.light_items()[0]
    assert light["callout_n"] == 2
    assert light["callouts"][0].startswith("rank ties")


def test_a_turn_without_the_section_keeps_the_last_callouts(srv):
    it = item(srv, "a", srv.RUNNING)
    srv.finish_turn(it, {"result": REPORT}, None, time.time(), "refine", False)
    srv.finish_turn(it, {"result": "fixed the join"}, None, time.time(),
                    "refine", False)
    assert it["callout_n"] == 2
    srv.finish_turn(it, {"result": "all clear\n\n## Callouts\n\nnone\n"}, None,
                    time.time(), "refine", False)
    assert it["callout_n"] == 0
    assert srv.light_items()[0]["callouts"] == []


def test_an_item_that_never_landed_has_no_callout_pill(srv):
    item(srv, "a", srv.QUEUED)
    assert srv.light_items()[0]["callout_n"] is None


def test_the_callout_ask_is_its_own_turn_not_a_report_section(srv):
    for brief in (srv.CREATE_BRIEF, srv.HANDOFF_BRIEF, srv.HANDOFF_TAIL,
                  srv.REVIEW_TAIL):
        assert "## Callouts" not in brief
    text = srv.callout_brief()
    assert "## Callouts" in text
    assert "P1-P3" in text
    for kind, pct in srv.CALLOUT_RATES:
        assert f"{kind} {pct}%" in text
    # the later stage reports its own pass and leaves the earlier one alone
    assert "covers your own pass" in srv.HANDOFF_TAIL


def test_a_pending_callout_survives_its_continuation_turns(srv):
    it = item(srv, "a", srv.RUNNING, phase="create", callout_wait="create",
              sessions={"create": "cs", "refine": None})
    worker(srv, it, phase="create")
    for trigger in ("callout", "resume", "nudge", "bail"):
        srv.launch(it, "poke", "create", trigger=trigger)
        assert it["callout_wait"] == "create"
    srv.launch(it, "a user comment", "create")
    assert "callout_wait" not in it


def test_callout_ranks_are_read_off_the_entries(srv):
    assert srv.callout_rank(["[P2] a call", "[P1] urgent", "no mark"]) == 1
    assert srv.callout_rank(["[P0] the runner crashes", "[P2] a call"]) == 0
    assert srv.callout_rank(["P3 loose mark"]) == 3
    assert srv.callout_rank(["**[P1]** bolded mark"]) == 1
    assert srv.callout_rank(["**[P2] bold runs on"]) == 2
    assert srv.callout_rank(["no marks here"]) is None
    assert srv.callout_rank([]) is None


# ---------- finalize seeding ----------

def three_stage(srv, item_id="a", **kw):
    kw.setdefault("phase", "refine")
    return item(srv, item_id, srv.NEEDS_REVIEW, landed=["create"],
                chain=[{"name": "create", "backend": "claude", "model": "m1"},
                       {"name": "refine", "backend": "claude", "model": "m2"},
                       {"name": "finalize", "backend": "claude", "model": "m3"}],
                sessions={"create": "cs", "refine": "rs", "finalize": None},
                lastActive={"create": None, "refine": None, "finalize": None},
                **kw)


def test_the_final_stage_is_seeded_with_the_whole_chain(srv):
    it = three_stage(srv, reports={"create": "what create found",
                                   "refine": "what refine changed"})
    msg = srv.advance_message(it, "refine", False)
    assert msg.index("what create found") < msg.index("what refine changed")
    assert "## handoff report from the create session" in msg
    assert "## handoff report from the refine session" in msg


def test_a_non_final_advance_carries_only_the_report_before_it(srv):
    it = three_stage(srv, phase="create", reports={"create": "what create found"})
    it["reports"]["refine"] = "not written yet"
    msg = srv.advance_message(it, "create", True)
    assert "what create found" in msg
    assert "not written yet" not in msg


def test_a_final_stage_with_one_report_reads_as_before(srv):
    it = three_stage(srv, reports={"refine": "what refine changed"})
    msg = srv.advance_message(it, "refine", False)
    assert "## handoff report from the refine session" in msg
    assert "create session" not in msg


def test_a_final_stage_with_no_report_says_so(srv):
    it = three_stage(srv)
    assert "(the refine session left no report)" in \
        srv.advance_message(it, "refine", False)


# ---------- provenance ledger ----------

def test_every_landing_writes_a_ledger_line(srv, monkeypatch):
    monkeypatch.setattr(srv, "now", lambda: 1700.0)
    it = item(srv, "a", srv.RUNNING,
              chain=[{"name": "create", "backend": "codex", "model": "gpt-5.1-codex"},
                     {"name": "refine", "backend": "claude", "model": "claude-fable-5"}])
    srv.finish_turn(it, {"result": "r"}, None, time.time(), "refine", False)
    rows = srv.ledger_rows()
    assert rows == [{"task": "a", "stage": "refine", "backend": "claude",
                     "model": "claude-fable-5", "session": "sess-a",
                     "ts": 1700, "source": "console"}]
    srv.finish_turn(it, {"result": "r2"}, None, time.time(), "refine", False)
    assert len(srv.ledger_rows()) == 2       # append-only, one line per landing


def test_the_ledger_reader_tolerates_other_writers(srv):
    srv.LEDGER.parent.mkdir(parents=True, exist_ok=True)
    srv.LEDGER.write_text(
        '{"task": "a", "stage": "legacy", "backend": "claude", '
        '"model": "claude-fable-5", "session": null, "ts": 1, "source": "backfill"}\n'
        "\n"
        "not json at all\n"
        '{"no task": true}\n'
        '{"task": "b", "stage": "create", "model": "claude-opus-5", "ts": 2}\n')
    rows = srv.ledger_rows()
    assert [r["task"] for r in rows] == ["a", "b"]
    assert srv.fabled(rows) == {"a"}


def test_a_finalize_landing_counts_as_the_fable_pass(srv):
    srv.ledger_append({"task": "c", "stage": "finalize", "model": "claude-opus-5"})
    srv.ledger_append({"task": "d", "stage": "refine", "model": "claude-opus-5"})
    assert srv.fabled(srv.ledger_rows()) == {"c"}


# ---------- flags ----------

def test_a_flag_is_set_cleared_and_kept(srv, monkeypatch):
    monkeypatch.setattr(srv, "now", lambda: 900.0)
    assert srv.act_flag({"id": "a", "level": 1}) == {"ok": True, "level": 1}
    assert srv.flags() == {"a": {"level": 1, "ts": 900}}
    srv.act_flag({"id": "a", "level": 3})
    assert srv.flags()["a"]["level"] == 3
    assert srv.act_flag({"id": "a", "level": 0}) == {"ok": True, "level": 0}
    assert srv.flags() == {}


def test_flags_outlive_the_process(srv):
    srv.act_flag({"id": "a", "level": 2})
    srv.FLAGS = None                       # what a restart reads
    assert srv.flags() == {"a": {"level": 2, "ts": srv.flags()["a"]["ts"]}}
    assert json.loads(srv.FLAGS_FILE.read_text())["a"]["level"] == 2


def test_a_flag_survives_the_item_being_dropped(srv):
    item(srv, "a", srv.NEEDS_REVIEW)
    srv.act_flag({"id": "a", "level": 1})
    srv.act_drop("a")
    assert srv.STATE["items"] == []
    assert srv.flags()["a"]["level"] == 1


def test_a_flag_level_is_held_to_the_three(srv):
    assert "level" in srv.act_flag({"id": "a", "level": 4})["error"]
    assert "level" in srv.act_flag({"id": "a", "level": "high"})["error"]
    assert srv.act_flag({"id": "", "level": 1})["error"] == "no task id"
    assert srv.flags() == {}


# ---------- the finalize backlog ----------

def backlog_solver(srv, item_id, text="// concept: a shape\n"):
    write_solver(srv, item_id, text)


def test_the_backlog_holds_the_solvers_with_no_fable_pass(srv):
    for tid in ("aaa", "fff", "ggg"):
        backlog_solver(srv, tid)
    srv.ledger_append({"task": "fff", "stage": "finalize",
                       "model": "claude-opus-5", "source": "console"})
    srv.ledger_append({"task": "ggg", "stage": "legacy",
                       "model": "claude-fable-5", "source": "backfill"})
    assert [r["id"] for r in srv.backlog_view()] == ["aaa"]


def test_dismiss_drops_a_task_from_the_backlog(srv):
    for tid in ("aaa", "bbb"):
        backlog_solver(srv, tid)
    assert srv.act_dismiss({"id": "aaa"}).get("ok")
    assert [r["id"] for r in srv.backlog_view()] == ["bbb"]
    row = [r for r in srv.ledger_rows() if r["task"] == "aaa"][0]
    assert row["stage"] == "dismissed" and row["source"] == "user"
    assert "no solver" in srv.act_dismiss({"id": "zzz"})["error"]


def test_the_backlog_sorts_flags_then_comps_then_callouts(srv):
    for tid in ("aaa", "bbb", "ccc", "ddd", "eee"):
        backlog_solver(srv, tid)
    write_solver(srv, "bbb", "// concept: tiles\n.comp CornerDist {\n}\n")
    srv.save_report("ccc", "refine", REPORT)
    srv.act_flag({"id": "ddd", "level": 2})
    srv.act_flag({"id": "eee", "level": 1})
    rows = srv.backlog_view()
    assert [r["id"] for r in rows] == ["eee", "ddd", "bbb", "ccc", "aaa"]
    by_id = {r["id"]: r for r in rows}
    assert by_id["eee"]["flag"] == 1
    assert by_id["bbb"]["comps"] == ["CornerDist"]
    assert by_id["bbb"]["comps_unproposed"] == ["CornerDist"]
    assert by_id["ccc"]["callout_n"] == 2
    assert by_id["ccc"]["reports"] == ["refine"]
    assert by_id["aaa"]["reports"] == []
    assert by_id["aaa"]["title"] == "concept: a shape"


def test_a_self_rank_outsorts_comps_and_counts(srv):
    for tid in ("aaa", "bbb", "ccc"):
        backlog_solver(srv, tid)
    write_solver(srv, "aaa", "// concept: tiles\n.comp CornerDist {\n}\n")
    srv.save_report("bbb", "refine", REPORT)   # two entries, no marks
    srv.save_report("ccc", "refine",
                    "done\n\n## Callouts\n\n1. [P2] the pin is a guess\n")
    rows = srv.backlog_view()
    assert [r["id"] for r in rows] == ["ccc", "aaa", "bbb"]
    assert rows[0]["callout_rank"] == 2
    assert rows[1]["callout_rank"] is None


def test_a_p3_does_not_jump_the_tasks_that_ask_for_something(srv):
    """A P3 is a note, so it sorts in the band with reports that raised
    nothing rather than ahead of a comp or an unmarked entry."""
    for tid in ("aaa", "bbb", "ccc", "ddd"):
        backlog_solver(srv, tid)
    write_solver(srv, "bbb", "// concept: tiles\n.comp CornerDist {\n}\n")
    srv.save_report("ccc", "refine", REPORT)   # two entries, no marks
    srv.save_report("ddd", "refine",
                    "done\n\n## Callouts\n\n1. [P3] the name reads oddly\n")
    rows = srv.backlog_view()
    assert [r["id"] for r in rows] == ["bbb", "ccc", "ddd", "aaa"]
    assert rows[2]["callout_rank"] == 3
    assert rows[2]["callout_act"] == 0


def test_a_p3_still_edges_out_a_report_that_raised_nothing(srv):
    for tid in ("aaa", "bbb"):
        backlog_solver(srv, tid)
    srv.save_report("aaa", "refine",
                    "done\n\n## Callouts\n\n1. [P3] a passing note\n")
    rows = srv.backlog_view()
    assert [r["id"] for r in rows] == ["aaa", "bbb"]


def test_a_p1_still_outranks_everything_below_a_flag(srv):
    for tid in ("aaa", "bbb", "ccc"):
        backlog_solver(srv, tid)
    write_solver(srv, "bbb", "// concept: tiles\n.comp CornerDist {\n}\n")
    srv.save_report("ccc", "refine",
                    "done\n\n## Callouts\n\n1. [P1] the pin is a guess\n")
    srv.act_flag({"id": "aaa", "level": 1})
    assert [r["id"] for r in srv.backlog_view()] == ["aaa", "ccc", "bbb"]


def test_callout_act_counts_only_the_entries_that_ask(srv):
    assert srv.callout_act(["[P1] a", "[P2] b", "[P3] c"]) == 2
    assert srv.callout_act(["**[P3]** bolded note", "P3 loose mark"]) == 0
    assert srv.callout_act(["no mark at all"]) == 1
    assert srv.callout_act([]) == 0


def test_a_landed_pass_with_no_solver_still_ranks(srv):
    backlog_solver(srv, "bbb")
    srv.save_report("aaa", "refine", "no file written\n\n## Callouts\n\n1. [P1] a call\n")
    item(srv, "aaa", srv.NEEDS_REVIEW, chain=srv.default_chain())
    rows = {r["id"]: r for r in srv.backlog_view()}
    assert set(rows) == {"aaa", "bbb"}
    assert rows["aaa"]["no_solver"] and not rows["bbb"]["no_solver"]
    # the reports carry the row where the file cannot
    assert rows["aaa"]["reports"] == ["refine"]
    assert rows["aaa"]["callout_rank"] == 1


def test_a_missing_solver_leads_the_backlog(srv):
    backlog_solver(srv, "aaa")
    srv.act_flag({"id": "aaa", "level": 1})
    srv.save_report("zzz", "refine", "no file written")
    item(srv, "zzz", srv.NEEDS_REVIEW, chain=srv.default_chain())
    # the id sorts last and it carries no callouts, so only the lead term
    # can put it above a P1-flagged task
    assert [r["id"] for r in srv.backlog_view()] == ["zzz", "aaa"]


def test_a_p0_follows_no_solver_and_leads_the_flags(srv):
    for tid in ("aaa", "bbb"):
        backlog_solver(srv, tid)
    srv.act_flag({"id": "aaa", "level": 1})
    srv.save_report("bbb", "refine",
                    "done\n\n## Callouts\n\n1. [P0] run_dl crashes on this task\n")
    srv.save_report("zzz", "refine", "no file written")
    item(srv, "zzz", srv.NEEDS_REVIEW, chain=srv.default_chain())
    rows = srv.backlog_view()
    assert [r["id"] for r in rows] == ["zzz", "bbb", "aaa"]
    assert rows[1]["callout_rank"] == 0


def test_a_pass_still_running_its_first_stage_has_no_row(srv):
    item(srv, "aaa", srv.RUNNING, chain=srv.default_chain(),
         phase="create", landed=[])
    assert srv.backlog_view() == []


def test_a_dismissed_solverless_task_leaves_the_backlog(srv):
    srv.save_report("aaa", "refine", "no file written")
    item(srv, "aaa", srv.NEEDS_REVIEW, chain=srv.default_chain())
    assert [r["id"] for r in srv.backlog_view()] == ["aaa"]
    srv.ledger_append({"task": "aaa", "stage": "dismissed",
                       "model": None, "source": "user"})
    srv.BACKLOG_CACHE["at"] = 0.0
    assert srv.backlog_view() == []


def test_a_task_the_console_holds_stays_out_of_the_backlog(srv):
    backlog_solver(srv, "aaa")
    backlog_solver(srv, "bbb")
    item(srv, "aaa", srv.NEEDS_REVIEW)
    assert [r["id"] for r in srv.backlog_view()] == ["bbb"]


def test_save_exports_the_approved_ids(srv):
    item(srv, "a", srv.APPROVED)
    item(srv, "b", srv.NEEDS_REVIEW)
    srv.save()
    assert srv.APPROVED_FILE.read_text() == "a\n"
    srv.find("a")["state"] = srv.COMMITTED
    srv.save()
    assert srv.APPROVED_FILE.read_text() == ""


def test_a_refine_done_item_ranks_in_the_backlog(srv):
    for tid in ("aaa", "bbb", "ccc"):
        backlog_solver(srv, tid)
    srv.save_report("aaa", "refine", "done\n\n## Callouts\n\n1. [P1] a call\n")
    item(srv, "aaa", srv.NEEDS_REVIEW, chain=srv.default_chain())
    # a mid-chain item stays held even on the finalize-bearing chain
    item(srv, "bbb", srv.NEEDS_REVIEW, chain=srv.default_chain(),
         phase="create", sessions={"create": "sess-bbb"}, landed=["create"])
    rows = srv.backlog_view()
    assert [r["id"] for r in rows] == ["aaa", "ccc"]
    assert rows[0]["callout_rank"] == 1


def test_start_finalize_advances_a_refine_done_item(srv, monkeypatch):
    sent = finalize_launch(srv, monkeypatch)
    backlog_solver(srv, "aaa")
    srv.save_report("aaa", "refine", "the handoff")
    it = item(srv, "aaa", srv.NEEDS_REVIEW, chain=srv.default_chain())
    assert srv.act_finalize({"id": "aaa"}) == \
        {"ok": True, "id": "aaa", "advanced": True}
    assert srv.find("aaa") is it
    assert it["phase"] == "finalize" and it["state"] == srv.RUNNING
    (_, phase), = sent
    assert phase == "finalize"


def test_the_backlog_scan_is_reused_between_polls(srv):
    backlog_solver(srv, "aaa")
    srv.backlog_view()
    backlog_solver(srv, "bbb")
    assert [r["id"] for r in srv.backlog_view()] == ["aaa"]   # inside the TTL
    srv.BACKLOG_CACHE["at"] = 0.0
    assert [r["id"] for r in srv.backlog_view()] == ["aaa", "bbb"]


def test_a_flag_shows_up_without_waiting_for_the_scan(srv):
    backlog_solver(srv, "aaa")
    srv.backlog_view()
    srv.act_flag({"id": "aaa", "level": 1})
    assert srv.backlog_view()[0]["flag"] == 1


# ---------- starting a finalize pass ----------

def finalize_launch(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch", lambda it, msg, phase, **kw:
                        sent.append((msg, phase)))
    return sent


def test_start_finalize_seeds_from_the_persisted_reports(srv, monkeypatch):
    sent = finalize_launch(srv, monkeypatch)
    backlog_solver(srv, "aaa")
    srv.save_report("aaa", "create", "what create found")
    srv.save_report("aaa", "refine", "what refine changed")
    res = srv.act_finalize({"id": "aaa"})
    assert res == {"ok": True, "id": "aaa", "seeded": ["create", "refine"]}
    it = srv.find("aaa")
    assert srv.stage_names(it) == ["finalize"]
    assert it["sessions"] == {"finalize": None}
    assert it["phase"] == "finalize" and it["state"] == srv.RUNNING
    assert it["chain"][0]["model"] == srv.default_chain()[-1]["model"]
    (msg, phase), = sent
    assert phase == "finalize"
    assert msg.index("what create found") < msg.index("what refine changed")
    assert srv.REVIEW_TAIL in msg
    assert srv.HANDOFF_TAIL not in msg


def test_start_finalize_over_a_solver_with_no_reports(srv, monkeypatch):
    sent = finalize_launch(srv, monkeypatch)
    backlog_solver(srv, "aaa")
    assert srv.act_finalize({"id": "aaa"})["seeded"] == []
    (msg, _), = sent
    assert "No earlier session left a report" in msg
    assert "handoff report from" not in msg
    assert srv.task_block("aaa") in msg
    assert srv.find("aaa")["feed"][0]["text"].endswith("no earlier reports")


def test_start_finalize_needs_a_solver_and_a_free_task(srv, monkeypatch):
    finalize_launch(srv, monkeypatch)
    assert "no solver" in srv.act_finalize({"id": "aaa"})["error"]
    backlog_solver(srv, "aaa")
    item(srv, "aaa", srv.NEEDS_REVIEW)
    assert "already in the console" in srv.act_finalize({"id": "aaa"})["error"]


def test_a_started_finalize_pass_lands_for_review(srv, monkeypatch):
    finalize_launch(srv, monkeypatch)
    backlog_solver(srv, "aaa")
    srv.act_finalize({"id": "aaa"})
    it = srv.find("aaa")
    srv.finish_turn(it, {"result": "the review"}, None, time.time(),
                    "finalize", False)
    assert it["state"] == srv.NEEDS_REVIEW
    assert srv.fabled(srv.ledger_rows()) == {"aaa"}
    assert srv.backlog_view() == []
