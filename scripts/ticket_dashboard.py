"""The ticket dashboard: an HTTP server whose page gives, from the main
tree's tracker, the spend records, the usage cache and the state of the main
session's latest operator, the answers to the user's questions on tickets,
and updates itself in the browser as the tracker changes.

    uv run python scripts/ticket_dashboard.py <address> <port>

serves GET alone, at two routes. `/` renders the page on each request, as
one HTML document with its CSS and JavaScript inline. `EVENTS` is a
Server-Sent Events stream that sends an event each time `fingerprint`
changes, read every `POLL` seconds while the client is connected; on that
event the page fetches `/` and replaces its content in place. The server
serves no ticket file, and writes no file but the spend records under
`tickets/spends/` that `spends.change_spend` writes for settled changes,
reached through `spends.budget` and `ticket_watch.watched`."""

import argparse
import html
import json
import re
import sys
import time
from collections import Counter
from collections.abc import Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from file_ticket import main_tickets
from idle_sessions import named_main
from operator_reads import operator_runs
from spends import SPENDS, Unknown, budget, recorded_spend
from state_assembly import read_state
from state_reads import new_state
from ticket_form import section, section_head
from ticket_reads import read_tickets
from ticket_watch import watched
from transcript_snapshots import Refused
from usage_limit import Reading, read, usage_file

from operations import directives, taking
from operations.pacing import Scripted, Until, WindowName
from operations.state import Spend, State, Ticket
from operations.tracker import blocked_on_user, wait_line
from ticketing.times import utc_stamp
from ticketing.vocabulary import UNTAKEN, Kind, Status

EVENTS = "/events"
"""The route of the Server-Sent Events stream."""

POLL = 3.0
"""The seconds between two reads of `fingerprint` for a connected client."""

WEEKLY_LIMIT = 8400.0
AFTER_DECISION = 7.0
"""The weekly usage limit in dollars and a change's spend after its
decision, as `prompts/agents/notes/decisions.md#cost-and-time` gives
them."""

IMPACT = "Impact"
SAVING_KINDS = (Kind.BUG, Kind.PERFORMANCE, Kind.DELAY)
"""The kinds whose open tickets the page gives as bugs and cost savings,
with the first sentence of their `## Impact` section."""

OPEN = frozenset(Status) - {Status.CLOSED, Status.DRAFT}
DAY = 86400.0
TREND_DAYS = 14


type Stamp = tuple[str, int, int] | None


def stamp(path: Path) -> Stamp:
    """The name, modification time and size of `path`, or None where it
    does not exist."""
    try:
        st = path.stat()
    except OSError:
        return None
    return (path.name, st.st_mtime_ns, st.st_size)


def fingerprint(tickets: Path) -> tuple[Stamp, ...]:
    """The stamps of each status directory of `tickets`, of each ticket file
    outside `tickets/closed/` (a log line appended to a file changes its
    time and not its directory's), of `tickets/spends/` and of the usage
    cache. The page answers a change of it with a render."""
    out: list[Stamp] = []
    for s in Status:
        d = tickets / s.value
        out.append(stamp(d))
        if s is not Status.CLOSED and d.is_dir():
            out.extend(stamp(p) for p in sorted(d.iterdir()))
    return (*out, stamp(tickets / SPENDS), stamp(usage_file()))


def render(tickets: Path) -> str:
    """The page of `tickets` as it stands at the call: a new state of the
    held reads (`state_reads.new_state`), so that no read gives a file as
    an earlier render read it."""
    now = new_state()
    undecided: list[str] = []
    return page(tickets, now, read(now, undecided), operator_state(tickets), undecided)


def operator_state(tickets: Path) -> State | str:
    """The state of the latest operator of the main session, as `operate.py
    waits` reads it, or why there is none."""
    session = named_main(tickets)
    if session is None:
        return "no main session is set (`file_ticket.py main`)"
    try:
        operators = operator_runs(session, "")
        if not operators:
            return f"no operator of the main session {session} ran `next`"
        return read_state(operators[-1][0])[0]
    except Refused as e:
        return f"the operator's state does not read: {e}"


def dollars(d: float) -> str:
    return f"${d:,.2f} ({100 * d / WEEKLY_LIMIT:.2f}% wk)"


def spend_text(s: Spend) -> str:
    return f"{dollars(s.dollars)} [{', '.join(sorted(s.by_role)) or 'no role'}]"


def impact(t: Ticket) -> str:
    """The first sentence of the `## Impact` section of `t`'s file."""
    try:
        text = t.path.read_text()
    except OSError:
        return ""
    if section_head(text, IMPACT) is None:
        return ""
    body = " ".join(section(text, IMPACT).split())
    end = body.find(". ")
    return body if end < 0 else body[:end + 1]


@dataclass(frozen=True)
class Costs:
    """The spend of each closed change that has a record, and the estimated
    cost of each other change, in dollars, with the roles each counts."""
    spent: dict[str, Spend]
    estimated: dict[str, tuple[float, tuple[str, ...]] | None]


def costs(tickets: Path, all_: Mapping[str, Ticket], now: float, undecided: list[str]) -> Costs:
    spent: dict[str, Spend] = {}
    estimated: dict[str, tuple[float, tuple[str, ...]] | None] = {}
    budgets: dict[frozenset[str], tuple[float, tuple[str, ...]] | None] = {}
    for n, t in all_.items():
        if t.kind is not Kind.CHANGE:
            continue
        if t.status is Status.CLOSED:
            r = recorded_spend(t.path)
            if r is not None and r is not Unknown.SPEND:
                spent[n] = r
            continue
        if t.editors is None:
            estimated[n] = None
            continue
        key = frozenset(t.editors)
        if key not in budgets:
            b = budget(tickets, frozenset(t.editors), now, undecided)
            budgets[key] = None if b is None else (b.dollars + AFTER_DECISION,
                                                   tuple(sorted(b.role_medians)))
        estimated[n] = budgets[key]
    return Costs(spent, estimated)


def served_by(all_: Mapping[str, Ticket]) -> dict[str, list[str]]:
    """The changes whose Motivation gives each ticket, in the tracker's
    order."""
    out: dict[str, list[str]] = {}
    for n, t in sorted(all_.items(), key=lambda kv: kv[1].order):
        if t.kind is Kind.CHANGE:
            for m in t.motivation:
                if n not in out.setdefault(m, []):
                    out[m].append(n)
    return out


def waits_on(t: Ticket) -> list[str]:
    """The tickets `t` waits on: the change of its wait line and its
    `depends-on` field."""
    line = wait_line(t)
    first = [line.on_change] if line is not None and line.on_change is not None else []
    return list(dict.fromkeys([*first, *t.depends_on]))


def status_at(t: Ticket, at: float) -> Status | None:
    held = [ln.status for ln in t.log if ln.time <= at]
    return held[-1] if held else None


def trend(all_: Iterable[Ticket], now: float) -> list[tuple[str, int, int, int]]:
    """For each of the last `TREND_DAYS` days (UTC), the tickets filed, the
    moves into `tickets/closed/`, and the open tickets at its end."""
    today = now - now % DAY
    days = [today - i * DAY for i in range(TREND_DAYS - 1, -1, -1)]
    filed: Counter[float] = Counter()
    closed: Counter[float] = Counter()
    open_at: Counter[float] = Counter()
    for t in all_:
        filed[t.filed - t.filed % DAY] += 1
        for ln in t.log:
            if ln.status is Status.CLOSED:
                closed[ln.time - ln.time % DAY] += 1
        for d in days:
            if status_at(t, min(now, d + DAY)) in OPEN:
                open_at[d] += 1
    return [(time.strftime("%m-%d", time.gmtime(d)), filed[d], closed[d], open_at[d]) for d in days]


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


def now_section(state: State | str, usage: Reading, today: float,
                open_: Iterable[str]) -> str:
    parts: list[str] = []
    if isinstance(state, str):
        parts.append(f'<p class="warn">{esc(state)}; the Op lines and the in-flight spend are not shown.</p>')
    else:
        pace_lines = [ln.text for ln in directives.session_lines(state)
                      if ln.kind is directives.Directive.PACE]
        match state.computed.pace:
            case Until(at, cap):
                verdict = (f"admits from {utc_stamp(at)}" + ("" if cap is None else f", cap {cap}"))
            case Scripted(_, admits):
                verdict = "script admits" if admits else "script holds"
            case other:
                verdict = f"not computed: {other}"
        held = set(open_)
        exp = sorted(held & taking.expedited(state))
        allowed = sorted(held & taking.allowed(state))
        parts.append(table(["Op line", "In force"], [
            ["pace", f"{esc(pace_lines[-1] if pace_lines and directives.pace(state) is not None else 'default (five-hour, even)')}"
                     f" &mdash; {esc(verdict)}"],
            ["pause", "paused" if directives.paused(state) else "running"],
            ["scope", "own" if directives.own_scope(state) else "all"],
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


def page(tickets: Path, now: float, usage: Reading, state: State | str,
         undecided: list[str]) -> str:
    """The text of the page at `now`."""
    all_, unread = read_tickets(tickets)
    c = costs(tickets, all_, now, undecided)
    held_spend = {} if isinstance(state, str) else state.computed.spent
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
                return "spent " + spend_text(held_spend[n])
            if n in c.spent:
                return "spent " + spend_text(c.spent[n])
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
    ex = set() if isinstance(state, str) else taking.expedited(state)
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
                        esc(all_[n].log[-1].note),
                        esc(spend_text(c.spent[n])) if n in c.spent else ""] for n in recent])
    today = (sum(c.spent[n].dollars for n in recent if n in c.spent)
             + sum(s.dollars for s in held_spend.values()))

    trend_rows = trend(all_.values(), now)
    top = max([1, *(r[3] for r in trend_rows)])
    trend_html = table(["Day (UTC)", "Filed", "Closed", "Open at end", "Open, drawn"],
                       [[esc(d), str(f), str(cl), str(o),
                         f'<span class="bar" style="width:{300 * o / top:.0f}px"></span>']
                        for d, f, cl, o in trend_rows])

    data = {n: {"k": str(t.kind), "s": str(t.status), "t": t.title, "se": t.session,
                "p": str(t.path), "w": waits_on(t), "wb": waited_by.get(n, []),
                "m": list(t.motivation), "sb": serving.get(n, []),
                "e": estimate(n), "g": int(n in gains),
                "c": est_text(n) if t.kind is Kind.CHANGE or t.status in OPEN else "",
                "l": [[utc_stamp(ln.time), str(ln.status), ln.agent, ln.note] for ln in t.log]}
            for n, t in ((n, all_[n]) for n in order)}
    blob = json.dumps(data, separators=(",", ":")).replace("<", "\\u003c")
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
    return filled(TEMPLATE, {
        "RENDERED": esc(utc_stamp(now)), "NAV": nav, "BODY": body, "EVENTS": EVENTS,
        "NOTES": f"<ul class='notes'>{notes}</ul>" if notes else "",
        "OPEN": json.dumps(sorted(OPEN)), "DATA": blob})


def filled(template: str, parts: Mapping[str, str]) -> str:
    """`template` with each `@NAME@` in it replaced by `parts[NAME]`, in one
    pass, so that no text a part inserts is read as a placeholder."""
    return re.sub(r"@([A-Z]+)@", lambda m: parts[m[1]], template)


SEARCH = """<div class="filters">
<input id="q" type="search" placeholder="number, title, kind or log words" size="40">
<select id="fkind"><option value="">any kind</option>@KINDS@</select>
<select id="fstatus"><option value="">any status</option><option value="open">open</option>@STATUSES@</select>
<input id="fsession" type="text" placeholder="session" size="6">
<label>est. cost below $<input id="fbelow" type="number" min="0" step="1" style="width:5em"></label>
<label><input id="fpriced" type="checkbox"> gain priced only</label>
</div><p id="count" class="hint"></p><div id="results"></div>"""

TEMPLATE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Tickets</title><style>
body{font:14px/1.4 -apple-system,Helvetica,Arial,sans-serif;margin:0 16px 40px;color:#222}
header{position:sticky;top:0;background:#fff;border-bottom:1px solid #ccc;padding:6px 0;z-index:2}
h1{font-size:18px;margin:0 12px 0 0;display:inline}h2{font-size:16px;margin:22px 0 6px;border-bottom:2px solid #ddd}
a.nav{margin-right:10px;white-space:nowrap}.box{overflow-x:auto;max-width:100%}
table{border-collapse:collapse;width:100%;margin:4px 0}
th,td{border:1px solid #ddd;padding:3px 6px;text-align:left;vertical-align:top;overflow-wrap:anywhere}
th{background:#f3f3f3}tr:nth-child(even) td{background:#fafafa}
.warn{color:#b00020;font-weight:600}.ok{color:#1b7f2a}.hint{color:#666;font-size:12px;margin:2px 0}
.bar{display:inline-block;height:10px;background:#4a78c2;max-width:100%}
.filters{display:flex;gap:10px;flex-wrap:wrap;align-items:center}.filters input,.filters select{font-size:16px;max-width:100%}
.res{border:1px solid #ddd;margin:4px 0;padding:4px 8px;overflow-wrap:anywhere}.res summary{cursor:pointer}
.log{font:12px/1.35 Menlo,monospace;white-space:pre-wrap;margin:4px 0}.path{font:12px Menlo,monospace;color:#555}
.notes{color:#666;font-size:12px;overflow-wrap:anywhere}
@media (min-width:701px){td:nth-child(-n+3){white-space:nowrap;overflow-wrap:normal}}
#live-state{font-size:12px}
@media (max-width:700px){body{margin:0 8px 40px;font-size:13px}
header{position:static}h2{font-size:15px}
.box table,.box tbody,.box tr,.box td{display:block;width:auto}.box thead{display:none}
.box tr{border:1px solid #ddd;margin:0 0 6px;padding:2px 0}.box td{border:0;padding:1px 6px;overflow-wrap:anywhere}
.box td:empty{display:none}.box td::before{content:attr(data-l) ": ";color:#666;font-size:12px}
.box tr:nth-child(even) td{background:none}
#q{width:100%}}
</style></head><body>
<header><h1>Tickets</h1><span class="hint">rendered <span id="rendered">@RENDERED@</span> UTC;
<span id="live-state">connecting</span></span><br>@NAV@</header>
<div id="live">@NOTES@
@BODY@
<script id="data" type="application/json">@DATA@</script></div>
<script>
let T=JSON.parse(document.getElementById('data').textContent);
const ids=['q','fkind','fstatus','fsession','fbelow','fpriced'];
const OPEN=s=>@OPEN@.includes(s);
function val(id){const e=document.getElementById(id);return e.type==='checkbox'?(e.checked?'1':''):e.value}
function setv(id,v){const e=document.getElementById(id);if(e.type==='checkbox')e.checked=!!v;else e.value=v||''}
function snapshot(){const s={open:[...document.querySelectorAll('details.res[open]')].map(d=>d.dataset.n)};
ids.forEach(i=>s[i]=val(i));return s}
function fromHash(){const h=new URLSearchParams(location.hash.slice(1));const s={};
const map={q:'q',kind:'fkind',status:'fstatus',session:'fsession',below:'fbelow',priced:'fpriced'};
let any=false;for(const[k,i]of Object.entries(map))if(h.has(k)){s[i]=h.get(k);any=true}return any?s:null}
function keep(n,t){const k=val('fkind'),st=val('fstatus'),se=val('fsession'),b=val('fbelow'),p=val('fpriced');
if(k&&t.k!==k)return false;if(st&&(st==='open'?!OPEN(t.s):t.s!==st))return false;
if(se&&String(t.se)!==se)return false;if(b!==''&&t.e!==null&&t.e>=+b)return false;if(p&&!t.g)return false;return true}
function lk(n){return `<a href="#" class="tk" data-n="${n}">${n}</a>`+(T[n]?` <i>${T[n].s}</i>`:'')}
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function item(n,open){const t=T[n];const rows=t.l.map(l=>esc(l.join(' '))).join('\\n');
const L=(name,xs)=>xs.length?`<div><b>${name}:</b> ${xs.map(lk).join(', ')}</div>`:'';
return `<details class="res" data-n="${n}"${open?' open':''}><summary><b>${n}</b> <i>${t.s}</i> ${t.k}: ${esc(t.t)}${t.c?` <span class="hint">${esc(t.c)}</span>`:''}</summary>
<div class="path">${esc(t.p)}</div>${L('waits on',t.w)}${L('waited on by',t.wb)}${L('serves',t.m)}${L('served by change',t.sb)}
<div class="hint">body: uv run python scripts/file_ticket.py show ${n}</div><div class="log">${rows}</div></details>`}
function search(openSet){const q=val('q').toLowerCase().trim();const words=q.split(/\\s+/).filter(Boolean);
document.querySelectorAll('tr.worth').forEach(r=>{const t={k:r.dataset.kind,s:r.dataset.status,se:r.dataset.session,
e:r.dataset.est===''?null:+r.dataset.est,g:+r.dataset.priced};r.style.display=keep(null,t)?'':'none'});
const out=[];if(words.length){for(const n of Object.keys(T).reverse()){const t=T[n];if(!keep(n,t))continue;
{const hay=(n+' '+t.t+' '+t.k+' '+t.l.map(l=>l[3]).join(' ')).toLowerCase();if(!words.every(w=>hay.includes(w)))continue}
out.push(n);if(out.length>=200)break}}
document.getElementById('count').textContent=words.length?`${out.length}${out.length>=200?'+':''} matches, newest first`:'Type to search all tickets, closed ones included. The filters apply to the matches and to Bugs and cost savings.';
document.getElementById('results').innerHTML=out.map(n=>item(n,openSet.has(n)||n===q)).join('')}
function restore(s){if(s)ids.forEach(i=>setv(i,s[i]));search(new Set(s&&s.open||[]))}
function openTicket(n){document.getElementById('q').value=n;search(new Set([n]));document.getElementById('search').scrollIntoView()}
document.addEventListener('click',e=>{const a=e.target.closest('a.tk');if(a){e.preventDefault();openTicket(a.dataset.n)}});
document.addEventListener('input',e=>{if(ids.includes(e.target.id))search(new Set())});
window.addEventListener('hashchange',()=>{const h=fromHash();if(h)restore(h)});
restore(fromHash());
let busy=false,again=false;
async function update(){if(busy){again=true;return}busy=true;
try{const r=await fetch('/',{cache:'no-store'});const d=new DOMParser().parseFromString(await r.text(),'text/html');
const s=snapshot(),x=window.scrollX,y=window.scrollY;
document.getElementById('live').replaceWith(d.getElementById('live'));
document.getElementById('rendered').textContent=d.getElementById('rendered').textContent;
T=JSON.parse(document.getElementById('data').textContent);restore(s);window.scrollTo(x,y)}
catch(e){document.getElementById('live-state').textContent='update failed: '+e}
busy=false;if(again){again=false;update()}}
const ev=new EventSource('@EVENTS@');const st=document.getElementById('live-state');
ev.onopen=()=>{st.textContent='live: updates as tickets change'};
ev.onerror=()=>{st.textContent='disconnected; retrying'};
ev.onmessage=()=>update();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    """Serves `/` and `EVENTS` of the tracker `tickets`, and nothing else.
    Each render runs on the one thread of `renderer`: the reads it makes
    keep a SQLite store (`kept_reads`) that only the thread that opened it
    may use."""
    tickets: Path
    renderer: ThreadPoolExecutor

    def do_GET(self) -> None:
        match self.path.split("?", 1)[0]:
            case "/":
                began = time.monotonic()
                body = self.renderer.submit(render, self.tickets).result().encode()
                self.log_message("rendered %d bytes in %.2f s", len(body), time.monotonic() - began)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            case p if p == EVENTS:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.stream()
            case _:
                self.send_error(404)

    def stream(self) -> None:
        """Sends an event each time `fingerprint` changes, and a comment
        line at each other read, so that a closed client ends the loop."""
        last = fingerprint(self.tickets)
        try:
            self.wfile.write(b": open\n\n")
            self.wfile.flush()
            while True:
                time.sleep(POLL)
                now = fingerprint(self.tickets)
                self.wfile.write(b"data: changed\n\n" if now != last else b": same\n\n")
                self.wfile.flush()
                last = now
        except (BrokenPipeError, ConnectionResetError):
            return


def serve(address: str, port: int, tickets: Path) -> ThreadingHTTPServer:
    """A server of `tickets` bound to `address` and `port`, not yet
    serving."""
    handler = type("Bound", (Handler,), {"tickets": tickets,
                                         "renderer": ThreadPoolExecutor(max_workers=1)})
    server = ThreadingHTTPServer((address, port), handler)
    server.daemon_threads = True
    return server


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("address")
    parser.add_argument("port", type=int)
    parser.add_argument("--tickets", type=Path, default=None,
                        help="the tracker to serve; the main tree's `tickets/` where not given")
    args = parser.parse_args(argv)
    server = serve(args.address, args.port, args.tickets or main_tickets())
    print(f"serving http://{args.address}:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
