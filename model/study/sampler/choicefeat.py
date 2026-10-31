"""choicefeat: the feature functions of choicecheap, the mask, and the runtime scorer of its models (the steer of sample2_choice.py).
Imports relfeat (pure Python); the Scorer also needs numpy and sklearn (to unpickle the tree).

A feature function is  fn(row, option) -> {name: float};  `row` is a masked choice row, `option` one of row['options'].
A plugin file (choicecheap --plugin f.py) defines  FEATURE_FUNCS = {'set': fn}  and a model uses it by listing 'set' in --feats; a
plugin's dense name 'path' becomes 'set.path'.  A field a row may lack is read with .get.  context(row) gives the parsed row (below).
Built-in sets: base (every option: logp, kind, phase, k, relation, position among the options), cols (a column option or the
stop at a column), val (a value, field or operand option: label recency, type match), stop (the atom stop: the finished atom, the
labels nothing reads).

A choice row is one pick of a clause's atom after its relation: phase cols (a column, or STOP at a column), fcol (a field of a
record column, or END), val (a value of a column), fval (a value of a field), op (an operand of a comparison).
  k          the atom's index in the clause, from 1
  phase      as above; and 'atom stop' (the mask calls it 'stop'): the hazard decision after atom k, options STOP and GO, p P's hazard
  neg        whether the atom is a NOT atom
  rel        the relation: its lib name, 'declared' for a derived relation, or 'cmp:Ne' etc. for a comparison
  rkind      the decoder's kind of the relation: 'lib relation', 'relation macro', 'fact relation', 'relation' (derived); null for a comparison
  col        val: the lib column's name, else null (always null for a derived relation)
  ctype      val, fval: the type of the column (of the field, for fval) the value fills, null where unknown
  rtypes     the types of the relation's columns by column position, null where unknown; null in a position with no column. A derived
             relation's has one entry for each column token, and 'Record' for a record column
  text       the atom so far.  Column tokens are positions: '(neighbor (:0 L1) (:1 *L2) (:4'; a label is L<i>, i the order in which
             the clause made it (a fresh label is '*L<i>'); a record column holds '(:0 (:0 L3)'
  prefix     the clause's atoms before atom k, as strings
  scope_labels, scope_types   the labels the prefix made and their types, aligned by index (null at k = 1)
  options    per option: tok, kind, p (P's share) and, for a column option of phase cols, ctype (the column's type), name (a lib
             relation's column name, null for a derived one) and key (whether that name is 'key', null for a derived relation).
             kinds: column (':3'), stop (tok STOP, at a column), end (END), fresh ('*'), zero ('0'), label ('L2')
             The STOP option of a column pick is there only where the atom may end (P's share of it is the atom's stop chance at that column).
An atom stop row is of the finished atom: text is its whole text, prefix and scope_labels/scope_types include it (the labels it made are
  the last '*' of the prefix), rel and rkind/rtypes are its relation's, arity is the relation's number of columns (null where unknown), ncols
  the number of columns the atom names, and the options are STOP and GO (P's hazard and its complement).
  point_group  {'kind': 'RULE', 'DET' or 'INIT'}, the head of the clause being drawn (INIT for a port; a RULE that OUT reads is a 'RULE')
  prior_uses the earlier atoms of the relation, oldest first: those of the program's earlier clauses, then those of the clause's atoms
             before this one (an atom stop's leave out the finished atom); [] for a comparison.  Per atom: {'same_clause': bool, 'cols':
             {':3': 'fresh' | 'read' | 'zero' | 'rec'}}, one entry for each column the atom names: a * (or ^) label, a label, 0, a record
A row from CHOICE_ROWS also has gold, task, case, point and gold_atom; the mask drops them.

mask_row(row) is what a feature sees.  It keeps only: k, phase, neg, rel, rkind, col, ctype, rtypes, text, prefix, scope_labels,
scope_types, arity, ncols, point_group (only its kind), prior_uses, options (tok, kind, p, ctype, name, key).  So it hides: gold, gold_atom,
clause, task, case, point, and any other field of an old row's point_group (the group, output, depth, d_out).  In what it keeps it hides the
author's names (prior_uses has none):
  derived relations   in the prefix '&r2.box' becomes '&r2'; a derived atom's column names become '_' ('(:key ...' -> '(:_ ...')
  label names         V0, V1, ... in the order the prefix first makes them with '*'; scope_labels takes the same names
  types               normalised to the name before '(' ('Pose(...)' -> 'Pose')
The label with token L<i> is the i-th '*' in the prefix, then in the text: its name is V<j> where V<j> is the name of the i-th '*'
of the prefix, and its type is scope_types[scope_labels.index('V<j>')].  A label made in this atom (i beyond the prefix's) takes
the type of the column it fills, rtypes[column position].  context(row) gives these.
"""
import collections
import importlib.util
import math
import os
import pickle
import re
import sys

import numpy as np

import relfeat

PHASES = ('cols', 'fcol', 'val', 'fval', 'op', 'stop')  # the phases a model can score
DEFAULT_PHASES = ('cols', 'fcol', 'val', 'fval', 'op')
KEEP_ROW = ('k', 'phase', 'neg', 'rel', 'rkind', 'col', 'ctype', 'rtypes', 'text', 'prefix', 'scope_labels', 'scope_types', 'arity', 'ncols',
            'prior_uses', 'options')
KEEP_OPT = ('tok', 'kind', 'p', 'ctype', 'name', 'key')
KINDS = ('column', 'stop', 'end', 'fresh', 'zero', 'label')
RKINDS = {'lib relation': 'lib', 'relation macro': 'macro', 'fact relation': 'fact', 'relation': 'declared'}
STAR_NAME = re.compile(r'\*([A-Za-z_]\w*)')
LABEL_TOK = re.compile(r'(?<![\w:&.])(\*?)([A-Za-z_]\w*)(?![\w.])')
DERIVED_ATOM = re.compile(r'^\((?:NOT \()?&r')
DERIVED_COL = re.compile(r'\(:[A-Za-z_]\w*')
CANON = re.compile(r'(\*?)\b(V\d+)\b')
TXT_REF = re.compile(r'(?<![\w*])L(\d+)\b')
TXT_NEW = re.compile(r'\*L(\d+)\b')
TXT_COL = re.compile(r'\(:(\d+)')


def phase_of(row):
    """The phase's name in the masked row and in a model's phases: 'stop' for the atom stop."""
    return 'stop' if row['phase'] == 'atom stop' else row['phase']


def nt(t):
    return None if t is None else relfeat.norm_type(t)


# ---- the mask ----

def mask_row(row):
    """The row a feature sees (see the module docstring)."""
    pre = row.get('prefix') or []
    order = []
    for a in pre:
        for m in STAR_NAME.finditer(a):
            if m.group(1) not in order:
                order.append(m.group(1))
    for n in row.get('scope_labels') or []:
        if n not in order:
            order.append(n)
    cmap = {n: 'V%d' % i for i, n in enumerate(order)}

    def rename(a):
        a = relfeat.DERIVED_REF.sub(lambda m: relfeat._mask_ref(m, 'all'), a)
        if DERIVED_ATOM.match(a):
            a = DERIVED_COL.sub('(:_', a)
        return LABEL_TOK.sub(lambda m: m.group(1) + cmap.get(m.group(2), m.group(2)), a)
    derived = row.get('rel') == 'declared'
    out = {k: row.get(k) for k in KEEP_ROW}
    out['phase'] = phase_of(row)
    out['neg'] = bool(row.get('neg'))
    out['prefix'] = [rename(a) for a in pre]
    out['point_group'] = {'kind': (row.get('point_group') or {}).get('kind')}
    sl = row.get('scope_labels')
    out['scope_labels'] = [cmap[n] for n in sl] if sl is not None else None
    out['scope_types'] = [nt(t) for t in row.get('scope_types') or []]
    out['ctype'] = nt(row.get('ctype'))
    out['rtypes'] = [nt(t) for t in row['rtypes']] if row.get('rtypes') else None
    if derived:
        out['col'] = None
    out['options'] = [dict({k: o.get(k) for k in KEEP_OPT}, ctype=nt(o.get('ctype')),
                           **(dict(name=None, key=None) if derived else {})) for o in row['options']]
    return out


# ---- the parsed row ----

def _ctx(row):
    pre, text, k = row.get('prefix') or [], row.get('text') or '', row['k']
    created, first_at, last_at, reads = [], {}, {}, collections.Counter()
    for t, a in enumerate(pre, 1):
        for m in CANON.finditer(a):
            nm = m.group(2)
            if m.group(1):
                created.append(nm)
                first_at.setdefault(nm, t)
            else:
                reads[nm] += 1
            last_at[nm] = t
    stype = dict(zip(row.get('scope_labels') or [], row.get('scope_types') or []))
    rtypes = row.get('rtypes') or []
    cols = []  # (position, text of the column) of the atom's top-level columns so far
    for m in TXT_COL.finditer(text):
        if text[:m.start()].count('(') - text[:m.start()].count(')') == 1:
            cols.append([int(m.group(1)), m.start(), len(text)])
    for a, b in zip(cols, cols[1:]):
        a[2] = b[1]
    named = [c[0] for c in cols]
    if row['phase'] in ('val', 'fval') and named:
        named = named[:-1]  # the last column is the one being filled
    atype = {}  # label made in this atom -> its column's type
    for c, s, e in cols if row['phase'] != 'stop' else ():  # a stop row's prefix holds the atom's labels already
        for m in TXT_NEW.finditer(text[s:e]):
            atype[int(m.group(1))] = rtypes[c] if c < len(rtypes) else None
    refs = {int(x) for x in TXT_REF.findall(text)}
    labs = sorted({int(o['tok'][1:]) for o in row['options'] if o['kind'] == 'label'})
    types = list(stype.values()) + list(atype.values())
    ps = [o['p'] for o in row['options']]
    order = sorted(range(len(ps)), key=lambda i: -ps[i])
    rank = {row['options'][i]['tok']: r for r, i in enumerate(order)}
    ctype = row.get('ctype')
    info = {}  # label index -> (age, since last mention, reads, type)
    for i in labs:
        nm = created[i] if i < len(created) else None
        if nm is None:
            info[i] = (0, 0, 0, atype.get(i))
        else:
            info[i] = (k - first_at[nm], k - last_at[nm], reads[nm], stype.get(nm))
    for i in refs:
        if i not in info and i < len(created):
            nm = created[i]
            info[i] = (k - first_at[nm], k - last_at[nm], reads[nm], stype.get(nm))
    ref_types = {info[i][3] for i in refs if i in info and info[i][3]}
    return dict(created=created, first_at=first_at, reads=reads, info=info, named=named, last=named[-1] if named else -1, refs=refs, labs=labs, types=types,
                ctype=ctype, rtypes=rtypes, rank=rank, pos={o['tok']: i for i, o in enumerate(row['options'])},
                pmax=max(ps) if ps else 0.0, rec_rank={i: r for r, i in enumerate(sorted(labs, key=lambda i: info[i][1]))},
                ref_types=ref_types, nlab=len(labs))


def context(row):
    return relfeat.row_cache(row, _ctx)


def compat(a, b):
    return a is not None and b is not None and (a == b or relfeat._sub(a, b) or relfeat._sub(b, a))


def n_in_scope(c, t):
    return sum(compat(t, x) for x in c['types'])


# ---- features ----

def f_base(row, o):
    c = context(row)
    n = len(row['options'])
    i = c['pos'][o['tok']]
    lp = math.log(max(o['p'], 1e-9))
    rel = row.get('rel') or ''
    d = {'dlogp': lp - math.log(max(c['pmax'], 1e-9)), 'rank': float(c['rank'][o['tok']]), 'pos': float(i), 'pos_frac': i / n,
         'nopt': float(n), 'k': float(row['k']), 'k1': float(row['k'] == 1), 'ph_' + row['phase']: 1.0, 'k_' + o['kind']: 1.0,
         'rk_' + (RKINDS.get(row.get('rkind')) or ('cmp' if rel.startswith('cmp:') else 'declared' if rel == 'declared' else 'lib')): 1.0,
         'rel_' + rel: 1.0, 'nnamed': float(len(c['named'])), 'cur_col': float(c['last']), 'nscope': float(len(c['types'])),
         'arity': float(len(c['rtypes'])), 'neg': float(bool(row.get('neg')))}
    if row.get('col'):
        d['rcn_' + row['col']] = 1.0
    if c['ctype']:
        d['rc_' + c['ctype']] = 1.0
        d['rc_in_scope'] = float(n_in_scope(c, c['ctype']))
    return d


def f_cols(row, o):
    if row['phase'] not in ('cols', 'fcol'):
        return {}
    c = context(row)
    rt = c['rtypes']
    named = set(c['named'])
    left = [j for j in range(len(rt)) if j not in named]
    d = {'left': float(len(left)), 'left_in_scope': float(sum(n_in_scope(c, rt[j]) > 0 for j in left if rt[j])),
         'left_known': float(sum(rt[j] is not None for j in left))}
    if o['kind'] == 'stop':
        d['is_stop'] = 1.0
    if o['kind'] == 'column':
        j = int(o['tok'][1:])
        t = o.get('ctype')
        d.update(col=float(j), col_rel=float(j - c['last']), back=float(j <= c['last']), named=float(j in named),
                 gap=float(j - c['last'] - 1))
        if o.get('name'):
            d['cn_' + o['name']] = 1.0
        if o.get('key') is not None:
            d['key'] = float(o['key'])
        if t:
            d['oc_' + t] = 1.0
            d['oc_in_scope'] = float(n_in_scope(c, t))
            d['oc_exact'] = float(sum(x == t for x in c['types']))
            d['oc_named'] = float(sum(rt[x] == t for x in named if x < len(rt)))
        else:
            d['oc_unknown'] = 1.0
    return d


def f_val(row, o):
    if row['phase'] not in ('val', 'fval', 'op'):
        return {}
    c = context(row)
    ct = c['ctype']
    d = {'nlab': float(c['nlab'])}
    if o['kind'] == 'column':
        d['field_col'] = float(o['tok'][1:])
    if o['kind'] != 'label':
        return d
    i = int(o['tok'][1:])
    age, rec, reads, lt = c['info'].get(i, (0, 0, 0, None))
    d.update(lidx=float(i), lnewest=float(i == c['labs'][-1]), lfrom_newest=float(c['labs'][-1] - i), lage=float(age), lrec=float(rec),
             lrec_rank=float(c['rec_rank'][i]), lreads=float(reads), lunread=float(reads == 0 and i not in c['refs']),
             lin_text=float(i in c['refs']), lthis_atom=float(age == 0), ltype_known=float(lt is not None),
             lsame_type=float(sum(x == lt for x in c['types'])) if lt else 0.0)
    if lt:
        d['lt_' + lt] = 1.0
    if ct and lt:
        d['tmatch'] = 1.0 if lt == ct else -1.0
        d['tcompat'] = 1.0 if compat(lt, ct) else -1.0
    if row['phase'] == 'op' and c['ref_types'] and lt:
        d['op_match'] = 1.0 if lt in c['ref_types'] else -1.0
    return d


def f_stop(row, o):
    if row['phase'] != 'stop':
        return {}
    c = context(row)
    pre = row.get('prefix') or []
    names = set(c['created'])
    unread = [n for n in names if c['reads'][n] == 0]
    last = len(pre)
    new = [n for n in names if c['first_at'][n] == last]
    heads = [a[1:].split(' ')[0] for a in pre if a.startswith('(') and not a.startswith('(NOT')]
    ar = row.get('arity')
    d = {'is_stop': float(o['tok'] == 'STOP'), 'a_ncols': float(row.get('ncols') or 0), 'a_arity': float(ar or 0),
         'a_frac': (row.get('ncols') or 0) / ar if ar else 0.0, 'a_known': float(bool(ar)),
         'unread': float(len(unread)), 'unread_frac': len(unread) / len(names) if names else 0.0, 'unread_new': float(sum(n in new for n in unread)),
         'unread_old': float(len(unread) - sum(n in new for n in unread)), 'new_labels': float(len(new)), 'nlabels': float(len(names)),
         'natoms_derived': float(sum(h.startswith('&r') for h in heads)), 'nneg': float(sum(a.startswith('(NOT') for a in pre)),
         'distinct_rels': float(len(set(heads))), 'repeat_rel': float(len(heads) > 1 and heads[-1] in heads[:-1]),
         'last_reads_new': float(any(c['reads'][n] > 0 for n in new))}
    return d


FEATURE_FUNCS = {'base': f_base, 'cols': f_cols, 'val': f_val, 'stop': f_stop}
BUILTIN = frozenset(FEATURE_FUNCS)


def qualify(group, name):
    return name if group in BUILTIN else group + '.' + name


def option_dicts(row, groups):
    """Per option of a masked row: {feature: value} of the feature sets in `groups`, with 'logp' (log of P's share, floored at 1e-9)."""
    out = []
    for o in row['options']:
        d = {'logp': math.log(max(o['p'], 1e-9))}
        for g in groups:
            for n, v in (FEATURE_FUNCS[g](row, o) or {}).items():
                if v and n != 'logp':
                    d[qualify(g, n)] = float(v)
        out.append(d)
    return out


# ---- the runtime scorer ----

def one_thread():
    """One OpenMP thread in every loaded library (a draw worker is one process; see relsteer.one_thread)."""
    try:
        from threadpoolctl import threadpool_limits
        threadpool_limits(limits=1)
    except ImportError:
        pass


def load_plugin(path):
    spec = importlib.util.spec_from_file_location('choicecheap_plugin', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    FEATURE_FUNCS.update(mod.FEATURE_FUNCS)


class Scorer:
    """sc = Scorer('/path/choice.pkl');  f = sc.f(row)  ->  list[float], one per row['options']: the model's score minus log(P's share);
    a steer multiplies weight i by exp(beta * f[i]).  row: a choice row as the sampler writes it (the mask is applied here)."""

    def __init__(self, path):
        with open(path, 'rb') as f:
            ck = pickle.load(f)
        one_thread()
        m = ck['hgb']
        self.groups, self.model, self.beta = m['groups_used'], m['model'], m['beta']
        self.phases = frozenset(ck.get('phases') or DEFAULT_PHASES)  # the phases the model was trained on
        if ck.get('plugin') and any(g not in FEATURE_FUNCS for g in self.groups):
            load_plugin(os.path.join(os.path.dirname(os.path.abspath(__file__)), ck['plugin']))
        self.col = {n: j for j, n in enumerate(m['names'])}
        self.nd = len(self.col)

    def f(self, row):
        row = mask_row(row)
        ds = option_dicts(row, self.groups)
        X = np.zeros((len(ds), self.nd), np.float32)
        col = self.col
        for i, d in enumerate(ds):
            for n, v in d.items():
                j = col.get(n)
                if j is not None:
                    X[i, j] = v
        return (self.beta * self.model.decision_function(X) - np.array([d['logp'] for d in ds])).tolist()
