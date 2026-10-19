"""The ticket dashboard's search over all tickets, closed ones included,
and the sheet of a ticket (`ticket_dashboard`), over the entries of a
render (`dashboard_html.Rendered`): the words of a request, as the page's
search box gives them in the URL's `q` parameter, the HTML of their hits,
newest first and at most `LIMIT` of them, and the HTML of a ticket's
sheet."""

from collections.abc import Mapping

from dashboard_html import NOTE_WORDS, Entry, clock, cut, esc, tap

from operations.state import LogLine

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
    hay = " ".join([n, e.phrase, t.title, str(t.kind), *(ln.note for ln in t.log)]).lower()
    return all(w in hay for w in words)


def results(entries: Mapping[str, Entry], words: tuple[str, ...]) -> str:
    """The HTML of the hits of `words` among `entries`, in the tracker's
    order, newest first, each a card that opens the ticket's sheet."""
    if not words:
        return ""
    out: list[str] = []
    for n in reversed(list(entries)):
        e = entries[n]
        if matched(n, e, words):
            out.append(tap(n, f'<span class="num">{esc(n)}</span> <span class="sh">{esc(e.phrase)}</span>'
                              f'<div class="meta">{esc(e.status)}</div>', "card"))
            if len(out) >= LIMIT:
                break
    return "".join(out) or '<div class="meta">No match</div>'


def log_line(ln: LogLine, now: float) -> str:
    """The HTML of the log line `ln`: its time, status and note, where the
    note is cut, with the cut and the full note and a label that expands it."""
    head = f"{esc(clock(ln.time, now))} · {esc(ln.status)} · "
    if len(ln.note.split()) <= NOTE_WORDS:
        return f'<div class="lg">{head}{esc(ln.note)}</div>'
    return (f'<div class="lg">{head}<span>{esc(cut(ln.note, NOTE_WORDS))}</span><span hidden>{esc(ln.note)}</span>'
            ' <i class="more">more</i></div>')


def sheet(e: Entry, now: float) -> str:
    """The HTML of the sheet of `e`: its number and kind, its phrase, the
    plain sentence on its status and its last `SHEET_LINES` log lines."""
    t = e.ticket
    lines = "".join(log_line(ln, now) for ln in t.log[-SHEET_LINES:])
    return (f'<div class="num">{esc(t.number)} · {esc(t.kind)}</div>'
            f'<div class="sh" style="font-size:17px">{esc(e.phrase)}</div><div class="p">{esc(e.status)}</div>{lines}')
