"""A worker process: the command that spawns one, the threads that write to
it and read its stream, the handler that reads each event the stream carries,
and the adoption that keeps a live worker across a re-exec."""

import fcntl
import json
import os
import queue
import signal
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import config, drain, landing, pacing, prompts, refusals, solvers, spend, store, workers


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
    rows = []
    inheritable = []
    try:
        for (item_id, phase), worker in store.PROCS.items():
            proc = worker["proc"]
            stdin_fd, stdout_fd = proc.stdin.fileno(), proc.stdout.fileno()
            for fd in (stdin_fd, stdout_fd):
                os.set_inheritable(fd, True)
                inheritable.append(fd)
            it = store.find(item_id)
            rows.append({"item": item_id, "phase": phase, "pid": proc.pid,
                         "stdin_fd": stdin_fd, "stdout_fd": stdout_fd,
                         "session": it["sessions"].get(phase) if it else None,
                         "turn_seq": worker["turn_seq"], "state": worker["state"],
                         "started": worker["started"]})
        return {"server_pid": os.getpid(), "workers": rows}
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
                      "bg": {}, "session_seen": bool(entry.get("session")),
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
                    store.say(it, store.event(f"session lost on reload: {lost_session}"),
                              sess=phase)
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
    elif rel.startswith("docs/wf-solver/proposals/"):
        p_["files"][rel] = (p_["proposals"] or {}).get(rel, "")
    else:
        p = config.ROOT / rel
        p_["files"][rel] = p.read_text() if p.exists() else ""


def note_touched(it: dict, worker: dict, inp: dict) -> None:
    """Remember the shared files a tool call names, by path or by file name.
    A watched file that changes over the turn is charged to the turn only
    when one of its calls named it; the rest is the user's own editing."""
    blob = json.dumps(inp)
    touched = worker.setdefault("touched", set())
    for rel in solvers.watched_paths(it["id"]):
        if rel not in touched and (rel in blob or rel.rsplit("/", 1)[-1] in blob):
            touched.add(rel)


def task_ask(inp: dict) -> str:
    """The brief a Task call gives its subagent, as feed markdown."""
    head = " · ".join(x for x in (str(inp.get("subagent_type") or "").strip(),
                                  str(inp.get("description") or "").strip()) if x)
    prompt = str(inp.get("prompt") or "").strip()
    return f"**{head}**\n\n{prompt}" if head else prompt


# The CLI registers the subagent tool as Task in the init event and emits
# its calls as Agent, so a tool_use block may carry either name.
DISPATCH = ("Task", "Agent")


def bg_label(name: str, inp: dict) -> str:
    """What a background task the worker started is called in the feed."""
    if name in DISPATCH:
        return str(inp.get("description") or "").strip() or "a subagent"
    cmd = str(inp.get("command") or "").replace("\n", " ").strip()
    return f"`{cmd[:60]}`" if cmd else name


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


# Words asking for a pass that ends in Simplify and Prune, so the turn's


def permission_decision(req: dict) -> dict:
    """The console's answer to one permission request. A worker may edit the
    agent files, which the CLI holds back as files of its own; the edit
    surfaces at landing as a shared write. Every other request keeps the
    refusal the CLI already reached."""
    if req.get("tool_name") in ("Edit", "Write"):
        try:
            asked = Path((req.get("input") or {}).get("file_path") or "").resolve()
        except OSError:
            asked = None
        if (asked is not None and asked.suffix == ".md"
                and asked.parent == config.AGENT_DIR.resolve()):
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
    agents = prompts.worker_agents(it["append"])
    if agents:
        cmd += ["--agents", agents]
    if st.get("model"):
        cmd += ["--model", st["model"]]
    effort = st.get("effort") or config.CLAUDE_EFFORT
    if effort:
        cmd += ["--effort", effort]
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
              "reqs": {}, "bg": {}, "idle_since": None}
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
        kind, subtype = ev.get("type"), ev.get("subtype")
        if kind == "control_request":
            answer_permission(worker, it, ev, phase)
        elif kind == "system" and subtype == "init":
            on_init(worker, it, ev, phase)
        elif kind == "system" and subtype == "task_started":
            on_task_started(worker, ev)
        elif kind == "system" and subtype == "task_notification":
            on_task_notification(worker, ev)
        elif kind == "system" and subtype == "thinking_tokens":
            on_thinking_tokens(worker, it, ev, phase)
        elif kind == "assistant":
            on_assistant(worker, it, ev, phase, first_response)
        elif kind == "system" and subtype == "compact_boundary":
            on_compact_boundary(worker, it, ev, phase)
        elif kind == "result":
            on_result(worker, it, ev, phase)


def on_init(worker: dict, it: dict | None, ev: dict, phase: str) -> None:
    """The event that opens a turn. Caller holds LOCK."""
    if it and not worker["session_seen"]:
        it["sessions"][phase] = ev.get("session_id") or it["sessions"].get(phase)
        worker["session_seen"] = True
        extra = sorted(set(ev.get("tools") or ()) - config.WORKER_TOOLS)
        if extra:
            store.say(it, store.event("\u26a0 tools outside the worker set — "
                                      + ", ".join(extra)), sess=phase)
    # A worker can start a turn on its own (a background-task notification,
    # for one); init marks only a turn the console sent, or the one a steer
    # starts when it lands a moment too late.
    if worker["state"] == "sending":
        worker["state"] = "running"
    elif it and worker["state"] == "idle" and (
            worker.get("steer") or worker.get("bg") or worker.get("woke")
            or it.get("bg_wait") == phase):
        workers.adopt_turn(it, worker, phase)


def on_task_started(worker: dict, ev: dict) -> None:
    """A call that got a background task. The task's result reaches the
    session as a notification, which lands after this turn ends, so the task
    stays outstanding across the turns between here and that notification. A
    task a subagent started is the subagent's. Caller holds LOCK."""
    label = worker.get("launch", {}).pop(ev.get("tool_use_id"), None)
    if label:
        worker.setdefault("bg", {})[ev["tool_use_id"]] = label


def on_task_notification(worker: dict, ev: dict) -> None:
    """A background task reported. Caller holds LOCK."""
    worker.get("bg", {}).pop(ev.get("tool_use_id"), None)
    # A notification the worker takes while idle opens a turn, whose init
    # follows this event.
    if worker["state"] == "idle":
        worker["woke"] = True


def on_thinking_tokens(worker: dict, it: dict | None, ev: dict, phase: str) -> None:
    """A stretch of thinking, counted against the runaway warning. Caller
    holds LOCK."""
    if not it or worker["state"] not in ("sending", "running"):
        return
    worker["think_run"] = (worker.get("think_run", 0)
                           + (ev.get("estimated_tokens_delta") or 0))
    if worker["think_run"] >= workers.RUNAWAY_THINK and not worker.get("escalate"):
        # Warn only. An interrupt here aborts the generation, and an aborted
        # generation writes nothing — the reasoning is gone. A generation that
        # runs to the cap lands in the transcript with its signature, which
        # patch_capped turns into context the relaunch keeps. So the cap is
        # the cheaper exit, at the cost of the rest of the budget.
        worker["think_run"] = 0
        store.say(it, store.event(f"long thinking — {workers.RUNAWAY_THINK // 1000}k "
                                  "tokens with no actions yet"), sess=phase)


def on_assistant(worker: dict, it: dict | None, ev: dict, phase: str,
                 first_response) -> None:
    """One message the model wrote: its feed lines, the files it touched, and
    the usage the request reports. Caller holds LOCK."""
    if first_response:
        first_response.set()
    if not it:
        return
    msg = ev.get("message", {})
    mid = msg.get("id") or ""
    sub = bool(ev.get("parent_tool_use_id"))
    usage = msg.get("usage")
    if usage and mid and not sub and worker["state"] in ("sending", "running"):
        # One entry per request; a request's block events repeat the same
        # usage. Subagent requests run their own context.
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
            note_touched(it, worker, inp)
            if not sub and block.get("id") and (
                    name in DISPATCH or inp.get("run_in_background")):
                # A call that asks for a task. Whether it got one is the
                # harness's word: task_started names the call, and a call a
                # hook refused never starts.
                worker.setdefault("launch", {})[block["id"]] = bg_label(name, inp)
            if name in DISPATCH:
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
    # The live CLI streams stop_reason as null on every assistant event, so
    # today this fires only for a stream that does report the cap — the fake
    # worker, or a CLI that starts filling the field in. The transcript tail
    # is the detector that works now.
    if (msg.get("stop_reason") == "max_tokens" and blocks and
            all(b.get("type") == "thinking" for b in blocks) and
            worker["state"] in ("sending", "running") and
            not worker.get("escalate") and
            (mid, "runaway") not in worker["seen"]):
        worker["seen"].add((mid, "runaway"))
        workers.runaway_detected(it, worker, "hit the output cap with no actions")


def on_compact_boundary(worker: dict, it: dict | None, ev: dict, phase: str) -> None:
    """The session was compacted. Caller holds LOCK."""
    if not it:
        return
    # a compact from any ask counts as the one the auto compact owes this
    # stretch of the session
    it.setdefault("auto_compacted", {})[phase] = True
    worker["compacted"] = True
    meta = ev.get("compact_metadata") or {}
    store.say(it, store.event(
        "compacted · pre {pre:,} · post {post:,} · dropped {drop:,}".format(
            pre=meta.get("pre_tokens", 0), post=meta.get("post_tokens", 0),
            drop=meta.get("cumulative_dropped_tokens", 0))), sess=phase)
    # A compact turn reports no per-request usage, so this event is the only
    # word on the new context size until the next turn lands.
    post = meta.get("post_tokens")
    ctx = it.get("context", {}).get(phase)
    if ctx and isinstance(post, (int, float)) and post > 0:
        ctx["used"] = post
        ctx["percent"] = post / ctx["window"] * 100
        ctx["compactPct"] = spend.compact_pct(
            post, ctx.get("model") or store.model_of(it, phase), ctx.get("limiting"))


def on_result(worker: dict, it: dict | None, ev: dict, phase: str) -> None:
    """The end of a turn: its landing, or the note and the relaunch a turn
    that ended without one gets. Caller holds LOCK."""
    if not it or worker["state"] not in ("sending", "running"):
        return
    worker["got_result"] = True
    reason = ev.get("terminal_reason", "completed")
    escalate = worker.pop("escalate", None)
    handoff = worker["handoff"]
    ask = worker.get("ask")
    recover = None
    try:
        # The last messages may not have reached the tail's poll, and leaving
        # them unread would carry them into the next turn.
        if it["sessions"].get(phase):
            try:
                workers.tail_turn(worker, it["sessions"][phase])
            except OSError:
                pass
        reqs = list(worker.get("reqs", {}).values())
        # A generation that reached the cap is recorded with its thinking; one
        # the interrupt caught in flight is not, so an unfinished run is what
        # the turn lost.
        lost = 0 if reason == "completed" else worker.get("think_run", 0)
        if reason == "completed":
            landing.finish_turn(it, ev, worker["trigger"], worker["started"],
                                phase, handoff, reqs)
        else:
            if escalate:
                pass  # the interrupt we sent landed; relaunched below
            elif reason == "aborted_streaming":
                store.say(it, store.event("stopped"), sess=phase)
            else:
                if refusals.refusal_kind(ev) == refusals.RETRIED_REFUSAL:
                    recover = refusals.REPORT_ASKS.get(worker["trigger"])
                store.say(it, store.event(refusals.failure_note(ev, reason,
                                                                bool(recover))),
                          sess=phase)
            # A segment that never lands still spent quota, and this line is
            # the only place it is ever counted.
            store.say(it, store.event(spend.turn_note(it, ev, phase, worker["started"],
                                                      reqs, lost, done=False)),
                      sess=phase)
            if not escalate and not recover:
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
        # The worker goes idle even if landing the turn blew up; a wedged
        # "running" state would block sends and reloads.
        worker.update(state="idle", started=None, trigger=None,
                      handoff=False, seen=set(), got_result=False,
                      think_run=0, reqs={}, idle_since=time.time())
    if escalate and reason != "completed":
        # The relaunch must come from a fresh process: the live one holds the
        # turn's history in memory, where the capped thinking is already gone.
        # A respawn rebuilds from the transcript, which patch_capped repairs
        # first.
        workers.detach_for_respawn(it, worker)
        store.DEFERRED.put_nowait(("revive", worker, escalate, handoff))
        drain.ensure_drain()
    elif recover:
        # The refused ask is in the live process's history as much as in the
        # transcript, so the retry comes from a fresh process over a
        # transcript with the ask cut out.
        workers.detach_for_respawn(it, worker)
        store.DEFERRED.put_nowait(("refuse", worker, recover, ask))
        drain.ensure_drain()


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
