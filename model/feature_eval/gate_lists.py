#!/usr/bin/env python
"""The Gate of docs/feature-spec/evaluation-protocol.md: trees that rank a gold query above its
mutants, trained on train tasks and read on dev tasks, read additively over what a shape reads.

  gate_lists.py build ROOT OUT                   every shape, with each fact stored once at the level where
                                                 it holds, for a fit by engine/block-boost
  gate_lists.py fit OUT --sets ... --filters ... [--seeds N]
                                                 one line per set: the ensemble of N fits, with each fit's
                                                 spread, per-task values in OUT/fits.jsonl, every column's
                                                 summed gain in OUT/importance/, and the fits and their
                                                 columns in OUT/models/
  gate_lists.py compare OUT A B [--filter F]     the paired difference of two sets over dev tasks
  gate_lists.py score OUT SET VECTOR... [--filter F]
                                                 the score of a fit on each table a `feature-encoder vector`
                                                 file holds, at the assignment it holds first

ROOT is what `candidate-lists` writes: `lists/` on the true outputs and `null/` on deranged ones. A table's named shapes, from
ROOT/../named, stand beside its generated shapes.
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
                the pair family from ROOT/../state. They read true outputs, so a set that compares outputs
                leaves out output and pairs
  graph         a candidate's place in its state's graph, from ROOT/../state
  relations     the state's other tables against the candidate's: each shape's mean over the tables that the
                query reads, over their ancestors and over the rest, from ROOT/../state
  relations_least, relations_most
                the same, with each shape's least and greatest over those tables
  query         what a candidate's query says of its table with no row: where its columns come from, and what the
                query does with them, from ROOT/../named
  qv            what a candidate's table has against the tables its query reads: a share of its entries
                that each one has, its rows over theirs, its entries new to them. It reads the shapes
                that read the output, so a set that compares true and deranged outputs leaves it out
A term may end in `~WORD` to leave out the shapes whose name holds WORD, or `^WORD` to keep only those.
A set may end in `@K` to read only the shapes that tell gold from a mutant on K train tasks or more.
A fit reads one column for each set of columns equal on all its train rows, named by its shortest label.
"""
import argparse
import json
import pickle
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
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
# A shape's mean, least and greatest over the tables of a relation, at their places in a pooled list.
RELATION_NUMBERS = {'relations': 2, 'relations_least': 1, 'relations_most': 3}
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


HEX_VALUE = np.full(256, 255, dtype=np.uint8)
HEX_VALUE[np.frombuffer(b'0123456789abcdef', dtype=np.uint8)] = np.arange(16, dtype=np.uint8)
HEX_SHIFT = np.arange(60, -4, -4, dtype=np.uint64)


def names_in(folder, wanted):
    """The fields of each wanted id's line in a folder's names files, and the id of `(cardinality T)` where the folder has it. A line starts with its id in 16 hex digits and a
    tab, so a file's ids are read as arrays and only a wanted line is split. A run still going or stopped leaves its file with an unfinished end."""
    table = np.array(sorted(wanted), dtype=np.uint64)
    held = {}
    rows_key = None
    for path in sorted(folder.glob('names*.tsv.zst')):
        pieces = []
        with path.open('rb') as raw:
            reader = zstandard.ZstdDecompressor().stream_reader(raw, read_across_frames=True)
            try:
                while piece := reader.read(1 << 24):
                    pieces.append(piece)
            except zstandard.ZstdError:
                pass
        data = b''.join(pieces)
        del pieces
        marked = data.find(b'\t(cardinality T)\t')
        if marked >= 16:
            rows_key = int(data[marked - 16:marked], 16)
        text = np.frombuffer(data, dtype=np.uint8)
        ends = np.flatnonzero(text == 10)
        starts = np.concatenate(([0], ends[:-1] + 1)) if len(ends) else ends
        starts, ends = starts[ends - starts > 17], ends[ends - starts > 17]
        for first in range(0, len(starts), 1 << 20):
            at, end = starts[first:first + (1 << 20)], ends[first:first + (1 << 20)]
            digits = HEX_VALUE[text[at[:, None] + np.arange(16)]]
            good = (digits != 255).all(axis=1) & (text[at + 16] == 9)
            keys = (digits.astype(np.uint64) << HEX_SHIFT).sum(axis=1, dtype=np.uint64)
            for line_at, line_end in zip(at[good & place(keys, table)[1]].tolist(), end[good & place(keys, table)[1]].tolist()):
                parts = data[line_at:line_end].decode().split('\t')
                key = int(parts[0], 16)
                if len(parts) == 4 and key not in held:
                    held[key] = parts
    return held, rows_key


class Tally:
    """How many of the arrays given hold each id, with a bound on what stands unmerged."""

    def __init__(self):
        self.ids = np.zeros(0, dtype=np.uint64)
        self.counts = np.zeros(0, dtype=np.int64)
        self.held = []
        self.size = 0
        self.seen = False

    def add(self, ids):
        self.held.append(ids)
        self.size += len(ids)
        self.seen = True
        if self.size > 20_000_000:
            self.merge()

    def merge(self):
        if self.held:
            ids = np.concatenate([self.ids] + self.held)
            counts = np.concatenate([self.counts, np.ones(self.size, dtype=np.int64)])
            self.ids, inverse = np.unique(ids, return_inverse=True)
            self.counts = np.bincount(inverse.reshape(-1), weights=counts, minlength=len(self.ids)).astype(np.int64)
            self.held, self.size = [], 0

    def result(self):
        self.merge()
        return self.ids, self.counts


def every_entry(held, other):
    """A table's active shapes in order, with the least, the mean and the greatest of each."""
    ids = np.concatenate((held[0], other[0]))
    order = np.argsort(ids, kind='stable')
    return ids[order], {channel: np.concatenate((held[1], other[at]))[order] for at, channel in ((1, 'least'), (2, 'mean'), (3, 'most'))}


def told_apart(gold, mutant):
    """The shapes whose mean differs on two tables, where a shape only one of them has counts as differing."""
    in_mutant, hit = place(gold[0], mutant[0])
    ours, theirs = gold[1]['mean'][hit], mutant[1]['mean'][in_mutant[hit]]
    differs = (ours != theirs) & ~(np.isnan(ours) & np.isnan(theirs))
    return np.concatenate((gold[0][~hit], mutant[0][~place(mutant[0], gold[0])[1]], gold[0][hit][differs]))


def with_named(lists, others, folder, name, items):
    """Adds to a task's lists each table's named shapes from a folder of named lists, where its tables stand at the same places. Gives the lists of the
    candidates' query numbers."""
    path = folder / name
    if not path.exists():
        return {}
    head, named_lists, named_others = read_lists(path, graded=True)
    if [item['gold'] for item in head['items']] != [item['gold'] for item in items]:
        print('named file out of step', name, flush=True)
        return {}
    queries = {}
    for owner, held in named_lists.items():
        if isinstance(owner, str) and owner.endswith('/query'):
            queries[owner] = held
            continue
        if owner not in lists:
            lists[owner], others[owner] = held, named_others[owner]
            continue
        ids = np.concatenate((lists[owner][0], held[0]))
        order = np.argsort(ids, kind='stable')
        ids = ids[order]
        if (ids[1:] == ids[:-1]).any():
            raise ValueError(f'{folder} repeats a shape of {name} at {owner}')
        lists[owner] = (ids, np.concatenate((lists[owner][1], held[1]))[order])
        own, theirs = others[owner], named_others[owner]
        if not len(theirs[0]):
            continue
        ids = np.concatenate((own[0], theirs[0]))
        order = np.argsort(ids, kind='stable')
        if (ids[order][1:] == ids[order][:-1]).any():
            raise ValueError(f'{folder} repeats a shape of {name} at {owner}')
        # A list of the train outputs has only the train pairs, and a named shape is 0 past those.
        pairs = own[4].size // len(own[0]) if len(own[0]) else theirs[4].shape[1]
        at_pairs = np.concatenate((own[4].reshape(len(own[0]), pairs), theirs[4][:, :pairs]))[order]
        others[owner] = (ids[order], *(np.concatenate((own[at], theirs[at]))[order] for at in (1, 2, 3)), at_pairs)
    return queries


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


def share_same(own, use, there, hit):
    """The share of a table's entries that another table has with the same numbers, where `there` and `hit` are `place` of its ids in the other's."""
    if not len(own[0]):
        return 0.0
    here, there = np.flatnonzero(hit), there[hit]
    same = np.ones(len(here), dtype=bool)
    for channel in ('least', 'mean', 'most'):
        a, b = own[1][channel][here], use[1][channel][there]
        same &= (a == b) | (np.isnan(a) & np.isnan(b))
    return float(same.sum()) / len(own[0])


def relation_numbers(own, stable_count, new_stable, uses, read_tables, rows_key, assignments):
    """QV_NAMES's values for one candidate. `uses` holds the entries of the input and of each table its query reads,
    and `read_tables` those of the tables alone."""
    active = len(own[0])
    placed = [place(own[0], use[0]) for use in uses]
    new_active = active - int(np.logical_or.reduce([hit for _, hit in placed]).sum()) if uses else active
    shares = [share_same(own, use, there, hit) for use, (there, hit) in zip(uses, placed)]
    own_rows = rows_of(own, rows_key)
    ratios = [own_rows / rows for rows in (rows_of(table, rows_key) for table in read_tables) if rows]
    return (active, stable_count, stable_count / active if active else 0.0, new_stable, new_stable / stable_count if stable_count else 0.0, new_active, new_active / active if active else 0.0,
            len(read_tables), assignments or 0, max(shares, default=0.0), min(shares, default=0.0), max(ratios, default=0.0), min(ratios, default=0.0))


def place(ids, table):
    at = np.searchsorted(table, ids)
    at[at == len(table)] = 0
    hit = table[at] == ids if len(table) else np.zeros(len(ids), dtype=bool)
    return at, hit


def build(root, out):
    from block_fit import BlockMatrix
    root, out = Path(root), Path(out)
    (out / 'blocks').mkdir(parents=True, exist_ok=True)
    BlockMatrix.folder = out / 'blocks'
    maker = BlockMatrix
    parts = split_of()
    files = sorted((root / 'lists').glob('*.lists.zst'))
    print(len(files), 'task files', flush=True)
    # Which shapes tell gold from a mutant on three train tasks or more, on the true and on the null lists.
    told = {kind: Tally() for kind in ('stable', 'null', 'graded', 'null_graded')}
    every_shape = Tally()
    wide_root = root.parent / 'wide'
    state_root = root.parent / 'state'
    named_root = root.parent / 'named'
    more_root = root.parent / 'more'
    state_each_root = root.parent / 'state_each'
    query_seen = []
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
        query_lists = with_named(lists, others, named_root / 'lists', path.name, head['items'])
        with_named(null_lists, null_others, named_root / 'null', path.name, head['items'])
        with_named(lists, others, more_root / 'lists', path.name, head['items'])
        with_named(null_lists, null_others, more_root / 'null', path.name, head['items'])
        if query_lists:
            query_seen.append(np.unique(np.concatenate([held[0] for held in query_lists.values()])))
        seen = {kind: [] for kind in told}
        for item in head['items']:
            if item['last']:
                continue
            gold = item['gold']
            for mutant in item['mutants']:
                for kind, held, other in (('stable', lists, others), ('null', null_lists, null_others)):
                    a, b = held.get(gold), held.get(mutant['table'])
                    if a is not None and b is not None:
                        seen[kind].append(a[0][~place(a[0], b[0])[1]])
                        seen[kind].append(b[0][~place(b[0], a[0])[1]])
                        if len(other[gold][0]) or len(other[mutant['table']][0]):
                            seen['graded' if kind == 'stable' else 'null_graded'].append(told_apart(every_entry(a, other[gold]), every_entry(b, other[mutant['table']])))
        for kind, held in seen.items():
            if held:
                told[kind].add(np.unique(np.concatenate(held)))
        shapes = [entries[0] for tables in (lists, others, null_lists, null_others) for entries in tables.values()]
        if shapes:
            every_shape.add(np.unique(np.concatenate(shapes)))
        wide, wide_others = wide_lists(wide_root / 'lists', path.name, head['items'])
        wide_null, _ = wide_lists(wide_root / 'null', path.name, head['items'])
        apart = [entries[0] for held in (wide, wide_null) for entries in held.values()]
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
    columns = np.unique(np.concatenate([every_shape.result()[0]] + [held.result()[0] for held in told.values() if held.seen]))

    def every_id(held):
        return np.unique(np.concatenate(held)) if held else np.zeros(0, dtype=np.uint64)

    wide_columns, pair_columns = every_id(told_wide), every_id(pair_seen)
    family_columns = {family: every_id(held) for family, held in family_seen.items()}
    graph_columns, relation_columns, query_columns = every_id(graph_seen), every_id(relation_seen), every_id(query_seen)
    print('family columns', {family: len(held) for family, held in family_columns.items()}, 'graph', len(graph_columns), 'relations', len(relation_columns), 'query', len(query_columns), flush=True)
    column_tasks = np.zeros(len(columns), dtype=np.int32)
    for held in told.values():
        if held.seen:
            ids, counts = held.result()
            spots, hit = place(ids, columns)
            np.maximum.at(column_tasks, spots[hit], counts[hit])
    del told
    print('task-wide columns', len(wide_columns), 'pair columns', len(pair_columns), flush=True)
    # The names of the columns.
    names, flags, sizes = {}, {}, {}
    rows_key = 0
    wanted = set(columns.tolist())
    wanted_family = set(family_columns['input'].tolist()) | set(family_columns['output'].tolist())
    wanted_query = set(query_columns.tolist())
    held_on, found_key = names_in(root / 'lists', wanted | wanted_family)
    held_named, named_key = names_in(named_root / 'lists', wanted | wanted_query)
    held_more, more_key = names_in(more_root / 'lists', wanted)
    rows_key = next((key for key in (found_key, named_key, more_key) if key is not None), 0)
    for held in (held_on, held_named, held_more):
        for key, parts_line in held.items():
            if key in wanted:
                names[key], flags[key], sizes[key] = parts_line[1], int(parts_line[2]), int(parts_line[3])
    print('names found', len(names), 'of', len(wanted), flush=True)
    family_names, family_flags = {}, {}
    for key, parts_line in held_on.items():
        if key in wanted_family:
            family_names[key], family_flags[key] = parts_line[1], int(parts_line[2])
    wanted_state = set(family_columns['pairs'].tolist()) | set(graph_columns.tolist()) | set(relation_columns.tolist())
    if state_root.exists():
        for key, parts_line in names_in(state_root / 'lists', wanted_state)[0].items():
            family_names[key], family_flags[key] = parts_line[1], int(parts_line[2])
    for key, parts_line in held_named.items():
        if key in wanted_query:
            family_names[key] = parts_line[1]
    wanted_wide = set(wide_columns.tolist()) | set(pair_columns.tolist())
    wide_names, wide_flags = {}, {}
    if wide_root.exists():
        for key, parts_line in names_in(wide_root / 'lists', wanted_wide)[0].items():
            wide_names[key], wide_flags[key] = parts_line[1], int(parts_line[2])
    base_vocab = {}
    context_vocab = {}
    data = {}
    parents_root = root.parent / 'parents'
    # A row per example holds what some task tells apart.
    each_keep = column_tasks >= 1
    for split in ('train', 'dev'):
        rows = []
        mats = {name: maker() for name in ('base', 'stable', 'null', 'contingent', 'null_contingent', 'ctx', 'qv', 'mean', 'least', 'most', 'null_mean', 'null_least', 'null_most', 'wide', 'null_wide', 'pair_least', 'pair_mean', 'pair_most', 'each', 'null_each', 'graph', 'query', 'relations_each') + tuple(RELATION_NUMBERS)}
        example_of = []
        example_pair = []
        row_task = []
        first_example = []
        task_rows = {family: {channel: maker() for channel in ('stable', 'mean')} for family in FAMILIES}
        task_examples = {family: maker() for family in FAMILIES}
        task_train = []
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
            query_lists = with_named(lists, others, named_root / 'lists', path.name, head['items'])
            with_named(null_lists, null_others, named_root / 'null', path.name, head['items'])
            with_named(lists, others, more_root / 'lists', path.name, head['items'])
            with_named(null_lists, null_others, more_root / 'null', path.name, head['items'])
            wide, wide_others = wide_lists(wide_root / 'lists', path.name, head['items'])
            wide_null, _ = wide_lists(wide_root / 'null', path.name, head['items'])
            pair_numbers = wide_others.get('constant-values', (np.zeros(0, dtype=np.uint64),) + (np.zeros(0, dtype=np.float32),) * 3)
            pair_spots, pair_hit = place(pair_numbers[0], pair_columns)
            state, state_others, state_item = state_lists(state_root / 'lists', path.name)
            _, state_each_others, _ = state_lists(state_each_root / 'lists', path.name)
            first_example.append(examples_so_far)
            task_train.append(head['train'])
            example_count = head['train'] + head.get('test', 0)
            examples_so_far += example_count
            for family, owner in FAMILIES.items():
                held, other = (state, state_others) if family == 'pairs' else (lists, others)
                if owner not in held:
                    task_rows[family]['stable'].add([])
                    task_rows[family]['mean'].add([])
                    for _ in range(example_count):
                        task_examples[family].add([])
                    continue
                entries = other[owner]
                spots, hit = place(held[owner][0], family_columns[family])
                task_rows[family]['stable'].add(spots[hit], held[owner][1][hit])
                ids, numbers = every_entry(held[owner], entries)
                spots, hit = place(ids, family_columns[family])
                task_rows[family]['mean'].add(spots[hit], numbers['mean'][hit])
                graded_at, graded_hit = place(entries[0], family_columns[family])
                for pair in range(example_count):
                    held_here = entries[4].shape[1] > pair
                    values = entries[4][:, pair][graded_hit] if held_here else np.zeros(0, dtype=np.float32)
                    active = values != 0
                    task_examples[family].add(graded_at[graded_hit][active] if held_here else np.zeros(0, dtype=np.int64), values[active])
            read_true, read_true_others = parent_lists(parents_root / 'lists', path.name)
            read_null, read_null_others = parent_lists(parents_root / 'null', path.name)
            place_of = {listed['table']: listed['gold'] for listed in head['items']}
            place_of.update(head.get('places', {}))
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
                    example_of.extend([len(rows) - 1] * example_count)
                    example_pair.extend(range(example_count))
                    row_task.append(len(first_example) - 1)
                    state_at = state_item.get(item['form'])
                    graph = state.get(f'{state_at}/{j}/graph')
                    if graph is None:
                        mats['graph'].add([])
                    else:
                        spots, hit = place(graph[0], graph_columns)
                        mats['graph'].add(spots[hit], graph[1][hit])
                    relation_at, relation_values = [], {name: [] for name in RELATION_NUMBERS}
                    for number, relation in enumerate(RELATIONS):
                        held = state_others.get(f'{state_at}/{j}/{relation}')
                        if held is not None:
                            spots, hit = place(held[0], relation_columns)
                            relation_at.append(spots[hit] + number * len(relation_columns))
                            for name, place_at in RELATION_NUMBERS.items():
                                relation_values[name].append(held[place_at][hit])
                    for name in RELATION_NUMBERS:
                        if relation_at:
                            mats[name].add(np.concatenate(relation_at), np.concatenate(relation_values[name]))
                        else:
                            mats[name].add([])
                    # The values against the state's tables at each example, for the row of each.
                    for pair in range(example_count):
                        each_at, each_values = [], []
                        for number, relation in enumerate(RELATIONS):
                            each_held = state_each_others.get(f'{state_at}/{j}/{relation}')
                            if each_held is not None and each_held[4].shape[1] > pair:
                                spots, hit = place(each_held[0], relation_columns)
                                values = each_held[4][:, pair][hit]
                                active = values != 0
                                each_at.append(spots[hit][active] + number * len(relation_columns))
                                each_values.append(values[active])
                        if each_at:
                            mats['relations_each'].add(np.concatenate(each_at), np.concatenate(each_values))
                        else:
                            mats['relations_each'].add([])
                    held = query_lists.get(f'{at}/{j}/query')
                    if held is None:
                        mats['query'].add([])
                    else:
                        spots, hit = place(held[0], query_columns)
                        mats['query'].add(spots[hit], held[1][hit])
                    for kind, held_lists, held_others, held_read, held_read_others in (('stable', lists, others, read_true, read_true_others), ('null', null_lists, null_others, read_null, read_null_others)):
                        held = held_lists.get(table)
                        each_name = 'each' if kind == 'stable' else 'null_each'
                        channel_of = {'mean': 'mean', 'least': 'least', 'most': 'most'} if kind == 'stable' else {'mean': 'null_mean', 'least': 'null_least', 'most': 'null_most'}
                        if held is None:
                            for name in channel_of.values():
                                mats[name].add([])
                            mats[kind].add([])
                            for _ in range(example_count):
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
                        graded_ids, *_, at_pairs = held_others[table]
                        graded_spots, graded_hit = place(graded_ids, columns)
                        graded_hit = graded_hit & each_keep[graded_spots]
                        for pair in range(example_count):
                            held_here = at_pairs.shape[1] > pair
                            values = at_pairs[:, pair][graded_hit] if held_here else np.zeros(0, dtype=np.float32)
                            active = values != 0
                            place_at = graded_spots[graded_hit][active] if held_here else np.zeros(0, dtype=np.int64)
                            mats[each_name].add(place_at, values[active])
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
        nnz = {name: mats[name].count for name in mats}
        for name in mats:
            mats[name].write(out / 'blocks' / f'{split}.{name}.zst')
        for family in FAMILIES:
            task_rows[family]['stable'].write(out / 'blocks' / f'{split}.family.{family}.stable.zst')
            task_rows[family]['mean'].write(out / 'blocks' / f'{split}.family.{family}.mean.zst')
            task_examples[family].write(out / 'blocks' / f'{split}.family.{family}.each.zst')
        data[split] = dict(rows=rows, example_of=np.array(example_of, dtype=np.int64), index=dict(example_pair=np.array(example_pair, dtype=np.int64), row_task=np.array(row_task, dtype=np.int64), first_example=np.array(first_example, dtype=np.int64), task_train=np.array(task_train, dtype=np.int64), examples=examples_so_far))
        print(split, 'rows', len(rows), 'nnz', nnz, flush=True)
    for split in data:
        with (out / f'{split}.rows.pkl').open('wb') as sink:
            pickle.dump(data[split]['rows'], sink, protocol=4)
        with (out / f'{split}.example_of.pkl').open('wb') as sink:
            pickle.dump(data[split]['example_of'], sink, protocol=4)
        with (out / f'{split}.index.pkl').open('wb') as sink:
            pickle.dump(data[split]['index'], sink, protocol=4)
    meta = dict(columns=columns, column_tasks=column_tasks, names=names, flags=flags, sizes=sizes, base=base_vocab, ctx=context_vocab, wide_columns=wide_columns, pair_columns=pair_columns, wide_names=wide_names, wide_flags=wide_flags, family_columns=family_columns, family_names=family_names, family_flags=family_flags, graph_columns=graph_columns, relation_columns=relation_columns, query_columns=query_columns)
    meta['blocks'] = True
    meta['widths'] = dict({name: len(columns) for name in ('stable', 'null', 'contingent', 'null_contingent', 'mean', 'least', 'most', 'null_mean', 'null_least', 'null_most', 'each', 'null_each')}, base=len(base_vocab), ctx=len(context_vocab), qv=len(QV_NAMES), wide=len(wide_columns), null_wide=len(wide_columns), pair_least=len(pair_columns), pair_mean=len(pair_columns), pair_most=len(pair_columns), relations_each=len(RELATIONS) * len(relation_columns), graph=len(graph_columns), query=len(query_columns), **{name: len(RELATIONS) * len(relation_columns) for name in RELATION_NUMBERS})
    with (out / 'meta.pkl').open('wb') as sink:
        pickle.dump(meta, sink, protocol=4)
    code = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, cwd=ROOT_REPO).stdout.strip()
    (out / 'provenance.json').write_text(json.dumps(dict(lists=str(root), code=code, tasks={split: len({row[0] for row in data[split]['rows']}) for split in data}, columns=len(columns))))
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


def per_pair(spec):
    return any(raw.split('~')[0].split('^')[0] in ('TIOe', 'TIOe_null') for raw in spec.split('+'))


def channel_null(channel):
    return 'null' if channel == 'stable' else f'null_{channel}'


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
    # Past a shape's scope it has no entry: a shape that reads the output has a train pair's scope.
    for line in open_text(path):
        record = json.loads(line)
        if 'at' not in record:
            if 'train' in record:
                block += 1
                train = record['train']
            continue
        if block != 1:
            break
        slots = record['at'][:train] if record['reads'] & 2 else record['at']
        values = [0.0 if slot == 0 else (slot[0][0] / slot[0][1] if isinstance(slot[0], list) else float(slot[0])) for slot in slots if slot is not None]
        if not values:
            entries[record['shape']] = (0.0, float('nan'), float('nan'), float('nan'), [float('nan')] * len(slots) + [0.0] * (len(record['at']) - len(slots)))
        elif any(values):
            stable = values[0] if all(slot not in (0, None) and slot == slots[0] for slot in slots) else 0.0
            at = [float('nan') if slot is None else 0.0 if slot == 0 else (slot[0][0] / slot[0][1] if isinstance(slot[0], list) else float(slot[0])) for slot in slots] + [0.0] * (len(record['at']) - len(slots))
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
    import block_fit
    return block_fit.score(Path(out) / 'models', spec, name, vectors)


def fit(out, sets, filters, threads, fraction, seeds=5):
    import block_fit
    out = Path(out)
    meta = pickle.load((out / 'meta.pkl').open('rb'))
    if not meta.get('blocks'):
        raise SystemExit(f'{out} holds a store of an older form: build it again')
    return block_fit.fit(out, meta, sets, filters, threads, fraction, seeds)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['build', 'fit', 'compare', 'score'])
    parser.add_argument('paths', nargs='+')
    parser.add_argument('--sets', nargs='*', default=[])
    parser.add_argument('--filters', nargs='*', default=['rows', 'same'])
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--fraction', type=float, default=0.5)
    parser.add_argument('--seeds', type=int, default=5)
    parser.add_argument('--filter', default='rows')
    a = parser.parse_args()
    if a.command == 'build':
        build(a.paths[0], a.paths[1])
    elif a.command == 'compare':
        compare(a.paths[0], a.paths[1], a.paths[2], a.filter)
    elif a.command == 'score':
        score(a.paths[0], a.paths[1], a.filter, a.paths[2:])
    else:
        fit(a.paths[0], a.sets, a.filters, a.threads, a.fraction, a.seeds)


if __name__ == '__main__':
    main()
