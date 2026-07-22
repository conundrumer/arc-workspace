#!/usr/bin/env python3
"""Review console for batch solver workers.

Serves the console UI, launches `claude -p` workers in waves, resumes them
with review comments, and commits approved solvers.

    uv run python tools/console/server.py [--port 8347]

Env:
    CONSOLE_FAKE=1     use fake_worker.py instead of claude (UI demo)
    CONSOLE_CLAUDE     claude binary (default: claude)
    CONSOLE_MODEL      worker model override (default: CLI default)
"""

import argparse
import fcntl
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
MODEL = os.environ.get("CONSOLE_MODEL")

WORKER_FLAGS = [
    "--output-format", "stream-json", "--verbose",
    "--permission-mode", "acceptEdits",
    "--allowedTools",
    "Bash(uv run:*)", "Bash(cat:*)", "Bash(ls:*)", "Bash(souffle:*)",
    "--add-dir", str(REF_DIR),
    "--exclude-dynamic-system-prompt-sections",
]
STAGGER_TIMEOUT = 120  # seconds to wait for the first worker's first API response
TRAILER = "\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>\n"

LOCK = threading.RLock()
COND = threading.Condition(LOCK)
STATE = {"seq": 0, "wave": 0, "items": []}
PROCS: dict[str, subprocess.Popen] = {}
KILLED: set[str] = set()  # items whose running turn the user stopped
USAGE: list[dict] = []  # account rate-limit windows, refreshed in background


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
        if it["state"] in ("running", "commented"):
            it["state"] = "needs-review" if it.get("session") else "queued"
            it["feed"].append(event("interrupted by console restart"))


def find(item_id: str) -> dict | None:
    for it in STATE["items"]:
        if it["id"] == item_id:
            return it
    return None


def event(text: str) -> dict:
    return {"kind": "event", "text": text}


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
    tf = it.setdefault("turn_files", {})
    if rel in tf:
        return
    if rel == f"programs/solvers/{it['id']}.dl":
        tf[rel] = it.get("snap", "")
    elif rel == "docs/wf-solver/proposals.md":
        tf[rel] = it.get("snap_prop", "")
    else:
        p = ROOT / rel
        tf[rel] = p.read_text() if p.exists() else ""


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
    it["hash_before"] = solver_hash(it["id"])
    it["snap"] = solver_text(it["id"])
    it["snap_prop"] = prop_text()
    it["dirty_before"] = it["dirty"]
    it["turn_files"] = {}
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
                        label = tool_label(name, inp)
                        if label:
                            entry = {"kind": "tool", "text": label}
                            key = (mid, "tool", block.get("id") or label)
                    if entry and key not in seen:
                        seen.add(key)
                        it["feed"].append(entry)
            elif kind == "result":
                got_result = True
                finish_turn(it, ev, trigger, started)
            else:
                continue
            it["ver"] = it.get("ver", 0) + 1
        bump()
    proc.wait()
    with LOCK:
        PROCS.pop(item_id, None)
        it = find(item_id)
        if it and not got_result:
            if item_id in KILLED:
                KILLED.discard(item_id)
                it["feed"].append(event("stopped"))
            else:
                tail = ""
                log = LOG_DIR / f"{item_id}.log"
                if log.exists():
                    tail = log.read_text(errors="replace")[-400:].strip()
                it["feed"].append(event(f"worker exited without result (code {proc.returncode}) — {tail}"))
            it["state"] = "needs-review" if it.get("session") else "queued"
            it["updated"] = True
            it["ver"] = it.get("ver", 0) + 1
    if first_response:
        first_response.set()
    bump()


def finish_turn(it: dict, ev: dict, trigger: str | None, started: float) -> None:
    it["rev"] = it.get("rev", 0) + 1
    text = (ev.get("result") or "").strip()
    if it["feed"] and it["feed"][-1]["kind"] == "worker" and it["feed"][-1]["text"].strip() == text:
        it["feed"][-1] = {"kind": "report", "rev": it["rev"], "text": text}
    elif text:
        it["feed"].append({"kind": "report", "rev": it["rev"], "text": text})
    cost = ev.get("total_cost_usd")
    mins = (time.time() - started) / 60
    note = f"turn done · {mins:.0f}m" if mins >= 1 else "turn done · <1m"
    if isinstance(cost, (int, float)):
        note += f" · ${cost:.2f}"
    it["feed"].append(event(note))
    if trigger == "cleanup" or it["rev"] == 1:
        it["dirty"] = False
    elif solver_hash(it["id"]) != it.get("hash_before", ""):
        it["dirty"] = True
    it["state"] = "needs-review"
    it["updated"] = True
    it["lastActive"] = int(time.time() * 1000)
    it["title"] = title_of(it["id"]) or it.get("title", "")
    it["prop_after"] = prop_text()


FIRST_RESPONSE: dict[str, threading.Event] = {}


def start_wave(k: int) -> dict:
    with LOCK:
        if any(it["state"] in ("running", "queued") for it in STATE["items"]):
            return {"error": "a wave is still launching or running"}
        STATE["items"] = [it for it in STATE["items"] if it["state"] != "committed"]
        existing = {it["id"] for it in STATE["items"]}
        out = subprocess.run(["bash", "scripts/queue.sh", "-n", str(k + len(existing))],
                             cwd=ROOT, capture_output=True, text=True)
        if out.returncode != 0:
            return {"error": "queue.sh failed: " + out.stderr.strip()[-200:]}
        picked = []
        for line in out.stdout.splitlines():
            m = re.match(r"\s*(\d+)\s+(\S+)", line)
            if m and m.group(2) not in existing:
                picked.append((m.group(2), int(m.group(1))))
        picked = picked[:k]
        if not picked:
            return {"error": "queue is empty"}
        STATE["wave"] += 1
        append = str(build_append(STATE["wave"]))
        for tid, est in picked:
            STATE["items"].append({
                "id": tid, "est": est, "wave": STATE["wave"], "state": "queued",
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
        it["state"] = "running"
        it["feed"].append(event("launched (cache seeder)"))
        launch(it, first_message(ids[0]))
    bump()
    first.wait(timeout=STAGGER_TIMEOUT)
    FIRST_RESPONSE.pop(ids[0], None)
    with LOCK:
        for tid in ids[1:]:
            it = find(tid)
            it["state"] = "running"
            it["feed"].append(event("launched"))
            launch(it, first_message(tid))
    bump()


def first_message(tid: str) -> str:
    return f"Task: {tid}. Work this solver per the cadence."


# ---------- actions ----------

def act_comment(item_id: str, text: str) -> dict:
    text = text.strip()
    if text.lower() in ("commit", "next"):
        return {"error": f"`{text}` is a console action, not a worker message"}
    with LOCK:
        it = find(item_id)
        if it is None:
            return {"error": "unknown item"}
        if item_id in PROCS:
            return {"error": "worker busy — wait for the turn to land"}
        if not it.get("session"):
            return {"error": "no session yet"}
        it["feed"].append({"kind": "you", "text": text})
        it["state"] = "commented"
        it["updated"] = False
        trigger = "cleanup" if text.lower() == "cleanup" else None
        launch(it, text, trigger)
    bump()
    return {"ok": True}


def act_approve(item_id: str) -> dict:
    with LOCK:
        it = find(item_id)
        if it is None or it["state"] != "needs-review":
            return {"error": "nothing to approve"}
        if item_id in PROCS:
            return {"error": "worker busy"}
        if it["dirty"]:
            it["feed"].append(event("auto cleanup"))
            it["feed"].append({"kind": "you", "text": "cleanup"})
            it["state"] = "commented"
            it["updated"] = False
            launch(it, "cleanup", "cleanup")
            res = {"ok": True, "cleanup": True}
        else:
            it["state"] = "approved"
            it["updated"] = False
            it["feed"].append(event("approved"))
            res = {"ok": True}
    bump()
    return res


def act_unapprove(item_id: str) -> dict:
    with LOCK:
        it = find(item_id)
        if it is None or it["state"] != "approved":
            return {"error": "not approved"}
        it["state"] = "needs-review"
        it["feed"].append(event("approval withdrawn"))
    bump()
    return {"ok": True}


def act_seen(item_id: str) -> dict:
    with LOCK:
        it = find(item_id)
        if it:
            it["updated"] = False
    bump()
    return {"ok": True}


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


def act_revert(item_id: str) -> dict:
    with LOCK:
        it = find(item_id)
        if it is None:
            return {"error": "unknown item"}
        if item_id in PROCS:
            return {"error": "worker busy"}
        snap = it.get("snap", "")
        if not snap or snap == solver_text(item_id):
            return {"error": "nothing to revert"}
        solver_path(item_id).write_text(snap)
        reverted = [f"programs/solvers/{item_id}.dl"]
        # proposals.md is shared across workers: restore only if this turn
        # changed it and nothing touched it since the turn landed
        sp, pa = it.get("snap_prop"), it.get("prop_after")
        if sp is not None and pa is not None and sp != pa and prop_text() == pa:
            (DOCS / "proposals.md").write_text(sp)
            reverted.append("docs/wf-solver/proposals.md")
        it["dirty"] = it.get("dirty_before", False)
        it["reverted"] = reverted
        it["feed"].append(event("edits reverted"))
        it["ver"] = it.get("ver", 0) + 1
    bump()
    return {"ok": True}


def act_commit() -> dict:
    with LOCK:
        ids = [it["id"] for it in STATE["items"] if it["state"] == "approved"]
        if not ids:
            return {"error": "nothing approved"}
        paths = [str(solver_path(i).relative_to(ROOT)) for i in ids]
        proposals = "docs/wf-solver/proposals.md"
        if subprocess.run(["git", "diff", "--quiet", "--", proposals],
                          cwd=ROOT).returncode != 0:
            paths.append(proposals)
        subprocess.run(["git", "add", *paths], cwd=ROOT, check=False)
        msg = ("Add " + ", ".join(sorted(ids)) +
               "\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>\n")
        out = subprocess.run(["git", "commit", "-m", msg], cwd=ROOT,
                             capture_output=True, text=True)
        if out.returncode != 0:
            return {"error": "git commit failed: " + (out.stderr or out.stdout).strip()[-200:]}
        msgs = ["Add " + ", ".join(sorted(ids))]
        lib_msg = commit_promotion()
        if lib_msg:
            msgs.append(lib_msg)
        solver_msg = commit_solvers()
        if solver_msg:
            msgs.append(solver_msg)
        msgs += commit_docs()
        for it in STATE["items"]:
            if it["id"] in ids:
                it["state"] = "committed"
                it["feed"].append(event("committed"))
                it["ver"] = it.get("ver", 0) + 1
    bump()
    return {"ok": True, "msg": " + ".join(msgs)}


def commit_promotion() -> str | None:
    """After the wave commit: lib.dl plus caller edits left in the tree are
    promotion fallout — commit them in the repo's `lib:` style. Caller holds
    LOCK."""
    chk = subprocess.run(["git", "status", "--porcelain", "--",
                          "programs/lib.dl", "programs/solvers"],
                         cwd=ROOT, capture_output=True, text=True)
    left = [l[3:] for l in chk.stdout.splitlines() if l[:2].strip() == "M"]
    if "programs/lib.dl" not in left:
        return None
    diff = subprocess.run(["git", "diff", "--", "programs/lib.dl"],
                          cwd=ROOT, capture_output=True, text=True).stdout
    names = (re.findall(r"^\+\.comp (\w+)", diff, re.M) or
             re.findall(r"^\+\s*\.decl (\w+)", diff, re.M))
    src = next((it["id"] for it in STATE["items"]
                if "programs/lib.dl" in (it.get("turn_files") or {})), None)
    msg = "lib: " + (", ".join(dict.fromkeys(names)) or "promotion")
    msg += f" promoted from {src}" if src else " promoted"
    subprocess.run(["git", "add", *left], cwd=ROOT, check=False)
    out = subprocess.run(["git", "commit", "-m", msg + TRAILER],
                         cwd=ROOT, capture_output=True, text=True)
    return msg if out.returncode == 0 else None


def commit_solvers() -> str | None:
    """Modified tracked solvers left after the promotion stage: family or
    retag fallout from a worker turn. One commit, named by the changed
    concept-header terms. Caller holds LOCK."""
    chk = subprocess.run(["git", "status", "--porcelain", "--", "programs/solvers"],
                         cwd=ROOT, capture_output=True, text=True)
    left = [l[3:] for l in chk.stdout.splitlines() if l[:2].strip() == "M"]
    if not left:
        return None
    diff = subprocess.run(["git", "diff", "--", *left], cwd=ROOT,
                          capture_output=True, text=True).stdout
    plus = list(dict.fromkeys(
        t for line in re.findall(r"^\+// (?:concept|family): (.+)$", diff, re.M)
        for t in line.split()))
    minus = list(dict.fromkeys(
        t for line in re.findall(r"^-// (?:concept|family): (.+)$", diff, re.M)
        for t in line.split()))
    added = [t for t in plus if t not in minus]
    removed = [t for t in minus if t not in plus]
    parts = ", ".join(added[:6])
    if removed:
        rem = ", ".join("-" + t for t in removed[:4])
        parts = f"{parts}; {rem}" if parts else rem
    if not parts:
        parts = f"{len(left)} updated"
    msg = f"solvers: {parts}"
    subprocess.run(["git", "add", *left], cwd=ROOT, check=False)
    out = subprocess.run(["git", "commit", "-m", msg + TRAILER],
                         cwd=ROOT, capture_output=True, text=True)
    return msg if out.returncode == 0 else None


def commit_docs() -> list[str]:
    """Worker edits to wf-solver docs (proposals.md rides the Add commit):
    one commit per file, named by the changed term names. Caller holds LOCK."""
    chk = subprocess.run(["git", "status", "--porcelain", "--", "docs/wf-solver"],
                         cwd=ROOT, capture_output=True, text=True)
    msgs = []
    for line in chk.stdout.splitlines():
        if line[:2].strip() != "M":
            continue
        rel = line[3:]
        stem = Path(rel).stem
        if stem == "proposals" or not rel.endswith(".md"):
            continue
        diff = subprocess.run(["git", "diff", "--", rel], cwd=ROOT,
                              capture_output=True, text=True).stdout
        plus = list(dict.fromkeys(re.findall(r"^\+.*?`([\w-]+)`", diff, re.M)))
        minus = [t for t in dict.fromkeys(re.findall(r"^-.*?`([\w-]+)`", diff, re.M))
                 if t not in plus]
        parts = ", ".join(plus[:6])
        if minus:
            removed = ", ".join("-" + t for t in minus[:4])
            parts = f"{parts}; {removed}" if parts else removed
        if not parts:
            added = [l[1:].strip() for l in diff.splitlines()
                     if l.startswith("+") and not l.startswith("+++") and l[1:].strip()]
            parts = added[0][:50] if added else "updates"
        msg = f"{stem}: {parts}"
        subprocess.run(["git", "add", rel], cwd=ROOT, check=False)
        out = subprocess.run(["git", "commit", "-m", msg + TRAILER],
                             cwd=ROOT, capture_output=True, text=True)
        if out.returncode == 0:
            msgs.append(msg)
    return msgs


# ---------- http ----------

def light_items() -> list[dict]:
    return [{k: it.get(k) for k in
             ("id", "state", "dirty", "updated", "session", "lastActive",
              "wave", "rev", "title", "est", "ver")} |
            {"busy": it["id"] in PROCS}
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
                tf = it.get("turn_files") or {}
                files = []
                for rel in [solver_rel] + [p for p in tf if p != solver_rel]:
                    p = ROOT / rel
                    files.append({
                        "path": rel,
                        "snap": tf.get(rel, it.get("snap", "") if rel == solver_rel else ""),
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
            res = start_wave(int(body.get("k", 6)))
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
