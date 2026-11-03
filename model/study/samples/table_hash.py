"""Constants and helpers of the TableHash. The engine computes the TableHash (`tables['hash']` of the export by assignment): the hash of a table's
Type and its Set of Rows at one assignment. This module holds the cell widths, the check that Ident cells are values, and the hash of a table
that is counts-only at an assignment (the engine gives no hash for it).

  counts_hash(types, counts)   -> 'c2:<hex>'   its column types and its row counts
"""
import hashlib
import os
import sys
from collections import Counter

WIDE = {'Position': 4, 'Box': 4, 'Offset': 4}


def require_value_idents() -> None:
    """The hash is stable across sessions only where Ident cells are values."""
    if os.environ.get('ARCLOG_IDENT_SOURCE') != 'value':
        print('ARCLOG_IDENT_SOURCE must be "value"; the TableHash is not stable across sessions otherwise', file=sys.stderr)
        sys.exit(2)


def _h(*parts: bytes) -> bytes:
    m = hashlib.blake2b(digest_size=16)
    for p in parts:
        m.update(len(p).to_bytes(8, 'little'))
        m.update(p)
    return m.digest()


def spans(types: list[str]) -> list[tuple[int, int]]:
    out, at = [], 0
    for t in types:
        w = WIDE.get(t, 1)
        out.append((at, at + w))
        at += w
    return out


def counts_hash(types: list[str], counts: list[tuple[int, int]]) -> str:
    """The hash of a table at an assignment where the engine gives no rows: its column types and the row count of each Rows, as (example code,
    count). The assignment is not in it. It compares only as a measurement: two different tables can share it."""
    bag = sorted(Counter(counts).items())
    return 'c2:' + _h(b'counts', '|'.join(sorted(types)).encode(), repr(bag).encode()).hex()
