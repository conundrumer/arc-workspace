#!/usr/bin/env python
"""atom_fit.py convert OUT ROOT | fit OUT ARM [--threads T] | report OUT ARM...: a softmax over a decision's candidate atoms, read against the token tree on the same candidates.

ROOT holds train_* and dev_* folders of atom_rows.py. Each decision's first candidate is the positive. A decision whose positive is outside the tree's top TOP atoms is left out, and each other is cut to those atoms, so a set holds what a live set holds. Arms: nt, the point, the relation token and the atom's structure, with no table of the atom; t, those and the body table with the atom added, and its difference from the body before. report prints dev bits per decision, over a decision's candidates, for each arm and for the tree (the sum of its token bits over a candidate's path, as a softmax over these candidates), by source and by kind."""
import argparse, base64, collections, glob, io, json, pickle, sys, time
from pathlib import Path
import numpy as np
import zstandard
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from study_paths import REPO_ROOT  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / 'model/feature_eval'))
import block_fit  # noqa: E402

block_fit.MAX_BIN, block_fit.SAMPLE_CAP = 255, 200000
TOP = 12  # the atoms of a decision: the tree's top ones, with the true atom among them
PARAMS = dict(learning_rate=0.05, num_leaves=31, min_data_in_leaf=50, min_sum_hessian=1e-3, fraction=0.8, max_rounds=1500, patience=60, seed=0)
NONE = 0xFFFFFFFF


def lines(path):
    return io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(open(path, 'rb'), read_across_frames=True), encoding='utf-8')


def dump(path, value):
    with zstandard.ZstdCompressor(level=3).stream_writer(open(path, 'wb')) as sink:
        pickle.dump(value, sink, protocol=5)


def load(path):
    with zstandard.ZstdDecompressor().stream_reader(open(path, 'rb')) as source:
        return pickle.load(source)


def arr(text, shape=None):
    x = np.frombuffer(base64.b64decode(text), '<f4')
    return x.reshape(shape) if shape else x


def convert(out, root):
    out, root = Path(out), Path(root)
    (out / 'blocks').mkdir(parents=True, exist_ok=True)
    block_fit.BlockMatrix.folder = out / 'blocks'
    head = None
    for split in ('train', 'dev'):
        point, cand, table = block_fit.BlockMatrix(), block_fit.BlockMatrix(), block_fit.BlockMatrix()
        at_table = {}
        points, labels, starts, of_point, table_of, tree_bits = [], [], [0], [], [], []
        ranks = collections.defaultdict(list)
        decisions = []
        t0 = time.time()
        files = sorted(root.glob(f'{split}_*/*.atoms.zst'))
        for done, path in enumerate(files, 1):
            source = path.parent.name.split('_', 1)[1]
            with lines(path) as f:
                head_here = json.loads(f.readline())
                head = head or head_here
                n_tok, n_struct, n_av = len(head['tok_names']), len(head['struct_names']), len(head['av_names'])
                task = head_here['task']
                for line in f:
                    r = json.loads(line)
                    n = r['n']
                    bits = np.array(r['bits'], np.float64)
                    by = np.argsort(bits, kind='stable')
                    rank = int(np.flatnonzero(by == 0)[0])
                    ranks[source + ' ' + r['kind']].append(rank)
                    outside = bits[1:]
                    top = np.sort(outside)[:TOP]
                    decisions.append(dict(task=task, sample=r['sample'], kind=r['kind'], source=source, length=r['length'], gold=float(bits[0]), mass=float(min(1.0, (2.0 ** -np.sort(bits)[:TOP]).sum())), kept=-1 if n < 2 or rank >= TOP else len(points)))
                    if n < 2 or rank >= TOP:  # the set is the tree's top atoms, as live: an atom outside them would stand out by being there
                        continue
                    chosen = np.sort(by[:TOP])
                    vp = arr(r['point'])
                    at = np.flatnonzero(vp != 0)
                    point.add(at, vp[at])
                    tok = arr(r['tok'], (n, n_tok))[chosen]; st = arr(r['struct'], (n, n_struct))[chosen]; av = arr(r['av'], (n, n_av))[chosen]; de = arr(r['delta'], (n, n_av))[chosen]
                    rows = np.concatenate([tok, st, np.array(r['defined'], np.float32)[chosen, None]], 1)
                    n = len(chosen)
                    where = np.zeros(n, np.uint32)
                    for i in range(n):
                        here = np.flatnonzero(rows[i] != 0)
                        cand.add(here, rows[i][here])
                        joined = np.concatenate([av[i], de[i]])
                        key = (task, joined.tobytes())
                        place = at_table.get(key)
                        if place is None:
                            place = at_table[key] = len(at_table)
                            nz = np.flatnonzero(joined != 0)
                            table.add(nz, joined[nz])
                        where[i] = place
                    table_of.append(where)
                    marks = np.zeros(n, np.uint8); marks[0] = 1
                    labels.append(marks); starts.append(starts[-1] + n); of_point.append(np.full(n, len(points), np.uint32))
                    tree_bits.append(bits[chosen])
                    points.append(dict(task=task, source=source, kind=r['kind'], first=[t[0] for t in r['tokens'][:1]], n=n))
            if done % 25 == 0 or done == len(files):
                print(f'{split} {done}/{len(files)}, {done / (time.time() - t0):.1f}/s, decisions {len(points)}, rows {starts[-1]}, tables {len(at_table)}', flush=True)
        point.write(out / 'blocks' / f'{split}.point.zst'); cand.write(out / 'blocks' / f'{split}.cand.zst'); table.write(out / 'blocks' / f'{split}.table.zst')
        dump(out / f'{split}.pkl.zst', dict(points=points, labels=np.concatenate(labels), starts=np.array(starts, np.uint32), of_point=np.concatenate(of_point), table_of=np.concatenate(table_of), tables=len(at_table), tree_bits=np.concatenate(tree_bits), head=head, decisions=decisions))
        print(split, 'written', len(points), 'decisions', starts[-1], 'rows', collections.Counter(p['source'] for p in points), flush=True)
        for key in sorted(ranks):
            x = np.array(ranks[key])
            print(f'  {split} {key}: {len(x)} decisions, the true atom is the tree\'s first {np.mean(x < 1):.3f}, in its top 4 {np.mean(x < 4):.3f}, 8 {np.mean(x < 8):.3f}, 12 {np.mean(x < 12):.3f}', flush=True)


def plan_of(out, split, work, data, arm):
    plan = block_fit.Plan(work / split, out, split, {})
    rows = len(data['labels'])
    head = data['head']
    plan.map('point', data['of_point'], len(data['points']))
    plan.map('row', np.arange(rows, dtype=np.uint32), rows)
    plan.add('point', len(head['point_names']), 'point', np.arange(len(head['point_names'])), head['point_names'])
    names = head['tok_names'] + ['atom:' + x for x in head['struct_names']] + ['atom:defined']
    keep = np.array([i for i, n in enumerate(names) if arm == 't' or not (n == 'atom:defined' or n.startswith('pq:body'))])
    plan.add('cand', len(names), 'row', keep, [names[i] for i in keep])
    if arm == 't':
        plan.map('table', data['table_of'], data['tables'])
        av = head['av_names']
        table_names = av + ['d' + x[1:] for x in av]
        plan.add('table', len(table_names), 'table', np.arange(len(table_names)), table_names)
    return plan


def fit(out, arm, threads):
    out = Path(out)
    train, dev = load(out / 'train.pkl.zst'), load(out / 'dev.pkl.zst')
    work = out / 'work' / arm
    plan = plan_of(out, 'train', work, train, arm)
    labels = plan.labels
    plan.write(threads)
    if not (work / 'train' / 'nans.u64').exists():
        block_fit.run('scan', work / 'train')
    keep, members = block_fit.kept_columns(work / 'train', labels, PARAMS['min_data_in_leaf'])
    block_fit.raw(work / 'train' / 'keep.i32', keep, np.int32)
    (work / 'columns.json').write_text(json.dumps([labels[m[0]] for m in members]))
    print('columns', len(labels), 'kept', len(members), flush=True)
    if not (work / 'train' / 'compiled.json').exists():
        block_fit.run('compile', work / 'train')
    dev_plan = plan_of(out, 'dev', work, dev, arm)
    dev_plan.write(threads, reference=work / 'train')
    block_fit.raw(work / 'dev' / 'keep.i32', keep, np.int32)
    if not (work / 'dev' / 'compiled.json').exists():
        block_fit.run('compile', work / 'dev')
    for split, data in (('train', train), ('dev', dev)):
        block_fit.raw(work / f'{split}.groups.u32', data['starts'], np.uint32)
        block_fit.raw(work / f'{split}.labels.u8', data['labels'], np.uint8)
    (work / 'fit.json').write_text(json.dumps(dict(PARAMS, threads=threads, train=str(work / 'train'), dev=str(work / 'dev'), out=str(work / 'fits'), groups=str(work / 'train.groups.u32'), labels=str(work / 'train.labels.u8'), dev_groups=str(work / 'dev.groups.u32'), dev_labels=str(work / 'dev.labels.u8'))))
    block_fit.run('softmax', work / 'fit.json')
    print(json.loads((work / 'fits' / 'result.json').read_text()), flush=True)


def query_bits(dev, scores):
    """(median and mean bits per query by source and kind): the token tree's, and for each arm what the live writer gives. A query is a run of a sample's decisions along which the length grows. At a decision whose true atom is in the set, the arm's chance is the set's mass under the token tree times the arm's share of it. From a decision outside the set, the rest of the query goes by tokens, at the mass outside the set and then the token tree's bits."""
    starts = dev['starts'].astype(np.int64)
    share = {}
    for name, s in scores.items():
        got = np.zeros(len(starts) - 1)
        for i in range(len(starts) - 1):
            x = s[starts[i]:starts[i + 1]]
            e = np.exp(x - x.max())
            got[i] = -np.log2(e[0] / e.sum())
        share[name] = got
    queries, here, last = [], [], None
    for d in dev['decisions']:
        key = (d['task'], d['sample'])
        if key != last or (here and d['length'] <= here[-1]['length']):
            if here:
                queries.append(here)
            here, last = [], key
        here.append(d)
    if here:
        queries.append(here)
    table = collections.defaultdict(lambda: collections.defaultdict(list))
    for q in queries:
        tree = sum(d['gold'] for d in q)
        for key in ('all', q[0]['source'], q[0]['source'] + ' ' + q[0]['kind']):
            table[key]['token tree'].append(tree)
        for name in share:
            total, tokens = 0.0, False
            for d in q:
                if tokens:
                    total += d['gold']
                elif d['kept'] < 0:
                    total += -np.log2(max(1.0 - d['mass'], 1e-3)) + d['gold']
                    tokens = True
                else:
                    total += -np.log2(max(d['mass'], 1e-9)) + share[name][d['kept']]
            for key in ('all', q[0]['source'], q[0]['source'] + ' ' + q[0]['kind']):
                table[key][name].append(total)
    print('bits per query, median (mean):')
    for key in sorted(table):
        print('  %-14s %5d  ' % (key, len(table[key]['token tree'])) + '  '.join('%s %.1f (%.1f)' % (name, np.median(v), np.mean(v)) for name, v in table[key].items()))


def report(out, arms):
    out = Path(out)
    dev = load(out / 'dev.pkl.zst')
    starts = dev['starts'].astype(np.int64); bits = dev['tree_bits']
    scores = {'tree': -bits * np.log(2)}
    for arm in arms:
        scores[arm] = np.fromfile(out / 'work' / arm / 'fits' / 'dev_best.f64', dtype=np.float64)
    table = collections.defaultdict(dict)
    for name, s in scores.items():
        g = collections.defaultdict(list)
        for i, p in enumerate(dev['points']):
            lo, hi = starts[i], starts[i + 1]
            x = s[lo:hi]
            e = np.exp(x - x.max())
            b = -np.log2(e[0] / e.sum()); top = float(x[0] >= x.max())
            for key in ('all', p['source'], p['source'] + ' ' + p['kind']):
                g[key].append((b, top))
        for k, v in g.items():
            table[k][name] = (len(v), float(np.mean([a for a, _ in v])), float(np.mean([c for _, c in v])))
    for k in sorted(table):
        print('%-16s %6d  ' % (k, table[k]['tree'][0]) + '  '.join('%s %.3f bits, top %.3f' % (name, v[1], v[2]) for name, v in table[k].items()))
    query_bits(dev, {name: s for name, s in scores.items() if name != 'tree'})


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('command'); ap.add_argument('out'); ap.add_argument('arms', nargs='*'); ap.add_argument('--threads', type=int, default=3)
    a = ap.parse_args()
    if a.command == 'convert':
        convert(a.out, a.arms[0])
    elif a.command == 'fit':
        fit(a.out, a.arms[0], a.threads)
    else:
        report(a.out, a.arms)
