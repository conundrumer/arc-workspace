"""A turn from its launch to its landing: the moves it makes by itself,
what it spent, and the transcript the console reads."""

import json
import sys
import time

import pytest

from .conftest import (
    TICK,
    codex_item,
    create_item,
    finalize_item,
    item,
    land_report,
    night_workers,
    tagged,
    transcript,
    worker,
)

# ---------- the automatic moves ----------

def test_auto_finalize_lifts_the_stop_before_finalize(srv):
    srv.start_wave(1)
    it = srv.find("t00")
    assert not srv.auto_advances(it, "refine")
    assert srv.act_auto({"finalize": True}) == {"ok": True}
    # read at landing time, so an item already in flight hands on too
    assert srv.auto_advances(it, "refine")
    assert it["auto_stop"] == "finalize"
    # the setting outlives the process
    srv.STATE.update(json.loads(srv.STATE_FILE.read_text()))
    assert srv.auto() == {"finalize": True, "compact": False, "compact_landing": False}


def test_auto_finalize_leaves_a_stop_before_another_stage(srv):
    srv.act_auto({"finalize": True})
    srv.start_wave(1, chain=[{"name": "create"}, {"name": "refine"}])
    it = srv.find("t00")
    assert it["auto_stop"] == "refine"
    assert not srv.auto_advances(it, "create")


def test_auto_compact_fires_within_the_margin(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, **kw: sent.append((msg, phase)))
    srv.act_auto({"compact": True})
    early = finalize_item(srv, "a", idle_for=srv.IDLE_TTL - srv.COMPACT_MARGIN - 60)
    due = finalize_item(srv, "b", idle_for=srv.IDLE_TTL - srv.COMPACT_MARGIN + 1)
    srv.auto_compact()
    assert sent == [("/compact", "finalize")]
    assert "auto_compacted" not in early
    assert due["auto_compacted"] == {"finalize": True}
    assert "auto compact" in due["feed"][-1]["text"]
    # once per real turn: the check does not fire again on the same session
    srv.auto_compact()
    assert len(sent) == 1


def test_auto_compact_is_off_until_set(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, **kw: sent.append((msg, phase)))
    finalize_item(srv, "a", idle_for=srv.IDLE_TTL)
    srv.auto_compact()
    assert sent == []


def test_auto_compact_leaves_settled_and_busy_sessions_alone(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, **kw: sent.append((it["id"], msg)))
    srv.act_auto({"compact": True})
    finalize_item(srv, "approved", state=srv.APPROVED, idle_for=srv.IDLE_TTL)
    finalize_item(srv, "held", idle_for=srv.IDLE_TTL, callout_wait="finalize")
    running = finalize_item(srv, "running", idle_for=srv.IDLE_TTL)
    srv.PROCS[("running", "finalize")]["state"] = "running"
    reaped = finalize_item(srv, "reaped", idle_for=srv.IDLE_TTL)
    del srv.PROCS[("reaped", "finalize")]
    refine = item(srv, "refine", srv.NEEDS_REVIEW, chain=srv.default_chain())
    worker(srv, refine)["idle_since"] = time.time() - srv.IDLE_TTL
    srv.auto_compact()
    assert sent == []
    assert all("auto_compacted" not in it for it in (running, reaped, refine))


def test_the_idle_reap_compacts_a_covered_session_first(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, **kw: sent.append((msg, phase)))
    reaped = []
    monkeypatch.setattr(srv, "queue_reap", reaped.append)
    srv.act_auto({"compact": True})
    it = finalize_item(srv, "a", idle_for=srv.IDLE_TTL + 1)
    srv.reap_idle()
    assert sent == [("/compact", "finalize")] and reaped == []
    assert ("a", "finalize") in srv.PROCS
    assert "before the worker is reaped" in it["feed"][-1]["text"]
    # compacted, the session is the reap's on the next pass
    srv.reap_idle()
    assert len(sent) == 1 and [w["item_id"] for w in reaped] == ["a"]


def test_the_night_cap_compacts_a_covered_session_first(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, **kw: sent.append((it["id"], msg)))
    reaped = []
    monkeypatch.setattr(srv, "queue_reap", reaped.append)
    monkeypatch.setattr(srv, "NIGHT_WORKER_CAP", 1)
    srv.act_auto({"compact": True})
    finalize_item(srv, "old", idle_for=300, night=True)
    night_workers(srv, [100])
    srv.reap_idle()
    assert sent == [("old", "/compact")] and reaped == []
    srv.reap_idle()
    assert len(sent) == 1 and [w["item_id"] for w in reaped] == ["old"]


def test_a_slash_turn_cut_by_quota_is_not_resumed(srv):
    srv.night()["on"] = True
    it = item(srv, "a", srv.NEEDS_REVIEW)
    worker(srv, it, state="running")["slash"] = True
    srv.quota_cut(it, "refine", False)
    assert "resume_phase" not in it and "resume_at" not in it
    assert it["feed"][-1]["text"] == "usage limit"


def test_a_real_landing_arms_the_auto_compact_again(srv, monkeypatch):
    monkeypatch.setattr(srv, "launch", lambda *a, **kw: None)
    srv.act_auto({"compact": True})
    it = finalize_item(srv, "a", idle_for=srv.IDLE_TTL)
    srv.auto_compact()
    assert it["auto_compacted"] == {"finalize": True}
    w = srv.PROCS[("a", "finalize")]
    w["slash"] = True
    srv.finish_turn(it, {"result": "compacted"}, None, time.time(), "finalize", False)
    assert it["auto_compacted"] == {"finalize": True}
    w["slash"] = False
    srv.finish_turn(it, {"result": "a reply"}, None, time.time(), "finalize", False)
    assert it["auto_compacted"] == {}


def test_a_compact_the_user_asked_for_disarms_the_auto_compact(srv, monkeypatch):
    launched = []
    monkeypatch.setattr(srv, "launch", lambda it, msg, *a, **kw: launched.append(msg))
    srv.act_auto({"compact": True})
    it = finalize_item(srv, "a")
    w = srv.PROCS[("a", "finalize")]
    srv.handle_event(w, {"type": "system", "subtype": "compact_boundary",
                         "compact_metadata": {"pre_tokens": 180000, "post_tokens": 12000,
                                              "cumulative_dropped_tokens": 168000}}, None)
    assert it["auto_compacted"] == {"finalize": True}
    w["idle_since"] = time.time() - srv.IDLE_TTL
    srv.auto_compact()
    assert launched == []


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
        srv.finish_turn(it, {"result": tagged(f"report from {phase}")}, None,
                        time.time(), phase, True)
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


def test_worker_cmd_for_a_claude_stage_carries_the_effort(srv, tmp_path, monkeypatch):
    monkeypatch.setattr(srv, "FAKE", False)
    append = tmp_path / "append.md"
    append.write_text("brief")
    it = codex_item(srv, "a", srv.NEEDS_REVIEW, append=str(append))
    cmd = srv.worker_cmd(it, "refine")
    assert cmd[cmd.index("--effort") + 1] == srv.CLAUDE_EFFORT == "high"
    it["chain"][1]["effort"] = "low"
    cmd = srv.worker_cmd(it, "refine")
    assert cmd[cmd.index("--effort") + 1] == "low"


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


def test_a_compact_starts_the_cache_baseline_over(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW)
    srv.finish_turn(it, usage_result(180000), None, time.time(), "refine", False)
    w = worker(srv, it, state="running")
    srv.handle_event(w, {"type": "system", "subtype": "compact_boundary",
                         "compact_metadata": {"pre_tokens": 180000, "post_tokens": 12000,
                                              "cumulative_dropped_tokens": 168000}}, None)
    srv.finish_turn(it, usage_result(180000), None, time.time(), "refine", False)
    assert "refine" not in it["cache_read"]
    srv.start_turn(it, w, "refine")
    srv.finish_turn(it, usage_result(12000), None, time.time(), "refine", False)
    assert "DROP" not in it["feed"][-1]["text"]
    assert it["cache_read"]["refine"] == 12000


def test_a_request_that_carried_nothing_is_no_drop(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW)
    srv.finish_turn(it, usage_result(28000), None, time.time(), "refine", False)
    srv.finish_turn(it, usage_result(0, 0, 0), None, time.time(), "refine", False)
    assert "DROP" not in it["feed"][-1]["text"]
    assert it["cache_read"]["refine"] == 28000


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
        time.sleep(TICK)
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
    it = item(srv, "a", srv.RUNNING, respawn_wait="refine")
    it["runaway"] = {"refine": 1}
    w = worker(srv, it, state="dying")
    path = transcript(srv, monkeypatch, tmp_path, "sess-a", [cap_row()])
    srv.PROCS.pop(("a", "refine"))
    srv.revive(w, "nudge", False)
    assert json.loads(path.read_text())["message"]["stop_reason"] == "end_turn"
    assert any("preserved" in m.get("text", "") for m in it["feed"])
    assert sent == [(srv.NUDGE_BRIEF, "refine")]
    assert "respawn_wait" not in it


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
    assert it["respawn_wait"] == "refine" and srv.active(it)


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


def test_append_carries_the_scratch_note_and_the_docs(srv):
    (srv.DOCS / "style.md").write_text("# Style\n\nEvery word of it.\n")
    out = srv.append_path().read_text()
    assert out.startswith("## Scratch")
    assert "# docs/wf-solver/style.md\n\n# Style\n\nEvery word of it.\n" in out


def test_worker_agents_carry_the_appendix(srv):
    (srv.DOCS / "style.md").write_text("# Style\n\nEvery word of it.\n")
    agents = json.loads(srv.worker_agents(str(srv.append_path())))
    assert set(agents) == {p.stem for p in srv.AGENT_DIR.glob("*.md")}
    for agent in agents.values():
        assert agent["prompt"].endswith(srv.append_path().read_text())


def test_commit_subject_names_added_and_changed_solvers(srv):
    assert srv.commit_subject(["a", "b"], []) == "Add a, b"
    assert srv.commit_subject([], ["a"]) == "Update a"
    assert srv.commit_subject(["a"], ["b", "c"]) == "Add a; update b, c"


def test_seen_clears_the_updated_badge(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW, updated=True)
    srv.act_seen("a")
    assert it["updated"] is False
