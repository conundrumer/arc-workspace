"""The actions the user takes on an item, and what each one records."""

import json
import os
import signal
import threading
import time
import types

from .conftest import PROP, item, worker, write_solver

# ---------- actions ----------

def test_unknown_item_is_reported(srv):
    assert srv.act_approve("nope")["error"] == "unknown item"


def test_approve_and_withdraw(srv):
    """Approval takes the draft line out of the solver file, and withdrawing
    it puts the line back under the task-id line."""
    it = item(srv, "a", srv.NEEDS_REVIEW, updated=True)
    write_solver(srv, "a", "// a\n// draft\n// concept: tiles\n")
    assert srv.act_approve("a") == {"ok": True}
    assert it["state"] == srv.APPROVED
    assert it["updated"] is False
    assert srv.solver_text("a") == "// a\n// concept: tiles\n"
    assert srv.act_unapprove("a") == {"ok": True}
    assert it["state"] == srv.NEEDS_REVIEW
    assert srv.solver_text("a") == "// a\n// draft\n// concept: tiles\n"


def test_the_tag_goes_under_a_task_id_line_that_ends_the_file(srv):
    """A last line carries no newline of its own, and the tag still lands on a
    line of its own."""
    write_solver(srv, "a", "// a")
    assert srv.mark_draft("a") is True
    assert srv.solver_text("a") == "// a\n// draft\n"
    assert srv.is_draft("a")


def test_the_tag_is_written_in_one_step(srv):
    """A worker session, a souffle run, and the ref-note hook read the solver
    while the console retags it, and none of them sees a half-written file."""
    body = "// a\n" + "// filler\n" * 60000
    write_solver(srv, "a", body)
    short, stop = [], threading.Event()

    def read():
        p = srv.solver_path("a")
        while not stop.is_set():
            try:
                text = p.read_text()
            except OSError:
                continue
            if len(text) < len(body):
                short.append(len(text))
                return

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    for _ in range(200):
        srv.mark_draft("a")
        srv.clear_draft("a")
    stop.set()
    reader.join(3)
    assert short == []


def test_approve_needs_a_reviewable_item(srv):
    item(srv, "a", srv.QUEUED)
    assert srv.act_approve("a")["error"] == "nothing to approve"


def test_a_revert_refuses_while_a_turn_is_in_flight_and_an_approval_does_not(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW)
    worker(srv, it, state="running")
    assert "busy" in srv.act_revert("a")["error"]
    assert srv.act_approve("a")["ok"] is True
    assert it["state"] == srv.APPROVED


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
    # the snapshot is the file as the turn found it; the tag the landing put
    # on it belongs to the console, and only approval takes it off
    assert srv.solver_text("a") == "// before\n// draft\n"
    assert it["dirty"] is False
    assert it["reverted"] == {"files": ["programs/solvers/a.dl"], "phase": "refine"}


def test_a_revert_of_an_approved_solver_leaves_it_approved(srv):
    """Approval takes the tag off, and a revert of the turn that followed it
    puts back the file the user approved."""
    it = item(srv, "a", srv.APPROVED, dirty=False)
    it["pre"] = {"hash": "", "solver": "// a\n// concept: tiles\n", "proposals": "",
                 "dirty": False, "files": {}}
    write_solver(srv, "a", "// a\n// draft\n// concept: tiles, revised\n")
    assert srv.act_revert("a") == {"ok": True}
    assert srv.solver_text("a") == "// a\n// concept: tiles\n"


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
    it["pre"] = {"hash": "", "solver": "// before\n", "proposals": {},
                 "dirty": False, "files": {f"{PROP}/X.md": "A\n"}}
    write_prop(srv, "X", "A\nB\n")
    write_solver(srv, "a", "// after\n")
    srv.act_revert("a")
    assert srv.prop_text() == "A\n"
    assert f"{PROP}/X.md" in it["reverted"]["files"]


def test_revert_deletes_the_entry_this_turn_wrote(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW, prop_after={f"{PROP}/New.md": "new\n"})
    it["pre"] = {"hash": "", "solver": "// before\n", "proposals": {},
                 "dirty": False, "files": {f"{PROP}/New.md": ""}}
    write_prop(srv, "New", "new\n")
    write_solver(srv, "a", "// after\n")
    srv.act_revert("a")
    assert srv.prop_files() == {}
    assert f"{PROP}/New.md" in it["reverted"]["files"]


def test_revert_leaves_an_entry_another_worker_touched(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW, prop_after={f"{PROP}/X.md": "A\nB\n"})
    it["pre"] = {"hash": "", "solver": "// before\n", "proposals": {},
                 "dirty": False, "files": {f"{PROP}/X.md": "A\n"}}
    write_prop(srv, "X", "A\nB\nC\n")  # a later turn appended
    write_solver(srv, "a", "// after\n")
    srv.act_revert("a")
    assert srv.prop_text() == "A\nB\nC\n"
    assert it["reverted"]["files"] == ["programs/solvers/a.dl"]


def test_a_landing_keeps_only_the_entries_the_turn_edited(srv):
    write_prop(srv, "Other", "# Other\n")
    it = item(srv, "a", srv.RUNNING)
    it["pre"] = {"hash": "", "solver": "", "proposals": srv.prop_files(), "dirty": False,
                 "files": {f"{PROP}/Border.md": ""}, "watched": srv.watched_hashes("a")}
    write_prop(srv, "Border", "# Border\n")
    srv.finish_turn(it, {"result": ""}, None, time.time(), "refine", False)
    assert it["pre"]["proposals"] == {}
    assert it["prop_after"] == {f"{PROP}/Border.md": "# Border\n"}


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


def test_a_dismissal_takes_a_task_off_the_lens(srv):
    """Approval is the solver file's own, so the ledger rules only by a
    dismissal. The `approved` rows of the rounds before are read as rulings
    still, so they never count as landings."""
    srv.ledger_append({"task": "c", "stage": "finalize", "model": "claude-fable-5"})
    srv.ledger_append({"task": "d", "stage": "approved", "model": None, "source": "user"})
    srv.ledger_append({"task": "e", "stage": "dismissed", "model": None, "source": "user"})
    assert srv.ruled(srv.ledger_rows()) == {"e"}
    assert srv.passes_of(srv.ledger_rows()) == {
        "c": [{"stage": "finalize", "model": "fable"}]}


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


# ---------- retro ----------

def test_a_retro_records_when_it_ran(srv, monkeypatch):
    assert srv.retro_mark() == 0
    monkeypatch.setattr(srv, "now", lambda: 900.0)
    assert srv.act_retro() == {"ok": True, "ts": 900}
    assert srv.retro_mark() == 900
    assert json.loads(srv.RETRO_FILE.read_text()) == {"ts": 900}


def test_the_retro_mark_is_written_beside_the_file_and_renamed(srv, monkeypatch):
    """A reader that catches the console mid-write reads a whole mark. A mark
    read as 0 would widen the retro window to every task there is."""
    class Watched(type(srv.RETRO_FILE)):
        written = []

        def write_text(self, *args, **kw):
            Watched.written.append(self.name)
            return super().write_text(*args, **kw)

    monkeypatch.setattr(srv, "RETRO_FILE", Watched(srv.RETRO_FILE))
    monkeypatch.setattr(srv, "now", lambda: 900.0)
    srv.act_retro()
    assert Watched.written == ["retro.tmp"]
    assert srv.retro_mark() == 900


def test_a_retro_lists_the_tasks_whose_callouts_landed_since_the_mark(srv, monkeypatch):
    monkeypatch.setattr(srv, "now", lambda: 900.0)
    srv.act_retro()
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
    assert srv.retro_view() == {
        "retro_mark": 900,
        "items": [{"id": "b", "title": "", "ts": 950, "callouts": ["[P2] a doc gap"]}]}


def test_a_flag_level_is_held_to_the_three(srv):
    assert "level" in srv.act_flag({"id": "a", "level": 4})["error"]
    assert "level" in srv.act_flag({"id": "a", "level": "high"})["error"]
    assert srv.act_flag({"id": "", "level": 1})["error"] == "no task id"
    assert srv.flags() == {}


# ---------- commit ----------

def fake_git(srv, monkeypatch, status, head=""):
    """The git calls act_commit makes, recorded. A status call answers with
    the lines its pathspecs cover, as git's own filtering does."""
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        out = ""
        if cmd[1] == "ls-tree":
            out = head
        elif cmd[1] == "status":
            paths = cmd[cmd.index("--") + 1:]
            out = "".join(line + "\n" for line in status.splitlines()
                          if any(line[3:].startswith(p) for p in paths))
        return types.SimpleNamespace(returncode=0, stdout=out, stderr="")

    monkeypatch.setattr(srv.subprocess, "run", run)
    return calls


def commit_repo(srv, tmp_path, monkeypatch):
    """A root the solver paths are read against, so a commit names them the
    way git does. aaaa1111 carries the user's approval — no draft line;
    bbbb2222 is tagged."""
    solvers = tmp_path / "programs" / "solvers"
    solvers.mkdir(parents=True)
    monkeypatch.setattr(srv, "ROOT", tmp_path)
    monkeypatch.setattr(srv, "SOLVERS", solvers)
    (solvers / "aaaa1111.dl").write_text("// aaaa1111\n")
    (solvers / "bbbb2222.dl").write_text("// bbbb2222\n// draft\n")


STATUS = (" M programs/solvers/aaaa1111.dl\n"
          "?? programs/solvers/bbbb2222.dl\n"
          "?? docs/wf-solver/proposals/EDGE_GAP.md\n"
          "?? programs/solvers/.tmpq55dd1ie.dl\n"
          " M programs/lib.dl\n")


def test_a_commit_carries_the_unapproved_solvers_beside_the_approved_ones(
        srv, tmp_path, monkeypatch):
    commit_repo(srv, tmp_path, monkeypatch)
    approved = item(srv, "aaaa1111", srv.APPROVED)
    unapproved = item(srv, "bbbb2222", srv.NEEDS_REVIEW)
    monkeypatch.setattr(srv, "run_committer", lambda: None)
    calls = fake_git(srv, monkeypatch, STATUS,
                     head="programs/solvers/aaaa1111.dl")

    assert srv.act_commit()["ok"] is True
    add = next(c for c in calls if c[1] == "add")
    # lib.dl sits outside the commit's scope: the committer session takes it.
    # The `.tmp` file is a running souffle's scratch, not work.
    assert add[2:] == ["docs/wf-solver/proposals/EDGE_GAP.md",
                       "programs/solvers/aaaa1111.dl",
                       "programs/solvers/bbbb2222.dl"]
    commit = next(c for c in calls if c[1] == "commit")
    assert commit[3] == "Update aaaa1111 (carries bbbb2222)"
    # the commit is not the ruling: the approved item ends the round, the
    # unapproved one stays where it was, and the ledger records neither
    assert approved["state"] == srv.COMMITTED
    assert unapproved["state"] == srv.NEEDS_REVIEW
    assert srv.ledger_rows() == []


def test_an_approved_item_with_no_solver_file_stays_out_of_the_add(
        srv, tmp_path, monkeypatch):
    """One pathspec git cannot match makes the whole add fail and stages
    nothing, so a pass that wrote no solver leaves nothing for the add to
    name."""
    commit_repo(srv, tmp_path, monkeypatch)
    item(srv, "aaaa1111", srv.APPROVED)
    item(srv, "cccc3333", srv.APPROVED)      # its pass wrote no solver
    monkeypatch.setattr(srv, "run_committer", lambda: None)
    calls = fake_git(srv, monkeypatch, STATUS,
                     head="programs/solvers/aaaa1111.dl")

    assert srv.act_commit()["ok"] is True
    add = next(c for c in calls if c[1] == "add")
    assert "programs/solvers/cccc3333.dl" not in add
    assert "programs/solvers/aaaa1111.dl" in add
    commit = next(c for c in calls if c[1] == "commit")
    assert commit[3] == "Add cccc3333; update aaaa1111 (carries bbbb2222)"


def test_a_commit_subject_counts_the_carried_solvers_past_a_few(srv):
    assert srv.commit_subject([], ["aaaa1111"], ["bbbb2222", "cccc3333"]) == \
        "Update aaaa1111 (carries bbbb2222, cccc3333)"
    many = [f"{n}" * 8 for n in range(5)]
    assert srv.commit_subject(["aaaa1111"], [], many) == \
        "Add aaaa1111 (carries 5 unapproved solvers)"


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


def test_a_commit_waits_for_the_running_solver_sessions(srv, tmp_path, monkeypatch):
    commit_repo(srv, tmp_path, monkeypatch)
    item(srv, "aaaa1111", srv.APPROVED)
    monkeypatch.setattr(srv, "run_committer", lambda: None)
    calls = fake_git(srv, monkeypatch, STATUS, head="programs/solvers/aaaa1111.dl")
    srv.PROCS[("cccc3333", "create")] = {"state": "running"}
    try:
        assert srv.act_commit() == {"error": "a solver session is running"}
        assert not any(c[1] == "add" for c in calls)
    finally:
        del srv.PROCS[("cccc3333", "create")]


def test_a_committer_the_timeout_ends_leaves_nothing_reading_it(srv, tmp_path,
                                                                 monkeypatch):
    """A session that leaves a process of its own behind holds the pipe the
    run reads. The timeout ends the session and what it started, so the run
    returns and the flag comes off."""
    fake = tmp_path / "claude.sh"
    marker = tmp_path / "alive"
    fake.write_text(f"#!/bin/sh\n(sl" f"eep 30; touch {marker}) &\nexit 0\n")
    fake.chmod(0o755)
    monkeypatch.setattr(srv, "ROOT", tmp_path)
    monkeypatch.setattr(srv, "CLAUDE", str(fake))
    monkeypatch.setattr(srv, "COMMITTER_FLAGS", [])
    monkeypatch.setattr(srv, "COMMIT_TIMEOUT", .2)
    srv.COMMITTER.update(running=True, note=None, started=time.time(), feed=[])
    done = threading.Event()
    threading.Thread(target=lambda: (srv.run_committer(), done.set()),
                     daemon=True).start()
    assert done.wait(10)
    assert srv.COMMITTER["running"] is False
    assert not marker.exists()


def test_a_committer_does_not_start_after_a_shutdown(srv, tmp_path, monkeypatch):
    """The run opens on a thread of its own, so a shutdown reaches the console
    before the thread reaches the spawn. A session started after that has
    nothing left to end it, and it writes git with the console gone."""
    fake = tmp_path / "claude.sh"
    marker = tmp_path / "started"
    fake.write_text(f"#!/bin/sh\ntouch {marker}\n")
    fake.chmod(0o755)
    monkeypatch.setattr(srv, "ROOT", tmp_path)
    monkeypatch.setattr(srv, "CLAUDE", str(fake))
    monkeypatch.setattr(srv, "COMMITTER_FLAGS", [])
    srv.shutdown_workers()
    srv.COMMITTER.update(running=True, note=None, started=time.time(), feed=[])
    srv.run_committer()
    assert not marker.exists()
    assert srv.COMMITTER["running"] is False
    assert "shutting down" in srv.COMMITTER["note"]


def test_a_shutdown_between_the_spawn_and_the_publish_ends_the_session(
        srv, tmp_path, monkeypatch):
    """A shutdown in that window reads no process and leaves the session
    running, so the run reads the flag the shutdown set and ends the session
    itself."""
    fake = tmp_path / "claude.sh"
    marker = tmp_path / "finished"
    fake.write_text(f"#!/bin/sh\nsl" f"eep 30\ntouch {marker}\n")
    fake.chmod(0o755)
    monkeypatch.setattr(srv, "ROOT", tmp_path)
    monkeypatch.setattr(srv, "CLAUDE", str(fake))
    monkeypatch.setattr(srv, "COMMITTER_FLAGS", [])
    spawn = srv.subprocess.Popen

    def popen(cmd, **kw):
        proc = spawn(cmd, **kw)
        if cmd[0] == str(fake):
            srv.SHUTTING_DOWN = True
        return proc

    monkeypatch.setattr(srv.subprocess, "Popen", popen)
    srv.COMMITTER.update(running=True, note=None, started=time.time(), feed=[])
    done = threading.Event()
    threading.Thread(target=lambda: (srv.run_committer(), done.set()),
                     daemon=True).start()
    assert done.wait(10)
    assert not marker.exists()
    assert srv.COMMITTER_PROC is None


def test_a_kill_leaves_a_session_already_waited_for_alone(srv, monkeypatch):
    """The pid of a waited-for session is free for the next process the
    machine starts, and the kill would reach that one's whole session
    group."""
    hits = []
    monkeypatch.setattr(srv.os, "killpg", lambda *a: hits.append(a))

    class Session:
        pid, returncode = 999999, 0

        def kill(self):
            hits.append("kill")

    srv.kill_session(Session())
    assert hits == []
    Session.returncode = None
    srv.kill_session(Session())
    assert hits == [(999999, signal.SIGKILL)]


def test_a_committer_that_cannot_start_clears_its_flag(srv, tmp_path, monkeypatch):
    """The flag a committer run holds refuses every later commit and holds the
    reload for as long as the console runs, so a session that never starts
    takes it off on its way out."""
    monkeypatch.setattr(srv, "ROOT", tmp_path)
    monkeypatch.setattr(srv, "CLAUDE", str(tmp_path / "no-such-claude"))
    srv.COMMITTER.update(running=True, note=None, started=time.time(), feed=[])
    srv.run_committer()
    assert srv.COMMITTER["running"] is False
    assert "committer failed" in srv.COMMITTER["note"]
    with srv.LOCK:
        assert srv.turns_in_flight() is False
