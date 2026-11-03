"""near_read.py with the tables that restate the input and the tables that depend only on the grid's size left out."""
import json, sys, os
H = os.path.dirname(os.path.abspath(__file__))
bins = [('1', lambda j: j == 1), ('.9 to 1', lambda j: .9 <= j < 1), ('.5 to .9', lambda j: .5 <= j < .9), ('over 0 to .5', lambda j: 0 < j < .5), ('0', lambda j: j == 0)]
for T in sys.argv[1:]:
    r = [json.loads(l) for l in open(f'{H}/w/{T}.near.jsonl')]; f = json.load(open(f'{H}/w/{T}.restate.json')); g_ = json.load(open(f'{H}/w/{T}.gridonly.json')); f = {k: f.get(k) or g_.get(k) for k in set(f) | set(g_)}
    k = [x for x in r if not f.get(x['table'])]
    print(T, 'left out', sum(x['side'] == 'gold' for x in r if f.get(x['table'])), '/', sum(x['side'] == 'node' for x in r if f.get(x['table'])), 'left', sum(x['side'] == 'gold' for x in k), '/', sum(x['side'] == 'node' for x in k))
    print('  out:', [x['table'] for x in r if f.get(x['table'])])
    for n, g in bins: print(f"  {n:14} {sum(g(x['jaccard']) and x['side'] == 'gold' for x in k):4} / {sum(g(x['jaccard']) and x['side'] == 'node' for x in k)}")
    print('  met non-gold:', [x['table'] for x in k if x['jaccard'] == 1 and x['side'] == 'node'])
    print('  near:', [(x['side'][0], x['table'], x['jaccard'], x['by']) for x in sorted(k, key=lambda x: -x['jaccard']) if .5 <= x['jaccard'] < 1])
