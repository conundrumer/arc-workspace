"""The overnight admitter: the resumes that came due, and the next
admission into each slot of the active source: a queue task, the next
unfinalized solver's finalize pass, or one of each."""

import re
import sys
import threading
from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import backlog, pacing, prompts, store, waves, workers

# Dial name -> the range the UI may set it to.
NIGHT_DIALS = {"target": (1, 40), "finalize_target": (1, 40), "reserve": (0, 100),
               "floor": (0, 100)}
ADMIT_POLL = 30        # seconds between admitter passes
END_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


NIGHT_WAKE = threading.Event()


def end_epoch(hhmm: str) -> float:
    """The next time the clock reads `hhmm`: today if that is still ahead,
    else tomorrow. So an end the user sets is never already past."""
    now = datetime.fromtimestamp(store.now())
    at = now.replace(hour=int(hhmm[:2]), minute=int(hhmm[3:]), second=0, microsecond=0)
    if at <= now:
        at += timedelta(days=1)
    return at.timestamp()


def end_label(epoch: float) -> str:
    return datetime.fromtimestamp(epoch).strftime("%H:%M")


def night_off(cfg: dict, why: str) -> None:
    """Turn the mode off. Turns in flight run on; the admitter stops. The
    end belongs to the run it ended, so it goes with it. Caller holds
    LOCK."""
    cfg["on"] = False
    cfg["wave"] = None
    cfg["end"] = None
    pacing.night_say("autopilot off" + (" · " + why if why else ""))


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
    live = store.PROCS.get((it["id"], phase)) is not None
    brief = (pacing.RESUME_BRIEF
             + (pacing.RESUME_AGENTS_LIVE if live else pacing.RESUME_AGENTS_GONE)
             + (pacing.RESUME_HANDOFF_NOTE if handoff else ""))
    store.say(it, {"kind": "you", "text": brief}, sess=phase)
    pacing.night_say(f"{it['id']} · resuming {phase}")
    workers.launch(it, brief, phase, trigger="resume", handoff=handoff,
                   admitted=True)


@dataclass
class TickInputs:
    """What one admitter pass read for its slots: the queue script's next
    tasks, the unfinalized rows, and the refusal a failed queue script
    returned in place of its rows."""

    queue: list[tuple[str, int]] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)
    refusal: store.Reject | None = None


def queue_next(inputs: TickInputs) -> list[tuple[str, int]]:
    """The next queue task the console does not already hold, out of the rows
    the pass read. A queue script that failed carries its refusal here, and
    the caller takes it as its own. The rows were read with LOCK down, so a
    task admitted since then is dropped again. Caller holds LOCK."""
    if inputs.refusal is not None:
        raise inputs.refusal
    existing = {it["id"] for it in store.STATE["items"]}
    return [row for row in inputs.queue if row[0] not in existing][:1]


def night_admit(inputs: TickInputs) -> list[str]:
    """Admit the next queued task into the night's wave. Caller holds LOCK.

    Every admission of one night belongs to one wave, so the committed items
    of the round before are cleared out the way a hand-started wave clears
    them."""
    cfg = pacing.night()
    waves.drop_committed()
    try:
        picked = queue_next(inputs)
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


def night_finalize(inputs: TickInputs) -> list[str]:
    """Start the finalize pass of the next unfinalized solver, in the
    autopilot's finalize order. Caller holds LOCK.

    A task the console holds is a candidate only when its item is done up to
    finalize: one mid-chain, cut, or already finalizing is passed over in
    silence, since the list carries every solver on disk. A worker that fails
    to start ends the pass, as the cause holds for every row."""
    cfg = pacing.night()
    for row in inputs.rows:
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


# What the admitter last found when it asked whether finalize work waits.
# The question costs a scan of the solvers and a git call, so the view reads
# the pass's answer rather than asking again on every poll.
FINALIZE_WAITING = False


def finalize_waiting(inputs: TickInputs) -> bool:
    """Whether the finalize slot has a solver to take, read without taking
    it: the same test night_finalize applies to each row."""
    global FINALIZE_WAITING
    FINALIZE_WAITING = False
    for row in inputs.rows:
        it = store.find(row["id"])
        if it is None or backlog.finalize_ready(it):
            FINALIZE_WAITING = True
            break
    return FINALIZE_WAITING


# What the admitter last found when it asked whether queue work waits. The
# question shells out to the queue script, so the view reads the pass's
# answer rather than asking again on every poll.
QUEUE_WAITING = False


def queue_waiting(inputs: TickInputs) -> bool:
    """Whether the queue slot has a task to take, read without taking it: the
    pick night_admit would make. A queue script that refused reads as nothing
    waiting."""
    global QUEUE_WAITING
    try:
        QUEUE_WAITING = bool(queue_next(inputs))
    except store.Reject:
        QUEUE_WAITING = False
    return QUEUE_WAITING


# The other slot of the both source.
OTHER_SLOT = {"queue": "finalize", "finalize": "queue"}


def slot_waiting(kind: str, inputs: TickInputs, probe: bool = True) -> bool:
    """Whether the slot of `kind` has work to take. `probe` reads the pass's
    rows; the view takes the last answer."""
    if kind == "finalize":
        return finalize_waiting(inputs) if probe else FINALIZE_WAITING
    return queue_waiting(inputs) if probe else QUEUE_WAITING


def slot_gate(cfg: dict, kind: str, inputs: TickInputs | None = None,
              probe: bool = True) -> dict:
    """The slot's gate: the pacer over the slot's models, and the hold that
    lets the other slot go first while its window trails, it has room under
    its target, and work waits for it."""
    gate = pacing.pacer(models=pacing.slot_models(kind))
    if gate["open"] and kind in OTHER_SLOT:
        hold = pacing.lead_hold(cfg, kind)
        other = OTHER_SLOT[kind]
        room = pacing.slot_live(cfg, other) < pacing.slot_target(cfg, other)
        if hold and room and slot_waiting(other, inputs or TickInputs(), probe):
            gate = {**gate, "open": False, "hold": hold[0], "why": hold[1]}
    return gate


def tick_inputs(kinds: list[str], held: Collection[str]) -> TickInputs:
    """What the slots of `kinds` are read for, taken with LOCK down: the queue
    script's next tasks, and the unfinalized rows in the autopilot's finalize
    order; building those rows takes a git read. A slot at its target is left
    unread, and the pass leaves it alone.

    A pass admits one queue task and asks whether another waits behind it, so
    it takes two rows past the tasks `held` names."""
    inputs = TickInputs()
    if "queue" in kinds:
        try:
            inputs.queue = waves.queue_pick(2, "name", held)
        except store.Reject as exc:
            inputs.refusal = exc
    if "finalize" in kinds:
        inputs.rows = backlog.pass_view(backlog.solver_ages())
    return inputs


def night_tick() -> dict:
    """One admitter pass: the resumes that came due, then one admission into
    each slot of the active source that is free and whose gate is open. The
    counts are read again for each slot, so an admission into the first is
    seen by the second.

    A pass reads the queue script and git between the two stretches it holds
    LOCK: every worker reader thread and every poll waits on that lock, and a
    pass runs every 30 seconds."""
    out = {"resumed": [], "admitted": [], "held": None}
    changed = False
    stagger = []
    with store.LOCK:
        cfg = pacing.night()
        if cfg["on"] and cfg["end"] and cfg["end"] <= store.now():
            night_off(cfg, "scheduled end " + end_label(cfg["end"]))
            changed = True
        if not cfg["on"] or store.RELOADING or store.SHUTTING_DOWN:
            if changed:
                store.bump()
            return out
        for it in due_resumes():
            resume_item(it)
            out["resumed"].append(it["id"])
            changed = True
        slots = pacing.slot_order(cfg)
        free = [kind for kind in slots
                if pacing.slot_live(cfg, kind) < pacing.slot_target(cfg, kind)]
        held = {it["id"] for it in store.STATE["items"]}
    inputs = tick_inputs(free, held)
    with store.LOCK:
        holds = []
        # The reads run with LOCK down, and a reload, a shutdown, or the user
        # turning autopilot off lands in that stretch. Each of them calls the
        # admission off, the way the pass's first stretch reads them.
        if not pacing.night()["on"] or store.RELOADING or store.SHUTTING_DOWN:
            slots = []
        for kind in slots:
            # a slot the pass did not read for was at its target when it
            # looked, and has nothing to admit from
            if kind not in free or \
                    pacing.slot_live(cfg, kind) >= pacing.slot_target(cfg, kind):
                continue
            gate = slot_gate(cfg, kind, inputs)
            if gate["open"]:
                ids = (night_finalize(inputs) if kind == "finalize"
                       else night_admit(inputs))
                out["admitted"] += ids
                if kind == "queue":
                    stagger = ids
                changed = changed or bool(ids)
            else:
                holds.append((kind, gate["hold"]))
        if holds:
            # one hold for every slot reads once; anything else names the slots
            same = len(holds) == len(slots) and len({h for _, h in holds}) == 1
            out["held"] = holds[0][1] if same else \
                ", ".join(f"{kind}: {h}" for kind, h in holds)
            changed |= pacing.night_say("hold · " + out["held"], once=True)
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
             "gate": slot_gate(cfg, kind, probe=False) if cfg["on"] else None}
            for kind in pacing.slot_order(cfg)]


def joint_gate(slots: list[dict]) -> dict | None:
    """One gate over the slots: open while any slot's is, with the line the
    panel prints as `verdict`. Slots that read the same give one verdict;
    slots that differ are named."""
    live = [s for s in slots if s["gate"]]
    if not live:
        return None
    gates = [s["gate"] for s in live]
    out = dict(gates[0])
    out["open"] = any(g["open"] for g in gates)
    if len({(g["open"], g["why"]) for g in gates}) == 1:
        out["why"] = gates[0]["why"]
        out["verdict"] = "open" if out["open"] else "held · " + out["why"]
    else:
        out["why"] = out["verdict"] = ", ".join(
            f"{s['kind']} open" if s["gate"]["open"]
            else f"{s['kind']} held ({s['gate']['why']})" for s in live)
    return out


def night_view() -> dict:
    """What the console shows for the mode."""
    cfg = pacing.night()
    view = {name: cfg[name] for name in pacing.NIGHT_DEFAULTS}
    slots = slots_view(cfg)
    gate = joint_gate(slots)
    soon = [(it["resume_at"], f"{it['id']} resumes") for it in store.STATE["items"]
            if it.get("resume_at")]
    if cfg["on"] and cfg["end"]:
        soon.append((cfg["end"], "autopilot ends"))
    if cfg["on"] and not soon:
        soon.append((store.now() + ADMIT_POLL, "pass"))
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
        if "balance" in body and bool(body["balance"]) != cfg["balance"]:
            cfg["balance"] = bool(body["balance"])
            if cfg["on"]:
                pacing.night_say("balance · " + ("on" if cfg["balance"] else "off"))
        for name, choices in (("source", pacing.NIGHT_SOURCES), ("pace", pacing.PACE_MODES)):
            if name not in body:
                continue
            if body[name] not in choices:
                return {"error": f"{name} must be one of " + ", ".join(choices)}
            if body[name] != cfg[name]:
                cfg[name] = body[name]
                if cfg["on"]:
                    pacing.night_say(f"{name} · {cfg[name]}")
        if "end" in body:
            # a clock time, or nothing for no end; the epoch is the next time
            # the clock reads it, so it is ahead of now when it is set
            end = body["end"]
            if end in (None, ""):
                if cfg["end"] is not None:
                    cfg["end"] = None
                    if cfg["on"]:
                        pacing.night_say("end · none")
            elif not isinstance(end, str) or not END_TIME.match(end):
                return {"error": "end must be a clock time, HH:MM"}
            else:
                cfg["end"] = end_epoch(end)
                if cfg["on"]:
                    pacing.night_say("end · " + end)
        if "on" in body and bool(body["on"]) != cfg["on"]:
            if body["on"]:
                cfg["on"] = True
                wk = pacing.window("wk")
                cfg.update(since=store.now(), wave=None, append=None,
                           wk_start=wk["pct"] if wk else None,
                           wk_start_at=store.now() if wk else None)
                if cfg["end"] and cfg["end"] <= store.now():
                    # set for a run that never came; it would end this one at once
                    cfg["end"] = None
                slots = pacing.SOURCE_SLOTS[cfg["source"]]
                targets = (f"target {cfg['target']} · finalize target {cfg['finalize_target']}"
                           if len(slots) > 1 else f"target {pacing.slot_target(cfg, slots[0])}")
                ends = f" · ends {end_label(cfg['end'])}" if cfg["end"] else ""
                pacing.night_say(f"autopilot on · {cfg['source']} · {targets}{ends}")
            else:
                night_off(cfg, "")
        NIGHT_WAKE.set()
    store.bump()
    return {"ok": True}
