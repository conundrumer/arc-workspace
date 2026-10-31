"""Round 4, explorer L: what separates an X with extra rows from an X that lost rows.

L1: which Dir column orders a pair of Box or Position columns, and whether any does.
L2: where a Position cell lies in a Box column of its frame: on the edge, inside it, or outside it.
L3: whether a Position lies nearer the side that a Dir column names than the opposite side.
L4: how much of the source column's values X keeps, per column, for the columns that the form binds from an available table.
L5: whether the cells of a Position column with a sized frame lie on the cells the task changes and on the input's background.
L6: how strongly pairs of nominal columns of X depend on each other (adjusted normalized mutual information).
L8: which relation (same, adjacent, aligned, nested) two Position columns or two Box columns of one frame stand in, row by row.
"""
import collections as C
import itertools
import math

from featlib import feature, parse

GRID = ('Position', 'Box')


def _dir_value(cell):
    v = cell['value']
    return v[0] if len(v) == 1 and 0 <= v[0] <= 3 else None


def _same_frame_pairs(fields, kinds):
    """(i, j) for i < j, fields of one type from kinds with one non-empty frame tag."""
    groups = C.defaultdict(list)
    for i, f in enumerate(fields):
        if f['type'] in kinds and f.get('frame', ''):
            groups[f['type'], f['frame']].append(i)
    return [c for g in groups.values() for c in itertools.combinations(g, 2)]


# ---------------------------------------------------------------- L1

@feature
def l1_dir_orient(p):
    """L1: over pairs of Box (or Position) columns of one frame and every Dir column of X, the share of rows where the first column's margin at the Dir value is smaller (lt), larger (gt) or equal (eq); reports the Dir columns that give a strict one-sided order in every row (strict_cols), the best one-sided share (best) and the tie share of that column (tie). None without a pair or a Dir column."""
    x = p.x
    fields = x.fields
    pairs = _same_frame_pairs(fields, GRID)
    dirs = [k for k, f in enumerate(fields) if f['type'] == 'Dir']
    if not pairs or not dirs:
        return None
    n = C.Counter()
    lt = C.Counter()
    gt = C.Counter()
    for e in x.entries:
        for row in e['rows']:
            for i, j in pairs:
                a, b = row[i]['value'], row[j]['value']
                if len(a) != 4 or len(b) != 4:
                    continue
                for k in dirs:
                    d = _dir_value(row[k])
                    if d is None:
                        continue
                    n[i, j, k] += 1
                    lt[i, j, k] += a[d] < b[d]
                    gt[i, j, k] += a[d] > b[d]
    if not n:
        return None
    strict = 0
    best = (-1.0, 0.0)
    for key, total in n.items():
        s = max(lt[key], gt[key]) / total
        strict += s == 1.0
        tie = 1.0 - (lt[key] + gt[key]) / total
        if (s, -tie) > (best[0], -best[1]):
            best = (s, tie)
    return {'strict_cols': strict, 'best': best[0], 'tie': best[1]}


# ---------------------------------------------------------------- L2

@feature
def l2_cell_box(p):
    """L2: over pairs of a Position column and a Box column with the same non-empty frame tag, the share of rows whose cell lies inside the box (in), on its edge (edge: inside with a margin equal to the box's) or strictly inside it (inner); in_min is the smallest over the Position columns of the largest in over the boxes of that column's frame (every cell lies in some box; a cell is not expected inside the box of another object), edge_max and inner_max the largest, mix_max the largest 1 - max(edge, inner, outside). None without such a pair."""
    x = p.x
    fields = x.fields
    pos = [i for i, f in enumerate(fields) if f['type'] == 'Position' and f.get('frame', '')]
    box = [j for j, f in enumerate(fields) if f['type'] == 'Box' and f.get('frame', '')]
    pairs = [(i, j) for i in pos for j in box if fields[i]['frame'] == fields[j]['frame']]
    if not pairs:
        return None
    stats = []
    inside = C.defaultdict(float)
    for i, j in pairs:
        n = ins = edge = 0
        for e in x.entries:
            for row in e['rows']:
                a, b = row[i]['value'], row[j]['value']
                if len(a) != 4 or len(b) != 4:
                    continue
                n += 1
                if all(a[k] >= b[k] for k in range(4)):
                    ins += 1
                    edge += any(a[k] == b[k] for k in range(4))
        if n:
            stats.append((ins / n, edge / n, (ins - edge) / n))
            inside[i] = max(inside[i], ins / n)
    if not stats:
        return None
    return {'in_min': min(inside.values()), 'edge_max': max(s[1] for s in stats),
            'inner_max': max(s[2] for s in stats),
            'mix_max': max(1.0 - max(s[1], s[2], 1.0 - s[0]) for s in stats)}


# ---------------------------------------------------------------- L3

@feature
def l3_toward_side(p):
    """L3: over pairs of a Dir column and a Position column of X, the share of rows where the cell's margin at the Dir value is smaller than its margin at the opposite side (near), larger (far) or equal (tie); the pair with the most one-sided share. None without such a pair."""
    x = p.x
    fields = x.fields
    pos = [i for i, f in enumerate(fields) if f['type'] == 'Position']
    dirs = [k for k, f in enumerate(fields) if f['type'] == 'Dir']
    if not pos or not dirs:
        return None
    n = C.Counter()
    near = C.Counter()
    far = C.Counter()
    for e in x.entries:
        for row in e['rows']:
            for i in pos:
                a = row[i]['value']
                if len(a) != 4:
                    continue
                for k in dirs:
                    d = _dir_value(row[k])
                    if d is None:
                        continue
                    n[i, k] += 1
                    near[i, k] += a[d] < a[d ^ 1]
                    far[i, k] += a[d] > a[d ^ 1]
    if not n:
        return None
    key = max(n, key=lambda c: (max(near[c], far[c]) / n[c], near[c]))
    t = n[key]
    return {'near': near[key] / t, 'far': far[key] / t, 'tie': 1.0 - (near[key] + far[key]) / t}


# ---------------------------------------------------------------- L4

def _walk(tree):
    """Atoms of a parsed form outside OR and NOT."""
    if isinstance(tree, list):
        if tree and isinstance(tree[0], str) and tree[0] in ('OR', 'NOT'):
            return
        if tree and isinstance(tree[0], str) and not tree[0].startswith(':') and tree[0] not in ('OR', 'NOT'):
            yield tree
            return
        for t in tree:
            yield from _walk(t)


def _bound(atom, tfields):
    """[(table field index, variable name)] for the starred terms of an atom that reads a table with fields tfields."""
    out = []
    for s in atom[1:]:
        if not (isinstance(s, list) and s and isinstance(s[0], str) and s[0].startswith(':')):
            continue
        site, terms = s[0][1:], s[1:]
        sub = [n for n in tfields if n.startswith(site + '.')]
        plain = 0
        for t in terms:
            if isinstance(t, str):
                if not t.startswith('*'):
                    plain += 1
                    continue
                name = site if site in tfields else (sub[plain] if plain < len(sub) else None)
                plain += 1
                if name is not None:
                    out.append((tfields.index(name), t[1:]))
            elif isinstance(t, list) and t and isinstance(t[0], str) and t[0].startswith(':'):
                for q in t[1:]:
                    if isinstance(q, str) and q.startswith('*') and site + '.' + t[0][1:] in tfields:
                        out.append((tfields.index(site + '.' + t[0][1:]), q[1:]))
    return out


def _header_vars(p):
    """At an INIT input point: {X field name: variable} from the header of the port that holds the form; else {}."""
    if not p.kind.startswith('INIT'):
        return {}
    lines = [l for l in (p.dir / 'mutant.arclog').read_text().splitlines() if l.strip()]
    if p.point[0] >= len(lines):
        return {}
    tree = parse(lines[p.point[0]])
    t = tree[0] if tree and isinstance(tree[0], list) else None
    if not t or t[0] != 'INIT' or len(t) < 4:
        return {}
    body = parse(p.form)
    body = body[0] if body and isinstance(body[0], list) else []
    wanted = [repr(a) for a in _walk(body)]
    best = None
    stack = list(t[3:])
    while stack:
        port = stack.pop()
        if not isinstance(port, list):
            continue
        stack.extend(q for q in port[1:] if isinstance(q, list))
        if len(port) < 2 or not isinstance(port[1], list) or not port[1]:
            continue
        head = port[1][0]
        if not isinstance(head, list) or not head or not str(head[0]).startswith(':'):
            continue
        names = [repr(a) for a in _walk(port[2:])]
        score = (len(set(names) & set(wanted)), -abs(len(names) - len(wanted)))
        if best is None or score > best[0]:
            best = (score, port)
    if best is None:
        return {}
    out = {}
    for head in best[1][1]:
        if isinstance(head, list) and len(head) == 2 and isinstance(head[1], str):
            out[head[0][1:]] = head[1]
    return out


def _first_models(table):
    out = {}
    for e in table.entries:
        out.setdefault((e['assignment'], e['train']), e['rows'])
    return out


# Not a feature: it reads ports at and after the point from mutant.arclog; G8 (g_keeps_source) replaces it.
def l4_source_coverage(p):
    """L4: for each column of X that the form binds at a starred site of an available table's column (INIT port columns through the port header), the share of that table column's distinct values, per context and summed over contexts, that X's column holds; Ident columns by count only (min of 1 and the ratio of distinct counts), other types by value. min and mean over columns; lost is the number of columns below 1; ident_min is the smallest over Ident columns. None if no column qualifies. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so its rows would be compared with one example's rows of an earlier table."""
    if p.kind == 'Det':
        return None
    x = p.x
    xnames = x.names()
    xtypes = x.types()
    header = _header_vars(p)
    avail = {t.name: t for t in p.available()}
    xctx = _first_models(x)
    var_of = {n: header.get(n, n) for n in xnames}
    cover = {}
    for atom in _walk(parse(p.form)):
        t = avail.get(atom[0])
        if t is None or 'Example' in t.types():
            continue
        tmodels = _first_models(t)
        ttypes = t.types()
        for ti, v in _bound(atom, t.names()):
            cols = [c for c, n in enumerate(xnames) if var_of[n] == v]
            if not cols or ttypes[ti] != xtypes[cols[0]] or ttypes[ti] in ('Example', 'Axis'):
                continue
            c = cols[0]
            ident = xtypes[c] == 'Ident'
            inter = total = 0
            for key, trows in tmodels.items():
                if key not in xctx:
                    continue
                sv = {tuple(r[ti]['value']) for r in trows}
                if not sv:
                    continue
                xv = {tuple(r[c]['value']) for r in xctx[key]}
                inter += min(len(sv), len(xv)) if ident else len(sv & xv)
                total += len(sv)
            if total and c not in cover:
                cover[c] = (inter / total, ident)
    if not cover:
        return None
    vals = [v for v, _ in cover.values()]
    ids = [v for v, ident in cover.values() if ident]
    out = {'min': min(vals), 'mean': sum(vals) / len(vals), 'lost': sum(v < 1.0 for v in vals)}
    if ids:
        out['ident_min'] = min(ids)
    return out


# ---------------------------------------------------------------- L5

def _train_list(p):
    tr = p.train
    return tr['train'] if isinstance(tr, dict) and 'train' in tr else tr


@feature
def l5_sized_cells(p):
    """L5: for each Position column whose frame tag is empty or names a relation site and whose cells all have a resolved extent equal to the size of that example's train input and output (entries where the two grids have the size only) and lie on a cell of that frame (no negative margin), the share of distinct cells on the input's most common color (bg), the share of distinct cells where the output differs from the input (chg_prec) and the share of the changed cells that the column holds (chg_cov); the column with the largest chg_cov. None without such a column. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if p.kind == 'Det':
        return None
    x = p.x
    train = _train_list(p)
    best = None
    for pi, f in enumerate(x.fields):
        if f['type'] != 'Position' or f.get('frame', '') in ('input', 'output'):
            continue
        cells = bg = chg = need = hit = 0
        ok = seen = True
        for e in x.entries:
            if e['train'] >= len(train):
                continue
            gin, gout = train[e['train']]['input'], train[e['train']]['output']
            h, w = len(gin), len(gin[0])
            if (len(gout), len(gout[0])) != (h, w):
                continue
            todo = {(r, c) for r in range(h) for c in range(w) if gout[r][c] != gin[r][c]}
            counts = C.Counter(v for row in gin for v in row)
            ground = counts.most_common(1)[0][0]
            held = set()
            for row in e['rows']:
                cell = row[pi]
                if cell.get('extent_status') != 'resolved' or tuple(cell.get('extent') or ()) != (h, w):
                    ok = False
                    break
                t, b, l, r = cell['value']
                if min(cell['value']) < 0 or t + b != h - 1 or l + r != w - 1:
                    ok = False
                    break
                held.add((t, l))
            if not ok:
                break
            seen = True
            cells += len(held)
            bg += sum(gin[r][c] == ground for r, c in held)
            chg += len(held & todo)
            need += len(todo)
            hit += len(held & todo)
        if not ok or not cells or not need:
            continue
        cand = (hit / need, chg / cells, bg / cells)
        if best is None or cand[:2] > best[:2]:
            best = cand
    if best is None:
        return None
    return {'chg_cov': best[0], 'chg_prec': best[1], 'bg': best[2]}


# ---------------------------------------------------------------- L6

NOMINAL_SKIP = ('Position', 'Box', 'Example', 'Offset')


def _entropy(counts):
    n = sum(counts.values())
    return -sum(v / n * math.log(v / n) for v in counts.values() if v)


@feature
def l6_association(p):
    """L6: for pairs of X columns whose type is not Position, Box, Offset or Example, the adjusted normalized mutual information (mutual information minus its expectation under independence, over the smaller entropy; clipped to 0..1) of the two columns inside each entry with at least 6 rows and at most 12 distinct values per column, averaged over entries weighted by rows. mean and min over the pairs; low is the number of pairs below 0.05; dir_mean is the mean over pairs of two Dir or DiagDir columns. None without a pair."""
    x = p.x
    fields = x.fields
    cols = [i for i, f in enumerate(fields) if f['type'] not in NOMINAL_SKIP]
    if len(cols) < 2:
        return None
    acc = C.defaultdict(lambda: [0, 0.0])
    for e in x.entries:
        rows = e['rows']
        n = len(rows)
        if n < 6:
            continue
        keys = {c: [tuple(r[c]['value']) for r in rows] for c in cols}
        marg = {c: C.Counter(keys[c]) for c in cols}
        for a, b in itertools.combinations(cols, 2):
            ca, cb = marg[a], marg[b]
            if not (2 <= len(ca) <= 12 and 2 <= len(cb) <= 12):
                continue
            joint = C.Counter(zip(keys[a], keys[b]))
            ha, hb = _entropy(ca), _entropy(cb)
            mi = ha + hb - _entropy(joint) - (len(ca) - 1) * (len(cb) - 1) / (2 * n)
            v = min(1.0, max(0.0, mi / min(ha, hb)))
            acc[a, b][0] += n
            acc[a, b][1] += n * v
    if not acc:
        return None
    vals = {k: s / w for k, (w, s) in acc.items()}
    out = {'mean': sum(vals.values()) / len(vals), 'min': min(vals.values()),
           'low': sum(v < 0.05 for v in vals.values())}
    dd = [v for (a, b), v in vals.items() if fields[a]['type'] in ('Dir', 'DiagDir') and fields[b]['type'] in ('Dir', 'DiagDir')]
    if dd:
        out['dir_mean'] = sum(dd) / len(dd)
    return out


# ---------------------------------------------------------------- L8

def _pos_relation(a, b):
    dt, dl = abs(a[0] - b[0]), abs(a[2] - b[2])
    if dt == 0 and dl == 0:
        return 'same'
    if dt <= 1 and dl <= 1:
        return 'adj'
    if dt == 0:
        return 'row'
    if dl == 0:
        return 'col'
    return 'diag' if dt == dl else 'other'


def _box_relation(a, b):
    if a == b:
        return 'same'
    if all(x <= y for x, y in zip(a, b)) or all(x >= y for x, y in zip(a, b)):
        return 'nest'
    return 'other'


@feature
def l8_pair_relation(p):
    """L8: for each pair of Position columns, or of Box columns, with one non-empty frame tag, the class of each row's relation (Position: same cell, adjacent within one cell, same row, same column, diagonal, other; Box: equal, nested, other). mix_max and mix_mean are 1 minus the largest class share, largest and mean over the pairs; same_max and adj_max are the largest share of identical and of adjacent pairs; pure is the number of pairs with one class. None without a pair."""
    x = p.x
    fields = x.fields
    pairs = _same_frame_pairs(fields, GRID)
    if not pairs:
        return None
    mixes, same, adj, pure = [], [], [], 0
    for i, j in pairs:
        classify = _pos_relation if fields[i]['type'] == 'Position' else _box_relation
        counts = C.Counter()
        for e in x.entries:
            for row in e['rows']:
                a, b = row[i]['value'], row[j]['value']
                if len(a) == 4 and len(b) == 4:
                    counts[classify(a, b)] += 1
        n = sum(counts.values())
        if not n:
            continue
        mixes.append(1.0 - max(counts.values()) / n)
        same.append(counts['same'] / n)
        adj.append(counts['adj'] / n)
        pure += len(counts) == 1
    if not mixes:
        return None
    return {'mix_max': max(mixes), 'mix_mean': sum(mixes) / len(mixes), 'same_max': max(same),
            'adj_max': max(adj), 'pure': pure}
