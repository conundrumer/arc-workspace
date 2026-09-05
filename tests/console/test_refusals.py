"""A report ask the model's safeguards refused, and the retries it gets."""

import json
import time

import pytest

from .conftest import item, transcript, worker


def test_a_safeguard_refusal_is_named_in_the_feed(srv):
    text = ("API Error: Opus 5's safeguards flagged this message (https://x). "
            "This sometimes happens with safe, normal conversations.\n\n"
            "Details: `[reasoning_extraction]`\n\nRequest ID: req_1")
    note = srv.failure_note({"result": text}, "api_error")
    assert note.startswith("turn refused by the model's safeguards (reasoning_extraction)")
    assert "fresh session" in note
    assert srv.failure_note({"result": "overloaded"}, "api_error") == "turn failed (api_error)"


REFUSAL = ("API Error: Fable 5's safeguards flagged this message (https://x). "
           "This sometimes happens with safe, normal conversations.\n\n"
           "Details: `[reasoning_extraction]`\n\nRequest ID: req_2")


def refused_result(srv, it, trigger, ask="the ask", handoff=False):
    w = worker(srv, it, state="running")
    w.update(started=time.time(), trigger=trigger, handoff=handoff, ask=ask)
    srv.handle_event(w, {"type": "result", "terminal_reason": "api_error",
                         "result": REFUSAL}, None)
    return w


@pytest.mark.parametrize("trigger, kind", [("handoff", "handoff"), ("bail", "handoff"),
                                           ("callout", "callout")])
def test_a_refused_report_ask_hands_the_worker_to_recovery(srv, monkeypatch,
                                                           trigger, kind):
    monkeypatch.setattr(srv, "ensure_drain", lambda: None)
    it = item(srv, "a", srv.RUNNING)
    w = refused_result(srv, it, trigger, handoff=kind == "handoff")
    assert srv.PROCS.get(("a", "refine")) is None
    assert w["state"] == "dying"
    assert srv.DEFERRED.get_nowait() == ("refuse", w, kind, "the ask")
    assert it["state"] == srv.RUNNING            # the stage is still at work
    assert it["respawn_wait"] == "refine" and srv.active(it)
    note = [m["text"] for m in it["feed"] if "safeguards" in m["text"]][0]
    assert "(reasoning_extraction)" in note and "fresh session" not in note


def test_the_relaunch_window_reads_as_busy(srv, monkeypatch):
    """No worker sits in PROCS between the detach and the fresh spawn, so
    the mark is what keeps a comment, an action, and a reload off the
    session until the relaunch lands."""
    it = item(srv, "a", srv.RUNNING, respawn_wait="refine")
    assert srv.active(it)
    with srv.LOCK:
        assert srv.turns_in_flight()
    assert "relaunch in flight" in srv.act_comment("a", "one more thing")["error"]
    assert "busy" in srv.act_session("a", "refine", "other")["error"]
    assert srv.light_items()[0]["active"] is True


def test_a_refused_user_comment_lands_for_the_user(srv, monkeypatch):
    monkeypatch.setattr(srv, "ensure_drain", lambda: None)
    it = item(srv, "a", srv.COMMENTED)
    w = refused_result(srv, it, None)
    assert srv.PROCS.get(("a", "refine")) is w and w["state"] == "idle"
    assert srv.DEFERRED.empty()
    assert it["state"] == srv.NEEDS_REVIEW
    assert any("fresh session" in m["text"] for m in it["feed"])


def user_row(text, **kw):
    return {"type": "user", "message": {"role": "user", "content": text}, **kw}


def test_strip_ask_cuts_the_transcript_back_to_before_the_ask(srv, monkeypatch,
                                                              tmp_path):
    kept = [user_row("first turn"), {"type": "assistant", "message": {"content": []}}]
    blocks = user_row([{"type": "text", "text": "the ask"}])
    path = transcript(srv, monkeypatch, tmp_path, "sess-a", kept + [
        user_row("the ask", isSidechain=True),     # a subagent's own row
        blocks, {"type": "assistant", "isApiErrorMessage": True,
                 "message": {"content": [{"type": "text", "text": REFUSAL}]}}])
    assert srv.strip_ask(path, "the ask") == 2
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows == kept + [user_row("the ask", isSidechain=True)]
    assert srv.strip_ask(path, "the ask") == 0      # the sidechain row is not the ask


def test_recovery_cuts_the_ask_and_asks_again_in_plainer_words(srv, monkeypatch,
                                                              tmp_path):
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, **kw: sent.append((msg, phase, kw)))
    it = item(srv, "a", srv.RUNNING, respawn_wait="refine")
    w = worker(srv, it, state="dying")
    srv.PROCS.pop(("a", "refine"))
    path = transcript(srv, monkeypatch, tmp_path, "sess-a",
                      [user_row("first turn"), user_row("the ask")])
    srv.recover_refusal(w, "handoff", "the ask")
    assert path.read_text().count("\n") == 1
    assert any("cut from the transcript" in m["text"] for m in it["feed"])
    assert it["refused"] == {"refine": {"handoff": 1}}
    assert it["state"] == srv.RUNNING
    assert "respawn_wait" not in it
    assert sent == [(srv.REFUSED_HANDOFF_BRIEF, "refine",
                     {"trigger": "handoff", "handoff": True, "admitted": True})]
    assert srv.stage_of(it, "refine")["model"] != srv.REFUSAL_MODEL


def test_recovery_without_a_session_lands_the_turn(srv, monkeypatch):
    monkeypatch.setattr(srv, "launch", lambda *a, **kw: pytest.fail("asked again"))
    it = item(srv, "a", srv.RUNNING, sessions={"create": None, "refine": None},
              respawn_wait="refine", callout_wait="refine")
    w = worker(srv, it, state="dying")
    srv.PROCS.pop(("a", "refine"))
    srv.recover_refusal(w, "handoff", "the ask")
    assert it["state"] == srv.QUEUED
    assert "refused" not in it
    assert "respawn_wait" not in it and "callout_wait" not in it
    assert any("no session" in m["text"] for m in it["feed"])


def test_a_second_refusal_moves_the_stage_to_the_fallback_model(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, **kw: sent.append((msg, phase, kw)))
    it = item(srv, "a", srv.RUNNING, callout_wait="refine",
              refused={"refine": {"callout": 1}})
    w = worker(srv, it, state="dying")
    srv.PROCS.pop(("a", "refine"))
    srv.recover_refusal(w, "callout", None)
    assert srv.stage_of(it, "refine")["model"] == srv.REFUSAL_MODEL
    assert srv.stage_of(it, "create")["model"] != srv.REFUSAL_MODEL
    assert it["callout_wait"] == "refine"
    assert sent == [(srv.refused_callout_brief(), "refine",
                     {"trigger": "callout", "admitted": True})]
    assert any(srv.REFUSAL_MODEL in m["text"] for m in it["feed"])


def test_a_third_refusal_lands_the_handoff_on_the_sessions_last_text(srv, monkeypatch):
    monkeypatch.setattr(srv, "launch", lambda *a, **kw: pytest.fail("asked again"))
    it = item(srv, "a", srv.RUNNING, refused={"refine": {"handoff": 2}},
              feed=[{"kind": "worker", "text": "an aside", "sess": "create"},
                    {"kind": "worker", "text": "the pass as it ended", "sess": "refine"},
                    {"kind": "worker", "text": "a subagent", "sess": "refine", "sub": True}])
    w = worker(srv, it, state="dying")
    srv.PROCS.pop(("a", "refine"))
    srv.recover_refusal(w, "handoff", None)
    assert it["reports"] == {"refine": "the pass as it ended"}
    assert srv.report_path("a", "refine").read_text() == "the pass as it ended"
    assert it["state"] == srv.NEEDS_REVIEW and it["updated"] is True
    assert "callout_wait" not in it


def test_a_third_refusal_lands_the_callouts_unwritten(srv, monkeypatch):
    monkeypatch.setattr(srv, "launch", lambda *a, **kw: pytest.fail("asked again"))
    it = item(srv, "a", srv.RUNNING, callout_wait="refine",
              refused={"refine": {"callout": 2}}, reports={"refine": "the report"})
    w = worker(srv, it, state="dying")
    srv.PROCS.pop(("a", "refine"))
    srv.recover_refusal(w, "callout", None)
    assert it["reports"] == {"refine": "the report"}
    assert "callout_wait" not in it
    assert it["state"] == srv.NEEDS_REVIEW
    assert any("stands without them" in m["text"] for m in it["feed"])
