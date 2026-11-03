"""Shared code of the tower read: pins, the walk, pattern, place, tower facts, the backoff models and their scoring, the bootstrap.

  tw_lib.py check      prints the pins and exits 1 on a mismatch
  tw_lib.py manifest   writes manifest.json

Design: /private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-tower-read-design/design.md
Imports ib_lib (the Ident read's code) by path and sets its pins to this design's pins.
"""
import collections
import gc
import hashlib
import importlib.util
import itertools
import json
import math
import os
import random
import sys
import time

R = os.path.dirname(os.path.abspath(__file__))
WS = '/Users/davidlu/code/arc-workspace'
STUDY = WS + '/work/lm/data-study'
# The Ident read whose code is reused. Its corpus rows (21,181) equal those of features-ident-block-read-heldout37-ramp22, form for form.
IB = STUDY + '/features-worker/results/features-ident-block-read-keyident-krc-heldout37-ramp22'
DAGO = STUDY + '/features-worker/results/features-dag-order-census-heldout37/features_dag_order.py'
DAGO_SHA = '676309d44cc28c71'
DESIGN = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-tower-read-design/design.md'
WALK_MD = STUDY + '/sampler/search-worker/chain-state/walk.md'

sys.dont_write_bytecode = True
sys.path.insert(0, IB)
import ib_lib as L  # noqa: E402

L.KIT = STUDY + '/sampler/sampler-worker/kits/sampler-pool-keyident-value-199853802'
L.SAMPLER_DIR = L.KIT + '/model/study/sampler'
L.MODELS = {'37': L.KIT + '/models-kr', 'ramp': L.KIT + '/models-krf', 'corpus': L.KIT + '/models-kr'}
L.MODEL_SHAS = {
    'models-kr/live_priors.pkl': '3c859731e9d875ce', 'models-kr/relR4_o.pkl': '3015d409597fff42',
    'models-kr/choice5_o.pkl': '686949ea5cc5a89f', 'models-kr/tilt_v1.json': 'ca858276d4713e92',
    'models-krf/live_priors.pkl': '7406dc3e810f5211', 'models-krf/relR4_o.pkl': '3015d409597fff42',
    'models-krf/choice5_o.pkl': '686949ea5cc5a89f', 'models-krf/tilt_v1.json': 'ca858276d4713e92',
}
L.SAMPLER_SHA = 'a5873bf24e00'
L.SETTINGS_ENV = dict(P_DAG='1', ORDER_FREE='col,tie,key', ARCLOG_IDENT_SOURCE='value', RAYON_NUM_THREADS='1', OMP_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
L.R = IB  # ib_lib.pins() reads IB/corpus-pin.json

KIT = L.KIT
SETTINGS_ENV = L.SETTINGS_ENV
KINDS = L.KINDS
NAME = L.NAME
MODES = ('EXTEND', 'BT1', 'BT2', 'BT3+', 'JUMP')
BANDS = ('BT1', 'BT2', 'BT3+')
MODE6 = ('EXTEND', 'BT1', 'BT2', 'BT3+', 'JUMP0', 'JUMP+')
NSEED_HELD = 16

_dago = None


def dago():
    """features_dag_order, imported by path after its sha256 matches."""
    global _dago
    if _dago is None:
        h = L.sha256(DAGO)
        if not h.startswith(DAGO_SHA):
            print('pin mismatch: features_dag_order.py sha256 %s' % h[:16], file=sys.stderr)
            sys.exit(1)
        spec = importlib.util.spec_from_file_location('features_dag_order', DAGO)
        _dago = importlib.util.module_from_spec(spec)
        sys.modules['features_dag_order'] = _dago
        spec.loader.exec_module(_dago)
    return _dago


# ------------------------------------------------------------------ pins

def pins():
    out = list(L.pins())
    out.append(('KEY_IDENT unset', 'KEY_IDENT' not in os.environ, os.environ.get('KEY_IDENT')))
    h = L.sha256(DAGO)
    out.append(('features_dag_order.py', h.startswith(DAGO_SHA), h[:16]))
    return out


def check_pins(verbose=False):
    ps = pins()
    if verbose:
        for name, ok, value in ps:
            print('%-4s %-28s %s' % ('ok' if ok else 'BAD', name, value))
    bad = [p for p in ps if not p[1]]
    if bad:
        print('pin mismatch: ' + ', '.join('%s=%s' % (n, v) for n, _, v in bad), file=sys.stderr)
        sys.exit(1)


def setup(engine=True):
    """Checks the pins. With engine, imports the sampler modules into ib_lib and returns live."""
    check_pins()
    dago()
    if engine:
        L.setup()
        return L.live
    return None


# ------------------------------------------------------------------ gold, shapes

def tasks_of(which):
    return {'37': L.held_tasks(), 'ramp': L.ramp_tasks(), 'held': L.held_tasks() + L.ramp_tasks(), 'corpus': L.corpus_stems()}[which]


def gold_forms(task):
    st = L.set_of(task)
    return L.forms_of(L.corpus_gold(task) if st == 'corpus' else L.held_gold()[task])


def kind_of(raw):
    return raw if raw in KINDS else 'OTHER'


def head_of(form):
    return dago().parse(form)[1]


def corpus_shape_rows():
    """stem -> {g: (kind, shape, holds)} from IB/corpus/rows-*.jsonl."""
    import glob
    out = collections.defaultdict(dict)
    for fn in sorted(glob.glob(IB + '/corpus/rows-*.jsonl')):
        for line in open(fn):
            x = json.loads(line)
            if 'stem' in x and 'g' in x:
                out[x['stem']][x['g']] = (x['kind'], x['shape'], x['holds'])
    return out


def held_shape_rows(task):
    """{g: (kind, shape, holds)} from R/shapes/T.json, or None."""
    fn = '%s/shapes/%s.json' % (R, task)
    if not os.path.exists(fn):
        return None
    return {x['g']: (x['kind'], x['shape'], x['holds']) for x in json.load(open(fn))}


# ------------------------------------------------------------------ the walk

def mode_of(reads_f, chain):
    """(mode band, d) of a form that reads reads_f, against the chain: EXTEND, BT1/BT2/BT3+ (d is the distance), or JUMP."""
    m = len(chain)
    if m and chain[-1] in reads_f:
        return 'EXTEND', 0
    for j in range(m - 2, -1, -1):
        if chain[j] in reads_f:
            d = m - 1 - j
            return BANDS[min(d, 3) - 1], d
    return 'JUMP', 0


def walk(forms, seed, theta=None, task='', dag=None):
    """The round-0 walk of walk.md (lambda = 1) over the gold forms. Returns the step records: the columns of walk.md plus
    walk_bits, _S (the placed set before the step) and _chain (the chain before the step). dag is the ProgramDag of the forms, if the caller has it. With theta, a function (state, cell) -> weight
    over all 20 cells, with state = (kind_h, m, chain_roots), the draw is P_theta over the cells that R holds and Z_t is their mass."""
    D = dago()
    dag = dag or D.ProgramDag(forms)
    keys = list(dag.lines)
    rng = random.Random('%d|%s' % (seed, D.short(''.join(sorted(dag.content[k] for k in keys)), 16)))
    S, chain, recs = set(), [], []
    all_cells = [(b, k) for b in MODES for k in KINDS]
    while len(S) < len(keys):
        ready = sorted((k for k in keys if k not in S and dag.parent_ids[k] <= S), key=dag.tie)
        cells = collections.defaultdict(list)
        rmodes = collections.Counter()
        for k in ready:
            band = mode_of(dag.parent_ids[k], chain)[0]
            cells[(band, kind_of(dag.kinds[k]))].append(k)
            rmodes[band] += 1
        ordered = sorted(cells)
        h = chain[-1] if chain else ''
        if theta is None:
            cell = ordered[rng.randrange(len(ordered))]
            z = len(ordered) / 20
        else:
            state = (kind_of(dag.kinds[h]) if h else '', len(chain), sum(1 for c in chain if not dag.parent_ids[c]))
            w = {c: theta(state, c) for c in set(all_cells) | set(ordered)}
            held = sum(w[c] for c in ordered)
            roll, cell = rng.random() * held, ordered[-1]
            for c in ordered:
                roll -= w[c]
                if roll < 0:
                    cell = c
                    break
            z = held / sum(w[c] for c in all_cells)
        f = cells[cell][rng.randrange(len(cells[cell]))]
        band, d = mode_of(dag.parent_ids[f], chain)
        recs.append(dict(
            task=task, seed=seed, round=0, t=len(S), key_f=f, key_h=h, m=len(chain), mode=band, d=d,
            kind_h=kind_of(dag.kinds[h]) if h else '', kind_f=kind_of(dag.kinds[f]), nR=len(ready),
            R_modes={b: rmodes.get(b, 0) for b in MODES}, n_reads=len(dag.parent_ids[f]),
            n_root_reads=sum(1 for p in dag.parent_ids[f] if not dag.parent_ids[p]), logw=0.0,
            walk_bits=math.log2(len(ordered)) + math.log2(len(cells[cell])), _S=frozenset(S), _chain=tuple(chain), _z=z))
        if band == 'EXTEND':
            chain.append(f)
        elif band == 'JUMP':
            chain = [f]
        else:
            chain = chain[:len(chain) - d] + [f]
        S.add(f)
    logw = sum(math.log2(r['_z']) for r in recs)
    for r in recs:
        r['logw'] = logw
        del r['_z']
    return recs


# ------------------------------------------------------------------ pattern, place, facts

PATTERNS = ['%s|%s|%s|%s|%s' % p for p in itertools.product(MODE6, ('0', '1+'), ('0', '1', '2+'), ('0', '1', '2+'), ('0', '1+'))]
PATTERN_INDEX = {p: i for i, p in enumerate(PATTERNS)}
assert len(PATTERNS) == 216


def band3(n):
    return '0' if n == 0 else '1' if n == 1 else '2+'


def pattern(rd, chain, S, dag):
    """The read pattern of a form that reads the set rd (forms of S), at the state (S, chain): mode6|stack_more|open|inner|roots."""
    band = mode_of(rd, chain)[0]
    mode6 = band if band != 'JUMP' else ('JUMP+' if rd else 'JUMP0')
    on = rd & set(chain)
    more = len(on) - (1 if band != 'JUMP' else 0)
    off = rd - on
    read_by = set()
    for s in S:
        read_by |= dag.parent_ids[s]
    n_open = sum(1 for x in off if x not in read_by)
    roots = sum(1 for x in rd if not dag.parent_ids[x])
    return '%s|%s|%s|%s|%s' % (mode6, '1+' if more >= 1 else '0', band3(n_open), band3(len(off) - n_open), '1+' if roots >= 1 else '0')


def pattern_of_text(text, S, chain, dag):
    """The pattern of a drawn clause: its reads are the scope heads that its text names."""
    return pattern({x for x in NAME.findall(text) if x in S}, chain, S, dag)


def place(dag, f):
    n = len(dag.parent_ids[f])
    if n == 0:
        return 'root'
    if n == 1:
        return 'chain step'
    return 'join' if dag.child_ids[f] else 'top join'


def mode_class(band):
    return 'EXTEND' if band == 'EXTEND' else 'JUMP' if band == 'JUMP' else 'BACKTRACK'


def bin_depth(n):
    return '0' if n == 0 else '1' if n == 1 else '2' if n == 2 else '3-5' if n <= 5 else '6+'


FACT_VALUES = {
    'n_present': ['0', '1-2', '3-5', '6-11', '12+'],
    'n_open': ['0', '1', '2', '3-4', '5+'],
    'ident_open': ['0', '1'],
    'maxdepth': ['-', '0', '1', '2', '3-5', '6+'],
    'h_kind': ['RULE', 'DET', 'INIT', 'other', 'none'],
    'h_ident': ['0', '1'],
    'h_nreads': ['0', '1', '2+'],
    'h_depth': ['-', '0', '1', '2', '3-5', '6+'],
    'prev': ['EXTEND', 'BT1', 'BT2', 'BT3+', 'JUMP', 'START'],
    'm_band': ['0', '1', '2', '3-4', '5+'],
    'chain_roots': ['0', '1', '2+'],
}
FACT_NAMES = list(FACT_VALUES)
FACT_INDEX = {k: {v: i for i, v in enumerate(vs)} for k, vs in FACT_VALUES.items()}


def facts_of(S, chain, prev, dag, holds):
    """The tower facts at a step, from S as a DAG, the kinds, holds and the walk so far. Reads no ready set and no text order."""
    read_by = set()
    for s in S:
        read_by |= dag.parent_ids[s]
    open_ = [s for s in S if s not in read_by]
    h = chain[-1] if chain else None
    hk = kind_of(dag.kinds[h]) if h else None
    return dict(
        n_present=L.bin_nscope(len(S)), n_open=L.bin_link_in(len(open_)), ident_open=str(int(any(holds.get(s) for s in open_))),
        maxdepth='-' if not S else bin_depth(max(dag.depths[s] for s in S)),
        h_kind='none' if h is None else hk if hk in ('RULE', 'DET', 'INIT') else 'other',
        h_ident=str(int(bool(h and holds.get(h)))), h_nreads=band3(len(dag.parent_ids[h])) if h else '0',
        h_depth=bin_depth(dag.depths[h]) if h else '-', prev=prev, m_band=L.bin_link_in(len(chain)),
        chain_roots=band3(sum(1 for c in chain if not dag.parent_ids[c])))


def annotate(dag, recs, holds):
    """Adds g-free per-step fields to the walk's records: facts, place, pattern, mode6. Drops _S and _chain."""
    prev = 'START'
    for r in recs:
        f, S, chain = r['key_f'], r['_S'], list(r['_chain'])
        r['facts'] = facts_of(S, chain, prev, dag, holds)
        r['place'] = place(dag, f)
        r['pattern'] = pattern(dag.parent_ids[f], chain, S, dag)
        prev = r['mode']
        del r['_S'], r['_chain']
    return recs


# ------------------------------------------------------------------ models

def I_ge1(shape):
    return int(shape is not None and L.i_ge1(shape))


def shape_part(shape):
    return L.within(shape)


M0_LEVELS = [('n_present', 'n_open', 'ident_open', 'maxdepth'), ('n_open', 'ident_open'), ('ident_open',), ()]
M1_LEVELS = [('h_kind', 'h_ident', 'h_nreads', 'h_depth', 'n_present', 'n_open', 'ident_open', 'maxdepth'),
             ('h_kind', 'h_ident', 'h_nreads', 'n_open', 'ident_open'), ('h_kind', 'h_ident', 'ident_open'), ('ident_open',), ()]


def _with_state(names, levels):
    return [tuple(names) + lv for lv in levels]


SHAPE_LEVELS = {
    'M0': M0_LEVELS,
    'M1': M1_LEVELS,
    'M2A': _with_state(('sA',), M1_LEVELS) + [()],
    'M2B': _with_state(('sB',), M1_LEVELS) + [()],
    'M2M': _with_state(('prev',), M1_LEVELS) + [()],
    'M3': _with_state(('prev', 'm_band', 'chain_roots'), M1_LEVELS) + [('prev',), ()],
}
PATTERN_LEVELS = {m: _with_state(('kind', 'I'), lv) + [('kind',), ()] for m, lv in SHAPE_LEVELS.items()}
TOWER_MODELS = list(SHAPE_LEVELS)
FS_MODELS = ('M2A', 'M2B')  # fit with the state permuted within each corpus walk
ALPHAS = (0.5, 2, 8, 32, 128)

KIND_VALUES = list(KINDS) + ['OTHER']
CARD = {k: len(v) for k, v in FACT_VALUES.items()} | {'kind': len(KIND_VALUES), 'I': 2, 'sA': 2, 'sB': 2}


def fold_of(stem):
    return int(hashlib.sha1(stem.encode()).hexdigest()[:8], 16) % 5


def columns(steps, shapes_index=None):
    """Integer columns of step dicts (each with facts, kind_f, shape or None, pattern): the facts, kind, I, sA, sB; y_shape, y_pat."""
    import numpy as np
    n = len(steps)
    cols = {name: np.fromiter((FACT_INDEX[name][s['facts'][name]] for s in steps), np.int64, n) for name in FACT_NAMES}
    cols['kind'] = np.fromiter((KIND_VALUES.index(s['kind_f']) for s in steps), np.int64, n)
    cols['I'] = np.fromiter((I_ge1(s['shape']) for s in steps), np.int64, n)
    set_state(cols)
    cols['y_pat'] = np.fromiter((PATTERN_INDEX[s['pattern']] for s in steps), np.int64, n)
    if shapes_index is not None:
        unseen = len(shapes_index)
        cols['y_shape'] = np.fromiter((shapes_index.get(s['shape'], unseen) for s in steps), np.int64, n)
    return cols


def set_state(cols):
    cols['sA'] = (cols['prev'] == FACT_INDEX['prev']['EXTEND']).astype('int64')
    cols['sB'] = (cols['prev'] <= FACT_INDEX['prev']['BT3+']).astype('int64')  # EXTEND, BT1, BT2, BT3+ are indices 0 to 3
    return cols


def level_keys(cols, levels):
    """Per level, the int64 key of the cell (a radix number of the level's columns)."""
    import numpy as np
    n = len(cols['prev'])
    out = []
    for names in levels:
        key = np.zeros(n, np.int64)
        for nm in names:
            key = key * CARD[nm] + cols[nm]
        out.append(key)
    return out


def _lookup(uk, uc, q):
    import numpy as np
    if len(uk) == 0:
        return np.zeros(len(q), np.int64)
    i = np.searchsorted(uk, q)
    i[i == len(uk)] = 0
    return np.where(uk[i] == q, uc[i], 0)


class Backoff:
    """Count tables along a chain of cells, each level smoothed toward the next coarser one:
    p_l(y|c) = (n_l(c,y) + alpha p_{l+1}(y|c')) / (n_l(c) + alpha), the last level toward (n(y)+.5)/(N+.5V)."""

    def __init__(self, V):
        self.V = V

    def fit(self, K, y, idx):
        import numpy as np
        yt = y[idx]
        self.N = len(yt)
        self.ny = np.bincount(yt, minlength=self.V)
        self.cell, self.joint = [], []
        for key in K:
            k = key[idx]
            self.cell.append(np.unique(k, return_counts=True))
            self.joint.append(np.unique(k * self.V + yt, return_counts=True))
        return self

    def score(self, K, y, idx, alpha):
        """Bits of y[idx] under the fit, at the cells K[l][idx]."""
        import numpy as np
        yt = y[idx]
        p = (self.ny[yt] + .5) / (self.N + .5 * self.V)
        for l in range(len(K) - 1, -1, -1):
            k = K[l][idx]
            nc = _lookup(*self.cell[l], k)
            nj = _lookup(*self.joint[l], k * self.V + yt)
            p = (nj + alpha * p) / (nc + alpha)
        return -np.log2(p)


def cv_alpha(K, y, V, folds):
    """(best alpha, mean CV bits at it, {alpha: mean bits}) by the 5 folds."""
    import numpy as np
    tot = {a: 0.0 for a in ALPHAS}
    for f in range(5):
        tr, te = np.nonzero(folds != f)[0], np.nonzero(folds == f)[0]
        b = Backoff(V).fit(K, y, tr)
        for a in ALPHAS:
            tot[a] += float(b.score(K, y, te, a).sum())
    n = len(y)
    best = min(ALPHAS, key=lambda a: tot[a])
    return best, tot[best] / n, {a: v / n for a, v in tot.items()}


# ------------------------------------------------------------------ bootstrap

def bootstrap_tasks(per_task, stat, n=2000, seed=0):
    """per_task: {task: vector of sums}; stat: function of a (draws, k) array of summed vectors -> (draws,) values.
    Returns (point, lo, hi): stat of all tasks, and the 2.5% and 97.5% points over n resamples of the tasks."""
    import numpy as np
    tasks = sorted(per_task)
    if not tasks:
        return None, None, None
    M = np.array([per_task[t] for t in tasks], float)
    point = float(stat(M.sum(0)[None, :])[0])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(tasks), size=(n, len(tasks)))
    vals = stat(M[idx].sum(1))
    vals = vals[np.isfinite(vals)]
    return point, float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


# ------------------------------------------------------------------ streaming helpers

def append_line(fh, obj):
    fh.write(json.dumps(obj, separators=(',', ':')) + '\n')
    fh.flush()


def read_lines(fn):
    if not os.path.exists(fn):
        return
    for line in open(fn):
        try:
            yield json.loads(line)
        except ValueError:
            continue


def gc_clean():
    gc.collect()


def draw_seed(task, key_f, i):
    return int(hashlib.sha1(('%s %s %d' % (task, key_f, i)).encode()).hexdigest()[:12], 16)


# ------------------------------------------------------------------ manifest

PREDICTIONS = {
    'state shares on the 37 (t>=1, seed 0)': 'EXTEND 45 to 60%, BACKTRACK 8 to 18%, JUMP 25 to 40%, JUMP0 12 to 20%; meaning A 45 to 60%, meaning B 60 to 75%. Ramp: EXTEND 40 to 55%, JUMP 30 to 45%',
    'transitions': 'P(EXTEND | prev = EXTEND) 55 to 70%, P(EXTEND | prev = JUMP) 35 to 55%',
    'bits per form on the 37': 'proposal mean 5 to 7, median 4 to 6; M0 3.6 to 4.6; M1 3.4 to 4.3; M2A 3.2 to 4.1; M2B .03 to .1 bits above M2A',
    'saving of M2A against the proposal on the 37': '1.5 to 3 bits per form, interval above 0; 60% or more of it in the pattern part',
    'source': 'set facts carry 75% or more of the saving; the last built .1 to .4 bits; the state .05 to .25 bits, interval above 0 on the 37 and including 0 on the ramp; M3 adds 0 to .15 bits over M2M',
    'by place (saving of M2A)': 'root 2 to 4 bits; chain step 1 to 2.5; join .5 to 1.5; top join 0 to 1.5, the smallest; chain steps hold the largest share of saved bits',
    'steps with h_joint = 0': '10 to 25%',
    'controls': 'read-time-shuffled gain -.1 to 0; fit-shuffled M2A within .03 of M1; spread of M2A bits per form over walk seeds <= .1; held bits <= CV bits + .4; mean walk_bits 1.5 to 2.5',
    'verdict on the 37': 'the saving holds and the state holds, but most of the saving comes from learned set conditioning, not from the state. The roots and the chain steps hold most of the saved bits',
}


def write_manifest(extra=None):
    m = dict(
        design=DESIGN, record=R, date=time.strftime('%Y-%m-%d %H:%M:%S'), walk_definition=WALK_MD + ' ("Walk", round 0)',
        kit=KIT, sampler_sha_prefix=L.SAMPLER_SHA, engine=L.ENGINE, engine_so_sha256=L.SO_SHA, python=L.PY + ' -u',
        models=dict(L.MODELS, note='the 37 use models-kr, the ramp uses models-krf, the corpus fit needs no models'), model_sha256_prefix16=L.MODEL_SHAS,
        settings=SETTINGS_ENV | {'KEY_IDENT': 'unset', 'STEER_COVER': 'unset'},
        held_gold=dict(path=L.HELD_GOLD, sha256_prefix=L.HELD_GOLD_SHA), ident_only_list=dict(path=L.IDENT_LIST, sha256_prefix=L.IDENT_LIST_SHA),
        corpus_gold=dict(path=L.CORPUS_GOLD, pin=IB + '/corpus-pin.json', stems='all less eval-tasks.txt (99) less ramp-fold.txt (22): 989'),
        corpus_shapes=IB + '/corpus/rows-*.jsonl',
        task_sets=dict(held=L.HELD_DIR + '/tasks.txt', ramp=L.HELD_DIR + '/ramp-fold.txt'),
        task_json=dict(held=KIT + '/data/tasks/<task>.json'),
        dag_order=dict(path=DAGO, sha256_prefix=DAGO_SHA), ident_read_code=IB,
        gold={'held': 'features-node-score-refit-loop/live-gold-r1/points-eval.json', 'corpus': 'pairs.jsonl.gz first row gold_sexp'},
        walk=dict(seeds_corpus=4, seeds_held=NSEED_HELD, lam=1, round=0),
        draws=dict(batch=32, cap=128, stop_hits=8, cpu_cap_s=45, deadline_s=20),
        predictions=PREDICTIONS,
    )
    m.update(extra or {})
    json.dump(m, open(R + '/manifest.json', 'w'), indent=1)
    return m


if __name__ == '__main__':
    if sys.argv[1:] == ['check']:
        check_pins(verbose=True)
    elif sys.argv[1:] == ['manifest']:
        write_manifest()
        print('wrote', R + '/manifest.json')
    else:
        sys.exit(__doc__)
