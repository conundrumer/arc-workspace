"""The feature build: reads each task's row store and writes its TableVectors, AssignmentVectors and QueryVectors. It never calls the engine.

  python build_tables.py SET [--shard k/N] [--tasks id,id]      run with the kit's python (numpy and scipy): the work/.../runtime-kaggle-py313 venv

Reads OUTD/SET/rows/<task>.jsonl.gz (row_store.py). Writes OUTD/SET/tables/<task>.jsonl.gz, to a temp file and then a rename. A task whose file holds the
sha of its row store and of this code is skipped. The AssignmentVector is computed by the sampler kit's `writer.assignment_vector` (`KIT`), so training and
serving give one value; ARC_SAMPLER_KIT, when set, names the kit's sampler folder. The kit's `arclog` needs the engine wheel on PYTHONPATH. Lines:

  header    task, split, src (the row store's), versions, names (the TableVector's), assignment_vector_names, function_names, use_names
  vec       one per distinct TableHash: hash, kind, values (null for NaN), in the order of header.names
  entry     one per (table, assignment): function, name, assignment, hash. The vector is the `vec` of that hash
  given     input, ex_input and ex_output: hash
  assignment_vector  one per parameterized table: query, name, values (null for NaN) in the order of header.assignment_vector_names; and one per base
            table: base, values. It is computed from the (TableHash, engine TableVector) pairs of the table's `entry` records (of the base table's `given`
            record), and from the walk's cap flag in the row store. The engine TableVector is the row store's `engine_features`: the 82 features that
            the writer takes, the first of which `vec` repeats (`table_vec.ENGINE_NAMES`)
  function  one per function: id, names order is header.function_names; values; per_use [[table, values]]; column_origin
  footer    counts, the check of the hash against today's table_key
"""
import argparse
import hashlib
import importlib
import inspect
import json
import os
import sys
import time
import zlib
from collections.abc import Mapping
from functools import cache as memoize
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path

import function_vec as FV
import row_store as RS
import table_read as TR
import table_hash as TH
import table_vec as TV
import numpy as np

OUTD = Path('/Users/davidlu/code/arc-workspace/work/lm/data-study/samples')
TASKS = Path('/Users/davidlu/code/arc-workspace/data/tasks')
KIT = Path(os.environ.get('ARC_SAMPLER_KIT', '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-m2-writer/model/study/sampler'))  # a release's model/study/sampler
CODE = ['build_tables.py', 'table_facts.py', 'table_read.py', 'table_vec.py', 'function_vec.py', 'table_hash.py']
AV_SCHEMA = 'a1'
SCHEMA = f'{TV.SCHEMA}+{FV.SCHEMA}+{AV_SCHEMA}'


@memoize
def sampler_writer() -> Any:
    """The kit's `writer` module. The kit has a `row_store` of its own, which its `table_adapter` binds when it is imported; the module of this folder
    is put back under that name afterwards. Exits with a message where the import fails."""
    own, saved_path = sys.modules.pop('row_store', None), list(sys.path)
    sys.path.insert(0, str(KIT))
    try:
        w = importlib.import_module('writer')
    except Exception as e:
        raise SystemExit(f'build_tables: cannot import the sampler kit writer from {KIT} ({type(e).__name__}: {e}). '
                         f'Run with the kit python and the engine wheel on PYTHONPATH (PYTHONPATH=<site folder> ARCLOG_IDENT_SOURCE=value).') from e
    finally:
        sys.path[:] = saved_path
        sys.modules.pop('row_store', None)
        if own is not None:
            sys.modules['row_store'] = own
    if list(w._TABLE_NAMES[:len(TV.ENGINE_NAMES)]) != TV.ENGINE_NAMES:
        raise SystemExit(f"build_tables: the writer's TableVector features do not start with table_vec.ENGINE_NAMES: {list(w._TABLE_NAMES[:len(TV.ENGINE_NAMES)])}")
    return w


@memoize
def code_sha() -> str:
    h = hashlib.sha256()
    for f in CODE:
        h.update(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), f), 'rb').read())
    w = sampler_writer()  # the AssignmentVector is part of the tables file
    h.update('\0'.join(w.assignment_vector_names()).encode())
    h.update(inspect.getsource(w.assignment_vector).encode())
    return h.hexdigest()[:16]


def current_versions(tables_header: dict, rows_header: dict) -> bool:
    """Whether a tables file was built on the engine and the QueryHash version that the row store's header names."""
    return all(tables_header.get(k) == rows_header.get(k) for k in ('hash_version', 'query_hash_version', 'engine_features_version'))


def clean(v: list[float]) -> list[float | None]:
    return [None if x != x else x for x in v]


def assignment_vector_records(store: RS.Store, queries: set[str] | None = None) -> list[dict]:
    """The `assignment_vector` records: one per parameterized table of the store (of the queries in `queries`, where given), then one per base table.
    The writer's TableVector is the engine's (`arclog.table_feature_names()`: the writer serves with that vector alone), which the row store holds for each
    table as `engine_features`; the `vec` records hold the wider Python TableVector, which the writer does not know. The capped flag of a parameterized
    table is the row store's `stopped` flag of its output."""
    w = sampler_writer()
    for t in [*store.tables, *store.given]:
        if len(t.engine_features) != len(w._TABLE_NAMES):
            raise ValueError(f'the row store holds {len(t.engine_features)} engine features for table {t.hash}; the writer takes {len(w._TABLE_NAMES)}')
    at: dict[tuple[str, str], list[RS.StoredTable]] = {}
    for t in store.tables:
        if queries is None or t.function in queries:  # t.function: the table's query (future name: `query`)
            at.setdefault((t.function, t.name), []).append(t)
    out = []
    for (qid, name), ts in at.items():
        capped = any(o.get('stopped') for o in store.functions.get(qid, {}).get('outputs', []) if o['o'] == ts[0].o)
        out.append(dict(t='assignment_vector', query=qid, name=name, values=clean([float(x) for x in w.assignment_vector([(t.hash, t.engine_features) for t in ts], capped)])))
    if queries is None:
        for t in store.given:  # t.function: the base table's name
            out.append(dict(t='assignment_vector', base=t.function, values=clean([float(x) for x in w.assignment_vector([(t.hash, t.engine_features)], False)])))
    return out


def table_key(t: RS.StoredTable) -> Any:
    """What two stored tables share a TableAt by: their TableHash. A table with no TableHash is shared with none."""
    return t.hash if t.hash is not None else (t.function, t.o, t.assignment)


def legacy_check(store: RS.Store) -> dict:
    """Tables with no DET assignment that today's `table_key` puts together must have one TableHash."""
    groups: dict[str, set[str]] = {}
    for t in store.tables:
        if not t.assignment and t.legacy is not None and not t.counts_only:
            groups.setdefault(t.legacy, set()).add(t.hash)
    return dict(legacy_groups=len(groups), legacy_groups_split=sum(len(h) > 1 for h in groups.values()), legacy_tables=sum(1 for t in store.tables if not t.assignment and t.legacy is not None and not t.counts_only))


def native_example(store: RS.Store, t: RS.StoredTable) -> bool:
    """Whether the table's own Type has an Example column. The store adds one, last, to a Type that has none; the export's labels name the own
    columns only, so a Type without the column has one label fewer than the store's types. Of the given tables, `ex_input` and `ex_output` have it."""
    if t.function in RS.GIVEN:
        return t.function != 'input'
    out = next((o for o in store.functions.get(t.function, {}).get('outputs', []) if o['o'] == t.o), None)
    return out is not None and len(out['labels']) == len(out['types'])


def dev_features(t: RS.StoredTable, ctx: TR.TaskCtx, n_train: int, capped: bool, native: bool) -> list[float] | None:
    """The engine's features from Python (`arclog_features.features`) over the stored rows, as the export passes a table: the own Type (the Example
    column only where `native`), the own cells (with the example index in an Example column), each TableRows once with its example, and a task-level
    table (its example keys have an item of kind 0) once, at example 0. `capped`: the table's own state sequence stopped at the cap. None where the
    module is not on the path, and for a Type with no cell."""
    try:
        import arclog_features as AF  # pyright: ignore[reportMissingImports]
    except ImportError:
        return None
    task_level = any(k[0] == 0 for k in t.examples)
    spans = TH.spans(t.types)[t.types.index('Example')]
    types = t.types if native else [x for x in t.types if x != 'Example']
    width = sum(TH.WIDE.get(x, 1) for x in types)
    if not width:  # a Type with no cell: the module counts rows by cells, so it takes no TableRows of it
        return None
    chunks, bounds, examples, at_row = [], [], [], 0
    for r in t.rows:
        e = 0 if (task_level and not native) or r.ex == RS.NO_EXAMPLE else TR.example_index(r.ex, n_train)
        if native:
            c = r.cells.copy()
            c[:, spans[0]] = e  # the cell holds the example index (the store holds the code)
        else:
            c = np.delete(r.cells, np.s_[spans[0]:spans[1]], axis=1)
        bounds.append(at_row)
        examples.append(e)  # the module takes empty TableRows, and reads their example from here
        chunks.append(c)
        at_row += len(c)
    cells = np.concatenate(chunks) if chunks else np.zeros((0, width), np.int32)
    names, vals = AF.features(types, np.ascontiguousarray(cells, dtype=np.int32).ravel(), types.index('Example') if native else None, ctx.grids, bounds,
                              examples, task_level=task_level, capped=capped)
    return [float(v) for v in vals]


def differs(a: list[float], b: list[float]) -> bool:
    return len(a) != len(b) or any(abs(x - y) > 1e-5 * max(1.0, abs(x), abs(y)) for x, y in zip(a, b))


def build_task(task: str, src: Path, out: Path) -> dict:
    store = RS.read_store(str(src))
    n_train, n_test = store.header['n_train'], store.header['n_test']
    ctx = TR.TaskCtx(json.loads((TASKS / f'{task}.json').read_text()))
    pairs = TV.pairs_of(ctx)
    outfeat, _ = TV.kit()
    fd = out.with_name(out.name + f'.{os.getpid()}.tmp')
    w = RS.GzWriter(str(fd))

    def put(r: dict) -> None:
        w.write(json.dumps(r) + '\n')

    put(dict(t='header', task=task, split=store.header.get('split'), src=store.header['src'], rows_code=store.header['code'], code=code_sha(), schema=SCHEMA, hash_source=store.header['hash_source'], hash_version=store.header['hash_version'], engine_features_version=store.header['engine_features_version'],
             query_hash_version=store.header["query_hash_version"], names=TV.NAMES, assignment_vector_names=list(sampler_writer().assignment_vector_names()),
             function_names=FV.value_names(), use_names=FV.USE_NAMES))
    cache: dict[Any, TR.TableAt] = {}
    vecs: set[str] = set()
    by_table: dict[FV.Ref, dict[RS.AssignKey, TR.TableAt]] = {}

    cmp = dict(compared=0, python_differs=0, dev_differs=0, dev_missing=0)

    def vec_of(t: RS.StoredTable) -> TR.TableAt:
        tab = cache.get(table_key(t))
        if tab is None:
            tab = cache[table_key(t)] = TR.table_at(t, n_train, n_test, native_example(store, t))
            if t.hash is None:  # a vector is keyed by its TableHash, so a table with none has no `vec` record; its entry says `hash` null
                return tab
            v = TV.table_vec(tab, ctx)
            put(dict(t='vec', hash=t.hash, kind='counts_only' if t.counts_only else 'content', values=clean(v)))
            if t.engine_features and not t.counts_only:  # the engine's features, against Python's and against the engine's from Python
                cmp['compared'] += 1
                mine = [v[TV.NAMES.index(n)] for n in TV.ENGINE_NAMES]
                cmp['python_differs'] += differs(t.engine_features[:len(mine)], mine)  # Python writes the first features of the engine's 28 again
                dev = dev_features(t, ctx, n_train, any(o.get('stopped') for o in store.functions.get(t.function, {}).get('outputs', []) if o['o'] == t.o), native_example(store, t))
                if dev is None:
                    cmp['dev_missing'] += 1
                else:
                    cmp['dev_differs'] += differs(t.engine_features, dev)
        return tab

    for t in store.tables:
        tab = vec_of(t)
        by_table.setdefault((t.function, t.name), {})[t.assignment] = tab
        put(dict(t='entry', function=t.function, name=t.name, assignment=[list(p) for p in t.assignment], hash=t.hash))
    for t in store.given:
        tab = vec_of(t)
        by_table.setdefault(('given', t.function), {})[()] = tab
        put(dict(t='given', name=t.function, hash=t.hash))
    n_av = {'parameterized': 0, 'base': 0}
    for r in assignment_vector_records(store):
        put(r)
        n_av['base' if 'base' in r else 'parameterized'] += 1
    dets = {fid: set(fn['dets']) for fid, fn in store.functions.items()}
    n_fn = 0
    for fid, fn in store.functions.items():
        if any('error' not in o for o in fn['outputs']):
            r = FV.function_vec(fn, by_table, dets, ctx, pairs, outfeat)
            put(dict(t='function', **{**r, 'values': clean(r['values']), 'per_use': [[u, clean(x)] for u, x in r['per_use']]}))
            n_fn += 1
    check = legacy_check(store)
    put(dict(t='footer', tables=len(store.tables), tables_without_hash=sum(t.hash is None for t in store.tables), vectors=len(cache), assignment_vectors=n_av['parameterized'], base_assignment_vectors=n_av['base'], functions=n_fn, **check, **cmp))
    w.close()
    os.replace(fd, out)
    return dict(tables=len(store.tables), vectors=len(cache), assignment_vectors=n_av['parameterized'], functions=n_fn, **check, **cmp)


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or '').split('\n')[0])
    ap.add_argument('set')
    ap.add_argument('--shard', default='0/1')
    ap.add_argument('--tasks', default='')
    a = ap.parse_args()
    k, n = map(int, a.shard.split('/'))
    rows, tabs = OUTD / a.set / 'rows', OUTD / a.set / 'tables'
    tabs.mkdir(parents=True, exist_ok=True)
    only = set(filter(None, a.tasks.split(',')))
    todo = []
    for p in sorted(rows.glob('*.jsonl.gz')):
        task = p.name.removesuffix('.jsonl.gz')
        if zlib.crc32(task.encode()) % n == k and (not only or task in only):
            h, mine = RS.header_of(str(p)) or {}, RS.header_of(str(tabs / p.name)) or {}
            if not (mine.get('src') == h.get('src') and mine.get('rows_code') == h.get('code') and mine.get('code') == code_sha() and current_versions(mine, h)):
                todo.append((task, p))
    print(f'{a.set} shard {k}/{n}: {len(todo)} tasks to run', flush=True)
    t0 = time.time()
    for i, (task, p) in enumerate(todo):
        t1 = time.time()
        r = build_task(task, p, tabs / p.name)
        el = time.time() - t0
        print(f'{a.set} {task} {i + 1}/{len(todo)}: {r["tables"]} entries, {r["vectors"]} vectors, {r["assignment_vectors"]} assignment vectors, {r["functions"]} functions, {time.time() - t1:.1f} s, '
              f'{60 * (i + 1) / el:.1f} tasks/min, ETA {el / (i + 1) * (len(todo) - i - 1):.0f} s, legacy groups {r["legacy_groups"]} split {r["legacy_groups_split"]}, engine features: {r["compared"]} compared, {r["python_differs"]} differ from Python, {r["dev_differs"]} from the dev module', flush=True)
    print(f'{a.set} shard {k}/{n} done: {len(todo)} tasks in {time.time() - t0:.0f} s', flush=True)


if __name__ == '__main__':
    main()
