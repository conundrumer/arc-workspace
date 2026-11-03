"""What a pool proposes: head types and row shapes of the junk nodes of the node records, and a text check of seeded gold against the fit rows' text.

  junk_node_rows.py --out FILE [--tasks N] [--per-task N] [--shard K/N]

One row per junk node of a sample of tasks (hashed order). The row has the attributes of next_form_facts on the node's table. A rerun skips finished tasks. An INIT's relations are separate nodes with one clause: the row is the first node of a clause.
"""
import argparse
import gzip
import hashlib
import io
import json
import os
import random
import re
import sys
import time

import zstandard as zstd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shape_facts as F  # noqa: E402

L = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-corpus-pool-seed1-120s-ship7/level1_search/'
VIEW = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-v3-cover-forms-a036da074/corpus-view/'
WIDE = ('Position', 'Box', 'Offset')
ATOM = re.compile(r'\(([A-Za-z_]\w*) \(:')
HEAD = re.compile(r'\((\S+)\s+(&\S+)\s*(\(|[^\s()]+)?')
NAME = re.compile(r'&[a-z]+\d+')


def attrs(n):
    types = n.get('table_types')
    if not types:
        return None
    widths = [4 if t in WIDE else 1 for t in types]
    offs = [0]
    for w in widths:
        offs.append(offs[-1] + w)
    per = {}
    for e in n['x_rows'] or ():
        per.setdefault(tuple(e[0]), e)
    train = sorted(k for k in per if k[0] == 1) or sorted(per)
    pos = [offs[i] for i, t in enumerate(types) if t == 'Position']
    best, bn = None, -1
    for a in pos:
        v = set()
        for k in train:
            for r in per[k][1]:
                v.add((k, tuple(r[a:a + 4])))
        if len(v) > bn:
            best, bn = a, len(v)
    geom, rel = [], []
    spans = list(zip(offs, offs[1:]))
    for k in train:
        rows = per[k][1]
        tup = [tuple(tuple(r[a:b]) if b - a > 1 else r[a] for a, b in spans) for r in rows]
        rel.append(F.rel_shape(tup, types))
        if best is not None and rows:
            r0 = rows[0]
            geom.append(F.geom_shape({(r[best], r[best + 2]) for r in rows}, r0[best] + r0[best + 1] + 1, r0[best + 2] + r0[best + 3] + 1))
        elif best is not None:
            geom.append('empty')
    return dict(cols='+'.join(sorted(types)), coarse='+'.join(sorted(set(types))), geom=('no position' if 'Position' not in types else F.modal(geom) or 'empty'), rel=F.modal(rel) or 'empty')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--tasks', type=int, default=150)
    ap.add_argument('--per-task', type=int, default=250)
    ap.add_argument('--shard', default='0/1')
    a = ap.parse_args()
    names = sorted((e.name.split('.')[0] for e in os.scandir(L) if e.name.endswith('.nodes.jsonl.zst') and e.stat().st_size), key=lambda t: hashlib.sha1(t.encode()).hexdigest())[:a.tasks]
    k, n = map(int, a.shard.split('/'))
    names = names[k::n]
    done = set()
    if os.path.exists(a.out):
        done = {json.loads(x)['task'] for x in open(a.out)}
    names = [t for t in names if t not in done]
    t0 = time.time()
    dz = zstd.ZstdDecompressor()
    with open(a.out, 'a') as out:
        for i, t in enumerate(names):
            with open(L + t + '.nodes.jsonl.zst', 'rb') as fh:
                lines = list(io.TextIOWrapper(dz.stream_reader(fh), encoding='utf8'))
            rng = random.Random(t)
            rng.shuffle(lines)
            seen, c = set(), 0
            for x in lines:
                if c >= a.per_task:
                    break
                r = json.loads(x)
                if r['tags'].get('kind') != 'junk':
                    continue
                cl = r.get('clause')
                if not cl or cl in seen:
                    continue
                seen.add(cl)
                m = attrs(r)
                if m is None:
                    continue
                h = HEAD.match(cl)
                kind, third = h.group(1), h.group(3)
                m.update(task=t, kind=kind, comp=third if third and third != '(' else None, libs=sorted(set(ATOM.findall(cl))), depth=r.get('depth'))
                out.write(json.dumps(m, separators=(',', ':')) + '\n')
                c += 1
            out.flush()
            rate = (i + 1) / (time.time() - t0)
            print('%d/%d tasks, %.2f tasks/s, eta %.0f s' % (i + 1, len(names), rate, (len(names) - i - 1) / rate), flush=True)


if __name__ == '__main__':
    main()
