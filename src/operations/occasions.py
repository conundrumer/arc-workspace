"""The rules that the procedures of After a batch (`batches`) and of the
launches no batch holds (`unbatched`) share: the time from which the
next launch of a kind counts what stands (`opened`), whether a change
merged since a time (`merged`, `merged_since`), and the number of the
next launch of a kind (`next_number`)."""

from operations.directives import Directive, numbers
from operations.state import Agent, Merge, State


def merged(state: State, since: float) -> bool:
    return (any(c.time > since and c.merge is Merge.MERGED for c in state.transcripts.calls)
            or any(t > since for _, t in numbers(state, Directive.MERGED)))


def next_number(past: list[Agent]) -> str:
    """The subject of the next launch of the kind whose launches are
    `past`: its number, counted from 1."""
    return str(len(past) + 1)


def opened(state: State, past: list[Agent]) -> float | None:
    """The time from which the next launch of the kind whose launches are
    `past`, those the session's operators made, counts what stands: the
    launch of the last of `past`, or the session's start where `past` is
    empty. None where the last of `past` runs."""
    if past and past[-1].pending:
        return None
    return past[-1].launched if past else state.started


def merged_since(state: State, past: list[Agent]) -> float | None:
    since = opened(state, past)
    return since if since is not None and merged(state, since) else None
