"""Bins of row Jaccard between each main table and its nearest second-DAG table, gold / non-gold."""
import json, sys, os
H = os.path.dirname(os.path.abspath(__file__))
bins = [('1', lambda j: j == 1), ('.9 to 1', lambda j: .9 <= j < 1), ('.5 to .9', lambda j: .5 <= j < .9), ('over 0 to .5', lambda j: 0 < j < .5), ('0', lambda j: j == 0)]
for T in sys.argv[1:]:
    r = [json.loads(l) for l in open(f'{H}/w/{T}.near.jsonl')]
    print(T, 'gold', sum(x['side'] == 'gold' for x in r), 'node', sum(x['side'] == 'node' for x in r))
    for n, f in bins: print(f"  {n:14} {sum(f(x['jaccard']) and x['side'] == 'gold' for x in r):4} / {sum(f(x['jaccard']) and x['side'] == 'node' for x in r)}")
    for x in sorted(r, key=lambda x: -x['jaccard']):
        if 0 < x['jaccard'] < 1: print('   ', x['side'], x['table'], x['rows'], x['jaccard'], x['recall'], x['precision'], x['by'])
