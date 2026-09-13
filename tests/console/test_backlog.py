"""The unfinalized solvers the finalize lens lists, and the passes started over them."""

import json
import threading
import time

from .conftest import (
    HOLD,
    PROP,
    REPORT,
    backlog_solver,
    finalize_item,
    finalize_launch,
    get,
    item,
    lock_free,
    tagged,
    write_solver,
)

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
    srv.clear_draft("hhh")      # the user approved it: the draft line is gone
    rows = {r["id"]: r for r in srv.backlog_view()}
    assert list(rows) == ["aaa", "fff", "ggg"]
    assert rows["fff"]["passes"] == [{"stage": "finalize", "model": "opus"}]
    assert rows["aaa"]["passes"] == []


def test_a_draft_read_stands_until_the_file_changes(srv, monkeypatch):
    """The lens asks of every solver on each request, so an unchanged file is
    read once."""
    backlog_solver(srv, "aaa")
    reads = []
    read = srv.solver_text
    monkeypatch.setattr(srv, "solver_text",
                        lambda tid: (reads.append(tid), read(tid))[1])
    assert srv.is_draft("aaa")
    assert srv.is_draft("aaa")
    assert reads == ["aaa"]
    write_solver(srv, "aaa", "// keywords: a shape\n")
    assert not srv.is_draft("aaa")
    assert reads == ["aaa", "aaa"]


def test_approving_a_solver_from_the_lens_takes_its_draft_line_off(srv):
    for tid in ("aaa", "bbb"):
        backlog_solver(srv, tid)
    assert srv.act_approve_solver({"id": "aaa"}).get("ok")
    assert [r["id"] for r in srv.backlog_view()] == ["bbb"]
    assert not srv.is_draft("aaa")
    assert srv.ledger_rows() == []
    assert "no solver" in srv.act_approve_solver({"id": "zzz"})["error"]


def test_a_lens_approval_moves_the_item_the_console_holds(srv):
    """The lens and the item panel make one ruling. An item left at
    needs-review has its approval withdrawn by the next revert, which tags
    the file it restores."""
    backlog_solver(srv, "aaa")
    it = item(srv, "aaa", srv.NEEDS_REVIEW)
    assert srv.act_approve_solver({"id": "aaa"}).get("ok")
    assert it["state"] == srv.APPROVED
    assert not srv.is_draft("aaa")
    assert it["feed"][-1]["text"] == "approved"
    srv.pre(it).update(solver="// keywords: a shape, revised\n")
    assert srv.act_revert("aaa") == {"ok": True}
    assert not srv.is_draft("aaa")


def test_lens_approval_waits_for_a_landing_under_way(srv):
    """A landing rewrites the same file under LOCK, so the tag the lens takes
    off is not one a landing is in the middle of putting back."""
    backlog_solver(srv, "aaa")
    done = threading.Event()

    def approve():
        srv.act_approve_solver({"id": "aaa"})
        done.set()

    with srv.LOCK:
        threading.Thread(target=approve, daemon=True).start()
        time.sleep(HOLD)
        assert srv.is_draft("aaa")
    assert done.wait(3)
    assert not srv.is_draft("aaa")


def test_a_lens_approval_stands_through_a_turn_in_flight(srv):
    """An approval does not wait for the item's turn: the landing keeps the
    item approved and leaves the file untagged."""
    backlog_solver(srv, "aaa")
    it = finalize_item(srv, "aaa", state=srv.RUNNING)
    w = srv.PROCS[("aaa", "finalize")]
    srv.start_turn(it, w, "finalize", state="running")
    assert srv.act_approve_solver({"id": "aaa"}) == {"ok": True}
    assert it["state"] == srv.APPROVED
    assert not srv.is_draft("aaa")
    write_solver(srv, "aaa", "// keywords: a shape, revised\n")
    w["state"] = "idle"
    srv.finish_turn(it, {"result": tagged("done")}, None, time.time(),
                    "finalize", False)
    assert it["state"] == srv.APPROVED
    assert not srv.is_draft("aaa")


def test_the_lens_route_reads_git_with_the_lock_down(srv, monkeypatch):
    """The row order comes in part from a git read. Held under LOCK, that read
    stalls every worker reader thread and the page's own poll for as long as
    git takes."""
    backlog_solver(srv, "aaa")
    free = []
    ages = srv.solver_ages
    monkeypatch.setattr(srv, "solver_ages",
                        lambda: (free.append(lock_free(srv)), ages())[1])
    assert get(srv, "/api/backlog")["status"] == 200
    assert free == [True]


def test_a_row_carries_when_its_solver_was_added(srv, monkeypatch):
    """The row reports the first commit for the page to show; the review
    order does not read it."""
    for tid in ("aaa", "bbb", "ccc"):
        backlog_solver(srv, tid)
    monkeypatch.setattr(srv, "solver_ages", lambda: {"aaa": 200, "bbb": 100})
    rows = srv.backlog_view()
    assert [r["id"] for r in rows] == ["aaa", "bbb", "ccc"]
    assert [r["added"] for r in rows] == [200, 100, None]   # ccc: not committed yet


def test_dismiss_drops_a_task_from_the_backlog(srv):
    for tid in ("aaa", "bbb"):
        backlog_solver(srv, tid)
    assert srv.act_dismiss({"id": "aaa"}).get("ok")
    assert [r["id"] for r in srv.backlog_view()] == ["bbb"]
    row = [r for r in srv.ledger_rows() if r["task"] == "aaa"][0]
    assert row["stage"] == "dismissed" and row["source"] == "user"
    assert "no solver" in srv.act_dismiss({"id": "zzz"})["error"]


NAMING = "Naming — the comp name says the mechanism"
SCOPE = "Scope — the rule reaches outside its own example"
SWEEP = "tile size — the pairs leave the largest tile untested"
SWEEP2 = "gap width — the pairs show one gap only"
CITE = "principles.md Coverage cites this solver on approval."


def draft(*, reviews=(), comps=(), workarounds=(), rules=0) -> str:
    """A draft solver: the header, the review lines a retro left in it, and a
    body of `rules` facts, which is its dl size."""
    lines = ["// tid", "// draft", "// keywords: tiling", "// output: a grid"]
    lines += [f"// review {kind}: {text}" for kind, text in reviews]
    lines.append("")
    for name in comps:
        lines += [f".comp {name} {{", "    .decl d(x: number)", "}"]
    lines += [f"// @workaround: {text}" for text in workarounds]
    lines.append(".decl out(x: number)")
    lines += [f"out({n})." for n in range(rules)]
    return "\n".join(lines) + "\n"


def test_the_review_order_bands(srv):
    """Under the principle priority: the missing solver, then the rows carrying
    a principle need, the widest reach first, then the rest. The solver size
    breaks a tie, and the id breaks the last one."""
    write_solver(srv, "aaa", draft(reviews=[("principle", NAMING)]))
    write_solver(srv, "bbb", draft(reviews=[("principle", NAMING)]))
    write_solver(srv, "ccc", draft(reviews=[("principle", SCOPE)]))
    write_solver(srv, "ddd", draft(rules=1))
    write_solver(srv, "eee", draft(rules=3, workarounds=["a scan, not the functor"]))
    # a pass that wrote no solver: the absence of a reading leads
    srv.save_report("zzz", "refine", "no file written")
    item(srv, "zzz", srv.NEEDS_REVIEW, chain=srv.default_chain())

    rows = srv.backlog_view()
    assert [r["id"] for r in rows] == ["zzz", "aaa", "bbb", "ccc", "eee", "ddd"]
    by_id = {r["id"]: r for r in rows}
    assert by_id["zzz"]["no_solver"]
    # aaa and bbb name one heading, so each reaches the other
    assert by_id["aaa"]["reach"]["principle"] == 2
    assert by_id["bbb"]["reach"]["principle"] == 2
    assert by_id["ccc"]["reach"]["principle"] == 1
    assert by_id["eee"]["reach"] == {"principle": 0, "proposal": 0,
                                     "workaround": 1, "sweep": 0, "cite": 0}
    assert by_id["eee"]["dl_size"] == 3 and by_id["ddd"]["dl_size"] == 1


def test_the_autopilot_order_leads_with_the_lines_a_pass_can_act_on(srv):
    """The autopilot orders the same rows on its own: the most review lines,
    workaround lines, and proposal comps first, then the larger solver, then
    the id. A comp counts as one, whatever its entry state."""
    write_solver(srv, "aaa", draft(reviews=[("principle", NAMING)], rules=5))
    write_solver(srv, "bbb", draft(reviews=[("principle", SCOPE), ("sweep", SWEEP)],
                                   rules=1))
    write_solver(srv, "ccc", draft(workarounds=["a scan, not the functor"], rules=9))
    write_solver(srv, "ddd", draft(rules=20))
    write_solver(srv, "eee", draft(comps=["CornerDist"], rules=2))
    assert [r["id"] for r in srv.pass_view()] == ["bbb", "ccc", "aaa", "eee", "ddd"]
    # the lens keeps the review order
    assert [r["id"] for r in srv.backlog_view()] == ["aaa", "bbb", "ddd", "ccc", "eee"]


def test_the_priority_leads_the_rows_holding_its_kind(srv):
    write_solver(srv, "aaa", draft(reviews=[("principle", NAMING)]))
    write_solver(srv, "bbb", draft(comps=["CornerDist"]))
    write_solver(srv, "ccc", draft(workarounds=["a scan, not the functor"]))
    assert [r["id"] for r in srv.backlog_view()] == ["aaa", "bbb", "ccc"]
    srv.act_priority({"kind": "proposal"})
    assert [r["id"] for r in srv.backlog_view()] == ["bbb", "aaa", "ccc"]
    srv.act_priority({"kind": "workaround"})
    assert [r["id"] for r in srv.backlog_view()] == ["ccc", "aaa", "bbb"]


def test_a_sweep_line_is_a_need_and_leads_under_the_sweep_priority(srv):
    """A `// review sweep:` line counts as a sweep need, and the sweep
    priority puts the rows holding one first."""
    write_solver(srv, "aaa", draft(reviews=[("principle", NAMING)]))
    write_solver(srv, "bbb", draft(reviews=[("sweep", SWEEP), ("sweep", SWEEP2)]))
    assert srv.needs_of("bbb")["sweep"] == [SWEEP, SWEEP2]
    rows = {r["id"]: r for r in srv.backlog_view()}
    assert rows["bbb"]["reach"]["sweep"] == 2
    assert rows["aaa"]["reach"]["sweep"] == 0
    srv.act_priority({"kind": "sweep"})
    assert [r["id"] for r in srv.backlog_view()] == ["bbb", "aaa"]


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
    write_solver(srv, "aaa", draft())
    write_solver(srv, "bbb", draft(reviews=[("principle", NAMING)]))
    write_solver(srv, "ccc", draft())
    item(srv, "aaa", srv.NEEDS_REVIEW, chain=srv.default_chain(), phase="finalize")
    item(srv, "bbb", srv.NEEDS_REVIEW, chain=srv.default_chain(), phase="finalize")
    item(srv, "ccc", srv.NEEDS_REVIEW, chain=srv.default_chain(), phase="refine")
    view = srv.lens_view()
    assert view["items"] == []
    assert [r["id"] for r in view["finalizing"]] == ["bbb", "aaa"]
    assert view["finalizing"][0]["reach"]["principle"] == 1
    assert view["priority"] == "principle"


def test_a_task_the_console_holds_stays_out_of_the_backlog(srv):
    backlog_solver(srv, "aaa")
    backlog_solver(srv, "bbb")
    item(srv, "aaa", srv.NEEDS_REVIEW)
    assert [r["id"] for r in srv.backlog_view()] == ["bbb"]


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
    backlog_solver(srv, "aaa", "// draft\n// keywords: a shape, revised\n")
    assert srv.backlog_view()[0]["title"] == "keywords: a shape, revised"
    assert srv.ROW_CACHE["aaa"] is not first


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


# ---------- what a solver holds for review ----------

REVIEWED = """\
// aaa
// draft
// keywords: tiling
// input: a grid of tiles
// output: the grid with every tile recolored
// review principle: Naming — the comp name says the mechanism
//  and not the shape it reads

.comp CornerDist {
    // @workaround: the seam is found by a scan, not by the box functor
    .decl d(x: number)
}
.decl out(x: number)
out(1).
"""


def test_the_needs_read_the_review_lines_the_comps_and_the_workarounds(srv):
    """A review value continues on a line of `//` and two spaces, and the
    proposal needs come from the comps the solver declares."""
    write_solver(srv, "aaa", REVIEWED)
    assert srv.needs_of("aaa") == {
        "principle": ["Naming — the comp name says the mechanism "
                      "and not the shape it reads"],
        "proposal": ["CornerDist"],
        "workaround": ["the seam is found by a scan, not by the box functor"],
        "sweep": [],
        "cite": []}


def test_a_cite_line_is_a_cite_need(srv):
    """A `// review cite:` line reads as a need of kind `cite`, the way the
    other review kinds do."""
    write_solver(srv, "aaa", draft(reviews=[("cite", CITE)]))
    assert srv.needs_of("aaa")["cite"] == [CITE]


def test_a_cite_need_reaches_so_the_cite_focus_leads_with_it(srv):
    """The lens orders the rows under a focus by their reach in that kind, so
    a solver with a cite line leads under the cite focus."""
    write_solver(srv, "aaa", draft(reviews=[("cite", CITE)]))
    write_solver(srv, "bbb", draft())
    rows = {r["id"]: r for r in srv.backlog_view()}
    assert rows["aaa"]["reach"]["cite"] == 1
    assert rows["bbb"]["reach"]["cite"] == 0
    srv.act_priority({"kind": "cite"})
    assert srv.lens_view()["items"][0]["id"] == "aaa"


def test_approval_clears_the_review_lines_and_withdrawing_it_puts_them_back(srv):
    """The review lines are the user's open asks of a draft, so they leave
    with the draft line and come back where they stood."""
    write_solver(srv, "aaa", REVIEWED)
    assert srv.clear_draft("aaa")
    text = srv.solver_text("aaa")
    assert "// draft" not in text and "review principle" not in text
    assert json.loads(srv.REVIEWS_FILE.read_text()) == {"aaa": [
        "// review principle: Naming — the comp name says the mechanism",
        "//  and not the shape it reads"]}
    assert srv.mark_draft("aaa")
    assert srv.solver_text("aaa") == REVIEWED
    assert json.loads(srv.REVIEWS_FILE.read_text()) == {}


def test_approval_places_the_pending_citation(srv):
    """A doc holds a solver's citation pending while the solver is a draft.
    The user approves the solver, and the pending line becomes the citation."""
    doc = srv.DOCS / "principles.md"
    doc.write_text("# Coverage\n\n"
                   "  <!-- draft: aaa \u2014 reads the legend by its corner -->\n")
    write_solver(srv, "aaa", draft(reviews=[("cite", CITE)]))
    assert srv.act_approve_solver({"id": "aaa"}) == {"ok": True}
    assert doc.read_text() == ("# Coverage\n\n"
                              "  - aaa <!-- reads the legend by its corner -->\n")


def test_approval_leaves_another_tasks_pending_citation(srv):
    """The pending lines name their task, and approval places only the lines
    of the solver approved."""
    doc = srv.DOCS / "principles.md"
    other = "<!-- draft: bbb \u2014 reads the legend by its corner -->\n"
    doc.write_text("# Coverage\n\n" + other)
    write_solver(srv, "aaa", draft(reviews=[("cite", CITE)]))
    assert srv.act_approve_solver({"id": "aaa"}) == {"ok": True}
    assert doc.read_text() == "# Coverage\n\n" + other


def test_the_peek_route_carries_the_header_and_the_needs(srv):
    write_solver(srv, "aaa", REVIEWED)
    body = get(srv, "/api/peek/aaa")["body"]
    assert body["title"] == "keywords: tiling"
    assert body["header"]["input"] == "a grid of tiles"
    assert body["needs"]["proposal"] == ["CornerDist"]
    assert body["needs"]["principle"][0].startswith("Naming —")
    assert get(srv, "/api/peek/zzz")["status"] == 404
