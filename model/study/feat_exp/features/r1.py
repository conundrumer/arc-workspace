"""Round 1 table features (ledger E2, E3, E5, E6, E7, E8): the candidate table X, the train grids and X's frame metadata."""
import collections as C
import itertools

from featlib import feature

GRID_TYPES = ('Position', 'Box')


def _resolved(cell):
    return cell.get('extent_status') == 'resolved' and cell.get('extent')


def _out_of_frame(cell, kind):
    """True if a Position or Box cell with a resolved extent falls outside it."""
    v = cell['value']
    if len(v) != 4:
        return False
    h, w = cell['extent']
    t, b, l, r = v
    out = min(v) < 0 or t + b > h - 1 or l + r > w - 1
    if kind == 'Position':
        out = out or t + b != h - 1 or l + r != w - 1
    return out


@feature
def e2_off_frame_rows(p):
    """E2: rows of X with a Position or Box cell outside its resolved extent (count and share of all rows)."""
    x = p.x
    idx = [(i, f['type']) for i, f in enumerate(x.fields) if f['type'] in GRID_TYPES]
    if not idx:
        return None
    total = bad = 0
    seen = False
    for e in x.entries:
        for row in e['rows']:
            total += 1
            flag = False
            for i, kind in idx:
                if _resolved(row[i]):
                    seen = True
                    flag = flag or _out_of_frame(row[i], kind)
            bad += flag
    if not seen:
        return None
    return {'rows': bad, 'share': bad / total}


def _role_order(p, a, b):
    """Whether X's column a comes before column b by the role its name gives it: at an INIT input point, the order
    of the two columns in the component's port; elsewhere the columns are labels, and there is none (None)."""
    clause = p.clause
    if not p.kind.startswith('INIT') or clause.port is None or not clause.component:
        return None
    comp = p.lib.component(clause.component)
    cols = [c for c, _, _ in (comp['inputs'].get(clause.port, []) if comp else [])]
    ca, cb = a.column, b.column
    if ca in cols and cb in cols and ca != cb:
        return cols.index(ca) < cols.index(cb)
    return None


@feature
def e3_binary_relation(p):
    """E3: over pairs of Box or Position columns with the same type and a named frame, per context and key: reflexive and symmetric shares, density against n(n-1)/2, and the share of rows oriented by a single Dir key column (a row (a, b) is oriented where a's margin at the Dir value is below b's; the pair's columns are taken in the order of their port roles, and in the order that orients more rows where they have no role). A key with fewer than 3 elements is left out of the reflexive, symmetric, density and strict total keys: with 2 elements a relation is trivially dense and total."""
    x = p.x
    cols = x.columns()
    groups = C.defaultdict(list)
    for c in cols:
        if c.type in GRID_TYPES and c.frame:
            groups[c.type, c.frame].append(c)
    pairs = [c for g in groups.values() for c in itertools.combinations(g, 2)]
    if not pairs:
        return None
    triples = refl = sym = ordered = max_pairs = 0
    orient_n = orient_ok = 0
    for ca, cb in pairs:
        i, j = ca.index, cb.index
        role = _role_order(p, ca, cb)
        key = [c.index for c in cols if c.index not in (i, j) and c.type not in GRID_TYPES]
        dirs = [c.index for c in cols if c.index in key and c.type == 'Dir']
        n_pair = ok_ab = ok_ba = 0
        for e in x.entries:
            seen = set()
            elements = C.defaultdict(set)
            for row in e['rows']:
                k = tuple(tuple(row[c]['value']) for c in key)
                a, b = tuple(row[i]['value']), tuple(row[j]['value'])
                if (k, a, b) in seen:
                    continue
                seen.add((k, a, b))
                elements[k].add(a)
                elements[k].add(b)
                if len(dirs) == 1 and len(a) == 4 and len(b) == 4:
                    d = row[dirs[0]]['value']
                    if len(d) == 1 and 0 <= d[0] <= 3:
                        n_pair += 1
                        ok_ab += a[d[0]] < b[d[0]]
                        ok_ba += b[d[0]] < a[d[0]]
            big = {k for k, el in elements.items() if len(el) >= 3}
            counted = [t for t in seen if t[0] in big]
            triples += len(counted)
            for k, a, b in counted:
                if a == b:
                    refl += 1
                else:
                    ordered += 1
                    sym += (k, b, a) in seen
            max_pairs += sum(len(elements[k]) * (len(elements[k]) - 1) // 2 for k in big)
        orient_n += n_pair
        orient_ok += ok_ab if role is True else ok_ba if role is False else max(ok_ab, ok_ba)
    out = {'refl': refl / triples if triples else 0.0, 'sym': sym / triples if triples else 0.0}
    if max_pairs:
        out['density'] = ordered / max_pairs
    if orient_n:
        out['oriented'] = orient_ok / orient_n
    if triples and max_pairs:
        strict = refl == 0 and sym == 0 and ordered == max_pairs
        out['strict_total'] = float(strict)
        if orient_n:
            out['strict_total_oriented'] = float(strict and orient_ok == orient_n)
    return out


@feature
def e5_free_columns(p):
    """E5: number (and share) of X columns that are independent of the others in every context with two rows and two values of that column."""
    x = p.x
    n = len(x.fields)
    if n < 2:
        return None
    free = [True] * n
    seen = [False] * n
    for e in x.entries:
        rows = {tuple(tuple(c['value']) for c in row) for row in e['rows']}
        if len(rows) < 2:
            continue
        for c in range(n):
            if not free[c]:
                continue
            dom = {r[c] for r in rows}
            if len(dom) < 2:
                continue
            rest = {r[:c] + r[c + 1:] for r in rows}
            seen[c] = True
            if len(rows) != len(dom) * len(rest):
                free[c] = False
    count = sum(1 for c in range(n) if free[c] and seen[c])
    return {'cols': count, 'share': count / n}


@feature
def e6_equal_columns(p):
    """E6: rows of X where two Position, Box or Dir columns with the same type and frame tag hold the same value (count and share of rows)."""
    x = p.x
    groups = C.defaultdict(list)
    for i, f in enumerate(x.fields):
        if f['type'] in ('Position', 'Box', 'Dir'):
            groups[f['type'], f.get('frame', '')].append(i)
    pairs = [c for g in groups.values() for c in itertools.combinations(g, 2)]
    if not pairs:
        return None
    total = hits = 0
    for e in x.entries:
        for row in e['rows']:
            total += 1
            hits += sum(row[i]['value'] == row[j]['value'] for i, j in pairs)
    return {'cells': hits, 'share': hits / total if total else 0.0}


@feature
def e7_frame_metadata(p):
    """E7: counts of Position and Box fields by frame tag kind (empty, input, output, relation site), the share of their cells with an unresolved extent (overall and for each kind), and the share of input and output cells whose extent is the train grid's size. `size_match` is left out at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a cell's extent would be compared with another example's grid."""
    x = p.x
    kinds = {}
    for i, f in enumerate(x.fields):
        if f['type'] in GRID_TYPES:
            tag = f.get('frame', '')
            kinds[i] = 'empty' if not tag else tag if tag in ('input', 'output') else 'site'
    if not kinds:
        return None
    out = {'fields_' + k: sum(v == k for v in kinds.values()) for k in ('empty', 'input', 'output', 'site')}
    train = p.train
    cells = unres = 0
    by_kind = C.defaultdict(lambda: [0, 0])
    size_n = size_ok = 0
    for e in x.entries:
        grid = train[e['train']] if e['train'] < len(train) else None
        dims = {}
        if grid and p.kind != 'Det':
            dims = {'input': (len(grid['input']), len(grid['input'][0])),
                    'output': (len(grid['output']), len(grid['output'][0]))}
        for row in e['rows']:
            for i, k in kinds.items():
                cells += 1
                by_kind[k][0] += 1
                cell = row[i]
                if not _resolved(cell):
                    unres += 1
                    by_kind[k][1] += 1
                    continue
                ext = tuple(cell['extent'])
                if k in dims:
                    size_n += 1
                    size_ok += ext == dims[k]
    out['unresolved'] = unres / cells if cells else 0.0
    for k, (n, u) in by_kind.items():
        out['unresolved_' + k] = u / n
    if size_n:
        out['size_match'] = size_ok / size_n
    return out


@feature
def e8_paint_against_output(p):
    """E8: where X has a Position column tagged output and a Color column, precision of X rows against the train output and coverage of the output grid's cells (over the pairs of such a Position and a Color column, the best by coverage, then precision; a row belongs to the example its Example value names). None at a Det point, where X is a task-level table whose rows belong to no one example."""
    if p.kind == 'Det':
        return None
    x = p.x
    cols = x.columns()
    pos = [c.index for c in cols if c.type == 'Position' and c.frame == 'output']
    col = [c.index for c in cols if c.type == 'Color']
    if not pos or not col:
        return None
    examples = {e.index: e for e in p.examples()}
    rows_of = x.examples(decoded=False)
    best = None
    for pi in pos:
        for ci in col:
            rows = right = cells = painted = 0
            for (_, ex), models in rows_of.items():
                e = examples.get(ex)
                if e is None:
                    continue
                grid = e.output.cells
                h, w = e.output.size
                cells += h * w
                hit = set()
                for model in models:
                    for row in model:
                        rows += 1
                        v = row[pi]
                        if len(v) != 4:
                            continue
                        t, b, l, r = v
                        if min(t, b, l, r) < 0 or t + b != h - 1 or l + r != w - 1:
                            continue
                        if grid[t][l] == row[ci][0]:
                            right += 1
                            hit.add((t, l))
                painted += len(hit)
            if not cells:
                continue
            cand = (painted / cells, right / rows if rows else 0.0)
            if best is None or cand > best:
                best = cand
    if best is None:
        return None
    return {'coverage': best[0], 'precision': best[1]}
