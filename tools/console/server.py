#!/usr/bin/env python3
"""Review console for batch solver workers.

Serves the console UI, launches `claude -p` workers in waves, resumes them
with review comments, and commits approved solvers.

    uv run python tools/console/server.py [--port 8347]

Env:
    CONSOLE_FAKE=1     use fake_worker.py instead of claude (UI demo)
    CONSOLE_CLAUDE     claude binary (default: claude)
    CONSOLE_CREATE_MODEL   create-phase model (default: claude-opus-5)
    CONSOLE_REFINE_MODEL   refine-phase model (default: claude-fable-5)
    CONSOLE_COMMIT_MODEL   committer model (default: claude-opus-5)
"""

import argparse
import fcntl
import functools
import hashlib
import json
import os
import queue
import re
import signal
import stat
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Run as a script, but loaded by file path in tests, where this directory is
# not on the import path.
sys.path.append(str(Path(__file__).resolve().parent))

import quota  # noqa: E402
from calibrate import CACHE_READ, rates  # noqa: E402

from dl.context import appendix  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATE_DIR = Path(os.environ.get("CONSOLE_STATE_DIR", HERE / "state"))
STATE_FILE = STATE_DIR / "state.json"
SAMPLE_FILE = STATE_DIR / "usage-samples.jsonl"
LOG_DIR = STATE_DIR / "logs"
SOLVERS = ROOT / "programs" / "solvers"
DOCS = ROOT / "docs" / "wf-solver"
TASKS = ROOT / "data" / "tasks"
REF_DIR = (ROOT.parent / "arc-synth-bun").resolve()

FAKE = os.environ.get("CONSOLE_FAKE") == "1"
CLAUDE = os.environ.get("CONSOLE_CLAUDE", "claude")
MODELS = {"create": os.environ.get("CONSOLE_CREATE_MODEL", "claude-opus-5"),
          "refine": os.environ.get("CONSOLE_REFINE_MODEL", "claude-fable-5")}
COMMIT_MODEL = os.environ.get("CONSOLE_COMMIT_MODEL", "claude-opus-5")

WORKER_FLAGS = [
    "--output-format", "stream-json", "--input-format", "stream-json", "--verbose",
    "--permission-mode", "acceptEdits",
    "--allowedTools",
    "Bash(uv run:*)", "Bash(cat:*)", "Bash(ls:*)", "Bash(souffle:*)",
    "--add-dir", str(REF_DIR),
    "--exclude-dynamic-system-prompt-sections",
]
STAGGER_TIMEOUT = 120  # seconds to wait for the first worker's first API response
# What a worker session is allowed to leave behind. The brief and the
# leftovers check read the same list, so widening it moves both.
COMMIT_SCOPE = ["programs", "docs/wf-solver", "src/dl", "scripts", "tests"]
COMMIT_BRIEF = f"""Commit the changes that solver workers left in the working tree.

Scope: files git already tracks, under {", ".join(p + "/" for p in COMMIT_SCOPE)}. A session that hits a gap in the runner fixes it there, so those changes belong in the same sweep. Never stage untracked files, and leave changes outside that scope alone.

Read git status and the diffs, and recent git log for message style. Group the changes into clean commits the way the log does; write each message from what the diff shows."""
COMMITTER_FLAGS = [
    "--output-format", "json",
    "--allowedTools", "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)",
    "Bash(git show:*)", "Bash(git add:*)", "Bash(git commit:*)",
    "--add-dir", str(REF_DIR),
    "--exclude-dynamic-system-prompt-sections",
]

LOCK = threading.RLock()
COND = threading.Condition(LOCK)
STATE = {"seq": 0, "wave": 0, "items": []}
PROCS: dict[tuple[str, str], dict] = {}
DEFERRED = queue.Queue()
DEFERRED_THREAD = None
STOP = object()
SHUTTING_DOWN = False
RELOADING = False
USAGE: list[dict] = []  # account rate-limit windows, refreshed in background
COMMITTER = {"running": False, "note": None}
WORKER_HANDOFF_ENV = "CONSOLE_WORKER_HANDOFF"


# ---------- item lifecycle ----------
#
# An item runs as two linked sessions: `create` writes the solver and ends its
# pass with a handoff report, `refine` takes over from that report. `phase`
# names the session that owns the item; the handoff flips it once, and only
# from a turn launched with the handoff flag — the wave's first create turn,
# or a `handoff` comment that asks for a fresh report. A stopped or dead turn
# never hands off. Comments target either session; a debug turn to `create`
# after the handoff does not hand off again.
#
# A turn ends in NEEDS_REVIEW, whether it reported a result or died mid-flight;
# a worker that never reported a session falls back to QUEUED instead. `load`
# applies that same fallback to turns a console restart cut short, so no ACTIVE
# state survives a restart. Comments relaunch from NEEDS_REVIEW or APPROVED,
# approval moves between those two, and a commit ends at COMMITTED.
# console.html renders the same six names — keep the two in step.

QUEUED = "queued"              # picked for a wave, worker not started
RUNNING = "running"            # the item's first turn is in flight
COMMENTED = "commented"        # a follow-up turn from a review comment is in flight
NEEDS_REVIEW = "needs-review"  # a turn landed; the user has not ruled on it
APPROVED = "approved"          # ready for the next commit
COMMITTED = "committed"        # committed; dropped when the next wave starts

ACTIVE = (RUNNING, COMMENTED)


def active(it: dict) -> bool:
    """Whether an item has a turn or handoff in flight."""
    return (it.get("handoff_pending", False) or
            any(w["state"] in ("spawning", "sending", "running")
                for (item_id, _), w in PROCS.items() if item_id == it["id"]))


class Reject(Exception):
    """An action refused for a reason worth showing the user."""


def action(fn):
    """Wrap an `act_*` body that takes the resolved item: hold LOCK, resolve
    the id, turn Reject into an error reply, and bump only when it lands."""
    @functools.wraps(fn)
    def wrapped(item_id: str, *args, **kw) -> dict:
        with LOCK:
            it = find(item_id)
            if it is None:
                return {"error": "unknown item"}
            try:
                res = fn(it, *args, **kw)
            except Reject as e:
                return {"error": str(e)}
        bump()
        return res or {"ok": True}
    return wrapped


def require_idle(it: dict) -> None:
    if RELOADING:
        raise Reject("server reload in progress — wait for it to finish")
    if active(it):
        raise Reject("worker busy — wait for the turn to land")


# ---------- state ----------

def bump() -> None:
    with COND:
        STATE["seq"] += 1
        save()
        COND.notify_all()


def save() -> None:
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(STATE, indent=1))
    tmp.replace(STATE_FILE)


def load() -> None:
    if not STATE_FILE.exists():
        return
    STATE.update(json.loads(STATE_FILE.read_text()))
    for it in STATE["items"]:
        migrate(it)
        if it["state"] in ACTIVE:
            it.pop("pending_handoff", None)
            it.pop("handoff_pending", None)
            say(it, event("interrupted by console restart"))
            turn_died(it, it.get("last_turn_phase") or it["phase"])


def migrate(it: dict) -> None:
    """Fold state written by earlier console versions forward."""
    if "sessions" not in it:
        old = it.pop("session", None)
        it["sessions"] = {"create": None, "refine": old}
        it["phase"] = "refine" if old else "create"
        it["refined"] = bool(old)
        it["lastActive"] = {"create": None, "refine": it.get("lastActive")}
        for m in it.get("feed", []):
            m.setdefault("sess", "refine")
        if isinstance(it.get("reverted"), list):
            it["reverted"] = {"files": it["reverted"], "phase": "refine"}
    if "pre" in it:
        return
    it["pre"] = {"hash": it.pop("hash_before", ""),
                 "solver": it.pop("snap", ""),
                 "proposals": it.pop("snap_prop", ""),
                 "dirty": it.pop("dirty_before", False),
                 "files": it.pop("turn_files", None) or {}}


def find(item_id: str) -> dict | None:
    for it in STATE["items"]:
        if it["id"] == item_id:
            return it
    return None


def touch(it: dict) -> None:
    """Mark the item's /api/item payload — feed and files — as changed, so a
    polling console refetches it."""
    it["ver"] = it.get("ver", 0) + 1


def say(it: dict, entry: dict, sess: str | None = None) -> None:
    entry.setdefault("sess", sess or it.get("phase", "refine"))
    it["feed"].append(entry)
    touch(it)


def event(text: str) -> dict:
    return {"kind": "event", "text": text}


def pre(it: dict) -> dict:
    """The item's pre-turn snapshot, empty before its first turn."""
    return it.setdefault("pre", {"hash": "", "solver": "", "proposals": "",
                                 "dirty": False, "files": {}})


def solver_path(item_id: str) -> Path:
    return SOLVERS / f"{item_id}.dl"


def solver_hash(item_id: str) -> str:
    p = solver_path(item_id)
    return hashlib.sha1(p.read_bytes()).hexdigest() if p.exists() else ""


def solver_text(item_id: str) -> str:
    p = solver_path(item_id)
    return p.read_text() if p.exists() else ""


def prop_text() -> str:
    p = DOCS / "proposals.md"
    return p.read_text() if p.exists() else ""


def title_of(item_id: str) -> str:
    p = solver_path(item_id)
    if not p.exists():
        return ""
    for line in p.read_text().splitlines()[:4]:
        m = re.match(r"//\s*((concept|family):.*)", line)
        if m:
            return m.group(1)
    return ""


# ---------- worker prompt ----------

def skill_body() -> str:
    """SKILL.md minus frontmatter and <!-- batch:skip --> regions."""
    text = (ROOT / ".claude" / "skills" / "session" / "SKILL.md").read_text()
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    text = re.sub(r"<!-- batch:skip -->.*?<!-- /batch:skip -->\n?", "", text, flags=re.S)
    return text.strip()


def build_append(wave: int) -> Path:
    """The worker's system-prompt appendix: the skill body plus the docs and
    lib.dl, in the projection dl.context renders. Byte-identical for both
    phases, so the two sessions share the longest possible prompt prefix."""
    path = STATE_DIR / f"wave-{wave:02d}-append.md"
    path.write_text(skill_body() + "\n" + appendix(DOCS))
    return path


# ---------- first messages ----------
#
# Both phases open with the same task block, so the messages share a prefix
# beyond the appendix; only the tail after it diverges.

CREATE_BRIEF = """You are the create phase of a two-session flow: you create the solver, then a separate refine session takes over.

Do steps 1-3 of the creation pass with the data above; do not re-read the data. Skip steps 4-5. When a question about the data comes up, run something that answers it rather than settling it in your head. In place of the review, end your turn with a handoff report addressed to the refine session: the model claim, each choice point with the alternatives you considered and why you discarded them, and the audit findings and judgment calls. Make it complete enough that the refine session rederives nothing."""

HANDOFF_BRIEF = """Write the handoff report for the refine session that takes over from you: the model claim, each choice point with the alternatives you considered and why you discarded them, and the audit findings and judgment calls. Cover the whole session, including turns after any earlier report. Make it complete enough that the refine session rederives nothing."""

NUDGE_BRIEF = """Your last turn was cut off at the output limit while it was still thinking.

Stop trying to settle the task in your head. Take the smallest thing you are still unsure about and run something that answers it. Partial and wrong is fine.

Do not spend the whole next turn thinking. If you do, it will be your final turn."""

BAIL_BRIEF = """Two turns went entirely to thinking, so the task moves to the refine session now. Stop solving.

Write a short state of play from what is already in front of you, without working anything out again:

- how you read the task
- what you ran, and what came back
- where you got stuck, and what you would try next

Keep it brief and factual. The refine session needs your dead ends and your open question, not a full account."""

# Thinking tokens with no tool call or text before the feed says so. Well
# above a working turn's bursts, and far enough below the 64k output cap that
# the warning still arrives with the generation in progress.
RUNAWAY_THINK = 40_000
# Seconds between transcript reads. The CLI resubmits a capped generation on
# its own and the retry carries none of the thinking, so every poll of delay
# risks another full output budget spent on the same dead end.
CAP_POLL = 5

REFINE_BRIEF = """You are the refine phase of a two-session flow: a create session did steps 1-3 of the creation pass and left the handoff report above.

Read programs/solvers/{tid}.dl first — the report describes it, but you edit the file itself. Then refine the solver: judge the model and the code yourself, and edit what falls short. Then do steps 2-5 of the creation pass, so your own edits get the simplify and prune treatment too. Trust the report for what was already tried; do not rederive discarded alternatives."""


def task_block(tid: str) -> str:
    p = TASKS / f"{tid}.json"
    task = p.read_text().rstrip() if p.exists() else "(missing)"
    return f"Task: {tid}\n\n## data/tasks/{tid}.json\n\n```json\n{task}\n```"


def create_message(tid: str) -> str:
    p = REF_DIR / "programs" / "solvers" / f"{tid}.ts"
    ref = p.read_text().rstrip() if p.exists() else "(missing)"
    return (task_block(tid)
            + f"\n\n## ../arc-synth-bun/programs/solvers/{tid}.ts (reference)\n\n"
            + f"```ts\n{ref}\n```\n\n" + CREATE_BRIEF)


def refine_message(it: dict) -> str:
    report = (it.get("handoff_report") or "").strip() \
        or "(the create session left no report)"
    return (task_block(it["id"])
            + "\n\n## handoff report from the create session\n\n" + report
            + "\n\n" + REFINE_BRIEF.format(tid=it["id"]))


# ---------- workers ----------

class AdoptedProcess:
    """The small Popen surface used by worker lifecycle code after exec."""

    def __init__(self, pid: int, stdin, stdout):
        self.pid = pid
        self.stdin = stdin
        self.stdout = stdout
        self.returncode = None
        self._wait_lock = threading.Lock()

    def _record(self, status: int) -> int:
        self.returncode = os.waitstatus_to_exitcode(status)
        return self.returncode

    def poll(self):
        with self._wait_lock:
            if self.returncode is not None:
                return self.returncode
            try:
                pid, status = os.waitpid(self.pid, os.WNOHANG)
            except ChildProcessError:
                return self.returncode
            return self._record(status) if pid else None

    def wait(self, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            with self._wait_lock:
                if self.returncode is not None:
                    return self.returncode
                flags = 0 if deadline is None else os.WNOHANG
                try:
                    pid, status = os.waitpid(self.pid, flags)
                except ChildProcessError:
                    if self.returncode is not None:
                        return self.returncode
                    raise
                if pid:
                    return self._record(status)
            if deadline is not None and time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired(str(self.pid), timeout)
            time.sleep(.01)

    def terminate(self):
        os.kill(self.pid, signal.SIGTERM)

    def kill(self):
        os.kill(self.pid, signal.SIGKILL)


def start_worker_threads(worker: dict) -> None:
    worker["writer"] = threading.Thread(target=writer, args=(worker,), daemon=True)
    worker["reader"] = threading.Thread(target=reader, args=(worker,), daemon=True)
    worker["writer"].start()
    worker["reader"].start()


def worker_manifest() -> dict:
    workers = []
    inheritable = []
    try:
        for (item_id, phase), worker in PROCS.items():
            proc = worker["proc"]
            stdin_fd, stdout_fd = proc.stdin.fileno(), proc.stdout.fileno()
            for fd in (stdin_fd, stdout_fd):
                os.set_inheritable(fd, True)
                inheritable.append(fd)
            it = find(item_id)
            workers.append({"item": item_id, "phase": phase, "pid": proc.pid,
                             "stdin_fd": stdin_fd, "stdout_fd": stdout_fd,
                             "session": it["sessions"].get(phase) if it else None,
                             "turn_seq": worker["turn_seq"], "state": worker["state"],
                             "started": worker["started"]})
        return {"server_pid": os.getpid(), "workers": workers}
    except Exception:
        # A failed handoff must not leak descriptors into later child processes.
        for fd in inheritable:
            try:
                os.set_inheritable(fd, False)
            except OSError:
                pass
        raise


def read_worker_handoff() -> dict:
    raw = os.environ.pop(WORKER_HANDOFF_ENV, None)
    if not raw:
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def _handoff_child(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        waited, _ = os.waitpid(pid, os.WNOHANG)
        return waited == 0
    except (ChildProcessError, OSError):
        return False


def adopt_workers(manifest: dict) -> None:
    entries = manifest.get("workers", []) if isinstance(manifest, dict) else []
    valid_source = (manifest.get("server_pid") == os.getpid()
                    if isinstance(manifest, dict) else False)
    for entry in entries:
        proc = None
        fds = []
        child = False
        try:
            item_id, phase = entry["item"], entry["phase"]
            if not valid_source:
                raise ValueError("manifest came from a different server process")
            pid = int(entry["pid"])
            fds = [int(entry["stdin_fd"]), int(entry["stdout_fd"])]
            it = find(item_id)
            if not it or phase not in ("create", "refine") or \
                    entry.get("state") != "idle" or entry.get("started") is not None or \
                    it["sessions"].get(phase) != entry.get("session"):
                raise ValueError("manifest does not match idle state")
            if not _handoff_child(pid):
                raise ValueError("worker is not a live child")
            child = True
            modes = [fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE for fd in fds]
            if not all(stat.S_ISFIFO(os.fstat(fd).st_mode) for fd in fds) or \
                    modes != [os.O_WRONLY, os.O_RDONLY]:
                raise ValueError("worker pipe is not a FIFO")
            for fd in fds:
                os.set_inheritable(fd, False)
            stdin = os.fdopen(fds[0], "w", buffering=1)
            stdout = os.fdopen(fds[1], "r", buffering=1)
            proc = AdoptedProcess(pid, stdin, stdout)
            worker = {"item_id": item_id, "phase": phase, "proc": proc,
                      "outbound": queue.Queue(), "state": "idle",
                      "turn_seq": int(entry.get("turn_seq", 0)), "started": None,
                      "trigger": None, "handoff": False, "seen": set(),
                      "got_result": False, "think_run": 0, "reqs": {},
                      "session_seen": bool(entry.get("session"))}
            PROCS[(item_id, phase)] = worker
            start_worker_threads(worker)
        except (KeyError, TypeError, ValueError, OSError) as exc:
            print(f"worker handoff rejected: {exc}", file=sys.stderr)
            if isinstance(entry, dict):
                it = find(entry.get("item"))
                phase = entry.get("phase")
                if it is not None and phase in ("create", "refine"):
                    lost_session = it["sessions"].get(phase)
                    it["sessions"][phase] = None
                    say(it, event(f"{phase} session lost on reload: {lost_session}"), sess=phase)
            for fd in fds:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if proc is not None and proc.poll() is None:
                proc.terminate()
            elif child:
                try:
                    os.kill(pid, signal.SIGTERM)
                    os.waitpid(pid, 0)
                except (ChildProcessError, OSError):
                    pass

def record_edit(it: dict, fp: str) -> None:
    """First edit of a file in a turn: keep its pre-edit content for the
    per-file diff tabs. The tool_use event streams before the tool runs."""
    try:
        rel = str(Path(fp).resolve().relative_to(ROOT))
    except ValueError:
        return
    p_ = pre(it)
    if rel in p_["files"]:
        return
    if rel == f"programs/solvers/{it['id']}.dl":
        p_["files"][rel] = p_["solver"]
    elif rel == "docs/wf-solver/proposals.md":
        p_["files"][rel] = p_["proposals"]
    else:
        p = ROOT / rel
        p_["files"][rel] = p.read_text() if p.exists() else ""


def task_ask(inp: dict) -> str:
    """The brief a Task call gives its subagent, as feed markdown."""
    head = " · ".join(x for x in (str(inp.get("subagent_type") or "").strip(),
                                  str(inp.get("description") or "").strip()) if x)
    prompt = str(inp.get("prompt") or "").strip()
    return f"**{head}**\n\n{prompt}" if head else prompt


def tool_label(name: str, inp: dict) -> str | None:
    if name in ("TodoWrite", "ToolSearch", "TaskUpdate", "TaskCreate"):
        return None
    if name in ("Edit", "Write", "Read", "NotebookEdit"):
        fp = str(inp.get("file_path", ""))
        rel = fp.removeprefix(str(ROOT) + "/")
        return f"{name} {rel}"
    if name == "Bash":
        cmd = str(inp.get("command", "")).replace("\n", " ")
        return f"Bash {cmd[:90]}"
    if name in ("Grep", "Glob"):
        return f"{name} {inp.get('pattern', '')}"
    return name


# Leading words of a message whose cadence ends in Simplify and Prune, so the
# turn's edits land already clean.
CLEAN_TRIGGERS = ("cleanup", "fit")


def launch(it: dict, message: str, phase: str, trigger: str | None = None,
           handoff: bool = False, admitted: bool = False,
           escalated: bool = False) -> None:
    """Spawn the phase worker if needed, then enqueue one turn. The nudge and
    the bail are turns of one chain and keep its count; every other turn starts
    its own, so a turn asked to think hard is judged on its own stretches."""
    if RELOADING and not admitted:
        raise Reject("server reload in progress — wait for it to finish")
    if not escalated:
        it.setdefault("runaway", {}).pop(phase, None)
    # The CLI reads a slash command only when it opens the message, so a turn
    # carrying one skips the notices below and leaves them, and the watermarks
    # behind them, for the next real turn to deliver.
    slash = message.startswith("/")
    rv = it.get("reverted")
    if slash:
        pass
    elif rv and rv.get("phase") == phase:
        it.pop("reverted")
        message = ("<system-reminder>The user reverted the file edits from your "
                   f"previous turn; {', '.join(rv['files'])} on disk is back to its "
                   "pre-turn state. Re-read before editing.</system-reminder>\n\n"
                   + message)
    else:
        seen = it.get("seen_hash", {}).get(phase)
        if seen is not None and seen != solver_hash(it["id"]):
            message = ("<system-reminder>programs/solvers/"
                       f"{it['id']}.dl changed on disk since your last turn. "
                       "Re-read before editing.</system-reminder>\n\n" + message)
    it["last_turn_phase"] = phase
    key = (it["id"], phase)
    worker = PROCS.get(key)
    if worker is None:
        if it["sessions"].get(phase):
            say(it, event(f"{phase} worker restarting — resuming its session"),
                sess=phase)
        worker = spawn_worker(it, phase)
    it["pre"] = {"hash": solver_hash(it["id"]), "solver": solver_text(it["id"]),
                 "proposals": prop_text(), "dirty": it["dirty"], "files": {},
                 "slash": slash}
    worker["turn_seq"] += 1
    worker.update(state="sending", started=time.time(), trigger=trigger,
                  handoff=handoff, seen=set(), got_result=False, think_run=0,
                  reqs={})
    worker["outbound"].put_nowait({"type": "user",
        "message": {"role": "user", "content": message}})


def worker_cmd(it: dict, phase: str) -> list[str]:
    if FAKE:
        return [sys.executable, str(HERE / "fake_worker.py"), it["id"], phase]
    cmd = [CLAUDE, "--append-system-prompt", Path(it["append"]).read_text(),
           *WORKER_FLAGS]
    if MODELS[phase]:
        cmd += ["--model", MODELS[phase]]
    if it["sessions"].get(phase):
        cmd += ["--resume", it["sessions"][phase]]
    return cmd


def spawn_worker(it: dict, phase: str) -> dict:
    item_id = it["id"]
    cmd = worker_cmd(it, phase)
    log = open(LOG_DIR / f"{item_id}.log", "ab")
    proc = subprocess.Popen(cmd, cwd=ROOT, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=log, text=True)
    log.close()
    worker = {"item_id": item_id, "phase": phase, "proc": proc,
              "outbound": queue.Queue(), "state": "spawning", "turn_seq": 0,
              "started": None, "trigger": None, "handoff": False, "seen": set(),
              "got_result": False, "session_seen": False, "think_run": 0,
              "reqs": {}}
    # A new process restarts the session's running totals.
    it.setdefault("cost_seen", {})[phase] = {"total": 0, "fable": 0}
    # A resumed session keeps its context, so its cache baseline stands and
    # a cold resume shows up as a DROP.
    if not it["sessions"].get(phase):
        it.setdefault("cache_read", {}).pop(phase, None)
    PROCS[(item_id, phase)] = worker
    start_worker_threads(worker)
    worker["state"] = "idle"
    return worker


def writer(worker: dict) -> None:
    proc = worker["proc"]
    while True:
        event = worker["outbound"].get()
        if event is STOP:
            return
        try:
            data = json.dumps(event) + "\n"
            written = proc.stdin.write(data)
            proc.stdin.flush()
            if written != len(data):
                proc.terminate()
                return
        except (BrokenPipeError, OSError, ValueError):
            try:
                proc.terminate()
            except OSError:
                pass
            return


def reader(worker: dict) -> None:
    item_id, phase, proc = worker["item_id"], worker["phase"], worker["proc"]
    first_response = FIRST_RESPONSE.get(item_id)
    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            try:
                handle_event(worker, ev, first_response)
            except Exception as exc:  # a bad event must not wedge the turn
                with LOCK:
                    it = find(item_id)
                    if it:
                        say(it, event(f"⚠ reader error, event skipped: {exc!r}"),
                            sess=phase)
                        if worker["state"] not in ("sending", "running") and \
                                it["state"] in (RUNNING, COMMENTED):
                            turn_died(it, phase)  # the crash cut the turn's landing
            bump()
    except (OSError, ValueError):
        # Shutdown closes the pipe out from under a blocked read. There is
        # nothing left to drain either way, so fall through to the cleanup.
        pass
    proc.wait()
    with LOCK:
        worker["outbound"].put_nowait(STOP)
        if PROCS.get((item_id, phase)) is worker:
            PROCS.pop((item_id, phase), None)
        worker["state"] = "dead"
        it = find(item_id)
        if it and worker["started"] is not None:
            tail = ""
            log = LOG_DIR / f"{item_id}.log"
            if log.exists():
                tail = log.read_text(errors="replace")[-400:].strip()
            say(it, event(f"worker exited without result (code {proc.returncode}) — {tail}"),
                sess=phase)
            turn_died(it, phase)
    if first_response:
        first_response.set()
    bump()


def handle_event(worker: dict, ev: dict, first_response) -> None:
    """One stream event from a worker. Runs on the worker's reader thread."""
    item_id, phase = worker["item_id"], worker["phase"]
    with LOCK:
        it = find(item_id)
        kind = ev.get("type")
        if kind == "system" and ev.get("subtype") == "init":
            if it and not worker["session_seen"]:
                it["sessions"][phase] = ev.get("session_id") or it["sessions"].get(phase)
                worker["session_seen"] = True
            # A worker can start a turn on its own (a background-task
            # notification, for one); init marks only a turn the console sent.
            if worker["state"] == "sending":
                worker["state"] = "running"
        elif kind == "system" and ev.get("subtype") == "thinking_tokens":
            if it and worker["state"] in ("sending", "running"):
                worker["think_run"] = (worker.get("think_run", 0)
                                       + (ev.get("estimated_tokens_delta") or 0))
                if (worker["think_run"] >= RUNAWAY_THINK
                        and not worker.get("escalate")):
                    # Warn only. An interrupt here aborts the generation, and
                    # an aborted generation writes nothing — the reasoning is
                    # gone. A generation that runs to the cap lands in the
                    # transcript with its signature, which patch_capped turns
                    # into context the relaunch keeps. So the cap is the
                    # cheaper exit, at the cost of the rest of the budget.
                    worker["think_run"] = 0
                    say(it, event(f"long thinking — {RUNAWAY_THINK // 1000}k "
                                  "tokens with no actions yet"), sess=phase)
        elif kind == "assistant":
            if first_response:
                first_response.set()
            if not it:
                return
            msg = ev.get("message", {})
            mid = msg.get("id") or ""
            sub = bool(ev.get("parent_tool_use_id"))
            usage = msg.get("usage")
            if usage and mid and not sub and \
                    worker["state"] in ("sending", "running"):
                # One entry per request; a request's block events repeat the
                # same usage. Subagent requests run their own context.
                worker.setdefault("reqs", {})[mid] = usage
            for block in msg.get("content", []):
                entry, key = None, None
                if block.get("type") == "text" and block.get("text", "").strip():
                    entry = {"kind": "worker", "text": block["text"]}
                    key = (mid, "text", block["text"])
                elif block.get("type") == "tool_use":
                    name = block.get("name", "?")
                    inp = block.get("input", {}) or {}
                    if name in ("Edit", "Write", "NotebookEdit") and inp.get("file_path"):
                        record_edit(it, inp["file_path"])
                    if name == "Task":
                        entry = {"kind": "ask", "text": task_ask(inp)}
                        key = (mid, "task", block.get("id") or entry["text"])
                    else:
                        label = tool_label(name, inp)
                        if label:
                            entry = {"kind": "tool", "text": label}
                            key = (mid, "tool", block.get("id") or label)
                if entry and key not in worker["seen"]:
                    worker["seen"].add(key)
                    if sub or entry["kind"] == "ask":
                        entry["sub"] = True
                    say(it, entry, sess=phase)
            blocks = msg.get("content") or []
            if any(b.get("type") != "thinking" for b in blocks):
                worker["think_run"] = 0
            # The live CLI streams stop_reason as null on every assistant
            # event, so today this fires only for a stream that does report
            # the cap — the fake worker, or a CLI that starts filling the
            # field in. The transcript tail is the detector that works now.
            if (msg.get("stop_reason") == "max_tokens" and blocks and
                    all(b.get("type") == "thinking" for b in blocks) and
                    worker["state"] in ("sending", "running") and
                    not worker.get("escalate") and
                    (mid, "runaway") not in worker["seen"]):
                worker["seen"].add((mid, "runaway"))
                runaway_detected(it, worker, "hit the output cap with no actions")
        elif kind == "system" and ev.get("subtype") == "compact_boundary":
            if not it:
                return
            meta = ev.get("compact_metadata") or {}
            say(it, event("compacted · pre {pre:,} · post {post:,} · dropped {drop:,}".format(
                pre=meta.get("pre_tokens", 0), post=meta.get("post_tokens", 0),
                drop=meta.get("cumulative_dropped_tokens", 0))), sess=phase)
            # A compact turn reports no per-request usage, so this event is the
            # only word on the new context size until the next turn lands.
            post = meta.get("post_tokens")
            ctx = it.get("context", {}).get(phase)
            if ctx and isinstance(post, (int, float)) and post > 0:
                ctx["used"] = post
                ctx["percent"] = post / ctx["window"] * 100
                ctx["compactPct"] = compact_pct(post, ctx.get("model")
                                                or MODELS[phase], ctx.get("limiting"))
        elif kind == "result":
            if not it or worker["state"] not in ("sending", "running"):
                return
            worker["got_result"] = True
            reason = ev.get("terminal_reason", "completed")
            escalate = worker.pop("escalate", None)
            handoff = worker["handoff"]
            try:
                # The last messages may not have reached the tail's poll, and
                # leaving them unread would carry them into the next turn.
                if it["sessions"].get(phase):
                    try:
                        tail_turn(worker, it["sessions"][phase])
                    except OSError:
                        pass
                reqs = list(worker.get("reqs", {}).values())
                # A generation that reached the cap is recorded with its
                # thinking; one the interrupt caught in flight is not, so an
                # unfinished run is what the turn lost.
                lost = 0 if reason == "completed" else worker.get("think_run", 0)
                if reason == "completed":
                    finish_turn(it, ev, worker["trigger"], worker["started"],
                                phase, handoff, reqs)
                else:
                    if escalate:
                        pass  # the interrupt we sent landed; relaunched below
                    elif reason == "aborted_streaming":
                        say(it, event("stopped"), sess=phase)
                    else:
                        say(it, event(f"turn failed ({reason})"), sess=phase)
                    # A segment that never lands still spent quota, and this
                    # line is the only place it is ever counted.
                    say(it, event(turn_note(it, ev, phase, worker["started"],
                                            reqs, lost, done=False)),
                        sess=phase)
                    if not escalate:
                        turn_died(it, phase)
            finally:
                # The worker goes idle even if landing the turn blew up;
                # a wedged "running" state would block sends and reloads.
                worker.update(state="idle", started=None, trigger=None,
                              handoff=False, seen=set(), got_result=False,
                              think_run=0, reqs={})
            if escalate and reason != "completed":
                # The relaunch must come from a fresh process: the live one
                # holds the turn's history in memory, where the capped
                # thinking is already gone. A respawn rebuilds from the
                # transcript, which patch_capped repairs first.
                if PROCS.get((item_id, phase)) is worker:
                    PROCS.pop((item_id, phase))
                    worker["state"] = "dying"
                    worker["outbound"].put_nowait(STOP)
                DEFERRED.put_nowait(("revive", worker, escalate, handoff))
                ensure_drain()


def turn_died(it: dict, phase: str) -> None:
    """End-of-turn fallback when no result landed. A refine turn that died
    before reporting a session puts the item back in the create phase, where
    `handoff` can retry."""
    if phase == "refine" and not it["sessions"]["refine"]:
        it["phase"] = "create"
    it["state"] = NEEDS_REVIEW if it["sessions"][it["phase"]] else QUEUED
    it["updated"] = True


def transcript_of(session: str) -> Path | None:
    """The CLI's own record of a session."""
    return next(iter(quota.PROJECTS.glob(f"*/{session}.jsonl")), None)


def tail_rows(worker: dict, session: str) -> list[dict]:
    """Assistant messages the transcript gained since the last read. The first
    read only marks the position, so a resumed session's history stays behind
    us. Subagent rows belong to their own context and are skipped."""
    path = worker.get("tail_path")
    if path is None or path.name != f"{session}.jsonl":
        path = transcript_of(session)
        if path is None:
            return []
        worker["tail_path"] = path
        worker["tail_at"] = path.stat().st_size
        return []
    at = worker.get("tail_at", 0)
    with path.open("rb") as fh:
        fh.seek(at)
        chunk = fh.read()
    # A row still being written has no newline yet; leave it for the next read.
    cut = chunk.rfind(b"\n") + 1
    if not cut:
        return []
    worker["tail_at"] = at + cut
    rows = []
    for line in chunk[:cut].splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("type") == "assistant" and not row.get("isSidechain"):
            rows.append(row.get("message") or {})
    return rows


def tail_turn(worker: dict, session: str) -> str | None:
    """Report a generation that spent its whole output budget on thinking.

    The stream reports `stop_reason: null` on every assistant message, so a
    capped generation is legible only in the file."""
    capped = None
    for msg in tail_rows(worker, session):
        out = (msg.get("usage") or {}).get("output_tokens")
        blocks = msg.get("content") or []
        if (msg.get("stop_reason") == "max_tokens" and blocks
                and all(b.get("type") == "thinking" for b in blocks)):
            capped = f"spent {out or 0:,} output tokens on thinking alone"
    return capped


def patch_capped(path: Path) -> int:
    """Rewrite capped thinking-only rows so a resumed session keeps them.

    The CLI's history builder drops an assistant message that is nothing but
    thinking cut off at the output cap, and with it the signature that holds
    the only copy of the reasoning. Marked as a completed turn with a text
    block after the untouched thinking block, the message survives the
    builder, and the API decrypts the signature and restores the reasoning
    to the context. Call only with the worker process dead; the rewrite must
    not race the CLI's own appends."""
    patched, out = 0, []
    for line in path.read_text().splitlines(True):
        try:
            row = json.loads(line)
        except ValueError:
            out.append(line)
            continue
        msg = row.get("message") or {}
        blocks = msg.get("content") or []
        if (row.get("type") == "assistant" and not row.get("isSidechain")
                and msg.get("stop_reason") == "max_tokens"
                and isinstance(blocks, list) and blocks
                and all(b.get("type") == "thinking" for b in blocks)):
            msg["stop_reason"] = "end_turn"
            msg["content"] = blocks + [
                {"type": "text", "text": "[cut off at the output limit]"}]
            line = json.dumps(row) + "\n"
            patched += 1
        out.append(line)
    if patched:
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text("".join(out))
        tmp.replace(path)
    return patched


def check_caps() -> None:
    """Read every running worker's transcript and interrupt a generation that
    hit the output cap while thinking.

    The CLI resubmits such a generation on its own, and the retry carries none
    of the thinking forward, so an uncaught cap buys another full budget spent
    on the same dead end."""
    with LOCK:
        for worker in list(PROCS.values()):
            if (worker["state"] not in ("sending", "running")
                    or worker.get("escalate")):
                continue
            it = find(worker["item_id"])
            session = (it or {}).get("sessions", {}).get(worker["phase"])
            if not it or not session:
                continue
            try:
                capped = tail_turn(worker, session)
            except OSError:
                continue
            if capped:
                runaway_detected(it, worker, capped)


def watch_caps() -> None:
    while True:
        time.sleep(CAP_POLL)
        check_caps()


def runaway_detected(it: dict, worker: dict, note: str) -> None:
    """A generation is thinking at length with no work landing. Interrupt it,
    which also cancels the CLI's own retry of the capped generation; the
    result handler hands the worker to revive. Caller holds LOCK."""
    phase = worker["phase"]
    count = it.setdefault("runaway", {}).get(phase, 0) + 1
    it["runaway"][phase] = count
    worker["escalate"] = "nudge" if count == 1 else "bail"
    say(it, event(f"⚠ runaway thinking — {note} "
                  f"({count}× this session) — {worker['escalate']}"), sess=phase)
    worker["outbound"].put_nowait({"type": "control_request",
        "request_id": str(uuid.uuid4()), "request": {"subtype": "interrupt"}})


def revive(worker: dict, stage: str, handoff: bool) -> None:
    """Preserve a capped generation's thinking, then relaunch its turn.

    Runs on the drain thread with the worker already detached: the process
    dies first, the transcript patch lands while nothing else writes the
    file, and the relaunch spawns a fresh process whose resume reads the
    repaired history."""
    if worker.get("proc") is not None:
        reap(worker)
    with LOCK:
        it = find(worker["item_id"])
        if not it:
            return
        phase = worker["phase"]
        session = it["sessions"].get(phase)
        path = transcript_of(session) if session else None
        if path is not None:
            try:
                if patch_capped(path):
                    say(it, event("capped thinking preserved for the resume"),
                        sess=phase)
            except OSError as exc:
                say(it, event(f"transcript patch failed: {exc}"), sess=phase)
        escalate_turn(it, phase, stage, handoff)
    bump()


def escalate_turn(it: dict, phase: str, stage: str, handoff: bool) -> None:
    """Relaunch after a runaway interrupt lands. Caller holds LOCK and has
    reset the worker. The nudge keeps the turn's own handoff flag. A create
    bail asks for the report whose landing hands off; a refine bail has no
    stronger session to receive it, so the item lands for review. A bail that
    itself runs away has said its piece twice, so the item lands either way."""
    count = it.get("runaway", {}).get(phase, 0)
    if stage == "nudge":
        launch(it, NUDGE_BRIEF, phase, handoff=handoff, admitted=True,
               escalated=True)
    elif phase == "create" and count <= 2:
        launch(it, BAIL_BRIEF, phase, handoff=True, admitted=True,
               escalated=True)
    else:
        turn_died(it, phase)


def complete_handoff(it: dict) -> None:
    """Flip the item to the refine phase and enqueue its first turn."""
    if RELOADING:
        it["state"] = NEEDS_REVIEW
        it["updated"] = True
        say(it, event("handoff paused for server reload"), sess="create")
        return
    it["phase"] = "refine"
    it["state"] = RUNNING
    say(it, event("handoff — refine session starting"))
    launch(it, refine_message(it), "refine")


# Dollars of list-price usage per 1% of each rate-limit window. Nothing
# publishes what a window holds, so these come from measurement: price every
# assistant message in ~/.claude/projects that falls inside a window at list
# rates, then divide by that window's utilization from the OAuth usage API.
# Re-measure when the plan changes; a stale figure scales every readout.
QUOTA_RATE = {"5h": 4.44, "wk": 19.58, "fbl": 6.91}


def quota_note(it: dict, ev: dict, phase: str) -> str:
    """A turn's quota draw, per window. The result event's figures run over
    the whole session, so the turn is the step since the last landing."""
    total = ev.get("total_cost_usd")
    if not isinstance(total, (int, float)):
        return ""
    # The Fable weekly window counts Fable usage alone, so it gets its own sum.
    fable = sum(u.get("costUSD") or 0
                for m, u in (ev.get("modelUsage") or {}).items()
                if isinstance(u, dict) and m.startswith(("claude-fable", "claude-mythos")))
    seen = it.setdefault("cost_seen", {}).get(phase) or {"total": 0, "fable": 0}
    if total < seen["total"]:  # a fresh session restarted the running totals
        seen = {"total": 0, "fable": 0}
    d_total, d_fable = total - seen["total"], fable - seen["fable"]
    it["cost_seen"][phase] = {"total": total, "fable": fable}
    parts = [f"5h {d_total / QUOTA_RATE['5h']:.2f}%",
             f"wk {d_total / QUOTA_RATE['wk']:.2f}%"]
    if d_fable:
        parts.append(f"fbl {d_fable / QUOTA_RATE['fbl']:.2f}%")
    return " · " + " · ".join(parts)


def limiting_window(model: str) -> str | None:
    """The window a spend by `model` would hit first: the most-used one among
    those the model draws down."""
    fable = model.startswith(("claude-fable", "claude-mythos"))
    rows = [u for u in USAGE
            if u["label"] in QUOTA_RATE and (u["label"] != "fbl" or fable)]
    if not rows:
        return None
    return max(rows, key=lambda u: u["pct"])["label"]


# What pressing compact costs: one call that reads the session's context and
# writes a summary of it. A working session's context is cached, so the read
# bills at the cache-read fraction; the TTL beside the button is what says
# whether that still holds. The next turn's cache write is that turn's cost,
# not this one's. No compaction has been sampled, so the summary size is a
# stand-in — measure one and correct it here.
COMPACT_SUMMARY = 3_000


def compact_pct(used: int, model: str, limiting: str | None) -> float | None:
    """What compacting a context of `used` tokens would draw from its window."""
    pair = rates(model)
    if pair is None or not limiting:
        return None
    cost = (used * pair[0] * CACHE_READ + COMPACT_SUMMARY * pair[1]) / 1_000_000
    return cost / QUOTA_RATE[limiting]


def out_tokens(ev: dict) -> int:
    """What the model generated this segment. The stream's per-message counts
    are placeholders, and the result event is the first true figure — it
    carries one for a segment the interrupt cut short as well."""
    usage = ev.get("usage") or {}
    if isinstance(usage.get("output_tokens"), int):
        return usage["output_tokens"]
    return sum(x.get("output_tokens") or 0
               for x in (usage.get("iterations") or []) if isinstance(x, dict))


def turn_usage(it: dict, ev: dict, phase: str,
               reqs: list | None = None) -> str:
    """Record the request-level cache and context facts used by the UI.
    `reqs` holds the per-request usage collected from the turn's stream
    events; the result event's iterations carry only the final request."""
    requests = [u for u in (reqs or []) if isinstance(u, dict)]
    if not requests:
        iterations = (ev.get("usage") or {}).get("iterations") or []
        requests = [x for x in iterations if isinstance(x, dict)]

    spent = out_tokens(ev)
    # A segment cut before any request usage arrived still generated tokens.
    if not requests:
        return f"out {spent:,}" if spent else ""

    previous = it.setdefault("cache_read", {}).get(phase)
    drops = []
    for request in requests:
        cache_read = request.get("cache_read_input_tokens")
        if isinstance(cache_read, (int, float)):
            if isinstance(previous, (int, float)) and cache_read < previous:
                drops.append((previous, cache_read))
            previous = cache_read
    it["cache_read"][phase] = previous
    last = requests[-1]
    cache_read = sum(r.get("cache_read_input_tokens") or 0 for r in requests)
    written = sum(r.get("cache_creation_input_tokens") or 0 for r in requests)
    parts = [f"cache r {cache_read:,} w {written:,}"]
    if spent:
        parts.append(f"out {spent:,}")
    if drops:
        before, after = drops[-1]
        parts.append(f"⚠ DROP {before:,}→{after:,}")

    # The final prompt size is the last request's, not the turn's sums.
    used = ((last.get("cache_read_input_tokens") or 0)
            + (last.get("cache_creation_input_tokens") or 0)
            + (last.get("input_tokens") or 0))
    candidates = [(name, usage) for name, usage in (ev.get("modelUsage") or {}).items()
                  if isinstance(usage, dict) and usage.get("contextWindow")]
    if candidates:
        model, model_usage = max(candidates, key=lambda pair:
            (pair[1].get("cacheReadInputTokens") or 0) +
            (pair[1].get("cacheCreationInputTokens") or 0) +
            (pair[1].get("inputTokens") or 0))
        window = model_usage["contextWindow"]
        canonical = model_usage.get("canonicalModel") or model
        limiting = limiting_window(canonical)
        it.setdefault("context", {})[phase] = {
            "used": used, "window": window,
            "percent": used / window * 100,
            "limiting": limiting, "model": canonical,
            "compactPct": compact_pct(used, canonical, limiting),
        }
    return " · ".join(parts)


def think_note(tokens: int, phase: str) -> str:
    """Discarded thinking never reaches the CLI's cost accounting, so price
    the estimate at the phase model's output rate. It is measured differently
    from the dollars beside it, so it reads as its own term."""
    pair = rates(MODELS[phase])
    note = f" · lost ~{tokens // 1000}k think"
    if pair is None:
        return note
    cost = tokens * pair[1] / 1_000_000
    return note + f" ≈ {cost / QUOTA_RATE['5h']:.2f}% 5h"


def turn_note(it: dict, ev: dict, phase: str, started: float | None,
              reqs: list | None, lost: int = 0,
              done: bool = True) -> str:
    """One turn segment's draw, for the feed."""
    head = "turn done" if done else "turn cut"
    mins = (time.time() - started) / 60 if started else 0
    note = f"{head} · {mins:.0f}m" if mins >= 1 else f"{head} · <1m"
    # A cut result carries no cost figure. Reading one anyway would reset the
    # session baseline to zero and bill the whole session to the next landing;
    # leaving it be lets that landing's step cover this segment too.
    if ev.get("total_cost_usd"):
        note += quota_note(it, ev, phase)
    if lost:
        note += think_note(lost, phase)
    usage = turn_usage(it, ev, phase, reqs)
    return note + (" · " + usage if usage else "")


def finish_turn(it: dict, ev: dict, trigger: str | None, started: float,
                phase: str, handoff: bool,
                reqs: list | None = None) -> None:
    it["rev"] = it.get("rev", 0) + 1
    text = (ev.get("result") or "").strip()
    if text:
        # the result event can arrive well after the turn's messages (e.g. a
        # background subagent turn), so look back through the current turn
        match = None
        for m in reversed(it["feed"]):
            if m["kind"] in ("report", "you"):
                break
            if m["kind"] == "worker" and not m.get("sub") and m["text"].strip() == text:
                match = m
                break
        if match:
            match.clear()
            match.update(kind="report", rev=it["rev"], text=text, sess=phase)
            touch(it)
        else:
            say(it, {"kind": "report", "rev": it["rev"], "text": text}, sess=phase)
    say(it, event(turn_note(it, ev, phase, started, reqs)), sess=phase)
    # the create pass ends in prune, and the refine pass is itself the quality
    # pass, so each phase's first landing is clean by cadence
    first_refine = phase == "refine" and not it.get("refined")
    if phase == "refine":
        it["refined"] = True
    if trigger in CLEAN_TRIGGERS or first_refine or (phase == "create" and it["rev"] == 1):
        it["dirty"] = False
    elif solver_hash(it["id"]) != pre(it)["hash"]:
        it["dirty"] = True
    if not pre(it).get("slash"):
        it.setdefault("seen_hash", {})[phase] = solver_hash(it["id"])
    it["lastActive"][phase] = int(time.time() * 1000)
    it["title"] = title_of(it["id"]) or it.get("title", "")
    it["prop_after"] = prop_text()
    if handoff and phase == "create":
        it["handoff_report"] = text
        it["handoff_pending"] = True
        worker = PROCS.get((it["id"], phase))
        if worker:
            DEFERRED.put_nowait(("handoff", it["id"], phase, worker["turn_seq"]))
            ensure_drain()
    elif not pre(it).get("slash"):
        it["state"] = NEEDS_REVIEW
        it["updated"] = True


def ensure_drain() -> None:
    global DEFERRED_THREAD
    if DEFERRED_THREAD is None or not DEFERRED_THREAD.is_alive():
        DEFERRED_THREAD = threading.Thread(target=drain_deferred, daemon=True)
        DEFERRED_THREAD.start()


def drain_deferred() -> None:
    while True:
        job = DEFERRED.get()
        if job is STOP:
            return
        try:
            if job[0] == "reap":
                reap(job[1])
                continue
            if job[0] == "revive":
                revive(*job[1:])
                continue
            _, item_id, phase, turn_seq = job
            with LOCK:
                it = find(item_id)
                worker = PROCS.get((item_id, phase))
                if not it or not it.get("handoff_pending") or not worker or \
                        worker["turn_seq"] != turn_seq:
                    if it:
                        it.pop("handoff_pending", None)
                    continue
                it.pop("handoff_pending", None)
                complete_handoff(it)
            bump()
        except Exception as exc:
            print(f"deferred {job[0]} failed: {exc}", file=sys.stderr)


def detach_workers(item_id: str) -> list[dict]:
    workers = []
    for key, worker in list(PROCS.items()):
        if key[0] == item_id and PROCS.get(key) is worker:
            PROCS.pop(key)
            worker["state"] = "dying"
            worker["outbound"].put_nowait(STOP)
            workers.append(worker)
    return workers


def queue_reap(worker: dict) -> None:
    DEFERRED.put_nowait(("reap", worker))
    ensure_drain()


def reap(worker: dict) -> None:
    proc = worker["proc"]
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                print(f"worker {worker['item_id']} did not exit after kill",
                      file=sys.stderr)
    for pipe in (proc.stdin, proc.stdout):
        if pipe:
            try:
                pipe.close()
            except OSError:
                pass
    worker["reader"].join(timeout=3)
    worker["writer"].join(timeout=3)
    worker["state"] = "dead"


FIRST_RESPONSE: dict[str, threading.Event] = {}

WAVE_DEBOUNCE = 5  # seconds; a fumbled double-click, not a deliberate second wave
LAST_WAVE_AT = 0.0


def queue_pick(n: int, order: str) -> list[tuple[str, int]]:
    """Top `n` unsolved tasks from scripts/queue.sh, as (id, size estimate)."""
    out = subprocess.run(["bash", "scripts/queue.sh", "-n", str(n), "--order", order],
                         cwd=ROOT, capture_output=True, text=True)
    if out.returncode != 0:
        raise Reject("queue.sh failed: " + out.stderr.strip()[-200:])
    picked = []
    for line in out.stdout.splitlines():
        m = re.match(r"\s*(\d+)\s+(\S+)", line)
        if m:
            picked.append((m.group(2), int(m.group(1))))
    return picked


def start_wave(k: int, order: str = "name") -> dict:
    global LAST_WAVE_AT
    with LOCK:
        if RELOADING:
            return {"error": "server reload in progress — wait for it to finish"}
        if time.time() - LAST_WAVE_AT < WAVE_DEBOUNCE:
            return {"error": "a wave just started — wait a moment to start another"}
        if order not in ("name", "size"):
            return {"error": f"unknown order: {order}"}
        committed = [it for it in STATE["items"] if it["state"] == COMMITTED]
        for old in committed:
            for worker in detach_workers(old["id"]):
                queue_reap(worker)
        STATE["items"] = [it for it in STATE["items"] if it["state"] != COMMITTED]
        existing = {it["id"] for it in STATE["items"]}
        try:
            picked = [p for p in queue_pick(k + len(existing), order)
                      if p[0] not in existing][:k]
        except Reject as e:
            return {"error": str(e)}
        if not picked:
            return {"error": "queue is empty"}
        LAST_WAVE_AT = time.time()
        STATE["wave"] += 1
        append = str(build_append(STATE["wave"]))
        for tid, est in picked:
            STATE["items"].append({
                "id": tid, "est": est, "wave": STATE["wave"], "state": QUEUED,
                "sessions": {"create": None, "refine": None}, "phase": "create",
                "refined": False, "dirty": False, "updated": False, "rev": 0,
                "lastActive": {"create": None, "refine": None},
                "title": "", "feed": [], "append": append, "ver": 0,
            })
    bump()
    threading.Thread(target=stagger_launch,
                     args=([tid for tid, _ in picked],), daemon=True).start()
    return {"ok": True, "ids": [tid for tid, _ in picked]}


def stagger_launch(ids: list[str]) -> None:
    """Launch the first worker alone so it writes the shared prompt-cache
    prefix, then fan the rest out once its first API response arrives."""
    first = threading.Event()
    seeded = False
    with LOCK:
        it = find(ids[0])
        if it is not None and it["state"] == QUEUED and not active(it):
            FIRST_RESPONSE[ids[0]] = first
            it["state"] = RUNNING
            say(it, event("launched (cache seeder)"))
            launch(it, create_message(ids[0]), "create", handoff=True, admitted=True)
            seeded = True
    bump()
    if seeded:
        first.wait(timeout=STAGGER_TIMEOUT)
        with LOCK:
            if FIRST_RESPONSE.get(ids[0]) is first:
                FIRST_RESPONSE.pop(ids[0], None)
    with LOCK:
        for tid in ids[1:]:
            it = find(tid)
            if it is None or it["state"] != QUEUED or active(it):
                continue
            it["state"] = RUNNING
            say(it, event("launched"))
            launch(it, create_message(tid), "create", handoff=True, admitted=True)
    bump()


def resume_queued_wave() -> None:
    """Give persisted admissions an owner after an exec or failed reload."""
    with LOCK:
        ids = [it["id"] for it in STATE["items"] if it["state"] == QUEUED and
               not any(item_id == it["id"] for item_id, _ in PROCS)]
    if ids:
        threading.Thread(target=stagger_launch, args=(ids,), daemon=True).start()


# ---------- actions ----------

def submit_comment(it: dict, text: str, sess: str | None = None) -> None:
    text = text.strip()
    low = text.lower()
    if low in ("commit", "next"):
        raise Reject(f"`{text}` is a console action, not a worker message")
    require_idle(it)
    if low == "handoff":
        if it["phase"] != "create":
            raise Reject("already handed off")
        if not it["sessions"]["create"]:
            raise Reject("no session yet")
        say(it, {"kind": "you", "text": text}, sess="create")
        it["state"] = COMMENTED
        it["updated"] = False
        launch(it, HANDOFF_BRIEF, "create", handoff=True)
        return
    sess = sess if sess in ("create", "refine") else it["phase"]
    if not it["sessions"].get(sess):
        raise Reject("no session yet")
    say(it, {"kind": "you", "text": text}, sess=sess)
    if not text.startswith("/"):
        it["state"] = COMMENTED
        it["updated"] = False
    head = low.split()[:1]
    trigger = head[0] if head and head[0] in CLEAN_TRIGGERS else None
    launch(it, text, sess, trigger=trigger)


act_comment = action(submit_comment)


@action
def act_compact(it: dict, sess: str | None = None) -> None:
    submit_comment(it, "/compact", sess)


@action
def act_approve(it: dict) -> None:
    if it["state"] != NEEDS_REVIEW:
        raise Reject("nothing to approve")
    require_idle(it)
    it["state"] = APPROVED
    it["updated"] = False
    say(it, event("approved"))


@action
def act_unapprove(it: dict) -> None:
    if it["state"] != APPROVED:
        raise Reject("not approved")
    it["state"] = NEEDS_REVIEW
    say(it, event("approval withdrawn"))


@action
def act_seen(it: dict) -> None:
    it["updated"] = False


@action
def act_drop(it: dict) -> None:
    """Forget an item and its feed. The solver file on disk is left alone."""
    require_idle(it)
    for worker in detach_workers(it["id"]):
        queue_reap(worker)
    STATE["items"] = [x for x in STATE["items"] if x["id"] != it["id"]]


def act_kill(item_id: str) -> dict:
    with LOCK:
        running = [w for (tid, _), w in PROCS.items()
                   if tid == item_id and w["state"] in ("sending", "running")]
        if not running:
            return {"error": "no worker running"}
        worker, turn_seq = running[0], running[0]["turn_seq"]
        worker.pop("escalate", None)  # the user's stop outranks a relaunch
        worker["outbound"].put_nowait({"type": "control_request",
            "request_id": str(uuid.uuid4()), "request": {"subtype": "interrupt"}})

    def force():
        time.sleep(10)
        with LOCK:
            current = PROCS.get((worker["item_id"], worker["phase"]))
            if current is not worker or worker["turn_seq"] != turn_seq or \
                    worker["state"] not in ("sending", "running"):
                return
            proc = worker["proc"]
            if proc.poll() is None:
                proc.terminate()
    threading.Thread(target=force, daemon=True).start()
    return {"ok": True}


@action
def act_revert(it: dict) -> None:
    require_idle(it)
    item_id = it["id"]
    snap = pre(it)["solver"]
    if not snap or snap == solver_text(item_id):
        raise Reject("nothing to revert")
    solver_path(item_id).write_text(snap)
    reverted = [f"programs/solvers/{item_id}.dl"]
    # proposals.md is shared across workers: restore only if this turn
    # changed it and nothing touched it since the turn landed
    sp, pa = pre(it)["proposals"], it.get("prop_after")
    if pa is not None and sp != pa and prop_text() == pa:
        (DOCS / "proposals.md").write_text(sp)
        reverted.append("docs/wf-solver/proposals.md")
    it["dirty"] = pre(it)["dirty"]
    it["reverted"] = {"files": reverted,
                      "phase": it.get("last_turn_phase") or it["phase"]}
    say(it, event("edits reverted"))


def commit_subject(added: list[str], changed: list[str]) -> str:
    parts = []
    if added:
        parts.append("Add " + ", ".join(added))
    if changed:
        parts.append(("update " if parts else "Update ") + ", ".join(changed))
    return "; ".join(parts)


def act_commit() -> dict:
    with LOCK:
        if COMMITTER["running"]:
            return {"error": "committer session still running"}
        ids = [it["id"] for it in STATE["items"] if it["state"] == APPROVED]
        if not ids:
            return {"error": "nothing approved"}
        rels = {i: str(solver_path(i).relative_to(ROOT)) for i in ids}
        # HEAD, not the index: a solver staged by something else is still new
        in_head = set(subprocess.run(["git", "ls-tree", "-r", "--name-only", "HEAD",
                                      "--", *rels.values()],
                                     cwd=ROOT, capture_output=True, text=True).stdout.split())
        msg = commit_subject(sorted(i for i in ids if rels[i] not in in_head),
                             sorted(i for i in ids if rels[i] in in_head))
        paths = list(rels.values())
        proposals = "docs/wf-solver/proposals.md"
        if subprocess.run(["git", "diff", "--quiet", "--", proposals],
                          cwd=ROOT).returncode != 0:
            paths.append(proposals)
        subprocess.run(["git", "add", *paths], cwd=ROOT, check=False)
        out = subprocess.run(["git", "commit", "-m", msg], cwd=ROOT,
                             capture_output=True, text=True)
        if out.returncode != 0:
            return {"error": "git commit failed: " + (out.stderr or out.stdout).strip()[-200:]}
        msgs = [msg]
        for it in STATE["items"]:
            if it["id"] in ids:
                it["state"] = COMMITTED
                say(it, event("committed"))
                for worker in detach_workers(it["id"]):
                    queue_reap(worker)
        chk = subprocess.run(["git", "status", "--porcelain", "--", *COMMIT_SCOPE],
                             cwd=ROOT, capture_output=True, text=True)
        leftovers = any(not l.startswith("??") for l in chk.stdout.splitlines())
        if leftovers and not FAKE:
            COMMITTER["running"] = True
            COMMITTER["note"] = None
            append = STATE_DIR / f"wave-{STATE['wave']:02d}-append.md"
            threading.Thread(target=run_committer, args=(append,),
                             daemon=True).start()
            msgs.append("committer running…")
    bump()
    return {"ok": True, "msg": " + ".join(msgs)}


def run_committer(append: Path) -> None:
    """One-shot session that commits worker fallout with judged messages."""
    before = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip()
    cmd = [CLAUDE, "-p", COMMIT_BRIEF, *COMMITTER_FLAGS]
    if append.exists():
        cmd += ["--append-system-prompt", append.read_text()]
    if COMMIT_MODEL:
        cmd += ["--model", COMMIT_MODEL]
    with open(LOG_DIR / "committer.log", "ab") as log:
        try:
            subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=log, timeout=900)
        except subprocess.TimeoutExpired:
            pass
    out = subprocess.run(["git", "log", "--format=%s", f"{before}..HEAD"],
                         cwd=ROOT, capture_output=True, text=True).stdout
    subjects = [s for s in out.splitlines() if s]
    with LOCK:
        COMMITTER["running"] = False
        COMMITTER["note"] = ("committer: " + "; ".join(reversed(subjects))
                             if subjects else
                             "committer made no commits — see state/logs/committer.log")
    bump()


# ---------- http ----------

def light_items() -> list[dict]:
    out = []
    for it in STATE["items"]:
        live = {phase: (worker := PROCS.get((it["id"], phase))) is not None and
                       worker["state"] != "dead"
                for phase in ("create", "refine")}
        running = next((phase for phase in ("create", "refine")
                        if (worker := PROCS.get((it["id"], phase))) and
                        worker["state"] in ("sending", "running")), None)
        turn = PROCS.get((it["id"], running)) if running else None
        out.append({k: it.get(k) for k in
                    ("id", "state", "dirty", "updated", "sessions", "phase", "context",
                     "lastActive", "wave", "rev", "title", "est", "ver", "append")} |
                   {"active": active(it), "turnPhase": running,
                    "turnStarted": turn["started"] if turn else None,
                    "workerLive": live})
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, obj, status=200, ctype="application/json"):
        body = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
        try:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # client abandoned the request (e.g. page reload mid long-poll)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            self.reply((HERE / "console.html").read_bytes(), ctype="text/html")
        elif url.path.startswith("/vendor/"):
            p = HERE / "vendor" / Path(url.path).name
            if not p.exists():
                return self.reply({"error": "not found"}, 404)
            self.reply(p.read_bytes(), ctype="application/javascript")
        elif url.path == "/api/state":
            q = parse_qs(url.query)
            since = int(q.get("since", ["0"])[0])
            wait = float(q.get("wait", ["0"])[0])
            deadline = time.time() + min(wait, 25)
            with COND:
                while STATE["seq"] <= since and time.time() < deadline:
                    COND.wait(deadline - time.time())
                snap = {"seq": STATE["seq"], "wave": STATE["wave"],
                        "items": light_items(), "usage": USAGE,
                        "cli": {"addDir": str(REF_DIR), "models": MODELS},
                        "committer": dict(COMMITTER),
                        "solved": len(list(SOLVERS.glob("*.dl"))),
                        "total": len(list(REF_DIR.glob("programs/solvers/*.ts")))}
            self.reply(snap)
        elif url.path.startswith("/api/item/"):
            item_id = url.path.rsplit("/", 1)[1]
            with LOCK:
                it = find(item_id)
                if it is None:
                    return self.reply({"error": "unknown item"}, 404)
                solver_rel = f"programs/solvers/{item_id}.dl"
                edited = pre(it)["files"]
                files = []
                for rel in [solver_rel] + [r for r in edited if r != solver_rel]:
                    p = ROOT / rel
                    files.append({
                        "path": rel,
                        "snap": edited.get(rel, pre(it)["solver"] if rel == solver_rel else ""),
                        "code": p.read_text() if p.exists() else "",
                    })
                self.reply({"feed": it["feed"], "files": files,
                            "ver": it.get("ver", 0)})
        elif url.path.startswith("/api/task/"):
            item_id = url.path.rsplit("/", 1)[1]
            p = TASKS / f"{item_id}.json"
            if not p.exists():
                return self.reply({"error": "no task json"}, 404)
            self.reply(p.read_bytes())
        else:
            self.reply({"error": "not found"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        route = urlparse(self.path).path
        if route == "/api/wave":
            res = start_wave(int(body.get("k", 6)), body.get("order", "name"))
        elif route == "/api/comment":
            res = act_comment(body.get("id", ""), body.get("text", ""),
                              body.get("sess"))
        elif route == "/api/compact":
            res = act_compact(body.get("id", ""), body.get("sess"))
        elif route == "/api/approve":
            res = act_approve(body.get("id", ""))
        elif route == "/api/unapprove":
            res = act_unapprove(body.get("id", ""))
        elif route == "/api/seen":
            res = act_seen(body.get("id", ""))
        elif route == "/api/kill":
            res = act_kill(body.get("id", ""))
        elif route == "/api/drop":
            res = act_drop(body.get("id", ""))
        elif route == "/api/revert":
            res = act_revert(body.get("id", ""))
        elif route == "/api/commit":
            res = act_commit()
        else:
            return self.reply({"error": "not found"}, 404)
        self.reply(res, 400 if "error" in res else 200)


def read_usage() -> list[dict]:
    """Rate-limit windows from the OAuth usage API cache; [] on any surprise."""
    from datetime import datetime
    try:
        raw = json.loads((Path.home() / ".claude" / "usage-api.json").read_text())
        out = []
        for lim in (raw.get("data") or {}).get("limits") or []:
            pct, kind = lim.get("percent"), lim.get("kind")
            scope = (((lim.get("scope") or {}).get("model")) or {}).get("display_name")
            if pct is None:
                continue
            if kind == "session":
                label, window = "5h", 5 * 3600
            elif kind == "weekly_all":
                label, window = "wk", 7 * 86400
            elif scope:
                label = "fbl" if scope.lower().startswith("fable") else scope[:3].lower()
                window = 7 * 86400
            else:
                continue
            reset = None
            if lim.get("resets_at"):
                reset = int(datetime.fromisoformat(lim["resets_at"]).timestamp())
            out.append({"label": label, "pct": pct, "reset": reset, "window": window})
        return out
    except Exception:
        return []


def usage_loop() -> None:
    global USAGE
    script = Path.home() / ".claude" / "scripts" / "fetch-usage-api.sh"
    sampler = quota.Sampler()
    while True:
        if script.exists():
            subprocess.run(["bash", str(script)], capture_output=True, timeout=30)
        USAGE = read_usage()
        # Pairs each window's utilization with the tokens spent inside it, so
        # the QUOTA_RATE figures can be refit from observation rather than
        # measured by hand. Never worth failing the poll over.
        try:
            sampler.record(SAMPLE_FILE)
        except Exception:
            pass
        time.sleep(60)


def watch_reload() -> None:
    """Quiesce turns and re-exec on a server.py change."""
    src = Path(__file__)
    mtime = src.stat().st_mtime
    while True:
        time.sleep(2)
        try:
            if src.stat().st_mtime == mtime:
                continue
        except OSError:
            continue
        print("server.py changed — restarting")
        reload_server()


def quiesce_workers() -> None:
    """Block new turns and wait for the in-flight ones to land, however long
    they take. A turn is never cut for a reload."""
    global RELOADING
    with COND:
        RELOADING = True
        while any(active(it) or it["state"] == QUEUED for it in STATE["items"]):
            COND.wait()
        # A reader's TextIOWrapper may read ahead and lose buffered output at
        # exec. Idle workers have no pending turn output, which makes this cut safe.


def reload_server() -> None:
    global RELOADING
    manifest = None
    try:
        quiesce_workers()
        with LOCK:
            if any(active(it) or it["state"] == QUEUED for it in STATE["items"]):
                for it in STATE["items"]:
                    say(it, event("reload aborted because a new turn started"))
                RELOADING = False
                save()
                return
            manifest = worker_manifest()
            os.environ[WORKER_HANDOFF_ENV] = json.dumps(manifest)
            save()
            os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as exc:
        if manifest is not None:
            for entry in manifest["workers"]:
                for name in ("stdin_fd", "stdout_fd"):
                    try:
                        os.set_inheritable(entry[name], False)
                    except OSError:
                        pass
        os.environ.pop(WORKER_HANDOFF_ENV, None)
        RELOADING = False
        with LOCK:
            for it in STATE["items"]:
                say(it, event(f"reload failed — server still running: {exc}"))
            save()
        resume_queued_wave()


def shutdown_workers() -> None:
    global SHUTTING_DOWN
    with LOCK:
        if SHUTTING_DOWN:
            return
        SHUTTING_DOWN = True
        workers = list(PROCS.values())
        PROCS.clear()
        for worker in workers:
            worker["state"] = "dying"
            worker["outbound"].put_nowait(STOP)
    DEFERRED.put_nowait(STOP)
    for worker in workers:
        proc = worker["proc"]
        if proc.poll() is None:
            proc.terminate()
    for worker in workers:
        proc = worker["proc"]
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        for pipe in (proc.stdin, proc.stdout):
            if pipe:
                try:
                    pipe.close()
                except OSError:
                    pass
        worker["reader"].join(timeout=3)
        worker["writer"].join(timeout=3)
    if DEFERRED_THREAD:
        DEFERRED_THREAD.join(timeout=4)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8347)
    args = ap.parse_args()
    STATE_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
    global _state_lock
    _state_lock = open(STATE_DIR / ".lock", "w")
    try:
        fcntl.flock(_state_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("another console server owns this state dir — refusing to start")
    handoff = read_worker_handoff()
    load()
    adopt_workers(handoff)
    save()
    resume_queued_wave()
    threading.Thread(target=watch_reload, daemon=True).start()
    threading.Thread(target=usage_loop, daemon=True).start()
    threading.Thread(target=watch_caps, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    stopping = threading.Event()
    def request_stop(signum, frame):
        if not stopping.is_set():
            stopping.set()
            threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    mode = " (FAKE workers)" if FAKE else ""
    print(f"solver console · http://127.0.0.1:{args.port}{mode}")
    try:
        server.serve_forever()
    finally:
        server.server_close()
        shutdown_workers()


if __name__ == "__main__":
    main()
