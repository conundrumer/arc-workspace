"""A turn that lands: the report it files, the callouts that follow it, the
hold a background task puts on a handoff, and the compact a finalize landing
owes."""

import difflib
import time

from . import config, drain, ledger, prompts, solvers, spend, store, workers


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
        shown = solvers.untagged(text)
        if match:
            match.clear()
            match.update(kind="report", rev=it["rev"], text=shown, sess=phase)
            store.touch(it)
        else:
            store.say(it, {"kind": "report", "rev": it["rev"], "text": shown}, sess=phase)
    store.say(it, store.event(spend.turn_note(it, ev, phase, started, reqs)), sess=phase)
    worker = store.PROCS.get((it["id"], phase))
    # A compact rebuilds the context, so the next turn reads a small cache by
    # design; the baseline starts over rather than flagging a drop.
    if worker and worker.get("compacted"):
        it.get("cache_read", {}).pop(phase, None)
    # A turn with no callouts says nothing about them, so the item keeps what
    # the last report that carried them left.
    if solvers.callout_body(text) is not None:
        it["callouts"] = solvers.parse_callouts(text)
        it["callout_n"] = len(it["callouts"])
        it["callout_rank"] = solvers.callout_rank(it["callouts"])
    # An entry the turn wrote under docs/wf-solver/proposals/ is the task's
    # proposal. It stays with the item, and the ledger line carries it, so
    # the backlog still knows once the item is gone. A concurrent turn adds
    # entries to the same directory, so only the turn's own edits count.
    after = solvers.prop_files()
    before = store.pre(it).get("proposals")
    new_entries = sorted((set(after) - set(before if isinstance(before, dict) else ()))
                         & set(store.pre(it)["files"]))
    if new_entries:
        it["entries"] = sorted(set(it.get("entries", [])) | set(new_entries))
    # The snapshot of every entry served the turn; what stays is the pair a
    # revert compares, for the entries the turn edited: their pre-turn text
    # is in `pre.files`, and their text as landed goes here.
    store.pre(it)["proposals"] = {}
    it["prop_after"] = {rel: text for rel, text in after.items()
                        if rel in store.pre(it)["files"]}
    ledger.ledger_append({"task": it["id"], "stage": phase,
                          "backend": store.backend_of(it, phase),
                          "model": store.model_of(it, phase),
                          "session": it["sessions"].get(phase), "ts": int(store.now()),
                          "source": "console",
                          **({"entries": new_entries} if new_entries else {})})
    # the create pass ends in prune, and every later pass is itself a quality
    # pass, so each stage's first landing is clean by the procedure
    landed = it.setdefault("landed", [])
    first_landing = phase not in landed
    if first_landing:
        landed.append(phase)
    if trigger in workers.CLEAN_TRIGGERS or first_landing:
        it["dirty"] = False
    elif solvers.solver_hash(it["id"]) != store.pre(it)["hash"]:
        it["dirty"] = True
    # The worker writes the draft tag with the solver (its brief). A landing
    # tags a file the session left untagged, so every landed solver reads as
    # unapproved until approval takes the tag off. The tag goes in below the
    # reads of what the session changed, so the console's own line is never
    # taken for the session's work. An approved item is one the user has
    # ruled on: a turn landing after that ruling leaves the file as the
    # approval left it, untagged.
    if it["state"] != store.APPROVED and solvers.mark_draft(it["id"]):
        # Every session of the item reads one snapshot of the file as the turn
        # found it, and a session that opened its turn while this one ran keeps
        # that snapshot to its own landing. The tag goes into the snapshot too,
        # so that landing reads the console's line as the file it was handed,
        # not as an edit of its own.
        store.pre(it)["hash"] = solvers.solver_hash(it["id"])
    if not store.slash_turn(it, phase):
        it.setdefault("seen_hash", {})[phase] = solvers.solver_hash(it["id"])
        # a real turn landed: the session may be auto-compacted once more
        it.get("auto_compacted", {}).pop(phase, None)
    # The compact hands its summary back as output, and nothing sends that
    # summary until the next real turn, so the session lands with its cache
    # cold: the stamp is set a full TTL back.
    now_ms = int(time.time() * 1000)
    if worker and worker.get("compacted") and store.slash_turn(it, phase):
        it["lastActive"][phase] = now_ms - config.CACHE_TTL * 1000
    else:
        it["lastActive"][phase] = now_ms
    it["title"] = solvers.title_of(it["id"]) or it.get("title", "")
    it["comps"] = solvers.comps_of(it["id"])
    it["comps_unproposed"] = solvers.unproposed(it["comps"], solvers.prop_text())
    it["landed_at"] = store.now()
    fresh = [rel for rel in store.shared_writes(it, (worker or {}).get("touched"))
             if rel not in it.setdefault("shared_writes", [])]
    if fresh:
        it["shared_writes"].extend(fresh)
        store.say(it, store.event("shared files changed: " + ", ".join(fresh)), sess=phase)
    it.pop("quota_retry", None)  # the stage got a turn through; retries reset
    if it.get("resume_phase") == phase and not store.slash_turn(it, phase):
        # a turn got through on the cut stage, so the pass went on without
        # the resume; one still scheduled would run it again
        for key in ("resume_at", "resume_phase", "resume_handoff"):
            it.pop(key, None)
    report = solvers.tagged(text, solvers.HANDOFF_TAG)
    callouts = solvers.tagged(text, solvers.CALLOUTS_TAG)
    callout_landing = it.get("callout_wait") == phase
    if callout_landing:
        it.pop("callout_wait", None)
    outstanding = sorted((worker or {}).get("bg", {}).values())
    if callout_landing:
        # a callout turn on an older brief answers with the section in
        # place of the block
        land_callouts(it, phase, callouts if callouts is not None else text)
    elif store.next_stage(it, phase) and (report is not None or handoff):
        hand_on(it, phase, text, report, callouts, worker, outstanding)
    elif it.get("bg_wait") == phase:
        settle_hold(it, phase, worker, outstanding)
    elif phase == "finalize" and it.get("auto_finalize") and not store.slash_turn(it, phase):
        land_auto_finalize(it, phase, text, report, callouts, worker, outstanding)
    elif not store.slash_turn(it, phase) and not store.busy_elsewhere(it, phase):
        # a side turn landing while another session runs leaves the state to
        # the pass that owns it
        to_review(it)


def to_review(it: dict) -> None:
    """Leave a landed item for the user. An approved item keeps its state:
    the user ruled on it, and a turn landing after that ruling does not take
    the ruling back. Caller holds LOCK."""
    it["updated"] = True
    if it["state"] != store.APPROVED:
        it["state"] = store.NEEDS_REVIEW


def owed(it: dict) -> str | None:
    """What the stage an item waits on still lacks of what its landing
    produces, when nothing is in flight to bring it: the handoff report, the
    callouts on that report, or the advance the chain would have made by
    itself. None for a stage that has it all, or one whose turn is still to
    land."""
    if it["state"] != store.NEEDS_REVIEW or store.active(it):
        return None
    phase = it["phase"]
    if store.next_stage(it, phase) is None:
        return None
    report = solvers.report_of(it, phase)
    if not report:
        return "report"
    if solvers.callout_body(report) is None:
        return "callouts"
    if workers.auto_advances(it, phase):
        return "handoff"
    return None


def owe(it: dict, kind: str, phase: str, worker: dict) -> None:
    """Queue a turn the landing owes the item. The count keeps a reload off
    the item until the drain has sent the turn, or set it aside. Caller holds
    LOCK."""
    it["owed"] = it.get("owed", 0) + 1
    store.DEFERRED.put_nowait((kind, it["id"], phase, worker["turn_seq"]))
    drain.ensure_drain()


def hand_on(it: dict, phase: str, text: str, report: str | None,
            callouts: str | None, worker: dict | None,
            outstanding: list[str]) -> None:
    """A landing on a stage with a successor. The block is the handoff,
    whichever turn carries it. A turn asked for one that ends without it is
    either waiting on a task it started, or missed the ask: the ask goes out
    once more, and a second miss files the text as written. Caller holds
    LOCK."""
    if report is None and worker and outstanding:
        hold_handoff(it, phase, outstanding)
        return
    if report is None:
        if worker and not it.get("reasked", {}).get(phase):
            it.setdefault("reasked", {})[phase] = True
            drop_hold(it, phase)
            store.say(it, store.event("no handoff block — asking again"), sess=phase)
            owe(it, "rehandoff", phase, worker)
            return
        store.say(it, store.event("no handoff block — the text stands as the report"),
                  sess=phase)
        report = text
    it.get("reasked", {}).pop(phase, None)
    drop_hold(it, phase)
    if worker and outstanding:
        hold_handoff(it, phase, outstanding, report)
    elif callouts is not None:
        # the turn wrote its callouts with the report: no callout turn
        file_report(it, phase, report)
        land_callouts(it, phase, callouts)
    else:
        land_handoff(it, phase, report)


def settle_hold(it: dict, phase: str, worker: dict | None,
                outstanding: list[str]) -> None:
    """A turn a background notification woke, with no block of its own: once
    nothing is outstanding, the held report lands, or the ask the hold owes
    goes out. Caller holds LOCK."""
    if worker and outstanding:
        it["bg_at"] = store.now()
        store.say(it, store.event("handoff held — " + ", ".join(outstanding)
                                  + " has not reported"), sess=phase)
    elif worker and it.get("bg_filed"):
        drop_hold(it, phase)
        land_handoff(it, phase, "")
    elif worker:
        drop_hold(it, phase)
        owe(it, "rehandoff", phase, worker)
    else:
        drop_hold(it, phase)
        to_review(it)


def land_auto_finalize(it: dict, phase: str, text: str, report: str | None,
                       callouts: str | None, worker: dict | None,
                       outstanding: list[str]) -> None:
    """The finalize pass auto-advance opened lands with no one reading it, so
    its first landing files the text as the stage report and asks for the
    callouts, which the finalize lens sorts on. A landing with a task still
    outstanding waits for the one that task wakes. Caller holds LOCK."""
    if worker and outstanding:
        to_review(it)
        return
    it.pop("auto_finalize", None)
    # the compact on landing waits for the callouts, so the marker rides to
    # their landing
    it["landing_compact"] = phase
    body = (report if report is not None
            else solvers.untagged(solvers.CALLOUTS_TAG.sub("", text))).strip()
    if callouts is None:
        land_handoff(it, phase, body)
    else:
        if body:
            file_report(it, phase, body)
        land_callouts(it, phase, callouts)


def hold_handoff(it: dict, phase: str, outstanding: list[str],
                 report: str = "") -> None:
    """Wait out the background tasks a handoff turn started.

    A background dispatch ends the turn before the task reports. A report the
    turn wrote is filed and lands once the tasks are in; without one, the
    notification wakes the session into a turn of its own, and when a
    landing finds nothing outstanding, the handoff ask goes out again."""
    if report:
        file_report(it, phase, report)
        it["bg_filed"] = True
    it["bg_wait"] = phase
    it["bg_at"] = store.now()
    store.say(it, store.event("handoff held — " + ", ".join(outstanding)
                              + " has not reported"), sess=phase)


def drop_hold(it: dict, phase: str) -> None:
    if it.get("bg_wait") == phase:
        it.pop("bg_wait", None)
        it.pop("bg_at", None)
        it.pop("bg_filed", None)


def solver_diff(it: dict, phase: str) -> str:
    """The unified diff from the solver as the stage found it, read at the
    stage's first turn, to the file as it stands. Empty when the stage has
    changed nothing."""
    before = (it.get("stage_pre") or {}).get(phase, "")
    after = solvers.solver_text(it["id"])
    rel = f"programs/solvers/{it['id']}.dl"
    return "\n".join(difflib.unified_diff(before.splitlines(), after.splitlines(),
                                          fromfile=rel, tofile=rel, lineterm=""))


def file_report(it: dict, phase: str, text: str) -> None:
    """A landing's text becomes the stage report, and the stage's solver diff
    is filed beside it; the next filing replaces both, so what stands is
    always the last thing the session wrote and the change it left."""
    diff = solver_diff(it, phase)
    it.setdefault("reports", {})[phase] = text
    it.setdefault("diffs", {})[phase] = diff
    solvers.save_report(it["id"], phase, text)
    solvers.save_diff(it["id"], phase, diff)


def land_handoff(it: dict, phase: str, text: str) -> None:
    """File a stage's report and ask for its callouts."""
    if text:
        file_report(it, phase, text)
    # the callouts get their own turn before any advance
    worker = store.PROCS.get((it["id"], phase))
    if worker:
        it["callout_wait"] = phase
        owe(it, "callout", phase, worker)
    else:
        it.pop("landing_compact", None)
        to_review(it)


def ask_callouts(it: dict, phase: str) -> None:
    """Open the callout turn on a stage whose report is filed and whose
    worker holds no turn: the reaped worker comes back on a resume. Caller
    holds LOCK."""
    it["callout_wait"] = phase
    it["state"] = store.RUNNING
    it["updated"] = False
    store.say(it, store.event("callout turn starting"), sess=phase)
    workers.launch(it, prompts.callout_brief(), phase, trigger="callout", admitted=True)


def land_callouts(it: dict, phase: str, body: str) -> None:
    """Join the callouts onto the stage report, so parsing and the finalize
    read see one document per stage, then advance. The final stage has
    nowhere to advance to and waits for the user."""
    if body.strip():
        section = (body if solvers.CALLOUT_HEAD.search(body)
                   else "## Callouts\n\n" + body.strip())
        combined = solvers.join_callouts(it.get("reports", {}).get(phase) or "",
                                         section)
        it.setdefault("reports", {})[phase] = combined
        solvers.save_report(it["id"], phase, combined)
    if workers.auto_advances(it, phase):
        it["handoff_pending"] = True
        worker = store.PROCS.get((it["id"], phase))
        if worker:
            owe(it, "handoff", phase, worker)
    else:
        to_review(it)
        compact_on_landing(it, phase)


def compact_on_landing(it: dict, phase: str) -> None:
    """Queue the compact a finalize landing the autopilot opened owes, once
    its callouts are in. The job reads the setting when it runs, and a turn
    the worker started since takes precedence. Caller holds LOCK."""
    if it.pop("landing_compact", None) != phase or not store.auto()["compact_landing"]:
        return
    worker = store.PROCS.get((it["id"], phase))
    store.DEFERRED.put_nowait(("compact", it["id"], phase,
                               worker["turn_seq"] if worker else None))
    drain.ensure_drain()
