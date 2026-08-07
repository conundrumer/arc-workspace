#!/usr/bin/env python3
"""Review console for batch solver workers.

Serves the console UI, launches `claude -p` workers in waves, resumes them
with review comments, and commits approved solvers.

    uv run python tools/console/server.py [--port 8347]

Env:
    CONSOLE_FAKE=1     use fake_worker.py instead of claude (UI demo)
    CONSOLE_CLAUDE     claude binary (default: claude)
    CONSOLE_MODEL      worker model (default: claude-fable-5)
    CONSOLE_COMMIT_MODEL   committer model (default: claude-opus-5)
"""

import argparse
import fcntl
import functools
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATE_DIR = Path(os.environ.get("CONSOLE_STATE_DIR", HERE / "state"))
STATE_FILE = STATE_DIR / "state.json"
LOG_DIR = STATE_DIR / "logs"
SOLVERS = ROOT / "programs" / "solvers"
DOCS = ROOT / "docs" / "wf-solver"
TASKS = ROOT / "data" / "tasks"
REF_DIR = (ROOT.parent / "arc-synth-bun").resolve()

FAKE = os.environ.get("CONSOLE_FAKE") == "1"
CLAUDE = os.environ.get("CONSOLE_CLAUDE", "claude")
MODEL = os.environ.get("CONSOLE_MODEL", "claude-fable-5")
COMMIT_MODEL = os.environ.get("CONSOLE_COMMIT_MODEL", "claude-opus-5")

WORKER_FLAGS = [
    "--output-format", "stream-json", "--verbose",
    "--permission-mode", "acceptEdits",
    "--allowedTools",
    "Bash(uv run:*)", "Bash(cat:*)", "Bash(ls:*)", "Bash(souffle:*)",
    "--add-dir", str(REF_DIR),
    "--exclude-dynamic-system-prompt-sections",
]
STAGGER_TIMEOUT = 120  # seconds to wait for the first worker's first API response
COMMIT_BRIEF = """Commit the changes that solver workers left in the working tree.

Scope: files git already tracks, under programs/ and docs/wf-solver/. Never stage untracked files, and leave changes outside that scope alone.

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
PROCS: dict[str, subprocess.Popen] = {}
KILLED: set[str] = set()  # items whose running turn the user stopped
USAGE: list[dict] = []  # account rate-limit windows, refreshed in background
COMMITTER = {"running": False, "note": None}


# ---------- item lifecycle ----------
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
    """Whether a worker turn is in flight. The state alone is not enough: the
    result event flips the item to NEEDS_REVIEW while its reader is still
    draining stdout, and the process stays in PROCS until that finishes."""
    return it["state"] in ACTIVE or it["id"] in PROCS


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
    if it["id"] in PROCS:
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
            it["state"] = NEEDS_REVIEW if it.get("session") else QUEUED
            say(it, event("interrupted by console restart"))


def migrate(it: dict) -> None:
    """Fold an item written before `pre` into the grouped snapshot."""
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


def say(it: dict, entry: dict) -> None:
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
    parts = [skill_body() + "\n"]
    for doc in sorted(DOCS.glob("*.md")):
        parts.append(f"\n---\n\n# docs/wf-solver/{doc.name}\n\n{doc.read_text()}")
    lib = (ROOT / "programs" / "lib.dl").read_text()
    parts.append(f"\n---\n\n# programs/lib.dl\n\n```\n{lib}\n```\n")
    path = STATE_DIR / f"wave-{wave:02d}-append.md"
    path.write_text("".join(parts))
    return path


# ---------- workers ----------

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


def launch(it: dict, message: str, trigger: str | None = None) -> None:
    """Start a worker turn for `it`. Caller holds LOCK and has set state."""
    reverted = it.pop("reverted", None)
    if reverted:
        message = ("<system-reminder>The user reverted the file edits from your "
                   f"previous turn; {', '.join(reverted)} on disk is back to its "
                   "pre-turn state. Re-read before editing.</system-reminder>\n\n"
                   + message)
    if FAKE:
        cmd = [sys.executable, str(HERE / "fake_worker.py"), it["id"], message]
    else:
        cmd = [CLAUDE, "-p", message,
               "--append-system-prompt", Path(it["append"]).read_text(),
               *WORKER_FLAGS]
        if MODEL:
            cmd += ["--model", MODEL]
        if it.get("session"):
            cmd += ["--resume", it["session"]]
    log = open(LOG_DIR / f"{it['id']}.log", "ab")
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=log, text=True)
    log.close()
    PROCS[it["id"]] = proc
    it["pre"] = {"hash": solver_hash(it["id"]), "solver": solver_text(it["id"]),
                 "proposals": prop_text(), "dirty": it["dirty"], "files": {}}
    threading.Thread(target=reader, args=(it["id"], proc, trigger),
                     daemon=True).start()


def reader(item_id: str, proc: subprocess.Popen, trigger: str | None) -> None:
    started = time.time()
    got_result = False
    seen: set = set()  # stream-json emits one event per content block, same message id
    first_response = FIRST_RESPONSE.get(item_id)
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        with LOCK:
            it = find(item_id)
            if it is None:
                break
            kind = ev.get("type")
            if kind == "system" and ev.get("subtype") == "init":
                it["session"] = ev.get("session_id") or it.get("session")
            elif kind == "assistant":
                if first_response:
                    first_response.set()
                msg = ev.get("message", {})
                mid = msg.get("id") or ""
                sub = bool(ev.get("parent_tool_use_id"))
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
                    if entry and key not in seen:
                        seen.add(key)
                        if sub or entry["kind"] == "ask":
                            entry["sub"] = True
                        say(it, entry)
            elif kind == "result":
                got_result = True
                finish_turn(it, ev, trigger, started)
        bump()
    proc.wait()
    with LOCK:
        PROCS.pop(item_id, None)
        it = find(item_id)
        if it and not got_result:
            if item_id in KILLED:
                KILLED.discard(item_id)
                say(it, event("stopped"))
            else:
                tail = ""
                log = LOG_DIR / f"{item_id}.log"
                if log.exists():
                    tail = log.read_text(errors="replace")[-400:].strip()
                say(it, event(f"worker exited without result (code {proc.returncode}) — {tail}"))
            it["state"] = NEEDS_REVIEW if it.get("session") else QUEUED
            it["updated"] = True
    if first_response:
        first_response.set()
    bump()


def finish_turn(it: dict, ev: dict, trigger: str | None, started: float) -> None:
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
            match.update(kind="report", rev=it["rev"], text=text)
            touch(it)
        else:
            say(it, {"kind": "report", "rev": it["rev"], "text": text})
    cost = ev.get("total_cost_usd")
    mins = (time.time() - started) / 60
    note = f"turn done · {mins:.0f}m" if mins >= 1 else "turn done · <1m"
    if isinstance(cost, (int, float)):
        note += f" · ${cost:.2f}"
    say(it, event(note))
    if trigger in CLEAN_TRIGGERS or it["rev"] == 1:
        it["dirty"] = False
    elif solver_hash(it["id"]) != pre(it)["hash"]:
        it["dirty"] = True
    it["state"] = NEEDS_REVIEW
    it["updated"] = True
    it["lastActive"] = int(time.time() * 1000)
    it["title"] = title_of(it["id"]) or it.get("title", "")
    it["prop_after"] = prop_text()


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
        if time.time() - LAST_WAVE_AT < WAVE_DEBOUNCE:
            return {"error": "a wave just started — wait a moment to start another"}
        if order not in ("name", "size"):
            return {"error": f"unknown order: {order}"}
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
                "session": None, "dirty": False, "updated": False, "rev": 0,
                "lastActive": None, "title": "", "feed": [], "append": append,
                "ver": 0,
            })
    bump()
    threading.Thread(target=stagger_launch,
                     args=([tid for tid, _ in picked],), daemon=True).start()
    return {"ok": True, "ids": [tid for tid, _ in picked]}


def stagger_launch(ids: list[str]) -> None:
    """Launch the first worker alone so it writes the shared prompt-cache
    prefix, then fan the rest out once its first API response arrives."""
    first = FIRST_RESPONSE[ids[0]] = threading.Event()
    with LOCK:
        it = find(ids[0])
        it["state"] = RUNNING
        say(it, event("launched (cache seeder)"))
        launch(it, first_message(ids[0]))
    bump()
    first.wait(timeout=STAGGER_TIMEOUT)
    FIRST_RESPONSE.pop(ids[0], None)
    with LOCK:
        for tid in ids[1:]:
            it = find(tid)
            it["state"] = RUNNING
            say(it, event("launched"))
            launch(it, first_message(tid))
    bump()


def first_message(tid: str) -> str:
    return f"Task: {tid}. Work this solver per the cadence."


# ---------- actions ----------

@action
def act_comment(it: dict, text: str) -> None:
    text = text.strip()
    if text.lower() in ("commit", "next"):
        raise Reject(f"`{text}` is a console action, not a worker message")
    require_idle(it)
    if not it.get("session"):
        raise Reject("no session yet")
    say(it, {"kind": "you", "text": text})
    it["state"] = COMMENTED
    it["updated"] = False
    head = text.lower().split()[:1]
    trigger = head[0] if head and head[0] in CLEAN_TRIGGERS else None
    launch(it, text, trigger)


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
    STATE["items"] = [x for x in STATE["items"] if x["id"] != it["id"]]


def act_kill(item_id: str) -> dict:
    proc = PROCS.get(item_id)
    if proc is None:
        return {"error": "no worker running"}
    KILLED.add(item_id)
    proc.terminate()

    def force():
        time.sleep(10)
        if proc.poll() is None:
            proc.kill()
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
    it["reverted"] = reverted
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
        chk = subprocess.run(["git", "status", "--porcelain", "--",
                              "programs", "docs/wf-solver"],
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
    return [{k: it.get(k) for k in
             ("id", "state", "dirty", "updated", "session", "lastActive",
              "wave", "rev", "title", "est", "ver", "append")} |
            {"active": active(it)}
            for it in STATE["items"]]


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
                        "cli": {"addDir": str(REF_DIR), "model": MODEL},
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
            res = act_comment(body.get("id", ""), body.get("text", ""))
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
    while True:
        if script.exists():
            subprocess.run(["bash", str(script)], capture_output=True, timeout=30)
        USAGE = read_usage()
        time.sleep(60)


def watch_reload() -> None:
    """Re-exec when server.py changes, once no worker is mid-turn."""
    src = Path(__file__)
    mtime = src.stat().st_mtime
    while True:
        time.sleep(2)
        try:
            if src.stat().st_mtime == mtime:
                continue
        except OSError:
            continue
        with LOCK:
            if PROCS:
                continue
            save()
        print("server.py changed — restarting")
        os.execv(sys.executable, [sys.executable] + sys.argv)


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
    load()
    save()
    threading.Thread(target=watch_reload, daemon=True).start()
    threading.Thread(target=usage_loop, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    mode = " (FAKE workers)" if FAKE else ""
    print(f"solver console · http://127.0.0.1:{args.port}{mode}")
    server.serve_forever()


if __name__ == "__main__":
    main()
