"""The fit of the gradient-boosted trees over the training rows (stage 5 of the sample build writes them, points_write.py).

  python3 fit_trees.py --points DIR --out PATH [--points-per-task N] [--seed S] [--dev-tasks T,T] [--alpha A] [--rounds R] ...
  python3 fit_trees.py --points DIR --check [--alpha A]

DIR is `samples/SET/points/`. The point files of train tasks give the fit and those of dev tasks give the evaluation, by the split in each file's header. A file whose header split is
held-out (or `held`, its name in older files) is an error, and so is a DIR below `points_held-out` or `points_held`. The tasks of split.OUT_OF_SCOPE are left
out of the fit and of --score, and the report's `out_of_scope` names them. --dev-tasks names tasks to treat as dev whatever their header says (for development on a small set; held-out stays an error).
Where no file is dev, the fit runs exactly --rounds rounds, which must then be given, and it evaluates nothing.
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

--out is the file of `booster.save_model`. Beside it, `<out>.json` holds the params, the evaluation, the matrix sizes, the feature names, the header fields that define the features, and
`plan`, the writer plan of the point files (their header's `plan`), which serving reads (sampler/writer_plan.py). The point files must all give one plan.

The point files must all carry the same header fields that define the features. --wheels-alike W,W names engine wheels (header `wheel`, such as site-exp61,site-exp62) whose point
files are equal where both build a task, so that files of those wheels go in one fit. The report's `wheel` is then the sorted list of the wheels of the files. A fit with
--wheels-alike needs --wheels-alike-check, the JSON files of run/points_alike.py that show the equality: each with no differing task, and together naming every wheel of
--wheels-alike. The report's `wheels_alike` holds those files.

With --shapes N (default 900; 0 leaves them out), the point files' `shapes` records (one per table: hashes and least, mean, most of its shapes) and `tok_tables` records (one per sample: the tables of each
token) add columns after the others: for chosen shapes, the rank and the median-difference form of a point's table tokens' values (shape_rel.py, which holds the choice and the column fill and which
serving calls too). The choice reads the train files alone; the model's `uses` hold the column names, and `<out>.shapes.json` holds the chosen shapes. Files with no such records add no column.
"""
import argparse
import base64
import gzip
import io
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
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterator

import lightgbm as lgb
import numpy as np
import zstandard

import shape_rel as SR
from split import OUT_OF_SCOPE, is_held_out, out_of_scope

HELD_FOLDERS = ('points_held-out', 'points_held')  # the folder name, and the one that earlier runs wrote
FEATURE_FIELDS = ('schema', 'extractor_sha', 'writer_sha', 'wheel', 'point_names', 'option_names', 'table_names', 'uses', 'vector_names', 'vector_point_cols')
HESSIAN_FLOOR = 1e-6
SPECIAL = re.compile(r'[\s",:\[\]{}]')  # the characters that LightGBM refuses in a feature name
type Floats = np.ndarray
type Ints = np.ndarray




def points_stem(path):
    """The task of a points file, written as streamable zstd or, for an older file, gzip."""
    return path.name.split('.jsonl')[0]


def open_points(path):
    """The lines of a points file, in either form."""
    if path.suffix == '.zst':
        return io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(open(path, 'rb'), read_across_frames=True), encoding='utf-8')
    return gzip.open(path, 'rt')

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
    weights: Floats | None = None  # (groups,) float64: each point's `weight` (1 where it has none); None where no point has one

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


def task_weight(groups: Groups) -> Floats:
    """The weight of each row under --task-weights: 1 over its task's count of groups, scaled so that the mean group weight is 1. Each task then weighs the same in
    the loss, as a cap of points per task would make it, and no point is left out."""
    tasks = np.asarray(groups.tasks)
    names, at, counts = np.unique(tasks, return_inverse=True, return_counts=True)
    w = (len(tasks) / len(names)) / counts[at].astype(np.float64)
    return np.repeat(w, groups.sizes)


def objective_of(groups: Groups, alpha: float = 0.0, task_weights: bool = False) -> Callable[[Floats, Any], tuple[Floats, Floats]]:
    """The custom objective of LightGBM over a set of groups: (gradient, Hessian) of the summed group losses, with the denominator weights of alpha, and with
    task_weights each group's loss weighed by task_weight."""
    starts, sizes, positive = groups.starts, groups.sizes, groups.positive.astype(np.float64)
    weight = loss_weight(groups, alpha)
    rows = task_weight(groups) if task_weights else None
    if groups.weights is not None:  # each point's own weight, as a kind point's share of its state's targets
        own = np.repeat(groups.weights, groups.sizes)
        rows = own if rows is None else rows * own

    def objective(scores: Floats, _data: Any) -> tuple[Floats, Floats]:
        t = group_terms(np.asarray(scores, np.float64), positive, starts, sizes, weight)
        g, h = t.p - t.q, np.maximum(t.p * (1.0 - t.p), HESSIAN_FLOOR)
        return (g, h) if rows is None else (g * rows, h * rows)
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
    with open_points(path) as f:
        for text in f:
            yield json.loads(text)


def header_of(path: Path) -> dict:
    try:
        first = next(records_of(path), None)
    except (OSError, EOFError, ValueError) as e:
        raise FitError(f'{path}: unreadable: {e}') from e
    if not first or first.get('record') != 'header':
        raise FitError(f'{path}: the first record is not a header')
    if points_stem(path) != first['task']:
        raise FitError(f'{path}: the header names task {first["task"]}')
    return first


def point_folder(folder: Path) -> Path:
    if any(name in folder.resolve().parts for name in HELD_FOLDERS):
        raise FitError(f'{folder}: a fit never reads {" or ".join(HELD_FOLDERS)}')
    if not folder.is_dir():
        raise FitError(f'{folder}: not a folder')
    return folder


def split_files(folders: list[Path], dev_tasks: set[str]) -> tuple[list[Path], list[Path], dict[str, dict]]:
    """(train files, dev files, the header of each task) of the folders, by the split in each header; --dev-tasks moves tasks to dev. A header split other than train or dev is an error.
    A task of split.out_of_scope() is left out."""
    skip = out_of_scope()
    paths = sorted((p for folder in folders for p in point_folder(folder).glob('*.jsonl.*') if points_stem(p) not in skip), key=lambda p: p.name)
    heads = {points_stem(p): header_of(p) for p in paths}
    unknown = dev_tasks - heads.keys()
    if unknown:
        raise FitError(f'--dev-tasks names tasks with no file in {", ".join(map(str, folders))}: {sorted(unknown)}')
    train: list[Path] = []
    dev: list[Path] = []
    for p in paths:
        task = points_stem(p)
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
    keep: Ints | None = None  # with vectors and --drop-prefixes: the columns of the whole vector that the matrix keeps, in order; vector_*_cols are columns of the whole vector
    width: int = 0  # with keep: the whole vector's width
    shapes: SR.Spec | None = None  # --shapes: the shape columns, which are the last columns of `names`


DROP_KINDS: frozenset[str] = frozenset()  # --drop-point-kinds: the point kinds (a point's `kind`, such as KIND) that the fit and the evaluation leave out
TABLE_CHOICE = False  # --table-choice: only the points where two or more ids name a table (the vector's tokg:table is not 0) are kept
TABLE_RANKER = False  # --table-ranker: only the points where two or more ids name a table and a positive names one; each keeps its table ids alone, and its positives among them
WRITERS_ALIKE: frozenset[str] = frozenset()  # --writers-alike: writer_sha values whose point files are equal, as a change of the writer's serving code alone leaves them
DROP: tuple[str, ...] = ()  # --drop-prefixes: the vector columns whose names start with one of these are left out of the matrix and the model
DROP_NAMES: frozenset[str] = frozenset()  # --drop-names: the vector columns with exactly these names are left out too


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
        ids = np.setdiff1d(np.arange(len(names), dtype=np.int64), point)
        if DROP or DROP_NAMES:
            keep = np.array([i for i, n in enumerate(names) if not (DROP and n.startswith(DROP)) and n not in DROP_NAMES], np.int64)
            return Layout([names[i] for i in keep], empty, empty, empty, point, ids, keep, len(names))
        return Layout(names, empty, empty, empty, point, ids)
    parts = [*fields['option_names'], *fields['table_names'], *fields['point_names']]
    if len(set(parts)) != len(parts):
        raise FitError('a feature name appears twice in the header')
    names = list(fields['uses']) if fields.get('uses') is not None else parts
    if sorted(names) != sorted(parts):
        raise FitError('the header\'s uses are not the option, table and point names')
    at = {n: i for i, n in enumerate(names)}
    option, table, point = (np.array([at[n] for n in fields[k]], np.int64) for k in ('option_names', 'table_names', 'point_names'))
    return Layout(names, option, table, point)


def alike_checks(args: argparse.Namespace) -> list[dict]:
    """The points_alike.py files of --wheels-alike-check, which must show that the wheels of --wheels-alike give equal points."""
    wheels = set(filter(None, args.wheels_alike.split(',')))
    if not wheels:
        return []
    checks = [json.loads(Path(f).read_text()) for f in args.wheels_alike_check]
    for f, c in zip(args.wheels_alike_check, checks):
        if c.get('differ') or not c.get('tasks'):
            raise FitError(f'{f}: {len(c.get("differ") or {})} tasks differ, {len(c.get("tasks") or [])} compared')
    shown = {w for c in checks for w in c.get('wheels', [])}
    if not wheels <= shown:
        raise FitError(f'--wheels-alike {sorted(wheels)}: no --wheels-alike-check file names {sorted(wheels - shown)}')
    return checks


def feature_fields(heads: list[dict], wheels_alike: frozenset[str] = frozenset()) -> dict[str, Any]:
    """The header fields that define the features; every file must carry the same ones, with the wheels of wheels_alike taken as one wheel."""
    if not heads:
        raise FitError('no point files')

    def of(h: dict) -> dict[str, Any]:
        return {k: ('alike' if (k == 'wheel' and h.get(k) in wheels_alike) or (k == 'writer_sha' and h.get(k) in WRITERS_ALIKE) else h.get(k)) for k in FEATURE_FIELDS}
    fields = of(heads[0])
    for h in heads[1:]:
        other = of(h)
        if other != fields:
            differ = [k for k in FEATURE_FIELDS if other[k] != fields[k]]
            raise FitError(f'the files of tasks {heads[0]["task"]} and {h["task"]} differ in {differ}')
    wheels = sorted({h.get('wheel') for h in heads})
    return fields | dict(wheel=wheels[0] if len(wheels) == 1 else wheels)


def plan_of(heads: list[dict]) -> str | None:
    """The writer plan of the point files: their header's `plan`, the same in every file."""
    plans = {h.get('plan') for h in heads}
    if len(plans) > 1:
        raise FitError(f'the point files give the plans {sorted(map(str, plans))}')
    return next(iter(plans), None)


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
    weight: float | None = None  # the point's `weight`, where it has one: the share of a state's targets that a kind point stands for (points_write.write_kind_point)
    shape_at: Ints | None = None  # with shapes: the index in the point's ids of each table token (an id with an entry in its sample's `tok_tables`); None where the file has no `tok_tables` for the sample
    shape_tables: list | None = None  # with shape_at: each table token's shape record (hashes, values, stopped), combined over its tables (shape_rel.combine)


def choice_key(seed: int, sample: str, position: int) -> int:
    return int.from_bytes(hashlib.sha256(f'{seed}:{sample}:{position}'.encode()).digest()[:8], 'big')


def kept_of(path: Path, head: dict, per_task: int, seed: int, shapes: bool = False) -> tuple[list[Kept], dict[int, Floats], Counter[str]]:
    """The kept points of one file in file order, the table vectors by index, and the counts. Points with fewer than two ids or with no positive id are counted and left out. With per_task > 0 the
    points with the smallest hash keys are kept. With shapes, the file's `shapes` records (one per table: its shapes' hashes and values) and `tok_tables` records (one per sample: the tables of each of
    its tokens) give each kept point its table tokens' records (Kept.shape_at, Kept.shape_tables), wherever the records stand in the file."""
    n_option, n_table, n_point = len(head['option_names']), len(head['table_names']), len(head['point_names'])
    is_vector = head.get('vector_names') is not None
    n_vp = len(head.get('vector_point_cols') or [])
    n_vo = len(head["vector_names"]) - n_vp if is_vector else 0
    tables: dict[int, Floats] = {}
    kept: list[tuple[int, int, Kept]] = []  # a heap of (-key, position, point) where per_task > 0
    count: Counter[str] = Counter()
    table_at = None
    shape_of: dict[str, tuple] = {}  # table hash -> (hashes, values, stopped)
    token_tables: dict[str, dict] = {}  # sample -> {token: [table hash, ...]}
    ids_of: dict[int, tuple[str, Ints]] = {}  # file position -> (sample, ids) of the points that may be kept, where shapes
    if TABLE_CHOICE or TABLE_RANKER:
        if not is_vector:
            raise FitError(f'{path}: --table-choice and --table-ranker read the vector column tokg:table, and the file holds no vectors')
        in_point = set(head.get('vector_point_cols') or [])
        table_at = [name for at, name in enumerate(head['vector_names']) if at not in in_point].index('tokg:table')
    for position, rec in enumerate(records_of(path)):
        kind = rec['record']
        if kind == 'table':
            vector = np.array(rec['values'], np.float32)
            if vector.shape != (n_table,):
                raise FitError(f'{path}: table {rec["i"]} has {vector.shape} values; the header names {n_table}')
            tables[int(rec['i'])] = vector
        elif kind == 'shapes' and shapes:
            try:
                shape_of[rec['table']] = SR.decode(rec['h'], rec['v'], rec.get('stopped', False))
            except ValueError as e:
                raise FitError(f'{path}: the shapes record of table {rec["table"]}: {e}') from e
        elif kind == 'tok_tables' and shapes:
            token_tables[rec['sample']] = rec['map']
        elif kind == 'point':
            count['points'] += 1
            n = len(rec['ids'])
            if is_vector:
                vp_bytes, vo_bytes = base64.b64decode(rec['vp']), base64.b64decode(rec['vo'])
                if len(vp_bytes) != 4 * n_vp or len(vo_bytes) != 4 * n * n_vo:
                    raise FitError(f'{path}: the point at record {position} has parts of different sizes')
            elif len(rec['option']) != n or len(rec['table']) != n or len(rec['point']) != n_point:
                raise FitError(f'{path}: the point at record {position} has parts of different sizes')
            if rec.get('kind') in DROP_KINDS:
                count['points of a left-out kind'] += 1
                continue
            # A point left out keeps its position, so the choice keys of the others do not move.
            if table_at is not None and np.count_nonzero(np.frombuffer(vo_bytes, '<f4').reshape(n, n_vo)[:, table_at]) < 2:
                count['points with fewer than two table ids'] += 1
                continue
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
            positive = np.array(rec['positive'], np.int64)
            ids = np.array(rec['ids'], np.int64) if shapes else None
            vo = None
            if TABLE_RANKER and is_vector:
                vo = np.frombuffer(vo_bytes, '<f4').astype(np.float32).reshape(n, n_vo)
                is_table = vo[:, table_at] != 0
                if np.count_nonzero(is_table) < 2:
                    count['points with fewer than two table ids'] += 1
                    continue
                if not is_table[positive].any():
                    count['points where no positive names a table'] += 1
                    continue
                sel = np.flatnonzero(is_table)
                at = {int(j): k for k, j in enumerate(sel)}
                positive = np.array(sorted(at[int(i)] for i in positive if int(i) in at), np.int64)
                vo, n = vo[sel], len(sel)
                ids = ids[sel] if ids is not None else None
                drawn = drawn[sel] if drawn is not None else None
            key = choice_key(seed, rec['sample'], position)
            if per_task > 0 and len(kept) >= per_task and -kept[0][0] <= key:
                continue
            if is_vector:
                if vo is None:
                    vo = np.frombuffer(vo_bytes, '<f4').astype(np.float32).reshape(n, n_vo)
                got = Kept(np.zeros((n, 0), np.float32), np.zeros(0, np.int64), np.zeros(0, np.float32), positive, n,
                           np.frombuffer(vp_bytes, '<f4').astype(np.float32), vo, drawn)
            else:
                got = Kept(np.array(rec['option'], np.float32).reshape(n, n_option), np.array(rec['table'], np.int64),
                           np.array(rec['point'], np.float32), np.array(rec['positive'], np.int64), n, drawn=drawn)
            if 'weight' in rec:
                got.weight = float(rec['weight'])
            if ids is not None:
                ids_of[position] = (rec['sample'], ids)
            if per_task > 0 and len(kept) >= per_task:
                heapq.heapreplace(kept, (-key, position, got))
            elif per_task > 0:
                heapq.heappush(kept, (-key, position, got))
            else:
                kept.append((-key, position, got))
    count['points kept'] = len(kept)
    kept.sort(key=lambda k: k[1])
    if shapes and token_tables:
        combined: dict[tuple, tuple] = {}  # a token's tables -> its combined record (a table that is stopped makes it stopped: NaN in every shape)
        for _, position, got in kept:
            sample, ids = ids_of[position]
            by_token = token_tables.get(sample)
            if by_token is None:
                continue
            at, recs = [], []
            for i, tok in enumerate(ids.tolist()):
                tabs = by_token.get(str(tok))
                if tabs is None:
                    continue
                key = tuple(tabs)
                if key not in combined:
                    missing = [t for t in key if t not in shape_of]
                    if missing:
                        raise FitError(f'{path}: sample {sample} token {tok} has tables {missing[:3]} that no shapes record gives')
                    combined[key] = SR.combine(shape_of[t] for t in key)
                at.append(i)
                recs.append(combined[key])
            got.shape_at, got.shape_tables = np.array(at, np.int64), recs
    return [k for _, _, k in kept], tables, count


_SHAPE_LAST: list = [None, None, None]  # the point, the spec and the matrix of the last shape_matrix; rows are read point by point, so a point's matrix is made once


def shape_matrix(k: Kept, spec: SR.Spec) -> Floats:
    """The shape columns of the point k's table tokens (SR.columns)."""
    if _SHAPE_LAST[0] is not k or _SHAPE_LAST[1] is not spec:
        _SHAPE_LAST[:] = [k, spec, SR.columns(k.shape_tables or [], spec)]
    return _SHAPE_LAST[2]


def fill_shapes(out: Floats, k: Kept, spec: SR.Spec, lo: int, hi: int) -> None:
    """Write the shape columns of rows lo to hi of the point k into out: NaN on ids that are not table tokens, and on every id where the point has fewer than 2 table tokens."""
    out[:] = np.nan
    if k.shape_at is None or len(k.shape_at) < 2:
        return
    sel = (k.shape_at >= lo) & (k.shape_at < hi)
    out[k.shape_at[sel] - lo] = shape_matrix(k, spec)[sel]


def fill_rows(out: Floats, k: Kept, tables: dict[int, Floats], layout: Layout, lo: int, hi: int) -> None:
    """Write rows lo to hi of the point k into out, which has hi - lo rows."""
    if layout.shapes is not None:
        base = len(layout.names) - len(layout.shapes.names)
        fill_shapes(out[:, base:], k, layout.shapes, lo, hi)
        out = out[:, :base]
    if layout.vector_id_cols is not None and layout.vector_point_cols is not None and k.vo is not None and k.vp is not None:
        if layout.keep is not None:  # --drop-prefixes: the whole vector, then the kept columns
            whole = np.empty((hi - lo, layout.width), out.dtype)
            whole[:, layout.vector_id_cols] = k.vo[lo:hi]
            whole[:, layout.vector_point_cols] = k.vp
            out[:] = whole[:, layout.keep]
            return
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


def weights_of(kept: list[Kept]) -> Floats | None:
    """The weight of each point, 1 where it has none; None where no point has one."""
    if all(k.weight is None for k in kept):
        return None
    return np.array([1.0 if k.weight is None else k.weight for k in kept], np.float64)


def joined_weights(pieces: list[Groups]) -> Floats | None:
    """The weights of the pieces' groups in one array, 1 for a piece with none; None where no piece has any."""
    if all(g.weights is None for g in pieces):
        return None
    return np.concatenate([g.weights if g.weights is not None else np.ones(len(g.sizes)) for g in pieces])


def joined_drawn(pieces: list[Groups]) -> Floats | None:
    """The drawn counts of the pieces' rows in one array, 0 for a piece with none; None where no piece has any."""
    if all(g.drawn is None for g in pieces):
        return None
    return np.concatenate([g.drawn if g.drawn is not None else np.zeros(g.rows, np.float32) for g in pieces])


def read_file(path: Path, head: dict, layout: Layout, per_task: int, seed: int) -> tuple[Dense, Counter[str]]:
    """The groups of one file, with their rows in one matrix."""
    kept, tables, count = kept_of(path, head, per_task, seed, layout.shapes is not None)
    positive, sizes, drawn = positive_of(kept)
    matrix = np.empty((len(positive), len(layout.names)), np.float32)
    at = 0
    for k in kept:
        end = at + k.size
        fill_rows(matrix[at:end], k, tables, layout, 0, k.size)
        at = end
    return Dense(positive, sizes, len(layout.names), [head['task']] * len(sizes), drawn, weights_of(kept), matrix=matrix), count


def load(paths: list[Path], heads: dict[str, dict], layout: Layout, per_task: int, seed: int) -> tuple[Dense, Counter[str]]:
    """The groups of the files, in one matrix. The pieces are copied in one by one so that the peak is the matrix and one piece."""
    pieces: list[Dense] = []
    count: Counter[str] = Counter()
    for p in paths:
        piece, c = read_file(p, heads[points_stem(p)], layout, per_task, seed)
        count += c
        if len(piece.sizes):
            pieces.append(piece)
    if not pieces:
        raise FitError('the files give no point with two ids and a positive id')
    total = sum(g.rows for g in pieces)
    drawn, weights = joined_drawn(list(pieces)), joined_weights(list(pieces))
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
    return Dense(positive, np.concatenate(sizes), len(layout.names), tasks, drawn, weights, matrix=matrix), count


class PointReader:
    """Reads the kept points of a point file again whenever a pass over the rows needs them, and holds those of one file at a time."""

    def __init__(self, layout: Layout, per_task: int, seed: int):
        self.layout, self.per_task, self.seed = layout, per_task, seed
        self.held: tuple[Path, list[Kept], dict[int, Floats]] | None = None

    def points(self, path: Path, head: dict) -> tuple[list[Kept], dict[int, Floats]]:
        if self.held is None or self.held[0] != path:
            self.held = None  # free the points of the last file before the next file is read
            kept, tables, _ = kept_of(path, head, self.per_task, self.seed, self.layout.shapes is not None)
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


def plan_rows(paths: list[Path], heads: dict[str, dict], layout: Layout, per_task: int, seed: int, counts: SR.ShapeCounts | None = None) -> tuple[Groups, list[PointRows], PointReader, Counter[str]]:
    """The groups of the files without their rows, and one PointRows per file that keeps a point. This pass reads each file to choose its points; the rows are read again later. With counts, the
    table tokens' shape records of the kept points are added to it."""
    reader = PointReader(layout, per_task, seed)
    count: Counter[str] = Counter()
    rows: list[PointRows] = []
    positives: list[Floats] = []
    sizes: list[Ints] = []
    drawn: list[Groups] = []  # the drawn counts of each file, as pieces for joined_drawn
    tasks: list[str] = []
    for p in paths:
        head = heads[points_stem(p)]
        kept, _, c = kept_of(p, head, per_task, seed, counts is not None)
        count += c
        if counts is not None:
            counts.add_file(k.shape_tables for k in kept if k.shape_tables is not None)
        if not kept:
            continue
        positive, size, file_drawn = positive_of(kept)
        positives.append(positive)
        sizes.append(size)
        drawn.append(Groups(positive, size, 0, drawn=file_drawn, weights=weights_of(kept)))
        tasks.extend([head['task']] * len(size))
        rows.append(PointRows(reader, p, head, size))
    if not rows:
        raise FitError('the files give no point with two ids and a positive id')
    return Groups(np.concatenate(positives), np.concatenate(sizes), len(layout.names), tasks, joined_drawn(drawn), joined_weights(drawn)), rows, reader, count


def booster_names(names: list[str]) -> list[str]:
    """The names as LightGBM takes them: it refuses `:` and other JSON characters, so each is written as `_`. They must stay distinct."""
    safe = [SPECIAL.sub('_', n) for n in names]
    if len(set(safe)) != len(safe):
        raise FitError('two feature names are equal once their special characters are replaced')
    return safe


# ---------------------------------------------------------------- the shape columns

def with_shapes(layout: Layout, spec: SR.Spec) -> Layout:
    """The layout with the spec's columns after the others."""
    return replace(layout, names=[*layout.names, *spec.names], shapes=spec)


def merge_shapes(spec: SR.Spec, files: list[Path], heads: dict[str, dict], layout: Layout, per_task: int, seed: int) -> tuple[SR.Spec | None, dict[str, str]]:
    """One pass over the training files: the spec without the columns that equal an earlier column on every kept training point with 2 or more table tokens, and the dropped names with the
    names that stand for them."""
    hashed = SR.ColumnHash(len(spec.names))
    for p in files:
        kept, _, _ = kept_of(p, heads[points_stem(p)], per_task, seed, True)
        for k in kept:
            if k.shape_tables is not None and len(k.shape_tables) >= 2:
                hashed.add(SR.columns(k.shape_tables, spec))
    return hashed.merged(spec) if hashed.rows else (spec, {})


def shape_sidecar(spec: SR.Spec, merged: dict[str, str], info: dict, encoder_commit: str | None) -> dict[str, Any]:
    """The kept shapes with their text (arclog.shape_text where arclog imports, else None), their columns, the columns merged into others, and the commit of the encoder."""
    try:
        from arclog import shape_text  # type: ignore[import-not-found]
    except ImportError:
        shape_text = None
    by_hash: dict[str, list[str]] = {}
    for n in spec.names:
        by_hash.setdefault(SR.NAME.fullmatch(n).group(2), []).append(n)  # type: ignore[union-attr]
    shapes = [dict(hash=h, text=shape_text(int(h, 16)) if shape_text else None, columns=cols) for h, cols in by_hash.items()]
    return dict(encoder_commit=encoder_commit, selection=info, shapes=shapes, merged_into=merged)


# ---------------------------------------------------------------- the check

def check(folder: Path, seed: int, alpha: float = 0.0) -> int:
    """Compare the gradient with a central finite difference of the loss on the real group with the most positive ids among those with some, but not all, ids positive. With alpha,
    the group is the one with the most drawn count among those, if one has a drawn count, and the loss has its denominator weights."""
    for p in sorted(point_folder(folder).glob('*.jsonl.*')):
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

class Progress:
    """LightGBM callback of a fit with no dev files: print the round, the seconds so far and the ETA every `period` rounds of `rounds`."""
    order = 30
    before_iteration = False

    def __init__(self, period: int, rounds: int):
        self.period, self.rounds, self.t0 = period, rounds, time.time()

    def __call__(self, env: Any) -> None:
        k = env.iteration + 1
        if self.period > 0 and k % self.period == 0:
            el = time.time() - self.t0
            print(f'round {k} of {self.rounds}, {el:.0f} s, ETA {el / k * (self.rounds - k):.0f} s', flush=True)


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
    alike = alike_checks(args)
    train_files, dev_files, heads = split_files(args.points, dev_tasks)
    if not train_files:
        raise FitError('no train files: the fit needs some')
    if not dev_files and args.rounds is None:
        raise FitError('no dev files: the fit then runs a fixed count of rounds, which --rounds gives')
    rounds = args.rounds if args.rounds is not None else 2000
    fields = feature_fields([heads[points_stem(p)] for p in (*train_files, *dev_files)], frozenset(filter(None, args.wheels_alike.split(','))))
    plan = plan_of([heads[points_stem(p)] for p in (*train_files, *dev_files)])
    layout = layout_of(fields)
    counts = SR.ShapeCounts() if args.shapes > 0 else None
    train, train_rows, reader, train_count = plan_rows(train_files, heads, layout, args.points_per_task, args.seed, counts)
    shapes_report: dict[str, Any] | None = None
    sidecar: dict[str, Any] = {}
    if counts is not None:
        spec, info = SR.kept_spec(counts, args.shapes)
        merged: dict[str, str] = {}
        if spec is not None:
            before = len(spec.names)
            spec, merged = merge_shapes(spec, train_files, heads, layout, args.points_per_task, args.seed)
            assert spec is not None
            layout = with_shapes(layout, spec)
            reader.layout = layout
            train.columns = len(layout.names)
            info |= dict(columns_before_merge=before, columns=len(spec.names))
            commits = {heads[points_stem(p)].get('encoder_commit') for p in train_files}
            shapes_report = dict(info, sidecar=str(args.out) + '.shapes.json')
            sidecar = shape_sidecar(spec, merged, info, commits.pop() if len(commits) == 1 else None)
        print(f'shapes: {info}', flush=True)
    names = layout.names
    safe = booster_names(names)
    dev, dev_count = load(dev_files, heads, layout, args.points_per_task, args.seed) if dev_files else (None, Counter())
    sizes = dict(train=train.describe(), **({} if dev is None else dict(dev=dev.describe())))
    for split, d in sizes.items():
        print(f'{split} matrix: {d["groups"]} points, {d["rows"]} rows x {d["columns"]} columns float32 = {d["matrix_bytes"] / (1 << 20):.1f} MiB, '
              f'{d["bytes_per_row"]} bytes per row with its positive mark, {d["ids_per_group"]} ids and {d["positives_per_group"]} positives per point, {d["tasks"]} tasks', flush=True)
    print(f'loaded in {time.time() - t0:.1f} s; points left out: train {dict(train_count)} dev {dict(dev_count)}', flush=True)

    params: dict[str, Any] = dict(num_leaves=args.num_leaves, learning_rate=args.learning_rate, min_data_in_leaf=args.min_data_in_leaf, min_sum_hessian_in_leaf=args.min_sum_hessian,
                                  feature_fraction=args.feature_fraction, seed=args.seed, num_threads=args.threads, verbosity=-1, metric='None')
    if args.alpha and (train.drawn is None or not train.drawn.any()):
        print(f'--alpha {args.alpha}: the train points have no drawn count, so the loss has no weight', flush=True)
    train_objective = objective_of(train, args.alpha, args.task_weights)
    train_set = SequenceDataset(train_rows, label=train.positive, feature_name=safe, params=dict(params, max_bin=255), free_raw_data=True)
    train_set.construct()
    reader.release()
    t1 = time.time()
    curve: list[float] = []
    if dev is None:  # no dev files: exactly --rounds rounds, and no evaluation
        booster = lgb.train(dict(params, objective=train_objective), train_set, num_boost_round=rounds, callbacks=[Progress(args.log_every, rounds)])
        best = booster.current_iteration()
        print(f'fit: {best} rounds in {time.time() - t1:.1f} s, no dev files', flush=True)
    else:
        dev_starts, dev_sizes, dev_positive = dev.starts, dev.sizes, dev.positive.astype(np.float64)

        def dev_loss(scores: Floats, _data: Any) -> tuple[str, float, bool]:
            return 'dev_loss', float(group_terms(np.asarray(scores, np.float64), dev_positive, dev_starts, dev_sizes).loss.mean()), False

        dev_set = lgb.Dataset(dev.matrix, label=dev.positive, reference=train_set, feature_name=safe, free_raw_data=False)
        reporter = Reporter(args.log_every)
        booster = lgb.train(dict(params, objective=train_objective), train_set, num_boost_round=rounds, valid_sets=[dev_set], valid_names=['dev'], feval=dev_loss,
                            callbacks=[reporter, lgb.early_stopping(args.early_stopping, first_metric_only=True, verbose=False)])
        best = booster.best_iteration or booster.current_iteration()
        curve = reporter.curve
        print(f'fit: {booster.current_iteration()} rounds in {time.time() - t1:.1f} s, best round {best}, dev loss at best {curve[best - 1]:.6f}', flush=True)

    out: Path = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(out), num_iteration=best)
    if shapes_report is not None:
        Path(str(out) + '.shapes.json').write_text(json.dumps(sidecar, indent=1))
    got = base = None
    if dev is not None:
        scores = booster.predict(dev.matrix, num_iteration=best, raw_score=True)
        got, base = evaluate(np.asarray(scores), dev), uniform_baseline(dev)
        print(f'dev, trees:   mean loss {got["mean_loss"]:.6f}  top-scored id is positive {got["top_is_positive"]:.4f}  ({got["points"]} points)')
        print(f'dev, uniform: mean loss {base["mean_loss"]:.6f}  top-scored id is positive {base["top_is_positive"]:.4f}  (every id ties; credit shared)')
    report = dict(
        model=str(out), plan=plan, params=dict(params, objective='custom: -log(sum of softmax over the positive ids), per point', alpha=args.alpha), rounds_run=booster.current_iteration(), best_round=best,
        early_stopping_rounds=None if dev is None else args.early_stopping, max_rounds=rounds, dev_loss_by_round=curve, dev=got, dev_uniform=base,
        points_per_task=args.points_per_task, seed=args.seed, dev_tasks_override=sorted(dev_tasks), points_dir=[str(f) for f in args.points], matrix=sizes,
        points_left_out=dict(train=dict(train_count), dev=dict(dev_count)), train_tasks=sorted(set(train.tasks)), dev_tasks=[] if dev is None else sorted(set(dev.tasks)),
        features=dict(uses_from_header=fields.get('uses') is not None, uses=names, booster_names=safe, header=fields), wheels_alike=alike, out_of_scope=dict(file=str(OUT_OF_SCOPE), tasks=out_of_scope()), shapes=shapes_report, peak_rss_mib=round(peak_rss_mib(), 1), seconds=round(time.time() - t0, 1), code_commit=commit)
    Path(str(out) + '.json').write_text(json.dumps(report, indent=1))
    print(f'wrote {out} and {out}.json; peak RSS {peak_rss_mib():.0f} MiB')
    return 0


def score(args: argparse.Namespace) -> int:
    """Scores the saved booster --score on the dev files of --points, or on the tasks of --score-tasks among them, as the fit scores its dev points."""
    _, dev_files, heads = split_files(args.points, set())
    if args.score_tasks:
        want = set(args.score_tasks.split(','))
        dev_files = [p for p in dev_files if points_stem(p) in want]
    fields = feature_fields([heads[points_stem(p)] for p in dev_files], frozenset(filter(None, args.wheels_alike.split(','))))
    layout = layout_of(fields)
    meta = Path(str(args.score) + '.json')
    spec = SR.Spec.of_names(json.loads(meta.read_text())['features']['uses']) if meta.exists() else None  # a model with shape columns reads them from its own names
    if spec is not None:
        layout = with_shapes(layout, spec)
    dev, _ = load(dev_files, heads, layout, args.points_per_task, args.seed)
    booster = lgb.Booster(model_file=str(args.score))
    got, base = evaluate(np.asarray(booster.predict(dev.matrix, raw_score=True)), dev), uniform_baseline(dev)
    print(f'dev, trees:   mean loss {got["mean_loss"]:.6f}  top-scored id is positive {got["top_is_positive"]:.4f}  ({got["points"]} points, {len(set(dev.tasks))} tasks)')
    print(f'dev, uniform: mean loss {base["mean_loss"]:.6f}  top-scored id is positive {base["top_is_positive"]:.4f}')
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or '').split('\n')[0])
    ap.add_argument('--points', type=Path, nargs='+', required=True, help='the folders samples/SET/points/<plan>, such as the train and the dev one')
    ap.add_argument('--out', type=Path, help='the file of the saved booster')
    ap.add_argument('--check', action='store_true', help='check the gradient against a finite difference on one real group, then stop')
    ap.add_argument('--points-per-task', type=int, default=0, help='at most N points of a task, chosen by a seeded hash (0: all)')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--score', type=Path, help='a saved booster: score it on the dev points, and fit nothing')
    ap.add_argument('--score-tasks', help='with --score: comma-separated dev tasks, the only ones scored')
    ap.add_argument('--dev-tasks', help='comma-separated tasks to treat as dev, whatever their header says (development only)')
    ap.add_argument('--writers-alike', default='', help="S,S: writer_sha values whose point files go in one fit: shas of writers that differ only in code that no feature reads, checked by extracting tasks again under the newer writer and finding the same points")
    ap.add_argument('--drop-point-kinds', default='', help='K,K: leave out the points of these kinds, such as KIND, from the fit and the evaluation')
    ap.add_argument('--table-choice', action='store_true', help='keep only the points where two or more ids name a table (the vector column tokg:table)')
    ap.add_argument('--drop-names', default='', help='vector columns to leave out by exact name, separated by commas (--drop-prefixes leaves out by prefix)')
    ap.add_argument('--table-ranker', action='store_true', help='keep only the points where two or more ids name a table and a positive names one, each with its table ids alone: a model of which table, given that the answer is one')
    ap.add_argument('--drop-prefixes', default='', help='P,P: leave out the vector columns whose names start with one of these (an arm of column blocks, such as tok:,state:,task:,pq:body:)')
    ap.add_argument('--task-weights', action='store_true', help="weigh each train point by 1 over its task's points (scaled to a mean of 1), so that each task weighs the same; use with --points-per-task 0")
    ap.add_argument('--alpha', type=float, default=0.0, help='the train loss weighs each id in the softmax denominator by 1 + alpha * drawn (0: no weight)')
    ap.add_argument('--wheels-alike', default='', help='W,W: engine wheels whose point files go in one fit (header wheel, such as site-exp61,site-exp62)')
    ap.add_argument('--wheels-alike-check', nargs='+', default=[], help='with --wheels-alike: the JSON files of run/points_alike.py that show the wheels give equal points')
    ap.add_argument('--shapes', type=int, default=900, help='the column budget of the shape columns (the points files\' `shapes` and `tok_tables` records; shape_rel.py): the shapes most often unequal across a training point\'s table tokens, 6 columns each, 2 for a stable shape (0: none)')
    ap.add_argument('--rounds', type=int, help='with dev files, the most rounds (default 2000); with none, the count of rounds, which must be given')
    ap.add_argument('--early-stopping', type=int, default=50, help='stop after this many rounds without a better dev loss')
    ap.add_argument('--log-every', type=int, default=50)
    ap.add_argument('--num-leaves', type=int, default=63)
    ap.add_argument('--learning-rate', type=float, default=0.05)
    ap.add_argument('--min-data-in-leaf', type=int, default=100)
    ap.add_argument('--min-sum-hessian', type=float, default=1e-3, help="LightGBM's min_sum_hessian_in_leaf: the least sum of hessians in a leaf (LightGBM's default 1e-3)")
    ap.add_argument('--feature-fraction', type=float, default=0.8)
    ap.add_argument('--threads', type=int, default=int(os.environ.get('ARC_HEAVY_CPUS', '1')))
    args = ap.parse_args()
    global DROP, DROP_NAMES, DROP_KINDS, TABLE_CHOICE, TABLE_RANKER, WRITERS_ALIKE
    WRITERS_ALIKE = frozenset(x for x in args.writers_alike.split(',') if x)
    DROP = tuple(x for x in args.drop_prefixes.split(',') if x)
    DROP_KINDS = frozenset(x for x in args.drop_point_kinds.split(',') if x)
    TABLE_CHOICE = args.table_choice
    TABLE_RANKER = args.table_ranker
    DROP_NAMES = frozenset(x for x in args.drop_names.split(',') if x)
    try:
        if args.check:
            return check(args.points[0], args.seed, args.alpha)
        if args.score:
            return score(args)
        if args.out is None:
            ap.error('--out is required unless --check or --score')
        return fit(args)
    except FitError as e:
        print(f'error: {e}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
