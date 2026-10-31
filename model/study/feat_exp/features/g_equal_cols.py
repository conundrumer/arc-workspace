"""G14 Two columns equal in a row.

Replaces `r6q.q1_diag_stratum` (`diag`, `diag_rows`), `r2a.a1_degenerate_cols.dups`, `r1.e6_equal_columns`,
`r1.e3_binary_relation.refl`, `r3d.d1_relation_laws.refl` and `r4l.l8_pair_relation.same_max`.
"""
import itertools

from featlib import feature


def _pairs(x):
    """Pairs of columns that hold one known type, other than Example, with one frame tag. A Position, Box or Offset
    value carries its frame tag, so two values of different frames are never equal."""
    cols = [c for c in x.columns() if c.type is not None and c.type != 'Example' and c.frame is not None]
    return [(a.index, b.index) for a, b in itertools.combinations(cols, 2)
            if a.type == b.type and a.frame == b.frame]


@feature
def g14_equal_cols(p):
    """G14 Two columns equal in a row: over the pairs of X columns of one type and one frame tag, `diag_rows` (the largest
    share of X's rows whose two values are equal) and `dups` (the pairs whose values are equal in every row). None
    without such a pair or below 2 rows.

    Needs: partial. Monotone: partly (`dups` yes: equality in every row stays; `diag_rows` no: a filter can remove the equal rows).
    """
    x = p.x
    pairs = _pairs(x)
    if not pairs:
        return None
    rows = [r for models in x.examples(tests=True).values() for model in models for r in model]
    if len(rows) < 2:
        return None
    best = 0.0
    dups = 0
    for a, b in pairs:
        hit = sum(1 for r in rows if r[a] == r[b])
        best = max(best, hit / len(rows))
        dups += hit == len(rows)
    return {'diag_rows': best, 'dups': dups}
