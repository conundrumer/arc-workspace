"""Round 2, explorer A: degenerate columns of the candidate table X."""
import itertools

from featlib import feature

SKIP = ('Ident', 'Example')


def _flat(p):
    """(types, frames, columns) over every row of every entry of X; columns[j] lists the values of field j
    (empty for Ident and Example fields, which no feature here reads)."""
    x = p.x
    types, frames = x.types(), x.frames()
    keep = [j for j, t in enumerate(types) if t not in SKIP]
    cols = [[] for _ in types]
    n = 0
    for e in x.all_entries:  # X's own rows: the test entries too
        for r in e['rows']:
            n += 1
            for j in keep:
                cols[j].append(tuple(r[j]['value']))
    return types, frames, cols, n


@feature
def a1_degenerate_cols(p):
    """A1: columns of X that carry no information, over all rows of all entries (None below 2 rows).

    dups: pairs of fields with the same type and frame tag (not Ident or Example) whose values are equal in every row.
    dups_varying: the dups whose column takes at least 2 distinct values.
    const_number: Number fields that take one value in every row.
    """
    types, frames, cols, n = _flat(p)
    if n < 2:
        return None
    dups = varying = 0
    for a, b in itertools.combinations(range(len(types)), 2):
        if types[a] == types[b] and frames[a] == frames[b] and types[a] not in SKIP and cols[a] == cols[b]:
            dups += 1
            varying += len(set(cols[a])) > 1
    const_number = sum(1 for j, t in enumerate(types) if t == 'Number' and len(set(cols[j])) == 1)
    return {'dups': dups, 'dups_varying': varying, 'const_number': const_number}
