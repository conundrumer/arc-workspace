"""Round 9, explorer X: how well X's rows line up with the connected components of the train inputs.

Structures of a train input, computed from its cells alone. With bg the smallest of the grid's most common colors:

- cc8: 8-connected components of the cells off bg (any colors together).
- col8, col4: 8- or 4-connected components of the cells of one color, bg left out.
- cls: the cells of one color off bg (a color class).
- clsall: the cells of each color, bg included.

A group of X is the set of cells that one Position column (frame tag `input`, extent equal to the input) holds in the rows
that share one value of an Ident column. Each context reads the first model of X.
"""
import collections as C
import functools

from featlib import feature

DEFS = ('cc8', 'col8', 'col4', 'cls', 'clsall')
N8 = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0)]
N4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def _split(cells, nbrs):
    """Connected components of a set of cells, each a frozenset."""
    cells = set(cells)
    seen = set()
    out = []
    for s in sorted(cells):
        if s in seen:
            continue
        seen.add(s)
        stack, comp = [s], []
        while stack:
            r, c = stack.pop()
            comp.append((r, c))
            for dr, dc in nbrs:
                n = (r + dr, c + dc)
                if n in cells and n not in seen:
                    seen.add(n)
                    stack.append(n)
        out.append(frozenset(comp))
    return out


@functools.lru_cache(maxsize=256)
def _structures(cells):
    """{definition: [frozenset of cells]} for a grid given as a tuple of rows."""
    h, w = len(cells), len(cells[0]) if cells else 0
    count = C.Counter(v for row in cells for v in row)
    top = max(count.values())
    bg = min(k for k, v in count.items() if v == top)
    by = C.defaultdict(set)
    for r in range(h):
        for c in range(w):
            by[cells[r][c]].add((r, c))
    fg = set().union(*[s for k, s in by.items() if k != bg]) if len(by) > 1 else set()
    out = {'cc8': _split(fg, N8), 'col8': [], 'col4': [], 'cls': [], 'clsall': []}
    for k, s in sorted(by.items()):
        out['clsall'].append(frozenset(s))
        if k == bg:
            continue
        out['cls'].append(frozenset(s))
        out['col8'] += _split(s, N8)
        out['col4'] += _split(s, N4)
    return out


def _first(x):
    """{(assignment, example): rows of the first model}; a context the table has with no row is empty."""
    ex = x.examples()
    if any(c.type == 'Example' for c in x.columns()):
        return {k: m[0] for k, m in ex.items() if m}
    keys = {(e['assignment'], e['train']) for e in x.entries}
    return {k: (ex[k][0] if ex.get(k) else []) for k in keys}


def _groups(rows, key, col, size):
    """{value of the key column: set of (top, left) cells of the Position column on a grid of that size}."""
    out = C.defaultdict(set)
    for r in rows:
        m = r[col]
        if getattr(m, 'size', None) == size and m.in_frame():
            out[r[key]].add(m.cell)
    return {k: v for k, v in out.items() if v}


def _score(groups, structs):
    """(exact cover, exact precision, soft recall, soft precision) of the groups against the structures."""
    gs = [frozenset(g) for g in groups.values()]
    gset = set(gs)
    sset = set(structs)
    cov = sum(s in gset for s in structs) / len(structs)
    prec = sum(g in sset for g in gs) / len(gs)
    where = C.defaultdict(list)
    for i, s in enumerate(structs):
        for c in s:
            where[c].append(i)
    rec = pre = 0.0
    inter = [C.Counter() for _ in gs]
    for gi, g in enumerate(gs):
        for c in g:
            for i in where.get(c, ()):
                inter[gi][i] += 1
    best_s = [0.0] * len(structs)
    for gi, g in enumerate(gs):
        if inter[gi]:
            pre += max(inter[gi].values()) / len(g)
        for i, n in inter[gi].items():
            best_s[i] = max(best_s[i], n / len(structs[i]))
    return cov, prec, sum(best_s) / len(structs), pre / len(gs)


def _pairs(x):
    keys = [c.index for c in x.columns() if c.type == 'Ident']
    cols = [c.index for c in x.columns() if c.type == 'Position' and c.frame_kind == 'input']
    return keys, cols


@feature
def x1_component_lineup(p):
    """X1: how the Ident groups of X line up with the connected components of the train inputs.

    For each Ident column K and each input-frame Position column P, a group is the cells of P in the rows with one value
    of K. Per structure definition d (cc8, col8, col4: 8- or 4-connected components of the cells off the most common color,
    all colors together or one color at a time; cls, clsall: the cells of one color, without or with the most common
    color) and per context with at least 2 structures: `cov_d` is the share of structures that one group equals, `prec_d`
    the share of groups that one structure equals, `rec_d` and `pre_d` the same with the best overlap share in place of
    equality. Contexts weigh alike. The (K, P) pair with the largest sum of cov and prec is read for each d. `cov`,
    `prec`, `rec`, `pre` are the largest over d. None without an Ident column, an input-frame Position column, or a
    context whose input has 2 structures.
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.
    """
    if p.kind == 'Det':
        return None
    x = p.x
    keys, cols = _pairs(x)
    if not keys or not cols:
        return None
    exs = p.examples()
    ctx = _first(x)
    out = {}
    for d in DEFS:
        best = None
        for k in keys:
            for c in cols:
                tot = [0.0] * 4
                n = 0
                for (_, ei), rows in ctx.items():
                    if not 0 <= ei < len(exs):
                        continue
                    grid = exs[ei].input
                    structs = _structures(grid.cells)[d]
                    if len(structs) < 2:
                        continue
                    groups = _groups(rows, k, c, grid.size)
                    s = _score(groups, structs) if groups else (0.0, 0.0, 0.0, 0.0)
                    tot = [a + b for a, b in zip(tot, s)]
                    n += 1
                if n:
                    cand = [v / n for v in tot]
                    if best is None or cand[0] + cand[1] > best[0] + best[1]:
                        best = cand
        if best is not None:
            for name, v in zip(('cov', 'prec', 'rec', 'pre'), best):
                out[f'{name}_{d}'] = v
    if not out:
        return None
    for name in ('cov', 'prec', 'rec', 'pre'):
        vals = [v for k, v in out.items() if k.startswith(name + '_')]
        out[name] = max(vals)
    return out


def _within(groups, structs):
    """The share of groups whose cells all lie in one structure."""
    owner = {}
    for i, s in enumerate(structs):
        for c in s:
            owner.setdefault(c, set()).add(i)
    n = 0
    for g in groups.values():
        common = None
        for c in g:
            common = owner.get(c, set()) if common is None else common & owner.get(c, set())
            if not common:
                break
        n += bool(common)
    return n / len(groups)


@feature
def x2_group_within(p):
    """X2: whether the Ident groups of X lie inside single connected components of the train inputs.

    As in X1, a group is the cells of an input-frame Position column in the rows with one value of an Ident column. Per
    structure definition d (cc8, col8, col4, cls, clsall; see the module docstring) and per context with at least 2
    structures and a group: `within_d` is the share of groups whose cells all lie in one structure (a cell off every
    structure, such as a cell of the most common color for cc8, puts a group outside). Over the (K, P) pairs, the
    largest value of each d (`within_d`) and the mean (`mean_d`). `within` and `mean` are the largest over d. A context
    where X has no group counts 0. None without an Ident column, an input-frame Position column, or a context whose
    input has 2 structures.
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.
    """
    if p.kind == 'Det':
        return None
    x = p.x
    keys, cols = _pairs(x)
    if not keys or not cols:
        return None
    exs = p.examples()
    ctx = _first(x)
    out = {}
    for d in DEFS:
        vals = []
        for k in keys:
            for c in cols:
                tot = n = 0
                for (_, ei), rows in ctx.items():
                    if not 0 <= ei < len(exs):
                        continue
                    grid = exs[ei].input
                    structs = _structures(grid.cells)[d]
                    if len(structs) < 2:
                        continue
                    groups = _groups(rows, k, c, grid.size)
                    tot += _within(groups, structs) if groups else 0.0
                    n += 1
                if n:
                    vals.append(tot / n)
        if vals:
            out[f'within_{d}'] = max(vals)
            out[f'mean_{d}'] = sum(vals) / len(vals)
    if not out:
        return None
    for name in ('within', 'mean'):
        out[name] = max(v for k, v in out.items() if k.startswith(name + '_'))
    return out


def _bbox(cells):
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return (min(rs), max(rs), min(cs), max(cs))


@feature
def x3_box_lineup(p):
    """X3: how the input-frame Box values of X line up with the bounding boxes of the connected components.

    For each Box column with frame tag input, per context and per structure definition d (cc8, col8, col4, cls; see the
    module docstring) with at least 2 structures: `bcov_d` is the share of the structures whose bounding box is a value of
    the column, `bprec_d` the share of the column's distinct values that are the bounding box of a structure. The column
    with the largest sum is read. `bcov` and `bprec` are the largest over d. None without such a column or a context whose
    input has 2 structures.
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.
    """
    if p.kind == 'Det':
        return None
    x = p.x
    cols = [c.index for c in x.columns() if c.type == 'Box' and c.frame_kind == 'input']
    if not cols:
        return None
    exs = p.examples()
    ctx = _first(x)
    out = {}
    for d in ('cc8', 'col8', 'col4', 'cls'):
        best = None
        for c in cols:
            tc = tp = 0.0
            n = 0
            for (_, ei), rows in ctx.items():
                if not 0 <= ei < len(exs):
                    continue
                grid = exs[ei].input
                structs = _structures(grid.cells)[d]
                if len(structs) < 2:
                    continue
                h, w = grid.size
                boxes = set()
                for r in rows:
                    m = r[c]
                    if getattr(m, 'size', None) == grid.size and m.in_frame():
                        boxes.add((m.top, h - 1 - m.bottom, m.left, w - 1 - m.right))
                want = {_bbox(s) for s in structs}
                tc += sum(_bbox(s) in boxes for s in structs) / len(structs)
                tp += (sum(b in want for b in boxes) / len(boxes)) if boxes else 0.0
                n += 1
            if n:
                cand = (tc / n, tp / n)
                if best is None or sum(cand) > sum(best):
                    best = cand
        if best is not None:
            out[f'bcov_{d}'], out[f'bprec_{d}'] = best
    if not out:
        return None
    for name in ('bcov', 'bprec'):
        out[name] = max(v for k, v in out.items() if k.startswith(name + '_'))
    return out


def _changed_structures(ex):
    """{definition: [frozenset]} of the changed cells of a same-size example: chg8, chg4 (8- or 4-connected components of
    the cells where the output differs from the input) and chgcol (8-connected components per output color)."""
    chg = ex.changed()
    out = {'chg8': _split(chg, N8), 'chg4': _split(chg, N4), 'chgcol': []}
    by = C.defaultdict(set)
    for r, c in chg:
        by[ex.output[r, c]].add((r, c))
    for k, s in sorted(by.items()):
        out['chgcol'] += _split(s, N8)
    return out


def _full_score(groups, structs):
    """(cov, prec, rec, pre, within) of the groups against the structures."""
    return _score(groups, structs) + (_within(groups, structs),)


def _read(p, frame_kind, source, defs, min_structs):
    """Per definition, the five scores of the best (Ident column, Position column of that frame) pair, averaged over
    the contexts where the source gives at least min_structs structures; {} when no context applies."""
    x = p.x
    keys = [c.index for c in x.columns() if c.type == 'Ident']
    cols = [c.index for c in x.columns() if c.type == 'Position' and c.frame_kind == frame_kind]
    if not keys or not cols:
        return {}
    exs = p.examples()
    ctx = _first(x)
    out = {}
    for d in defs:
        best = None
        for k in keys:
            for c in cols:
                tot = [0.0] * 5
                n = 0
                for (_, ei), rows in ctx.items():
                    if not 0 <= ei < len(exs):
                        continue
                    got = source(exs[ei])
                    if got is None:
                        continue
                    size, structs = got[0], got[1].get(d, [])
                    if len(structs) < min_structs:
                        continue
                    groups = _groups(rows, k, c, size)
                    s = _full_score(groups, structs) if groups else (0.0,) * 5
                    tot = [a + b for a, b in zip(tot, s)]
                    n += 1
                if n:
                    cand = [v / n for v in tot]
                    if best is None or sum(cand) > sum(best):
                        best = cand
        if best is not None:
            for name, v in zip(('cov', 'prec', 'rec', 'pre', 'within'), best):
                out[f'{name}_{d}'] = v
    return out


def _with_best(out):
    for name in ('cov', 'prec', 'rec', 'pre', 'within'):
        vals = [v for k, v in out.items() if k.startswith(name + '_')]
        if vals:
            out[name] = max(vals)
    return out or None


@feature
def x4_changed_components(p):
    """X4: how the Ident groups of X line up with the connected regions of changed cells.

    On examples whose input and output have one size and that differ: structures chg8 and chg4 (8- or 4-connected regions
    of the cells where the output differs from the input) and chgcol (8-connected regions of changed cells of one output
    color). A group is the cells of an input-frame Position column in the rows with one value of an Ident column. Per
    definition d: `cov_d`, `prec_d`, `rec_d`, `pre_d`, `within_d` as in X1 and X2 for the (K, P) pair with the largest sum,
    on contexts with at least 2 regions; the largest over d under the bare names. None without such a column or context.
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.
    """
    if p.kind == 'Det':
        return None
    def source(e):
        if not e.same_size or not e.changed():
            return None
        return e.input.size, _changed_structures(e)

    return _with_best(_read(p, 'input', source, ('chg8', 'chg4', 'chgcol'), 2))


@feature
def x5_component_split(p):
    """X5: whether the cells of an input-frame Position column of X keep the connected components of the train inputs whole.

    For each Position column with frame tag input and the input's extent, per context and per definition d (cc8, col8,
    col4, cls; see the module docstring) with at least 2 structures: `full_d` is the share of structures that the column
    holds in full, `split_d` the share that it holds in part (a cell, not all), and `split_of_hit_d` the split share among the
    structures it holds a cell of. The column with the smallest `split_of_hit` is read (ties: the largest `full`);
    contexts weigh alike. `split`, `full` and `split_of_hit` are the largest, largest and smallest over d. None without
    such a column or a context whose input has 2 structures.
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.
    """
    if p.kind == 'Det':
        return None
    x = p.x
    cols = [c.index for c in x.columns() if c.type == 'Position' and c.frame_kind == 'input']
    if not cols:
        return None
    exs = p.examples()
    ctx = _first(x)
    out = {}
    for d in ('cc8', 'col8', 'col4', 'cls'):
        best = None
        for c in cols:
            tot = [0.0, 0.0, 0.0]
            n = nh = 0
            for (_, ei), rows in ctx.items():
                if not 0 <= ei < len(exs):
                    continue
                grid = exs[ei].input
                structs = _structures(grid.cells)[d]
                if len(structs) < 2:
                    continue
                cells = {r[c].cell for r in rows if getattr(r[c], 'size', None) == grid.size and r[c].in_frame()}
                full = sum(s <= cells for s in structs)
                part = sum(bool(s & cells) and not s <= cells for s in structs)
                tot[0] += full / len(structs)
                tot[1] += part / len(structs)
                if full + part:
                    tot[2] += part / (full + part)
                    nh += 1
                n += 1
            if n and nh:
                cand = (tot[0] / n, tot[1] / n, tot[2] / nh)
                if best is None or (cand[2], -cand[0]) < (best[2], -best[0]):
                    best = cand
        if best is not None:
            out[f'full_{d}'], out[f'split_{d}'], out[f'split_of_hit_{d}'] = best
    if not out:
        return None
    out['full'] = max(v for k, v in out.items() if k.startswith('full_'))
    out['split'] = max(v for k, v in out.items() if k.startswith('split_') and not k.startswith('split_of'))
    out['split_of_hit'] = min(v for k, v in out.items() if k.startswith('split_of_hit_'))
    return out


@feature
def x6_ident_count(p):
    """X6: whether X has one Ident value per connected component of the train inputs.

    Per context (first model of X, rows of every Ident column) and per structure definition d (cc8, col8, col4, cls; see
    the module docstring) with at least 2 structures: for each Ident column K, the count n of its distinct values and the
    count m of structures. `eq_d` is 1 when some K has n = m in every such context (else 0), `gap_d` the smallest, over K,
    of the mean over contexts of |ln(n / m)| (a context where X has no value of K counts n = 0.5). `eq` and `gap` are the
    largest and the smallest over d. None without an Ident column or a context whose input has 2 structures.
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.
    """
    if p.kind == 'Det':
        return None
    import math
    x = p.x
    keys = [c.index for c in x.columns() if c.type == 'Ident']
    if not keys:
        return None
    exs = p.examples()
    ctx = _first(x)
    out = {}
    for d in ('cc8', 'col8', 'col4', 'cls'):
        eq = 0
        gaps = []
        for k in keys:
            same = True
            tot = 0.0
            n = 0
            for (_, ei), rows in ctx.items():
                if not 0 <= ei < len(exs):
                    continue
                m = len(_structures(exs[ei].input.cells)[d])
                if m < 2:
                    continue
                cnt = len({r[k] for r in rows})
                same &= cnt == m
                tot += abs(math.log((cnt or 0.5) / m))
                n += 1
            if n:
                eq |= same
                gaps.append(tot / n)
        if gaps:
            out[f'eq_{d}'] = float(eq)
            out[f'gap_{d}'] = min(gaps)
    if not out:
        return None
    out['eq'] = max(v for k, v in out.items() if k.startswith('eq_'))
    out['gap'] = min(v for k, v in out.items() if k.startswith('gap_'))
    return out


@feature
def x7_box_owner(p):
    """X7: whether a row's input-frame Position lies in the connected component whose bounding box its input-frame Box is.

    For each pair of an input-frame Box column B and an input-frame Position column P (two columns), per context and per
    definition d (cc8, col8, cls; see the module docstring) with at least 2 structures: over the distinct (B, P) pairs of
    the rows, `own_d` is the share where B is the bounding box of a structure that holds the cell of P, `boxed_d` the share
    where B is the bounding box of some structure. The pair with the largest `own_d` is read. `own` and `boxed` are the
    largest over d. None without such a pair or a context whose input has 2 structures.
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.
    """
    if p.kind == 'Det':
        return None
    x = p.x
    bcols = [c.index for c in x.columns() if c.type == 'Box' and c.frame_kind == 'input']
    pcols = [c.index for c in x.columns() if c.type == 'Position' and c.frame_kind == 'input']
    if not bcols or not pcols:
        return None
    exs = p.examples()
    ctx = _first(x)
    out = {}
    for d in ('cc8', 'col8', 'cls'):
        best = None
        for b in bcols:
            for c in pcols:
                own = boxed = 0.0
                n = 0
                for (_, ei), rows in ctx.items():
                    if not 0 <= ei < len(exs):
                        continue
                    grid = exs[ei].input
                    structs = _structures(grid.cells)[d]
                    if len(structs) < 2:
                        continue
                    h, w = grid.size
                    by_box = C.defaultdict(list)
                    for s in structs:
                        by_box[_bbox(s)].append(s)
                    pairs = set()
                    for r in rows:
                        mb, mp = r[b], r[c]
                        if getattr(mb, 'size', None) == grid.size and getattr(mp, 'size', None) == grid.size \
                                and mb.in_frame() and mp.in_frame():
                            pairs.add(((mb.top, h - 1 - mb.bottom, mb.left, w - 1 - mb.right), mp.cell))
                    if not pairs:
                        n += 1
                        continue
                    own += sum(any(cell in s for s in by_box.get(box, ())) for box, cell in pairs) / len(pairs)
                    boxed += sum(box in by_box for box, _ in pairs) / len(pairs)
                    n += 1
                if n:
                    cand = (own / n, boxed / n)
                    if best is None or cand > best:
                        best = cand
        if best is not None:
            out[f'own_{d}'], out[f'boxed_{d}'] = best
    if not out:
        return None
    out['own'] = max(v for k, v in out.items() if k.startswith('own_'))
    out['boxed'] = max(v for k, v in out.items() if k.startswith('boxed_'))
    return out
