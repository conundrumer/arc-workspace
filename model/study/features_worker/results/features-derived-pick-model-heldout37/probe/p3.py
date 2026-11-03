"""Probe 3: on one N600 task, the merge keys of every bank form (one replay of the bank in depth order, in chunks), the gold forms whose reads all have
an equal bank relation, and the cost. This is the input of scopes built as the pool builds them.

    bash ../../features-scope-loss-c-read-heldout37-ramp22/env.sh ../features-derived-pick-model-heldout37/probe/p3.py TASK BUDGET
"""
import json
import resource
import sys
import time

sys.path.insert(0, '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-derived-pick-model-heldout37/probe')
T0 = time.time()
import common as C  # noqa: E402

task, budget = sys.argv[1], float(sys.argv[2])
c = C.NCtx(task)
sess, d, _ = C.D.session_of(task)
gk = C.gold_read_keys(c, sess, d)
fs = c.bank['forms']
order = sorted(fs, key=lambda f: (fs[f].depth, f))
key_of = {}
t1 = time.time()
n = 0
for f in order:
    if time.time() - T0 > budget:
        break
    anc, todo = set(), [f]
    while todo:
        x = todo.pop()
        if x not in anc:
            anc.add(x)
            todo += list(fs[x].parents)
    texts = [fs[x].text for x in sorted(anc, key=lambda x: (fs[x].depth, x))]
    rel = C.relations(texts, sess, d)
    for (h, j), v in rel.items():
        if h == '&f%d' % f:
            key_of.setdefault(v['key'], f)
    n += 1
el = time.time() - t1
readable = [(g, kind) for g, kind, keys, own in gk if keys <= set(key_of)]
print('bank forms %d replayed %d in %.1fs (%.1f ms a form), rss %.2f GiB; gold forms %d, with derived reads %d, all reads in the bank %d %s' % (
    len(fs), n, el, 1000 * el / max(n, 1), resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 30, len(c.lines), len(gk), len(readable), readable), flush=True)
print('depth of bank forms:', json.dumps(dict(sorted(__import__('collections').Counter(fs[f].depth for f in fs).items()))))
