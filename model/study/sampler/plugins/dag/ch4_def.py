"""A choicecheap plugin: the features of ch3_def.py less ch3o on a row with no marks (dagset.view), with the facts of a stop row's finished atom taken out, and ch4o and ch4s."""
import collections
import os
import re
import sys

C = os.path.dirname(os.path.abspath(__file__))
S_ = os.path.dirname(os.path.dirname(C))
if S_ not in sys.path:
    sys.path.insert(0, S_)
sys.path.insert(0, C)
import choicefeat as cf  # noqa: E402
import dagset  # noqa: E402

TXT_L = re.compile(r'(?<![\w:&.])L(\d+)\b')


def dag_ctx(row):
    """choicefeat._ctx's keys on a row with no marks. A label's name V<i> holds the number of its token L<i>. A label's reads are its sites in the prefix less one. A label of the atom's
    text is new where the prefix doesn't hold it. Age and recency have no value here: first_at, last_at and rec_rank are constants, and info's age is 1 for a label of the prefix and 0 for a
    new one. `rank` is the count of options with higher p, so options of equal p tie."""
    pre, text = row.get('prefix') or [], row.get('text') or ''
    sites = collections.Counter(m.group(2) for a in pre for m in cf.CANON.finditer(a))
    created = ['V%d' % i for i in range(1 + max((int(x[1:]) for x in sites), default=-1))]
    reads = collections.Counter({x: c - 1 for x, c in sites.items()})
    stype = dict(zip(row.get('scope_labels') or [], row.get('scope_types') or []))
    rtypes = row.get('rtypes') or []
    cols = []
    for m in cf.TXT_COL.finditer(text):
        if text[:m.start()].count('(') - text[:m.start()].count(')') == 1:
            cols.append([int(m.group(1)), m.start(), len(text)])
    for a, b in zip(cols, cols[1:]):
        a[2] = b[1]
    named = [c[0] for c in cols]
    if row['phase'] in ('val', 'fval') and named:
        named = named[:-1]
    occ = collections.Counter(int(x) for x in TXT_L.findall(text))
    new = sorted(i for i in occ if 'V%d' % i not in sites)
    atype = {}
    for c, s, e in cols if row['phase'] != 'stop' else ():
        for x in TXT_L.findall(text[s:e]):
            if int(x) in new:
                atype.setdefault(int(x), rtypes[c] if c < len(rtypes) else None)
    refs = {i for i, n in occ.items() if i not in new or n > 1}
    labs = sorted({int(o['tok'][1:]) for o in row['options'] if o['kind'] == 'label'})
    types = list(stype.values()) + list(atype.values())
    info = {}
    for i in set(labs) | refs:
        nm = created[i] if i < len(created) else None
        info[i] = (1, 1, reads[nm], stype.get(nm)) if nm in sites else (0, 0, 0, atype.get(i))
    ps = [o['p'] for o in row['options']]
    ref_types = {info[i][3] for i in refs if info[i][3]}
    return dict(created=created, first_at=dict.fromkeys(created, 0), last_at=dict.fromkeys(created, 0), reads=reads, info=info, named=named, last=named[-1] if named else -1, refs=refs, labs=labs,
                types=types, ctype=row.get('ctype'), rtypes=rtypes, rank={o['tok']: sum(x > o['p'] for x in ps) for o in row['options']}, pos={o['tok']: i for i, o in enumerate(row['options'])},
                pmax=max(ps) if ps else 0.0, rec_rank=dict.fromkeys(labs, 0), ref_types=ref_types, nlab=len(labs), new=new, nfresh=len(new), nread=sum(occ.values()) - len(new))


cf._ctx = dag_ctx


def _no_last(fn, drop):
    """fn, less the keys that match drop at a stop row: at that row they read the finished atom, which is the last atom of one order."""
    pat = re.compile(drop)

    def at(row, o):
        d = fn(row, o) or {}
        return {k: v for k, v in d.items() if not pat.match(k)} if row['phase'] == 'stop' else d
    return at


F = {g: dagset.load(f'{C}/features/{g}.py', g + '_dag').FEATURE_FUNCS[g] for g in ('ch1b', 'ch1c', 'ch2d', 'ch2e', 'ch2f')}
F['ch1a'] = dagset.load(f'{C}/../ch3/features/ch1a.py', 'ch1a_dag').FEATURE_FUNCS['ch1a']
F['base'] = _no_last(cf.f_base, r'rel_|rk_|arity$|nnamed$|neg$|cur_col$')
F['cols'], F['val'] = cf.f_cols, cf.f_val
F['stop'] = _no_last(cf.f_stop, r'(a_arity|a_ncols|a_frac|a_known|new_labels|unread_new|unread_old|repeat_rel|last_reads_new)$')
F['ch1c'] = _no_last(F['ch1c'], r'c5_')
F['ch2d'] = _no_last(F['ch2d'], r'd4_nf|d4_nr|d4_pure_fresh|d4_newtype_|e7_has')
F['ch2e'] = _no_last(F['ch2e'], r'e2_|e3_unread_last|e3_unread_old|e7_neg_unread0')
F.update(dagset.load(f'{C}/features/ch4o.py', 'ch4o').FEATURE_FUNCS)
FEATURE_FUNCS = {g: dagset.on_view(fn) for g, fn in F.items()}
