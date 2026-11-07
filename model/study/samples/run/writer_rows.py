#!/usr/bin/env python
"""writer_rows.py convert OUT NAME=FOLDER:K:C ... [--workers N] | fit OUT ARM [--threads T] | report OUT ARM...: the writer's rows from several sources of points, each a folder that points_write.py wrote, with the table summaries in its rows.

From each file of a source: K points by a hash, and up to C more among the points where two or more admitted tokens name a table. No point is chosen by its label. Dev rows come from the same sources under the same rule, and report gives them by source. A table's row in the fit is its summaries; two tokens of a task with equal summaries share one. token:id reads 0 for a token that names a table of the state, so a live run sets WRITER_TOKEN_ID_NO_TABLE=1.
"""
import argparse, base64, collections, gzip, hashlib, heapq, io, json, multiprocessing as mp, os, pickle, sys, time
import zstandard
from pathlib import Path


def open_points(path):
    """A points file's lines: streamable zstd, or gzip where an older file has it."""
    if str(path).endswith('.zst'):
        return io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(open(path, 'rb'), read_across_frames=True), encoding='utf-8')
    import gzip
    return gzip.open(path, 'rt')


import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from study_paths import DATA_ROOT, REPO_ROOT  # noqa: E402
sys.path.insert(0, str(REPO_ROOT / 'model/feature_eval'))
import block_fit  # noqa: E402

NO_COLUMN_BODY = os.environ.get('WRITER_ROWS_NO_COLUMN_BODY') == '1'  # blanks the body table's columns at column points, to test what they are worth
block_fit.MAX_BIN, block_fit.SAMPLE_CAP = 255, 200000
PARAMS = dict(learning_rate=0.05, num_leaves=63, min_data_in_leaf=100, min_sum_hessian=1e-3, fraction=0.8, max_rounds=2000, patience=50, seed=0)
NONE = 0xFFFFFFFF


def key_of(sample, position):
    return int.from_bytes(hashlib.sha256(f'0:{sample}:{position}'.encode()).digest()[:8], 'big')


def read_job(job):
    """A file's kept points: source, split, path, the points chosen by hash, and the most among those where two or more admitted tokens name a table."""
    source, split, path, chosen_k, choice_cap = job
    task = path.name.split('.')[0]
    random_k, choice, records = [], [], {}
    with open_points(path) as f:
        head = json.loads(f.readline())
        names = head['vector_names']
        point_cols = head['vector_point_cols']
        in_point = set(point_cols)
        option_cols = [i for i in range(len(names)) if i not in in_point]
        option_names = [names[i] for i in option_cols]
        tok_at = [i for i, x in enumerate(option_names) if x.startswith('tok:')]
        other_at = [i for i, x in enumerate(option_names) if not x.startswith('tok:')]
        table_at = option_names.index('tokg:table')
        for position, line in enumerate(f, 1):
            if not line.startswith('{"record":"point"') and not line.startswith('{"record": "point"'):
                continue
            rec = json.loads(line)
            n = len(rec['ids'])
            if n < 2 or not rec['positive']:
                continue
            key = key_of(rec['sample'], position)
            vo = np.frombuffer(base64.b64decode(rec['vo']), '<f4').reshape(n, -1)
            keep = False
            if len(random_k) < chosen_k:
                heapq.heappush(random_k, (-key, position))
                keep = True
            elif random_k and -random_k[0][0] > key:
                heapq.heapreplace(random_k, (-key, position))
                keep = True
            if choice_cap and np.count_nonzero(vo[:, table_at]) >= 2:
                choice.append((key, position))
                keep = True
            if keep:
                records[position] = rec
    choice.sort()
    keep = {p for _, p in random_k} | {p for _, p in choice[:choice_cap]}
    points = []
    point_names = [names[i] for i in point_cols]
    phase_at = point_names.index('place:phase')
    body_at = [i for i, x in enumerate(point_names) if x.startswith('pq:body:')]
    match_at = [i for i, x in enumerate(option_names) if x.startswith('tokm:body_')]
    for position in sorted(keep):
        rec = records[position]
        n = len(rec['ids'])
        vp = np.frombuffer(base64.b64decode(rec['vp']), '<f4')
        vo = np.frombuffer(base64.b64decode(rec['vo']), '<f4').reshape(n, -1)
        if NO_COLUMN_BODY and vp[phase_at] == 6:  # at a column point the body table in progress is not read: what the writer gives where the engine gives no body
            vp = vp.copy(); vp[body_at] = np.nan
            vo = vo.copy(); vo[:, match_at] = np.where(vo[:, option_names.index('tokg:table')] != 0, np.nan, 0)
        at = np.flatnonzero(vp != 0)
        vectors = [vo[i, tok_at].copy() if vo[i, table_at] else None for i in range(n)]
        points.append(dict(task=task, sample=rec['sample'], kind=rec['kind'], length=rec['length'], ids=rec['ids'], positive=rec['positive'], vp_at=at, vp=vp[at], vo=vo[:, other_at], vectors=vectors, source=source))
    return dict(task=task, names=[names[i] for i in point_cols], option_names=[option_names[i] for i in other_at], points=points, tok_names=[x for x in option_names if x.startswith('tok:')])


def write_split(out, split, jobs, workers):
    block_fit.BlockMatrix.folder = out / 'blocks'
    point, token, tok = block_fit.BlockMatrix(), block_fit.BlockMatrix(), block_fit.BlockMatrix()
    points, labels, starts, of_point, table_of = [], [], [0], [], []
    point_names = option_names = feature_names = None
    at_table = {}
    started = time.time()
    with mp.Pool(workers) as pool:
        for done, got in enumerate(pool.imap(read_job, jobs, chunksize=4), 1):
            if point_names is None:
                point_names, option_names = got['names'], got['option_names']
                id_at, table_at = option_names.index('token:id'), option_names.index('tokg:table')
            assert got['names'] == point_names and got['option_names'] == option_names, got['task']
            feature_names = feature_names or got['tok_names']
            task = got['task']
            for p in got['points']:
                n = len(p['ids'])
                point.add(p['vp_at'], p['vp'])
                vo = p['vo'].copy()
                vo[vo[:, table_at] != 0, id_at] = 0
                for row in vo:
                    here = np.flatnonzero(row != 0)
                    token.add(here, row[here])
                marks = np.zeros(n, np.uint8); marks[p['positive']] = 1
                labels.append(marks); starts.append(starts[-1] + n); of_point.append(np.full(n, len(points), np.uint32))
                where = np.full(n, NONE, dtype=np.uint32)
                for i, vector in enumerate(p['vectors']):
                    if vector is not None:
                        key = (task, vector.tobytes())
                        place = at_table.get(key)
                        if place is None:
                            place = at_table[key] = len(at_table)
                            here = np.flatnonzero(vector != 0)  # NaN != 0
                            tok.add(here, vector[here])
                        where[i] = place
                table_of.append(where)
                points.append(dict(task=task, sample=p['sample'], kind=p['kind'], length=p['length'], ids=p['ids'], source=p['source']))
            if done % 50 == 0 or done == len(jobs):
                rate = done / (time.time() - started)
                print(f'{split} {done}/{len(jobs)} files, {rate:.1f}/s, ETA {(len(jobs) - done) / rate:.0f}s, points {len(points)}, rows {starts[-1]}, tables {len(at_table)}', flush=True)
    point.write(out / 'blocks' / f'{split}.point.zst'); token.write(out / 'blocks' / f'{split}.token.zst'); tok.write(out / 'blocks' / f'{split}.tok.zst')
    np.save(out / f'{split}.table_of.npy', np.concatenate(table_of))
    with (out / f'{split}.pkl').open('wb') as sink:
        pickle.dump(dict(points=points, labels=np.concatenate(labels), starts=np.array(starts, np.uint32), of_point=np.concatenate(of_point), point_names=point_names, option_names=option_names, feature_names=feature_names, tables=len(at_table)), sink)
    print(split, 'written', len(points), 'points', starts[-1], 'rows', len(at_table), 'tables', collections.Counter(p['source'] for p in points), flush=True)


def convert(out, sources, workers):
    """sources: name=folder:chosen_k:choice_cap, one per source of points."""
    out = Path(out)
    (out / 'blocks').mkdir(parents=True, exist_ok=True)
    for split in ('train', 'dev'):
        jobs = []
        for held in sources:
            name, rest = held.split('=')
            folder, chosen_k, choice_cap = rest.rsplit(':', 2)
            jobs += [(name, split, p, int(chosen_k), int(choice_cap)) for p in sorted((Path(folder) / split / 'points' / 'ordered').glob('*.jsonl.*'))]
        write_split(out, split, jobs, workers)


def plan_of(out, split, work, data, arm):
    plan = block_fit.Plan(work / split, out, split, {})
    rows = len(data['labels'])
    plan.map('point', data['of_point'], len(data['points']))
    plan.map('row', np.arange(rows, dtype=np.uint32), rows)
    plan.add('point', len(data['point_names']), 'point', np.arange(len(data['point_names'])), data['point_names'])
    plan.add('token', len(data['option_names']), 'row', np.arange(len(data['option_names'])), data['option_names'])
    plan.map('table', np.load(out / f'{split}.table_of.npy'), data['tables'])
    names = data['feature_names']
    plan.add('tok', len(names), 'table', np.arange(len(names)), names)
    return plan


def fit(out, arm, threads):
    out = Path(out)
    train, dev = pickle.load((out / 'train.pkl').open('rb')), pickle.load((out / 'dev.pkl').open('rb'))
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
    (work / 'fit.json').write_text(json.dumps(dict(PARAMS, threads=threads, train=str(work / 'train'), dev=str(work / 'dev'), out=str(work / 'fits'),
                                                   groups=str(work / 'train.groups.u32'), labels=str(work / 'train.labels.u8'), dev_groups=str(work / 'dev.groups.u32'), dev_labels=str(work / 'dev.labels.u8'))))
    block_fit.run('softmax', work / 'fit.json')
    print(json.loads((work / 'fits' / 'result.json').read_text()), flush=True)


def report(out, arms):
    out = Path(out)
    dev = pickle.load((out / 'dev.pkl').open('rb'))
    starts = dev['starts'].astype(np.int64); labels = dev['labels']
    naming = np.load(out / 'dev.table_of.npy') != NONE
    table = {}
    for arm in arms:
        s = np.fromfile(out / 'work' / arm / 'fits' / 'dev_best.f64', dtype=np.float64)
        g = collections.defaultdict(list)
        for i, p in enumerate(dev['points']):
            lo, hi = starts[i], starts[i + 1]
            x, y = s[lo:hi], labels[lo:hi]
            e = np.exp(x - x.max())
            loss = -np.log(e[y > 0].sum() / e.sum()); top = float((y[x == x.max()] > 0).mean())
            src = p['source']
            g[src + ' all'].append((loss, top)); g[src + ' kind ' + p['kind']].append((loss, top))
            if naming[lo:hi][y > 0].any():
                g[src + ' answer names a table'].append((loss, top))
            elif naming[lo:hi].sum() >= 2:
                g[src + ' 2+ tables, answer elsewhere'].append((loss, top))
        table[arm] = {k: (len(v), float(np.mean([a for a, _ in v])), float(np.mean([b for _, b in v]))) for k, v in g.items()}
    for k in sorted(table[arms[0]]):
        print('%-36s %6d  ' % (k, table[arms[0]][k][0]) + '  '.join('%s %.4f %.4f' % (arm, table[arm][k][1], table[arm][k][2]) for arm in arms))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('command'); ap.add_argument('out'); ap.add_argument('arms', nargs='*'); ap.add_argument('--threads', type=int, default=4); ap.add_argument('--workers', type=int, default=4)
    a = ap.parse_args()
    if a.command == 'convert':
        convert(a.out, a.arms, a.workers)
    elif a.command == 'fit':
        fit(a.out, a.arms[0], a.threads)
    else:
        report(a.out, a.arms)
