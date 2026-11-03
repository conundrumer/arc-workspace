"""For each draw file (a train task's draws.jsonl): for each drawn query (a draw's last step), its state's gold part (the state's queries that are skeleton queries) and its other part.
Whether the gold part equals a sample's state, so the sample's targets are known there, and how many of those targets the state has not written."""
import collections
import json
import sys
from pathlib import Path

SK = Path(__file__).resolve().parents[4] / "work/lm/data-study/samples/training/skeleton"
for f in sys.argv[1:]:
    draws = [json.loads(l) for l in open(f) if '"steps"' in l]
    task = draws[0]['task']
    recs = [json.loads(l) for l in open(SK / f'{task}.jsonl')]
    gold = {r['hash'] for r in recs if r['record'] == 'query'}
    samples = {frozenset(r['state']['queries']): set(r['target_queries']) for r in recs if r['record'] == 'sample'}
    c = collections.Counter()
    for d in draws:
        st = set(d['steps'][-1]['state'])
        g = frozenset(st & gold)
        c['draws'] += 1
        c['state has non-gold queries'] += bool(st - gold)
        c['gold part empty'] += not g
        if g in samples:
            c['gold part is a sample state'] += 1
            c['  and some target not yet written'] += bool(samples[g] - st)
            c['  drawn query is one of those targets'] += d['steps'][-1]['query_hash'] in samples[g]
    print(task, dict(c))

# The distinct non-gold queries over all draws' states, and the distinct states
for f in sys.argv[1:]:
    draws = [json.loads(l) for l in open(f) if '"steps"' in l]
    task = draws[0]['task']
    gold = {json.loads(l)['hash'] for l in open(SK / f'{task}.jsonl') if '"record": "query"' in l}
    q = {h for d in draws for h in d['steps'][-1]['state']} - gold
    print(task, 'distinct non-gold state queries', len(q), 'distinct states', len({frozenset(d['steps'][-1]['state']) for d in draws}))
