"""Per held form: its primary reader, the reader's census bits, the bits of that reader with the read left open, and what the rest of its body offers a table check.

Reads records only: form rows and census walks of features-next-form-content-given-task-heldout37, per-form-held.jsonl of features-backward-from-out-content-heldout37, census forms. No engine, no search. Writes edge-rows.jsonl beside this file.

reader_open_bits = reader total - bits of the pick that names the read form + bits of the choice "some derived relation" at that pick, on gold's written-order census walk.
"""
import collections
import json
import math
import os
import re
import subprocess
import sys

W = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
FB = W + 'features-worker/results/features-backward-from-out-content-heldout37/'
FN = W + 'features-worker/results/features-next-form-content-given-task-heldout37/'
HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
sys.path.insert(0, FB)
import backward_edges as E  # noqa: E402

rows = collections.defaultdict(list)
for x in open(FN + 'rows-held/form-rows-held-0.jsonl'):
    r = json.loads(x)
    rows[r['task']].append(r)
for t in rows:
    rows[t].sort(key=lambda r: r['form'])
per = {(r['task'], r['form']): r for r in map(json.loads, open(FB + 'per-form-held.jsonl'))}
walk = subprocess.run(['zstd', '-dc', FN + 'walks-held/walk-held-0.jsonl.zst'], capture_output=True).stdout.decode()
walks = {(r['task'], r['form']): r for r in map(json.loads, walk.splitlines())}
HEAD = re.compile(r'\(\w+ (&r\d+)')
out = []
for t, forms in rows.items():
    edges, depth, prim, atoms, oat, c = E.task_edges('held', t, forms)
    heads = sorted((int(m[1]), i) for i, r in enumerate(forms) for m in [re.match(r'\(\S+\s+&r(\d+)', r['text'] or '')] if m)
    slots = {}
    for i, (h, g) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else h + 1
        for k in range(h, max(end, h + 1)):
            slots[k] = g
    n = len(forms)
    for f, e in prim.items():
        reader, j, _, _ = e
        p = per[t, f]
        d = dict(task=t, form=f, kind=p['kind'], bits=p['bits'], saved=p.get('t1 full', 0.0), depth=depth[f], reader='OUT' if reader == n else reader, reader_kind='OUT' if reader == n else forms[reader]['kind'])
        if reader == n:
            d.update(reader_bits=0.0, reader_open_bits=0.0, reader_reads=1, reader_atoms=len(oat), rest_atoms=len(oat) - 1, shared=None, pick=None)
            out.append(d)
            continue
        q = per[t, reader]
        w = walks.get((t, reader))
        pick = None
        if w:
            for pk in w['picks']:
                m = re.match(r'&r(\d+)', pk.get('gold') or '')
                if m and slots.get(int(m[1])) == f:
                    pick = pk
                    break
        rd = [x for x in forms[reader]['reads'] if x[1] == 'relation' and x[2] is not None]
        at = atoms[reader]
        rest = [a for i, a in enumerate(at) if i != j and not a['neg']]
        hole_labs = {s[1] for s in at[j]['sites'] if s[1] is not None} if j is not None else set()
        rest_labs = {s[1] for a in rest for s in a['sites'] if s[1] is not None}
        d.update(reader_bits=q['bits'], reader_atoms=len(at), rest_atoms=len(rest), reader_reads=len({x[2] for x in rd}), shared=len(hole_labs & rest_labs), hole_labels=len(hole_labs), in_port=bool(j is not None and at[j].get('port')), in_or=bool(j is not None and at[j].get('ors')))
        if pick is not None and q['bits'] is not None:
            tot = sum(x[2] for x in pick['rels'])
            dsum = sum(x[2] for x in pick['rels'] if x[1] == 'd')
            class_bits = -math.log2(dsum / tot) if dsum > 0 else 0.0
            d.update(pick=pick['q_bits'], class_bits=round(class_bits, 3), n_derived=sum(x[1] == 'd' for x in pick['rels']), reader_open_bits=round(q['bits'] - pick['q_bits'] + class_bits, 2))
        else:
            d.update(pick=None, reader_open_bits=None)
        out.append(d)
with open(HERE + 'edge-rows.jsonl', 'w') as f:
    for d in out:
        f.write(json.dumps(d) + '\n')
print(len(out), sum(d['reader_open_bits'] is not None for d in out), collections.Counter(d['reader_kind'] for d in out))
