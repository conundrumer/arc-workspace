"""Replays a seeded plain run's node records through scope rules, and reads the share of visits whose scope holds all of a ready form's parents, by parent count, on the run's own visits and pool growth. One JSON per task and rule; a rerun skips finished ones. No rule reads gold.

  features_scope_replay.py EVENTS_DIR NODES_DIR POLICY_DIR POINTS OUT LEVEL K N [--rules name ...]
"""
import argparse, collections, glob, gzip, importlib, json, math, os, random, re, statistics as st, subprocess, sys, time, types
HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
for a in 'events nodes policy points out'.split():
    ap.add_argument(a)
ap.add_argument('level', type=int); ap.add_argument('K', type=int); ap.add_argument('N', type=int)
ap.add_argument('--rules', nargs='*')
ap.add_argument('--oracle-report', default='/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker')
a = ap.parse_args()
sys.path[:0] = [a.policy, a.oracle_report, HERE]
from search_oracle_report import gold  # noqa: E402
import policy  # noqa: E402
MAX_SCOPE_FORMS = 96
os.environ.setdefault('SCOPE_TOP', '40')
RULES = {
    'plain-k6': ('plain', 6, {}), 'plain-k3': ('plain', 3, {}), 'plain-k12': ('plain', 12, {}),
    'connect-fill-k6': ('connect', 6, dict(FILL=1, PAIR=0)), 'connect-one': ('connect', 6, dict(FILL=0, PAIR=0)),
    'plain-top6': ('top', 6, {}), 'connect-nofit-k6': ('connect', 6, dict(FILL=1, PAIR=0, NOFIT=1)),
    'connect-fill-new-k6': ('connect', 6, dict(FILL=1, PAIR=1)), 'connect-one-new': ('connect', 6, dict(FILL=0, PAIR=1)),
}
import features_scope_connect as C  # noqa: E402
FITS = C.fits
specs = {x['task']: x['gold_sexp'] for x in json.load(open(a.points))}
HEAD = re.compile(r'&f(\d+)')


def records(task):
    out = []
    for raw in subprocess.run(['zstd', '-dcq', f'{a.nodes}/{task}.nodes.jsonl.zst'], capture_output=True).stdout.splitlines():
        try:
            out.append(json.loads(raw))
        except ValueError:
            pass
    return out


def scores(task, recs):
    o = f'{a.out}/scores/{task}.json'
    if os.path.exists(o):
        return {int(k): v for k, v in json.load(open(o)).items()}
    p = policy.Policy(json.load(open(f'/Users/davidlu/code/arc-workspace/data/tasks/{task}.json')))
    for r in recs:
        p.add(types.SimpleNamespace(id=int(r['token']), types=r['types'], table_types=r['table_types'], arity=r['arity'], depth=r['depth'], parents=[int(x) for x in r['parents']],
                                    clause=r['clause'] or '', rows=r['x_rows'], examples=r['examples'], n_clauses=1, n_readers=0))
    json.dump(p.score, open(o + '.new', 'w')); os.replace(o + '.new', o)
    return dict(p.score)


class Stub:
    def __init__(self, score):
        self.score, self.uses, self.ids = score, {}, []


def replay(task, recs, score, ev, name):
    kinds, reads, fid, ready = gold(specs[task], a.level)
    rule, k, cfg = RULES[name]
    C.FILL, C.PAIR = cfg.get('FILL', 1), cfg.get('PAIR', 0)
    C.fits = (lambda x, y: True) if cfg.get('NOFIT') else FITS
    pool = types.SimpleNamespace(nodes={}, policy=Stub(score))
    order = [types.SimpleNamespace(id=int(r['token']), table_types=r['table_types'], form=int(HEAD.search(r['clause']).group(1))) for r in recs]
    parents = collections.defaultdict(set)
    for r, n in zip(recs, order):
        parents[n.form] |= {int(x) for x in HEAD.findall(r['clause'])} - {n.form}
    for j, f in fid.items():
        parents[f] |= {fid[x] for x in reads[j]}
    visits = [e for e in ev if e['event'] == 'visit']
    n0 = len(recs) - sum(e['new'] for e in visits)
    upto, grown, prev, cur = n0, 0, None, set()
    rng = random.Random(f'{task} replay')
    need = {i: {fid[j] for j in reads[i]} for i in ready if reads[i]}
    hold = collections.Counter(); logged = collections.Counter(); sizes = []; scopes = 0
    for e in visits:
        for n in order[grown:upto]:
            if n.id not in pool.nodes:
                pool.nodes[n.id] = n; pool.policy.ids.append(n.id); pool.policy.uses[n.id] = 0
        grown = upto
        if e['fids'] != prev:
            prev = e['fids']; scopes += 1
            if rule == 'top':
                P = pool.policy
                key = {i: P.score[i] - policy.USES * P.uses[i] - math.log(-math.log(rng.random() or 1e-12)) for i in P.ids}
                ids = sorted(P.ids, key=lambda i: -key[i])[:k]
                for i in ids:
                    P.uses[i] += 1
            else:
                ids = policy.Policy.scope(pool.policy, k, rng) if rule == 'plain' else C.picks(pool, k, rng)
            cur = set()
            for n in ids:
                got, todo = set(), [pool.nodes[n].form]
                while todo:
                    f = todo.pop()
                    if f not in got and f not in cur:
                        got.add(f); todo += parents[f]
                if len(cur) + len(got) <= MAX_SCOPE_FORMS:
                    cur |= got
        sizes.append(len(cur))
        for i, s in need.items():
            hold[i] += s <= cur
            logged[i] += s <= set(e['fids'])
        upto += e['new']
    fitset = {}
    byform = collections.defaultdict(list)
    for n in order:
        byform[n.form].append(n)
    for i, s in need.items():
        if len(s) > 1 and all(byform[f] for f in s):
            fitset[i] = int(C.connected([byform[f][0] for f in s]) or any(C.connected([rng.choice(byform[f]) for f in s]) for _ in range(20)))
    live = [n for n in order if set(n.table_types) - C.SKIP]
    sample = [rng.sample(live, 2) for _ in range(2000)] if len(live) > 1 else []
    share = sum(FITS(x, y) for x, y in sample) / max(len(sample), 1)
    return dict(task=task, rule=name, pair_fit=share, visits=len(visits), scopes=scopes, forms=st.median(sizes) if sizes else 0,
                rows=[dict(form=i, parents=len(s), hold=hold[i], logged=logged[i]) for i, s in need.items()], fit=fitset)


os.makedirs(a.out + '/scores', exist_ok=True)
files = sorted(glob.glob(a.nodes + '/*.nodes.jsonl.zst'))[a.K::a.N]
t0 = time.time()
names = a.rules or list(RULES)
for i, f in enumerate(files, 1):
    task = os.path.basename(f).split('.')[0]
    if task not in specs or not os.path.exists(f'{a.events}/{task}.events.jsonl'):
        continue
    ev = [json.loads(l) for l in open(f'{a.events}/{task}.events.jsonl')]
    recs = None
    for name in names:
        o = f'{a.out}/{name}/{task}.json'
        if os.path.exists(o):
            continue
        recs = recs or records(task)
        os.makedirs(os.path.dirname(o), exist_ok=True)
        res = replay(task, recs, scores(task, recs), ev, name)
        json.dump(res, open(o + '.new', 'w')); os.replace(o + '.new', o)
    el = time.time() - t0
    print(f'{i}/{len(files)} {task} | {el:.0f} s | ETA {el / i * (len(files) - i):.0f} s', flush=True)
