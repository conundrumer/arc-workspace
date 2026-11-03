"""Case reads on the non-held tasks: why each RIGID_DET task misses, and what the false hits are.

For each RIGID_DET task, s8 and m8 shapes with at least 3 cells and 2 D4 images, colors free:
  in  classes in the inputs; inpose classes with 2 poses in the inputs;
  copied classes that reappear in a train output; outpose classes with 2 poses in the outputs of those;
  moved copied classes with a copy in changed cells;
  outonly classes of the outputs with 2 poses that no input shows.

For each plain task hit by a fixed form, kind of false hit, first that applies:
  mirror   a same-size output with a mirror or a turn symmetry the input lacks
  tile     an output larger than the input
  crop     an output smaller than the input
  in-place same-size grids, with some hit at the same pose too
  other    the rest

  features_cases.py ROWS...
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
src = open(HERE + 'features_shape_posed.py').read().rsplit('\nmain()\n', 1)[0]
fp = {'__file__': HERE + 'features_shape_posed.py', '__name__': 'fp'}
exec(compile(src, 'features_shape_posed.py', 'exec'), fp)
load, instances, norm, images = fp['load'], fp['instances'], fp['norm'], fp['images']


def classes(grids, kind):
    out = collections.defaultdict(set)
    for g in grids:
        for cells in instances(g, {kind})[kind]:
            if 3 <= len(cells) <= fp['MAXS']:
                p = norm(cells, 'free')
                ims = images(p)
                if len(ims) >= 2:
                    out[min(ims)].add(p)
    return out


def symmetric(g):
    up = g[::-1]
    side = [r[::-1] for r in g]
    turn = [r[::-1] for r in up]
    tr = [list(x) for x in zip(*g)]
    return g == up or g == side or g == turn or g == tr


rows = []
for p in sys.argv[1:]:
    rows += [json.loads(x) for x in open(p)]
by = {r['task']: r for r in rows}
print('task group | kind in inpose copied outpose moved outonly')
for r in sorted(rows, key=lambda r: (r['group'], r['task'])):
    if r['group'] not in ('positive', 'one-pose'):
        continue
    train, tests = load(r['task'])
    ins, outs = [a for a, _ in train] + tests, [o for _, o in train]
    sizes = sorted({(len(a), len(a[0]), len(o), len(o[0])) for a, o in train})
    line = []
    for kind in ('s8', 'm8'):
        ci, co = classes(ins, kind), classes(outs, kind)
        both = set(ci) & set(co)
        line.append(f"{kind} {len(ci)} {sum(len(v) >= 2 for v in ci.values())} {len(both)} {sum(len(co[k]) >= 2 for k in both)} {sum(len(co[k] - ci[k]) > 0 for k in both)} {sum(len(v) >= 2 for k, v in co.items() if k not in ci)}")
    print(r['task'], r['group'], '|', ' | '.join(line), '| same size' if all(s[:2] == s[2:] for s in sizes) else f'| sizes {sizes[:2]}')

FALSE_FORMS = ('base', 'task-several', 'other', 'win')
kinds = {f: collections.defaultdict(list) for f in FALSE_FORMS}
for r in rows:
    if r['group'] != 'plain' or r['whole'][0] + r['whole'][1]:
        continue
    for f in FALSE_FORMS:
        if not r['forms'][f][0]:
            continue
        train, _ = load(r['task'])
        same = all(len(a) == len(o) and len(a[0]) == len(o[0]) for a, o in train)
        if same and any(symmetric(o) and not symmetric(a) for a, o in train):
            k = 'mirror'
        elif any(len(o) * len(o[0]) > len(a) * len(a[0]) for a, o in train):
            k = 'tile'
        elif any(len(o) * len(o[0]) < len(a) * len(a[0]) for a, o in train):
            k = 'crop'
        elif r['forms'][f][1]:
            k = 'in-place'
        else:
            k = 'other'
        kinds[f][k].append(r['task'])
for f, d in kinds.items():
    print(f, {k: (len(v), v[:6]) for k, v in sorted(d.items(), key=lambda x: -len(x[1]))})
apart = [r for r in rows if r['whole'][0] + r['whole'][1]]
print('set apart', len(apart), 'base hits', sum(r['forms']['base'][0] for r in apart), 'other hits', sum(r['forms']['other'][0] for r in apart), [r['task'] for r in apart if r['forms']['base'][0]][:6])
