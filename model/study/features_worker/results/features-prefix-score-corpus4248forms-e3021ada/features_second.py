"""Second-order features: a prefix's table read against a table in scope.

  features(r, text, scope, pairs) -> {name: value or None}

The pair is the prefix's table and the table of the last relation atom (`&rN`) in `text`, read from `scope`; the changed cells of the train pairs score both. No gold, no label, no task name is read. A value is None where the feature does not apply (no relation atom, no Position column in both tables, a train pair of another size).
"""
import math
import re

GRID = ('Position', 'Box')
RELSLOT = re.compile(r'\(&r(\d+)\b')
CAP = 400  # rows per example read
FEATURES = {
    'pair.sc_n': 'Number of scope tables the atoms read.',
    'pair.sc_rows': 'Log2 of rows of the prefix table over rows of the scope table the last relation atom reads (mean over train inputs).',
    'pair.sc_p_in_s': 'Best share of a prefix column values found among the same-type column values of the last scope table read.',
    'pair.sc_s_in_p': 'Share of that scope table column values that the matched prefix column keeps.',
    'pair.sc_same': 'One when the matched prefix column and scope column hold the same set of values in every train input.',
    'pair.sc_cols_new': 'Share of the prefix table columns whose type does not occur in the last scope table read.',
    'pair.sc_rows_min': 'The smallest, over the scope tables the atoms read, of log2 rows of the prefix table over rows of that scope table.',
    'pair.sc_rows_max': 'The largest, over the scope tables the atoms read, of log2 rows of the prefix table over rows of that scope table.',
    'pair.sc_prec_d': 'Share of the matched prefix Position cells that are changed cells, minus that share for the matched scope table Position cells.',
    'pair.sc_rec_d': 'Share of changed cells the matched prefix Position cells cover, minus that share for the matched scope table Position cells.',
    'pair.sc_prec': 'Share of the matched scope table Position cells that are changed cells.',
}


def _widths(types):
    return [4 if t in GRID else 1 for t in types]


def _columns(rows, types):
    w = _widths(types)
    n = sum(w)
    out = []
    for r in rows:
        if len(r) != n:
            return None
        i = 0
        c = []
        for k in w:
            c.append(tuple(r[i:i + k]))
            i += k
        out.append(tuple(c))
    return out


def _mean(v):
    v = [x for x in v if x is not None]
    return sum(v) / len(v) if v else None


def _tab(r, pairs):
    """{example: rows as tuples of cells} for train inputs."""
    types = r.get('table_types') or r['types']
    out = {}
    for ent in r.get('x_rows') or []:
        (a, e), rows = ent[0], ent[1]
        if a != 1 or e >= len(pairs):
            continue
        c = _columns(rows[:CAP], types)
        if c is not None:
            out[e] = c
    return types, out


def _scope_cols(sc):
    """{example: rows as cells} for a scope entry, and its types."""
    types = sc['types']
    out = {}
    for ent in sc.get('x_rows') or []:
        (a, e), rows = ent[0], ent[1]
        if a == 2:
            continue
        c = _columns(rows[:CAP], types)
        if c is not None:
            out[e if a == 1 else 'g'] = c
    return types, out


def features(r, text, scope, pairs):
    out = {k: None for k in FEATURES}
    try:
        types, tab = _tab(r, pairs)
        if tab:
            _scope(out, text, scope, pairs, types, tab)
    except Exception:  # noqa: BLE001
        pass
    return out


def _scope(out, text, scope, pairs, types, tab):
    slots = [int(m) for t in text for m in RELSLOT.findall(t)]
    out['pair.sc_n'] = len(set(slots))
    if not slots or not scope:
        return
    sc = scope.get(slots[-1])
    if sc is None:
        sc = scope.get(str(slots[-1]))
    if sc is None:
        return
    stypes, stab = _scope_cols(sc)
    if not stab:
        return
    ratios = _ratios(tab, stab)
    out['pair.sc_rows'] = _mean(ratios)
    allr = []
    for sl in set(slots):
        sc2 = scope.get(sl)
        if sc2 is not None:
            st2 = _scope_cols(sc2)[1]
            if st2:
                allr.append(_mean(_ratios(tab, st2)))
    allr = [x for x in allr if x is not None]
    if allr:
        out['pair.sc_rows_min'] = min(allr)
        out['pair.sc_rows_max'] = max(allr)
    _scope_delta(out, types, tab, stypes, stab, pairs)
    # best matched column pair of the same type, by share of the prefix values found in the scope column
    best = None
    for i, t in enumerate(types):
        for j, u in enumerate(stypes):
            if t != u:
                continue
            a_in = a_tot = s_in = s_tot = 0
            same = True
            for e, rows in tab.items():
                s = stab.get(e)
                if s is None:
                    s = stab.get('g')
                if s is None:
                    continue
                pv = {row[i] for row in rows}
                sv = {row[j] for row in s}
                a_in += len(pv & sv)
                a_tot += len(pv)
                s_in += len(pv & sv)
                s_tot += len(sv)
                same = same and pv == sv
            if a_tot and s_tot:
                key = (a_in / a_tot, s_in / s_tot)
                if best is None or key > best[0]:
                    best = (key, same)
    if best:
        out['pair.sc_p_in_s'], out['pair.sc_s_in_p'] = best[0]
        out['pair.sc_same'] = float(best[1])
    out['pair.sc_cols_new'] = sum(t not in stypes for t in types) / len(types)


def _ratios(tab, stab):
    res = []
    for e, rows in tab.items():
        s = stab.get(e)
        if s is None:
            s = stab.get('g')
        if s is not None:
            res.append(math.log2((len(rows) + 1) / (len(s) + 1)))
    return res


def _cells(rows, i):
    return {(row[i][0], row[i][2]) for row in rows}


def _scope_delta(out, types, tab, stypes, stab, pairs):
    """Precision and recall on changed cells of the matched prefix Position column against the matched scope one."""
    pp = [i for i, t in enumerate(types) if t == 'Position']
    sp = [j for j, t in enumerate(stypes) if t == 'Position']
    if not pp or not sp:
        return
    ex = [e for e in tab if (e in stab or 'g' in stab) and pairs[e].same and pairs[e].changed]
    if not ex:
        return
    best = None
    for i in pp:
        for j in sp:
            inter = union = 0
            for e in ex:
                a = _cells(tab[e], i)
                b = _cells(stab.get(e) or stab['g'], j)
                inter += len(a & b)
                union += len(a | b)
            if union and (best is None or inter / union > best[0]):
                best = (inter / union, i, j)
    if best is None:
        return
    _, i, j = best
    pd, rd, ps = [], [], []
    for e in ex:
        c = pairs[e].changed
        a = _cells(tab[e], i)
        b = _cells(stab.get(e) or stab['g'], j)
        if not a or not b:
            continue
        pa, pb = len(a & c) / len(a), len(b & c) / len(b)
        pd.append(pa - pb)
        rd.append((len(a & c) - len(b & c)) / len(c))
        ps.append(pb)
    out['pair.sc_prec_d'] = _mean(pd)
    out['pair.sc_rec_d'] = _mean(rd)
    out['pair.sc_prec'] = _mean(ps)

