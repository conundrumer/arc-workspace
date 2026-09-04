#!/usr/bin/env python3
"""Review console for batch solver workers.

Serves the console UI, launches `claude -p` workers in waves, resumes them
with review comments, and commits approved solvers.

    uv run python tools/console/server.py [--port 8347]

Env:
    CONSOLE_FAKE=1     use fake_worker.py instead of claude (UI demo)
    CONSOLE_CLAUDE     claude binary (default: claude)
    CONSOLE_OPUS_MODEL     the model id behind the "opus" setting (default: claude-opus-5)
    CONSOLE_FABLE_MODEL    the model id behind the "fable" setting (default: claude-fable-5)
    CONSOLE_CLAUDE_EFFORT  effort for claude stages whose chain names none (default: high)
    CONSOLE_COMMIT_MODEL   committer model (default: claude-opus-5)
    CONSOLE_REFUSAL_MODEL  model a stage moves to after its report asks are refused twice (default: claude-sonnet-5)
"""

import argparse
import fcntl
import json
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Run as a script, but loaded by file path in tests, where this directory is
# not on the import path.
sys.path.append(str(Path(__file__).resolve().parent))

from solver_console import (  # noqa: E402
    actions,
    backlog,
    config,
    ledger,
    overnight,
    pacing,
    prompts,
    reload,
    solvers,
    store,
    waves,
    workers,
)


def item_files(it: dict) -> list[dict]:
    """The code pane's tabs: the solver, the files this turn edited, and the
    entries the task's sessions added, which stay across turns."""
    solver_rel = f"programs/solvers/{it['id']}.dl"
    edited = store.pre(it)["files"]
    paths = {rel: config.ROOT / rel
             for rel in [solver_rel] + [r for r in edited if r != solver_rel]}
    for rel in it.get("entries", []):
        if rel not in paths and solvers.prop_path(rel).exists():
            paths[rel] = solvers.prop_path(rel)
    files = []
    for rel, p in paths.items():
        files.append({
            "path": rel,
            "snap": edited.get(rel, store.pre(it)["solver"]
                               if rel == solver_rel else ""),
            "code": p.read_text() if p.exists() else "",
        })
    return files


def light_items() -> list[dict]:
    out = []
    for it in store.STATE["items"]:
        names = store.stage_names(it)
        live = {phase: (worker := store.PROCS.get((it["id"], phase))) is not None and
                       worker["state"] != "dead"
                for phase in names}
        busy = {phase: (worker := store.PROCS.get((it["id"], phase))) is not None and
                       worker["state"] in ("spawning", "sending", "running")
                for phase in names}
        running = next((phase for phase in names
                        if (worker := store.PROCS.get((it["id"], phase))) and
                        worker["state"] in ("sending", "running")), None)
        turn = store.PROCS.get((it["id"], running)) if running else None
        out.append({k: it.get(k) for k in
                    ("id", "state", "dirty", "updated", "sessions", "phase", "context",
                     "lastActive", "wave", "rev", "title", "est", "ver", "append",
                     "comps", "comps_unproposed", "auto_advance",
                     "callouts", "callout_n", "callout_rank", "shared_writes")} |
                   {"chain": store.chain_of(it), "active": store.active(it),
                    "entries": solvers.entry_names(it.get("entries", [])),
                    "busy": busy,
                    "handoffPending": it.get("handoff_pending", False),
                    "turnPhase": running,
                    "turnStarted": turn["started"] if turn else None,
                    "workerLive": live,
                    "hasReport": bool(solvers.report_of(it, it["phase"])),
                    "cutPhase": it.get("resume_phase")})
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
            self.reply((config.HERE / "console.html").read_bytes(), ctype="text/html")
        elif url.path.startswith("/vendor/"):
            p = config.HERE / "vendor" / Path(url.path).name
            if not p.exists():
                return self.reply({"error": "not found"}, 404)
            self.reply(p.read_bytes(), ctype="application/javascript")
        elif url.path == "/api/state":
            q = parse_qs(url.query)
            since = int(q.get("since", ["0"])[0])
            wait = float(q.get("wait", ["0"])[0])
            deadline = time.time() + min(wait, 25)
            with store.COND:
                while store.STATE["seq"] <= since and time.time() < deadline:
                    store.COND.wait(deadline - time.time())
                snap = {"seq": store.STATE["seq"], "wave": store.STATE["wave"],
                        "items": light_items(), "usage": store.USAGE,
                        "night": overnight.night_view(),
                        "cli": {"addDir": str(config.REF_DIR)},
                        "pipeline": dict(store.pipeline()),
                        "models": list(config.MODEL_IDS),
                        "committer": dict(store.COMMITTER),
                        "debriefed": ledger.debriefed(),
                        "solved": len([p for p in config.SOLVERS.glob("*.dl")
                                       if not p.name.startswith(".")]),
                        "total": len(list(config.REF_DIR.glob("programs/solvers/*.ts")))}
            self.reply(snap)
        elif url.path.startswith("/api/item/"):
            item_id = url.path.rsplit("/", 1)[1]
            with store.LOCK:
                it = store.find(item_id)
                if it is None:
                    return self.reply({"error": "unknown item"}, 404)
                self.reply({"feed": it["feed"], "files": item_files(it),
                            "ver": it.get("ver", 0)})
        elif url.path == "/api/backlog":
            self.reply({"items": backlog.backlog_view()})
        elif url.path == "/api/debrief":
            self.reply(ledger.debrief_view())
        elif url.path.startswith("/api/peek/"):
            item_id = url.path.rsplit("/", 1)[1]
            if not solvers.solver_path(item_id).exists():
                return self.reply({"error": "no solver"}, 404)
            with store.LOCK:
                reports = [{"stage": name, "text": text}
                           for name, text in prompts.persisted_reports(item_id)]
            self.reply({"id": item_id, "title": solvers.title_of(item_id),
                        "solver": solvers.solver_text(item_id), "reports": reports})
        elif url.path.startswith("/api/task/"):
            item_id = url.path.rsplit("/", 1)[1]
            p = config.TASKS / f"{item_id}.json"
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
            res = waves.start_wave(int(body.get("k", 6)), body.get("order", "name"),
                                   body.get("chain"))
        elif route == "/api/pipeline":
            res = actions.act_pipeline(body)
        elif route == "/api/comment":
            res = actions.act_comment(body.get("id", ""), body.get("text", ""),
                                      body.get("sess"))
        elif route == "/api/compact":
            res = actions.act_compact(body.get("id", ""), body.get("sess"))
        elif route == "/api/approve":
            res = actions.act_approve(body.get("id", ""))
        elif route == "/api/unapprove":
            res = actions.act_unapprove(body.get("id", ""))
        elif route == "/api/advance":
            res = actions.act_advance(body.get("id", ""))
        elif route == "/api/land":
            res = actions.act_land(body.get("id", ""))
        elif route == "/api/model":
            res = actions.act_model(body.get("id", ""), str(body.get("phase") or ""),
                                    str(body.get("model") or ""))
        elif route == "/api/session":
            res = actions.act_session(body.get("id", ""), str(body.get("phase") or ""),
                                      str(body.get("session") or ""))
        elif route == "/api/resume":
            res = actions.act_resume(body.get("id", ""))
        elif route == "/api/seen":
            res = actions.act_seen(body.get("id", ""))
        elif route == "/api/kill":
            res = actions.act_kill(body.get("id", ""))
        elif route == "/api/drop":
            res = actions.act_drop(body.get("id", ""))
        elif route == "/api/revert":
            res = actions.act_revert(body.get("id", ""))
        elif route == "/api/commit":
            res = actions.act_commit()
        elif route == "/api/night":
            res = overnight.act_night(body)
        elif route == "/api/flag":
            res = ledger.act_flag(body)
        elif route == "/api/debrief":
            res = ledger.act_debrief()
        elif route == "/api/finalize":
            res = backlog.act_finalize(body)
        elif route == "/api/dismiss":
            res = backlog.act_dismiss(body)
        elif route == "/api/approve-solver":
            res = backlog.act_approve_solver(body)
        else:
            return self.reply({"error": "not found"}, 404)
        self.reply(res, 400 if "error" in res else 200)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8347)
    args = ap.parse_args()
    config.STATE_DIR.mkdir(exist_ok=True)
    config.LOG_DIR.mkdir(exist_ok=True)
    global _state_lock
    _state_lock = open(config.STATE_DIR / ".lock", "w")
    try:
        fcntl.flock(_state_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("another console server owns this state dir — refusing to start")
    handoff = workers.read_worker_handoff()
    store.load()
    ledger.seed_entries()
    workers.adopt_workers(handoff)
    workers.expire_holds(force=True)
    store.save()
    waves.resume_queued_wave()
    threading.Thread(target=reload.watch_reload, daemon=True).start()
    threading.Thread(target=pacing.usage_loop, daemon=True).start()
    threading.Thread(target=workers.watch_caps, daemon=True).start()
    threading.Thread(target=overnight.night_loop, daemon=True).start()
    threading.Thread(target=workers.idle_loop, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    stopping = threading.Event()
    def request_stop(signum, frame):
        if not stopping.is_set():
            stopping.set()
            threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    mode = " (FAKE workers)" if config.FAKE else ""
    print(f"solver console · http://127.0.0.1:{args.port}{mode}")
    try:
        server.serve_forever()
    finally:
        server.server_close()
        reload.shutdown_workers()


if __name__ == "__main__":
    main()
