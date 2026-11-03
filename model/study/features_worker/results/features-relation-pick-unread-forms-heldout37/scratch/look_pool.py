"""Throwaway look at one task of the pool run: event kinds, node fields, tags, parents."""
import collections
import json
import subprocess
import sys
import time

RUN = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/runs/search-pool-factored-priors-heldout35-600s-ship7/'
arm, task = sys.argv[1], sys.argv[2]
ev = [json.loads(x) for x in open('%s%s/%s.events.jsonl' % (RUN, arm, task))]
print(collections.Counter(e.get('event') for e in ev))
seen = set()
for e in ev:
    if e.get('event') not in seen:
        seen.add(e.get('event'))
        print(json.dumps(e)[:400])
done = json.load(open('%s%s/%s.done.json' % (RUN, arm, task)))
print({k: v for k, v in done.items() if k != 'counts'})
t0 = time.time()
p = subprocess.Popen(['zstd', '-dc', '%s%s/%s.nodes.jsonl.zst' % (RUN, arm, task)], stdout=subprocess.PIPE, text=True, bufsize=1 << 20)
keys, kinds, tags = collections.Counter(), collections.Counter(), collections.Counter()
nodes = []
for line in p.stdout:
    d = json.loads(line)
    x = d.pop('x_rows', None)
    keys.update(d.keys())
    kinds[(d.get('clause') or '').split()[0]] += 1
    t = d.get('tags') or {}
    tags[(t.get('kind'), t.get('seeded'))] += 1
    nodes.append(d)
p.wait()
print(len(nodes), 'nodes', round(time.time() - t0, 2), 's')
print(keys)
print(kinds)
print(tags)
for n in nodes[:3] + nodes[60:64] + nodes[-3:]:
    print(json.dumps(n)[:700])
reads = collections.Counter()
for n in nodes:
    for q in n.get('parents') or []:
        reads[q if not isinstance(q, list) else tuple(q)] += 1
print('nodes read', len(reads), 'of', len(nodes))
print(list(reads.items())[:10])
