"""Review console: wave admission, item actions, and state loading.

The console module is loaded fresh per test with CONSOLE_STATE_DIR pointed at a
tmp dir, so its module-level state and paths never touch the real workspace.
"""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER_PY = ROOT / "tools" / "console" / "server.py"


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
    monkeypatch.setattr(s, "build_append", lambda wave: s.STATE_DIR / "append.md")
    monkeypatch.setattr(s, "stagger_launch", lambda ids: None)
    return s


def item(s, item_id, state, **kw):
    """Append an item the way start_wave does, then override for the test."""
    it = {"id": item_id, "est": 10, "wave": 1, "state": state, "session": "sess-" + item_id,
          "dirty": False, "updated": False, "rev": 1, "lastActive": None, "title": "",
          "feed": [], "append": "", "ver": 0}
    it.update(kw)
    s.STATE["items"].append(it)
    return it


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
    item(srv, "a", srv.NEEDS_REVIEW)
    srv.PROCS["a"] = object()
    assert "busy" in srv.act_comment("a", "tighten the join")["error"]
    assert "busy" in srv.act_approve("a")["error"]
    assert "busy" in srv.act_revert("a")["error"]


def test_comment_needs_a_session(srv):
    item(srv, "a", srv.NEEDS_REVIEW, session=None)
    assert srv.act_comment("a", "hi")["error"] == "no session yet"


def test_console_actions_are_not_worker_messages(srv):
    item(srv, "a", srv.NEEDS_REVIEW)
    assert "console action" in srv.act_comment("a", "commit")["error"]


def test_comment_launches_a_follow_up_turn(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch", lambda it, msg, trig=None: sent.append((msg, trig)))
    it = item(srv, "a", srv.NEEDS_REVIEW)
    assert srv.act_comment("a", "cleanup please") == {"ok": True}
    assert sent == [("cleanup please", "cleanup")]
    assert it["state"] == srv.COMMENTED
    assert it["feed"][-1] == {"kind": "you", "text": "cleanup please"}


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
    assert it["reverted"] == ["programs/solvers/a.dl"]


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
    assert "docs/wf-solver/proposals.md" in it["reverted"]


def test_revert_leaves_proposals_another_worker_touched(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW, prop_after="A\nB\n")
    it["pre"] = {"hash": "", "solver": "// before\n", "proposals": "A\n",
                 "dirty": False, "files": {}}
    (srv.DOCS / "proposals.md").write_text("A\nB\nC\n")  # a later turn appended
    write_solver(srv, "a", "// after\n")
    srv.act_revert("a")
    assert srv.prop_text() == "A\nB\nC\n"
    assert it["reverted"] == ["programs/solvers/a.dl"]


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

def test_active_covers_both_declared_and_draining_turns(srv):
    item(srv, "a", srv.RUNNING)
    item(srv, "b", srv.NEEDS_REVIEW)
    item(srv, "c", srv.NEEDS_REVIEW)
    srv.PROCS["c"] = object()  # result landed, stdout still draining
    assert {i["id"]: i["active"] for i in srv.light_items()} == {
        "a": True, "b": False, "c": True}
