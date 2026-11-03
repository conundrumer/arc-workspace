"""Targets and conditioning facts of each gold form, from the rows of next_form_rows.py.

Each fact reads only the state before the form: the task's grids, and the forms before it with their tables.

Families:
  need    n_: what the train outputs still need against the found tables, and what changes between input and output at the task's start
  grid    g_: the task's input grids and sizes
  foundset fs_: columns, row shapes and components of the found tables, as a set, with no use of gold's order
  order   f_: the last form written, the count of forms and other facts that read gold's order. A pool has no such order, so this family is an upper bound

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

R = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-next-form-content-given-task-heldout37/'
FAMILY = {}


def load(split):
    """{task: [form rows in order]} of a split. The held split reads rows-held, and only the final read loads it."""
    folder = R + ('rows-held/' if split == 'held' else 'rows/')
    out = collections.defaultdict(list)
    for p in sorted(glob.glob(folder + 'form-rows-%s-*.jsonl' % split)):
        with open(p) as f:
            for x in f:
                r = json.loads(x)
                out[r['task']].append(r)
    for t in out:
        out[t].sort(key=lambda r: r['form'])
    return dict(out)


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


def foundset_facts(prev):
    """Facts of the set of found forms. No fact here reads the order of the forms."""
    d = {}
    comps = {p['comp'] for p in prev if p['kind'] == 'INIT'}
    types, geoms, rels = set(), set(), set()
    paint = pos = False
    read = set()
    for p in prev:
        read.update(x[2] for x in p['reads'] if x[2] is not None)
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
    d['fs_ninit'] = bucket(sum(p['kind'] == 'INIT' for p in prev), [0, 1, 3])
    d['fs_ndet'] = bucket(sum(p['kind'] == 'DET' for p in prev), [0, 1, 3])
    d['fs_nrule'] = bucket(sum(p['kind'] == 'RULE' for p in prev), [0, 1, 3, 7])
    un = [p for i, p in enumerate(prev) if i not in read]
    d['fs_unread'] = bucket(len(un), [0, 1, 2, 4])
    uty = set()
    for p in un:
        t = main_table(p)
        if t and t.get('types'):
            uty.add(frozenset(t['types']))
    d['fs_u_paint'] = 'yes' if any({'Position', 'Color'} <= x for x in uty) else 'no'
    d['fs_u_pos'] = 'yes' if any('Position' in x for x in uty) else 'no'
    d['fs_u_col'] = 'yes' if any(x == {'Color'} for x in uty) else 'no'
    d['fs_u_ident'] = 'yes' if any('Ident' in x for x in uty) else 'no'
    d['fs_u_nat'] = 'yes' if any(x <= {'Nat', 'Int'} for x in uty) else 'no'
    return d


def found_facts(forms, f, r):
    """Facts of forms[:f]."""
    d = {}
    prev = forms[:f]
    d['f_n'] = bucket(f, [0, 1, 3, 7, 15])
    d.update(foundset_facts(prev))
    read = set()
    for p in prev:
        read.update(x[2] for x in p['reads'] if x[2] is not None)
    unread = [i for i in range(f) if i not in read]
    last = prev[-1] if prev else None
    lt = main_table(last) if last else None
    d['f_lkind'] = last['kind'] if last else 'start'
    d['f_lcomp'] = (last['comp'] or last['kind']) if last else 'start'
    libs = lib_set(last) if last else []
    d['f_llib'] = next((x for x in libs if x not in ('input',)), 'nolib') if last else 'start'
    d['f_lcols'] = coarse_types(lt) if last else 'start'
    d['f_lgeom'] = geom_of(lt) if last else 'start'
    d['f_lrel'] = rel_of(lt) if last else 'start'
    l2 = prev[-2]['kind'] if len(prev) > 1 else 'start'
    d['f_l2'] = l2 + '>' + d['f_lkind']
    u = forms[unread[-1]] if unread else None
    ut = main_table(u) if u else None
    d['f_ucols'] = coarse_types(ut) if u else 'all read'
    d['f_ugeom'] = geom_of(ut) if u else 'all read'
    d['f_ucomp'] = (u['comp'] or u['kind']) if u else 'all read'
    d['f_cut'] = cut_fact(forms, f)
    return d


def cut_fact(forms, f):
    """How much the last form cut the uncovered cells: a need fact, read against the state before it."""
    if f == 0:
        return 'start'
    a, b = sum(forms[f - 1]['state']['xleft']), sum(forms[f]['state']['xleft'])
    if a == 0:
        return 'none left'
    return 'none' if a == b else 'more' if b > a else 'most' if b < a / 2 else 'some'


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
    """A flat list of {task, form, kind, facts, targets} in task order."""
    out = []
    for t in sorted(tasks):
        forms = tasks[t]
        g0 = start_facts(forms[0]['state'])
        for f, r in enumerate(forms):
            if r['form'] != f:
                break
            x = dict(g0)
            x.update(need_facts(r['state']))
            x.update(found_facts(forms, f, r))
            out.append(dict(task=t, form=f, kind=r['kind'], text=r['text'], source=r['source'], fact=x, y=targets(r, forms), t_need=r['t_need'], fault=r.get('fault')))
    return out


FAMILIES = {'need': ('n_', 'n0_'), 'grid': ('g_',), 'foundset': ('fs_',), 'order': ('f_',)}


def open_keys(forms, f):
    """The derived keys that the forms before f hold."""
    out = set()
    for p in forms[:f]:
        ords = {t.get('ord') for t in p.get('tables', ()) if t.get('ord') is not None} or {0}
        for o in ords:
            out.add(key_of(p, o))
    return out


def attach_open(rows, tasks):
    for r in rows:
        r['open'] = open_keys(tasks[r['task']], r['form'])
    return rows


def categorical(rows, ycol, kinds):
    """Rows of a target with one value per form."""
    return [dict(task=r['task'], form=r['form'], kind=r['kind'], fact=r['fact'], y=r['y'][ycol]) for r in rows if r['kind'] in kinds and r['y'][ycol] is not None]


def bag(rows, kinds, keys=True):
    """One row per distinct token that a form reads: its lib relations, and with keys its derived keys."""
    out = []
    for r in rows:
        if r['kind'] in kinds:
            for t in r['y']['t_lib']:
                out.append(dict(task=r['task'], form=r['form'], kind=r['kind'], fact=r['fact'], y=t, open=r.get('open')))
            if keys:
                for t in r['y']['t_keys']:
                    out.append(dict(task=r['task'], form=r['form'], kind=r['kind'], fact=r['fact'], y=t, open=r.get('open')))
    return out


def family_keys(rows):
    return {k: sorted({a for r in rows for a in r['fact'] if a.startswith(p)}) for k, p in FAMILIES.items()}


TIERS = {'grid': ('grid',), 'need': ('grid', 'need'), 'foundset': ('grid', 'foundset'), 'need+foundset': ('grid', 'need', 'foundset'), 'all': ('grid', 'need', 'foundset', 'order')}
