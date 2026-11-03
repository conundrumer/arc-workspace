"""Every combination of the statistic's factors on the non-held tasks, as a check that the fixed forms miss no better form.

Chosen after the fixed forms were read. Its best row is a maximum over the grid, so it reads high by selection. Writes only the forms that hit a task.

  features_sweep.py --shard i/n OUT
"""
import argparse
import hashlib
import itertools
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
src = open(HERE + 'features_shape_posed.py').read().rsplit('\nmain()\n', 1)[0]
fp = {'__file__': HERE + 'features_shape_posed.py', '__name__': 'fp'}
exec(compile(src, 'features_shape_posed.py', 'exec'), fp)
F, load, build, read, ev, whole = fp['F'], fp['load'], fp['build_input'], fp['read_outputs'], fp['evaluate'], fp['whole_flag']


def grid():
    forms = {}
    for kind, col, match, chg, scope, pose, size, images in itertools.product(
            ('s8', 's4', 'm8', 'cs', 'win'), ('same', 'free'), ('comp', 'embed'), (0, 1), ('pair', 'across', 'task'),
            ('new', 'other', 'several'), (3, 4, 6, 8), (2, 4, 8)):
        if match == 'embed' and kind not in ('s8', 'm8'):
            continue
        if match == 'embed' and size < 4:
            continue
        forms['/'.join(map(str, (kind, col, match, chg, scope, pose, size, images)))] = F(kind, col, match, chg, scope, pose, size, images)
    return forms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shard', default='0/1')
    ap.add_argument('out')
    args = ap.parse_args()
    forms = grid()
    names = list(forms)
    json.dump(names, open(HERE + 'sweep-forms.json', 'w'))
    labels = {}
    for line in open(HERE + 'labels.tsv').read().split('\n')[1:]:
        if line:
            x = line.split('\t')
            labels[x[0]] = x
    keep = ('positive', 'one-pose', 'looks-posed', 'plain')
    tasks = sorted((t for t, x in labels.items() if x[2] == 'train' and x[1] in keep), key=lambda t: hashlib.sha1(t.encode()).hexdigest())
    i, n = map(int, args.shard.split('/'))
    tasks = tasks[i::n]
    done = set()
    if os.path.exists(args.out):
        done = {json.loads(x)['task'] for x in open(args.out) if x.endswith('\n')}
    todo = [t for t in tasks if t not in done]
    need = {(f['kind'], f['col']) for f in forms.values()}
    emb = sorted({(f['kind'], f['col']) for f in forms.values() if f['match'] == 'embed'})
    print(f'shard {args.shard}: {len(tasks)} tasks, {len(done)} done, {len(names)} forms', flush=True)
    t0 = time.time()
    with open(args.out, 'a') as f:
        for at, t in enumerate(todo):
            train, tests = load(t)
            tabs, maps, _ = build(train, tests, need)
            recs, _ = read(train, [o for _, o in train], tabs, maps, emb)
            hits = {}
            for j, nm in enumerate(names):
                v = ev(forms[nm], tabs, recs, len(train))
                if v[0]:
                    hits[j] = [v[2], v[3], round(v[4] / v[5], 3)]
            f.write(json.dumps(dict(task=t, group=labels[t][1], whole=whole(train), hits=hits), separators=(',', ':')) + '\n')
            f.flush()
            fp['IMAGES'].clear()
            rate = (at + 1) / (time.time() - t0)
            print(f'{t} {at + 1}/{len(todo)} {rate:.1f}/s eta {(len(todo) - at - 1) / rate / 60:.1f}m', flush=True)


main()
