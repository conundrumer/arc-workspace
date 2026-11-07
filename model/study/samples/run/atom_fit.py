#!/usr/bin/env python
"""atom_fit.py convert OUT ROOT... | fit OUT ARM [--threads T] | report OUT ARM... [--logits NAME=FILE]: a softmax over a decision's candidate atoms, read against the token tree on the same candidates.

A ROOT holds train_* and dev_* folders of atom_rows.py. Each decision's first candidate is the positive. A decision whose positive is outside the tree's top TOP atoms is left out, and each other is cut to those atoms, so a set holds what a live set holds. Arms: nt, the point, the first token and the atom's structure, with no table of the atom; t, those and the body table with the atom added, and its difference from the body before; b, only the tree's bits for the atom and their gap to the set's best; nb and tb, nt and t with those bits; nbs and tbs, those with the candidate's place in its set (set_columns), and tbs also with its table's difference from the set's mean. With --gen FOLDER, convert keeps the tasks that have generated lists there, read by the tg_read.py beside FOLDER, and the arms read them: tg, nb with the lists; tg_null, nb with the control's lists; tgt, tb with the lists. A fit chooses its round on train tasks held out from fitting (held_out), and report prints dev bits per decision, over a decision's candidates, for each arm and for the tree (the sum of its token bits over a candidate's path, as a softmax over these candidates), by source and by kind."""
import argparse, base64, collections, glob, hashlib, io, json, os, pickle, struct, subprocess, sys, time
from pathlib import Path
import numpy as np
import zstandard
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from study_paths import REPO_ROOT  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / 'model/feature_eval'))
import block_fit  # noqa: E402

block_fit.MAX_BIN, block_fit.SAMPLE_CAP = 255, 200000
RESUME = os.environ.get('ATOM_RESUME') == '1'  # the read of a writer that chooses whole atoms again after an atom it wrote by tokens
NOT_TOKEN = 14  # the token NOT, in the writer's fixed vocabulary
HOLD = 15  # the percent of train tasks held out
TOP = 12  # the atoms of a decision: the tree's top ones, with the true atom among them
PARAMS = dict(learning_rate=0.05, num_leaves=31, min_data_in_leaf=50, min_sum_hessian=1e-3, fraction=0.8, max_rounds=1500, patience=60, seed=0)
NONE = 0xFFFFFFFF


def lines(path):
    return io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(open(path, 'rb'), read_across_frames=True), encoding='utf-8')


def held_out(task):
    """Whether a train task is held out from fitting, to choose a fit's round."""
    return int(hashlib.sha256(task.encode()).hexdigest()[:8], 16) % 100 < HOLD


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


def convert(out, roots, gen_root=None, drop_flagged=False):
    out = Path(out)
    tg_read = None
    if gen_root:  # the reader of the lists stands beside their folder
        sys.path.insert(0, str(Path(gen_root).parent))
        import tg_read
    index = tg_read.Index() if gen_root else None
    (out / 'blocks').mkdir(parents=True, exist_ok=True)
    block_fit.BlockMatrix.folder = out / 'blocks'
    head = None
    for split in ('train', 'hold', 'dev'):
        point, cand, table, rel = block_fit.BlockMatrix(), block_fit.BlockMatrix(), block_fit.BlockMatrix(), block_fit.BlockMatrix()
        gen, gen_null = block_fit.BlockMatrix(), block_fit.BlockMatrix()
        gen_of, gen_null_of = [], []
        gen_rows, gen_null_rows = 0, 0
        at_table = {}
        points, labels, starts, of_point, table_of, tree_bits = [], [], [0], [], [], []
        ranks = collections.defaultdict(list)
        dropped = collections.Counter()
        decisions = []
        t0 = time.time()
        found = {}  # the first root that holds a task's rows of a source gives them
        for root in map(Path, roots):
            for path in sorted(root.glob(f'{"dev" if split == "dev" else "train"}_*/*.atoms.zst')):
                if split == 'dev' or held_out(path.name.split('.')[0]) == (split == 'hold'):
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
                last_not, last_place = False, (None, None, -1)
                for line in f:
                    r = json.loads(line)
                    n = r['n']
                    place = (r['sample'], r.get('target'), r['length'])
                    was, last_not = last_not, r['tokens'][0][0] == NOT_TOKEN and len(r['tokens'][0]) > 1
                    at_before, last_place = last_place, place
                    if was and at_before[:2] == place[:2] and place[2] == at_before[2] + 1:  # the decision inside a NOT atom, which a live choice doesn't have
                        last_not = False
                        continue
                    if lists is not None and r['decision'] not in lists:
                        continue
                    bits = np.array(r['bits'], np.float64)
                    by = np.argsort(bits, kind='stable')
                    rank = int(np.flatnonzero(by == 0)[0])
                    ranks[source + ' ' + r['kind']].append(rank)
                    outside = bits[1:]
                    top = np.sort(outside)[:TOP]
                    decisions.append(dict(task=task, sample=r['sample'], target=r.get('target'), kind=r['kind'], source=source, length=r['length'], gold=float(bits[0]), mass=float(min(1.0, (2.0 ** -np.sort(bits)[:TOP]).sum())), kept=-1 if n < 2 or rank >= TOP else len(points)))
                    if n < 2 or rank >= TOP:  # the set is the tree's top atoms, as live: an atom outside them would stand out by being there
                        continue
                    chosen = np.sort(by[:TOP])
                    flag_rows = None
                    if lists is not None:  # the two flags of a candidate's list; with drop_flagged, a flagged candidate leaves the set, and a flagged true atom takes its decision with it
                        flag_rows = np.array([tg_read.flags(lists[r['decision']].cands[i], r['defined'][i]) for i in chosen], np.float32)
                        if drop_flagged:
                            good = flag_rows.sum(1) == 0
                            if not good[0] or good.sum() < 2:
                                dropped['decisions'] += 1
                                decisions[-1]['kept'] = -1
                                continue
                            dropped['candidates'] += int((~good).sum())
                            chosen, flag_rows = chosen[good], flag_rows[good]
                    vp = arr(r['point'])
                    at = np.flatnonzero(vp != 0)
                    point.add(at, vp[at])
                    tok = arr(r['tok'], (n, n_tok))[chosen]; st = arr(r['struct'], (n, n_struct))[chosen]; av = arr(r['av'], (n, n_av))[chosen]; de = arr(r['delta'], (n, n_av))[chosen]
                    kept_bits = bits[chosen]
                    extra = set_columns(kept_bits, [r['tokens'][i][0] for i in chosen])
                    rows = np.concatenate([tok, st, np.array(r['defined'], np.float32)[chosen, None], kept_bits[:, None].astype(np.float32), (kept_bits - kept_bits.min())[:, None].astype(np.float32), extra], 1)
                    if flag_rows is not None:
                        rows = np.concatenate([rows, flag_rows], 1)
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
                    points.append(dict(task=task, source=source, folder=path.parent.name, decision=r.get('decision'), kind=r['kind'], first=[t[0] for t in r['tokens'][:1]], n=n))
            if done % 25 == 0 or done == len(files):
                print(f'{split} {done}/{len(files)}, {done / (time.time() - t0):.1f}/s, decisions {len(points)}, rows {starts[-1]}, tables {len(at_table)}', flush=True)
        point.write(out / 'blocks' / f'{split}.point.zst'); cand.write(out / 'blocks' / f'{split}.cand.zst'); table.write(out / 'blocks' / f'{split}.table.zst'); rel.write(out / 'blocks' / f'{split}.rel.zst')
        if gen_root:
            gen.write(out / 'blocks' / f'{split}.gen.zst'); gen_null.write(out / 'blocks' / f'{split}.gen_null.zst')
        dump(out / f'{split}.pkl.zst', dict(points=points, labels=np.concatenate(labels), starts=np.array(starts, np.uint32), of_point=np.concatenate(of_point), table_of=np.concatenate(table_of), tables=len(at_table), tree_bits=np.concatenate(tree_bits), head=head, decisions=decisions, gen_of=np.concatenate(gen_of) if gen_of else None, gen_null_of=np.concatenate(gen_null_of) if gen_null_of else None, gen_rows=gen_rows, gen_null_rows=gen_null_rows, gen_width=index.width() if index else 0))
        print(split, 'written', len(points), 'decisions', starts[-1], 'rows', collections.Counter(p['source'] for p in points), flush=True)
        if drop_flagged:
            print(split, 'left out', dict(dropped), flush=True)
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
    flag_names = ['atom:too_wide', 'atom:no_value'] if data['gen_of'] is not None else []
    names = names + flag_names
    tree_only = arm == 'b'  # the tree's bits alone
    with_bits = arm in ('b', 'nb', 'tb', 'nbs', 'tbs', 'tg', 'tg_null', 'tgt', 'nt_gen')
    with_table = arm in ('t', 'tb', 'tbs', 'tgt')
    with_set = arm in ('nbs', 'tbs')
    with_gen = arm in ('tg', 'tg_null', 'tgt')
    def wanted(n):
        if n in flag_names:
            return with_gen
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


def read_block(path, width, used, rows):
    """The columns of a block that `used` (each column's place in the result, or -1) names, as a dense rows x places matrix. An absent entry is 0."""
    places = int(used.max()) + 1 if used.size and used.max() >= 0 else 0
    out = np.zeros((rows, places), np.float32)
    with zstandard.ZstdDecompressor().stream_reader(open(path, 'rb'), read_across_frames=True) as source:
        data = source.read()
    at, base = 0, 0
    while at < len(data):
        n, entries = struct.unpack_from('<IQ', data, at)
        at += 12
        lengths = np.frombuffer(data, '<u4', n, at)
        at += 4 * n
        columns = np.cumsum(np.frombuffer(data, '<i4', entries, at).astype(np.int64))
        at += 4 * entries
        values = np.frombuffer(data, '<f4', entries, at)
        at += 4 * entries
        row = np.repeat(np.arange(base, base + n), lengths)
        keep = used[columns] >= 0
        out[row[keep], used[columns[keep]]] = values[keep]
        base += n
    return out


def score_dev(out, arm, data, split='dev', name='dev_read.f64'):
    """Writes fits/dev_read.f64, a fit's score of each dev row at its chosen round. The fit's own dev is the held-out train tasks."""
    import lightgbm
    work = out / 'work' / arm
    best = json.loads((work / 'fits' / 'result.json').read_text())['best_round']
    tool = Path(__file__).resolve().parent / 'to_lightgbm.py'
    subprocess.run([sys.executable, str(tool), str(work), str(work / 'model.txt'), '--rounds', str(best)], check=True, stdout=subprocess.DEVNULL)
    uses = json.loads((work / 'model.uses.json').read_text())
    plan = plan_of(out, split, work / 'read', data, arm)
    place = {label: i for i, label in enumerate(uses)}
    rows = len(data['labels'])
    M = np.zeros((rows, len(uses)), np.float32)
    for source, width, map_name, at, ids in plan.uses:
        used = np.full(width, -1, np.int64)
        targets = []
        for column, column_id in zip(at.tolist(), np.asarray(ids).tolist()):
            label = plan.labels[column_id]
            if label in place:
                used[column] = len(targets)
                targets.append(place[label])
        if not targets:
            continue
        of = plan.maps[map_name][1]
        block = read_block(plan.source(source), width, used, int(of.max()) + 1)
        M[:, targets] = block[of]
    booster = lightgbm.Booster(model_file=str(work / 'model.txt'))
    booster.predict(M[:1], raw_score=True)
    np.asarray(booster.predict(M, raw_score=True, num_threads=2), np.float64).tofile(work / 'fits' / name)


def fit(out, arm, threads):
    out = Path(out)
    train, real_dev = load(out / 'train.pkl.zst'), load(out / 'dev.pkl.zst')
    dev = load(out / 'hold.pkl.zst')  # a fit chooses its round on train tasks held out from fitting
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
    dev_plan = plan_of(out, 'hold', work, dev, arm)
    dev_plan.write(threads, reference=work / 'train')
    block_fit.raw(work / 'hold' / 'keep.i32', keep, np.int32)
    if not (work / 'hold' / 'compiled.json').exists():
        block_fit.run('compile', work / 'hold')
    for split, data in (('train', train), ('dev', dev)):  # dev here is the held-out train tasks
        block_fit.raw(work / f'{split}.groups.u32', data['starts'], np.uint32)
        block_fit.raw(work / f'{split}.labels.u8', data['labels'], np.uint8)
    (work / 'fit.json').write_text(json.dumps(dict(PARAMS, threads=threads, train=str(work / 'train'), dev=str(work / 'hold'), out=str(work / 'fits'), groups=str(work / 'train.groups.u32'), labels=str(work / 'train.labels.u8'), dev_groups=str(work / 'dev.groups.u32'), dev_labels=str(work / 'dev.labels.u8'))))
    block_fit.run('softmax', work / 'fit.json')
    print(json.loads((work / 'fits' / 'result.json').read_text()), flush=True)
    real_dev['gen_width_all'] = dev['gen_width_all']
    score_dev(out, arm, real_dev)
    score_dev(out, arm, dev, 'hold', 'hold_read.f64')
    held = np.fromfile(work / 'fits' / 'dev_best.f64', dtype=np.float64)
    again = np.fromfile(work / 'fits' / 'hold_read.f64', dtype=np.float64)
    print('the read against the fit on held-out rows: largest difference %.6f' % float(np.abs(held - again).max()), flush=True)


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
    by_query = collections.defaultdict(list)
    for d in dev['decisions']:
        by_query[(d['task'], d['source'], d['sample'], d.get('target'), d['kind'])].append(d)
    queries = [sorted(q, key=lambda d: d['length']) for q in by_query.values()]
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
                    tokens = not RESUME
                else:
                    total += -np.log2(1.0 - escape * (1.0 - d['mass'])) + share[name][d['kept']]
            for key in ('all', q[0]['source'], q[0]['source'] + ' ' + q[0]['kind']):
                table[key][name].append(total)
    print('bits per query, median (mean):')
    for key in sorted(table):
        print('  %-14s %5d  ' % (key, len(table[key]['token tree'])) + '  '.join('%s %.1f (%.1f)' % (name, np.median(v), np.mean(v)) for name, v in table[key].items()))
    print('share of queries at most 3, 5, 7 bits:')
    for key in sorted(table):
        print('  %-14s %5d  ' % (key, len(table[key]['token tree'])) + '  '.join('%s %.2f %.2f %.2f' % (name, np.mean(np.array(v) <= 3), np.mean(np.array(v) <= 5), np.mean(np.array(v) <= 7)) for name, v in table[key].items()))


def logits_file(dev, path):
    """Scores from a file of JSON lines {folder, task, decision, logits}, with a logit per candidate of the set, in the order of its rows. A decision the file lacks scores 0 for each candidate, and the count is printed."""
    held = {}
    for line in open(path):
        r = json.loads(line)
        held[(r['folder'], r['task'], r['decision'])] = r['logits']
    starts = dev['starts'].astype(np.int64)
    out = np.zeros(int(starts[-1]))
    missing = 0
    for i, p in enumerate(dev['points']):
        got = held.get((p['folder'], p['task'], p['decision']))
        if got is None or len(got) != starts[i + 1] - starts[i]:
            missing += 1
            continue
        out[starts[i]:starts[i + 1]] = got
    print(path, 'decisions without logits:', missing, 'of', len(dev['points']))
    return out


def per_task(dev, a, b):
    """Top-1 per task of scores a less scores b: the mean over tasks, and a 95% bootstrap interval over tasks."""
    starts = dev['starts'].astype(np.int64)
    by = collections.defaultdict(list)
    for i, p in enumerate(dev['points']):
        lo, hi = starts[i], starts[i + 1]
        by[p['task']].append(float(a[lo:hi][0] >= a[lo:hi].max()) - float(b[lo:hi][0] >= b[lo:hi].max()))
    d = np.array([np.mean(v) for v in by.values()])
    rng = np.random.default_rng(0)
    boot = rng.choice(d, (10000, len(d))).mean(1)
    return len(d), float(d.mean()), float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))


def report(out, arms, logits=()):
    out = Path(out)
    dev = load(out / 'dev.pkl.zst')
    starts = dev['starts'].astype(np.int64); bits = dev['tree_bits']
    scores = {'tree': -bits * np.log(2)}
    for arm in arms:
        read = out / 'work' / arm / 'fits' / 'dev_read.f64'
        scores[arm] = np.fromfile(read if read.exists() else out / 'work' / arm / 'fits' / 'dev_best.f64', dtype=np.float64)
    for item in logits:
        name, path = item.split('=', 1)
        scores[name] = logits_file(dev, path)
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
    for name, x in scores.items():
        if name != 'tree':
            t, mean, low, high = per_task(dev, x, scores['tree'])
            print('%s top-1 per task less the token tree, %d tasks: %+.4f (%+.4f, %+.4f)' % (name, t, mean, low, high))
    escape = escape_share(load(out / 'train.pkl.zst'))
    print('the share of the mass outside a set that stays with tokens, from train rows:', escape)
    query_bits(dev, {name: s for name, s in scores.items() if name != 'tree'}, escape)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('command'); ap.add_argument('out'); ap.add_argument('arms', nargs='*'); ap.add_argument('--threads', type=int, default=3); ap.add_argument('--gen'); ap.add_argument('--drop-flagged', action='store_true'); ap.add_argument('--logits', action='append', default=[])
    a = ap.parse_args()
    if a.command == 'convert':
        convert(a.out, a.arms, a.gen, a.drop_flagged)
    elif a.command == 'fit':
        fit(a.out, a.arms[0], a.threads)
    else:
        report(a.out, a.arms, a.logits)
