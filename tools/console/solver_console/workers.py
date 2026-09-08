"""A worker's turns: the launch that opens one, the steer that reaches one
already in flight, the handoff to the next stage, and the relaunch a turn
that ran away gets."""

import json
import re
import time
import uuid
from pathlib import Path

from . import config, landing, pacing, process, prompts, solvers, store

# Thinking tokens with no tool call or text before the feed says so. Well
# above a working turn's bursts, and far enough below the 64k output cap that
# the warning still arrives with the generation in progress.
RUNAWAY_THINK = 40_000
# Seconds between transcript reads. The CLI resubmits a capped generation on
# its own and the retry carries none of the thinking, so every poll of delay
# risks another full output budget spent on the same dead end.
CAP_POLL = 5


# edits land already clean.
CLEAN_TRIGGERS = ("cleanup",)
CLEANUP_RE = re.compile(r"\bcleanup\b")


def clean_trigger(text: str) -> str | None:
    """The clean pass a message asks for. `cleanup` counts anywhere in the
    message, since it is often the tail of a longer instruction."""
    return "cleanup" if CLEANUP_RE.search(text.lower()) else None


def launch(it: dict, message: str, phase: str, trigger: str | None = None,
           handoff: bool = False, admitted: bool = False,
           escalated: bool = False) -> None:
    """Spawn the phase worker if needed, then enqueue one turn. The nudge and
    the bail are turns of one chain and keep its count; every other turn starts
    its own, so a turn asked to think hard is judged on its own stretches."""
    if store.RELOADING and not admitted:
        raise store.Reject("server reload in progress")
    if not escalated:
        it.setdefault("runaway", {}).pop(phase, None)
    # Any turn except the callout ask and its continuations (resume, nudge,
    # bail) supersedes a pending callout landing, so a stale marker cannot
    # claim a later turn's text for the report.
    if trigger not in ("callout", "resume", "nudge", "bail"):
        if it.get("callout_wait") == phase:
            it.pop("callout_wait", None)
        if it.get("landing_compact") == phase:
            it.pop("landing_compact", None)
    # A held handoff is the console's own ask, still owed. Any other turn takes
    # the pass over, and the hold goes with it.
    if trigger not in ("handoff", "resume", "nudge", "bail"):
        landing.drop_hold(it, phase)
    # The CLI reads a slash command only when it opens the message, so a turn
    # carrying one skips the notices below and leaves them, and the watermarks
    # behind them, for the next real turn to deliver.
    slash = message.startswith("/")
    rv = it.get("reverted")
    key = (it["id"], phase)
    worker = store.PROCS.get(key)
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
        if seen is not None and seen != solvers.solver_hash(it["id"]):
            message = ("<system-reminder>programs/solvers/"
                       f"{it['id']}.dl changed on disk since your last turn. "
                       "Re-read before editing.</system-reminder>\n\n" + message)
        # A resident worker keeps the appendix its system prompt was built
        # from, so its cached prefix holds; it hears that the sources moved on.
        if worker is not None and str(prompts.append_path()) != it["append"]:
            message = ("<system-reminder>Your system prompt's copy of docs/wf-solver and "
                       "programs/lib.dl is behind the files. Before you "
                       "use a primitive, read `uv run python scripts/context.py` "
                       "or the lib.dl sections you need.</system-reminder>\n\n"
                       + message)
    it["last_turn_phase"] = phase
    if worker is None:
        if it["sessions"].get(phase):
            store.say(it, store.event("worker restarting — resuming its session"),
                      sess=phase)
        # A fresh process has no cached prefix to lose, so it reads the
        # appendix as it stands; under unchanged sources the content hash
        # returns the same file.
        it["append"] = str(prompts.append_path())
        worker = process.spawn_worker(it, phase)
    start_turn(it, worker, phase, trigger=trigger, handoff=handoff, slash=slash)
    # the message as sent, which is how its transcript row reads
    worker["ask"] = message
    worker["outbound"].put_nowait({"type": "user",
        "message": {"role": "user", "content": message}})


def start_turn(it: dict, worker: dict, phase: str, trigger: str | None = None,
               handoff: bool = False, slash: bool = False,
               state: str = "sending") -> None:
    """Open a turn's bookkeeping: the snapshot its landing diffs against, and
    the counters it fills. Every turn passes through here, the ones the console
    sends and the one it adopts."""
    if not store.busy_elsewhere(it, phase):
        # a side turn leaves the snapshot with the turn that owns the solver
        it["pre"] = {"hash": solvers.solver_hash(it["id"]), "solver": solvers.solver_text(it["id"]),
                     "proposals": solvers.prop_files(), "dirty": it["dirty"], "files": {},
                     "watched": solvers.watched_hashes(it["id"])}
    worker["turn_seq"] += 1
    worker.pop("steer", None)
    worker.pop("woke", None)
    worker.update(state=state, started=time.time(), trigger=trigger,
                  handoff=handoff, slash=slash, seen=set(), got_result=False,
                  think_run=0, reqs={}, launch={}, touched=set(), compacted=False,
                  idle_since=None)


def steer(it: dict, worker: dict, text: str, phase: str) -> None:
    """Send a message into a turn already running. The CLI hands it over at the
    turn's next tool boundary and the turn absorbs it, so no bookkeeping opens
    here: the turn keeps its snapshot, its count, and its one landing. A clean
    pass the message asks for still reaches the turn it steers."""
    trigger = clean_trigger(text)
    if trigger and not worker.get("trigger"):
        worker["trigger"] = trigger
    worker["steer"] = {"trigger": trigger, "at": time.time()}
    store.say(it, {"kind": "steer", "text": text}, sess=phase)
    worker["outbound"].put_nowait({"type": "user",
        "message": {"role": "user", "content": text}})


def adopt_turn(it: dict, worker: dict, phase: str) -> None:
    """Take over a turn the worker starts by itself: the one a steer opens when
    it reaches the worker just after the turn it was meant for landed, and the
    one a background task opens when its notification wakes the session. init
    opens every turn and arrives before the turn's first action, so the
    snapshot still holds the pre-turn files. A turn left unadopted lands
    nothing: its text, its edits, and its cost all go unread."""
    pending = worker.pop("steer", None)
    start_turn(it, worker, phase,
               trigger=(pending or {}).get("trigger"), state="running")
    if it["state"] not in store.ACTIVE:
        it["state"] = store.COMMENTED
        it["updated"] = False
    why = ("message reached the worker as the turn landed"
           if pending else "a background task woke the session")
    store.say(it, store.event(why), sess=phase)


def detach_for_respawn(it: dict, worker: dict) -> None:
    """Take a worker out of PROCS ahead of a relaunch on the drain thread,
    and mark the item busy until that relaunch lands. Without the mark the
    item reads as idle in between: a comment would open a turn of its own on
    the session, and a reload would exec with the relaunch still queued.
    Caller holds LOCK."""
    key = (worker["item_id"], worker["phase"])
    if store.PROCS.get(key) is worker:
        store.PROCS.pop(key)
        worker["state"] = "dying"
        worker["outbound"].put_nowait(store.STOP)
    it["respawn_wait"] = worker["phase"]


def respawn_done(it: dict, phase: str) -> None:
    """Lift the relaunch mark. Caller holds LOCK, with the fresh worker in
    PROCS or the item landed."""
    if it.get("respawn_wait") == phase:
        it.pop("respawn_wait", None)


def transcript_of(session: str) -> Path | None:
    """The CLI's own record of a session."""
    return next(iter(config.PROJECTS.glob(f"*/{session}.jsonl")), None)


def tail_rows(worker: dict, session: str) -> list[dict]:
    """Assistant messages the transcript gained since the last read. The
    first read only marks the position, so a resumed session's history stays
    behind us. Subagent rows belong to their own context and are skipped."""
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
        if row.get("isSidechain"):
            continue
        if row.get("type") == "assistant":
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
    with store.LOCK:
        for worker in list(store.PROCS.values()):
            if (worker["state"] not in ("sending", "running")
                    or worker.get("escalate")):
                continue
            it = store.find(worker["item_id"])
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
    store.say(it, store.event(f"⚠ runaway thinking — {note} "
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
        process.reap(worker)
    with store.LOCK:
        it = store.find(worker["item_id"])
        if not it:
            return
        phase = worker["phase"]
        try:
            session = it["sessions"].get(phase)
            path = transcript_of(session) if session else None
            if path is not None:
                try:
                    if patch_capped(path):
                        store.say(it, store.event("capped thinking preserved"),
                                  sess=phase)
                except OSError as exc:
                    store.say(it, store.event(f"transcript patch failed: {exc}"),
                              sess=phase)
            escalate_turn(it, phase, step, handoff)
        finally:
            respawn_done(it, phase)
    store.bump()


def escalate_turn(it: dict, phase: str, step: str, handoff: bool) -> None:
    """Relaunch after a runaway interrupt lands. Caller holds LOCK and has
    reset the worker. The nudge keeps the turn's own handoff flag. A bail on a
    non-final stage asks for the report whose landing hands off; the final
    stage has no stronger session to receive it, so the item lands for review.
    A bail that itself runs away has said its piece twice, so the item lands
    either way."""
    count = it.get("runaway", {}).get(phase, 0)
    if step == "nudge":
        launch(it, prompts.NUDGE_BRIEF, phase, trigger="nudge", handoff=handoff,
               admitted=True, escalated=True)
    elif store.next_stage(it, phase) and count <= 2:
        launch(it, prompts.BAIL_BRIEF, phase, trigger="bail", handoff=True,
               admitted=True, escalated=True)
    else:
        store.turn_died(it, phase)


def auto_advances(it: dict, phase: str) -> bool:
    """Whether a report landing at `phase` hands the item on by itself.

    `auto_stop` names a stage auto-advance will not launch, so a run can carry
    items through the cheap stages and stop before an expensive one. Without
    it, auto-advance runs the whole chain. The auto finalize setting lifts the
    stop when the stage it names is finalize, unless the autopilot is on with
    a finalize slot: then its admitter is the only way into finalize, so the
    pacer gates every start."""
    if not it.get("auto_advance"):
        return False
    nxt = store.next_stage(it, phase)
    if not nxt:
        return False
    if nxt["name"] != it.get("auto_stop"):
        return True
    if nxt["name"] != "finalize" or not store.auto()["finalize"]:
        return False
    return not pacing.admitter_owns_finalize(pacing.night())


def advance_stage(it: dict) -> None:
    """Move the item on to the next stage and enqueue its first turn."""
    nxt = store.next_stage(it, it["phase"])
    if nxt is None:
        return
    if store.RELOADING:
        it["state"] = store.NEEDS_REVIEW
        it["updated"] = True
        store.say(it, store.event("handoff paused for server reload"))
        return
    prev, it["phase"] = it["phase"], nxt["name"]
    # A new stage is a new session, so it reads the appendix as it stands;
    # under unchanged sources the content hash returns the wave's shared
    # file, and the cached prefix holds.
    it["append"] = str(prompts.append_path())
    it["state"] = store.RUNNING
    store.say(it, store.event(f"handoff — {nxt['name']} session starting"))
    # A stage with a successor opens its pass under the handoff flag, so its
    # landing hands the chain on the way the first stage's does.
    more = store.next_stage(it, nxt["name"]) is not None
    launch(it, prompts.advance_message(it, prev, more), nxt["name"], handoff=more)


def detach_workers(item_id: str) -> list[dict]:
    workers = []
    for key, worker in list(store.PROCS.items()):
        if key[0] == item_id and store.PROCS.get(key) is worker:
            store.PROCS.pop(key)
            worker["state"] = "dying"
            worker["outbound"].put_nowait(store.STOP)
            workers.append(worker)
    return workers
