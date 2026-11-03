"""Sanity of the OUT features on one pool: gold nodes against junk."""
import glob, os, sys, time, collections
sys.path[:0] = ['/Users/davidlu/code/arc-workspace/model/study', '.']
from judge3.framed_jsonl import iter_json
from nodefeat import load_pairs
from outfeat import out_features, link_features
P = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/runs/superdag1'
for f in sorted(glob.glob(P + '/*.nodes.jsonl.zst'))[:6]:
    t = os.path.basename(f)[:8]; pairs = load_pairs(t); N = {}; tag = {}; t0 = time.time(); n = 0
    for r in iter_json(f):
        d, s = out_features(r, pairs); N[r['token']] = (r.get('parents') or [], d, s); tag[r['token']] = (r.get('tags') or {}).get('kind'); n += 1
    link_features(N); dt = (time.time() - t0) / max(n, 1)
    k = collections.Counter(tag.values())
    g = [N[x][1] for x in N if tag[x] == 'gold']
    jj = [N[x][1] for x in N if tag[x] != 'gold']
    def m(L, key):
        v = [x[key] for x in L if key in x]
        return f'{len(v)}:{sum(v)/len(v):.3f}:{max(v):.2f}' if v else '-'
    print(t, n, dict(k), f'{dt*1000:.2f}ms', *[f'{key} g {m(g,key)} j {m(jj,key)}' for key in ('out_gain','out_exact','fill_rec','link_adds')])
