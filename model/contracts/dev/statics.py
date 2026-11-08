"""Dev labeling layer: which static features of a table's query go with a falsifiable emptiness postcondition, over tasks.

    python3 statics.py TASK [TASK ...]

For each table whose `empty` postcondition was tested, the query's static features (query.py) against whether emptiness is falsifiable.
"""
import json
import os
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / 'features'))
import paths  # noqa: E402
import query as Q  # noqa: E402

OUTDIR = Path(os.environ.get('CONTRACTS_OUT', HERE / 'out'))
GEN = paths.GEN
c = Counter()
for task in sys.argv[1:]:
    p = OUTDIR / (task + '.verdicts.post.json')
    if not p.exists():
        continue
    qf = Q.query_features(paths.read_gen(GEN / (task + '.arclog')))
    for t, r in json.load(open(p)).items():
        v = r['postconditions'].get(t + '|empty', {}).get('verdict')
        if v in (None, 'untested'):
            continue
        fals = v in ('new', 'redundant')
        node, _, port = t.partition('.')
        q = qf.get(node, {})
        is_input = port in q.get('inputs written', [])
        shape = ('proposer DET' if q.get('kind') in ('DET', 'DET_OR_RULE') and q.get('proposer') and not q.get('atoms') else
                 'DET with clauses' if q.get('kind') in ('DET', 'DET_OR_RULE', 'RULE_OR_DET') else
                 'instance input port' if is_input else
                 'instance output' if q.get('kind') == 'INIT' else
                 'RULE with NOT' if q.get('negations') else
                 'RULE joining 2+ derived tables' if q.get('derived reads', 0) >= 2 else
                 'RULE, other')
        reading = {None: 'unread'}.get(r['reading'], 'claim' if r['reading'] == 'claim' else 'plumbing')
        c[shape, fals] += 1
        c[shape, reading, fals] += 1
print('%-32s %-22s %-22s %-22s' % ('query shape', 'emptiness falsifiable', 'claims', 'plumbing'))
for shape in sorted({k[0] for k in c}):
    f, n = c[shape, True], c[shape, True] + c[shape, False]
    fc, nc = c[shape, 'claim', True], c[shape, 'claim', True] + c[shape, 'claim', False]
    fp, np_ = c[shape, 'plumbing', True], c[shape, 'plumbing', True] + c[shape, 'plumbing', False]
    print('%-32s %3d of %3d             %3d of %3d             %3d of %3d' % (shape, f, n, fc, nc, fp, np_))
