"""The HTML of the ticket dashboard's page (`ticket_dashboard`): the strip
at its top and each section of it, built from the reads of
`dashboard_reads`, the texts of times and of a ticket's status they give,
and the page whole in the template of `dashboard_template`, with the
search's entries of each ticket kept beside it (`Rendered`)."""

import html
import json
import re
import time
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dashboard_reads import (DAY, OPEN, STALE_RECORD, Stage, change_of, hits_full, phrase, stage,
                             users)
from dashboard_template import EVENTS, LAST_LOOK, SEARCH_ROUTE, TEMPLATE, TICKET_ROUTE
from state_assembly import ScriptAdmits, Shown, ShownAgent, ShownParty, Start
from ticket_reads import read_tickets
from usage_limit import Reading

from operations.roles import Role
from operations.pacing import Capped, Until, Usage, WindowName
from operations.parties import Hold, OnTicket
from operations.state import NotComputed, Ticket
from operations.tracker import blocked_on_user
from ticketing.vocabulary import Kind, Resolution, Status

WEEKLY_LIMIT = 8400.0
"""The weekly usage limit in dollars, as
`prompts/agents/notes/decisions.md#cost-and-time` gives it."""

NOTE_WORDS = 18
"""The most words of a log line's note the page gives."""

FIRST_STARTS = 8
"""The most tickets Up next gives of those set to start."""

PAUSED_STARTS = 15
"""The most tickets Up next gives of those the `Op pause.` line holds."""

SINCE_SECONDS = 2 * DAY
"""How far back Since you looked reads the tracker."""

QUEUE_DAYS = 7

STATUS_WORDS: Mapping[Status, str] = {
    Status.DRAFT: "Draft", Status.NEW: "Not started", Status.APPROVED: "Approved, not started",
    Status.REOPENED: "Reopened", Status.RELEASED: "Released, not started", Status.ASSIGNED: "Taken",
    Status.BLOCKED: "Waits on you", Status.WAITING: "Waiting", Status.CLOSED: "Done",
    Status.DEFERRED: "Deferred"}
"""The plain words of each status."""


def esc(s: object) -> str:
    return html.escape(str(s))


def cut(text: str, words: int = NOTE_WORDS) -> str:
    """The first `words` words of `text`, with an ellipsis where it holds
    more."""
    w = text.split()
    return " ".join(w[:words]) + ("…" if len(w) > words else "")


def ago(seconds: float) -> str:
    m = int(seconds // 60)
    if m < 1:
        return "just now"
    if m < 60:
        return f"{m} min"
    h = m // 60
    return f"{h} h" if h < 24 else f"{h // 24} d"


def clock(at: float, now: float) -> str:
    """The local time `at`, with its day where it is not the day of `now`."""
    same = time.localtime(at)[:3] == time.localtime(now)[:3]
    return time.strftime("%-I:%M %p" if same else "%a %-I:%M %p", time.localtime(at))


def hold_text(h: ShownParty) -> str:
    match h:
        case Hold.PAUSE:
            return "Held by your pause"
        case Hold.OWN_SCOPE:
            return "Held by your own-scope line"
        case Hold.PACE:
            return "Held by the usage pace"
        case Hold.TAKES:
            return "Held by the run scripts' takes"
        case OnTicket(number):
            return f"Starts after {number}"


def start_hold_text(h: ScriptAdmits | Until | NotComputed | Capped, now: float) -> str:
    match h:
        case Until(at, _):
            return f"The pace holds agent starts until {clock(at, now)}"
        case Capped(cap):
            return f"The pace's cap of {cap} running agents holds agent starts"
        case ScriptAdmits():
            return "The pace script holds agent starts"
        case NotComputed(why):
            return f"Agent starts are held: the pace is not computed ({why})"


def role_words(r: Role) -> str:
    return r.value.replace("-", " ")


def tap(n: str, inner: str, cls: str = "row") -> str:
    """`inner` in an element whose tap opens the sheet of ticket `n`."""
    tag = "button" if cls == "card" else "div"
    return f'<{tag} class="{cls} tk" data-n="{esc(n)}">{inner}</{tag}>'


@dataclass(frozen=True)
class Entry:
    """A ticket as the search and its sheet give it: its phrase and the
    plain sentence on its status."""
    ticket: Ticket
    phrase: str
    status: str


@dataclass(frozen=True)
class Rendered:
    """A render of the page: its text, the search's entry of each ticket in
    the tracker's order, and the time of the render."""
    text: str
    entries: Mapping[str, Entry]
    at: float


@dataclass(frozen=True)
class View:
    """What the sections of one render read: the tracker's tickets in its
    order, the operator's record or why there is none, the usage, the
    time, the tickets expedited, the pending agents by ticket number, and
    the party that holds each ticket the operators start next."""
    all_: Mapping[str, Ticket]
    state: Shown | str
    usage: Usage
    now: float
    expedited: frozenset[str]
    agents: Mapping[str, list[ShownAgent]]
    holds: Mapping[str, ShownParty]

    def mine(self, t: Ticket) -> bool:
        return users(t, self.expedited)

    def phrase(self, t: Ticket) -> str:
        return phrase(t, self.all_)

    def working(self, t: Ticket) -> list[ShownAgent]:
        """The agents at work on `t` or on its change."""
        c = change_of(t, self.all_)
        return [*self.agents.get(t.number, []), *([] if c is None else self.agents.get(c.number, []))]

    def status(self, t: Ticket) -> str:
        """The plain sentence on the status of `t`."""
        if t.status is Status.CLOSED:
            last = t.log[-1]
            return f"Done {clock(last.time, self.now)}" + ("" if last.resolution is None else f" · {last.resolution}")
        if w := self.working(t):
            a = max(w, key=lambda a: a.launched)
            return f"{role_words(a.role).capitalize()} at work, {ago(self.now - a.launched)}"
        if (c := change_of(t, self.all_)) is not None:
            return f"Waiting on {c.number} ({self.phrase(c)})"
        if (h := self.holds.get(t.number)) is not None:
            return hold_text(h)
        return STATUS_WORDS[t.status]


def strip(v: View, mine: int) -> str:
    ops = "Ops: no record" if isinstance(v.state, str) else "Ops paused" if v.state.paused else "Ops running"
    wk = v.usage.windows.get(WindowName.SEVEN_DAY)
    held = not isinstance(v.state, str) and v.state.start_hold is not None
    if wk is None:
        bar, line = "", "Week: the usage cache gives no reading"
    else:
        full = hits_full(v.usage, WindowName.SEVEN_DAY)
        bar = (f'<div class="bar"><i style="width:{min(100, wk.used_pct):.0f}%"></i>'
               f'<b style="left:{min(100, wk.elapsed_pct):.0f}%"></b></div>')
        line = (f"Week {wk.used_pct:.0f}% used, {wk.elapsed_pct:.0f}% elapsed"
                + ("" if full is None else f' · <span class="w">hits 100% {clock(full, v.now)}</span>'))
    line += ' · <span class="w">agent starts held</span>' if held else ""
    return (f'<div class="strip"><div class="r1">{ops} · {mine} in flight</div>{bar}'
            f'<div class="r2">{line}</div></div>')


def health(v: View, notes: list[str]) -> str:
    """The HTML of Health: the user's tickets that wait on nothing, the
    hold of agent starts, a stale record, no agent at work, and `notes`,
    the lines of the reads that did not decide."""
    out = [f'<div class="alert">⚠ {esc(n)}</div>' for n in notes]
    if isinstance(v.state, str):
        return "".join(out) + f'<div class="alert">⚠ {esc(v.state)}</div>'
    out += [tap(n, f"⚠ <b>{esc(n)}</b> {esc(v.phrase(v.all_[n]))} · waits on nothing for {ago(v.now - since)}", "alert")
           for n, since in v.state.unwaited.items() if n in v.all_ and v.mine(v.all_[n])]
    if v.state.start_hold is not None:
        out.append(f'<div class="alert">⏸ {esc(start_hold_text(v.state.start_hold, v.now))}</div>')
    if v.now - v.state.at > STALE_RECORD:
        out.append(f'<div class="alert">⚠ No operator has read the state since {clock(v.state.at, v.now)}</div>')
    if not v.state.agents:
        out.append('<div class="alert">⚠ No agent is at work</div>')
    return "".join(out) or '<div class="ok">✓ All moving</div>'


def stepper(s: Stage) -> str:
    return '<div class="steps">' + "".join(
        f'<span class="st {"done" if k < s else "now" if k == s else ""}">{k.name.capitalize()}</span>'
        for k in Stage) + "</div>"


def in_flight(v: View) -> tuple[str, int]:
    """The HTML of In flight, and the count of the user's tickets it gives
    a card."""
    open_ = [t for t in v.all_.values() if t.status in OPEN]
    carried = {c.number for t in open_ if (c := change_of(t, v.all_)) is not None}
    flying: list[tuple[Ticket, list[ShownAgent]]] = []
    for t in open_:
        if t.number in carried or (t.kind is Kind.CHANGE and any(
                m in v.all_ and v.all_[m].status in OPEN for m in t.motivation)):
            continue
        if w := v.working(t):
            flying.append((t, w))
    mine = sorted([x for x in flying if v.mine(x[0])], key=lambda x: (x[0].number not in v.expedited, -x[0].filed))
    other = [x for x in flying if not v.mine(x[0])]
    running = {t.number for t, _ in flying}

    def star(t: Ticket) -> str:
        return '<span class="star" title="expedited">★</span>' if t.number in v.expedited else ""

    def card(t: Ticket, w: list[ShownAgent]) -> str:
        a = max(w, key=lambda a: a.launched)
        return tap(t.number, f'{star(t)}<span class="num">{esc(t.number)}</span> <span class="sh">{esc(v.phrase(t))}</span>'
                   f'{stepper(stage([x.role for x in w], change_of(t, v.all_) or t))}'
                   f'<div class="meta">{esc(role_words(a.role))} · {ago(v.now - a.launched)}</div>', "card")

    waiting = [v.all_[n] for n in sorted(v.expedited) if n in v.all_ and v.all_[n].status in OPEN
               and n not in running and n not in carried]
    out = "".join(card(t, w) for t, w in mine) or '<div class="meta">Nothing of yours is running.</div>'
    out += "".join(tap(t.number, f'{star(t)}<span class="num">{esc(t.number)}</span> <span class="sh">{esc(v.phrase(t))}</span>'
                       f'<div class="meta">{esc(v.status(t))}</div>', "card") for t in waiting)
    if other:
        out += (f"<details><summary>{len(other)} more from reviews and checks</summary>"
                + "".join(tap(t.number, f'<span class="num">{esc(t.number)}</span> {esc(v.phrase(t))}') for t, _ in other)
                + "</details>")
    return out, len(mine)


def up_next(v: View) -> str:
    if isinstance(v.state, str):
        return f'<div class="meta">{esc(v.state)}</div>'
    starts = [s for s in v.state.starts if s.number in v.all_]
    starts.sort(key=lambda s: not v.mine(v.all_[s.number]))
    first = [s for s in starts if s.held is None] + [s for s in starts if s.held not in (None, Hold.PAUSE)]
    paused = [s for s in starts if s.held is Hold.PAUSE]

    def line(s: Start) -> str:
        t = v.all_[s.number]
        star = '<span class="star">★</span>' if t.number in v.expedited else ""
        return tap(t.number, f'{star}<span class="num">{esc(t.number)}</span> {esc(v.phrase(t))}'
                   f' <span class="meta">· {esc(v.status(t))}</span>')

    out = '<div class="card">' + ("".join(line(s) for s in first[:FIRST_STARTS])
                                  or '<div class="meta">Nothing is set to start.</div>')
    if len(first) > FIRST_STARTS:
        out += f'<div class="meta">+{len(first) - FIRST_STARTS} more set to start</div>'
    out += "</div>"
    if paused:
        out += (f"<details><summary>{len(paused)} start once your pause ends</summary>"
                + "".join(line(s) for s in paused[:PAUSED_STARTS])
                + (f'<div class="meta">+{len(paused) - PAUSED_STARTS} more</div>' if len(paused) > PAUSED_STARTS else "")
                + "</details>")
    return out


def events(v: View) -> list[dict[str, object]]:
    """The filings and the merges of the last `SINCE_SECONDS`, newest
    first, each with whether its ticket is the user's, and the number and
    phrase of a ticket of the user's, which the page lists, where it
    counts the others."""
    found: list[tuple[float, str, Ticket]] = []
    for t in v.all_.values():
        if v.now - t.filed <= SINCE_SECONDS:
            found.append((t.filed, "filed", t))
        if t.kind is Kind.CHANGE:
            found.extend((ln.time, "merged", t) for ln in t.log if ln.status is Status.CLOSED
                         and ln.resolution is Resolution.FIXED and v.now - ln.time <= SINCE_SECONDS)
    found.sort(key=lambda e: -e[0])
    return [{"t": round(at), "k": kind, "n": t.number, "u": True, "s": v.phrase(t)} if v.mine(t)
            else {"t": round(at), "k": kind, "u": False} for at, kind, t in found]


def kv(k: str, val: str) -> str:
    return f'<div class="kv"><span>{esc(k)}</span><span>{val}</span></div>'


def pace(v: View) -> str:
    wk = v.usage.windows.get(WindowName.SEVEN_DAY)
    fh = v.usage.windows.get(WindowName.FIVE_HOUR)
    full = hits_full(v.usage, WindowName.SEVEN_DAY)
    if wk is None:
        head = "Week: no reading"
    elif full is not None:
        head = (f'Week {wk.used_pct:.0f}% · <span class="w">at this rate, 100% {clock(full, v.now)},'
                f' {ago(wk.resets_at - full)} before reset</span>')
    else:
        head = f"Week {wk.used_pct:.0f}% · on track: {wk.used_pct / max(wk.elapsed_pct, 1) * 100:.0f}% at reset"
    line = ("no record" if isinstance(v.state, str) else
            "default (five-hour, even)" if v.state.pace_line is None else v.state.pace_line)
    rows = [kv("Pace line", esc(line))]
    if fh is None:
        rows.append(kv("5-hour window", "no reading"))
    else:
        fh_full = hits_full(v.usage, WindowName.FIVE_HOUR)
        rows += [kv("5-hour window", f"{fh.used_pct:.0f}% used, {fh.elapsed_pct:.0f}% elapsed"),
                 kv("5-hour resets", clock(fh.resets_at, v.now))]
        if fh_full is not None:
            rows.append(kv("5-hour 100% at", f'<span class="w">{clock(fh_full, v.now)}</span>'))
    if wk is not None:
        rows.append(kv("Week resets", time.strftime("%a %b %-d, %-I:%M %p", time.localtime(wk.resets_at))))
    rows.append(kv("1% of the week", f"${WEEKLY_LIMIT / 100:,.0f}"))
    return f"<details><summary>{head}</summary>{''.join(rows)}</details>"


def queue(v: View) -> str:
    open_ = [t for t in v.all_.values() if t.status in OPEN]
    paused = 0 if isinstance(v.state, str) else sum(1 for s in v.state.starts if s.held is Hold.PAUSE)
    by = Counter(v.mine(t) for t in open_)
    days = []
    for d in range(QUEUE_DAYS - 1, -1, -1):
        lo, hi = v.now - (d + 1) * DAY, v.now - d * DAY
        days.append((time.strftime("%a", time.localtime(hi - 1)),
                     sum(1 for t in v.all_.values() if lo <= t.filed < hi),
                     sum(1 for t in v.all_.values() for ln in t.log if ln.status is Status.CLOSED and lo <= ln.time < hi)))
    top = max([1, *(f for _, f, _ in days), *(c for _, _, c in days)])
    bars = "".join(f'<div><i style="height:{100 * f / top:.0f}%"></i><i class="c" style="height:{100 * c / top:.0f}%"></i></div>'
                   for _, f, c in days)
    return (f"<details><summary>{len(open_)} open · {paused} held by your pause</summary>"
            + kv("Held by your pause", str(paused))
            + kv("Waiting on another ticket", str(sum(1 for t in open_ if t.status is Status.WAITING)))
            + kv("Filed by you or the coordinator", str(by[True]))
            + kv("Filed by reviews and checks", str(by[False]))
            + '<div class="meta" style="margin-top:8px">Filed <span style="color:var(--acc)">■</span>'
              f' and closed <span style="color:var(--ok)">■</span>, last {QUEUE_DAYS} days</div>'
            + f'<div class="days">{bars}</div>'
            + '<div class="dl">' + "".join(f"<span>{d}<br>{f}/{c}</span>" for d, f, c in days) + "</div></details>")


def blocked(v: View) -> tuple[str, int]:
    """The HTML of Blocked, and the count of its tickets."""
    rows = [(t, ln) for t in v.all_.values()
            if (ln := blocked_on_user(t)) is not None]
    body = "".join(tap(t.number, f'<span class="num">{esc(t.number)}</span> <span class="sh">{esc(v.phrase(t))}</span>'
                       f'<div class="meta">{esc(cut(ln.note))}</div>') for t, ln in rows)
    return (f"<details><summary>{len(rows)} wait on your decision</summary>"
            + (body or '<div class="meta">Nothing waits on you.</div>') + "</details>"), len(rows)


def page(tickets: Path, now: float, usage: Reading, state: Shown | str,
         undecided: list[str]) -> Rendered:
    """The page at `now`, with the `undecided` lines of its reads."""
    read, unread = read_tickets(tickets)
    all_ = dict(sorted(read.items(), key=lambda kv: kv[1].order))
    agents: dict[str, list[ShownAgent]] = {}
    if not isinstance(state, str):
        for a in state.agents:
            for n in a.tickets:
                agents.setdefault(n, []).append(a)
    v = View(all_, state, usage.usage, now, frozenset(() if isinstance(state, str) else state.expedited),
             agents, {} if isinstance(state, str) else {s.number: s.held for s in state.starts if s.held is not None})
    flight, mine = in_flight(v)
    stuck, waits = blocked(v)
    sections = [
        ("health", "Health", health(v, [*undecided, *(f"unread: {u.path}: {u.why}" for u in unread)])),
        ("flight", "In flight · yours", flight + '<div class="meta" style="font-size:12px">★ expedited</div>'),
        ("next", "Up next", up_next(v)), ("sl", "Since you looked", '<div id="since"></div>'),
        ("pace", "Pace", pace(v)), ("queue", "Queue", queue(v)),
        ("find", "Find a ticket",
         '<input id="q" type="search" placeholder="Number or words" autocomplete="off"><div id="res"></div>'),
        ("blocked", f"Blocked on you · {waits}", stuck),
    ]
    body = (strip(v, mine) + "<main>"
            + "".join(f'<h2 id="{i}">{esc(h)}</h2>{b}' for i, h, b in sections)
            + '<script type="application/json" id="events">'
            + json.dumps(events(v), separators=(",", ":")).replace("<", "\\u003c") + "</script></main>")
    text = filled(TEMPLATE, {"BODY": body, "EVENTS": EVENTS, "SEARCH": SEARCH_ROUTE, "TICKET": TICKET_ROUTE,
                             "LASTLOOK": LAST_LOOK})
    entries = {n: Entry(t, v.phrase(t), v.status(t)) for n, t in all_.items()}
    return Rendered(text, entries, now)


def filled(template: str, parts: Mapping[str, str]) -> str:
    """`template` with each `@NAME@` in it replaced by `parts[NAME]`, in one
    pass, so that no text a part inserts is read as a placeholder."""
    return re.sub(r"@([A-Z]+)@", lambda m: parts[m[1]], template)
