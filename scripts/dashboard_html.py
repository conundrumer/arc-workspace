"""The HTML of the ticket dashboard's page (`ticket_dashboard`): the strip
at its top and each section of it, built from the reads of
`dashboard_reads` and the standing of each open ticket (`Standings`), the
texts of times and of a ticket's status they give, and the page whole in
the template of `dashboard_template`, with the search's entries of each ticket kept beside it (`Rendered`)."""

import html
import json
import re
import time
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from dashboard_reads import (DAY, OPEN, STALE_RECORD, OperatorRecords, Stage, change_of, hits_full, phrase,
                             stage, users)
from dashboard_template import EVENTS, LAST_LOOK, SEARCH_ROUTE, TAB, TEMPLATE, TICKET_ROUTE
from state_assembly import ScriptAdmits, Shown, ShownAgent, ShownParty, Start
from ticket_reads import read_tickets
from usage_limit import Reading

from operations.change_budget import taken
from operations.roles import Role
from operations.pacing import Capped, Until, Usage, WindowName
from operations.parties import Hold, OnTicket
from operations.state import NotComputed, Ticket
from operations.tracker import blocked_on_user
from ticketing.vocabulary import UNTAKEN, Kind, Resolution, Status

WEEKLY_LIMIT = 8400.0
"""The weekly usage limit in dollars, as
`prompts/agents/notes/decisions.md#cost-and-time` gives it."""

NOTE_WORDS = 18
"""The most words of a log line's note the page gives."""

GROUP_SHOWN = 6
"""The most rows a group of held tickets in Queued gives above its fold."""

MERGED_NOTE = "merged"
"""The opening of the note of a log line that gives a released ticket's
change as merged."""

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
    order, the records of the sessions' operators, the usage, the time, the
    tickets expedited, the pending agents by ticket number, the tickets the
    operators start next, and the party that holds each of them that one
    holds."""
    all_: Mapping[str, Ticket]
    records: OperatorRecords
    usage: Usage
    now: float
    expedited: frozenset[str]
    agents: Mapping[str, list[ShownAgent]]
    starts: list[Start]
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


def usage_bar(usage: Usage, name: WindowName, label: str) -> str:
    """The HTML of one row of the strip: `label`, a bar of the used share of
    window `name`, hot where the use is ahead of the elapsed time, with a tick
    at the elapsed share, and the used percent."""
    win = usage.windows.get(name)
    if win is None:
        return (f'<div class="ub"><span class="ul">{esc(label)}</span><div class="bar"></div>'
                '<span class="uv">–</span></div>')
    hot = win.used_pct > win.elapsed_pct
    return (f'<div class="ub"><span class="ul">{esc(label)}</span>'
            f'<div class="bar"><i{' class="hot"' if hot else ""} style="width:{min(100, win.used_pct):.0f}%"></i>'
            f'<b style="left:{min(100, win.elapsed_pct):.0f}%"></b></div>'
            f'<span class="uv{" w" if hot else ""}">{win.used_pct:.0f}%</span></div>')


def per_session[T](v: View, value: Callable[[Shown], T]) -> list[tuple[str, T]]:
    """The `value` of each record, led by its session's name and a space,
    `Main` for a main session with no index, or the one value with an
    empty lead where every record gives it."""
    given = [("Main " if r.index is None else f"{session_name(r.index)} ", value(r.shown)) for r in v.records.records]
    return [("", given[0][1])] if given and all(x == given[0][1] for _, x in given) else given


def strip(v: View, working: int) -> str:
    states = per_session(v, lambda s: "paused" if s.paused else "running")
    ops = ("Ops: no record" if not states else f"Ops {states[0][1]}" if len(states) == 1
           else "Ops: " + ", ".join(f"{lead}{x}" for lead, x in states))
    held = [lead.strip() for lead, h in per_session(v, lambda s: s.start_hold is not None) if h]
    starts = ("" if not held else ' · <span class="w">agent starts held'
              + ("" if held == [""] else f" ({esc(', '.join(held))})") + "</span>")
    return (f'<div class="strip"><div class="r1">{ops} · {working} in flight{starts}</div>'
            f'{usage_bar(v.usage, WindowName.SEVEN_DAY, "Week")}'
            f'{usage_bar(v.usage, WindowName.FIVE_HOUR, "5 h")}</div>')


def health(v: View, notes: list[str]) -> str:
    """The HTML of Health: the user's tickets that wait on nothing, the
    hold of agent starts, a stale record, no agent at work, and `notes`,
    the lines of the reads that did not decide."""
    out = [f'<div class="alert">⚠ {esc(n)}</div>' for n in notes]
    if v.records.main_missing is not None:
        out.append(f'<div class="alert">⚠ {esc(v.records.main_missing)}</div>')
    if not v.records.records:
        return "".join(out)
    out += [tap(n, f"⚠ <b>{esc(n)}</b> {esc(v.phrase(v.all_[n]))} · waits on nothing for {ago(v.now - since)}", "alert")
            for n, since in v.records.unwaited().items() if n in v.all_ and v.mine(v.all_[n])]
    out += [f'<div class="alert">⏸ {esc(lead)}{esc(start_hold_text(h, v.now))}</div>'
            for lead, h in per_session(v, lambda s: s.start_hold) if h is not None]
    out += [f'<div class="alert">⚠ {esc(lead)}No operator has read the state since {clock(at, v.now)}</div>'
            for lead, at in per_session(v, lambda s: s.at if v.now - s.at > STALE_RECORD else None) if at is not None]
    if not v.agents:
        out.append('<div class="alert">⚠ No agent is at work</div>')
    return "".join(out) or '<div class="ok">✓ All moving</div>'


class Standing(Enum):
    """Where an open ticket stands: at work, ready for its session's
    operator to start, waiting on a ticket at work or ready, or held, with
    what holds it."""
    WORKING = auto()
    READY = auto()
    WAITING = auto()
    PAUSED = auto()
    OWN_SCOPE = auto()
    NO_OPERATOR = auto()
    HELD = auto()
    ON_HOLD = auto()


MOVING = frozenset({Standing.WORKING, Standing.READY, Standing.WAITING})
"""The standings of a blocker that leave the ticket it blocks waiting on
it; a blocker held otherwise passes its hold on."""

HELD_HEAD: Mapping[Standing, str] = {
    Standing.PAUSED: "Paused", Standing.OWN_SCOPE: "Outside its own work",
    Standing.NO_OPERATOR: "No operator running", Standing.HELD: "Held by a line",
    Standing.ON_HOLD: "On hold by you"}
"""The head of each group of held tickets in a session's tab of Queued,
in the order of the groups, where the hold is the session's own."""

ELSEWHERE_HEAD: Mapping[Standing, str] = {
    Standing.PAUSED: "Waits on paused {session}", Standing.OWN_SCOPE: "Waits on {session}'s other work",
    Standing.NO_OPERATOR: "Waits on {session}, no operator", Standing.HELD: "Waits on a hold in {session}"}
"""The head of a group whose hold is that of another session, `{session}`."""


class Standings:
    """The standing of each open ticket of a view, as `state` gives it."""

    def __init__(self, v: View) -> None:
        self.v = v
        records = v.records.records
        self.paused = {r.index for r in records if r.shown.paused}
        self.own_scope = {r.index for r in records if r.shown.own_scope}
        self.live = {r.index for r in records}
        self.main = None if v.records.main_missing is not None or not records else records[0].index
        self.open_ = [t for t in v.all_.values() if t.status in OPEN]
        self.carried = {c.number for t in self.open_ if (c := change_of(t, v.all_)) is not None}
        self.motivated: dict[str, list[Ticket]] = {}
        for t in self.open_:
            for m in t.motivation:
                self.motivated.setdefault(m, []).append(t)
        self.position: dict[str, int] = {}
        """The place of each ticket among the starts of its record that no
        hold but the pace holds, in their order."""
        for r in records:
            k = 0
            for st in r.shown.starts:
                if st.number not in self.position and (st.held is None or st.held is Hold.PACE):
                    self.position[st.number] = k
                    k += 1
        self.memo: dict[str, tuple[Standing, Ticket]] = {}

    def shown(self, t: Ticket) -> bool:
        """Whether `t` has a row of its own: a ticket that an open ticket
        waits on as its change, or that an open ticket's Motivation gives,
        shows in that ticket's row, and a released ticket whose log gives
        its change merged has none."""
        if t.number in self.carried:
            return False
        if any(m in self.v.all_ and self.v.all_[m].status in OPEN for m in t.motivation):
            return False
        return not (t.status is Status.RELEASED and any(ln.note.startswith(MERGED_NOTE) for ln in t.log))

    def agents(self, t: Ticket) -> list[ShownAgent]:
        """The agents at work on `t`, on its change, or on an open ticket
        whose Motivation gives `t`."""
        return [*self.v.working(t), *(a for x in self.motivated.get(t.number, []) for a in self.v.working(x))]

    def blocker(self, t: Ticket) -> Ticket | None:
        """The first open ticket `depends-on` of `t` gives, else the open
        change `t` waits on."""
        deps = [d for d in t.depends_on if d in self.v.all_ and self.v.all_[d].status in OPEN]
        if deps:
            return self.v.all_[deps[0]]
        c = change_of(t, self.v.all_)
        return c if c is not None and c.status in OPEN else None

    def own(self, t: Ticket) -> Standing:
        """The standing of `t` apart from its blockers."""
        v = self.v
        c = change_of(t, v.all_)
        if self.agents(t):
            return Standing.WORKING
        if t.status is Status.BLOCKED or (c is not None and c.status is Status.BLOCKED):
            return Standing.ON_HOLD
        if t.session is None or t.session not in self.live:
            return Standing.NO_OPERATOR
        if t.session in self.paused and t.number not in v.expedited:
            return Standing.PAUSED
        if t.session in self.own_scope and not v.mine(t):
            return Standing.OWN_SCOPE
        if t.number in self.position or (t.status in UNTAKEN and t.number not in v.holds):
            return Standing.READY
        return Standing.HELD

    def state(self, t: Ticket, seen: frozenset[str] = frozenset()) -> tuple[Standing, Ticket]:
        """The standing of `t` and the ticket it stands by: `t`'s own
        standing and `t` where it is at work, on hold or has no blocker;
        waiting and its blocker where that blocker's standing is in
        `MOVING`; else the state of its blocker."""
        if t.number in self.memo:
            return self.memo[t.number]
        k = self.own(t)
        b = None if k in (Standing.WORKING, Standing.ON_HOLD) else self.blocker(t)
        if b is None or b.number in seen:
            out = (k, t)
        else:
            bk, root = self.state(b, seen | {t.number})
            out = (Standing.WAITING, b) if bk in MOVING else (bk, root)
        self.memo[t.number] = out
        return out


def stage_bar(s: Stage, at_work: bool) -> str:
    """A bar of one cell for each stage, done up to `s`, and at `s` at work
    where `at_work` holds and stopped otherwise."""
    at = "n" if at_work else "x"
    cells = "".join(f'<b class="{"d" if k < s else at if k == s else ""}"></b>' for k in Stage)
    return f'<span class="mb">{cells}</span>'


def stopped_bar(v: View, t: Ticket) -> str:
    """The stage bar of `t`, which no agent works on, where its change
    passed Triage before its work stopped; else nothing."""
    c = change_of(t, v.all_)
    s = None if c is None else stage([], c)
    return "" if s is None or s is Stage.TRIAGE else stage_bar(s, False)


def row(v: View, t: Ticket, right: str, lead: int | None = None) -> str:
    """The row of `t`, led by `lead` where it is given, with `right` at its
    end."""
    star = '<span class="star">★</span>' if t.number in v.expedited else ""
    p = v.phrase(t)
    return tap(t.number, ("" if lead is None else f'<span class="wq">{lead}</span>')
               + f'<span class="wn">{esc(t.number)}</span><span class="wp">{star}{esc(p[:1].upper() + p[1:])}</span>'
               f'<span class="ws">{right}</span>', "wr" + ("" if lead is None else " ld") + (" me" if v.mine(t) else ""))


def link(n: str) -> str:
    return f'<a class="tk" data-n="{esc(n)}">{esc(n)} ›</a>'


def active(v: View, st: Standings) -> tuple[str, int]:
    """The HTML of Active, the tickets at work in the order of their
    takes, and the count of its rows."""
    rows: list[tuple[float, Ticket, str]] = []
    for t in st.open_:
        if st.shown(t) and (w := st.agents(t)):
            a = max(w, key=lambda a: a.launched)
            c = change_of(t, v.all_)
            s = stage([x.role for x in w], c or t)
            take = taken(c or t)
            rows.append((t.filed if take is None else take.time, t,
                         f"{stage_bar(s, True)}{s.name.capitalize()} · {ago(v.now - a.launched)}"))
    rows.sort(key=lambda r: r[0])
    if not rows:
        return '<div class="meta">Nothing is being worked on.</div>', 0
    return '<div class="wl">' + "".join(row(v, t, r) for _, t, r in rows) + "</div>", len(rows)


def session_line(st: Standings, s: int | None) -> str:
    if s not in st.live:
        return "No operator running"
    if s in st.paused:
        return "Paused" + (" by you" if s == st.main else "")
    if s in st.own_scope:
        return "Running · takes only its own work"
    return "Running"


def tab_word(st: Standings, s: int | None) -> str:
    if s not in st.live:
        return "no operator"
    return "paused" if s in st.paused else "running"


def session_name(s: int | None) -> str:
    return "No session" if s is None else f"S{s}"


def queued(v: View, st: Standings) -> str:
    """The HTML of Queued: a tab for each session that filed a ticket shown
    and not at work, and in it, its operator's state, its tickets ready in
    the order of their starts, those waiting, and the held ones in a group
    for each hold."""
    sessions: dict[int | None, list[tuple[Ticket, Standing, Ticket]]] = {}
    for t in st.open_:
        if not st.shown(t):
            continue
        k, root = st.state(t)
        if k is not Standing.WORKING:
            sessions.setdefault(t.session, []).append((t, k, root))
    if not sessions:
        return '<div class="meta">Nothing is queued.</div>'

    def ordered(xs: list[Ticket]) -> list[Ticket]:
        return sorted(xs, key=lambda t: (not v.mine(t), t.number not in v.expedited,
                                         st.position.get(t.number, len(st.position)), t.filed))

    keys = sorted(sessions, key=lambda s: (s not in st.live, s in st.paused, -len(sessions[s])))
    tabs = "".join(f'<button class="tab" data-s="{s}">{session_name(s)} <small>{tab_word(st, s)}</small></button>'
                   for s in keys)
    panes = ""
    for s in keys:
        items = sessions[s]
        ready = ordered([t for t, k, _ in items if k is Standing.READY])
        waiting = ordered([t for t, k, _ in items if k is Standing.WAITING])
        body = f'<div class="sh2">{esc(session_line(st, s))}</div>'
        if ready:
            body += ('<div class="gh">Next</div><div class="wl">'
                     + "".join(row(v, t, stopped_bar(v, t), i + 1) for i, t in enumerate(ready)) + "</div>")
        if waiting:
            body += ('<div class="gh">Waiting</div><div class="wl">'
                     + "".join(row(v, t, f"{stopped_bar(v, t)}<span>after {link(st.state(t)[1].number)}</span>") for t in waiting)
                     + "</div>")
        groups: dict[tuple[int, bool, str], list[tuple[Ticket, Ticket]]] = {}
        for t, k, root in items:
            if k in MOVING:
                continue
            elsewhere = root.session != s and k in ELSEWHERE_HEAD
            label = ELSEWHERE_HEAD[k].format(session=session_name(root.session)) if elsewhere else HELD_HEAD[k]
            groups.setdefault((list(HELD_HEAD).index(k), elsewhere, label), []).append((t, root))
        for (_, _, label), xs in sorted(groups.items()):
            xs.sort(key=lambda x: (not v.mine(x[0]), x[0].number not in v.expedited, x[0].filed))
            rows = [row(v, t, stopped_bar(v, t) + ("" if root is t else f"<span>via {link(root.number)}</span>"))
                    for t, root in xs]
            inner = '<div class="wl">' + "".join(rows[:GROUP_SHOWN])
            if rows[GROUP_SHOWN:]:
                inner += f"<details><summary>{len(rows) - GROUP_SHOWN} more ›</summary>" + "".join(rows[GROUP_SHOWN:]) + "</details>"
            opened = " open" if label == HELD_HEAD[Standing.ON_HOLD] or any(v.mine(t) for t, _ in xs) else ""
            body += f'<details class="grp"{opened}><summary>{esc(label)} · {len(xs)}</summary>{inner}</div></details>'
        panes += f'<div class="pane" data-s="{s}">{body}</div>'
    return f'<div class="tabs">{tabs}</div>{panes}'


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
    lines = per_session(v, lambda s: "default (five-hour, even)" if s.pace_line is None else s.pace_line)
    line = "; ".join(f"{lead}{x}" for lead, x in lines) or "no record"
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
    paused = sum(1 for s in v.starts if s.held is Hold.PAUSE)
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


def page(tickets: Path, now: float, usage: Reading, records: OperatorRecords,
         undecided: list[str]) -> Rendered:
    """The page at `now`, with the `undecided` lines of its reads."""
    read, unread = read_tickets(tickets)
    all_ = dict(sorted(read.items(), key=lambda kv: kv[1].order))
    starts = records.starts()
    v = View(all_, records, usage.usage, now, records.expedited(), records.agents(), starts,
             {s.number: s.held for s in starts if s.held is not None})
    st = Standings(v)
    work, working = active(v, st)
    stuck, waits = blocked(v)
    sections = [
        ("health", "Health", health(v, [*undecided, *(f"unread: {u.path}: {u.why}" for u in unread)])),
        ("active", "Active", work),
        ("queued", "Queued", queued(v, st)
         + '<div class="key"><span><i></i>filed by you</span><span>★ expedited</span></div>'),
        ("sl", "Since you looked", '<div id="since"></div>'),
        ("pace", "Pace", pace(v)), ("queue", "Queue", queue(v)),
        ("find", "Find",
         '<input id="q" type="search" placeholder="Number or words" autocomplete="off"><div id="res"></div>'),
        ("blocked", f"Blocked on you · {waits}", stuck),
    ]
    body = (strip(v, working) + "<main>"
            + "".join(f'<h2 id="{i}">{esc(h)}</h2>{b}' for i, h, b in sections)
            + '<script type="application/json" id="events">'
            + json.dumps(events(v), separators=(",", ":")).replace("<", "\\u003c") + "</script></main>")
    text = filled(TEMPLATE, {"BODY": body, "EVENTS": EVENTS, "SEARCH": SEARCH_ROUTE, "TICKET": TICKET_ROUTE,
                             "LASTLOOK": LAST_LOOK, "TAB": TAB})
    entries = {n: Entry(t, v.phrase(t), v.status(t)) for n, t in all_.items()}
    return Rendered(text, entries, now)


def filled(template: str, parts: Mapping[str, str]) -> str:
    """`template` with each `@NAME@` in it replaced by `parts[NAME]`, in one
    pass, so that no text a part inserts is read as a placeholder."""
    return re.sub(r"@([A-Z]+)@", lambda m: parts[m[1]], template)
