"""The actions the console takes on an item, and the commit that ends a
round."""

import json
import os
import re
import signal
import subprocess
import threading
import time
import uuid

from . import config, drain, landing, overnight, process, prompts, solvers, store, workers


def submit_comment(it: dict, text: str, sess: str | None = None) -> None:
    text = text.strip()
    low = text.lower()
    if low in ("commit", "next"):
        raise store.Reject(f"`{text}` is a console action")
    if low == "handoff":
        store.require_idle(it)
        phase = it["phase"]
        if not store.next_stage(it, phase):
            raise store.Reject("final stage — nothing to hand off to")
        if not it["sessions"].get(phase):
            raise store.Reject("no session yet")
        store.say(it, {"kind": "you", "text": text}, sess=phase)
        it["state"] = store.COMMENTED
        it["updated"] = False
        workers.launch(it, prompts.HANDOFF_BRIEF, phase, handoff=True)
        return
    # a comment goes to one session, so only that session has to be idle —
    # an earlier stage can talk while the current pass runs
    sess = sess if sess in store.stage_names(it) else it["phase"]
    store.defer_reload()
    if it.get("handoff_pending", False):
        raise store.Reject("handoff in flight — wait for the next session")
    if it.get("respawn_wait") == sess:
        raise store.Reject("relaunch in flight — wait for the turn to land")
    w = store.PROCS.get((it["id"], sess))
    if w and w["state"] in ("sending", "running"):
        if text.startswith("/"):
            raise store.Reject("worker busy — a slash command counts only at the "
                               "head of a turn")
        if w.get("slash"):
            # a compact has no turn to absorb a steer; the message would be lost
            raise store.Reject("worker busy — a slash command is running; wait "
                               "for it to land")
        workers.steer(it, w, text, sess)
        return
    if w and w["state"] == "spawning":
        raise store.Reject("worker busy — wait for the turn to land")
    if not it["sessions"].get(sess):
        raise store.Reject("no session yet")
    store.say(it, {"kind": "you", "text": text}, sess=sess)
    if not text.startswith("/") and not store.busy_elsewhere(it, sess):
        it["state"] = store.COMMENTED
        it["updated"] = False
    workers.launch(it, text, sess, trigger=workers.clean_trigger(text))


act_comment = store.action(submit_comment)


@store.action
def act_compact(it: dict, sess: str | None = None) -> None:
    submit_comment(it, "/compact", sess)


@store.action
def act_approve(it: dict) -> None:
    if it["state"] != store.NEEDS_REVIEW:
        raise store.Reject("nothing to approve")
    store.require_idle(it)
    store.approve(it)


@store.action
def act_unapprove(it: dict) -> None:
    if it["state"] != store.APPROVED:
        raise store.Reject("not approved")
    it["state"] = store.NEEDS_REVIEW
    solvers.mark_draft(it["id"])
    store.say(it, store.event("approval withdrawn"))


@store.action
def act_advance(it: dict) -> None:
    """Hand a reviewed stage to the next one by hand — what auto-advance does
    on its own for the waves that ask for it."""
    store.require_idle(it)
    if not store.next_stage(it, it["phase"]):
        raise store.Reject("final stage — nothing to advance to")
    if it["state"] not in (store.NEEDS_REVIEW, store.APPROVED):
        raise store.Reject("wait for the turn to land")
    if not solvers.report_of(it, it["phase"]):
        raise store.Reject("no handoff report yet — send `handoff` first")
    it["updated"] = False
    workers.advance_stage(it)


@store.action
def act_land(it: dict) -> None:
    """Take the stage's filed report as its handoff: the callout turn runs,
    and the chain goes on from there. For a stage whose landing stopped
    short of the callouts."""
    store.require_idle(it)
    phase = it["phase"]
    if not store.next_stage(it, phase):
        raise store.Reject("final stage — nothing to hand off to")
    if it["state"] not in (store.NEEDS_REVIEW, store.APPROVED):
        raise store.Reject("wait for the turn to land")
    if not solvers.report_of(it, phase):
        raise store.Reject("no handoff report yet — send `handoff` first")
    if not it["sessions"].get(phase):
        raise store.Reject("no session yet")
    landing.ask_callouts(it, phase)


def set_session(it: dict, phase: str, session: str) -> None:
    """Point a stage at another CLI session by hand: a copy of its transcript
    cut back to an earlier turn, made outside the console. The next ask
    resumes it."""
    store.require_idle(it)
    if phase not in store.stage_names(it):
        raise store.Reject(f"no stage {phase!r}")
    session = session.strip()
    if not session or workers.transcript_of(session) is None:
        raise store.Reject("no transcript for that session id")
    old = it["sessions"].get(phase)
    # a live worker holds the old session in its process; the next ask
    # spawns one on the new id
    worker = store.PROCS.get((it["id"], phase))
    if worker:
        store.PROCS.pop((it["id"], phase))
        worker["state"] = "dying"
        worker["outbound"].put_nowait(store.STOP)
        drain.queue_reap(worker)
    it["sessions"][phase] = session
    store.say(it, store.event(f"session replaced by hand — was {old or 'none'}"),
              sess=phase)


act_session = store.action(set_session)


def set_model(it: dict, phase: str, model: str) -> None:
    """Change the model one stage of this item runs on, for the turns still
    to come. A session the API refuses on one model can go on under
    another, which is the CLI's own advice for a refusal."""
    store.require_idle(it)
    if phase not in store.stage_names(it):
        raise store.Reject(f"no stage {phase!r}")
    model = model.strip()
    if not model:
        raise store.Reject("no model")
    st = store.stage_of(it, phase)
    old = st.get("model")
    st["model"] = model
    worker = store.PROCS.get((it["id"], phase))
    if worker:
        store.PROCS.pop((it["id"], phase))
        worker["state"] = "dying"
        worker["outbound"].put_nowait(store.STOP)
        drain.queue_reap(worker)
    store.say(it, store.event(f"model set by hand to {model} — was {old or 'default'}"),
              sess=phase)


act_model = store.action(set_model)


@store.action
def act_resume(it: dict) -> None:
    """Continue the stage a usage limit cut off, keeping the cut turn's handoff
    flag. Overnight mode does this on a timer once the window resets."""
    store.require_idle(it)
    if not it.get("resume_phase"):
        raise store.Reject("no cut turn to resume")
    it["updated"] = False
    overnight.resume_item(it)


@store.action
def act_seen(it: dict) -> None:
    it["updated"] = False


@store.action
def act_drop(it: dict) -> None:
    """Forget an item and its feed. The solver file on disk is left alone."""
    store.require_idle(it)
    for worker in workers.detach_workers(it["id"]):
        drain.queue_reap(worker)
    store.STATE["items"] = [x for x in store.STATE["items"] if x["id"] != it["id"]]


def act_kill(item_id: str) -> dict:
    with store.LOCK:
        running = [w for (tid, _), w in store.PROCS.items()
                   if tid == item_id and w["state"] in ("sending", "running")]
        if not running:
            return {"error": "no worker running"}
        worker, turn_seq = running[0], running[0]["turn_seq"]
        worker.pop("escalate", None)  # the user's stop outranks a relaunch
        worker["outbound"].put_nowait({"type": "control_request",
            "request_id": str(uuid.uuid4()), "request": {"subtype": "interrupt"}})

    def force():
        time.sleep(10)
        with store.LOCK:
            current = store.PROCS.get((worker["item_id"], worker["phase"]))
            if current is not worker or worker["turn_seq"] != turn_seq or \
                    worker["state"] not in ("sending", "running"):
                return
            proc = worker["proc"]
            if proc.poll() is None:
                proc.terminate()
    threading.Thread(target=force, daemon=True).start()
    return {"ok": True}


@store.action
def act_revert(it: dict) -> None:
    store.require_idle(it)
    item_id = it["id"]
    snap = store.pre(it)["solver"]
    if not snap or snap == solvers.solver_text(item_id):
        raise store.Reject("nothing to revert")
    solvers.write_solver(item_id, snap)
    # The snapshot is the file as the turn found it, and the turn that landed
    # tagged it after that, so the restore puts back a file the tag may have
    # been missing from. Approval is the only thing that takes the tag off.
    if it["state"] != store.APPROVED:
        solvers.mark_draft(item_id)
    reverted = [f"programs/solvers/{item_id}.dl"]
    # the proposal entries are shared across workers: restore one only if
    # this turn edited it and nothing touched it since the turn landed
    before = {rel: text for rel, text in store.pre(it)["files"].items()
              if rel.startswith(solvers.PROP_DIR + "/")}
    after = it.get("prop_after")
    after = after if isinstance(after, dict) else {}
    now = solvers.prop_files()
    for rel in sorted(before):
        b, a = before[rel], after.get(rel, "")
        if b == a or now.get(rel, "") != a:
            continue
        p = solvers.prop_path(rel)
        if b:
            p.write_text(b)
        elif p.exists():
            p.unlink()
        reverted.append(rel)
    it["dirty"] = store.pre(it)["dirty"]
    it["reverted"] = {"files": reverted,
                      "phase": it.get("last_turn_phase") or it["phase"]}
    store.say(it, store.event("edits reverted"))


SOLVER_REL = re.compile(r"programs/solvers/([0-9a-f]{8})\.dl$")
# How many unapproved solvers a commit subject names before it counts them.
CARRIED_NAMED = 4


def commit_subject(added: list[str], changed: list[str],
                   carried: list[str] = ()) -> str:
    parts = []
    if added:
        parts.append("Add " + ", ".join(added))
    if changed:
        parts.append(("update " if parts else "Update ") + ", ".join(changed))
    msg = "; ".join(parts)
    if carried:
        named = (", ".join(carried) if len(carried) <= CARRIED_NAMED
                 else f"{len(carried)} unapproved solvers")
        msg += f" (carries {named})"
    return msg


def changed_paths() -> list[str]:
    """Every changed or untracked file under the commit's scope, as git
    status names it. A running souffle drops `.tmp*.dl` scratch files beside
    the solvers, so a dotfile is not work and stays out."""
    out = subprocess.run(["git", "status", "--porcelain", "--", *config.COMMIT_STAGE],
                         cwd=config.ROOT, capture_output=True, text=True)
    paths = set()
    for line in out.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip().split(" -> ")[-1].strip('"')
        if not path.rsplit("/", 1)[-1].startswith("."):
            paths.add(path)
    return sorted(paths)


def act_commit() -> dict:
    """Commit the scope as it stands: the approved solvers, and the solvers
    and entries beside them that no one has ruled on yet. Each solver file
    says which it is — a draft tag means unapproved — and only the items the
    console holds as approved move to COMMITTED."""
    with store.LOCK:
        if store.COMMITTER["running"]:
            return {"error": "committer session still running"}
        # a solver session mid-turn may be writing the tree the commit takes
        if any(w["state"] in ("spawning", "sending", "running")
               for w in store.PROCS.values()):
            return {"error": "a solver session is running"}
        ids = [it["id"] for it in store.STATE["items"] if it["state"] == store.APPROVED]
        if not ids:
            return {"error": "nothing approved"}
        paths = changed_paths()
        stems = {m.group(1) for p in paths if (m := SOLVER_REL.match(p))}
        # the file says whether the user approved it; the items the console
        # holds as approved are the ones it has just untagged
        named = sorted({s for s in stems if not solvers.is_draft(s)} | set(ids))
        carried = sorted(stems - set(named))
        rels = {i: str(solvers.solver_path(i).relative_to(config.ROOT))
                for i in named}
        # HEAD, not the index: a solver staged by something else is still new
        in_head = set(subprocess.run(["git", "ls-tree", "-r", "--name-only", "HEAD",
                                      "--", *rels.values()],
                                     cwd=config.ROOT, capture_output=True,
                                     text=True).stdout.split())
        msg = commit_subject([i for i in named if rels[i] not in in_head],
                             [i for i in named if rels[i] in in_head],
                             carried)
        # One pathspec git cannot match makes the whole add fail and stages
        # nothing, so an approved item whose pass wrote no solver file is
        # named in the subject and left out of the add. A solver deleted from
        # the tree is staged all the same: git status lists it.
        stage = set(paths) | {rels[i] for i in named
                              if solvers.solver_path(i).exists()}
        subprocess.run(["git", "add", *sorted(stage)], cwd=config.ROOT, check=False)
        out = subprocess.run(["git", "commit", "-m", msg], cwd=config.ROOT,
                             capture_output=True, text=True)
        if out.returncode != 0:
            return {"error": "git commit failed: " + (out.stderr or out.stdout).strip()[-200:]}
        msgs = [msg]
        for it in store.STATE["items"]:
            if it["id"] in ids:
                it["state"] = store.COMMITTED
                store.say(it, store.event("committed"))
                for worker in workers.detach_workers(it["id"]):
                    drain.queue_reap(worker)
        chk = subprocess.run(["git", "status", "--porcelain", "--", *config.COMMIT_SCOPE],
                             cwd=config.ROOT, capture_output=True, text=True)
        leftovers = any(not l.startswith("??") for l in chk.stdout.splitlines())
        if leftovers and not config.FAKE:
            store.COMMITTER.update(running=True, note=None, started=time.time(),
                                   feed=[])
            threading.Thread(target=run_committer, daemon=True).start()
            msgs.append("committer running…")
    store.bump()
    return {"ok": True, "msg": " + ".join(msgs)}


def kill_session(proc: subprocess.Popen) -> None:
    """End the session and everything it started.

    A session already waited for is left alone: its pid is free for the next
    process the machine starts, and the kill would reach that one's whole
    session group. A session whose own process has ended, with something it
    started still running, has not been waited for, and the group kill takes
    what it left.
    """
    if proc.returncode is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        proc.kill()


def run_committer() -> None:
    """One-shot session that commits worker fallout with judged messages.

    It reads the diffs and the log, so it takes none of the worker appendix:
    that one carries the worker's own rule of no git writes.

    The process is published while it runs, so a shutdown ends the session the
    way it ends a worker.

    The run ends with the flag off, whatever happened to it. A session that
    never started — no CLI on the path, no room for the process — raises
    here, on a thread of its own where nothing reads the exception, and the
    flag left standing would refuse every later commit and hold the reload
    for as long as the console runs.
    """
    note = None
    try:
        # The run opens on a thread of its own, so a shutdown reaches this
        # point ahead of the session. A session started after the shutdown has
        # nothing to end it: it would write git with the console gone.
        with store.LOCK:
            if store.SHUTTING_DOWN:
                raise store.Reject("the console is shutting down")
        before = subprocess.run(["git", "rev-parse", "HEAD"], cwd=config.ROOT,
                                capture_output=True, text=True).stdout.strip()
        cmd = [config.CLAUDE, "-p", config.COMMIT_BRIEF, *config.COMMITTER_FLAGS]
        if config.COMMIT_MODEL:
            cmd += ["--model", config.COMMIT_MODEL]
        seen: set = set()
        with open(config.LOG_DIR / "committer.log", "ab") as log:
            # The session runs in a session group of its own, so the timeout
            # takes the tools it left running with it. A process the session
            # leaves behind holds the pipe this thread reads open, and the
            # read would go on past the run, with the flag still up.
            proc = subprocess.Popen(cmd, cwd=config.ROOT, env=config.WORKER_ENV,
                                    stdout=subprocess.PIPE, stderr=log,
                                    start_new_session=True)
            store.COMMITTER_PROC = proc
            # A shutdown between the spawn and the line above reads no process
            # and leaves the session running, so the flag it set is read here:
            # one of the two ends the session.
            with store.LOCK:
                if store.SHUTTING_DOWN:
                    kill_session(proc)
            timer = threading.Timer(config.COMMIT_TIMEOUT, kill_session, args=(proc,))
            timer.start()
            try:
                for line in proc.stdout:
                    log.write(line)
                    try:
                        ev = json.loads(line)
                    except ValueError:
                        continue
                    entries = []
                    for key, entry in committer_entries(ev):
                        if key not in seen:
                            seen.add(key)
                            entries.append(entry)
                    if entries:
                        with store.LOCK:
                            store.COMMITTER["feed"].extend(entries)
                        store.bump()
                proc.wait()
            finally:
                timer.cancel()
        out = subprocess.run(["git", "log", "--format=%s", f"{before}..HEAD"],
                             cwd=config.ROOT, capture_output=True, text=True).stdout
        subjects = [s for s in out.splitlines() if s]
        note = ("committer: " + "; ".join(reversed(subjects)) if subjects else
                "committer made no commits — see state/logs/committer.log")
    except Exception as exc:
        note = f"committer failed: {exc}"
    finally:
        store.COMMITTER_PROC = None
        with store.LOCK:
            store.COMMITTER.update(running=False, note=note)
            store.COMMITTER["feed"].append(store.event(note))
        store.bump()


def committer_entries(ev: dict) -> list[tuple[tuple, dict]]:
    """The feed entries one committer stream event makes, each with the key
    that tells a repeat of it from a new one: the stream sends a message's
    blocks one event at a time, under the message's id."""
    if ev.get("type") != "assistant":
        return []
    msg = ev.get("message") or {}
    mid = msg.get("id") or ""
    out = []
    for block in msg.get("content") or []:
        if block.get("type") == "text" and block.get("text", "").strip():
            out.append(((mid, "text", block["text"]),
                        {"kind": "worker", "text": block["text"]}))
        elif block.get("type") == "tool_use":
            label = process.tool_label(block.get("name", "?"), block.get("input") or {})
            if label:
                out.append(((mid, "tool", block.get("id") or label),
                            {"kind": "tool", "text": label}))
    return out


def act_auto(body: dict) -> dict:
    """Set the automatic-move settings. Each applies from the next moment it
    is read."""
    with store.LOCK:
        cfg = store.auto()
        for name in config.AUTO_DEFAULTS:
            if name in body:
                cfg[name] = bool(body[name])
    store.bump()
    return {"ok": True}


def act_pipeline(body: dict) -> dict:
    """Set the model a pipeline stage runs. The next wave reads it."""
    with store.LOCK:
        cfg = store.pipeline()
        for name in store.PIPELINE_STAGES:
            if name not in body:
                continue
            word = str(body[name] or "")
            if word not in config.MODEL_IDS:
                return {"error": f"unknown model: {word}"}
            cfg[name] = word
    store.bump()
    return {"ok": True}
