"""Round 11, explorer I: where the columns of X come from, read from the finished clause's form."""
from featlib import feature

_LIBRARY = ('relation', 'macro')
_TABLE = ('table', 'clause', 'port', 'output', 'x')


def _origin(var):
    """'computed' where a library relation or macro makes the variable, 'table' where a read of a table does,
    'fact' where an input or example fact does, None where no site makes it."""
    kinds = {b.atom.kind for b in var.binders if b.atom is not None and not b.atom.negated}
    if kinds & set(_LIBRARY):
        return 'computed'
    if kinds & set(_TABLE):
        return 'table'
    if 'fact' in kinds:
        return 'fact'
    return None


@feature
def i2_column_origin(p):
    """I2: where X's columns come from. Over the X columns that are not of type Example: `computed` (a library relation
    or macro makes the column's variable), `table` (a read of an earlier table makes it), `fact` (an input or example
    fact makes it), `share_computed`, and `copy_all` (1 when no column is computed). None without a column.

    Needs: form. Monotone: no.
    """
    cols = [v for v in p.clause.x_columns.values() if v is not None and v.resolved_type != 'Example']
    if not cols:
        return None
    n = {'computed': 0, 'table': 0, 'fact': 0}
    for v in cols:
        o = _origin(v)
        if o:
            n[o] += 1
    return {'computed': n['computed'], 'table': n['table'], 'fact': n['fact'],
            'share_computed': n['computed'] / len(cols), 'copy_all': float(n['computed'] == 0)}
