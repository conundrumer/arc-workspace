#!/usr/bin/env python
"""Whether a model's row gives each first-version feature, on the tables that v1_dump.py wrote.

  v1_cover.py OUT.tsv --v1 DIR --blocks DIR --lists DIR [DIR ...] [--named DIR] [--state DIR] [--skip FILE] [--form shape|place] [--base] [--no-mutants] [--nearest] [--counts FILE] [--tasks N] [--procs N]

A row is one table, of the ground-truth program or of a dumped mutant, at one train pair. Its columns are the table's shapes at that pair, from its list and its list in
`--named`, and the columns of a store's `base`, `qv`, `graph`, `relations` and `wide` at its candidate. `--skip` names tasks to leave out.

With `--base`, a row is one train pair of a task, its features are what the first version says of the input grid, the output and the changed cells, and
its columns are the shapes of the lists of `input` and `ex_output`, the task's constants, and of the pair family in the lists of `--state`.

A first-version feature can name a column by its place in its table, and another table by its identity. Under `--form shape`, the default, each such
feature is judged in the form a shape holds: over the bindings of one type signature, with another table written as how it stands to the owner, its
greatest value, and for a word, whether some binding gives that word. Under `--form place`, each is judged as it stands.

A feature is covered where its value at each row is a function of one column's value there, on the rows where the feature has a value, and that
function is monotone or changes few times along the column, so a few splits can read it. A feature with under 5 rows off its commonest value has low
support, and is not judged. Text that describes a column or a table has no number, so it is not judged. A table at another assignment than its list's is left out. With
`--nearest`, a missing feature that reads the table alone also has the column that gives its value on the most rows, with that share, where a value
met once counts for nothing.

Each feature is judged again with its values shuffled across the rows where it has a value, so a reader can see how often the criterion passes by
chance: more columns and fewer rows raise that rate. `--counts` names a file of v1_column_counts.py, and then a column stands only where a store's train
rows hold an entry of it on at least a leaf's least count of rows, since no fit can read another.

Streams one line per distinct feature, with the first version's metadata of the feature (what it reads, its aggregation level and what else it
reads) and the names that share its values.
"""
import argparse
import collections
import json
import multiprocessing as mp
import pickle
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
from common import open_text  # noqa: E402

TOKEN = re.compile(r'(?:\w+\.)?⟨c:[^⟩]*⟩')
TABLE = re.compile(r'⟨t:[^⟩]*⟩')
OTHER_COLUMN = re.compile(r'(⟨t:[^⟩]*⟩)\.((?:\w+\.)?⟨c:[^⟩]*⟩)')
BASE_TYPES = {'⟨c:P⟩': 'Position', '⟨c:Col⟩': 'Color'}
DEFAULT = np.iinfo(np.int64).max
OTHER = 1 << 63
MIN_DATA = 20
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


def collect(pair, name, types_of, tables, form, out, row, coordinates, coordinate_of):
    """Adds to `out` a row's values of the features of one table at one pair. `types_of` gives each table's column tokens' types by its name."""
    prefix = name + '|'
    own = types_of.get(name, {})
    place_of = {}
    pooled = {}
    words = {}
    for key, value in pair.items():
        if key.startswith(prefix) and key.endswith(' describe') and isinstance(value, str) and TABLE.fullmatch(key[len(prefix):-len(' describe')]):
            place = value.split(' ')[0].lstrip('[')
            place_of[key[len(prefix):-len(' describe')]] = place if place in ('parent', 'ancestor') else 'table'
    for key, value in pair.items():
        if not key.startswith(prefix) or value is None:
            continue
        feature = key[len(prefix):]
        if feature.endswith(' describe'):
            continue
        if form == 'place':
            out[feature][row] = value
            coordinate_of.setdefault(feature, coordinates.get(feature))
            continue

        def of_other(match):
            other = types_of.get(tables.get(match[1], ''), {})
            return f'{place_of.get(match[1], "table")}.?{other.get(match[2], "")}'

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
    parser.add_argument('--state')
    parser.add_argument('--skip')
    parser.add_argument('--form', choices=['shape', 'place'], default='shape')
    parser.add_argument('--base', action='store_true')
    parser.add_argument('--no-mutants', action='store_true')
    parser.add_argument('--nearest', action='store_true')
    parser.add_argument('--counts')
    parser.add_argument('--tasks', type=int)
    parser.add_argument('--procs', type=int, default=3)
    args = parser.parse_args()
    blocks = Path(args.blocks)
    meta = pickle.load((blocks / 'meta.pkl').open('rb'))
    candidates = pickle.load((blocks / 'train.rows.pkl').open('rb'))
    candidate_of = {(row[0], row[1], row[2]): at for at, row in enumerate(candidates)}
    extra = {}
    extra['base'] = {place: 'base:' + key for key, place in meta['base'].items()}
    extra['qv'] = {place: 'qv:' + name for place, name in enumerate(g.QV_NAMES)}
    extra['graph'] = {place: 'graph:' + meta['family_names'].get(int(key), '') for place, key in enumerate(meta['graph_columns'])}
    extra['relations'] = {place: relation + ':' + meta['family_names'].get(int(key), '') for place, (relation, key) in enumerate((r, k) for r in g.RELATIONS for k in meta['relation_columns'])}
    extra['wide'] = {place: 'wide:' + meta['wide_names'].get(int(key), '') for place, key in enumerate(meta['wide_columns'])}
    offset = {source: OTHER + (place << 32) for place, source in enumerate(extra)}
    name_of = {offset[source] + column: name for source, names in extra.items() for column, name in names.items()}
    skipped = set(Path(args.skip).read_text().split()) if args.skip else set()
    paths = sorted(path for path in Path(args.v1).glob('*.json.zst') if path.name.split('.')[0] not in skipped)
    paths = paths[:args.tasks] if args.tasks else paths
    tasks = {path.name.split('.')[0] for path in paths}
    extras = {} if args.base else {source: read_source(blocks, source, {at for key, at in candidate_of.items() if key[0] in tasks}) for source in extra}
    rows = 0
    row_of, shape_of, value_of = [], [], []
    features = collections.defaultdict(dict)
    coordinate_of = {}
    started = time.time()
    used = 0
    other_assignment = [0]

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
                if 'pair' in state_lists:
                    add_list(row, state_lists['pair'], state_others['pair'], at)
                for owner in ('input', 'output', 'changed'):
                    # Every table of this form names its owner, so the owner stands in the feature's name.
                    renamed = {f'{owner}|{owner}: {key[len(owner) + 1:]}': value for key, value in pair.items() if key.startswith(owner + '|')}
                    collect(renamed, owner, {}, {}, args.form, features, row, {}, coordinate_of)
            continue
        mutants = collections.defaultdict(list)
        if not args.no_mutants:
            for mutant in data.get('mutants', []):
                if 'pairs' in mutant:
                    mutants[(mutant['form'], mutant['mutant'])].append(mutant)

        def add_rows(pairs, name, place, candidate, own_types, query_list=None):
            nonlocal rows
            own_named = (named_lists[place], named_others[place]) if place in named_lists else None
            for at, pair in enumerate(pairs):
                if not any(key.startswith(name + '|') for key in pair):
                    continue
                # A table at another assignment than its list's reads other rows, so it says nothing of its list's columns.
                if pair.get(f'{name}|rows') not in (None, head['train_rows'][place][at]):
                    other_assignment[0] += 1
                    continue
                row = rows
                rows += 1
                add_list(row, lists[place], others[place], at)
                if own_named:
                    add_list(row, own_named[0], own_named[1], at)
                if query_list in named_lists:
                    add_list(row, named_lists[query_list], named_others[query_list], at)
                for source, by in extras.items():
                    if candidate in by:
                        columns, values = by[candidate]
                        row_of.append(np.full(len(columns), row, dtype=np.int32))
                        shape_of.append(np.uint64(offset[source]) + columns.astype(np.uint64))
                        value_of.append(values)
                collect(pair, name, own_types, tables, args.form, features, row, coordinates, coordinate_of)

        for item_at, item in enumerate(head['items']):
            name, place = item['table'], item['gold']
            if place not in lists or (task, item_at, 0) not in candidate_of:
                continue
            add_rows(data['pairs'], name, place, candidate_of[(task, item_at, 0)], types_of, f'{item_at}/0/query')
            for j, mutant in enumerate(item['mutants'], 1):
                for held in mutants.get((item['form'], mutant['mutant']), []):
                    if mutant['table'] in lists and (task, item_at, j) in candidate_of:
                        own_types = dict(types_of)
                        own_types.update({key: {token: ty for token, ty in columns} for key, columns in held['columns'].items()})
                        add_rows(held['pairs'], name, mutant['table'], candidate_of[(task, item_at, j)], own_types, f'{item_at}/{j}/query')
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
    # Columns that give one partition of the rows stand as one, kept as its shortest name, so each feature tests fewer columns.
    order = np.lexsort((row, val, shape))
    row, shape, val = row[order], shape[order], val[order]
    new_group = np.concatenate(([True], (shape[1:] != shape[:-1]) | (val[1:] != val[:-1])))
    rank = np.cumsum(new_group) - 1
    starts = np.flatnonzero(np.concatenate(([True], shape[1:] != shape[:-1])))
    ends = np.concatenate((starts[1:], [len(shape)]))
    signature = {}
    keep_shape = np.zeros(len(unique_ids), dtype=bool)
    readable = np.ones(len(unique_ids), dtype=bool)
    if args.counts:
        held = np.load(args.counts)
        readable = np.isin(unique_ids, held['ids'][held['counts'] >= MIN_DATA])
        print(f'columns a fit can read {int(readable.sum())} of {len(unique_ids)}', flush=True)
    for start, end in zip(starts.tolist(), ends.tolist()):
        key = (row[start:end].tobytes(), (rank[start:end] - rank[start]).tobytes())
        if readable[shape[start]] and key not in signature:
            signature[key] = shape[start]
            keep_shape[shape[start]] = True
    print(f'columns {len(unique_ids)} kept {int(keep_shape.sum())}', flush=True)
    wanted = set(unique_ids.tolist())
    for folder in [args.lists[-1]] + ([args.named] if args.named else []) + ([args.state] if args.state else []):
        for line in g.name_lines(Path(folder)):
            parts = line.rstrip('\n').split('\t')
            if len(parts) == 4 and int(parts[0], 16) in wanted:
                name_of[int(parts[0], 16)] = parts[1]
    kept = keep_shape[shape]
    row, shape, val = row[kept], shape[kept], val[kept]
    del signature, rank, new_group
    new_group = np.concatenate(([True], (shape[1:] != shape[:-1]) | (val[1:] != val[:-1])))
    group_start = np.flatnonzero(new_group)
    group_shape = shape[group_start]
    shape_start = np.flatnonzero(np.concatenate(([True], group_shape[1:] != group_shape[:-1])))
    entry_shape_start = np.flatnonzero(np.concatenate(([True], shape[1:] != shape[:-1])))
    columns_here = group_shape[shape_start]
    total = len(unique_ids)
    print(f'tasks {used} rows {rows} left out at another assignment {other_assignment[0]} columns {int(keep_shape.sum())} entries {len(row)} features {len(features)} read {time.time() - started:.0f}s', flush=True)

    def key_of(value):
        return (0, float(value)) if isinstance(value, (bool, int, float)) else (1, str(value))

    def nearest(c, defined, classes):
        """The column that gives the feature's value on the most rows, and that share: each of its values gives its commonest class, and
        a value met once counts for nothing. The rows with no entry count as one value."""
        n = int(defined.sum())
        here = c[row]
        good = defined[row]
        class_totals = np.bincount(c[defined], minlength=classes)
        in_rest = np.tile(class_totals, (len(shape_start), 1)).astype(np.int64)
        most = np.zeros(len(group_start), dtype=np.int64)
        for place in range(classes):
            hits = np.add.reduceat((good & (here == place)).astype(np.int64), group_start)
            most = np.maximum(most, hits)
            in_rest[:, place] -= np.add.reduceat(hits, shape_start)
        members = np.add.reduceat(good.astype(np.int64), group_start)
        most = np.where(members >= 2, most, 0)
        best = np.add.reduceat(most, shape_start) + in_rest.max(axis=1)
        at = int(np.argmax(best))
        return name_of.get(int(unique_ids[columns_here[at]]), '?'), round(float(best[at]) / n, 3)

    def judged(feature, at, with_nearest):
        counts = collections.Counter(key_of(value) for value in at.values())
        keys = {key: place for place, key in enumerate(sorted(counts))}
        k = len(keys)
        off = len(at) - max(counts.values())
        if k < 2:
            return feature, len(at), off, k, 'zero variance', 0, '', '', ''
        if off < 5:
            return feature, len(at), off, k, 'low support', 0, '', '', ''
        numeric = all(key[0] == 0 for key in keys)
        c = np.full(rows, DEFAULT, dtype=np.int64)
        for own, value in at.items():
            c[own] = keys[key_of(value)]
        defined = c != DEFAULT
        n, s1, s2 = int(defined.sum()), int(c[defined].sum()), int((c[defined] ** 2).sum())
        here = c[row]
        good = defined[row]
        low = np.minimum.reduceat(here, group_start)
        high = np.maximum.reduceat(np.where(good, here, -1), group_start)
        has_rows = high >= 0
        impure = has_rows & (low != high)
        shape_bad = np.logical_or.reduceat(impure, shape_start)
        weight = good.astype(np.int64)
        masked = np.where(good, here, 0)
        cn = np.add.reduceat(weight, entry_shape_start)
        c1 = np.add.reduceat(masked, entry_shape_start)
        c2 = np.add.reduceat(masked * masked, entry_shape_start)
        rest_n, rest_1, rest_2 = n - cn, s1 - c1, s2 - c2
        rest_bad = rest_n * rest_2 != rest_1 * rest_1
        candidate_shapes = ~shape_bad & ~rest_bad & (cn > 0)

        def missing():
            if not with_nearest or (coordinate_of.get(feature) or ['', '', ''])[2] != 'owner':
                return feature, len(at), off, k, 'missing', 0, '', '', ''
            if k > 12:
                bins = np.digitize(c, np.quantile(c[defined], np.linspace(0, 1, 13)[1:-1]))
                name, share = nearest(np.where(defined, bins, DEFAULT), defined, 13)
            else:
                name, share = nearest(c, defined, k)
            return feature, len(at), off, k, 'missing', 0, '', name, share

        if not candidate_shapes.any():
            return missing()
        g_class, g_shape = low[has_rows], group_shape[has_rows]
        same = g_shape[1:] == g_shape[:-1]
        d = g_class[1:] - g_class[:-1]
        runs = np.bincount(g_shape[1:][same & (d != 0)], minlength=total) + 1
        up = np.bincount(g_shape[1:][same & (d > 0)], minlength=total)
        down = np.bincount(g_shape[1:][same & (d < 0)], minlength=total)
        first_class = np.full(total, -1, dtype=np.int64)
        starts_here = np.concatenate(([True], ~same))
        first_class[g_shape[starts_here]] = g_class[starts_here]
        runs, up, down, first_class = runs[columns_here], up[columns_here], down[columns_here], first_class[columns_here]
        with np.errstate(divide='ignore', invalid='ignore'):
            default_class = np.where(rest_n > 0, rest_1 / np.maximum(rest_n, 1), first_class)
        runs = runs + (default_class != first_class)
        up = up + (default_class < first_class)
        down = down + (default_class > first_class)
        ok = candidate_shapes & ((runs <= max(2 * k, 6)) | (numeric & ((up == 0) | (down == 0))))
        found = np.flatnonzero(ok)
        if not len(found):
            return missing()
        best = found[np.argsort(runs[found], kind='stable')[:40]]
        best_name = min((name_of.get(int(unique_ids[columns_here[place]]), '?') for place in best), key=len)
        return feature, len(at), off, k, 'covered', len(found), best_name, '', ''

    def one(item):
        feature, at = item
        values = list(at.values())
        random.Random(feature).shuffle(values)
        return judged(feature, at, args.nearest) + (judged(feature, dict(zip(at, values)), False)[4],)

    JUDGE = one
    same_values = collections.defaultdict(list)
    for feature, at in features.items():
        same_values[hash(tuple(sorted((own, str(value)) for own, value in at.items())))].append(feature)
    items = [(names[0], features[names[0]]) for names in same_values.values()]
    others_of = {names[0]: names[1:] for names in same_values.values()}
    items.sort(key=lambda item: -len(item[1]))
    print('features with distinct values', len(items), flush=True)
    begun = time.time()
    tally = collections.Counter()
    with open(args.out, 'w') as sink, mp.get_context('fork').Pool(args.procs) as pool:
        sink.write('feature\trows\toff\tvalues\tstatus\tcolumns\tshortest\tnearest\tnearest share\tshuffled\treads\tlevel\tarity\tsame values\n')
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
