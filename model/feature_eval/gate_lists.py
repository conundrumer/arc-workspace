#!/usr/bin/env python
"""The Gate of docs/feature-spec/evaluation-protocol.md: trees that rank a gold query above its
mutants, trained on train tasks and read on dev tasks, read additively over what a shape reads.

  gate_lists.py build ROOT OUT [--min-tasks N]   the rows and the sparse matrices
  gate_lists.py fit OUT --sets ... --filters ... [--seeds N]
                                                 one line per set: the ensemble of N fits, with each fit's
                                                 spread, per-task values in OUT/fits.jsonl, every column's
                                                 summed gain in OUT/importance/, and the fits and their
                                                 columns in OUT/models/
  gate_lists.py compare OUT A B [--filter F]     the paired difference of two sets over dev tasks
  gate_lists.py score OUT SET VECTOR... [--filter F]
                                                 the score of a fit on each table a `feature-encoder vector`
                                                 file holds, at the assignment it holds first

ROOT is what `candidate-lists` writes: `lists/` on the true outputs and `null/` on deranged ones.
A shape's reading is one of: T, the table alone; TI, the table and the input; TO, the table and the
output; TIO, all three. A set is written as terms joined by `+`:
  base0, base   the features with no table content
  T, TI, TIO    the shapes up to that reading, on the true outputs: a shape's value where it is stable
  TIO_null      those, with each shape that reads the output taken on deranged outputs
  TIOg, TIOr    TIO's shapes with more of their numbers: g adds the mean over examples of every active
                shape, and r adds the least and the greatest too; `_null` as for TIO_null
  TIg, TIr      the same for the shapes that read no output
  TIOe          one row per candidate and example: a shape's value at that example beside its stable value, so a
                row keeps which value goes with which at an example. A set's line reads the mean over a
                candidate's rows, and `worst` reads its worst row. `_null` as for TIO_null. Every other term of
                its set repeats on each of a candidate's rows
  contingent, contingent_null
                the shapes of a candidate that not every table it reads has as stable
  ctx           the base tables' own part roots
  wide, wide_null
                a table's task-wide roots, from ROOT/../wide; `_null` as for TIO_null
  pair          a pair's own numbers, as the least, the mean and the greatest over examples, the same on
                every row of a task. They read the output, so a set that compares outputs leaves them out
  input, output, pairs
                what a task holds, the same on every candidate of an example: the base tables' vectors, and
                the pair family from ROOT/../state. Each reads the shapes that enough tasks have. They read
                true outputs, so a set that compares outputs leaves out output and pairs
  graph         a candidate's place in its state's graph, from ROOT/../state
  relations     the state's other tables against the candidate's: each shape's mean over the tables that the
                query reads, over their ancestors and over the rest, from ROOT/../state
  qv            what a candidate's table has against the tables its query reads: a share of its entries
                that each one has, its rows over theirs, its entries new to them. It reads the shapes
                that read the output, so a set that compares true and deranged outputs leaves it out
A term may end in `~WORD` to leave out the shapes whose name holds WORD, or `^WORD` to keep only those.
A set may end in `@K` to read only the shapes that tell gold from a mutant on K train tasks or more.
A fit reads one column for each set of columns equal on all its train rows, named by its shortest label.
"""
import argparse
import hashlib
import json
import pickle
import re
import subprocess
import sys
import time
from array import array
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import zstandard

sys.path.insert(0, str(Path(__file__).resolve().parent))
from candidate import read_lists  # noqa: E402
from common import open_text, read_json  # noqa: E402
from query_structure import LABEL_STRUCTURE, Reader, base_features, parse_forms  # noqa: E402

ROOT_REPO = Path('/Users/davidlu/code/arc-workspace')
READS = {4: 'T', 5: 'TI', 6: 'TO', 7: 'TIO'}
# What a task holds, and where each list stands.
FAMILIES = {'input': 'input', 'output': 'ex_output', 'pairs': 'pair'}
RELATIONS = ('parent', 'ancestor', 'other')
# The numbers of a shape that each graded term reads.
CHANNELS = {'TIOg': ('stable', 'mean'), 'TIOr': ('stable', 'mean', 'least', 'most'), 'TIg': ('stable', 'mean'), 'TIr': ('stable', 'mean', 'least', 'most')}


def split_of():
    out = {}
    for line in (ROOT_REPO / 'work/lm/data-study/samples/split.tsv').read_text().splitlines()[1:]:
        task, part, _ = line.split('\t')
        out[task] = part
    return out


def name_lines(folder):
    """Each line of a folder's names files: a run writes one of its own, and a run still going or
    stopped leaves its file with an unfinished end."""
    for path in sorted(folder.glob('names*.tsv.zst')):
        try:
            yield from open_text(path)
        except zstandard.ZstdError:
            continue


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


def every_entry(held, other):
    """A table's active shapes in order, with the least, the mean and the greatest of each."""
    ids = np.concatenate((held[0], other[0]))
    order = np.argsort(ids)
    return ids[order], {channel: np.concatenate((held[1], other[at]))[order] for at, channel in ((1, 'least'), (2, 'mean'), (3, 'most'))}


def told_apart(gold, mutant):
    """The shapes whose mean differs on two tables, where a shape only one of them has counts as differing."""
    _, in_gold, in_mutant = np.intersect1d(gold[0], mutant[0], assume_unique=True, return_indices=True)
    ours, theirs = gold[1]['mean'][in_gold], mutant[1]['mean'][in_mutant]
    differs = (ours != theirs) & ~(np.isnan(ours) & np.isnan(theirs))
    return np.concatenate((np.setxor1d(gold[0], mutant[0], assume_unique=True), gold[0][in_gold[differs]]))


def wide_lists(folder, name, items):
    """A task's lists of task-wide roots, where its file exists and its tables stand at the places of the per-input file."""
    path = folder / name
    if not path.exists():
        return {}, {}
    head, lists, others = read_lists(path, graded=True)
    if [item['gold'] for item in head['items']] != [item['gold'] for item in items]:
        print('wide file out of step', name, flush=True)
        return {}, {}
    return lists, others


def own_numbers(values):
    return values[0], {'mean': values[1]}


def read_names(forms, at):
    """The relations a form reads."""
    if at >= len(forms):
        return []
    reader = Reader()
    reader.form(forms[at])
    return sorted(set(reader.reads))


def parent_lists(folder, name):
    path = folder / name
    return read_lists(path, graded=True)[1:] if path.exists() else ({}, {})


def named(name, lists, others, parents, parent_others, place_of):
    """A read table's list and its other entries, from the parents' file, or from the table's own place."""
    if name in parents:
        return parents[name], parent_others[name]
    place = place_of.get(name)
    if place is not None and place in lists:
        return lists[place], others[place]
    return None


def rows_of(entry, key):
    """A table's mean row count, from its entry for the table's own count."""
    at = np.searchsorted(entry[0], key)
    return float(entry[1]['mean'][at]) if at < len(entry[0]) and entry[0][at] == key else 0.0


def state_lists(folder, name):
    """A task's state lists, with each of its items' place among them by the item's form."""
    path = folder / name
    if not path.exists():
        return {}, {}, {}
    head, lists, others = read_lists(path, graded=True)
    return lists, others, {item['form']: at for at, item in enumerate(head['items'])}


QV_NAMES = ('active', 'stable', 'stable_share', 'new_stable', 'new_stable_share', 'new_active', 'new_active_share', 'uses', 'assignments',
            'same_entries_share:max', 'same_entries_share:min', 'rows_over_use:max', 'rows_over_use:min')


def share_same(own, use):
    """The share of a table's entries that another table has with the same numbers."""
    if not len(own[0]):
        return 0.0
    _, here, there = np.intersect1d(own[0], use[0], assume_unique=True, return_indices=True)
    same = np.ones(len(here), dtype=bool)
    for channel in ('least', 'mean', 'most'):
        a, b = own[1][channel][here], use[1][channel][there]
        same &= (a == b) | (np.isnan(a) & np.isnan(b))
    return float(same.sum()) / len(own[0])


def relation_numbers(own, stable_count, new_stable, uses, read_tables, rows_key, assignments):
    """QV_NAMES's values for one candidate. `uses` holds the entries of the input and of each table its query reads,
    and `read_tables` those of the tables alone."""
    active = len(own[0])
    seen = np.unique(np.concatenate([use[0] for use in uses])) if uses else np.zeros(0, dtype=np.uint64)
    new_active = len(np.setdiff1d(own[0], seen, assume_unique=True))
    shares = [share_same(own, use) for use in uses]
    own_rows = rows_of(own, rows_key)
    ratios = [own_rows / rows for rows in (rows_of(table, rows_key) for table in read_tables) if rows]
    return (active, stable_count, stable_count / active if active else 0.0, new_stable, new_stable / stable_count if stable_count else 0.0, new_active, new_active / active if active else 0.0,
            len(read_tables), assignments or 0, max(shares, default=0.0), min(shares, default=0.0), max(ratios, default=0.0), min(ratios, default=0.0))


def place(ids, table):
    at = np.searchsorted(table, ids)
    at[at == len(table)] = 0
    hit = table[at] == ids if len(table) else np.zeros(len(ids), dtype=bool)
    return at, hit


def build(root, out, min_tasks, each_tasks=None):
    root, out = Path(root), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    parts = split_of()
    files = sorted((root / 'lists').glob('*.lists.zst'))
    print(len(files), 'task files', flush=True)
    # Which shapes tell gold from a mutant on three train tasks or more, on the true and on the null lists.
    told = {'stable': [], 'null': [], 'graded': [], 'null_graded': []}
    wide_root = root.parent / 'wide'
    state_root = root.parent / 'state'
    told_wide = []
    pair_seen = []
    family_seen = {family: [] for family in FAMILIES}
    graph_seen = []
    relation_seen = []
    started = time.time()
    done = 0
    for path in files:
        task = path.name.split('.')[0]
        if parts.get(task) != 'train':
            continue
        head, lists, others = read_lists(path, graded=True)
        null_path = root / 'null' / path.name
        null_lists, null_others = read_lists(null_path, graded=True)[1:] if null_path.exists() else ({}, {})
        seen = {kind: [] for kind in told}
        for item in head['items']:
            if item['last']:
                continue
            gold = item['gold']
            for mutant in item['mutants']:
                for kind, held, other in (('stable', lists, others), ('null', null_lists, null_others)):
                    a, b = held.get(gold), held.get(mutant['table'])
                    if a is not None and b is not None:
                        seen[kind].append(np.setxor1d(a[0], b[0], assume_unique=True))
                        if len(other[gold][0]) or len(other[mutant['table']][0]):
                            seen['graded' if kind == 'stable' else 'null_graded'].append(told_apart(every_entry(a, other[gold]), every_entry(b, other[mutant['table']])))
        for kind, held in seen.items():
            if held:
                told[kind].append(np.unique(np.concatenate(held)))
        wide, wide_others = wide_lists(wide_root / 'lists', path.name, head['items'])
        wide_null, _ = wide_lists(wide_root / 'null', path.name, head['items'])
        apart = []
        for item in head['items']:
            if item['last']:
                continue
            for mutant in item['mutants']:
                for held in (wide, wide_null):
                    a, b = held.get(item['gold']), held.get(mutant['table'])
                    if a is not None and b is not None:
                        apart.append(told_apart(own_numbers(a), own_numbers(b)))
        if apart:
            told_wide.append(np.unique(np.concatenate(apart)))
        if 'constant-values' in wide_others:
            pair_seen.append(wide_others['constant-values'][0])
        state, state_others, _ = state_lists(state_root / 'lists', path.name)
        for family, owner in FAMILIES.items():
            held, other = (state, state_others) if family == 'pairs' else (lists, others)
            if owner in held:
                family_seen[family].append(np.concatenate((held[owner][0], other[owner][0])))
        graph_ids = [state[owner][0] for owner in state if isinstance(owner, str) and owner.endswith('/graph')]
        if graph_ids:
            graph_seen.append(np.unique(np.concatenate(graph_ids)))
        relation_ids = [state_others[owner][0] for owner in state if isinstance(owner, str) and owner.rsplit('/', 1)[-1] in RELATIONS]
        if relation_ids:
            relation_seen.append(np.unique(np.concatenate(relation_ids)))
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
    columns = np.unique(np.concatenate(list(chosen.values())))
    def common(held):
        if not held:
            return np.zeros(0, dtype=np.uint64)
        ids, counts = np.unique(np.concatenate(held), return_counts=True)
        return ids[counts >= min_tasks]
    wide_columns, pair_columns = common(told_wide), common(pair_seen)
    train_files = sum(1 for path in files if parts.get(path.name.split('.')[0]) == 'train')
    each_tasks = max(min_tasks, train_files // 10) if each_tasks is None else each_tasks
    def common_at(held, at_least):
        if not held:
            return np.zeros(0, dtype=np.uint64)
        ids, counts = np.unique(np.concatenate(held), return_counts=True)
        return ids[counts >= at_least]
    family_columns = {family: common_at(held, each_tasks) for family, held in family_seen.items()}
    graph_columns, relation_columns = common_at(graph_seen, 1), common_at(relation_seen, each_tasks)
    print('family columns', {family: len(held) for family, held in family_columns.items()}, 'graph', len(graph_columns), 'relations', len(relation_columns), flush=True)
    column_tasks = np.zeros(len(columns), dtype=np.int32)
    for held in told.values():
        if held:
            ids, counts = np.unique(np.concatenate(held), return_counts=True)
            spots, hit = place(ids, columns)
            np.maximum.at(column_tasks, spots[hit], counts[hit])
    print('task-wide columns', len(wide_columns), 'pair columns', len(pair_columns), flush=True)
    # The names of the columns.
    names, flags, sizes = {}, {}, {}
    rows_key = 0
    wanted = set(columns.tolist())
    for line in name_lines(root / 'lists'):
        parts_line = line.rstrip('\n').split('\t')
        if len(parts_line) != 4:
            continue
        key = int(parts_line[0], 16)
        if key in wanted:
            names[key], flags[key], sizes[key] = parts_line[1], int(parts_line[2]), int(parts_line[3])
        if parts_line[1] == '(cardinality T)':
            rows_key = key
    print('names found', len(names), 'of', len(wanted), flush=True)
    wanted_family = set(family_columns['input'].tolist()) | set(family_columns['output'].tolist())
    family_names = {}
    for line in name_lines(root / 'lists'):
        parts_line = line.rstrip('\n').split('\t')
        if len(parts_line) == 4 and int(parts_line[0], 16) in wanted_family:
            family_names[int(parts_line[0], 16)] = parts_line[1]
    wanted_state = set(family_columns['pairs'].tolist()) | set(graph_columns.tolist()) | set(relation_columns.tolist())
    if state_root.exists():
        for line in name_lines(state_root / 'lists'):
            parts_line = line.rstrip('\n').split('\t')
            if len(parts_line) == 4 and int(parts_line[0], 16) in wanted_state:
                family_names[int(parts_line[0], 16)] = parts_line[1]
    wanted_wide = set(wide_columns.tolist()) | set(pair_columns.tolist())
    wide_names, wide_flags = {}, {}
    if wide_root.exists():
        for line in name_lines(wide_root / 'lists'):
            parts_line = line.rstrip('\n').split('\t')
            if len(parts_line) == 4 and int(parts_line[0], 16) in wanted_wide:
                wide_names[int(parts_line[0], 16)], wide_flags[int(parts_line[0], 16)] = parts_line[1], int(parts_line[2])
    base_vocab = {}
    context_vocab = {}
    data = {}
    parents_root = root.parent / 'parents'
    # A row per example holds only what enough tasks tell apart, since it repeats each entry once per example.
    each_keep = column_tasks >= each_tasks
    print('example rows read shapes told apart on', each_tasks, 'tasks or more:', int(each_keep.sum()), flush=True)
    for split in ('train', 'dev'):
        rows = []
        mats = {name: Matrix() for name in ('base', 'stable', 'null', 'contingent', 'null_contingent', 'ctx', 'qv', 'mean', 'least', 'most', 'null_mean', 'null_least', 'null_most', 'wide', 'null_wide', 'pair_least', 'pair_mean', 'pair_most', 'each', 'null_each', 'graph', 'relations')}
        example_of = []
        example_pair = []
        row_task = []
        first_example = []
        task_rows = {family: {channel: Matrix() for channel in ('stable', 'mean')} for family in FAMILIES}
        task_examples = {family: Matrix() for family in FAMILIES}
        examples_so_far = 0
        count = 0
        started = time.time()
        for path in files:
            task = path.name.split('.')[0]
            if parts.get(task) != split:
                continue
            head, lists, others = read_lists(path, graded=True)
            null_path = root / 'null' / path.name
            null_lists, null_others = read_lists(null_path, graded=True)[1:] if null_path.exists() else ({}, {})
            wide, wide_others = wide_lists(wide_root / 'lists', path.name, head['items'])
            wide_null, _ = wide_lists(wide_root / 'null', path.name, head['items'])
            pair_numbers = wide_others.get('constant-values', (np.zeros(0, dtype=np.uint64),) + (np.zeros(0, dtype=np.float32),) * 3)
            pair_spots, pair_hit = place(pair_numbers[0], pair_columns)
            state, state_others, state_item = state_lists(state_root / 'lists', path.name)
            first_example.append(examples_so_far)
            examples_so_far += head['train']
            for family, owner in FAMILIES.items():
                held, other = (state, state_others) if family == 'pairs' else (lists, others)
                if owner not in held:
                    task_rows[family]['stable'].add([])
                    task_rows[family]['mean'].add([])
                    for _ in range(head['train']):
                        task_examples[family].add([])
                    continue
                entries = other[owner]
                spots, hit = place(held[owner][0], family_columns[family])
                task_rows[family]['stable'].add(spots[hit], held[owner][1][hit])
                stable_at, stable_values = spots[hit], held[owner][1][hit]
                ids, numbers = every_entry(held[owner], entries)
                spots, hit = place(ids, family_columns[family])
                task_rows[family]['mean'].add(spots[hit], numbers['mean'][hit])
                graded_at, graded_hit = place(entries[0], family_columns[family])
                for pair in range(head['train']):
                    values = entries[4][:, pair][graded_hit] if entries[4].shape[1] else np.zeros(0, dtype=np.float32)
                    active = values != 0
                    at_all = np.concatenate((stable_at, graded_at[graded_hit][active] if entries[4].shape[1] else np.zeros(0, dtype=np.int64)))
                    order = np.argsort(at_all)
                    task_examples[family].add(at_all[order], np.concatenate((stable_values, values[active]))[order])
            read_true, read_true_others = parent_lists(parents_root / 'lists', path.name)
            read_null, read_null_others = parent_lists(parents_root / 'null', path.name)
            place_of = {listed['table']: listed['gold'] for listed in head['items']}
            mutants = read_json(root / split / 'mutants' / f'{task}.json')
            gold_forms = parse_forms(mutants['gold'])
            by_form = {q['form']: q for q in mutants['queries']}
            parsed = {}
            constants = lists.get('constants', (np.zeros(0, dtype=np.uint64), np.zeros(0, dtype=np.float32)))
            if 'constants' in others:
                constants = (np.concatenate((constants[0], others['constants'][0])), np.concatenate((constants[1], others['constants'][2])))
            for key in constants[0].tolist():
                if split == 'train':
                    context_vocab.setdefault(key, len(context_vocab))
            ctx_row = sorted((context_vocab[key], float(value)) for key, value in zip(constants[0].tolist(), constants[1].tolist()) if key in context_vocab)
            for at, item in enumerate(head['items']):
                query = by_form[item['form']]
                members = [(item['gold'], 'gold', False, gold_forms, item['types'], item.get('task_level'), item.get('assignments'))]
                for mutant in item['mutants']:
                    record = query['mutants'][mutant['mutant']]
                    key = (item['form'], mutant['mutant'])
                    if key not in parsed:
                        parsed[key] = parse_forms(record['text'])
                    members.append((mutant['table'], mutant['edit'], bool(mutant.get('extra')), parsed[key], mutant['types'], mutant.get('task_level'), mutant.get('assignments')))
                gold_key = None
                for j, (table, edit, extra, forms, types, task_level, assignments) in enumerate(members):
                    reads = read_names(forms, item['form'])
                    features = base_features(forms, item['form'], gold_forms, types, task_level)
                    if split == 'train':
                        pairs = [(base_vocab.setdefault(k, len(base_vocab)), float(v)) for k, v in features.items() if v]
                    else:
                        pairs = [(base_vocab[k], float(v)) for k, v in features.items() if v and k in base_vocab]
                    pairs.sort()
                    mats['base'].add([p[0] for p in pairs], [p[1] for p in pairs])
                    if j == 0:
                        gold_key = pairs
                    same = j > 0 and pairs == gold_key
                    train_rows = head['train_rows'][table]
                    group = 'gold' if j == 0 else ('mutant empty' if any(not n for n in train_rows) else 'has rows')
                    rows.append((task, at, j, edit, group, bool(item['last']), extra, same, False))
                    for name_, held_wide in (('wide', wide), ('null_wide', wide_null)):
                        entries = held_wide.get(table)
                        if entries is None:
                            mats[name_].add([])
                        else:
                            spots, hit = place(entries[0], wide_columns)
                            mats[name_].add(spots[hit], entries[1][hit])
                    for at_number, name_ in ((1, 'pair_least'), (2, 'pair_mean'), (3, 'pair_most')):
                        mats[name_].add(pair_spots[pair_hit], pair_numbers[at_number][pair_hit])
                    example_of.extend([len(rows) - 1] * head['train'])
                    example_pair.extend(range(head['train']))
                    row_task.append(len(first_example) - 1)
                    state_at = state_item.get(item['form'])
                    graph = state.get(f'{state_at}/{j}/graph')
                    if graph is None:
                        mats['graph'].add([])
                    else:
                        spots, hit = place(graph[0], graph_columns)
                        mats['graph'].add(spots[hit], graph[1][hit])
                    relation_at, relation_values = [], []
                    for number, relation in enumerate(RELATIONS):
                        held = state_others.get(f'{state_at}/{j}/{relation}')
                        if held is not None:
                            spots, hit = place(held[0], relation_columns)
                            relation_at.append(spots[hit] + number * len(relation_columns))
                            relation_values.append(held[2][hit])
                    if relation_at:
                        mats['relations'].add(np.concatenate(relation_at), np.concatenate(relation_values))
                    else:
                        mats['relations'].add([])
                    for kind, held_lists, held_others, held_read, held_read_others in (('stable', lists, others, read_true, read_true_others), ('null', null_lists, null_others, read_null, read_null_others)):
                        held = held_lists.get(table)
                        each_name = 'each' if kind == 'stable' else 'null_each'
                        channel_of = {'least': 'least', 'mean': 'mean', 'most': 'most'} if kind == 'stable' else {'least': 'null_least', 'mean': 'null_mean', 'most': 'null_most'}
                        if held is None:
                            for name in channel_of.values():
                                mats[name].add([])
                            mats[kind].add([])
                            for _ in range(head['train']):
                                mats[each_name].add([])
                            if kind == 'stable':
                                mats['qv'].add([])
                            if kind == 'stable':
                                mats['contingent'].add([])
                            else:
                                mats['null_contingent'].add([])
                            continue
                        spots, hit = place(held[0], columns)
                        mats[kind].add(spots[hit], held[1][hit])
                        ids, numbers = every_entry(held, held_others[table])
                        spots, hit = place(ids, columns)
                        for channel, name in channel_of.items():
                            mats[name].add(spots[hit], numbers[channel][hit])
                        stable_spots, stable_hit = place(held[0], columns)
                        stable_hit = stable_hit & each_keep[stable_spots]
                        graded_ids, *_, at_pairs = held_others[table]
                        graded_spots, graded_hit = place(graded_ids, columns)
                        graded_hit = graded_hit & each_keep[graded_spots]
                        for pair in range(head['train']):
                            values = at_pairs[:, pair][graded_hit] if at_pairs.shape[1] else np.zeros(0, dtype=np.float32)
                            active = values != 0
                            place_at = graded_spots[graded_hit][active] if at_pairs.shape[1] else np.zeros(0, dtype=np.int64)
                            at_all = np.concatenate((stable_spots[stable_hit], place_at))
                            order = np.argsort(at_all)
                            mats[each_name].add(at_all[order], np.concatenate((held[1][stable_hit], values[active]))[order])
                        # What not every table the query reads has as stable, nor the input.
                        read_tables = [found for found in (named(name, held_lists, held_others, held_read, held_read_others, place_of) for name in reads) if found is not None]
                        base = held_lists.get('input')
                        common = np.intersect1d(held[0], base[0], assume_unique=True) if base is not None else np.zeros(0, dtype=np.uint64)
                        for read_table, _ in read_tables:
                            common = np.intersect1d(common, read_table[0], assume_unique=True)
                        fresh = np.setdiff1d(held[0], common, assume_unique=True)
                        if kind == 'stable':
                            read_entries = [every_entry(read_table, read_other) for read_table, read_other in read_tables]
                            uses = ([every_entry(held_lists['input'], held_others['input'])] if 'input' in held_lists else []) + read_entries
                            numbers_of = relation_numbers((ids, numbers), len(held[0]), len(fresh), uses, read_entries, rows_key, assignments)
                            mats['qv'].add(np.arange(len(QV_NAMES)), np.array(numbers_of, dtype=np.float32))
                        spots, hit = place(fresh, columns)
                        mats['contingent' if kind == 'stable' else 'null_contingent'].add(spots[hit])
                    mats['ctx'].add([pair[0] for pair in ctx_row], [pair[1] for pair in ctx_row])
            count += 1
            if count % 50 == 0:
                print(f'{split} {count} {count / (time.time() - started):.1f}/s rows {len(rows)} nnz {mats["stable"].count}', flush=True)
        data[split] = dict(rows=rows, example_of=np.array(example_of, dtype=np.int64), index=dict(example_pair=np.array(example_pair, dtype=np.int64), row_task=np.array(row_task, dtype=np.int64), first_example=np.array(first_example, dtype=np.int64)), family={family: dict(stable=task_rows[family]['stable'].csr(len(family_columns[family])), mean=task_rows[family]['mean'].csr(len(family_columns[family])), each=task_examples[family].csr(len(family_columns[family]))) for family in FAMILIES}, matrices={name: mats[name].csr({'base': 4096, 'ctx': 8192, 'qv': len(QV_NAMES), 'wide': len(wide_columns), 'null_wide': len(wide_columns), 'pair_least': len(pair_columns), 'pair_mean': len(pair_columns), 'pair_most': len(pair_columns), 'graph': len(graph_columns), 'relations': len(RELATIONS) * len(relation_columns)}.get(name, len(columns))) for name in mats})
        print(split, 'rows', len(rows), 'nnz', {name: mats[name].count for name in mats}, flush=True)
    width_base, width_ctx = len(base_vocab), len(context_vocab)
    for split in data:
        data[split]['matrices']['base'] = data[split]['matrices']['base'][:, :width_base]
        data[split]['matrices']['ctx'] = data[split]['matrices']['ctx'][:, :width_ctx]
        with (out / f'{split}.rows.pkl').open('wb') as sink:
            pickle.dump(data[split]['rows'], sink, protocol=4)
        with (out / f'{split}.example_of.pkl').open('wb') as sink:
            pickle.dump(data[split]['example_of'], sink, protocol=4)
        with (out / f'{split}.index.pkl').open('wb') as sink:
            pickle.dump(data[split]['index'], sink, protocol=4)
        with (out / f'{split}.family.pkl').open('wb') as sink:
            pickle.dump(data[split]['family'], sink, protocol=4)
        for name, matrix in data[split]['matrices'].items():
            with (out / f'{split}.{name}.pkl').open('wb') as sink:
                pickle.dump(matrix, sink, protocol=4)
    meta = dict(columns=columns, column_tasks=column_tasks, names=names, flags=flags, sizes=sizes, base=base_vocab, ctx=context_vocab, wide_columns=wide_columns, pair_columns=pair_columns, wide_names=wide_names, wide_flags=wide_flags, family_columns=family_columns, family_names=family_names, graph_columns=graph_columns, relation_columns=relation_columns)
    with (out / 'meta.pkl').open('wb') as sink:
        pickle.dump(meta, sink, protocol=4)
    code = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, cwd=ROOT_REPO).stdout.strip()
    (out / 'provenance.json').write_text(json.dumps(dict(lists=str(root), code=code, min_tasks=min_tasks, each_tasks=each_tasks, tasks={split: len({row[0] for row in data[split]['rows']}) for split in data}, columns=len(columns))))
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


def per_pair(spec):
    return any(raw.split('~')[0].split('^')[0] in ('TIOe', 'TIOe_null') for raw in spec.split('+'))


def channel_null(channel):
    return 'null' if channel == 'stable' else f'null_{channel}'


def distinct_columns(X, labels):
    """One column for each set of columns equal on every row of X, and none for a column with no entry.
    Gives the columns kept and, for each, every column it stands for, its own first."""
    columns = X.tocsc()
    columns.sort_indices()
    groups = defaultdict(list)
    for j in range(columns.shape[1]):
        start, end = columns.indptr[j], columns.indptr[j + 1]
        if start < end:
            groups[hashlib.blake2b(columns.indices[start:end].tobytes() + columns.data[start:end].tobytes(), digest_size=16).digest()].append(j)
    members = sorted(sorted(group, key=lambda j: (len(labels[j]), labels[j])) for group in groups.values())
    return [group[0] for group in members], members


def write_importance(path, gain, splits, labels, members):
    """Each column's gain and splits, most gain first, with the column it is read through."""
    order = np.argsort(-gain, kind='stable')
    lines = (f'{gain[at]:.6g}\t{splits[at]}\t{labels[members[at][0]]}\t{labels[member]}\n' for at in order for member in members[at])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(zstandard.ZstdCompressor(level=6).compress(''.join(lines).encode()))


def compare(out, first, second, name):
    """The difference of two sets' task AUCs, on the tasks both read, from the last fit of each in OUT/fits.jsonl."""
    last = {}
    for line in (Path(out) / 'fits.jsonl').read_text().splitlines():
        record = json.loads(line)
        if record['filter'] == name:
            last[record['spec']] = record['auc']
    tasks = sorted(set(last[first]) & set(last[second]))
    differences = [last[first][task] - last[second][task] for task in tasks]
    low, high = boot(differences)
    print(f'{name}: {first} less {second}: {np.mean(differences):+.3f} ({low:+.3f}, {high:+.3f}) over {len(tasks)} tasks; better {sum(d > 0 for d in differences)}, worse {sum(d < 0 for d in differences)}', flush=True)


def vector_entries(path):
    """A vector file's first table as a fit reads it: per shape, its value where stable, its least, mean and
    greatest, and its value at each pair, over the train pairs, since the fit's tables hold train rows alone."""
    entries, train, block = {}, 0, 0
    for line in open_text(path):
        record = json.loads(line)
        if 'at' not in record:
            if 'train' in record:
                block += 1
                train = record['train']
            continue
        if block != 1:
            break
        slots = record['at'][:train]
        values = [0.0 if slot == 0 else (slot[0][0] / slot[0][1] if isinstance(slot[0], list) else float(slot[0])) for slot in slots if slot is not None]
        if not values:
            entries[record['shape']] = (0.0, float('nan'), float('nan'), float('nan'), [float('nan')] * len(slots))
        elif any(values):
            stable = values[0] if all(slot not in (0, None) and slot == slots[0] for slot in slots) else 0.0
            at = [float('nan') if slot is None else 0.0 if slot == 0 else (slot[0][0] / slot[0][1] if isinstance(slot[0], list) else float(slot[0])) for slot in slots]
            entries[record['shape']] = (stable, stable, stable, stable, at) if stable else (0.0, min(values), sum(values) / len(values), max(values), at)
    return entries


def column_value(label, entries, pair=0):
    """A column's value on one table at one pair, from its label: `shape:channel`, or a shape alone for its stable value."""
    shape, _, channel = label.rpartition(':') if label.rsplit(':', 1)[-1] in ('stable', 'mean', 'least', 'most', 'each') else (label, '', 'stable')
    held = entries.get(shape)
    if held is None:
        return 0.0
    return held[4][pair] if channel == 'each' else held[('stable', 'least', 'mean', 'most').index(channel)]


def score(out, spec, name, vectors):
    import lightgbm as lgb
    models = Path(out) / 'models'
    columns = (models / f'{name}.{spec}.columns.txt').read_text().splitlines()
    fits = [lgb.Booster(model_file=str(path)) for path in sorted(models.glob(f'{name}.{spec}.[0-9]*.txt'))]
    for vector in vectors:
        entries = vector_entries(vector)
        pairs = max((len(held[4]) for held in entries.values()), default=1) if per_pair(spec.split('@')[0]) else 1
        row = np.array([[column_value(label, entries, pair) for label in columns] for pair in range(pairs)])
        at = np.mean([fit.predict(row) for fit in fits], axis=0)
        print('|'.join(f'{value:+.3f}' for value in at) + f' {sum(1 for v in row[0] if v != 0)} of {len(columns)} columns hold an entry\t{vector}', flush=True)


def fit(out, sets, filters, threads, fraction, seeds=5):
    out = Path(out)
    meta = pickle.load((out / 'meta.pkl').open('rb'))
    needed = {'base'}
    families_needed = False
    for spec in sets:
        for raw in spec.split('@')[0].split('+'):
            term = re.split(r'[~^]', raw)[0]
            if term == 'TIO_null':
                needed |= {'stable', 'null'}
            elif term in ('T', 'TI', 'TIO'):
                needed.add('stable')
            elif term == 'contingent':
                needed.add(term)
            elif term == 'contingent_null':
                needed |= {'contingent', 'null_contingent'}
            elif term in ('ctx', 'qv', 'wide', 'graph', 'relations'):
                needed.add(term)
            elif term in FAMILIES:
                families_needed = True
            elif term == 'wide_null':
                needed |= {'wide', 'null_wide'}
            elif term == 'TIOe':
                needed |= {'each', 'stable'}
            elif term == 'TIOe_null':
                needed |= {'each', 'stable', 'null_each', 'null'}
            elif term == 'pair':
                needed |= {'pair_least', 'pair_mean', 'pair_most'}
            elif term in CHANNELS:
                needed |= set(CHANNELS[term])
            elif term.endswith('_null') and term[:-5] in CHANNELS:
                needed |= set(CHANNELS[term[:-5]]) | {channel_null(channel) for channel in CHANNELS[term[:-5]]}

    def loaded(split):
        rows = pickle.load((out / f'{split}.rows.pkl').open('rb'))
        example_of = pickle.load((out / f'{split}.example_of.pkl').open('rb')) if (out / f'{split}.example_of.pkl').exists() else None
        index = pickle.load((out / f'{split}.index.pkl').open('rb')) if (out / f'{split}.index.pkl').exists() else None
        family = pickle.load((out / f'{split}.family.pkl').open('rb')) if families_needed else None
        return dict(rows=rows, example_of=example_of, index=index, family=family, matrices={name: pickle.load((out / f'{split}.{name}.pkl').open('rb')) for name in needed})

    train, dev = loaded('train'), loaded('dev')
    columns = meta['columns']
    flags = np.array([meta['flags'].get(int(key), 0) for key in columns])
    names = [meta['names'].get(int(key), '') for key in columns]
    base_names = {index: key for key, index in meta['base'].items()}
    ctx_names = {index: str(key) for key, index in meta['ctx'].items()}
    print('rows', len(train['rows']), len(dev['rows']), 'columns', len(columns), 'by reading', Counter(READS.get(int(f), '?') for f in flags), flush=True)
    base_columns = {
        'base0': np.array([i for i in range(len(base_names)) if base_names[i] not in LABEL_STRUCTURE]),
        'base': np.arange(len(base_names)),
    }
    wide_labels = [meta['wide_names'].get(int(key), '') for key in meta.get('wide_columns', [])]
    wide_reads = np.array([meta['wide_flags'].get(int(key), 0) for key in meta.get('wide_columns', [])])
    masks = {'T': flags == 4, 'TI': (flags == 4) | (flags == 5), 'TIO': flags > 0, 'O': flags >= 6}

    column_tasks = meta.get('column_tasks', np.zeros(len(columns), dtype=np.int32))
    told_on = {'tasks': 0}

    def word_mask(term, labels):
        """A term's name filter: `~WORD` leaves out, `^WORD` keeps. It also keeps a set's `@K`."""
        keep = column_tasks >= told_on['tasks']
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
            elif term == 'qv':
                parts.append(split['matrices']['qv'])
                labels.extend(f'qv:{name}' for name in QV_NAMES)
            elif term in FAMILIES:
                held = split['family'][term]
                labels_of = [f"{term}:{meta['family_names'].get(int(key), '')}" for key in meta['family_columns'][term]]
                index = split['index']
                if per_pair(spec):
                    tasks = index['row_task'][split['example_of']]
                    parts.append(held['each'][index['first_example'][tasks] + index['example_pair']])
                    labels.extend(f'{label}:each' for label in labels_of)
                    parts.append(held['stable'][tasks])
                    labels.extend(f'{label}:stable' for label in labels_of)
                else:
                    parts.append(held['stable'][index['row_task']])
                    labels.extend(f'{label}:stable' for label in labels_of)
                    parts.append(held['mean'][index['row_task']])
                    labels.extend(f'{label}:mean' for label in labels_of)
            elif term == 'graph':
                parts.append(split['matrices']['graph'])
                labels.extend(f"graph:{meta['family_names'].get(int(key), '')}" for key in meta['graph_columns'])
            elif term == 'relations':
                parts.append(split['matrices']['relations'])
                labels.extend(f"{relation}:{meta['family_names'].get(int(key), '')}" for relation in RELATIONS for key in meta['relation_columns'])
            elif term == 'wide':
                parts.append(split['matrices']['wide'])
                labels.extend(wide_labels)
            elif term == 'wide_null':
                keep_true = np.flatnonzero(wide_reads < 6)
                keep_null = np.flatnonzero(wide_reads >= 6)
                parts.append(split['matrices']['wide'][:, keep_true])
                parts.append(split['matrices']['null_wide'][:, keep_null])
                labels.extend(wide_labels[int(i)] for i in keep_true)
                labels.extend(wide_labels[int(i)] for i in keep_null)
            elif term == 'pair':
                for channel in ('least', 'mean', 'most'):
                    parts.append(split['matrices'][f'pair_{channel}'])
                    labels.extend(f"{meta['wide_names'].get(int(key), '')}:{channel}" for key in meta['pair_columns'])
            elif term in ('T', 'TI', 'TIO'):
                keep = np.flatnonzero(masks[term] & word_mask(raw, names))
                parts.append(split['matrices']['stable'][:, keep])
                labels.extend(names[int(i)] for i in keep)
            elif term == 'contingent':
                keep = np.flatnonzero(word_mask(raw, names))
                parts.append(split['matrices'][term][:, keep])
                labels.extend(term + ':' + names[int(i)] for i in keep)
            elif term == 'TIOe':
                keep = np.flatnonzero((flags > 0) & word_mask(raw, names))
                parts.append(split['matrices']['each'][:, keep])
                labels.extend(f'{names[int(i)]}:each' for i in keep)
                parts.append(split['matrices']['stable'][:, keep])
                labels.extend(f'{names[int(i)]}:stable' for i in keep)
            elif term == 'TIOe_null':
                keep_true = np.flatnonzero((flags < 6) & (flags > 0) & word_mask(raw, names))
                keep_null = np.flatnonzero((flags >= 6) & word_mask(raw, names))
                for channel, null_channel, suffix in (('each', 'null_each', 'each'), ('stable', 'null', 'stable')):
                    parts.append(split['matrices'][channel][:, keep_true])
                    parts.append(split['matrices'][null_channel][:, keep_null])
                    labels.extend(f'{names[int(i)]}:{suffix}' for i in keep_true)
                    labels.extend(f'{names[int(i)]}:{suffix}' for i in keep_null)
            elif term in CHANNELS:
                keep = np.flatnonzero((flags > 0) & (flags < 6 if term.startswith('TI') and not term.startswith('TIO') else True) & word_mask(raw, names))
                for channel in CHANNELS[term]:
                    parts.append(split['matrices'][channel][:, keep])
                    labels.extend(f'{names[int(i)]}:{channel}' for i in keep)
            elif term.endswith('_null') and term[:-5] in CHANNELS:
                keep_true = np.flatnonzero((flags < 6) & (flags > 0) & word_mask(raw, names))
                keep_null = np.flatnonzero((flags >= 6) & word_mask(raw, names))
                for channel in CHANNELS[term[:-5]]:
                    parts.append(split['matrices'][channel][:, keep_true])
                    parts.append(split['matrices'][channel_null(channel)][:, keep_null])
                    labels.extend(f'{names[int(i)]}:{channel}' for i in keep_true)
                    labels.extend(f'{names[int(i)]}:{channel}' for i in keep_null)
            elif term in ('TIO_null', 'contingent_null'):
                first, second = ('stable', 'null') if term == 'TIO_null' else ('contingent', 'null_contingent')
                keep_true = np.flatnonzero((flags < 6) & (flags > 0) & word_mask(raw, names))
                keep_null = np.flatnonzero((flags >= 6) & word_mask(raw, names))
                parts.append(split['matrices'][first][:, keep_true])
                parts.append(split['matrices'][second][:, keep_null])
                labels.extend(names[int(i)] for i in keep_true)
                labels.extend(names[int(i)] for i in keep_null)
            else:
                raise ValueError(term)
        if per_pair(spec):
            # A candidate's own terms repeat on each of its pair rows.
            parts = [part.tocsr()[split['example_of']] if part.shape[0] == len(split['rows']) else part for part in parts]
        return (sp.hstack(parts, format='csr') if len(parts) > 1 else parts[0].tocsr()), labels

    def per_candidate(split, values, spec):
        """Each candidate's value: the mean over its example rows, where a set reads them."""
        if not per_pair(spec):
            return values
        of = split['example_of']
        return np.bincount(of, weights=values, minlength=len(split['rows'])) / np.maximum(np.bincount(of, minlength=len(split['rows'])), 1)

    def worst_of(split, values):
        """Each candidate's value at its worst example."""
        out = np.full(len(split['rows']), np.inf)
        np.minimum.at(out, split['example_of'], values)
        return out

    def pair_rows(split, groups):
        """The rows and the groups of a fit on pair rows: each candidate's rows stand for it in its group."""
        at = defaultdict(list)
        for row, candidate in enumerate(split['example_of'].tolist()):
            at[candidate].append(row)
        rows = [split['rows'][candidate] for candidate in split['example_of'].tolist()]
        return rows, [[row for member in group for row in at[member]] for group in groups]

    sink = (out / 'fits.jsonl').open('a')
    for name in filters:
        chosen = FILTERS[name]
        args = {k: v for k, v in chosen.items() if k != 'label'}
        train_groups = selected(train['rows'], **args)
        dev_groups = selected(dev['rows'], **args)
        for spec in sets:
            started = time.time()
            written_spec, _, told = spec.partition('@')
            told_on['tasks'] = int(told or 0)
            X_train, labels = matrix(train, written_spec)
            X_dev, _ = matrix(dev, written_spec)
            written = X_train.shape[1]
            kept, members = distinct_columns(X_train, labels)
            X_train, X_dev = X_train[:, kept], X_dev[:, kept]
            fit_rows, fit_groups = pair_rows(train, train_groups) if per_pair(written_spec) else (train['rows'], train_groups)
            runs = [fit_one(X_train, fit_rows, fit_groups, seed=7 + at, threads=threads, fraction=fraction) for at in range(seeds)]
            gain = sum(model.feature_importance(importance_type='gain') for model, _ in runs)
            splits = sum(model.feature_importance(importance_type='split') for model, _ in runs)
            write_importance(out / 'importance' / f'{name}.{spec}.tsv.zst', gain, splits, labels, members)
            kept_labels = [labels[j] for j in kept]
            for at, (model, _) in enumerate(runs):
                (out / 'models').mkdir(exist_ok=True)
                (out / 'models' / f'{name}.{spec}.{at}.txt').write_text(model.model_to_string())
            (out / 'models' / f'{name}.{spec}.columns.txt').write_text('\n'.join(kept_labels) + '\n')
            labels = kept_labels
            raw = [model.predict(X_dev) for model, _ in runs]
            each = [per_candidate(dev, values, written_spec) for values in raw]
            each_auc = [float(np.mean(list(score_items(dev['rows'], dev_groups, values)[0].values()))) for values in each]
            rounds = int(np.median([held for _, held in runs]))
            scores = np.mean(each, axis=0)
            auc, mrr, first, edits = score_items(dev['rows'], dev_groups, scores)
            worst = float(np.mean(list(score_items(dev['rows'], dev_groups, worst_of(dev, np.mean(raw, axis=0)))[0].values()))) if per_pair(written_spec) else None
            values = list(auc.values())
            low, high = boot(values)
            pairs = sum(len(g) - 1 for g in dev_groups)
            top = np.argsort(-gain)[:15]
            train_auc = np.mean(list(score_items(train['rows'], train_groups, per_candidate(train, np.mean([model.predict(X_train) for model, _ in runs], axis=0), written_spec))[0].values()))
            print(f"{name:6} {spec:26} AUC {np.mean(values):.3f} ({low:.3f}, {high:.3f}) worst {worst if worst is None else round(worst, 3)} seeds {np.mean(each_auc):.3f}+-{np.std(each_auc):.3f} first {np.mean(list(first.values())):.3f} rr {np.mean(list(mrr.values())):.3f} tasks {len(values)} pairs {pairs} | train {train_auc:.3f} rounds {rounds} cols {written} distinct {X_train.shape[1]} used {int((gain > 0).sum())} {time.time() - started:.0f}s | " + ' '.join(f'{e} {np.mean(list(h.values())):.3f}' for e, h in sorted(edits.items())), flush=True)
            sink.write(json.dumps(dict(filter=name, spec=spec, auc=auc, mrr=mrr, first=first, edits={e: h for e, h in edits.items()}, rounds=rounds, worst=worst, seeds=each_auc, columns=written, distinct=X_train.shape[1], used=int((gain > 0).sum()), top=[(labels[int(i)], float(gain[i])) for i in top if gain[i] > 0])) + '\n')
            sink.flush()
    sink.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['build', 'fit', 'compare', 'score'])
    parser.add_argument('paths', nargs='+')
    parser.add_argument('--min-tasks', type=int, default=3)
    parser.add_argument('--each-tasks', type=int)
    parser.add_argument('--sets', nargs='*', default=[])
    parser.add_argument('--filters', nargs='*', default=['rows', 'same'])
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--fraction', type=float, default=0.5)
    parser.add_argument('--seeds', type=int, default=5)
    parser.add_argument('--filter', default='rows')
    a = parser.parse_args()
    if a.command == 'build':
        build(a.paths[0], a.paths[1], a.min_tasks, a.each_tasks)
    elif a.command == 'compare':
        compare(a.paths[0], a.paths[1], a.paths[2], a.filter)
    elif a.command == 'score':
        score(a.paths[0], a.paths[1], a.filter, a.paths[2:])
    else:
        fit(a.paths[0], a.sets, a.filters, a.threads, a.fraction, a.seeds)


if __name__ == '__main__':
    main()
