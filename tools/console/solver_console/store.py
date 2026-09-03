"""The console's shared state: the item list, the locks, the worker
registry, and the stage chain."""

import functools
import json
import queue
import re
import threading
import time

from . import config, solvers

LOCK = threading.RLock()
COND = threading.Condition(LOCK)
STATE = {"seq": 0, "wave": 0, "items": []}
PROCS: dict[tuple[str, str], dict] = {}
FIRST_RESPONSE: dict[str, threading.Event] = {}
DEFERRED = queue.Queue()
DEFERRED_THREAD = None
STOP = object()
SHUTTING_DOWN = False
RELOADING = False
USAGE: list[dict] = []  # account rate-limit windows, refreshed in background
# The committer session in flight or last run: `feed` holds what it said and
# ran, in the entries the item feeds use, so the console can show a run while
# it goes.
COMMITTER = {"running": False, "note": None, "started": None, "feed": []}
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
# A report lands either way; who acts on it is the item's `auto_advance` and
# `auto_stop`. A wave item hands itself on through every stage before the last,
# and stops there: the landing that would launch the last stage lands in review
# instead, still in the stage that reported, and the advance or finalize action
# moves it on when the user asks. An item built for one stage alone never hands
# off.
# Every report is also written under state/reports/, so it outlives the item a
# commit drops and can seed a later stage over a solver already committed.
#
# A turn ends in NEEDS_REVIEW, whether it reported a result or died mid-flight;
# a worker that never reported a session falls back to QUEUED instead. `load`
# applies that same fallback to turns a console restart cut short, so no ACTIVE
# state survives a restart. Comments relaunch from NEEDS_REVIEW or APPROVED,
# approval moves between those two, and a commit ends at COMMITTED.
# console.html renders the same names — keep the two in step.

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
# within an item and key everything the item holds per session, the report
# files and PROCS included.

BACKENDS = ("claude", "codex")
STAGE_NAME = re.compile(r"[A-Za-z0-9_-]{1,32}")


PIPELINE_STAGES = tuple(config.PIPELINE_DEFAULTS)


def pipeline() -> dict:
    """The pipeline settings: the model name each settable stage runs, filled
    in with the defaults. A wave reads them when it starts, so a change
    reaches the next wave and leaves the items already running as they are."""
    cfg = STATE.setdefault("pipeline", {})
    for name, value in config.PIPELINE_DEFAULTS.items():
        if cfg.get(name) not in config.MODEL_IDS:
            cfg[name] = value
    return cfg


def stage_model(name: str) -> str:
    """The model id a stage runs under the current settings."""
    return config.MODEL_IDS[pipeline().get(name, config.FINALIZE_MODEL)]


def default_chain() -> list[dict]:
    """What a wave runs when it names no chain."""
    return [{"name": name, "backend": "claude", "model": stage_model(name)}
            for name in ("create", "refine", "finalize")]


def two_phase_chain() -> list[dict]:
    """The create/refine pair earlier console versions ran, which items
    written by those versions are read as."""
    return [{"name": "create", "backend": "claude", "model": stage_model("create")},
            {"name": "refine", "backend": "claude",
             "model": config.MODEL_IDS[config.FINALIZE_MODEL]}]


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
    return {"name": name, "backend": "claude", "model": stage_model(name)}


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
    """The chain a wave request asks for, checked. The console never asks for
    one; a request made by hand may, and its stages then name their own
    backend and model. Stage names key report files, so they are held to a
    filename-safe shape."""
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


def defer_reload() -> None:
    """Drop a pending quiesce so a user action can go through. The watcher
    arms again once the console is next quiet. Caller holds LOCK."""
    global RELOADING
    if RELOADING:
        RELOADING = False
        COND.notify_all()


def require_idle(it: dict) -> None:
    defer_reload()
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
    """Publish the state under the lock it is mutated under. Two savers share
    the one temp file, so the second to write it leaves the first with nothing
    to rename, and either can serialize a dict the other is still changing."""
    with LOCK:
        tmp = config.STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(STATE, indent=1))
        tmp.replace(config.STATE_FILE)
    # ref_note.py reads this: the ids ratified ahead of their commit
    text = "".join(it["id"] + "\n" for it in STATE["items"]
                   if it["state"] == APPROVED)
    if not config.APPROVED_FILE.exists() or config.APPROVED_FILE.read_text() != text:
        config.APPROVED_FILE.write_text(text)


def load() -> None:
    if not config.STATE_FILE.exists():
        return
    STATE.update(json.loads(config.STATE_FILE.read_text()))
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
        it["chain"][1]["model"] = (it.get("refine_model")
                                   or config.MODEL_IDS[config.FINALIZE_MODEL])
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
        # the proposals snapshot was one file's text; it is a dict per entry
        if not isinstance(it["pre"].get("proposals"), dict):
            it["pre"]["proposals"] = {}
        if not isinstance(it.get("prop_after", {}), dict):
            it["prop_after"] = {}
        return
    it.pop("snap_prop", None)
    it["pre"] = {"hash": it.pop("hash_before", ""),
                 "solver": it.pop("snap", ""),
                 "proposals": {},
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
    return it.setdefault("pre", {"hash": "", "solver": "", "proposals": {},
                                 "dirty": False, "files": {}})


def shared_writes(it: dict) -> list[str]:
    """Repo files the turn changed outside the pass's own surface — the
    solver and its scratch directory."""
    own = f"programs/solvers/{it['id']}.dl"
    watched = solvers.watched_paths(it["id"])
    hits = set()
    for rel, digest in pre(it).get("watched", {}).items():
        p = watched.get(rel)
        if p is None or solvers.file_hash(p) != digest:
            hits.add(rel)
    for rel, snap in pre(it)["files"].items():
        if rel == own or rel.startswith(".scratch/") or rel in hits:
            continue
        p = config.ROOT / rel
        if (p.read_text() if p.exists() else "") != snap:
            hits.add(rel)
    return sorted(hits)


def seed_report(it: dict) -> None:
    """Adopt the report files when state carries none, so an item that came
    back after a restart or a commit still knows what earlier stages found."""
    reports = it.setdefault("reports", {})
    for name in stage_names(it):
        if not (reports.get(name) or "").strip():
            text = solvers.report_of(it, name)
            if text:
                reports[name] = text
        text = reports.get(name) or ""
        collapsed = solvers.collapse_callouts(text)
        if collapsed != text:
            reports[name] = collapsed
            solvers.save_report(it["id"], name, collapsed)


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

