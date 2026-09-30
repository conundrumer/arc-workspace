"""A turn's failures: a bad chain, a landing that raises, a half-written
transcript row, and the appendix built by several callers at once."""

import json
import threading
import time

import pytest

from .conftest import (
    item,
    transcript,
    worker,
)


def test_a_wave_refuses_a_malformed_chain(srv):
    assert "non-empty" in srv.start_wave(1, chain=[])["error"]
    assert "unknown backend" in srv.start_wave(1, chain=[
        {"name": "create", "backend": "gemini"}])["error"]
    assert "duplicate" in srv.start_wave(1, chain=[
        {"name": "create"}, {"name": "create"}])["error"]
    assert "bad stage name" in srv.start_wave(1, chain=[
        {"name": "../escape"}])["error"]
    assert srv.STATE["items"] == []


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


def cap_row(out=64000, **kw):
    """A transcript row for a generation the output cap cut off mid-thought."""
    row = {"type": "assistant",
           "message": {"id": "cap", "stop_reason": "max_tokens",
                       "usage": {"output_tokens": out},
                       "content": [{"type": "thinking", "thinking": ""}]}}
    row.update(kw)
    return row


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


def test_two_callers_building_the_appendix_at_once_each_get_it_whole(srv):
    """A rename publishes the file, and two callers writing one file between
    them would publish it half written."""
    (srv.DOCS / "style.md").write_text(
        "+ id: style\n\n# Style\n" + "- Every word of it.\n" * 60000)
    text = srv.append_path().read_text()
    srv.append_path().unlink()          # as the first build after a docs change
    out, ready = [], threading.Barrier(6)

    def build():
        ready.wait()
        try:
            out.append(srv.append_path().read_text())
        except OSError as exc:
            out.append(repr(exc))

    threads = [threading.Thread(target=build) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(20)
    assert out == [text] * 6


def test_worker_cmd_stays_well_under_the_argument_limit(srv, tmp_path, monkeypatch):
    """Both renderings of the handbook ride in argv, inside the agents JSON.
    The limit the spawn hits is macOS's 1 MiB over argv and the environment
    together, which is what spawn_worker passes, so the bound is taken over
    both."""
    from handbook.context import render
    monkeypatch.setattr(srv, "FAKE", False)
    append = tmp_path / "append.md"
    append.write_text(render())   # the repo's own docs and lib.dl
    it = item(srv, "a", srv.NEEDS_REVIEW, append=str(append))
    cmd = srv.worker_cmd(it, "refine")
    env = [f"{k}={v}" for k, v in srv.WORKER_ENV.items()]
    assert sum(len(s.encode()) + 1 for s in [*cmd, *env]) < 1024 * 1024


