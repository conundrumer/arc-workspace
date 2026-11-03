"""Throwaway: checks of fit-picks.jsonl. Non-held rows only."""
import collections
import json

D = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-relation-pick-unread-forms-heldout37/'
rows = [json.loads(x) for x in open(D + 'fit-picks.jsonl')]
print(len(rows), sum(r['valid'] for r in rows), len({r['task'] for r in rows}))
ps = [p for r in rows for p in r['picks']]
print(len(ps), sum(p['derived'] for p in ps))
d = [abs(p['q'] - p['share']) for p in ps if p['share'] is not None]
print('q vs share: n', len(d), 'max', max(d), 'over .01', sum(x > .01 for x in d), 'none', sum(p['share'] is None for p in ps))
print(collections.Counter(p['phase'] for p in ps))
der = [p for p in ps if p['derived']]
for n in ('unread_later', 'unread_before', 'unread_so_far'):
    print(n, 'inside', sum(p['inside'][n] for p in der) / len(der), 'forms med', sorted(p['n'][n] for p in der)[len(der) // 2], 'opts med', sorted(p['o'][n] for p in der)[len(der) // 2], 'inside and offered', sum(p['inside'][n] and p['o'][n] > 0 for p in der))
