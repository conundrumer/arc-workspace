"""The HTML of the ticket dashboard's page (`ticket_dashboard`): the strip
at its top and each section of it, built from the reads of
`dashboard_reads` and the standing of each open ticket (`Standings`), the
texts of times and of a ticket's status they give, and the page whole in
the template of `dashboard_template`, with the search's entries of each ticket kept beside it (`Rendered`)."""

import html
import json
import math
import re
import time
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from dashboard_standings import HOLD_WORD, HELD_HEAD, MOVING, Row, Standing, Standings, merged
from dashboard_words import clock, hold_text, start_hold_text
from dashboard_reads import (DAY, OPEN, STALE_RECORD, CodexWindow, OperatorRecords, Stage, change_of, hits_full,
                             journal_work, logged, phrase, stage, users, Work)
from dashboard_template import DONE_TAB, EVENTS, LAST_LOOK, QUEUED_TAB, SEARCH_ROUTE, TEMPLATE, TICKET_ROUTE
from shown_state import ScriptAdmits, Shown, ShownAgent, ShownParty, Start
from ticket_reads import read_tickets
from usage_limit import Reading

from operations.change_budget import taken
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

GROUP_SHOWN = 6
"""The most rows a group of held tickets gives above its fold."""

DONE_SECONDS = DAY
"""How far back Done reads the closes."""

LIST_SHOWN = 8
"""The most rows Your work, a tab of Done, or Since you looked gives above its fold."""

CLOSE_WORDS: Mapping[Resolution | None, str] = {
    Resolution.FIXED: "Fixed", Resolution.DUPLICATE: "Duplicate",
    Resolution.CANNOT_REPRODUCE: "Can't reproduce", Resolution.WONTFIX: "Won't fix",
    Resolution.INVALID: "Invalid", None: "Closed"}
"""The words of each resolution a close gives, and of a close that gives
none."""

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



def role_words(r: Role) -> str:
    return r.value.replace("-", " ")


def at_work(w: list[ShownAgent], now: float) -> str:
    """The words on the latest of the agents `w` at work."""
    a = max(w, key=lambda a: a.launched)
    return f"{role_words(a.role)} at work, {ago(now - a.launched)}"


def capitalized(text: str) -> str:
    return text[:1].upper() + text[1:]


def tap(n: str, inner: str, cls: str = "row") -> str:
    """`inner` in an element whose tap opens the sheet of ticket `n`."""
    tag = "button" if cls == "card" else "div"
    return f'<{tag} class="{cls} tk" data-n="{esc(n)}">{inner}</{tag}>'


@dataclass(frozen=True)
class ChangeState:
    """A live change whose row represents an open ticket, the words of its
    state as a row of Active or Queued gives it, and whether an agent is at
    work on it (`change_states`)."""
    change: Ticket
    state: str
    at_work: bool


@dataclass(frozen=True)
class Entry:
    """A ticket as the search and its sheet give it: its phrase, the plain
    sentence on its status, and the live changes whose rows represent it."""
    ticket: Ticket
    phrase: str
    status: str
    changes: list[ChangeState]


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
    operators start next, the party that holds each of them that one
    holds, and the work on each change the step journals record, by its
    number (`dashboard_reads.journal_work`)."""
    all_: Mapping[str, Ticket]
    records: OperatorRecords
    usage: Usage
    now: float
    expedited: frozenset[str]
    agents: Mapping[str, list[ShownAgent]]
    starts: list[Start]
    holds: Mapping[str, ShownParty]
    work: Mapping[str, list[Work]]
    codex: CodexWindow | None = None

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
            return at_work(w, self.now).capitalize()
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


def codex_bar(window: CodexWindow | None, now: float) -> str:
    """The weekly Codex account usage and reset, or unavailable."""
    label = '<span class="ul">Codex</span>'
    if window is None or window.resets_at <= now:
        return (f'<div class="ub">{label}<div class="bar"></div>'
                '<span class="cr">Unavailable</span></div>')
    return (f'<div class="ub">{label}<div class="bar">'
            f'<i style="width:{window.used_pct:.0f}%"></i></div>'
            f'<span class="uv">{window.used_pct:.0f}%</span>'
            f'<span class="cr">Resets {esc(clock(window.resets_at, now))}</span></div>')


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
            f'{usage_bar(v.usage, WindowName.FIVE_HOUR, "5 h")}'
            f'{codex_bar(v.codex, v.now)}</div>')


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




class Mark(Enum):
    """The cell of a stage bar at the stage it reaches, by its CSS class:
    an agent at work, work stopped unfinished, or work finished."""
    AT_WORK = "n"
    STOPPED = "x"
    FINISHED = "d"


def stage_bar(s: Stage, mark: Mark) -> str:
    """A bar of one cell for each stage, done up to `s`, and at `s` as
    `mark` gives."""
    cells = "".join(f'<b class="{"d" if k < s else mark.value if k == s else ""}"></b>' for k in Stage)
    return f'<span class="mb">{cells}</span>'


def basis(v: View, r: Row) -> Ticket:
    """The ticket whose stage the row `r` gives: its change, else the
    change its ticket waits on, else its ticket."""
    return r.change or change_of(r.lead, v.all_) or r.lead


def stopped_bar(v: View, r: Row) -> str:
    """The stage bar of `r`, whose subject no agent works on, from where
    the work on its change stands (`dashboard_reads.logged`), where that
    work reached past Triage; else nothing."""
    c = basis(v, r)
    c = None if c.kind is not Kind.CHANGE else c
    w = None if c is None else logged(c, v.work.get(c.number, []))
    if w is None or w.stage is Stage.TRIAGE:
        return ""
    return stage_bar(w.stage, Mark.FINISHED if w.finished else Mark.STOPPED)


def row(v: View, t: Ticket, right: str, change: Ticket | None, lead: int | None = None,
        members: tuple[Ticket, ...] = ()) -> str:
    """The row of `t`, led by `lead` where it is given, with the number of
    `change`, the change whose state it gives, under its own, and `right`
    at its end."""
    if merged(t):
        right = f'{esc(t.status.value.capitalize())} · merged, awaiting tracker closure'
    star = '<span class="star">★</span>' if t.number in v.expedited else ""
    under = "" if change is None or change is t else f'<small>{link(change.number)}</small>'
    related = ''.join(f'<a class="tk related" data-n="{esc(m.number)}">'
                      f'{esc(m.number)} · {esc(capitalized(v.phrase(m)))}</a>'
                      for m in members if m.number != t.number )
    related = f'<span class="members">{related}</span>' if related else ""
    return tap(t.number, ("" if lead is None else f'<span class="wq">{lead}</span>')
               + f'<span class="wn">{esc(t.number)}{under}</span><span class="wp">{star}{esc(capitalized(v.phrase(t)))}</span>'
               f'<span class="ws">{right}</span>{related}', "wr" + ("" if lead is None else " ld") + (" me" if v.mine(t) else ""))


def link(n: str) -> str:
    return f'<a class="tk" data-n="{esc(n)}">{esc(n)} ›</a>'


def active(v: View, st: Standings, selected: list[Row] | None = None) -> tuple[str, int]:
    """The HTML of Active, the rows whose subject an agent is at work on,
    in the order of their takes, the newest first among those of one
    time, and the count of its rows."""
    rows: list[tuple[float, float, Row, str]] = []
    for r in st.rows if selected is None else selected:
        if st.shown(r) and (w := st.agents(r.subject)):
            a = max(w, key=lambda a: a.launched)
            b = basis(v, r)
            s = stage([x.role for x in w], b)
            take = taken(b)
            rows.append((r.subject.filed if take is None else take.time, -r.subject.filed, r,
                         f"{stage_bar(s, Mark.AT_WORK)}{s.name.capitalize()} · {ago(v.now - a.launched)}"))
    rows.sort(key=lambda x: x[:2])
    if not rows:
        return '<div class="meta">Nothing is being worked on.</div>', 0
    return '<div class="wl">' + "".join(row(v, r.lead, right, r.change, members=r.members) for _, _, r, right in rows) + "</div>", len(rows)


def session_line(st: Standings, s: int | None) -> str:
    """The line atop the tab of session `s` in Queued: whether its operator
    runs, and whether it keeps to its own work; where it is paused, ending
    on the words that lead the groups of what a resume starts."""
    if s not in st.live:
        return "No operator running"
    paused = s in st.paused
    state = ("Paused" + (" by you" if s == st.main else "")) if paused else "Running"
    return state + (" · takes only its own work" if s in st.own_scope else "") + (" · on resume:" if paused else "")


def tab_word(st: Standings, s: int | None) -> str:
    if s not in st.live:
        return "no operator"
    return "paused" if s in st.paused else "running"


def session_name(s: int | None) -> str:
    return "No session" if s is None else f"S{s}"


def behind(st: Standings, root: Ticket) -> str:
    """The words of a ticket behind held work: the held ticket `root` and
    what holds it."""
    return f"after {root.number} · {HOLD_WORD[st.own(root)]}"


def change_states(v: View, st: Standings, t: Ticket) -> list[ChangeState]:
    """The live changes whose rows represent `t` (`Standings.changes`),
    each with the words of its state: the agent at work on it, next to
    start, the ticket it waits on, or the head of its group of held
    tickets; those at work first."""
    out: list[ChangeState] = []
    for c in st.changes.get(t.number, []):
        k, root = st.state(c)
        match k:
            case Standing.WORKING:
                words = at_work(st.agents(c), v.now)
            case Standing.READY:
                words = "next to start"
            case Standing.WAITING:
                words = f"after {root.number}"
            case Standing.BEHIND:
                words = behind(st, root)
            case _:
                words = HELD_HEAD[k].lower()
        out.append(ChangeState(c, words, k is Standing.WORKING))
    return sorted(out, key=lambda x: not x.at_work)


def folded(rows: list[str], shown: int) -> str:
    """`rows` in a list, the first `shown` of them open and the rest under
    a fold."""
    rest = rows[shown:]
    more = "" if not rest else f"<details><summary>{len(rest)} more ›</summary>{''.join(rest)}</details>"
    return f'<div class="wl">{"".join(rows[:shown])}{more}</div>'


def tab_set(key: str, panes: list[tuple[int | None, str, str]]) -> str:
    """A tab for each session of `panes`, with its word, over its pane's
    HTML; the browser keeps the tab last chosen under `key`."""
    tabs = "".join(f'<button class="tab" data-s="{s}">{session_name(s)} <small>{esc(word)}</small></button>'
                   for s, word, _ in panes)
    return (f'<div class="tset" data-key="{esc(key)}"><div class="tabs">{tabs}</div>'
            + "".join(f'<div class="pane" data-s="{s}">{body}</div>' for s, _, body in panes) + "</div>")


def queued(v: View, st: Standings, selected: list[Row] | None = None) -> str:
    """The HTML of Queued: a tab for each session that filed the ticket
    of a row shown whose subject is not at work, and in it, its operator's
    state, its rows ready (`Next`, or `Next on resume` in a paused
    session), those waiting, and the held ones in a group for each hold.
    The rows ready and those waiting go in the order of their starts, and
    the rows no start orders after them; those rows, and the held ones, go
    the user's tickets first, then the expedited ones, then the newest
    first."""
    sessions: dict[int | None, list[tuple[Row, Standing, Ticket]]] = {}
    for r in st.rows if selected is None else selected:
        k, root = st.state(r.subject)
        if k is not Standing.WORKING:
            sessions.setdefault(r.lead.session, []).append((r, k, root))
    if not sessions:
        return '<div class="meta">Nothing is queued.</div>'

    def ordered(xs: list[Row]) -> list[Row]:
        return sorted(xs, key=lambda r: (st.position.get(r.subject.number, len(st.position)), not v.mine(r.lead),
                                         r.lead.number not in v.expedited, -r.subject.filed))

    keys = sorted(sessions, key=lambda s: (s not in st.live, s in st.paused, -len(sessions[s])))
    panes: list[tuple[int | None, str, str]] = []
    for s in keys:
        items = sessions[s]
        ready = ordered([r for r, k, _ in items if k is Standing.READY])
        waiting = ordered([r for r, k, _ in items if k is Standing.WAITING])
        body = f'<div class="sh2">{esc(session_line(st, s))}</div>'
        if ready:
            body += (f'<div class="gh">Next{" on resume" if s in st.paused else ""}</div><div class="wl">'
                     + "".join(row(v, r.lead, stopped_bar(v, r), r.change, st.position.get(r.subject.number, i) + 1, r.members) for i, r in enumerate(ready)) + "</div>")
        if waiting:
            body += ('<div class="gh">Waiting</div><div class="wl">'
                     + "".join(row(v, r.lead, f"{stopped_bar(v, r)}<span>after {link(st.state(r.subject)[1].number)}</span>",
                                 r.change, members=r.members) for r in waiting)
                     + "</div>")
        groups: dict[Standing, list[tuple[Row, Ticket]]] = {}
        for r, k, root in items:
            if k not in MOVING:
                groups.setdefault(k, []).append((r, root))
        for k, xs in sorted(groups.items(), key=lambda g: list(HELD_HEAD).index(g[0])):
            label = HELD_HEAD[k]
            xs.sort(key=lambda x: (not v.mine(x[0].lead), x[0].lead.number not in v.expedited, -x[0].subject.filed))
            rows = [row(v, r.lead, stopped_bar(v, r) + (f"<span>after {link(root.number)} · {esc(HOLD_WORD[st.own(root)])}</span>"
                                                        if k is Standing.BEHIND else ""), r.change, members=r.members)
                    for r, root in xs]
            inner = folded(rows, GROUP_SHOWN)
            opened = " open" if label == HELD_HEAD[Standing.ON_HOLD] or any(v.mine(r.lead) for r, _ in xs) else ""
            body += f'<details class="grp"{opened}><summary>{esc(label)} · {len(xs)}</summary>{inner}</details>'
        panes.append((s, tab_word(st, s), body))
    return tab_set(QUEUED_TAB, panes)


def held_by_line(st: Standings, r: Row) -> bool:
    k, root = st.state(r.subject)
    return k is Standing.HELD or (k is Standing.BEHIND and st.own(root) is Standing.HELD)


def priority(v: View, st: Standings, rows: list[Row], shown: int) -> str:
    """Rows with their session, standing, operator position and stage."""
    rendered = []
    for r in rows:
        t = r.subject
        k, root = st.state(t)
        if k is Standing.WORKING:
            w = st.agents(t)
            state = stage_bar(stage([a.role for a in w], basis(v, r)), Mark.AT_WORK) + at_work(w, v.now)
        elif k is Standing.READY:
            position = st.position.get(t.number)
            state = 'Ready' + ('' if position is None else f' · position {position + 1}')
            if t.session in st.paused:
                state += ' · starts on resume'
        elif k in (Standing.WAITING, Standing.BEHIND):
            state = f'after {link(root.number)}'
            if k is Standing.BEHIND:
                state += f' · {esc(HOLD_WORD[st.own(root)])}'
        else:
            state = esc(HELD_HEAD[k])
        if any(m.status is Status.BLOCKED for m in r.members):
            state += ' · waits on your decision'
        if k is not Standing.WORKING:
            state = stopped_bar(v, r) + state
        rendered.append(row(v, r.lead, f'{session_name(t.session)} · {state}', r.change, members=r.members))
    return folded(rendered, shown)


def done(v: View) -> str:
    """The HTML of Done: a tab for each session that filed a ticket closed
    in the last `DONE_SECONDS`, with the count of its closes, and in it
    those tickets newest first by their closes and then by their filings,
    each with how and when it closed. A
    closed ticket whose merge closed one of them (`LogLine.closed_by`), or
    whose Motivation gives one of them, shows as that one, with its number
    under that one's."""
    closes = {t.number: ln for t in v.all_.values() if t.status is Status.CLOSED
              and (ln := t.log[-1]).status is Status.CLOSED and v.now - ln.time <= DONE_SECONDS}
    within = {n: v.all_[n] for n in closes}
    waited = {ln.closed_by for ln in closes.values() if ln.closed_by is not None}
    shown = sorted((t for n, t in within.items() if n not in waited and not any(m in closes for m in t.motivation)),
                   key=lambda t: (-closes[t.number].time, -t.filed))
    if not shown:
        return '<div class="meta">Nothing closed in the last day.</div>'
    sessions: dict[int | None, list[Ticket]] = {}
    for t in shown:
        sessions.setdefault(t.session, []).append(t)

    def change(t: Ticket) -> Ticket | None:
        by = closes[t.number].closed_by
        c = None if by is None else v.all_.get(by)
        return c if c is not None else next((x for x in within.values() if x.kind is Kind.CHANGE
                                             and t.number in x.motivation), None)

    def right(t: Ticket) -> str:
        ln = closes[t.number]
        return f"{CLOSE_WORDS[ln.resolution]} · {clock(ln.time, v.now)}"
    return tab_set(DONE_TAB, [(s, str(len(ts)), folded([row(v, t, right(t), change(t)) for t in ts], LIST_SHOWN))
                              for s, ts in sessions.items()])


def events(v: View) -> list[dict[str, object]]:
    """The filings and the merges of the last `SINCE_SECONDS`, newest
    first, each with its ticket's number and phrase and whether the ticket
    is the user's."""
    found: list[tuple[float, str, Ticket]] = []
    for t in v.all_.values():
        if v.now - t.filed <= SINCE_SECONDS:
            found.append((t.filed, "filed", t))
        if t.kind is Kind.CHANGE:
            found.extend((ln.time, "merged", t) for ln in t.log if ln.status is Status.CLOSED
                         and ln.resolution is Resolution.FIXED and v.now - ln.time <= SINCE_SECONDS)
    found.sort(key=lambda e: (-e[0], -e[2].filed))
    return [{"t": round(at), "k": kind, "n": t.number, "u": v.mine(t), "s": capitalized(v.phrase(t))}
            for at, kind, t in found]


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
    """The HTML of Blocked, its tickets newest first, and their count."""
    rows = sorted(((t, ln) for t in v.all_.values() if (ln := blocked_on_user(t)) is not None),
                  key=lambda x: -x[0].filed)
    body = "".join(tap(t.number, f'<span class="num">{esc(t.number)}</span> <span class="sh">{esc(v.phrase(t))}</span>'
                       f'<div class="meta">{esc(cut(ln.note))}</div>') for t, ln in rows)
    return (f"<details><summary>{len(rows)} wait on your decision</summary>"
            + (body or '<div class="meta">Nothing waits on you.</div>') + "</details>"), len(rows)


def page(tickets: Path, now: float, usage: Reading, records: OperatorRecords,
         undecided: list[str], codex: CodexWindow | None = None) -> Rendered:
    """The page at `now`, with the `undecided` lines of its reads."""
    read, unread = read_tickets(tickets)
    all_ = dict(sorted(read.items(), key=lambda kv: kv[1].order))
    starts = records.starts()
    v = View(all_, records, usage.usage, now, records.expedited(), records.agents(), starts,
             {s.number: s.held for s in starts if s.held is not None}, journal_work(tickets), codex)
    st = Standings(v)
    _, working = active(v, st)
    yours = [r for r in st.rows if any(v.mine(m) or m.number in v.expedited for m in r.members)]
    yours.sort(key=lambda r: (not any(m.number in v.expedited for m in r.members),
                             0 if held_by_line(st, r) else 1 if st.state(r.subject)[0] is Standing.WORKING else 2,
                             -r.subject.filed))
    remaining = [r for r in st.rows if r not in yours]
    held = sorted((r for r in remaining if held_by_line(st, r)), key=lambda r: -r.subject.filed)
    remaining = [r for r in remaining if r not in held]
    work, _ = active(v, st, remaining)
    stuck, waits = blocked(v)
    sections = [
        ("yours", f"Your work · {len(yours)}", priority(v, st, yours, LIST_SHOWN)),
        ("held", f"Held by a line · {len(held)}", priority(v, st, held, GROUP_SHOWN)),
        ("health", "Health", health(v, [*undecided, *(f"unread: {u.path}: {u.why}" for u in unread)])),
        ("active", "Active", work),
        ("queued", "Queued", queued(v, st, remaining)),
        ("done", "Done", done(v) + '<div class="key"><span><i></i>filed by you</span><span>★ expedited</span></div>'),
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
                             "LASTLOOK": LAST_LOOK, "SHOWN": str(LIST_SHOWN)})
    entries = {n: Entry(t, v.phrase(t), v.status(t), change_states(v, st, t)) for n, t in all_.items()}
    return Rendered(text, entries, now)


def filled(template: str, parts: Mapping[str, str]) -> str:
    """`template` with each `@NAME@` in it replaced by `parts[NAME]`, in one
    pass, so that no text a part inserts is read as a placeholder."""
    return re.sub(r"@([A-Z]+)@", lambda m: parts[m[1]], template)
