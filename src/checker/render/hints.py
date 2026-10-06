"""The directive lines a `derive` or `store` report tells the session to
add."""

from dataclasses import dataclass
from enum import StrEnum

from solver.annotations import (
    IgnoreForm,
    Slot,
    comment_text,
    derive_text,
    ignore_text,
    store_text,
)


class HintKind(StrEnum):
    """The line a `derive` or `store` report tells the session to add."""

    DERIVE = "derive"
    STORE = "store"
    IGNORE_DERIVE = "ignore derive"
    IGNORE_STORE = "ignore store"


@dataclass(frozen=True)
class Hint:
    """A directive line to add: its kind, the proposer of a `@derive`
    or `@ignore: derive <Proposer>` line, the relation a line on an instance names, and the site it goes
    above: the instance of an `.init`, or the block of a `RIGID` call;
    None for the relation's own `.decl`. `alone` says no `@derive` or
    `@store` line stands above it in the report, so it states the
    site."""

    kind: HintKind
    proposer: str | None = None
    relation: str | None = None
    site: str | None = None
    alone: bool = False


def derive_line_to_add(proposer: str) -> str:
    """The `@derive` line of `proposer` for the agent to add, its
    plausibility and verdict left as slots."""
    return comment_text(derive_text(proposer, Slot.PLAUSIBILITY,
                                    Slot.VERDICT))


def hint_line(h: Hint) -> str:
    """The line the session adds, as the `derive` and `store` reports
    print it ([Program](docs/handbook/solver-file.md#program))."""
    if h.kind == HintKind.DERIVE:
        add = "add:" if h.site is None \
            else f"add above `RIGID({h.site}, …)`:"
        assert h.proposer is not None
        return f"{add} " + derive_line_to_add(h.proposer)
    named = h.relation if h.site is not None else None
    add = "add:" if h.site is None else f"add above `.init {h.site}`:"
    if h.kind == HintKind.STORE:
        return f"{add} " + comment_text(store_text(
            named, Slot.PLAUSIBILITY, Slot.VERDICT))
    lead = f"{add} " if h.alone and h.site is not None else "or:  "
    if h.kind == HintKind.IGNORE_DERIVE:
        return lead + comment_text(ignore_text(
            named, IgnoreForm.DERIVE, Slot.REASON, h.proposer))
    return lead + comment_text(ignore_text(named, IgnoreForm.STORE,
                                           Slot.REASON))
