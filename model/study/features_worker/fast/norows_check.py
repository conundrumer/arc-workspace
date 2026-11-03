import sys, json, time, collections as C
import numpy as np
sys.path[:0] = ['/Users/davidlu/code/arc-workspace/work/lm/data-study/feat-exp/study', '/Users/davidlu/code/arc-workspace/model/study']
from online_score import PointScorer, SOFT_NOROWS
from judge3.framed_jsonl import iter_json
R = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b9773fdd-d09f-4bd5-b2d0-ebeaa83d8c6d/scratchpad/sampler/runN_d'
G = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/gap/runNd.csv.gz.stream.jsonl.zst'
NAMES = json.load(open(R + '/names.json'))
full = {r['pair_id']: r.get('soft_score') for r in iter_json(G)}
pts = C.OrderedDict()
for d in iter_json(R + '/draws.jsonl.zst'):
    k = (d['task'], d['case'], json.dumps(d['point']))
    if k not in pts and len(pts) >= int(sys.argv[1]):
        break
    pts.setdefault(k, []).append(d)
dt, same, rho = [], 0, []
for k, ds in pts.items():
    ps = PointScorer(*k, rules=None, soft=SOFT_NOROWS); names = NAMES.get('|'.join(k), {})
    assert not ps.needs_rows
    a, b = [], []
    for d in ds:
        if d.get('fail') or not d.get('clause') or not d.get('x_rows'):
            continue
        r1 = ps.score(d, names)
        t = time.perf_counter(); r0 = ps.score(dict(d, x_rows=[]), names); dt.append(time.perf_counter() - t)
        same += r0['soft_score'] == r1['soft_score']
        f = full.get(f"{k[0]}|{k[1]}|{k[2]}|{d['draw']}")
        if f is not None and r0['soft_score'] is not None:
            a.append(r0['soft_score']); b.append(f)
    if len(a) > 3:
        rho.append(np.corrcoef(np.argsort(np.argsort(a)), np.argsort(np.argsort(b)))[0, 1])
dt = np.array(dt) * 1000
print(f'{len(dt)} draws: score without rows equals score with rows on {same}; ms per draw mean {dt.mean():.1f} median {np.median(dt):.1f} p90 {np.percentile(dt, 90):.1f} max {dt.max():.0f}')
print(f'rank correlation with the full v11 score within a point: median {np.median(rho):.2f} over {len(rho)} points (min {min(rho):.2f})')
