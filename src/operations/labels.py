"""The label of a ticket, which every text for a person calls: the ticket's
kind letter joined to its number, then its plain title in parentheses, as
`C11-3451 (…)`, and after the title of a `change` or a `validation` the
`request` it serves, as `, for R11-3437`; with the phrase of a ticket and
the request a ticket serves, which the label builds on."""

from collections.abc import Mapping

from operations.state import Ticket
from ticketing.vocabulary import Kind, lettered


def served_request(t: Ticket, all_: Mapping[str, Ticket], seen: frozenset[str] = frozenset()) -> Ticket | None:
    """The first `request` the Motivation of `t` gives, followed through
    the `change` tickets it gives."""
    for m in t.motivation:
        r = all_.get(m)
        if r is None or m in seen:
            continue
        if r.kind is Kind.REQUEST:
            return r
        if r.kind is Kind.CHANGE and (found := served_request(r, all_, seen | {t.number, m})) is not None:
            return found
    return None


def title_text(t: Ticket) -> str:
    """The text of the title of `t` after its first `: `, up to its first
    `, ` or `;`, with its first letter capitalized."""
    _, colon, after = t.title.partition(": ")
    cut = (after if colon else t.title).split(", ")[0].split(";")[0]
    return cut[:1].upper() + cut[1:]


def phrase(t: Ticket, all_: Mapping[str, Ticket]) -> str:
    """The phrase of `t`: its Goal; else the Goal of `served_request`; else
    `title_text`."""
    r = served_request(t, all_)
    goal = t.goal if t.goal is not None else None if r is None else r.goal
    if goal is not None:
        return " ".join(goal.split())
    return title_text(t)


def shown_number(t: Ticket) -> str:
    """The number of `t` as a reader sees it: its kind letter and number."""
    return lettered(t.kind, t.number)


def request_of(t: Ticket, all_: Mapping[str, Ticket]) -> Ticket | None:
    """The request that `t` serves, where `t` is a `change` or a
    `validation` and `all_` holds that request."""
    match t.kind:
        case Kind.CHANGE:
            return served_request(t, all_)
        case Kind.VALIDATION:
            return None if t.validates is None else all_.get(t.validates)
        case _:
            return None


def label(t: Ticket, all_: Mapping[str, Ticket]) -> str:
    """The label of `t`: `<lettered> (<plain title>)`, the plain title being
    `title_text` for a `change` and a `validation` and `phrase` for another
    kind, and, for those two kinds, `, for <lettered request>` after it where
    `request_of` finds the request."""
    if t.kind not in (Kind.CHANGE, Kind.VALIDATION):
        return f"{shown_number(t)} ({phrase(t, all_)})"
    request = request_of(t, all_)
    served = "" if request is None else f", for {shown_number(request)}"
    return f"{shown_number(t)} ({title_text(t)}){served}"
