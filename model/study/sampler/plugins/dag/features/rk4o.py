"""rk4o: a6_* of rk1a on the unread labels of the prefix, read as a set of atoms. A label is open when it has one site. rk4o(row, option) -> {a6_<what>: float}."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dagset  # noqa: E402

G = dagset.rk3o


def rk4o(row, o):
    g = G._graph(row)
    open_t = {g.lt[n] for n in g.cnt if g.cnt[n] == 1 and g.lt[n]}
    types = [G._nt(t) for t in o.get('types') or []]
    d = {'a6_n_open': float(sum(c == 1 for c in g.cnt.values()))}
    if open_t:
        hit = sum(any(G._sub(u, t) or G._sub(t, u) for u in open_t) for t in types)
        d['a6_open_hit'] = float(hit)
        d['a6_open_frac'] = hit / len(types) if types else 0.0
    return d


FEATURE_FUNCS = {'rk4o': rk4o}
