"""The fixtures and helpers the console tests share.

The console module is loaded fresh per test with CONSOLE_STATE_DIR pointed at a
tmp dir, so its module-level state and paths never touch the real workspace.
"""

import importlib.util
import json
import queue
import sys
import threading
import time
from pathlib import Path

import pytest

from dl.context import DOCS

ROOT = Path(__file__).resolve().parents[2]
SERVER_PY = ROOT / "tools" / "console" / "server.py"
PACKAGE = "solver_console"
FAKE_WORKER = ROOT / "tools" / "console" / "fake_worker.py"
# Enough of a window for a test to reach a turn mid-flight, without the demo
# pacing the fake worker uses by default.
FAKE_PACE = "0.002"
# How often a test re-checks state a worker thread is about to change.
TICK = .002
# How long a test waits before it calls something blocked. The code under test
# either moves within a thread hand-off or is holding, so the margin only has
# to clear scheduling noise.
SETTLE = .02
# How long a test holds a window open for something that must not happen.
# Wider than SETTLE: the assertion is only as strong as the window.
HOLD = .2


class Console:
    """One namespace over the server's modules: a name resolves to the module
    that defines it, so a test reads and patches it where its callers see it.

    Patching reaches every caller because the package modules import each
    other as `from . import mod` and read attributes at call time; a
    `from .mod import name` import would hold a reference no patch reaches.
    """

    def __init__(self, entry):
        mods = [entry] + [m for name, m in sorted(sys.modules.items())
                          if name.startswith(PACKAGE + ".")]
        seen = {}
        for mod in mods:
            for name, val in vars(mod).items():
                if not name.startswith("__"):
                    assert seen.setdefault(name, val) is val, \
                        f"`{name}` names different things in two modules"
        object.__setattr__(self, "_mods", mods)

    def __getattr__(self, name):
        for mod in object.__getattribute__(self, "_mods"):
            if name in vars(mod):
                return getattr(mod, name)
        raise AttributeError(name)

    def __setattr__(self, name, value):
        mods = object.__getattribute__(self, "_mods")
        for mod in mods:
            if name in vars(mod):
                setattr(mod, name, value)
                return
        setattr(mods[0], name, value)


def load_console():
    """server.py, its package, and the helper modules beside it, run into
    modules of their own, so no module-level state carries between tests."""
    for name in [n for n in sys.modules
                 if n in ("console_server", "quota", "calibrate") or n.startswith(PACKAGE)]:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location("console_server", SERVER_PY)
    entry = importlib.util.module_from_spec(spec)
    sys.modules["console_server"] = entry
    spec.loader.exec_module(entry)
    return Console(entry)


@pytest.fixture(scope="session")
def workdir(tmp_path_factory):
    """A root for the per-test directories. The numbered directories pytest
    hands out cost more than the tests that use them."""
    return tmp_path_factory.mktemp("console")


@pytest.fixture
def tmp_path(workdir, request):     # noqa: A002 — replaces pytest's own
    path = workdir / request.node.name[:80]
    n = 0
    while path.exists():
        n += 1
        path = workdir / f"{request.node.name[:80]}-{n}"
    path.mkdir()
    return path


@pytest.fixture
def srv(tmp_path, monkeypatch):
    monkeypatch.setenv("CONSOLE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("CONSOLE_CLAUDE_HOME", str(tmp_path / "claude-home"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "user-home"))
    # The server snapshots the environment into WORKER_ENV at import, so the
    # fake worker's pace has to be set before the module loads.
    monkeypatch.setenv("CONSOLE_FAKE_PACE", FAKE_PACE)
    s = load_console()
    s.STATE_DIR.mkdir(parents=True)
    s.LOG_DIR.mkdir(parents=True)
    for name in ("SOLVERS", "DOCS"):
        d = tmp_path / name.lower()
        d.mkdir()
        monkeypatch.setattr(s, name, d)
    for name in DOCS:
        (s.DOCS / name).write_text(f"# {name}\n")
    monkeypatch.setattr(s, "queue_pick",
                        lambda n, order: [(f"t{i:02d}", 10 + i) for i in range(n)])
    s._test_stagger_launch = s.stagger_launch
    monkeypatch.setattr(s, "stagger_launch", lambda ids: None)
    # A worker thread outliving its test closes pipes on its way out, and the
    # next test's subprocess is handed those same descriptor numbers. Join them
    # before the test ends so the numbers stay claimed.
    threads = []
    start = s.start_worker_threads

    def start_and_track(worker):
        start(worker)
        threads.extend([worker["writer"], worker["reader"]])

    monkeypatch.setattr(s, "start_worker_threads", start_and_track)
    yield s
    for worker in list(s.PROCS.values()):
        proc = worker.get("proc")           # some tests stand in a stub here
        if callable(getattr(proc, "poll", None)) and proc.poll() is None:
            proc.terminate()
    for thread in threads:
        thread.join(timeout=3)


def lock_free(srv) -> bool:
    """Whether another thread could take LOCK right now."""
    got = []

    def take():
        if srv.LOCK.acquire(timeout=SETTLE):
            srv.LOCK.release()
            got.append(True)

    t = threading.Thread(target=take)
    t.start()
    t.join()
    return bool(got)


def item(s, item_id, state, **kw):
    """Append an item the way start_wave does, then override for the test."""
    it = {"id": item_id, "est": 10, "wave": 1, "state": state,
          "chain": s.two_phase_chain(), "auto_advance": False,
          "sessions": {"create": None, "refine": "sess-" + item_id},
          "phase": "refine", "landed": ["refine"],
          "lastActive": {"create": None, "refine": None},
          "dirty": False, "updated": False, "rev": 1, "title": "",
          "feed": [], "append": "", "ver": 0, "reports": {}}
    it.update(kw)
    s.STATE["items"].append(it)
    return it


def tagged(text, tag="handoff"):
    """A worker's act: the text between its tags, as a turn ends with it."""
    return f"``(・_・)``\n\n<{tag}>\n{text}\n</{tag}>\n\n*tink*"


def worker(s, it, phase="refine", state="idle", turn_seq=1):
    w = {"item_id": it["id"], "phase": phase, "state": state,
         "turn_seq": turn_seq, "outbound": queue.Queue(), "seen": set(),
         "session_seen": True, "handoff": False, "got_result": False,
         "started": None, "trigger": None, "think_run": 0, "reqs": {}}
    s.PROCS[(it["id"], phase)] = w
    return w


def create_item(srv, item_id="a", **kw):
    """An item mid-create, the way a wave admits one."""
    return item(srv, item_id, srv.RUNNING, phase="create", landed=[], rev=0,
                sessions={"create": "cs", "refine": None}, **kw)


def land_report(srv, it, text="tried X, discarded Y"):
    srv.finish_turn(it, {"result": tagged(text)}, None, time.time(), "create", True)


def finalize_item(srv, item_id="a", state=None, idle_for=0, **kw):
    """An unapproved finalize session whose worker has sat idle `idle_for`
    seconds, its cache aging as long."""
    it = item(srv, item_id, state or srv.NEEDS_REVIEW, chain=srv.default_chain(),
              phase="finalize",
              sessions={"create": "cs", "refine": "rs", "finalize": "fs"},
              landed=["create", "refine", "finalize"],
              lastActive={"create": None, "refine": None,
                          "finalize": int((time.time() - idle_for) * 1000)}, **kw)
    w = worker(srv, it, phase="finalize")
    w["idle_since"] = time.time() - idle_for
    return it


def codex_item(srv, item_id, state, **kw):
    """An item whose first stage runs on codex."""
    kw.setdefault("sessions", {"create": None, "refine": None})
    return item(srv, item_id, state, phase="create", landed=[],
                chain=[{"name": "create", "backend": "codex",
                        "model": "gpt-5.1-codex", "effort": "high"},
                       {"name": "refine", "backend": "claude",
                        "model": "claude-fable-5"}],
                lastActive={"create": None, "refine": None}, **kw)


def transcript(srv, monkeypatch, tmp_path, session, rows=()):
    """Stand in for the CLI's record of a session."""
    home = tmp_path / "projects"
    (home / "proj").mkdir(parents=True, exist_ok=True)
    path = home / "proj" / f"{session}.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    monkeypatch.setattr(srv, "PROJECTS", home)
    return path


def write_solver(srv, item_id, text):
    srv.solver_path(item_id).write_text(text)


PROP = "docs/wf-solver/proposals"


def idle_worker(s, it, phase="refine", idle_for=0, **kw):
    """A worker parked in PROCS that went idle `idle_for` seconds ago."""
    w = worker(s, it, phase=phase)
    w.update(idle_since=time.time() - idle_for, **kw)
    return w


def night_workers(s, idle_for):
    """One autopilot item per entry, each parked with a worker that went idle
    that many seconds ago."""
    for n, seconds in enumerate(idle_for):
        idle_worker(s, item(s, f"n{n}", s.NEEDS_REVIEW, night=True),
                    idle_for=seconds)


REPORT = """The model hypothesis stands.

## Callouts

- rank ties are broken by position; the data does not say so
- `rank_of` reads like lib material
"""


def backlog_solver(srv, item_id, text="// draft\n// concept: a shape\n"):
    """A solver on disk the user has not approved: the draft line is the
    console's own tag."""
    write_solver(srv, item_id, text)


def finalize_launch(srv, monkeypatch):
    sent = []
    monkeypatch.setattr(srv, "launch", lambda it, msg, phase, **kw:
                        sent.append((msg, phase)))
    return sent


def get(srv, path):
    """One GET through the handler, without a socket: the reply it would send."""
    h = srv.Handler.__new__(srv.Handler)
    h.path = path
    out = {}
    h.reply = lambda obj, status=200, ctype="application/json": \
        out.update(body=obj, status=status, ctype=ctype)
    h.do_GET()
    return out
