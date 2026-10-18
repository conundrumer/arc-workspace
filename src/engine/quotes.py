"""The handbook words a piece of code rests on.

`quotes(document, heading, words)` decorates a function or a class, and
stands as `Annotated` metadata on a constant or a type alias. `document`
is a path relative to `docs/handbook/`, `heading` is the text of a heading
in it, and `words` stand under that heading as written, up to line
wrapping. `python -m controlled_markdown check` reads every `quotes(...)`
call in the code files as a literal and checks the words against the
document.

`guard(words)` decorates a hint or lint check that guards against a form no
handbook document names, in place of `quotes`; `words` say what it guards
against. The same check accepts it on a hint or lint alone.
"""

from dataclasses import dataclass

QUOTES_ATTRIBUTE = "__quotes__"
GUARD_ATTRIBUTE = "__guard__"


@dataclass(frozen=True)
class quotes:
    """Handbook words, quoted where the code that rests on them stands."""

    document: str
    heading: str
    words: str

    def __call__[T](self, target: T) -> T:
        """`target`, with these words added to the ones it rests on."""
        setattr(target, QUOTES_ATTRIBUTE, (self, *quoted(target)))
        return target


def quoted(target: object) -> tuple[quotes, ...]:
    """The words a decorated function or class rests on, in the order its
    decorators stand."""
    return getattr(target, QUOTES_ATTRIBUTE, ())


@dataclass(frozen=True)
class guard:
    """What a hint or lint check guards against, where no handbook passage
    names the form."""

    words: str

    def __call__[T](self, target: T) -> T:
        """`target`, marked with what it guards against."""
        setattr(target, GUARD_ATTRIBUTE, self)
        return target


def guarded(target: object) -> guard | None:
    """What a decorated check guards against; None where it has no
    `guard`."""
    got = getattr(target, GUARD_ATTRIBUTE, None)
    return got if isinstance(got, guard) else None
