"""Wave admission, the chain a wave runs, and the state a restart loads."""

import json

from .conftest import item, worker

# ---------- waves ----------

def test_wave_queues_k_items(srv):
    res = srv.start_wave(2)
    assert res["ids"] == ["t00", "t01"]
    assert srv.STATE["wave"] == 1
    assert [it["state"] for it in srv.STATE["items"]] == [srv.QUEUED, srv.QUEUED]


def test_a_wave_item_hands_itself_on_up_to_the_last_stage(srv):
    res = srv.start_wave(1)
    assert res["ids"] == ["t00"]
    it = srv.STATE["items"][0]
    assert it["auto_advance"] is True
    assert it["auto_stop"] == "finalize"
    assert srv.auto_advances(it, "create")
    assert not srv.auto_advances(it, "refine")


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


# ---------- the chain a wave runs ----------

def test_a_wave_runs_the_default_chain_unless_asked_otherwise(srv):
    srv.start_wave(1)
    plain = srv.find("t00")
    assert plain["chain"] == srv.default_chain()
    assert [st["name"] for st in plain["chain"]] == ["create", "refine", "finalize"]
    assert plain["sessions"] == {"create": None, "refine": None, "finalize": None}
    srv.LAST_WAVE_AT = 0.0
    srv.start_wave(1, chain=[
        {"name": "create", "backend": "codex", "model": "gpt-5.1-codex",
         "effort": "high"},
        {"name": "refine", "model": "claude-mythos-1"}])
    other = srv.find("t01")
    assert other["chain"] == [
        {"name": "create", "backend": "codex", "model": "gpt-5.1-codex",
         "effort": "high"},
        {"name": "refine", "backend": "claude", "model": "claude-mythos-1"}]
    assert other["auto_stop"] == "refine"


def test_the_pipeline_starts_at_opus_and_finalizes_on_fable(srv):
    assert srv.pipeline() == {"create": "opus", "refine": "opus"}
    assert [st["model"] for st in srv.default_chain()] == [
        srv.MODEL_IDS["opus"], srv.MODEL_IDS["opus"], srv.MODEL_IDS["fable"]]


def test_a_pipeline_setting_is_stored_but_the_next_wave_runs_the_default(srv):
    srv.start_wave(1)
    assert srv.act_pipeline({"refine": "fable"}) == {"ok": True}
    assert srv.pipeline() == {"create": "opus", "refine": "fable"}
    assert srv.find("t00")["chain"][1]["model"] == srv.MODEL_IDS["opus"]
    srv.LAST_WAVE_AT = 0.0
    srv.start_wave(1)
    assert srv.find("t01")["chain"][1]["model"] == srv.MODEL_IDS["opus"]
    # the setting outlives the process
    srv.STATE.update(json.loads(srv.STATE_FILE.read_text()))
    assert srv.pipeline() == {"create": "opus", "refine": "fable"}


def test_a_pipeline_setting_names_a_known_model(srv):
    assert "error" in srv.act_pipeline({"create": "codex"})
    srv.act_pipeline({"finalize": "opus"})   # not a settable stage: ignored
    assert srv.pipeline() == {"create": "opus", "refine": "opus"}


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
    assert it["pre"] == {"hash": "abc", "solver": "// old\n", "proposals": {},
                         "dirty": False,
                         "files": {"docs/wf-solver/proposals.md": "A\n"}}
    assert not {"hash_before", "snap", "snap_prop", "dirty_before", "turn_files"} & set(it)


def test_load_drops_the_entry_snapshots_a_landed_turn_left(srv):
    prop = "docs/wf-solver/proposals"
    saved = {"seq": 1, "wave": 1, "items": [{
        "id": "a", "state": srv.NEEDS_REVIEW, "dirty": False, "updated": False,
        "rev": 2, "feed": [], "ver": 0, "title": "", "phase": "refine",
        "sessions": {"create": "cs", "refine": "rs"}, "chain": srv.two_phase_chain(),
        "lastActive": {"create": None, "refine": None},
        "pre": {"hash": "", "solver": "", "dirty": False,
                "proposals": {f"{prop}/X.md": "A\n", f"{prop}/Y.md": "Y\n"},
                "files": {f"{prop}/X.md": "A\n"}},
        "prop_after": {f"{prop}/X.md": "A\nB\n", f"{prop}/Y.md": "Y\n"},
    }]}
    srv.STATE_FILE.write_text(json.dumps(saved))
    srv.load()
    it = srv.STATE["items"][0]
    assert it["pre"]["proposals"] == {}
    assert it["prop_after"] == {f"{prop}/X.md": "A\nB\n"}


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
        {"name": "create", "backend": "claude", "model": srv.MODEL_IDS["opus"]},
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
