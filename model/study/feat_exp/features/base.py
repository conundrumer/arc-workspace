"""Size of the candidate table X (ledger K2)."""
from featlib import feature


def _counts(p):
    return [len(m) for ms in p.x.contexts(tests=True).values() for m in ms]  # X's own entries, test inputs too


@feature
def x_rows(p):
    """Mean row count of X over its entries."""
    n = _counts(p)
    return sum(n) / len(n) if n else None


@feature
def x_empty_share(p):
    """Share of X's entries with no rows."""
    n = _counts(p)
    return sum(k == 0 for k in n) / len(n) if n else None
