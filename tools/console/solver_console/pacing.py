"""The account's rate-limit windows, the overnight pace gate, and what a
quota death does to an item."""

import json
import random
import re
import sys
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
    "source": "queue",  # where the admitter draws from
    "pace": "share",   # whether the week's quota is shared or spent to the wall
    "target": 6,       # items in flight the admitter keeps under the queue source
    "finalize_target": 3,   # the same, under the unfinalized source
    "reserve": 10,     # points of weekly quota held back from the pace line
    "floor": 5,        # weekly points spendable however early in the week
    "catchup": True,   # spend the slack the week has accumulated
}

# share: the pace lines hold weekly quota back for work outside the console.
# exhaust: the account is the console's alone, and the week is spent down to
# its limits; only the spend rules below gate an admission.
PACE_MODES = ("share", "exhaust")


# The queue source admits a task from the queue and runs it up to the stop;
# the unfinalized source takes the next unfinalized solver and runs its
# finalize pass; both runs the two side by side, each with its own slot.
NIGHT_SOURCES = ("queue", "unfinalized", "both")
# The slots a source admits into, in the order a pass checks them: a landed
# refine's finalize pass goes ahead of a new task.
SOURCE_SLOTS = {"queue": ("queue",), "unfinalized": ("finalize",),
                "both": ("finalize", "queue")}
NIGHT_LOG = 40         # night log entries kept
LIVE = (store.QUEUED, store.RUNNING, store.COMMENTED)   # states with work still to come


# The spend rules. The fleet's rate in each window is read off the account's
# own utilization, as the slope of the window's readings over the last
# SLOPE_SPAN, so no model of what an item costs is needed and the rate
# follows the pipeline as it stands. An admission is held when the fleet's
# rate plus one more item's share would pass the window's budget: what is
# left, spread over the time to the reset for the 5h window, and over the
# next hour for a weekly one. The hour is the cache TTL. A turn cut by a
# limit resumes cold past it, and a weekly window is spread by the pace
# line or not at all, so an hour of spend is the headroom every window
# keeps. Near a reset the time to it is clamped to the same hour, so the
# last hour opens no wider than the headroom allows.
SLOPE_SPAN = 15 * 60
SLOPE_MIN = 3 * 60      # readings must span this long before a slope is read
STALE = 3 * 60          # a newest reading older than this reads as no slope
SHARE_SPAN = 10 * 60    # readings must span this long before a share is written
WALL = 3600
# What one item spends in a window, in points an hour, until the fleet has
# been observed. From September 2026: fifteen live items took the 5h window
# at about 85 points an hour, and the weekly figures follow at the windows'
# dollar rates.
# Readings further apart than this have a gap between them.
READING_GAP = 3 * config.USAGE_POLL
SHARE_PRIOR = {"5h": 6.0, "wk": 1.4, "fbl": 3.9}
# A reset that moves less than this is the API's rounding, not a new window.
RESET_WOBBLE = 60
# A reading that falls more than this since the last one is a new window.
ROLLOVER_DROP = 5
# Under exhaust with both slots, points the Fable window may trail the weekly
# one before the queue slot holds for finalize work.
FABLE_LAG = 3

# Each window's recent readings, oldest first, as (time, pct, workers
# mid-turn), and the reset each history belongs to. Replaced whole on every
# reading, so a pass reads one consistent list. A seeded reading carries None
# for the workers, since the file does not say how many were spending.
HISTORY: dict[str, list[tuple[float, float, int | None]]] = {}
HISTORY_RESET: dict[str, float | None] = {}
# When the reading in store.USAGE was fetched; None before the first poll.
# A reading older than USAGE_STALE holds admissions: a cache that stopped
# moving says nothing about where the windows stand.
USAGE_AT: float | None = None
USAGE_STALE = 10 * 60

# Spread the resumes of a fleet that all died on the same limit.
RESUME_JITTER = (30, 210)
RESUME_FALLBACK = 15 * 60   # when no reset time is known
RESUME_BRIEF = ("your previous turn was cut off by a usage limit; continue "
                "from where you stopped")
# The agents a cut turn had running died with it. A message reaches one only
# from the process that spawned it, so the note depends on whether the
# resume lands in that process or a fresh one.
RESUME_AGENTS_LIVE = ("; the agents that were running died with it, so message "
                      "each one to continue rather than launching it again")
RESUME_AGENTS_GONE = ("; the agents that were running died with it and cannot "
                      "be messaged from this process, so launch them again")
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
    """The model ids a queue admission runs by itself: every stage before the
    stop, and the finalize stage when the auto finalize setting lifts the
    stop. With the admitter owning finalize the stop holds, so the stage is
    not the admission's to run."""
    chain = store.default_chain()
    run = chain[:-1]
    if chain and chain[-1]["name"] == "finalize" and store.auto()["finalize"] \
            and not admitter_owns_finalize(night()):
        run = chain
    return [st.get("model") or "" for st in run]


def slot_models(kind: str) -> list[str]:
    """The model ids an admission into the slot of `kind` runs."""
    if kind == "finalize":
        return [store.stage_model("finalize")]
    return night_models()


def admit_models() -> list[str]:
    """The model ids the active source's admissions run, every slot
    together."""
    out: list[str] = []
    for kind in SOURCE_SLOTS[night()["source"]]:
        out += [m for m in slot_models(kind) if m not in out]
    return out


def slot_target(cfg: dict, kind: str) -> int:
    """How many items in flight the slot of `kind` keeps."""
    return cfg["finalize_target"] if kind == "finalize" else cfg["target"]


def slot_live(cfg: dict, kind: str) -> int:
    """The items in flight the slot of `kind` counts. A single source counts
    every live item against its one target; both counts the finalize passes
    against the finalize slot and every other item against the queue slot."""
    if cfg["source"] != "both":
        return len(live_items())
    return sum(1 for it in live_items()
               if (it["phase"] == "finalize") == (kind == "finalize"))


def admitter_owns_finalize(cfg: dict) -> bool:
    """Whether every start of a finalize pass goes through the admitter, so
    the pacer gates it: the mode is on with a source that has a finalize
    slot."""
    return bool(cfg["on"]) and "finalize" in SOURCE_SLOTS[cfg["source"]]


def night() -> dict:
    """The mode's config and running notes, filled in with the defaults."""
    cfg = store.STATE.setdefault("overnight", {})
    for name, value in NIGHT_DEFAULTS.items():
        cfg.setdefault(name, value)
    if cfg["source"] not in NIGHT_SOURCES:
        cfg["source"] = NIGHT_DEFAULTS["source"]
    if cfg["pace"] not in PACE_MODES:
        cfg["pace"] = NIGHT_DEFAULTS["pace"]
    cfg.setdefault("log", [])
    return cfg


# How far back a `once` line looks for its repeat. Each slot of a pass can
# leave one standing note, so with two slots the notes would take turns at
# the end of the log if only the last line counted.
ONCE_BACK = 3


def night_say(text: str, once: bool = False) -> bool:
    """Add a line to the night log. `once` drops a repeat of a line among the
    last few, so a hold that outlives many passes is recorded once."""
    log = night()["log"]
    if once and any(e["text"] == text for e in log[-ONCE_BACK:]):
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


# A worker spends from the moment its turn is sent until the turn ends.
SPENDING = ("spawning", "sending", "running")


def spending() -> int:
    """Workers mid-turn: what the fleet's rate is spread over. Under the
    lock, since the usage thread counts while other threads add and drop
    workers."""
    with store.LOCK:
        return sum(1 for w in store.PROCS.values() if w.get("state") in SPENDING)


def note_usage(rows: list[dict], at: float | None = None,
               busy: int | None = -1) -> None:
    """Add a reading of each window to its history. A window whose reset
    moved or whose value fell has rolled over, and its history starts
    again. `busy` is the workers mid-turn, counted now unless given."""
    global HISTORY, HISTORY_RESET
    at = store.now() if at is None else at
    if busy == -1:
        busy = spending()
    hist, resets = dict(HISTORY), dict(HISTORY_RESET)
    for u in rows:
        label, pct, reset = u.get("label"), u.get("pct"), u.get("reset")
        if label is None or pct is None:
            continue
        prev = hist.get(label) or []
        if prev:
            last_reset = resets.get(label)
            moved = (reset is None) != (last_reset is None) or (
                reset is not None and abs(reset - last_reset) > RESET_WOBBLE)
            if moved or pct < prev[-1][1] - ROLLOVER_DROP:
                prev = []
        hist[label] = [r for r in prev if at - r[0] <= SLOPE_SPAN] + [(at, pct, busy)]
        resets[label] = reset
    HISTORY, HISTORY_RESET = hist, resets


def seed_history(path: Path | None = None) -> None:
    """Start the history from the sampler's file, so a reload does not wait
    out the span before a slope can be read."""
    path = config.SAMPLE_FILE if path is None else path
    try:
        lines = path.read_text(errors="replace").splitlines()[-(SLOPE_SPAN // 60 + 2):]
    except (OSError, ValueError):
        return
    for line in lines:
        try:
            row = json.loads(line)
            rows = [{"label": label, "pct": w.get("pct"), "reset": w.get("end")}
                    for label, w in (row.get("windows") or {}).items()]
            note_usage(rows, at=float(row["t"]), busy=None)
        except (ValueError, KeyError, TypeError, AttributeError):
            continue


def recent(label: str) -> list[tuple]:
    """The window's readings inside the span as of now, or none when the
    newest has gone stale: readings that stopped arriving say nothing about
    the fleet as it stands."""
    at = store.now()
    pts = [r for r in HISTORY.get(label) or [] if at - r[0] <= SLOPE_SPAN]
    if pts and at - pts[-1][0] > STALE:
        return []
    return pts


def rate(label: str) -> float | None:
    """The window's spend in points an hour, the least-squares slope over its
    recent readings; None until they span SLOPE_MIN."""
    pts = recent(label)
    if len(pts) < 2 or pts[-1][0] - pts[0][0] < SLOPE_MIN:
        return None
    n = len(pts)
    mt = sum(r[0] for r in pts) / n
    mp = sum(r[1] for r in pts) / n
    var = sum((r[0] - mt) ** 2 for r in pts)
    if not var:
        return None
    return 3600 * sum((r[0] - mt) * (r[1] - mp) for r in pts) / var


def share(label: str, cfg: dict, observed: float | None) -> float:
    """What one item spends in the window, in points an hour. Read from the
    fleet while its rate shows, as the slope over the workers mid-turn
    across the same readings, and remembered in the config for the times
    none runs; the prior stands until something is observed."""
    shares = cfg.setdefault("share", {})
    pts = recent(label)
    counted = [r[2] for r in pts if r[2] is not None]
    busy = sum(counted) / len(counted) if counted else 0
    # One short or one-sided stretch must not set what every later admission
    # is measured by, so a share is written only off a full span of readings
    # with none missing: a slope across a gap is shaped by the gap.
    steady = all(b[0] - a[0] <= READING_GAP for a, b in zip(pts, pts[1:], strict=False))
    if observed is not None and observed > 0 and busy > 0 and steady \
            and pts[-1][0] - pts[0][0] >= SHARE_SPAN:
        shares[label] = round(observed / busy, 2)
    prior = SHARE_PRIOR.get(label, SHARE_PRIOR["5h"])
    stored = shares.get(label)
    if not stored:
        return prior
    # Only a running item measures the share again. With nothing spending, a
    # stored share above the prior would hold the one admission that could
    # correct it, so the idle fleet is measured by the smaller of the two.
    return min(stored, prior) if spending() == 0 else stored


def budget(u: dict, at: float) -> float:
    """Points an hour the window can take: what is left, over the time to
    its reset for the 5h window and over the next hour for a weekly one,
    the time to a reset never read as less than that hour. A 5h window
    with no reset is a full window away from one."""
    left = max(0.0, 100.0 - (u.get("pct") or 0))
    if u.get("label") == "5h":
        to_reset = (u["reset"] - at) if u.get("reset") else (u.get("window") or WALL)
        return left / (max(to_reset, WALL) / 3600)
    return left / (WALL / 3600)


def spend_windows(models: list[str]) -> list[dict]:
    """The windows an admission running `models` draws down, each once."""
    out: list[dict] = []
    for m in models:
        out += [u for u in draws(m) if u not in out]
    return out


def pacer(at: float | None = None, models: list[str] | None = None) -> dict:
    """Whether the admitter may start another item, and what to say about it.
    `models` are the model ids the admission would run; a window paces the
    gate only when one of them draws it down.

    Only new admissions are gated. A turn already in flight, a review comment,
    and every manual action run whatever the windows read.
    """
    at = store.now() if at is None else at
    if models is None:
        models = admit_models()
    cfg = night()
    wk = window("wk")
    # `why` says what the gate read; `hold` names the rule that held, in
    # words that stay the same while the numbers move, so the night log
    # records a hold once.
    out = {"open": False, "why": "", "hold": "", "wk": None, "line": None,
           "elapsed": None, "fbl": None, "windows": []}
    wk_elapsed = elapsed_pct(wk, at)
    if wk is None or wk_elapsed is None:
        out["why"] = out["hold"] = "no weekly usage reading yet"
        return out
    if USAGE_AT is not None and at - USAGE_AT > USAGE_STALE:
        out["hold"] = "usage reading stale"
        out["why"] = f"usage reading stale ({(at - USAGE_AT) / 60:.0f} min old)"
        return out
    out.update(wk=wk["pct"], elapsed=wk_elapsed)
    # The spend rules, on every window the admission draws. A worker mid-turn
    # counts at one share even before the slope shows it, so a burst of
    # admissions is not under-read while the newest are warming up.
    busy = spending()
    spend_held = None
    for u in spend_windows(models):
        observed = rate(u["label"])
        sh = share(u["label"], cfg, observed)
        expected = max(observed or 0.0, busy * sh)
        b = budget(u, at)
        out["windows"].append({"label": u["label"], "pct": u["pct"], "rate": expected,
                               "share": sh, "budget": b})
        if spend_held is None and expected + sh > b:
            spend_held = (f"{u['label']} over budget",
                          f"{u['label']} at {u['pct']:.0f}%: {expected:.1f} + {sh:.1f} "
                          f"points an hour over its budget of {b:.1f}")
    held = pace_lines(cfg, models, wk, wk_elapsed, at, out) \
        if cfg["pace"] == "share" else None
    held = held or spend_held
    if held:
        out["hold"], out["why"] = held
        return out
    out["open"] = True
    out["why"] = out["hold"] = "at pace"
    return out


def pace_lines(cfg: dict, models: list[str], wk: dict, wk_elapsed: float,
               at: float, out: dict) -> tuple[str, str] | None:
    """The share-mode holds: the weekly and Fable pace lines, and the strict
    pace when catchup is off. A hold as (rule, reading), or None."""
    # The floor keeps the first hours of a week spendable: elapsed% starts at
    # zero there, and the pace line alone would hold every admission until the
    # week had caught up with the reserve.
    line = max(cfg["floor"], wk_elapsed - cfg["reserve"])
    out["line"] = line
    if wk["pct"] > line:
        return "wk at pace", f"wk at pace ({wk['pct']:.0f}% vs {line:.0f}%)"
    # The Fable window paces the same way when an admission runs Fable.
    fbl = window(FABLE_WINDOW) if any(is_fable(m) for m in models) else None
    fbl_elapsed = elapsed_pct(fbl, at)
    if fbl_elapsed is not None:
        fbl_line = max(cfg["floor"], fbl_elapsed - cfg["reserve"])
        out["fbl"] = fbl["pct"]
        if fbl["pct"] > fbl_line:
            return "fbl at pace", f"fbl at pace ({fbl['pct']:.0f}% vs {fbl_line:.0f}%)"
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
                return ("wk above strict pace",
                        f"wk above strict pace (+{wk['pct'] - start:.1f} "
                        f"vs +{points:.1f} since mode start)")
    return None


def fable_trails(cfg: dict) -> tuple[str, str] | None:
    """Under exhaust with both slots, the hold on the queue slot while the
    Fable window trails the weekly one, as (rule, reading): Opus spend
    cannot move the Fable window, so the week that exhausts both runs
    finalize first. The caller checks that the finalize slot can take
    work and that work waits."""
    if cfg["pace"] != "exhaust" or cfg["source"] != "both":
        return None
    wk, fbl = window("wk"), window(FABLE_WINDOW)
    if not wk or not fbl or fbl["pct"] >= wk["pct"] - FABLE_LAG:
        return None
    return ("Fable window trails, finalize first",
            f"Fable window trails the weekly one (fbl {fbl['pct']:.0f}% vs "
            f"wk {wk['pct']:.0f}%), finalize first")


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
        # A slash command has nothing to continue from. A compact that died
        # this way leaves the session as it was, so the auto compact may try
        # again, and the user may compact by hand.
        it.get("auto_compacted", {}).pop(phase, None)
        return
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


# The statusline file's keys, and the window each names.
STATUS_WINDOWS = {"five_hour": ("5h", 5 * 3600), "seven_day": ("wk", 7 * 86400),
                  "fable_weekly": ("fbl", 7 * 86400)}


def api_usage(path: Path | None = None) -> tuple[float, list[dict]]:
    """When the OAuth usage API cache was fetched, and its windows; (0, [])
    on any surprise."""
    from datetime import datetime
    path = config.USAGE_API if path is None else path
    try:
        raw = json.loads(path.read_text())
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
        return float(raw.get("fetched_at") or 0), out
    except Exception:
        return 0.0, []


def status_usage(path: Path | None = None) -> tuple[float, list[dict]]:
    """When the statusline last wrote its usage file, and its windows; (0, [])
    on any surprise."""
    path = config.USAGE_STATUS if path is None else path
    try:
        raw = json.loads(path.read_text())
        out = []
        for key, (label, window) in STATUS_WINDOWS.items():
            lim = raw.get(key) or {}
            if lim.get("used_pct") is None:
                continue
            out.append({"label": label, "pct": lim["used_pct"],
                        "reset": lim.get("resets_at_epoch"), "window": window})
        return path.stat().st_mtime, out
    except Exception:
        return 0.0, []


def usage_reading(api: Path | None = None,
                  status: Path | None = None) -> tuple[float, list[dict]]:
    """When the fresher of the two files was written, and its rate-limit
    windows; (0, []) when neither reads."""
    api_at, api_rows = api_usage(api)
    status_at, status_rows = status_usage(status)
    if status_rows and status_at > api_at:
        return status_at, status_rows
    if api_rows:
        return api_at, api_rows
    return status_at, status_rows


def read_usage(api: Path | None = None, status: Path | None = None) -> list[dict]:
    """Rate-limit windows from the fresher of the two files; [] when neither
    reads."""
    return usage_reading(api, status)[1]


def usage_loop() -> None:
    """Fetch the account's windows every poll."""
    global USAGE_AT
    sampler = quota.Sampler()
    seed_history()
    while True:
        # A poll that fails must not end the loop: the pacer reads nothing
        # else, and a night with no readings admits nothing.
        try:
            quota.fetch(force=True)
            at, fresh = usage_reading()
            if fresh:
                store.USAGE = fresh
                # The same reading again is a cache that did not move, not a
                # fleet that stopped spending, so it adds nothing to the slope.
                if at != USAGE_AT:
                    USAGE_AT = at
                    note_usage(fresh)
            # Pairs each window's utilization with the tokens spent inside it,
            # so the QUOTA_RATE figures can be refit from observation rather
            # than measured by hand.
            sampler.record(config.SAMPLE_FILE)
        except Exception as exc:
            print(f"usage poll failed: {exc!r}", file=sys.stderr)
        time.sleep(config.USAGE_POLL)
