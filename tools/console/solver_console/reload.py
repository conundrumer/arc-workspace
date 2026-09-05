"""Quiescing the console for a re-exec, and the shutdown that ends it."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import config, process, store, waves


def turns_in_flight() -> bool:
    """Whether any item holds a turn the reload has to wait out. Caller holds
    LOCK."""
    return any(store.active(it) or it["state"] == store.QUEUED for it in store.STATE["items"])


RELOAD_POLL = 2  # seconds between checks of the sources' mtimes
# What the console runs on. An edit to any of it is a reload.
SOURCES = [config.HERE / "server.py",
           *sorted(Path(__file__).resolve().parent.glob("*.py"))]


def watch_reload() -> None:
    """Re-exec on a source change, at the console's next quiet moment."""
    mtime = max(p.stat().st_mtime for p in SOURCES)
    while True:
        time.sleep(RELOAD_POLL)
        try:
            current = max(p.stat().st_mtime for p in SOURCES)
        except OSError:
            continue
        if current == mtime:
            continue
        with store.LOCK:
            # Arming under a running turn would hold the reload for as long as
            # the turn takes, and the flag blocks the user for that stretch.
            if turns_in_flight():
                continue
        print("server source changed — restarting")
        if reload_server() == "failed":
            mtime = current   # the exec did not take; wait for the next edit


def quiesce_workers() -> bool:
    """Block new turns and wait for the in-flight ones to land, however long
    they take. A turn is never cut for a reload. False once a user action has
    taken the flag back."""
    with store.COND:
        store.RELOADING = True
        while store.RELOADING and turns_in_flight():
            store.COND.wait()
        # A reader's TextIOWrapper may read ahead and lose buffered output at
        # exec. Idle workers have no pending turn output, which makes this cut safe.
        return store.RELOADING


def reload_server() -> str:
    """Hand the workers over to a fresh server. "deferred" when the console
    took the flag back, "failed" when the exec did not take; on success it does
    not return."""
    manifest = None
    try:
        if quiesce_workers():
            with store.LOCK:
                # The flag is the standing claim on the exec: an action that
                # dropped it in the meantime keeps its own work off the cut.
                if store.RELOADING and not turns_in_flight():
                    manifest = process.worker_manifest()
                    os.environ[store.WORKER_HANDOFF_ENV] = json.dumps(manifest)
                    store.save()
                    os.execv(sys.executable, [sys.executable] + sys.argv)
                store.RELOADING = False
        print("reload deferred — the console is in use")
        return "deferred"
    except Exception as exc:
        if manifest is not None:
            for entry in manifest["workers"]:
                for name in ("stdin_fd", "stdout_fd"):
                    try:
                        os.set_inheritable(entry[name], False)
                    except OSError:
                        pass
        os.environ.pop(store.WORKER_HANDOFF_ENV, None)
        store.RELOADING = False
        with store.LOCK:
            for it in store.STATE["items"]:
                store.say(it, store.event(f"reload failed — server still running: {exc}"))
            store.save()
        waves.resume_queued_wave()
        return "failed"


def shutdown_workers() -> None:
    with store.LOCK:
        if store.SHUTTING_DOWN:
            return
        store.SHUTTING_DOWN = True
        dying = list(store.PROCS.values())
        store.PROCS.clear()
        for worker in dying:
            worker["state"] = "dying"
            worker["outbound"].put_nowait(store.STOP)
    store.DEFERRED.put_nowait(store.STOP)
    for worker in dying:
        proc = worker["proc"]
        if proc.poll() is None:
            proc.terminate()
    for worker in dying:
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
    if store.DEFERRED_THREAD:
        store.DEFERRED_THREAD.join(timeout=4)
