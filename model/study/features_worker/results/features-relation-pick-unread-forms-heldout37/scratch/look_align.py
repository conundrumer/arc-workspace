"""Throwaway: where the walk's picks and the census atoms do not align."""
import json
import sys
D = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-relation-pick-unread-forms-heldout37/'
sys.path.insert(0, D)
walk = {}
for x in open(D + 'walk-held-before.jsonl'):
    r = json.loads(x)
    walk[(r['task'], r['line'])] = r
n = 0
for x in open(D + 'part1-forms.jsonl'):
    f = json.loads(x)
    w = walk.get((f['task'], f['line']))
    if not w:
        continue
    i = 0
    msg = []
    for a in f['atoms']:
        for key in ('op', 'rel'):
            if (key == 'op' and a['op_bits'] is None) or (key == 'rel' and a['rel_bits'] is None):
                continue
            if i >= len(w['picks']):
                msg.append(('short', a['atom'], key, a['text'][:50]))
                continue
            p = w['picks'][i]
            i += 1
            if key == 'rel' and p['gold'] != a['rel']:
                msg.append((a['atom'], key, a['text'][:50], p['gold'], p['phase'], p['q_bits'], a['rel_bits']))
    if i != len(w['picks']):
        msg.append(('count', i, len(w['picks']), [p['gold'] for p in w['picks']][i:i + 3]))
    if msg:
        n += 1
        print(f['task'], f['line'], f['kind'], f['valid'], msg[:3])
print(n)
