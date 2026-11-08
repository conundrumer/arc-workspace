"""Constants and helpers of the TableHash. The engine computes the TableHash (`tables['hash']` of the export by assignment): the hash of a table's
Type and its Set of Rows at one assignment. This module holds the cell widths and the check that Ident cells are values. A table for which the engine gives no hash has
no TableHash: no code makes one for it.
"""
import os
import sys

WIDE = {'Position': 4, 'Box': 4, 'Offset': 4}


def require_value_idents() -> None:
    """The hash is stable across sessions only where Ident cells are values."""
    if os.environ.get('ARCLOG_IDENT_SOURCE') != 'value':
        print('ARCLOG_IDENT_SOURCE must be "value"; the TableHash is not stable across sessions otherwise', file=sys.stderr)
        sys.exit(2)


def spans(types: list[str]) -> list[tuple[int, int]]:
    out, at = [], 0
    for t in types:
        w = WIDE.get(t, 1)
        out.append((at, at + w))
        at += w
    return out
