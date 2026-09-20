"""One survey of a proposals entry: the files it takes, the lock that holds
two callers to one run, and the session's end."""

import importlib
import signal
import threading
import time
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STAMP = "%Y-%m-%d %H:%M"

ENTRY = """# `Thing` — an operation

An index sentence.

Match: a rule with a Dir column.
"""

RESULT_EVENT = '{"type":"result","is_error":false,"result":"Callers: none."}'

# A stand-in for prompts/roles/survey.md, which names no agent.
ROLE = """- Survey the operation the entry names, over the scope the brief gives.
- The report holds its four parts.
"""


@pytest.fixture
def sv(srv):
    """The surveys module, under the console's patched paths. Nothing in the
    server imports it, so the test loads it itself."""
    return importlib.import_module("solver_console.surveys")


def entry(srv, name, text=ENTRY):
    d = srv.DOCS / "proposals"
    d.mkdir(exist_ok=True)
    path = d / f"{name}.md"
    path.write_text(text)
    return path


def surveyed(when, result="Callers: none.", head=ENTRY):
    """An entry whose newest survey ran at that time."""
    return f"{head}\nSurvey: {when}\n\n{result}\n"


def stamp(ago):
    """A `Survey:` line's time, that many seconds back."""
    return time.strftime(STAMP, time.localtime(time.time() - ago))


def fake_claude(tmp_path, body, name="claude.sh"):
    """A stand-in for the CLI, so a run opens no session."""
    path = tmp_path / name
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)
    return str(path)


def local(srv, sv, tmp_path, monkeypatch, body=f"echo '{RESULT_EVENT}'\n"):
    """Point the run at the test's own tree and at a fake CLI. The role the
    brief opens with sits in that tree as well: the run reads the file before
    it launches, and a writer replacing the one under prompts/roles/ would
    fail the read."""
    roles = tmp_path / "roles"
    roles.mkdir(exist_ok=True)
    (roles / "survey.md").write_text(ROLE)
    monkeypatch.setattr(srv, "ROLE_DIR", roles)
    monkeypatch.setattr(srv, "ROOT", tmp_path)
    monkeypatch.setattr(srv, "CLAUDE", fake_claude(tmp_path, body))
    monkeypatch.setattr(srv, "SURVEY_FLAGS", [])
    monkeypatch.setattr(sv, "survey_session", lambda: [])


def test_a_file_outside_the_proposals_directory_is_not_an_entry(sv, srv, tmp_path,
                                                                monkeypatch):
    """A run appends its result to the file it is handed, so the command takes
    only the files the entries live in."""
    monkeypatch.setattr(srv, "ROOT", tmp_path)
    monkeypatch.setattr(srv, "DOCS", tmp_path / "docs" / "wf-solver")
    srv.DOCS.mkdir(parents=True)
    monkeypatch.setattr(srv, "PROPS", srv.DOCS / "proposals")
    entry(srv, "Thing")
    doc = tmp_path / "docs" / "wf-solver" / "protocol.md"
    doc.write_text("# the protocol\n")
    assert sv.entry_path("docs/wf-solver/protocol.md") == doc
    assert sv.in_proposals(doc) is False
    assert sv.in_proposals(sv.entry_path("/etc/passwd")) is False


def test_two_callers_on_one_entry_cost_one_survey(sv, srv, tmp_path, monkeypatch):
    """The second caller waits for the lock, reads the entry again, and finds
    the result the first one filed."""
    path = entry(srv, "Thing")
    counter = tmp_path / "runs"
    local(srv, sv, tmp_path, monkeypatch,
          body=f"echo x >> {counter}\nsl" f"eep .2\necho '{RESULT_EVENT}'\n")
    monkeypatch.setattr(sv, "survey_scope", lambda w: [])
    codes = []
    threads = [threading.Thread(target=lambda: codes.append(sv.survey_entry(path)))
               for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(20)
    assert codes == [0, 0]
    assert counter.read_text() == "x\n"
    assert path.read_text().count("Survey:") == 1


def test_a_scope_the_runner_cannot_list_stops_the_command(sv, srv, tmp_path,
                                                          monkeypatch, capsys):
    """No answer and an empty scope read the same way otherwise, and the entry
    would pass as current with the survey it is owed never run."""
    path = entry(srv, "Thing", surveyed(stamp(7200)))
    local(srv, sv, tmp_path, monkeypatch, body="exit 1\n")
    monkeypatch.setattr(
        srv.subprocess, "run",
        lambda *a, **kw: types.SimpleNamespace(
            returncode=1, stdout="", stderr="git found no history\n"))
    assert sv.survey_entry(path) == 1
    assert "could not be listed" in capsys.readouterr().err
    assert "Survey:" in path.read_text()


def test_a_kill_leaves_a_session_already_waited_for_alone(sv, srv, monkeypatch):
    """The pid of a waited-for session is free for the next process the
    machine starts, and the kill would reach that one's whole session
    group."""
    hits = []
    monkeypatch.setattr(srv.os, "killpg", lambda *a: hits.append(a))

    class Session:
        pid, returncode = 999999, 0

        def kill(self):
            hits.append("kill")

    sv.survey_kill(Session())
    assert hits == []
    Session.returncode = None
    sv.survey_kill(Session())
    assert hits == [(999999, signal.SIGKILL)]


def test_a_run_the_timeout_ends_leaves_nothing_reading_it(sv, srv, tmp_path,
                                                          monkeypatch):
    """A session that leaves a process of its own behind holds the pipe the
    run reads. The timeout ends the session and what it started, so the run
    returns."""
    path = entry(srv, "Thing")
    marker = tmp_path / "alive"
    local(srv, sv, tmp_path, monkeypatch,
          body=f"(sl" f"eep 30; touch {marker}) &\nexit 0\n")
    monkeypatch.setattr(srv, "SURVEY_TIMEOUT", .2)
    done = threading.Event()
    codes = []

    def go():
        codes.append(sv.survey_entry(path))
        done.set()

    threading.Thread(target=go, daemon=True).start()
    assert done.wait(10)
    assert codes == [1] and not marker.exists()


