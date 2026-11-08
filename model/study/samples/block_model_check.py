"""Checks the model that block_model_lgb.py wrote against the trees it came from, on rows of the store (block_store.py).

  python3 block_model_check.py --store STORE --model-jsonl OUT/model.jsonl --model MODEL.txt [--rows 2000] [--seed 0] [--tolerance 1e-9]
                               [--points DIR [DIR ...] --verify-tasks 3]

For a sample of rows of the store, it rebuilds each row's values from the blocks the row points to (the raw float32 values in point_blocks.zst and id_blocks.zst), and then scores the
row twice:
  walk     the trees of model.jsonl, walked in Python: on a numeric column a value goes left where it is at most the threshold (a null threshold sends every number left); a NaN goes the
           way default_left says where nan_seen, and reads as 0 elsewhere. On a categorical column (threshold "categorical") a value goes left where it is one of the split's `categories`,
           and right otherwise, as a NaN does
  predict  `lightgbm.Booster(model_file=MODEL.txt).predict(rows, raw_score=True)`
It prints the largest difference of the two scores, and exits 1 where it is above --tolerance.

With --points, it also compares the store with fit_trees.py's own rows: for --verify-tasks tasks (the first, the last and the ones between, among those in the store), every row of the
task (at most --verify-rows) that fit_trees.read_file builds is compared with the row rebuilt from the store, with the labels and the sizes of the groups. This reads those points files.
"""
import argparse
import json
import struct
import sys
import time
from pathlib import Path
from typing import Any, Iterator

import lightgbm as lgb
import numpy as np
import zstandard

import fit_trees as FT


def read_exact(r, n: int, eof_ok: bool = False) -> bytes:
    parts, got = [], 0
    while got < n:
        b = r.read(n - got)
        if not b:
            if eof_ok and got == 0:
                return b''
            raise EOFError('a stream ends inside a frame')
        parts.append(b)
        got += len(b)
    return b''.join(parts)


def frames(path: Path) -> Iterator[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """(each block's length, each entry's column, each entry's value) of every frame of a stream of blocks."""
    with open(path, 'rb') as f, zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True) as r:
        while True:
            head = read_exact(r, 12, eof_ok=True)
            if not head:
                return
            rows, entries = struct.unpack('<IQ', head)
            lengths = np.frombuffer(read_exact(r, 4 * rows), '<u4')
            deltas = np.frombuffer(read_exact(r, 4 * entries), '<i4')
            values = np.frombuffer(read_exact(r, 4 * entries), '<f4')
            yield lengths, np.cumsum(deltas, dtype=np.int64), values


def blocks_of(path: Path, wanted: np.ndarray, colmap: np.ndarray) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    """The entries (store columns, values) of the blocks in `wanted` (sorted, distinct), by block number."""
    out: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    base = 0
    for lengths, columns, values in frames(path):
        n = len(lengths)
        lo, hi = np.searchsorted(wanted, [base, base + n])
        if hi > lo:
            ends = np.cumsum(lengths.astype(np.int64))
            for b in wanted[lo:hi].tolist():
                i = b - base
                a, z = int(ends[i] - lengths[i]), int(ends[i])
                out[b] = (colmap[columns[a:z]], values[a:z])
        base += n
        if base > wanted[-1]:
            break
    missing = [b for b in wanted.tolist() if b not in out]
    if missing:
        raise SystemExit(f'{path}: no block {missing[:5]}; it holds {base}')
    return out


class Store:
    def __init__(self, folder: Path):
        self.folder = folder
        self.plan = json.loads((folder / 'plan.json').read_text())
        self.names = json.loads((folder / 'names.json').read_text())
        self.rows = self.plan['rows']
        self.point_map = np.memmap(folder / 'rowmap_point.u32', '<u4', 'r')
        self.id_map = np.memmap(folder / 'rowmap_id.u32', '<u4', 'r')
        self.labels = np.memmap(folder / 'labels.u8', np.uint8, 'r')
        self.groups = np.memmap(folder / 'groups.u32', '<u4', 'r')
        self.point_cols = np.fromfile(folder / 'colmap_point.i32', '<i4')
        self.id_cols = np.fromfile(folder / 'colmap_id.i32', '<i4')
        keep_file = folder / 'keep.i32'
        self.keep = np.fromfile(keep_file, '<i4') if keep_file.exists() else np.arange(len(self.names), dtype=np.int32)
        assert len(self.point_map) == len(self.id_map) == len(self.labels) == self.rows
        assert self.groups[-1] == self.rows

    def rows_of(self, rows: np.ndarray) -> np.ndarray:
        """float32 values of the rows, in the store's columns."""
        pb, ib = self.point_map[rows], self.id_map[rows]
        pwant, iwant = np.unique(pb), np.unique(ib)
        pblocks = blocks_of(self.folder / 'point_blocks.zst', pwant, self.point_cols)
        iblocks = blocks_of(self.folder / 'id_blocks.zst', iwant, self.id_cols)
        x = np.zeros((len(rows), len(self.names)), np.float32)
        for i, (p, q) in enumerate(zip(pb.tolist(), ib.tolist())):
            c, v = pblocks[p]
            x[i, c] = v
            c, v = iblocks[q]
            x[i, c] = v
        return x

    def kept(self, x: np.ndarray) -> np.ndarray:
        """The columns of the model: the kept columns of x, in the order keep.i32 numbers them."""
        if len(self.keep) == len(self.names) and np.array_equal(self.keep, np.arange(len(self.names))):
            return x
        out = np.zeros((len(x), int(self.keep.max()) + 1), x.dtype)
        for j, k in enumerate(self.keep.tolist()):
            if k >= 0:
                out[:, k] = x[:, j]
        return out


def walk(trees: list[dict[str, Any]], x: np.ndarray) -> np.ndarray:
    """The sum of the trees' leaf values at each row of x (float64 values), by the rule of block-boost's split."""
    score = np.zeros(len(x))
    for t in trees:
        if not t['column']:
            score += t['value'][0]
            continue
        column = np.array(t['column'])
        threshold = np.array([np.inf if v is None or v == 'categorical' else v for v in t['threshold']], np.float64)
        categories = t['categories']
        categorical = [n for n, c in enumerate(categories) if c is not None]
        default_left = np.array(t['default_left'], bool)
        nan_seen = np.array(t['nan_seen'], bool)
        left, right = np.array(t['left']), np.array(t['right'])
        value = np.array(t['value'])
        node = np.zeros(len(x), np.int64)
        while True:
            live = np.flatnonzero(node >= 0)
            if not len(live):
                break
            n = node[live]
            v = x[live, column[n]]
            nan = np.isnan(v)
            go_left = np.where(nan, np.where(nan_seen[n], default_left[n], 0.0 <= threshold[n]), v <= threshold[n])
            for split in categorical:
                at = n == split
                if at.any():
                    seen = v[at]
                    known = ~np.isnan(seen)
                    member = np.zeros(len(seen), bool)
                    member[known] = np.isin(np.trunc(seen[known]).astype(np.int64), categories[split])
                    go_left[at] = member
            node[live] = np.where(go_left, left[n], right[n])
        score += value[~node]
    return score


def verify_points(store: Store, args: argparse.Namespace) -> bool:
    features = json.loads((store.folder / 'features.json').read_text())
    FT.DROP = tuple(features['drop_prefixes'])
    FT.DROP_NAMES = frozenset(features['drop_names'])
    train, dev, heads = FT.split_files(args.points, set())
    path_of = {FT.points_stem(p): p for p in (*train, *dev)}
    places = json.loads((store.folder / 'assembled.json').read_text())['places']
    count = max(1, min(args.verify_tasks, len(places)))
    chosen = [places[round(i * (len(places) - 1) / max(count - 1, 1))] for i in range(count)]
    ok = True
    for place in chosen:
        task = place['task']
        head = heads[task]
        layout = FT.layout_of(FT.feature_fields([head]))
        dense, _ = FT.read_file(path_of[task], head, layout, 0, 0)
        row0, n = place['row'], place['rows']
        assert dense.rows == n, (task, dense.rows, n)
        limit = min(n, args.verify_rows)
        mine = store.rows_of(np.arange(row0, row0 + limit))
        same = bool(np.array_equal(mine, dense.matrix[:limit], equal_nan=True))
        labels = bool(np.array_equal(np.asarray(store.labels[row0:row0 + n]), dense.positive.astype(np.uint8)))
        g0 = place['group']
        starts = np.asarray(store.groups[g0:g0 + place['points']]).astype(np.int64) - row0
        sizes = bool(np.array_equal(np.diff(np.append(starts, n)), dense.sizes))
        print(f'verify {task}: {limit} of {n} rows equal {same}; labels equal {labels}; group sizes equal {sizes}')
        ok = ok and same and labels and sizes
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or '').split('\n')[0])
    ap.add_argument('--store', type=Path, required=True)
    ap.add_argument('--model-jsonl', type=Path, required=True)
    ap.add_argument('--model', type=Path, required=True, help='the LightGBM text model')
    ap.add_argument('--rows', type=int, default=2000)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--tolerance', type=float, default=1e-9)
    ap.add_argument('--points', type=Path, nargs='*', default=[], help='with this, also compare the store with fit_trees.py rows of the points files')
    ap.add_argument('--verify-tasks', type=int, default=3)
    ap.add_argument('--verify-rows', type=int, default=200000)
    args = ap.parse_args()
    started = time.time()
    store = Store(args.store)
    booster = lgb.Booster(model_file=str(args.model))
    trees = []
    with open(args.model_jsonl) as f:
        for line in f:
            if line.strip() and len(trees) < booster.num_trees():
                trees.append(json.loads(line))
    kept = int(store.keep.max()) + 1
    if booster.num_feature() != kept or len(trees) != booster.num_trees():
        print(f'error: the model has {booster.num_feature()} features and {booster.num_trees()} trees; the store keeps {kept} columns and model.jsonl gives {len(trees)} trees', file=sys.stderr)
        return 2
    rng = np.random.default_rng(args.seed)
    n = min(args.rows, store.rows)
    rows = np.unique(np.concatenate([[0, store.rows - 1], rng.choice(store.rows, n, replace=False)]))
    if any('categories' not in t for t in trees):
        print(f'error: {args.model_jsonl} has trees with no `categories`: it is of a block-boost that does not split categories', file=sys.stderr)
        return 2
    categorical_splits = sum(c is not None for t in trees for c in t['categories'])
    print(f'store {store.rows} rows, {len(store.names)} columns; model {len(trees)} trees, {categorical_splits} categorical splits; {len(rows)} rows sampled', flush=True)
    x = store.kept(store.rows_of(rows))
    print(f'rows rebuilt in {time.time() - started:.1f} s; {int(np.isnan(x).any(axis=1).sum())} of them hold a NaN; {int((x != 0).sum())} nonzero cells', flush=True)
    walked = walk(trees, x.astype(np.float64))
    predicted = np.asarray(booster.predict(x, raw_score=True), np.float64)
    diff = np.abs(walked - predicted)
    print(f'scores: walk range [{walked.min():.6f}, {walked.max():.6f}], predict range [{predicted.min():.6f}, {predicted.max():.6f}]')
    print(f'max |walk - predict| = {diff.max():.3e} at row {int(rows[int(diff.argmax())])}, mean {diff.mean():.3e}, tolerance {args.tolerance:g}')
    good = bool(diff.max() <= args.tolerance)
    if args.points:
        good = verify_points(store, args) and good
    print('OK' if good else 'FAIL', f'{time.time() - started:.1f} s')
    return 0 if good else 1


if __name__ == '__main__':
    sys.exit(main())
