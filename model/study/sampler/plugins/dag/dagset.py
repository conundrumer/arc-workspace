"""Facts of a body's atoms as a set, and the row that a feature sees, for rk4_def.py and ch4_def.py."""
import importlib.util
import os
import re

R = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'rk2')
MARK = re.compile(r'[*^]')
_view = [None, None]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


rk3o = load(f'{R}/features/rk3o.py', 'rk3o_dag')
rk3o._STAR = re.compile(r'[A-Za-z_]\w*')  # rk3o took a prefix's labels from its `*` sites. Each identifier that its _parse keeps at a site is a label, so a label is any name there


def view(row):
    """The row with `*` and `^` out of `prefix` and `text`. A walk's order places those marks, so no model reads them. The same row gives the same object, for the feature sets' caches."""
    if _view[0] is not row:
        out = dict(row)
        out['prefix'] = [MARK.sub('', a) for a in row.get('prefix') or []]
        if row.get('text'):
            out['text'] = MARK.sub('', row['text'])
        _view[0], _view[1] = row, out
    return _view[1]


def on_view(fn):
    return lambda row, o: fn(view(row), o)


def rel_labels(row):
    """[[name, type or None, atom, reads, atom]] of the prefix's labels, the format of rk1c._labels. The type comes from the atoms as a set (rk3o._types). reads is the label's sites less
    one. atom is the atom that holds a label of one site. A label of more sites has a number of its own below 0, so it shares an atom with no other label. The list is sorted by type and
    reads, so it does not depend on the prefix's order."""
    g = rk3o._graph(row)
    out = [[n, g.lt[n], next(iter(g.hold[n])) if g.cnt[n] == 1 else -1 - j, g.cnt[n] - 1] for j, n in enumerate(sorted(g.cnt))]
    out = [x + [x[2]] for x in out]
    return sorted(out, key=lambda x: (str(x[1]), x[3]))
