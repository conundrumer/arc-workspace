"""A report ask the model's safeguards refused: the ladder of retries it
gets, and the landing the stage settles into once the retries run out."""

import json
import re
from pathlib import Path

from . import config, landing, process, prompts, store, workers

# The API's safeguards refuse a request as a plain api_error; the result text
# names the category. A refusal is deterministic on the session's context,
# so a turn the console does not retry carries the CLI's own advice.
SAFEGUARD = re.compile(r"safeguards flagged.*?\[(\w+)\]", re.S)
# The category the safeguards give a request that reads as asking the model
# for its reasoning. A report ask can read that way, so one refused under it
# is retried: in plainer words first, then on REFUSAL_MODEL, and after that
# the stage lands with what it has. The ladder answers the console's own
# asks, by the trigger the turn carries; a refused user comment is the
# user's to resend.
RETRIED_REFUSAL = "reasoning_extraction"
REPORT_ASKS = {"handoff": "handoff", "bail": "handoff", "callout": "callout"}
REFUSAL_RETRIES = 2  # asks sent again before the stage lands without one


def refusal_kind(ev: dict) -> str | None:
    """The safeguard category a result event names, if it is a refusal."""
    hit = SAFEGUARD.search(str(ev.get("result") or ""))
    return hit.group(1) if hit else None


def failure_note(ev: dict, reason: str, retried: bool = False) -> str:
    """The feed line for a turn that ended without a result."""
    kind = refusal_kind(ev)
    if kind and retried:
        return f"turn refused by the model's safeguards ({kind})"
    if kind:
        return (f"turn refused by the model's safeguards ({kind}) — "
                "the same request fails again here; it needs a fresh session")
    errors = "; ".join(str(e) for e in ev.get("errors") or [] if e)
    return f"turn failed ({reason})" + (f" — {errors}" if errors else "")


def user_text(row: dict) -> str:
    """The text of a transcript's user row, whichever shape it was written in."""
    content = (row.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content
                       if isinstance(b, dict) and b.get("type") == "text")
    return ""


def strip_ask(path: Path, ask: str) -> int:
    """Cut a transcript back to before the console's ask `ask`, so a resume
    reads the history without it. Rows from the ask on belong to the refused
    turn, which the retry asks for again. Returns the rows cut. Call only
    with the worker process dead; the rewrite must not race the CLI's
    appends."""
    lines = path.read_text().splitlines(True)
    at = None
    for i, line in enumerate(lines):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if (row.get("type") == "user" and not row.get("isSidechain")
                and user_text(row) == ask):
            at = i
    if at is None:
        return 0
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("".join(lines[:at]))
    tmp.replace(path)
    return len(lines) - at


def last_worker_text(it: dict, phase: str) -> str:
    """The last thing the stage's session said in the feed."""
    for m in reversed(it["feed"]):
        if (m.get("sess") == phase and m["kind"] in ("worker", "report")
                and not m.get("sub")):
            return m["text"]
    return ""


def recover_refusal(worker: dict, kind: str, ask: str | None) -> None:
    """Send a refused report ask again, one rung up the ladder.

    Runs on the drain thread with the worker already detached, the way revive
    does: the process dies first, the refused ask comes out of the transcript
    while nothing else writes the file, and the retry spawns a fresh process
    whose resume reads the history without it."""
    if worker.get("proc") is not None:
        process.reap(worker)
    with store.LOCK:
        it = store.find(worker["item_id"])
        if not it:
            return
        phase = worker["phase"]
        try:
            session = it["sessions"].get(phase)
            if not session:
                # a retry would open a session with none of the pass in it
                store.say(it, store.event("no session to ask again — the turn is lost"),
                          sess=phase)
                it.pop("callout_wait", None)
                store.turn_died(it, phase)
            else:
                path = workers.transcript_of(session)
                if path is not None and ask:
                    try:
                        if strip_ask(path, ask):
                            store.say(it, store.event("refused ask cut from the transcript"),
                                      sess=phase)
                    except OSError as exc:
                        store.say(it, store.event(f"transcript cut failed: {exc}"),
                                  sess=phase)
                counts = it.setdefault("refused", {}).setdefault(phase, {})
                counts[kind] = counts.get(kind, 0) + 1
                retry_refusal(it, phase, kind, counts[kind])
        finally:
            workers.respawn_done(it, phase)
    store.bump()


def retry_refusal(it: dict, phase: str, kind: str, count: int) -> None:
    """The `count`th refusal of one ask kind on a stage: the plainer ask, then
    the same on REFUSAL_MODEL, then the stage lands with what it has. Caller
    holds LOCK, with the stage's worker gone."""
    if count > REFUSAL_RETRIES:
        settle_refusal(it, phase, kind)
        return
    if count == 1:
        store.say(it, store.event("asking again in plainer words"), sess=phase)
    else:
        st = store.stage_of(it, phase)
        if st.get("model") != config.REFUSAL_MODEL:
            store.say(it, store.event(f"refused again — the stage moves to "
                                      f"{config.REFUSAL_MODEL}"), sess=phase)
            st["model"] = config.REFUSAL_MODEL
    it["state"] = store.RUNNING
    try:
        if kind == "callout":
            it["callout_wait"] = phase
            workers.launch(it, prompts.refused_callout_brief(), phase, trigger="callout",
                   admitted=True)
        else:
            workers.launch(it, prompts.refused_handoff_brief(), phase, trigger="handoff",
                   handoff=True, admitted=True)
    except (store.Reject, OSError) as exc:
        store.say(it, store.event(f"retry failed: {exc}"), sess=phase)
        it.pop("callout_wait", None)
        store.turn_died(it, phase)


def settle_refusal(it: dict, phase: str, kind: str) -> None:
    """Land a stage whose report ask was refused past the retries. The
    handoff takes the session's last message as the report; the callouts
    stay unwritten. Either way the item waits for the user, who can `land`
    the report or resend the ask by hand. Caller holds LOCK."""
    if kind == "callout":
        it.pop("callout_wait", None)
        store.say(it, store.event("callouts refused past the retries — "
                                  "the report stands without them"), sess=phase)
        landing.compact_on_landing(it, phase)
    elif (it.get("reports") or {}).get(phase):
        store.say(it, store.event("handoff refused past the retries — "
                                  "the filed report stands"), sess=phase)
    elif text := last_worker_text(it, phase):
        landing.file_report(it, phase, text)
        store.say(it, store.event("handoff refused past the retries — the "
                                  "session's last message stands as the report"),
                  sess=phase)
    else:
        store.say(it, store.event("handoff refused past the retries — no report"),
                  sess=phase)
    it["state"] = store.NEEDS_REVIEW
    it["updated"] = True
    it["landed_at"] = store.now()
