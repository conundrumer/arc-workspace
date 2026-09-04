"""The account's rate-limit windows, the overnight pace gate, and what a
quota death does to an item."""

import json
import random
import re
import subprocess
import time
from pathlib import Path

import quota

from . import config, store

# The console running the queue unattended. An admitter keeps a target number
# of items in flight, a pacer decides whether the account can afford to start
# another one, and a turn the account's quota killed is resumed once the window
# resets. Nothing is approved and nothing is committed without the user: the
# night's items land in review and wait for morning.

NIGHT_DEFAULTS = {
    "on": False,
    "target": 6,       # items in flight the admitter keeps
    "reserve": 10,     # points of weekly quota held back from the pace line
    "floor": 5,        # weekly points spendable however early in the week
    "ceiling": 75,     # 5h utilization above which new admissions hold
    "catchup": True,   # spend the slack the week has accumulated
}


NIGHT_LOG = 40         # night log entries kept
LIVE = (store.QUEUED, store.RUNNING, store.COMMENTED)   # states with work still to come


# The last hour before the 5h window resets, where the ceiling stops applying.
# It matches the prompt-cache TTL: a turn that exhausts quota this close to the
# reset resumes just after it with its cache still warm, so the retry costs
# little. The same overrun earlier in the window strands a cold context, and
# rebuilding it is what the ceiling exists to avoid.
SQUEEZE = 3600
# Spread the resumes of a fleet that all died on the same limit.
RESUME_JITTER = (30, 210)
RESUME_FALLBACK = 15 * 60   # when no reset time is known
RESUME_BRIEF = ("your previous turn was cut off by a usage limit; continue "
                "from where you stopped")
# Added when the cut turn owed a handoff report, so a session on an older
# brief still learns where the report goes.
RESUME_HANDOFF_NOTE = ("; the handoff report goes between `<handoff>` and "
                       "`</handoff>` tags")

# A turn cut short by an exhausted account. The result event's
# `api_error_status` carries the HTTP status of an API failure, and 429 is the
# account out of quota; every other ending reads null. The CLI has no
# terminal_reason of its own for the case — a usage limit arrives as a plain
# api_error — so a worker that died before reporting one is judged on the
# wording its log tail left behind instead.
QUOTA_STATUS = "429"
QUOTA_REASONS = ("rate_limit", "usage_limit", "usage_limit_reached")
QUOTA_TEXT = re.compile(r"usage limit|rate[ _-]?limit|too many requests|quota",
                        re.I)


def quota_death(status=None, reason: str | None = None, text: str = "") -> bool:
    """Whether a turn ended because the account ran out of quota."""
    if status is not None and str(status) == QUOTA_STATUS:
        return True
    if (reason or "").lower() in QUOTA_REASONS:
        return True
    return bool(text and QUOTA_TEXT.search(text))


# The account's windows, which every model draws down, and the Fable window,
# which Fable models draw down as well.
ACCOUNT_WINDOWS = ("5h", "wk")
FABLE_WINDOW = "fbl"


def is_fable(model: str) -> bool:
    return model.startswith(("claude-fable", "claude-mythos"))


def draws(model: str) -> list[dict]:
    """The rate-limit windows a spend by `model` draws down."""
    return [u for u in store.USAGE
            if u.get("label") in ACCOUNT_WINDOWS
            or (u.get("label") == FABLE_WINDOW and is_fable(model))]


def night_models() -> list[str]:
    """The model ids a night item runs by itself: every stage before the stop,
    and the finalize stage when the auto finalize setting lifts the stop."""
    chain = store.default_chain()
    run = chain[:-1]
    if chain and chain[-1]["name"] == "finalize" and store.auto()["finalize"]:
        run = chain
    return [st.get("model") or "" for st in run]


def night() -> dict:
    """The mode's config and running notes, filled in with the defaults."""
    cfg = store.STATE.setdefault("overnight", {})
    for name, value in NIGHT_DEFAULTS.items():
        cfg.setdefault(name, value)
    cfg.setdefault("log", [])
    return cfg


def night_say(text: str, once: bool = False) -> bool:
    """Add a line to the night log. `once` drops a repeat of the line already
    at the end, so a hold that outlives many passes is recorded once."""
    log = night()["log"]
    if once and log and log[-1]["text"] == text:
        return False
    log.append({"t": int(store.now()), "text": text})
    del log[:-NIGHT_LOG]
    return True


def clock(at: float) -> str:
    return time.strftime("%H:%M", time.localtime(at))


def window(label: str) -> dict | None:
    return next((u for u in store.USAGE if u.get("label") == label), None)


def elapsed_pct(u: dict | None, at: float) -> float | None:
    """How far through its window a rate limit is, in percent."""
    if not u or not u.get("reset") or not u.get("window"):
        return None
    return max(0.0, min(100.0, 100 * (1 - (u["reset"] - at) / u["window"])))


def pacer(at: float | None = None) -> dict:
    """Whether the admitter may start another item, and what to say about it.

    Only new admissions are gated. A turn already in flight, a review comment,
    and every manual action run whatever the windows read.
    """
    at = store.now() if at is None else at
    cfg = night()
    wk, five = window("wk"), window("5h")
    out = {"open": False, "why": "", "next": None, "wk": None, "line": None,
           "fiveh": None, "ceiling": cfg["ceiling"], "squeeze": False,
           "squeezeAt": None}
    wk_elapsed = elapsed_pct(wk, at)
    if wk is None or wk_elapsed is None:
        out["why"] = "no weekly usage reading yet"
        return out
    # The floor keeps the first hours of a week spendable: elapsed% starts at
    # zero there, and the pace line alone would hold every admission until the
    # week had caught up with the reserve.
    line = max(cfg["floor"], wk_elapsed - cfg["reserve"])
    out.update(wk=wk["pct"], line=line, elapsed=wk_elapsed)
    if five and five.get("reset"):
        out["squeezeAt"] = five["reset"] - SQUEEZE
        out["squeeze"] = at >= out["squeezeAt"]
        out["fiveh"] = five["pct"]
    if wk["pct"] > line:
        out["why"] = f"wk at pace ({wk['pct']:.0f}% vs {line:.0f}%)"
        return out
    # The Fable window paces the same way when a night stage runs Fable.
    fbl = window(FABLE_WINDOW) if any(is_fable(m) for m in night_models()) else None
    fbl_elapsed = elapsed_pct(fbl, at)
    if fbl_elapsed is not None:
        fbl_line = max(cfg["floor"], fbl_elapsed - cfg["reserve"])
        out["fbl"] = fbl["pct"]
        if fbl["pct"] > fbl_line:
            out["why"] = f"fbl at pace ({fbl['pct']:.0f}% vs {fbl_line:.0f}%)"
            return out
    if not cfg["catchup"]:
        # Strict pace: spend no faster than the window elapses, measured from
        # the moment the mode came on. A window that rolled over under us reads
        # as a drop in utilization, and starts the measurement again.
        start, since = cfg.get("wk_start"), cfg.get("wk_start_at")
        if start is None or since is None or wk["pct"] < start:
            cfg["wk_start"], cfg["wk_start_at"] = wk["pct"], at
        else:
            points = 100 * (at - since) / wk["window"]
            if wk["pct"] - start > points:
                out["why"] = (f"wk above strict pace (+{wk['pct'] - start:.1f} "
                              f"vs +{points:.1f} since mode start)")
                return out
    # No reset time means the 5h window is not running — nothing to hold for.
    if out["squeezeAt"] and five["pct"] > cfg["ceiling"] and not out["squeeze"]:
        out["next"] = out["squeezeAt"]
        out["why"] = (f"5h above ceiling ({five['pct']:.0f}% > "
                      f"{cfg['ceiling']}%), squeeze zone opens at "
                      f"{clock(out['squeezeAt'])}")
        return out
    out["open"] = True
    out["why"] = "squeeze zone — reset is close" if out["squeeze"] else "at pace"
    return out


def live_items() -> list[dict]:
    """Items the night still has work coming for. A scheduled quota-death
    resume holds its slot, so the admitter does not fill the night past its
    target ahead of one."""
    return [it for it in store.STATE["items"]
            if it["state"] in LIVE or it.get("resume_at")]


def night_landed() -> int:
    """Items that landed unreviewed since the mode came on."""
    since = night().get("since") or 0
    return sum(1 for it in store.STATE["items"] if it["state"] == store.NEEDS_REVIEW
               and (it.get("landed_at") or 0) >= since)


def limit_reset(model: str) -> float | None:
    """When the window a death under `model` hit resets. A window the model
    draws down that reads full is the one that ran out, and the latest reset
    among those is when every one of them is open again; when the cache has
    not caught up and none reads full, the 5h window is the usual one."""
    full = [u["reset"] for u in draws(model)
            if u.get("reset") and (u.get("pct") or 0) >= 100]
    if full:
        return max(full)
    return (window("5h") or {}).get("reset")


def quota_cut(it: dict, phase: str, handoff: bool) -> None:
    """A turn died with the account out of quota. In overnight mode the item
    gets one automatic resume just after the window it hit resets; a second
    death on the same stage leaves it for review. Caller holds LOCK."""
    store.say(it, store.event("usage limit"), sess=phase)
    if store.slash_turn(it, phase):
        return   # a slash command has nothing to continue from
    # The flag lives in the worker, which dies with the turn, so the item takes
    # a copy whatever the mode is. Without it a resume by hand opens the stage
    # as a plain comment: the pass runs again and lands, and the item stays put.
    it.update(resume_phase=phase, resume_handoff=bool(handoff))
    cfg = night()
    if not cfg["on"]:
        return
    if it.get("quota_retry"):
        store.say(it, store.event("second usage limit — left for review"), sess=phase)
        night_say(f"{it['id']} · second usage limit, left for review")
        return
    reset = limit_reset(store.stage_of(it, phase).get("model") or "")
    at = reset if reset and reset > store.now() else store.now() + RESUME_FALLBACK
    at += random.uniform(*RESUME_JITTER)
    it.update(quota_retry=phase, resume_at=at)
    store.say(it, store.event(f"resume scheduled for {clock(at)}"), sess=phase)
    night_say(f"{it['id']} · usage limit in {phase}, resume at {clock(at)}")


def read_usage() -> list[dict]:
    """Rate-limit windows from the OAuth usage API cache; [] on any surprise."""
    from datetime import datetime
    try:
        raw = json.loads((Path.home() / ".claude" / "usage-api.json").read_text())
        out = []
        for lim in (raw.get("data") or {}).get("limits") or []:
            pct, kind = lim.get("percent"), lim.get("kind")
            scope = (((lim.get("scope") or {}).get("model")) or {}).get("display_name")
            if pct is None:
                continue
            if kind == "session":
                label, window = "5h", 5 * 3600
            elif kind == "weekly_all":
                label, window = "wk", 7 * 86400
            elif scope:
                label = "fbl" if scope.lower().startswith("fable") else scope[:3].lower()
                window = 7 * 86400
            else:
                continue
            reset = None
            if lim.get("resets_at"):
                reset = int(datetime.fromisoformat(lim["resets_at"]).timestamp())
            out.append({"label": label, "pct": pct, "reset": reset, "window": window})
        return out
    except Exception:
        return []


def usage_loop() -> None:
    script = Path.home() / ".claude" / "scripts" / "fetch-usage-api.sh"
    sampler = quota.Sampler()
    while True:
        if script.exists():
            subprocess.run(["bash", str(script)], capture_output=True, timeout=30)
        store.USAGE = read_usage()
        # Pairs each window's utilization with the tokens spent inside it, so
        # the QUOTA_RATE figures can be refit from observation rather than
        # measured by hand. Never worth failing the poll over.
        try:
            sampler.record(config.SAMPLE_FILE)
        except Exception:
            pass
        time.sleep(60)
