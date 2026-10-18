"""A script's `--help` printed in parts: the bare `--help` prints the
script's usage with one line per part, and `--help PART` prints that part,
so that each print meets the thirty-line rule of
[Prose in code](src/controlled_markdown/writing.md#prose-in-code)."""

from collections.abc import Callable, Mapping
from enum import StrEnum

from transcript_snapshots import print_refused

from controlled_markdown import mctx

PARTS_LEAD = mctx("- `--help PART` prints a part of the help:")
"""The line of the bare `--help` above its part lines."""

PART_LINE = mctx("- `--help {part}`: {purpose}")
"""The line of the bare `--help` that gives a part."""

REFUSED_PART = mctx("`--help` takes at most one PART, one of {parts}")


def print_help[P: StrEnum](rest: list[str], kind: type[P], usage: Callable[[str], str],
                           purposes: Mapping[P, str], text: Callable[[P], str]) -> int:
    """Print the help `rest`, the arguments after `--help`, asks for, or
    refuse `rest`. `usage` gives the bare help from the lines that list the
    parts of `kind`, each with its purpose of `purposes`, and `text` gives
    the text of a part."""
    if not rest:
        lines = [PARTS_LEAD, *("    " + PART_LINE.format(part=p, purpose=purposes[p])
                               for p in kind)]
        print(usage("\n".join(lines)).rstrip("\n"))
        return 0
    if len(rest) > 1 or rest[0] not in {p.value for p in kind}:
        print_refused(REFUSED_PART.format(parts=", ".join(f"`{p}`" for p in kind)))
        return 2
    print(text(kind(rest[0])).rstrip("\n"))
    return 0
