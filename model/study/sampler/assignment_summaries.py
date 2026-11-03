"""AssignmentSummary and assignment_summaries: the summary of a step_tables result (ct), one AssignmentSummary per table at an assignment. No rows cross here: the TableHash, the
example keys and the TableVector are the engine's. The rows of a table are read through table_adapter.py alone.

ct.tables has one row per table at an assignment. The columns that name the QueryHash are read through QUERY and HAS_QUERY, so that a rename of
the wheel's columns is one line here.
"""
import dataclasses

import numpy as np

type QueryHash = int  # u128
type Name = str
type Table = tuple[QueryHash, Name] | str  # a query's table; a base table by its own name
type Assignment = tuple[tuple[QueryHash, int], ...]  # (DET QueryHash, value hash), sorted by QueryHash; empty when the table depends on no DET

QUERY = 'query', 'definition', 'function'  # the wheel's column of the QueryHash, the first that the wheel has
HAS_QUERY = 'has_query', 'has_definition', 'has_function'
SLOT = 'slot', 'relation'  # the vocabulary slot of the table; negative for a body table
SLOT_NAME = 'slot '  # how the wheel names a DET in an assignment while it gives no QueryHash there
FMT = {'uint8': 'B', 'int32': 'i', 'uint32': 'I', 'int64': 'q', 'uint64': 'Q'}


@dataclasses.dataclass(frozen=True, slots=True)
class AssignmentSummary:
    table: Table | None  # None for a body table, whose query is not finished
    at: Assignment
    slot: int  # -1 for a body table
    types: tuple[str, ...]
    labels: tuple[str, ...]
    hash: int | None  # the TableHash
    examples: tuple[tuple[int, int, int, int, int], ...]  # (kind, index, distinct, rows, hash)
    features: np.ndarray  # float32, the TableVector, a copy
    unhashed: str = ''  # why hash is None (the engine's unhashed_reason); empty where it has one
    capped: bool = False  # the engine's walk of the table stopped at its cap of 256 values (the `capped` column of ct.tables); one value for every assignment of the table


def accessor(names, T):
    """The first of names that the table columns T have."""
    for n in names:
        if n in T:
            return n
    raise KeyError(names[0])


def ints(ct, part, key):
    """The column part.key of ct as a sequence of numbers (or the list the wheel gives)."""
    v = getattr(ct, part)[key]
    if isinstance(v, (bytes, bytearray, memoryview)) or hasattr(v, '__buffer__'):
        return memoryview(v).cast('B').cast(FMT[ct.dtypes[part + '.' + key]])
    return v


def wide(ct, part, key, n=16):
    """The column part.key of ct, n bytes a row, as a list of ints (little-endian)."""
    b = bytes(memoryview(getattr(ct, part)[key]))
    return [int.from_bytes(b[i:i + n], 'little') for i in range(0, len(b), n)]


def slot_of(name):
    """The number in a DET name of the wheel ('slot 7'), or None."""
    return int(name[len(SLOT_NAME):]) if isinstance(name, str) and name.startswith(SLOT_NAME) else None


def assignment_summaries(ct, slots=None) -> list[AssignmentSummary]:
    """One AssignmentSummary per (table, assignment) of a step_tables result, in its order. slots: slot -> QueryHash of the DETs of the program so far, for a wheel
    that names a DET of an assignment by its slot; the DETs of ct itself are added. A DET that no slot names takes the number -1 - slot."""
    T = ct.tables
    n = len(T['form'])
    if not n:
        return []
    dcol, hcol, scol = accessor(QUERY, T), accessor(HAS_QUERY, T), accessor(SLOT, T)
    query, has, slot = wide(ct, 'tables', dcol), ints(ct, 'tables', hcol), ints(ct, 'tables', scol)
    hashes, hashed = wide(ct, 'tables', 'hash'), ints(ct, 'tables', 'hashed')
    names = list(T['name'])
    vec = np.frombuffer(T['features'], np.float32).reshape(n, -1)
    reasons = list(T['unhashed_reason']) if 'unhashed_reason' in T else []
    capped = ints(ct, 'tables', 'capped') if 'capped' in T else ()
    known = dict(slots or {})
    for i in range(n):
        if has[i] and not names[i] and slot[i] >= 0:
            known[int(slot[i])] = query[i]
    at, ek = [[] for _ in range(n)], [[] for _ in range(n)]
    A = ct.assignments
    if len(A['det']):
        values, rows = wide(ct, 'assignments', 'value'), ints(ct, 'assignments', 'table')
        for r, d, v in zip(rows, A['det'], values):
            if isinstance(d, (bytes, bytearray, memoryview)):
                d = int.from_bytes(bytes(d), 'little')
            elif slot_of(d) is not None:
                d = known.get(slot_of(d), -1 - slot_of(d))
            at[r].append((d, v))
    E = ct.example_keys
    if len(E['table']):
        cols = [ints(ct, 'example_keys', k) for k in ('table', 'kind', 'index', 'distinct', 'rows', 'hash')]
        for t, k, i, d, r, h in zip(*cols):
            ek[t].append((int(k), int(i), int(d), int(r), int(h)))
    out = []
    for i in range(n):
        if has[i]:
            table = query[i], names[i]
        else:
            table = names[i] or None
        out.append(AssignmentSummary(table, tuple(sorted(at[i])), int(slot[i]), tuple(str(t) for t in T['column_types'][i]), tuple(T['column_labels'][i]),
                            hashes[i] if hashed[i] else None, tuple(ek[i]), vec[i].copy(), reasons[i] if i < len(reasons) else '',
                            bool(capped[i]) if i < len(capped) else False))
    return out
