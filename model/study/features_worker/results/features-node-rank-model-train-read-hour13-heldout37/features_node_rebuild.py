"""Items 5 and 6 for N600, H and B: rebuild the rows of one run's nodes from its bank, label them by session key, and write features. Resumes.

  ./rt_set.sh SET features_node_rebuild.py SET ARM TASK SECONDS        (SET: n600, hour or base; rt600.sh is rt_set.sh n600)

Replays each bank form with its ancestors in depth order (the code path of scratch/rebuild_rate.py). In the same session it replays
the right program's forms (G/gold-v3-combined-cut/view-final), so a node is positive when the order-free session key of its table
equals the key of a table of a gold form (OUT lines left out). Writes n600-rows/TASK.partNNN.npz per call, n600/TASK.gold.json once,
n600/TASK.progress.json. Prints rows, rate and ETA. Rows (x_rows) are not kept.

Row check per node: equal (row hash pair equals the bank's), ident (an Ident column and equal counts), tied (same counts, other hash,
no Ident column), other counts, no table (the replay gave no table for the node).
"""
import collections, gzip, json, os, pickle, sys, time, types as _types
T0 = time.time()
HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-rank-model-train-read-hour13-heldout37/'  # the data folder
SET, ARM, TASK, SECONDS = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
W = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/'
G = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/'
SETS = {'n600': dict(kit='kits/sampler-pool-dag-nodes-train50-final-8be414670/', models='models-final', root='sampler-pool-dag-nodes-train50-600s/out/', view='gold-v3-combined-cut/view-final'),
        'hour': dict(kit='kits/sampler-pool-fold-hour-8be414670/', models='models-coverf', root='sampler-pool-fold-hour-3600s/out/', points=W + 'sampler-extended-cut/points-with-ramp.json'),
        'base': dict(kit='kits/sampler-pool-extended-text-pass1-8be414670/', models='models-base', root='sampler-pool-extended-text-pass1-600s/out-all37/', points=G + 'gold-v3-extended-cut/view-pass1/points-eval.json')}
S_ = SETS[SET]
KIT = W + S_['kit']
sys.path.insert(0, KIT + 'model/study/sampler'); sys.path.insert(0, KIT + 'policy'); sys.path.insert(0, HERE)
import numpy as np
import superdag as D
import superdag_search as Q
D.table_key = Q.table_key
live, arclog = D.live, D.arclog
S = D.S
import features_node_feats as FE
import policy as HP

RC = ['equal', 'ident', 'tied', 'other counts', 'no table']
OUT = HERE + SET + '-rows/'
os.makedirs(OUT, exist_ok=True)
STEM = TASK if SET == 'n600' else ARM + '.' + TASK
prog_path = OUT + STEM + '.progress.json'
prog = json.load(open(prog_path)) if os.path.exists(prog_path) else dict(next=0, parts=0, nodes=0, rc={})

d = W + S_['root'] + ARM + '/' + TASK + '/work/'
st = pickle.load(open(d + TASK + '.out.jsonl.bank', 'rb'))
forms, nodes, pol = st['forms'], st['nodes'], st['policy']
task = json.load(open(KIT + 'data/tasks/%s.json' % TASK))
for x in task['test']:
    x.pop('output', None)
ctx = FE.TaskCtx(task)
sampler = live.Sampler(KIT + S_['models'])
settings = arclog.DecodeSettings(relations=D.RELATIONS, **D.SETTINGS)
session = arclog.Session(arclog.Task.from_json(json.dumps(task), arclog.World.Open), settings, session_bytes=1 << 30)
run = D.Run(sampler.pri, session, 0, time.monotonic() + 86400, task, live.Limits())


def replay(texts):
    """[(parsed table, key, row pairs)] for the tables of the last form of texts, or None where the replay fails."""
    run.collect = []
    run.scoped = None
    try:
        run.scope(texts)
        ct = run.collect[-1]
    except Exception:
        return None
    finally:
        run.collect = None
    out = []
    for _, j in D.relation_tables(ct):
        try:
            tb = S.parse_table(D.OneTable(ct, j))
        except D.M.Fail:
            continue
        k, ex = Q.table_key(tb)
        out.append((tb, k, ex))
    return out


# the right program's forms, in this session
if 'view' in S_:
    gold_text = json.loads(gzip.open(G + S_['view'] + '/' + TASK + '/pairs.jsonl.gz', 'rt').readline())['gold_sexp']
else:
    gold_text = {x['task']: x['gold_sexp'] for x in json.load(open(S_['points']))}[TASK]
glines = [x for x in gold_text.strip().split('\n') if not x.startswith('(OUT')]
gold_keys = []
run.collect = []
run.scoped = None
err = None
try:
    run.scope(glines)
except Exception as e:
    err = str(e)[:100]
for i, ct in enumerate(run.collect or []):
    ks = set()
    for _, j in D.relation_tables(ct):
        try:
            tb = S.parse_table(D.OneTable(ct, j))
        except D.M.Fail:
            continue
        ks.add(Q.table_key(tb)[0])
    gold_keys.append(ks)
run.collect = None
run.scoped = None
gold_of_key = collections.defaultdict(set)
for g, ks in enumerate(gold_keys):
    for k in ks:
        gold_of_key[k].add(g)
if not os.path.exists(OUT + STEM + '.gold.json'):
    import re
    reads, head = [], {}
    for i, x in enumerate(glines):
        names = re.findall(r'&r\d+', x)
        h = names[0]
        reads.append(sorted({head[m] for m in names[1:] if m in head and m != h}))
        head[h] = i
    json.dump(dict(lines=glines, reads=reads, kinds=[x[1:x.index(' ')] for x in glines], tables_per_form=[len(k) for k in gold_keys], replay_error=err, forms_replayed=len(gold_keys)), open(OUT + STEM + '.gold.json', 'w'))

# hand features
hp = HP.Policy(task)
hp_path = OUT + STEM + '.hand.pkl'
if prog['next'] and os.path.exists(hp_path):
    hp.nodes = pickle.load(open(hp_path, 'rb'))
HN = hp.names


def anc(f):
    got, s = set(), [f]
    while s:
        x = s.pop()
        if x not in got:
            got.add(x)
            s += forms[x].parents
    return sorted(got, key=lambda y: (forms[y].depth, y))


fids = sorted(forms)
rows = collections.defaultdict(list)
rcc = collections.Counter()
t_setup = time.time() - T0
t1 = time.time()
i = prog['next']
n_done = 0
KIND = {'DET': 0, 'RULE': 1, 'INIT': 2}
while i < len(fids) and time.time() - T0 < SECONDS:
    f = fids[i]
    i += 1
    fo = forms[f]
    tabs = replay([forms[x].text for x in anc(f)])
    used = set()
    if tabs is None:
        rcc['(forms whose replay failed)'] += 1
    elif len(tabs) == 0:
        rcc['(forms whose replay gave no table)'] += 1
    for n in sorted(fo.nodes):
        node = nodes[n]
        want = json.dumps([sorted(node.table_types), node.examples])
        pick, code = None, 4
        if tabs is not None:
            for q, (tb, k, ex) in enumerate(tabs):
                if q not in used and json.dumps([sorted(str(t) for t in tb['types']), ex]) == want:
                    pick, code = q, 0
                    break
            if pick is None:
                cnt = [e[:3] for e in node.examples]
                same_t = [q for q, (tb, k, ex) in enumerate(tabs) if q not in used and sorted(str(t) for t in tb['types']) == sorted(node.table_types)]
                hit = [q for q in same_t if [e[:3] for e in tabs[q][2]] == cnt]
                if hit:
                    pick = hit[0]
                    code = 1 if 'Ident' in node.table_types else 2
                elif same_t:
                    code = 3
        rcc[RC[code]] += 1
        meta = [n, f, code, KIND.get(fo.kind, 3), fo.depth, node.depth, node.age, pol['score'].get(n, np.nan), pol['uses'].get(n, 0)]
        if pick is None:
            rows['meta'].append(meta + [-1, 0])
            rows['X'].append(np.full(len(FE.NAMES), np.nan, np.float32))
            rows['H'].append(np.full(len(HN), np.nan, np.float32))
            rows['gold'].append([])
            continue
        used.add(pick)
        tb, k, ex = tabs[pick]
        ty = [str(t) for t in tb['types']]
        xr = S.rows_with_models(tb, S.X_ROWS_CAP)
        g = sorted(gold_of_key.get(k, ()))
        feat = FE.node_features(ty, xr, node.clause, fo.kind, fo.depth, fo.reads, ctx)
        rows['X'].append(np.array([feat[nm] for nm in FE.NAMES], np.float32))
        sn = _types.SimpleNamespace(id=n, types=node.types, table_types=ty, arity=node.arity, depth=node.depth, parents=node.parents, clause=node.clause, rows=xr, examples=node.examples)
        try:
            hd = hp.feats(sn)
            hv = np.full(len(HN), np.nan, np.float32)
            for nm, v in hd.items():
                if nm in hp.ix:
                    hv[hp.ix[nm]] = v
        except Exception:
            hv = np.full(len(HN), np.nan, np.float32)
        rows['H'].append(hv)
        rows['meta'].append(meta + [1 if g else 0, FE.plain_sig(ty, xr, ctx.n_train, ctx.n_test)])
        rows['gold'].append(g)
    n_done += 1
el = time.time() - t1
if rows['meta']:
    part = prog['parts'] + 1
    M = np.array(rows['meta'], np.float64)
    np.savez_compressed(OUT + STEM + '.part%03d.npz' % part, meta=M, X=np.stack(rows['X']), H=np.stack(rows['H']), gold=np.array([json.dumps(rows['gold'])]), names=np.array(FE.NAMES), hand_names=np.array(HN),
                        meta_cols=np.array('node form rowcheck kind form_depth node_depth age score uses y plain'.split()))
    prog['parts'] = part
    prog['nodes'] += len(rows['meta'])
    for kx, v in rcc.items():
        prog['rc'][kx] = prog['rc'].get(kx, 0) + v
prog['next'] = i
prog['forms'] = len(fids)
pickle.dump(hp.nodes, open(hp_path, 'wb'))
json.dump(prog, open(prog_path, 'w'))
rate = n_done / el if el > 0 and n_done else 0
print(STEM, 'forms', i, '/', len(fids), 'nodes written', prog['nodes'], 'setup s', round(t_setup, 1), 'this call', n_done, 'forms in', round(el, 1), 's',
      'rate %.1f forms/s' % rate, 'ETA for the task s', round((len(fids) - i) / rate) if rate else None, 'gold forms replayed', len(gold_keys), 'of', len(glines), 'row check', dict(rcc), flush=True)
