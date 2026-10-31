"""Round 13, explorer A: Color columns of X against the colours of the train grids, and how X varies between examples.

A context is the first model of one (assignment, train input) entry of X. A table with an Example column holds the rows
of every example in each entry, so the colour features skip it. At a Det point X is the task-level body table, whose
entries hold the rows of all examples: every feature here is None there.
The background of an input is its most common colour (all colours tied for most common); its minority colour is the
least common one (only where the input has two or more colours).
"""
import itertools

from featlib import ORIENTATION_TYPES, feature

NUMBER_TYPES = ('Number', 'Nat', 'Int')


def _train_list(p):
    tr = p.train
    return tr['train'] if isinstance(tr, dict) and 'train' in tr else tr


def _usable(p):
    return p.kind != 'Det' and not any(f['type'] == 'Example' for f in p.x.fields)


def _contexts(p):
    """[(example index, rows)]: the first model of each (assignment, train) entry of X, rows as lists of cells."""
    seen = {}
    for e in p.x.entries:
        seen.setdefault((e['assignment'], e['train']), (e['train'], e['rows']))
    return list(seen.values())


def _grids(p):
    return {e['index']: e for e in _train_list(p)} if _train_list(p) and isinstance(_train_list(p)[0], dict) \
        and 'index' in _train_list(p)[0] else {i: e for i, e in enumerate(_train_list(p))}


def _roles(grid):
    """(background colours, minority colours) of a grid (list of rows); minority is empty with one colour."""
    count = {}
    for row in grid:
        for c in row:
            count[c] = count.get(c, 0) + 1
    if not count:
        return set(), set()
    hi, lo = max(count.values()), min(count.values())
    bg = {c for c, n in count.items() if n == hi}
    last = {c for c, n in count.items() if n == lo} if len(count) > 1 else set()
    return bg, last


@feature
def a1_color_ground(p):
    """A1: the colours of X's Color columns against the colours of the example's train input. Per Color column and
    context with rows, the share of rows on the input's background colour (`bg`) and on its minority colour (`last`),
    averaged over contexts. `bg_max`, `bg_min`: the largest and smallest `bg` over the Color columns. `bg_all`: 1 when
    every Color column is on the background in every row of every context, else 0. `last_max`: the largest `last`.
    None at a Det point, with an Example column, without a Color column, or without a context that has rows and a grid.

    Needs: partial. Monotone: no (a filter can remove the rows that are off the background).
    """
    try:
        if not _usable(p):
            return None
        cols = [i for i, f in enumerate(p.x.fields) if f['type'] == 'Color']
        if not cols:
            return None
        grids = _grids(p)
        bg_s = {i: [] for i in cols}
        last_s = {i: [] for i in cols}
        for t, rows in _contexts(p):
            g = grids.get(t)
            if g is None or not rows:
                continue
            bg, last = _roles(g['input'])
            for i in cols:
                v = [r[i]['value'][0] for r in rows if r[i].get('value')]
                if not v:
                    continue
                bg_s[i].append(sum(c in bg for c in v) / len(v))
                last_s[i].append(sum(c in last for c in v) / len(v))
        use = [i for i in cols if bg_s[i]]
        if not use:
            return None
        bg = [sum(bg_s[i]) / len(bg_s[i]) for i in use]
        last = [sum(last_s[i]) / len(last_s[i]) for i in use]
        full = all(min(bg_s[i]) >= 1.0 for i in use)
        return {'bg_max': max(bg), 'bg_min': min(bg), 'bg_all': float(full), 'last_max': max(last)}
    except Exception:
        return None


def _cell_in(cell, shape):
    """(top, left) of a Position cell whose resolved extent is `shape` (height, width) and that lies in it, else None."""
    v = cell.get('value') or []
    ext = cell.get('extent')
    if len(v) != 4 or cell.get('extent_status') != 'resolved' or not ext or tuple(ext) != shape:
        return None
    top, left = v[0], v[2]
    return (top, left) if 0 <= top < shape[0] and 0 <= left < shape[1] else None


@feature
def a2_cell_colour(p):
    """A2: the colour that X gives a cell against the colour the train grids have there. For each pair of a Position
    column with frame tag `input` (cells read in the train input) or `output` and a Color column, over rows whose cell
    lies in a grid of the cell's extent:
    `in_max`, `in_min`: the largest and smallest share, over pairs with an input-tag column, of rows whose colour is the
    input's colour at the cell (X re-reads the input). `in_exact`: 1 when every such pair is 1.
    `noop_max`, `noop_min`: the same share over pairs with an output-tag column, on examples whose input and output
    have one size (rows that paint a cell with the colour it already has).
    None at a Det point, with an Example column, or without such a pair.

    Needs: partial. Monotone: no.
    """
    try:
        if not _usable(p):
            return None
        fields = p.x.fields
        pos_in = [i for i, f in enumerate(fields) if f['type'] == 'Position' and f.get('frame') == 'input']
        pos_out = [i for i, f in enumerate(fields) if f['type'] == 'Position' and f.get('frame') == 'output']
        col = [i for i, f in enumerate(fields) if f['type'] == 'Color']
        if not col or not (pos_in or pos_out):
            return None
        grids = _grids(p)
        tot = {}
        for t, rows in _contexts(p):
            g = grids.get(t)
            if g is None or not rows:
                continue
            I, O = g['input'], g['output']
            same = len(I) == len(O) and len(I[0]) == len(O[0])
            for kind, pcols in (('in', pos_in), ('out', pos_out)):
                if kind == 'out' and not same:
                    continue
                shape = (len(I), len(I[0])) if kind == 'in' else (len(O), len(O[0]))
                for pi in pcols:
                    for ci in col:
                        acc = tot.setdefault((kind, pi, ci), [0, 0])
                        for r in rows:
                            xy = _cell_in(r[pi], shape)
                            if xy is None or not r[ci].get('value'):
                                continue
                            acc[0] += 1
                            acc[1] += I[xy[0]][xy[1]] == r[ci]['value'][0]
        out = {}
        ins = [a[1] / a[0] for (k, _, _), a in tot.items() if k == 'in' and a[0]]
        outs = [a[1] / a[0] for (k, _, _), a in tot.items() if k == 'out' and a[0]]
        if ins:
            out.update(in_max=max(ins), in_min=min(ins), in_exact=float(min(ins) >= 1.0))
        if outs:
            out.update(noop_max=max(outs), noop_min=min(outs))
        return out or None
    except Exception:
        return None


@feature
def a3_example_agreement(p):
    """A3: how much X differs between the train examples. Over the examples where X has rows, the distinct rows of an
    example (Example columns left out): `jac_mean`, `jac_min`: the mean and smallest Jaccard overlap of two examples'
    row sets; `identical`: 1 when all examples hold one row set. `col_jac_mean`, `col_jac_min`: the same overlap taken
    on the value set of each Color, Number or orientation column, averaged over columns. None at a Det point and with
    fewer than 2 examples that have rows.

    Needs: partial. Monotone: no.
    """
    try:
        if p.kind == 'Det':
            return None
        cols = p.x.columns()
        keep = [i for i, c in enumerate(cols) if c.type != 'Example']
        by = {}
        for (a, e), models in p.x.examples(decoded=False).items():
            if models and models[0]:
                by.setdefault(e, set()).update(tuple(r[i] for i in keep) for r in models[0])
        sets = [s for s in by.values() if s]
        if len(sets) < 2:
            return None

        def jac(a, b):
            return len(a & b) / len(a | b)

        pairs = [jac(a, b) for a, b in itertools.combinations(sets, 2)]
        out = {'jac_mean': sum(pairs) / len(pairs), 'jac_min': min(pairs), 'identical': float(all(s == sets[0] for s in sets))}
        cj = []
        for j, i in enumerate(keep):
            if cols[i].type == 'Color' or cols[i].type in NUMBER_TYPES or cols[i].type in ORIENTATION_TYPES:
                vs = [{r[j] for r in s} for s in sets]
                pr = [jac(a, b) for a, b in itertools.combinations(vs, 2)]
                cj.append(sum(pr) / len(pr))
        if cj:
            out['col_jac_mean'] = sum(cj) / len(cj)
            out['col_jac_min'] = min(cj)
        return out
    except Exception:
        return None
