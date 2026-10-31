"""Round 11, explorer o: form-only features."""
from featlib import feature, ORIENTATION_TYPES


@feature
def o2_domain_only(p):
    """O2: 1 when every column of X has the type of a fixed enumeration (a direction, an axis, a symmetry or a sense) or
    is an Example column, so that X lists library values and no value of the train grids; else 0. None where the
    clause has no X column."""
    cols = getattr(p.clause, 'x_columns', None)
    if not cols:
        return None
    types = [v.resolved_type for v in cols.values()]
    return float(all(t in ORIENTATION_TYPES or t == 'Example' for t in types))
