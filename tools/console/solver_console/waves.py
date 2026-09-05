"""Picking tasks off the queue and launching a wave of items over them."""

import re
import subprocess
import threading
import time

from . import config, drain, prompts, store, workers

WAVE_DEBOUNCE = 5  # seconds; a fumbled double-click, not a deliberate second wave
LAST_WAVE_AT = 0.0


def queue_pick(n: int, order: str) -> list[tuple[str, int]]:
    """Top `n` unsolved tasks from scripts/queue.sh, as (id, size estimate)."""
    out = subprocess.run(["bash", "scripts/queue.sh", "-n", str(n), "--order", order],
                         cwd=config.ROOT, capture_output=True, text=True)
    if out.returncode != 0:
        raise store.Reject("queue.sh failed: " + out.stderr.strip()[-200:])
    picked = []
    for line in out.stdout.splitlines():
        m = re.match(r"\s*(\d+)\s+(\S+)", line)
        if m:
            picked.append((m.group(2), int(m.group(1))))
    return picked


def drop_committed() -> None:
    """Forget the committed items of the round before, with their workers."""
    for old in [it for it in store.STATE["items"] if it["state"] == store.COMMITTED]:
        for worker in workers.detach_workers(old["id"]):
            drain.queue_reap(worker)
    store.STATE["items"] = [it for it in store.STATE["items"] if it["state"] != store.COMMITTED]


def pick_new(k: int, order: str) -> list[tuple[str, int]]:
    """The next k queue tasks the console does not already hold."""
    existing = {it["id"] for it in store.STATE["items"]}
    return [p for p in queue_pick(k + len(existing), order)
            if p[0] not in existing][:k]


def make_items(picked: list[tuple[str, int]], chain: list[dict], wave: int,
               append: str, night: bool = False) -> list[str]:
    """Append picked tasks as items of `wave`. Caller holds LOCK.

    An item hands itself on up to the chain's last stage and stops there, so
    that pass stays the user's own call."""
    names = [st["name"] for st in chain]
    for tid, est in picked:
        it = {
            "id": tid, "est": est, "wave": wave, "state": store.QUEUED,
            "chain": [dict(st) for st in chain],
            "auto_advance": True, "auto_stop": names[-1],
            "sessions": dict.fromkeys(names), "phase": names[0],
            "landed": [], "dirty": False, "updated": False, "rev": 0,
            "lastActive": dict.fromkeys(names),
            "title": "", "feed": [], "append": append, "ver": 0,
            "reports": {},
        }
        if night:
            # the cap follows the workers autopilot started, whether or not it
            # is still on when they go idle
            it["night"] = True
        store.seed_report(it)
        store.STATE["items"].append(it)
    return [tid for tid, _ in picked]


def start_wave(k: int, order: str = "name", chain: list | None = None) -> dict:
    global LAST_WAVE_AT
    with store.LOCK:
        store.defer_reload()
        if time.time() - LAST_WAVE_AT < WAVE_DEBOUNCE:
            return {"error": "a wave just started"}
        if order not in ("name", "size"):
            return {"error": f"unknown order: {order}"}
        try:
            chain = store.clean_chain(chain)
        except store.Reject as e:
            return {"error": str(e)}
        drop_committed()
        try:
            picked = pick_new(k, order)
        except store.Reject as e:
            return {"error": str(e)}
        if not picked:
            return {"error": "queue is empty"}
        LAST_WAVE_AT = time.time()
        store.STATE["wave"] += 1
        ids = make_items(picked, chain, store.STATE["wave"],
                         str(prompts.append_path()))
    store.bump()
    threading.Thread(target=stagger_launch, args=(ids,), daemon=True).start()
    return {"ok": True, "ids": ids}


def stagger_launch(ids: list[str]) -> None:
    """Launch one claude-backed worker alone so it writes the shared
    prompt-cache prefix, then fan the rest out once its first API response
    arrives. A codex-backed first stage draws on no such cache, so it neither
    seeds nor waits — a wave of them launches together."""
    first = threading.Event()
    seed, seeded = None, False
    with store.LOCK:
        for tid in ids:
            it = store.find(tid)
            if it is not None and store.backend_of(it, it["phase"]) == "claude":
                seed = tid
                break
        if seed is not None:
            it = store.find(seed)
            if it["state"] == store.QUEUED and not store.active(it):
                store.FIRST_RESPONSE[seed] = first
                it["state"] = store.RUNNING
                store.say(it, store.event("launched (cache seeder)"))
                workers.launch(it, prompts.create_message(seed), it["phase"], handoff=True,
                               admitted=True)
                seeded = True
    store.bump()
    if seeded:
        first.wait(timeout=config.STAGGER_TIMEOUT)
        with store.LOCK:
            if store.FIRST_RESPONSE.get(seed) is first:
                store.FIRST_RESPONSE.pop(seed, None)
    with store.LOCK:
        for tid in ids:
            if seeded and tid == seed:
                continue
            it = store.find(tid)
            if it is None or it["state"] != store.QUEUED or store.active(it):
                continue
            it["state"] = store.RUNNING
            store.say(it, store.event("launched"))
            workers.launch(it, prompts.create_message(tid), it["phase"], handoff=True,
                           admitted=True)
    store.bump()


def resume_queued_wave() -> None:
    """Give persisted admissions an owner after an exec or failed reload."""
    with store.LOCK:
        ids = [it["id"] for it in store.STATE["items"] if it["state"] == store.QUEUED and
               not any(item_id == it["id"] for item_id, _ in store.PROCS)]
    if ids:
        threading.Thread(target=stagger_launch, args=(ids,), daemon=True).start()
