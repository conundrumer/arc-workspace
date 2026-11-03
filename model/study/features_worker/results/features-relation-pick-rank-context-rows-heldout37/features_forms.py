#!/usr/bin/env python
"""Lists the RULE forms of the corpus's non-held tasks by part, and checks that no held or evaluation task is in a list.

Writes forms-test.json and forms-train.json in the run folder: rows with the task at [4] and the line at [5]. A form whose body is a proposer alone is left out, as live_rows.py leaves it out.
"""
import gzip
import json
import os
import re
import zlib

R = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
W = R + 'sampler/sampler-worker/'
OUT = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-relation-pick-rank-context-rows-heldout37/'
CORPUS = R + 'sampler/corpus-v3mix/'
leave = set(open(W + 'held/leave_out.txt').read().split())
held = set(open(W + 'held/tasks.txt').read().split())
assert held <= leave
tasks = sorted(t for t in os.listdir(CORPUS) if t not in leave and os.path.exists(CORPUS + t + '/pairs.jsonl.gz'))
parts = {'test': [], 'train': []}
counts = {'test': set(), 'train': set()}
for t in tasks:
    with gzip.open(CORPUS + t + '/pairs.jsonl.gz', 'rt') as f:
        lines = [x for x in json.loads(f.readline())['gold_sexp'].splitlines() if x.strip()]
    part = 'test' if zlib.crc32(('test' + t).encode()) % 6 == 0 else 'train'
    for i, x in enumerate(lines):
        if x.split()[0].lstrip('(') == 'RULE' and not re.match(r'\((RULE|DET) \S+ [A-Za-z]\S*\)$', x.strip()):
            parts[part].append(['RULE', '', 0, 0, t, i])
            counts[part].add(t)
for p, v in parts.items():
    assert not {r[4] for r in v} & leave
    json.dump(v, open(OUT + 'forms-%s.json' % p, 'w'))
    print(p, len(counts[p]), 'tasks', len(v), 'forms')
