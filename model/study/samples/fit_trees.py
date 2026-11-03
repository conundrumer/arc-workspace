"""The fit of the gradient-boosted trees over the training rows (stage 5 of the sample build writes them, points_write.py).

  python3 fit_trees.py --points DIR --out PATH [--points-per-task N] [--seed S] [--dev-tasks T,T] [--alpha A] [--rounds R] ...
  python3 fit_trees.py --points DIR --check [--alpha A]

DIR is `samples/SET/points/`. The point files of train tasks give the fit and those of dev tasks give the evaluation, by the split in each file's header. A file whose header split is
held-out (or `held`, its name in older files) is an error, and so is a DIR below `points_held-out` or `points_held`. --dev-tasks names tasks to treat as dev whatever their header says (for development on a small set; held-out stays an error).
With --points-per-task N a task keeps at most N of its points, chosen by a hash of the seed, the sample id and the point's position in its file (0: all).

A row is one (point, id): the id's option values, the id's table vector and the point's values. The columns are in the order of the header's `uses` (the writer's feature names, which
serving takes as the model's columns). A header without `uses` gives option names, then table names, then point names. A header with `vector_names` (points_write.py --vectors) gives
rows that are the writer's writing-point vector of the id, rebuilt from the point's `vp` and the id's row of `vo`, with the columns in the order of `vector_names`; NaN is kept as a value.
A point is a group. The score of an id is a sum of the trees'
leaf values. In a group with scores s, p = softmax(s) over the group's ids, and q = softmax over the positive ids only. The loss of a group is -log(sum of p over the positive ids), its
gradient in s is p - q and its Hessian is p(1 - p), floored at 1e-6. --check compares that gradient with a finite difference of the loss on a real group.
With --alpha A (default 0), the train loss weighs each id's term of the softmax denominator by w = 1 + A * drawn, with drawn the id's count in the point's `drawn` (points_write.py --draws;
0 for an id it does not list): p = w e^s / sum(w e^s), and the loss, gradient and Hessian are as above with that p. A drawn count on a positive id is an error. The dev loss, the
evaluation and the booster's scores do not read the weight. With A = 0, or with no drawn count, the fit is the one without --alpha.

--out is the file of `booster.save_model`. Beside it, `<out>.json` holds the params, the evaluation, the matrix sizes, the feature names and the header fields that define the features.
"""
import argparse
import base64
import gzip
import hashlib
import heapq
import json
import os
import re
import resource
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator

import lightgbm as lgb
import numpy as np

from split import is_held_out

HELD_FOLDERS = ('points_held-out', 'points_held')  # the folder name, and the one that earlier runs wrote
FEATURE_FIELDS = ('schema', 'extractor_sha', 'writer_sha', 'wheel', 'point_names', 'option_names', 'table_names', 'uses', 'vector_names', 'vector_point_cols')
HESSIAN_FLOOR = 1e-6
SPECIAL = re.compile(r'[\s",:\[\]{}]')  # the characters that LightGBM refuses in a feature name
type Floats = np.ndarray
type Ints = np.ndarray


class FitError(Exception):
    """A point file or an argument that the fit refuses; the message is the reason."""


# ---------------------------------------------------------------- the groups

@dataclass
class Groups:
    """Rows grouped by point: the 0/1 positive mark of each row, the size of each group and the column count of the rows."""
    positive: Floats  # (rows,) float32
    sizes: Ints  # (groups,) int64
    columns: int
    tasks: list[str] = field(default_factory=list)
    drawn: Floats | None = None  # (rows,) float32: the drawn count of each row's id; None where the rows have none

    @property
    def rows(self) -> int:
        return len(self.positive)

    @property
    def starts(self) -> Ints:
        return np.concatenate(([0], np.cumsum(self.sizes)[:-1])).astype(np.int64)

    def describe(self) -> dict[str, Any]:
        rows, groups = self.rows, max(len(self.sizes), 1)
        item = np.dtype(np.float32).itemsize
        return dict(tasks=len(set(self.tasks)), groups=len(self.sizes), rows=rows, columns=self.columns, ids_per_group=round(rows / groups, 2),
                    positives_per_group=round(float(self.positive.sum()) / groups, 3), drawn=float(self.drawn.sum()) if self.drawn is not None else 0.0, matrix_bytes=rows * self.columns * item,
                    bytes_per_row=(rows * self.columns * item + self.positive.nbytes) // max(rows, 1))


@dataclass
class Dense(Groups):
    """Groups with their rows in one matrix."""
    matrix: Floats = field(kw_only=True)  # (rows, columns) float32


# ---------------------------------------------------------------- the loss and its gradient

@dataclass
class Terms:
    p: Floats  # softmax over each group's ids
    q: Floats  # softmax over each group's positive ids, 0 elsewhere
    loss: Floats  # per group, -log(sum of p over the positive ids)
    tied_top: Floats  # per group, the count of ids with the highest score
    tied_top_positive: Floats  # per group, the count of those that are positive


def group_terms(scores: Floats, positive: Floats, starts: Ints, sizes: Ints, weight: Floats | None = None) -> Terms:
    """The softmax terms of every group at once; each group has at least one id and at least one positive id. weight, if given, is each id's weight in the softmax denominator, 1 on
    the positive ids."""
    mark = positive > 0
    top = np.maximum.reduceat(scores, starts)
    e = np.exp(scores - np.repeat(top, sizes))
    if weight is not None:
        e = e * weight
    total = np.add.reduceat(e, starts)
    top_pos = np.maximum.reduceat(np.where(mark, scores, -np.inf), starts)
    e_pos = np.where(mark, np.exp(scores - np.repeat(top_pos, sizes)), 0.0)
    total_pos = np.add.reduceat(e_pos, starts)
    loss = (np.log(total) + top) - (np.log(total_pos) + top_pos)
    tied = scores == np.repeat(top, sizes)
    return Terms(e / np.repeat(total, sizes), e_pos / np.repeat(total_pos, sizes), loss, np.add.reduceat(tied.astype(np.float64), starts),
                 np.add.reduceat((tied & mark).astype(np.float64), starts))


def loss_weight(groups: Groups, alpha: float) -> Floats | None:
    """1 + alpha * drawn for each row, or None where alpha is 0 or no row has a drawn count."""
    if alpha == 0 or groups.drawn is None or not groups.drawn.any():
        return None
    return 1.0 + alpha * groups.drawn.astype(np.float64)


def objective_of(groups: Groups, alpha: float = 0.0) -> Callable[[Floats, Any], tuple[Floats, Floats]]:
    """The custom objective of LightGBM over a set of groups: (gradient, Hessian) of the summed group losses, with the denominator weights of alpha."""
    starts, sizes, positive = groups.starts, groups.sizes, groups.positive.astype(np.float64)
    weight = loss_weight(groups, alpha)

    def objective(scores: Floats, _data: Any) -> tuple[Floats, Floats]:
        t = group_terms(np.asarray(scores, np.float64), positive, starts, sizes, weight)
        return t.p - t.q, np.maximum(t.p * (1.0 - t.p), HESSIAN_FLOOR)
    return objective


def evaluate(scores: Floats, groups: Groups) -> dict[str, float]:
    """Over the points: the mean loss, and the share of points whose top-scored id is a positive. Ids tied at the top share a point's credit equally."""
    t = group_terms(np.asarray(scores, np.float64), groups.positive, groups.starts, groups.sizes)
    return dict(points=int(len(groups.sizes)), mean_loss=float(t.loss.mean()), top_is_positive=float((t.tied_top_positive / t.tied_top).mean()))


def uniform_baseline(groups: Groups) -> dict[str, float]:
    """The same two numbers for p = 1 / len(ids): the sum of p over the positives is positives / ids, and every id ties for the top."""
    share = np.add.reduceat(groups.positive.astype(np.float64), groups.starts) / groups.sizes
    return dict(points=int(len(groups.sizes)), mean_loss=float((-np.log(share)).mean()), top_is_positive=float(share.mean()))


# ---------------------------------------------------------------- reading point files

def records_of(path: Path) -> Iterator[dict]:
    with gzip.open(path, 'rt') as f:
        for text in f:
            yield json.loads(text)


def header_of(path: Path) -> dict:
    try:
        first = next(records_of(path), None)
    except (OSError, EOFError, ValueError) as e:
        raise FitError(f'{path}: unreadable: {e}') from e
    if not first or first.get('record') != 'header':
        raise FitError(f'{path}: the first record is not a header')
    if path.name != f'{first["task"]}.jsonl.gz':
        raise FitError(f'{path}: the header names task {first["task"]}')
    return first


def point_folder(folder: Path) -> Path:
    if any(name in folder.resolve().parts for name in HELD_FOLDERS):
        raise FitError(f'{folder}: a fit never reads {" or ".join(HELD_FOLDERS)}')
    if not folder.is_dir():
        raise FitError(f'{folder}: not a folder')
    return folder


def split_files(folder: Path, dev_tasks: set[str]) -> tuple[list[Path], list[Path], dict[str, dict]]:
    """(train files, dev files, the header of each task), by the split in each header; --dev-tasks moves tasks to dev. A header split other than train or dev is an error."""
    paths = sorted(point_folder(folder).glob('*.jsonl.gz'))
    heads = {p.name.removesuffix('.jsonl.gz'): header_of(p) for p in paths}
    unknown = dev_tasks - heads.keys()
    if unknown:
        raise FitError(f'--dev-tasks names tasks with no file in {folder}: {sorted(unknown)}')
    train: list[Path] = []
    dev: list[Path] = []
    for p in paths:
        task = p.name.removesuffix('.jsonl.gz')
        split = heads[task]['split']
        if is_held_out(split):
            raise FitError(f'{p}: the header split is {split!r}; a fit never reads a held-out file')
        if split not in ('train', 'dev'):
            raise FitError(f'{p}: the header split is {split!r}; only train and dev files are read')
        (dev if split == 'dev' or task in dev_tasks else train).append(p)
    return train, dev, heads


@dataclass
class Layout:
    """Where each part of a row goes in the matrix: the column of each option name, table name and point name, and the column names in order."""
    names: list[str]
    option_cols: Ints
    table_cols: Ints
    point_cols: Ints
    vector_point_cols: Ints | None = None  # with vectors: the columns that `vp` gives
    vector_id_cols: Ints | None = None  # with vectors: the columns that the rows of `vo` give


def layout_of(fields: dict[str, Any]) -> Layout:
    """The columns follow the header's `vector_names` where it has them, else its `uses` where it has one, and else the option names, the table names and the point names."""
    if fields.get('vector_names') is not None:
        names = list(fields['vector_names'])
        if len(set(names)) != len(names):
            raise FitError('a vector name appears twice in the header')
        if fields.get('uses') != names:
            raise FitError('the header\'s uses are not its vector names')
        point = np.array(fields.get('vector_point_cols') or [], np.int64)
        if len(set(point.tolist())) != len(point) or (len(point) and (point.min() < 0 or point.max() >= len(names))):
            raise FitError('the header\'s vector_point_cols are not distinct columns of the vector')
        empty = np.zeros(0, np.int64)
        return Layout(names, empty, empty, empty, point, np.setdiff1d(np.arange(len(names), dtype=np.int64), point))
    parts = [*fields['option_names'], *fields['table_names'], *fields['point_names']]
    if len(set(parts)) != len(parts):
        raise FitError('a feature name appears twice in the header')
    names = list(fields['uses']) if fields.get('uses') is not None else parts
    if sorted(names) != sorted(parts):
        raise FitError('the header\'s uses are not the option, table and point names')
    at = {n: i for i, n in enumerate(names)}
    return Layout(names, *(np.array([at[n] for n in fields[k]], np.int64) for k in ('option_names', 'table_names', 'point_names')))


def feature_fields(heads: list[dict]) -> dict[str, Any]:
    """The header fields that define the features; every file must carry the same ones."""
    if not heads:
        raise FitError('no point files')
    fields = {k: heads[0].get(k) for k in FEATURE_FIELDS}
    for h in heads[1:]:
        other = {k: h.get(k) for k in FEATURE_FIELDS}
        if other != fields:
            differ = [k for k in FEATURE_FIELDS if other[k] != fields[k]]
            raise FitError(f'the files of tasks {heads[0]["task"]} and {h["task"]} differ in {differ}')
    return fields


@dataclass
class Kept:
    """A point kept for the matrix: its option values, the table index of each id, its values and the indexes of its positive ids. With vectors the option, table and point values are empty,
    and vp (the point-scope columns) and vo (one row of the other columns for each id) hold the vector."""
    option: Floats
    table: Ints
    point: Floats
    positive: Ints
    size: int
    vp: Floats | None = None
    vo: Floats | None = None
    drawn: Floats | None = None  # (size,) float32 where the point lists drawn counts


def choice_key(seed: int, sample: str, position: int) -> int:
    return int.from_bytes(hashlib.sha256(f'{seed}:{sample}:{position}'.encode()).digest()[:8], 'big')


def kept_of(path: Path, head: dict, per_task: int, seed: int) -> tuple[list[Kept], dict[int, Floats], Counter[str]]:
    """The kept points of one file in file order, the table vectors by index, and the counts. Points with fewer than two ids or with no positive id are counted and left out. With per_task > 0 the
    points with the smallest hash keys are kept."""
    n_option, n_table, n_point = len(head['option_names']), len(head['table_names']), len(head['point_names'])
    is_vector = head.get('vector_names') is not None
    n_vp = len(head.get('vector_point_cols') or [])
    n_vo = len(head["vector_names"]) - n_vp if is_vector else 0
    tables: dict[int, Floats] = {}
    kept: list[tuple[int, int, Kept]] = []  # a heap of (-key, position, point) where per_task > 0
    count: Counter[str] = Counter()
    for position, rec in enumerate(records_of(path)):
        kind = rec['record']
        if kind == 'table':
            vector = np.array(rec['values'], np.float32)
            if vector.shape != (n_table,):
                raise FitError(f'{path}: table {rec["i"]} has {vector.shape} values; the header names {n_table}')
            tables[int(rec['i'])] = vector
        elif kind == 'point':
            count['points'] += 1
            n = len(rec['ids'])
            if is_vector:
                vp_bytes, vo_bytes = base64.b64decode(rec['vp']), base64.b64decode(rec['vo'])
                if len(vp_bytes) != 4 * n_vp or len(vo_bytes) != 4 * n * n_vo:
                    raise FitError(f'{path}: the point at record {position} has parts of different sizes')
            elif len(rec['option']) != n or len(rec['table']) != n or len(rec['point']) != n_point:
                raise FitError(f'{path}: the point at record {position} has parts of different sizes')
            if n < 2:
                count['points with fewer than two ids'] += 1
                continue
            if not rec['positive']:
                count['points with no positive id'] += 1
                continue
            if min(rec['positive']) < 0 or max(rec['positive']) >= n:
                raise FitError(f'{path}: the point at record {position} has a positive index outside its ids')
            drawn = None
            if rec.get('drawn'):
                drawn = np.zeros(n, np.float32)
                for i, c in rec['drawn']:
                    if not 0 <= i < n or i in rec['positive'] or c < 0:
                        raise FitError(f'{path}: the point at record {position} has a drawn count outside its ids, on a positive id, or below 0')
                    drawn[i] = c
            if not is_vector:
                missing = set(rec['table']) - tables.keys()
                if missing:
                    raise FitError(f'{path}: the point at record {position} uses tables {sorted(missing)[:5]} that no record defines')
            key = choice_key(seed, rec['sample'], position)
            if per_task > 0 and len(kept) >= per_task and -kept[0][0] <= key:
                continue
            if is_vector:
                got = Kept(np.zeros((n, 0), np.float32), np.zeros(0, np.int64), np.zeros(0, np.float32), np.array(rec['positive'], np.int64), n,
                           np.frombuffer(vp_bytes, '<f4').astype(np.float32), np.frombuffer(vo_bytes, '<f4').astype(np.float32).reshape(n, n_vo), drawn)
            else:
                got = Kept(np.array(rec['option'], np.float32).reshape(n, n_option), np.array(rec['table'], np.int64),
                           np.array(rec['point'], np.float32), np.array(rec['positive'], np.int64), n, drawn=drawn)
            if per_task > 0 and len(kept) >= per_task:
                heapq.heapreplace(kept, (-key, position, got))
            elif per_task > 0:
                heapq.heappush(kept, (-key, position, got))
            else:
                kept.append((-key, position, got))
    count['points kept'] = len(kept)
    kept.sort(key=lambda k: k[1])
    return [k for _, _, k in kept], tables, count


def fill_rows(out: Floats, k: Kept, tables: dict[int, Floats], layout: Layout, lo: int, hi: int) -> None:
    """Write rows lo to hi of the point k into out, which has hi - lo rows."""
    if layout.vector_id_cols is not None and layout.vector_point_cols is not None and k.vo is not None and k.vp is not None:
        out[:, layout.vector_id_cols] = k.vo[lo:hi]
        out[:, layout.vector_point_cols] = k.vp
        return
    out[:, layout.option_cols] = k.option[lo:hi]
    out[:, layout.table_cols] = np.stack([tables[int(i)] for i in k.table[lo:hi]]) if len(layout.table_cols) else 0
    out[:, layout.point_cols] = k.point


def positive_of(kept: list[Kept]) -> tuple[Floats, Ints, Floats | None]:
    """The 0/1 positive mark of every row of the points, the size of each point, and the drawn count of every row (None where no point lists one)."""
    sizes = np.array([k.size for k in kept], np.int64)
    positive = np.zeros(int(sizes.sum()), np.float32)
    drawn = np.zeros(len(positive), np.float32) if any(k.drawn is not None for k in kept) else None
    at = 0
    for k in kept:
        positive[at + k.positive] = 1.0
        if drawn is not None and k.drawn is not None:
            drawn[at:at + k.size] = k.drawn
        at += k.size
    return positive, sizes, drawn


def joined_drawn(pieces: list[Groups]) -> Floats | None:
    """The drawn counts of the pieces' rows in one array, 0 for a piece with none; None where no piece has any."""
    if all(g.drawn is None for g in pieces):
        return None
    return np.concatenate([g.drawn if g.drawn is not None else np.zeros(g.rows, np.float32) for g in pieces])


def read_file(path: Path, head: dict, layout: Layout, per_task: int, seed: int) -> tuple[Dense, Counter[str]]:
    """The groups of one file, with their rows in one matrix."""
    kept, tables, count = kept_of(path, head, per_task, seed)
    positive, sizes, drawn = positive_of(kept)
    matrix = np.empty((len(positive), len(layout.names)), np.float32)
    at = 0
    for k in kept:
        end = at + k.size
        fill_rows(matrix[at:end], k, tables, layout, 0, k.size)
        at = end
    return Dense(positive, sizes, len(layout.names), [head['task']] * len(sizes), drawn, matrix=matrix), count


def load(paths: list[Path], heads: dict[str, dict], layout: Layout, per_task: int, seed: int) -> tuple[Dense, Counter[str]]:
    """The groups of the files, in one matrix. The pieces are copied in one by one so that the peak is the matrix and one piece."""
    pieces: list[Dense] = []
    count: Counter[str] = Counter()
    for p in paths:
        piece, c = read_file(p, heads[p.name.removesuffix('.jsonl.gz')], layout, per_task, seed)
        count += c
        if len(piece.sizes):
            pieces.append(piece)
    if not pieces:
        raise FitError('the files give no point with two ids and a positive id')
    total = sum(g.rows for g in pieces)
    drawn = joined_drawn(list(pieces))
    matrix = np.empty((total, len(layout.names)), np.float32)
    positive = np.empty(total, np.float32)
    sizes: list[Ints] = []
    tasks: list[str] = []
    at = 0
    while pieces:
        g = pieces.pop(0)
        matrix[at:at + g.rows] = g.matrix
        positive[at:at + g.rows] = g.positive
        sizes.append(g.sizes)
        tasks.extend(g.tasks)
        at += g.rows
    return Dense(positive, np.concatenate(sizes), len(layout.names), tasks, drawn, matrix=matrix), count


class PointReader:
    """Reads the kept points of a point file again whenever a pass over the rows needs them, and holds those of one file at a time."""

    def __init__(self, layout: Layout, per_task: int, seed: int):
        self.layout, self.per_task, self.seed = layout, per_task, seed
        self.held: tuple[Path, list[Kept], dict[int, Floats]] | None = None

    def points(self, path: Path, head: dict) -> tuple[list[Kept], dict[int, Floats]]:
        if self.held is None or self.held[0] != path:
            self.held = None  # free the points of the last file before the next file is read
            kept, tables, _ = kept_of(path, head, self.per_task, self.seed)
            self.held = (path, kept, tables)
        return self.held[1], self.held[2]

    def release(self) -> None:
        self.held = None


class PointRows(lgb.Sequence):
    """The rows of one file's kept points, as float64 rows that LightGBM reads one at a time (the sample for the bin bounds) or in batches (the push). The rows are built from the points on request."""
    batch_size = 4096

    def __init__(self, reader: PointReader, path: Path, head: dict, sizes: Ints):
        self.reader, self.path, self.head = reader, path, head
        self.ends = np.cumsum(sizes)
        self.begins = self.ends - sizes

    def __len__(self) -> int:
        return int(self.ends[-1])

    def __getitem__(self, idx: int | slice | list[int]) -> np.ndarray:
        kept, tables = self.reader.points(self.path, self.head)
        layout = self.reader.layout
        if isinstance(idx, (int, np.integer)):
            row = int(idx) + len(self) if idx < 0 else int(idx)
            idx = slice(row, row + 1)
            single = True
        elif isinstance(idx, slice):
            single = False
        else:
            raise TypeError(f'a PointRows is indexed by an integer or a slice, not {type(idx).__name__}')
        start, stop, _ = idx.indices(len(self))
        out = np.empty((max(stop - start, 0), len(layout.names)), np.float64)
        p = int(np.searchsorted(self.ends, start, side='right'))
        while p < len(kept) and self.begins[p] < stop:
            lo, hi = max(start, int(self.begins[p])), min(stop, int(self.ends[p]))
            fill_rows(out[lo - start:hi - start], kept[p], tables, layout, lo - int(self.begins[p]), hi - int(self.begins[p]))
            p += 1
        return out[0] if single else out


class SequenceDataset(lgb.Dataset):
    """A Dataset of Sequences. Dataset.get_params leaves out `seed` and `min_data_in_leaf`, which the sampling and the bin search of a Dataset of a matrix do use: `seed` sets the sampling seed
    (data_random_seed) and `min_data_in_leaf` sets the pre-filter of features. This adds them so that the bins equal those of the matrix."""

    def get_params(self) -> dict[str, Any]:
        params = super().get_params()
        return params | {k: v for k, v in (self.params or {}).items() if k in ('seed', 'min_data_in_leaf')}


def plan_rows(paths: list[Path], heads: dict[str, dict], layout: Layout, per_task: int, seed: int) -> tuple[Groups, list[PointRows], PointReader, Counter[str]]:
    """The groups of the files without their rows, and one PointRows per file that keeps a point. This pass reads each file to choose its points; the rows are read again later."""
    reader = PointReader(layout, per_task, seed)
    count: Counter[str] = Counter()
    rows: list[PointRows] = []
    positives: list[Floats] = []
    sizes: list[Ints] = []
    drawn: list[Groups] = []  # the drawn counts of each file, as pieces for joined_drawn
    tasks: list[str] = []
    for p in paths:
        head = heads[p.name.removesuffix('.jsonl.gz')]
        kept, _, c = kept_of(p, head, per_task, seed)
        count += c
        if not kept:
            continue
        positive, size, file_drawn = positive_of(kept)
        positives.append(positive)
        sizes.append(size)
        drawn.append(Groups(positive, size, 0, drawn=file_drawn))
        tasks.extend([head['task']] * len(size))
        rows.append(PointRows(reader, p, head, size))
    if not rows:
        raise FitError('the files give no point with two ids and a positive id')
    return Groups(np.concatenate(positives), np.concatenate(sizes), len(layout.names), tasks, joined_drawn(drawn)), rows, reader, count


def booster_names(names: list[str]) -> list[str]:
    """The names as LightGBM takes them: it refuses `:` and other JSON characters, so each is written as `_`. They must stay distinct."""
    safe = [SPECIAL.sub('_', n) for n in names]
    if len(set(safe)) != len(safe):
        raise FitError('two feature names are equal once their special characters are replaced')
    return safe


# ---------------------------------------------------------------- the check

def check(folder: Path, seed: int, alpha: float = 0.0) -> int:
    """Compare the gradient with a central finite difference of the loss on the real group with the most positive ids among those with some, but not all, ids positive. With alpha,
    the group is the one with the most drawn count among those, if one has a drawn count, and the loss has its denominator weights."""
    for p in sorted(point_folder(folder).glob('*.jsonl.gz')):
        head = header_of(p)
        if head['split'] not in ('train', 'dev'):
            continue
        groups, _ = read_file(p, head, layout_of(feature_fields([head])), 0, seed)
        pos_count = np.add.reduceat(groups.positive, groups.starts)
        usable = np.flatnonzero((pos_count > 0) & (pos_count < groups.sizes))
        if not len(usable):
            continue
        g = int(usable[np.argmax(pos_count[usable])])
        if alpha and groups.drawn is not None:
            drawn_count = np.add.reduceat(groups.drawn, groups.starts)
            if drawn_count[usable].max() > 0:
                g = int(usable[np.argmax(drawn_count[usable])])
        start, size = int(groups.starts[g]), int(groups.sizes[g])
        positive = groups.positive[start:start + size].astype(np.float64)
        starts, sizes = np.array([0], np.int64), np.array([size], np.int64)
        one = Groups(positive.astype(np.float32), sizes, groups.columns, drawn=None if groups.drawn is None else groups.drawn[start:start + size])
        objective = objective_of(one, alpha)
        weight = loss_weight(one, alpha)
        rng = np.random.default_rng(seed)
        worst = 0.0
        for scale in (0.1, 1.0, 5.0):
            s = rng.normal(0.0, scale, size)
            grad, hess = objective(s, None)
            step = 1e-6
            numeric = np.empty(size)
            for i in range(size):
                up, down = s.copy(), s.copy()
                up[i] += step
                down[i] -= step
                numeric[i] = (group_terms(up, positive, starts, sizes, weight).loss[0] - group_terms(down, positive, starts, sizes, weight).loss[0]) / (2 * step)
            worst = max(worst, float(np.abs(grad - numeric).max()))
        print(f'check: task {head["task"]} group {g} ids {size} positives {int(positive.sum())} drawn {0 if one.drawn is None else int(one.drawn.sum())} alpha {alpha} gradient vs finite difference, max |error| over 3 score draws = {worst:.3e}; '
              f'Hessian min {hess.min():.3e} max {hess.max():.3e}')
        return 0 if worst < 1e-6 else 1
    raise FitError(f'{folder}: no group with some, but not all, ids positive')


# ---------------------------------------------------------------- the fit

class Reporter:
    """LightGBM callback: keep the dev loss of every round and print it every `period` rounds."""
    order = 30
    before_iteration = False

    def __init__(self, period: int):
        self.period = period
        self.curve: list[float] = []

    def __call__(self, env: Any) -> None:
        loss = float(env.evaluation_result_list[0][2])
        self.curve.append(loss)
        if self.period > 0 and (env.iteration + 1) % self.period == 0:
            print(f'round {env.iteration + 1} dev loss {loss:.6f}', flush=True)


def code_commit() -> dict[str, Any]:
    """The commit of the repo that holds this file, and the paths under this file's folder that differ from it (empty where the code is the commit's)."""
    here = Path(__file__).resolve().parent
    def git(*a: str) -> str:
        return subprocess.run(['git', '-C', str(here), *a], capture_output=True, text=True, check=True).stdout.strip()
    return dict(sha=git('rev-parse', 'HEAD'), dirty=sorted(git('status', '--porcelain', '--', '.').splitlines()))


def peak_rss_mib() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1 << 20) if sys.platform == 'darwin' else peak / 1024


def fit(args: argparse.Namespace) -> int:
    t0, commit = time.time(), code_commit()  # the code as the fit starts; a commit during the fit does not change what it ran
    dev_tasks = set(args.dev_tasks.split(',')) if args.dev_tasks else set()
    train_files, dev_files, heads = split_files(args.points, dev_tasks)
    if not train_files or not dev_files:
        raise FitError(f'{len(train_files)} train files and {len(dev_files)} dev files: the fit needs both')
    fields = feature_fields([heads[p.name.removesuffix('.jsonl.gz')] for p in (*train_files, *dev_files)])
    layout = layout_of(fields)
    names = layout.names
    safe = booster_names(names)
    train, train_rows, reader, train_count = plan_rows(train_files, heads, layout, args.points_per_task, args.seed)
    dev, dev_count = load(dev_files, heads, layout, args.points_per_task, args.seed)
    sizes = dict(train=train.describe(), dev=dev.describe())
    for split, d in sizes.items():
        print(f'{split} matrix: {d["groups"]} points, {d["rows"]} rows x {d["columns"]} columns float32 = {d["matrix_bytes"] / (1 << 20):.1f} MiB, '
              f'{d["bytes_per_row"]} bytes per row with its positive mark, {d["ids_per_group"]} ids and {d["positives_per_group"]} positives per point, {d["tasks"]} tasks', flush=True)
    print(f'loaded in {time.time() - t0:.1f} s; points left out: train {dict(train_count)} dev {dict(dev_count)}', flush=True)

    params: dict[str, Any] = dict(num_leaves=args.num_leaves, learning_rate=args.learning_rate, min_data_in_leaf=args.min_data_in_leaf, feature_fraction=args.feature_fraction,
                                  seed=args.seed, num_threads=args.threads, verbosity=-1, metric='None')
    if args.alpha and (train.drawn is None or not train.drawn.any()):
        print(f'--alpha {args.alpha}: the train points have no drawn count, so the loss has no weight', flush=True)
    train_objective = objective_of(train, args.alpha)
    dev_starts, dev_sizes, dev_positive = dev.starts, dev.sizes, dev.positive.astype(np.float64)

    def dev_loss(scores: Floats, _data: Any) -> tuple[str, float, bool]:
        return 'dev_loss', float(group_terms(np.asarray(scores, np.float64), dev_positive, dev_starts, dev_sizes).loss.mean()), False

    train_set = SequenceDataset(train_rows, label=train.positive, feature_name=safe, params=dict(params, max_bin=255), free_raw_data=True)
    train_set.construct()
    reader.release()
    dev_set = lgb.Dataset(dev.matrix, label=dev.positive, reference=train_set, feature_name=safe, free_raw_data=False)
    reporter = Reporter(args.log_every)
    t1 = time.time()
    booster = lgb.train(dict(params, objective=train_objective), train_set, num_boost_round=args.rounds, valid_sets=[dev_set], valid_names=['dev'], feval=dev_loss,
                        callbacks=[reporter, lgb.early_stopping(args.early_stopping, first_metric_only=True, verbose=False)])
    best = booster.best_iteration or booster.current_iteration()
    print(f'fit: {booster.current_iteration()} rounds in {time.time() - t1:.1f} s, best round {best}, dev loss at best {reporter.curve[best - 1]:.6f}', flush=True)

    out: Path = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(out), num_iteration=best)
    scores = booster.predict(dev.matrix, num_iteration=best, raw_score=True)
    got, base = evaluate(np.asarray(scores), dev), uniform_baseline(dev)
    print(f'dev, trees:   mean loss {got["mean_loss"]:.6f}  top-scored id is positive {got["top_is_positive"]:.4f}  ({got["points"]} points)')
    print(f'dev, uniform: mean loss {base["mean_loss"]:.6f}  top-scored id is positive {base["top_is_positive"]:.4f}  (every id ties; credit shared)')
    report = dict(
        model=str(out), params=dict(params, objective='custom: -log(sum of softmax over the positive ids), per point', alpha=args.alpha), rounds_run=booster.current_iteration(), best_round=best,
        early_stopping_rounds=args.early_stopping, max_rounds=args.rounds, dev_loss_by_round=reporter.curve, dev=got, dev_uniform=base,
        points_per_task=args.points_per_task, seed=args.seed, dev_tasks_override=sorted(dev_tasks), points_dir=str(args.points), matrix=sizes,
        points_left_out=dict(train=dict(train_count), dev=dict(dev_count)), train_tasks=sorted(set(train.tasks)), dev_tasks=sorted(set(dev.tasks)),
        features=dict(uses_from_header=fields.get('uses') is not None, uses=names, booster_names=safe, header=fields), peak_rss_mib=round(peak_rss_mib(), 1), seconds=round(time.time() - t0, 1), code_commit=commit)
    Path(str(out) + '.json').write_text(json.dumps(report, indent=1))
    print(f'wrote {out} and {out}.json; peak RSS {peak_rss_mib():.0f} MiB')
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or '').split('\n')[0])
    ap.add_argument('--points', type=Path, required=True, help='the folder samples/SET/points/')
    ap.add_argument('--out', type=Path, help='the file of the saved booster')
    ap.add_argument('--check', action='store_true', help='check the gradient against a finite difference on one real group, then stop')
    ap.add_argument('--points-per-task', type=int, default=0, help='at most N points of a task, chosen by a seeded hash (0: all)')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--dev-tasks', help='comma-separated tasks to treat as dev, whatever their header says (development only)')
    ap.add_argument('--alpha', type=float, default=0.0, help='the train loss weighs each id in the softmax denominator by 1 + alpha * drawn (0: no weight)')
    ap.add_argument('--rounds', type=int, default=2000)
    ap.add_argument('--early-stopping', type=int, default=50, help='stop after this many rounds without a better dev loss')
    ap.add_argument('--log-every', type=int, default=50)
    ap.add_argument('--num-leaves', type=int, default=63)
    ap.add_argument('--learning-rate', type=float, default=0.05)
    ap.add_argument('--min-data-in-leaf', type=int, default=100)
    ap.add_argument('--feature-fraction', type=float, default=0.8)
    ap.add_argument('--threads', type=int, default=int(os.environ.get('ARC_HEAVY_CPUS', '1')))
    args = ap.parse_args()
    try:
        if args.check:
            return check(args.points, args.seed, args.alpha)
        if args.out is None:
            ap.error('--out is required unless --check')
        return fit(args)
    except FitError as e:
        print(f'error: {e}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
