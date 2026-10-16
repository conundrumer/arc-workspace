#!/usr/bin/env python3
"""monitor-console.py — a health digest of the solver console for an agent
watching an unattended autopilot night.

Usage:
    scripts/monitor-console.py              # digest since the last run, then save a snapshot
    scripts/monitor-console.py --peek       # digest without moving the snapshot
    scripts/monitor-console.py --reset      # forget the snapshot, then run
    scripts/monitor-console.py --preflight  # also check the console home's account
    scripts/monitor-console.py --port 8347  # a console on another port

The reader is the agent, not the user. The digest is short on purpose: one
run costs a few hundred tokens of context, so a poll every 50 minutes for a
whole night stays cheap. The script reads the state endpoint, the night log,
the worker logs, the usage cache, and the git lock. It opens no report, feed
body, or transcript. Only stdlib is used, so it runs with `python3` or
`uv run python`.

Cadence: poll at most every 50 minutes (a ScheduleWakeup of 3000 seconds).
Longer waits let the prompt cache of the monitoring session go cold. Shorter
polls buy nothing, since the pacer itself acts every minute.

How to read the digest
----------------------
Each run prints these sections, then FLAGS. When FLAGS is empty, nothing
needs a hand and the next poll is the whole response.

server    Whether the state endpoint answered, and how far `seq` moved since
          the snapshot. Autopilot on, items live, and no movement across a
          whole poll is a stall.
night     The mode's dials, its gate (open or held, and why), and each slot's
          live count against its target. Under exhaust the targets are upper
          bounds only; the pacer sizes the fleet from measured spend.
windows   The usage cache's age and the console account's OAuth token
          expiry, then each rate-limit window: percent used, time to reset,
          the pacer's rate (points an hour), one item's share, the window's
          budget, plus the rate measured across this poll and the percent
          the window will reach at its reset if the poll's rate holds.
items     Counts by state, the turns in flight with their ages, and items
          waiting on a resume after a usage limit.
progress  What happened since the snapshot: admissions, sessions
          launched, handoffs to the next stage, turns done with the points
          they spent, cold turns (cache write above cache read), usage
          limits hit, and callouts on record. The first run after a reset
          has no snapshot and prints no deltas.
logs      New lines in the worker logs and the server log that match an
          error pattern. The server log exists only when the server was
          started with its stderr captured:
              just console 2>&1 | tee tools/console/state/server.log
          Without it the pacer's own failures ("overnight pass failed",
          "usage poll failed") are visible nowhere.
git       A stale index lock. Workers commit through git, so a lock left by
          a killed process blocks every commit.
night log The night log lines added since the snapshot.

The flags and what to do about them
-----------------------------------
Each flag names its threshold and carries a level. The levels are what to
do, in order of how much they cost:

BRAKE  Post autopilot off. Admissions stop and the turns in flight finish.
       It costs nothing and burns nothing, so it is the default for anything
       not diagnosed within a few minutes:
           curl -sX POST localhost:8347/api/night -d '{"on": false}'
FIX    A tooling fault. Diagnose, then edit. See "Editing the console while
       it runs" below.
NOTE   Report it to the user; do not act. Solver turns are the solvers'
       business.

server down              The endpoint did not answer. Check the process
                         (`pgrep -f tools/console/server.py`). Only a dead
                         process is restarted; a restart loses the turns in
                         flight, so a live server is never restarted for a
                         code change. FIX.
seq stalled              Autopilot on, items live, seq unchanged since the
                         snapshot. Read the turns in flight before ruling:
                         one long turn is a NOTE, a fleet that all stopped
                         is a FIX.
usage cache stale        The usage cache is older than 10 minutes. The pacer
                         holds every admission on a stale reading, so the
                         night is wasted quietly. A NOTE while autopilot is
                         off. Check the token line first, then the fetch
                         script under the console home. FIX.
token expired            The console account's OAuth access token is past
                         its expiry. The usage endpoint answers 429 to an
                         expired token, so the cache goes stale, and the
                         pacer then holds every admission. The CLI refreshes
                         the token only when a process under the console
                         home makes a request, so an empty fleet never
                         refreshes it. One cheap call does:
                             CLAUDE_CONFIG_DIR=~/.claude-console claude -p \
                               "reply with the single word ok" \
                               --model claude-haiku-4-5-20251001
                         The next usage poll then succeeds. FIX.
usage flat under load    Turns spent points this poll and no window moved.
                         The fetch reads another account. FIX.
gate open, no admission  Gate open, a slot below target, and no admission
                         across a whole poll. The admitter is broken. FIX.
gate held, fleet empty   Held for budget with nothing live, no spend in
                         the pacer's rate, and the window under half spent.
                         A hold with a rate still showing is the slope
                         lagging the turns that just ended, and clears on
                         its own within its span. FIX.
5h overrun projected     The 5h window is projected past 110 with its reset
                         more than an hour away, by the poll's rate (only
                         when the poll spans 30 minutes or more; a shorter
                         span reads one burst as a trend) and by the
                         window's own average since it opened (once it is
                         30 minutes old), both. The pacer's rule keeps the
                         fleet's rate plus one share under what is left per
                         hour, so a few points over pace is normal and it
                         corrects as the budget shrinks. Past 110 is a
                         fault. FIX, and BRAKE past 130.
usage limit hit          An item hit a usage limit. Each one with the reset
                         more than an hour away is a pacer bug. FIX.
relaunch loop            One item launched, resumed, or lost a session
                         more than twice this poll. Handoffs to the next
                         stage do not count; a fast item hands off twice in
                         an hour. A relaunch loop with a cold cache is the
                         way to burn millions of tokens. BRAKE, then FIX.
long turn                A turn older than 3 hours. NOTE.
spawn stuck              A worker spawning across two polls with no turn.
                         Look at its worker log for an auth error. FIX.
worker log error         A new worker log line matched an error pattern.
                         An auth or keychain line is a FIX; a single tool
                         error inside a turn is a NOTE.
server log error         A new server log line matched. FIX.
stale git lock           `.git/index.lock` older than 10 minutes with no git
                         process alive. Remove the lock. FIX.

Editing the console while it runs
---------------------------------
The server re-execs itself when `tools/console/server.py` or a module under
`tools/console/solver_console/` changes, at its next quiet moment (no turn
in flight, nothing queued). The exec replaces the process before the new
code is imported, so a file with an import-time error kills the server and
loses the workers. Never save a broken file over a watched one:

- For a small edit, write the new text to a copy, run `python -m py_compile`
  on the copy, then move the copy over the watched file. One rename is one
  mtime change.
- For a larger edit, make it in a git worktree, run `python -m py_compile`
  on each file it changes there, then apply the same edit to the main tree
  with one write.
- A busy fleet is rarely quiet, so a reload can wait a long time. Check on
  the next poll that it took: the server log says "server source changed —
  restarting", and the process id stays the same across the exec.

Before the launch
-----------------
- Run `uv run python scripts/context.py`.
- Run this script with `--preflight`. It shows the account the console home
  is logged into and the account of the user's own home; they must differ.
- Set the dials on the night endpoint, for example
  `{"pace": "exhaust", "source": "both", "on": true}`, and confirm them in
  the night section of the next run.
- Start the server with its stderr captured (see the logs section above).

Snapshot
--------
The snapshot lives at `tools/console/state/monitor.json`, inside the
console's ignored state dir. It holds the last poll's time, seq, usage rows,
per-item feed counts, per-item worker state, and log sizes. `--reset` drops
it; the first run after a reset reports no deltas.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = Path(os.environ.get("CONSOLE_STATE_DIR", ROOT / "tools/console/state"))
SNAPSHOT = STATE_DIR / "monitor.json"
LOG_DIR = STATE_DIR / "logs"
SERVER_LOG = STATE_DIR / "server.log"
REPORT_DIR = STATE_DIR / "reports"
CLAUDE_HOME = Path(os.environ.get("CONSOLE_CLAUDE_HOME", Path.home() / ".claude-console"))
USAGE_API = CLAUDE_HOME / "usage-api.json"
USAGE_STATUS = CLAUDE_HOME / "usage.json"

USAGE_STALE = 10 * 60
LONG_TURN = 3 * 3600
LOCK_STALE = 10 * 60
RELAUNCHES = 2          # session starts per item per poll above which it is a loop
HELD_EMPTY_PCT = 50     # a budget hold with nothing live is suspect under this
PROJECT_SPAN = 30 * 60  # a poll shorter than this reads one burst as a trend
OVERRUN = 110           # projected percent at reset that is a fault, not pace noise
OVERRUN_BRAKE = 130
WINDOW_HOURS = {"5h": 5.0, "wk": 168.0, "fbl": 168.0}
BUSY = ("spawning", "sending", "running")
ERROR_RE = re.compile(r"not logged in|invalid api key|authentication|unauthorized|"
                      r"keychain|oauth|traceback|error|429|rate.?limit", re.I)
TURN_RE = re.compile(r"^turn done · (?P<dur>\S+) · (?P<rest>.*)$")
POINT_RE = re.compile(r"\b(5h|wk|fbl) ([\d.]+)%")
CACHE_RE = re.compile(r"cache r ([\d,]+) w ([\d,]+)")
# Feed events that mean a session process started outside the chain's own
# handoffs, and the resume brief the console sends after a usage limit.
LAUNCHED = ("launched", "session lost on reload", "worker exited without result")
RESUMED = "your previous turn was cut off by a usage limit"
HANDOFF = "session starting"


def num(s: str) -> int:
    return int(s.replace(",", ""))


def hhmm(t: float | None) -> str:
    return time.strftime("%H:%M", time.localtime(t)) if t else "—"


def age(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 3600:
        return f"{seconds // 60}m"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


def fetch_state(port: int) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state", timeout=5) as r:
            return json.load(r)
    except (urllib.error.URLError, OSError, ValueError):
        return None


def load_snapshot() -> dict:
    try:
        return json.loads(SNAPSHOT.read_text())
    except (OSError, ValueError):
        return {}


def file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def new_lines(path: Path, offset: int) -> list[str]:
    """The lines a file gained past `offset` bytes; the file's tail when it
    shrank (a fresh log under the same name)."""
    size = file_size(path)
    if size == offset:
        return []
    try:
        with path.open("rb") as f:
            f.seek(offset if offset < size else 0)
            return f.read().decode(errors="replace").splitlines()
    except OSError:
        return []


class Digest:
    def __init__(self):
        self.lines: list[str] = []
        self.flags: list[tuple[str, str]] = []

    def section(self, name: str):
        self.lines.append(f"[{name}]")

    def say(self, text: str):
        self.lines.append("  " + text)

    def flag(self, level: str, text: str):
        self.flags.append((level, text))

    def render(self) -> str:
        out = list(self.lines)
        out.append("[FLAGS]")
        if not self.flags:
            out.append("  none")
        for level, text in sorted(self.flags, key=lambda f: ("BRAKE", "FIX", "NOTE").index(f[0])):
            out.append(f"  {level:5} {text}")
        return "\n".join(out)


def usage_age(now: float) -> float | None:
    """Seconds since the fresher usage cache was written; None when neither exists."""
    ages = [now - p.stat().st_mtime for p in (USAGE_API, USAGE_STATUS) if p.exists()]
    return min(ages) if ages else None


def token_expiry(home: Path) -> float | None:
    """When the home's OAuth access token expires, from the keychain item the
    CLI keeps for that config dir; None when it cannot be read."""
    if sys.platform != "darwin":
        return None
    import hashlib
    service = "Claude Code-credentials-" + hashlib.sha256(str(home).encode()).hexdigest()[:8]
    try:
        out = subprocess.run(["security", "find-generic-password", "-s", service, "-w"],
                             capture_output=True, text=True, timeout=10)
        return json.loads(out.stdout)["claudeAiOauth"]["expiresAt"] / 1000
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return None


def account(home: Path | None) -> str:
    env = dict(os.environ)
    env.pop("CLAUDE_CONFIG_DIR", None)
    if home is not None:
        env["CLAUDE_CONFIG_DIR"] = str(home)
    try:
        out = subprocess.run(["claude", "auth", "status", "--json"], env=env,
                             capture_output=True, text=True, timeout=20)
        return json.loads(out.stdout).get("email") or "(not logged in)"
    except (OSError, ValueError, subprocess.SubprocessError):
        return "(auth status failed)"


def turn_events(feed: list[dict]) -> list[dict]:
    """The `turn done` events of a feed, parsed: points per window and cache
    counts."""
    out = []
    for e in feed:
        if e.get("kind") != "event":
            continue
        m = TURN_RE.match(e.get("text", ""))
        if not m:
            continue
        points = {k: float(v) for k, v in POINT_RE.findall(m.group("rest"))}
        cache = CACHE_RE.search(m.group("rest"))
        out.append({"dur": m.group("dur"), "points": points,
                    "r": num(cache.group(1)) if cache else 0,
                    "w": num(cache.group(2)) if cache else 0})
    return out


def run(args) -> int:
    now = time.time()
    d = Digest()
    prev = {} if args.reset else load_snapshot()
    since = prev.get("t")
    span_h = (now - since) / 3600 if since else None
    d.lines.append(f"monitor · {hhmm(now)} · since {hhmm(since)}"
                   + (f" ({age(now - since)})" if since else " (no snapshot)"))

    state = fetch_state(args.port)
    d.section("server")
    if state is None:
        d.say(f"no answer on port {args.port}")
        d.flag("FIX", "server down — check `pgrep -f tools/console/server.py`; "
                      "restart only if the process is gone")
        print(d.render())
        return 1
    seq, prev_seq = state["seq"], prev.get("seq")
    d.say(f"seq {seq}" + (f" (+{seq - prev_seq})" if prev_seq is not None else ""))

    night = state.get("night") or {}
    gate = night.get("gate") or {}
    items = state.get("items") or []
    on = bool(night.get("on"))

    d.section("night")
    d.say(f"autopilot {'on' if on else 'off'} · pace {night.get('pace')} · "
          f"source {night.get('source')} · target {night.get('target')} · "
          f"finalize_target {night.get('finalize_target')}")
    slots = night.get("slots") or []
    d.say("slots " + " · ".join(f"{s['kind']} {s['live']}/{s['target']}" for s in slots)
          + f" · live items {night.get('live')} · landed tonight {night.get('landed')}")
    if gate:
        d.say(("gate open · " if gate.get("open") else "gate held · ") + str(gate.get("why")))
    nxt = night.get("next")
    if nxt:
        d.say(f"next: {nxt['what']} at {hhmm(nxt['at'])}")

    d.section("windows")
    ua = usage_age(now)
    rows = {r["label"]: r for r in state.get("usage") or []}
    prev_rows = prev.get("usage") or {}
    pacer_rows = {w["label"]: w for w in gate.get("windows") or []}
    exp = token_expiry(CLAUDE_HOME)
    token = ("unreadable" if exp is None else
             f"expired {age(now - exp)} ago" if exp < now else f"valid {age(exp - now)}")
    d.say(f"usage cache age {age(ua) if ua is not None else 'no file'} · token {token}")
    if exp is not None and exp < now:
        d.flag("FIX", f"token expired — the console account's token lapsed {age(now - exp)} "
                      "ago; one Haiku call under the console home refreshes it")
    elif ua is None or ua > USAGE_STALE:
        d.flag("FIX" if on else "NOTE",
               f"usage cache stale ({age(ua) if ua is not None else 'no file'}) — "
               f"the pacer holds on it; check the fetch under {CLAUDE_HOME}")
    moved = False
    for label, r in rows.items():
        pct, reset = r["pct"], r.get("reset")
        to_reset_h = (reset - now) / 3600 if reset else None
        parts = [f"{label} {pct:.1f}%",
                 f"reset in {age(reset - now) if reset else '?'}"]
        p = pacer_rows.get(label)
        if p:
            parts.append(f"pacer rate {p['rate']:.1f} + share {p['share']:.1f} "
                         f"vs budget {p['budget']:.1f}/h")
        pr = prev_rows.get(label)
        projections = []
        window_h = WINDOW_HOURS.get(label)
        # The window's own average reads a trend only once it has run a
        # while; the first minutes after a reset are one burst.
        if to_reset_h is not None and window_h and \
                (window_h - to_reset_h) * 3600 >= PROJECT_SPAN:
            avg_rate = pct / (window_h - to_reset_h)
            projections.append(pct + avg_rate * to_reset_h)
            parts.append(f"window avg {avg_rate:.1f}/h")
        if pr and span_h and span_h > 0:
            same_window = pr.get("reset") == reset or pct >= pr["pct"]
            if same_window:
                poll_rate = (pct - pr["pct"]) / span_h
                moved = moved or pct != pr["pct"]
                parts.append(f"poll rate {poll_rate:.1f}/h")
                if to_reset_h is not None and span_h * 3600 >= PROJECT_SPAN:
                    projections.append(pct + poll_rate * to_reset_h)
            else:
                parts.append("window rolled over")
                moved = True
        if projections:
            projected = min(projections)
            parts.append(f"→ {projected:.0f}% at reset")
            if (label == "5h" and projected > OVERRUN
                    and to_reset_h is not None and to_reset_h > 1):
                d.flag("BRAKE" if projected > OVERRUN_BRAKE else "FIX",
                       f"5h overrun projected ({projected:.0f}% at reset, "
                       f"{age(reset - now)} away)")
        d.say(" · ".join(parts))

    d.section("items")
    by_state: dict[str, int] = {}
    for it in items:
        by_state[it["state"]] = by_state.get(it["state"], 0) + 1
    d.say(" · ".join(f"{k} {v}" for k, v in sorted(by_state.items())) or "no items")
    turns = [(it, now - it["turnStarted"]) for it in items
             if it.get("turnPhase") and it.get("turnStarted")]
    for it, dur in sorted(turns, key=lambda t: -t[1]):
        d.say(f"turn {it['id']} {it['turnPhase']} {age(dur)}")
        if dur > LONG_TURN:
            d.flag("NOTE", f"long turn — {it['id']} {it['turnPhase']} running {age(dur)}")
    prev_spawning = set(prev.get("spawning") or [])
    spawning = []
    for it in items:
        busy = it.get("busy") or {}
        if any(busy.values()) and not it.get("turnPhase"):
            spawning.append(it["id"])
            if it["id"] in prev_spawning:
                d.flag("FIX", f"spawn stuck — {it['id']} has been spawning since the last poll; "
                              f"read {LOG_DIR / (it['id'] + '.log')}")
    if spawning:
        d.say("spawning " + ", ".join(spawning))
    waiting = [it for it in items if it.get("resume_at")]
    for it in waiting:
        d.say(f"resume waits: {it['id']} at {hhmm(it['resume_at'])}")

    d.section("progress")
    prev_items = prev.get("items") or {}
    starts = handoffs = turns_done = cold = limits = 0
    spent: dict[str, float] = {}
    loops = []
    reports_now = sum(it.get("callout_n") or 0 for it in items)
    # The light items on the state endpoint carry no feed, so the per-item
    # events come from the state file, which the server writes on every change.
    try:
        full = json.loads((STATE_DIR / "state.json").read_text())["items"]
    except (OSError, ValueError, KeyError):
        full = []
    item_snap: dict[str, dict] = {}
    for it in full:
        feed = it.get("feed") or []
        events = [e.get("text", "") for e in feed if e.get("kind") == "event"]
        n_start = sum(1 for t in events if t.startswith(LAUNCHED)) + \
            sum(1 for e in feed if e.get("kind") == "you"
                and e.get("text", "").startswith(RESUMED))
        n_hand = sum(1 for t in events if HANDOFF in t)
        n_limit = sum(1 for t in events if t.startswith("usage limit"))
        tev = turn_events(feed)
        pi = prev_items.get(it["id"], {})
        d_start = n_start - pi.get("starts", 0)
        d_limit = n_limit - pi.get("limits", 0)
        new_turns = tev[pi.get("turns", 0):]
        if since:
            starts += max(d_start, 0)
            handoffs += max(n_hand - pi.get("handoffs", 0), 0)
            limits += max(d_limit, 0)
            turns_done += len(new_turns)
            for t in new_turns:
                for k, v in t["points"].items():
                    spent[k] = spent.get(k, 0) + v
                if t["w"] > t["r"]:
                    cold += 1
            if d_start > RELAUNCHES:
                loops.append((it["id"], d_start))
            if d_limit > 0:
                d.flag("FIX", f"usage limit hit — {it['id']} ({d_limit} this poll)")
        item_snap[it["id"]] = {"starts": n_start, "handoffs": n_hand,
                               "limits": n_limit, "turns": len(tev)}
    prev_reports = prev.get("reports")
    if since:
        d.say(f"launched {starts} · handoffs {handoffs} · turns done {turns_done} · "
              f"cold turns {cold} · usage limits {limits} · callouts on record {reports_now}"
              + (f" ({reports_now - prev_reports:+d})" if prev_reports is not None else ""))
    else:
        d.say(f"no snapshot; deltas start next run · callouts on record {reports_now}")
    if spent:
        d.say("points spent by turns: " + " · ".join(f"{k} {v:.1f}" for k, v in spent.items()))
    for item_id, n in loops:
        d.flag("BRAKE", f"relaunch loop — {item_id} started {n} sessions this poll")
    log_since = [e for e in night.get("log") or [] if not since or e["t"] > since]
    admitted = sum(1 for e in log_since if e["text"].startswith("admitted"))
    if since and on:
        below = [s for s in slots if s["live"] < s["target"]]
        if gate.get("open") and below and admitted == 0 and starts == 0:
            d.flag("FIX", "gate open, no admission — a slot is below target and nothing "
                          "was admitted across the poll")
        if not gate.get("open") and night.get("live") == 0 and \
                "over budget" in str(gate.get("hold", "")):
            label = str(gate.get("hold")).split()[0]
            pct = rows.get(label, {}).get("pct", 0)
            if pct < HELD_EMPTY_PCT and pacer_rows.get(label, {}).get("rate", 0) < 1:
                d.flag("FIX", f"gate held, fleet empty — {gate.get('why')}")
        if seq == prev_seq and night.get("live"):
            d.flag("FIX", "seq stalled — autopilot on, items live, nothing changed "
                          "since the last poll")
        if spent.get("5h", 0) > 0.5 and rows and not moved:
            d.flag("FIX", "usage flat under load — turns spent points and no window moved; "
                          "the fetch may read another account")

    d.section("logs")
    prev_sizes = prev.get("log_sizes") or {}
    sizes: dict[str, int] = {}
    hits = 0
    for p in sorted(LOG_DIR.glob("*.log")) if LOG_DIR.exists() else []:
        sizes[p.name] = file_size(p)
        if p.name not in prev_sizes and since:
            prev_sizes[p.name] = 0
        if p.name in prev_sizes:
            for line in new_lines(p, prev_sizes[p.name]):
                if ERROR_RE.search(line):
                    hits += 1
                    if hits <= 8:
                        d.say(f"{p.name}: {line.strip()[:160]}")
                        d.flag("FIX" if re.search(r"logged in|api key|auth|keychain|oauth|429",
                                                  line, re.I) else "NOTE",
                               f"worker log error — {p.name}: {line.strip()[:100]}")
    if SERVER_LOG.exists():
        sizes["server.log"] = file_size(SERVER_LOG)
        for line in new_lines(SERVER_LOG, prev_sizes.get("server.log", 0)):
            if "restarting" in line:
                d.say(f"server.log: {line.strip()[:160]}")
            elif ERROR_RE.search(line) or "failed" in line:
                hits += 1
                d.say(f"server.log: {line.strip()[:160]}")
                d.flag("FIX", f"server log error — {line.strip()[:100]}")
    else:
        d.say("no server.log — start the server with `just console 2>&1 | tee "
              f"{SERVER_LOG}` to see the pacer's own failures")
    if not hits:
        d.say("no new error lines")

    d.section("git")
    lock = ROOT / ".git/index.lock"
    if lock.exists():
        lock_age = now - lock.stat().st_mtime
        git_alive = subprocess.run(["pgrep", "-x", "git"], capture_output=True).returncode == 0
        d.say(f"index.lock present, {age(lock_age)} old, "
              f"git {'running' if git_alive else 'not running'}")
        if lock_age > LOCK_STALE and not git_alive:
            d.flag("FIX", f"stale git lock — remove {lock}")
    else:
        d.say("no index.lock")

    d.section("night log")
    for e in log_since[-12:]:
        d.say(f"{hhmm(e['t'])} {e['text']}")
    if not log_since:
        d.say("no new lines")

    if args.preflight:
        d.section("accounts")
        console_acct, main_acct = account(CLAUDE_HOME), account(None)
        d.say(f"console home {CLAUDE_HOME}: {console_acct}")
        d.say(f"your home: {main_acct}")
        if console_acct == main_acct:
            d.flag("FIX", "both homes are logged into the same account")
        fetch = Path.home() / ".claude/scripts/fetch-usage-api.sh"
        d.say(f"fetch script {'present' if fetch.exists() else 'missing'}: {fetch}")

    print(d.render())
    if not args.peek:
        snap = {"t": now, "seq": seq, "usage": rows, "items": item_snap,
                "spawning": spawning, "reports": reports_now, "log_sizes": sizes}
        try:
            SNAPSHOT.write_text(json.dumps(snap))
        except OSError as exc:
            print(f"snapshot not saved: {exc}", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--port", type=int, default=int(os.environ.get("CONSOLE_PORT", 8347)))
    ap.add_argument("--peek", action="store_true", help="do not move the snapshot")
    ap.add_argument("--reset", action="store_true", help="forget the snapshot first")
    ap.add_argument("--preflight", action="store_true",
                    help="also report the accounts of the two Claude homes")
    return run(ap.parse_args())


if __name__ == "__main__":
    sys.exit(main())
