"""Pick tables for the reads of items 11 to 15, 18 and 19: a compact table of the pick rows of a part, from the walks of features_dagc_walk.py, with a resumable cache.

  import features_dagc_rows as RW
  T = RW.load('held-parents', 'off', kinds=('RULE',), seconds=20)       # reads what exists, resumes from scratch/mine/tab-*.pkl
  T.entries[(point, key)]  ->  dict(rec fields..., cnt)                # one entry per (point, pick key); key = RW.key_of(row)
  T.nok[point]             ->  the walks of the point that finished with ok
  RW.weight(T, e)          ->  cnt / nok: the weight of a pick, so each form weighs what one order weighs

The pick key is (task, line_id, form, scope_id, phase, atom, downset id), the key of the probe rows of features_dagc_probe.py. A (point, key) pair that several orders reach is one entry; it keeps the options and weights
of its first walk and counts the walks in `cnt` (`conf` counts later walks whose options or weights differ at 5 places). A frame that a running walker has not finished is ignored.
Nothing here reads gold's text, a form's place in gold's text or a mark. `gold_idx` is a label.
"""
import collections
import glob
import io
import json
import math
import os
import pickle
import time
import zlib

import numpy as np
import zstandard

np.seterr(all='ignore')  # Accelerate's matmul sets the flags on finite values

ME = os.path.dirname(os.path.abspath(__file__)) + '/'
CACHE = ME + 'scratch/mine/'
CLASS = {'relation': 'derived', 'lib relation': 'lib', 'relation macro': 'macro', 'fact relation': 'fact', 'NOT': 'NOT', 'CMP': 'comparison'}
REL_KINDS = ('relation', 'lib relation', 'relation macro', 'fact relation')
NAME, KIND, WGT, DEAD, OWN = range(5)
BANDS = ('empty', '1', '2', '3+')
HELD = set(open('/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/held/tasks.txt').read().split())


def walk_frames(path, skip=0):
    """(pick lines, form row) of each finished walk of a zst file after `skip` walks. A frame cut short by a running writer ends the stream."""
    if not os.path.exists(path):
        return
    n, buf = 0, []
    with open(path, 'rb') as f:
        try:
            for line in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True), encoding='utf8'):
                if not line.endswith('\n'):
                    return
                if line.startswith('{"rec": "form"'):
                    n += 1
                    if n > skip:
                        yield buf, json.loads(line)
                    buf = []
                elif n >= skip:
                    buf.append(line)
        except zstandard.ZstdError:
            return


def dsid_of(down):
    import features_dag_order as D
    return D.short('|'.join(sorted(down)), 12)


def key_of(d):
    return (d['task'], d['line_id'], d['form'], d['scope_id'], d['phase'], d['atom'], dsid_of(d['downset']))


def path_of(atom_id):
    return atom_id.split('|', 1)[0]


def conj_size(d):
    """The atoms of the downset in the pick's conjunction: in the pick atom's body or in a body that encloses it. A sibling branch of an OR is not in it."""
    q = path_of(d['atom'])
    return sum(1 for x in d['downset'] if q == path_of(x) or q.startswith(path_of(x) + '/'))


def band_of(d_depth, conj):
    """d_depth band of a pick: `empty` where D is empty in the pick's conjunction, else 1, 2 or 3+."""
    if conj == 0:
        return 'empty'
    return '1' if d_depth <= 1 else '2' if d_depth == 2 else '3+'


def compact(d, point):
    c = conj_size(d)
    g = d['gold_idx']
    return dict(point=point, task=d['task'], line_id=d['line_id'], form=d['form'], kind=d['kind'], scope_id=d['scope_id'], phase=d['phase'], atom=d['atom'], dsid=dsid_of(d['downset']), d_depth=d['d_depth'], dsize=d['dsize'], conj=c,
                band=band_of(d['d_depth'], c), place=d['place'], under=d['under'], gold_idx=g, q_bits=d['q_bits'], opts=d['opts'], nscope=d['nscope'], order_id=d['order_id'], downset=d['downset'],
                n_atoms=d.get('nsize'))


def cls_of(e):
    """The class of gold's option: own, derived, lib, macro, fact, NOT, comparison; None where gold is not among the options."""
    g = e['gold_idx']
    if g is None:
        return None
    o = e['opts'][g]
    if o[OWN] and o[KIND] in REL_KINDS:
        return 'own'
    return CLASS[o[KIND]]


def gold_alive(e):
    g = e['gold_idx']
    return g is not None and not e['opts'][g][DEAD]


class Table:
    def __init__(self):
        self.entries = {}
        self.nok = collections.Counter()
        self.walks = []  # per walk: dict(point, order_idx, ok, total, kind, ...)
        self.done = {}  # file -> walks consumed
        self.conf = 0
        self.sig = None

    def points(self):
        return self.nok


def weight(T, e):
    return e['cnt'] / max(T.nok[e['point']], 1)


def _load_file(f, name, kinds, tasks, seconds, parts, t0, compactor=None):
    """The table of one walks file, cached per file. The cache holds the signature of the file's first walk: a file that a rewalk replaced is read again from its start."""
    path = CACHE + 'tab-%s-%s.pkl' % (name, os.path.basename(f))
    T = None
    if os.path.exists(path):
        T = pickle.load(open(path, 'rb'))
    sig = None
    for _rows, fm in walk_frames(f):
        sig = (fm['point'], fm['order_idx'], fm['order_id'], fm['seconds'], fm['total'])
        break
    if T is not None and T.sig != sig:
        T = None
    if T is None:
        T = Table()
        T.sig = sig
    skip = T.done.get(f, 0)
    n = 0
    for rows, fm in walk_frames(f, skip):
        if seconds and time.time() - t0 > seconds:
            break
        n += 1
        if tasks is not None and fm['task'] not in tasks:
            continue
        w = dict(point=fm['point'], order_idx=fm['order_idx'], ok=fm['ok'], total=fm.get('total'), kind=fm['kind'], task=fm['task'], line_id=fm['line_id'], scope_id=fm['scope_id'], form=fm['form'], seconds=fm.get('seconds'), picks=fm.get('picks'), nscope=fm.get('nscope'))
        if parts:
            w['parts'] = fm.get('parts')
        T.walks.append(w)
        if not fm['ok'] or fm['kind'] not in kinds:
            continue
        T.nok[fm['point']] += 1
        seen = set()
        for line in rows:
            d = json.loads(line)
            k = key_of(d)
            if k in seen:
                continue
            seen.add(k)
            e = T.entries.get((fm['point'], k))
            if e is None:
                c = (compactor or compact)(d, fm['point'])
                if c is None:
                    continue
                c['cnt'] = 1
                c['key'] = k
                T.entries[(fm['point'], k)] = c
            else:
                e['cnt'] += 1
                if 'opts' in e and (len(e['opts']) != len(d['opts']) or any(a[0] != b[0] or abs(a[2] - b[2]) > 1e-5 for a, b in zip(e['opts'], d['opts']))):
                    T.conf += 1
    T.done[f] = skip + n
    if n:
        tmp = path + '.tmp'
        pickle.dump(T, open(tmp, 'wb'), protocol=4)
        os.replace(tmp, path)
    return T


def load(part, steers, kinds=('RULE',), tasks=None, seconds=None, parts=False, tag='', shards=None, compactor=None):
    """The table of a part and a steer, from walks/PART-STEERS-*.jsonl.zst, merged over the files. kinds: kinds of forms whose picks are kept (every walk counts for `walks`). tasks: a set of tasks to keep, or None for all."""
    os.makedirs(CACHE, exist_ok=True)
    name = '%s-%s-%s%s%s' % (part, steers, ''.join(k[0] for k in kinds), tag, '' if tasks is None else '-t%08x' % zlib.crc32(','.join(sorted(tasks)).encode()))
    files = sorted(glob.glob(ME + 'walks/%s-%s-*of*.jsonl.zst' % (part, steers)))
    if shards is not None:
        files = [f for f in files if int(os.path.basename(f).rsplit('-', 1)[1].split('of')[0]) in shards]
    t0 = time.time()
    T = Table()
    T.files = {}
    for f in files:
        t = _load_file(f, name, kinds, tasks, seconds, parts, t0, compactor)
        T.entries.update(t.entries)
        T.nok.update(t.nok)
        T.walks += t.walks
        T.conf += t.conf
        T.files[os.path.basename(f)] = t.done[f]
    return T


_DRAWS = {}


def boot(num, den, tasks, mask=None, B=10000, seed=0):
    """(ratio of sums, 2.5%, 97.5%) by resampling tasks. num, den, tasks are arrays of one entry per pick."""
    num, den, tasks = np.asarray(num, float), np.asarray(den, float), np.asarray(tasks)
    if mask is not None:
        num, den, tasks = num[mask], den[mask], tasks[mask]
    if len(num) == 0 or den.sum() <= 0:
        return (float('nan'),) * 3
    u, inv = np.unique(tasks, return_inverse=True)
    a, c = np.bincount(inv, num, len(u)), np.bincount(inv, den, len(u))
    key = (len(u), B, seed)
    if key not in _DRAWS:
        _DRAWS[key] = np.random.RandomState(seed).multinomial(len(u), [1.0 / len(u)] * len(u), B).astype(float)
    W = _DRAWS[key]
    d = W @ c
    with np.errstate(all='ignore'):
        r = (W @ a)[d > 0] / d[d > 0]
    return float(a.sum() / c.sum()), float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))


def fmt3(t, d=3):
    return '%+.*f (%+.*f to %+.*f)' % (d, t[0], d, t[1], d, t[2])


def quart(v):
    if len(v) == 0:
        return [None] * 3
    q = np.percentile(np.asarray(v, float), [25, 50, 75])
    return [round(float(x), 1) for x in q]


def form_bits(steers, part, path=ME + 'form-bits-dag.tsv'):
    """{(task, line_id, scope_id): bits_mean} of form-bits-dag.tsv for a steer and part."""
    out = {}
    with open(path) as f:
        head = f.readline().rstrip('\n').split('\t')
        ix = {h: i for i, h in enumerate(head)}
        for line in f:
            r = line.rstrip('\n').split('\t')
            if r[ix['steers']] == steers and r[ix['part']] == part:
                out[r[ix['task']], int(r[ix['line_id']]), r[ix['scope_id']]] = float(r[ix['bits_mean']])
    return out


def table_md(head, rows):
    out = ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    out += ['| ' + ' | '.join(str(c) for c in r) + ' |' for r in rows]
    return '\n'.join(out) + '\n'
