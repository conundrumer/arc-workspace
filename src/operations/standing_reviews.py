"""The standing doc reviews.

A standing doc review is a doc reviewer on one reader's whole context at
the head of `master`. The one that launches after a merge is on the
first of the readers of `State.readers` that no standing doc review of
the session runs on that no tag records, or, where each of those has
one, on the one whose tag points at the oldest commit.

A standing doc review launches at any step where none runs and a change
merged since `occasions.opened` of the standing doc reviews: where the head of
`master` is not the commit the last one's brief gives. `master` only
fast-forwards, so another head means a change merged after that launch,
whichever session merged it, and a last brief that gives no commit counts
as one that gives another commit. Where none was launched, it launches
where a commit of `master` has a time after the session's start.

A standing doc review also launches at any step on an overdue reader: one
that no tag records, or whose tag points at a commit older than
`STANDING_SPAN` that a later commit of `master` follows, where no
standing doc review of the session on that reader runs or launched at
the head of `master`, as the commit its brief gives shows. Each step
launches the first overdue reader of `State.readers`, so the overdue
readers launch in turn, with no wait on each other's runs."""

from collections.abc import Mapping
from dataclasses import dataclass

from controlled_markdown import mctx
from operations import briefs
from operations.completion import decided, occupies
from operations.main_session import main_only
from operations.occasions import opened
from operations.state import Agent, Reader, State
from operations.steps import Launch, Step, Undecided
from operations.unbatched import STANDING


STANDING_SPAN = 86400
"""The age, in seconds, of the commit a reader's standing doc review tag
points at, past which the reader is overdue where a later commit of
`master` follows that commit."""


@main_only
def standing_review(state: State) -> Step | None:
    """The launch of a standing doc review, where one is due."""
    past = [a for a in STANDING.agents(state) if occupies(a)]
    if opened(state, past) is None:
        return None
    if not past:
        due = any(c.time > state.started for c in state.git.commits)
    else:
        last = past[-1]
        tags = state.git.doc_reviews
        tagged = (tags is not None and tags.get(last.subject, float("-inf"))
                  >= state.git.commits[0].time)
        due = not at_head(state, last) or (not tagged and not decided(last))
    return doc_review(state) if due else None


def at_head(state: State, review: Agent) -> bool:
    """Whether the standing doc review `review` launched at the head of
    `master`."""
    return briefs.standing_commit(review.brief) == state.git.commits[0].hash


@main_only
def overdue_review(state: State) -> Step | None:
    """The launch of a standing doc review on an overdue reader, where one
    is due."""
    free = free_readers(state)
    if not isinstance(free, Free):
        return free
    reviewed = {a.subject for a in STANDING.agents(state) if (a.pending or decided(a)) and at_head(state, a)}

    def overdue(r: Reader) -> bool:
        t = free.times.get(r.tag)
        return t is None or (t < state.now - STANDING_SPAN and any(c.time > t for c in state.git.commits))

    reader = next((r for r in free.readers if r.tag not in reviewed and overdue(r)), None)
    return None if reader is None else standing_launch(state, reader)


UNREAD_TAGS = mctx("a `doc-review/<reader>` tag does not read as a commit")


@dataclass(frozen=True)
class Free:
    """The readers, in the order of `State.readers`, that no standing doc
    review of the session runs on, and the time of the commit each
    reader's `doc-review/<reader>` tag points at, by tag."""
    readers: list[Reader]
    times: Mapping[str, float]


def free_readers(state: State) -> Free | Undecided | None:
    """The readers a standing doc review may launch on, or None where no
    reader is listed."""
    readers = state.readers.value
    if not readers:
        return None
    times = state.git.doc_reviews
    if times is None:
        return Undecided(UNREAD_TAGS)
    running = {a.subject for a in STANDING.agents(state) if a.pending}
    return Free([r for r in readers if r.tag not in running], times)


def doc_review(state: State) -> Step | None:
    """The launch of a standing doc review, on the reader it is due on."""
    free = free_readers(state)
    if free is None:
        return Undecided(mctx("no reader is listed for a standing doc review"))
    if not isinstance(free, Free):
        return free
    if not free.readers:
        return None
    times = free.times
    unreviewed = [r for r in free.readers if r.tag not in times]
    return standing_launch(state, unreviewed[0] if unreviewed else min(free.readers, key=lambda r: times[r.tag]))


def standing_launch(state: State, reader: Reader) -> Launch:
    """The launch of a standing doc review on `reader`, at the head of
    `master`."""
    return Launch(STANDING.role, reader.tag,
                  briefs.standing_doc_review(" ".join((reader.name, *reader.args)), reader.tag,
                                             state.git.commits[0].hash, state.me),
                  occasion=state.git.commits[0].hash)
