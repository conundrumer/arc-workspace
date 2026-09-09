"""What a landing does: the report it hands on, the callouts it asks for,
the holds it waits out, and the compact it owes."""

import json
import threading
import time

from .conftest import (
    REPORT,
    create_item,
    finalize_item,
    item,
    land_report,
    tagged,
    transcript,
    worker,
)

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
    srv.finish_turn(it, {"result": tagged("the report")}, None, time.time(), "create", True)
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


def test_a_new_stage_reads_the_appendix_as_it_stands(srv, monkeypatch):
    monkeypatch.setattr(srv, "launch", lambda *a, **kw: None)
    it = item(srv, "a", srv.NEEDS_REVIEW, phase="create",
              append="/stale/appendix.md")
    srv.advance_stage(it)
    assert it["append"] == str(srv.append_path())


def test_a_respawn_reads_the_appendix_as_it_stands(srv, monkeypatch):
    read = []

    def spawn(it, phase):
        read.append(it["append"])
        return worker(srv, it, phase)

    monkeypatch.setattr(srv, "spawn_worker", spawn)
    it = item(srv, "a", srv.NEEDS_REVIEW, append="/stale/appendix.md")
    srv.launch(it, "look again", "refine")
    assert read == [str(srv.append_path())]


def test_a_resident_worker_hears_the_appendix_moved_on(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW, append="/stale/appendix.md")
    w = worker(srv, it)
    srv.launch(it, "look again", "refine")
    sent = w["outbound"].get_nowait()["message"]["content"]
    assert sent.startswith("<system-reminder>Your system prompt's copy of docs/wf-solver and "
                           "programs/lib.dl is behind the files.")
    assert sent.endswith("</system-reminder>\n\nlook again")
    # the prefix its system prompt was built from stays, so its cache holds
    assert it["append"] == "/stale/appendix.md"
    it["append"] = str(srv.append_path())
    srv.launch(it, "look again", "refine")
    assert w["outbound"].get_nowait()["message"]["content"] == "look again"


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


# ---------- a handoff held for a background task ----------

def bg_dispatch(mid="m1", tool_id="toolu_1", name="Task", **inp):
    """A tool_use event for a call whose result may land after the turn."""
    return {"type": "assistant", "message": {"id": mid, "content": [
        {"type": "tool_use", "id": tool_id, "name": name, "input": inp}]}}


def task_started(tool_id="toolu_1", **kw):
    """The CLI's word that a call got a background task."""
    return {"type": "system", "subtype": "task_started", "task_id": "t" + tool_id,
            "tool_use_id": tool_id, **kw}


def notification(tool_id="toolu_1"):
    """The CLI's word that a background task reported."""
    return {"type": "system", "subtype": "task_notification",
            "task_id": "t" + tool_id, "tool_use_id": tool_id, "status": "completed"}


def test_what_a_turn_starts_in_the_background_is_outstanding(srv):
    it = create_item(srv)
    w = worker(srv, it, phase="create", state="running")
    srv.handle_event(w, bg_dispatch(subagent_type="claude",
                                    description="Sweep corpus"), None)
    srv.handle_event(w, task_started(), None)
    srv.handle_event(w, bg_dispatch("m2", "toolu_2", "Bash",
                                    command="uv run pytest"), None)
    srv.handle_event(w, bg_dispatch("m3", "toolu_3", "Bash", command="souffle x",
                                    run_in_background=True), None)
    srv.handle_event(w, task_started("toolu_3"), None)
    # the CLI emits a subagent call under either registered name
    srv.handle_event(w, bg_dispatch("m5", "toolu_5", "Agent",
                                    description="Survey sweep"), None)
    srv.handle_event(w, task_started("toolu_5"), None)
    srv.handle_event(w, {**bg_dispatch("m4", "toolu_4", description="its own"),
                         "parent_tool_use_id": "toolu_1"}, None)
    srv.handle_event(w, task_started("toolu_4", spawn_depth=2), None)
    # the foreground Bash reports inside the turn; the subagent's own dispatch
    # belongs to the subagent
    assert w["bg"] == {"toolu_1": "Sweep corpus", "toolu_3": "`souffle x`",
                       "toolu_5": "Survey sweep"}


def test_a_call_a_hook_refuses_is_not_outstanding(srv):
    it = create_item(srv)
    w = worker(srv, it, phase="create", state="running")
    srv.handle_event(w, bg_dispatch("m1", "toolu_1", "Bash", command="sleep 150",
                                    run_in_background=True), None)
    srv.handle_event(w, {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "toolu_1", "is_error": True,
         "content": "Blocked: this command waits by timer or poll loop."}]}}, None)
    assert not w.get("bg")


def test_a_notification_takes_a_task_off_the_outstanding_set(srv):
    it = create_item(srv)
    w = worker(srv, it, phase="create", state="running")
    w["bg"] = {"toolu_1": "Sweep corpus", "toolu_9": "another sweep"}
    srv.handle_event(w, notification(), None)
    assert w["bg"] == {"toolu_9": "another sweep"}
    assert not w.get("woke")            # the running turn takes it in


def test_a_handoff_waiting_on_a_subagent_is_held(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, **kw: sent.append(phase))
    it = create_item(srv)
    w = worker(srv, it, phase="create", state="running", turn_seq=4)
    w["bg"] = {"toolu_1": "Sweep corpus"}
    srv.finish_turn(it, {"result": "the sweep is still running"}, None,
                    time.time(), "create", True)
    assert it["bg_wait"] == "create"
    # the turn ended without its report, as the brief asks while a task runs
    assert it["reports"] == {}
    assert not srv.report_path("a", "create").exists()
    assert "bg_filed" not in it
    assert sent == []           # no callout ask while the hold stands
    assert "handoff held — Sweep corpus" in it["feed"][-1]["text"]
    assert "asking again" not in it["feed"][-1]["text"]
    # a report written with the task still out is filed, and lands when it is in
    srv.finish_turn(it, {"result": tagged("the report so far")}, None,
                    time.time(), "create", True)
    assert it["bg_wait"] == "create" and it["bg_filed"] is True
    assert it["reports"] == {"create": "the report so far"}


def test_a_background_wake_starts_a_turn_of_its_own(srv):
    it = create_item(srv)
    it["state"] = srv.NEEDS_REVIEW
    w = worker(srv, it, phase="create")
    init = {"type": "system", "subtype": "init", "session_id": "cs"}
    srv.handle_event(w, init, None)
    assert w["state"] == "idle"          # nothing outstanding, nothing to adopt
    w["bg"] = {"toolu_1": "Sweep corpus"}
    srv.handle_event(w, init, None)
    assert w["state"] == "running"
    assert it["state"] == srv.COMMENTED
    assert "a background task woke the session" in it["feed"][-1]["text"]
    # the notification for the last task lands before the turn it opens
    w["state"] = "idle"
    srv.handle_event(w, notification(), None)
    assert w["bg"] == {}
    srv.handle_event(w, init, None)
    assert w["state"] == "running"
    assert "woke" not in w


def test_the_woken_turn_sends_the_handoff_ask_again(srv, monkeypatch):
    asked = threading.Event()
    sent = []

    def fake_launch(it, msg, phase, trigger=None, handoff=False, **kw):
        sent.append((msg, phase, trigger, handoff))
        asked.set()
    monkeypatch.setattr(srv, "launch", fake_launch)
    it = create_item(srv, bg_wait="create", bg_at=time.time())
    worker(srv, it, phase="create", state="running", turn_seq=4)
    srv.finish_turn(it, {"result": "the sweep found five sites"}, None,
                    time.time(), "create", False)
    assert asked.wait(1)
    assert sent == [(srv.HANDOFF_BRIEF, "create", "handoff", True)]
    assert "bg_wait" not in it
    assert it["reports"] == {}      # a note on the result is not the report


def test_the_woken_turn_lands_the_block_it_carries(srv, monkeypatch):
    monkeypatch.setattr(srv, "launch", lambda *a, **kw: None)
    monkeypatch.setattr(srv, "ensure_drain", lambda: None)
    it = create_item(srv, bg_wait="create", bg_at=time.time())
    w = worker(srv, it, phase="create", state="running", turn_seq=4)
    srv.finish_turn(it, {"result": tagged("the sweep found five sites")}, None,
                    time.time(), "create", False)
    assert "bg_wait" not in it
    assert it["reports"] == {"create": "the sweep found five sites"}
    assert it["callout_wait"] == "create"
    assert srv.DEFERRED.get_nowait() == ("callout", "a", "create", w["turn_seq"])


def test_the_woken_turn_lands_the_report_the_hold_filed(srv, monkeypatch):
    monkeypatch.setattr(srv, "launch", lambda *a, **kw: None)
    monkeypatch.setattr(srv, "ensure_drain", lambda: None)
    it = create_item(srv, bg_wait="create", bg_at=time.time(), bg_filed=True,
                     reports={"create": "the report so far"})
    w = worker(srv, it, phase="create", state="running", turn_seq=4)
    srv.finish_turn(it, {"result": "the sweep is in; nothing to add"}, None,
                    time.time(), "create", False)
    assert "bg_wait" not in it and "bg_filed" not in it
    assert it["reports"] == {"create": "the report so far"}
    assert it["callout_wait"] == "create"
    assert srv.DEFERRED.get_nowait() == ("callout", "a", "create", w["turn_seq"])


def test_a_comment_turn_that_carries_the_block_lands(srv, monkeypatch):
    """The block is the act, whichever turn carries it."""
    monkeypatch.setattr(srv, "launch", lambda *a, **kw: None)
    monkeypatch.setattr(srv, "ensure_drain", lambda: None)
    it = create_item(srv)
    w = worker(srv, it, phase="create", state="running", turn_seq=2)
    srv.finish_turn(it, {"result": tagged("as you asked, the handoff")}, None,
                    time.time(), "create", False)
    assert it["reports"] == {"create": "as you asked, the handoff"}
    assert it["callout_wait"] == "create"
    assert srv.DEFERRED.get_nowait() == ("callout", "a", "create", w["turn_seq"])


def test_an_asked_turn_without_the_block_is_asked_once_more(srv, monkeypatch):
    monkeypatch.setattr(srv, "ensure_drain", lambda: None)
    it = create_item(srv)
    w = worker(srv, it, phase="create", state="running", turn_seq=4)
    srv.finish_turn(it, {"result": "here is my report, untagged"}, None,
                    time.time(), "create", True)
    assert it["reports"] == {}
    assert it["reasked"] == {"create": True}
    assert "no handoff block — asking again" in it["feed"][-1]["text"]
    assert srv.DEFERRED.get_nowait() == ("rehandoff", "a", "create", w["turn_seq"])
    # the second miss files the text as written, and the callouts follow
    srv.finish_turn(it, {"result": "still untagged"}, None, time.time(), "create", True)
    assert it["reports"] == {"create": "still untagged"}
    assert "reasked" not in it or "create" not in it["reasked"]
    assert it["callout_wait"] == "create"
    assert srv.DEFERRED.get_nowait() == ("callout", "a", "create", w["turn_seq"])


def test_callouts_written_with_the_report_skip_the_callout_turn(srv, monkeypatch):
    monkeypatch.setattr(srv, "ensure_drain", lambda: None)
    it = create_item(srv, auto_advance=True)
    w = worker(srv, it, phase="create", state="running", turn_seq=4)
    text = tagged("the report") + "\n\n<callouts>\n1. [P2] a call\n</callouts>"
    srv.finish_turn(it, {"result": text}, None, time.time(), "create", True)
    assert it["reports"] == {"create": "the report\n\n## Callouts\n\n1. [P2] a call"}
    assert it["callouts"] == ["[P2] a call"]
    assert "callout_wait" not in it
    assert it["handoff_pending"] is True
    assert srv.DEFERRED.get_nowait() == ("handoff", "a", "create", w["turn_seq"])
    # the feed shows the text without the tags
    report = [m for m in it["feed"] if m["kind"] == "report"][-1]["text"]
    assert "<handoff>" not in report and "the report" in report
    assert "<callouts>" not in report and "[P2] a call" in report


def test_a_tagged_callout_turn_joins_the_section(srv, monkeypatch):
    monkeypatch.setattr(srv, "ensure_drain", lambda: None)
    it = create_item(srv, callout_wait="create", reports={"create": "the report"})
    worker(srv, it, phase="create", state="running", turn_seq=5)
    srv.finish_turn(it, {"result": tagged("none", "callouts")}, None,
                    time.time(), "create", False)
    assert it["reports"] == {"create": "the report\n\n## Callouts\n\nnone"}
    assert it["callouts"] == []


def test_a_second_callout_turn_replaces_the_section(srv, monkeypatch):
    monkeypatch.setattr(srv, "ensure_drain", lambda: None)
    it = create_item(srv, callout_wait="create",
                     reports={"create": "the report\n\n## Callouts\n\n1. [P2] old"})
    worker(srv, it, phase="create", state="running", turn_seq=5)
    srv.finish_turn(it, {"result": tagged("1. [P1] new", "callouts")}, None,
                    time.time(), "create", False)
    assert it["reports"] == {"create": "the report\n\n## Callouts\n\n1. [P1] new"}
    assert it["callouts"] == ["[P1] new"]


def test_a_report_with_two_callout_sections_keeps_the_last_at_load(srv):
    doubled = "the report\n\n## Callouts\n\n1. [P2] old\n\n## Callouts\n\n1. [P1] new"
    it = create_item(srv, reports={"create": doubled})
    srv.seed_report(it)
    assert it["reports"]["create"] == "the report\n\n## Callouts\n\n1. [P1] new"
    assert srv.report_path(it["id"], "create").read_text() == it["reports"]["create"]
    assert srv.collapse_callouts("one section\n\n## Callouts\n\nnone") == \
        "one section\n\n## Callouts\n\nnone"


def test_the_blocks_are_read_closed_and_last(srv):
    assert srv.tagged("<handoff>\n a \n</handoff>", srv.HANDOFF_TAG) == "a"
    assert srv.tagged("<handoff>\ncut off", srv.HANDOFF_TAG) is None
    assert srv.tagged("<handoff>x</handoff> and <handoff>y</handoff>",
                      srv.HANDOFF_TAG) == "y"
    assert srv.untagged("hi\n<handoff>\nbody\n</handoff>\nbye") == "hi\nbody\nbye"
    assert srv.callout_body("<callouts>\n## Callouts\n\n- one\n</callouts>").strip() == "- one"
    assert srv.parse_callouts("<callouts>\n1. [P1] a\n2. [P3] b\n</callouts>") == \
        ["[P1] a", "[P3] b"]
    assert srv.parse_callouts("<callouts>\nnone\n</callouts>") == []
    assert srv.callout_body("no callouts here") is None


def test_a_stage_can_be_pointed_at_another_session(srv, monkeypatch, tmp_path):
    transcript(srv, monkeypatch, tmp_path, "cut-copy")
    monkeypatch.setattr(srv, "ensure_drain", lambda: None)
    it = item(srv, "a", srv.NEEDS_REVIEW)
    w = worker(srv, it, phase="refine")
    assert "no transcript" in srv.act_session("a", "refine", "missing")["error"]
    assert "no stage" in srv.act_session("a", "create2", "cut-copy")["error"]
    assert srv.act_session("a", "refine", "cut-copy") == {"ok": True}
    assert it["sessions"]["refine"] == "cut-copy"
    assert ("a", "refine") not in srv.PROCS          # the old worker goes
    assert w["state"] == "dying"
    assert "session replaced by hand — was sess-a" in it["feed"][-1]["text"]
    assert srv.DEFERRED.get_nowait() == ("reap", w)


def test_a_stage_model_can_be_changed_by_hand(srv, monkeypatch):
    monkeypatch.setattr(srv, "ensure_drain", lambda: None)
    it = item(srv, "a", srv.NEEDS_REVIEW)
    w = worker(srv, it, phase="refine")
    assert "no stage" in srv.act_model("a", "nope", "m2")["error"]
    assert "no model" in srv.act_model("a", "refine", " ")["error"]
    assert srv.act_model("a", "refine", "m2") == {"ok": True}
    assert srv.stage_of(it, "refine")["model"] == "m2"
    assert ("a", "refine") not in srv.PROCS and w["state"] == "dying"
    assert "model set by hand to m2" in it["feed"][-1]["text"]


def test_land_takes_the_filed_report_as_the_handoff(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, **kw: sent.append((msg, phase, kw)))
    it = item(srv, "a", srv.NEEDS_REVIEW, chain=srv.default_chain(),
              reports={"refine": "the report"})
    assert srv.act_land("a") == {"ok": True}
    assert it["callout_wait"] == "refine" and it["state"] == srv.RUNNING
    assert sent == [(srv.callout_brief(), "refine",
                     {"trigger": "callout", "admitted": True})]
    assert "callout turn starting" in it["feed"][-1]["text"]
    it["state"] = srv.NEEDS_REVIEW
    it["reports"] = {}
    assert "no handoff report" in srv.act_land("a")["error"]


def test_a_held_landing_with_work_still_outstanding_stays_held(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, **kw: sent.append(phase))
    it = create_item(srv, bg_wait="create", bg_at=time.time() - 300)
    w = worker(srv, it, phase="create", state="running", turn_seq=4)
    w["bg"] = {"toolu_2": "another sweep"}
    srv.finish_turn(it, {"result": "notes so far"}, None,
                    time.time(), "create", False)
    assert it["bg_wait"] == "create"
    assert it["bg_at"] > time.time() - 60      # the wait starts over
    assert it["reports"] == {}
    assert sent == []
    assert "handoff held — another sweep" in it["feed"][-1]["text"]


def test_a_hold_stands_through_its_own_handoff_ask(srv):
    it = create_item(srv, bg_wait="create", bg_at=time.time())
    worker(srv, it, phase="create")
    for trigger in ("handoff", "resume", "nudge", "bail"):
        srv.launch(it, "poke", "create", trigger=trigger)
        assert it["bg_wait"] == "create"
    srv.launch(it, "a user comment", "create")
    assert "bg_wait" not in it


def test_a_hold_the_task_never_ends_expires_into_a_review(srv):
    it = create_item(srv, bg_wait="create", bg_at=time.time() - srv.BG_TTL - 1)
    w = worker(srv, it, phase="create", state="running")
    srv.expire_holds()
    assert it["bg_wait"] == "create"     # the running turn settles it
    w["state"] = "idle"
    srv.expire_holds()
    assert "bg_wait" not in it
    assert it["state"] == srv.NEEDS_REVIEW
    assert it["reports"] == {}
    assert "no report" in it["feed"][-1]["text"]


def test_an_expired_hold_lands_the_filed_report(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, **kw: sent.append((msg, phase, kw)))
    it = create_item(srv, bg_wait="create", bg_at=time.time() - srv.BG_TTL - 1,
                     bg_filed=True, reports={"create": "notes so far"})
    worker(srv, it, phase="create")
    srv.expire_holds()
    assert "bg_wait" not in it and "bg_filed" not in it
    assert it["reports"] == {"create": "notes so far"}
    assert it["callout_wait"] == "create" and it["state"] == srv.RUNNING
    assert sent == [(srv.callout_brief(), "create", {"trigger": "callout", "admitted": True})]
    assert any("the filed report lands" in e["text"] for e in it["feed"]
               if e["kind"] == "event")


def test_a_restart_ends_every_hold(srv, monkeypatch):
    """The outstanding set went with the process, so a hold found at startup
    has nothing left to wait on."""
    monkeypatch.setattr(srv, "launch", lambda *a, **kw: None)
    fresh = create_item(srv, "a", bg_wait="create", bg_at=time.time(),
                        reports={"create": "notes so far"})
    bare = create_item(srv, "b", bg_wait="create", bg_at=time.time())
    worker(srv, fresh, phase="create")
    srv.expire_holds()
    assert fresh["bg_wait"] == "create"      # not due
    srv.expire_holds(force=True)
    assert "bg_wait" not in fresh and fresh["callout_wait"] == "create"
    assert "bg_wait" not in bare and bare["state"] == srv.NEEDS_REVIEW
    assert "a console restart" in bare["feed"][-1]["text"]


def test_a_worker_may_wait_on_what_it_starts(srv):
    denied = srv.WORKER_FLAGS[srv.WORKER_FLAGS.index("--disallowedTools") + 1:]
    for name in ("Monitor", "TaskOutput"):
        assert name in srv.WORKER_TOOLS
        assert name not in denied


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


# ---------- callouts ----------


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


def test_a_sign_off_line_is_not_a_callout(srv):
    text = ("## Callouts\nthe const shape is a guess\n"
            "the audit left one case open\n\n*tink*\n")
    assert srv.parse_callouts(text) == ["the const shape is a guess",
                                        "the audit left one case open"]
    assert srv.parse_callouts("## Callouts\n\n*tink*\n") == []
    assert srv.parse_callouts("## Callouts\n\nnone\n\n*purr*\n") == []
    assert srv.parse_callouts("## Callouts\n\n- one\n\n**glass**\n") == ["one"]


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


def test_a_stage_that_landed_short_of_what_it_owes_says_so(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW, phase="create", landed=["create"],
              sessions={"create": "cs", "refine": None}, auto_advance=True)
    assert srv.owed(it) == "report"
    it["reports"] = {"create": "the model claim"}
    assert srv.owed(it) == "callouts"
    it["reports"] = {"create": REPORT}
    assert srv.owed(it) == "handoff"
    assert srv.light_items()[0]["owes"] == "handoff"
    it["auto_advance"] = False        # the chain waits for the user by design
    assert srv.owed(it) is None
    it["auto_advance"] = True
    it["handoff_pending"] = True      # the advance is in flight
    assert srv.owed(it) is None
    it.pop("handoff_pending")
    it["state"] = srv.RUNNING
    assert srv.owed(it) is None
    it["state"] = srv.NEEDS_REVIEW
    it["phase"] = "refine"            # the last stage owes nothing after it
    assert srv.owed(it) is None


def test_an_item_that_never_landed_has_no_callout_pill(srv):
    item(srv, "a", srv.QUEUED)
    assert srv.light_items()[0]["callout_n"] is None


def test_the_callout_ask_is_its_own_turn_not_a_report_section(srv):
    for brief in (srv.CREATE_BRIEF, srv.HANDOFF_BRIEF, srv.HANDOFF_TAIL,
                  srv.REVIEW_TAIL):
        assert "## Callouts" not in brief and "<callouts>" not in brief
    # every message that asks for a report says where it goes
    for brief in (srv.CREATE_BRIEF, srv.HANDOFF_BRIEF, srv.HANDOFF_TAIL,
                  srv.BAIL_BRIEF, srv.RESUME_HANDOFF_NOTE):
        assert "<handoff>" in brief
    assert "<handoff>" not in srv.REVIEW_TAIL
    text = srv.callout_brief()
    assert "<callouts>" in text
    assert "P1-P3" in text
    for kind, pct, band, desc in srv.callout_bands():
        assert f"- P{band} · {kind} {pct}%: {desc}" in text
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


# ---------- compact on landing ----------

def landing_item(srv, monkeypatch, on=True, **kw):
    """A finalize pass the autopilot opened, mid-turn, with the compact on
    landing set unless `on` is False. Launches are recorded, and the deferred
    jobs wait until the test drains them."""
    sent = []
    monkeypatch.setattr(srv, "launch", lambda it, msg, phase, **kw: sent.append((msg, phase)))
    drain = srv.ensure_drain
    monkeypatch.setattr(srv, "ensure_drain", lambda: None)
    if on:
        srv.act_auto({"compact_landing": True})
    it = finalize_item(srv, state=srv.RUNNING, auto_finalize=True, **kw)
    w = srv.PROCS[("a", "finalize")]
    w["state"], w["turn_seq"] = "running", 4
    return it, sent, drain


def drained(drain, until, wait=2):
    drain()
    deadline = time.time() + wait
    while not until() and time.time() < deadline:
        time.sleep(0.01)
    return until()


def test_the_compact_on_landing_follows_the_callout_turn(srv, monkeypatch):
    it, sent, drain = landing_item(srv, monkeypatch)
    srv.finish_turn(it, {"result": "the solver holds up"}, None, time.time(), "finalize", False)
    assert srv.DEFERRED.get_nowait() == ("callout", "a", "finalize", 4)
    assert srv.DEFERRED.empty() and it["landing_compact"] == "finalize"
    srv.finish_turn(it, {"result": "<callouts>\n1. [P2] a call\n</callouts>"}, None,
                    time.time(), "finalize", False)
    assert "landing_compact" not in it and it["state"] == srv.NEEDS_REVIEW
    assert srv.DEFERRED.queue[0] == ("compact", "a", "finalize", 4)
    # the result handler marks the worker idle before it lets go of the lock
    srv.PROCS[("a", "finalize")]["state"] = "idle"
    assert drained(drain, lambda: sent)
    assert sent == [("/compact", "finalize")]
    assert it["auto_compacted"] == {"finalize": True}
    assert it["feed"][-1]["text"] == "auto compact — on landing"


def test_callouts_written_inline_queue_the_compact_at_once(srv, monkeypatch):
    it, sent, drain = landing_item(srv, monkeypatch)
    srv.finish_turn(it, {"result": "holds up\n\n<callouts>\n1. [P1] a call\n</callouts>"},
                    None, time.time(), "finalize", False)
    assert srv.DEFERRED.queue[0] == ("compact", "a", "finalize", 4)
    assert "landing_compact" not in it


def test_callouts_refused_past_the_retries_still_compact(srv, monkeypatch):
    it, sent, drain = landing_item(srv, monkeypatch, callout_wait="finalize",
                                   landing_compact="finalize",
                                   refused={"finalize": {"callout": 2}},
                                   reports={"finalize": "the report"})
    w = srv.PROCS.pop(("a", "finalize"))
    w["state"] = "dying"
    srv.recover_refusal(w, "callout", None)
    assert it["state"] == srv.NEEDS_REVIEW and "landing_compact" not in it
    assert srv.DEFERRED.queue[0] == ("compact", "a", "finalize", None)
    assert drained(drain, lambda: sent)
    assert sent == [("/compact", "finalize")]


def test_the_compact_on_landing_is_off_until_set(srv, monkeypatch):
    it, sent, drain = landing_item(srv, monkeypatch, on=False)
    srv.finish_turn(it, {"result": "holds up\n\n<callouts>\n1. [P1] a call\n</callouts>"},
                    None, time.time(), "finalize", False)
    assert srv.DEFERRED.empty() and "landing_compact" not in it
    assert it["state"] == srv.NEEDS_REVIEW


def test_the_compact_job_reads_the_setting_when_it_runs(srv, monkeypatch):
    it, sent, drain = landing_item(srv, monkeypatch)
    srv.finish_turn(it, {"result": "holds up\n\n<callouts>\n1. [P1] a call\n</callouts>"},
                    None, time.time(), "finalize", False)
    srv.act_auto({"compact_landing": False})
    assert not drained(drain, lambda: sent, wait=0.3)
    assert "auto_compacted" not in it


def test_a_turn_since_the_landing_takes_precedence_over_the_compact(srv, monkeypatch):
    it, sent, drain = landing_item(srv, monkeypatch)
    srv.finish_turn(it, {"result": "holds up\n\n<callouts>\n1. [P1] a call\n</callouts>"},
                    None, time.time(), "finalize", False)
    srv.PROCS[("a", "finalize")]["turn_seq"] = 5
    assert not drained(drain, lambda: sent, wait=0.3)


def test_a_compact_filed_without_a_turn_number_waits_out_a_turn_the_user_opened(srv, monkeypatch):
    """The refusal path files the compact with its worker gone. A comment
    the user sends before the job runs opens a turn on a fresh worker, and
    the compact must not be sent into it."""
    it, sent, drain = landing_item(srv, monkeypatch, callout_wait="finalize",
                                   landing_compact="finalize",
                                   refused={"finalize": {"callout": 2}},
                                   reports={"finalize": "the report"})
    w = srv.PROCS.pop(("a", "finalize"))
    w["state"] = "dying"
    srv.recover_refusal(w, "callout", None)
    assert srv.DEFERRED.queue[0] == ("compact", "a", "finalize", None)
    fresh = worker(srv, it, phase="finalize")
    fresh["state"], fresh["turn_seq"] = "running", 1
    it["state"] = srv.COMMENTED
    assert not drained(drain, lambda: sent, wait=0.3)
    assert "auto_compacted" not in it


def test_a_compact_already_done_is_not_sent_again_on_landing(srv, monkeypatch):
    it, sent, drain = landing_item(srv, monkeypatch, callout_wait="finalize",
                                   landing_compact="finalize",
                                   refused={"finalize": {"callout": 2}},
                                   reports={"finalize": "the report"})
    w = srv.PROCS.pop(("a", "finalize"))
    w["state"] = "dying"
    srv.recover_refusal(w, "callout", None)
    it["auto_compacted"] = {"finalize": True}
    assert not drained(drain, lambda: sent, wait=0.3)


def test_a_finalize_the_user_ran_by_hand_is_not_compacted_on_landing(srv, monkeypatch):
    it, sent, drain = landing_item(srv, monkeypatch)
    it.pop("auto_finalize")
    srv.finish_turn(it, {"result": "holds up\n\n<callouts>\n1. [P1] a call\n</callouts>"},
                    None, time.time(), "finalize", False)
    assert srv.DEFERRED.empty() and "landing_compact" not in it


def test_a_compact_cut_by_the_limit_arms_the_auto_compact_again(srv):
    srv.night()["on"] = True
    it = finalize_item(srv, "a", auto_compacted={"finalize": True})
    w = srv.PROCS[("a", "finalize")]
    w["state"], w["slash"] = "running", True
    srv.quota_cut(it, "finalize", False)
    assert it["auto_compacted"] == {}
    assert "resume_at" not in it
