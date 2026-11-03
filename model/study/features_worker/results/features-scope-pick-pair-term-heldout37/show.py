"""Prints sections of reads.jsonl."""
import json, sys
H = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-scope-pick-pair-term-heldout37/'
want = sys.argv[1:]
for l in open(H + 'reads.jsonl'):
    q = json.loads(l)
    if want and q['section'] not in want:
        continue
    v = q['value']
    if q['section'] == 'auc':
        for lab, d in v.items():
            print(lab, d['sets'], d['tasks'])
            for c, r in d['facts'].items():
                print('   %-14s auc %.3f pooled %.3f %s %s' % (c, r['auc'], r['pooled'], r['range'], (r.get('shuffled'), r.get('shuffled_range')) if 'shuffled' in r else ''))
    elif q['section'] == 'together':
        for lab, d in v.items():
            print(lab, d['sets'], d['shuffled_fit'])
            for c, r in d['models'].items():
                print('   %-20s auc %.3f pooled %.3f %s %s' % (c, r['auc'], r['pooled'], r['range'], r['beta_median']))
    elif q['section'] == 'bits':
        for lab, d in v.items():
            print(lab, d['sets'], d['shuffled_fit'])
            for c, r in d['models'].items():
                print('   %-20s %s' % (c, {k: (x['saving'], x['range']) for k, x in r.items() if k in ('first any', 'first_late any', 'out any', 'first_r2 any')}), r['weights'])
            for c, r in d['sensitivity'].items():
                print('   %-22s %s' % (c, {k: x['saving'] for k, x in r.items()}))
    else:
        print(q['section'], json.dumps(v, indent=None)[:6000])
