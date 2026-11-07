#!/usr/bin/env python
"""atom_fit_full.py convert OUT ROOT [--negatives N] [--mine MODEL] | fit OUT ARM [--threads T] | report OUT ARM... [--tokens ROOT]: a softmax over a decision's whole candidate set, from rows of atom_rows_full.py.

A fit sees each true atom with N other candidates chosen at random, or with --mine half of them the candidates that MODEL ranks highest. A fit chooses its round on train tasks held out from fitting. report scores every candidate of each dev decision, and prints the true atom's rank: how often it is in the top 1, 4, 12, 32 and 100, against the token tree's proposals from the rows of atom_rows.py (--tokens) on the same targets.

Arms: s, the point, the first token and the atom's structure, with the first token's bits; t, those and the table with the atom added, and its difference from the body before."""
import argparse, base64, collections, hashlib, io, json, os, pickle, random, re, subprocess, sys, time
from pathlib import Path
import numpy as np
import zstandard
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from study_paths import REPO_ROOT  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / 'model/feature_eval'))
import block_fit  # noqa: E402

block_fit.MAX_BIN, block_fit.SAMPLE_CAP = 255, 200000
PARAMS = dict(learning_rate=0.05, num_leaves=31, min_data_in_leaf=50, min_sum_hessian=1e-3, fraction=0.8, max_rounds=1500, patience=60, seed=0)
HOLD = 15
VOCAB = json.load(open(os.environ.get('ATOM_VOCAB', Path(__file__).resolve().parent / 'vocab.json')))['names']  # the token names of a session made for rows, by id
sys.path.insert(0, str(REPO_ROOT / 'model/study/sampler'))
import atom_columns as AC
CAND = AC.CAND


def held_out(task):
    return int(hashlib.sha256(task.encode()).hexdigest()[:8], 16) % 100 < HOLD


def lines(path):
    return io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(open(path, 'rb'), read_across_frames=True), encoding='utf-8')


def arr(text, shape=None):
    x = np.frombuffer(base64.b64decode(text), '<f4')
    return x.reshape(shape) if shape else x


def dump(path, value):
    with zstandard.ZstdCompressor(level=3).stream_writer(open(path, 'wb')) as sink:
        pickle.dump(value, sink, protocol=5)


def load(path):
    with zstandard.ZstdDecompressor().stream_reader(open(path, 'rb')) as source:
        return pickle.load(source)


def cand_rows(rec):
    """The candidate block of a decision, n x len(CAND)."""
    S = [AC.structure([VOCAB[t] for t in x]) for x in rec['tokens']]
    return AC.cand_rows(S, rec['first_of'], rec['first_bits'], np.array(rec['table_of']) >= 0)


def table_rows(rec, width):
    """(v, v less the body's) of each table of a decision, and a last row for a candidate with no table."""
    base = arr(rec['base'])
    t = arr(rec['tables'], (-1, width)) if rec['tables'] else np.zeros((0, width), np.float32)
    v = np.concatenate([t, np.full((1, width), np.nan, np.float32)])
    return np.concatenate([v, v - base], 1)


def read_file(path):
    """(the header, [decision records with `positives`, a list of (target, place)]) of a file."""
    with lines(path) as f:
        head = json.loads(f.readline())
        held, by = [], {}
        for line in f:
            r = json.loads(line)
            if 'same_as' in r:
                got = by.get(r['same_as'])
                if got is not None:
                    got['positives'].append((r['target'], r['positive'], r.get('twin', False)))
                continue
            r['positives'] = [(r['target'], r['positive'], r.get('twin', False))]
            by[r['decision']] = r
            held.append(r)
    return head, held


def convert(out, root, negatives, mine):
    out, root = Path(out), Path(root)
    (out / 'blocks').mkdir(parents=True, exist_ok=True)
    block_fit.BlockMatrix.folder = out / 'blocks'
    booster = uses = None
    if mine:
        import lightgbm
        booster = lightgbm.Booster(model_file=mine)
        uses = json.loads(Path(mine).with_suffix('.uses.json').read_text())
    head = None
    for split in ('train', 'hold'):
        point, first, table, cand = block_fit.BlockMatrix(), block_fit.BlockMatrix(), block_fit.BlockMatrix(), block_fit.BlockMatrix()
        of_point, of_first, of_table, labels, starts = [], [], [], [], [0]
        counts = collections.Counter()
        n_point = n_first = n_table = 0
        rng = random.Random(split)
        files = sorted(p for p in root.glob('train_*/*.full.zst') if held_out(p.name.split('.')[0]) == (split == 'hold'))
        t0 = time.time()
        for done, path in enumerate(files, 1):
            head_here, held = read_file(path)
            head = head or head_here
            w_a = len(head['av_names'])
            for rec in held:
                good = [(t, p) for t, p, _ in rec['positives'] if p is not None]
                counts['targets'] += len(rec['positives'])
                counts['true atom not in the list'] += len(rec['positives']) - len(good)
                if not good or rec['n'] < 2:
                    continue
                vp = arr(rec['point'])
                at = np.flatnonzero(vp != 0)
                point.add(at, vp[at])
                tok = arr(rec['tok'], (len(rec['first']), len(head['tok_names'])))
                for row in tok:
                    at = np.flatnonzero(row != 0)
                    first.add(at, row[at])
                T = table_rows(rec, w_a)
                for row in T:
                    at = np.flatnonzero(row != 0)
                    table.add(at, row[at])
                C = cand_rows(rec)
                first_of, table_of = np.array(rec['first_of']), np.array(rec['table_of'])
                table_of = np.where(table_of < 0, len(T) - 1, table_of)
                true = {p for _, p in good}
                others = [i for i in range(rec['n']) if i not in true]
                ranked = None
                if booster is not None and others:
                    ranked = score_decision(rec, head, booster, uses)
                for _, p in good:
                    if booster is not None:
                        top = sorted(others, key=lambda i: -ranked[i])[:negatives // 2]
                        rest = rng.sample(others, min(len(others), negatives - len(top)))
                        chosen = list(dict.fromkeys(top + rest))
                    else:
                        chosen = rng.sample(others, min(len(others), negatives))
                    rows = [p] + chosen
                    for i in rows:
                        at = np.flatnonzero(C[i] != 0)
                        cand.add(at, C[i][at])
                    of_point.append(np.full(len(rows), n_point, np.uint32))
                    of_first.append(n_first + first_of[rows].astype(np.uint32))
                    of_table.append(n_table + table_of[rows].astype(np.uint32))
                    marks = np.zeros(len(rows), np.uint8); marks[0] = 1
                    labels.append(marks)
                    starts.append(starts[-1] + len(rows))
                    counts['groups'] += 1
                n_point += 1; n_first += len(tok); n_table += len(T)
            if done % 25 == 0 or done == len(files):
                print(f'{split} {done}/{len(files)}, {done / (time.time() - t0):.1f}/s, {dict(counts)}, rows {starts[-1]}', flush=True)
        point.write(out / 'blocks' / f'{split}.point.zst'); first.write(out / 'blocks' / f'{split}.first.zst'); table.write(out / 'blocks' / f'{split}.table.zst'); cand.write(out / 'blocks' / f'{split}.cand.zst')
        dump(out / f'{split}.pkl.zst', dict(labels=np.concatenate(labels), starts=np.array(starts, np.uint32), of_point=np.concatenate(of_point), of_first=np.concatenate(of_first), of_table=np.concatenate(of_table), n_point=n_point, n_first=n_first, n_table=n_table, head=head, counts=dict(counts)))


def plan_of(out, split, work, data, arm):
    plan = block_fit.Plan(work / split, out, split, {})
    head = data['head']
    rows = len(data['labels'])
    plan.map('point', data['of_point'], data['n_point'])
    plan.map('first', data['of_first'], data['n_first'])
    plan.map('row', np.arange(rows, dtype=np.uint32), rows)
    plan.add('point', len(head['point_names']), 'point', np.arange(len(head['point_names'])), head['point_names'])
    plan.add('first', len(head['tok_names']), 'first', np.arange(len(head['tok_names'])), head['tok_names'])
    keep = np.array([i for i, n in enumerate(CAND) if arm == 't' or n != 'atom:defined'])
    plan.add('cand', len(CAND), 'row', keep, [CAND[i] for i in keep])
    if arm == 't':
        plan.map('table', data['of_table'], data['n_table'])
        av = head['av_names']
        names = av + ['d' + x[1:] for x in av]
        plan.add('table', len(names), 'table', np.arange(len(names)), names)
    return plan


def fit(out, arm, threads):
    out = Path(out)
    train, dev = load(out / 'train.pkl.zst'), load(out / 'hold.pkl.zst')
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
    plan_of(out, 'hold', work, dev, arm).write(threads, reference=work / 'train')
    block_fit.raw(work / 'hold' / 'keep.i32', keep, np.int32)
    if not (work / 'hold' / 'compiled.json').exists():
        block_fit.run('compile', work / 'hold')
    for split, data in (('train', train), ('dev', dev)):
        block_fit.raw(work / f'{split}.groups.u32', data['starts'], np.uint32)
        block_fit.raw(work / f'{split}.labels.u8', data['labels'], np.uint8)
    (work / 'fit.json').write_text(json.dumps(dict(PARAMS, threads=threads, train=str(work / 'train'), dev=str(work / 'hold'), out=str(work / 'fits'), groups=str(work / 'train.groups.u32'), labels=str(work / 'train.labels.u8'), dev_groups=str(work / 'dev.groups.u32'), dev_labels=str(work / 'dev.labels.u8'))))
    block_fit.run('softmax', work / 'fit.json')
    result = json.loads((work / 'fits' / 'result.json').read_text())
    print(result, flush=True)
    tool = Path(__file__).resolve().parent / 'to_lightgbm.py'
    subprocess.run([sys.executable, str(tool), str(work), str(out / f'{arm}.txt'), '--rounds', str(result['best_round'])], check=True)


def score_decision(rec, head, booster, uses):
    n = rec['n']
    w_a = len(head['av_names'])
    columns = {}
    vp = arr(rec['point'])
    tok = arr(rec['tok'], (len(rec['first']), len(head['tok_names'])))
    first_of = np.array(rec['first_of'])
    C = cand_rows(rec)
    T = table_rows(rec, w_a)
    table_of = np.array(rec['table_of'])
    table_of = np.where(table_of < 0, len(T) - 1, table_of)
    at_point = {x: i for i, x in enumerate(head['point_names'])}
    at_tok = {x: i for i, x in enumerate(head['tok_names'])}
    at_cand = {x: i for i, x in enumerate(CAND)}
    names = head['av_names'] + ['d' + x[1:] for x in head['av_names']]
    at_table = {x: i for i, x in enumerate(names)}
    M = np.zeros((n, len(uses)), np.float32)
    for k, u in enumerate(uses):
        if u in at_point:
            M[:, k] = vp[at_point[u]]
        elif u in at_tok:
            M[:, k] = tok[first_of, at_tok[u]]
        elif u in at_cand:
            M[:, k] = C[:, at_cand[u]]
        elif u in at_table:
            M[:, k] = T[table_of, at_table[u]]
    return np.asarray(booster.predict(M, raw_score=True, num_threads=2), np.float64)


def report(out, arms, tokens):
    import lightgbm
    out = Path(out)
    root = Path(os.environ['ATOM_FULL_ROOT'])  # the folder of atom_rows_full.py's rows
    tree = {}
    if tokens:
        for path in Path(tokens).glob('dev_*/*.atoms.zst'):
            folder = path.parent.name
            with lines(path) as f:
                f.readline()
                for line in f:
                    r = json.loads(line)
                    b = np.array(r['bits'])
                    tree[(folder, r['task'], r['sample'], r['target'])] = (int(np.flatnonzero(np.argsort(b, kind='stable') == 0)[0]), float(b[0]))
    models = {arm: (lightgbm.Booster(model_file=str(out / f'{arm}.txt')), json.loads((out / f'{arm}.uses.json').read_text())) for arm in arms}
    results = collections.defaultdict(lambda: collections.defaultdict(list))
    for path in sorted(root.glob('dev_*/*.full.zst')):
        folder = path.parent.name
        head, held = read_file(path)
        for rec in held:
            scores = {arm: score_decision(rec, head, *m) for arm, m in models.items()}
            for target, p, _ in rec['positives']:
                key = folder + ' ' + rec['kind']
                t = tree.get((folder, rec['task'], rec['sample'], target))
                for arm, s in scores.items():
                    if p is None:
                        results[key][arm].append((10 ** 6, 40.0))
                        results[folder][arm].append((10 ** 6, 40.0))
                        continue
                    rank = int((s > s[p]).sum())
                    e = np.exp(s - s.max())
                    bits = float(-np.log2(max(e[p] / e.sum(), 1e-12)))
                    results[key][arm].append((rank, bits))
                    results[folder][arm].append((rank, bits))
                if t is not None:
                    results[key]['tokens'].append(t)
                    results[folder]['tokens'].append(t)
    for key in sorted(results):
        print(key)
        for arm, v in sorted(results[key].items()):
            x = np.array(v)
            print('   %-8s %5d targets: top 1 %.3f, 4 %.3f, 12 %.3f, 32 %.3f, 100 %.3f; bits median %.2f mean %.2f' % (arm, len(x), *[np.mean(x[:, 0] < k) for k in (1, 4, 12, 32, 100)], np.median(x[:, 1]), np.mean(x[:, 1])))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('command'); ap.add_argument('out'); ap.add_argument('arms', nargs='*'); ap.add_argument('--threads', type=int, default=3); ap.add_argument('--negatives', type=int, default=63); ap.add_argument('--mine'); ap.add_argument('--tokens')
    a = ap.parse_args()
    if a.command == 'convert':
        convert(a.out, a.arms[0], a.negatives, a.mine)
    elif a.command == 'fit':
        fit(a.out, a.arms[0], a.threads)
    else:
        report(a.out, a.arms, a.tokens)
