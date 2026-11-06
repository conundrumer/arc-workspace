#!/usr/bin/env python
"""The gate on per-table lists: trees that rank a gold query above its mutants, trained on train
tasks and read on dev tasks, read additively over what a shape reads.

  gate_lists.py build ROOT OUT [--min-tasks N]   the rows and the sparse matrices
  gate_lists.py fit OUT --sets ... --filters ... one line per fit, with per-task values in OUT/fits.jsonl

A shape's reading is one of: T, the table alone; TI, the table and the input; TO, the table and the
output; TIO, all three. A set is written as terms joined by `+`:
  base0, base   the features with no table content
  T, TI, TIO    the shapes up to that reading, on the true outputs
  TIO_null      those, with each shape that reads the output taken on deranged outputs
  contingent, fresh, contingent_null, fresh_null
                the shapes of a candidate that not every table it reads has as stable, and those
                whose value none of them has, against the input and those tables
  ctx           the base tables' own part roots
  breaks        shapes with no output leaf that a test input breaks
A term may end in `~WORD` to leave out the shapes whose name holds WORD, or `^WORD` to keep only those.
"""
import argparse
import json
import pickle
import re
import struct
import sys
import time
from array import array
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import zstandard

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import open_text, read_json  # noqa: E402
from query_structure import LABEL_STRUCTURE, base_features, parse_forms  # noqa: E402

ROOT_REPO = Path('/Users/davidlu/code/arc-workspace')
READS = {4: 'T', 5: 'TI', 6: 'TO', 7: 'TIO'}


def read_lists(path):
    raw = zstandard.ZstdDecompressor().stream_reader(open(path, 'rb')).read()
    n = struct.unpack('<Q', raw[:8])[0]
    head = json.loads(raw[8:8 + n])
    at = 8 + n
    dictionary = np.frombuffer(raw, dtype='<u8', count=head['shapes'], offset=at)
    at += 8 * head['shapes']
    lists = {}
    for held in head['lists']:
        values = None
        ids = np.frombuffer(raw, dtype='<u4', count=held['count'], offset=at)
        at += 4 * held['count']
        if held.get('values'):
            values = np.frombuffer(raw, dtype='<f4', count=held['count'], offset=at)
            at += 4 * held['count']
        lists[(held['owner'], held['kind'])] = (dictionary[ids], values)
    return head, lists


def split_of():
    out = {}
    for line in (ROOT_REPO / 'work/lm/data-study/samples/split.tsv').read_text().splitlines()[1:]:
        task, part, _ = line.split('\t')
        out[task] = part
    return out


class Matrix:
    def __init__(self):
        self.indptr = array('q', [0])
        self.indices = []
        self.data = []
        self.count = 0

    def add(self, indices, data=None):
        self.indices.append(np.asarray(indices, dtype=np.int32))
        self.data.append(np.ones(len(indices), dtype=np.float32) if data is None else np.asarray(data, dtype=np.float32))
        self.count += len(indices)
        self.indptr.append(self.count)

    def csr(self, width):
        indices = np.concatenate(self.indices) if self.indices else np.zeros(0, dtype=np.int32)
        data = np.concatenate(self.data) if self.data else np.zeros(0, dtype=np.float32)
        return sp.csr_matrix((data, indices, np.frombuffer(self.indptr, dtype=np.int64)), shape=(len(self.indptr) - 1, width))


def build(root, out, min_tasks):
    root, out = Path(root), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    parts = split_of()
    files = sorted((root / 'lists').glob('*.lists.zst'))
    print(len(files), 'task files', flush=True)
    # Which shapes tell gold from a mutant on three train tasks or more, on the true and on the null lists.
    told = {'stable': [], 'null': [], 'breaks': []}
    started = time.time()
    done = 0
    for path in files:
        task = path.name.split('.')[0]
        if parts.get(task) != 'train':
            continue
        head, lists = read_lists(path)
        seen = {kind: [] for kind in told}
        for item in head['items']:
            if item['last']:
                continue
            gold = item['gold']
            for mutant in item['mutants']:
                for kind in told:
                    a, b = lists.get((gold, kind)), lists.get((mutant['table'], kind))
                    if a is not None and b is not None:
                        seen[kind].append(np.setxor1d(a[0], b[0], assume_unique=True))
        for kind, held in seen.items():
            if held:
                told[kind].append(np.unique(np.concatenate(held)))
        done += 1
        if done % 100 == 0:
            print(f'scan {done} {done / (time.time() - started):.1f}/s', flush=True)
    chosen = {}
    for kind, held in told.items():
        if not held:
            chosen[kind] = np.zeros(0, dtype=np.uint64)
            continue
        ids, counts = np.unique(np.concatenate(held), return_counts=True)
        chosen[kind] = ids[counts >= min_tasks]
        print(kind, 'told apart on some task', len(ids), f'on {min_tasks}+ tasks', len(chosen[kind]), flush=True)
    columns = np.union1d(chosen['stable'], chosen['null'])
    breaks = chosen['breaks']
    context_names = {}
    # The names of the columns.
    names, flags, sizes = {}, {}, {}
    wanted = set(columns.tolist()) | set(breaks.tolist())
    for line in open_text(root / 'lists/names.tsv.zst'):
        parts_line = line.rstrip('\n').split('\t')
        if len(parts_line) != 4:
            continue
        key = int(parts_line[0], 16)
        if key in wanted:
            names[key], flags[key], sizes[key] = parts_line[1], int(parts_line[2]), int(parts_line[3])
    print('names found', len(names), 'of', len(wanted), flush=True)
    base_vocab = {}
    context_vocab = {}
    data = {}
    for split in ('train', 'dev'):
        rows = []
        mats = {name: Matrix() for name in ('base', 'stable', 'null', 'breaks', 'contingent', 'fresh', 'null_contingent', 'null_fresh', 'ctx')}
        count = 0
        started = time.time()
        for path in files:
            task = path.name.split('.')[0]
            if parts.get(task) != split:
                continue
            head, lists = read_lists(path)
            mutants = read_json(root / split / 'mutants' / f'{task}.json')
            gold_forms = parse_forms(mutants['gold'])
            by_form = {q['form']: q for q in mutants['queries']}
            parsed = {}
            def place(ids, table):
                at = np.searchsorted(table, ids)
                at[at == len(table)] = 0
                hit = table[at] == ids if len(table) else np.zeros(len(ids), dtype=bool)
                return at, hit
            own_ctx = lists.get(('constants', 'stable'), (np.zeros(0, dtype=np.uint64), None))[0].tolist()
            for key in own_ctx:
                if split == 'train':
                    context_vocab.setdefault(key, len(context_vocab))
            ctx_row = sorted(context_vocab[key] for key in own_ctx if key in context_vocab)
            for at, item in enumerate(head['items']):
                query = by_form[item['form']]
                members = [(item['gold'], 'gold', False, gold_forms)]
                for mutant in item['mutants']:
                    record = query['mutants'][mutant['mutant']]
                    key = (item['form'], mutant['mutant'])
                    if key not in parsed:
                        parsed[key] = parse_forms(record['text'])
                    members.append((mutant['table'], mutant['edit'], bool(mutant.get('extra')), parsed[key]))
                gold_key = None
                for j, (table, edit, extra, forms) in enumerate(members):
                    record = head['tables'][table]
                    features = base_features(forms, item['form'], gold_forms, record['types'], record.get('task_level'))
                    if split == 'train':
                        pairs = [(base_vocab.setdefault(k, len(base_vocab)), float(v)) for k, v in features.items() if v]
                    else:
                        pairs = [(base_vocab[k], float(v)) for k, v in features.items() if v and k in base_vocab]
                    pairs.sort()
                    mats['base'].add([p[0] for p in pairs], [p[1] for p in pairs])
                    if j == 0:
                        gold_key = pairs
                    same = j > 0 and pairs == gold_key
                    train_rows = record.get('train_rows') or []
                    group = 'gold' if j == 0 else ('mutant empty' if any(not n for n in train_rows) else 'has rows')
                    rows.append((task, at, j, edit, group, bool(item['last']), extra, same, head['train'] != head['train']))
                    for kind, table_columns in (('stable', columns), ('null', columns), ('contingent', columns), ('fresh', columns), ('null_contingent', columns), ('null_fresh', columns), ('breaks', breaks)):
                        held = lists.get((table, kind))
                        if held is None:
                            mats[kind].add([])
                            continue
                        spots, hit = place(held[0], table_columns)
                        values = held[1][hit] if held[1] is not None else None
                        mats[kind].add(spots[hit], values)
                    mats['ctx'].add(ctx_row)
            count += 1
            if count % 50 == 0:
                print(f'{split} {count} {count / (time.time() - started):.1f}/s rows {len(rows)} nnz {mats["stable"].count}', flush=True)
        data[split] = dict(rows=rows, matrices={name: mats[name].csr({'base': 4096, 'ctx': 8192, 'breaks': len(breaks)}.get(name, len(columns))) for name in mats})
        print(split, 'rows', len(rows), 'nnz', {name: mats[name].count for name in mats}, flush=True)
    width_base, width_ctx = len(base_vocab), len(context_vocab)
    for split in data:
        data[split]['matrices']['base'] = data[split]['matrices']['base'][:, :width_base]
        data[split]['matrices']['ctx'] = data[split]['matrices']['ctx'][:, :width_ctx]
        with (out / f'{split}.rows.pkl').open('wb') as sink:
            pickle.dump(data[split]['rows'], sink, protocol=4)
        for name, matrix in data[split]['matrices'].items():
            with (out / f'{split}.{name}.pkl').open('wb') as sink:
                pickle.dump(matrix, sink, protocol=4)
    meta = dict(columns=columns, breaks=breaks, names=names, flags=flags, sizes=sizes, base=base_vocab, ctx=context_vocab)
    with (out / 'meta.pkl').open('wb') as sink:
        pickle.dump(meta, sink, protocol=4)
    print('built', flush=True)


def selected(rows, want_rows, include_last, include_extra, only_same):
    items = defaultdict(list)
    for index, row in enumerate(rows):
        items[(row[0], row[1])].append(index)
    out = []
    for members in items.values():
        first = rows[members[0]]
        if first[5] and not include_last:
            continue
        kept = [members[0]]
        for m in members[1:]:
            row = rows[m]
            if want_rows and row[4] == 'mutant empty':
                continue
            if row[6] and not include_extra:
                continue
            if only_same and not row[7]:
                continue
            kept.append(m)
        if len(kept) >= 2:
            out.append(kept)
    return out


FILTERS = {
    'rows': dict(want_rows=True, include_last=False, include_extra=False, only_same=False, label='mutant has rows, no last query'),
    'every': dict(want_rows=False, include_last=False, include_extra=False, only_same=False, label='every mutant, no last query'),
    'same': dict(want_rows=True, include_last=False, include_extra=True, only_same=True, label='same structure as gold, mutant has rows, no last query'),
}


def boot(values, n=2000):
    values = np.array(values, dtype=float)
    rng = np.random.default_rng(7)
    means = values[rng.integers(0, len(values), (n, len(values)))].mean(axis=1)
    return float(np.quantile(means, 0.005)), float(np.quantile(means, 0.995))


def score_items(rows, groups, scores):
    per_task = defaultdict(lambda: [0.0, 0, 0.0, 0.0, 0])
    per_edit = defaultdict(lambda: defaultdict(lambda: [0.0, 0]))
    for members in groups:
        task = rows[members[0]][0]
        gold = scores[members[0]]
        rest = scores[members[1:]]
        wins = (gold > rest).astype(float) + 0.5 * (gold == rest)
        held = per_task[task]
        held[0] += wins.sum()
        held[1] += len(rest)
        better = (rest > gold).sum() + 0.5 * (rest == gold).sum()
        held[2] += 1.0 / (1.0 + better)
        held[3] += float(better == 0)
        held[4] += 1
        for member, win in zip(members[1:], wins):
            edit = per_edit[task][rows[member][3]]
            edit[0] += win
            edit[1] += 1
    auc = {task: held[0] / held[1] for task, held in per_task.items()}
    mrr = {task: held[2] / held[4] for task, held in per_task.items()}
    first = {task: held[3] / held[4] for task, held in per_task.items()}
    edits = defaultdict(dict)
    for task, held in per_edit.items():
        for edit, (wins, count) in held.items():
            edits[edit][task] = wins / count
    return auc, mrr, first, edits


def group_auc(preds, data):
    total = count = 0.0
    at = 0
    for size in data.get_group():
        size = int(size)
        gold, rest = preds[at], preds[at + 1:at + size]
        total += float(((gold > rest) + 0.5 * (gold == rest)).mean())
        count += 1
        at += size
    return 'group_auc', total / max(count, 1.0), True


def fit_one(X, rows, groups, seed=7, threads=4, fraction=0.5):
    import lightgbm as lgb
    params = dict(objective='lambdarank', metric='None', label_gain=[0, 1], lambdarank_truncation_level=40, learning_rate=0.05, num_leaves=31, min_data_in_leaf=20, feature_fraction=fraction, feature_pre_filter=True, max_bin=31, num_threads=threads, verbosity=-1, seed=seed)
    tasks = sorted({rows[g[0]][0] for g in groups})
    rng = np.random.default_rng(seed)
    held = set(rng.choice(tasks, size=max(1, len(tasks) * 15 // 100), replace=False).tolist())

    def dataset(chosen, reference=None):
        order = [m for g in chosen for m in g]
        labels = np.array([1 if rows[m][2] == 0 else 0 for m in order])
        return lgb.Dataset(X[order], label=labels, group=[len(g) for g in chosen], reference=reference, free_raw_data=True)

    inner = [g for g in groups if rows[g[0]][0] not in held]
    outer = [g for g in groups if rows[g[0]][0] in held]
    train_set = dataset(inner)
    valid_set = dataset(outer, train_set)
    booster = lgb.train(params, train_set, num_boost_round=1500, valid_sets=[valid_set], feval=group_auc, callbacks=[lgb.early_stopping(100, verbose=False)])
    rounds = max(booster.best_iteration, 10)
    final = lgb.train(params, dataset(groups), num_boost_round=rounds)
    return final, rounds


def fit(out, sets, filters, threads, fraction):
    out = Path(out)
    meta = pickle.load((out / 'meta.pkl').open('rb'))
    needed = {'base'}
    for spec in sets:
        for raw in spec.split('+'):
            term = re.split(r'[~^]', raw)[0]
            if term == 'TIO_null':
                needed |= {'stable', 'null'}
            elif term in ('T', 'TI', 'TIO'):
                needed.add('stable')
            elif term in ('contingent', 'fresh'):
                needed.add(term)
            elif term in ('contingent_null', 'fresh_null'):
                needed |= {term.split('_')[0], 'null_' + term.split('_')[0]}
            elif term in ('ctx', 'breaks'):
                needed.add(term)

    def loaded(split):
        rows = pickle.load((out / f'{split}.rows.pkl').open('rb'))
        return dict(rows=rows, matrices={name: pickle.load((out / f'{split}.{name}.pkl').open('rb')) for name in needed})

    train, dev = loaded('train'), loaded('dev')
    columns = meta['columns']
    flags = np.array([meta['flags'].get(int(key), 0) for key in columns])
    names = [meta['names'].get(int(key), '') for key in columns]
    breaks_names = [meta['names'].get(int(key), '') for key in meta['breaks']]
    base_names = {index: key for key, index in meta['base'].items()}
    ctx_names = {index: str(key) for key, index in meta['ctx'].items()}
    print('rows', len(train['rows']), len(dev['rows']), 'columns', len(columns), 'by reading', Counter(READS.get(int(f), '?') for f in flags), flush=True)
    base_columns = {
        'base0': np.array([i for i in range(len(base_names)) if base_names[i] not in LABEL_STRUCTURE]),
        'base': np.arange(len(base_names)),
    }
    masks = {'T': flags == 4, 'TI': (flags == 4) | (flags == 5), 'TIO': flags > 0, 'O': flags >= 6}

    def word_mask(term, labels):
        """A term's name filter: `~WORD` leaves out, `^WORD` keeps."""
        keep = np.ones(len(labels), dtype=bool)
        for sign, word in re.findall(r'([~^])([^~^]+)', term):
            holds = np.array([word in label for label in labels])
            keep &= ~holds if sign == '~' else holds
        return keep

    def matrix(split, spec):
        parts = []
        labels = []
        for raw in spec.split('+'):
            term = re.split(r'[~^]', raw)[0]
            if term in base_columns:
                parts.append(split['matrices']['base'][:, base_columns[term]])
                labels.extend(base_names[int(i)] for i in base_columns[term])
            elif term == 'ctx':
                parts.append(split['matrices']['ctx'])
                labels.extend(ctx_names[i] for i in range(len(ctx_names)))
            elif term == 'breaks':
                parts.append(split['matrices']['breaks'])
                labels.extend('breaks:' + n for n in breaks_names)
            elif term in ('T', 'TI', 'TIO'):
                keep = np.flatnonzero(masks[term] & word_mask(raw, names))
                parts.append(split['matrices']['stable'][:, keep])
                labels.extend(names[int(i)] for i in keep)
            elif term in ('contingent', 'fresh'):
                keep = np.flatnonzero(word_mask(raw, names))
                parts.append(split['matrices'][term][:, keep])
                labels.extend(term + ':' + names[int(i)] for i in keep)
            elif term in ('TIO_null', 'contingent_null', 'fresh_null'):
                first, second = ('stable', 'null') if term == 'TIO_null' else (term.split('_')[0], 'null_' + term.split('_')[0])
                keep_true = np.flatnonzero((flags < 6) & (flags > 0) & word_mask(raw, names))
                keep_null = np.flatnonzero((flags >= 6) & word_mask(raw, names))
                parts.append(split['matrices'][first][:, keep_true])
                parts.append(split['matrices'][second][:, keep_null])
                labels.extend(names[int(i)] for i in keep_true)
                labels.extend(names[int(i)] for i in keep_null)
            else:
                raise ValueError(term)
        return (sp.hstack(parts, format='csr') if len(parts) > 1 else parts[0].tocsr()), labels

    sink = (out / 'fits.jsonl').open('a')
    for name in filters:
        chosen = FILTERS[name]
        args = {k: v for k, v in chosen.items() if k != 'label'}
        train_groups = selected(train['rows'], **args)
        dev_groups = selected(dev['rows'], **args)
        for spec in sets:
            started = time.time()
            X_train, labels = matrix(train, spec)
            X_dev, _ = matrix(dev, spec)
            model, rounds = fit_one(X_train, train['rows'], train_groups, threads=threads, fraction=fraction)
            scores = model.predict(X_dev)
            auc, mrr, first, edits = score_items(dev['rows'], dev_groups, scores)
            values = list(auc.values())
            low, high = boot(values)
            pairs = sum(len(g) - 1 for g in dev_groups)
            gain = model.feature_importance(importance_type='gain')
            top = np.argsort(-gain)[:15]
            train_auc = np.mean(list(score_items(train['rows'], train_groups, model.predict(X_train))[0].values()))
            print(f"{name:6} {spec:26} AUC {np.mean(values):.3f} ({low:.3f}, {high:.3f}) first {np.mean(list(first.values())):.3f} rr {np.mean(list(mrr.values())):.3f} tasks {len(values)} pairs {pairs} | train {train_auc:.3f} rounds {rounds} cols {X_train.shape[1]} used {int((gain > 0).sum())} {time.time() - started:.0f}s | " + ' '.join(f'{e} {np.mean(list(h.values())):.3f}' for e, h in sorted(edits.items())), flush=True)
            sink.write(json.dumps(dict(filter=name, spec=spec, auc=auc, mrr=mrr, first=first, edits={e: h for e, h in edits.items()}, rounds=rounds, top=[(labels[int(i)], float(gain[i])) for i in top if gain[i] > 0])) + '\n')
            sink.flush()
    sink.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['build', 'fit'])
    parser.add_argument('paths', nargs='+')
    parser.add_argument('--min-tasks', type=int, default=3)
    parser.add_argument('--sets', nargs='*', default=[])
    parser.add_argument('--filters', nargs='*', default=['rows', 'same'])
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--fraction', type=float, default=0.5)
    a = parser.parse_args()
    if a.command == 'build':
        build(a.paths[0], a.paths[1], a.min_tasks)
    else:
        fit(a.paths[0], a.sets, a.filters, a.threads, a.fraction)


if __name__ == '__main__':
    main()
