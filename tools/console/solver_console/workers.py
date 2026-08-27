"""Worker processes: launching a turn, reading its stream, and accounting
for what it spent."""

import fcntl
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
from pathlib import Path

import quota
from calibrate import CACHE_READ, rates

from . import config, ledger, pacing, prompts, solvers, store

# Thinking tokens with no tool call or text before the feed says so. Well
# above a working turn's bursts, and far enough below the 64k output cap that
# the warning still arrives with the generation in progress.
RUNAWAY_THINK = 40_000
# Seconds between transcript reads. The CLI resubmits a capped generation on
# its own and the retry carries none of the thinking, so every poll of delay
# risks another full output budget spent on the same dead end.
CAP_POLL = 5


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
        for (item_id, phase), worker in store.PROCS.items():
            proc = worker["proc"]
            stdin_fd, stdout_fd = proc.stdin.fileno(), proc.stdout.fileno()
            for fd in (stdin_fd, stdout_fd):
                os.set_inheritable(fd, True)
                inheritable.append(fd)
            it = store.find(item_id)
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
    raw = os.environ.pop(store.WORKER_HANDOFF_ENV, None)
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
            it = store.find(item_id)
            if not it or phase not in store.stage_names(it) or \
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
                      "session_seen": bool(entry.get("session")),
                      "idle_since": time.time()}
            store.PROCS[(item_id, phase)] = worker
            start_worker_threads(worker)
        except (KeyError, TypeError, ValueError, OSError) as exc:
            print(f"worker handoff rejected: {exc}", file=sys.stderr)
            if isinstance(entry, dict):
                it = store.find(entry.get("item"))
                phase = entry.get("phase")
                if it is not None and phase in store.stage_names(it):
                    lost_session = it["sessions"].get(phase)
                    it["sessions"][phase] = None
                    store.say(it, store.event(f"{phase} session lost on reload: "
                                              f"{lost_session}"), sess=phase)
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
        rel = str(Path(fp).resolve().relative_to(config.ROOT))
    except ValueError:
        return
    p_ = store.pre(it)
    if rel in p_["files"]:
        return
    if rel == f"programs/solvers/{it['id']}.dl":
        p_["files"][rel] = p_["solver"]
    elif rel == "docs/wf-solver/proposals.md":
        p_["files"][rel] = p_["proposals"]
    else:
        p = config.ROOT / rel
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
        rel = fp.removeprefix(str(config.ROOT) + "/")
        return f"{name} {rel}"
    if name == "Bash":
        cmd = str(inp.get("command", "")).replace("\n", " ")
        return f"Bash {cmd[:90]}"
    if name in ("Grep", "Glob"):
        return f"{name} {inp.get('pattern', '')}"
    return name


# Words asking for a cadence that ends in Simplify and Prune, so the turn's
# edits land already clean.
CLEAN_TRIGGERS = ("cleanup", "fit")
CLEANUP_RE = re.compile(r"\bcleanup\b")


def clean_trigger(text: str) -> str | None:
    """The clean cadence a message asks for. `cleanup` counts anywhere in the
    message, since it is often the tail of a longer instruction; `fit` counts
    only as the opening word, since elsewhere it reads as an ordinary verb."""
    low = text.lower()
    if CLEANUP_RE.search(low):
        return "cleanup"
    return "fit" if low.split()[:1] == ["fit"] else None


def launch(it: dict, message: str, phase: str, trigger: str | None = None,
           handoff: bool = False, admitted: bool = False,
           escalated: bool = False) -> None:
    """Spawn the phase worker if needed, then enqueue one turn. The nudge and
    the bail are turns of one chain and keep its count; every other turn starts
    its own, so a turn asked to think hard is judged on its own stretches."""
    if store.RELOADING and not admitted:
        raise store.Reject("server reload in progress — wait for it to finish")
    if not escalated:
        it.setdefault("runaway", {}).pop(phase, None)
    # Any turn except the callout ask and its continuations (resume, nudge,
    # bail) supersedes a pending callout landing, so a stale marker cannot
    # claim a later turn's text for the report.
    if trigger not in ("callout", "resume", "nudge", "bail") and \
            it.get("callout_wait") == phase:
        it.pop("callout_wait", None)
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
        if seen is not None and seen != solvers.solver_hash(it["id"]):
            message = ("<system-reminder>programs/solvers/"
                       f"{it['id']}.dl changed on disk since your last turn. "
                       "Re-read before editing.</system-reminder>\n\n" + message)
    it["last_turn_phase"] = phase
    key = (it["id"], phase)
    worker = store.PROCS.get(key)
    if worker is None:
        if it["sessions"].get(phase):
            store.say(it, store.event(f"{phase} worker restarting — resuming its session"),
                      sess=phase)
        worker = spawn_worker(it, phase)
    start_turn(it, worker, phase, trigger=trigger, handoff=handoff, slash=slash)
    worker["outbound"].put_nowait({"type": "user",
        "message": {"role": "user", "content": message}})


def start_turn(it: dict, worker: dict, phase: str, trigger: str | None = None,
               handoff: bool = False, slash: bool = False,
               state: str = "sending") -> None:
    """Open a turn's bookkeeping: the snapshot its landing diffs against, and
    the counters it fills. Every turn passes through here, the ones the console
    sends and the one it adopts."""
    if not store.busy_elsewhere(it, phase):
        # a side turn leaves the snapshot with the turn that owns the solver
        it["pre"] = {"hash": solvers.solver_hash(it["id"]), "solver": solvers.solver_text(it["id"]),
                     "proposals": solvers.prop_text(), "dirty": it["dirty"], "files": {},
                     "watched": solvers.watched_hashes(it["id"]), "slash": slash}
    worker["turn_seq"] += 1
    worker.pop("steer", None)
    worker.update(state=state, started=time.time(), trigger=trigger,
                  handoff=handoff, seen=set(), got_result=False, think_run=0,
                  reqs={}, idle_since=None)


def steer(it: dict, worker: dict, text: str, phase: str) -> None:
    """Send a message into a turn already running. The CLI hands it over at the
    turn's next tool boundary and the turn absorbs it, so no bookkeeping opens
    here: the turn keeps its snapshot, its count, and its one landing. A clean
    cadence the message asks for still reaches the turn it steers."""
    trigger = clean_trigger(text)
    if trigger and not worker.get("trigger"):
        worker["trigger"] = trigger
    worker["steer"] = {"trigger": trigger, "at": time.time()}
    store.say(it, {"kind": "steer", "text": text}, sess=phase)
    worker["outbound"].put_nowait({"type": "user",
        "message": {"role": "user", "content": text}})


def adopt_turn(it: dict, worker: dict, phase: str) -> None:
    """Take over the turn a steer starts when it reaches the worker just after
    the turn it was meant for landed. init opens every turn and arrives before
    the turn's first action, so the snapshot still holds the pre-turn files."""
    pending = worker.pop("steer", None) or {}
    start_turn(it, worker, phase, trigger=pending.get("trigger"), state="running")
    if it["state"] not in store.ACTIVE:
        it["state"] = store.COMMENTED
        it["updated"] = False
    store.say(it, store.event("message reached the worker as the turn landed — "
                              "it runs as a turn of its own"), sess=phase)


def permission_decision(req: dict) -> dict:
    """The console's answer to one permission request. A worker may edit the
    skill it runs on, which the CLI holds back as a file of its own. Every
    other request keeps the refusal the CLI already reached."""
    if req.get("tool_name") in ("Edit", "Write"):
        try:
            asked = Path((req.get("input") or {}).get("file_path") or "").resolve()
        except OSError:
            asked = None
        if asked is not None and asked == config.SKILL_MD.resolve():
            return {"behavior": "allow", "updatedInput": req.get("input") or {}}
    return {"behavior": "deny",
            "message": req.get("decision_reason") or "not permitted"}


def answer_permission(worker: dict, it: dict | None, ev: dict, phase: str) -> None:
    """Settle a control request the worker's CLI raised. One left unanswered
    holds the turn open until the process dies, so every path here writes a
    response first and reports to the feed afterwards."""
    req = ev.get("request") or {}
    request_id = ev.get("request_id")
    if req.get("subtype") != "can_use_tool":
        worker["outbound"].put_nowait({"type": "control_response", "response": {
            "subtype": "error", "request_id": request_id,
            "error": f"unsupported control request: {req.get('subtype')}"}})
        return
    try:
        decision = permission_decision(req)
    except Exception as exc:  # an unanswered request costs more than a refusal
        decision = {"behavior": "deny", "message": f"console error: {exc!r}"}
    worker["outbound"].put_nowait({"type": "control_response", "response": {
        "subtype": "success", "request_id": request_id,
        "response": {**decision, "toolUseID": req.get("tool_use_id")}}})
    if it:
        target = (req.get("input") or {}).get("file_path") or ""
        try:
            target = str(Path(target).relative_to(config.ROOT))
        except ValueError:
            pass
        verb = "allowed" if decision["behavior"] == "allow" else "denied"
        store.say(it, store.event(f"permission {verb}: "
                                  f"{req.get('tool_name') or '?'} {target}".rstrip()), sess=phase)


def worker_cmd(it: dict, phase: str) -> list[str]:
    if config.FAKE:
        return [sys.executable, str(config.HERE / "fake_worker.py"), it["id"], phase]
    st = store.stage_of(it, phase)
    session = it["sessions"].get(phase)
    if (st.get("backend") or "claude") == "codex":
        # The adapter reads the appendix itself; codex exec has no
        # system-prompt append, and WORKER_FLAGS has no codex equivalent.
        cmd = [sys.executable, str(config.HERE / "codex_worker.py"),
               "--append", str(it["append"]), "--add-dir", str(config.REF_DIR)]
        if st.get("model"):
            cmd += ["--model", st["model"]]
        if st.get("effort"):
            cmd += ["--effort", st["effort"]]
        if session:
            cmd += ["--resume", session]
        return cmd
    cmd = [config.CLAUDE, "--append-system-prompt", Path(it["append"]).read_text(),
           *config.WORKER_FLAGS]
    if st.get("model"):
        cmd += ["--model", st["model"]]
    if session:
        cmd += ["--resume", session]
    return cmd


def spawn_worker(it: dict, phase: str) -> dict:
    item_id = it["id"]
    cmd = worker_cmd(it, phase)
    log = open(config.LOG_DIR / f"{item_id}.log", "ab")
    proc = subprocess.Popen(cmd, cwd=config.ROOT,
                            env={**config.WORKER_ENV, "CONSOLE_TASK": item_id},
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=log, text=True)
    log.close()
    worker = {"item_id": item_id, "phase": phase, "proc": proc,
              "outbound": queue.Queue(), "state": "spawning", "turn_seq": 0,
              "started": None, "trigger": None, "handoff": False, "seen": set(),
              "got_result": False, "session_seen": False, "think_run": 0,
              "reqs": {}, "idle_since": None}
    # A new process restarts the session's running totals.
    it.setdefault("cost_seen", {})[phase] = {"total": 0, "fable": 0}
    # A resumed session keeps its context, so its cache baseline stands and
    # a cold resume shows up as a DROP.
    if not it["sessions"].get(phase):
        it.setdefault("cache_read", {}).pop(phase, None)
    store.PROCS[(item_id, phase)] = worker
    start_worker_threads(worker)
    worker.update(state="idle", idle_since=time.time())
    return worker


def writer(worker: dict) -> None:
    proc = worker["proc"]
    while True:
        event = worker["outbound"].get()
        if event is store.STOP:
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
    first_response = store.FIRST_RESPONSE.get(item_id)
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
                with store.LOCK:
                    it = store.find(item_id)
                    if it:
                        store.say(it, store.event(f"⚠ reader error, event skipped: {exc!r}"),
                                  sess=phase)
                        if worker["state"] not in ("sending", "running") and \
                                it["state"] in (store.RUNNING, store.COMMENTED):
                            store.turn_died(it, phase)  # the crash cut the turn's landing
            store.bump()
    except (OSError, ValueError):
        # Shutdown closes the pipe out from under a blocked read. There is
        # nothing left to drain either way, so fall through to the cleanup.
        pass
    proc.wait()
    with store.LOCK:
        worker["outbound"].put_nowait(store.STOP)
        if store.PROCS.get((item_id, phase)) is worker:
            store.PROCS.pop((item_id, phase), None)
        worker["state"] = "dead"
        it = store.find(item_id)
        if it and worker["started"] is not None:
            tail = ""
            log = config.LOG_DIR / f"{item_id}.log"
            if log.exists():
                tail = log.read_text(errors="replace")[-400:].strip()
            store.say(it, store.event("worker exited without result "
                                      f"(code {proc.returncode}) — {tail}"),
                      sess=phase)
            store.turn_died(it, phase)
            if pacing.quota_death(text=tail):
                pacing.quota_cut(it, phase, bool(worker.get("handoff")))
    if first_response:
        first_response.set()
    store.bump()


def handle_event(worker: dict, ev: dict, first_response) -> None:
    """One stream event from a worker. Runs on the worker's reader thread."""
    item_id, phase = worker["item_id"], worker["phase"]
    with store.LOCK:
        it = store.find(item_id)
        kind = ev.get("type")
        if kind == "control_request":
            answer_permission(worker, it, ev, phase)
        elif kind == "system" and ev.get("subtype") == "init":
            if it and not worker["session_seen"]:
                it["sessions"][phase] = ev.get("session_id") or it["sessions"].get(phase)
                worker["session_seen"] = True
                extra = sorted(set(ev.get("tools") or ()) - config.WORKER_TOOLS)
                if extra:
                    store.say(it, store.event("\u26a0 tools outside the worker set — "
                                              + ", ".join(extra)), sess=phase)
            # A worker can start a turn on its own (a background-task
            # notification, for one); init marks only a turn the console sent,
            # or the one a steer starts when it lands a moment too late.
            if worker["state"] == "sending":
                worker["state"] = "running"
            elif it and worker["state"] == "idle" and worker.get("steer"):
                adopt_turn(it, worker, phase)
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
                    store.say(it, store.event(f"long thinking — {RUNAWAY_THINK // 1000}k "
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
                    store.say(it, entry, sess=phase)
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
            store.say(it, store.event(
                "compacted · pre {pre:,} · post {post:,} · dropped {drop:,}".format(
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
                                                or store.model_of(it, phase),
                                                ctx.get("limiting"))
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
                        store.say(it, store.event("stopped"), sess=phase)
                    else:
                        store.say(it, store.event(f"turn failed ({reason})"), sess=phase)
                    # A segment that never lands still spent quota, and this
                    # line is the only place it is ever counted.
                    store.say(it, store.event(turn_note(it, ev, phase, worker["started"],
                                                        reqs, lost, done=False)),
                              sess=phase)
                    if not escalate:
                        store.turn_died(it, phase)
                        if pacing.quota_death(ev.get("api_error_status"), reason,
                                              str(ev.get("result") or "")):
                            pacing.quota_cut(it, phase, handoff)
            finally:
                # A steer written before this turn was landing is one this turn
                # absorbed, so it explains no later turn.
                pending = worker.get("steer")
                if pending and time.time() - pending["at"] > config.STEER_RACE:
                    worker.pop("steer", None)
                # The worker goes idle even if landing the turn blew up;
                # a wedged "running" state would block sends and reloads.
                worker.update(state="idle", started=None, trigger=None,
                              handoff=False, seen=set(), got_result=False,
                              think_run=0, reqs={}, idle_since=time.time())
            if escalate and reason != "completed":
                # The relaunch must come from a fresh process: the live one
                # holds the turn's history in memory, where the capped
                # thinking is already gone. A respawn rebuilds from the
                # transcript, which patch_capped repairs first.
                if store.PROCS.get((item_id, phase)) is worker:
                    store.PROCS.pop((item_id, phase))
                    worker["state"] = "dying"
                    worker["outbound"].put_nowait(store.STOP)
                store.DEFERRED.put_nowait(("revive", worker, escalate, handoff))
                ensure_drain()


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
    with store.LOCK:
        for worker in list(store.PROCS.values()):
            if (worker["state"] not in ("sending", "running")
                    or worker.get("escalate")):
                continue
            it = store.find(worker["item_id"])
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
    store.say(it, store.event(f"⚠ runaway thinking — {note} "
                              f"({count}× this session) — {worker['escalate']}"), sess=phase)
    worker["outbound"].put_nowait({"type": "control_request",
        "request_id": str(uuid.uuid4()), "request": {"subtype": "interrupt"}})


def revive(worker: dict, step: str, handoff: bool) -> None:
    """Preserve a capped generation's thinking, then relaunch its turn.

    Runs on the drain thread with the worker already detached: the process
    dies first, the transcript patch lands while nothing else writes the
    file, and the relaunch spawns a fresh process whose resume reads the
    repaired history."""
    if worker.get("proc") is not None:
        reap(worker)
    with store.LOCK:
        it = store.find(worker["item_id"])
        if not it:
            return
        phase = worker["phase"]
        session = it["sessions"].get(phase)
        path = transcript_of(session) if session else None
        if path is not None:
            try:
                if patch_capped(path):
                    store.say(it, store.event("capped thinking preserved for the resume"),
                              sess=phase)
            except OSError as exc:
                store.say(it, store.event(f"transcript patch failed: {exc}"), sess=phase)
        escalate_turn(it, phase, step, handoff)
    store.bump()


def escalate_turn(it: dict, phase: str, step: str, handoff: bool) -> None:
    """Relaunch after a runaway interrupt lands. Caller holds LOCK and has
    reset the worker. The nudge keeps the turn's own handoff flag. A bail on a
    non-final stage asks for the report whose landing hands off; the final
    stage has no stronger session to receive it, so the item lands for review.
    A bail that itself runs away has said its piece twice, so the item lands
    either way."""
    count = it.get("runaway", {}).get(phase, 0)
    if step == "nudge":
        launch(it, prompts.NUDGE_BRIEF, phase, trigger="nudge", handoff=handoff,
               admitted=True, escalated=True)
    elif store.next_stage(it, phase) and count <= 2:
        launch(it, prompts.BAIL_BRIEF, phase, trigger="bail", handoff=True,
               admitted=True, escalated=True)
    else:
        store.turn_died(it, phase)


def auto_advances(it: dict, phase: str) -> bool:
    """Whether a report landing at `phase` hands the item on by itself.

    `auto_stop` names a stage auto-advance will not launch, so a run can carry
    items through the cheap stages and stop before an expensive one. Without
    it, auto-advance runs the whole chain."""
    if not it.get("auto_advance"):
        return False
    nxt = store.next_stage(it, phase)
    return bool(nxt) and nxt["name"] != it.get("auto_stop")


def advance_stage(it: dict) -> None:
    """Move the item on to the next stage and enqueue its first turn."""
    nxt = store.next_stage(it, it["phase"])
    if nxt is None:
        return
    if store.RELOADING:
        it["state"] = store.NEEDS_REVIEW
        it["updated"] = True
        store.say(it, store.event("handoff paused for server reload"))
        return
    prev, it["phase"] = it["phase"], nxt["name"]
    it["state"] = store.RUNNING
    store.say(it, store.event(f"handoff — {nxt['name']} session starting"))
    # A stage with a successor opens its pass under the handoff flag, so its
    # landing hands the chain on the way the first stage's does.
    more = store.next_stage(it, nxt["name"]) is not None
    launch(it, prompts.advance_message(it, prev, more), nxt["name"], handoff=more)


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
    rows = [u for u in store.USAGE
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


def think_note(tokens: int, model: str) -> str:
    """Discarded thinking never reaches the CLI's cost accounting, so price
    the estimate at the stage model's output rate. It is measured differently
    from the dollars beside it, so it reads as its own term."""
    pair = rates(model)
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
        note += think_note(lost, store.model_of(it, phase))
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
            store.touch(it)
        else:
            store.say(it, {"kind": "report", "rev": it["rev"], "text": text}, sess=phase)
    store.say(it, store.event(turn_note(it, ev, phase, started, reqs)), sess=phase)
    # A turn with no Callouts section says nothing about them, so the item
    # keeps what the last report that carried one left.
    if text and solvers.CALLOUT_HEAD.search(text):
        it["callouts"] = solvers.parse_callouts(text)
        it["callout_n"] = len(it["callouts"])
        it["callout_rank"] = solvers.callout_rank(it["callouts"])
    ledger.ledger_append({"task": it["id"], "stage": phase,
                          "backend": store.backend_of(it, phase),
                          "model": store.model_of(it, phase),
                          "session": it["sessions"].get(phase), "ts": int(store.now()),
                          "source": "console"})
    # the create pass ends in prune, and every later pass is itself a quality
    # pass, so each stage's first landing is clean by cadence
    landed = it.setdefault("landed", [])
    first_landing = phase not in landed
    if first_landing:
        landed.append(phase)
    if trigger in CLEAN_TRIGGERS or first_landing:
        it["dirty"] = False
    elif solvers.solver_hash(it["id"]) != store.pre(it)["hash"]:
        it["dirty"] = True
    if not store.pre(it).get("slash"):
        it.setdefault("seen_hash", {})[phase] = solvers.solver_hash(it["id"])
    it["lastActive"][phase] = int(time.time() * 1000)
    it["title"] = solvers.title_of(it["id"]) or it.get("title", "")
    it["prop_after"] = solvers.prop_text()
    it["comps"] = solvers.comps_of(it["id"])
    it["comps_unproposed"] = solvers.unproposed(it["comps"], it["prop_after"])
    it["landed_at"] = store.now()
    fresh = [rel for rel in store.shared_writes(it)
             if rel not in it.setdefault("shared_writes", [])]
    if fresh:
        it["shared_writes"].extend(fresh)
        store.say(it, store.event("shared files changed: " + ", ".join(fresh)), sess=phase)
    it.pop("quota_retry", None)  # the stage got a turn through; retries reset
    if it.get("resume_phase") == phase and not it.get("resume_at"):
        it.pop("resume_phase", None)
        it.pop("resume_handoff", None)
    callout_landing = it.get("callout_wait") == phase
    if callout_landing:
        it.pop("callout_wait", None)
    if callout_landing and store.next_stage(it, phase):
        # the callout turn's text joins the stage report, so parsing and the
        # finalize read see one document per stage
        if text:
            combined = ((it.get("reports", {}).get(phase) or "").rstrip()
                        + "\n\n" + text)
            it.setdefault("reports", {})[phase] = combined
            solvers.save_report(it["id"], phase, combined)
        if auto_advances(it, phase):
            it["handoff_pending"] = True
            worker = store.PROCS.get((it["id"], phase))
            if worker:
                store.DEFERRED.put_nowait(("handoff", it["id"], phase, worker["turn_seq"]))
                ensure_drain()
        else:
            it["state"] = store.NEEDS_REVIEW
            it["updated"] = True
    elif handoff and store.next_stage(it, phase):
        it.setdefault("reports", {})[phase] = text
        solvers.save_report(it["id"], phase, text)
        # the callouts get their own turn before any advance
        worker = store.PROCS.get((it["id"], phase))
        if worker:
            it["callout_wait"] = phase
            store.DEFERRED.put_nowait(("callout", it["id"], phase, worker["turn_seq"]))
            ensure_drain()
        else:
            it["state"] = store.NEEDS_REVIEW
            it["updated"] = True
    elif not store.pre(it).get("slash") and not store.busy_elsewhere(it, phase):
        # a side turn landing while another session runs leaves the state to
        # the pass that owns it
        it["state"] = store.NEEDS_REVIEW
        it["updated"] = True


def ensure_drain() -> None:
    if store.DEFERRED_THREAD is None or not store.DEFERRED_THREAD.is_alive():
        store.DEFERRED_THREAD = threading.Thread(target=drain_deferred, daemon=True)
        store.DEFERRED_THREAD.start()


def drain_deferred() -> None:
    while True:
        job = store.DEFERRED.get()
        if job is store.STOP:
            return
        try:
            if job[0] == "reap":
                reap(job[1])
                continue
            if job[0] == "revive":
                revive(*job[1:])
                continue
            kind, item_id, phase, turn_seq = job
            with store.LOCK:
                it = store.find(item_id)
                worker = store.PROCS.get((item_id, phase))
                if kind == "callout":
                    if not it or it.get("callout_wait") != phase:
                        continue
                    if not worker or worker["turn_seq"] != turn_seq or store.RELOADING:
                        # the report stands without callouts
                        it.pop("callout_wait", None)
                        it["state"] = store.NEEDS_REVIEW
                        it["updated"] = True
                        if store.RELOADING:
                            store.say(it, store.event("callouts paused for server reload"),
                                      sess=phase)
                    else:
                        it["state"] = store.RUNNING
                        store.say(it, store.event("callout turn starting"), sess=phase)
                        launch(it, prompts.callout_brief(), phase, trigger="callout")
                elif not it or not it.get("handoff_pending") or not worker or \
                        worker["turn_seq"] != turn_seq:
                    if it:
                        it.pop("handoff_pending", None)
                    continue
                else:
                    it.pop("handoff_pending", None)
                    advance_stage(it)
            store.bump()
        except Exception as exc:
            print(f"deferred {job[0]} failed: {exc}", file=sys.stderr)


def detach_workers(item_id: str) -> list[dict]:
    workers = []
    for key, worker in list(store.PROCS.items()):
        if key[0] == item_id and store.PROCS.get(key) is worker:
            store.PROCS.pop(key)
            worker["state"] = "dying"
            worker["outbound"].put_nowait(store.STOP)
            workers.append(worker)
    return workers


def queue_reap(worker: dict) -> None:
    store.DEFERRED.put_nowait(("reap", worker))
    ensure_drain()


def reapable(key: tuple[str, str], worker: dict) -> dict | None:
    """The item behind an idle worker that may be dropped, or None. An item
    with a deferred job queued keeps its worker: drain_deferred skips the
    callout turn and the stage advance when the worker is gone."""
    if worker["state"] != "idle" or worker.get("idle_since") is None or \
            store.PROCS.get(key) is not worker:
        return None
    it = store.find(key[0])
    if it is None or it.get("callout_wait") or it.get("handoff_pending"):
        return None
    return it


def drop_worker(it: dict, key: tuple[str, str], worker: dict, why: str) -> None:
    """Take an idle worker out of PROCS and stop its process. Caller holds
    LOCK. The item keeps its session id, so a later comment resumes the phase
    from the transcript."""
    store.PROCS.pop(key)
    worker["state"] = "dying"
    worker["outbound"].put_nowait(store.STOP)
    store.say(it, store.event(f"{key[1]} worker reaped {why}"), sess=key[1])
    queue_reap(worker)


def reap_idle() -> None:
    """Drop idle workers under two rules. Anything idle past IDLE_TTL goes.
    Beyond that, the workers of autopilot items are held to NIGHT_WORKER_CAP,
    counting the running ones, oldest idle first."""
    now = time.time()
    reaped = 0
    with store.LOCK:
        for key, worker in list(store.PROCS.items()):
            it = reapable(key, worker)
            since = worker.get("idle_since")
            if it is None or now - since < config.IDLE_TTL:
                continue
            drop_worker(it, key, worker,
                        f"after {int((now - since) // 60)}m idle")
            reaped += 1
        night_keys = [key for key in store.PROCS
                      if (it := store.find(key[0])) is not None and it.get("night")]
        over = len(night_keys) - config.NIGHT_WORKER_CAP
        if over > 0:
            spare = []
            for key in night_keys:
                worker = store.PROCS[key]
                it = reapable(key, worker)
                if it is not None:
                    spare.append((worker["idle_since"], key, worker, it))
            spare.sort(key=lambda row: row[0])
            for _, key, worker, it in spare[:over]:
                drop_worker(it, key, worker,
                            f"over the {config.NIGHT_WORKER_CAP}-worker autopilot cap")
                reaped += 1
    if reaped:
        store.bump()


def idle_loop() -> None:
    while True:
        time.sleep(config.IDLE_POLL)
        if store.SHUTTING_DOWN or store.RELOADING:
            continue
        try:
            reap_idle()
        except Exception as exc:
            print(f"idle reap failed: {exc}", file=sys.stderr)


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
