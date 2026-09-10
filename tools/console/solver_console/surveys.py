"""One survey of a proposals entry: the scope it covers, the session that
writes the report, and the append that files the result.

`scripts/survey.py` is the caller. A survey runs only when that command is
run; nothing here dispatches on its own.

The entry under docs/wf-solver/proposals/ carries the result, under a
`Survey:` line, in the form the lib addition protocol states. The line and
the result go in together at the end of the run, so an entry never shows a
`Survey:` line with nothing under it.

A lock file under `.scratch/surveys/<name>/` holds one survey per entry. A
caller that waits for the lock re-reads the entry, and a result the first
caller filed leaves the entry current, so two callers on one entry cost one
survey. The run's own files go under `.scratch/surveys/<name>/<run time>/`.
"""

import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import config, prompts

# The line the protocol reads, and the line that says the entry is closed.
SURVEY_LINE = re.compile(r"^Survey:[ \t]*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})", re.M)
CLOSED_LINE = re.compile(r"^Closed:", re.M)
SURVEY_STAMP = "%Y-%m-%d %H:%M"
RUN_STAMP = "%Y-%m-%d-%H%M%S"


def entry_path(name: str) -> Path:
    """The entry a caller names: an entry's name under
    docs/wf-solver/proposals/, or a path to a file there. A relative path is
    read from the repo root, so the directory the caller runs in does not
    change what the name reaches."""
    path = Path(name)
    if path.suffix != ".md":
        path = path.with_name(path.name + ".md")
    if len(path.parts) == 1:
        path = config.DOCS / "proposals" / path
    elif not path.is_absolute():
        path = config.ROOT / path
    return path.resolve()


def proposals_dir() -> Path:
    """The directory the entries live in."""
    return (config.DOCS / "proposals").resolve()


def in_proposals(path: Path) -> bool:
    """Whether the path names a file in that directory. The run appends its
    result to the file it is handed, so a file outside is refused."""
    return path.parent == proposals_dir()


def newest_survey(text: str) -> str | None:
    """The time of the entry's newest `Survey:` line, as the line writes it."""
    stamps = SURVEY_LINE.findall(text)
    return max(stamps) if stamps else None


def survey_result(text: str) -> bool:
    """Whether a result stands under the entry's newest `Survey:` line."""
    ends = [m.end() for m in SURVEY_LINE.finditer(text)]
    if not ends:
        return False
    nl = text.find("\n", ends[-1])
    return nl >= 0 and bool(text[nl:].strip())


def survey_minute(at: float) -> str:
    """A clock reading in the form a `Survey:` line writes it."""
    return time.strftime(SURVEY_STAMP, time.localtime(at))


def filed_since(text: str, at: float) -> bool:
    """Whether the entry carries a result from the minute of that clock
    reading or a later one. A caller that waited for the lock reads its own
    arrival against the result the run before it filed."""
    when = newest_survey(text)
    return when is not None and survey_result(text) and when >= survey_minute(at)


def survey_time(when: str) -> float | None:
    """A `Survey:` line's time as a clock reading, or None when the line
    carries a time no clock holds."""
    try:
        return time.mktime(time.strptime(when, SURVEY_STAMP))
    except ValueError:
        return None


class ScopeUnknown(Exception):
    """The runner could not list the solvers a survey since a time covers."""


def survey_scope(when: str) -> list[str]:
    """The solvers a survey since that time covers, as the runner lists
    them. A runner that refuses raises: no answer and an empty scope read the
    same way otherwise, and the entry would pass as current with the survey
    it is owed never run."""
    out = subprocess.run(["uv", "run", "python", "scripts/run_dl.py", "since", when],
                         cwd=config.ROOT, capture_output=True, text=True)
    if out.returncode != 0:
        raise ScopeUnknown((out.stderr or out.stdout).strip()
                           or f"run_dl.py since {when!r} failed")
    return out.stdout.split()


def survey_plan(text: str) -> dict | None:
    """What the entry is owed: the time the survey runs from and the solvers
    in its scope, or None when the entry is current.

    An entry with no result is surveyed over the whole corpus, and so is one
    whose newest `Survey:` line carries a time no clock holds. An entry with a
    result is surveyed over the solvers written since that line's time; with
    no such solver the entry is current.
    """
    when = newest_survey(text)
    at = survey_time(when) if when is not None else None
    if at is None or not survey_result(text):
        return {"since": None, "scope": None}
    scope = survey_scope(when)
    return {"since": when, "scope": scope} if scope else None


def survey_header(plan: dict, at: float) -> str:
    """The `Survey:` line the run's result goes under: its time, and the scope
    it covered."""
    stamp = survey_minute(at)
    if plan["scope"] is None:
        return f"Survey: {stamp} — the whole corpus."
    return (f"Survey: {stamp} — the solvers since {plan['since']}, "
            + ", ".join(plan["scope"]) + ".")


def append_survey(path: Path, header: str, result: str) -> None:
    """Add the `Survey:` line and the run's report at the end of the entry.
    The report is filed as the session returned it, stripped of surrounding
    whitespace.

    The flock orders this module's own writers of the entry against each
    other. A session that edits the entry with its own tools takes no lock,
    so the append and such an edit are not ordered against each other.
    """
    with open(path, "r+") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        body = fh.read().rstrip("\n")
        fh.seek(0)
        fh.write(body + "\n\n" + header + "\n\n" + result.strip() + "\n")
        fh.truncate()


def survey_session() -> list[str]:
    """The flags that run the `survey` agent's definition as the session
    itself: its body with the appendix a worker reads as the system prompt,
    and the model and effort the definition names. Empty when the definition
    is missing."""
    agents = json.loads(prompts.worker_agents(str(prompts.append_path())) or "{}")
    agent = agents.get("survey")
    if not agent:
        return []
    flags = ["--system-prompt", agent["prompt"]]
    for key in ("model", "effort"):
        if agent.get(key):
            flags += [f"--{key}", agent[key]]
    return flags


def survey_kill(proc: subprocess.Popen) -> None:
    """End the run's session and everything it started.

    A session already waited for is left alone: its pid is free for the next
    process the machine starts, and the kill would reach that one's whole
    session group. A session whose own process has ended, with something it
    started still running, has not been waited for, and the group kill takes
    what it left.
    """
    if proc.returncode is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        proc.kill()


def run_survey(path: Path, plan: dict, run_dir: Path) -> str:
    """One survey: a `claude -p` session that runs under the `survey` agent's
    own definition. It hands back the report the session returned, and an
    empty string when the session returned none.

    The session runs in a session group of its own, so the timeout takes the
    tools it left running with it. A process the session leaves behind holds
    the pipe this call reads open, and the read would go on past the run.
    """
    scope = ("the whole corpus" if plan["scope"] is None
             else "the solvers " + ", ".join(plan["scope"]))
    brief = config.SURVEY_BRIEF.format(entry=path.relative_to(config.ROOT),
                                       scope=scope,
                                       scratch=run_dir.relative_to(config.ROOT))
    cmd = [config.CLAUDE, "-p", brief, *config.SURVEY_FLAGS, *survey_session()]
    result = ""
    with open(run_log(run_dir), "ab") as log:
        proc = subprocess.Popen(cmd, cwd=config.ROOT, env=config.WORKER_ENV,
                                stdout=subprocess.PIPE, stderr=log,
                                start_new_session=True)
        timer = threading.Timer(config.SURVEY_TIMEOUT, survey_kill, args=(proc,))
        timer.start()
        try:
            for line in proc.stdout:
                log.write(line)
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if ev.get("type") == "result" and not ev.get("is_error"):
                    result = (ev.get("result") or "").strip()
            proc.wait()
        finally:
            timer.cancel()
    return result


def run_log(run_dir: Path) -> Path:
    """The file the run's stream and its session's errors go to."""
    return run_dir / "session.log"


def survey_entry(path: Path, force: bool = False) -> int:
    """Survey the entry once, and file the result in it. The return is the
    command's exit code.

    The lock file holds one survey per entry. The entry is read again under
    the lock: a caller that waited finds the result the run before it filed,
    and the entry is current.
    """
    started = time.time()
    scratch = config.ROOT / ".scratch" / "surveys" / path.stem
    scratch.mkdir(parents=True, exist_ok=True)
    with open(scratch / "lock", "w") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        text = path.read_text()
        if CLOSED_LINE.search(text) and not force:
            print(f"{path.name} is closed. Strike its `Closed:` line to reopen it, "
                  "or pass --force.", file=sys.stderr)
            return 1
        if filed_since(text, started):
            print(f"{path.name}: the {newest_survey(text)} survey covers it.")
            return 0
        try:
            plan = survey_plan(text)
        except ScopeUnknown as exc:
            print(f"{path.name}: the solvers in scope could not be listed: {exc}",
                  file=sys.stderr)
            return 1
        if plan is None:
            print(f"{path.name} is current.")
            return 0
        at = time.time()
        run_dir = scratch / time.strftime(RUN_STAMP, time.localtime(at))
        run_dir.mkdir(parents=True, exist_ok=True)
        try:
            result = run_survey(path, plan, run_dir)
        except OSError as exc:
            print(f"{path.name}: the survey session could not start: {exc}",
                  file=sys.stderr)
            return 1
        if not result:
            print(f"{path.name}: the survey returned no report. "
                  f"See {run_log(run_dir)}.", file=sys.stderr)
            return 1
        append_survey(path, survey_header(plan, at), result)
        print(f"{path.name}: the result of the {survey_minute(at)} survey is filed.")
        return 0
