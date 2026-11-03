"""Write the results of rerun_no_tables.py into the fits shard files (fits-SET-K.jsonl) of a set, then run `gold_union_fits.py SET merge` for fits-SET.jsonl (rerun_no_tables.sh does).

  python apply_reruns.py SET RESULTS.jsonl
"""
import glob, json, sys
s, res = sys.argv[1], {}
for l in open(sys.argv[2]):
    if l.startswith('{'):
        r = json.loads(l); res[r['task'], r['text_sha']] = r['result']
G = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-union/'
n = 0
for p in glob.glob(G + 'fits-%s-*.jsonl' % s):
    out = []
    for l in open(p):
        r = json.loads(l)
        if r.get('t') == 'header':
            out.append(l)
            continue
        for x in r['programs']:
            if (r['task'], x['text_sha']) in res:
                a, k, ok, why = res[r['task'], x['text_sha']]
                x.update(assignments=a, fitting=k, fit=None if why else k > 0, test_ok=None if why else ok, why=why); n += 1
        out.append(json.dumps(r) + '\n')
    open(p, 'w').write(''.join(out))
print(n, 'programs updated')
