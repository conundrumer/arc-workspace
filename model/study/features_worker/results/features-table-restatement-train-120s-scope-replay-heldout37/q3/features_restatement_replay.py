"""Replays a seeded plain run's node records through scope rules that skip a redundant pick, and reads the share of visits whose scope holds all of a ready form's parents, on the run's own visits and pool growth. A second count takes a parent as held when the scope holds any table of its class. One JSON per task and rule; a rerun skips finished ones. No rule reads gold.

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
    'plain-k6': ('plain', 6, {}), 'credit-k6': ('plain', 6, {}), 'skip-class-k6': ('skip', 6, dict(ARROW=0)), 'skip-arrow-k6': ('skip', 6, dict(ARROW=1)),
}
import features_scope_connect as C  # noqa: E402
sys.path.insert(0, os.path.dirname(HERE))
import features_restatement_probe as P2  # noqa: E402
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


def relate(task):
    """The plain class of each node, and the pairs of classes with a one-source arrow, in the direction source, target."""
    want = any('arrow' in n for n in names)
    o = f"{a.out}/{'rel-arrows' if want else 'rel'}/{task}.json"
    if os.path.exists(o):
        d = json.load(open(o))
        return {int(k): v for k, v in d['cls'].items()}, {tuple(x) for x in d['arrows']}
    tables, token_of, _ = P2.load(f'{a.nodes}/{task}.nodes.jsonl.zst')
    reps, _ = P2.classes_of(tables, token_of)
    of = {x: r.i for r in reps for x in r.ids}
    cls = {t: of[i] for t, i in token_of.items() if i in of}
    by_key = collections.defaultdict(set)
    for t in reps:
        by_key[hash(t.canon)].add(t.i)
    arrows = set()

    def mark(rel, ty, ex, sid):
        if any(ex):
            for x in by_key.get(P2.plain_key(ty, ex, example=False), ()):
                if x != sid:
                    arrows.add((sid, x))

    dom = collections.defaultdict(lambda: [set() for _ in reps[0].ex])
    for t in reps:
        for c, ty in enumerate(t.types):
            for i, rows in enumerate(t.ex):
                dom[ty][i].update(r[c] for r in rows)
    for s in reps if want else ():
        P2.one_source(s.types, s.ex, dom, s.i, mark)
    os.makedirs(os.path.dirname(o), exist_ok=True)
    json.dump(dict(cls=cls, arrows=sorted(arrows)), open(o + '.new', 'w')); os.replace(o + '.new', o)
    return cls, arrows


def credit(task, targets):
    """For each target class, the classes that give it by one arrow. A source is tried only if its column types can hold a target's, with one Nat added for a count."""
    o = f'{a.out}/credit/{task}.json'
    if os.path.exists(o):
        return {int(k): set(v) for k, v in json.load(open(o)).items()}
    tables, token_of, _ = P2.load(f'{a.nodes}/{task}.nodes.jsonl.zst')
    reps, _ = P2.classes_of(tables, token_of)
    by_key = {hash(reps[c].canon): c for c in targets}
    wanted = [collections.Counter(reps[c].types) for c in targets]
    out = collections.defaultdict(set)

    def mark(rel, ty, ex, sid):
        if any(ex):
            x = by_key.get(P2.plain_key(ty, ex, example=False))
            if x is not None and x != sid:
                out[x].add(sid)

    dom = collections.defaultdict(lambda: [set() for _ in reps[0].ex])
    for t in reps:
        for c, ty in enumerate(t.types):
            for i, rows in enumerate(t.ex):
                dom[ty][i].update(r[c] for r in rows)
    for s in reps:
        have = collections.Counter(s.types)
        have['Nat'] += 1
        if any(not (w - have) for w in wanted):
            P2.one_source(s.types, s.ex, dom, s.i, mark)
    os.makedirs(os.path.dirname(o), exist_ok=True)
    json.dump({k: sorted(v) for k, v in out.items()}, open(o + '.new', 'w')); os.replace(o + '.new', o)
    return dict(out)


def skip_scope(P, k, rng, cls, arrows, use_arrows):
    """Policy.scope, with a pick left out where it repeats the class of a kept pick, or, with use_arrows, has an arrow to or from one."""
    if not P.ids:
        return []
    keys = {i: P.score[i] - policy.USES * P.uses[i] - math.log(-math.log(rng.random() or 1e-12)) for i in P.ids}
    kept, seen = [], set()

    def fits(i):
        c = cls.get(i)
        if c is None:
            return True
        if c in seen:
            return False
        return not (use_arrows and any((c, x) in arrows or (x, c) in arrows for x in seen))

    def take(order, n):
        for i in order:
            if len(kept) >= n:
                return
            if i not in kept and fits(i):
                kept.append(i)
                if cls.get(i) is not None:
                    seen.add(cls[i])

    take(sorted(P.ids, key=lambda i: -keys[i]), max(1, k - k // 4))
    take(sorted(P.ids, key=lambda i: (P.uses[i], i)), k)
    for i in kept:
        P.uses[i] += 1
    return kept


class Stub:
    def __init__(self, score):
        self.score, self.uses, self.ids = score, {}, []


def replay(task, recs, score, ev, name):
    kinds, reads, fid, ready = gold(specs[task], a.level)
    rule, k, cfg = RULES[name]
    C.FILL, C.PAIR = cfg.get('FILL', 1), cfg.get('PAIR', 0)
    C.fits = (lambda x, y: True) if cfg.get('NOFIT') else FITS
    pool = types.SimpleNamespace(nodes={}, policy=Stub(score))
    cls, arrows = relate(task)
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
    hold = collections.Counter(); logged = collections.Counter(); by_class = collections.Counter(); sizes = []; scopes = 0
    form_cls = collections.defaultdict(set)
    for n in order:
        if n.id in cls:
            form_cls[n.form].add(cls[n.id])
    cur_cls = set()
    by_arrow = collections.Counter()
    src = credit(task, sorted({c for s in need.values() for f in s for c in form_cls[f]})) if name == 'credit-k6' else {}
    for e in visits:
        for n in order[grown:upto]:
            if n.id not in pool.nodes:
                pool.nodes[n.id] = n; pool.policy.ids.append(n.id); pool.policy.uses[n.id] = 0
        grown = upto
        if e['fids'] != prev:
            prev = e['fids']; scopes += 1
            if rule == 'skip':
                ids = skip_scope(pool.policy, k, rng, cls, arrows, cfg['ARROW'])
            else:
                ids = policy.Policy.scope(pool.policy, k, rng)
            cur = set()
            for n in ids:
                got, todo = set(), [pool.nodes[n].form]
                while todo:
                    f = todo.pop()
                    if f not in got and f not in cur:
                        got.add(f); todo += parents[f]
                if len(cur) + len(got) <= MAX_SCOPE_FORMS:
                    cur |= got
            cur_cls = set().union(*(form_cls[f] for f in cur)) if cur else set()
        sizes.append(len(cur))
        for i, s in need.items():
            hold[i] += s <= cur
            logged[i] += s <= set(e['fids'])
            by_class[i] += all(f in cur or form_cls[f] & cur_cls for f in s)
            if name == 'credit-k6':
                by_arrow[i] += all(f in cur or form_cls[f] & cur_cls or any(src.get(c, set()) & cur_cls for c in form_cls[f]) for f in s)
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
                rows=[dict(form=i, parents=len(s), hold=hold[i], logged=logged[i], by_class=by_class[i], by_arrow=by_arrow[i]) for i, s in need.items()], fit=fitset)


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
