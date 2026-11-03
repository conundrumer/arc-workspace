"""What reading a kept prefix costs at the relation pick of stage 2, and what the live prefix score returns there. For each stage split: the prior's bits and rank for the kept prefix at the first relation pick, the uniform pick's bits, and the rank of the read atom among the task's one-atom junk prefixes by log chance, then with beta times the score.

  features_stage2_read_cost.py OUT.jsonl TWO_STAGE_BITS MISS_CASES HELD_ROWS    from a kit's top folder
"""
import collections, glob, gzip, json, math, os, pickle, sys, tempfile
import numpy as np
import live, live_try, or_q, search, search_gold as G, superdag as D
from nodefeat import Pair
import features_prefix_score as SC
out, two, miss, held = sys.argv[1:5]
BETAS = (2., 4.)
specs = {x['task']: x['gold_sexp'] for x in json.load(open('points-eval.json'))}
cases = {(c['task'], c['form']): c for c in map(json.loads, open(miss))}
sampler = live.Sampler(os.environ['SEARCH_MODELS'])
tmp = tempfile.mkdtemp()
done = {(r['task'], r['form'], r['split']) for r in map(json.loads, open(out))} if os.path.exists(out) else set()
SC.install()
st = dict(rel=None, first=None, pairs=None)
o_pick, o_table = or_q.GuidedDrawer.pick, live.Run.table


def pick(self, opts, weights):
    o, q = o_pick(self, opts, weights)
    f = sys._getframe(1)
    while f is not None and f.f_code.co_name != 'atom':
        f = f.f_back
    if st['rel'] is None and f is not None and f.f_locals['n'].phase in ('root', 'root2'):
        w = {x: float(y) for x, y in zip(opts, weights)}; s = sum(w.values()); g = w.get(o, 0)
        st['rel'] = dict(n=len(opts), live=sum(v > 0 for v in w.values()), bits=-math.log2(g / s) if g > 0 else None, rank=1 + sum(v > g for v in w.values()))
    return o, q


def table(self, fr, dec, pg):
    got = o_table(self, fr, dec, pg)
    if got[0] is not None and st['first'] is None:
        up = sys._getframe(1)
        while up is not None and up.f_code.co_name != 'body':
            up = up.f_back
        if up is not None and up.f_locals.get('kind') == 'RULE':
            at = list(up.f_locals.get('text') or []) + ([up.f_locals['res'][3]] if up.f_locals.get('res') else [])
            if len(at) == 1:
                st['first'] = SC.score(got[0], dict(run=self, pairs=st['pairs'], text=at, atoms=1))
    return got


or_q.GuidedDrawer.pick, live.Run.table = pick, table
JUNK = {}


def junk(task):
    if task in JUNK:
        return JUNK[task]
    b = SC.bundle(); ix = b['ix']; rows = {}
    for f in glob.glob(f'{held}/{task}.*.pkl.gz'):
        with gzip.open(f, 'rb') as g:
            r = pickle.load(g)
        for x in r['rows']:
            if x['src'] == 'search' and x['place'] == 'RULE' and x['atoms'] == 1 and x['logq'] is not None:
                rows.setdefault(tuple(x['sigs']), x)
    rows = list(rows.values()); X = np.full((len(rows), len(ix) + 6), np.nan, np.float32)
    for i, x in enumerate(rows):
        X[i, -1] = 1; X[i, -2] = False; X[i, -3 - b['places'].index('RULE')] = 1
        for k, v in x['f'].items():
            j = ix.get(k)
            if j is not None and v is not None:
                X[i, j] = v
    JUNK[task] = (np.array([x['logq'] for x in rows]), b['model'].decision_function(X))
    return JUNK[task]


with open(out, 'a') as f:
    for line in open(two):
        c = json.loads(line)
        task, i, s = c['task'], c['form'], c['split']
        if (task, i, s) in done or not c.get('same_table'):
            continue
        lines = [x for x in specs[task].strip().split('\n') if not x.startswith('(OUT')]
        scope = [lines[j] for j in cases[task, i]['keep']]
        path = tmp + '/g.json'
        json.dump([dict(task=task, gold_sexp='\n'.join(scope + [c['first'], c['second']]))], open(path, 'w'))
        G.GOLDS = path; G.golds.cache_clear()
        st.update(rel=None, first=None, pairs=[Pair(p['input'], p['output']) for p in json.load(open(f'data/tasks/{task}.json'))['train']])
        try:
            q = or_q.one(sampler, task, 'x', [len(scope) + 1, 0])
        except Exception as e:  # noqa: BLE001
            print(task, i, s, 'failed', str(e)[:100], flush=True); continue
        row = dict(task=task, form=i, split=s, rel=st['rel'], score=st['first'], atom_bits=q['atoms'][0][2] if q.get('atoms') else None, total=q.get('total'), parts={k: v for k, v in q.get('parts', {}).items() if 'relation' in k})
        if st['first'] is not None and row['atom_bits'] is not None:
            lq, sv = junk(task); g = -math.log(2) * row['atom_bits']
            row.update(pool=len(lq), base=math.log2(1 + int((lq > g).sum())), **{f'beta{b:g}': math.log2(1 + int((lq + b * sv > g + b * st['first']).sum())) for b in BETAS})
        f.write(json.dumps(row) + '\n'); f.flush()
        print(task, i, s, row['rel'], row.get('base'), row.get('beta4'), flush=True)
