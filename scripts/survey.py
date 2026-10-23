"""Survey one lib proposals entry and file the result in it.

    uv run python scripts/survey.py <entry>

A run that starts prints its run directory and the `session.log` under it. A
run may take up to an hour; when it ends, the entry holds the report under
a `Survey:` line of its own.

The scope is every solver when the entry holds no result, and otherwise
the solvers written since the entry's newest `Survey:` time. An entry with no
such solver is current, and the command runs nothing. A closed entry is
refused.
"""

import argparse
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

from engine import checkout

ROOT = checkout.ROOT

# The line the protocol reads, and the line that says the entry is closed.
SURVEY_LINE = re.compile(r"^Survey:[ \t]*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})", re.M)
CLOSED_LINE = re.compile(r"^Closed:", re.M)
SURVEY_STAMP = "%Y-%m-%d %H:%M"
RUN_STAMP = "%Y-%m-%d-%H%M%S"
PROPS = ROOT / "docs" / "wf-solver" / "proposals"
SURVEY_TIMEOUT = 3600  # seconds a survey session may run
SURVEY_FLAGS = [
    "--output-format", "stream-json", "--verbose",
    "--permission-mode", "acceptEdits",
    "--allowedTools", "Bash", "Glob", "Grep", "Read", "Write",
    "--strict-mcp-config",
]
BRIEF = """Survey the lib proposals entry {entry} over {scope}.
Follow the survey the lib addition protocol states in docs/handbook/lib-protocol.md.
Write your files under {scratch}, and reply with the report to file under the entry's `Survey:` line."""
SURVEYS_DIR = checkout.work() / "surveys"
"""The directory of each entry's lock and runs, by the entry's name."""


def entry_path(name: str) -> Path:
    """The entry a caller names: an entry's name under
    docs/wf-solver/proposals/, or a path to a file there. A relative path is
    read from the repo root, so the directory the caller runs in does not
    change what the name reaches."""
    path = Path(name)
    if path.suffix != ".md":
        path = path.with_name(path.name + ".md")
    if len(path.parts) == 1:
        path = PROPS / path
    elif not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def proposals_dir() -> Path:
    """The directory the entries live in."""
    return PROPS.resolve()


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
    """Whether the entry has a result from the minute of that clock
    reading or a later one. A caller that waited for the lock reads its own
    arrival against the result the run before it filed. A `Survey:` line
    gives its time to the minute, so the clock reading is taken to its own
    minute first."""
    when = newest_survey(text)
    if when is None or not survey_result(text):
        return False
    filed = survey_time(when)
    return filed is not None and filed >= at - at % 60


def survey_time(when: str) -> float | None:
    """A `Survey:` line's time as a clock reading, or None when the line
    gives a time no clock holds."""
    try:
        return time.mktime(time.strptime(when, SURVEY_STAMP))
    except ValueError:
        return None


class ScopeUnknown(Exception):
    """The runner could not list the solvers a survey since a time covers."""


class TimeUnknown(Exception):
    """The entry's newest `Survey:` line gives a time no clock holds."""


def survey_scope(when: str) -> list[str]:
    """The solvers a survey since that time covers, as the runner lists
    them. The working tree's changed solvers count as newer than any time, so
    the scope is the solvers in the commits after that time plus the changed
    solvers in the working tree. A runner that refuses raises: no answer and
    an empty scope read the same way otherwise, and the entry would pass as
    current with the survey it is owed never run."""
    out = subprocess.run(["uv", "run", "python", "scripts/run_dl.py", "since", when],
                         cwd=ROOT, capture_output=True, text=True)
    if out.returncode != 0:
        raise ScopeUnknown((out.stderr or out.stdout).strip()
                           or f"run_dl.py since {when!r} failed")
    return out.stdout.split()


def survey_plan(text: str) -> dict | None:
    """What the entry is owed: the time the survey runs from and the solvers
    in its scope, or None when the entry is current.

    An entry with no `Survey:` line, and an entry whose newest such line
    has no result, are surveyed over every solver. An entry with a
    result is surveyed over the solvers written since that line's time, which
    are the solvers in the commits after that time plus the changed solvers in
    the working tree; with no such solver the entry is current. A newest
    `Survey:` line whose time no clock holds raises: the scope it stands for
    cannot be read.
    """
    when = newest_survey(text)
    if when is None or not survey_result(text):
        return {"since": None, "scope": None}
    if survey_time(when) is None:
        raise TimeUnknown(f"Survey: {when}")
    scope = survey_scope(when)
    return {"since": when, "scope": scope} if scope else None



def survey_header(plan: dict, at: float) -> str:
    """The `Survey:` line the run's result goes under: its time, and the time
    its scope runs from. `run_dl.py since` lists that scope again from git:
    the working tree's changed solvers count as newer than any time, so the
    scope is the commits after that time plus the working tree."""
    stamp = survey_minute(at)
    if plan["scope"] is None:
        return f"Survey: {stamp} — every solver."
    return f"Survey: {stamp} — the solvers since {plan['since']}."


SOUND_LINE = re.compile(r"\n\s*`?\*[a-z]+\*`?\s*$")


def append_survey(path: Path, header: str, result: str) -> None:
    """Add the `Survey:` line and the run's report at the end of the entry.
    The report is filed as the session returned it, stripped of surrounding
    whitespace and of a closing sound-name line, `*tink*`, backticked or not,
    that the session's reply style adds.

    The caller holds the entry's lock, which orders this module's own writers
    of the entry against each other. A session that edits the entry with its
    own tools takes no lock, so the append and such an edit are not ordered
    against each other.
    """
    with open(path, "r+") as fh:
        body = fh.read().rstrip("\n")
        fh.seek(0)
        report = SOUND_LINE.sub("", result.strip()).strip()
        fh.write(body + "\n\n" + header + "\n\n" + report + "\n")
        fh.truncate()


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


def survey_cmd(path: Path, plan: dict, run_dir: Path) -> list[str]:
    """The command one run launches: the CLI in print mode, with the flags
    that let the session read the corpus and write under the run's scratch
    path, and a brief that names the entry, the scope and that path."""
    scope = ("every solver" if plan["scope"] is None
             else "the solvers " + ", ".join(plan["scope"]))
    brief = BRIEF.format(entry=path.relative_to(ROOT), scope=scope,
                         scratch=checkout.shown(run_dir, ROOT))
    # The brief may open with "-", which the CLI takes for an option unless
    # it follows "--".
    return ["claude", "-p", *SURVEY_FLAGS, "--", brief]


def run_survey(cmd: list[str], run_dir: Path) -> str:
    """One survey: the `claude -p` session the command names. It hands back
    the report the session returned, and an empty string when the session
    returned none.

    The session runs in a session group of its own, so the timeout takes the
    tools it left running with it. A process the session leaves behind holds
    the pipe this call reads open, and the read would go on past the run.
    """
    result = ""
    with open(run_log(run_dir), "ab") as log:
        proc = subprocess.Popen(cmd, cwd=ROOT,
                                stdout=subprocess.PIPE, stderr=log,
                                start_new_session=True)
        timer = threading.Timer(SURVEY_TIMEOUT, survey_kill, args=(proc,))
        timer.start()
        assert proc.stdout is not None
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
    scratch = SURVEYS_DIR / path.stem
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
        except TimeUnknown as exc:
            print(f"{path.name}: the newest `Survey:` line carries a time no "
                  f"clock holds: {exc}", file=sys.stderr)
            return 1
        if plan is None:
            print(f"{path.name} is current.")
            return 0
        at = time.time()
        run_dir = scratch / time.strftime(RUN_STAMP, time.localtime(at))
        run_dir.mkdir(parents=True, exist_ok=True)
        print(f"{path.name}: the run writes under {run_dir}. "
              f"Its session's stream goes to {run_log(run_dir)}.", flush=True)
        try:
            cmd = survey_cmd(path, plan, run_dir)
        except OSError as exc:
            print(f"{path.name}: the session's brief could not be read: {exc}",
                  file=sys.stderr)
            return 1
        try:
            result = run_survey(cmd, run_dir)
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


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entry", help="a path under docs/wf-solver/proposals/, "
                                  "or the entry's name")
    ap.add_argument("--force", action="store_true",
                    help="survey a closed entry")
    args = ap.parse_args(argv)
    path = entry_path(args.entry)
    if not in_proposals(path):
        print(f"{path} is not an entry: the entries are the files under "
              f"{proposals_dir()}.", file=sys.stderr)
        return 1
    if not path.is_file():
        print(f"no entry at {path}", file=sys.stderr)
        return 1
    return survey_entry(path, force=args.force)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
