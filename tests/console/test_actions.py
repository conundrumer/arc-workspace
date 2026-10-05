"""The console's writes beside other readers: the draft tag, a revert over
another worker's entry, the ledger, the retro mark, and the committer
session's end."""

import signal
import threading
import time

from .conftest import PROP, item, write_solver


def test_the_tag_is_written_in_one_step(srv):
    """A worker session, a souffle run, and the ref-note hook read the solver
    while the console retags it, and none of them sees a half-written file."""
    body = "// a\n" + "// filler\n" * 20000
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
    # A writer that truncates in place is caught every time at this body and
    # this many rounds, and is missed at a fifth of the rounds.
    for _ in range(50):
        srv.mark_draft("a")
        srv.clear_draft("a")
    stop.set()
    reader.join(3)
    assert short == []


def write_prop(srv, name, text):
    (srv.DOCS / "proposals").mkdir(exist_ok=True)
    (srv.DOCS / "proposals" / f"{name}.md").write_text(text)


def test_revert_leaves_an_entry_another_worker_touched(srv):
    it = item(srv, "a", srv.NEEDS_REVIEW, prop_after={f"{PROP}/X.md": "A\nB\n"})
    it["pre"] = {"hash": "", "solver": "// before\n", "proposals": {},
                 "dirty": False, "files": {f"{PROP}/X.md": "A\n"}}
    write_prop(srv, "X", "A\nB\nC\n")  # a later turn appended
    write_solver(srv, "a", "// after\n")
    srv.act_revert("a")
    assert srv.prop_text() == "A\nB\nC\n"
    assert it["reverted"]["files"] == ["programs/solvers/a.dl"]


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
    srv.mark_retro()
    assert Watched.written == ["retro.tmp"]
    assert srv.retro_mark() == 900


# The scope one committer run takes.
SCOPE = ["programs/lib.dl"]


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
    srv.run_committer(SCOPE)
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
    threading.Thread(target=lambda: (srv.run_committer(SCOPE), done.set()),
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
        pid = 999999
        returncode: int | None = 0

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
    srv.run_committer(SCOPE)
    assert srv.COMMITTER["running"] is False
    assert "committer failed" in srv.COMMITTER["note"]
    with srv.LOCK:
        assert srv.turns_in_flight() is False
