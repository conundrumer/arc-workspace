"""Dev labeling layer: for each table whose verdict differs from its reading, the evidence behind the verdict, over tasks.

    python3 causes.py TASK [TASK ...]

A plumbing table that comes out informative is listed with its kind (an instance's output or input port, or a form of the program) and its new
postconditions, each marked `out` where it reads the train output. A claim that comes out redundant is listed with the prior tables whose
features fail on the same variants. A claim that comes out untested is listed as such.
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
from features import OUTPUT_FEATURES  # noqa: E402

OUTDIR = Path(os.environ.get('CONTRACTS_OUT', HERE / 'out'))
GEN = paths.GEN
kinds = Counter()
for task in sys.argv[1:]:
    p = OUTDIR / (task + '.verdicts.post.json')
    if not p.exists():
        continue
    qf = Q.query_features(paths.read_gen(GEN / (task + '.arclog')))
    for t, r in json.load(open(p)).items():
        reading, verdict = r['reading'], r['verdict']
        if reading is None:
            continue
        node, _, port = t.partition('.')
        q = qf.get(node, {})
        what = ('%s input %s' % (q.get('component'), port) if port in q.get('inputs written', []) else '%s output %s' % (q.get('component'), port)) if port else q.get('kind', '?')
        pcs = r['postconditions']
        if reading != 'claim' and verdict == 'informative':
            new = [k.split('|', 1)[1] + (' [out]' if any(s in k for s in OUTPUT_FEATURES) else '') for k, v in pcs.items() if v['verdict'] == 'new']
            side = 'output-side' if all('[out]' in x for x in new) else 'input-side' if not any('[out]' in x for x in new) else 'both'
            kinds['plumbing informative', what.split()[1] if port else 'form', side] += 1
            print('%s %-24s plumbing informative (%s): %s' % (task, t, what, '; '.join(new[:4])))
        elif reading == 'claim' and verdict == 'redundant':
            same = sorted({s.split('|')[0] for v in pcs.values() if v['verdict'] == 'redundant' for s in v.get('same_as', [])})
            sub = 'no counterexample' if not same else 'explained by input' if same == ['input'] else 'explained by tables'
            kinds['claim redundant', sub, ''] += 1
            print('%s %-24s claim redundant (%s): %s' % (task, t, what, 'no counterexample' if not same else 'explained by ' + ', '.join(same)))
        elif reading == 'claim' and verdict == 'untested':
            kinds['claim untested', '', ''] += 1
            print('%s %-24s claim untested (%s)' % (task, t, what))
print()
for k, n in sorted(kinds.items()):
    print(n, ' / '.join(x for x in k if x))
