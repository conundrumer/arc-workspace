#!/usr/bin/env python
"""The walker against the census, steers live: for forms of the census arm `parents` / `seed-0` (census-dag-join.jsonl), the walker's walk on the census's scope and target gives the census's total and its bits at each pick.

  features_dagc_env.sh 1 features_dagc_walk_check.py [PER_KIND] [SECONDS]      appends to walk-check-census.txt
The scope is rebuilt with the census folder's own order module (the scope's order is part of the census arm).
"""
import importlib.util
import json
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import features_dagc_lib as L  # noqa: E402
import features_dagc_walk as W  # noqa: E402

CENSUS = L.SCRATCH / 'records/features-dag-order-census-heldout37'


def main():
    per = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    budget = float(sys.argv[2]) if len(sys.argv) > 2 else 25
    spec = importlib.util.spec_from_file_location('old_order', CENSUS / 'features_dag_order.py')
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    rows = [json.loads(x) for p in sorted(CENSUS.glob('census-dag-join-shard*.jsonl')) for x in open(p)]
    rows = [r for r in rows if r['scope'] == 'parents' and r['order'] == 'seed-0' and not r.get('bad') and not r.get('dead') and not r.get('left') and not r.get('error') and r.get('aligned')]
    bits = {}
    for line in (x for p in sorted(CENSUS.glob('per-pick-dag-join-shard*.tsv')) for x in open(p)):
        f = line.rstrip('\n').split('\t')
        if f[0] == 'revision' or f[4] != 'parents' or f[5] != 'seed-0':
            continue
        bits.setdefault((f[1], int(f[2])), []).append(float(f[22]))
    gold = L.base_gold()
    env = W.Env('held', 'live', False, '')
    t0, tally, bad = time.time(), {}, []
    done = Path(L.OUT_DIR / 'walk-check-census.txt')
    for r in rows:
        k = r['kind']
        t = tally.setdefault(k, dict(forms=0, total_equal=0, bits_equal=0, picks=0))
        if t['forms'] >= per or time.time() - t0 > budget:
            continue
        lines = gold[r['task']]
        prog = old.ProgramDag(lines)
        key = old.parse(lines[r['line']])[1]
        scope = prog.texts(prog.random_order(0, prog.ancestors(key)))
        if len(scope) != r['nscope']:
            continue
        q, picks, aligned, heads_ok, sec, dag, leaves, _e, _c = env.walk(r['task'], k, scope, r['target'], 'x')
        mine = [p['q_bits'] for p in picks]
        theirs = bits.get((r['task'], r['line']), [])
        t['forms'] += 1
        t['total_equal'] += q.get('total') == r['total']
        same = len(mine) == len(theirs) and all(abs(a - b) < 1e-3 for a, b in zip(mine, theirs))
        t['bits_equal'] += same
        t['picks'] += len(mine)
        if not same or q.get('total') != r['total']:
            bad.append((r['task'], r['line'], k, q.get('total'), r['total'], len(mine), len(theirs)))
    out = ['walker vs census (steers live, scope and target of the census arm parents seed-0): %s' % tally, 'mismatches: %s' % bad[:8], '%.0f s' % (time.time() - t0)]
    print('\n'.join(out))
    with open(done, 'a') as f:
        f.write('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
