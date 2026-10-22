"""The HTML of the ticket dashboard's page (`ticket_dashboard`): the strip
at its top and each section of it, built from the reads of
`dashboard_reads` and the standing of each open ticket (`Standings`), the
texts of times and of a ticket's status they give, and the page whole in
the template of `dashboard_template`, with the search's entries of each ticket kept beside it (`Rendered`)."""

import html
import math
import re
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from dashboard_health import health
from dashboard_standings import HOLD_WORD, HELD_HEAD, MOVING, Row, Standing, Standings, merged
from dashboard_usage import codex_bar, usage_bar
from dashboard_words import clock, hold_text, start_hold_text
from dashboard_reads import (DAY, OPEN, CodexWindow, OperatorRecords, Stage, change_of, hits_full,
                             journal_work, latest, log_work, phrase, spans, stage, users, Span, Work)
from dashboard_template import CLEAR_ROUTE, EVENTS, FOLD, QUEUED_TAB, SEARCH_ROUTE, TEMPLATE, TICKET_ROUTE
from shown_state import ScriptAdmits, Shown, ShownAgent, ShownParty, Start
from ticket_reads import read_tickets
from usage_limit import Reading

from operations.change_budget import taken
from operations.roles import ANALYST_NAMES, Role
from operations.pacing import Capped, Until, Usage, WindowName
from operations.parties import Hold, OnTicket
from operations.state import NotComputed, Ticket
from operations.tracker import blocked_on_user
from ticketing.vocabulary import COORDINATOR, Kind, Resolution, Status

WEEKLY_LIMIT = 8400.0
"""The weekly usage limit in dollars, as
`prompts/agents/notes/decisions.md#cost-and-time` gives it."""

NOTE_WORDS = 18
"""The most words of a log line's note the page gives."""

GROUP_SHOWN = 6
"""The most rows a group of held tickets gives above its fold."""

MARKS = {"merged": ("✓", "m"), "ended": ("⊘", "x"), "blocked": ("!", "b")}
"""The glyph at the start of an Updates row and the class that colours it,
by the kind of its event."""

SINCE_SECONDS = 2 * DAY
"""How far back Updates reads the tracker."""

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
    """The words on work with workers and its latest agent."""
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
    tickets expedited, the agents at work by ticket number, the tickets the
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
    held = [(lead.strip(), h) for lead, h in per_session(v, lambda s: s.start_hold) if h is not None]
    names = [lead for lead, _ in held]
    why = "; ".join(f"{lead}: " * bool(lead) + start_hold_text(h, v.now) for lead, h in held)
    starts = ("" if not held else f' · <span class="w" title="{esc(why)}">agent starts held'
              + ("" if names == [""] else f" ({esc(', '.join(names))})") + "</span>")
    return (f'<div class="strip"><div class="r1">{ops} · {working} active{starts} · Rendered {clock(v.now, v.now)}</div>'
            f'{usage_bar(v.usage, WindowName.SEVEN_DAY, "Week")}'
            f'{usage_bar(v.usage, WindowName.FIVE_HOUR, "5 h")}'
            f'{codex_bar(v.codex, v.now)}</div>')


class Mark(Enum):
    """The cell of a stage bar at the stage it reaches, by its CSS class:
    an agent at work, work stopped unfinished, or work finished."""
    AT_WORK = "n"
    STOPPED = "x"
    FINISHED = "d"


def stage_bar(s: Stage, mark: Mark, runs: Sequence[Span] = ()) -> str:
    """A bar of one cell for each stage, done up to `s`, and at `s` as
    `mark` gives. The cells of a run in `runs` are a group of the width of
    its stages, that holds the run once for each of its passes, the earlier
    passes done and `s` in the last."""
    def cell(k: Stage, last: bool) -> str:
        return f'<b class="{"d" if not last or k < s else mark.value if k == s else ""}"></b>'
    out: list[str] = []
    for k in Stage:
        run = next((r for r in runs if r.first <= k <= r.last), None)
        if run is None:
            out.append(cell(k, True))
        elif k == run.first:
            width = run.last - run.first + 1
            inner = "".join(cell(Stage(j), p == run.passes - 1) for p in range(run.passes)
                            for j in range(run.first, run.last + 1))
            out.append(f'<i style="flex:{width}">{inner}</i>')
    return f'<span class="mb">{"".join(out)}</span>'


def basis(v: View, r: Row) -> Ticket:
    """The ticket whose stage the row `r` gives: its change, else the
    change its ticket waits on, else its ticket."""
    return r.change or change_of(r.lead, v.all_) or r.lead


def progress(v: View, r: Row) -> Work | None:
    """The furthest recorded work of the row's members and its change,
    retaining the latest result at that stage. Filing alone is no work."""
    work = row_work(v, r)
    if spans(change_work(v, basis(v, r))):
        return latest(work)
    return max(work, key=lambda w: (w.stage, w.at), default=None)


def change_work(v: View, c: Ticket) -> list[Work]:
    """The work on the change `c`: its log's and its agents'."""
    return [*log_work(c)[1:], *v.work.get(c.number, [])]


def row_work(v: View, r: Row) -> list[Work]:
    tickets = {t.number: t for t in (*r.members, basis(v, r))}
    return [w for t in tickets.values() for w in change_work(v, t)]


def stopped_bar(v: View, r: Row) -> str:
    """The row's recorded progress while no agent is at work on it."""
    w = progress(v, r)
    return "" if w is None else stage_bar(w.stage, Mark.FINISHED if w.finished else Mark.STOPPED,
                                          spans(change_work(v, basis(v, r))))


def priority(v: View, r: Row) -> tuple[bool, bool]:
    """Expedited work first, then other work of the user, across a bundle."""
    return (not any(t.number in v.expedited for t in r.members),
            not any(v.mine(t) for t in r.members))


def row(v: View, t: Ticket, right: str, change: Ticket | None,
        members: tuple[Ticket, ...] = ()) -> str:
    """The row of `t`, with its change number below its own and `right`
    on the line above it. A bundle leads with its change, and members fold after three."""
    if merged(t):
        right = f'<span>{esc(t.status.value.capitalize())} · merged, awaiting tracker closure</span>'
    star = '<span class="star">★</span>' if t.number in v.expedited else ""
    under = "" if change is None or change is t else f'<small>{link(change.number)}</small>'
    bundle = t is change and sum(m.kind is Kind.REQUEST for m in members) > 1
    related = [(m, f'<a class="tk related" data-n="{esc(m.number)}">'
                f'{esc(m.number)} · {esc(capitalized(v.phrase(m)))}</a>')
               for m in members if m.number != t.number]
    texts = [text for _, text in related]
    visible, rest = texts[:3], texts[3:]
    more = "" if not rest else f'<details><summary>+{len(rest)} more</summary>{"".join(rest)}</details>'
    related_html = f'<div class="members">{"".join(visible)}{more}</div>' if related else ""
    title = t.title if bundle else capitalized(v.phrase(t))
    top = f'<span class="wt">{right}</span>' if right else ""
    return tap(t.number,
               f'{top}<span class="wn">{esc(t.number)}{under}</span><span class="wp">{star}{esc(title)}</span>'
               f'{related_html}', "wr" + (" me" if v.mine(t) else ""))


def link(n: str) -> str:
    return f'<a class="tk" data-n="{esc(n)}">{esc(n)} ›</a>'


def active(v: View, st: Standings) -> tuple[str, int]:
    """The HTML of Active, including taken work between agent runs,
    expedited and user work first, then in the order of their takes,
    the newest first among those of one time, and the count of its rows."""
    rows: list[tuple[float, float, Row, str]] = []
    for r in st.rows:
        w = st.row_agents(r)
        if st.shown(r) and st.active(r):
            b = basis(v, r)
            if w:
                a = max(w, key=lambda a: a.launched)
                s = stage([x.role for x in w], b)
                runs = spans(change_work(v, b))
                if (p := progress(v, r)) is not None and not runs:
                    s = max(s, p.stage)
                right = f"{stage_bar(s, Mark.AT_WORK, runs)}<span>{s.name.capitalize()} · {ago(v.now - a.launched)}</span>"
            take = taken(b)
            if not w:
                last = max([x.at for x in row_work(v, r)] + ([] if take is None else [take.time]), default=r.subject.filed)
                right = f"{stopped_bar(v, r)}<span>Idle · {ago(v.now - last)}</span>"
            rows.append((r.subject.filed if take is None else take.time, -r.subject.filed, r, right))
    rows.sort(key=lambda x: (*priority(v, x[2]), *x[:2]))
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
                words = "idle" if st.active(Row(c, c, (c,))) else "next to start"
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


def queued(v: View, st: Standings) -> str:
    """The HTML of Queued: a tab for each session that filed the ticket
    of a row shown whose subject has no active work, and in it, its operator's
    state, its rows ready (`Next`, or `Next on resume` in a paused
    session), those waiting, drafts, and the held ones in a group for each hold.
    Drafts have no operator standing or start order. Analyst-filed drafts
    with a log entry in the last day show above the fold; others fold as parked.
    Each list puts expedited work first, then other work of the user.
    Within those priorities, ready and waiting rows keep the start order,
    followed by rows without a start; remaining ties go newest first."""
    sessions: dict[int | None, list[tuple[Row, Standing | None, Ticket]]] = {}
    for r in st.rows:
        if st.active(r):
            continue
        if r.subject.status is Status.DRAFT:
            k, root = None, r.subject
        else:
            k, root = st.state(r.subject)
        sessions.setdefault(r.lead.session, []).append((r, k, root))
    if not sessions:
        return '<div class="meta">Nothing is queued.</div>'

    def ordered(xs: list[Row]) -> list[Row]:
        return sorted(xs, key=lambda r: (*priority(v, r),
                                         st.position.get(r.subject.number, len(st.position)), -r.subject.filed))

    keys = sorted(sessions, key=lambda s: (s not in st.live, s in st.paused, -len(sessions[s])))
    panes: list[tuple[int | None, str, str]] = []
    for s in keys:
        items = sessions[s]
        ready = ordered([r for r, k, _ in items if k is Standing.READY])
        waiting = ordered([r for r, k, _ in items if k is Standing.WAITING])
        body = f'<div class="sh2">{esc(session_line(st, s))}</div>'
        if ready:
            rows = '<div class="wl">' + "".join(
                row(v, r.lead, stopped_bar(v, r), r.change, r.members) for r in ready) + "</div>"
            body += (f'<details class="grp"><summary>Next on resume</summary>{rows}</details>'
                     if s in st.paused else f'<div class="gh">Next</div>{rows}')
        if waiting:
            body += ('<div class="gh">Waiting</div><div class="wl">'
                     + "".join(row(v, r.lead, f"{stopped_bar(v, r)}<span>after {link(st.state(r.subject)[1].number)}</span>",
                                 r.change, members=r.members) for r in waiting)
                     + "</div>")
        drafts = sorted((r for r, k, _ in items if k is None),
                        key=lambda r: (*priority(v, r), -r.subject.filed))
        if drafts:
            fresh: list[str] = []
            parked: list[str] = []
            for r in drafts:
                t = r.subject
                pipeline = bool(t.log and t.log[0].agent in ANALYST_NAMES and v.now - t.last_time < DAY)
                (fresh if pipeline else parked).append(row(v, r.lead, stopped_bar(v, r), r.change, r.members))
            fold = (f'<details><summary>Parked · {len(parked)}</summary>{"".join(parked)}</details>'
                    if parked else "")
            body += f'<div class="gh">Draft</div><div class="wl">{"".join(fresh)}{fold}</div>'
        groups: dict[Standing, list[tuple[Row, Ticket]]] = {}
        for r, k, root in items:
            if k is not None and k not in MOVING:
                groups.setdefault(k, []).append((r, root))
        for k, xs in sorted(groups.items(), key=lambda g: list(HELD_HEAD).index(g[0])):
            label = HELD_HEAD[k]
            xs.sort(key=lambda x: (*priority(v, x[0]), -x[0].subject.filed))
            rows = [row(v, r.lead, stopped_bar(v, r) + (f"<span>after {link(root.number)} · {esc(HOLD_WORD[st.own(root)])}</span>"
                                                        if k is Standing.BEHIND else ""), r.change, members=r.members)
                    for r, root in xs]
            inner = folded(rows, GROUP_SHOWN)
            opened = " open" if label == HELD_HEAD[Standing.ON_HOLD] or any(v.mine(r.lead) for r, _ in xs) else ""
            body += f'<details class="grp"{opened}><summary>{esc(label)} · {len(xs)}</summary>{inner}</details>'
        panes.append((s, tab_word(st, s), body))
    return tab_set(QUEUED_TAB, panes)


def updates(v: View, cleared: float) -> str:
    """Updates: what concerns the user within `SINCE_SECONDS` and is newer
    than `cleared`: the merges of changes, the ends of the tickets the
    coordinator filed, and those of them that wait on the user. The groups
    run in that order, each newest first, under a Clear that sends the time
    of the newest. Each row ends with the span from the ticket's filing to its event,
    then the time of the event."""
    found: list[tuple[int, float, tuple[str, str], str, Ticket]] = []
    for t in v.all_.values():
        if t.kind is Kind.CHANGE:
            found.extend((0, ln.time, MARKS["merged"], "", t) for ln in t.log if ln.status is Status.CLOSED
                         and ln.resolution is Resolution.FIXED)
        if t.filer != COORDINATOR:
            continue
        end = t.log[-1] if t.log else None
        if t.status is Status.CLOSED and end is not None and end.status is Status.CLOSED:
            if t.kind is not Kind.CHANGE or end.resolution is not Resolution.FIXED:
                word = end.resolution.value if end.resolution else "closed"
                mark = MARKS["merged"] if end.resolution is Resolution.FIXED else MARKS["ended"]
                found.append((1, end.time, mark, f" · {word}", t))
        elif t.status is Status.BLOCKED:
            found.extend((2, ln.time, MARKS["blocked"], "", t) for ln in t.log[-1:] if ln.status is Status.BLOCKED)
    fresh = sorted((e for e in found if e[1] > cleared and v.now - e[1] <= SINCE_SECONDS),
                   key=lambda e: (e[0], -e[1], -e[4].filed))
    rows = "".join(f'<div class="wr tk{" me" if v.mine(t) else ""}" data-n="{esc(t.number)}">'
                   f'<span class="wn"><i class="{cls}">{mark}</i> {esc(t.number)}</span>'
                   f'<span class="wp">{esc(capitalized(v.phrase(t)) + word)}</span><span class="ws">{ago(max(at - t.filed, 60))} · {clock(at, v.now)}</span></div>'
                   for _, at, (mark, cls), word, t in fresh)
    body = (f'<button class="tab" id="clear" data-t="{max(e[1] for e in fresh)!r}">Clear</button><div class="wl">{rows}</div>'
            if fresh else '<div class="meta">Nothing new.</div>')
    head = f"Updates · {len(fresh)}" if fresh else "Updates"
    return f'<details data-k="since" class="grp"><summary id="sl">{head}</summary><div id="since">{body}</div></details>'


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
    if v.codex is not None and v.codex.resets_at > v.now:
        rows.append(kv("Codex resets", time.strftime("%a %b %-d, %-I:%M %p", time.localtime(v.codex.resets_at))))
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
         codex: CodexWindow | None = None, cleared: float = 0.0) -> Rendered:
    """The page at `now`, with Updates cleared up to `cleared`."""
    read, _ = read_tickets(tickets)
    all_ = dict(sorted(read.items(), key=lambda kv: kv[1].order))
    starts = records.starts()
    v = View(all_, records, usage.usage, now, records.expedited(), records.agents(), starts,
             {s.number: s.held for s in starts if s.held is not None}, journal_work(tickets), codex)
    st = Standings(v)
    work, working = active(v, st)
    stuck, waits = blocked(v)
    sections = [
        ("health", "Health", health(v)),
        ("sl", "", updates(v, cleared)),
        ("active", "Active", work),
        ("queued", "Queued", queued(v, st)),
        ("blocked", f"Blocked on you · {waits}", stuck),
        ("pace", "Pace", pace(v)), ("queue", "Queue", queue(v)),
        ("find", "Find",
         '<input id="q" type="search" placeholder="Number or words" autocomplete="off"><div id="res"></div>'),
    ]
    body = (strip(v, working) + "<main>"
            + "".join((f'<h2 id="{i}">{esc(h)}</h2>' if h else "") + b for i, h, b in sections)
            + "</main>")
    text = filled(TEMPLATE, {"BODY": body, "EVENTS": EVENTS, "SEARCH": SEARCH_ROUTE, "TICKET": TICKET_ROUTE,
                             "CLEAR": CLEAR_ROUTE, "FOLD": FOLD})
    entries = {n: Entry(t, v.phrase(t), v.status(t), change_states(v, st, t)) for n, t in all_.items()}
    return Rendered(text, entries, now)


def filled(template: str, parts: Mapping[str, str]) -> str:
    """`template` with each `@NAME@` in it replaced by `parts[NAME]`, in one
    pass, so that no text a part inserts is read as a placeholder."""
    return re.sub(r"@([A-Z]+)@", lambda m: parts[m[1]], template)
