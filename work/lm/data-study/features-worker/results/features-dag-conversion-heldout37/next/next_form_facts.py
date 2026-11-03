"""Targets and conditioning facts of each gold form, from the rows of next_form_rows.py.

A row is a target form with a seed. The state is a set S of found forms, the `cut` of the target for the seed. Each fact reads the grids of the task and the tables of the forms of S as a set: no fact reads the order of S, the order of a form's text, or which form was written last.

Families:
  need     n_: what the train outputs still need against the found tables, and what changes between input and output at the task's start (n0_)
  grid     g_: the task's input grids and sizes
  foundset fs_: columns, row shapes and components of the found tables, as a set; and the facts of the forms of S that no form of S reads, as multi-hot facts of their kinds, components, column types, geometric shapes and relational shapes (fs_ul_); f_n, the count of forms of S

Targets:
  t_comp   the component of an INIT or of a DET that has one; 'body' for a DET with a body
  t_reads  the set of lib relations (kinds lib relation, relation macro, fact relation) and derived keys the form reads
  t_cols   the head's column types, sorted
  t_coarse the head's column types with duplicates removed, sorted
  t_geom   the geometric shape of the rows' positions, 'no position' with no Position column
  t_rel    the relational shape of the rows
"""
import collections
import glob
import json
import math
import os
import statistics

R = os.path.dirname(os.path.abspath(__file__)) + '/'
BANNED = ('under', 'form_atoms', 'nsize', 'form_not', 'form_or')  # columns of the pick rows that no fact reads
FAMILY = {}


def load(split, folder=None):
    """{task: dict(forms={key: form row}, states={(key, seed): state row}, task=task row)} of a split. The held split reads rows-held, and only the final read loads it."""
    folder = folder or R + ('rows-held/' if split == 'held' else 'rows/')
    out = {}
    for kind in ('task', 'form', 'state'):
        for p in sorted(glob.glob(folder + '%s-rows-%s-*.jsonl' % (kind, split))):
            with open(p) as f:
                for x in f:
                    r = json.loads(x)
                    d = out.setdefault(r['task'], dict(forms={}, states={}, task=None))
                    if kind == 'task':
                        d['task'] = r
                    elif kind == 'form':
                        d['forms'][r['key']] = r
                    else:
                        d['states'][r['key'], r['seed']] = r
    return {t: d for t, d in out.items() if d['task'] and not d['task'].get('fault') and d['states']}


def bucket(x, cuts):
    for c in cuts:
        if x <= c:
            return '<=%g' % c
    return '>%g' % cuts[-1]


def share(a, b):
    if b == 0:
        return 'none'
    s = a / b
    if s == 0:
        return '0'
    if s < .25:
        return '<.25'
    if s < .75:
        return '<.75'
    if s < 1:
        return '<1'
    return '1'


def main_table(r):
    """The form's head table: the table with the lowest declared ordinal that has rows' facts, else the first."""
    ts = [t for t in r.get('tables', ()) if t.get('types') is not None]
    ok = [t for t in ts if 'nrows' in t]
    ok.sort(key=lambda t: (t.get('ord') is None, t.get('ord') or 0))
    return ok[0] if ok else (ts[0] if ts else None)


def head_types(t):
    return '+'.join(sorted(t['types'])) if t and t.get('types') else 'none'


def coarse_types(t):
    return '+'.join(sorted(set(t['types']))) if t and t.get('types') else 'none'


def geom_of(t):
    if not t or 'nrows' not in t:
        return 'no table'
    if 'Position' not in t['types']:
        return 'no position'
    return t.get('ngeom') or 'empty'


def rel_of(t):
    if not t or 'nrows' not in t:
        return 'no table'
    return t.get('nrel') or 'empty'


def key_of(owner, table_ord):
    """The key of a derived read: the owner's component and declared ordinal, or the owner's kind and head column types."""
    if owner['kind'] == 'INIT':
        return 'D:%s#%s' % (owner['comp'], table_ord)
    if owner['kind'] == 'DET':
        return 'D:DET:%s' % (owner['comp'] if owner['comp'] else coarse_types(main_table(owner)))
    return 'D:%s:%s' % (owner['kind'], coarse_types(main_table(owner)))


def lib_set(r):
    return sorted({x[0] for x in r['reads'] if x[1] != 'relation'})


def key_set(r, forms):
    out = set()
    for x in r['reads']:
        if x[1] == 'relation' and x[2] is not None:
            out.add(key_of(forms[x[2]], x[3]))
    return sorted(out)


def targets(r, forms):
    t = main_table(r)
    comp = r['comp'] if r['comp'] else ('body' if r['kind'] in ('DET', 'INIT') else None)
    y = dict(t_comp=comp, t_lib=lib_set(r), t_keys=key_set(r, forms), t_cols=head_types(t), t_coarse=coarse_types(t), t_geom=geom_of(t), t_rel=rel_of(t))
    y['t_shape'] = y['t_geom'] + '|' + y['t_rel']
    y['t_head'] = y['t_coarse'] + '|' + y['t_shape']
    y['t_content'] = str(comp or r['kind']) + '|' + y['t_head']
    return y


def need_facts(st):
    ch, un, up = sum(st['changed']), sum(st['uncov']), sum(st['unpos'])
    n = len(st['changed']) or 1
    d = {}
    d['n_left'] = share(un, ch)
    d['n_posleft'] = share(up, ch)
    d['n_cells'] = bucket(un / n, [0, 3, 15, 63, 255])
    d['n_chg'] = bucket(ch / n, [3, 15, 63, 255])
    d['n_area'] = share(ch, sum(st['area']))
    gs = [g for g in st['geom'] if g != 'empty']
    d['n_geom'] = collections.Counter(gs).most_common(1)[0][0] if gs else 'nothing left'
    d['n_agree'] = 'agree' if gs and len(set(gs)) == 1 else ('none' if not gs else 'differ')
    d['n_ncc'] = bucket(statistics.median(st['ncc']), [0, 1, 3, 9])
    cols = [set(x) for x in st['colors']]
    allc = set().union(*cols) if cols else set()
    d['n_ncol'] = bucket(len(allc), [0, 1, 2, 3])
    d['n_colconst'] = 'same' if cols and all(c == cols[0] for c in cols) else 'varies'
    new = sum(st['new'])
    tot = sum(len(c) for c in cols)
    d['n_new'] = 'none left' if tot == 0 else ('all new' if new == tot else 'some new' if new else 'no new')
    a, m, c = sum(st['add']), sum(st['rem']), sum(st['rec'])
    d['n_trans'] = 'resize' if not st['same'] else ('none' if a + m + c == 0 else max((a, 'add'), (m, 'remove'), (c, 'recolor'))[1])
    d['n_same'] = 'same' if st['same'] else 'resize'
    d['n_countsame'] = 'equal' if len(set(st['uncov'])) == 1 else 'differ'
    hs = [b[0] for b in st['bbox'] if b[0]]
    ws = [b[1] for b in st['bbox'] if b[0]]
    d['n_bbox'] = 'none' if not hs else 'thin' if max(min(h, w) for h, w in zip(hs, ws)) == 1 else bucket(statistics.median(h * w for h, w in zip(hs, ws)), [9, 36, 100])

    def part(xs):
        return share(sum(xs), len(xs)) if xs else 'none'
    d['n_adj'] = part(st['adj'])
    d['n_encl'] = part(st['encl'])
    d['n_onobj'] = part(st['onobj'])
    d['n_rc'] = part(st['rc'])
    d['n_copy'] = part(st['copy'])
    d['n_jac'] = 'none' if not st['jac'] else bucket(sum(st['jac']) / len(st['jac']), [0, .25, .5, .9, .999])
    d['n_colfound'] = part(st['colfound'])
    # Cells that the found tables do not predict, one train example left out.
    xc = sum(st['xleft'])
    d['n_xleft'] = share(xc, ch)
    d['n_xcells'] = bucket(xc / n, [0, 3, 15, 63, 255])
    d['n_xall'] = share(sum(st['xall']), sum(st['area']))
    xg = [g for g in st['xgeom'] if g != 'empty']
    d['n_xgeom'] = collections.Counter(xg).most_common(1)[0][0] if xg else 'nothing left'
    d['n_xncc'] = bucket(statistics.median(st['xncc']), [0, 1, 3, 9])
    xs = [set(c) for c in st['xcol']]
    xall = set().union(*xs) if xs else set()
    d['n_xncol'] = bucket(len(xall), [0, 1, 2, 3])
    t2 = sum(len(c) for c in xs)
    d['n_xnew'] = 'none left' if t2 == 0 else ('all new' if sum(st['xnew']) == t2 else 'some new' if sum(st['xnew']) else 'no new')
    d['n_xadj'] = part(st['xadj'])
    d['n_xencl'] = part(st['xencl'])
    d['n_xonobj'] = part(st['xonobj'])
    return d


TOP_COMPS = ('Connectivity', 'Order', 'BoundingBox', 'Ray', 'Cardinality', 'Frame', 'Division', 'Inclusion', 'Quotient', 'Tiling', 'Flood', 'Boundary', 'Distance', 'Propagation', 'Occurrences', 'Singleton')
TOP_TYPES = ('Ident', 'Box', 'Nat', 'Int', 'Axis', 'Dir', 'Dir8', 'D4', 'Offset')
TOP_GEOM = ('whole grid', 'rectangle', 'ring', 'blob', 'blocks', 'lines', 'dots', 'scatter', 'single cell', 'diagonal')
TOP_REL = ('function', 'one to one', 'many to many', 'cross product', 'order', 'chain', 'equivalence', 'symmetric')


TOP_UTYPES = ('Position', 'Color') + TOP_TYPES
TOP_ULCOMP = TOP_COMPS + ('body',)


def read_keys(S):
    """The keys of the forms that a form of S reads."""
    out = set()
    for p in S:
        out.update(x[2] for x in p['reads'] if x[2] is not None)
    return out


def unread_of(S):
    """The forms of S that no form of S reads."""
    read = read_keys(S)
    return [p for p in S if p['key'] not in read]


def foundset_facts(S):
    """Facts of the set S of found forms. No fact reads the order of S."""
    d = {}
    comps = {p['comp'] for p in S if p['kind'] == 'INIT'}
    types, geoms, rels = set(), set(), set()
    paint = pos = False
    for p in S:
        for t in p.get('tables', ()):
            ty = set(t.get('types') or ())
            types |= ty
            if 'nrows' in t:
                geoms.add(t.get('ngeom'))
                rels.add(t.get('nrel'))
            if 'Position' in ty:
                pos = True
                paint = paint or 'Color' in ty
    for c in TOP_COMPS:
        d['fs_c_' + c] = 'yes' if c in comps else 'no'
    for c in TOP_TYPES:
        d['fs_t_' + c] = 'yes' if c in types else 'no'
    for c in TOP_GEOM:
        d['fs_g_' + c.replace(' ', '_')] = 'yes' if c in geoms else 'no'
    for c in TOP_REL:
        d['fs_r_' + c.replace(' ', '_')] = 'yes' if c in rels else 'no'
    d['fs_paint'] = 'paint' if paint else 'pos' if pos else 'nopos'
    d['fs_ninit'] = bucket(sum(p['kind'] == 'INIT' for p in S), [0, 1, 3])
    d['fs_ndet'] = bucket(sum(p['kind'] == 'DET' for p in S), [0, 1, 3])
    d['fs_nrule'] = bucket(sum(p['kind'] == 'RULE' for p in S), [0, 1, 3, 7])
    un = unread_of(S)
    d['fs_unread'] = bucket(len(un), [0, 1, 2, 4])
    uty = set()
    ucomp, ukind, ugeom, urel = set(), set(), set(), set()
    for p in un:
        ukind.add(p['kind'])
        if p['kind'] in ('INIT', 'DET'):
            ucomp.add(p['comp'] if p['comp'] else 'body')
        t = main_table(p)
        if t and t.get('types'):
            uty.add(frozenset(t['types']))
        if t and 'nrows' in t:
            ugeom.add(t.get('ngeom'))
            urel.add(t.get('nrel'))
    d['fs_u_paint'] = 'yes' if any({'Position', 'Color'} <= x for x in uty) else 'no'
    d['fs_u_pos'] = 'yes' if any('Position' in x for x in uty) else 'no'
    d['fs_u_col'] = 'yes' if any(x == {'Color'} for x in uty) else 'no'
    d['fs_u_ident'] = 'yes' if any('Ident' in x for x in uty) else 'no'
    d['fs_u_nat'] = 'yes' if any(x <= {'Nat', 'Int'} for x in uty) else 'no'
    for k in KINDS:
        d['fs_ul_k_' + k] = 'yes' if k in ukind else 'no'
    for c in TOP_ULCOMP:
        d['fs_ul_c_' + c] = 'yes' if c in ucomp else 'no'
    for c in TOP_UTYPES:
        d['fs_ul_t_' + c] = 'yes' if any(c in x for x in uty) else 'no'
    for c in TOP_GEOM:
        d['fs_ul_g_' + c.replace(' ', '_')] = 'yes' if c in ugeom else 'no'
    for c in TOP_REL:
        d['fs_ul_r_' + c.replace(' ', '_')] = 'yes' if c in urel else 'no'
    return d


KINDS = ('RULE', 'DET', 'INIT')


def found_facts(S):
    """Facts of the set S of the forms found before the target."""
    d = dict(f_n=bucket(len(S), [0, 1, 3, 7, 15]))
    d.update(foundset_facts(S))
    return d


def start_facts(st):
    """Facts of the task, from the state before its first form."""
    d = {}
    n = len(st['changed']) or 1
    s = st['static']
    d['g_area'] = bucket(sum(st['area']) / n, [25, 100, 225, 400])
    d['g_nex'] = bucket(n, [2, 3, 4])
    d['g_nobj'] = bucket(s['nobj'], [1, 2, 4, 9, 25])
    d['g_ncol'] = bucket(s['ncol'], [2, 3, 4, 6])
    d['g_period_in'] = str(s['period_in'])
    a = need_facts(st)
    d['n0_resize'] = s['resize']
    d['n0_crop'] = str(s['crop'])
    d['n0_embed'] = str(s['embed'])
    d['n0_sym'] = s['sym']
    d['n0_period'] = str(s['period'])
    d['n0_colormap'] = str(s['colormap'])
    d['n0_newcol'] = s['newcol']
    d['n0_outbox'] = str(s['outbox'])
    for k in ('n_chg', 'n_area', 'n_new', 'n_ncol', 'n_trans', 'n_geom', 'n_ncc', 'n_adj', 'n_encl', 'n_onobj', 'n_rc', 'n_copy', 'n_bbox', 'n_colconst', 'n_countsame', 'n_xleft', 'n_xgeom', 'n_xnew'):
        d['n0' + k[1:]] = a[k]
    return d


def rows_of(tasks):
    """A flat list of {task, form, key, seed, scope_id, kind, facts, targets, open} in task order, one per target form and seed."""
    out = []
    for t in sorted(tasks):
        d = tasks[t]
        forms = d['forms']
        g0 = start_facts(dict(d['task']['start'], static=d['task']['static']))
        for (key, seed), st in sorted(d['states'].items()):
            r = forms[key]
            S = [forms[k] for k in st['scope']]
            x = dict(g0)
            x.update(need_facts(st['state']))
            x.update(found_facts(S))
            out.append(dict(task=t, form=r['form'], key=key, seed=seed, scope_id=st['scope_id'], kind=r['kind'], text=r['text'], source=r['source'], fact=x, y=targets(r, forms), open=open_keys(S), t_need=st['t_need'], fault=r.get('fault')))
    return out


FAMILIES = {'need': ('n_', 'n0_'), 'grid': ('g_',), 'foundset': ('fs_', 'f_n')}


def open_keys(S):
    """The derived keys that the forms of S hold."""
    out = set()
    for p in S:
        ords = {t.get('ord') for t in p.get('tables', ()) if t.get('ord') is not None} or {0}
        for o in ords:
            out.add(key_of(p, o))
    return out


def categorical(rows, ycol, kinds):
    """Rows of a target with one value per form."""
    return [dict(task=r['task'], form=r['form'], key=r['key'], seed=r['seed'], scope_id=r['scope_id'], kind=r['kind'], fact=r['fact'], y=r['y'][ycol], open=r['open']) for r in rows if r['kind'] in kinds and r['y'][ycol] is not None]


def bag(rows, kinds, keys=True):
    """One row per distinct token that a form reads: its lib relations, and with keys its derived keys."""
    out = []
    for r in rows:
        if r['kind'] in kinds:
            for t in r['y']['t_lib']:
                out.append(dict(task=r['task'], form=r['form'], key=r['key'], seed=r['seed'], scope_id=r['scope_id'], kind=r['kind'], fact=r['fact'], y=t, open=r['open']))
            if keys:
                for t in r['y']['t_keys']:
                    out.append(dict(task=r['task'], form=r['form'], key=r['key'], seed=r['seed'], scope_id=r['scope_id'], kind=r['kind'], fact=r['fact'], y=t, open=r['open']))
    return out


def family_keys(rows):
    return {k: sorted({a for r in rows for a in r['fact'] if a.startswith(p)}) for k, p in FAMILIES.items()}


TIERS = {'grid': ('grid',), 'need': ('grid', 'need'), 'foundset': ('grid', 'foundset'), 'need+foundset': ('grid', 'need', 'foundset')}
