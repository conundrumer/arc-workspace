"""Stage 5 of the sample build: the training rows of the gradient-boosted trees, one writing point of a target query at a time, with the writer's own features.

  python3 points_write.py SET --plan ordered|unordered [--shard k/N] [--tasks T,T,...] [--samples-per-task K] [--seed S] [--seconds X] [--max-states N] [--vectors] [--out DIR]

SET is ramp, 37 or training. The extractor (train_rows.points_of, with writer.Features) and the engine wheel come from sys.path: run it with the runtime python and with PYTHONPATH holding the
extractor's folder and the wheel's site folder. For each task of OUTD/SET/skeleton it writes OUTD/SET/points/<plan>/<task>.jsonl.gz (train and dev tasks) or OUTD/SET/points_held/<plan>/<task>.jsonl.gz
(held tasks), to a temp file and then renamed, and skips a task whose file holds the same skeleton sha, extractor shas, wheel, code sha and sample choice. It is not a fit: it writes every
task, held ones included, and calls no split guard. With --samples-per-task K a task keeps at most K samples, chosen by a hash of the seed and the sample id (0: all).

For each sample:
- Scope: the union of the members' programs, members in dependency order (fewest closure queries first, then QueryHash), each with one global label `&r<position>`, and each query's own text
  rewritten from its local labels to the global ones (local &r<i> is closure[i]; the last local label is the query's own).
- For each target query: its text over the scope's labels, its kind and its token stream as train_rows.py takes them; train_rows.points_of_targets gives the writing points of all targets of a kind with every feature name, a shared prefix once.
- Labels come from the extractor: `positive_ids` (a subset of `ids`), `live`, `order` and `order_why` of each record of `train_rows.points_of_targets(..., plan=PLAN)`. Under `ordered`
  each target is walked in its canonical order (or its given order where no rule gives its QueryHash), and the positives are the next tokens of the live targets. Under `unordered` the points are
  the states of a search over each target's item set, one record for each live target at a state, all with the state's positives. The records of one point must agree on `positive_ids` and
  `live`; the points where they do not are counted.
- A point is written once for each (sample, kind, token prefix); under `unordered` the token prefix is that of the first visit of a state, so it is the state's key too.

A file is gzip JSONL:
- `header`: task, set, plan, split, uses (every feature name, in the extractor's order), skeleton_sha, extractor_sha (train_rows.py), writer_sha (writer.py), wheel (the site folder's name), code (this file's sha), samples_per_task, seed, point_names,
  option_names (the option names without `table:`), table_names (the `table:` names, in order).
- `table`: {i, values}: one vector of the `table:` option columns, written once before its first use.
- `point`: sample, kind, length (the number of model tokens so far, the kind token included), ids, option (ids x option_names), table (the `table` index of each id), point (values of
  point_names), positive (indexes into ids), live (the count of live targets).
- `summary`: the counts of the file, last.
Rebuilding the extractor's option matrix from option and table must give it back bit for bit; each written point is checked on the text as written.

With --vectors a point row is the writer's full writing-point vector of each id (`writer.Features.vectors`; train_rows.points_of_targets(..., vectors=True)) in place of the 260 prefix features:
- `header` also has `vectors` (true), `vector_names` (the column names, in order), `vector_point_cols` (the indexes of the columns of the point-scope blocks, which every id of a point repeats)
  and `uses` = `vector_names`; `option_names`, `table_names` and `point_names` are empty.
- `point` has `vp` (the point-scope columns, one row) and `vo` (the other columns, one row for each id), each float32 little-endian in base64, and has neither `option`, `table` nor `point`.
- A point is written only if rebuilding the matrix from `vp` and `vo` gives the extractor's matrix back bit for bit (NaN equal to NaN) and every point-scope column is equal across the ids of the point.
  A point that fails is counted (`rebuild failures`, `point-scope columns that differ across ids`) and not written.
- A file with vectors and a file without are never current for each other.
"""
import argparse
import base64
import gzip
import hashlib
import importlib
import json
import math
import os
import re
import sys
import tempfile
import time
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

OUTD = Path('/Users/davidlu/code/arc-workspace/work/lm/data-study/samples')
REPO = Path(__file__).resolve().parents[3]
SCHEMA = 'points-1'
VECTOR_COUNTS = ('point-scope columns that differ across ids', 'vector shape or names differ from the header')
LABEL = re.compile(r'&r(\d+)')
type Atom = tuple[int, ...]


class Reject(Exception):
    """A sample or a target query that cannot be written; the message is the reason that is counted."""


@dataclass
class Point:
    """A writing point of a sample, written once for its (kind, token prefix)."""
    kind: str
    tokens: tuple[int, ...]
    phase: str
    ids: list[int]
    ids_text: str
    option_text: str
    table: list[int]
    point_text: str
    positive_ids: np.ndarray
    live: int
    next_ids: set[int] = field(default_factory=set)
    vp: str = ''  # with --vectors: the point-scope columns and the id-scope columns, as base64
    vo: str = ''


@dataclass
class Totals:
    counts: Counter[str] = field(default_factory=Counter)
    seconds: defaultdict[str, float] = field(default_factory=lambda: defaultdict(float))
    failures: dict[str, Counter[str]] = field(default_factory=dict)  # kind of failure -> reason -> count
    examples: dict[str, str] = field(default_factory=dict)  # reason -> one example
    search: Counter[str] = field(default_factory=Counter)  # the extractor's counts of the plan, and the order of each target
    largest: int = 0  # the most states of one search

    def fail(self, what: str, reason: str, example: str) -> None:
        self.failures.setdefault(what, Counter())[reason] += 1
        self.examples.setdefault(f'{what}: {reason}', example)

    def add(self, other: 'Totals') -> None:
        self.counts += other.counts
        for k, v in other.seconds.items():
            self.seconds[k] += v
        self.search += other.search
        self.largest = max(self.largest, other.largest)
        for what, c in other.failures.items():
            self.failures.setdefault(what, Counter()).update(c)
        for k, v in other.examples.items():
            self.examples.setdefault(k, v)


def why(e: BaseException) -> str:
    text = str(e).strip().splitlines()
    return f'{type(e).__name__}: {text[0][:90] if text else ""}'


def module_file(m: Any) -> Path:
    """The file of an imported module, resolved."""
    return Path(m.__file__).resolve()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------- number text

def float_text(x: np.floating) -> str:
    if math.isnan(x):
        return 'NaN'
    if math.isinf(x):
        return 'Infinity' if x > 0 else '-Infinity'
    if x == 0:
        return '-0.0' if math.copysign(1.0, x) < 0 else '0'
    if x == int(x) and abs(x) < 1e7:
        return str(int(x))
    return str(np.float32(x))


def row_text(row: np.ndarray) -> str:
    """A float32 vector as JSON text, each number as the shortest text that gives its float32 back."""
    if np.isfinite(row).all() and not np.signbit(row[row == 0]).any() and (np.abs(row) < 1e7).all():
        as_int = row.astype(np.int64)
        if (as_int == row).all():
            return json.dumps(as_int.tolist(), separators=(',', ':'))
    return '[' + ','.join(float_text(x) for x in row) + ']'


def matrix_text(m: np.ndarray) -> str:
    return '[' + ','.join(row_text(r) for r in m) + ']'


def same_bits(a: np.ndarray, b: np.ndarray) -> bool:
    return a.shape == b.shape and bool(np.array_equal(a, b, equal_nan=True)) and bool(np.array_equal(np.signbit(a), np.signbit(b)))


def f32_text(a: np.ndarray) -> str:
    """A float32 array as little-endian bytes in base64."""
    return base64.b64encode(np.ascontiguousarray(a, dtype='<f4').tobytes()).decode('ascii')


def f32_back(text: str, shape: tuple[int, ...]) -> np.ndarray:
    return np.frombuffer(base64.b64decode(text), dtype='<f4').astype(np.float32).reshape(shape)


def vector_point_cols(wr: Any, names: tuple[str, ...]) -> list[int]:
    """The indexes of the columns of the point-scope blocks of writer.VECTOR_BLOCKS; each column name is `<block>:<feature>` and belongs to exactly one block."""
    cols = []
    for i, n in enumerate(names):
        owners = [b for b in wr.VECTOR_BLOCKS.values() if n.startswith(b.name + ':')]
        if len(owners) != 1:
            raise RuntimeError(f'the vector column {n!r} belongs to {len(owners)} blocks')
        if owners[0].scope == 'point':
            cols.append(i)
    return cols


# ---------------------------------------------------------------- the scope

def scope_of(members: list[str], queries: dict[str, dict]) -> tuple[list[str], dict[str, str]]:
    """(the members' texts in scope order, the global label of each member's QueryHash)."""
    for h in members:
        if h not in queries:
            raise Reject('a member has no query record')
    order = sorted(members, key=lambda h: (len(queries[h]['closure']), h))
    label = {h: f'&r{i}' for i, h in enumerate(order)}
    texts = []
    for h in order:
        q = queries[h]
        for c in q['closure']:
            if c not in label:
                raise Reject('a member\'s closure names a query that is not a member')
            if int(label[c][2:]) >= int(label[h][2:]):
                raise Reject('a member\'s closure is not before it in dependency order')
        texts.append(rewrite(q, label, label[h]))
    return texts, label


def rewrite(query: dict, label: dict[str, str], own: str) -> str:
    """The query's own text with its local labels written as the global ones; `own` is the label of the query itself."""
    program, closure = query['program'], query['closure']
    if len(program) != len(closure) + 1:
        raise Reject('the program is not its closure and then the query\'s own text')

    def put(m: re.Match[str]) -> str:
        i = int(m.group(1))
        if i < len(closure):
            if closure[i] not in label:
                raise Reject('a closure query has no label in the scope')
            return label[closure[i]]
        if i == len(closure):
            return own
        raise Reject('a local label past the query\'s own')
    return LABEL.sub(put, program[-1])


# ---------------------------------------------------------------- stepping a target's stream

# ---------------------------------------------------------------- one file

class Sink:
    """A task's file: the header, the table vectors once each before their first use, the points, the summary."""

    def __init__(self, path: Path, header: dict):
        fd, self.tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + '.')
        self.f = gzip.open(os.fdopen(fd, 'wb'), 'wt', compresslevel=6)
        self.path = path
        self.index: dict[bytes, int] = {}
        self.parsed: list[np.ndarray] = []
        self.pending: list[str] = []
        self.f.write(json.dumps(header) + '\n')

    def table_index(self, row: np.ndarray) -> int:
        key = row.tobytes()
        i = self.index.get(key)
        if i is None:
            i = self.index[key] = len(self.parsed)
            text = row_text(row)
            self.parsed.append(np.array(json.loads(text), np.float32))
            self.pending.append(f'{{"record":"table","i":{i},"values":{text}}}\n')
        return i

    def flush_tables(self) -> None:
        self.f.writelines(self.pending)
        self.pending.clear()

    def close(self, summary: dict) -> None:
        self.f.write(json.dumps(dict(record='summary', **summary)) + '\n')
        self.f.close()
        os.replace(self.tmp, self.path)

    def abort(self) -> None:
        try:
            self.f.close()
        finally:
            if os.path.exists(self.tmp):
                os.unlink(self.tmp)


# ---------------------------------------------------------------- one sample

@dataclass
class Env:
    live: Any
    wr: Any
    tr: Any
    run: Any
    uses: tuple[str, ...]
    option_names: tuple[str, ...]
    point_names: tuple[str, ...]
    plain: list[int]  # the columns of the option names without `table:`
    table: list[int]  # the columns of the `table:` names
    sink: Sink
    totals: Totals
    plan: str
    seconds: float
    max_states: int
    vector_names: tuple[str, ...] | None = None  # with --vectors, the columns of the vector
    vector_point_cols: list[int] = field(default_factory=list)
    vector_id_cols: list[int] = field(default_factory=list)


def point_of_vector(env: Env, kind: str, rec: dict) -> Point | None:
    """The point with its vector as vp and vo, or None (counted) where the vector does not rebuild or a point-scope column differs across the ids."""
    vec: np.ndarray = rec['vectors']
    n = len(rec['ids'])
    if env.vector_names is None or tuple(rec["names"]) != env.vector_names or vec.shape != (n, len(env.vector_names)) or vec.dtype != np.float32:
        env.totals.counts['vector shape or names differ from the header'] += 1
        return None
    pc, ic = env.vector_point_cols, env.vector_id_cols
    if n and not same_bits(vec[:, pc], np.broadcast_to(vec[:1, pc], (n, len(pc)))):
        env.totals.counts['point-scope columns that differ across ids'] += 1
        return None
    vp_text, vo_text = f32_text(vec[0, pc]), f32_text(vec[:, ic])
    full = np.empty(vec.shape, np.float32)
    full[:, pc] = f32_back(vp_text, (1, len(pc)))
    full[:, ic] = f32_back(vo_text, (n, len(ic)))
    ids_text = json.dumps(rec['ids'].tolist(), separators=(',', ':'))
    if not same_bits(full, vec) or json.loads(ids_text) != rec['ids'].tolist():
        env.totals.counts['rebuild failures'] += 1
        return None
    return Point(kind, tuple(int(t) for t in rec['tokens']), rec['phase'], rec['ids'].tolist(), ids_text, '', [], '', rec['positive_ids'], int(rec['live']), vp=vp_text, vo=vo_text)


def point_of_record(env: Env, kind: str, rec: dict) -> Point | None:
    if env.vector_names is not None:
        return point_of_vector(env, kind, rec)
    opt: np.ndarray = rec['option']
    n = len(rec['ids'])
    plain, table = opt[:, env.plain], np.ascontiguousarray(opt[:, env.table])
    option_text = matrix_text(plain)
    table_ix = [env.sink.table_index(table[i]) for i in range(n)]
    ids_text = json.dumps(rec['ids'].tolist(), separators=(',', ':'))
    point_text = row_text(rec['point'])
    # the rebuild check, on the text as written
    back_plain = np.array(json.loads(option_text), np.float32).reshape(n, len(env.plain))
    full = np.empty(opt.shape, np.float32)
    full[:, env.plain] = back_plain
    if env.table:
        full[:, env.table] = np.stack([env.sink.parsed[i] for i in table_ix])
    if not same_bits(full, opt) or not same_bits(np.array(json.loads(point_text), np.float32), rec['point']) or json.loads(ids_text) != rec['ids'].tolist():
        env.totals.counts['rebuild failures'] += 1
    return Point(kind, tuple(int(t) for t in rec['tokens']), rec['phase'], rec['ids'].tolist(), ids_text, option_text, table_ix, point_text, rec['positive_ids'], int(rec['live']))


def process_sample(env: Env, sample: dict, queries: dict[str, dict]) -> None:
    tot, wr, live = env.totals, env.wr, env.live
    texts, label = scope_of(sample['state']['queries'], queries)
    scope = tuple(texts)
    try:
        env.run.scope(scope)
    except Exception as e:
        raise Reject('the engine refused the scope: ' + why(e)) from e
    # the targets: text over the scope's labels and the token stream
    targets: dict[str, list[tuple[str, list[int]]]] = {}
    for h in sample['target_queries']:
        tot.counts['targets'] += 1
        try:
            q = queries[h]
            text = rewrite(q, label, f'&r{len(scope)}')
            ids, model, paths = live.arclog.StudyProgram.from_sexp('\n'.join((*scope, text, live.READER_OUT)), env.run.session.settings).decode_stream()
            stream = [int(t) for t, m, p in zip(ids, model, paths) if m and p[0] == len(scope)]
            kind = env.run.V.name(stream[0])
            if kind not in live.KIND_TOK:
                raise Reject(f'the kind {kind} is not written')
            if kind != q['kind']:
                raise Reject('the stream\'s kind differs from the query\'s kind')
        except Reject as e:
            tot.fail('target', str(e), f'{h} {sample["id"]}')
            continue
        except Exception as e:
            tot.fail('target', 'decode: ' + why(e), f'{h} {sample["id"]}')
            continue
        targets.setdefault(kind, []).append((text, stream))
    for kind, group in targets.items():
        points: dict[tuple[int, ...], Point] = {}
        refused: set[tuple[int, ...]] = set()  # token prefixes whose point failed its checks
        failed: set[int] = set()
        stats: Counter[str] = Counter()
        t0 = time.perf_counter()
        it = env.tr.points_of_targets(env.run, scope, kind, [stream for _, stream in group], env.uses, plan=env.plan, seconds=env.seconds, max_states=env.max_states, stats=stats,
                                      vectors=env.vector_names is not None)
        while True:
            try:
                got = next(it, None)
            except Exception as e:
                tot.seconds['extractor'] += time.perf_counter() - t0
                tot.fail('sample', 'points_of_targets: ' + why(e), f'{sample["id"]} {kind}')
                break
            tot.seconds['extractor'] += time.perf_counter() - t0
            if got is None:
                break
            ti, rec = got
            t1 = time.perf_counter()
            if 'error' in rec:
                if ti not in failed:
                    failed.add(ti)
                    tot.fail('target', 'points_of_targets: ' + why(rec['error']), f'{group[ti][0][:160]} {sample["id"]}')
            elif rec['left_mask']:
                tot.counts['left the mask'] += 1
            else:
                tot.counts['points before dedupe'] += 1
                key = tuple(int(t) for t in rec['tokens'])
                p = points.get(key)
                if key in refused:
                    continue
                if p is None:
                    p = point_of_record(env, kind, rec)
                    if p is None:
                        refused.add(key)
                        continue
                    points[key] = p
                elif not np.array_equal(p.positive_ids, rec['positive_ids']) or p.live != rec['live']:
                    tot.counts['points whose records disagree on the positives'] += 1
                if rec['next_id'] is not None:
                    p.next_ids.add(int(rec['next_id']))
                if rec['order'] == 'gold':
                    tot.examples.setdefault('order_why: ' + rec['order_why'].split(':')[0], f'{group[ti][0][:160]} {sample["id"]}: {rec["order_why"][:160]}')
            tot.seconds['assembly'] += time.perf_counter() - t1
            t0 = time.perf_counter()
        tot.search.update(stats)
        tot.largest = max(tot.largest, stats['unordered:states'])
        if stats['unordered:states'] == tot.largest and env.plan == 'unordered':
            tot.examples['largest search'] = f'{stats["unordered:states"]} states, {len(group)} targets of kind {kind}, sample {sample["id"]}'
        t1 = time.perf_counter()
        env.sink.flush_tables()
        for p in points.values():
            where = {t: i for i, t in enumerate(p.ids)}
            pos = sorted(where[int(t)] for t in p.positive_ids if int(t) in where)
            if len(pos) != len(p.positive_ids):
                tot.counts['points with a positive that is not in ids'] += 1
            if any(nx not in set(int(t) for t in p.positive_ids) for nx in p.next_ids):
                tot.counts['points whose next token is no positive'] += 1
            tot.counts['points'] += 1
            tot.counts['ids'] += len(p.ids)
            tot.counts['positives'] += len(pos)
            tot.counts['live'] += p.live
            tot.counts['points with no positive'] += not pos
            tot.counts['points with one positive'] += len(pos) == 1
            if env.vector_names is not None:
                env.sink.f.write(f'{{"record":"point","sample":"{sample["id"]}","kind":"{kind}","length":{len(p.tokens)},"ids":{p.ids_text},"vp":"{p.vp}","vo":"{p.vo}",'
                                 f'"positive":{json.dumps(pos, separators=(",", ":"))},"live":{p.live}}}\n')
                continue
            env.sink.f.write(f'{{"record":"point","sample":"{sample["id"]}","kind":"{kind}","length":{len(p.tokens)},"ids":{p.ids_text},"option":{p.option_text},'
                             f'"table":{json.dumps(p.table, separators=(",", ":"))},"point":{p.point_text},"positive":{json.dumps(pos, separators=(",", ":"))},"live":{p.live}}}\n')
        tot.seconds['labels and writing'] += time.perf_counter() - t1


# ---------------------------------------------------------------- one task

def chosen(samples: list[dict], k: int, seed: int) -> list[dict]:
    if k <= 0 or len(samples) <= k:
        return samples
    keep = sorted(samples, key=lambda s: hashlib.sha256(f'{seed}:{s["id"]}'.encode()).hexdigest())[:k]
    return sorted(keep, key=samples.index)


def header_of(path: Path) -> dict | None:
    try:
        with gzip.open(path, 'rt') as f:
            return json.loads(f.readline())
    except (OSError, EOFError, ValueError):
        return None


def run_task(env_base: dict, set_name: str, task: str, args: argparse.Namespace, shas: dict[str, str], smp: Any, out: Path) -> Totals | None:
    live, wr, tr = env_base['live'], env_base['wr'], env_base['tr']
    skeleton = OUTD / set_name / 'skeleton' / f'{task}.jsonl'
    records = [json.loads(x) for x in skeleton.read_text().splitlines()]
    head = records[0]
    queries = {r['hash']: r for r in records if r['record'] == 'query'}
    samples = chosen([r for r in records if r['record'] == 'sample'], args.samples_per_task, args.seed)
    split = head['split']
    folder = out / set_name / ('points_held' if split == 'held' else 'points') / args.plan
    path = folder / f'{task}.jsonl.gz'
    header = dict(record='header', schema=SCHEMA, task=task, set=set_name, plan=args.plan, split=split, skeleton_sha=file_sha(skeleton), extractor_sha=shas['extractor'], writer_sha=shas['writer'],
                  wheel=shas['wheel'], code=shas['code'], samples_per_task=args.samples_per_task, seed=args.seed, seconds=args.seconds, max_states=args.max_states,
                  uses=list(env_base['uses']), point_names=list(env_base['point_names']), option_names=[env_base['option_names'][i] for i in env_base['plain']],
                  table_names=[env_base['option_names'][i] for i in env_base['table']])
    if args.vectors:
        # the vector's columns follow from the wheel and the writer, which the header names, so they are added after the skip check
        header = dict(header, vectors=True, point_names=[], option_names=[], table_names=[])
        header.pop('uses')
    old = header_of(path)
    if old and bool(old.get('vectors')) == args.vectors and {k: old.get(k) for k in header} == header:
        return None
    folder.mkdir(parents=True, exist_ok=True)
    sess, d, _ = env_base['live_try'].session_of(task)
    run = live.Run(smp.pri, sess, 0, time.monotonic() + 86400, d, live.Limits())
    vector_names: tuple[str, ...] | None = None
    point_cols: list[int] = []
    id_cols: list[int] = []
    if args.vectors:
        vector_names = tuple(wr.vector_names(run))
        point_cols = vector_point_cols(wr, vector_names)
        in_point = set(point_cols)
        id_cols = [i for i in range(len(vector_names)) if i not in in_point]
        header = dict(header, uses=list(vector_names), vector_names=list(vector_names), vector_point_cols=point_cols)
    sink = Sink(path, header)
    tot = Totals()
    uses = () if args.vectors else env_base['uses']  # the vector holds the features; the extractor need not make the prefix features too
    env = Env(live, wr, tr, run, uses, env_base['option_names'], env_base['point_names'], env_base['plain'], env_base['table'], sink, tot, args.plan, args.seconds, args.max_states,
              vector_names, point_cols, id_cols)
    try:
        for sample in samples:
            tot.counts['samples'] += 1
            before = tot.counts['points']
            try:
                process_sample(env, sample, queries)
            except Reject as e:
                tot.fail('sample', str(e), f'{sample["id"]} {task}')
                continue
            except Exception as e:
                tot.fail('sample', 'error: ' + why(e), f'{sample["id"]} {task}')
                continue
            tot.counts['samples written'] += 1
            tot.counts['samples with a point'] += tot.counts['points'] > before
        sink.close(dict(samples=tot.counts['samples'], points=tot.counts['points'], failures={k: dict(v) for k, v in tot.failures.items()}, rebuild_failures=tot.counts['rebuild failures'], **({'vector_failures': {k: tot.counts[k] for k in VECTOR_COUNTS}} if args.vectors else {}), search=dict(sorted(tot.search.items()))))
    except BaseException:
        sink.abort()
        raise
    return tot


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or '').split('\n')[0])
    ap.add_argument('set', choices=('ramp', '37', 'training'))
    ap.add_argument('--shard', default='0/1', help='k/N: the tasks with crc32(task) %% N == k')
    ap.add_argument('--tasks', help='comma-separated task ids')
    ap.add_argument('--samples-per-task', type=int, default=0, help='at most K samples of a task, chosen by a seeded hash of the sample id (0: all)')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--seconds', type=float, default=10.0, help='the extractor\'s time for the order or the search of one target')
    ap.add_argument('--max-states', type=int, default=20000, help='the most states of one unordered search')
    ap.add_argument('--plan', choices=('ordered', 'unordered'), required=True, help='the writer plan: ordered (a fixed order of atoms) or unordered (set labels)')
    ap.add_argument('--vectors', action='store_true', help='write the writer\'s full writing-point vector of each id in place of the prefix features')
    ap.add_argument('--out', type=Path, default=OUTD)
    args = ap.parse_args()
    k, n = map(int, args.shard.split('/'))
    tr = importlib.import_module('train_rows')
    wr = importlib.import_module('writer')
    live = importlib.import_module('live')
    live_try = importlib.import_module('live_try')
    live_try.P.REPO = os.environ.get('ARC_ROOT', str(REPO))
    sampler_dir = module_file(tr).parent
    smp = live.Sampler(str(sampler_dir / '../../../models-current'), steers=())
    uses = tuple(wr.feature_names())
    option_names, point_names = tr.split_uses(uses)
    plain = [i for i, x in enumerate(option_names) if not x.startswith('table:')]
    table = [i for i, x in enumerate(option_names) if x.startswith('table:')]
    shas = dict(extractor=file_sha(module_file(tr)), writer=file_sha(module_file(wr)), code=file_sha(Path(__file__)), wheel=module_file(live.arclog).parent.parent.name)
    env_base = dict(live=live, live_try=live_try, wr=wr, tr=tr, uses=uses, option_names=option_names, point_names=point_names, plain=plain, table=table)
    wanted = set(args.tasks.split(',')) if args.tasks else None
    tasks = sorted(p.stem for p in (OUTD / args.set / 'skeleton').glob('*.jsonl') if zlib.crc32(p.stem.encode()) % n == k and (wanted is None or p.stem in wanted))
    t0 = time.time()
    total, done, skipped = Totals(), 0, 0
    for i, task in enumerate(tasks, 1):
        t1 = time.time()
        got = run_task(env_base, args.set, task, args, shas, smp, args.out)
        if got is None:
            skipped += 1
            continue
        done += 1
        total.add(got)
        el = time.time() - t0
        c = got.counts
        print(f'{args.set} {task} {i}/{len(tasks)} samples {c["samples written"]}/{c["samples"]} points {c["points"]} ids/point {c["ids"] / max(c["points"], 1):.1f} '
              f'{c["points"] / max(time.time() - t1, 1e-9):.1f} points/s ETA {el / done * (len(tasks) - i):.0f}s', flush=True)
    c = total.counts
    p = max(c['points'], 1)
    print(json.dumps(dict(
        set=args.set, shard=args.shard, written=done, current=skipped, seconds=round(time.time() - t0, 1), samples=c['samples'], samples_written=c['samples written'], targets=c['targets'],
        points_before_dedupe=c['points before dedupe'], points=c['points'], ids_per_point=round(c['ids'] / p, 2), positives_per_point=round(c['positives'] / p, 3),
        live_per_point=round(c['live'] / p, 3), points_with_one_positive=c['points with one positive'], points_with_no_positive=c['points with no positive'],
        records_disagree_on_positives=c['points whose records disagree on the positives'], positive_not_in_ids=c['points with a positive that is not in ids'],
        next_token_no_positive=c['points whose next token is no positive'], left_the_mask=c['left the mask'], rebuild_failures=c['rebuild failures'], **({'vector_failures': {k: c[k] for k in VECTOR_COUNTS}} if args.vectors else {}),
        ms_per_point=round(1000 * (time.time() - t0) / p, 3),
        extractor_ms_per_point=round(1000 * total.seconds['extractor'] / p, 3), assembly_ms_per_record=round(1000 * total.seconds['assembly'] / max(c['points before dedupe'], 1), 3),
        largest_search_states=total.largest, search=dict(sorted(total.search.items())),
        failures={k2: dict(v) for k2, v in total.failures.items()}, examples=total.examples)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
