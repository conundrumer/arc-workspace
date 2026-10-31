"""Round 9, explorer k: the color map that the train pairs show, against the color map that X realizes.

The train pairs have a color map where every example has the same size for input and output, some cell changes, and
the colors of the changed cells map by a function in each example (an input color goes to one output color). X
realizes a map through a pair (A, B) of a from-side and a Color column: A is a Color column of X, or the input color
under an input-frame Position column of X (the cell of that column read in the train input), and B is another
Color column. The pairs (a, b) of one context are the distinct (A, B) values of its rows.
"""
import collections as C

from featlib import feature


def _contexts(table):
    """{(assignment, example): rows of the first model, a row being a tuple of decoded cells}; a context the table
    has with no row is empty."""
    ex = table.examples()
    if any(c.type == 'Example' for c in table.columns()):
        return {k: m[0] for k, m in ex.items() if m}
    keys = {(e['assignment'], e['train']) for e in table.entries}
    return {k: (ex[k][0] if ex.get(k) else []) for k in keys}


def _cell(m, size):
    """The (top, left) cell of a Position on a grid of that size, or None."""
    if not hasattr(m, 'margins'):
        return None
    t, b, l, r = m.margins
    h, w = size
    return (t, l) if min(m.margins) >= 0 and t + b == h - 1 and l + r == w - 1 else None


def _train_map(p):
    """(T, D, G): per example index, T[k] = {input color: set of output colors at its cells}, D[k] = {input color:
    output color} over the changed cells, and G the one map of all examples where they agree, else None. None
    where an example has another size for its output, no example changes a cell, or an example's changed cells
    map one input color to two output colors."""
    T, D = {}, {}
    for ex in p.examples():
        if not ex.same_size:
            return None
        t, d = C.defaultdict(set), {}
        h, w = ex.input.size
        for r in range(h):
            for c in range(w):
                a, b = ex.input.cells[r][c], ex.output.cells[r][c]
                t[a].add(b)
                if a != b:
                    if d.setdefault(a, b) != b:
                        return None
        T[ex.index], D[ex.index] = dict(t), d
    if not any(D.values()):
        return None
    G = {}
    for d in D.values():
        for a, b in d.items():
            if G.setdefault(a, b) != b:
                G = None
                break
        if G is None:
            break
    return T, D, G


def _pairs(p, ctxs, cols_a, cols_b, exs):
    """{(source, column index): {context: set of (a, b)}} for each from-side source and each Color column b.
    A source is ('col', i) for a Color column or ('in', i) for an input-frame Position column."""
    out = {}
    for sa in cols_a:
        for cb in cols_b:
            if sa[0] == 'col' and sa[1] == cb:
                continue
            per = {}
            for key, rows in ctxs.items():
                k = key[1]
                if k >= len(exs):
                    continue
                s = set()
                for row in rows:
                    if sa[0] == 'col':
                        a = row[sa[1]]
                    else:
                        cell = _cell(row[sa[1]], exs[k].input.size)
                        if cell is None:
                            continue
                        a = exs[k].input.cells[cell[0]][cell[1]]
                    s.add((a, row[cb]))
                per[key] = s
            out[sa, cb] = per
    return out


def _sources(x):
    cols = x.columns()
    colors = [c.index for c in cols if c.type == 'Color']
    srcs = [('col', i) for i in colors]
    srcs += [('in', c.index) for c in cols if c.type == 'Position' and c.frame_kind == 'input']
    return srcs, colors


def _ctx_metrics(s, t, d):
    """Metrics of one context's pair set s against the example's maps t and d (None for an empty set)."""
    froms = {a for a, _ in s}
    m = {'cov': sum((a, b) in s for a, b in d.items()) / len(d),
         'absent': sum(a not in froms for a in d) / len(d),
         'silent': sum(a in froms and all(b == a for x, b in s if x == a) for a in d) / len(d)}
    if s:
        m['prec'] = sum(b in t.get(a, ()) for a, b in s) / len(s)
    return m


def _best(p):
    """(train maps, best pair key, its {context: pair set}), the best pair having the highest mean `cov`, then
    `prec`; None where the structure or a pair is absent."""
    tm = _train_map(p)
    if tm is None:
        return None
    T, D, G = tm
    srcs, colors = _sources(p.x)
    if not srcs or not colors:
        return None
    exs = p.examples()
    ctxs = {k: v for k, v in _contexts(p.x).items() if k[1] in D and D[k[1]]}
    if not ctxs:
        return None
    allp = _pairs(p, ctxs, srcs, colors, exs)
    best = None
    for key, per in allp.items():
        ms = [_ctx_metrics(s, T[k[1]], D[k[1]]) for k, s in per.items()]
        if not ms:
            continue
        cov = sum(m['cov'] for m in ms) / len(ms)
        ps = [m['prec'] for m in ms if 'prec' in m]
        prec = sum(ps) / len(ps) if ps else 0.0
        cand = (cov, prec, str(key))
        if best is None or cand > best[0]:
            best = (cand, key, per)
    if best is None:
        return None
    return (T, D, G), best[1], best[2]


@feature
def k1_map_agree(p):
    """K1 map agree: how well X's best (from-side, Color) pair realizes the example's color map.

    Where the train examples all keep their size, change some cell, and recolor each input color to one output color
    in each example: for the pair of a from-side source (a Color column, or the input color under an input-frame
    Position column) and another Color column with the highest `cov`, then `prec`, means over the examples that
    change a color:
    cov: the share of the example's recolored input colors a whose pair (a, new color) is in X's pairs.
    prec: the share of X's distinct pairs (a, b) that the example shows (b is an output color under some cell of
    input color a).
    absent: the share of recolored input colors that are not a from-value of any X pair.
    silent: the share of recolored input colors whose X pairs all keep the color (a, a).
    None where the structure is absent or X has no pair of columns.
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.
    """
    if p.kind == 'Det':
        return None
    r = _best(p)
    if r is None:
        return None
    (T, D, G), key, per = r
    ms = [_ctx_metrics(s, T[k[1]], D[k[1]]) for k, s in per.items()]
    out = {name: sum(m[name] for m in ms) / len(ms) for name in ('cov', 'absent', 'silent')}
    ps = [m['prec'] for m in ms if 'prec' in m]
    if ps:
        out['prec'] = sum(ps) / len(ps)
    return out


@feature
def k2_fixed_map(p):
    """K2 fixed map: whether X's pairs over all examples agree with the one color map of the train examples.

    Where the changed cells of all examples agree on one map G (input color to output color), for the pair chosen
    as in K1, with S the union of X's pairs over the examples:
    cov: the share of G's input colors a with (a, G[a]) in S.
    clean: the share of G's input colors a whose S pairs are all (a, a) or (a, G[a]).
    extra: the share of S's from-values outside G that S sends to another color.
    None where the examples disagree on a map, or as in K1.
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.
    """
    if p.kind == 'Det':
        return None
    r = _best(p)
    if r is None or r[0][2] is None:
        return None
    (T, D, G), key, per = r
    S = set().union(*per.values()) if per else set()
    froms = {a for a, _ in S}
    cov = sum((a, b) in S for a, b in G.items()) / len(G)
    seen = [a for a in G if a in froms]
    clean = sum(all(b in (a, G[a]) for x, b in S if x == a) for a in seen) / len(seen) if seen else 0.0
    out = [a for a in froms if a not in G]
    extra = sum(any(b != a for x, b in S if x == a) for a in out) / len(out) if out else 0.0
    return {'cov': cov, 'clean': clean, 'extra': extra}


def _hist_metrics(rows, col, ex):
    """(under, over) of one context: X's rows per color of the Color column against the example's target counts, the
    target being the output's cells per color, or on a same-size example the output colors of the changed cells,
    whichever has the total nearer to X's row count. Both are shares of the target total."""
    x = C.Counter(r[col] for r in rows)
    full = C.Counter(c for row in ex.output.cells for c in row)
    chg = ex.changed()
    tgts = [full]
    if chg:
        tgts.append(C.Counter(ex.output.cells[r][c] for r, c in chg))
    n = len(rows)
    t = min(tgts, key=lambda t: (abs(sum(t.values()) - n), -sum(t.values())))
    tot = sum(t.values())
    under = sum(max(0, t[c] - x.get(c, 0)) for c in t) / tot
    over = sum(max(0, v - t.get(c, 0)) for c, v in x.items()) / tot
    return under, over


@feature
def k3_color_counts(p):
    """K3 color counts: X's rows per color against the colors of the cells that the output must hold.

    For each column that admits Color, per example, the target is the output's cell count per color, or on a same-size example
    that changes cells the output colors of the changed cells, whichever total is nearer to X's row count in that
    example. For the Color column with the least under + over, means over the examples:
    under: the cells of the target that X has no row for with that color, as a share of the target total.
    over: X's rows beyond the target count of their color, as a share of the target total.
    exact: the share of examples where every color count equals the target's.
    None without a Color column.
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.
    """
    if p.kind == 'Det':
        return None
    cols = [c.index for c in p.x.columns() if 'Color' in c.types]
    if not cols:
        return None
    exs = p.examples()
    ctxs = {k: v for k, v in _contexts(p.x).items() if k[1] < len(exs)}
    if not ctxs:
        return None
    best = None
    for col in cols:
        ms = [_hist_metrics(rows, col, exs[k[1]]) for k, rows in ctxs.items()]
        u = sum(m[0] for m in ms) / len(ms)
        o = sum(m[1] for m in ms) / len(ms)
        ex = sum(m == (0.0, 0.0) for m in ms) / len(ms)
        if best is None or (u + o, col) < best[0]:
            best = ((u + o, col), {'under': u, 'over': o, 'exact': ex})
    return best[1]


@feature
def k4_color_domain(p):
    """K4 color domain: which recolored input colors X's cells reach.

    Where the train examples have a color map (see K1), for each Position column of X with frame tag input, per
    example that changes cells, with S the column's distinct cells on the input grid and, for each input color a
    that the example recolors, r_a the share of the changed cells of color a that S holds. For the column with the
    highest mean r_a (then the highest `dom`), means over the examples:
    rmin: the smallest r_a; rmean: the mean of the r_a; miss: the share of recolored colors with r_a = 0.
    dom: the share of S on cells whose input color the example recolors.
    None where there is no such column or no example.
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.
    """
    if p.kind == 'Det':
        return None
    tm = _train_map(p)
    if tm is None:
        return None
    T, D, G = tm
    poss = [c for c in p.x.columns() if c.type == 'Position' and c.frame_kind == 'input']
    if not poss:
        return None
    exs = p.examples()
    ctxs = {k: v for k, v in _contexts(p.x).items() if k[1] < len(exs) and D.get(k[1])}
    if not ctxs:
        return None
    best = None
    for pos in poss:
        acc = C.defaultdict(float)
        n = 0
        for (_, k), rows in ctxs.items():
            ex = exs[k]
            cells = {_cell(row[pos.index], ex.input.size) for row in rows} - {None}
            chg = ex.changed()
            r = []
            for a in D[k]:
                cs = {c for c in chg if ex.input[c] == a}
                r.append(len(cs & cells) / len(cs))
            n += 1
            acc['rmin'] += min(r)
            acc['rmean'] += sum(r) / len(r)
            acc['miss'] += sum(x == 0 for x in r) / len(r)
            acc['dom'] += sum(ex.input[c] in D[k] for c in cells) / len(cells) if cells else 0.0
        res = {name: v / n for name, v in acc.items()}
        cand = (res['rmean'], res['dom'], pos.index)
        if best is None or cand > best[0]:
            best = (cand, res)
    return best[1]
