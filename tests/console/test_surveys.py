"""One survey of a proposals entry: the scope it covers, the result it files,
and the lock that holds two callers to one run."""

import importlib
import os
import signal
import subprocess
import sys
import threading
import time
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "survey.py"
PROPOSALS = ROOT / "docs" / "wf-solver" / "proposals"
STAMP = "%Y-%m-%d %H:%M"

ENTRY = """# `Thing` — an operation

An index sentence.

Match: a rule with a Dir column.
"""

RESULT_EVENT = '{"type":"result","is_error":false,"result":"Callers: none."}'


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
    """Point the run at the test's own tree and at a fake CLI."""
    monkeypatch.setattr(srv, "ROOT", tmp_path)
    monkeypatch.setattr(srv, "CLAUDE", fake_claude(tmp_path, body))
    monkeypatch.setattr(srv, "SURVEY_FLAGS", [])
    monkeypatch.setattr(sv, "survey_session", lambda: [])


# ---------- the scope ----------

def test_an_entry_with_no_result_is_surveyed_over_the_corpus(sv, srv):
    path = entry(srv, "Thing")
    assert sv.survey_plan(path.read_text()) == {"since": None, "scope": None}


def test_an_entry_with_a_result_is_surveyed_over_the_newer_solvers(sv, srv, monkeypatch):
    when = stamp(7200)
    path = entry(srv, "Thing", surveyed(when))
    monkeypatch.setattr(sv, "survey_scope", lambda w: ["aaa", "bbb"])
    assert sv.survey_plan(path.read_text()) == {"since": when,
                                                "scope": ["aaa", "bbb"]}


def test_an_empty_scope_leaves_the_entry_current(sv, srv, monkeypatch):
    path = entry(srv, "Thing", surveyed(stamp(7200)))
    monkeypatch.setattr(sv, "survey_scope", lambda w: [])
    assert sv.survey_plan(path.read_text()) is None


def test_a_survey_line_with_no_result_is_surveyed_over_the_corpus(sv, srv):
    path = entry(srv, "Thing", ENTRY + f"\nSurvey: {stamp(60)} — the whole corpus.\n")
    assert sv.survey_plan(path.read_text()) == {"since": None, "scope": None}


def test_a_survey_time_no_clock_holds_stops_the_command(sv, srv, tmp_path,
                                                        monkeypatch, capsys):
    """A `Survey:` line whose time reads as a date but names none stands for a
    scope the command cannot read."""
    path = entry(srv, "Thing", ENTRY + "\nSurvey: 2026-13-45 99:99\n\nCallers: none.\n")
    local(srv, sv, tmp_path, monkeypatch, body="exit 1\n")
    with pytest.raises(sv.TimeUnknown):
        sv.survey_plan(path.read_text())
    assert sv.survey_entry(path) == 1
    assert "Survey: 2026-13-45 99:99" in capsys.readouterr().err
    assert path.read_text().count("Survey:") == 1


def test_a_result_from_the_caller_own_minute_is_current(sv):
    """A `Survey:` line carries its time to the minute, and the caller reads
    its arrival at that resolution."""
    at = time.mktime(time.strptime("2026-02-02 03:04", STAMP)) + 59
    assert sv.filed_since(surveyed("2026-02-02 03:04"), at)
    assert not sv.filed_since(surveyed("2026-02-02 03:03"), at)


def test_an_entry_is_named_by_its_name_or_its_path(sv, srv):
    path = entry(srv, "Thing")
    assert sv.entry_path("Thing") == path
    assert sv.entry_path(str(path)) == path
    assert sv.entry_path(str(path.with_suffix(""))) == path


def test_a_relative_path_is_read_from_the_repo_root(sv, srv, tmp_path, monkeypatch):
    """The command runs in whatever directory the caller stands in, and the
    entry a relative path names is the same one from every one of them."""
    monkeypatch.setattr(srv, "ROOT", tmp_path)
    monkeypatch.setattr(srv, "DOCS", tmp_path / "docs" / "wf-solver")
    srv.DOCS.mkdir(parents=True)
    path = entry(srv, "Thing")
    monkeypatch.chdir(tmp_path.parent)
    assert sv.entry_path("docs/wf-solver/proposals/Thing.md") == path
    assert sv.in_proposals(path)


def test_a_file_outside_the_proposals_directory_is_not_an_entry(sv, srv, tmp_path,
                                                                monkeypatch):
    """A run appends its result to the file it is handed, so the command takes
    only the files the entries live in."""
    monkeypatch.setattr(srv, "ROOT", tmp_path)
    monkeypatch.setattr(srv, "DOCS", tmp_path / "docs" / "wf-solver")
    srv.DOCS.mkdir(parents=True)
    entry(srv, "Thing")
    doc = tmp_path / "docs" / "wf-solver" / "protocol.md"
    doc.write_text("# the protocol\n")
    assert sv.entry_path("docs/wf-solver/protocol.md") == doc
    assert sv.in_proposals(doc) is False
    assert sv.in_proposals(sv.entry_path("/etc/passwd")) is False


# ---------- the header and the append ----------

def test_a_result_lands_at_the_end_of_the_entry(sv, srv):
    path = entry(srv, "Thing", surveyed("2026-01-01 00:00"))
    plan = {"since": "2026-01-01 00:00", "scope": ["aaa", "bbb"]}
    at = time.mktime(time.strptime("2026-02-02 03:04", STAMP))
    sv.append_survey(path, sv.survey_header(plan, at), "One new caller.\n")
    text = path.read_text()
    assert text.endswith("Survey: 2026-02-02 03:04 — the solvers since "
                         "2026-01-01 00:00.\n\nOne new caller.\n")
    assert sv.newest_survey(text) == "2026-02-02 03:04"
    assert sv.survey_result(text)


def test_a_corpus_survey_names_the_whole_corpus(sv, srv):
    path = entry(srv, "Thing")
    at = time.mktime(time.strptime("2026-02-02 03:04", STAMP))
    sv.append_survey(path, sv.survey_header({"since": None, "scope": None}, at),
                     "Callers: none.")
    assert path.read_text().endswith(
        "Survey: 2026-02-02 03:04 — the whole corpus.\n\nCallers: none.\n")


def test_a_report_that_opens_with_its_own_heading_lands_intact(sv, srv):
    """The run returns the bare report, and the append files every line of
    it."""
    path = entry(srv, "Thing")
    at = time.mktime(time.strptime("2026-02-02 03:04", STAMP))
    sv.append_survey(path, sv.survey_header({"since": None, "scope": None}, at),
                     "\n## Survey: `Thing` over 12 solvers\n\nCallers: none.\n\n")
    assert path.read_text().endswith(
        "Survey: 2026-02-02 03:04 — the whole corpus.\n\n"
        "## Survey: `Thing` over 12 solvers\n\nCallers: none.\n")


# ---------- the run ----------

def test_a_run_files_its_report_and_writes_under_the_run_directory(sv, srv, tmp_path,
                                                                   monkeypatch):
    path = entry(srv, "Thing")
    local(srv, sv, tmp_path, monkeypatch)
    assert sv.survey_entry(path) == 0
    assert path.read_text().endswith("— the whole corpus.\n\nCallers: none.\n")
    runs = sorted((tmp_path / ".scratch" / "surveys" / "Thing").glob("2*"))
    assert len(runs) == 1 and (runs[0] / "session.log").exists()


def test_a_current_entry_runs_nothing(sv, srv, tmp_path, monkeypatch, capsys):
    path = entry(srv, "Thing", surveyed(stamp(7200)))
    local(srv, sv, tmp_path, monkeypatch, body="exit 1\n")
    monkeypatch.setattr(sv, "survey_scope", lambda w: [])
    assert sv.survey_entry(path) == 0
    assert "is current" in capsys.readouterr().out
    assert path.read_text() == surveyed(stamp(7200))


def test_a_closed_entry_is_refused_and_forced(sv, srv, tmp_path, monkeypatch, capsys):
    path = entry(srv, "Thing", ENTRY + "\nClosed: 2026-01-01 00:00 — lib holds it.\n")
    local(srv, sv, tmp_path, monkeypatch)
    assert sv.survey_entry(path) == 1
    assert "is closed" in capsys.readouterr().err
    assert "Survey:" not in path.read_text()
    assert sv.survey_entry(path, force=True) == 0
    assert path.read_text().endswith("Callers: none.\n")


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


def test_a_second_caller_finds_the_result_the_first_one_filed(sv, srv, tmp_path,
                                                              monkeypatch):
    """The scope a delta survey covers is never empty while the working tree
    holds uncommitted solvers, so the entry is read as current from the result
    itself: one filed since the caller arrived is the survey it came for."""
    path = entry(srv, "Thing")
    local(srv, sv, tmp_path, monkeypatch, body="exit 1\n")
    monkeypatch.setattr(sv, "survey_scope", lambda w: ["aaa", "bbb"])
    path.write_text(surveyed(stamp(0)))
    assert sv.survey_entry(path) == 0
    assert path.read_text() == surveyed(stamp(0))


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


def test_a_session_that_cannot_start_is_reported(sv, srv, tmp_path, monkeypatch,
                                                 capsys):
    """No CLI on the path ends the command with a line about it, not a
    traceback."""
    path = entry(srv, "Thing")
    local(srv, sv, tmp_path, monkeypatch)
    monkeypatch.setattr(srv, "CLAUDE", str(tmp_path / "no-such-claude"))
    assert sv.survey_entry(path) == 1
    assert "could not start" in capsys.readouterr().err
    assert "Survey:" not in path.read_text()


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


def test_a_run_that_returns_no_report_names_its_log(sv, srv, tmp_path, monkeypatch,
                                                    capsys):
    path = entry(srv, "Thing")
    local(srv, sv, tmp_path, monkeypatch, body="echo 'nothing' >&2\nexit 1\n")
    assert sv.survey_entry(path) == 1
    err = capsys.readouterr().err
    assert "no report" in err and "session.log" in err
    assert "Survey:" not in path.read_text()


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


# ---------- the command ----------

def test_the_command_surveys_the_entry_it_names(tmp_path):
    """`scripts/survey.py` on a real entry, with `claude` faked on PATH."""
    name = f"_scratch-entry-{os.getpid()}"
    path = PROPOSALS / f"{name}.md"
    path.write_text(ENTRY)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_claude(bin_dir, f"echo '{RESULT_EVENT}'\n", name="claude")
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}",
           "CONSOLE_STATE_DIR": str(tmp_path / "state")}
    env.pop("CONSOLE_CLAUDE", None)
    try:
        out = subprocess.run([sys.executable, str(SCRIPT), name], cwd=ROOT, env=env,
                             capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
        assert path.read_text().endswith(
            "— the whole corpus.\n\nCallers: none.\n")
    finally:
        path.unlink(missing_ok=True)
        subprocess.run(["rm", "-rf", str(ROOT / ".scratch" / "surveys" / name)])


# ---------- the session ----------

def test_the_session_is_the_handbook_agent_over_the_survey_role(sv, srv, tmp_path, monkeypatch):
    from dl.context import AGENT_META
    flags = sv.survey_session()
    assert flags[flags.index("--system-prompt-file") + 1] == str(srv.append_path())
    assert flags[flags.index("--model") + 1] == AGENT_META["model"]
    assert flags[flags.index("--effort") + 1] == AGENT_META["effort"]
    assert "--system-prompt" not in flags
    seen = tmp_path / "argv.txt"
    local(srv, sv, tmp_path, monkeypatch,
          body=f"printf '%s\\n' \"$@\" > {seen}\necho '{RESULT_EVENT}'\n")
    path = entry(srv, "Thing")
    sv.survey_entry(path)
    brief = seen.read_text().split("\n")[1]
    assert brief.startswith(sv.prompts.role_text("survey").split("\n")[0])
