"""The HTML of the ticket dashboard's page (`ticket_dashboard`): each
section of it, built from the reads of `dashboard_reads`, the tables they
are drawn in, and the page whole in the template of `dashboard_template`,
with the search's entries of each ticket kept beside it (`Rendered`)."""

import html
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from dashboard_reads import (DAY, OPEN, SAVING_KINDS, Entry, costs, first_sentence, impact, served_by,
                             trend, waits_on)
from dashboard_template import EVENTS, SEARCH, SEARCH_ROUTE, TEMPLATE
from state_assembly import ScriptAdmits, Shown
from ticket_reads import read_tickets
from ticket_watch import watched
from usage_limit import Reading

from operations.pacing import Until, WindowName
from operations.state import NotComputed
from operations.tracker import blocked_on_user
from ticketing.times import utc_stamp
from ticketing.vocabulary import UNTAKEN, Kind, Status

WEEKLY_LIMIT = 8400.0
"""The weekly usage limit in dollars, as
`prompts/agents/notes/decisions.md#cost-and-time` gives it."""


def dollars(d: float) -> str:
    return f"${d:,.2f} ({100 * d / WEEKLY_LIMIT:.2f}% wk)"


def spend_text(d: float, roles: Iterable[str]) -> str:
    return f"{dollars(d)} [{', '.join(sorted(roles)) or 'no role'}]"


def esc(s: object) -> str:
    return html.escape(str(s))


def link(n: str) -> str:
    return f'<a href="#" class="tk" data-n="{esc(n)}">{esc(n)}</a>'


type Row = list[str] | tuple[str, list[str]]
"""The cells of a table row, as HTML, with the attributes of its `tr`
element where it has any."""


def table(head: list[str], rows: Iterable[Row], cls: str = "") -> str:
    """A table in a box that scrolls sideways; each cell holds its column
    heading, which a narrow screen shows before the cell in place of the
    heading row."""
    h = "".join(f"<th>{esc(c)}</th>" for c in head)
    body = "".join(
        f"<tr{attrs}>" + "".join(f'<td data-l="{esc(label)}">{c}</td>'
                                  for label, c in zip(head, cells)) + "</tr>"
        for attrs, cells in ((f" {r[0]}", r[1]) if isinstance(r, tuple) else ("", r)
                             for r in rows))
    return (f'<div class="box"><table class="{cls}"><thead><tr>{h}</tr></thead>'
            f'<tbody>{body}</tbody></table></div>')


def now_section(state: Shown | str, usage: Reading, today: float,
                open_: Iterable[str]) -> str:
    parts: list[str] = []
    if isinstance(state, str):
        parts.append(f'<p class="warn">{esc(state)}; the Op lines and the in-flight spend are not shown.</p>')
    else:
        match state.pace:
            case Until(at, cap):
                verdict = (f"admits from {utc_stamp(at)}" + ("" if cap is None else f", cap {cap}"))
            case ScriptAdmits(admits):
                verdict = "script admits" if admits else "script holds"
            case NotComputed(why):
                verdict = f"not computed: {why}"
        held = set(open_)
        exp = [n for n in state.expedited if n in held]
        allowed = [n for n in state.allowed if n in held]
        parts.append(f'<p class="hint">As the operator\'s read of the state at {esc(utc_stamp(state.at))} UTC'
                     ' gave them:</p>')
        parts.append(table(["Op line", "In force"], [
            ["pace", f"{esc('default (five-hour, even)' if state.pace_line is None else state.pace_line)}"
                     f" &mdash; {esc(verdict)}"],
            ["pause", "paused" if state.paused else "running"],
            ["scope", "own" if state.own_scope else "all"],
            ["expedite (open)", " ".join(map(link, exp)) or "none"],
            ["allowed (open)", " ".join(map(link, allowed)) or "none"],
        ]))
    rows = []
    for name in (WindowName.FIVE_HOUR, WindowName.SEVEN_DAY):
        w = usage.usage.windows.get(name)
        if w is None:
            rows.append([esc(name), "unknown", "", ""])
            continue
        over = "warn" if w.used_pct > w.elapsed_pct else "ok"
        rows.append([esc(name), f'<span class="{over}">{w.used_pct:.0f}%</span>',
                     f"{w.elapsed_pct:.0f}%", esc(utc_stamp(w.resets_at))])
    parts.append(table(["Usage window", "Used", "Elapsed", "Resets (UTC)"], rows))
    parts.append(f"<p>Spend of changes settled in the last 24 hours and held now: <b>{esc(dollars(today))}</b></p>")
    return "".join(parts)


@dataclass(frozen=True)
class Rendered:
    """A render of the page: its text, the search's entry of each ticket in
    the tracker's order, and the time of the render."""
    text: str
    entries: Mapping[str, Entry]
    at: float


def page(tickets: Path, now: float, usage: Reading, state: Shown | str,
         undecided: list[str]) -> Rendered:
    """The page at `now`."""
    all_, unread = read_tickets(tickets)
    c = costs(tickets, all_, now, undecided)
    held_spend: Mapping[str, tuple[float, tuple[str, ...]]] = {} if isinstance(state, str) else {
        n: s for n, s in state.spent.items() if n not in c.spent}
    serving = served_by(all_)
    waited_by: dict[str, list[str]] = {}
    for n in sorted(all_, key=lambda n: all_[n].order):
        t = all_[n]
        if t.status is not Status.CLOSED:
            for w in waits_on(t):
                waited_by.setdefault(w, []).append(n)
    gains: dict[str, float] = {}
    for w in watched(tickets):
        for n in w.numbers:
            gains[str(n)] = w.loss

    def open_change(n: str) -> str | None:
        """The first change not closed whose Motivation gives `n`."""
        return next((ch for ch in serving.get(n, []) if all_[ch].status is not Status.CLOSED), None)

    def estimate(n: str) -> float | None:
        if all_[n].kind is Kind.CHANGE:
            e = c.estimated.get(n)
            return None if e is None else e[0]
        ch = open_change(n)
        return None if ch is None else estimate(ch)

    def est_text(n: str) -> str:
        t = all_[n]
        if t.kind is Kind.CHANGE:
            if n in held_spend:
                return "spent " + spend_text(*held_spend[n])
            if n in c.spent:
                return "spent " + spend_text(c.spent[n].dollars, c.spent[n].by_role)
            e = c.estimated.get(n)
            return "unknown" if e is None else f"est {dollars(e[0])} [{', '.join(e[1])}, after decision]"
        ch = open_change(n)
        return "no change" if ch is None else f"via {ch}: {est_text(ch)}"

    def change_of(n: str) -> str:
        if all_[n].kind is Kind.CHANGE:
            return ""
        chs = serving.get(n, [])
        return " ".join(f"{link(ch)} <i>{esc(all_[ch].status)}</i>" for ch in chs) or "none"

    def row(n: str, *extra: str) -> list[str]:
        t = all_[n]
        return [link(n), esc(t.kind), esc(t.status), esc(t.title), *extra]

    order = sorted(all_, key=lambda n: all_[n].order)
    impacts = {n: impact(all_[n]) for n in order
               if all_[n].kind in SAVING_KINDS and all_[n].status in OPEN}

    blocked = [(n, blocked_on_user(all_[n])) for n in order]
    needs = table(["#", "Kind", "Status", "Title", "Decision asked"],
                  [row(n, esc(ln.note)) for n, ln in blocked if ln is not None])

    open_ = [n for n in order if all_[n].status in OPEN]
    ex = set() if isinstance(state, str) else set(state.expedited)
    expedited = [n for n in open_ if n in ex]
    exp_html = table(["#", "Kind", "Status", "Title", "Change", "Cost"],
                     [row(n, change_of(n), esc(est_text(n))) for n in expedited if n in all_])

    flight = [n for n in order if all_[n].status is Status.ASSIGNED]
    flight_html = table(["#", "Kind", "Status", "Title", "Holder", "Cost", "Waited on by"],
                        [row(n, esc(all_[n].holder or ""), esc(est_text(n)),
                             str(len(waited_by.get(n, [])))) for n in flight])

    queue = [n for n in order if all_[n].status in UNTAKEN]
    queue_html = table(["#", "Kind", "Status", "Title", "Change", "Cost", "Waited on by"],
                       [row(n, change_of(n),
                            esc(est_text(n)), str(len(waited_by.get(n, [])))) for n in queue])

    waiting = sorted(((n, len(ws)) for n, ws in waited_by.items() if n in all_),
                     key=lambda p: (-p[1], all_[p[0]].order))
    waits_html = table(["#", "Kind", "Status", "Title", "Waited on by (count)", "Tickets"],
                       [row(n, str(k), " ".join(map(link, waited_by[n][:12]))
                            + (" &hellip;" if k > 12 else "")) for n, k in waiting[:40]])

    worth = [n for n in order if all_[n].status in OPEN
             and (all_[n].kind in SAVING_KINDS or n in gains)]
    worth_rows: list[Row] = []
    for n in worth:
        e = estimate(n)
        gain = (f"loss priced {dollars(gains[n])}" if n in gains else esc(impacts.get(n, "")))
        worth_rows.append((
            f'class="worth" data-kind="{esc(all_[n].kind)}" data-status="{esc(all_[n].status)}" '
            f'data-session="{esc(all_[n].session)}" data-est="{"" if e is None else f"{e:.2f}"}" '
            f'data-priced="{int(n in gains)}"', row(n, esc(est_text(n)), gain)))
    worth_html = table(["#", "Kind", "Status", "Title", "Estimated cost", "Gain or stated impact"],
                       worth_rows, "worth")

    recent = [n for n in order if all_[n].status is Status.CLOSED and all_[n].last_time >= now - DAY]
    done_html = table(["#", "Kind", "Closed", "Title", "Note", "Spend"],
                      [[link(n), esc(all_[n].kind), esc(utc_stamp(all_[n].last_time)), esc(all_[n].title),
                        esc(first_sentence(all_[n].log[-1].note)),
                        esc(spend_text(c.spent[n].dollars, c.spent[n].by_role)) if n in c.spent else ""]
                       for n in recent])
    today = (sum(c.spent[n].dollars for n in recent if n in c.spent)
             + sum(d for d, _ in held_spend.values()))

    trend_rows = trend(all_.values(), now)
    top = max([1, *(r[3] for r in trend_rows)])
    trend_html = table(["Day (UTC)", "Filed", "Closed", "Open at end", "Open, drawn"],
                       [[esc(d), str(f), str(cl), str(o),
                         f'<span class="bar" style="width:{300 * o / top:.0f}px"></span>']
                        for d, f, cl, o in trend_rows])

    entries = {n: Entry(t, tuple(waits_on(t)), tuple(waited_by.get(n, [])), tuple(serving.get(n, [])),
                        estimate(n), n in gains,
                        est_text(n) if t.kind is Kind.CHANGE or t.status in OPEN else "")
               for n, t in ((n, all_[n]) for n in order)}
    kinds = "".join(f'<option value="{esc(k)}">{esc(k)}</option>' for k in Kind)
    statuses = "".join(f'<option value="{esc(s)}">{esc(s)}</option>' for s in Status)
    notes = "".join(f"<li>{esc(u)}</li>" for u in undecided) + "".join(
        f"<li>unread: {esc(u.path)}: {esc(u.why)}</li>" for u in unread)
    sections = [
        ("now", "Now: Op lines, usage and spend", now_section(state, usage, today, open_)),
        ("search", "Search and filters", filled(SEARCH, {"KINDS": kinds, "STATUSES": statuses})),
        ("needs", f"Needs you: blocked on the user ({sum(1 for _, ln in blocked if ln)})", needs),
        ("exp", f"Expedited, open ({len(expedited)})", exp_html),
        ("flight", f"In flight ({len(flight)})", flight_html),
        ("waits", "What waits on what (most waited on first)", waits_html),
        ("trend", f"Trend ({len(open_)} open now)", trend_html),
        ("done", f"Done in the last 24 hours ({len(recent)})", done_html),
        ("worth", f"Bugs and cost savings ({len(worth)})", '<p class="hint">The filters under Search and filters apply here.</p>' + worth_html),
        ("queue", f"Queue ({len(queue)})", queue_html),
    ]
    nav = " ".join(f'<a href="#{i}" class="nav">{esc(h.split(":")[0].split(" (")[0])}</a>' for i, h, _ in sections)
    body = "".join(f'<section id="{i}"><h2>{esc(h)}</h2>{b}</section>' for i, h, b in sections)
    text = filled(TEMPLATE, {
        "RENDERED": esc(utc_stamp(now)), "NAV": nav, "BODY": body, "EVENTS": EVENTS,
        "SEARCH": SEARCH_ROUTE, "NOTES": f"<ul class='notes'>{notes}</ul>" if notes else "",
        "OPEN": json.dumps(sorted(OPEN))})
    return Rendered(text, entries, now)


def filled(template: str, parts: Mapping[str, str]) -> str:
    """`template` with each `@NAME@` in it replaced by `parts[NAME]`, in one
    pass, so that no text a part inserts is read as a placeholder."""
    return re.sub(r"@([A-Z]+)@", lambda m: parts[m[1]], template)
