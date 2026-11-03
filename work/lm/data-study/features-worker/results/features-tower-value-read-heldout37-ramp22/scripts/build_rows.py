"""T facts of the nodes of one read run, by engine replay of the bank's forms (the code path of features_node_rebuild.py, without gold keys and hand facts).

  scripts/rt_r1.sh build_rows.py TASK SEED SECONDS [ARM]        (SEED: s0 or s1; ARM: bundle or pass for a run of search-pass-r1, rows go to rows/pass_x/ARM_TASK_SEED)

Replays each bank form with its ancestors in depth order, matches each node of the form to a replayed table by (types, examples), and writes the T facts of
FE.names_T() for it. Writes rows/read_x/TASK_SEED.partNNN.npz per call and rows/read_x/TASK_SEED.progress.json. Resumes. A finished run has done=true.
Row check per node: equal (types and example hashes equal the bank's), ident (an Ident column and equal counts), other counts, no table.
"""
import collections
import json
import os
import pickle
import sys
import time

T0 = time.time()
HERE = os.path.dirname(os.path.abspath(__file__))
REC = os.path.dirname(HERE)
KIT = REC + '/kit/search-refit-r1-kit-0729e4943/'
FEAT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-score-refit-loop/'
TASK, SEED, SECONDS = sys.argv[1], sys.argv[2], float(sys.argv[3])
ARM = sys.argv[4] if len(sys.argv) > 4 else None   # bundle or pass: a run of search-pass-r1 (ramp tasks)
R1 = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/runs/search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943/'
sys.path.insert(0, FEAT)
sys.path.insert(0, HERE)
import numpy as np
import common as C
import superdag as D
import superdag_search as Q
D.table_key = Q.table_key
import features_node_feats as FE
live, arclog = D.live, D.arclog
S = D.S

OUT = REC + ('/rows/pass_x/' if ARM else '/rows/read_x/')
os.makedirs(OUT, exist_ok=True)
STEM = '%s_%s_%s' % (ARM, TASK, SEED) if ARM else '%s_%s' % (TASK, SEED)
prog_path = OUT + STEM + '.progress.json'
prog = json.load(open(prog_path)) if os.path.exists(prog_path) else dict(next=0, parts=0, nodes=0, rc={}, done=False, seconds=0.0)
if prog['done']:
    print(STEM, 'done already')
    sys.exit(0)

base = (C.PASS_R1 + 'out/%s_%s/%s/work/%s.out.jsonl' % (ARM, SEED, TASK, TASK)) if ARM else (R1 + 'out/bundle_%s/%s/work/%s.out.jsonl' % (SEED, TASK, TASK))
st = C.load_bank(base + '.bank')
forms, nodes = st['forms'], st['nodes']
task = json.load(open(base[:-len('.out.jsonl')] + '.task.json'))
for x in task['test']:
    x.pop('output', None)
ctx = FE.TaskCtx(task)
NAMES_T = FE.names_T()
sampler = live.Sampler(KIT + 'models-tk')
settings = arclog.DecodeSettings(relations=D.RELATIONS, **D.SETTINGS)
session = arclog.Session(arclog.Task.from_json(json.dumps(task), arclog.World.Open), settings, session_bytes=1 << 30)
run = D.Run(sampler.pri, session, 0, time.monotonic() + 86400, task, live.Limits())


def replay(texts):
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


def anc(f):
    got, s = set(), [f]
    while s:
        x = s.pop()
        if x not in got:
            got.add(x)
            s += forms[x].parents
    return sorted(got, key=lambda y: (forms[y].depth, y))


RC = ['equal', 'ident', 'other counts', 'no table']
fids = sorted(forms)
rows = collections.defaultdict(list)
rcc = collections.Counter()
t1 = time.time()
i = prog['next']
n_done = 0
while i < len(fids) and time.time() - T0 < SECONDS:
    f = fids[i]
    i += 1
    fo = forms[f]
    tabs = replay([forms[x].text for x in anc(f)])
    used = set()
    for n in sorted(fo.nodes):
        node = nodes[n]
        want = json.dumps([sorted(node.table_types), node.examples])
        pick, code = None, 3
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
                    code = 2
        rcc[RC[code]] += 1
        if pick is None:
            rows['meta'].append([n, f, code])
            rows['X'].append(np.full(len(NAMES_T), np.nan, np.float32))
            continue
        used.add(pick)
        tb, k, ex = tabs[pick]
        ty = [str(t) for t in tb['types']]
        xr = S.rows_with_models(tb, S.X_ROWS_CAP)
        feat = FE.node_features(ty, xr, node.clause, fo.kind, fo.depth, fo.reads, ctx, with_shape=False)
        rows['X'].append(np.array([feat[nm] for nm in NAMES_T], np.float32))
        rows['meta'].append([n, f, code])
    n_done += 1
el = time.time() - t1
if rows['meta']:
    part = prog['parts'] + 1
    np.savez_compressed(OUT + STEM + '.part%03d.npz' % part, meta=np.array(rows['meta'], np.int64), X=np.stack(rows['X']), names=np.array(NAMES_T))
    prog['parts'] = part
    prog['nodes'] += len(rows['meta'])
    for kx, v in rcc.items():
        prog['rc'][kx] = prog['rc'].get(kx, 0) + v
prog['next'] = i
prog['done'] = i >= len(fids)
prog['seconds'] += time.time() - T0
json.dump(prog, open(prog_path + '.tmp', 'w'))
os.replace(prog_path + '.tmp', prog_path)
rate = n_done / el if el > 0 and n_done else 0
print(STEM, 'forms', i, '/', len(fids), 'nodes written', prog['nodes'], 'of', len(nodes), 'this call', n_done, 'forms in', round(el, 1), 's', 'rate %.1f forms/s' % rate,
      'ETA for the run s', round((len(fids) - i) / rate) if rate else None, 'row check', dict(prog['rc']), flush=True)
