"""The ticket dashboard's search over all tickets, closed ones included,
and the sheet of a ticket (`ticket_dashboard`), over the entries of a
render (`dashboard_html.Rendered`): the words of a request, as the page's
search box gives them in the URL's `q` parameter, the HTML of their hits,
a ticket whose number, bare or with its kind letter, is one of them first, then newest first, and at most
`LIMIT` of them, and the HTML of a ticket's sheet, with the changes
whose rows lead with it."""

from collections.abc import Mapping

from dashboard_reads import about
from dashboard_html import NOTE_WORDS, Entry, clock, cut, esc, tap

from operations.labels import shown_number
from operations.state import LogLine, Ticket

LIMIT = 8
"""The most hits a search gives."""

SHEET_LINES = 6
"""The most log lines a ticket's sheet gives."""


def words(params: Mapping[str, list[str]]) -> tuple[str, ...]:
    """The words of the URL's parameters `params`, as `urllib.parse.parse_qs`
    gives them, lowercased."""
    q = params.get("q")
    return () if not q else tuple(q[-1].lower().split())


def matched(n: str, e: Entry, words: tuple[str, ...]) -> bool:
    """Whether each of `words` is in the number, phrase, title, kind or a
    log note of `e`, lowercased."""
    t = e.ticket
    hay = " ".join([n, shown_number(t), e.phrase, t.title, str(t.kind), *(ln.note for ln in t.log)]).lower()
    return all(w in hay for w in words)


def results(entries: Mapping[str, Entry], words: tuple[str, ...]) -> str:
    """The HTML of the hits of `words` among `entries`, each a card that
    opens the ticket's sheet: first an entry whose number, lowercased, is
    one of `words`, then the others in the tracker's order, newest first."""
    if not words:
        return ""
    hits = [n for n in reversed(list(entries)) if matched(n, entries[n], words)]
    hits.sort(key=lambda n: not {n.lower(), shown_number(entries[n].ticket).lower()} & set(words))
    return "".join(tap(n, f'<span class="num">{esc(entries[n].label)}</span>'
                          f'<div class="meta">{esc(entries[n].status)}</div>', "card")
                   for n in hits[:LIMIT]) or '<div class="meta">No match</div>'


def log_line(ln: LogLine, now: float) -> str:
    """The HTML of the log line `ln`: its time, status and note, where the
    note is cut, with the cut and the full note and a label that expands it."""
    return clipped(f"{esc(clock(ln.time, now))} · {esc(ln.status)} · ", ln.note)


def clipped(head: str, note: str) -> str:
    """The HTML of a line of the sheet: the HTML `head`, then `note`, cut
    where it is long, with the cut and the full note and a label that
    expands it."""
    if len(note.split()) <= NOTE_WORDS:
        return f'<div class="lg">{head}{esc(note)}</div>'
    return (f'<div class="lg">{head}<span>{esc(cut(note, NOTE_WORDS))}</span><span hidden>{esc(note)}</span>'
            ' <i class="more">more</i></div>')


def lines(t: Ticket, now: float) -> str:
    return "".join(log_line(ln, now) for ln in t.log[-SHEET_LINES:])


def sheet(e: Entry, now: float) -> str:
    """The HTML of the sheet of `e`: its number and kind, its phrase, what
    the ticket is about (`dashboard_reads.about`) where it says, each
    live change whose row leads with it with the words of that change's
    state, or else the plain sentence on its status, its last
    `SHEET_LINES` log lines, and the last `SHEET_LINES` of each of those
    changes an agent is at work on, or else of the first, under its
    number."""
    t, cs = e.ticket, e.changes
    leads = [e.status] if not cs else [f"Work on {c.label} · {c.state}" for c in cs]
    tails = [c for c in cs if c.at_work] or cs[:1]
    said = about(t, e.phrase)
    return (f'<div class="num">{esc(e.label)} · {esc(t.kind)}</div>'
            f'<div class="sh" style="font-size:17px">{esc(e.phrase)}</div>'
            + ("" if said is None else clipped("", said))
            + "".join(f'<div class="p">{esc(x)}</div>' for x in leads)
            + lines(t, now)
            + "".join(f'<div class="gh">Change {esc(c.label)}</div>{lines(c.change, now)}' for c in tails))
