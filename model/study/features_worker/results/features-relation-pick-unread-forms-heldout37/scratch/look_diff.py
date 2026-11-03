"""Throwaway: the two forms whose walk differs from the census."""
import json
import sys
sys.path.insert(0, '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-relation-pick-unread-forms-heldout37')
import features_unread_lib as L
D = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-relation-pick-unread-forms-heldout37/'
cen = {}
for x in open(L.BASE + 'census-base.jsonl'):
    r = json.loads(x)
    if r['scope'] == 'before':
        cen[(r['task'], r['line'])] = r
walk = {}
for x in open(D + 'walk-held-before.jsonl'):
    r = json.loads(x)
    walk[(r['task'], r['line'])] = r
for k in (('269e22fb', 5), ('8e5c0c38', 8)):
    a, b = cen[k], walk[k]
    print(k, a['target'][:300])
    print(' census', a['total'], a['parts'], a['bad'], a['fell_back'] if 'fell_back' in a else None)
    print(' walk  ', b['total'], b['bad'])
    print(' census atoms', a['atoms'], [d['cur'] for d in a['detail']])
    print(' walk atoms', b['atoms'], [d['cur'] for d in b['detail']])
    print(' walk picks', [(p['phase'], p['k'], p['gold'], p['q_bits']) for p in b['picks']])
