"""The membership and operator standing of dashboard work rows."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from dashboard_reads import OPEN, change_of
from shown_state import Hold, OnTicket, ShownAgent
from operations.state import Ticket
from ticketing.vocabulary import Kind, Status

if TYPE_CHECKING:
    from dashboard_html import View

MERGED_NOTE = "merged"

class Standing(Enum):
    """Where an open ticket stands, by the first thing that must change
    before it starts: nothing (at work or ready), a ticket that moves
    (waiting), a hold of its own or its session's, or a ticket held
    so (behind). The pause of a session is no such thing: a ticket of a
    paused session stands as it would once the session resumes."""
    WORKING = auto()
    READY = auto()
    WAITING = auto()
    OWN_SCOPE = auto()
    NO_OPERATOR = auto()
    HELD = auto()
    ON_HOLD = auto()
    DEFERRED = auto()
    BEHIND = auto()


MOVING = frozenset({Standing.WORKING, Standing.READY, Standing.WAITING})
"""The standings of a blocker that leave the ticket it blocks waiting on
it; a blocker held otherwise leaves it behind held work."""

FIRST = frozenset({Standing.WORKING, Standing.ON_HOLD, Standing.DEFERRED, Standing.NO_OPERATOR, Standing.OWN_SCOPE})
"""The standings of a ticket's own that must change before its blocker
matters."""

HELD_HEAD: Mapping[Standing, str] = {
    Standing.HELD: "Held by a line", Standing.BEHIND: "Behind held work",
    Standing.NO_OPERATOR: "No operator running", Standing.ON_HOLD: "On hold by you",
    Standing.OWN_SCOPE: "Outside its own work", Standing.DEFERRED: "Deferred"}
"""The head of each group of held tickets in a session's tab of Queued,
in the order of the groups."""

HOLD_WORD: Mapping[Standing, str] = {
    Standing.ON_HOLD: "on hold by you", Standing.DEFERRED: "deferred",
    Standing.OWN_SCOPE: "outside its own work", Standing.NO_OPERATOR: "no operator",
    Standing.HELD: "held by a line"}
"""What holds the ticket a row behind held work waits on."""


@dataclass(frozen=True)
class Row:
    """A work row's lead, live change, and complete open membership."""
    lead: Ticket
    change: Ticket | None
    members: tuple[Ticket, ...]

    @property
    def subject(self) -> Ticket:
        """The ticket whose state the row gives."""
        return self.lead if self.change is None else self.change


def merged(t: Ticket) -> bool:
    """Whether `t` is released and its log gives its change merged."""
    return t.status is Status.RELEASED and any(ln.note.startswith(MERGED_NOTE) for ln in t.log)


class Standings:
    """One row per live change with complete membership, and one row per uncovered open ticket."""

    def __init__(self, v: View) -> None:
        self.v = v
        records = v.records.records
        self.paused = {r.index for r in records if r.shown.paused}
        self.own_scope = {r.index for r in records if r.shown.own_scope}
        self.in_scope = {r.index: r.shown.in_scope for r in records}
        self.live = {r.index for r in records}
        self.main = None if v.records.main_missing is not None or not records else records[0].index
        self.open_ = [t for t in v.all_.values() if t.status in OPEN and not merged(t)]
        self.waiting_on: dict[str, list[Ticket]] = {}
        for t in self.open_:
            if (c := change_of(t, v.all_)) is not None:
                self.waiting_on.setdefault(c.number, []).append(t)
        self.position: dict[str, int] = {}
        """The place of each ticket among the starts of its record that no
        hold but the pace or the pause holds, in their order."""
        for r in records:
            k = 0
            for st in r.shown.starts:
                if st.number not in self.position and st.held in (None, Hold.PACE, Hold.PAUSE):
                    self.position[st.number] = k
                    k += 1
        self.pooled: dict[str, list[ShownAgent]] = {t.number: list(v.agents.get(t.number, [])) for t in self.open_}
        """The agents counted for the standing of each row's subject."""
        self.rows: list[Row] = []
        self.changes: dict[str, list[Ticket]] = {}
        covered: set[str] = set()
        for t in self.open_:
            if t.kind is not Kind.CHANGE:
                continue
            members = tuple(self.heads(t))
            lead = t if sum(h.kind is Kind.REQUEST for h in members) > 1 else self.lead(self.terminals(t))
            self.rows.append(Row(lead, t, members))
            covered.update(h.number for h in members)
            for h in members:
                if h is not t:
                    self.changes.setdefault(h.number, []).append(t)
        for t in v.all_.values():
            if t.status in OPEN and t.number not in covered:
                self.rows.append(Row(t, None, (t,)))
        for r in self.rows:
            workers = self.pooled.setdefault(r.subject.number, [])
            for member in r.members:
                if member.kind is not Kind.CHANGE and member is not r.subject:
                    for agent in v.agents.get(member.number, []):
                        if agent not in workers:
                            workers.append(agent)
        self.memo: dict[str, tuple[Standing, Ticket]] = {}

    def served(self, t: Ticket) -> list[Ticket]:
        all_ = self.v.all_
        return [all_[m] for m in t.motivation if m in all_ and all_[m].status in OPEN] + (
            self.waiting_on.get(t.number, []) if t.kind is Kind.CHANGE else [])

    def heads(self, t: Ticket, seen: frozenset[str] = frozenset()) -> list[Ticket]:
        """The complete open membership reached through Motivation and waiting links."""
        if t.number in seen:
            return []
        out = {t.number: t}
        for member in self.served(t):
            out.update((h.number, h) for h in self.heads(member, seen | {t.number}))
        return list(out.values())

    def terminals(self, t: Ticket, seen: frozenset[str] = frozenset()) -> list[Ticket]:
        """The terminal members used for the existing lead selection."""
        out: dict[str, Ticket] = {}
        for member in self.served(t):
            if member.number not in seen and member.number != t.number and not merged(member):
                out.update((h.number, h) for h in self.terminals(member, seen | {t.number}))
        return list(out.values()) or [t]

    @staticmethod
    def lead(heads: list[Ticket]) -> Ticket:
        """The ticket of `heads` a live change's row leads with: the oldest
        `request`, else the oldest."""
        return min(heads, key=lambda h: (h.kind is not Kind.REQUEST, h.filed))

    def shown(self, r: Row) -> bool:
        return True

    def agents(self, t: Ticket) -> list[ShownAgent]:
        """The agents whose work the standing of `t` counts (`pooled`)."""
        return self.pooled.get(t.number, [])

    def blocker(self, t: Ticket) -> Ticket | None:
        """The first open dependency, the ticket holding a start, or the
        unfinished change `t` waits on, including a draft."""
        deps = [d for d in t.depends_on if d in self.v.all_ and self.v.all_[d].status in OPEN]
        if deps:
            return self.v.all_[deps[0]]
        if isinstance(h := self.v.holds.get(t.number), OnTicket):
            if (held := self.v.all_.get(h.number)) is not None and held.status is not Status.CLOSED and not merged(held):
                return held
        c = change_of(t, self.v.all_)
        return c if c is not None and c.status is not Status.CLOSED and not merged(c) else None

    def own(self, t: Ticket) -> Standing:
        """The standing of `t` apart from its blockers."""
        v = self.v
        c = change_of(t, v.all_)
        if self.agents(t):
            return Standing.WORKING
        if t.status is Status.BLOCKED or (c is not None and c.status is Status.BLOCKED):
            return Standing.ON_HOLD
        if t.status is Status.DEFERRED:
            return Standing.DEFERRED
        if t.session is None or t.session not in self.live:
            return Standing.NO_OPERATOR
        if t.session in self.own_scope and not self.owned(t):
            return Standing.OWN_SCOPE
        match v.holds.get(t.number):
            case Hold.OWN_SCOPE:
                return Standing.OWN_SCOPE
            case Hold.TAKES:
                return Standing.HELD
            case _:
                return Standing.READY

    def owned(self, t: Ticket) -> bool:
        """Whether the operator of the session of `t`, which has a record,
        takes `t` while it keeps to its own scope: `t` is of the record's
        `in_scope`; or, where the record gives no `in_scope`, `t` is the
        user's."""
        admitted = self.in_scope[t.session]
        return self.v.mine(t) if admitted is None else t.number in admitted

    def state(self, t: Ticket, seen: frozenset[str] = frozenset()) -> tuple[Standing, Ticket]:
        """The standing of `t` and the ticket it stands by: `t`'s own
        standing and `t` where that standing is in `FIRST` or `t` has no
        blocker; waiting and its blocker where that blocker's standing is
        in `MOVING`; else behind held work and the held ticket at the end
        of the chain."""
        if t.number in self.memo:
            return self.memo[t.number]
        k = self.own(t)
        b = None if k in FIRST else self.blocker(t)
        if b is None or b.number in seen:
            out = (k, t)
        else:
            bk, root = self.state(b, seen | {t.number})
            out = (Standing.WAITING, b) if bk in MOVING else (Standing.BEHIND, root)
        self.memo[t.number] = out
        return out

