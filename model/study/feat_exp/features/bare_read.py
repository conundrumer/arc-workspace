"""Atoms that read a relation with columns and name none of them: an existence test, which the converter writes
where the solver's read binds no label that the clause uses."""
from featlib import feature


def _ncols(atom):
    iface = atom.interface
    if iface is None:
        return None
    cols = getattr(iface, 'columns', None)
    if callable(cols):
        cols = cols()
    return len(cols) if cols is not None else None


@feature
def bare_read(p):
    """`n`: the atoms (NOT included, comparisons not) that read a relation with one column or more and give no
    argument; `share`: n over the atoms that read a relation. None without a body."""
    body = p.clause.body
    if body is None:
        return None
    reads = [a for a in body.atoms if not a.operator]
    n = sum(1 for a in reads if not a.arguments and (_ncols(a) or 0) > 0)
    return {'n': n, 'share': n / len(reads) if reads else 0.0}
