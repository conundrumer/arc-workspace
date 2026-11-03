"""The fact on one fixed table: the single-color 8-connected components of the grids of a task, each a reading, in train inputs and test inputs, and in train outputs.

A class is a set of components equal up to D4 and translation, of at least MIN_ROWS cells and at least 4 D4 images. It counts where it holds 2 poses. For each side (inputs, outputs): classes that count, instances in them, their share of all components with at least 4 images, and whether a counted class has its poses in 2 examples.

  features_rigid_grid_read.py GROUPS OUT
"""
import collections
import json
import math
import sys

MIN_ROWS = 3
D4 = (lambda r, c: (r, c)), (lambda r, c: (r, -c)), (lambda r, c: (-r, c)), (lambda r, c: (-r, -c)), (lambda r, c: (c, r)), (lambda r, c: (c, -r)), (lambda r, c: (-c, r)), (lambda r, c: (-c, -r))


def norm(cells):
    r, c = min(x[0] for x in cells), min(x[1] for x in cells)
    return tuple(sorted((x[0] - r, x[1] - c) for x in cells))


def components(g):
    bg = collections.Counter(v for row in g for v in row).most_common(1)[0][0]
    seen, out = set(), []
    for i, row in enumerate(g):
        for j, v in enumerate(row):
            if v == bg or (i, j) in seen:
                continue
            stack, cells = [(i, j)], []
            seen.add((i, j))
            while stack:
                a, b = stack.pop()
                cells.append((a, b))
                for x in a - 1, a, a + 1:
                    for y in b - 1, b, b + 1:
                        if 0 <= x < len(g) and 0 <= y < len(row) and (x, y) not in seen and g[x][y] == v:
                            seen.add((x, y))
                            stack.append((x, y))
            out.append(cells)
    return out


def side(grids):
    classes = collections.defaultdict(lambda: collections.defaultdict(set))
    n = total = 0
    for at, g in enumerate(grids):
        for cells in components(g):
            if len(cells) < MIN_ROWS:
                continue
            forms = {norm([f(*x) for x in cells]) for f in D4}
            if len(forms) >= 4:
                total += 1
                classes[min(forms)][norm(cells)].add(at)
                n += 1
    hit = {k: v for k, v in classes.items() if len(v) >= 2}
    return dict(classes=len(hit), instances=sum(len(a) for v in hit.values() for a in v.values()), share=sum(len(a) for v in hit.values() for a in v.values()) / max(total, 1),
                across=sum(len({e for a in v.values() for e in a}) >= 2 for v in hit.values()), poses=max((len(v) for v in hit.values()), default=0))


rows = []
for line in open(sys.argv[1]):
    group, *stems = line.split()
    for t in stems:
        d = json.load(open(f'data/tasks/{t}.json'))
        a = side([p['input'] for p in d['train'] + d['test']])
        b = side([p['output'] for p in d['train']])
        rows.append(dict(task=t, group=group, input=a, output=b))
json.dump(rows, open(sys.argv[2], 'w'))
by = collections.defaultdict(list)
for r in rows:
    by[r['group']].append(r)
pos, neg = by['positive'], by['plain']
base = len(pos) / (len(pos) + len(neg))
print({g: len(v) for g, v in by.items()})
stats = {f'{s} {k}': (lambda r, s=s, k=k: r[s][k]) for s in ('input', 'output') for k in ('classes', 'instances', 'share', 'across', 'poses')}
stats['input or output poses'] = lambda r: max(r['input']['poses'], r['output']['poses'])
for name, f in stats.items():
    auc = sum((f(a) > f(b)) + .5 * (f(a) == f(b)) for a in pos for b in neg) / (len(pos) * len(neg))
    best = None
    for bar in sorted({f(r) for r in pos + neg}):
        tp, fp = sum(f(r) >= bar and f(r) > 0 for r in pos), sum(f(r) >= bar and f(r) > 0 for r in neg)
        if tp >= len(pos) / 2:
            bits = math.log2(tp / (tp + fp) / base)
            if best is None or bits > best[0]:
                best = bits, bar, tp, fp
    print(f'{name}: AUC {auc:.2f}', 'best bar at recall .5 or more: %.2f bits, bar %.2f, positive %d, plain %d' % best if best else 'no bar at recall .5', '|', ' '.join(f'{g} {sum(f(r) > 0 for r in v)}/{len(v)}' for g, v in by.items()))
