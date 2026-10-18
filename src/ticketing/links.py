"""The links that lead from a ticket, as Change tickets in
`prompts/agents/notes/tickets.md` defines a link."""

from collections.abc import Iterable


def link_targets[T](depends_on: Iterable[T], wait: T | None) -> list[T]:
    """The tickets a link leads to from a ticket whose `depends-on` gives
    `depends_on`, and which waits on the change `wait` under `waiting`,
    None where it stands elsewhere or waits on no change: each entry of
    `depends_on`, then `wait`."""
    return [*depends_on, *([wait] if wait is not None else [])]
