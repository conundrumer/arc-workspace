"""Whether a pool node's table holds instances that are equal only up to one D4 element each. One JSON line per task in OUT; a rerun skips finished tasks.

A reading is the set of values of one Position or Offset column at one key: the table's entry, plus up to two other columns. A DET table has one entry, so its key takes at least one column.
- strict: a value as stored, (row, rows after, column, columns after), which a D4 element permutes. It reads a frame part, as `relative` gives one.
- loose: a Position with its reading moved to the reading's least row and column, which stands for a `relative` the try didn't draw.
- all: every reading of the key has at least MIN_ROWS rows and all are one class under D4, with at least 2 different readings.
- some: 2 different readings of at least MIN_ROWS rows are one class under D4; other readings don't count.
A hit also gives the number of D4 images of its reading: 2 is a line or a domino shape, 8 has no symmetry.

  features_rigid_fact.py OUT GROUP RECORD ...
"""
import itertools
import json
import os
import subprocess
import sys
import time

WIDE = {'Box', 'Position', 'Offset'}
SHAPE = {'Position', 'Offset'}
MIN_ROWS = 3
KEY_COLUMNS = 2
D4 = (0, 1, 2, 3), (1, 0, 2, 3), (0, 1, 3, 2), (1, 0, 3, 2), (2, 3, 0, 1), (3, 2, 1, 0), (2, 3, 1, 0), (3, 2, 0, 1)


def columns(types):
    at, out = 0, []
    for t in types:
        w = 4 if t in WIDE else 1
        out.append((at, w))
        at += w
    return out, at


def images(reading):
    return {tuple(sorted(tuple(v[i] for i in g) for v in reading)) for g in D4}


def moved(reading):
    """The D4 images of a reading of cells, each moved to its least row and column."""
    out = set()
    for g in D4:
        cells = [tuple(v[i] for i in g) for v in reading]
        r, c = min(x[0] for x in cells), min(x[2] for x in cells)
        out.add(tuple(sorted((x[0] - r, x[2] - c) for x in cells)))
    return out


def pose(reading):
    """A reading of cells moved to its least row and column: 2 readings at different places in one pose have one value."""
    r, c = min(v[0] for v in reading), min(v[2] for v in reading)
    return tuple(sorted((v[0] - r, v[2] - c) for v in reading))


def classes(readings, image):
    """(whether every reading is one class, the most images of a class with 2 different readings; 0 where none has them)."""
    seen, top = {}, 0
    for form in set(readings):
        i = image(form)
        seen.setdefault(min(i), [set(), len(i)])[0].add(pose(form) if image is moved else form)
    for forms, n in seen.values():
        if len(forms) > 1:
            top = max(top, n)
    return len(seen) == 1 and top > 0, top


def node_hits(r):
    """{(mode, part): most images}: mode strict or loose, part all or some, over every key of one table of r. None where an entry was cut."""
    if any(e[2] != len(e[1]) for e in r['x_rows']):
        return None
    types = r.get('table_types') or r['types']
    spans, width = columns(types)
    shape = [i for i, t in enumerate(types) if t in SHAPE]
    got = {}
    rows = [(tuple(e[0]), row) for e in r['x_rows'] if e[1] and len(e[1][0]) == width for row in e[1]]
    if len(rows) < 2 * MIN_ROWS:
        return got
    task_wide = all(e[0] == 0 for e, _ in rows)
    for p in shape:
        a = spans[p][0]
        rest = [i for i in range(len(types)) if i != p]
        for n in range(1 if task_wide else 0, KEY_COLUMNS + 1):
            for key in itertools.combinations(rest, n):
                at = [spans[i] for i in key]
                groups = {}
                for e, row in rows:
                    groups.setdefault((e, tuple(tuple(row[x:x + w]) for x, w in at)), set()).add(tuple(row[a:a + 4]))
                big = [frozenset(v) for v in groups.values() if len(v) >= MIN_ROWS]
                if len(big) < 2:
                    continue
                whole = len(big) == len(groups)
                for mode, image in ('strict', images), ('loose', moved):
                    if mode == 'loose' and types[p] != 'Position':
                        continue
                    every, top = classes([tuple(sorted(x)) for x in big], image)
                    if top:
                        got['%s some' % mode] = max(got.get('%s some' % mode, 0), top)
                        if every and whole:
                            got['%s all' % mode] = max(got.get('%s all' % mode, 0), top)
    return got


out, group = sys.argv[1], sys.argv[2]
done = set()
if os.path.exists(out):
    done = {json.loads(x)['task'] for x in open(out)}
sink = open(out, 'a')
for path in sys.argv[3:]:
    task = os.path.basename(path)[:8]
    if task in done:
        continue
    kept = dict(nodes=0, dets=0, cut=0, seeded=0, spent=0.0, top=0.0, rows=0)
    first, hits, det_first, det_hits, samples = {}, {}, {}, {}, {}
    for raw in subprocess.Popen(['zstd', '-dcq', path], stdout=subprocess.PIPE).stdout:
        try:
            r = json.loads(raw)
        except ValueError:
            continue
        if 'x_rows' not in r:
            continue
        if (r.get('tags') or {}).get('seeded'):
            kept['seeded'] += 1
            continue
        det = (r['clause'] or '').startswith('(DET')
        t0 = time.perf_counter()
        got = node_hits(r)
        dt = time.perf_counter() - t0
        kept['nodes'] += 1
        kept['dets'] += det
        kept['spent'] += dt
        kept['top'] = max(kept['top'], dt)
        kept['rows'] += sum(e[2] for e in r['x_rows'])
        if got is None:
            kept['cut'] += 1
            continue
        for k, n in got.items():
            for a in 2, 4, 8:
                if n >= a:
                    name = '%s %d' % (k, a)
                    hits[name] = hits.get(name, 0) + 1
                    first.setdefault(name, kept['nodes'])
                    if det:
                        det_hits[name] = det_hits.get(name, 0) + 1
                        det_first.setdefault(name, kept['dets'])
                    samples.setdefault(name, (r['clause'] or '')[:200])
    sink.write(json.dumps(dict(task=task, group=group, **kept, hits=hits, first=first, det_hits=det_hits, det_first=det_first, samples=samples)) + '\n')
    sink.flush()
    print(task, group, kept['nodes'], 'nodes', round(kept['spent'], 2), 's', {k: v for k, v in hits.items() if k.endswith(' 4')}, flush=True)
print('done', flush=True)
