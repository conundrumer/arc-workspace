"""Throwaway: compares the run's gold (kit points-eval.json) and the census base gold, task by task, and lists the cover events."""
import json
import collections
import re

SP = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/'
B = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-helper-forms/gold-v3-helper-forms-a036da074/'
W = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/'
RUN = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/runs/search-pool-factored-priors-heldout35-600s-ship7/'
held = open(W + 'held/tasks.txt').read().split()
base = {p['task']: p['gold_sexp'] for p in json.load(open(B + 'points-base.json'))}
kit = {p['task']: p['gold_sexp'] for p in json.load(open(SP + 'kit23-extract/kit23/points-eval.json'))}
fact = {p['task']: p['gold_sexp'] for p in json.load(open(SP + 'kit23-extract/kit23/golds-factored.json'))}
print(len(kit), len(fact))
tot = collections.Counter()
for t in held:
    a = [x for x in base[t].splitlines() if x.strip()]
    b = [x for x in kit.get(t, '').splitlines() if x.strip()]
    c = [x for x in fact.get(t, '').splitlines() if x.strip()]
    same = sum(x in set(b) for x in a)
    eq = a == b
    hd = sum(re.match(r'\(\w+ &r\d+', x)[0] == re.match(r'\(\w+ &r\d+', y)[0] if re.match(r'\(\w+ &r\d+', x) and re.match(r'\(\w+ &r\d+', y) else False for x, y in zip(a, b))
    print(t, 'base', len(a), 'kit', len(b), 'factored', len(c), 'equal lines', same, 'same list', eq, 'head positions', hd)
    tot['same' if eq else 'diff'] += 1
print(tot)
t = '5961cc34'
a = [x for x in base[t].splitlines() if x.strip()]
b = [x for x in kit[t].splitlines() if x.strip()]
for x in a:
    print('BASE', x[:140])
for x in b:
    print('KIT ', x[:140])
for arm in ('factored_search', 'control_search'):
    print(arm, [(e['event'], e['gold'], e.get('node'), e['seconds']) for e in map(json.loads, open('%s%s/%s.events.jsonl' % (RUN, arm, t))) if e['event'].startswith('cover')])
