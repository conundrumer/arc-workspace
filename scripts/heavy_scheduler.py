"""Which waiting request the resource daemon starts next, and when each
waiting request is expected to start.

The machine's budget is `total`, in CPUs and GiB. A reserve of at most
`RESERVE_CPUS` CPUs and `RESERVE_GIB` GiB (half the budget where it is
smaller) is out of reach of the long jobs, which together take the rest, the
pool. A short job (`heavy_model.SHORT_MINUTES` declared minutes or fewer)
takes from the budget less what the long jobs hold and less the claim of the
head of the long queue: the pool capacity that head could take within its pool
and share limits, up to its ask. So the reserve stays the short jobs' own, and
the long head starts once the jobs that hold its capacity end, whatever short
jobs arrive. A long job takes from the pool, and within it
the jobs of its need and of the needs after it hold at most a share of the
pool: `now` all of it, `soon` four fifths, `idle` a half. Each of the short
and the long queue starts its first waiter alone, whatever the waiters behind
it ask, so a waiter that asks much is never passed by one that asks less. A
short job that runs past its declared minutes is held from then on as a long job of its
need (`Holding.lane`), with its CPUs and GiB unchanged: it counts against the pool and the
shares, and the claim of the long head covers it. A queue goes by need, then arrival; an `idle` waiter that has waited
`PROMOTE_SECONDS` goes as `soon`, with the `idle` share.

Standard library only, Python 3.9."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from heavy_model import Amount, Lane, Need, Waiter, lane_of

RESERVE_CPUS = 4
RESERVE_GIB = 4
SHARES = {Need.NOW: (1, 1), Need.SOON: (4, 5), Need.IDLE: (1, 2)}
"""For each need, the fraction of the pool that the jobs of that need and of the needs after
it hold at most."""
PROMOTE_SECONDS = 30 * 60
OVERDUE_SECONDS = 60
"""A job that has run past its declared minutes is expected to end this long after the
estimate."""


@dataclass(frozen=True)
class Holding:
    """What a running job takes. `need` is None for an ungated process, which takes from the
    pool whatever its lane. `ends` is the wall-clock time the job's declared minutes end at,
    or None."""
    lane: Lane
    need: Optional[Need]
    amount: Amount
    ends: Optional[float]


def reserve(total: Amount) -> Amount:
    return Amount(min(RESERVE_CPUS, total.cpus // 2), min(RESERVE_GIB, total.gib // 2))


def pool(total: Amount) -> Amount:
    return total - reserve(total)


def share(need: Need, whole: Amount) -> Amount:
    """The most that the jobs of `need` and the needs after it hold of `whole`."""
    num, den = SHARES[need]
    return Amount(*(max(1, n * num // den) if n else 0 for n in (whole.cpus, whole.gib)))


def limit(lane: Lane, need: Need, total: Amount) -> Amount:
    """The most one job of the lane and need may ask."""
    return total if lane is Lane.SHORT else share(need, pool(total))


def resolve(asked_cpus: Optional[int], asked_gib: Optional[int], lane: Lane, need: Need,
            total: Amount) -> Tuple[Amount, Amount, bool]:
    """What a call that asks `asked_cpus` and `asked_gib` (None where it gives none: 1 CPU, and 1 GiB
    more than its CPUs) is given, cut to `limit`; that limit; and whether the call was cut."""
    cap = limit(lane, need, total)
    cpus = min(asked_cpus or 1, cap.cpus)
    gib = min(asked_gib or 1 + cpus, cap.gib)
    return Amount(cpus, gib), cap, Amount(cpus, gib) != Amount(asked_cpus or 1, asked_gib or 1 + cpus)


def head_claim(holdings: Iterable[Holding], head: Waiter, total: Amount) -> Amount:
    """The pool capacity that `head`, the first waiter of the long queue, could take beside
    `holdings` within the pool and its share, up to its ask."""
    longs = [h for h in holdings if h.lane is Lane.LONG]
    below = [h for h in longs if h.need is None or h.need.rank >= head.need.rank]
    pool_room = pool(total) - sum_amounts(h.amount for h in longs)
    share_room = share(head.need, pool(total)) - sum_amounts(h.amount for h in below)
    return Amount(max(0, min(head.ask.cpus, pool_room.cpus, share_room.cpus)),
                  max(0, min(head.ask.gib, pool_room.gib, share_room.gib)))


def admissible(holdings: Iterable[Holding], lane: Lane, need: Need, ask: Amount, total: Amount,
               claim: Amount = Amount(0, 0)) -> bool:
    """Whether a job of `lane` and `need` that asks `ask` fits beside `holdings`, and, for a short
    job, beside `claim`, that of the head of the long queue."""
    held = list(holdings)
    taken = sum_amounts(h.amount for h in held)
    if not (taken + ask).within(total):
        return False
    if lane is Lane.SHORT:
        return (taken + claim + ask).within(total)
    longs = [h for h in held if h.lane is Lane.LONG]
    if not (sum_amounts(h.amount for h in longs) + ask).within(pool(total)):
        return False
    below = [h for h in longs if h.need is None or h.need.rank >= need.rank]
    return (sum_amounts(h.amount for h in below) + ask).within(share(need, pool(total)))


def sum_amounts(amounts: Iterable[Amount]) -> Amount:
    total = Amount(0, 0)
    for amount in amounts:
        total = total + amount
    return total


def effective_need(waiter: Waiter, now: float) -> Need:
    """The need that orders `waiter`: `soon` for an `idle` waiter that has waited
    `PROMOTE_SECONDS`."""
    if waiter.need is Need.IDLE and now - waiter.arrived >= PROMOTE_SECONDS:
        return Need.SOON
    return waiter.need


def queues(waiters: Iterable[Waiter], now: float) -> Dict[Lane, List[Waiter]]:
    """The waiters of each lane in the order they start."""
    out: Dict[Lane, List[Waiter]] = {Lane.SHORT: [], Lane.LONG: []}
    for w in sorted(waiters, key=lambda w: (effective_need(w, now).rank, w.arrived, w.id)):
        out[lane_of(w.minutes)].append(w)
    return out


def fits(held: List[Holding], waiter: Waiter, long_head: Optional[Waiter], total: Amount) -> bool:
    """Whether `waiter` fits beside `held`, where `long_head` is the head of the long queue."""
    claim = Amount(0, 0)
    if waiter.lane is Lane.SHORT and long_head is not None:
        claim = head_claim(held, long_head, total)
    return admissible(held, waiter.lane, waiter.need, waiter.ask, total, claim)


def next_waiters(waiters: Iterable[Waiter], holdings: List[Holding], total: Amount, now: float) -> List[Waiter]:
    """The waiters to start now, in order: the first of each queue while it fits, the long
    queue first."""
    started: List[Waiter] = []
    held = list(holdings)
    waiting = queues(waiters, now)
    for lane in (Lane.LONG, Lane.SHORT):
        queue = waiting[lane]
        while queue and fits(held, queue[0], waiting[Lane.LONG][0] if waiting[Lane.LONG] else None, total):
            w = queue.pop(0)
            held.append(Holding(lane, w.need, w.ask, now + w.minutes * 60))
            started.append(w)
    return started


def estimates(waiters: List[Waiter], holdings: List[Holding], total: Amount,
              now: float) -> Dict[int, Optional[float]]:
    """For each waiter, the wall-clock time at which it is expected to start: where the running
    jobs end at their declared ends and each waiter then runs its declared minutes. None where
    no end of a job frees enough."""
    held = list(holdings)
    waiting = queues(waiters, now)
    found: Dict[int, Optional[float]] = {}
    at = now
    while any(waiting.values()):
        for lane in (Lane.LONG, Lane.SHORT):
            queue = waiting[lane]
            while queue and fits(held, queue[0], waiting[Lane.LONG][0] if waiting[Lane.LONG] else None, total):
                w = queue.pop(0)
                found[w.id] = at
                held.append(Holding(lane, w.need, w.ask, at + w.minutes * 60))
        if not any(waiting.values()):
            break
        ending = [h for h in held if h.ends is not None]
        if not ending:
            break
        soonest = min(ending, key=lambda h: max(h.ends or 0.0, now + OVERDUE_SECONDS))
        at = max(at, soonest.ends or 0.0, now + OVERDUE_SECONDS)
        held.remove(soonest)
    for queue in waiting.values():
        for w in queue:
            found[w.id] = None
    return found
