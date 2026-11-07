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
from common import open_text, read_pickle  # noqa: E402

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
CANDIDATE_SOURCES = ['relations', 'relations_least', 'relations_most', 'graph', 'query', 'base', 'qv', 'wide']
JUDGE = None


def judge(item):
    return JUDGE(item)


def read_source(blocks, name, wanted):
    """The rows of a store's source at the candidates in `wanted`: candidate -> columns, values."""
    reader = zstandard.ZstdDecompressor().stream_reader(open(Path(blocks) / 'blocks' / f'train.{name}.zst', 'rb'), read_across_frames=True)

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


def number(value):
    return float(value) if isinstance(value, (bool, int, float)) else None


def by_table(pair):
    """A pair's values as {table: {feature: value}}."""
    out = collections.defaultdict(dict)
    for key, value in pair.items():
        name, _, feature = key.partition('|')
        out[name][feature] = value
    return out


def collect(at, name, types_of, tables, form, out, row, coordinates, coordinate_of, one_binding=False):
    """Adds to `out` a row's values of the features of one table at one pair, given as {feature: value}. `types_of` gives each table's column tokens' types by its name. Under
    `one_binding`, a feature that names a column stands only where its table has one column of that type."""
    own = types_of.get(name, {})
    of_type = collections.Counter(own.values())
    place_of = {}
    pooled = {}
    words = {}
    for feature, value in at.items():
        if feature.endswith(' describe') and isinstance(value, str) and TABLE.fullmatch(feature[:-len(' describe')]):
            place = value.split(' ')[0].lstrip('[')
            place_of[feature[:-len(' describe')]] = place if place in ('parent', 'ancestor') else 'table'
    for feature, value in at.items():
        if value is None or feature.endswith(' describe'):
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
    parser.add_argument('--tasks', type=int)
    parser.add_argument('--procs', type=int, default=3)
    args = parser.parse_args()
    begun_at = time.time()
    blocks = Path(args.blocks)
    meta = read_pickle(blocks / 'meta.pkl')
    candidates = read_pickle(blocks / 'train.rows.pkl')
    candidate_of = {(row[0], row[1], row[2]): at for at, row in enumerate(candidates)}
    extra = {}
    extra['base'] = {place: 'base:' + key for key, place in meta['base'].items()}
    extra['qv'] = {place: 'qv:' + name for place, name in enumerate(g.QV_NAMES)}
    extra['graph'] = {place: 'graph:' + meta['family_names'].get(int(key), '') for place, key in enumerate(meta['graph_columns'])}
    extra['relations'] = {place: relation + ':' + meta['family_names'].get(int(key), '') for place, (relation, key) in enumerate((r, k) for r in g.RELATIONS for k in meta['relation_columns'])}
    extra['wide'] = {place: 'wide:' + meta['wide_names'].get(int(key), '') for place, key in enumerate(meta['wide_columns'])}
    extra['contingent'] = {place: 'contingent:' + meta['names'].get(int(key), '') for place, key in enumerate(meta['columns'])}
    for pool in ('relations_least', 'relations_most'):
        if (blocks / 'blocks' / f'train.{pool}.zst').exists():
            extra[pool] = {place: pool + ':' + name.split(':', 1)[0] + ':' + name.split(':', 1)[1] for place, name in extra['relations'].items()}
    offset = {source: OTHER + (place << 32) for place, source in enumerate(extra)}
    name_of = {offset[source] + column: name for source, names in extra.items() for column, name in names.items()}
    skipped = set(Path(args.skip).read_text().split()) if args.skip else set()
    paths = sorted(path for path in Path(args.v1).glob('*.json.zst') if path.name.split('.')[0] not in skipped)
    in_store = {row[0] for row in candidates}
    paths = [path for path in paths if path.name.split('.')[0] in in_store and any((Path(folder) / (path.name.split('.')[0] + '.lists.zst')).exists() for folder in args.lists)]
    paths = paths[:args.tasks] if args.tasks else paths
    tasks = {path.name.split('.')[0] for path in paths}
    extras = {} if args.base else {source: read_source(blocks, source, {at for key, at in candidate_of.items() if key[0] in tasks}) for source in extra}
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

    def add_list(row, held, other, at):
        """A row's entries from a table's list at a pair."""
        row_of.append(np.full(len(held[0]), row, dtype=np.int32))
        shape_of.append(held[0])
        value_of.append(held[1])
        if len(other[0]) and other[4].shape[1] > at:
            values = other[4][:, at]
            active = values != 0
            row_of.append(np.full(int(active.sum()), row, dtype=np.int32))
            shape_of.append(other[0][active])
            value_of.append(values[active])

    for path in paths:
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

        def add_rows(pairs, name, place, candidate, own_types, query_list=None):
            nonlocal rows
            own_named = (named_lists[place], named_others[place]) if place in named_lists else None
            for at, pair in enumerate(pairs):
                table_at = pair.get(name)
                if table_at is None:
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
                        row_of.append(np.full(len(columns), row, dtype=np.int32))
                        shape_of.append(np.uint64(offset[source]) + columns.astype(np.uint64))
                        value_of.append(values)
                collect(table_at, name, own_types, tables, args.form, features, row, coordinates, coordinate_of, args.one_binding)

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
                        add_rows([by_table(pair) for pair in held['pairs']], name, mutant['table'], candidate_of[(task, item_at, j)], own_types, f'{item_at}/{j}/query')
    row = np.concatenate(row_of)
    ids = np.concatenate(shape_of)
    val = np.concatenate(value_of).astype(np.float64)
    del row_of, shape_of, value_of
    val = np.nan_to_num(val, nan=-7.77e7)
    keep = val != 0
    row, ids, val = row[keep], ids[keep], val[keep]
    # A word's column is 0 where the feature has a value there and another word.
    for key in [key for key in features if isinstance(key, tuple)]:
        at = features.pop(key)
        for word in {word for words in at.values() for word in words}:
            column = features[f'{key[1]} :{word}']
            for own in at:
                column.setdefault(own, 0.0)
    unique_ids, shape = np.unique(ids, return_inverse=True)
    del ids
    wanted = set(unique_ids.tolist())
    for folder in [args.lists[-1]] + ([args.named] if args.named else []) + ([args.more] if args.more else []) + ([args.state] if args.state else []):
        for key, parts in g.names_in(Path(folder), wanted)[0].items():
            name_of[key] = parts[1]
    source_at = {offset[source] + column: source for source, names in extra.items() for column in names}

    def source_of(key):
        if key in source_at:
            return source_at[key]
        name = name_of.get(key, '')
        return 'named' if name.startswith('(named') else 'query' if name.startswith('(query') else 'shape'

    sources = [source_of(int(key)) for key in unique_ids.tolist()]
    # Columns of one source that give one partition of the rows stand as one, so each feature tests fewer columns.
    order = np.lexsort((row, val, shape))
    row, shape, val = row[order], shape[order], val[order]
    new_group = np.concatenate(([True], (shape[1:] != shape[:-1]) | (val[1:] != val[:-1])))
    rank = np.cumsum(new_group) - 1
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
    kept = keep_shape[shape]
    row, shape, val = row[kept], shape[kept], val[kept]
    del signature, rank, new_group
    new_group = np.concatenate(([True], (shape[1:] != shape[:-1]) | (val[1:] != val[:-1])))
    group_start = np.flatnonzero(new_group)
    group_shape = shape[group_start]
    shape_start = np.flatnonzero(np.concatenate(([True], group_shape[1:] != group_shape[:-1])))
    entry_shape_start = np.flatnonzero(np.concatenate(([True], shape[1:] != shape[:-1])))
    columns_here = group_shape[shape_start]
    # Each entry's group of equal values, each group's shape among those kept, and each row's entries.
    group_of_entry = np.cumsum(new_group).astype(np.int32) - 1
    groups_of_shape = np.diff(np.append(shape_start, len(group_start)))
    shape_of_group = np.repeat(np.arange(len(shape_start)), groups_of_shape)
    entry_of_row = np.argsort(row, kind='stable')
    row_entries = np.bincount(row, minlength=rows)
    row_first = np.concatenate(([0], np.cumsum(row_entries)))
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

    def entries_on(rows_here):
        """The entries on some rows, in the order of their groups. Through the rows' own entries where they are few, since a look at every entry costs more."""
        total_here = int(row_entries[rows_here].sum())
        if total_here * 8 > len(row):
            defined = np.zeros(rows, dtype=bool)
            defined[rows_here] = True
            return np.flatnonzero(defined[row])
        if not total_here:
            return np.zeros(0, dtype=np.int64)
        held = np.concatenate([entry_of_row[row_first[own]:row_first[own + 1]] for own in rows_here.tolist()])
        held.sort()
        return held

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
        entries = entries_on(rows_here)
        if not len(entries):
            return 'no', 0.0, '', 0.0, ''
        groups, classes_at = group_of_entry[entries], c[row[entries]]
        starts = np.flatnonzero(np.concatenate(([True], groups[1:] != groups[:-1])))
        touched = np.repeat(np.arange(len(starts)), np.diff(np.append(starts, len(entries))))
        table = np.bincount(touched * k + classes_at, minlength=len(starts) * k).reshape(len(starts), k)
        members = table.sum(axis=1)
        most = np.where(members >= 2, table.max(axis=1), 0)
        shape_of = shape_of_group[groups[starts]]
        firsts = np.flatnonzero(np.concatenate(([True], shape_of[1:] != shape_of[:-1])))
        shape_here = shape_of[firsts]
        in_rest = np.bincount(c[rows_here], minlength=k)[None, :] - np.add.reduceat(table, firsts, axis=0)
        best = np.add.reduceat(most, firsts) + in_rest.max(axis=1)
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
        ends = np.append(firsts[1:], len(starts))
        group_ends = np.append(starts[1:], len(entries))
        dense = []
        for at_chosen in chosen.tolist():
            first, last = starts[firsts[at_chosen]], group_ends[ends[at_chosen] - 1]
            codes = np.zeros(n, dtype=np.int64)
            codes[place_of[row[entries[first:last]]]] = groups[first:last] - shape_start[shape_here[at_chosen]] + 1
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
        entries = entries_on(rows_here)
        if not len(entries):
            return missing
        groups, classes = group_of_entry[entries], c[row[entries]]
        starts = np.flatnonzero(np.concatenate(([True], groups[1:] != groups[:-1])))
        low, high = np.minimum.reduceat(classes, starts), np.maximum.reduceat(classes, starts)
        sizes = np.diff(np.append(starts, len(entries)))
        # Each shape that has an entry on the feature's rows, at the place of its first group among those.
        shape_of = shape_of_group[groups[starts]]
        firsts = np.flatnonzero(np.concatenate(([True], shape_of[1:] != shape_of[:-1])))
        shape_here = shape_of[firsts]
        cn = np.add.reduceat(sizes, firsts)
        c1 = np.add.reduceat(np.add.reduceat(classes, starts), firsts)
        c2 = np.add.reduceat(np.add.reduceat(classes * classes, starts), firsts)
        rest_n, rest_1, rest_2 = n - cn, s1 - c1, s2 - c2
        # A group of one class, and the rows with no entry of one class: a sum of squares equals the square of the sum over the count only there.
        candidate = ~np.logical_or.reduceat(low != high, firsts) & (rest_n * rest_2 == rest_1 * rest_1)
        allowed = group_of(feature)[1]
        if allowed is not None:
            candidate &= allowed[shape_here]
        if sources is not None:
            candidate &= np.isin(source_here[shape_here], sources)
        if not candidate.any():
            return missing
        same = shape_of[1:] == shape_of[:-1]
        d = low[1:] - low[:-1]
        runs = 1 + np.add.reduceat(np.concatenate(([0], same & (d != 0))).astype(np.int64), firsts)
        up = np.add.reduceat(np.concatenate(([0], same & (d > 0))).astype(np.int64), firsts)
        down = np.add.reduceat(np.concatenate(([0], same & (d < 0))).astype(np.int64), firsts)
        first_class = low[firsts]
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
        return real + (judged(feature, shuffled)[4], group_of(feature)[0], wider, whole) + pair

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
        sink.write('feature\trows\toff\tvalues\tstatus\tcolumns\tshortest\tshuffled\tgroup\ton wider tables\ton candidates\ttwo columns\tpair share\tpair\tone share\tone\ttwo columns shuffled\treads\tlevel\tarity\tsame values\n')
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
