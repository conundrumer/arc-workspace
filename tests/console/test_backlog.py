"""The finalize lens under LOCK, the state file under concurrent saves, and
the review lines a solver header carries through approval."""

import json
import threading
import time

from .conftest import (
    HOLD,
    backlog_solver,
    get,
    item,
    lock_free,
    write_solver,
)


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


def test_approval_leaves_another_tasks_pending_citation(srv):
    """The pending lines name their task, and approval places only the lines
    of the solver approved."""
    doc = srv.DOCS / "principles.md"
    other = "<!-- draft: bbb \u2014 reads the legend by its corner -->\n"
    doc.write_text("# Coverage\n\n" + other)
    write_solver(srv, "aaa", draft(reviews=[("cite", CITE)]))
    assert srv.act_approve_solver({"id": "aaa"}) == {"ok": True}
    assert doc.read_text() == "# Coverage\n\n" + other


