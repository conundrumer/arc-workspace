"""The actions the user takes on an item, and what each one records."""

import json
import os
import time

from .conftest import PROP, item, worker, write_solver

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


def test_a_steer_carries_a_clean_pass_into_the_turn(srv):
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    srv.act_comment("a", "then cleanup")
    assert w["trigger"] == "cleanup"


def test_a_steer_leaves_the_turns_own_pass_alone(srv):
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


def test_a_comment_is_not_steered_into_a_slash_turn(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW)
    w = worker(srv, it, state="running")
    w["slash"] = True
    assert "busy" in srv.act_comment("a", "look again")["error"]
    assert w["outbound"].empty() and it["feed"] == []


def test_a_side_turn_reads_its_own_slash_flag(srv):
    """A compact on one session and a comment on another run at once; the
    comment's landing must not be read as a slash turn's."""
    it = item(srv, "a", srv.NEEDS_REVIEW, chain=srv.default_chain(),
              sessions={"create": "cs", "refine": "rs", "finalize": "fs"},
              phase="finalize")
    worker(srv, it, phase="finalize")
    srv.act_compact("a", "finalize")
    worker(srv, it, phase="refine")
    srv.act_comment("a", "look again", "refine")
    assert srv.slash_turn(it, "finalize") and not srv.slash_turn(it, "refine")


# ---------- task-local comps ----------

def test_comps_beyond_the_stock_two_are_flagged_by_proposal(srv):
    write_solver(srv, "a", ".comp Params {\n}\n.comp CornerDist {\n}\n"
                           ".comp Wallpaper<Key> {\n}\n.comp Determine {\n}\n")
    (srv.DOCS / "proposals").mkdir()
    (srv.DOCS / "proposals" / "CornerDist.md").write_text("# CornerDist\n\nstaged here.\n")
    it = item(srv, "a", srv.RUNNING)
    srv.finish_turn(it, {"result": ""}, None, time.time(), "refine", False)
    assert it["comps"] == ["CornerDist", "Wallpaper"]
    assert it["comps_unproposed"] == ["Wallpaper"]
    light = srv.light_items()[0]
    assert light["comps"] == ["CornerDist", "Wallpaper"]
    assert light["comps_unproposed"] == ["Wallpaper"]


def test_a_stock_solver_flags_no_comps(srv):
    write_solver(srv, "a", ".comp Params {\n}\n.comp Parse<Key> {\n}\n"
                           ".init params = Params\n.comp Determine {\n}\n")
    it = item(srv, "a", srv.RUNNING)
    srv.finish_turn(it, {"result": ""}, None, time.time(), "refine", False)
    assert it["comps"] == []


# ---------- revert ----------


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


def write_prop(srv, name, text):
    (srv.DOCS / "proposals").mkdir(exist_ok=True)
    (srv.DOCS / "proposals" / f"{name}.md").write_text(text)


def test_revert_restores_the_entry_this_turn_edited(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW, prop_after={f"{PROP}/X.md": "A\nB\n"})
    it["pre"] = {"hash": "", "solver": "// before\n",
                 "proposals": {f"{PROP}/X.md": "A\n"}, "dirty": False, "files": {}}
    write_prop(srv, "X", "A\nB\n")
    write_solver(srv, "a", "// after\n")
    srv.act_revert("a")
    assert srv.prop_text() == "A\n"
    assert f"{PROP}/X.md" in it["reverted"]["files"]


def test_revert_deletes_the_entry_this_turn_wrote(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW, prop_after={f"{PROP}/New.md": "new\n"})
    it["pre"] = {"hash": "", "solver": "// before\n", "proposals": {},
                 "dirty": False, "files": {}}
    write_prop(srv, "New", "new\n")
    write_solver(srv, "a", "// after\n")
    srv.act_revert("a")
    assert srv.prop_files() == {}
    assert f"{PROP}/New.md" in it["reverted"]["files"]


def test_revert_leaves_an_entry_another_worker_touched(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW, prop_after={f"{PROP}/X.md": "A\nB\n"})
    it["pre"] = {"hash": "", "solver": "// before\n",
                 "proposals": {f"{PROP}/X.md": "A\n"}, "dirty": False, "files": {}}
    write_prop(srv, "X", "A\nB\nC\n")  # a later turn appended
    write_solver(srv, "a", "// after\n")
    srv.act_revert("a")
    assert srv.prop_text() == "A\nB\nC\n"
    assert it["reverted"]["files"] == ["programs/solvers/a.dl"]


# ---------- entries a task adds ----------

def test_an_entry_the_turn_added_stays_with_the_task(srv):
    it = item(srv, "a", srv.RUNNING)
    it["pre"] = {"hash": "", "solver": "", "proposals": {}, "dirty": False,
                 "files": {f"{PROP}/Border.md": ""}, "watched": srv.watched_hashes("a")}
    write_prop(srv, "Border", "# Border\n")
    srv.finish_turn(it, {"result": ""}, None, time.time(), "refine", False)
    assert it["entries"] == [f"{PROP}/Border.md"]
    assert srv.light_items()[0]["entries"] == ["Border"]
    row = [r for r in srv.ledger_rows() if r["task"] == "a"][-1]
    assert row["entries"] == [f"{PROP}/Border.md"]
    # a later turn that only edits the entry adds nothing, and drops nothing
    it["pre"] = {"hash": "", "solver": "", "proposals": srv.prop_files(),
                 "dirty": False, "files": {}, "watched": srv.watched_hashes("a")}
    write_prop(srv, "Border", "# Border\n\nmore\n")
    srv.finish_turn(it, {"result": ""}, None, time.time(), "refine", False)
    assert it["entries"] == [f"{PROP}/Border.md"]
    assert "entries" not in [r for r in srv.ledger_rows() if r["task"] == "a"][-1]


def test_an_entry_a_concurrent_turn_added_stays_with_that_turn(srv):
    it = item(srv, "a", srv.RUNNING)
    it["pre"] = {"hash": "", "solver": "", "proposals": {}, "dirty": False,
                 "files": {}, "watched": srv.watched_hashes("a")}
    write_prop(srv, "Other", "# Other\n")  # another task's turn wrote it
    srv.finish_turn(it, {"result": ""}, None, time.time(), "refine", False)
    assert "entries" not in it
    assert "entries" not in [r for r in srv.ledger_rows() if r["task"] == "a"][-1]


def test_an_item_from_before_entries_takes_them_from_the_ledger(srv):
    old = item(srv, "a", srv.NEEDS_REVIEW)
    kept = item(srv, "b", srv.NEEDS_REVIEW, entries=[f"{PROP}/Kept.md"])
    srv.ledger_append({"task": "a", "stage": "legacy", "source": "backfill",
                       "entries": [f"{PROP}/Border.md"]})
    srv.ledger_append({"task": "b", "stage": "legacy", "source": "backfill",
                       "entries": [f"{PROP}/Other.md"]})
    srv.seed_entries()
    assert old["entries"] == [f"{PROP}/Border.md"]
    assert kept["entries"] == [f"{PROP}/Kept.md"]     # its own list stands
    old["entries"] = []
    srv.seed_entries()
    assert old["entries"] == []                        # seeded once


def test_the_entry_keeps_its_tab_after_the_turn(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW, entries=[f"{PROP}/Border.md"])
    write_solver(srv, "a", "// v1\n")
    write_prop(srv, "Border", "# Border\n")
    # the turn's own edits are gone from the snapshot; the entry still lists
    it["pre"] = {"hash": "", "solver": "// v1\n", "proposals": srv.prop_files(),
                 "dirty": False, "files": {}}
    paths = [f["path"] for f in srv.item_files(it)]
    assert paths == ["programs/solvers/a.dl", f"{PROP}/Border.md"]
    assert srv.item_files(it)[1]["code"] == "# Border\n"
    # an entry gone from disk has no tab
    it["entries"] = [f"{PROP}/Gone.md"]
    assert [f["path"] for f in srv.item_files(it)] == ["programs/solvers/a.dl"]


# ---------- shared-file writes ----------

def test_a_turn_that_changes_a_shared_file_gets_flagged(srv):
    (srv.DOCS / "keywords.md").write_text("enclose: the old sense\n")
    it = item(srv, "a", srv.RUNNING)
    it["pre"] = {"hash": "", "solver": "", "proposals": "", "dirty": False,
                 "files": {}, "watched": srv.watched_hashes("a")}
    (srv.DOCS / "keywords.md").write_text("enclose: a new sense\n")
    srv.finish_turn(it, {"result": ""}, None, time.time(), "refine", False)
    assert it["shared_writes"] == ["docs/wf-solver/keywords.md"]
    assert any(e["kind"] == "event" and "shared files changed" in e["text"]
               for e in it["feed"])
    assert srv.light_items()[0]["shared_writes"] == ["docs/wf-solver/keywords.md"]


def bash_call(command):
    return {"type": "assistant", "message": {"id": "m9", "content": [
        {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": command}}]}}


def test_a_shared_file_no_call_named_changed_under_the_user(srv):
    (srv.DOCS / "keywords.md").write_text("old\n")
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    srv.handle_event(w, bash_call("grep -n enclose programs/solvers/a.dl"), None)
    it["pre"] = {"hash": "", "solver": "", "proposals": "", "dirty": False,
                 "files": {}, "watched": srv.watched_hashes("a")}
    (srv.DOCS / "keywords.md").write_text("new\n")
    srv.finish_turn(it, {"result": ""}, None, time.time(), "refine", False)
    assert it.get("shared_writes", []) == []


def test_a_shared_file_a_call_named_is_the_turns_write(srv):
    (srv.DOCS / "keywords.md").write_text("old\n")
    it = item(srv, "a", srv.RUNNING)
    w = worker(srv, it, state="running")
    it["pre"] = {"hash": "", "solver": "", "proposals": "", "dirty": False,
                 "files": {}, "watched": srv.watched_hashes("a")}
    srv.handle_event(w, bash_call("sed -i '' 's/old/new/' docs/wf-solver/keywords.md"), None)
    (srv.DOCS / "keywords.md").write_text("new\n")
    srv.finish_turn(it, {"result": ""}, None, time.time(), "refine", False)
    assert it["shared_writes"] == ["docs/wf-solver/keywords.md"]


def test_a_solver_only_turn_flags_no_shared_write(srv):
    (srv.DOCS / "keywords.md").write_text("stable\n")
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
    assert srv.ruled(rows) == set()


def test_a_ruling_takes_a_task_off_the_lens(srv):
    srv.ledger_append({"task": "c", "stage": "finalize", "model": "claude-fable-5"})
    srv.ledger_append({"task": "d", "stage": "approved", "model": None, "source": "user"})
    srv.ledger_append({"task": "e", "stage": "dismissed", "model": None, "source": "user"})
    assert srv.ruled(srv.ledger_rows()) == {"d", "e"}


def test_the_passes_name_the_model_of_each_stage_latest_landing(srv):
    srv.ledger_append({"task": "a", "stage": "refine", "model": "claude-opus-5", "ts": 2})
    srv.ledger_append({"task": "a", "stage": "create", "model": "claude-opus-5", "ts": 1})
    srv.ledger_append({"task": "a", "stage": "refine", "model": "claude-fable-5", "ts": 3})
    srv.ledger_append({"task": "a", "stage": "approved", "model": None, "ts": 4})
    srv.ledger_append({"task": "b", "stage": "legacy", "model": "claude-fable-5", "ts": 1})
    srv.ledger_append({"task": "b", "stage": "create", "backend": "codex",
                       "model": "gpt-5.6-sol", "ts": 2})
    assert srv.passes_of(srv.ledger_rows()) == {
        "a": [{"stage": "create", "model": "opus"}, {"stage": "refine", "model": "fable"}],
        "b": [{"stage": "legacy", "model": "fable"}, {"stage": "create", "model": "codex"}]}


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


# ---------- debrief ----------

def test_a_debrief_records_when_it_ran(srv, monkeypatch):
    assert srv.debriefed() == 0
    monkeypatch.setattr(srv, "now", lambda: 900.0)
    assert srv.act_debrief() == {"ok": True, "ts": 900}
    assert srv.debriefed() == 900
    assert json.loads(srv.DEBRIEF_FILE.read_text()) == {"ts": 900}


def test_a_debrief_lists_the_tasks_whose_callouts_landed_since_the_mark(srv, monkeypatch):
    monkeypatch.setattr(srv, "now", lambda: 900.0)
    srv.act_debrief()
    # a's refine callouts landed before the mark; its finalize turns since
    # filed no report, so the mark already covers what it carries
    srv.save_report("a", "refine", "done\n\n## Callouts\n\n- [P2] read already\n")
    os.utime(srv.report_path("a", "refine"), (850, 850))
    srv.ledger_append({"task": "a", "stage": "finalize", "ts": 950})
    # b's callout turn rewrote its report after the mark
    srv.save_report("b", "create", "done\n\n## Callouts\n\n- [P2] a doc gap\n")
    os.utime(srv.report_path("b", "create"), (950, 950))
    # c's report is filed and its callout turn has not landed yet
    srv.save_report("c", "create", "done\n")
    os.utime(srv.report_path("c", "create"), (960, 960))
    assert srv.debrief_view() == {
        "debriefed": 900,
        "items": [{"id": "b", "title": "", "ts": 950, "callouts": ["[P2] a doc gap"]}]}


def test_a_flag_level_is_held_to_the_three(srv):
    assert "level" in srv.act_flag({"id": "a", "level": 4})["error"]
    assert "level" in srv.act_flag({"id": "a", "level": "high"})["error"]
    assert srv.act_flag({"id": "", "level": 1})["error"] == "no task id"
    assert srv.flags() == {}


# ---------- committer feed ----------

def test_committer_entries_read_what_the_session_says_and_runs(srv):
    ev = {"type": "assistant", "message": {"id": "m1", "content": [
        {"type": "text", "text": "grouping the doc edits"},
        {"type": "tool_use", "id": "t1", "name": "Bash",
         "input": {"command": "git add docs/wf-solver/style.md"}},
        {"type": "tool_use", "id": "t2", "name": "ToolSearch", "input": {}}]}}
    keys_entries = srv.committer_entries(ev)
    assert [e for _, e in keys_entries] == [
        {"kind": "worker", "text": "grouping the doc edits"},
        {"kind": "tool", "text": "Bash git add docs/wf-solver/style.md"}]
    # a message's blocks arrive one event at a time, each repeating the message
    assert len({k for k, _ in keys_entries}) == 2
    assert srv.committer_entries({"type": "result", "result": "done"}) == []
