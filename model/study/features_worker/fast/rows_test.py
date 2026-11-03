"""Which soft-score functions change when a draw comes without X's rows (x_rows empty), and the time of each subset.
Usage: rows_test.py N_POINTS"""
import sys, json, time, collections as C
sys.path[:0] = ['/Users/davidlu/code/arc-workspace/work/lm/data-study/feat-exp/study', '/Users/davidlu/code/arc-workspace/model/study']
from online_score import PointScorer
from rulecheck import rename_relations
import rulecheck
from featlib import FEATURES
from draw_features import flat
from judge3.framed_jsonl import iter_json
S = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad'
R = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b9773fdd-d09f-4bd5-b2d0-ebeaa83d8c6d/scratchpad/sampler/runN_d'
NAMES = json.load(open(R + '/names.json'))
soft = rulecheck.SoftScore()
funcs = sorted({c.split('.', 1)[0] for c in soft.cols} & set(FEATURES))
subsets = {}
for n in ('zero', 'fast5'):
    drop = open(f'{S}/fast/{n}.drop').read().split(',')
    subsets[n] = [f for f in funcs if f + '.' not in drop and f not in drop]
N = int(sys.argv[1])
pts = C.OrderedDict()
for d in iter_json(R + '/draws.jsonl.zst'):
    k = (d['task'], d['case'], json.dumps(d['point']))
    if k not in pts and len(pts) >= N:
        break
    pts.setdefault(k, []).append(d)
diff, seen, t_full, t_none, nd, bad_none = C.Counter(), C.Counter(), C.Counter(), C.Counter(), 0, 0
for k, ds in pts.items():
    ps = PointScorer(*k, rules=None); rc = ps.rc; names = NAMES.get('|'.join(k), {})
    for d in ds:
        if d.get('fail') or not d.get('clause') or not d.get('x') or not d.get('x_rows'):
            continue
        clause = rename_relations(d['clause'], names)
        try:
            t = time.perf_counter(); x1 = rc.draw_x(d, clause); c1 = rc.candidate(clause, x1); t_full['_x'] += time.perf_counter() - t
            t = time.perf_counter(); x0 = rc.draw_x(dict(d, x_rows=[]), clause); c0 = rc.candidate(clause, x0); t_none['_x'] += time.perf_counter() - t
        except Exception as e:
            bad_none += 1; continue
        nd += 1
        for f in subsets['fast5']:
            try:
                t = time.perf_counter(); v1 = dict(flat(f, FEATURES[f](c1))); t_full[f] += time.perf_counter() - t
            except Exception:
                v1 = None
            try:
                t = time.perf_counter(); v0 = dict(flat(f, FEATURES[f](c0))); t_none[f] += time.perf_counter() - t
            except Exception:
                v0 = None
            seen[f] += 1
            if json.dumps(v1, sort_keys=True, default=str) != json.dumps(v0, sort_keys=True, default=str):
                diff[f] += 1
    print(k, 'draws', nd, flush=True)
print('draws', nd, 'x build failed without rows', bad_none)
for n, fs in subsets.items():
    ok = [f for f in fs if diff[f] == 0]
    print(f'{n}: {len(fs)} functions; {len(ok)} never change without rows; ms per draw with rows {1000 * (t_full["_x"] + sum(t_full[f] for f in fs)) / nd:.1f}, '
          f'without rows {1000 * (t_none["_x"] + sum(t_none[f] for f in fs)) / nd:.1f} (x build {1000 * t_full["_x"] / nd:.1f} / {1000 * t_none["_x"] / nd:.1f})')
    print('  change without rows:', ' '.join(f'{f}:{diff[f]}/{seen[f]}' for f in fs if diff[f]))
json.dump(sorted(f for f in subsets['fast5'] if diff[f] == 0 and seen[f]), open(f'{S}/fast/no_rows.json', 'w'))
