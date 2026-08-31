"""The actions the console takes on an item, and the commit that ends a
round."""

import subprocess
import threading
import time
import uuid
from pathlib import Path

from . import config, overnight, prompts, solvers, store, workers


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
    w = store.PROCS.get((it["id"], sess))
    if w and w["state"] in ("sending", "running"):
        if text.startswith("/"):
            raise store.Reject("worker busy — a slash command counts only at the "
                               "head of a turn")
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
    it["state"] = store.APPROVED
    it["updated"] = False
    store.say(it, store.event("approved"))


@store.action
def act_unapprove(it: dict) -> None:
    if it["state"] != store.APPROVED:
        raise store.Reject("not approved")
    it["state"] = store.NEEDS_REVIEW
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
        workers.queue_reap(worker)
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
    solvers.solver_path(item_id).write_text(snap)
    reverted = [f"programs/solvers/{item_id}.dl"]
    # the proposal entries are shared across workers: restore one only if
    # this turn changed it and nothing touched it since the turn landed
    before, after = store.pre(it)["proposals"], it.get("prop_after")
    before = before if isinstance(before, dict) else {}
    after = after if isinstance(after, dict) else {}
    now = solvers.prop_files()
    for rel in sorted(set(before) | set(after)):
        b, a = before.get(rel, ""), after.get(rel, "")
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


def commit_subject(added: list[str], changed: list[str]) -> str:
    parts = []
    if added:
        parts.append("Add " + ", ".join(added))
    if changed:
        parts.append(("update " if parts else "Update ") + ", ".join(changed))
    return "; ".join(parts)


def act_commit() -> dict:
    with store.LOCK:
        if store.COMMITTER["running"]:
            return {"error": "committer session still running"}
        ids = [it["id"] for it in store.STATE["items"] if it["state"] == store.APPROVED]
        if not ids:
            return {"error": "nothing approved"}
        rels = {i: str(solvers.solver_path(i).relative_to(config.ROOT)) for i in ids}
        # HEAD, not the index: a solver staged by something else is still new
        in_head = set(subprocess.run(["git", "ls-tree", "-r", "--name-only", "HEAD",
                                      "--", *rels.values()],
                                     cwd=config.ROOT, capture_output=True,
                                     text=True).stdout.split())
        msg = commit_subject(sorted(i for i in ids if rels[i] not in in_head),
                             sorted(i for i in ids if rels[i] in in_head))
        paths = list(rels.values())
        # new entries are untracked, so the directory is staged as a whole
        proposals = "docs/wf-solver/proposals"
        if subprocess.run(["git", "status", "--porcelain", "--", proposals],
                          cwd=config.ROOT, capture_output=True, text=True).stdout.strip():
            paths.append(proposals)
        subprocess.run(["git", "add", *paths], cwd=config.ROOT, check=False)
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
                    workers.queue_reap(worker)
        chk = subprocess.run(["git", "status", "--porcelain", "--", *config.COMMIT_SCOPE],
                             cwd=config.ROOT, capture_output=True, text=True)
        leftovers = any(not l.startswith("??") for l in chk.stdout.splitlines())
        if leftovers and not config.FAKE:
            store.COMMITTER["running"] = True
            store.COMMITTER["note"] = None
            threading.Thread(target=run_committer, args=(prompts.append_path(),),
                             daemon=True).start()
            msgs.append("committer running…")
    store.bump()
    return {"ok": True, "msg": " + ".join(msgs)}


def run_committer(append: Path) -> None:
    """One-shot session that commits worker fallout with judged messages."""
    before = subprocess.run(["git", "rev-parse", "HEAD"], cwd=config.ROOT,
                            capture_output=True, text=True).stdout.strip()
    cmd = [config.CLAUDE, "-p", config.COMMIT_BRIEF, *config.COMMITTER_FLAGS]
    if append.exists():
        cmd += ["--append-system-prompt", append.read_text()]
    if config.COMMIT_MODEL:
        cmd += ["--model", config.COMMIT_MODEL]
    with open(config.LOG_DIR / "committer.log", "ab") as log:
        try:
            subprocess.run(cmd, cwd=config.ROOT, env=config.WORKER_ENV, stdout=log, stderr=log,
                           timeout=900)
        except subprocess.TimeoutExpired:
            pass
    out = subprocess.run(["git", "log", "--format=%s", f"{before}..HEAD"],
                         cwd=config.ROOT, capture_output=True, text=True).stdout
    subjects = [s for s in out.splitlines() if s]
    with store.LOCK:
        store.COMMITTER["running"] = False
        store.COMMITTER["note"] = ("committer: " + "; ".join(reversed(subjects))
                                   if subjects else
                                   "committer made no commits — see state/logs/committer.log")
    store.bump()
