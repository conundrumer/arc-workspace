#!/usr/bin/env python
"""Whether a model's row gives each first-version feature, on the tables that v1_dump.py wrote.

  v1_cover.py OUT.tsv --v1 DIR --blocks DIR --lists DIR [DIR ...] [--named DIR] [--more DIR] [--state DIR] [--skip FILE] [--form shape|place] [--base] [--no-mutants] [--counts FILE] [--one-binding] [--disposition FILE] [--tasks N] [--procs N]

A row is one table, of the ground-truth program or of a dumped mutant, at one train pair. Its columns are the table's shapes at that pair, from its list and its list in
`--named`, and the columns of a store's `base`, `qv`, `graph`, `relations` and `wide` at its candidate. `--skip` names tasks to leave out.

With `--base`, a row is one train pair of a task, its features are what the first version says of the input grid, the output and the changed cells, and
its columns are the shapes of the lists of `input` and `ex_output`, the task's constants, and of the pair family in the lists of `--state`.

A first-version feature can name a column by its place in its table, and another table by its identity. Under `--form shape`, the default, each such
feature is judged in the form a shape holds: over the bindings of one type signature, with another table written as how it stands to the owner, its
greatest value, and for a word, whether some binding gives that word. Under `--form place`, each is judged as it stands.

A feature is covered where its value at each row is a function of one column's value there, on the rows where the feature has a value, and that
function is monotone or changes few times along the column, so a few splits can read it. A feature with under 5 rows off its commonest value has low
support, and is not judged. Text that describes a column or a table has no number, so it is not judged. A table at another assignment than its list's is left out, and so is a table with no rows at the pair.

Each feature is judged again with its values shuffled across the rows where it has a value, so a reader can see how often the criterion passes by
chance: more columns and fewer rows raise that rate. `--counts` names a file of v1_column_counts.py, and then a column stands only where a store's train
rows hold an entry of it on at least a leaf's least count of rows, since no fit can read another. A column the file does not count stands.

A shape reads every column of a type, and a first-version feature reads those in a frame, so the two can differ where a table has two columns of a type.
Under `--one-binding`, a feature that names a column stands only on the rows where its table has one column of that type.

`--disposition` names a file that gives each group of features the sources of the columns that may give it, by the form the specification states it in:
`shape`, `named`, or a store's source. A line gives its feature's group.

A missing feature is also judged on the rows whose table has more columns than the feature names: `on wider tables` gives that status, since a shape over a
`project` of all of a table's columns has no entry on that table, and such a feature is missing for that reason alone.

With `--pairs`, a missing feature of at most 12 values is judged against pairs of the 40 columns that alone give its value on the most rows: `two columns`
is `yes` where its value at each row is a function of the two columns' values and the two make few distinct pairs of values, and `pair share` is the best pair's
share of the rows it gives, with its names in `pair`, and `one share` and `one` give the best single column. `two columns shuffled` is that status on the shuffled values. `--only FILE` judges only the features whose
status in that earlier output is `missing`.

A store's `relations`, `relations_least`, `relations_most`, `graph`, `query`, `base`, `qv` and `wide` have one value per candidate over its examples, so they can't give a feature that
varies across a candidate's examples at each row. A missing feature is also judged on one row per candidate, where its value is its mean over the candidate's rows and its
columns are these: `on candidates` gives that status.

A store's `contingent` holds about as many entries as its lists, and one group of two features reads it, so it stands only under `--contingent`.

`--why PATTERN` judges nothing. For each feature whose name the pattern finds, it prints its nearest single column, the feature's values at each of that column's values, and the first table rows where the two part, by task, item, candidate, ARC example and table.

`--aggregates` also gives each shape of a table's lists its least, mean and greatest over the ARC examples, as columns of their own, so a feature that states something across the examples can be judged against them. A shape that holds one value at every example has that value as all three.

`--places FILE` gives the upstream tables of each table under the spec, by task, table, `gold` or a mutant's number, upstream table and place (`parent` or `ancestor`), tab-separated. The first version takes every table of an instance as upstream once a query reads one of the instance's tables, tables that no query reads among them, and the spec takes the tables that the queries read. A first-version feature that names an upstream table then takes that table's place under the spec, and stands only where the spec puts that table upstream.

`--left-out FILE` names tables by task and name, tab-separated, whose table rows stand out of the judging: the spec gives such a table no value where the first version gives one, as on a table with a cell off its frame.

A run over many tasks holds too much to sort every entry. `--ids-out FILE` reads every list and writes one column of each set of columns with one source and equal entries, holding only a sum per column, and judges nothing. `--keep-ids FILE` then reads only those columns.

The store's train and dev rows both stand as candidates, the train rows first, so a task of either split in `--v1` is judged. A store with no dev rows gives train rows only. `--keep-ids` holds an entry's column as its place among the kept columns.

Each feature is judged over runs of whole shapes of at most about `BATCH` entries, and the results of the runs are combined, so a feature on many rows holds only a run's entries at a time.

A missing feature also has `equal share`, the most table rows on which one column equals it, with a table row of no entry at 0, and `equal`, that column's name. A feature of two values holding 0 and 1 reads a column as holding where it has an entry that is not 0, so a count can stand for a flag. One odd table keeps a whole column from `covered`, so these say how near it stands.

Streams one line per distinct feature, with the first version's metadata of the feature (what it reads, its aggregation level and what else it
reads) and the names that share its values.
"""
import argparse
import collections
import csv
import json
import multiprocessing as mp
import random
import re
import struct
import sys
import time
from pathlib import Path

import numpy as np
import zstandard

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_lists as g  # noqa: E402
from candidate import read_lists  # noqa: E402
from common import data_exists, open_text, read_pickle  # noqa: E402

TOKEN = re.compile(r'(?:\w+\.)?⟨c:[^⟩]*⟩')
TABLE = re.compile(r'⟨t:[^⟩]*⟩')
OWN_HOLE = re.compile(r'(?<!\.)\?\w')
OTHER_COLUMN = re.compile(r'(⟨t:[^⟩]*⟩)\.((?:\w+\.)?⟨c:[^⟩]*⟩)')
BASE_TYPES = {'⟨c:P⟩': 'Position', '⟨c:Col⟩': 'Color'}
DEFAULT = np.iinfo(np.int64).max
OTHER = 1 << 63
MIN_DATA = 20
PAIR_COLUMNS = 40
PAIR_VALUES = 12
# The ids of a shape's least, mean and greatest over the examples are its own id with one of these bits set.
AGGREGATE_SALTS = [np.uint64(0x5A1E000000000001), np.uint64(0x3EA0000000000002), np.uint64(0x7051000000000003)]
CANDIDATE_SOURCES = ['relations', 'relations_least', 'relations_most', 'graph', 'query', 'base', 'qv', 'wide']
JUDGE = None


def judge(item):
    return JUDGE(item)


BLOCK = 1 << 24
# A batch of per-feature work holds the entries of whole shapes, about this many at most.
BATCH = 1 << 21


def has_source(blocks, name):
    return any((Path(blocks) / 'blocks' / f'{split}.{name}.zst').exists() for split in ('train', 'dev'))


def read_source(blocks, name, wanted, dev_first):
    """The rows of a store's source at the candidates in `wanted`: candidate -> columns, values. Rows from `dev_first` on are in the dev file, and the rows before it in the train file."""
    held = {}
    for split, shift in (('train', 0), ('dev', dev_first)):
        here = {at - shift for at in wanted if at >= shift and (split == 'dev' or at < dev_first)}
        if here:
            held.update({at + shift: found for at, found in read_file(Path(blocks) / 'blocks' / f'{split}.{name}.zst', here).items()})
    return held


def read_file(path, wanted):
    """The rows of one source file at the places in `wanted`: place -> columns, values."""
    reader = zstandard.ZstdDecompressor().stream_reader(open(path, 'rb'), read_across_frames=True)

    def read(n):
        out = b''
        while len(out) < n:
            piece = reader.read(n - len(out))
            if not piece:
                break
            out += piece
        return out

    held, first = {}, 0
    while True:
        head = read(12)
        if len(head) < 12:
            return held
        rows_here, entries = struct.unpack('<IQ', head)
        lengths = np.frombuffer(read(4 * rows_here), dtype=np.uint32)
        columns = np.cumsum(np.frombuffer(read(4 * entries), dtype=np.int32).astype(np.int64))
        values = np.frombuffer(read(4 * entries), dtype=np.float32)
        ends = np.cumsum(lengths)
        for at in range(rows_here):
            if first + at in wanted:
                start = ends[at - 1] if at else 0
                held[first + at] = (columns[start:ends[at]], values[start:ends[at]])
        first += rows_here


def gather(table, index):
    """`table[index]` with the index taken in blocks, so that no copy of it as int64 stands."""
    out = np.empty(len(index), dtype=table.dtype)
    for at in range(0, len(index), BLOCK):
        out[at:at + BLOCK] = table[index[at:at + BLOCK]]
    return out


def count_of(index, size):
    """`np.bincount(index, minlength=size)` over blocks."""
    total = np.zeros(size, dtype=np.int64)
    for at in range(0, len(index), BLOCK):
        total += np.bincount(index[at:at + BLOCK], minlength=size)
    return total


def sort_entries(row, shape, val, size):
    """The entries ordered by shape, then value, then row, as sorted in blocks of whole shapes. `shape` holds numbers below `size`."""
    ends = np.cumsum(count_of(shape, size))
    out_row, out_shape, out_val = np.empty_like(row), np.empty_like(shape), np.empty_like(val)
    first, at = 0, 0
    while first < size:
        last = min(max(int(np.searchsorted(ends, at + BLOCK, side='right')), first + 1), size)
        end = int(ends[last - 1])
        if end > at:
            here = np.flatnonzero((shape >= first) & (shape < last))
            order = here[np.lexsort((row[here], val[here], shape[here]))]
            out_row[at:end], out_shape[at:end], out_val[at:end] = row[order], shape[order], val[order]
        first, at = last, end
    return out_row, out_shape, out_val


def number(value):
    return float(value) if isinstance(value, (bool, int, float)) else None


def by_table(pair):
    """A pair's values as {table: {feature: value}}."""
    out = collections.defaultdict(dict)
    for key, value in pair.items():
        name, _, feature = key.partition('|')
        out[name][feature] = value
    return out


def collect(at, name, types_of, tables, form, out, row, coordinates, coordinate_of, one_binding=False, places=None):
    """Adds to `out` a row's values of the features of one table at one pair, given as {feature: value}. `types_of` gives each table's column tokens' types by its name. Under
    `one_binding`, a feature that names a column stands only where its table has one column of that type. `places` gives the upstream tables under the spec with their
    places, and a feature that names a table the first version puts upstream and the spec does not stands out. Returns the count of features that stand out so."""
    own = types_of.get(name, {})
    of_type = collections.Counter(own.values())
    group_columns = [token for token, ty in own.items() if ty in ('Ident', 'Color') or token.startswith('key.')]
    place_of = {}
    pooled = {}
    words = {}
    for feature, value in at.items():
        if feature.endswith(' describe') and isinstance(value, str) and TABLE.fullmatch(feature[:-len(' describe')]):
            place = value.split(' ')[0].lstrip('[')
            place_of[feature[:-len(' describe')]] = place if place in ('parent', 'ancestor') else 'table'
    not_upstream = set()
    if places is not None:
        for token, place in list(place_of.items()):
            if place in ('parent', 'ancestor'):
                if tables.get(token, '') in places:
                    place_of[token] = places[tables[token]]
                else:
                    not_upstream.add(token)
    dropped = 0
    for feature, value in at.items():
        if value is None or feature.endswith(' describe'):
            continue
        if not_upstream and any(token in not_upstream for token in TABLE.findall(feature)):
            dropped += 1
            continue
        # A table whose one group column is the column of the cells gives each cell a group of its own. No part takes a column as its own key.
        if 'of its Ident, Color and key columns' in feature and len(group_columns) == 1 and group_columns[0] in feature:
            continue
        if form == 'place':
            out[feature][row] = value
            coordinate_of.setdefault(feature, coordinates.get(feature))
            continue

        def of_other(match):
            other = types_of.get(tables.get(match[1], ''), {})
            return f'{place_of.get(match[1], "table")}.?{other.get(match[2], "")}'

        if one_binding and any(of_type[own.get(match[0], '')] > 1 for match in TOKEN.finditer(OTHER_COLUMN.sub('', feature))):
            continue
        shape = OTHER_COLUMN.sub(of_other, feature)
        shape = TOKEN.sub(lambda match: '?' + own.get(match[0], BASE_TYPES.get(match[0], '')), shape)
        shape = TABLE.sub(lambda match: place_of.get(match[0], 'table'), shape)
        coordinate_of.setdefault(shape, coordinates.get(feature))
        value_number = number(value)
        if value_number is not None:
            held = pooled.get(shape)
            pooled[shape] = value_number if held is None else max(held, value_number)
        else:
            words.setdefault(shape, set()).add(str(value))
    for shape, value in pooled.items():
        out[shape][row] = value
    for shape, held in words.items():
        for word in held:
            out[f'{shape} :{word}'][row] = 1.0
            coordinate_of.setdefault(f'{shape} :{word}', coordinate_of.get(shape))
        out[('words', shape)][row] = held
    return dropped


def main():
    global JUDGE
    parser = argparse.ArgumentParser()
    parser.add_argument('out')
    parser.add_argument('--v1', required=True)
    parser.add_argument('--blocks', required=True)
    parser.add_argument('--lists', nargs='+', required=True)
    parser.add_argument('--named')
    parser.add_argument('--more')
    parser.add_argument('--state')
    parser.add_argument('--skip')
    parser.add_argument('--form', choices=['shape', 'place'], default='shape')
    parser.add_argument('--base', action='store_true')
    parser.add_argument('--no-mutants', action='store_true')
    parser.add_argument('--counts')
    parser.add_argument('--one-binding', action='store_true')
    parser.add_argument('--disposition')
    parser.add_argument('--pairs', action='store_true')
    parser.add_argument('--only')
    parser.add_argument('--why')
    parser.add_argument('--contingent', action='store_true')
    parser.add_argument('--ids-out')
    parser.add_argument('--left-out')
    parser.add_argument('--places')
    parser.add_argument('--aggregates', action='store_true')
    parser.add_argument('--keep-ids')
    parser.add_argument('--tasks', type=int)
    parser.add_argument('--procs', type=int, default=3)
    args = parser.parse_args()
    begun_at = time.time()
    blocks = Path(args.blocks)
    meta = read_pickle(blocks / 'meta.pkl')
    # The candidates of the train split come first, and those of the dev split follow.
    candidates = list(read_pickle(blocks / 'train.rows.pkl'))
    dev_first = len(candidates)
    dev_examples_first = len(read_pickle(blocks / 'train.example_of.pkl'))
    if data_exists(blocks / 'dev.rows.pkl'):
        candidates += list(read_pickle(blocks / 'dev.rows.pkl'))
    candidate_of = {(row[0], row[1], row[2]): at for at, row in enumerate(candidates)}
    extra = {}
    extra['base'] = {place: 'base:' + key for key, place in meta['base'].items()}
    extra['qv'] = {place: 'qv:' + name for place, name in enumerate(g.QV_NAMES)}
    extra['graph'] = {place: 'graph:' + meta['family_names'].get(int(key), '') for place, key in enumerate(meta['graph_columns'])}
    extra['relations'] = {place: relation + ':' + meta['family_names'].get(int(key), '') for place, (relation, key) in enumerate((r, k) for r in g.RELATIONS for k in meta['relation_columns'])}
    extra['wide'] = {place: 'wide:' + meta['wide_names'].get(int(key), '') for place, key in enumerate(meta['wide_columns'])}
    # Its place stands either way, so a column's number does not change with the option.
    extra['contingent'] = {place: 'contingent:' + meta['names'].get(int(key), '') for place, key in enumerate(meta['columns'])} if args.contingent else {}
    for pool in ('relations_least', 'relations_most'):
        if has_source(blocks, pool):
            extra[pool] = {place: pool + ':' + name.split(':', 1)[0] + ':' + name.split(':', 1)[1] for place, name in extra['relations'].items()}
    if has_source(blocks, 'relations_each'):
        extra['relations_each'] = {place: 'each:' + name for place, name in extra['relations'].items()}
    offset = {source: OTHER + (place << 32) for place, source in enumerate(extra)}
    name_of = {offset[source] + column: name for source, names in extra.items() for column, name in names.items()}
    skipped = set(Path(args.skip).read_text().split()) if args.skip else set()
    paths = sorted(path for path in Path(args.v1).glob('*.json.zst') if path.name.split('.')[0] not in skipped)
    in_store = {row[0] for row in candidates}
    paths = [path for path in paths if path.name.split('.')[0] in in_store and any((Path(folder) / (path.name.split('.')[0] + '.lists.zst')).exists() for folder in args.lists)]
    paths = paths[:args.tasks] if args.tasks else paths
    tasks = {path.name.split('.')[0] for path in paths}
    extras = {} if args.base else {source: read_source(blocks, source, {at for key, at in candidate_of.items() if key[0] in tasks}, dev_first) for source in extra if source != 'relations_each' and (source != 'contingent' or args.contingent)}
    # A candidate's rows of `relations_each` stand together, one per example.
    each_rows, first_each = {}, None
    if 'relations_each' in extra and not args.base:
        example_of = np.asarray(read_pickle(blocks / 'train.example_of.pkl'))
        if len(candidates) > dev_first:
            example_of = np.concatenate((example_of, np.asarray(read_pickle(blocks / 'dev.example_of.pkl')) + dev_first))
        first_each = np.searchsorted(example_of, np.arange(len(candidates)))
        wanted = np.isin(example_of, np.array([at for key, at in candidate_of.items() if key[0] in tasks]))
        each_rows = read_source(blocks, 'relations_each', set(np.flatnonzero(wanted).tolist()), dev_examples_first)
    print(f'sources read {time.time() - begun_at:.0f}s', flush=True)
    rows = 0
    row_of, shape_of, value_of = [], [], []
    features = collections.defaultdict(dict)
    coordinate_of = {}
    started = time.time()
    used = 0
    other_assignment = [0]
    no_rows = [0]
    row_width = []
    row_candidate = []
    row_info = []

    keep_ids = np.load(args.keep_ids) if args.keep_ids else None
    left_out = set()
    if args.left_out:
        with open(args.left_out) as lines:
            left_out = {tuple(line.split('\t')[:2]) for line in lines}
    left_out_rows = [0]
    places = {}
    if args.places:
        with open(args.places) as lines:
            for line in lines:
                task_name, table_name, variant, other, place = line.rstrip('\n').split('\t')
                held = places.setdefault((task_name, table_name, variant), {})
                if other:
                    held[other] = place
    not_upstream_values = [0]
    seen_ids, seen_sums = [], []

    def take(row, ids, values):
        """A row's entries, of the kept columns where some are kept. Where the columns are kept by `--keep-ids` and the run judges, an entry's column is its place among them."""
        if keep_ids is not None:
            at = np.searchsorted(keep_ids, ids)
            at[at == len(keep_ids)] = 0
            found = keep_ids[at] == ids
            ids, values = (at[found].astype(np.int32) if not args.ids_out else ids[found]), values[found]
        row_of.append(np.full(len(ids), row, dtype=np.int32))
        shape_of.append(ids)
        # A copy, since a list's values are a view that would hold its whole file in memory.
        value_of.append(np.array(values, dtype=np.float32))

    def add_list(row, held, other, at):
        """A row's entries from a table's list at a pair."""
        take(row, held[0], np.asarray(held[1]))
        if len(other[0]) and other[4].shape[1] > at:
            values = other[4][:, at]
            active = values != 0
            take(row, other[0][active], values[active])
        if args.aggregates:
            for place, salt in enumerate(AGGREGATE_SALTS, 1):
                take(row, held[0] ^ salt, np.asarray(held[1]))
                if len(other[0]):
                    active = other[place] != 0
                    take(row, other[0][active] ^ salt, np.asarray(other[place])[active])

    def sum_entries():
        """Each column's sum of its entries' hashes, for the entries read since the last call. Two columns with equal entries have equal sums."""
        if not row_of:
            return
        ids = np.concatenate(shape_of)
        values = np.nan_to_num(np.concatenate(value_of), nan=-7.77e7)
        places = np.concatenate(row_of).astype(np.uint64)
        row_of.clear(), shape_of.clear(), value_of.clear()
        present = values != 0
        ids, values, places = ids[present], values[present], places[present]
        mixed = (places * np.uint64(0x9E3779B97F4A7C15)) ^ (values.astype(np.float32).view(np.uint32).astype(np.uint64) * np.uint64(0xC2B2AE3D27D4EB4F))
        mixed = (mixed ^ (mixed >> np.uint64(29))) * np.uint64(0xBF58476D1CE4E5B9)
        unique, inverse = np.unique(ids, return_inverse=True)
        total = np.zeros(len(unique), dtype=np.uint64)
        np.add.at(total, inverse, mixed)
        seen_ids.append(unique)
        seen_sums.append(total)

    for path in paths:
        if args.ids_out:
            sum_entries()
        with open_text(path) as lines:
            data = json.load(lines)
        task = data['task']
        file = next((Path(folder) / f'{task}.lists.zst' for folder in args.lists if (Path(folder) / f'{task}.lists.zst').exists()), None)
        if file is None:
            continue
        head, lists, others = read_lists(file, graded=True)
        named_lists, named_others = {}, {}
        if args.named and (Path(args.named) / f'{task}.lists.zst').exists():
            named_lists, named_others = read_lists(Path(args.named) / f'{task}.lists.zst', graded=True)[1:]
        more_lists, more_others = {}, {}
        if args.more and (Path(args.more) / f'{task}.lists.zst').exists():
            more_lists, more_others = read_lists(Path(args.more) / f'{task}.lists.zst', graded=True)[1:]
        coordinates = data.get('coordinates', {})
        tables = data.get('tables', {})
        types_of = {name: {token: ty for token, ty in columns} for name, columns in data['columns'].items()}
        used += 1
        if args.base:
            state_lists, state_others = {}, {}
            if args.state and (Path(args.state) / f'{task}.lists.zst').exists():
                state_lists, state_others = read_lists(Path(args.state) / f'{task}.lists.zst', graded=True)[1:]
            for at, pair in enumerate(data.get('base', [])):
                row = rows
                rows += 1
                for owner in ('input', 'ex_output', 'constants'):
                    if owner in lists:
                        add_list(row, lists[owner], others[owner], at)
                    if owner in named_lists:
                        add_list(row, named_lists[owner], named_others[owner], at)
                if 'pair' in state_lists:
                    add_list(row, state_lists['pair'], state_others['pair'], at)
                split_pair = by_table(pair)
                for owner in ('input', 'output', 'changed'):
                    # Every table of this form names its owner, so the owner stands in the feature's name.
                    renamed = {f'{owner}: {feature}': value for feature, value in split_pair.get(owner, {}).items()}
                    collect(renamed, owner, {}, {}, args.form, features, row, {}, coordinate_of)
            continue
        mutants = collections.defaultdict(list)
        if not args.no_mutants:
            for mutant in data.get('mutants', []):
                if 'pairs' in mutant:
                    mutants[(mutant['form'], mutant['mutant'])].append(mutant)

        gold_pairs = [by_table(pair) for pair in data['pairs']]

        def add_rows(pairs, name, place, candidate, own_types, query_list=None, variant='gold'):
            nonlocal rows
            own_named = (named_lists[place], named_others[place]) if place in named_lists else None
            for at, pair in enumerate(pairs):
                table_at = pair.get(name)
                if table_at is None:
                    continue
                if (task, name) in left_out:
                    left_out_rows[0] += 1
                    continue
                # A table at another assignment than its list's reads other rows, so it says nothing of its list's columns.
                if table_at.get('rows') not in (None, head['train_rows'][place][at]):
                    other_assignment[0] += 1
                    continue
                # On a table with no rows a first-version feature says only that its claim holds of nothing, and `(cardinality T)` gives that.
                if table_at.get('rows') == 0:
                    no_rows[0] += 1
                    continue
                row = rows
                rows += 1
                row_width.append(len(own_types.get(name, {})))
                row_candidate.append(candidate)
                row_info.append((task, candidates[candidate][1], candidates[candidate][2], at, name))
                add_list(row, lists[place], others[place], at)
                if own_named:
                    add_list(row, own_named[0], own_named[1], at)
                if place in more_lists:
                    add_list(row, more_lists[place], more_others[place], at)
                if query_list in named_lists:
                    add_list(row, named_lists[query_list], named_others[query_list], at)
                for source, by in extras.items():
                    if candidate in by:
                        columns, values = by[candidate]
                        take(row, np.uint64(offset[source]) + columns.astype(np.uint64), values)
                if first_each is not None and int(first_each[candidate]) + at in each_rows:
                    columns, values = each_rows[int(first_each[candidate]) + at]
                    take(row, np.uint64(offset['relations_each']) + columns.astype(np.uint64), values)
                if not args.ids_out:
                    not_upstream_values[0] += collect(table_at, name, own_types, tables, args.form, features, row, coordinates, coordinate_of, args.one_binding, places.get((task, name, variant)) if args.places else None)

        for item_at, item in enumerate(head['items']):
            name, place = item['table'], item['gold']
            if place not in lists or (task, item_at, 0) not in candidate_of:
                continue
            add_rows(gold_pairs, name, place, candidate_of[(task, item_at, 0)], types_of, f'{item_at}/0/query')
            for j, mutant in enumerate(item['mutants'], 1):
                for held in mutants.get((item['form'], mutant['mutant']), []):
                    if mutant['table'] in lists and (task, item_at, j) in candidate_of:
                        own_types = dict(types_of)
                        own_types.update({key: {token: ty for token, ty in columns} for key, columns in held['columns'].items()})
                        add_rows([by_table(pair) for pair in held['pairs']], name, mutant['table'], candidate_of[(task, item_at, j)], own_types, f'{item_at}/{j}/query', str(mutant['mutant']))
    del extras, each_rows
    print(f'table rows left out by name {left_out_rows[0]}', flush=True)
    if args.places:
        print(f'first-version values that name a table the spec does not put upstream {not_upstream_values[0]}', flush=True)
    if args.ids_out:
        sum_entries()
        ids = np.concatenate(seen_ids)
        sums = np.concatenate(seen_sums)
        unique_ids, inverse = np.unique(ids, return_inverse=True)
        total = np.zeros(len(unique_ids), dtype=np.uint64)
        np.add.at(total, inverse, sums)
        del ids, sums, inverse, seen_ids, seen_sums
        wanted = set(unique_ids.tolist())
        for folder in [args.lists[-1]] + ([args.named] if args.named else []) + ([args.more] if args.more else []) + ([args.state] if args.state else []):
            for key, parts in g.names_in(Path(folder), wanted)[0].items():
                name_of[key] = parts[1]
        source_at = {offset[source] + column: source for source, names in extra.items() for column in names}

        def kind_of(key):
            name = name_of.get(key, '')
            return source_at.get(key) or ('named' if name.startswith('(named') else 'query' if name.startswith('(query') else 'shape')

        first = {}
        for key, held in zip(unique_ids.tolist(), total.tolist()):
            signature = (kind_of(key), held)
            other = first.get(signature)
            if other is None or len(name_of.get(key, '')) < len(name_of.get(other, '')):
                first[signature] = key
        kept = np.array(sorted(first.values()), dtype=np.uint64)
        np.save(args.ids_out, kept)
        print(f'columns {len(unique_ids)} one of each {len(kept)}', flush=True)
        return
    row = np.concatenate(row_of)
    del row_of
    ids = np.concatenate(shape_of)
    del shape_of
    val = np.concatenate(value_of)
    del value_of
    val = np.nan_to_num(val, nan=-7.77e7)
    keep = val != 0
    row, ids, val = row[keep], ids[keep], val[keep]
    del keep
    # A word's column is 0 where the feature has a value there and another word.
    for key in [key for key in features if isinstance(key, tuple)]:
        at = features.pop(key)
        for word in {word for words in at.values() for word in words}:
            column = features[f'{key[1]} :{word}']
            for own in at:
                column.setdefault(own, 0.0)
    if keep_ids is not None and not args.ids_out:
        # The entries hold their column's place among the kept columns, so the columns that stand are those with an entry.
        present = count_of(ids, len(keep_ids)) > 0
        unique_ids = keep_ids[present]
        shape = gather((np.cumsum(present) - 1).astype(np.int32), ids)
    else:
        unique_ids, shape = np.unique(ids, return_inverse=True)
        shape = shape.astype(np.int32)
    del ids
    wanted = set(unique_ids.tolist())
    if args.aggregates:
        wanted |= {key ^ int(salt) for key in list(wanted) for salt in AGGREGATE_SALTS}
    for folder in [args.lists[-1]] + ([args.named] if args.named else []) + ([args.more] if args.more else []) + ([args.state] if args.state else []):
        for key, parts in g.names_in(Path(folder), wanted)[0].items():
            name_of[key] = parts[1]
    if args.aggregates:
        for key in unique_ids.tolist():
            for word, salt in zip(('least', 'mean', 'most'), AGGREGATE_SALTS):
                if key ^ int(salt) in name_of and key not in name_of:
                    name_of[key] = f'{word}:{name_of[key ^ int(salt)]}'
    source_at = {offset[source] + column: source for source, names in extra.items() for column in names}

    def source_of(key):
        if key in source_at:
            return source_at[key]
        name = name_of.get(key, '')
        return 'named' if name.startswith('(named') else 'query' if name.startswith('(query') else 'shape'

    sources = [source_of(int(key)) for key in unique_ids.tolist()]
    # Columns of one source that give one partition of the rows stand as one, so each feature tests fewer columns.
    row, shape, val = sort_entries(row, shape, val, len(unique_ids))
    new_group = np.concatenate(([True], (shape[1:] != shape[:-1]) | (val[1:] != val[:-1])))
    rank = np.cumsum(new_group, dtype=np.int32)
    rank -= 1
    starts = np.flatnonzero(np.concatenate(([True], shape[1:] != shape[:-1])))
    ends = np.concatenate((starts[1:], [len(shape)]))
    signature = set()
    keep_shape = np.zeros(len(unique_ids), dtype=bool)
    readable = np.ones(len(unique_ids), dtype=bool)
    if args.counts:
        held = np.load(args.counts)
        readable = np.isin(unique_ids, held['ids'][held['counts'] >= MIN_DATA]) | ~np.isin(unique_ids, held['ids'])
        print(f'columns a fit can read {int(readable.sum())} of {len(unique_ids)}', flush=True)
    for start, end in zip(starts.tolist(), ends.tolist()):
        key = hash((sources[shape[start]], row[start:end].tobytes(), (rank[start:end] - rank[start]).tobytes()))
        if readable[shape[start]] and key not in signature:
            signature.add(key)
            keep_shape[shape[start]] = True
    print(f'columns {len(unique_ids)} kept {int(keep_shape.sum())}', flush=True)
    kept = gather(keep_shape, shape)
    row, shape, val = row[kept], shape[kept], val[kept]
    del signature, rank, new_group, kept
    new_group = np.concatenate(([True], (shape[1:] != shape[:-1]) | (val[1:] != val[:-1])))
    # Each kept shape's entries, its column's place among the kept columns, each entry's group of equal values, and each row's entries.
    entry_shape_start = np.flatnonzero(np.concatenate(([True], shape[1:] != shape[:-1])))
    entry_shape_end = np.append(entry_shape_start[1:], len(shape))
    columns_here = shape[entry_shape_start]
    rank_of_column = np.full(len(unique_ids), -1, dtype=np.int32)
    rank_of_column[columns_here] = np.arange(len(columns_here), dtype=np.int32)
    group_of_entry = np.cumsum(new_group, dtype=np.int32)
    group_of_entry -= 1
    del new_group
    groups_of_shape = group_of_entry[entry_shape_end - 1] - group_of_entry[entry_shape_start] + 1
    row_entries = count_of(row, rows)
    row_first = np.concatenate(([0], np.cumsum(row_entries)))
    entry_of_row = np.empty(len(row), dtype=np.int32)
    low_row = 0
    while low_row < rows:
        high_row = min(max(int(np.searchsorted(row_first, row_first[low_row] + BLOCK, side='right')) - 1, low_row + 1), rows)
        here = np.flatnonzero((row >= low_row) & (row < high_row))
        entry_of_row[row_first[low_row]:row_first[high_row]] = here[np.argsort(row[here], kind='stable')]
        low_row = high_row
    # Whole shapes in turn, each run of them holding about `BATCH` entries.
    batch_ends = []
    at_shape = 0
    while at_shape < len(entry_shape_start):
        last_shape = max(int(np.searchsorted(entry_shape_end, entry_shape_start[at_shape] + BATCH, side='right')), at_shape + 1)
        batch_ends.append((int(entry_shape_start[at_shape]), int(entry_shape_end[last_shape - 1])))
        at_shape = last_shape
    total = len(unique_ids)
    source_here = np.array([sources[at] for at in columns_here.tolist()])
    groups = []
    if args.disposition:
        with open(args.disposition) as lines:
            for line in list(lines)[1:]:
                parts = line.rstrip('\n').split('\t')
                groups.append((parts[0], re.compile(parts[1]), np.isin(source_here, parts[4].split(','))))

    def group_of(feature):
        return next(((name, mask) for name, pattern, mask in groups if pattern.search(feature)), ('', None))

    print(f'tasks {used} rows {rows} left out at another assignment {other_assignment[0]} with no rows {no_rows[0]} columns {int(keep_shape.sum())} entries {len(row)} features {len(features)} read {time.time() - started:.0f}s', flush=True)

    def key_of(value):
        return (0, float(value)) if isinstance(value, (bool, int, float)) else (1, str(value))

    def entry_batches(rows_here):
        """The entries on some rows as runs of whole shapes, each in the order of the groups, with about `BATCH` entries at most in a run. Through the rows' own entries where they are few, since a look at every entry costs more."""
        total_here = int(row_entries[rows_here].sum())
        if not total_here:
            return
        if total_here * 8 > len(row):
            defined = np.zeros(rows, dtype=bool)
            defined[rows_here] = True
            for first, last in batch_ends:
                held = np.flatnonzero(defined[row[first:last]])
                if len(held):
                    yield held + first
            return
        held = np.concatenate([entry_of_row[row_first[own]:row_first[own + 1]] for own in rows_here.tolist()])
        held.sort()
        edges = np.flatnonzero(shape[held[1:]] != shape[held[:-1]]) + 1
        first = 0
        while first < len(held):
            last = first + BATCH
            if last >= len(held):
                last = len(held)
            else:
                at = int(np.searchsorted(edges, last, side='right'))
                if at and edges[at - 1] > first:
                    last = int(edges[at - 1])
                elif at < len(edges):
                    last = int(edges[at])
                else:
                    last = len(held)
            yield held[first:last].astype(np.int64)
            first = last

    def by_pairs(feature, at):
        """Whether two columns together give the feature's value: the status, the best pair's share of the rows and its names, and the best single column's share and name."""
        counts = collections.Counter(key_of(value) for value in at.values())
        keys = {key: place for place, key in enumerate(sorted(counts))}
        k = len(keys)
        if k < 2 or k > PAIR_VALUES:
            return '', '', '', '', ''
        rows_here = np.fromiter(at, dtype=np.int64, count=len(at))
        rows_here.sort()
        c = np.full(rows, -1, dtype=np.int64)
        c[list(at)] = [keys[key_of(value)] for value in at.values()]
        n = len(rows_here)
        in_all = np.bincount(c[rows_here], minlength=k)[None, :]
        shapes_here, bests = [], []
        for entries in entry_batches(rows_here):
            groups, classes_at = group_of_entry[entries], c[row[entries]]
            starts = np.flatnonzero(np.concatenate(([True], groups[1:] != groups[:-1])))
            touched = np.repeat(np.arange(len(starts)), np.diff(np.append(starts, len(entries))))
            table = np.bincount(touched * k + classes_at, minlength=len(starts) * k).reshape(len(starts), k)
            members = table.sum(axis=1)
            most = np.where(members >= 2, table.max(axis=1), 0)
            shape_of = rank_of_column[shape[entries[starts]]]
            firsts = np.flatnonzero(np.concatenate(([True], shape_of[1:] != shape_of[:-1])))
            in_rest = in_all - np.add.reduceat(table, firsts, axis=0)
            shapes_here.append(shape_of[firsts])
            bests.append(np.add.reduceat(most, firsts) + in_rest.max(axis=1))
        if not shapes_here:
            return 'no', 0.0, '', 0.0, ''
        shape_here = np.concatenate(shapes_here)
        best = np.concatenate(bests)
        best = np.where(groups_of_shape[shape_here] <= PAIR_VALUES, best, -1)
        allowed = group_of(feature)[1]
        if allowed is not None:
            best = np.where(allowed[shape_here], best, -1)
        order = np.argsort(-best, kind='stable')[:PAIR_COLUMNS]
        chosen = order[best[order] >= 0]
        if len(chosen) < 2:
            return 'no', 0.0, '', 0.0, ''
        name_at = lambda at_chosen: name_of.get(int(unique_ids[columns_here[shape_here[chosen[at_chosen]]]]), '?')
        one_share = round(float(best[chosen[0]]) / n, 3)
        place_of = np.full(rows, -1, dtype=np.int64)
        place_of[rows_here] = np.arange(n)
        classes = c[rows_here]
        dense = []
        for at_chosen in chosen.tolist():
            first, last = int(entry_shape_start[shape_here[at_chosen]]), int(entry_shape_end[shape_here[at_chosen]])
            own = np.flatnonzero(place_of[row[first:last]] >= 0) + first
            codes = np.zeros(n, dtype=np.int64)
            codes[place_of[row[own]]] = group_of_entry[own] - group_of_entry[first] + 1
            dense.append(np.unique(codes, return_inverse=True)[1])
        limit = max(4 * k, 12)
        found, top, top_pair = False, -1, None
        for a in range(len(chosen)):
            for b in range(a + 1, len(chosen)):
                wide = int(dense[b].max()) + 1
                cells = (int(dense[a].max()) + 1) * wide
                joint = np.bincount((dense[a] * wide + dense[b]) * k + classes, minlength=cells * k).reshape(cells, k)
                joint = joint[joint.sum(axis=1) > 0]
                if len(joint) > limit:
                    continue
                sizes = joint.sum(axis=1)
                share = int(joint.max(axis=1)[sizes >= 2].sum())
                if int((joint > 0).sum()) == len(joint) and sizes.min() >= 2:
                    found = True
                if share > top:
                    top, top_pair = share, (a, b)
        if top_pair is None:
            return 'no', 0.0, '', one_share, name_at(0)
        return 'yes' if found else 'no', round(top / n, 3), ' ;; '.join(name_at(at_chosen) for at_chosen in top_pair), one_share, name_at(0)

    def judged(feature, at, sources=None):
        counts = collections.Counter(key_of(value) for value in at.values())
        keys = {key: place for place, key in enumerate(sorted(counts))}
        k = len(keys)
        off = len(at) - max(counts.values())
        if k < 2:
            return feature, len(at), off, k, 'zero variance', 0, ''
        if off < 5:
            return feature, len(at), off, k, 'low support', 0, ''
        numeric = all(key[0] == 0 for key in keys)
        missing = (feature, len(at), off, k, 'missing', 0, '')
        rows_here = np.fromiter(at, dtype=np.int64, count=len(at))
        rows_here.sort()
        c = np.zeros(rows, dtype=np.int64)
        c[list(at)] = [keys[key_of(value)] for value in at.values()]
        n, s1, s2 = len(rows_here), int(c[rows_here].sum()), int((c[rows_here] ** 2).sum())
        # Each shape that has an entry on the feature's rows, in the order of the shapes, gives: its place among those kept, its entries, the sums of its classes and of their squares,
        # whether a group of it holds two classes, and the runs of its groups' least class.
        parts = []
        for entries in entry_batches(rows_here):
            groups, classes = group_of_entry[entries], c[row[entries]]
            starts = np.flatnonzero(np.concatenate(([True], groups[1:] != groups[:-1])))
            low, high = np.minimum.reduceat(classes, starts), np.maximum.reduceat(classes, starts)
            sizes = np.diff(np.append(starts, len(entries)))
            shape_of = rank_of_column[shape[entries[starts]]]
            firsts = np.flatnonzero(np.concatenate(([True], shape_of[1:] != shape_of[:-1])))
            same = shape_of[1:] == shape_of[:-1]
            d = low[1:] - low[:-1]
            parts.append((
                shape_of[firsts],
                np.add.reduceat(sizes, firsts),
                np.add.reduceat(np.add.reduceat(classes, starts), firsts),
                np.add.reduceat(np.add.reduceat(classes * classes, starts), firsts),
                np.logical_or.reduceat(low != high, firsts),
                1 + np.add.reduceat(np.concatenate(([0], same & (d != 0))).astype(np.int64), firsts),
                np.add.reduceat(np.concatenate(([0], same & (d > 0))).astype(np.int64), firsts),
                np.add.reduceat(np.concatenate(([0], same & (d < 0))).astype(np.int64), firsts),
                low[firsts]))
        if not parts:
            return missing
        shape_here, cn, c1, c2, mixed, runs, up, down, first_class = (np.concatenate(piece) for piece in zip(*parts))
        rest_n, rest_1, rest_2 = n - cn, s1 - c1, s2 - c2
        # A group of one class, and the rows with no entry of one class: a sum of squares equals the square of the sum over the count only there.
        candidate = ~mixed & (rest_n * rest_2 == rest_1 * rest_1)
        allowed = group_of(feature)[1]
        if allowed is not None:
            candidate &= allowed[shape_here]
        if sources is not None:
            candidate &= np.isin(source_here[shape_here], sources)
        if not candidate.any():
            return missing
        with np.errstate(divide='ignore', invalid='ignore'):
            default_class = np.where(rest_n > 0, rest_1 / np.maximum(rest_n, 1), first_class)
        runs = runs + (default_class != first_class)
        up = up + (default_class < first_class)
        down = down + (default_class > first_class)
        ok = candidate & ((runs <= max(2 * k, 6)) | (numeric & ((up == 0) | (down == 0))))
        found = np.flatnonzero(ok)
        if not len(found):
            return missing
        best = found[np.argsort(runs[found], kind='stable')[:40]]
        best_name = min((name_of.get(int(unique_ids[columns_here[shape_here[place]]]), '?') for place in best), key=len)
        return feature, len(at), off, k, 'covered', len(found), best_name

    def nearest_equal(feature, at):
        """The most table rows on which one column equals the feature, as a share, and the column's name."""
        numbers = {here: float(value) for here, value in at.items() if isinstance(value, (bool, int, float))}
        if not numbers:
            return '', ''
        here_rows = np.fromiter(numbers, dtype=np.int64, count=len(numbers))
        wanted_value = np.zeros(rows, dtype=np.float64)
        wanted_value[here_rows] = [numbers[here] for here in here_rows.tolist()]
        here_rows.sort()
        zero_rows = int((wanted_value[here_rows] == 0).sum())
        flags = set(numbers.values()) <= {0.0, 1.0}
        any_entry = False
        on_zero, equal, flag = (np.zeros(len(unique_ids), dtype=np.float64) for _ in range(3))
        for entries in entry_batches(here_rows):
            any_entry = True
            wanted_here = wanted_value[row[entries]]
            column = shape[entries]
            on_zero += np.bincount(column, weights=(wanted_here == 0).astype(np.float64), minlength=len(unique_ids))
            equal += np.bincount(column, weights=(np.abs(val[entries] - wanted_here) < 1e-3).astype(np.float64), minlength=len(unique_ids))
            if flags:
                flag += np.bincount(column, weights=(wanted_here == 1).astype(np.float64), minlength=len(unique_ids))
        if not any_entry:
            return '', ''
        agree = equal + zero_rows - on_zero
        if flags:
            agree = np.maximum(agree, flag + zero_rows - on_zero)
        allowed = group_of(feature)[1]
        if allowed is not None:
            mask = np.zeros(len(unique_ids), dtype=bool)
            mask[columns_here[allowed]] = True
            agree = np.where(mask, agree, -1)
        best = int(np.argmax(agree))
        return round(float(agree[best]) / len(numbers), 4), name_of.get(int(unique_ids[best]), '?')

    def on_candidates(feature, at):
        """The feature's status where a row is a candidate and its value the mean over that candidate's rows, against the columns with one value per candidate."""
        held = collections.defaultdict(list)
        for own, value in at.items():
            if isinstance(value, (bool, int, float)):
                held[row_candidate[own]].append((own, float(value)))
        if not held or len(held) == len(at):
            return ''
        means = {values[0][0]: round(sum(value for _, value in values) / len(values), 6) for values in held.values()}
        return judged(feature, means, CANDIDATE_SOURCES)[4]

    def one(item):
        feature, at = item
        values = list(at.values())
        random.Random(feature).shuffle(values)
        real = judged(feature, at)
        # A shape over a `project` of all of a table's columns has no entry on that table, so a feature can be missing for that reason alone.
        wider = ''
        holes = len(OWN_HOLE.findall(feature))
        if real[4] == 'missing' and holes and not args.base:
            narrow = {own: value for own, value in at.items() if row_width[own] > holes}
            if narrow and len(narrow) < len(at):
                wider = judged(feature, narrow)[4]
        shuffled = dict(zip(at, values))
        pair = ('', '', '', '', '', '')
        whole = on_candidates(feature, at) if real[4] == 'missing' and not args.base else ''
        if args.pairs and real[4] == 'missing':
            pair = by_pairs(feature, at) + (by_pairs(feature, shuffled)[0],)
        near = nearest_equal(feature, at) if real[4] == 'missing' else ('', '')
        return real + (judged(feature, shuffled)[4], group_of(feature)[0], wider, whole) + pair + near

    if args.why:
        by_name = {}
        for key, name in name_of.items():
            by_name.setdefault(name, key)
        for feature, at in features.items():
            if not isinstance(feature, str) or not re.search(args.why, feature):
                continue
            _, share, _, _, one_name = by_pairs(feature, at)[:5]
            key = by_name.get(one_name)
            print(f'\n{feature}: rows {len(at)}, nearest column {one_name}')
            # The columns that equal the feature on the most table rows, with a table row of no entry at 0.
            numbers = {here: float(value) for here, value in at.items() if isinstance(value, (bool, int, float))}
            if numbers:
                here_rows = np.fromiter(numbers, dtype=np.int64, count=len(numbers))
                here_rows.sort()
                wanted_value = np.zeros(rows, dtype=np.float64)
                wanted_value[here_rows] = [numbers[here] for here in here_rows.tolist()]
                on_rows = np.zeros(rows, dtype=bool)
                on_rows[here_rows] = True
                entries = np.flatnonzero(on_rows[row])
                equal = np.abs(val[entries] - wanted_value[row[entries]]) < 1e-3
                zero_rows = int((wanted_value[here_rows] == 0).sum())
                on_zero = wanted_value[row[entries]] == 0
                agree = np.bincount(shape[entries], weights=equal.astype(np.float64), minlength=len(unique_ids)) + zero_rows - np.bincount(shape[entries], weights=on_zero.astype(np.float64), minlength=len(unique_ids))
                best = np.argsort(-agree)[:6]
                print('  equal on the most table rows:', [(round(float(agree[place]) / len(numbers), 3), name_of.get(int(unique_ids[place]), '?')[:90]) for place in best])
                print('  feature: rows at 0', zero_rows, 'distinct values', len(set(numbers.values())))
                own = np.flatnonzero(shape == best[0])
                column = dict(zip(row[own].tolist(), val[own].tolist()))
                parted = [(row_info[here], value, column.get(here, 0.0), row_width[here]) for here, value in numbers.items() if abs(column.get(here, 0.0) - value) >= 1e-3]
                by_task = collections.Counter((held[0][0], held[0][4]) for held in parted)
                print('  parts on table rows', len(parted), 'by task and table', by_task.most_common(8))
                for held in parted[:6]:
                    print('    ', held)
            if key is None:
                continue
            place = np.searchsorted(unique_ids, key)
            own = np.flatnonzero(shape == place)
            column = dict(zip(row[own].tolist(), val[own].tolist()))
            classes = collections.defaultdict(collections.Counter)
            for here, value in at.items():
                classes[round(column.get(here, 0.0), 4)][value] += 1
            print('  at column value: the feature\'s values', {value: dict(held.most_common(4)) for value, held in sorted(classes.items())[:12]})
            shown = 0
            for here, value in at.items():
                held = classes[round(column.get(here, 0.0), 4)]
                if value != held.most_common(1)[0][0] and shown < 10:
                    shown += 1
                    print('  ', row_info[here], 'feature', value, 'column', column.get(here, 0.0))
        return
    JUDGE = one
    same_values = collections.defaultdict(list)
    for feature, at in features.items():
        same_values[hash(tuple(sorted((own, str(value)) for own, value in at.items())))].append(feature)
    items = [(names[0], features[names[0]]) for names in same_values.values()]
    others_of = {names[0]: names[1:] for names in same_values.values()}
    if args.only:
        with open(args.only) as lines:
            wanted = {parts['feature'] for parts in csv.DictReader(lines, delimiter='\t') if parts['status'] == 'missing'}
        items = [item for item in items if item[0] in wanted]
    items.sort(key=lambda item: -len(item[1]))
    print('features with distinct values', len(items), flush=True)
    begun = time.time()
    tally = collections.Counter()
    with open(args.out, 'w') as sink, mp.get_context('fork').Pool(args.procs) as pool:
        sink.write('feature\trows\toff\tvalues\tstatus\tcolumns\tshortest\tshuffled\tgroup\ton wider tables\ton candidates\ttwo columns\tpair share\tpair\tone share\tone\ttwo columns shuffled\tequal share\tequal\treads\tlevel\tarity\tsame values\n')
        for done, result in enumerate(pool.imap_unordered(judge, items, chunksize=4), 1):
            coordinate = coordinate_of.get(result[0]) or ['', '', '']
            sink.write('\t'.join(map(str, result)) + '\t' + '\t'.join(coordinate) + '\t' + ' ;; '.join(others_of[result[0]][:6]) + '\n')
            sink.flush()
            tally[result[4]] += 1
            if done % 200 == 0:
                rate = done / (time.time() - begun)
                print(f'{done}/{len(items)} {rate:.1f}/s ETA {(len(items) - done) / rate:.0f}s {dict(tally)}', flush=True)
    print('done', dict(tally), flush=True)


if __name__ == '__main__':
    main()
