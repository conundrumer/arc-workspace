"""Round 14, explorer A: the components of cells.dl (Connectivity, BoundingBox, Division, Ray, Boundary, Enclosure, Flood,
Occurrences, Outlines, Periods, Wallpaper in the sampler's library) and whether a candidate's use of an instance of one
fits the task.

An instance is an INIT clause before the point whose component is one of those. Its relations are `&<instance>.<relation>`.
Each statistic below is a property of one instance's output tables (read from the available tables, or from the
component's input tables where the output table was not exported), taken against the train inputs and outputs.
"""
import collections as C
import math

from featlib import feature

COMPONENTS = frozenset({'Connectivity', 'BoundingBox', 'Division', 'Ray', 'Boundary', 'Enclosure', 'Flood', 'Occurrences',
                        'Outlines', 'Periods', 'Wallpaper'})

_CACHE = {'point': None, 'data': {}}


def _point_cache(p):
    """A dict private to the point of `p`; it is replaced when the point changes."""
    key = str(getattr(p, 'point_dir', None)) + '|' + str(getattr(p, 'point', None))
    if _CACHE['point'] != key:
        _CACHE['point'] = key
        _CACHE['data'] = {}
    return _CACHE['data']


def _instances(p):
    """{instance name (no `&`): component} for the INIT clauses before the point that make one of the components."""
    c = _point_cache(p)
    if 'instances' not in c:
        out = {}
        try:
            for cl in p.clauses_before():
                if cl.keyword == 'INIT' and cl.component in COMPONENTS and cl.relation:
                    out[cl.relation.lstrip('&')] = cl.component
        except Exception:
            pass
        c['instances'] = out
    return c['instances']


def _tables_by_name(p):
    c = _point_cache(p)
    if 'tables' not in c:
        c['tables'] = {t.name: t for t in p.available()}
    return c['tables']


def _my_atoms(p):
    """[(atom, component, relation, instance)] for the atoms of the candidate's body that read an instance's relation."""
    out = []
    inst = _instances(p)
    if not inst:
        return out
    body = p.clause.body
    if body is None:
        return out
    for a in body.atoms:
        if a.operator or not a.relation.startswith('&'):
            continue
        base, _, rel = a.relation[1:].partition('.')
        if base in inst:
            out.append((a, inst[base], rel, base))
    return out


# ------------------------------------------------------------------------------------------------ grid helpers

def _examples(p):
    c = _point_cache(p)
    if 'examples' not in c:
        c['examples'] = {e.index: e for e in p.examples()}
    return c['examples']


def _table_rows(table):
    """{example index: [decoded rows]} of the first assignment and first model of each example."""
    out = {}
    try:
        for (asg, ex), models in sorted(table.examples().items(), key=lambda kv: (kv[0][0], kv[0][1])):
            if ex not in out and models:
                out[ex] = models[0]
    except Exception:
        return {}
    return out


def _col(table, name):
    for i, c in enumerate(table.columns()):
        if c.name == name:
            return i, c
    return None, None


def _cells_of(m, ex):
    """The set of (row, col) cells of a Margins value in the input frame of example `ex`; None where unresolved."""
    try:
        if m.frame not in ('input', ''):
            return None
        size = m.size or (ex.input.size if m.frame == 'input' else None)
        if size is None:
            return None
        h, w = size
        if (h, w) != ex.input.size:
            return None
        return {(r, c) for r in range(m.top, h - m.bottom) for c in range(m.left, w - m.right)}
    except Exception:
        return None


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


# ------------------------------------------------------------------------------------------ instance statistics

def _cell_cover(cells, ex):
    """(coverage of changed cells, precision against changed cells, share of the grid) of a cell set in one example."""
    chg = ex.changed()
    h, w = ex.input.size
    share = len(cells) / (h * w) if h * w else None
    if chg is None:
        return None, None, share
    inter = len(cells & chg)
    cov = inter / len(chg) if chg else None
    prec = inter / len(cells) if cells else None
    return cov, prec, share


def _stats_box(table, exs):
    """BoundingBox.box / Outlines.box: boxes of the instance against the changed cells."""
    bi, bc = _col(table, 'B')
    if bc is None:
        return {}
    cov, prec, share, n, crop = [], [], [], [], []
    for ex_i, rows in _table_rows(table).items():
        ex = exs.get(ex_i)
        if ex is None:
            continue
        cells, boxes = set(), 0
        sizes = set()
        for r in rows:
            m = r[bi]
            if not hasattr(m, 'top'):
                continue
            cs = _cells_of(m, ex)
            if cs is None:
                continue
            boxes += 1
            cells |= cs
            sizes.add((ex.input.height - m.top - m.bottom, ex.input.width - m.left - m.right))
        if not boxes:
            continue
        a, b, c = _cell_cover(cells, ex)
        cov.append(a)
        prec.append(b)
        share.append(c)
        n.append(boxes)
        if not ex.same_size:
            crop.append(1.0 if ex.output.size in sizes else 0.0)
    return {'box_cov': _mean(cov), 'box_prec': _mean(prec), 'box_share': _mean(share), 'box_n': _mean(n),
            'box_crop': _mean(crop)}


def _stats_cells(table, exs, column='P'):
    """A table with a Position column: the cells it lists against the changed cells."""
    pi, pc = _col(table, column)
    if pc is None:
        return {}
    cov, prec, share = [], [], []
    for ex_i, rows in _table_rows(table).items():
        ex = exs.get(ex_i)
        if ex is None:
            continue
        cells = set()
        for r in rows:
            m = r[pi]
            if hasattr(m, 'top') and m.frame in ('input', ''):
                cells.add((m.top, m.left))
        if not cells:
            continue
        a, b, c = _cell_cover(cells, ex)
        cov.append(a)
        prec.append(b)
        share.append(c)
    return {'cell_cov': _mean(cov), 'cell_prec': _mean(prec), 'cell_share': _mean(share)}


def _stats_component(table, exs):
    """Connectivity.component: the components against the grids."""
    pi, pc = _col(table, 'P')
    ii, ic = _col(table, 'Id')
    if pc is None or ic is None:
        return {}
    keys = [i for i, c in enumerate(table.columns()) if c.column == 'key' and c.type != 'Example']
    n_comp, single, size, uni_chg, uni_out, share = [], [], [], [], [], []
    for ex_i, rows in _table_rows(table).items():
        ex = exs.get(ex_i)
        if ex is None:
            continue
        groups = C.defaultdict(list)
        for r in rows:
            m = r[pi]
            if hasattr(m, 'top') and m.frame in ('input', ''):
                groups[(tuple(r[k] for k in keys), r[ii])].append((m.top, m.left))
        if not groups:
            continue
        cells = [c for g in groups.values() for c in g]
        n_comp.append(len(groups))
        single.append(sum(len(g) == 1 for g in groups.values()) / len(groups))
        size.append(len(cells) / len(groups))
        share.append(len(set(cells)) / (ex.input.height * ex.input.width))
        chg = ex.changed()
        multi = [g for g in groups.values() if len(g) > 1]
        if multi:
            if chg is not None:
                uni_chg.append(sum(len({c in chg for c in g}) == 1 for g in multi) / len(multi))
            if ex.same_size:
                uni_out.append(sum(len({ex.output.cells[r][c] for r, c in g}) == 1 for g in multi) / len(multi))
    return {'comp_n': _mean(n_comp), 'comp_single': _mean(single), 'comp_size': _mean(size), 'comp_share': _mean(share),
            'comp_uni_chg': _mean(uni_chg), 'comp_uni_out': _mean(uni_out)}


def _stats_ray(table, exs):
    """Ray.ray / Ray.end: the cells of the rays (K above 0) against the output."""
    pi, pc = _col(table, 'P')
    ki, kc = _col(table, 'K')
    oi, oc = _col(table, 'Origin')
    if pc is None or kc is None:
        return {}
    cov, prec, share, agree, length = [], [], [], [], []
    for ex_i, rows in _table_rows(table).items():
        ex = exs.get(ex_i)
        if ex is None:
            continue
        cells, ag = set(), []
        for r in rows:
            m, k = r[pi], r[ki]
            if not hasattr(m, 'top') or not isinstance(k, int) or k <= 0 or m.frame not in ('input', ''):
                continue
            cells.add((m.top, m.left))
            length.append(k)
            if oc is not None and ex.same_size:
                o = r[oi]
                if hasattr(o, 'top'):
                    try:
                        ag.append(1.0 if ex.output.cells[m.top][m.left] == ex.input.cells[o.top][o.left] else 0.0)
                    except Exception:
                        pass
        if not cells:
            continue
        a, b, c = _cell_cover(cells, ex)
        cov.append(a)
        prec.append(b)
        share.append(c)
        if ag:
            agree.append(sum(ag) / len(ag))
    return {'ray_cov': _mean(cov), 'ray_prec': _mean(prec), 'ray_share': _mean(share), 'ray_agree': _mean(agree),
            'ray_len': _mean(length)}


def _stats_tile(table, exs):
    """Division.tile: the tiles against the grids."""
    pi, pc = _col(table, 'P')
    oi, oc = _col(table, 'P_outer')
    if pc is None or oc is None:
        return {}
    n_t, match, size = [], [], []
    for ex_i, rows in _table_rows(table).items():
        ex = exs.get(ex_i)
        if ex is None:
            continue
        outer = set()
        top = left = -1
        for r in rows:
            o = r[oi]
            if hasattr(o, 'top'):
                outer.add((o.top, o.left))
                top, left = max(top, o.top), max(left, o.left)
        if not outer:
            continue
        n_t.append(len(outer))
        size.append(len(rows) / len(outer))
        match.append(1.0 if ex.output.size == (top + 1, left + 1) else 0.0)
    return {'tile_n': _mean(n_t), 'tile_out': _mean(match), 'tile_size': _mean(size)}


_STATS = {
    ('BoundingBox', 'box'): _stats_box,
    ('Outlines', 'box'): _stats_box,
    ('Connectivity', 'component'): _stats_component,
    ('Ray', 'ray'): _stats_ray,
    ('Ray', 'end'): _stats_ray,
    ('Division', 'tile'): _stats_tile,
}
_CELLS = {('Boundary', 'boundary'): 'P', ('Boundary', 'exposed'): 'P', ('Enclosure', 'enclosed'): 'P',
          ('Flood', 'reached'): 'P', ('BoundingBox', 'cell'): 'P', ('Connectivity', 'node'): 'P'}


def relation_stats(p, comp, rel, inst):
    """The statistics of the table `&inst.rel`: {name: number or None}; {} where the table is not available."""
    c = _point_cache(p)
    key = ('stats', inst, rel)
    if key not in c:
        out = {}
        try:
            t = _tables_by_name(p).get(f'&{inst}.{rel}')
            if t is not None and not t.missing:
                exs = _examples(p)
                fn = _STATS.get((comp, rel))
                if fn is not None:
                    out = fn(t, exs)
                elif (comp, rel) in _CELLS:
                    out = _stats_cells(t, exs, _CELLS[(comp, rel)])
        except Exception:
            out = {}
        c[key] = out
    return c[key]


# ------------------------------------------------------------------------------------------ INIT port simulation

def _port(p):
    """(component, port name) at an INIT input point whose component is one of COMPONENTS, else None."""
    try:
        if p.kind != 'INIT input':
            return None
        pb = p.ports_before()
        if pb is None or pb[0] not in COMPONENTS:
            return None
        return pb[0], pb[1]
    except Exception:
        return None


def _x_cellsets(p):
    """{example index: set of (row, col)} of X's first Position column in the input frame (the first Position column
    of frame '' counts when the examples are one size), over the first assignment and model of each example; None where
    X has no such column."""
    x = p.x
    cols = x.columns()
    pos = [(i, c) for i, c in enumerate(cols) if c.type == 'Position' and c.frame in ('input', '')]
    if not pos:
        return None
    i, c = pos[0]
    out = {}
    for ex_i, rows in _table_rows(x).items():
        s = set()
        for r in rows:
            m = r[i]
            if hasattr(m, 'top'):
                s.add((m.top, m.left))
        out[ex_i] = s
    return out


def _neighbors(cell, h, w):
    r, c = cell
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        if 0 <= r + dr < h and 0 <= c + dc < w:
            yield (r + dr, c + dc)


def _components(cells, h, w):
    seen, out = set(), []
    for s in cells:
        if s in seen:
            continue
        comp, stack = [], [s]
        seen.add(s)
        while stack:
            u = stack.pop()
            comp.append(u)
            for v in _neighbors(u, h, w):
                if v in cells and v not in seen:
                    seen.add(v)
                    stack.append(v)
        out.append(comp)
    return out


def _enclosed(cells, h, w):
    """The cells of the set that no walk through the set reaches from a set cell on the frame's edge."""
    reach, stack = set(), [u for u in cells if u[0] in (0, h - 1) or u[1] in (0, w - 1)]
    reach.update(stack)
    while stack:
        u = stack.pop()
        for v in _neighbors(u, h, w):
            if v in cells and v not in reach:
                reach.add(v)
                stack.append(v)
    return cells - reach


def _exposed(cells, h, w):
    """The cells of the set with no set cell one step toward some cardinal direction (off the grid counts as none)."""
    out = set()
    for (r, c) in cells:
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            if (r + dr, c + dc) not in cells:
                out.add((r, c))
                break
    return out


def _rays(src, h, w, dirs=((-1, 0), (1, 0), (0, -1), (0, 1))):
    out = set()
    for (r, c) in src:
        for dr, dc in dirs:
            rr, cc = r + dr, c + dc
            while 0 <= rr < h and 0 <= cc < w:
                out.add((rr, cc))
                rr, cc = rr + dr, cc + dc
    return out


def _fit(cells, ex):
    """cov, prec, share of a derived cell set against example `ex`'s changed cells."""
    return _cell_cover(cells, ex)


def port_stats(p):
    """The simulated statistics of the INIT port candidate: {name: number or None}, or None where the point is not an
    input port of one of the components or X has no input-frame Position column."""
    pt = _port(p)
    if pt is None:
        return None
    comp, port = pt
    sets = _x_cellsets(p)
    if sets is None:
        return None
    exs = _examples(p)
    acc = C.defaultdict(list)
    for ex_i, ex in exs.items():
        h, w = ex.input.size
        n = len([u for u in sets.get(ex_i, ()) if 0 <= u[0] < h and 0 <= u[1] < w])
        acc['ex_empty'].append(0.0 if n else 1.0)
        if n:
            acc['n_cells'].append(float(n))
    for ex_i, cells in sets.items():
        ex = exs.get(ex_i)
        if ex is None or not cells:
            continue
        h, w = ex.input.size
        cells = {u for u in cells if 0 <= u[0] < h and 0 <= u[1] < w}
        if not cells:
            continue
        cov, prec, share = _fit(cells, ex)
        acc['cov'].append(cov)
        acc['prec'].append(prec)
        acc['share'].append(share)
        bgc = ex.input.most_common()
        colours = [ex.input.cells[r][c] for r, c in cells]
        acc['bg'].append(sum(v in bgc for v in colours) / len(colours))
        acc['ncol'].append(float(len(set(colours))))
        chg = ex.changed()
        if comp == 'Connectivity' or comp == 'Flood' and port == 'node' or comp == 'Ray' and port == 'node':
            comps = _components(cells, h, w)
            acc['n_comp'].append(len(comps))
            acc['single'].append(sum(len(g) == 1 for g in comps) / len(comps))
            multi = [g for g in comps if len(g) > 1]
            if multi and chg is not None:
                acc['uni_chg'].append(sum(len({u in chg for u in g}) == 1 for g in multi) / len(multi))
            if multi and ex.same_size:
                acc['uni_out'].append(sum(len({ex.output.cells[r][c] for r, c in g}) == 1 for g in multi) / len(multi))
        if comp == 'Enclosure' or comp == 'Boundary':
            e = _enclosed(cells, h, w) if comp == 'Enclosure' else _exposed(cells, h, w)
            acc['d_nonempty'].append(1.0 if e else 0.0)
            acc['d_share'].append(len(e) / (h * w))
            a, b, _ = _fit(e, ex) if e else (None, None, None)
            acc['d_cov'].append(a)
            acc['d_prec'].append(b)
        if comp == 'BoundingBox':
            rs = [u[0] for u in cells]
            cs = [u[1] for u in cells]
            box = {(r, c) for r in range(min(rs), max(rs) + 1) for c in range(min(cs), max(cs) + 1)}
            a, b, s = _fit(box, ex)
            acc['bb_cov'].append(a)
            acc['bb_prec'].append(b)
            acc['bb_share'].append(s)
            acc['bb_fill'].append(len(cells) / len(box))
            if not ex.same_size:
                acc['bb_crop'].append(1.0 if ex.output.size == (max(rs) - min(rs) + 1, max(cs) - min(cs) + 1) else 0.0)
        if comp in ('Ray', 'Flood') and port == 'source':
            r = _rays(cells, h, w)
            a, b, s = _fit(r, ex)
            acc['r_cov'].append(a)
            acc['r_prec'].append(b)
            acc['r_share'].append(s)
            acc['n_src'].append(len(cells))
    return {k: _mean(v) for k, v in acc.items()}


# ------------------------------------------------------------------------------------------- groups of an instance

def _groups(table, comp, rel, ex):
    """The cell groups of one example from an instance's output table: the components of Connectivity.component, the
    cells of each BoundingBox/Outlines box, the cells of each Ray ray by (key, origin, direction) with K above 0, the cells
    of each Division tile by (key, P_outer). A list of sets of (row, col)."""
    cols = table.columns()
    rows = _table_rows(table).get(ex.index, [])
    keys = [i for i, c in enumerate(cols) if c.column == 'key' and c.type != 'Example']
    names = {c.name: i for i, c in enumerate(cols)}
    groups = C.defaultdict(set)
    try:
        if comp == 'Connectivity' and rel == 'component':
            pi, ii = names['P'], names['Id']
            for r in rows:
                m = r[pi]
                if hasattr(m, 'top'):
                    groups[(tuple(r[k] for k in keys), r[ii])].add((m.top, m.left))
        elif comp in ('BoundingBox', 'Outlines') and rel == 'box':
            bi = names['B']
            for n, r in enumerate(rows):
                cs = _cells_of(r[bi], ex) if hasattr(r[bi], 'top') else None
                if cs:
                    groups[n] = cs
        elif comp == 'Ray' and rel == 'ray':
            pi, ki, oi, di = names['P'], names['K'], names['Origin'], names['D']
            for r in rows:
                m = r[pi]
                if hasattr(m, 'top') and isinstance(r[ki], int) and r[ki] > 0:
                    groups[(tuple(r[k] for k in keys), r[oi], r[di])].add((m.top, m.left))
        elif comp == 'Division' and rel == 'tile':
            pi, oi = names['P'], names['P_outer']
            for r in rows:
                m = r[pi]
                if hasattr(m, 'top'):
                    groups[(tuple(r[k] for k in keys), r[oi])].add((m.top, m.left))
    except Exception:
        return []
    return list(groups.values())


def read_stats(p):
    """For the candidate's reads of the grouped relations (component, box, ray, tile): the completeness of X's cells
    against the groups of the instance: {relation key: {name: number}}, relation keys 'Connectivity.component' etc.
    X's cells are its first input-frame Position column."""
    sets = _x_cellsets(p) if p.kind != 'Det' else None
    out = {}
    if not sets:
        return out
    exs = _examples(p)
    for a, comp, rel, inst in _my_atoms(p):
        if (comp, rel) not in (('Connectivity', 'component'), ('BoundingBox', 'box'), ('Outlines', 'box'), ('Ray', 'ray'),
                               ('Division', 'tile')) or a.negated:
            continue
        t = _tables_by_name(p).get(f'&{inst}.{rel}')
        if t is None or t.missing:
            continue
        acc = C.defaultdict(list)
        for ex_i, cells in sets.items():
            ex = exs.get(ex_i)
            if ex is None or not cells:
                continue
            groups = _groups(t, comp, rel, ex)
            if not groups:
                continue
            touched = [g for g in groups if g & cells]
            if not touched:
                acc['touched'].append(0.0)
                continue
            comp_ = [len(g & cells) / len(g) for g in touched]
            acc['touched'].append(len(touched) / len(groups))
            acc['complete'].append(sum(c > 0.999 for c in comp_) / len(touched))
            acc['fill'].append(sum(comp_) / len(touched))
            allg = set().union(*groups)
            acc['inside'].append(len(cells & allg) / len(cells))
            acc['cover'].append(len(cells & allg) / len(allg))
        out[f'{comp}.{rel}'] = {k: _mean(v) for k, v in acc.items()}
    return out


# ----------------------------------------------------------------------------------------------------- features

def _port_group(p, members, keys):
    """port_stats(p) restricted to `keys`, when the point is a port in `members` ({(component, port)}); else None."""
    try:
        pt = _port(p)
        if pt is None or pt not in members:
            return None
        st = port_stats(p)
        if not st:
            return None
        out = {k: st.get(k) for k in keys}
        return {k: v for k, v in out.items() if v is not None} or None
    except Exception:
        return None


@feature
def a1_bbox_port(p):
    """A1: the `cell` port of a BoundingBox instance. The least box over X's cells, per example, against the cells the
    task changes: coverage of the changed cells (`bb_cov`), the share of the box that changes (`bb_prec`), the box's
    share of the grid (`bb_share`), X's share of the box (`bb_fill`), and where the output size differs from the input's,
    whether the output has the box's size (`bb_crop`). Also X's own coverage, precision and share of the grid, the
    share of X's cells on the input's most common colour (`bg`) and the number of colours under them (`ncol`). Gold's
    cells are an object, and draws that match the changed cells better than gold are common here.
    None except at that port, and where X has no input-frame Position column.
    """
    return _port_group(p, {('BoundingBox', 'cell')}, ('bb_cov', 'bb_prec', 'bb_share', 'bb_fill', 'bb_crop', 'cov', 'prec', 'share', 'bg', 'ncol'))


@feature
def a2_conn_port(p):
    """A2: the `node` port of a Connectivity instance. The 4-connected components of X's cells, per example: their count
    (`n_comp`), the share that are single cells (`single`), whether the set is one piece (`one`), the share of multi-cell
    components whose cells all change or all stay (`uni_chg`) and whose output cells share one colour (`uni_out`), and
    X's coverage, precision and grid share. None except at that port and with an input-frame Position column.
    """
    v = _port_group(p, {('Connectivity', 'node')}, ('n_comp', 'single', 'uni_chg', 'uni_out', 'cov', 'prec', 'share', 'bg', 'ncol'))
    if v is not None and 'n_comp' in v:
        v['one'] = 1.0 if v['n_comp'] <= 1.0 else 0.0
    return v


@feature
def a3_source_port(p):
    """A3: the `source` port of a Ray or a Flood instance. X's cell count per example (`n_src`) and grid share, the cells
    on the straight lines through them over the whole grid (`r_share`) against the changed cells (`r_cov`, `r_prec`), and
    X's own coverage and precision. Gold's sources are few. None except at those ports.
    """
    return _port_group(p, {('Ray', 'source'), ('Flood', 'source')}, ('n_src', 'share', 'r_cov', 'r_prec', 'r_share', 'cov', 'prec', 'bg', 'ncol'))


@feature
def a4_region_port(p):
    """A4: the `cell` port of an Enclosure or a Boundary instance. The cells the component derives from X (Enclosure: the
    cells no walk through X reaches from X's cells on the frame's edge; Boundary: the cells with no X cell one step toward
    some cardinal direction): non-empty in every example (`d_nonempty`), their grid share (`d_share`), coverage and precision
    against the changed cells (`d_cov`, `d_prec`), and X's coverage, precision and share. None except at those ports.
    """
    return _port_group(p, {('Enclosure', 'cell'), ('Boundary', 'cell')}, ('d_nonempty', 'd_share', 'd_cov', 'd_prec', 'cov', 'prec', 'share', 'bg', 'ncol'))


@feature
def a5_node_port(p):
    """A5: the `node` port of a Ray, a Flood or an Outlines instance. X's coverage of the changed cells, the share of X
    that changes and X's grid share, with the number of 4-connected pieces. None except at those ports.
    """
    v = _port_group(p, {('Ray', 'node'), ('Flood', 'node'), ('Outlines', 'node')}, ('cov', 'prec', 'share', 'n_comp', 'single', 'bg', 'ncol'))
    return v


_READ_KEYS = {('Connectivity', 'component'): 'comp', ('BoundingBox', 'box'): 'box', ('Outlines', 'box'): 'box',
              ('Ray', 'ray'): 'ray', ('Division', 'tile'): 'tile'}


@feature
def a6_group_fill(p):
    """A6: how X's cells sit in the groups of an instance it reads. For a read of Connectivity.component, BoundingBox.box,
    Ray.ray or Division.tile (the groups: the components, the boxes' cells, the rays from a source toward a direction, the
    tiles), per example: the share of groups that X touches (`<group>_touched`), the share of touched groups that X holds
    whole (`_complete`), the mean share of a touched group that X holds (`_fill`), the share of X's cells in some group
    (`_inside`) and the share of all groups' cells that X holds (`_cover`). The mean over the candidate's reads of
    that relation. None without such a read or without an input-frame Position column in X.
    """
    try:
        rs = read_stats(p)
        out = {}
        for rel, st in rs.items():
            comp, _, r = rel.partition('.')
            tag = _READ_KEYS.get((comp, r))
            for k, v in st.items():
                if v is not None:
                    out.setdefault(f'{tag}_{k}', []).append(v)
        return {k: sum(v) / len(v) for k, v in out.items()} or None
    except Exception:
        return None


@feature
def a7_read_fit(p):
    """A7: the fit of the instance a candidate reads. For each read of BoundingBox.box (also Outlines.box), Connectivity.component,
    Ray.ray or Division.tile, the instance table's statistics against the train grids: boxes (`box_cov`, `box_prec`, `box_share`,
    `box_n`, `box_crop`), components (`comp_n`, `comp_single`, `comp_size`, `comp_uni_chg`, `comp_uni_out`), rays (`ray_cov`,
    `ray_prec`, `ray_agree`, `ray_len`) and tiles (`tile_n`, `tile_size`). The mean over the candidate's reads. None without such a read.
    """
    try:
        out = {}
        for a, comp, rel, inst in _my_atoms(p):
            if (comp, rel) not in _READ_KEYS or a.negated:
                continue
            for k, v in relation_stats(p, comp, rel, inst).items():
                if v is not None:
                    out.setdefault(k, []).append(v)
        return {k: sum(v) / len(v) for k, v in out.items()} or None
    except Exception:
        return None
