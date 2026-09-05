"""The unfinalized solvers the finalize lens lists, and the passes started over them."""

import json
import threading
import time

from .conftest import PROP, REPORT, backlog_solver, finalize_launch, item, write_solver

# ---------- the finalize backlog ----------


def test_every_solver_not_ruled_on_is_unfinalized(srv):
    for tid in ("aaa", "fff", "ggg", "hhh"):
        backlog_solver(srv, tid)
    srv.ledger_append({"task": "fff", "stage": "finalize",
                       "model": "claude-opus-5", "source": "console"})
    srv.ledger_append({"task": "ggg", "stage": "legacy",
                       "model": "claude-fable-5", "source": "backfill"})
    srv.ledger_append({"task": "hhh", "stage": "finalize",
                       "model": "claude-fable-5", "source": "console"})
    srv.ledger_append({"task": "hhh", "stage": "approved", "model": None,
                       "source": "console"})
    rows = {r["id"]: r for r in srv.backlog_view()}
    assert list(rows) == ["aaa", "fff", "ggg"]
    assert rows["fff"]["passes"] == [{"stage": "finalize", "model": "opus"}]
    assert rows["aaa"]["passes"] == []


def test_approving_a_solver_from_the_lens_is_a_ledger_line(srv):
    for tid in ("aaa", "bbb"):
        backlog_solver(srv, tid)
    assert srv.act_approve_solver({"id": "aaa"}).get("ok")
    assert [r["id"] for r in srv.backlog_view()] == ["bbb"]
    row = [r for r in srv.ledger_rows() if r["task"] == "aaa"][0]
    assert row["stage"] == "approved" and row["source"] == "user"
    assert "no solver" in srv.act_approve_solver({"id": "zzz"})["error"]


def test_the_oldest_commit_breaks_the_last_tie(srv, monkeypatch):
    for tid in ("aaa", "bbb", "ccc"):
        backlog_solver(srv, tid)
    monkeypatch.setattr(srv, "solver_ages", lambda: {"aaa": 200, "bbb": 100})
    rows = srv.backlog_view()
    assert [r["id"] for r in rows] == ["bbb", "aaa", "ccc"]   # ccc: not committed yet
    assert [r["added"] for r in rows] == [100, 200, None]


def test_dismiss_drops_a_task_from_the_backlog(srv):
    for tid in ("aaa", "bbb"):
        backlog_solver(srv, tid)
    assert srv.act_dismiss({"id": "aaa"}).get("ok")
    assert [r["id"] for r in srv.backlog_view()] == ["bbb"]
    row = [r for r in srv.ledger_rows() if r["task"] == "aaa"][0]
    assert row["stage"] == "dismissed" and row["source"] == "user"
    assert "no solver" in srv.act_dismiss({"id": "zzz"})["error"]


def test_the_backlog_order_bands(srv):
    """One task per band, in the order the sort produces. The ids descend as
    the bands do, so only the sort key can put the rows in this order. The
    last two bands tie on every term of the key, and the id separates them."""
    for tid in ("t01", "t02", "t03", "t04", "t05", "t06",
                "t07", "t08", "t09", "t10", "t12"):
        backlog_solver(srv, tid)
    # a task whose session added an entry: the ledger line carries it
    srv.ledger_append({"task": "t12", "stage": "refine", "model": "claude-opus-5",
                       "source": "console", "entries": [f"{PROP}/Border.md"]})
    # a missing solver: the pass landed and wrote a report, but no file
    srv.save_report("t11", "refine", "no file written")
    item(srv, "t11", srv.NEEDS_REVIEW, chain=srv.default_chain())
    srv.save_report("t10", "refine",
                    "done\n\n## Callouts\n\n1. [P0] run_dl crashes on this task\n")
    srv.act_flag({"id": "t09", "level": 1})
    srv.act_flag({"id": "t08", "level": 2})
    srv.save_report("t07", "refine",
                    "done\n\n## Callouts\n\n1. [P1] the pin is a guess\n")
    srv.save_report("t06", "refine",
                    "done\n\n## Callouts\n\n1. [P2] the pin is a guess\n")
    write_solver(srv, "t05", "// concept: tiles\n.comp CornerDist {\n}\n")
    srv.save_report("t04", "refine", REPORT)   # two entries, no marks
    srv.save_report("t03", "refine",
                    "done\n\n## Callouts\n\n1. [P3] the name reads oddly\n")
    srv.save_report("t01", "refine", "done, nothing to raise\n")

    rows = srv.backlog_view()
    assert [r["id"] for r in rows] == [
        "t11",   # no solver
        "t10",   # P0
        "t12",   # an entry
        "t09",   # flag 1
        "t08",   # flag 2
        "t07",   # P1
        "t06",   # P2
        "t05",   # a comp
        "t04",   # callout entries with no mark
        "t03",   # P3
        "t01",   # a report that raised nothing
        "t02",   # nothing at all
    ]
    by_id = {r["id"]: r for r in rows}
    assert by_id["t12"]["entries"] == ["Border"] and by_id["t11"]["entries"] == []
    assert by_id["t11"]["no_solver"] and not by_id["t10"]["no_solver"]
    assert by_id["t10"]["callout_rank"] == 0
    assert by_id["t09"]["flag"] == 1
    assert by_id["t08"]["flag"] == 2
    assert by_id["t07"]["callout_rank"] == 1
    assert by_id["t06"]["callout_rank"] == 2
    assert by_id["t05"]["comps"] == ["CornerDist"]
    assert by_id["t05"]["comps_unproposed"] == ["CornerDist"]
    assert by_id["t05"]["callout_rank"] is None
    assert by_id["t04"]["callout_n"] == 2
    assert by_id["t04"]["reports"] == ["refine"]
    assert by_id["t03"]["callout_rank"] == 3
    assert by_id["t03"]["callout_act"] == 0
    assert by_id["t02"]["reports"] == []
    assert by_id["t02"]["title"] == "concept: a shape"
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
    assert srv.backlog_view() == []


def test_the_lens_ranks_the_finalize_passes_in_flight(srv):
    for tid in ("aaa", "bbb", "ccc"):
        backlog_solver(srv, tid)
    srv.save_report("bbb", "refine", "## Callouts\n\n1. [P1] a call")
    item(srv, "aaa", srv.NEEDS_REVIEW, chain=srv.default_chain(), phase="finalize")
    item(srv, "bbb", srv.NEEDS_REVIEW, chain=srv.default_chain(), phase="finalize")
    item(srv, "ccc", srv.NEEDS_REVIEW, chain=srv.default_chain(), phase="refine")
    view = srv.lens_view()
    assert view["items"] == []
    assert [r["id"] for r in view["finalizing"]] == ["bbb", "aaa"]
    assert view["finalizing"][0]["callout_n"] == 1
    assert "flag" in view["finalizing"][0]


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


def test_an_unfinalized_row_is_rebuilt_only_when_its_files_change(srv):
    backlog_solver(srv, "aaa")
    srv.backlog_view()
    first = srv.ROW_CACHE["aaa"]
    backlog_solver(srv, "bbb")
    assert [r["id"] for r in srv.backlog_view()] == ["aaa", "bbb"]
    assert srv.ROW_CACHE["aaa"] is first
    backlog_solver(srv, "aaa", "// concept: a shape, revised\n")
    assert srv.backlog_view()[0]["title"] == "concept: a shape, revised"
    assert srv.ROW_CACHE["aaa"] is not first


def test_a_flag_shows_up_without_waiting_for_the_scan(srv):
    backlog_solver(srv, "aaa")
    srv.backlog_view()
    srv.act_flag({"id": "aaa", "level": 1})
    assert srv.backlog_view()[0]["flag"] == 1


# ---------- starting a finalize pass ----------


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
    assert srv.backlog_view() == []


def test_concurrent_saves_publish_one_whole_state(srv):
    item(srv, "a", srv.NEEDS_REVIEW)
    stop = threading.Event()
    errors = []

    def churn():
        n = 0
        while not stop.is_set():
            n += 1
            with srv.LOCK:
                srv.STATE["items"][0]["rev"] = n
            time.sleep(.001)

    def saver():
        try:
            for _ in range(30):
                srv.save()
        except Exception as exc:      # a lost temp file, or a dict that moved
            errors.append(exc)

    writer = threading.Thread(target=churn, daemon=True)
    writer.start()
    savers = [threading.Thread(target=saver) for _ in range(4)]
    for thread in savers:
        thread.start()
    for thread in savers:
        thread.join(timeout=10)
    stop.set()
    writer.join(timeout=2)
    assert errors == []
    assert json.loads(srv.STATE_FILE.read_text())["items"][0]["id"] == "a"
