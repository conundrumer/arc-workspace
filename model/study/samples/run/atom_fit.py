#!/usr/bin/env python
"""atom_fit.py convert OUT ROOT... | fit OUT ARM [--threads T] | report OUT ARM...: a softmax over a decision's candidate atoms, read against the token tree on the same candidates.

A ROOT holds train_* and dev_* folders of atom_rows.py. Each decision's first candidate is the positive. A decision whose positive is outside the tree's top TOP atoms is left out, and each other is cut to those atoms, so a set holds what a live set holds. Arms: nt, the point, the first token and the atom's structure, with no table of the atom; t, those and the body table with the atom added, and its difference from the body before; b, only the tree's bits for the atom and their gap to the set's best; nb and tb, nt and t with those bits; nbs and tbs, those with the candidate's place in its set (set_columns), and tbs also with its table's difference from the set's mean. With --gen FOLDER, convert keeps the tasks that have generated lists there, read by the tg_read.py beside FOLDER, and the arms read them: tg, nb with the lists; tg_null, nb with the control's lists; tgt, tb with the lists. report prints dev bits per decision, over a decision's candidates, for each arm and for the tree (the sum of its token bits over a candidate's path, as a softmax over these candidates), by source and by kind."""
import argparse, base64, collections, glob, io, json, os, pickle, sys, time
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


SET_NAMES = ['atom:bits_rank', 'atom:bits_share', 'atom:same_first', 'atom:first_share']


def set_columns(bits, first):
    """A candidate's place in its set: its rank by the tree's bits, its share of the set's mass, the candidates with its first token, and their share. n x len(SET_NAMES)."""
    share = 2.0 ** -(bits - bits.min())
    share = share / share.sum()
    rank = np.argsort(np.argsort(bits, kind='stable'), kind='stable')
    first = np.asarray(first)
    same = (first[:, None] == first[None, :])
    return np.stack([rank, share, same.sum(1), (same * share[None, :]).sum(1)], 1).astype(np.float32)


def dump(path, value):
    with zstandard.ZstdCompressor(level=3).stream_writer(open(path, 'wb')) as sink:
        pickle.dump(value, sink, protocol=5)


def load(path):
    with zstandard.ZstdDecompressor().stream_reader(open(path, 'rb')) as source:
        return pickle.load(source)


def arr(text, shape=None):
    x = np.frombuffer(base64.b64decode(text), '<f4')
    return x.reshape(shape) if shape else x


def convert(out, roots, gen_root=None):
    out = Path(out)
    tg_read = None
    if gen_root:  # the reader of the lists stands beside their folder
        sys.path.insert(0, str(Path(gen_root).parent))
        import tg_read
    index = tg_read.Index() if gen_root else None
    (out / 'blocks').mkdir(parents=True, exist_ok=True)
    block_fit.BlockMatrix.folder = out / 'blocks'
    head = None
    for split in ('train', 'dev'):
        point, cand, table, rel = block_fit.BlockMatrix(), block_fit.BlockMatrix(), block_fit.BlockMatrix(), block_fit.BlockMatrix()
        gen, gen_null = block_fit.BlockMatrix(), block_fit.BlockMatrix()
        gen_of, gen_null_of = [], []
        gen_rows, gen_null_rows = 0, 0
        at_table = {}
        points, labels, starts, of_point, table_of, tree_bits = [], [], [0], [], [], []
        ranks = collections.defaultdict(list)
        decisions = []
        t0 = time.time()
        found = {}  # the first root that holds a task's rows of a source gives them
        for root in map(Path, roots):
            for path in sorted(root.glob(f'{split}_*/*.atoms.zst')):
                found.setdefault((path.parent.name, path.name), path)
        files = [found[k] for k in sorted(found)]
        for done, path in enumerate(files, 1):
            source = path.parent.name.split('_', 1)[1]
            lists, null_lists, at_gen, at_gen_null = None, {}, {}, {}
            if gen_root:
                gen_path = Path(gen_root) / path.parent.name / (path.name.split('.')[0] + '.gen.zst')
                if not gen_path.exists():
                    continue
                lists = {d.decision: d for d in tg_read.decisions(gen_path)}
                null_path = gen_path.with_name(path.name.split('.')[0] + '.null.zst')
                if null_path.exists():
                    null_lists = {d.decision: d for d in tg_read.decisions(null_path)}
            with lines(path) as f:
                head_here = json.loads(f.readline())
                head = head or head_here
                n_tok, n_struct, n_av = len(head['tok_names']), len(head['struct_names']), len(head['av_names'])
                task = head_here['task']
                for line in f:
                    r = json.loads(line)
                    n = r['n']
                    if lists is not None and r['decision'] not in lists:
                        continue
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
                    kept_bits = bits[chosen]
                    extra = set_columns(kept_bits, [r['tokens'][i][0] for i in chosen])
                    rows = np.concatenate([tok, st, np.array(r['defined'], np.float32)[chosen, None], kept_bits[:, None].astype(np.float32), (kept_bits - kept_bits.min())[:, None].astype(np.float32), extra], 1)
                    against = av - av.mean(0, keepdims=True)
                    for i in range(len(chosen)):
                        here = np.flatnonzero(against[i] != 0)
                        rel.add(here, against[i][here])
                    n = len(chosen)
                    if lists is not None:
                        d, nd = lists[r['decision']], null_lists.get(r['decision'])
                        body_null = None if nd is None else tg_read.null_list(d.body, nd.body, nd.reads_output)
                        here_gen, here_null = np.zeros(n, np.uint32), np.zeros(n, np.uint32)
                        for k, i in enumerate(chosen.tolist()):
                            key = (id(d.cands[i]), id(d.body))
                            place = at_gen.get(key)
                            if place is None:
                                place = at_gen[key] = gen_rows
                                gen_rows += 1
                                c, v = tg_read.columns(d.cands[i], d.body, index)
                                gen.add(c, v)
                            here_gen[k] = place
                            place = at_gen_null.get(key)
                            if place is None:
                                place = at_gen_null[key] = gen_null_rows
                                gen_null_rows += 1
                                if nd is None:
                                    c, v = tg_read.columns(d.cands[i], d.body, index)
                                else:
                                    c, v = tg_read.columns(tg_read.null_list(d.cands[i], nd.cands[i], nd.reads_output), body_null, index)
                                gen_null.add(c, v)
                            here_null[k] = place
                        gen_of.append(here_gen)
                        gen_null_of.append(here_null)
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
        point.write(out / 'blocks' / f'{split}.point.zst'); cand.write(out / 'blocks' / f'{split}.cand.zst'); table.write(out / 'blocks' / f'{split}.table.zst'); rel.write(out / 'blocks' / f'{split}.rel.zst')
        if gen_root:
            gen.write(out / 'blocks' / f'{split}.gen.zst'); gen_null.write(out / 'blocks' / f'{split}.gen_null.zst')
        dump(out / f'{split}.pkl.zst', dict(points=points, labels=np.concatenate(labels), starts=np.array(starts, np.uint32), of_point=np.concatenate(of_point), table_of=np.concatenate(table_of), tables=len(at_table), tree_bits=np.concatenate(tree_bits), head=head, decisions=decisions, gen_of=np.concatenate(gen_of) if gen_of else None, gen_null_of=np.concatenate(gen_null_of) if gen_null_of else None, gen_rows=gen_rows, gen_null_rows=gen_null_rows, gen_width=index.width() if index else 0))
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
    if arm != 'b':
        plan.add('point', len(head['point_names']), 'point', np.arange(len(head['point_names'])), head['point_names'])
    names = head['tok_names'] + ['atom:' + x for x in head['struct_names']] + ['atom:defined', 'atom:bits', 'atom:bits_gap'] + SET_NAMES
    tree_only = arm == 'b'  # the tree's bits alone
    with_bits = arm in ('b', 'nb', 'tb', 'nbs', 'tbs', 'tg', 'tg_null', 'tgt', 'nt_gen')
    with_table = arm in ('t', 'tb', 'tbs', 'tgt')
    with_set = arm in ('nbs', 'tbs')
    with_gen = arm in ('tg', 'tg_null', 'tgt')
    def wanted(n):
        if n in SET_NAMES:
            return with_set
        if n in ('atom:bits', 'atom:bits_gap'):
            return with_bits
        if tree_only:
            return False
        return with_table or n != 'atom:defined'
    keep = np.array([i for i, n in enumerate(names) if wanted(n)])
    plan.add('cand', len(names), 'row', keep, [names[i] for i in keep])
    if with_table:
        plan.map('table', data['table_of'], data['tables'])
        av = head['av_names']
        table_names = av + ['d' + x[1:] for x in av]
        plan.add('table', len(table_names), 'table', np.arange(len(table_names)), table_names)
        if with_set:
            plan.add('rel', len(av), 'row', np.arange(len(av)), ['r' + x[1:] for x in av])
    if with_gen:
        block, of, rows = ('gen_null', data['gen_null_of'], data['gen_null_rows']) if arm == 'tg_null' else ('gen', data['gen_of'], data['gen_rows'])
        plan.map(block, of, rows)
        width = data['gen_width_all']
        plan.add(block, width, block, np.arange(width), [f'g{i}' for i in range(width)])
    return plan


def fit(out, arm, threads):
    out = Path(out)
    train, dev = load(out / 'train.pkl.zst'), load(out / 'dev.pkl.zst')
    train['gen_width_all'] = dev['gen_width_all'] = max(train.get('gen_width', 0), dev.get('gen_width', 0))
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


def escape_share(train):
    """The share of the tree's mass outside a set that fits the train decisions best: the one that gives the true atom's place, in or out of the set, the fewest bits."""
    outside = np.array([1.0 - d['mass'] for d in train['decisions']])
    missed = np.array([d['kept'] < 0 for d in train['decisions']])
    grid = np.arange(0.01, 1.001, 0.01)
    loss = [-(missed.sum() * np.log2(s) + np.log2(1.0 - s * outside[~missed]).sum()) for s in grid]
    return float(grid[int(np.argmin(loss))])


def query_bits(dev, scores, escape):
    """(median and mean bits per query by source and kind): the token tree's, and for each arm what the live writer gives. A query is a run of a sample's decisions along which the length grows. At a decision whose true atom is in the set, the arm's chance is the mass that the live writer gives the set times the arm's share of it. From a decision outside the set, the rest of the query goes by tokens: the chance is the escape share times the token tree's chance, since a path that writes a proposed atom by tokens dies at its close."""
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
                    total += -np.log2(escape) + d['gold']
                    tokens = True
                else:
                    total += -np.log2(1.0 - escape * (1.0 - d['mass'])) + share[name][d['kept']]
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
    escape = escape_share(load(out / 'train.pkl.zst'))
    print('the share of the mass outside a set that stays with tokens, from train rows:', escape)
    query_bits(dev, {name: s for name, s in scores.items() if name != 'tree'}, escape)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('command'); ap.add_argument('out'); ap.add_argument('arms', nargs='*'); ap.add_argument('--threads', type=int, default=3); ap.add_argument('--gen')
    a = ap.parse_args()
    if a.command == 'convert':
        convert(a.out, a.arms, a.gen)
    elif a.command == 'fit':
        fit(a.out, a.arms[0], a.threads)
    else:
        report(a.out, a.arms)
