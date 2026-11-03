"""The TableVector (contract, `TableVector`): the features of one table at one assignment, from its Set of Rows and the task's given tables.

  table_vec(tab, ctx) -> list[float]    NAMES order; NaN where a feature has no value

A Rows is at one example under one constraint model. A quantity of one example is computed for each Rows of the example and averaged over them.
A statistic over the rows of the train examples (`row_distinct`) pools the rows of all Rows of an example. The paint of the table on the train
inputs (`out_gain`, `near_*`) paints each Rows on its own and takes the mean over the Rows of an example, as the engine's feature crate does. A table has no cap on its rows. The first 12 of ENGINE_NAMES are the crate's features
of the same names (`engine_features`).
"""
import importlib.util
import itertools
import math
import os
import sys
import zlib
from typing import Any

import numpy as np

from table_facts import FACT_NAMES, NAN, TYPE_NAMES, table_features
from table_read import Rw, TableAt, TaskCtx, fsum

SCHEMA = 't1'
MAX_CHOICES = 16
KIT_POLICY = os.environ.get('ARC_POLICY', '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-tiekey-value-0729e4943/policy')
ENGINE_NAMES = ['lmean', 'lmax', 'share', 'empty_all', 'empty_inputs', 'rows_mean', 'rows_min', 'rows_max', 'empty_any', 'one_row',
                'rows_per_example_mean', 'rows_per_example_max']  # the engine's features (arclog.table_feature_names()), written again in Python
NEW_NAMES = ['counts_only', 'row_distinct', 'test_same', 'near_only_missing', 'near_only_extra', 'near_fill', 'out_gain'] + ENGINE_NAMES
NAMES = FACT_NAMES + NEW_NAMES

type Pick = dict[tuple[int, int], int]  # (table, example) -> the index of the chosen Rows; absent: 0

_KIT: dict[str, Any] = {}


def kit() -> tuple[Any, Any]:
    """The policy's `outfeat` and `nodefeat`, loaded from the kit's policy folder."""
    if not _KIT:
        sys.path.insert(0, KIT_POLICY)
        for name in ('nodefeat', 'outfeat'):
            spec = importlib.util.spec_from_file_location(name, os.path.join(KIT_POLICY, name + '.py'))
            assert spec and spec.loader
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
            _KIT[name] = mod
    return _KIT['outfeat'], _KIT['nodefeat']


def pairs_of(ctx: TaskCtx) -> list[Any]:
    _, nodefeat = kit()
    return [nodefeat.Pair(a, b) for a, b in ctx.grids]


def picks(tabs: list[TableAt], ntr: int) -> list[Pick]:
    """The joint choices of one Rows per train example for each table. Rows within an example are in the order of their content."""
    slots = [(ti, e, len(t.per_example[e])) for ti, t in enumerate(tabs) for e in range(ntr) if len(t.per_example.get(e, ())) > 1]
    if not slots:
        return [{}]
    total = math.prod(n for _, _, n in slots)
    if total <= MAX_CHOICES:
        return [{(ti, e): i for (ti, e, _), i in zip(slots, ix)} for ix in itertools.product(*(range(n) for _, _, n in slots))]
    return [{(ti, e): zlib.crc32(f'{c}|{tabs[ti].hash}|{e}'.encode()) % n for ti, e, n in slots} for c in range(MAX_CHOICES)]


def paint_state(tab: TableAt, ti: int, pick: Pick, ctx: TaskCtx, pairs: list[Any]) -> tuple[dict, dict]:
    """The policy's `outfeat.out_features` of the table with the chosen Rows on the train pairs: (features, state), the state holding the fixed
    cells, the cells, the gain and the row count."""
    outfeat, _ = kit()
    types = ['Box' if t == 'Offset' else t for t in tab.types]  # the policy reads Position and Box as 4 cells; an Offset is 4 cells too
    x_rows = []
    for e in range(ctx.n_train):
        rs = tab.per_example.get(e)
        if rs:
            x_rows.append([(1, e), rs[pick.get((ti, e), 0)].body.tolist()])
    return outfeat.out_features({'table_types': types, 'types': types, 'x_rows': x_rows}, pairs)


def cells_of(rw: Rw, pi: int, ci: int) -> dict[tuple[int, int], list[int]]:
    """The colors painted on each cell (row, column) by the Position column at cell pi and the Color column at cell ci of one Rows."""
    a = rw.body
    if not len(a):
        return {}
    out: dict[tuple[int, int], list[int]] = {}
    for r, c, v in np.unique(np.stack([a[:, pi], a[:, pi + 2], a[:, ci]], 1), axis=0).tolist():
        out.setdefault((r, c), []).append(v)
    return out


def paint_all(tab: TableAt, ctx: TaskCtx, pairs: list[Any]) -> dict[str, float]:
    """The OUT features `out_gain`, `near_only_missing`, `near_only_extra` and `near_fill` of the crate (`Examples::out`): each Rows is painted on
    its example's train input on its own. The counts of an example (cells fixed, broken, stale, out of bounds, in conflict, and the error) and its pair
    value are the means over its Rows; an example with no Rows counts as one empty Rows. The features then combine the examples: the sums of those
    counts. The best (Position, Color) pair is the one with the least error. `near_remap` is not here. A task-level table has no train example in it,
    so it gives nothing, and neither does a table with no Position column."""
    outfeat, _ = kit()
    pos = [c[1] for c in tab.cols if c[0] == 'Position']
    if tab.task_level or not ctx.n_train or not pos:
        return {}
    base = max(sum(outfeat.base_err(p) for p in pairs), 1)
    best: tuple[float, float, float, float] | None = None  # (error, fixed, broke, stale) of the pair with the least error
    for pi in pos:
        for ci in (c[1] for c in tab.cols if c[0] == 'Color'):
            fixed = broke = stale = 0.0
            for e, p in enumerate(pairs):
                height, width = len(p.b), len(p.b[0])
                own = [0.0] * 3
                rws = tab.rows_of(e)
                for rw in rws:
                    f = b = st = 0
                    for (i, j), colors in cells_of(rw, pi, ci).items():
                        if not (0 <= i < height and 0 <= j < width):
                            continue
                        want = p.b[i][j]
                        was = outfeat.base_of(p, i, j) == want
                        if len(colors) == 1 and colors[0] == want:
                            f += not was
                        elif was:
                            b += 1
                        else:
                            st += 1
                    own[0] += f
                    own[1] += b
                    own[2] += st
                k = len(rws)
                fixed, broke, stale = fixed + own[0] / k, broke + own[1] / k, stale + own[2] / k
            err = base - fixed + broke  # `base` is at least 1
            if best is None or err < best[0]:
                best = (err, fixed, broke, stale)
    d: dict[str, float] = {}
    if best is not None:
        err, fixed, broke, stale = best
        d['out_gain'] = float(np.float32(1 - err / base))
        d['near_only_missing'] = float(err > 0 and broke == 0 and stale == 0 and fixed > 0)
        d['near_only_extra'] = float(fixed == base and err > 0)
    # one fill color for a Position column alone, chosen for each Rows on its own
    best_fill: tuple[float, float, float] | None = None
    for pi in pos:
        got = own_ = inside = n = 0.0
        for e, p in enumerate(pairs):
            height, width = len(p.b), len(p.b[0])
            sums = [0.0] * 4
            rws = tab.rows_of(e)
            for rw in rws:
                cells = {(r, c) for r, c in zip(rw.body[:, pi].tolist(), rw.body[:, pi + 2].tolist()) if 0 <= r < height and 0 <= c < width}
                counts = [0] * 10
                for i, j in cells:
                    counts[min(p.b[i][j], 9)] += 1
                m = max(counts)
                if not m:
                    continue
                v = counts.index(m)
                for i, j in cells:
                    sums[0] += p.b[i][j] == v and outfeat.base_of(p, i, j) != v
                    sums[1] += p.b[i][j] != v and outfeat.base_of(p, i, j) == p.b[i][j]
                sums[2] += m
                sums[3] += len(cells)
            k = len(rws)
            got, own_, inside, n = got + sums[0] / k, own_ + sums[1] / k, inside + sums[2] / k, n + sums[3] / k
        gain = (got - own_) / base
        if best_fill is None or gain > best_fill[0]:
            best_fill = (gain, got / base, inside / n if n > 0 else 0.0)
    if best_fill is not None:
        d['near_fill'] = float(best_fill[2] == 1.0 and best_fill[1] > 0)
    return d


def rows_of_example(tab: TableAt, e: int, rw: Rw) -> list[tuple]:
    """The rows of one Rows as the engine's cells have them: the example index among them where the table's own Type has an Example column."""
    return [tuple(r) + (e,) if tab.native else tuple(r) for r in rw.body.tolist()]


def signature(tab: TableAt, e: int) -> frozenset:
    """The distinct rows of each Rows of example e, sorted; an example with no Rows has one empty Rows."""
    sig = frozenset(tuple(sorted(set(rows_of_example(tab, e, rw)))) for rw in tab.per_example.get(e, ()))
    return sig or frozenset({()})


def engine_features(tab: TableAt, ctx: TaskCtx) -> list[float]:
    """The first 12 features of the engine (arclog-features), from the Rows grouped by example. The rows of an example are the mean over its Rows; a
    train example with no Rows has 0 rows; a test input that is not in the table is not read. A task-level table has no train example: its
    examples are all read where `lmean`, `lmax`, `share`, `empty_all`, `empty_inputs` and the counts of Rows say so, and `rows_mean`, `rows_min`,
    `rows_max`, `empty_any` and `one_row` are 0."""
    ntr = ctx.n_train

    def mean_n(e: int) -> float:
        rs = tab.per_example.get(e)
        return fsum([r.n for r in rs]) / len(rs) if rs else 0.0
    if tab.task_level or not ntr:
        exs = sorted(tab.per_example)
        train = inputs = [mean_n(e) for e in exs]
        sets = [float(len(tab.per_example[e])) for e in exs]
        own: list[float] = []
    else:
        train = [mean_n(e) for e in range(ntr)]
        inputs = train + [mean_n(e) for e in sorted(tab.per_example) if e >= ntr]
        sets = [float(len(tab.per_example.get(e, ()))) for e in range(ntr)] + [float(len(tab.per_example[e])) for e in sorted(tab.per_example) if e >= ntr]
        own = train

    def mean(v: list[float]) -> float:
        return fsum(v) / len(v) if v else 0.0
    f32 = np.float32
    return [float(f32(math.log1p(mean(train)))), float(f32(math.log1p(max(train, default=0.0)))),
            float(f32(sum(x > 0 for x in train) / len(train))) if train else 0.0,
            float(bool(train) and all(x == 0 for x in train)), float(bool(inputs) and all(x == 0 for x in inputs)),
            float(f32(mean(own))), float(f32(min(own, default=0.0))), float(f32(max(own, default=0.0))),
            float(bool(own) and min(own) == 0), float(bool(own) and max(own) == 1),
            float(f32(mean(sets))), float(f32(max(sets, default=0.0)))]


def new_facts(tab: TableAt, ctx: TaskCtx) -> dict[str, float]:
    d: dict[str, float] = {}
    d.update(zip(ENGINE_NAMES, engine_features(tab, ctx)))
    ntr = ctx.n_train
    train_level = bool(ntr) and not tab.task_level  # a task-level table has no train example in it
    # whether a test example in the table has the distinct rows of the first train example
    d['test_same'] = float(train_level and any(signature(tab, e) == signature(tab, 0) for e in tab.per_example if e >= ntr))
    # the share of the rows of all train examples (all their Rows) that are distinct
    flat = [r for e in range(ntr) for rw in tab.per_example.get(e, ()) for r in rows_of_example(tab, e, rw)] if train_level else []
    d['row_distinct'] = len(set(flat)) / len(flat) if flat and (tab.types or tab.native) else 0.0
    f = paint_all(tab, ctx, pairs_of(ctx))
    for name in ('out_gain', 'near_only_missing', 'near_only_extra', 'near_fill'):
        d[name] = f.get(name, 0.0)
    return d


def table_vec(tab: TableAt, ctx: TaskCtx) -> list[float]:
    if tab.counts_only:
        d = {k: v for k, v in table_features_types(tab).items()}
        d['counts_only'] = 1.0
    else:
        d = table_features(tab, ctx)
        d.update(new_facts(tab, ctx))
        d['counts_only'] = 0.0
    return [float(d.get(k, NAN)) for k in NAMES]


def table_features_types(tab: TableAt) -> dict[str, float]:
    """The facts that the column types alone give."""
    from table_facts import canon_type
    d = {k: 0.0 for k in TYPE_NAMES}
    for t in tab.types:
        d['tb_t_' + canon_type(t)] += 1
    d['tb_n_cols'] = float(len(tab.types))
    return d


def array(v: list[float]) -> np.ndarray:
    return np.array(v, np.float64)
