"""relfeat: the feature functions of relcheap, in pure Python (no numpy, torch or sklearn), and the derived-name mask.

A feature function is  fn(row, option) -> {name: float}.  A row is a relrows row (k, phase, scope, prefix, point_group, options).
Built-in sets:
  struct  relfit.py's own features without recency (a port; test_equal() checks it against relfit.py)
  b       r14b.option_features (a port; same check)
  x       sparse crosses ('x:' names): option name x prefix relation names; option types x scope types; kind x k; kind x group
  ctx     for trees: kind, k, group, phase, arity, option types and scope types as multi-hot
mask_row(row, mode) hides the author's names before any feature sees the row:
  'all'    every derived option's name becomes '&D'; a derived atom of the prefix keeps only its slot ('&r2.box' -> '&r2')
  'group'  as 'all', but a member name that the library declares stays ('&bbox.box' -> '&D.box', '&r2.box' stays)
  'none'   the row as it is (only for measuring the leak)
"""
import hashlib
import math
import re

EXCLUDE = {'recency0', 'recency_log'}  # relfit features that read slot distance
STRUCT_NAMES = ['logp', 'lib', 'derived', 'op', 'lib_k1', 'derived_k1', 'op_k1', 'in_scope', 'in_scope_frac', 'none_in_scope',
                'arity', 'repeat', 'recency0', 'recency_log', 'no_types']
PREV = re.compile(r'\((?:NOT \()?([^\s()]+)')
ATOM = re.compile(r'\((NOT )?\(?([^\s():][^\s()]*)')
DERIVED_REF = re.compile(r'&r\d+(\.\w+)?')

# member names that src/arclog_convert/lib-signature.dl declares (the outputs of the lib's component constructors)
LIB_MEMBERS = frozenset(
    'cell member node successor score rank probe dual_rank minimal secondary_score maximal cyclic_successor before source box size '
    'domain step gap dir component adjacent extent end ray side tile parts plural value edge reached inner outer observed equal '
    'superset pattern transform join predecessor conflict distance equivalent class exposed boundary target mismatch '
    'source_distance weight shape steps walk enclosed candidate occurrence excess'.split())

INPUT_SLOTS = {
    'compose': ('Box', 'Box'), 'relative': ('Box', 'Box'), 'inside': ('Box', 'Box'), 'interior': ('Box', 'Box'),
    'dist_pair': ('Box',), 'diag_dist': ('Box',), 'corner_dist': ('Box',), 'split': ('Box',), 'sub_extent': ('Position',),
    'box_extent': ('Box', 'Position'), 'edge_inset': ('Number',), 'axis_inset': ('Number', 'Number'),
    'uniform_inset': ('Number',), 'edge_outset': ('Number',), 'axis_outset': ('Number', 'Number'),
    'uniform_outset': ('Number',), 'jump_offset': ('Number',), 'step_offset': (), 'neighbor': ('Box',),
    'jump': ('Box', 'Number'), 'apply': ('Box',), 'apply_dir': (), 'apply_diag_dir': (), 'apply_dir8': (),
    'same_dist': ('Box', 'Box'), 'same_line': ('Position', 'Position'), 'nearer': ('Position', 'Position'),
    'centered': ('Box',),
}
_SUPER = {'Position': 'Box', 'Offset': 'Box', 'Dir': 'Dir8', 'DiagDir': 'Dir8', 'Axis': 'Axis4', 'DiagAxis': 'Axis4',
          'Nat': 'Number', 'Int': 'Number'}
FOLLOWS_INSIDE = ('relative', 'same_dist', 'centered')
FOLLOWS_RELATIVE = ('compose', 'apply', 'centered')
REPEATS = ('neighbor', 'split', 'box_extent', 'nearer', 'same_dist', 'apply', 'dist_pair')
KINDS = {'lib': 0, 'derived': 1, 'op': 2}
GROUPS = ['DET', 'RULE depth 1', 'RULE depth 2', 'RULE depth 3+', 'INIT port', 'output']


def norm_type(t):
    return str(t).split('(')[0]


def _sub(a, b):
    while a:
        if a == b:
            return True
        a = _SUPER.get(a)
    return False


# ---- the scores of rows seen ----

SCORED_CAP = 4096  # rows whose scores a scorer keeps; the store is emptied past it


class Scored(dict):
    """{digest of a row's text: its scores}. The search draws the same atom start again under different paths, and each time writes a row
    with the same values; a model's scores are a function of the row alone, so the first answer stands for all of them."""

    def get_or(self, row, score):
        key = hashlib.blake2b(repr(row).encode(), digest_size=16).digest()
        got = self.get(key)
        if got is None:
            if len(self) >= SCORED_CAP:
                self.clear()
            got = self[key] = score(row)
        return got


# ---- the mask ----

def _mask_member(member, mode):
    """The masked form of a derived name whose member part (after the dot) is `member` ('' if none)."""
    return '&D.' + member if mode == 'group' and member in LIB_MEMBERS else '&D'


def _mask_ref(m, mode):
    """A derived relation as the prefix writes it ('&r2.box'): its slot stays (which relation it is), its name is masked."""
    member = m.group(0).partition('.')[2]
    return m.group(0).partition('.')[0] + ('.' + member if mode == 'group' and member in LIB_MEMBERS else '')


def mask_row(row, mode='all'):
    """A copy of the row with the author's derived names hidden (the options' and the prefix's; `clause` and `gold_atom` are
    dropped).  Kind, types, columns, tok, p and every other field stay.  A mode ending in '_nogrp' also empties `point_group`."""
    if mode == 'none':
        return row
    nogrp = mode.endswith('_nogrp')  # also hide the point group, which is set from gold's program
    mode = mode.removesuffix('_nogrp')
    out = {k: v for k, v in row.items() if k not in ('clause', 'gold_atom')}
    if nogrp:
        out['point_group'] = {}
    out['options'] = [dict(o, name=_mask_member((o.get('name') or '').partition('.')[2], mode)) if o.get('kind') == 'derived' else o
                      for o in row['options']]
    out['prefix'] = [DERIVED_REF.sub(lambda m: _mask_ref(m, mode), a) for a in row.get('prefix') or []]
    return out


# ---- struct ----
_rc = [None, None]


def row_cache(row, fn):
    if _rc[0] is not row:
        _rc[0], _rc[1] = row, {}
    c = _rc[1]
    if fn not in c:
        c[fn] = fn(row)
    return c[fn]


def _struct_row(row):
    scope = set(row['scope'])
    text = ' '.join(row['prefix'])
    prev = set(PREV.findall(text)) | set(re.findall(r'&r\d+', text))  # a derived relation is read when its slot is (suffix or not)
    slots = [int(o['tok'][2:]) for o in row['options'] if o['kind'] == 'derived' and o['tok'][2:].isdigit()]
    return scope, prev, row['k'] == 1


def f_struct(row, o):
    scope, prev, k1 = row_cache(row, _struct_row)
    ts = o.get('types') or []
    hit = sum(t in scope for t in ts)
    kind = o['kind']
    return {'lib': float(kind == 'lib'), 'derived': float(kind == 'derived'), 'op': float(kind == 'op'),
            'lib_k1': float(kind == 'lib' and k1), 'derived_k1': float(kind == 'derived' and k1), 'op_k1': float(kind == 'op' and k1),
            'in_scope': float(hit), 'in_scope_frac': hit / len(ts) if ts else 0.0,
            'none_in_scope': float(bool(ts) and hit == 0 and not k1), 'arity': float(len(ts)), 'repeat': float(o['tok'] in prev),
            'no_types': float(not ts)}


# ---- b ----

def _last_atom(row):
    prefix = row.get('prefix') or []
    return prefix[-1][1:].split(' ')[0].rstrip(')') if prefix and prefix[-1].startswith('(') else None


def _fits_made(row, last):
    prefix = row['prefix']
    for o in row.get('options') or []:
        if o.get('tok') == last and o.get('columns'):
            return {dict(zip(o['columns'], o['types'])).get(col) for col, _ in re.findall(r'\(:(\w+) \*(\w+)\)', prefix[-1])}
    return set()


def f_b(row, o):
    name = o.get('tok')
    if name not in INPUT_SLOTS:
        return {}
    scope = row.get('scope') or []
    ready = all(any(_sub(t, slot) for t in scope) for slot in INPUT_SLOTS[name])
    last = row_cache(row, _last_atom)
    d = {'b_ready': float(ready), 'b_boxpos': float(ready and 'Box' in scope and 'Position' in scope),
         'b_follows_crop': float(last == 'inside' and name in FOLLOWS_INSIDE),
         'b_follows_relative': float(last == 'relative' and name in FOLLOWS_RELATIVE),
         'b_repeat': float(last == name and name in REPEATS), 'b_fits_enum': 0.0, 'b_listed': 1.0}
    if last and (last.endswith('_elem') or last in ('axis_of', 'opposite', 'perp', 'diag_dirs')):
        made = row_cache(row, lambda r: _fits_made(r, last))
        d['b_fits_enum'] = float(any(_sub(m, t) for m in made if m for t in o.get('types') or []))
    return d


# ---- x and ctx ----

def _ctx(row):
    by = {o['tok']: o for o in row['options']}
    pn = set()
    for a in row.get('prefix') or []:
        for m in ATOM.finditer(a):
            if m.group(1):
                pn.add('NOT')
            s = m.group(2)
            if s.startswith('&r'):
                mm = re.match(r'&r\d+', s)
                od = by.get(mm.group(0)) if mm else None
                pn.add(od['name'] if od else s)
            else:
                pn.add(s)
    pg = row.get('point_group') or {}
    return dict(pnames=sorted(pn), scope=sorted({norm_type(t) for t in row.get('scope') or []}), grp=pg.get('point_group', '?'),
                k=min(row['k'], 4))


def f_cross(row, o):
    c = row_cache(row, _ctx)
    kind = o['kind']
    d = {'x:kk:%s:%d' % (kind, c['k']): 1.0, 'x:kg:%s:%s' % (kind, c['grp']): 1.0}
    nm = o['name'] if kind == 'derived' else o['tok']
    for p in c['pnames']:
        d['x:np:%s|%s' % (nm, p)] = 1.0
    for t in {norm_type(t) for t in o.get('types') or []}:
        for s in c['scope']:
            d['x:ts:%s|%s' % (t, s)] = 1.0
    return d


def f_tree_ctx(row, o):
    c = row_cache(row, _ctx)
    d = {'c_kind': float(KINDS[o['kind']] + 1), 'c_k': float(row['k']), 'c_phase': float(row.get('phase') == 'root2'),
         'c_grp': float(GROUPS.index(c['grp']) + 1 if c['grp'] in GROUPS else 0), 'c_nscope': float(len(c['scope'])),
         'c_arity': float(len(o.get('types') or []))}
    for t in {norm_type(t) for t in o.get('types') or []}:
        d['t_' + t] = 1.0
    for s in c['scope']:
        d['s_' + s] = 1.0
    return d


FEATURE_FUNCS = {'struct': f_struct, 'b': f_b, 'x': f_cross, 'ctx': f_tree_ctx}


BUILTIN = frozenset(FEATURE_FUNCS)


def name_filter(path):
    """A test of a feature name, from a file of names, one a line. A line that ends in * is a prefix. logp always passes. With no path, every name passes."""
    if not path:
        return lambda n: True
    lines = open(path).read().split()
    exact = {x for x in lines if not x.endswith('*')} | {'logp'}
    pre = tuple(x[:-1] for x in lines if x.endswith('*'))
    return lambda n: n in exact or n.startswith(pre)


def qualify(group, name):
    """A plugin's dense feature 'path' is 'dag.path' (so two sets can use one name); 'x:' names and built-in sets keep theirs."""
    return name if group in BUILTIN or name.startswith('x:') else group + '.' + name


def option_dicts(row, groups):
    """Per option: {feature: value} of the feature sets in `groups`, with 'logp' (log of P's share, floored at 1e-9) first."""
    out = []
    for o in row['options']:
        d = {'logp': math.log(max(o['p'], 1e-9))}
        for g in groups:
            for n, v in (FEATURE_FUNCS[g](row, o) or {}).items():
                if v and n != 'logp':
                    d[qualify(g, n)] = float(v)
        out.append(d)
    return out


def test_equal(rows):
    """Largest difference between this port and relfit.py / r14b on `rows` (unmasked); (struct, b)."""
    import sys
    sys.path.insert(0, __file__.rsplit('/', 1)[0])
    import numpy as np
    import relnet
    nsx, nbx = relnet.relfit_ns(False), relnet.relfit_ns(True)
    ds = db = 0.0
    for r in rows:
        X = nsx['features'](r)
        for i, o in enumerate(r['options']):
            if o['kind'] == 'derived':
                continue  # `repeat` of a derived option differs from relfit's by design (see _struct_row)
            mine = f_struct(r, o)
            ref = {n: float(v) for n, v in zip(nsx['NAMES'], X[i]) if n not in EXCLUDE and n != 'logp'}
            for n in set(mine) | set(ref):
                ds = max(ds, abs(mine.get(n, 0.0) - ref.get(n, 0.0)))
            rb = nbx['option_features'](r, o)
            mb = f_b(r, o)
            if rb is None:
                db = max(db, float(bool(mb)))
            else:
                ref = {'b_' + k: float(v) for k, v in rb.items()}
                ref['b_listed'] = 1.0
                for n in set(mb) | set(ref):
                    db = max(db, abs(mb.get(n, 0.0) - ref.get(n, 0.0)))
    return ds, db
