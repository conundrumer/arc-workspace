"""The store of a fit's feature vectors, in the blocks that `engine/block-boost` reads (docs/feature-spec/export-design.md#how-a-fit-stores-its-feature-vectors).

  python3 block_store.py --points DIR [DIR ...] --out STORE [--jobs N] [--splits train] [--drop-names A,B] [--drop-prefixes P,P] [--max-bin 255] [--threads 6]

DIR is a folder of points files (`<task>.jsonl.zst`). The files, the points that a fit leaves out, the order of the points and the columns are those of fit_trees.py (`split_files`,
`kept_of`, `layout_of`): a row is one (writing point, id), a task's rows follow its points in file order, and tasks follow the file names. The columns are the vector's, less the ones
that --drop-names and --drop-prefixes name (their defaults are the columns a fit leaves out). A row of the store holds the same values as that row of fit_trees.py's matrix.

A task has two kinds of block. A point block is the kept point columns of a point's `vp`, and an id block is the kept id columns of an id's row of `vo`. A task keeps each distinct
block once, and a row points to one block of each kind. A block holds only its entries that are not 0: a NaN stays an entry, and -0.0 is 0. Two tasks never share a block.

STORE holds, as block-boost reads them:
  plan.json                       what `block-boost scan STORE` and `compile STORE` read: two maps (point blocks, id blocks) and two uses (the streams of the blocks)
  rowmap_point.u32, rowmap_id.u32 each row's point block and id block (raw u32, memory-mapped by block-boost)
  point_blocks.zst, id_blocks.zst the blocks, as streamable zstd frames of block-boost's `Records`
  colmap_point.i32, colmap_id.i32 each stream's column to the store's column
  keep.i32                        every column kept (the columns are already the kept ones)
  groups.u32, labels.u8           for `softmax`: the start of each writing point's rows, then the row count; 1 for a positive id
and for the readers of the model:
  names.json                      the column names, in the store's order
  features.json                   the names as LightGBM takes them, the header fields that define the features, the plan, the tasks
  assembled.json                  each task's place in the store

The work is by task and resumable. A task's blocks and rows stand in `shards/<task>.*`, and `shards/<task>.json` is written last; a run skips the tasks that have it. The
assembly then joins the shards and runs on its own when every task has a shard. Delete `shards/` to save its disk after the assembly. A shard is valid only for the columns of the
run that made it: a run with other columns, or other drops, stops.
"""
import argparse
import hashlib
import json
import os
import shutil
import struct
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
import zstandard

import fit_trees as FT

DEFAULT_DROP_NAMES = 'ctx:col,tokc:label_rank'
DEFAULT_DROP_PREFIXES = 'pq:body:,task:,tok:,judge_,tok_descendant_output:,tokg:port,tok_rank:test_same,tok_median_diff:test_same'
FRAME_BLOCKS = 1 << 16  # blocks to a frame of a stream
LEVEL = 3  # zstd level of the shards


# ---------------------------------------------------------------- columns

def split_columns(layout: FT.Layout) -> dict[str, Any]:
    """Where each kept column stands: the store's column j, and its index in a point's `vp` (point columns) or in a row of `vo` (id columns)."""
    if layout.vector_point_cols is None or layout.vector_id_cols is None:
        raise FT.FitError('the points files hold no vectors: block_store.py reads files with `vector_names`')
    keep = layout.keep if layout.keep is not None else np.arange(len(layout.names), dtype=np.int64)
    in_point = {int(c): i for i, c in enumerate(layout.vector_point_cols)}
    in_id = {int(c): i for i, c in enumerate(layout.vector_id_cols)}
    point_j, point_vp, id_j, id_vo = [], [], [], []
    for j, c in enumerate(keep.tolist()):
        if c in in_point:
            point_j.append(j)
            point_vp.append(in_point[c])
        else:
            id_j.append(j)
            id_vo.append(in_id[c])
    return dict(point_j=point_j, point_vp=point_vp, id_j=id_j, id_vo=id_vo)


def signature(names: list[str], cols: dict[str, Any], fields: dict[str, Any]) -> str:
    """What a shard depends on besides its points file: the columns and the header fields that define them."""
    text = json.dumps([names, cols['point_j'], cols['point_vp'], cols['id_j'], cols['id_vo'], fields], sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()


# ---------------------------------------------------------------- the blocks of one task

def canon(a: np.ndarray) -> np.ndarray:
    """float32 values with -0.0 as 0.0 and every NaN as the one NaN, so that equal blocks have equal bytes."""
    x = np.array(a, np.float32)
    x += np.float32(0.0)
    x[np.isnan(x)] = np.nan
    return x


def encode(blocks: list[np.ndarray], width: int) -> tuple[list[bytes], int]:
    """The frames of `Records` for the blocks (rows of `width` values): a block count, an entry count, each block's length, each entry's column as its difference from the entry
    before it (from 0 at the start of a frame), and each entry's value. An entry is a value that is not 0, and NaN is one. Also the count of entries."""
    out: list[bytes] = []
    entries = 0
    for a in range(0, len(blocks), FRAME_BLOCKS):
        chunk = np.stack(blocks[a:a + FRAME_BLOCKS]) if width else np.zeros((len(blocks[a:a + FRAME_BLOCKS]), 0), np.float32)
        mask = chunk != 0
        lengths = mask.sum(axis=1).astype('<u4')
        columns = np.nonzero(mask)[1]
        values = chunk[mask].astype('<f4')
        deltas = np.diff(columns, prepend=0).astype('<i4')
        out.append(struct.pack('<IQ', len(chunk), len(values)) + lengths.tobytes() + deltas.tobytes() + values.tobytes())
        entries += len(values)
    return out, entries


def write_zst(path: Path, chunks: list[bytes]) -> None:
    tmp = path.with_name(path.name + '.partial')
    with open(tmp, 'wb') as f, zstandard.ZstdCompressor(level=LEVEL).stream_writer(f, closefd=False) as w:
        for c in chunks:
            w.write(c)
    os.replace(tmp, path)


def read_zst(path: Path) -> bytes:
    with open(path, 'rb') as f, zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True) as r:
        return r.read()


STATE: dict[str, Any] = {}


def init_worker(state: dict[str, Any]) -> None:
    """The columns and drops of the run, set in each process (a started process does not inherit them)."""
    STATE.clear()
    STATE.update(state)
    FT.DROP = tuple(state['drop_prefixes'])
    FT.DROP_NAMES = frozenset(state['drop_names'])


def build_task(job: tuple[str, str, str]) -> dict[str, Any]:
    """Reads one points file and writes its shard, named by the file's unit (unit_of). Returns the shard's record."""
    path, shard_dir = Path(job[0]), Path(job[1])
    started = time.time()
    task = job[2]
    head = FT.header_of(path)
    kept, _tables, left_out = FT.kept_of(path, head, 0, 0)
    pv, iv = np.array(STATE['point_vp'], np.int64), np.array(STATE['id_vo'], np.int64)
    n_point, n_id = len(pv), len(iv)
    seen_point: dict[bytes, int] = {}
    seen_id: dict[bytes, int] = {}
    point_blocks: list[np.ndarray] = []
    id_blocks: list[np.ndarray] = []
    sizes = np.array([k.size for k in kept], np.uint32)
    rows = int(sizes.sum())
    point_of = np.empty(rows, np.uint32)
    id_of = np.empty(rows, np.uint32)
    label = np.zeros(rows, np.uint8)
    at = 0
    width = n_id * 4
    for k in kept:
        assert k.vp is not None and k.vo is not None
        p = canon(k.vp[pv])
        b = seen_point.setdefault(p.tobytes(), len(point_blocks))
        if b == len(point_blocks):
            point_blocks.append(p)
        point_of[at:at + k.size] = b
        sub = canon(k.vo[:, iv])
        raw = sub.tobytes()
        for i in range(k.size):
            key = raw[i * width:(i + 1) * width]
            b = seen_id.setdefault(key, len(id_blocks))
            if b == len(id_blocks):
                id_blocks.append(sub[i])
            id_of[at + i] = b
        label[at + k.positive] = 1
        at += k.size
    point_frames, point_entries = encode(point_blocks, n_point)
    id_frames, id_entries = encode(id_blocks, n_id)
    write_zst(shard_dir / f'{task}.point.zst', point_frames)
    write_zst(shard_dir / f'{task}.id.zst', id_frames)
    write_zst(shard_dir / f'{task}.rows.zst', [point_of.tobytes(), id_of.tobytes(), label.tobytes(), sizes.tobytes()])
    record = dict(task=task, signature=STATE['signature'], rows=rows, points=len(kept), point_blocks=len(point_blocks), id_blocks=len(id_blocks), point_entries=point_entries,
                  id_entries=id_entries, left_out=dict(left_out), input_bytes=path.stat().st_size, seconds=round(time.time() - started, 2))
    tmp = shard_dir / f'{task}.json.partial'
    tmp.write_text(json.dumps(record))
    os.replace(tmp, shard_dir / f'{task}.json')
    return record


# ---------------------------------------------------------------- the assembly

def write_raw(path: Path, parts) -> int:
    """Writes the byte strings of `parts` to path, in one file, atomically. Returns the byte count."""
    tmp = path.with_name(path.name + '.partial')
    n = 0
    with open(tmp, 'wb') as f:
        for p in parts:
            f.write(p)
            n += len(p)
    os.replace(tmp, path)
    return n


def assemble(out: Path, shard_dir: Path, records: list[dict[str, Any]], names: list[str], cols: dict[str, Any], features: dict[str, Any], max_bin: int, threads: int) -> dict[str, Any]:
    """Joins the shards of `records` (in order) into the files of the store."""
    live = [r for r in records if r['rows'] > 0]
    places = []
    row_at = group_at = point_at = id_at = 0
    for r in live:
        places.append(dict(task=r['task'], row=row_at, group=group_at, point_block=point_at, id_block=id_at, rows=r['rows'], points=r['points'], point_blocks=r['point_blocks'], id_blocks=r['id_blocks']))
        row_at, group_at, point_at, id_at = row_at + r['rows'], group_at + r['points'], point_at + r['point_blocks'], id_at + r['id_blocks']
    rows, groups, point_total, id_total = row_at, group_at, point_at, id_at
    if rows >= 1 << 32 or point_total >= 1 << 32 or id_total >= 1 << 32:
        raise FT.FitError('a count passes what u32 holds')
    started = time.time()
    point_file, id_file = out / 'rowmap_point.u32', out / 'rowmap_id.u32'
    label_file, group_file = out / 'labels.u8', out / 'groups.u32'
    handles = {n: open(out / (n + '.partial'), 'wb') for n in ('rowmap_point.u32', 'rowmap_id.u32', 'labels.u8', 'groups.u32', 'point_blocks.zst', 'id_blocks.zst')}
    try:
        for i, (r, place) in enumerate(zip(live, places), 1):
            data = read_zst(shard_dir / f"{r['task']}.rows.zst")
            n, p = r['rows'], r['points']
            assert len(data) == 9 * n + 4 * p, (r['task'], len(data))
            point_of = np.frombuffer(data, '<u4', n, 0).astype('<u4') + np.uint32(place['point_block'])
            id_of = np.frombuffer(data, '<u4', n, 4 * n).astype('<u4') + np.uint32(place['id_block'])
            label = data[8 * n:9 * n]
            sizes = np.frombuffer(data, '<u4', p, 9 * n).astype(np.uint64)
            starts = (np.cumsum(sizes) - sizes + np.uint64(place['row'])).astype('<u4')
            handles['rowmap_point.u32'].write(point_of.tobytes())
            handles['rowmap_id.u32'].write(id_of.tobytes())
            handles['labels.u8'].write(label)
            handles['groups.u32'].write(starts.tobytes())
            for kind, n_blocks in (('point', r['point_blocks']), ('id', r['id_blocks'])):
                if n_blocks:
                    with open(shard_dir / f"{r['task']}.{kind}.zst", 'rb') as f:
                        shutil.copyfileobj(f, handles[f'{kind}_blocks.zst'], 1 << 22)
            if i % 25 == 0 or i == len(live):
                print(f'assemble {i}/{len(live)} tasks, {time.time() - started:.0f} s', flush=True)
        handles['groups.u32'].write(np.array([rows], '<u4').tobytes())
    finally:
        for h in handles.values():
            h.close()
    for n in handles:
        os.replace(out / (n + '.partial'), out / n)
    for name, values in (('colmap_point.i32', cols['point_j']), ('colmap_id.i32', cols['id_j']), ('keep.i32', list(range(len(names))))):
        write_raw(out / name, [np.array(values, '<i4').tobytes()])
    plan = dict(rows=rows, columns=len(names), max_bin=max_bin, sample_cap=1 << 32, threads=threads,
                maps=[dict(file='rowmap_point.u32', domain=point_total), dict(file='rowmap_id.u32', domain=id_total)],
                uses=[dict(file='point_blocks.zst', map=0, col_map='colmap_point.i32'), dict(file='id_blocks.zst', map=1, col_map='colmap_id.i32')])
    (out / 'plan.json').write_text(json.dumps(plan, indent=1))
    (out / 'names.json').write_text(json.dumps(names))
    totals = dict(tasks=len(live), groups=groups, rows=rows, columns=len(names), point_columns=len(cols['point_j']), id_columns=len(cols['id_j']), point_blocks=point_total, id_blocks=id_total,
                  point_entries=sum(r['point_entries'] for r in live), id_entries=sum(r['id_entries'] for r in live))
    (out / 'features.json').write_text(json.dumps(dict(features, matrix=totals), indent=1))
    (out / 'assembled.json').write_text(json.dumps(dict(totals=totals, places=places, signature=records[0]['signature'] if records else None)))
    return totals


# ---------------------------------------------------------------- the run

def human(n: float) -> str:
    for unit in ('B', 'KiB', 'MiB', 'GiB'):
        if abs(n) < 1024 or unit == 'GiB':
            return f'{n:.1f} {unit}'
        n /= 1024
    return str(n)


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or '').split('\n')[0])
    ap.add_argument('--points', type=Path, nargs='+', required=True, help='folders of points files (<task>.jsonl.zst)')
    ap.add_argument('--out', type=Path, required=True, help='the store folder')
    ap.add_argument('--splits', default='train', help="the header splits whose files go in the store: train, dev or train,dev (a held-out file is an error, as in fit_trees.py)")
    ap.add_argument('--drop-names', default=DEFAULT_DROP_NAMES, help='vector columns to leave out by exact name, separated by commas')
    ap.add_argument('--drop-prefixes', default=DEFAULT_DROP_PREFIXES, help='vector columns to leave out by name prefix, separated by commas')
    ap.add_argument('--jobs', type=int, default=1, help='tasks built at once; each holds one points file in memory')
    ap.add_argument('--max-bin', type=int, default=255)
    ap.add_argument('--threads', type=int, default=6, help='the threads that scan and compile use (plan.json)')
    ap.add_argument('--no-assemble', action='store_true', help='build the shards and stop')
    args = ap.parse_args()
    drop_prefixes = tuple(x for x in args.drop_prefixes.split(',') if x)
    drop_names = tuple(x for x in args.drop_names.split(',') if x)
    wanted = set(x for x in args.splits.split(',') if x)
    if not wanted <= {'train', 'dev'}:
        print(f'error: --splits {args.splits}: only train and dev', file=sys.stderr)
        return 2
    init_worker(dict(drop_prefixes=drop_prefixes, drop_names=drop_names))
    try:
        train, dev, heads = FT.split_files(args.points, set())
        files = sorted([*(train if 'train' in wanted else []), *(dev if 'dev' in wanted else [])], key=lambda p: p.name)
        if not files:
            raise FT.FitError('no points files with the wanted splits')
        fields = FT.feature_fields([heads[FT.points_stem(p)] for p in files])
        plan = FT.plan_of([heads[FT.points_stem(p)] for p in files])
        layout = FT.layout_of(fields)
        cols = split_columns(layout)
    except FT.FitError as e:
        print(f'error: {e}', file=sys.stderr)
        return 2
    names = layout.names
    sig = signature(names, cols, fields)
    state = dict(drop_prefixes=list(drop_prefixes), drop_names=list(drop_names), signature=sig, **cols)
    init_worker(state)
    out: Path = args.out
    shard_dir = out / 'shards'
    shard_dir.mkdir(parents=True, exist_ok=True)
    config = out / 'config.json'
    if config.exists() and json.loads(config.read_text()).get('signature') != sig:
        print(f'error: {out} holds shards of other columns (config.json); use another --out', file=sys.stderr)
        return 2
    config.write_text(json.dumps(dict(signature=sig, drop_prefixes=drop_prefixes, drop_names=drop_names, columns=len(names), splits=sorted(wanted))))
    print(f'{len(train)} train and {len(dev)} dev files in the folders; {len(files)} used ({args.splits}); {len(names)} columns ({len(cols["point_j"])} point, {len(cols["id_j"])} id) of {layout.width or len(names)}; plan {plan}', flush=True)

    folders = [FT.point_folder(f).resolve() for f in args.points]

    def unit_of(p: Path) -> str:
        """The name of a file's shard: its task, and `<k>.<task>` for a file of the k-th folder of --points after the first, so that two folders may hold one task, as two rounds do."""
        k = folders.index(p.parent.resolve())
        return FT.points_stem(p) if k == 0 else f'{k}.{FT.points_stem(p)}'

    records: dict[str, dict[str, Any]] = {}
    todo = []
    for p in files:
        task = unit_of(p)
        meta = shard_dir / f'{task}.json'
        if meta.exists():
            rec = json.loads(meta.read_text())
            if rec.get('signature') != sig:
                print(f'error: the shard of {task} is of other columns; use another --out', file=sys.stderr)
                return 2
            records[task] = rec
        else:
            todo.append(p)
    print(f'{len(records)} tasks have a shard; {len(todo)} to build', flush=True)

    total_bytes = sum(p.stat().st_size for p in todo)
    done_bytes, done_tasks, started = 0, 0, time.time()
    totals = Counter()

    def report(rec: dict[str, Any]) -> None:
        nonlocal done_bytes, done_tasks
        records[rec['task']] = rec
        done_bytes += rec['input_bytes']
        done_tasks += 1
        elapsed = time.time() - started
        rate = done_bytes / max(elapsed, 1e-9)
        eta = (total_bytes - done_bytes) / rate
        totals['rows'] += rec['rows']
        print(f"[{done_tasks}/{len(todo)}] {rec['task']} rows {rec['rows']} points {rec['points']} point blocks {rec['point_blocks']} id blocks {rec['id_blocks']} "
              f"id entries {rec['id_entries']} {rec['seconds']:.1f} s | {human(rate)}/s of input, {100 * done_bytes / total_bytes:.0f}% , ETA {eta / 60:.1f} min", flush=True)

    jobs = [(str(p), str(shard_dir), unit_of(p)) for p in todo]
    try:
        if args.jobs <= 1 or len(jobs) <= 1:
            for job in jobs:
                report(build_task(job))
        else:
            with ProcessPoolExecutor(max_workers=args.jobs, initializer=init_worker, initargs=(state,)) as pool:
                for future in as_completed([pool.submit(build_task, job) for job in jobs]):
                    report(future.result())
    except FT.FitError as e:
        print(f'error: {e}', file=sys.stderr)
        return 2
    if args.no_assemble:
        return 0
    ordered = [records[unit_of(p)] for p in files]
    marker = out / 'assembled.json'
    if marker.exists() and not todo and json.loads(marker.read_text()).get('signature') == sig and [pl['task'] for pl in json.loads(marker.read_text())['places']] == [r['task'] for r in ordered if r['rows'] > 0]:
        print('the store is assembled already', flush=True)
        return 0
    features = dict(uses=names, booster_names=FT.booster_names(names), header=fields, plan=plan, points_dir=[str(f) for f in args.points], splits=sorted(wanted),
                    train_tasks=[r['task'] for r in ordered if r['rows'] > 0], drop_prefixes=list(drop_prefixes), drop_names=list(drop_names),
                    out_of_scope=dict(file=str(FT.OUT_OF_SCOPE), tasks=dict(FT.out_of_scope())),
                    points_left_out={r['task']: r['left_out'] for r in ordered})
    summary = assemble(out, shard_dir, ordered, names, cols, features, args.max_bin, args.threads)
    size = {n: (out / n).stat().st_size for n in ('rowmap_point.u32', 'rowmap_id.u32', 'labels.u8', 'groups.u32', 'point_blocks.zst', 'id_blocks.zst')}
    print(f'store {out}: {summary}', flush=True)
    print('files: ' + ', '.join(f'{n} {human(s)}' for n, s in size.items()), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
