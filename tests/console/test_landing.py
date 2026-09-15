"""The report file's write, and the blocks and callouts read off a worker's
text."""

import threading

from .conftest import (
    REPORT,
)


def test_a_report_is_filed_in_one_step(srv):
    """A reader that is not under LOCK — the retro view, a session reading
    the file — never sees a report half written."""
    body = "# report\n" + "a line\n" * 60000
    srv.save_report("a", "finalize", body)
    short, stop = [], threading.Event()

    def read():
        p = srv.report_path("a", "finalize")
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
        srv.save_report("a", "finalize", body)
    stop.set()
    reader.join(3)
    assert short == []


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


def test_callouts_are_read_off_the_report(srv):
    assert srv.parse_callouts(REPORT) == [
        "rank ties are broken by position; the data does not say so",
        "`rank_of` reads like lib material"]


def test_callouts_stop_at_the_next_heading(srv):
    text = "## Callouts\n\n- one\n\n## Next steps\n\n- two\n- three\n"
    assert srv.parse_callouts(text) == ["one"]


def test_a_sign_off_line_is_not_a_callout(srv):
    text = ("## Callouts\nthe const shape is a guess\n"
            "the audit left one case open\n\n*tink*\n")
    assert srv.parse_callouts(text) == ["the const shape is a guess",
                                        "the audit left one case open"]
    assert srv.parse_callouts("## Callouts\n\n*tink*\n") == []
    assert srv.parse_callouts("## Callouts\n\nnone\n\n*purr*\n") == []
    assert srv.parse_callouts("## Callouts\n\n- one\n\n**glass**\n") == ["one"]


def test_callout_ranks_are_read_off_the_entries(srv):
    assert srv.callout_rank(["[P2] a call", "[P1] urgent", "no mark"]) == 1
    assert srv.callout_rank(["[P0] the runner crashes", "[P2] a call"]) == 0
    assert srv.callout_rank(["P3 loose mark"]) == 3
    assert srv.callout_rank(["**[P1]** bolded mark"]) == 1
    assert srv.callout_rank(["**[P2] bold runs on"]) == 2
    assert srv.callout_rank(["no marks here"]) is None
    assert srv.callout_rank([]) is None


