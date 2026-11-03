"""Prints a section of reads.jsonl as lines."""
import json
import os
import sys
H = os.path.dirname(os.path.abspath(__file__)) + '/'
for l in open(H + 'reads.jsonl'):
    r = json.loads(l)
    if sys.argv[1:] and r['section'] not in sys.argv[1:]:
        continue
    print('==', r['section'])
    v = r['value']
    for k, x in v.items():
        if isinstance(x, dict) and 'any' in x:
            print(k)
            for g in ('any', 'RULE', 'DET', 'INIT'):
                print('   ', g, json.dumps(x[g]))
        elif isinstance(x, dict) and ('per_form' in x or 'pooled' in x):
            print(k)
            for u, t in x.items():
                for g in ('any', 'RULE', 'DET', 'INIT'):
                    print('   ', u, g, json.dumps(t[g]))
        else:
            print(k, json.dumps(x)[:1200])
