"""The rows of a fit as blocks, and the fit that reads them, for `gate_lists.py`.

A build writes each fact once, at the level where it holds: a value at one example in a row of `each`, a value
every example of a candidate has in a row of `stable`, and what a task holds in a row of its family. A row of a fit points to
one block of each kind, so a fact that many rows share costs one entry. `engine/block-boost` compiles these blocks for a set
and boosts over them, with the objective, tree growth and parameters of LightGBM's lambdarank.
"""
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import tempfile
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import zstandard

ROOT = Path(__file__).resolve().parents[2]
BINARY = Path(os.environ.get('BLOCK_BOOST', ROOT / 'engine/target/tool/block-boost'))
NONE = np.uint32(0xFFFFFFFF)
PARAMETERS = dict(learning_rate=0.05, num_leaves=31, min_data_in_leaf=20, min_sum_hessian=1e-3, truncation=40, max_rounds=1500, patience=100)
MAX_BIN = 31
# The entries of a column that its bins come from. LightGBM bins from up to 200,000 rows.
SAMPLE_CAP = 200000


class BlockMatrix:
    """A sparse matrix built one row at a time, as a stream of zstd frames. A frame holds a row count, an entry count, each
    row's length, each entry's column as its difference from the entry before, and each entry's value."""

    folder = None
    ENTRIES = 1 << 21
    ROWS = 4096

    def __init__(self):
        handle, self.path = tempfile.mkstemp(dir=BlockMatrix.folder, suffix='.working')
        os.close(handle)
        self.sink = open(self.path, 'wb')
        self.compressor = zstandard.ZstdCompressor(level=3)
        self.count = 0
        self.rows = 0
        self.lengths, self.columns, self.values = [], [], []
        self.held = 0

    def add(self, indices, data=None):
        columns = np.asarray(indices, dtype=np.int32)
        self.lengths.append(len(columns))
        self.columns.append(columns)
        self.values.append(np.ones(len(columns), dtype=np.float32) if data is None else np.asarray(data, dtype=np.float32))
        self.held += len(columns)
        self.count += len(columns)
        self.rows += 1
        if self.held >= self.ENTRIES or len(self.lengths) >= self.ROWS:
            self.flush()

    def flush(self):
        if not self.lengths:
            return
        columns = np.concatenate(self.columns)
        record = struct.pack('<IQ', len(self.lengths), len(columns)) + np.array(self.lengths, dtype=np.uint32).tobytes() + np.diff(columns, prepend=0).astype(np.int32).tobytes() + np.concatenate(self.values).tobytes()
        self.sink.write(self.compressor.compress(record))
        self.lengths, self.columns, self.values = [], [], []
        self.held = 0

    def write(self, path):
        self.flush()
        self.sink.close()
        os.replace(self.path, path)


def run(*arguments):
    if not BINARY.exists():
        raise SystemExit(f'{BINARY} is missing: run `cargo build --profile tool -p block-boost` in engine/')
    subprocess.run([str(BINARY), *map(str, arguments)], check=True)


def raw(path, values, kind):
    np.asarray(values, dtype=kind).tofile(path)


class Plan:
    """The columns of a set on one split: what each use of a source reads, and which block each row points to."""

    def __init__(self, directory, out, split, meta):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.out, self.split, self.meta = Path(out), split, meta
        self.labels, self.uses, self.maps = [], [], {}
        self.rows = 0

    def source(self, name):
        return self.out / 'blocks' / f'{self.split}.{name}.zst'

    def map(self, name, of, domain):
        self.maps[name] = (len(self.maps), np.asarray(of, dtype=np.uint32), domain)
        self.rows = len(of)

    def add(self, source, width, map_name, at, labels):
        """New columns, read from the columns `at` of a source, and their numbers."""
        first = len(self.labels)
        self.labels.extend(labels)
        ids = first + np.arange(len(at))
        self.also(source, width, map_name, at, ids)
        return ids

    def also(self, source, width, map_name, at, ids):
        """Columns that also read the columns `at` of a source."""
        if len(at):
            self.uses.append((source, width, map_name, np.asarray(at, dtype=np.int64), ids))

    def write(self, threads, reference=None):
        for name, (place, of, domain) in self.maps.items():
            raw(self.directory / f'map{place}.u32', of, np.uint32)
        uses = []
        for place, (source, width, map_name, at, ids) in enumerate(self.uses):
            col_map = np.full(width, -1, dtype=np.int32)
            col_map[at] = ids
            raw(self.directory / f'use{place}.i32', col_map, np.int32)
            uses.append(dict(file=str(self.source(source)), map=self.maps[map_name][0], col_map=f'use{place}.i32'))
        maps = sorted(self.maps.values(), key=lambda held: held[0])
        (self.directory / 'plan.json').write_text(json.dumps(dict(
            rows=self.rows, columns=len(self.labels), max_bin=MAX_BIN, sample_cap=SAMPLE_CAP, threads=threads, categorical=[],
            reference=str(reference) if reference else None,
            maps=[dict(file=f'map{place}.u32', domain=domain) for place, _, domain in maps], uses=uses)))


def plan_of(directory, out, split, meta, data, spec, groups, told):
    """A set's plan over the rows of `groups`, and the candidate of each row."""
    from gate_lists import CHANNELS, FAMILIES, LABEL_STRUCTURE, QV_NAMES, RELATIONS, channel_null, per_pair
    plan = Plan(directory, out, split, meta)
    widths = meta['widths']
    columns = meta['columns']
    flags = np.array([meta['flags'].get(int(key), 0) for key in columns])
    names = [meta['names'].get(int(key), '') for key in columns]
    column_tasks = meta['column_tasks']
    index = data['index']
    members = np.array(sorted({m for g in groups for m in g}), dtype=np.int64)
    per = per_pair(spec)
    if per:
        wanted = np.flatnonzero(np.isin(data['example_of'], members))
        of = data['example_of'][wanted]
        pair = index['example_pair'][wanted]
    else:
        wanted, of, pair = members, members, None
    candidates = len(data['rows'])
    tasks = index['row_task'][of]
    plan.map('candidate', of, candidates)
    plan.map('task', tasks, len(index['first_example']))
    if per:
        in_scope = pair < index['task_train'][tasks]
        plan.map('row', wanted, len(data['example_of']))
        plan.map('candidate_train', np.where(in_scope, of, NONE), candidates)
        plan.map('task_train', np.where(in_scope, tasks, NONE), len(index['first_example']))
        plan.map('task_example', index['first_example'][tasks] + pair, index['examples'])

    def word_mask(term, labels):
        keep = column_tasks >= told
        for sign, word in re.findall(r'([~^])([^~^]+)', term):
            holds = np.array([word in label for label in labels])
            keep &= ~holds if sign == '~' else holds
        return keep

    def named(at, suffix='', prefix=''):
        return [f'{prefix}{names[int(i)]}{suffix}' for i in at]

    def each_and_stable(each, stable, at, reads_output, each_labels, stable_labels, row_map, whole_map, train_map):
        """A value at one example, and a value every example has. The second is also the first's value at each example of
        the column's scope, which is the train pairs where the column reads the output."""
        each_ids = plan.add(each, widths[each], row_map, at, each_labels)
        stable_ids = plan.add(stable, widths[stable], whole_map, at, stable_labels)
        plan.also(stable, widths[stable], whole_map, at[~reads_output], each_ids[~reads_output])
        plan.also(stable, widths[stable], train_map, at[reads_output], each_ids[reads_output])

    base_names = {place: key for key, place in meta['base'].items()}
    ctx_names = {place: str(key) for key, place in meta['ctx'].items()}
    wide_labels = [meta['wide_names'].get(int(key), '') for key in meta['wide_columns']]
    wide_reads = np.array([meta['wide_flags'].get(int(key), 0) for key in meta['wide_columns']])
    masks = {'T': flags == 4, 'TI': (flags == 4) | (flags == 5), 'TIO': flags > 0}
    for raw_term in spec.split('+'):
        term = re.split(r'[~^]', raw_term)[0]
        if term in ('base0', 'base'):
            at = np.array([i for i in range(len(base_names)) if term == 'base' or base_names[i] not in LABEL_STRUCTURE])
            plan.add('base', widths['base'], 'candidate', at, [base_names[int(i)] for i in at])
        elif term == 'ctx':
            plan.add('ctx', widths['ctx'], 'candidate', np.arange(len(ctx_names)), [ctx_names[i] for i in range(len(ctx_names))])
        elif term == 'qv':
            plan.add('qv', widths['qv'], 'candidate', np.arange(len(QV_NAMES)), [f'qv:{name}' for name in QV_NAMES])
        elif term in FAMILIES:
            keys = meta['family_columns'][term]
            labels = [f"{term}:{meta['family_names'].get(int(key), '')}" for key in keys]
            at = np.arange(len(keys))
            width = len(keys)
            stable, mean, each = f'family.{term}.stable', f'family.{term}.mean', f'family.{term}.each'
            if per:
                reads = np.array([bool(meta['family_flags'].get(int(key), 0) & 2) for key in keys], dtype=bool)
                each_ids = plan.add(each, width, 'task_example', at, [f'{label}:each' for label in labels])
                plan.add(stable, width, 'task', at, [f'{label}:stable' for label in labels])
                plan.also(stable, width, 'task', at[~reads], each_ids[~reads])
                plan.also(stable, width, 'task_train', at[reads], each_ids[reads])
            else:
                plan.add(stable, width, 'task', at, [f'{label}:stable' for label in labels])
                plan.add(mean, width, 'task', at, [f'{label}:mean' for label in labels])
        elif term == 'graph':
            plan.add('graph', widths['graph'], 'candidate', np.arange(widths['graph']), [f"graph:{meta['family_names'].get(int(key), '')}" for key in meta['graph_columns']])
        elif term == 'query':
            plan.add('query', widths['query'], 'candidate', np.arange(widths['query']), [f"query:{meta['family_names'].get(int(key), '')}" for key in meta['query_columns']])
        elif term in ('relations', 'relations_least', 'relations_most'):
            suffix = {'relations': '', 'relations_least': ':least', 'relations_most': ':most'}[term]
            plan.add(term, widths[term], 'candidate', np.arange(widths[term]), [f"{relation}:{meta['family_names'].get(int(key), '')}{suffix}" for relation in RELATIONS for key in meta['relation_columns']])
        elif term == 'wide':
            plan.add('wide', widths['wide'], 'candidate', np.arange(widths['wide']), wide_labels)
        elif term == 'wide_null':
            keep_true, keep_null = np.flatnonzero(wide_reads < 6), np.flatnonzero(wide_reads >= 6)
            plan.add('wide', widths['wide'], 'candidate', keep_true, [wide_labels[int(i)] for i in keep_true])
            plan.add('null_wide', widths['wide'], 'candidate', keep_null, [wide_labels[int(i)] for i in keep_null])
        elif term == 'pair':
            for channel in ('least', 'mean', 'most'):
                plan.add(f'pair_{channel}', widths[f'pair_{channel}'], 'candidate', np.arange(widths[f'pair_{channel}']), [f"{meta['wide_names'].get(int(key), '')}:{channel}" for key in meta['pair_columns']])
        elif term in ('T', 'TI', 'TIO'):
            at = np.flatnonzero(masks[term] & word_mask(raw_term, names))
            plan.add('stable', widths['stable'], 'candidate', at, named(at))
        elif term == 'contingent':
            at = np.flatnonzero(word_mask(raw_term, names))
            plan.add('contingent', widths['contingent'], 'candidate', at, named(at, prefix='contingent:'))
        elif term == 'TIOe':
            at = np.flatnonzero((flags > 0) & word_mask(raw_term, names))
            each_and_stable('each', 'stable', at, flags[at] >= 6, named(at, ':each'), named(at, ':stable'), 'row', 'candidate', 'candidate_train')
        elif term == 'TIOe_null':
            mask = word_mask(raw_term, names)
            keep_true, keep_null = np.flatnonzero((flags < 6) & (flags > 0) & mask), np.flatnonzero((flags >= 6) & mask)
            each_and_stable('each', 'stable', keep_true, np.zeros(len(keep_true), dtype=bool), named(keep_true, ':each'), named(keep_true, ':stable'), 'row', 'candidate', 'candidate_train')
            each_and_stable('null_each', 'null', keep_null, np.ones(len(keep_null), dtype=bool), named(keep_null, ':each'), named(keep_null, ':stable'), 'row', 'candidate', 'candidate_train')
        elif term in CHANNELS:
            at = np.flatnonzero((flags > 0) & (flags < 6 if term.startswith('TI') and not term.startswith('TIO') else True) & word_mask(raw_term, names))
            for channel in CHANNELS[term]:
                plan.add(channel, widths[channel], 'candidate', at, named(at, f':{channel}'))
        elif term.endswith('_null') and term[:-5] in CHANNELS:
            mask = word_mask(raw_term, names)
            keep_true, keep_null = np.flatnonzero((flags < 6) & (flags > 0) & mask), np.flatnonzero((flags >= 6) & mask)
            for channel in CHANNELS[term[:-5]]:
                plan.add(channel, widths[channel], 'candidate', keep_true, named(keep_true, f':{channel}'))
                plan.add(channel_null(channel), widths[channel_null(channel)], 'candidate', keep_null, named(keep_null, f':{channel}'))
        elif term in ('TIO_null', 'contingent_null'):
            first, second = ('stable', 'null') if term == 'TIO_null' else ('contingent', 'null_contingent')
            mask = word_mask(raw_term, names)
            keep_true, keep_null = np.flatnonzero((flags < 6) & (flags > 0) & mask), np.flatnonzero((flags >= 6) & mask)
            plan.add(first, widths[first], 'candidate', keep_true, named(keep_true))
            plan.add(second, widths[second], 'candidate', keep_null, named(keep_null))
        else:
            raise ValueError(term)
    return plan, of


def kept_columns(directory, labels, min_data):
    """One column for each set of columns equal on every row, and none for a column on too few rows for a tree to split:
    a side of a split holds only such a column's rows or its default's, and that side needs `min_data` rows. Gives each
    column's number among those kept, or -1, and each kept column's members, its own label first."""
    directory = Path(directory)
    hash0, hash1 = np.fromfile(directory / 'hash0.u64', dtype=np.uint64), np.fromfile(directory / 'hash1.u64', dtype=np.uint64)
    count = np.fromfile(directory / 'count.u64', dtype=np.uint64)
    active = np.flatnonzero(count >= min_data)
    order = active[np.lexsort((count[active], hash1[active], hash0[active]))]
    groups = defaultdict(list)
    if len(order):
        same = (hash0[order][1:] == hash0[order][:-1]) & (hash1[order][1:] == hash1[order][:-1]) & (count[order][1:] == count[order][:-1])
        starts = np.concatenate(([0], np.flatnonzero(~same) + 1))
        for start, end in zip(starts.tolist(), starts[1:].tolist() + [len(order)]):
            groups[start] = order[start:end].tolist()
    members = sorted(sorted(group, key=lambda j: (len(labels[j]), labels[j])) for group in groups.values())
    keep = np.full(len(labels), -1, dtype=np.int32)
    for place, group in enumerate(members):
        keep[group[0]] = place
    return keep, members


def fit(out, meta, sets, filters, threads, fraction, seeds):
    from gate_lists import FILTERS, boot, per_pair, score_items, selected, write_importance
    from common import read_pickle
    out = Path(out)

    def loaded(split):
        return dict(
            rows=read_pickle(out / f'{split}.rows.pkl'),
            example_of=read_pickle(out / f'{split}.example_of.pkl'),
            index=read_pickle(out / f'{split}.index.pkl'))

    train, dev = loaded('train'), loaded('dev')
    print('train rows', len(train['rows']), 'columns', len(meta['columns']), flush=True)
    sink = (out / 'fits.jsonl').open('a')
    for name in filters:
        args = {k: v for k, v in FILTERS[name].items() if k != 'label'}
        train_groups = selected(train['rows'], **args)
        dev_groups = selected(dev['rows'], **args)
        for spec in sets:
            started = time.time()
            written_spec, _, told = spec.partition('@')
            # A restart goes on from the files of this directory, so its name holds everything those files depend on.
            settings = json.dumps(dict(PARAMETERS, max_bin=MAX_BIN, sample_cap=SAMPLE_CAP, fraction=fraction, seeds=seeds), sort_keys=True)
            code = hashlib.sha1(BINARY.read_bytes() + Path(__file__).read_bytes()).hexdigest()
            work = out / 'compiled' / hashlib.sha1(f'{name}|{spec}|{settings}|{code}'.encode()).hexdigest()[:16]
            plan, of_train = plan_of(work / 'train', out, 'train', meta, train, written_spec, train_groups, int(told or 0))
            labels = plan.labels
            plan.write(threads)
            print(f'{spec}: rows {plan.rows} columns {len(labels)} uses {len(plan.uses)}', flush=True)
            # A step whose last file exists is done, so a restart goes on from there.
            if not (work / 'train' / 'nans.u64').exists():
                run('scan', work / 'train')
            keep, members = kept_columns(work / 'train', labels, PARAMETERS['min_data_in_leaf'])
            raw(work / 'train' / 'keep.i32', keep, np.int32)
            if not (work / 'train' / 'compiled.json').exists():
                run('compile', work / 'train')
            dev_plan, of_dev = plan_of(work / 'dev', out, 'dev', meta, dev, written_spec, dev_groups, int(told or 0))
            dev_plan.write(threads, reference=work / 'train')
            raw(work / 'dev' / 'keep.i32', keep, np.int32)
            if not (work / 'dev' / 'compiled.json').exists():
                run('compile', work / 'dev')
            # A row's label is its candidate's, and a group's rows stand together.
            rows_at = defaultdict(list)
            for row, candidate in enumerate(of_train.tolist()):
                rows_at[candidate].append(row)
            group_rows = [[row for member in group for row in rows_at[member]] for group in train_groups]
            assert [row for rows in group_rows for row in rows] == list(range(len(of_train))), 'rows out of the order of the groups'
            raw(work / 'groups.u32', np.cumsum([0] + [len(rows) for rows in group_rows]), np.uint32)
            raw(work / 'labels.u8', [1 if train['rows'][candidate][2] == 0 else 0 for candidate in of_train.tolist()], np.uint8)
            group_tasks = [train['rows'][group[0]][0] for group in train_groups]
            tasks = sorted(set(group_tasks))
            seeded = []
            for at in range(seeds):
                seed = 7 + at
                rng = np.random.default_rng(seed)
                held = set(rng.choice(tasks, size=max(1, len(tasks) * 15 // 100), replace=False).tolist())
                raw(work / f'held.{seed}.u8', [task in held for task in group_tasks], np.uint8)
                seeded.append(dict(seed=seed, held=str(work / f'held.{seed}.u8')))
            (work / 'fit.json').write_text(json.dumps(dict(
                PARAMETERS, fraction=fraction, threads=threads, train=str(work / 'train'), dev=str(work / 'dev'), out=str(work / 'fits'),
                groups=str(work / 'groups.u32'), labels=str(work / 'labels.u8'), seeds=seeded)))
            run('fit', work / 'fit.json')
            kept_labels = [labels[group[0]] for group in members]
            gain, splits = np.zeros(len(members)), np.zeros(len(members), dtype=np.int64)
            scores_train, raw_dev, each_auc, rounds_all = [], [], [], []

            def per_candidate(of, values, count):
                return np.bincount(of, weights=values, minlength=count) / np.maximum(np.bincount(of, minlength=count), 1)

            (out / 'models').mkdir(exist_ok=True)
            for at, entry in enumerate(seeded):
                seed = entry['seed']
                fits = work / 'fits'
                gain += np.fromfile(fits / f'gain.{seed}.f64', dtype=np.float64)
                splits += np.fromfile(fits / f'splits.{seed}.u32', dtype=np.uint32)
                scores_train.append(np.fromfile(fits / f'train.{seed}.f64', dtype=np.float64))
                values = np.fromfile(fits / f'dev.{seed}.f64', dtype=np.float64)
                raw_dev.append(values)
                each_auc.append(float(np.mean(list(score_items(dev['rows'], dev_groups, per_candidate(of_dev, values, len(dev['rows'])))[0].values()))))
                rounds_all.append(json.loads((fits / f'done.{seed}.json').read_text())['rounds'])
                shutil.copy(fits / f'model.{seed}.jsonl', out / 'models' / f'{name}.{spec}.{at}.jsonl')
            write_importance(out / 'importance' / f'{name}.{spec}.tsv.zst', gain, splits, labels, members)
            (out / 'models' / f'{name}.{spec}.columns.txt').write_text('\n'.join(kept_labels) + '\n')
            train_auc = np.mean(list(score_items(train['rows'], train_groups, per_candidate(of_train, np.mean(scores_train, axis=0), len(train['rows'])))[0].values()))
            mean_dev = np.mean(raw_dev, axis=0)
            scores = per_candidate(of_dev, mean_dev, len(dev['rows']))
            auc, mrr, first, edits = score_items(dev['rows'], dev_groups, scores)
            worst = None
            if per_pair(written_spec):
                least = np.full(len(dev['rows']), np.inf)
                np.minimum.at(least, of_dev, mean_dev)
                worst = float(np.mean(list(score_items(dev['rows'], dev_groups, least)[0].values())))
            values = list(auc.values())
            low, high = boot(values)
            pairs = sum(len(g) - 1 for g in dev_groups)
            rounds = int(np.median(rounds_all))
            top = np.argsort(-gain)[:15]
            print(f"{name:6} {spec:26} AUC {np.mean(values):.3f} ({low:.3f}, {high:.3f}) worst {worst if worst is None else round(worst, 3)} seeds {np.mean(each_auc):.3f}+-{np.std(each_auc):.3f} first {np.mean(list(first.values())):.3f} rr {np.mean(list(mrr.values())):.3f} tasks {len(values)} pairs {pairs} | train {train_auc:.3f} rounds {rounds} cols {len(labels)} distinct {len(members)} used {int((gain > 0).sum())} {time.time() - started:.0f}s | " + ' '.join(f'{e} {np.mean(list(h.values())):.3f}' for e, h in sorted(edits.items())), flush=True)
            sink.write(json.dumps(dict(filter=name, spec=spec, auc=auc, mrr=mrr, first=first, edits={e: h for e, h in edits.items()}, rounds=rounds, worst=worst, seeds=each_auc, columns=len(labels), distinct=len(members), used=int((gain > 0).sum()), top=[(kept_labels[int(i)], float(gain[i])) for i in top if gain[i] > 0])) + '\n')
            sink.flush()
            shutil.rmtree(work)
    sink.close()


def score(models, spec, name, vectors):
    """A fit's value on each table of the vector files, at each example."""
    from gate_lists import column_value, per_pair, vector_entries
    columns = (models / f'{name}.{spec}.columns.txt').read_text().splitlines()
    fits = [[json.loads(line) for line in path.open()] for path in sorted(models.glob(f'{name}.{spec}.[0-9]*.jsonl'))]

    def leaf(tree, row):
        if not tree['column']:
            return tree['value'][0]
        node = 0
        while True:
            x = row[tree['column'][node]]
            if x != x and not tree['nan_seen'][node]:
                x = 0.0
            bound = tree['threshold'][node]
            goes_left = tree['default_left'][node] if x != x else bound is None or x <= bound
            node = tree['left'][node] if goes_left else tree['right'][node]
            if node < 0:
                return tree['value'][~node]

    for vector in vectors:
        entries = vector_entries(vector)
        pairs = max((len(held[4]) for held in entries.values()), default=1) if per_pair(spec.split('@')[0]) else 1
        at = []
        for pair in range(pairs):
            row = [column_value(label, entries, pair) for label in columns]
            at.append(np.mean([sum(leaf(tree, row) for tree in trees) for trees in fits]))
        print('|'.join(f'{value:+.3f}' for value in at) + f' {sum(1 for label in columns if column_value(label, entries, 0) != 0)} of {len(columns)} columns hold an entry\t{vector}', flush=True)
