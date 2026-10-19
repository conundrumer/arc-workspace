"""The ticket dashboard's search over all tickets, closed ones included
(`ticket_dashboard`): the filters and words of a request, as the page's
search form gives them in the URL's parameters, and the HTML of the
matches among the entries of a render (`dashboard_html.Rendered`), newest
first and at most `LIMIT` of them."""

from collections.abc import Mapping
from dataclasses import dataclass

from dashboard_html import esc, link
from dashboard_reads import OPEN, Entry

from ticketing.times import utc_stamp
from ticketing.vocabulary import Kind, Status

LIMIT = 200
"""The most matches a search gives."""

OPEN_WORD = "open"
"""The value of the status filter that keeps the open tickets."""


@dataclass(frozen=True)
class Query:
    """A search: its words, lowercased, and its filters: the kind, the
    statuses kept, the session as its text, the estimated cost a kept
    ticket's falls below, where it has one, and whether only the tickets
    with a priced gain are kept."""
    words: tuple[str, ...]
    kind: Kind | None
    statuses: frozenset[Status] | None
    session: str | None
    below: float | None
    priced: bool


def query(params: Mapping[str, list[str]]) -> Query:
    """The `Query` of the URL's parameters `params`, as `urllib.parse.parse_qs`
    gives them, each given at most once; raises `ValueError` on a value that
    is not one of its filter's."""
    one = {k: v[-1] for k, v in params.items()}
    status = one.get("status")
    below = one.get("below")
    return Query(
        tuple(one["q"].lower().split()) if "q" in one else (),
        Kind(one["kind"]) if "kind" in one else None,
        None if status is None else OPEN if status == OPEN_WORD else frozenset({Status(status)}),
        one.get("session"),
        None if below is None else float(below),
        "priced" in one)


def kept(e: Entry, q: Query) -> bool:
    """Whether the filters of `q` keep `e`; a ticket with no estimate passes
    the cost filter."""
    t = e.ticket
    return ((q.kind is None or t.kind is q.kind)
            and (q.statuses is None or t.status in q.statuses)
            and (q.session is None or (t.session is not None and str(t.session) == q.session))
            and (q.below is None or e.estimate is None or e.estimate < q.below)
            and (not q.priced or e.priced))


def matched(n: str, e: Entry, words: tuple[str, ...]) -> bool:
    """Whether each of `words` is in the number, title, kind or a log note
    of `e`, lowercased."""
    t = e.ticket
    hay = " ".join([n, t.title, str(t.kind), *(ln.note for ln in t.log)]).lower()
    return all(w in hay for w in words)


def results(entries: Mapping[str, Entry], q: Query) -> str:
    """The HTML of the count and of the matches of `q` among `entries`, in
    the tracker's order, newest first."""
    if not q.words:
        return ('<p class="hint">Type to search all tickets, closed ones included. The filters apply'
                ' to the matches and to Bugs and cost savings.</p>')
    out: list[str] = []
    for n in reversed(list(entries)):
        e = entries[n]
        if kept(e, q) and matched(n, e, q.words):
            out.append(n)
            if len(out) >= LIMIT:
                break
    count = f"{len(out)}{'+' if len(out) >= LIMIT else ''} matches, newest first"
    return f'<p class="hint">{count}</p>' + "".join(item(n, entries) for n in out)


def item(n: str, entries: Mapping[str, Entry]) -> str:
    """The result item of `n`: its links, cost text, path and log."""
    e = entries[n]
    t = e.ticket

    def linked(m: str) -> str:
        return link(m) + (f" <i>{esc(entries[m].ticket.status)}</i>" if m in entries else "")

    def listed(name: str, ns: tuple[str, ...]) -> str:
        return f"<div><b>{name}:</b> {', '.join(map(linked, ns))}</div>" if ns else ""

    log = "\n".join(esc(f"{utc_stamp(ln.time)} {ln.status} {ln.agent} {ln.note}") for ln in t.log)
    cost = f' <span class="hint">{esc(e.cost)}</span>' if e.cost else ""
    return (f'<details class="res" data-n="{esc(n)}"><summary><b>{esc(n)}</b> <i>{esc(t.status)}</i>'
            f' {esc(t.kind)}: {esc(t.title)}{cost}</summary>\n'
            f'<div class="path">{esc(t.path)}</div>{listed("waits on", e.waits_on)}'
            f'{listed("waited on by", e.waited_by)}{listed("serves", t.motivation)}'
            f'{listed("served by change", e.served_by)}\n'
            f'<div class="hint">body: uv run python scripts/file_ticket.py show {esc(n)}</div>'
            f'<div class="log">{log}</div></details>')
