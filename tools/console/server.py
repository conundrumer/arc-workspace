#!/usr/bin/env python3
"""Review console for batch solver workers.

Serves the console UI, launches `claude -p` workers in waves, resumes them
with review comments, and commits approved solvers.

    uv run python tools/console/server.py [--port 8347]

Env:
    CONSOLE_FAKE=1     use fake_worker.py instead of claude (UI demo)
    CONSOLE_CLAUDE     claude binary (default: claude)
    CONSOLE_CREATE_MODEL   the chains' stronger model (default: claude-opus-5)
    CONSOLE_REFINE_MODEL   the chains' cheaper model (default: claude-fable-5)
    CONSOLE_CODEX_MODEL    model for codex-backed stages (default: gpt-5.6-sol)
    CONSOLE_CODEX_EFFORT   reasoning effort for codex-backed stages (default: high)
    CONSOLE_COMMIT_MODEL   committer model (default: claude-opus-5)
"""

import argparse
import fcntl
import functools
import hashlib
import json
import os
import queue
import random
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
APPROVED_FILE = STATE_DIR / "approved.txt"
SAMPLE_FILE = STATE_DIR / "usage-samples.jsonl"
LOG_DIR = STATE_DIR / "logs"
REPORT_DIR = STATE_DIR / "reports"
LEDGER = REPORT_DIR / "ledger.jsonl"
FLAGS_FILE = STATE_DIR / "flags.json"
SOLVERS = ROOT / "programs" / "solvers"
LIB = ROOT / "programs" / "lib.dl"
DOCS = ROOT / "docs" / "wf-solver"
TASKS = ROOT / "data" / "tasks"
REF_DIR = (ROOT.parent / "arc-synth-bun").resolve()

FAKE = os.environ.get("CONSOLE_FAKE") == "1"
CLAUDE = os.environ.get("CONSOLE_CLAUDE", "claude")
MODELS = {"create": os.environ.get("CONSOLE_CREATE_MODEL", "claude-opus-5"),
          "refine": os.environ.get("CONSOLE_REFINE_MODEL", "claude-fable-5")}
CODEX_MODEL = os.environ.get("CONSOLE_CODEX_MODEL", "gpt-5.6-sol")
CODEX_EFFORT = os.environ.get("CONSOLE_CODEX_EFFORT", "high")
COMMIT_MODEL = os.environ.get("CONSOLE_COMMIT_MODEL", "claude-opus-5")

# The user's global prompt hook checks this and stays quiet for workers.
WORKER_ENV = {**os.environ, "CLAUDE_NO_HEADLINE": "1"}

WORKER_FLAGS = [
    "--output-format", "stream-json", "--input-format", "stream-json", "--verbose",
    "--permission-mode", "acceptEdits",
    # ref_note.py hooks in to note reads of unratified solvers, and
    # includeGitInstructions drops the git status block: it is rebuilt at
    # every spawn, so a resume that follows a commit or a solver write would
    # otherwise miss the cache on everything after the static prompt.
    "--settings", str(HERE / "worker-settings.json"),
    "--allowedTools",
    "Bash(uv run:*)", "Bash(cat:*)", "Bash(ls:*)", "Bash(souffle:*)",
    # Schemas a solver session never calls, kept out of the request. ToolSearch
    # stays: without it every deferred tool loads, which costs more than the
    # rest of this list saves. Dropping a name from here adds it to
    # WORKER_TOOLS. Denying Skill also drops the skill listing, which the
    # appendix already carries; `--disable-slash-commands` saves the same
    # tokens but takes `/compact` with it.
    "--disallowedTools",
    "CronCreate", "CronDelete", "CronList", "DesignSync", "EnterWorktree",
    "ExitWorktree", "ListAgents", "Monitor", "NotebookEdit", "PushNotification",
    "RemoteTrigger", "ReportFindings", "ScheduleWakeup", "Skill", "TaskOutput",
    "WebFetch", "WebSearch", "Workflow",
    "--add-dir", str(REF_DIR),
    "--exclude-dynamic-system-prompt-sections",
    # The claude.ai connectors are unauthenticated here and cost nothing while
    # they stay deferred. This holds them out whatever the deferral does.
    "--strict-mcp-config",
]
# What those flags leave loaded. A release that adds a tool lands it in the
# worker's context, and a denylist cannot know its name, so the init event is
# checked against this set and the difference goes to the feed. Dropping a name
# from here adds it to the denylist above.
WORKER_TOOLS = {"Task", "Bash", "Edit", "Read", "SendMessage", "TaskCreate",
                "TaskGet", "TaskList", "TaskStop", "TaskUpdate", "ToolSearch",
                "Write"}
STAGGER_TIMEOUT = 120  # seconds to wait for the first worker's first API response
# A worker holds its process for as long as it sits idle. Past the prompt
# cache, that process buys nothing a resume would not: the chain gives each
# phase its own session, so a worker that has reported is only ever woken by a
# review comment.
IDLE_TTL = 3600
IDLE_POLL = 60
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
# An item runs a chain of linked sessions, one per stage: the first stage
# writes the solver and ends its pass with a handoff report, each later stage
# takes over from the stage before it. `phase` names the stage that owns the
# item; a handoff moves it one stage on, and only from a turn launched with the
# handoff flag — the wave's first turn, or a `handoff` comment that asks the
# current stage for a fresh report. A stopped or dead turn never hands off.
# Comments target any stage's session; a debug turn to a stage the item has
# already left does not hand off again.
#
# A report lands either way; who acts on it is the wave's `auto_advance`
# choice. With it on, the landing moves the item on and launches the next stage
# by itself. With it off — the default — the item lands in review still in the
# stage that reported, and the advance action moves it on when the user asks.
# Every report is also written under state/reports/, so it outlives the item a
# commit drops and can seed a later stage over a solver already committed.
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


# ---------- stage chain ----------
#
# A stage descriptor is {name, backend, model, effort?}. Names are unique
# within an item and key everything held per session: `sessions`, `lastActive`,
# `context`, `cost_seen`, `cache_read`, `seen_hash`, feed entries, report
# files, and PROCS.

BACKENDS = ("claude", "codex")
STAGE_NAME = re.compile(r"[A-Za-z0-9_-]{1,32}")


def default_chain() -> list[dict]:
    """What a wave runs when it names no chain: the first preset."""
    return [{"name": "create", "backend": "claude", "model": MODELS["create"]},
            {"name": "refine", "backend": "claude", "model": MODELS["create"]},
            {"name": "finalize", "backend": "claude", "model": MODELS["refine"]}]


def two_phase_chain() -> list[dict]:
    """The create/refine pair earlier console versions ran, which items
    written by those versions are read as."""
    return [{"name": "create", "backend": "claude", "model": MODELS["create"]},
            {"name": "refine", "backend": "claude", "model": MODELS["refine"]}]


def stage_word(st: dict) -> str:
    """The stage as its model reads in a preset label: opus, fable, codex."""
    if st.get("backend") == "codex":
        return "codex"
    m = st.get("model") or ""
    return m.removeprefix("claude-").split("-")[0] or st["name"]


def preset_label(chain: list[dict]) -> str:
    return " → ".join(stage_word(st) for st in chain)


def wave_presets() -> list[dict]:
    """The chains the console offers at wave start."""
    codex = {"name": "create", "backend": "codex", "model": CODEX_MODEL}
    if CODEX_EFFORT:
        codex["effort"] = CODEX_EFFORT
    return [
        {"id": "claude", "label": preset_label(default_chain()),
         "chain": default_chain()},
        {"id": "codex", "label": preset_label([codex] + default_chain()[1:]),
         "chain": [codex] + default_chain()[1:]},
    ]


def chain_of(it: dict) -> list[dict]:
    return it.get("chain") or two_phase_chain()


def stage_names(it: dict) -> list[str]:
    return [st["name"] for st in chain_of(it)]


def stage_of(it: dict, name: str) -> dict:
    """The named stage's descriptor, or a plain claude stage when the chain
    has no entry under that name."""
    for st in chain_of(it):
        if st.get("name") == name:
            return st
    return {"name": name, "backend": "claude", "model": MODELS.get(name)}


def next_stage(it: dict, name: str) -> dict | None:
    chain = chain_of(it)
    names = [st["name"] for st in chain]
    if name not in names:
        return None
    at = names.index(name) + 1
    return chain[at] if at < len(chain) else None


def backend_of(it: dict, name: str) -> str:
    return stage_of(it, name).get("backend") or "claude"


def model_of(it: dict, name: str) -> str:
    return stage_of(it, name).get("model") or ""


def clean_chain(raw) -> list[dict]:
    """The chain a wave request asks for, checked. Stage names key report
    files, so they are held to a filename-safe shape."""
    if raw is None:
        return default_chain()
    if not isinstance(raw, list) or not raw:
        raise Reject("chain must be a non-empty list of stages")
    out, seen = [], set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise Reject("each stage must be an object")
        name = str(entry.get("name") or "").strip()
        if not STAGE_NAME.fullmatch(name):
            raise Reject(f"bad stage name: {entry.get('name')!r}")
        if name in seen:
            raise Reject(f"duplicate stage name: {name}")
        seen.add(name)
        backend = str(entry.get("backend") or "claude").strip()
        if backend not in BACKENDS:
            raise Reject(f"unknown backend: {backend}")
        st = {"name": name, "backend": backend,
              "model": str(entry.get("model") or "").strip() or None}
        effort = str(entry.get("effort") or "").strip()
        if effort:
            st["effort"] = effort
        out.append(st)
    return out


def active(it: dict) -> bool:
    """Whether an item has a turn or handoff in flight."""
    return it.get("handoff_pending", False) or busy_elsewhere(it, None)


def busy_elsewhere(it: dict, phase: str | None) -> bool:
    """Whether a session of the item other than `phase` has a turn in flight."""
    return any(w["state"] in ("spawning", "sending", "running")
               for (item_id, p), w in PROCS.items()
               if item_id == it["id"] and p != phase)


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

def now() -> float:
    """Wall clock for the scheduling logic, in one place so a test can move it
    without waiting out a rate-limit window."""
    return time.time()


def bump() -> None:
    with COND:
        STATE["seq"] += 1
        save()
        COND.notify_all()


def save() -> None:
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(STATE, indent=1))
    tmp.replace(STATE_FILE)
    # ref_note.py reads this: the ids ratified ahead of their commit
    text = "".join(it["id"] + "\n" for it in STATE["items"]
                   if it["state"] == APPROVED)
    if not APPROVED_FILE.exists() or APPROVED_FILE.read_text() != text:
        APPROVED_FILE.write_text(text)


def load() -> None:
    if not STATE_FILE.exists():
        return
    STATE.update(json.loads(STATE_FILE.read_text()))
    for it in STATE["items"]:
        migrate(it)
        if it["state"] in ACTIVE:
            it.pop("pending_handoff", None)
            it.pop("handoff_pending", None)
            it.pop("callout_wait", None)
            say(it, event("interrupted by console restart"))
            turn_died(it, it.get("last_turn_phase") or it["phase"])


def migrate(it: dict) -> None:
    """Fold state written by earlier console versions forward. The two-phase
    names carry over as stage names, so sessions, feeds, and report files keep
    the keys they were written under."""
    if "auto_advance" not in it:
        # every version before the flag handed off on its own
        it["auto_advance"] = bool(it.pop("auto_refine", True))
    it.pop("auto_refine", None)
    if not it.get("chain"):
        it["chain"] = two_phase_chain()
        it["chain"][1]["model"] = it.get("refine_model") or MODELS["refine"]
    it.pop("refine_model", None)
    if "reports" not in it:
        text = (it.pop("handoff_report", None) or "").strip()
        it["reports"] = {"create": text} if text else {}
    it.pop("handoff_report", None)
    seed_report(it)
    if "sessions" not in it:
        old = it.pop("session", None)
        it["sessions"] = {"create": None, "refine": old}
        it["phase"] = "refine" if old else "create"
        it["lastActive"] = {"create": None, "refine": it.get("lastActive")}
        for m in it.get("feed", []):
            m.setdefault("sess", "refine")
        if isinstance(it.get("reverted"), list):
            it["reverted"] = {"files": it["reverted"], "phase": "refine"}
    if "landed" not in it:
        # a stage that reported a session has landed a turn on it
        it["landed"] = [n for n, s in it["sessions"].items() if s]
    it.pop("refined", None)
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


def file_hash(p: Path) -> str:
    return hashlib.sha1(p.read_bytes()).hexdigest() if p.exists() else ""


def watched_paths(item_id: str) -> dict[str, Path]:
    """The shared files a pass has no business editing, by repo-relative
    name: the lib, the docs, and the task's own data. Hashed at launch and
    checked at landing, so a write that bypasses the edit tools (a Bash
    heredoc, a script) still surfaces."""
    paths = {"programs/lib.dl": LIB,
             f"data/tasks/{item_id}.json": TASKS / f"{item_id}.json"}
    for p in sorted(DOCS.glob("*.md")):
        paths[f"docs/wf-solver/{p.name}"] = p
    return paths


def watched_hashes(item_id: str) -> dict[str, str]:
    return {rel: file_hash(p) for rel, p in watched_paths(item_id).items()}


def shared_writes(it: dict) -> list[str]:
    """Repo files the turn changed outside the pass's own surface — the
    solver and its scratch directory."""
    own = f"programs/solvers/{it['id']}.dl"
    watched = watched_paths(it["id"])
    hits = set()
    for rel, digest in pre(it).get("watched", {}).items():
        p = watched.get(rel)
        if p is None or file_hash(p) != digest:
            hits.add(rel)
    for rel, snap in pre(it)["files"].items():
        if rel == own or rel.startswith(".scratch/") or rel in hits:
            continue
        p = ROOT / rel
        if (p.read_text() if p.exists() else "") != snap:
            hits.add(rel)
    return sorted(hits)


def prop_text() -> str:
    p = DOCS / "proposals.md"
    return p.read_text() if p.exists() else ""


def report_path(item_id: str, stage: str) -> Path:
    return REPORT_DIR / item_id / f"{stage}.md"


def save_report(item_id: str, stage: str, text: str) -> None:
    p = report_path(item_id, stage)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def report_of(it: dict, stage: str) -> str:
    """A stage's handoff report, from state or from the file that outlives it."""
    text = ((it.get("reports") or {}).get(stage) or "").strip()
    if text:
        return text
    p = report_path(it["id"], stage)
    return p.read_text().strip() if p.exists() else ""


CALLOUT_HEAD = re.compile(r"^\s{0,3}#{1,6}\s*callouts\b.*$", re.I | re.M)
HEADING = re.compile(r"^\s{0,3}#{1,6}\s", re.M)
BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")


def parse_callouts(text: str) -> list[str]:
    """The entries of a report's `## Callouts` section.

    Written by hand at the end of a long turn, so the shape is read loosely:
    any heading level, list items when the section uses them and plain lines
    when it does not, and `none` for a stage with nothing to raise."""
    head = None
    for head in CALLOUT_HEAD.finditer(text or ""):
        pass  # a report that wrote the section twice is read on its last one
    if head is None:
        return []
    body = text[head.end():]
    nxt = HEADING.search(body)
    if nxt:
        body = body[:nxt.start()]
    bullets, lines = [], []
    for line in body.splitlines():
        if not line.strip():
            continue
        item = BULLET.match(line)
        if item:
            bullets.append(item.group(1).strip())
        else:
            lines.append(line.strip())
    return [e for e in (bullets or lines) if e.strip(" .*_`").lower() != "none"]


# tolerates emphasis around the mark: `[P1]`, `**[P1]** …`, `**[P1] …`
RANK_MARK = re.compile(r"^[*_`]{0,2}\[?[Pp]([0-3])\]?[*_`]{0,2}\s")


def callout_rank(entries: list[str]) -> int | None:
    """The most urgent P-rank among the entries, when any carries one."""
    ranks = [int(m.group(1)) for e in entries if (m := RANK_MARK.match(e))]
    return min(ranks) if ranks else None


# What a rank is worth to the triage sort. A P3 is a note the worker left, not
# a ruling it wants, so it lands in the same band as a report that raised
# nothing, where comps and the acting callouts order it.
CALLOUT_WEIGHT = {0: 0, 1: 1, 2: 2, 3: 9}
NO_CALLOUT = 9


def callout_weight(rank: int | None) -> int:
    return CALLOUT_WEIGHT.get(rank, NO_CALLOUT)


def callout_act(entries: list[str]) -> int:
    """How many entries ask the user for something. A P3 does not."""
    return sum(1 for e in entries
               if not ((m := RANK_MARK.match(e)) and m.group(1) == "3"))


def report_stages(item_id: str) -> list[str]:
    """Stages the task has a persisted report for."""
    d = REPORT_DIR / item_id
    return sorted(p.stem for p in d.glob("*.md")) if d.is_dir() else []


def task_callouts(item_id: str) -> list[str]:
    """Callouts from the task's most recent persisted report."""
    d = REPORT_DIR / item_id
    try:
        files = sorted(d.glob("*.md"), key=lambda p: p.stat().st_mtime)
        return parse_callouts(files[-1].read_text()) if files else []
    except OSError:
        return []


# ---------- provenance ledger ----------
#
# One line per stage landing, append-only. Other writers add lines of the same
# shape — a backfill pass records the passes made before the ledger existed,
# under stage `legacy` — so readers take the fields they know and skip the rest.

FABLE = "claude-fable"


def ledger_append(row: dict) -> None:
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError as exc:
        print(f"ledger append failed: {exc}", file=sys.stderr)


def ledger_rows() -> list[dict]:
    rows = []
    try:
        text = LEDGER.read_text(errors="replace")
    except OSError:
        return rows
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("task"):
            rows.append(row)
    return rows


def fabled(rows: list[dict]) -> set[str]:
    """Tasks the finalize backlog is done with: a finalize landing, a landing
    on a fable model (the shape a backfilled line carries), or the user's
    dismissal."""
    return {row["task"] for row in rows
            if row.get("stage") in ("finalize", "dismissed")
            or str(row.get("model") or "").startswith(FABLE)}


# ---------- flags ----------
#
# Triage rulings, keyed by task and held apart from the console's items: a
# flag outlives the item it was raised on, and a task with no item can carry
# one. Level 1 sorts first.

FLAGS: dict | None = None


def flags() -> dict:
    global FLAGS
    if FLAGS is None:
        FLAGS = {}
        try:
            raw = json.loads(FLAGS_FILE.read_text())
        except (OSError, ValueError):
            raw = {}
        if isinstance(raw, dict):
            for tid, entry in raw.items():
                if isinstance(entry, dict) and entry.get("level") in (1, 2, 3):
                    FLAGS[str(tid)] = {"level": entry["level"],
                                       "ts": entry.get("ts") or 0}
    return FLAGS


def save_flags() -> None:
    FLAGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = FLAGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(flags(), indent=1))
    tmp.replace(FLAGS_FILE)


def act_flag(body: dict) -> dict:
    item_id = str(body.get("id") or "").strip()
    if not item_id:
        return {"error": "no task id"}
    try:
        level = int(body.get("level", 0))
    except (TypeError, ValueError):
        level = -1
    if level not in (0, 1, 2, 3):
        return {"error": "level must be 0, 1, 2, or 3"}
    with LOCK:
        table = flags()
        if level:
            table[item_id] = {"level": level, "ts": int(now())}
        else:
            table.pop(item_id, None)
        save_flags()
    bump()
    return {"ok": True, "level": level}


def seed_report(it: dict) -> None:
    """Adopt the report files when state carries none, so an item that came
    back after a restart or a commit still knows what earlier stages found."""
    reports = it.setdefault("reports", {})
    for name in stage_names(it):
        if not (reports.get(name) or "").strip():
            text = report_of(it, name)
            if text:
                reports[name] = text


# The components style.md gives every solver. Any other one is a task-local
# staging form, legal only while its proposals.md entry is open.
STOCK_COMPS = ("Consts", "Fit", "Parse")


def comps_of(item_id: str) -> list[str]:
    """Task-local `.comp` names the solver declares."""
    return [name for name in
            re.findall(r"^\.comp\s+([A-Za-z_]\w*)", solver_text(item_id), re.M)
            if name not in STOCK_COMPS]


def unproposed(names: list[str], proposals: str) -> list[str]:
    return [n for n in names
            if not re.search(rf"\b{re.escape(n)}\b", proposals)]


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


# Worker-only, so it stays out of SKILL.md: the interactive session shares that
# body and has a scratchpad of its own. A worker has neither, and a scratch file
# it writes otherwise lands in the repo root and stays there.
SCRATCH_NOTE = """## Scratch

Files you write to answer a question about the task go in `.scratch/<task_id>/`, not the repo root. Write creates the directory, and git ignores it."""


def build_append(wave: int) -> Path:
    """The worker's system-prompt appendix: the skill body and the scratch note,
    then the docs and lib.dl, in the projection dl.context renders. Byte-identical
    for every stage, so the sessions share the longest possible prompt prefix."""
    path = STATE_DIR / f"wave-{wave:02d}-append.md"
    path.write_text(skill_body() + "\n" + SCRATCH_NOTE + "\n" + appendix(DOCS))
    return path


def wave_append(wave: int) -> str:
    """The wave's appendix, reused when it is already on disk: a worker resumes
    by reading this file again, so a rewrite would move its prompt bytes."""
    path = STATE_DIR / f"wave-{wave:02d}-append.md"
    return str(path if path.exists() else build_append(wave))


# ---------- first messages ----------
#
# Every stage opens with the same task block, so the messages share a prefix
# beyond the appendix; only the tail after it diverges.

# After a report lands, the stage gets one more turn for the callouts, so
# ranking them is its own task instead of the tail of a long pass. The rates
# feed the brief as ranking signal; recalibrate by re-measuring engagement
# over newer transcripts and editing the table.
CALLOUT_RATES = [
    ("lib staging and task-local comps", 75),
    ("doc gaps", 58),
    ("simplification", 54),
    ("naming and vocabulary", 52),
    ("correctness risk", 50),
    ("lint and tooling", 39),
    ("alt models", 36),
    ("unwitnessed edges", 23),
    ("hedges", 16),
]

CALLOUT_BRIEF = """Your report is in. Now step back from the pass and write the callouts: entries deserving the user's attention — judgment calls you could not settle, calls you made that only the user can ratify, and anything else they should see.

Rank each entry P1-P3 by how likely the user is to engage it. Engagement rates by kind, as signal, not verdict: {rates}.

P0 stands apart from that scale: use it only for a clear mechanical problem with the tooling — the runner, the linter, or the audit crashing, giving a wrong result, or lacking something the cadence needed. A P0 jumps the triage queue, so a judgment call never carries it.

Reply with only a `## Callouts` section: a numbered list, each entry one or two lines opening with its `[P1]`-`[P3]` mark. With nothing to raise, the section is the single word `none`, which is what most solvers get."""


def callout_brief() -> str:
    rates = " · ".join(f"{kind} {pct}%" for kind, pct in CALLOUT_RATES)
    return CALLOUT_BRIEF.format(rates=rates)


CREATE_BRIEF = """You are the first session of a chained flow: you create the solver, then a separate session takes over from your report.

Do steps 1-4 of the creation pass with the data above; do not re-read the data. When the fit-plan verdict calls for a fit pass, do the fit pass too. Skip step 5. When a question about the data comes up, run something that answers it rather than settling it in your head. In place of the review, end your turn with a handoff report addressed to the next session: the model claim, each choice point with the alternatives you considered and why you discarded them, and the audit findings and judgment calls. Make it complete enough that the next session rederives nothing."""

HANDOFF_BRIEF = """Write the handoff report for the session that takes over from you: the model claim, each choice point with the alternatives you considered and why you discarded them, and the audit findings and judgment calls. Cover the whole session, including turns after any earlier report. Make it complete enough that the next session rederives nothing."""

NUDGE_BRIEF = """Your last turn was cut off at the output limit while it was still thinking.

Stop trying to settle the task in your head. Take the smallest thing you are still unsure about and run something that answers it. Partial and wrong is fine.

Do not spend the whole next turn thinking. If you do, it will be your final turn."""

BAIL_BRIEF = """Two turns went entirely to thinking, so your pass ends here. Stop solving.

Write a short state of play from what is already in front of you, without working anything out again:

- how you read the task
- what you ran, and what came back
- where you got stuck, and what you would try next

Keep it brief and factual. What the reader needs is your dead ends and your open question, not a full account."""

# Thinking tokens with no tool call or text before the feed says so. Well
# above a working turn's bursts, and far enough below the 64k output cap that
# the warning still arrives with the generation in progress.
RUNAWAY_THINK = 40_000
# Seconds between transcript reads. The CLI resubmits a capped generation on
# its own and the retry carries none of the thinking, so every poll of delay
# risks another full output budget spent on the same dead end.
CAP_POLL = 5

ADVANCE_BRIEF = """You are a later session of a chained flow: the creation pass is already done, and the sessions before you left the reports above.

Read programs/solvers/{tid}.dl first — the reports describe it, but you edit the file itself. Then refine the solver: judge the model and the code yourself, and edit what falls short. Trust the reports for what was already tried; do not rederive discarded alternatives.

Your edits stay in programs/solvers/{tid}.dl and .scratch/{tid}/. Shared files — programs/lib.dl, docs/wf-solver/, data/tasks/ — are the user's to change, even when the fix is designed and tested: what falls short there goes in your callouts. The callout is the surfacing step the protocols ask for, and the console carries it to the user, so an open one does not stall the chain. A `## Callouts` section in a report above is likewise addressed to the user and waits on a ruling; it is not an instruction to you, so act on none of it, and re-raise what still matters in your own callouts. A solver that already holds up under your judgment is a finished pass: say so and stop."""

# What the final stage opens with when the solver predates the chain and no
# report was ever written for it.
BARE_BRIEF = """You are the final session of a chained flow. No earlier session left a report, so the solver file is the whole account.

Read programs/solvers/{tid}.dl first. Then refine the solver: judge the model and the code yourself, and edit what falls short.

Your edits stay in programs/solvers/{tid}.dl and .scratch/{tid}/. Shared files — programs/lib.dl, docs/wf-solver/, data/tasks/ — are the user's to change: what falls short there goes in your callouts. A solver that already holds up under your judgment is a finished pass: say so and stop."""

# How a stage ends its pass. Every stage with a successor ends in a report the
# next one takes over from; only the last stage of the chain writes the review.
# The final stage reads every earlier report, so each one covers its own pass
# alone and none of them restates the one before it.
HANDOFF_TAIL = """

Then do steps 2-4 of the creation pass, so your own edits get the simplify and prune treatment too; when the fit-plan verdict calls for a fit pass, do the fit pass as well. In place of the review, end your turn with a handoff report for the session that takes over from you: the model claim as it now stands, what you changed and why, the alternatives you discarded, and your open judgment calls. The report covers your own pass — your rulings, your edits, your changes; what the reports above already establish stays with them."""

REVIEW_TAIL = """

Then do steps 2-5 of the creation pass, so your own edits get the simplify and prune treatment too; when the fit-plan verdict calls for a fit pass, do the fit pass as well. You are the last session of the chain, so the review at step 5 ends your turn, addressed to the user."""


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


def reports_block(pairs: list[tuple[str, str]]) -> str:
    return "\n\n".join(f"## handoff report from the {name} session\n\n{text}"
                       for name, text in pairs)


def prior_reports(it: dict, upto: str) -> list[tuple[str, str]]:
    """Each stage's report through `upto`, in chain order."""
    names = stage_names(it)
    at = names.index(upto) + 1 if upto in names else len(names)
    return [(name, text) for name in names[:at] if (text := report_of(it, name))]


def persisted_reports(item_id: str, skip: str = "") -> list[tuple[str, str]]:
    """The report files a task left behind, in chain order. A file whose stage
    the chain does not name follows the ones it does, so none is dropped."""
    order = [st["name"] for st in default_chain()]
    stems = [s for s in report_stages(item_id) if s != skip]
    names = ([n for n in order if n in stems]
             + [n for n in stems if n not in order])
    pairs = []
    for name in names:
        text = report_path(item_id, name).read_text().strip()
        if text:
            pairs.append((name, text))
    return pairs


def advance_message(it: dict, prev: str, more: bool) -> str:
    # A stage that hands on again takes over from the report before it. The
    # final stage judges the whole chain, so it reads every earlier report.
    pairs = (prior_reports(it, prev) if not more
             else [(prev, report_of(it, prev))])
    pairs = [(name, text) for name, text in pairs if text]
    body = (reports_block(pairs) if pairs else
            f"## handoff report from the {prev} session\n\n"
            f"(the {prev} session left no report)")
    return (task_block(it["id"]) + "\n\n" + body
            + "\n\n" + ADVANCE_BRIEF.format(tid=it["id"])
            + (HANDOFF_TAIL if more else REVIEW_TAIL))


def finalize_message(item_id: str, pairs: list[tuple[str, str]]) -> str:
    """The first message of a finalize pass started over a committed solver."""
    if not pairs:
        return (task_block(item_id) + "\n\n"
                + BARE_BRIEF.format(tid=item_id) + REVIEW_TAIL)
    return (task_block(item_id) + "\n\n" + reports_block(pairs) + "\n\n"
            + ADVANCE_BRIEF.format(tid=item_id) + REVIEW_TAIL)


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
            if not it or phase not in stage_names(it) or \
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
            PROCS[(item_id, phase)] = worker
            start_worker_threads(worker)
        except (KeyError, TypeError, ValueError, OSError) as exc:
            print(f"worker handoff rejected: {exc}", file=sys.stderr)
            if isinstance(entry, dict):
                it = find(entry.get("item"))
                phase = entry.get("phase")
                if it is not None and phase in stage_names(it):
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
    if RELOADING and not admitted:
        raise Reject("server reload in progress — wait for it to finish")
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
    if not busy_elsewhere(it, phase):
        # a side turn leaves the snapshot with the turn that owns the solver
        it["pre"] = {"hash": solver_hash(it["id"]), "solver": solver_text(it["id"]),
                     "proposals": prop_text(), "dirty": it["dirty"], "files": {},
                     "watched": watched_hashes(it["id"]), "slash": slash}
    worker["turn_seq"] += 1
    worker.update(state="sending", started=time.time(), trigger=trigger,
                  handoff=handoff, seen=set(), got_result=False, think_run=0,
                  reqs={}, idle_since=None)
    worker["outbound"].put_nowait({"type": "user",
        "message": {"role": "user", "content": message}})


def worker_cmd(it: dict, phase: str) -> list[str]:
    if FAKE:
        return [sys.executable, str(HERE / "fake_worker.py"), it["id"], phase]
    st = stage_of(it, phase)
    session = it["sessions"].get(phase)
    if (st.get("backend") or "claude") == "codex":
        # The adapter reads the appendix itself; codex exec has no
        # system-prompt append, and WORKER_FLAGS has no codex equivalent.
        cmd = [sys.executable, str(HERE / "codex_worker.py"),
               "--append", str(it["append"]), "--add-dir", str(REF_DIR)]
        if st.get("model"):
            cmd += ["--model", st["model"]]
        if st.get("effort"):
            cmd += ["--effort", st["effort"]]
        if session:
            cmd += ["--resume", session]
        return cmd
    cmd = [CLAUDE, "--append-system-prompt", Path(it["append"]).read_text(),
           *WORKER_FLAGS]
    if st.get("model"):
        cmd += ["--model", st["model"]]
    if session:
        cmd += ["--resume", session]
    return cmd


def spawn_worker(it: dict, phase: str) -> dict:
    item_id = it["id"]
    cmd = worker_cmd(it, phase)
    log = open(LOG_DIR / f"{item_id}.log", "ab")
    proc = subprocess.Popen(cmd, cwd=ROOT,
                            env={**WORKER_ENV, "CONSOLE_TASK": item_id},
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
    PROCS[(item_id, phase)] = worker
    start_worker_threads(worker)
    worker.update(state="idle", idle_since=time.time())
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
            if quota_death(text=tail):
                quota_cut(it, phase, bool(worker.get("handoff")))
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
                extra = sorted(set(ev.get("tools") or ()) - WORKER_TOOLS)
                if extra:
                    say(it, event("\u26a0 tools outside the worker set — "
                                  + ", ".join(extra)), sess=phase)
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
                                                or model_of(it, phase),
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
                        if quota_death(ev.get("api_error_status"), reason,
                                       str(ev.get("result") or "")):
                            quota_cut(it, phase, handoff)
            finally:
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
                if PROCS.get((item_id, phase)) is worker:
                    PROCS.pop((item_id, phase))
                    worker["state"] = "dying"
                    worker["outbound"].put_nowait(STOP)
                DEFERRED.put_nowait(("revive", worker, escalate, handoff))
                ensure_drain()


def turn_died(it: dict, phase: str) -> None:
    """End-of-turn fallback when no result landed. A turn that died before
    reporting a session puts the item back on the nearest earlier stage that
    has one, where `handoff` can retry."""
    if not it["sessions"].get(phase):
        names = stage_names(it)
        at = names.index(phase) if phase in names else 0
        for name in reversed(names[:at]):
            if it["sessions"].get(name):
                it["phase"] = name
                break
    it["state"] = NEEDS_REVIEW if it["sessions"].get(it["phase"]) else QUEUED
    it["updated"] = True
    it["landed_at"] = now()


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


def revive(worker: dict, step: str, handoff: bool) -> None:
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
        escalate_turn(it, phase, step, handoff)
    bump()


def escalate_turn(it: dict, phase: str, step: str, handoff: bool) -> None:
    """Relaunch after a runaway interrupt lands. Caller holds LOCK and has
    reset the worker. The nudge keeps the turn's own handoff flag. A bail on a
    non-final stage asks for the report whose landing hands off; the final
    stage has no stronger session to receive it, so the item lands for review.
    A bail that itself runs away has said its piece twice, so the item lands
    either way."""
    count = it.get("runaway", {}).get(phase, 0)
    if step == "nudge":
        launch(it, NUDGE_BRIEF, phase, trigger="nudge", handoff=handoff,
               admitted=True, escalated=True)
    elif next_stage(it, phase) and count <= 2:
        launch(it, BAIL_BRIEF, phase, trigger="bail", handoff=True,
               admitted=True, escalated=True)
    else:
        turn_died(it, phase)


def auto_advances(it: dict, phase: str) -> bool:
    """Whether a report landing at `phase` hands the item on by itself.

    `auto_stop` names a stage auto-advance will not launch, so a run can carry
    items through the cheap stages and stop before an expensive one. Without
    it, auto-advance runs the whole chain."""
    if not it.get("auto_advance"):
        return False
    nxt = next_stage(it, phase)
    return bool(nxt) and nxt["name"] != it.get("auto_stop")


def advance_stage(it: dict) -> None:
    """Move the item on to the next stage and enqueue its first turn."""
    nxt = next_stage(it, it["phase"])
    if nxt is None:
        return
    if RELOADING:
        it["state"] = NEEDS_REVIEW
        it["updated"] = True
        say(it, event("handoff paused for server reload"))
        return
    prev, it["phase"] = it["phase"], nxt["name"]
    it["state"] = RUNNING
    say(it, event(f"handoff — {nxt['name']} session starting"))
    # A stage with a successor opens its pass under the handoff flag, so its
    # landing hands the chain on the way the first stage's does.
    more = next_stage(it, nxt["name"]) is not None
    launch(it, advance_message(it, prev, more), nxt["name"], handoff=more)


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
        note += think_note(lost, model_of(it, phase))
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
    # A turn with no Callouts section says nothing about them, so the item
    # keeps what the last report that carried one left.
    if text and CALLOUT_HEAD.search(text):
        it["callouts"] = parse_callouts(text)
        it["callout_n"] = len(it["callouts"])
        it["callout_rank"] = callout_rank(it["callouts"])
    ledger_append({"task": it["id"], "stage": phase,
                   "backend": backend_of(it, phase), "model": model_of(it, phase),
                   "session": it["sessions"].get(phase), "ts": int(now()),
                   "source": "console"})
    # the create pass ends in prune, and every later pass is itself a quality
    # pass, so each stage's first landing is clean by cadence
    landed = it.setdefault("landed", [])
    first_landing = phase not in landed
    if first_landing:
        landed.append(phase)
    if trigger in CLEAN_TRIGGERS or first_landing:
        it["dirty"] = False
    elif solver_hash(it["id"]) != pre(it)["hash"]:
        it["dirty"] = True
    if not pre(it).get("slash"):
        it.setdefault("seen_hash", {})[phase] = solver_hash(it["id"])
    it["lastActive"][phase] = int(time.time() * 1000)
    it["title"] = title_of(it["id"]) or it.get("title", "")
    it["prop_after"] = prop_text()
    it["comps"] = comps_of(it["id"])
    it["comps_unproposed"] = unproposed(it["comps"], it["prop_after"])
    it["landed_at"] = now()
    fresh = [rel for rel in shared_writes(it)
             if rel not in it.setdefault("shared_writes", [])]
    if fresh:
        it["shared_writes"].extend(fresh)
        say(it, event("shared files changed: " + ", ".join(fresh)), sess=phase)
    it.pop("quota_retry", None)  # the stage got a turn through; retries reset
    callout_landing = it.get("callout_wait") == phase
    if callout_landing:
        it.pop("callout_wait", None)
    if callout_landing and next_stage(it, phase):
        # the callout turn's text joins the stage report, so parsing and the
        # finalize read see one document per stage
        if text:
            combined = ((it.get("reports", {}).get(phase) or "").rstrip()
                        + "\n\n" + text)
            it.setdefault("reports", {})[phase] = combined
            save_report(it["id"], phase, combined)
        if auto_advances(it, phase):
            it["handoff_pending"] = True
            worker = PROCS.get((it["id"], phase))
            if worker:
                DEFERRED.put_nowait(("handoff", it["id"], phase, worker["turn_seq"]))
                ensure_drain()
        else:
            it["state"] = NEEDS_REVIEW
            it["updated"] = True
    elif handoff and next_stage(it, phase):
        it.setdefault("reports", {})[phase] = text
        save_report(it["id"], phase, text)
        # the callouts get their own turn before any advance
        worker = PROCS.get((it["id"], phase))
        if worker:
            it["callout_wait"] = phase
            DEFERRED.put_nowait(("callout", it["id"], phase, worker["turn_seq"]))
            ensure_drain()
        else:
            it["state"] = NEEDS_REVIEW
            it["updated"] = True
    elif not pre(it).get("slash") and not busy_elsewhere(it, phase):
        # a side turn landing while another session runs leaves the state to
        # the pass that owns it
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
            kind, item_id, phase, turn_seq = job
            with LOCK:
                it = find(item_id)
                worker = PROCS.get((item_id, phase))
                if kind == "callout":
                    if not it or it.get("callout_wait") != phase:
                        continue
                    if not worker or worker["turn_seq"] != turn_seq or RELOADING:
                        # the report stands without callouts
                        it.pop("callout_wait", None)
                        it["state"] = NEEDS_REVIEW
                        it["updated"] = True
                        if RELOADING:
                            say(it, event("callouts paused for server reload"),
                                sess=phase)
                    else:
                        it["state"] = RUNNING
                        say(it, event("callout turn starting"), sess=phase)
                        launch(it, callout_brief(), phase, trigger="callout")
                elif not it or not it.get("handoff_pending") or not worker or \
                        worker["turn_seq"] != turn_seq:
                    if it:
                        it.pop("handoff_pending", None)
                    continue
                else:
                    it.pop("handoff_pending", None)
                    advance_stage(it)
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


def reap_idle() -> None:
    """Drop workers that have sat idle past IDLE_TTL. The item keeps its
    session id, so a later comment resumes the phase from the transcript.
    An item with a deferred job queued keeps its worker: drain_deferred
    skips the callout turn and the stage advance when the worker is gone."""
    now = time.time()
    reaped = 0
    with LOCK:
        for key, worker in list(PROCS.items()):
            since = worker.get("idle_since")
            if worker["state"] != "idle" or since is None or \
                    now - since < IDLE_TTL or PROCS.get(key) is not worker:
                continue
            it = find(key[0])
            if it is None or it.get("callout_wait") or it.get("handoff_pending"):
                continue
            PROCS.pop(key)
            worker["state"] = "dying"
            worker["outbound"].put_nowait(STOP)
            say(it, event(f"{key[1]} worker reaped after "
                          f"{int((now - since) // 60)}m idle"), sess=key[1])
            queue_reap(worker)
            reaped += 1
    if reaped:
        bump()


def idle_loop() -> None:
    while True:
        time.sleep(IDLE_POLL)
        if SHUTTING_DOWN or RELOADING:
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


def drop_committed() -> None:
    """Forget the committed items of the round before, with their workers."""
    for old in [it for it in STATE["items"] if it["state"] == COMMITTED]:
        for worker in detach_workers(old["id"]):
            queue_reap(worker)
    STATE["items"] = [it for it in STATE["items"] if it["state"] != COMMITTED]


def pick_new(k: int, order: str) -> list[tuple[str, int]]:
    """The next k queue tasks the console does not already hold."""
    existing = {it["id"] for it in STATE["items"]}
    return [p for p in queue_pick(k + len(existing), order)
            if p[0] not in existing][:k]


def make_items(picked: list[tuple[str, int]], chain: list[dict], wave: int,
               append: str, auto_advance: bool = False,
               auto_stop: str | None = None) -> list[str]:
    """Append picked tasks as items of `wave`. Caller holds LOCK."""
    names = [st["name"] for st in chain]
    for tid, est in picked:
        it = {
            "id": tid, "est": est, "wave": wave, "state": QUEUED,
            "chain": [dict(st) for st in chain],
            "auto_advance": bool(auto_advance),
            "sessions": dict.fromkeys(names), "phase": names[0],
            "landed": [], "dirty": False, "updated": False, "rev": 0,
            "lastActive": dict.fromkeys(names),
            "title": "", "feed": [], "append": append, "ver": 0,
            "reports": {},
        }
        if auto_stop:
            it["auto_stop"] = auto_stop
        seed_report(it)
        STATE["items"].append(it)
    return [tid for tid, _ in picked]


def start_wave(k: int, order: str = "name", auto_advance: bool = False,
               chain: list | None = None, auto_stop: str | None = None) -> dict:
    global LAST_WAVE_AT
    with LOCK:
        if RELOADING:
            return {"error": "server reload in progress — wait for it to finish"}
        if time.time() - LAST_WAVE_AT < WAVE_DEBOUNCE:
            return {"error": "a wave just started — wait a moment to start another"}
        if order not in ("name", "size"):
            return {"error": f"unknown order: {order}"}
        try:
            chain = clean_chain(chain)
        except Reject as e:
            return {"error": str(e)}
        if auto_stop and auto_stop not in [st["name"] for st in chain[1:]]:
            return {"error": f"auto_stop names no later stage: {auto_stop}"}
        auto_advance = auto_advance or bool(auto_stop)
        drop_committed()
        try:
            picked = pick_new(k, order)
        except Reject as e:
            return {"error": str(e)}
        if not picked:
            return {"error": "queue is empty"}
        LAST_WAVE_AT = time.time()
        STATE["wave"] += 1
        ids = make_items(picked, chain, STATE["wave"],
                         str(build_append(STATE["wave"])), auto_advance,
                         auto_stop)
    bump()
    threading.Thread(target=stagger_launch, args=(ids,), daemon=True).start()
    return {"ok": True, "ids": ids}


def stagger_launch(ids: list[str]) -> None:
    """Launch one claude-backed worker alone so it writes the shared
    prompt-cache prefix, then fan the rest out once its first API response
    arrives. A codex-backed first stage draws on no such cache, so it neither
    seeds nor waits — a wave of them launches together."""
    first = threading.Event()
    seed, seeded = None, False
    with LOCK:
        for tid in ids:
            it = find(tid)
            if it is not None and backend_of(it, it["phase"]) == "claude":
                seed = tid
                break
        if seed is not None:
            it = find(seed)
            if it["state"] == QUEUED and not active(it):
                FIRST_RESPONSE[seed] = first
                it["state"] = RUNNING
                say(it, event("launched (cache seeder)"))
                launch(it, create_message(seed), it["phase"], handoff=True,
                       admitted=True)
                seeded = True
    bump()
    if seeded:
        first.wait(timeout=STAGGER_TIMEOUT)
        with LOCK:
            if FIRST_RESPONSE.get(seed) is first:
                FIRST_RESPONSE.pop(seed, None)
    with LOCK:
        for tid in ids:
            if seeded and tid == seed:
                continue
            it = find(tid)
            if it is None or it["state"] != QUEUED or active(it):
                continue
            it["state"] = RUNNING
            say(it, event("launched"))
            launch(it, create_message(tid), it["phase"], handoff=True,
                   admitted=True)
    bump()


def resume_queued_wave() -> None:
    """Give persisted admissions an owner after an exec or failed reload."""
    with LOCK:
        ids = [it["id"] for it in STATE["items"] if it["state"] == QUEUED and
               not any(item_id == it["id"] for item_id, _ in PROCS)]
    if ids:
        threading.Thread(target=stagger_launch, args=(ids,), daemon=True).start()


# ---------- overnight mode ----------
#
# The console running the queue unattended. An admitter keeps a target number
# of items in flight, a pacer decides whether the account can afford to start
# another one, and a turn the account's quota killed is resumed once the window
# resets. Nothing is approved and nothing is committed without the user: the
# night's items land in review and wait for morning.

NIGHT_DEFAULTS = {
    "on": False,
    "target": 6,       # items in flight the admitter keeps
    "reserve": 10,     # points of weekly quota held back from the pace line
    "floor": 5,        # weekly points spendable however early in the week
    "ceiling": 75,     # 5h utilization above which new admissions hold
    "catchup": True,   # spend the slack the week has accumulated
}
# Dial name -> the range the UI may set it to.
NIGHT_DIALS = {"target": (1, 40), "reserve": (0, 100), "floor": (0, 100),
               "ceiling": (0, 100)}
ADMIT_POLL = 30        # seconds between admitter passes
NIGHT_LOG = 40         # night log entries kept
LIVE = (QUEUED, RUNNING, COMMENTED)   # states with work still to come
NIGHT_WAKE = threading.Event()

# The last hour before the 5h window resets, where the ceiling stops applying.
# It matches the prompt-cache TTL: a turn that exhausts quota this close to the
# reset resumes just after it with its cache still warm, so the retry costs
# little. The same overrun earlier in the window strands a cold context, and
# rebuilding it is what the ceiling exists to avoid.
SQUEEZE = 3600
# Spread the resumes of a fleet that all died on the same limit.
RESUME_JITTER = (30, 210)
RESUME_FALLBACK = 15 * 60   # when no 5h reset time is known
RESUME_BRIEF = ("your previous turn was cut off by a usage limit; continue "
                "from where you stopped")

# A turn cut short by an exhausted account. The result event's
# `api_error_status` carries the HTTP status of an API failure, and 429 is the
# account out of quota; every other ending reads null. The CLI has no
# terminal_reason of its own for the case — a usage limit arrives as a plain
# api_error — so a worker that died before reporting one is judged on the
# wording its log tail left behind instead.
QUOTA_STATUS = "429"
QUOTA_REASONS = ("rate_limit", "usage_limit", "usage_limit_reached")
QUOTA_TEXT = re.compile(r"usage limit|rate[ _-]?limit|too many requests|quota",
                        re.I)


def quota_death(status=None, reason: str | None = None, text: str = "") -> bool:
    """Whether a turn ended because the account ran out of quota."""
    if status is not None and str(status) == QUOTA_STATUS:
        return True
    if (reason or "").lower() in QUOTA_REASONS:
        return True
    return bool(text and QUOTA_TEXT.search(text))


def night() -> dict:
    """The mode's config and running notes, filled in with the defaults."""
    cfg = STATE.setdefault("overnight", {})
    for name, value in NIGHT_DEFAULTS.items():
        cfg.setdefault(name, value)
    cfg.setdefault("log", [])
    return cfg


def night_say(text: str, once: bool = False) -> bool:
    """Add a line to the night log. `once` drops a repeat of the line already
    at the end, so a hold that outlives many passes is recorded once."""
    log = night()["log"]
    if once and log and log[-1]["text"] == text:
        return False
    log.append({"t": int(now()), "text": text})
    del log[:-NIGHT_LOG]
    return True


def clock(at: float) -> str:
    return time.strftime("%H:%M", time.localtime(at))


def window(label: str) -> dict | None:
    return next((u for u in USAGE if u.get("label") == label), None)


def elapsed_pct(u: dict | None, at: float) -> float | None:
    """How far through its window a rate limit is, in percent."""
    if not u or not u.get("reset") or not u.get("window"):
        return None
    return max(0.0, min(100.0, 100 * (1 - (u["reset"] - at) / u["window"])))


def pacer(at: float | None = None) -> dict:
    """Whether the admitter may start another item, and what to say about it.

    Only new admissions are gated. A turn already in flight, a review comment,
    and every manual action run whatever the windows read.
    """
    at = now() if at is None else at
    cfg = night()
    wk, five = window("wk"), window("5h")
    out = {"open": False, "why": "", "next": None, "wk": None, "line": None,
           "fiveh": None, "ceiling": cfg["ceiling"], "squeeze": False,
           "squeezeAt": None}
    wk_elapsed = elapsed_pct(wk, at)
    if wk is None or wk_elapsed is None:
        out["why"] = "no weekly usage reading yet"
        return out
    # The floor keeps the first hours of a week spendable: elapsed% starts at
    # zero there, and the pace line alone would hold every admission until the
    # week had caught up with the reserve.
    line = max(cfg["floor"], wk_elapsed - cfg["reserve"])
    out.update(wk=wk["pct"], line=line, elapsed=wk_elapsed)
    if five and five.get("reset"):
        out["squeezeAt"] = five["reset"] - SQUEEZE
        out["squeeze"] = at >= out["squeezeAt"]
        out["fiveh"] = five["pct"]
    if wk["pct"] > line:
        out["why"] = f"wk at pace ({wk['pct']:.0f}% vs {line:.0f}%)"
        return out
    if not cfg["catchup"]:
        # Strict pace: spend no faster than the window elapses, measured from
        # the moment the mode came on. A window that rolled over under us reads
        # as a drop in utilization, and starts the measurement again.
        start, since = cfg.get("wk_start"), cfg.get("wk_start_at")
        if start is None or since is None or wk["pct"] < start:
            cfg["wk_start"], cfg["wk_start_at"] = wk["pct"], at
        else:
            points = 100 * (at - since) / wk["window"]
            if wk["pct"] - start > points:
                out["why"] = (f"wk above strict pace (+{wk['pct'] - start:.1f} "
                              f"vs +{points:.1f} since mode start)")
                return out
    # No reset time means the 5h window is not running — nothing to hold for.
    if out["squeezeAt"] and five["pct"] > cfg["ceiling"] and not out["squeeze"]:
        out["next"] = out["squeezeAt"]
        out["why"] = (f"5h above ceiling ({five['pct']:.0f}% > "
                      f"{cfg['ceiling']}%), squeeze zone opens at "
                      f"{clock(out['squeezeAt'])}")
        return out
    out["open"] = True
    out["why"] = "squeeze zone — reset is close" if out["squeeze"] else "at pace"
    return out


def live_items() -> list[dict]:
    """Items the night still has work coming for. A scheduled quota-death
    resume holds its slot, so the admitter does not fill the night past its
    target ahead of one."""
    return [it for it in STATE["items"]
            if it["state"] in LIVE or it.get("resume_at")]


def night_landed() -> int:
    """Items that landed unreviewed since the mode came on."""
    since = night().get("since") or 0
    return sum(1 for it in STATE["items"] if it["state"] == NEEDS_REVIEW
               and (it.get("landed_at") or 0) >= since)


def quota_cut(it: dict, phase: str, handoff: bool) -> None:
    """A turn died with the account out of quota. In overnight mode the item
    gets one automatic resume just after the 5h window resets; a second death
    on the same stage leaves it for review. Caller holds LOCK."""
    say(it, event("usage limit — turn cut short"), sess=phase)
    cfg = night()
    if not cfg["on"]:
        return
    if it.get("quota_retry"):
        say(it, event("second usage limit — left for review"), sess=phase)
        night_say(f"{it['id']} · second usage limit, left for review")
        return
    five = window("5h")
    reset = (five or {}).get("reset")
    at = reset if reset and reset > now() else now() + RESUME_FALLBACK
    at += random.uniform(*RESUME_JITTER)
    it.update(quota_retry=phase, resume_at=at, resume_phase=phase,
              resume_handoff=bool(handoff))
    say(it, event(f"resume scheduled for {clock(at)}"), sess=phase)
    night_say(f"{it['id']} · usage limit in {phase}, resume at {clock(at)}")


def due_resumes() -> list[dict]:
    at = now()
    return [it for it in STATE["items"]
            if it.get("resume_at") and it["resume_at"] <= at and not active(it)]


def resume_item(it: dict) -> None:
    """Relaunch the stage a usage limit cut off, as a comment would. Caller
    holds LOCK."""
    phase = it.pop("resume_phase", None) or it["phase"]
    handoff = bool(it.pop("resume_handoff", False))
    it.pop("resume_at", None)
    if not it["sessions"].get(phase):
        say(it, event("no session to resume — left for review"), sess=phase)
        night_say(f"{it['id']} · no session to resume, left for review")
        return
    it["state"] = COMMENTED
    it["updated"] = False
    say(it, {"kind": "you", "text": RESUME_BRIEF}, sess=phase)
    night_say(f"{it['id']} · resuming {phase} after the reset")
    launch(it, RESUME_BRIEF, phase, trigger="resume", handoff=handoff,
           admitted=True)


def night_admit() -> list[str]:
    """Admit the next queued task into the night's wave. Caller holds LOCK.

    Every admission of one night belongs to one wave, so the stages share a
    system-prompt appendix and the committed items of the round before are
    cleared out the way a hand-started wave clears them."""
    cfg = night()
    drop_committed()
    try:
        picked = pick_new(1, "name")
    except Reject as e:
        night_say(f"admission deferred — {e}", once=True)
        return []
    if not picked:
        night_say("queue is empty — nothing left to admit", once=True)
        return []
    chain = wave_presets()[0]["chain"]
    if not cfg.get("wave"):
        STATE["wave"] += 1
        cfg["wave"] = STATE["wave"]
        cfg["append"] = str(build_append(STATE["wave"]))
    ids = make_items(picked, chain, cfg["wave"], cfg["append"],
                     auto_advance=True, auto_stop=chain[-1]["name"])
    night_say("admitted " + ", ".join(ids) +
              f" · {len(live_items())}/{cfg['target']} live")
    return ids


def night_tick() -> dict:
    """One admitter pass: the resumes that came due, then one admission if a
    slot is free and the pacer allows it."""
    out = {"resumed": [], "admitted": [], "held": None}
    changed = False
    with LOCK:
        cfg = night()
        if not cfg["on"] or RELOADING or SHUTTING_DOWN:
            return out
        for it in due_resumes():
            resume_item(it)
            out["resumed"].append(it["id"])
            changed = True
        if len(live_items()) < cfg["target"]:
            gate = pacer()
            if gate["open"]:
                out["admitted"] = night_admit()
                changed = changed or bool(out["admitted"])
            else:
                out["held"] = gate["why"]
                changed |= night_say("pacer holding: " + gate["why"], once=True)
    if out["admitted"]:
        threading.Thread(target=stagger_launch, args=(out["admitted"],),
                         daemon=True).start()
    if changed:
        bump()
    return out


def night_loop() -> None:
    while True:
        NIGHT_WAKE.wait(ADMIT_POLL)
        NIGHT_WAKE.clear()
        try:
            night_tick()
        except Exception as exc:  # a failed pass must not end the night
            print(f"overnight pass failed: {exc!r}", file=sys.stderr)


def night_view() -> dict:
    """What the console shows for the mode."""
    cfg = night()
    view = {name: cfg[name] for name in NIGHT_DEFAULTS}
    gate = pacer() if cfg["on"] else None
    soon = [(it["resume_at"], f"{it['id']} resumes") for it in STATE["items"]
            if it.get("resume_at")]
    if gate and gate.get("next"):
        soon.append((gate["next"], "squeeze zone opens"))
    if cfg["on"] and not soon:
        soon.append((now() + ADMIT_POLL, "admitter pass"))
    at, what = min(soon) if soon else (None, "")
    view.update(gate=gate, live=len(live_items()), landed=night_landed(),
                log=cfg["log"][-8:],
                next=({"at": at, "what": what} if at else None))
    return view


def act_night(body: dict) -> dict:
    with LOCK:
        cfg = night()
        for name, (lo, hi) in NIGHT_DIALS.items():
            if name not in body:
                continue
            try:
                cfg[name] = max(lo, min(hi, int(body[name])))
            except (TypeError, ValueError):
                return {"error": f"{name} must be a number"}
        if "catchup" in body:
            cfg["catchup"] = bool(body["catchup"])
        if "on" in body and bool(body["on"]) != cfg["on"]:
            cfg["on"] = bool(body["on"])
            if cfg["on"]:
                wk = window("wk")
                cfg.update(since=now(), wave=None, append=None,
                           wk_start=wk["pct"] if wk else None,
                           wk_start_at=now() if wk else None)
                night_say(f"autopilot on · target {cfg['target']}")
            else:
                cfg["wave"] = None
                night_say("autopilot off")
        NIGHT_WAKE.set()
    bump()
    return {"ok": True}


# ---------- actions ----------

def submit_comment(it: dict, text: str, sess: str | None = None) -> None:
    text = text.strip()
    low = text.lower()
    if low in ("commit", "next"):
        raise Reject(f"`{text}` is a console action, not a worker message")
    if low == "handoff":
        require_idle(it)
        phase = it["phase"]
        if not next_stage(it, phase):
            raise Reject("final stage — nothing to hand off to")
        if not it["sessions"].get(phase):
            raise Reject("no session yet")
        say(it, {"kind": "you", "text": text}, sess=phase)
        it["state"] = COMMENTED
        it["updated"] = False
        launch(it, HANDOFF_BRIEF, phase, handoff=True)
        return
    # a comment goes to one session, so only that session has to be idle —
    # an earlier stage can talk while the current pass runs
    sess = sess if sess in stage_names(it) else it["phase"]
    if RELOADING:
        raise Reject("server reload in progress — wait for it to finish")
    if it.get("handoff_pending", False):
        raise Reject("handoff in flight — wait for the next session to start")
    w = PROCS.get((it["id"], sess))
    if w and w["state"] in ("spawning", "sending", "running"):
        raise Reject("worker busy — wait for the turn to land")
    if not it["sessions"].get(sess):
        raise Reject("no session yet")
    say(it, {"kind": "you", "text": text}, sess=sess)
    if not text.startswith("/") and not busy_elsewhere(it, sess):
        it["state"] = COMMENTED
        it["updated"] = False
    launch(it, text, sess, trigger=clean_trigger(text))


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
def act_advance(it: dict) -> None:
    """Hand a reviewed stage to the next one by hand — what auto-advance does
    on its own for the waves that ask for it."""
    require_idle(it)
    if not next_stage(it, it["phase"]):
        raise Reject("final stage — nothing to advance to")
    if it["state"] not in (NEEDS_REVIEW, APPROVED):
        raise Reject("wait for the turn to land")
    if not report_of(it, it["phase"]):
        raise Reject("no handoff report yet — send `handoff` first")
    it["updated"] = False
    advance_stage(it)


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
            subprocess.run(cmd, cwd=ROOT, env=WORKER_ENV, stdout=log, stderr=log,
                           timeout=900)
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


# ---------- finalize backlog ----------
#
# What the finalize lens lists under the items in flight: every solver on disk
# that no fable session has passed over yet. The scan reads every solver file
# and the whole ledger, so it is its own endpoint and never runs inside
# /api/state; the rows it produces are reused for a few seconds, while the
# flags and the live items are read fresh on every request.

BACKLOG_TTL = 3
BACKLOG_CACHE: dict = {"at": 0.0, "rows": []}


def backlog_row(item_id: str, proposals: str, no_solver: bool = False) -> dict:
    comps = comps_of(item_id)
    calls = task_callouts(item_id)
    return {"id": item_id, "title": title_of(item_id), "comps": comps,
            "comps_unproposed": unproposed(comps, proposals),
            "callouts": calls, "callout_n": len(calls),
            "callout_rank": callout_rank(calls),
            "callout_act": callout_act(calls),
            "reports": report_stages(item_id), "no_solver": no_solver}


def backlog_scan() -> list[dict]:
    done = fabled(ledger_rows())
    proposals = prop_text()
    rows = []
    for path in sorted(SOLVERS.glob("*.dl")):
        # a running souffle drops `.tmp*.dl` scratch files into the directory
        if path.name.startswith("."):
            continue
        item_id = path.stem
        if item_id in done:
            continue
        rows.append(backlog_row(item_id, proposals))
    # A pass that wrote no solver leaves the glob nothing to find, so the task
    # needing a ruling most is the one the scan cannot reach. The reports carry
    # it: the stage landed, and its account of why stands in for the file.
    rows += [backlog_row(it["id"], proposals, no_solver=True)
             for it in STATE["items"]
             if it.get("landed") and it["id"] not in done
             and not solver_path(it["id"]).exists()]
    return rows


def finalize_ready(it: dict) -> bool:
    """The wave chain has landed everything before finalize, so the task ranks
    in the backlog while the item still sits in the console — no approval or
    commit required."""
    nxt = next_stage(it, it["phase"])
    return (it["state"] in (NEEDS_REVIEW, APPROVED) and not active(it)
            and nxt is not None and nxt["name"] == "finalize"
            and bool(report_of(it, it["phase"])))


def backlog_view() -> list[dict]:
    with LOCK:
        at = time.monotonic()
        if at - BACKLOG_CACHE["at"] > BACKLOG_TTL:
            BACKLOG_CACHE.update(at=at, rows=backlog_scan())
        table = flags()
        held = {it["id"] for it in STATE["items"]
                if it["state"] != COMMITTED and not finalize_ready(it)}
        rows = [dict(row) for row in BACKLOG_CACHE["rows"]
                if row["id"] not in held]
        for row in rows:
            row["flag"] = (table.get(row["id"]) or {}).get("level", 0)
    # A missing solver leads: it outranks a flag because it is not a reading of
    # the task but the absence of one. A P0 — broken tooling — follows it,
    # ahead of the flags, since the breakage may hold up other passes too.
    # -callout_n runs last, so a report carrying only P3s still edges out one
    # that raised nothing once everything ahead of it ties.
    rows.sort(key=lambda row: (0 if row["no_solver"] else 1,
                               0 if row["callout_rank"] == 0 else 1,
                               row["flag"] or 9,
                               callout_weight(row["callout_rank"]),
                               0 if row["comps"] else 1,
                               -row["callout_act"], -row["callout_n"],
                               row["id"]))
    return rows


def act_dismiss(body: dict) -> dict:
    """Drop a task from the finalize backlog: a ledger line records the ruling
    that it needs no fable pass. Deleting that line by hand restores it."""
    item_id = str(body.get("id") or "").strip()
    if not item_id or not solver_path(item_id).exists():
        return {"error": f"no solver for {item_id}"}
    ledger_append({"task": item_id, "stage": "dismissed", "backend": None,
                   "model": None, "session": None, "ts": int(time.time()),
                   "source": "user"})
    with LOCK:
        BACKLOG_CACHE["at"] = 0.0
    bump()
    return {"ok": True}


def act_finalize(body: dict) -> dict:
    """Start a finalize pass: advance a wave item that is done up to finalize,
    or, for a solver the console no longer holds, a fresh item whose chain is
    that stage alone, seeded from the reports on disk."""
    item_id = str(body.get("id") or "").strip()
    with LOCK:
        if RELOADING:
            return {"error": "server reload in progress — wait for it to finish"}
        if not item_id or not solver_path(item_id).exists():
            return {"error": f"no solver for {item_id}"}
        it = find(item_id)
        if it is not None:
            if not finalize_ready(it):
                return {"error": "already in the console — use the item itself"}
            # the wave chain is done up to finalize: advance the item in place
            it["updated"] = False
            advance_stage(it)
            seeded_names = None
        else:
            stage = dict(default_chain()[-1])
            pairs = persisted_reports(item_id, skip=stage["name"])
            it = {"id": item_id, "est": 0, "wave": STATE["wave"], "state": RUNNING,
                  "chain": [stage], "auto_advance": False,
                  "sessions": {stage["name"]: None}, "phase": stage["name"],
                  "landed": [], "dirty": False, "updated": False, "rev": 0,
                  "lastActive": {stage["name"]: None}, "title": title_of(item_id),
                  "feed": [], "append": wave_append(STATE["wave"]), "ver": 0,
                  "reports": {}}
            STATE["items"].append(it)
            seeded = ", ".join(name for name, _ in pairs)
            say(it, event(f"{stage['name']} started · "
                          + (f"seeded from {seeded}" if seeded else "no earlier reports")))
            try:
                launch(it, finalize_message(item_id, pairs), stage["name"])
            except (Reject, OSError) as exc:
                # nothing is in flight, so the item goes rather than sit unstarted
                STATE["items"].remove(it)
                return {"error": f"could not start the worker: {exc}"}
            seeded_names = [name for name, _ in pairs]
        BACKLOG_CACHE["at"] = 0.0
    bump()
    if seeded_names is None:
        return {"ok": True, "id": item_id, "advanced": True}
    return {"ok": True, "id": item_id, "seeded": seeded_names}


# ---------- http ----------

def light_items() -> list[dict]:
    out = []
    for it in STATE["items"]:
        names = stage_names(it)
        live = {phase: (worker := PROCS.get((it["id"], phase))) is not None and
                       worker["state"] != "dead"
                for phase in names}
        busy = {phase: (worker := PROCS.get((it["id"], phase))) is not None and
                       worker["state"] in ("spawning", "sending", "running")
                for phase in names}
        running = next((phase for phase in names
                        if (worker := PROCS.get((it["id"], phase))) and
                        worker["state"] in ("sending", "running")), None)
        turn = PROCS.get((it["id"], running)) if running else None
        out.append({k: it.get(k) for k in
                    ("id", "state", "dirty", "updated", "sessions", "phase", "context",
                     "lastActive", "wave", "rev", "title", "est", "ver", "append",
                     "comps", "comps_unproposed", "auto_advance",
                     "callouts", "callout_n", "callout_rank", "shared_writes")} |
                   {"chain": chain_of(it), "active": active(it),
                    "busy": busy,
                    "handoffPending": it.get("handoff_pending", False),
                    "turnPhase": running,
                    "turnStarted": turn["started"] if turn else None,
                    "workerLive": live,
                    "hasReport": bool(report_of(it, it["phase"]))})
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
                        "night": night_view(),
                        "cli": {"addDir": str(REF_DIR), "presets": wave_presets()},
                        "committer": dict(COMMITTER),
                        "solved": len([p for p in SOLVERS.glob("*.dl")
                                       if not p.name.startswith(".")]),
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
        elif url.path == "/api/backlog":
            self.reply({"items": backlog_view()})
        elif url.path.startswith("/api/peek/"):
            item_id = url.path.rsplit("/", 1)[1]
            if not solver_path(item_id).exists():
                return self.reply({"error": "no solver"}, 404)
            with LOCK:
                reports = [{"stage": name, "text": text}
                           for name, text in persisted_reports(item_id)]
            self.reply({"id": item_id, "title": title_of(item_id),
                        "solver": solver_text(item_id), "reports": reports})
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
            res = start_wave(int(body.get("k", 6)), body.get("order", "name"),
                             bool(body.get("auto_advance", False)),
                             body.get("chain"),
                             str(body.get("auto_stop") or "") or None)
        elif route == "/api/comment":
            res = act_comment(body.get("id", ""), body.get("text", ""),
                              body.get("sess"))
        elif route == "/api/compact":
            res = act_compact(body.get("id", ""), body.get("sess"))
        elif route == "/api/approve":
            res = act_approve(body.get("id", ""))
        elif route == "/api/unapprove":
            res = act_unapprove(body.get("id", ""))
        elif route == "/api/advance":
            res = act_advance(body.get("id", ""))
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
        elif route == "/api/night":
            res = act_night(body)
        elif route == "/api/flag":
            res = act_flag(body)
        elif route == "/api/finalize":
            res = act_finalize(body)
        elif route == "/api/dismiss":
            res = act_dismiss(body)
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
    threading.Thread(target=night_loop, daemon=True).start()
    threading.Thread(target=idle_loop, daemon=True).start()
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
