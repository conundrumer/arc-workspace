"""The overnight admitter: the resumes that came due, and the next
admission into each slot of the active source: a queue task, the next
unfinalized solver's finalize pass, or one of each."""

import sys
import threading

from . import backlog, pacing, prompts, store, waves, workers

# Dial name -> the range the UI may set it to.
NIGHT_DIALS = {"target": (1, 40), "finalize_target": (1, 40), "reserve": (0, 100),
               "floor": (0, 100), "ceiling": (0, 100)}
ADMIT_POLL = 30        # seconds between admitter passes


NIGHT_WAKE = threading.Event()


def due_resumes() -> list[dict]:
    at = store.now()
    return [it for it in store.STATE["items"]
            if it.get("resume_at") and it["resume_at"] <= at and not store.active(it)]


def resume_item(it: dict) -> None:
    """Relaunch the stage a usage limit cut off, as a comment would. Caller
    holds LOCK."""
    phase = it.pop("resume_phase", None) or it["phase"]
    handoff = bool(it.pop("resume_handoff", False))
    it.pop("resume_at", None)
    if not it["sessions"].get(phase):
        store.say(it, store.event("no session to resume — left for review"), sess=phase)
        pacing.night_say(f"{it['id']} · no session to resume, left for review")
        return
    it["state"] = store.COMMENTED
    it["updated"] = False
    brief = pacing.RESUME_BRIEF + (pacing.RESUME_HANDOFF_NOTE if handoff else "")
    store.say(it, {"kind": "you", "text": brief}, sess=phase)
    pacing.night_say(f"{it['id']} · resuming {phase}")
    workers.launch(it, brief, phase, trigger="resume", handoff=handoff,
                   admitted=True)


def night_admit() -> list[str]:
    """Admit the next queued task into the night's wave. Caller holds LOCK.

    Every admission of one night belongs to one wave, so the committed items
    of the round before are cleared out the way a hand-started wave clears
    them."""
    cfg = pacing.night()
    waves.drop_committed()
    try:
        picked = waves.pick_new(1, "name")
    except store.Reject as e:
        pacing.night_say(f"admission deferred — {e}", once=True)
        return []
    if not picked:
        pacing.night_say("queue is empty", once=True)
        return []
    chain = store.default_chain()
    if not cfg.get("wave"):
        store.STATE["wave"] += 1
        cfg["wave"] = store.STATE["wave"]
    ids = waves.make_items(picked, chain, cfg["wave"], str(prompts.append_path()),
                           night=True)
    pacing.night_say("admitted " + ", ".join(ids) + " · create"
                     f" · {pacing.slot_live(cfg, 'queue')}/{cfg['target']} live")
    return ids


def night_finalize() -> list[str]:
    """Start the finalize pass of the next unfinalized solver, in triage
    order. Caller holds LOCK.

    A task the console holds is a candidate only when its item is done up to
    finalize: one mid-chain, cut, or already finalizing is passed over in
    silence, since the list carries every solver on disk. A worker that fails
    to start ends the pass, as the cause holds for every row."""
    cfg = pacing.night()
    for row in backlog.backlog_view():
        it = store.find(row["id"])
        if it is not None and not backlog.finalize_ready(it):
            continue
        res = backlog.start_finalize(row["id"])
        if "error" in res:
            pacing.night_say(f"{row['id']} · finalize not started — {res['error']}",
                             once=True)
            return []
        pacing.night_say(f"admitted {row['id']} · finalize"
                         f" · {pacing.slot_live(cfg, 'finalize')}/{cfg['finalize_target']} live")
        return [row["id"]]
    pacing.night_say("nothing to finalize", once=True)
    return []


def night_tick() -> dict:
    """One admitter pass: the resumes that came due, then one admission into
    each slot of the active source that is free and whose gate is open. The
    counts are read again for each slot, so an admission into the first is
    seen by the second."""
    out = {"resumed": [], "admitted": [], "held": None}
    changed = False
    stagger = []
    with store.LOCK:
        cfg = pacing.night()
        if not cfg["on"] or store.RELOADING or store.SHUTTING_DOWN:
            return out
        for it in due_resumes():
            resume_item(it)
            out["resumed"].append(it["id"])
            changed = True
        slots = pacing.SOURCE_SLOTS[cfg["source"]]
        held = []
        for kind in slots:
            if pacing.slot_live(cfg, kind) >= pacing.slot_target(cfg, kind):
                continue
            gate = pacing.pacer(models=pacing.slot_models(kind))
            if gate["open"]:
                ids = night_finalize() if kind == "finalize" else night_admit()
                out["admitted"] += ids
                if kind == "queue":
                    stagger = ids
                changed = changed or bool(ids)
            else:
                # under both the line names the slot, since the other may be open
                held.append(f"{kind}: {gate['why']}" if len(slots) > 1 else gate["why"])
        if held:
            out["held"] = " · ".join(held)
            changed |= pacing.night_say("pacer holding: " + out["held"], once=True)
    if stagger:
        threading.Thread(target=waves.stagger_launch, args=(stagger,),
                         daemon=True).start()
    if changed:
        store.bump()
    return out


def night_loop() -> None:
    while True:
        NIGHT_WAKE.wait(ADMIT_POLL)
        NIGHT_WAKE.clear()
        try:
            night_tick()
        except Exception as exc:  # a failed pass must not end the night
            print(f"overnight pass failed: {exc!r}", file=sys.stderr)


def slots_view(cfg: dict) -> list[dict]:
    """Each slot of the active source: its kind, what it holds against its
    target, and its gate while the mode is on."""
    return [{"kind": kind, "live": pacing.slot_live(cfg, kind),
             "target": pacing.slot_target(cfg, kind),
             "gate": pacing.pacer(models=pacing.slot_models(kind)) if cfg["on"] else None}
            for kind in pacing.SOURCE_SLOTS[cfg["source"]]]


def joint_gate(slots: list[dict]) -> dict | None:
    """One gate over the slots: open while any slot's is, with each slot's
    reason named when there is more than one."""
    gates = [s["gate"] for s in slots if s["gate"]]
    if not gates:
        return None
    if len(gates) == 1:
        return gates[0]
    out = dict(gates[0])
    out["open"] = any(g["open"] for g in gates)
    out["why"] = " · ".join(f"{s['kind']} {'open' if s['gate']['open'] else 'held'}: "
                            f"{s['gate']['why']}" for s in slots)
    nexts = [g["next"] for g in gates if g.get("next")]
    out["next"] = min(nexts) if nexts else None
    return out


def night_view() -> dict:
    """What the console shows for the mode."""
    cfg = pacing.night()
    view = {name: cfg[name] for name in pacing.NIGHT_DEFAULTS}
    slots = slots_view(cfg)
    gate = joint_gate(slots)
    soon = [(it["resume_at"], f"{it['id']} resumes") for it in store.STATE["items"]
            if it.get("resume_at")]
    if gate and gate.get("next"):
        soon.append((gate["next"], "squeeze zone opens"))
    if cfg["on"] and not soon:
        soon.append((store.now() + ADMIT_POLL, "admitter pass"))
    at, what = min(soon) if soon else (None, "")
    view.update(gate=gate, live=len(pacing.live_items()), landed=pacing.night_landed(),
                slots=[{k: v for k, v in s.items() if k != "gate"} for s in slots],
                log=cfg["log"][-8:],
                next=({"at": at, "what": what} if at else None))
    return view


def act_night(body: dict) -> dict:
    with store.LOCK:
        cfg = pacing.night()
        for name, (lo, hi) in NIGHT_DIALS.items():
            if name not in body:
                continue
            try:
                cfg[name] = max(lo, min(hi, int(body[name])))
            except (TypeError, ValueError):
                return {"error": f"{name} must be a number"}
        if "catchup" in body:
            cfg["catchup"] = bool(body["catchup"])
        if "source" in body:
            if body["source"] not in pacing.NIGHT_SOURCES:
                return {"error": "source must be one of " + ", ".join(pacing.NIGHT_SOURCES)}
            if body["source"] != cfg["source"]:
                cfg["source"] = body["source"]
                if cfg["on"]:
                    pacing.night_say(f"source · {cfg['source']}")
        if "on" in body and bool(body["on"]) != cfg["on"]:
            cfg["on"] = bool(body["on"])
            if cfg["on"]:
                wk = pacing.window("wk")
                cfg.update(since=store.now(), wave=None, append=None,
                           wk_start=wk["pct"] if wk else None,
                           wk_start_at=store.now() if wk else None)
                slots = pacing.SOURCE_SLOTS[cfg["source"]]
                targets = (f"target {cfg['target']} · finalize target {cfg['finalize_target']}"
                           if len(slots) > 1 else f"target {pacing.slot_target(cfg, slots[0])}")
                pacing.night_say(f"autopilot on · {cfg['source']} · {targets}")
            else:
                cfg["wave"] = None
                pacing.night_say("autopilot off")
        NIGHT_WAKE.set()
    store.bump()
    return {"ok": True}
