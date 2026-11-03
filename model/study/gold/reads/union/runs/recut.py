"""Recut the pinned program of each task from a solving case of its latest gold round: the old pinned case where it solves, else the solving case with the fewest lines; normal form, then dead lines pruned (OUT kept). Backs up pairs.jsonl.gz as pairs.before-recut.jsonl.gz. usage: recut.py SET TASK..."""
import gzip, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gold_union as U
from gold_union_fits import rows_of, sha16
from gold_cheapest_prune import dead_lines
s = sys.argv[1]
fits = {r['task']: r for r in rows_of(U.OUT + 'fits-%s.jsonl' % s)}
pubs = U.G.publications()
for t in sys.argv[2:]:
    V = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-v3-combined-cut/view-final/%s/pairs.jsonl.gz' % t
    old = json.loads(gzip.open(V, 'rt').readline())
    ok = {x['text_sha'] for x in fits[t]['programs'] if x['fit'] and x['test_ok']}
    p, res = pubs[t]
    good = [c for c in res['cases'] if sha16(c.get('filtered_program') or c.get('original_program') or '') in ok]
    if not good:
        print(t, 'no solving case in', p); continue
    bar = U.Bar(t)
    pick = [c for c in good if c['case'] == old.get('case')] or sorted(good, key=lambda c: len(U.program_lines(bar.normal(c.get('filtered_program') or c['original_program'])[0])))
    c = pick[0]
    ls = U.program_lines(bar.normal(c.get('filtered_program') or c['original_program'])[0])
    while (d := [k for k in dead_lines(ls) if not ls[k].startswith('(OUT')]):
        ls = [x for k, x in enumerate(ls) if k not in d]
    norm, fixed = bar.normal('\n'.join(ls))
    if not os.path.exists(V.replace('pairs.', 'pairs.before-recut.')):
        shutil.copy(V, V.replace('pairs.', 'pairs.before-recut.'))
    with gzip.open(V, 'wt') as f:
        f.write(json.dumps(dict(old, case=c['case'], gold_sexp=norm)) + '\n')
    print(t, p, 'case', c['case'], 'was', old.get('case'), 'lines', len(U.program_lines(norm)), 'fixed', fixed)
