"""Vocabulary of form-shape features from R120 and N600 clauses only: 80 relations, ports read from forms, op names.

  features_node_vocab.py SECONDS [R120_STEP]
Reads N600's export (clause field) and every R120_STEP-th R120 task (default 8). Writes vocab.json. One pass; no resume.
"""
import collections, json, os, subprocess, sys, time
HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-score-refit-loop/'  # the data folder
sys.path.insert(0, HERE)
import features_node_shape as SH
T0 = time.time(); LIMIT = float(sys.argv[1]); STEP = int(sys.argv[2]) if len(sys.argv) > 2 else 8
W = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/'
rel, port, ops = collections.Counter(), collections.Counter(), collections.Counter()
seen = collections.Counter()
def scan(path, field, src):
    p = subprocess.run(['zstd', '-dcq', path], capture_output=True, text=True)
    cl = set()
    for l in p.stdout.splitlines():
        try:
            r = json.loads(l)
        except ValueError:
            continue
        cl.add(r.get(field))
    for c in cl:
        if not c:
            continue
        h, ps, op = SH.vocab_counts(c)
        rel.update(h); port.update(ps); ops[op] += 1
    seen[src] += 1
N = W + 'sampler-node-export-train50/nodes/'
for f in sorted(os.listdir(N)):
    if time.time() - T0 > LIMIT * .6: break
    scan(N + f, 'clause', 'n600')
R = W + 'sampler-cover-clauses-train-120s-c87cf482a/out/'
fs = sorted(f for f in os.listdir(R) if f.endswith('.nodes.jsonl.zst'))[::STEP]
for f in fs:
    if time.time() - T0 > LIMIT: break
    scan(R + f, 'clause', 'r120')
ops.pop('body', None)
v = dict(relations=[k for k, _ in rel.most_common(80)], ports=[k for k, _ in port.most_common(20)], ops=[k for k, _ in ops.most_common(40)], sources=dict(seen), note='R120 and N600 clauses only')
json.dump(v, open(HERE + 'vocab.json', 'w'), indent=1)
print(dict(seen), 'rel', len(rel), 'ports', len(port), 'ops', len(ops), round(time.time() - T0, 1), 's'); print(v['ports']); print(v['ops'][:15]); print(v['relations'][:20])
