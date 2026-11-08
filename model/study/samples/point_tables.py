"""The table columns of the query writer's writing-point vector (spec: docs/sample-build/training-instances.md,
"Table columns of the writing-point vector"). Pure functions over `table_export.ExportTable`s, which `table_export.read_export` makes from
`arclog.step_tables(..., by_assignment=True, rows=True)`. They read no writer state and keep no cache between calls.

  successor_vector(table, capped=None)  -> float32[len(successor_names())]    names `succ:<n>`, n in the writer's assignment_vector_names()
  base_context(base)                    -> Ctx                                  the base tables' cells, read once for a task
  body_delta(cur, succ, base)           -> float32[len(delta_names())]        names `delta:<name>:min|mean|max`, then `delta:pairs`
  state_vector(tables, base, kinds)     -> float32[len(state_names())]        names `state:...`
  successor_names(), delta_names(), state_names()                             the names in column order
  VERSION                                                                      changes with any change of a value or a name

`base` of `body_delta` and `state_vector` is the mapping below or the Ctx that `base_context` makes from it (a mapping builds a Ctx in the call).

Tables. A table is an `ExportTable`; the tables of `base` are in the same layout: `base['input']` and `base['ex_output']` are read (`ex_input` is
accepted and unread). The number of train examples is the count of train examples in the entries of `base['input']`. Only train examples are
read. A table's rows at an example are the union of its TableRows at that example over its constraint models. The Example column is dropped
and is no column of the table: in a table that has one (`'Example' in types`, a native Example column) its cells hold the example index (train
first) and split the rows of an entry; in a table that has none, an entry's (kind, index) names the example and a task-level entry (kind 0)
holds for every example. This is `table_read.table_at`'s reading, and `table_read.TableAt` and `Rw` hold the result. A Position column is four
cells whose cells 0 and 2 are the row and the column of the position, and a Color column is one cell, as in `table_vec.cells_of`, which is
written here over int32 arrays with one packed int64 key for each (position, color) pair. A row whose entry is not complete (`Entry.complete`
False, no rows) makes its example unknown for that table, and every value that reads the example is NaN there.

Labels are used only to match the columns of two tables: a column of S is kept from C when C has a column of the same label and the same type
(the k-th column of a label in S matches the k-th in C).

Pairs. An `At.dets` is a list of (DET relation name, value hash) where the name is `'slot <n>'`. A pair is a successor assignment s of S and the
assignment c of C with c.dets == the part of s.dets whose names are DETs of C. A successor assignment with no such c makes no pair. Where S has
more DETs than C, several successor assignments pair with one current assignment. With `cur` None (END), `succ` is a list of the query's output
tables and each assignment of each is a pair with an empty C (no row, no column). Each value of a pair is the mean over train examples, NaN
values left out; the aggregates over pairs leave NaN out too. `delta:pairs` is the count of pairs, and the values are NaN when there are none.

Type classes of `cols_added:*`, by the column's type string. The strings found in the ramp row stores (work/lm/data-study/samples/ramp/rows) are
Example, Position, Color, Ident, Nat, Dir, Int, Axis, Box, DiagDir, Dir8, Offset, D4, DiagAxis and Sense:

  color     Color
  position  Position
  ident     Ident
  int       Nat, Int
  other     every other string: Box, Offset, Dir, Dir8, DiagDir, Axis, DiagAxis, D4, Sense (and any of Pose*, C4, Sym, Axis4)

`state_vector` takes `kinds`, parallel to `tables`: the kind of each parameterized table's query ('RULE', 'DET', 'INIT' or 'RIGID_DET');
`state:dets` counts the tables whose kind is 'DET'.
"""
import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

import table_hash as TH
import table_read as TR
from table_export import EXAMPLE_TRAIN, At, ExportTable

VERSION = 'point_tables.2'

NAN = float('nan')
TYPE_CLASS = {'Color': 'color', 'Position': 'position', 'Ident': 'ident', 'Nat': 'int', 'Int': 'int'}
CLASSES = ('color', 'position', 'ident', 'int', 'other')
AGGS = ('min', 'mean', 'max')
PAIR_NAMES = ('rows_cur', 'rows_succ', 'kept', 'lost', 'fanout', 'empty', 'cols_added', *('cols_added:' + c for c in CLASSES),
              'out_recall', 'out_precision', 'out_recall_gain', 'out_precision_gain', 'changed_recall', 'pos_recall', 'lost_cells')
_IX = {n: i for i, n in enumerate(PAIR_NAMES)}

# A (position, color) pair is one int64: three fields of 21 bits. A row or a column is clipped to [-2^20, 2^20), a color is masked to 21 bits.
FIELD = 21
OFFSET = 1 << 20
COLOR_MASK = (1 << FIELD) - 1


def _writer() -> Any:
    """The sampler kit's `writer` module, as `build_tables.sampler_writer` imports it."""
    import build_tables
    return build_tables.sampler_writer()


# ---------------------------------------------------------------------- names


def successor_names() -> list[str]:
    return ['succ:' + n for n in _writer().assignment_vector_names()]


def delta_names() -> list[str]:
    return [f'delta:{n}:{a}' for n in PAIR_NAMES for a in AGGS] + ['delta:pairs']


def _features() -> list[str]:
    """The TableVector feature names, from the names of the AssignmentVector (head of 4, then <f>:min, <f>:mean, <f>:max for each <f>)."""
    names = list(_writer().assignment_vector_names())[4:]
    return [names[i].rsplit(':', 1)[0] for i in range(0, len(names), 3)]


def state_names() -> list[str]:
    return (['state:tables', 'state:dets', 'state:capped', 'state:differ']
            + [f'state:{f}:mean:{a}' for f in _features() for a in ('mean', 'max')]
            + ['state:out_recall:max', 'state:out_precision:max', 'state:changed_recall:max'])


# ---------------------------------------------------------------------- the AssignmentVector


def successor_vector(table: ExportTable, capped: bool | None = None) -> np.ndarray:
    """The writer's `assignment_vector` over the (TableHash, engine features) of each assignment of `table`. `capped`: whether the table's walk
    stopped at the cap; None takes it from the assignments (`At.capped` of any)."""
    items = [(a.hash, np.asarray(a.features, np.float32)) for a in table.at]
    return np.asarray(_writer().assignment_vector(items, any(a.capped for a in table.at) if capped is None else capped), np.float32)


# ---------------------------------------------------------------------- a table at an assignment, over int32 cells


@dataclass
class _View:
    tab: TR.TableAt
    labels: list[str]  # of the columns of tab.cols
    unknown: frozenset[int]  # train examples whose rows the export does not give
    _union: dict[int, np.ndarray] = field(default_factory=dict)

    def rows(self, e: int) -> np.ndarray | None:
        """The union of the example's Rows (int32, one row per distinct row), None where unknown."""
        if e in self.unknown:
            return None
        got = self._union.get(e)
        if got is None:
            rws = self.tab.rows_of(e)
            got = rws[0].body if len(rws) == 1 else np.unique(np.concatenate([r.body for r in rws]), axis=0)
            self._union[e] = got
        return got


def _view(t: ExportTable, at: At, n_train: int) -> _View:
    """The `table_read.table_at` reading of an export entry set: columns without Example, the rows grouped by train example."""
    native = 'Example' in t.types
    spans = TH.spans(t.types)
    ex_at = spans[t.types.index('Example')] if native else None
    types = [x for x in t.types if x != 'Example']
    labels = [lb for lb, x in zip(t.labels, t.types) if x != 'Example']
    cols, first = [], 0
    for x in types:
        w = TH.WIDE.get(x, 1)
        cols.append((x, first, w))
        first += w
    full = sum(b - a for a, b in spans)
    per: dict[int, dict[bytes, TR.Rw]] = {}
    unknown: set[int] = set()

    def put(e: int, body: np.ndarray) -> None:
        rw = TR.Rw(len(body), body, None, hashlib.blake2b(body.tobytes() + len(body).to_bytes(8, 'little'), digest_size=8).digest())
        per.setdefault(e, {})[rw.key] = rw

    for en in at.entries:
        if en.kind not in (0, EXAMPLE_TRAIN):
            continue
        if not en.complete or en.rows is None:
            unknown.update(range(n_train) if native or en.kind == 0 else [en.index])
            continue
        rows = en.rows
        if rows.shape[1] != full:
            unknown.update(range(n_train))
            continue
        if ex_at is not None:
            code = rows[:, ex_at[0]]
            body = np.delete(rows, slice(*ex_at), axis=1)
            for e in np.unique(code).tolist():
                if 0 <= e < n_train:
                    put(e, body[code == e])
        elif en.kind == 0:
            for e in range(n_train):
                put(e, rows)
        elif en.index < n_train:
            put(en.index, rows)
    tab = TR.TableAt(types, cols, first, {e: list(d.values()) for e, d in per.items()}, False, at.hash, n_train, 0, native=native)
    tab.empty = TR.Rw(0, np.zeros((0, first), np.int32), None, b'')
    return _View(tab, labels, frozenset(unknown))


def _pos_keys(rows: np.ndarray, pi: int) -> np.ndarray:
    r = np.clip(rows[:, pi].astype(np.int64), -OFFSET, OFFSET - 1) + OFFSET
    c = np.clip(rows[:, pi + 2].astype(np.int64), -OFFSET, OFFSET - 1) + OFFSET
    return (r << FIELD) | c


def _cell_keys(rows: np.ndarray, pi: int, ci: int) -> np.ndarray:
    """The distinct (position, color) pairs of the Position column at cell pi and the Color column at cell ci, as sorted int64 keys."""
    return np.unique((_pos_keys(rows, pi) << FIELD) | (rows[:, ci].astype(np.int64) & COLOR_MASK))


def _count_in(a: np.ndarray, b: np.ndarray) -> int:
    """|a & b| of two sorted arrays of distinct values."""
    return int(np.isin(a, b, assume_unique=True).sum()) if len(a) and len(b) else 0


def _div(a: float, b: float) -> float:
    return a / b if b else NAN


@dataclass
class _Cells:
    """cells(T, e) for each train example (None where unknown), for the chosen Position and Color column."""
    view: _View
    keys: list[np.ndarray | None]
    pos_cells: list[int]
    _positions: dict[int, np.ndarray] = field(default_factory=dict)

    def positions(self, e: int) -> np.ndarray | None:
        """The distinct positions that any Position column of the table holds at example e."""
        rows = self.view.rows(e)
        if rows is None:
            return None
        got = self._positions.get(e)
        if got is None:
            got = self._positions[e] = np.unique(np.concatenate([_pos_keys(rows, pi) for pi in self.pos_cells]))
        return got


def _cells(v: _View, n_train: int, out: list[np.ndarray | None] | None) -> _Cells | None:
    """cells of the view: None where it has no Position column or no Color column. The pair of columns is the one with the highest recall
    against `out` (the mean of recall(T, e) over the examples where both are known and O(e) is not empty), ties to the first pair in column
    order (Position columns outer, Color columns inner). With `out` None, or with no recall defined, it is the first pair."""
    pos = [c[1] for c in v.tab.cols if c[0] == 'Position']
    col = [c[1] for c in v.tab.cols if c[0] == 'Color']
    if not pos or not col:
        return None
    best: list[np.ndarray | None] | None = None
    best_score = -1.0
    for pi in pos:
        for ci in col:
            keys = [None if (rows := v.rows(e)) is None else _cell_keys(rows, pi, ci) for e in range(n_train)]
            score = -1.0
            if out is not None and len(pos) * len(col) > 1:
                rec = [_count_in(k, o) / len(o) for k, o in zip(keys, out) if k is not None and o is not None and len(o)]
                score = math.fsum(rec) / len(rec) if rec else -1.0
            if best is None or score > best_score:
                best, best_score = keys, score
    assert best is not None
    return _Cells(v, best, pos)


# ---------------------------------------------------------------------- the task's tables


class Ctx:
    """What the base tables give, read once for a task: the number of train examples n, the outputs' cells O(e), the inputs' cells I(e) and D(e) = O(e) - I(e).
    `base_context` makes it; `body_delta` and `state_vector` take it in place of `base`. It holds no table of a call and is not changed by one."""

    def __init__(self, base: Mapping[str, ExportTable]):
        self.n = _n_train(base['input'])
        self.O = self._base_cells(base['ex_output'])
        self.I = self._base_cells(base['input'])
        self.D = [None if o is None or i is None else np.setdiff1d(o, i, assume_unique=True) for o, i in zip(self.O, self.I)]

    def _base_cells(self, t: ExportTable) -> list[np.ndarray | None]:
        if not t.at:
            return [None] * self.n
        c = _cells(_view(t, t.at[0], self.n), self.n, None)
        return list(c.keys) if c is not None else [None] * self.n


def base_context(base: Mapping[str, ExportTable]) -> Ctx:
    """The Ctx of the task's base tables ('input' and 'ex_output' are read). Make it once for a task and pass it as `base` to every call."""
    return Ctx(base)


class _Call:
    """A Ctx and the views and cells of the tables of one call, kept by the identity of their At. It lives for one call."""

    def __init__(self, base: 'Ctx | Mapping[str, ExportTable]'):
        ctx = base if isinstance(base, Ctx) else Ctx(base)
        self.n, self.O, self.D = ctx.n, ctx.O, ctx.D
        self.memo: dict[int, tuple[_View, _Cells | None]] = {}

    def of(self, t: ExportTable, at: At) -> tuple[_View, _Cells | None]:
        got = self.memo.get(id(at))
        if got is None:
            v = _view(t, at, self.n)
            got = self.memo[id(at)] = (v, _cells(v, self.n, self.O))
        return got


def _n_train(t: ExportTable) -> int:
    idx = [en.index for a in t.at for en in a.entries if en.kind == EXAMPLE_TRAIN]
    return max(idx) + 1 if idx else 0


def _stats(sk: np.ndarray, o: np.ndarray, d: np.ndarray | None) -> tuple[float, float, float]:
    """(recall, precision, changed_recall) of the cells sk against O(e) and D(e)."""
    inter = _count_in(sk, o)
    return _div(inter, len(o)), _div(inter, len(sk)), _div(_count_in(sk, d), len(d)) if d is not None else NAN


# ---------------------------------------------------------------------- aggregates that leave NaN out


def _agg(a: np.ndarray, how: str) -> np.ndarray:
    """The min, mean or max over axis 0 of a float64 array, NaN left out; NaN where a column is all NaN."""
    k = a.shape[1]
    if not a.shape[0]:
        return np.full(k, NAN)
    ok = ~np.isnan(a)
    n = ok.sum(0)
    if how == 'mean':
        out = np.where(ok, a, 0.0).sum(0) / np.maximum(n, 1)
    elif how == 'min':
        out = np.where(ok, a, np.inf).min(0)
    else:
        out = np.where(ok, a, -np.inf).max(0)
    out[n == 0] = NAN
    return out


# ---------------------------------------------------------------------- the pairs of a body delta


def _void(a: np.ndarray) -> np.ndarray:
    a = np.ascontiguousarray(a, np.int32)
    return a.view(np.dtype((np.void, 4 * a.shape[1]))).ravel()


def _match(cur: ExportTable | None, succ: ExportTable) -> tuple[list[int], list[int], list[str]]:
    """(the cells of C, the cells of S) of the kept columns in the same order, and the type class of each column of S that is not kept."""
    avail: dict[tuple[str, str], list[int]] = {}
    ccols: list[tuple[str, int, int]] = []
    if cur is not None:
        ccols, clab = _columns(cur)
        for i, (lab, c) in enumerate(zip(clab, ccols)):
            avail.setdefault((lab, c[0]), []).append(i)
    scols, slab = _columns(succ)
    cc, sc, added = [], [], []
    for lab, c in zip(slab, scols):
        got = avail.get((lab, c[0]))
        if got:
            i = got.pop(0)
            cc += range(ccols[i][1], ccols[i][1] + ccols[i][2])
            sc += range(c[1], c[1] + c[2])
        else:
            added.append(TYPE_CLASS.get(c[0], 'other'))
    return cc, sc, added


def _columns(t: ExportTable) -> tuple[list[tuple[str, int, int]], list[str]]:
    """(type, first cell, cells) and the label of each column of t, without Example."""
    cols, labels, first = [], [], 0
    for x, lb in zip(t.types, t.labels):
        if x == 'Example':
            continue
        w = TH.WIDE.get(x, 1)
        cols.append((x, first, w))
        labels.append(lb)
        first += w
    return cols, labels


def _restrict(cur: ExportTable, succ: ExportTable) -> list[tuple[At, At]]:
    """The pairs (c, s) of the successor assignments s of `succ` with the assignment c of `cur` that s restricts to."""
    names = {d for a in cur.at for d, _ in a.dets}
    by: dict[tuple, At] = {}
    for a in cur.at:
        by.setdefault(tuple(sorted(a.dets)), a)
    out = []
    for s in succ.at:
        c = by.get(tuple(sorted(x for x in s.dets if x[0] in names)))
        if c is not None:
            out.append((c, s))
    return out


def _pair(ctx: _Call, ct: ExportTable | None, c: At | None, st: ExportTable, s: At, m: tuple[list[int], list[int], list[str]]) -> np.ndarray:
    """The values of one pair, in PAIR_NAMES order."""
    cc, sc, added = m
    n = ctx.n
    cv, ccells = ctx.of(ct, c) if ct is not None and c is not None else (None, None)
    sv, scells = ctx.of(st, s)
    per = np.full((n, len(PAIR_NAMES)), NAN)
    for e in range(n):
        v = per[e]
        srows = sv.rows(e)
        if srows is None:
            continue
        ns = len(srows)
        v[_IX['rows_succ']] = math.log1p(ns)
        v[_IX['empty']] = float(ns == 0)
        crows = cv.rows(e) if cv is not None else np.zeros((0, 0), np.int32)
        cunk = crows is None  # C is there and its rows at e are not given
        if not cunk:
            assert crows is not None
            nc = len(crows)
            v[_IX['rows_cur']] = math.log1p(nc)
            count = 0
            if nc:
                if not cc:
                    count = nc if ns else 0
                else:
                    keys = np.unique(np.concatenate([_void(crows[:, cc]), _void(srows[:, sc])]), return_inverse=True)[1].ravel()
                    count = int(np.isin(keys[:nc], keys[nc:]).sum())
                v[_IX['kept']] = count / nc
                v[_IX['lost']] = 1.0 - count / nc
            v[_IX['fanout']] = ns / (count or 1)
        if scells is None or scells.keys[e] is None or ctx.O[e] is None:
            continue
        sk, o, d = scells.keys[e], ctx.O[e], ctx.D[e]
        assert sk is not None and o is not None
        rs, ps, v[_IX['changed_recall']] = _stats(sk, o, d)
        v[_IX['out_recall']], v[_IX['out_precision']] = rs, ps
        sp, op = scells.positions(e), np.unique(o >> FIELD)
        assert sp is not None
        v[_IX['pos_recall']] = _div(_count_in(sp, op), len(op))
        if cv is None or ccells is None:  # no cells(C, e): its recall is 0, its precision undefined, and it holds no cell
            v[_IX['out_recall_gain']] = rs
            v[_IX['lost_cells']] = 0.0 if len(o) else NAN
            continue
        ck = ccells.keys[e]
        if ck is None:
            continue
        rc, pc, _ = _stats(ck, o, None)
        v[_IX['out_recall_gain']] = rs - rc
        v[_IX['out_precision_gain']] = ps - pc
        held = o[np.isin(o, ck, assume_unique=True)]
        v[_IX['lost_cells']] = _div(len(held) - _count_in(held, sk), len(o))
    out = _agg(per, 'mean')
    out[_IX['cols_added']] = len(added)
    for k in CLASSES:
        out[_IX['cols_added:' + k]] = added.count(k)
    return out


def body_delta(cur: ExportTable | None, succ: ExportTable | Sequence[ExportTable], base: 'Ctx | Mapping[str, ExportTable]') -> np.ndarray:
    """The change from the current body table to the successor body table (spec: "Candidate block", the `delta:` columns).

    cur   the current body table, None at END.
    succ  the successor body table; at END (cur None) the list of the query's output tables, whose pairs are aggregated together.
    base  the task's base tables by name: 'input' and 'ex_output' (and 'ex_input', unread), in the layout of the other tables; or the Ctx of
          `base_context(those)`, which a caller makes once for a task.
    Returns float32 values in `delta_names()` order. NaN as the module docstring and the spec say."""
    tabs = [succ] if isinstance(succ, ExportTable) else list(succ)
    ctx = _Call(base)
    rows: list[np.ndarray] = []
    memo: dict[tuple, np.ndarray] = {}
    for st in tabs:
        m = _match(cur, st)
        for c, s in ([(None, a) for a in st.at] if cur is None else _restrict(cur, st)):
            key = (c.hash if c else None, s.hash, id(st)) if s.hash is not None and (c is None or c.hash is not None) else None
            got = memo.get(key) if key is not None else None
            if got is None:
                got = _pair(ctx, cur, c, st, s, m)
                if key is not None:
                    memo[key] = got
            rows.append(got)
    out = np.full(len(delta_names()), NAN)
    out[-1] = len(rows)
    if rows:
        a = np.stack(rows)
        for i in range(len(PAIR_NAMES)):
            for k, how in enumerate(AGGS):
                out[3 * i + k] = _agg(a[:, i:i + 1], how)[0]
    return out.astype(np.float32)


# ---------------------------------------------------------------------- the state block


def state_vector(tables: Sequence[ExportTable], base: 'Ctx | Mapping[str, ExportTable]', kinds: Sequence[str]) -> np.ndarray:
    """The `state:` columns over the state's parameterized tables.

    tables  the parameterized tables of the state, each an ExportTable with all its assignments.
    base    as for body_delta, tables or a Ctx.
    kinds   parallel to `tables`: the kind of the table's query, 'DET' for a table computed by a DET (`state:dets` counts those).
    A share or a mean over no table is NaN; a NaN feature of a table is left out of the mean and the max.
    Returns float32 values in `state_names()` order."""
    if len(kinds) != len(tables):
        raise ValueError('kinds must be parallel to tables')
    names = list(_writer().assignment_vector_names())
    feats = _features()
    ctx = _Call(base)
    av = np.stack([successor_vector(t) for t in tables]).astype(np.float64) if tables else np.zeros((0, len(names)))
    out = [float(len(tables)), float(sum(k == 'DET' for k in kinds)), float(av[:, 1].sum()) if len(av) else 0.0,
           float(_agg(av[:, 3:4], 'mean')[0])]
    for f in feats:
        col = av[:, names.index(f + ':mean')][:, None]
        out += [float(_agg(col, 'mean')[0]), float(_agg(col, 'max')[0])]
    best: list[tuple[float, float]] = []  # per table: (its best recall, the precision at that assignment)
    changed = []
    for t in tables:
        stats = []
        for at in t.at:
            v, cells = ctx.of(t, at)
            per = np.full((ctx.n, 3), NAN)
            if cells is not None:
                for e in range(ctx.n):
                    sk, o = cells.keys[e], ctx.O[e]
                    if sk is not None and o is not None:
                        per[e] = _stats(sk, o, ctx.D[e])
            stats.append(_agg(per, 'mean'))
        if not stats:
            continue
        a = np.stack(stats)
        ok = ~np.isnan(a[:, 0])
        if ok.any():
            i = int(np.argmax(np.where(ok, a[:, 0], -np.inf)))
            best.append((float(a[i, 0]), float(a[i, 1])))
        c = _agg(a[:, 2:3], 'max')[0]
        if not math.isnan(c):
            changed.append(float(c))
    top = max(best, key=lambda x: x[0], default=None)
    out += [top[0] if top else NAN, top[1] if top else NAN, max(changed) if changed else NAN]
    return np.array(out, np.float32)
