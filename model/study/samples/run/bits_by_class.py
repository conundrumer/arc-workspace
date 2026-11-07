#!/usr/bin/env python
"""bits_by_class.py POINTS MODEL OUT.json [--tasks N] [--workers W]: where a ground truth query's bits go under a tree: by the class of the answer token and the query's kind, and the distribution of bits per (sample, kind)'s target. Run with the kit's runtime python."""
import argparse, base64, collections, gzip, json, multiprocessing as mp, sys, time
from pathlib import Path
import io, zstandard


def open_points(path):
    """A points file's lines: streamable zstd, or gzip where an older file has it."""
    if str(path).endswith('.zst'):
        return io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(open(path, 'rb'), read_across_frames=True), encoding='utf-8')
    import gzip
    return gzip.open(path, 'rt')


import numpy as np
import lightgbm as lgb
CLASSES = ('kind', 'proposer', 'component', 'port', 'relation', 'table', 'column', 'field', 'label join', 'fresh label', 'key label', 'zero', 'operator', 'END', 'ALSO', 'OR', 'NOT', 'IF', 'ONE', 'other')
MODEL = {}
def load(path):
    MODEL['b'] = lgb.Booster(model_file=path); MODEL['u'] = json.loads(Path(path).with_suffix('.uses.json').read_text())
def one(path):
    booster, uses = MODEL['b'], MODEL['u']
    with open_points(path) as f:
        head = json.loads(f.readline())
        names = head['vector_names']; pc = head['vector_point_cols']; oc = [i for i in range(len(names)) if i not in set(pc)]
        at = {names[c]: k for k, c in enumerate(list(pc) + oc)}
        cols = [at[u] for u in uses]
        cls_at = at['token:class']
        by = collections.Counter(); count = collections.Counter(); ids_of = collections.Counter(); first = {}; cost = collections.Counter()
        for line in f:
            if not line.startswith('{"record":"point"') and not line.startswith('{"record": "point"'):
                continue
            r = json.loads(line)
            n = len(r['ids'])
            if not r['positive']:
                continue
            key = (r['sample'], r['kind'])
            if key not in first or r['length'] < first[key][0]:
                first[key] = (r['length'], r['live'])
            if n < 2:
                continue
            vp = np.frombuffer(base64.b64decode(r['vp']), '<f4'); vo = np.frombuffer(base64.b64decode(r['vo']), '<f4').reshape(n, -1)
            X = np.concatenate([np.broadcast_to(vp, (n, len(vp))), vo], 1)
            M = X[:, cols]
            s = booster.predict(M, raw_score=True, num_threads=1)
            e = np.exp(s - s.max()); p = e[r['positive']].sum() / e.sum()
            bits = r['live'] * -float(np.log2(p))
            c = CLASSES[int(X[r['positive'][0], cls_at])]
            by[r['kind'], c] += bits; count[r['kind'], c] += r['live']; ids_of[r['kind'], c] += r['live'] * n
            cost[key] += bits
    per = [(k[1], cost[k] / max(first[k][1], 1), first[k][1]) for k in cost]
    return dict(by={'|'.join(k): v for k, v in by.items()}, count={'|'.join(k): v for k, v in count.items()}, ids={'|'.join(k): v for k, v in ids_of.items()}, per=per)
if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('points'); ap.add_argument('model'); ap.add_argument('out'); ap.add_argument('--tasks', type=int, default=0); ap.add_argument('--workers', type=int, default=3)
    a = ap.parse_args()
    files = sorted((Path(a.points) / 'dev/points/ordered').glob('*.jsonl.*'))[:a.tasks or None]
    by, count, ids, per = collections.Counter(), collections.Counter(), collections.Counter(), []
    t0 = time.time()
    with mp.Pool(a.workers, initializer=load, initargs=(a.model,)) as pool:
        for i, g in enumerate(pool.imap_unordered(one, files), 1):
            by.update(g['by']); count.update(g['count']); ids.update(g['ids']); per += g['per']
            if i % 40 == 0 or i == len(files):
                print(f'{i}/{len(files)} {time.time() - t0:.0f}s', flush=True)
    targets = collections.Counter()
    for k, c, n in per:
        targets[k] += n
    json.dump(dict(by=by, count=count, ids=ids, per=per), open(a.out, 'w'))
    for kind in ('DET', 'RULE', 'INIT'):
        total = sum(v for k, v in by.items() if k.startswith(kind + '|'))
        print(f'{kind}: {targets[kind]} targets, mean {total / max(targets[kind], 1):.2f} bits; median of (sample, kind) means {np.median([c for k, c, n in per if k == kind]):.2f}; share of (sample, kind) under 8, 10, 12, 16 bits: ' + ', '.join('%.2f' % np.mean([c < b for k, c, n in per if k == kind]) for b in (8, 10, 12, 16)))
        for k, v in sorted(((k, v) for k, v in by.items() if k.startswith(kind + '|')), key=lambda x: -x[1])[:9]:
            print(f'   {k.split("|")[1]:<12} {v / max(targets[kind], 1):6.2f} bits per query  {count[k] / max(targets[kind], 1):5.2f} points per query  {v / max(count[k], 1):5.2f} bits per point  {ids[k] / max(count[k], 1):6.1f} ids per point')
