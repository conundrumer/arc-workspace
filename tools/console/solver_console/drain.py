"""The jobs a worker thread defers to a thread of its own, and the loop that
runs on idle: the turns a landing owes, the reap of idle workers, and the
compact that stands in for a reap."""

import sys
import threading
import time

from . import config, landing, process, prompts, refusals, store, workers


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
                process.reap(job[1])
                continue
            if job[0] == "revive":
                workers.revive(*job[1:])
                continue
            if job[0] == "refuse":
                refusals.recover_refusal(*job[1:])
                continue
            kind, item_id, phase, turn_seq = job
            with store.LOCK:
                it = store.find(item_id)
                worker = store.PROCS.get((item_id, phase))
                if it and kind in store.OWED_ASKS:
                    it["owed"] = max(0, it.get("owed", 0) - 1)
                if kind == "rehandoff":
                    if not it or it.get("bg_wait") == phase:
                        continue
                    if store.RELOADING:
                        store.pause_for_reload(it, phase, kind)
                    elif not worker or worker["turn_seq"] != turn_seq:
                        landing.to_review(it)
                    else:
                        resend_handoff(it, phase)
                elif kind == "callout":
                    if not it or it.get("callout_wait") != phase:
                        continue
                    if store.RELOADING:
                        it.pop("callout_wait", None)
                        store.pause_for_reload(it, phase, kind)
                    elif not worker or worker["turn_seq"] != turn_seq:
                        # the report stands without callouts
                        it.pop("callout_wait", None)
                        it.pop("landing_compact", None)
                        landing.to_review(it)
                    else:
                        it["state"] = store.RUNNING
                        store.say(it, store.event("callout turn starting"), sess=phase)
                        workers.launch(it, prompts.callout_brief(), phase, trigger="callout")
                elif kind == "compact":
                    # A turn since the landing, a turn or relaunch in flight
                    # on any session of the item, a compact already done, or
                    # a setting turned off in the meantime: no compact. The
                    # refusal path files the job with no turn number, since
                    # its worker is gone, so the item's own marks are what
                    # hold it off a turn the user opened.
                    if not it or store.active(it) \
                            or it.get("auto_compacted", {}).get(phase) \
                            or (turn_seq is not None
                                and (not worker or worker["turn_seq"] != turn_seq)) \
                            or not store.auto()["compact_landing"]:
                        continue
                    if store.RELOADING:
                        store.pause_for_reload(it, phase, kind)
                    else:
                        start_compact(it, phase, "on landing")
                elif not it or not it.get("handoff_pending") or not worker or \
                        worker["turn_seq"] != turn_seq:
                    if it:
                        it.pop("handoff_pending", None)
                    continue
                else:
                    it.pop("handoff_pending", None)
                    advance(it)
            store.bump()
        except Exception as exc:
            print(f"deferred {job[0]} failed: {exc}", file=sys.stderr)


def resend_handoff(it: dict, phase: str) -> None:
    """Ask the stage for its handoff block once more. Caller holds LOCK."""
    it["state"] = store.RUNNING
    store.say(it, store.event("handoff ask resent"), sess=phase)
    workers.launch(it, prompts.HANDOFF_BRIEF, phase, trigger="handoff", handoff=True,
                   admitted=True)


def advance(it: dict) -> None:
    """Move the item on to its next stage, on the chain's own decision.
    Caller holds LOCK."""
    prev = it["phase"]
    workers.advance_stage(it)
    # a finalize pass opened this way lands unattended, so its first
    # landing owes the lens its callouts
    if prev != "finalize" and it["phase"] == "finalize":
        it["auto_finalize"] = True


def resume_paused() -> None:
    """Send the turns a reload set aside, once it is over or called off. A
    turn the user opened on the item in the meantime supersedes its ask.
    Caller holds LOCK."""
    for it in store.STATE["items"]:
        ask = it.pop("reload_ask", None)
        if not ask:
            continue
        phase, kind = ask["phase"], ask["kind"]
        name = store.OWED_ASKS[kind]
        if store.active(it):
            store.say(it, store.event(f"{name} dropped — a turn ran since the reload"),
                      sess=phase)
            continue
        try:
            if kind == "callout":
                landing.ask_callouts(it, phase)
            elif kind == "rehandoff":
                resend_handoff(it, phase)
            elif kind == "compact":
                if not it.get("auto_compacted", {}).get(phase) \
                        and store.auto()["compact_landing"]:
                    start_compact(it, phase, "on landing")
            else:
                advance(it)
        except (store.Reject, OSError) as exc:
            store.say(it, store.event(f"{name} not resumed after the reload: {exc}"),
                      sess=phase)


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
    if it is None or it.get("callout_wait") or it.get("handoff_pending") \
            or it.get("bg_wait"):
        return None
    return it


def drop_worker(it: dict, key: tuple[str, str], worker: dict, why: str) -> None:
    """Take an idle worker out of PROCS and stop its process. Caller holds
    LOCK. The item keeps its session id, so a later comment resumes the phase
    from the transcript."""
    store.PROCS.pop(key)
    worker["state"] = "dying"
    worker["outbound"].put_nowait(store.STOP)
    store.say(it, store.event(f"worker reaped {why}"), sess=key[1])
    queue_reap(worker)


def reap_idle() -> None:
    """Drop idle workers under two rules. Anything idle past IDLE_TTL goes.
    Beyond that, the workers of autopilot items are held to NIGHT_WORKER_CAP,
    counting the running ones, oldest idle first. A session the auto compact
    covers is compacted in place of the drop, and a later pass drops it."""
    now = time.time()
    changed = 0
    with store.LOCK:
        for key, worker in list(store.PROCS.items()):
            it = reapable(key, worker)
            since = worker.get("idle_since")
            if it is None or now - since < config.IDLE_TTL:
                continue
            if compact_before_reap(it, key, worker, now):
                changed += 1
                continue
            drop_worker(it, key, worker,
                        f"after {int((now - since) // 60)}m idle")
            changed += 1
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
                if compact_before_reap(it, key, worker, now):
                    changed += 1
                    continue
                drop_worker(it, key, worker,
                            f"over the {config.NIGHT_WORKER_CAP}-worker autopilot cap")
                changed += 1
    if changed:
        store.bump()


def compact_due(it: dict, phase: str, worker: dict | None, now: float) -> float | None:
    """Seconds until the session's cache goes cold or the idle reap takes its
    worker, whichever comes first; None when the session is not one the auto
    compact covers: it must be an unapproved finalize session with an idle
    worker, nothing pending, and no compact since its last real turn."""
    if phase != "finalize" or it["state"] != store.NEEDS_REVIEW \
            or not it["sessions"].get(phase) or store.active(it) \
            or it.get("auto_compacted", {}).get(phase):
        return None
    if worker is None or reapable((it["id"], phase), worker) is None:
        return None
    la = (it.get("lastActive") or {}).get(phase)
    if not la:
        return None
    return min(la / 1000 + config.CACHE_TTL,
               worker["idle_since"] + config.IDLE_TTL) - now


def start_compact(it: dict, phase: str, why: str) -> bool:
    """Open the compact turn on a session, marked so that no second auto
    compact follows before a real turn lands. True when the turn went out.
    Caller holds LOCK."""
    store.say(it, store.event(f"auto compact — {why}"), sess=phase)
    try:
        workers.launch(it, "/compact", phase)
    except (store.Reject, OSError) as exc:
        # the turn never went out, so the session is still owed its compact
        store.say(it, store.event(f"auto compact failed: {exc}"), sess=phase)
        return False
    it.setdefault("auto_compacted", {})[phase] = True
    return True


def compact_before_reap(it: dict, key: tuple[str, str], worker: dict,
                        now: float) -> bool:
    """Compact a session the auto compact covers instead of reaping it, so
    the reap takes a compacted session on a later pass. True when the compact
    turn went out; on False the caller reaps the worker, which covers a
    compact whose launch was refused. Caller holds LOCK."""
    if not store.auto()["compact"] or compact_due(it, key[1], worker, now) is None:
        return False
    return start_compact(it, key[1], "before the worker is reaped")


def auto_compact() -> None:
    """Compact the unapproved finalize sessions that are about to lose their
    cache or their worker, so a later comment resumes on the summary rather
    than re-reading the whole context cold. One compact per real turn: the
    compact's own landing does not arm another, and neither does a compact
    the user asked for."""
    now = time.time()
    launched = 0
    with store.LOCK:
        if not store.auto()["compact"]:
            return
        for it in list(store.STATE["items"]):
            phase = it["phase"]
            left = compact_due(it, phase, store.PROCS.get((it["id"], phase)), now)
            if left is None or left > config.COMPACT_MARGIN:
                continue
            start_compact(it, phase, f"cache expires in {max(0, int(left // 60))}m")
            launched += 1
    if launched:
        store.bump()


def idle_loop() -> None:
    while True:
        time.sleep(config.IDLE_POLL)
        if store.SHUTTING_DOWN or store.RELOADING:
            continue
        for step in (auto_compact, reap_idle, expire_holds):
            try:
                step()
            except Exception as exc:
                print(f"{step.__name__} failed: {exc}", file=sys.stderr)


def expire_holds(force: bool = False) -> None:
    """End a handoff hold whose background task never reported, or every
    hold when forced: a restart drops the outstanding set with the process,
    so the holds it finds have nothing left to wait on. A report the stage
    filed lands, through its callout turn; without one the chain stops here
    for the user to rule on."""
    expired = False
    with store.LOCK:
        for it in list(store.STATE["items"]):
            phase = it.get("bg_wait")
            if not phase:
                continue
            if not force and store.now() - it.get("bg_at", 0) < config.BG_TTL:
                continue
            worker = store.PROCS.get((it["id"], phase))
            if worker and worker["state"] != "idle":
                continue  # a turn is running; its landing settles the hold
            landing.drop_hold(it, phase)
            why = "a console restart" if force else f"{config.BG_TTL // 60}m"
            if (it.get("reports") or {}).get(phase):
                store.say(it, store.event(f"handoff hold ended after {why} — "
                                          "the filed report lands"), sess=phase)
                try:
                    landing.ask_callouts(it, phase)
                except (store.Reject, OSError) as exc:
                    store.say(it, store.event(f"callout turn failed: {exc}"), sess=phase)
                    it["state"] = store.NEEDS_REVIEW
                    it["updated"] = True
            else:
                store.say(it, store.event(f"handoff hold ended after {why} — no report"),
                          sess=phase)
                it["state"] = store.NEEDS_REVIEW
                it["updated"] = True
            expired = True
    if expired:
        store.bump()
