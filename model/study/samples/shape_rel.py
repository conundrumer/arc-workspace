"""The relative forms of a writing point's table tokens' shape values, which the fit's loader (fit_trees.py) and the writer's serving block compute alike.

At a point, each table token has a value per column: one number of one shape of the feature language's shape vector, for the token's table. A shape that a
table's vector lacks has its default value, 0. A NaN value (the shape has no value at any example of its scope) takes no part. Over the point's table tokens,
column by column:
- `rank`: the value's rank among the defined values, from 0 (least) to 1 (greatest), with tied values at their mean rank; 0.5 where only one value is
  defined; NaN where the value is NaN.
- `mdiff`: the value less the median of the defined values, over their span (greatest less least); 0 where all defined values are equal; NaN where the value
  is NaN.

The module also holds what chooses the columns and fills them, for the loader and for serving:
- A table's record is `(hashes, values, stopped)`: a uint64 array of m shape hashes, a float32 array (m, 3) of each shape's least, mean and most, and whether the walk stopped
  (`stopped` may be left out where false). A hash a record lacks has the default value, 0; a stopped record is NaN in every shape. `decode` reads the two base64 fields of a `shapes` record. `combine` makes one token's record from the records of its tables.
- `columns(point_tables, spec)` is the matrix of one point: a row per table token, a column per name of the spec, with the NaN rules of the point.
- `ShapeCounts` and `kept_spec` choose the shapes from the training points, and `ColumnHash` finds the columns that are equal on every training point.
- A column's name is `shape_<rank|mdiff>:<hash as 16 hex digits>:<least|mean|most>`; `Spec.of_names` reads a model's columns back from them.
"""
import base64
import re

import numpy as np

NUMBERS = ('least', 'mean', 'most')
FORMS = ('rank', 'mdiff')
NAME = re.compile(r'shape_(rank|mdiff):([0-9a-f]+):(least|mean|most)')


def hex_of(h):
    return f'{int(h):016x}'


def name_of(form, h, number):
    return f'shape_{form}:{hex_of(h)}:{NUMBERS[number]}'


def decode(h, v, stopped=False):
    """The record `(hashes, values, stopped)` of the base64 fields `h` (uint64 hashes) and `v` (float32, n x 3, little-endian) and the `stopped` flag of a `shapes` record."""
    hashes = np.frombuffer(base64.b64decode(h), '<u8').astype(np.uint64)
    values = np.frombuffer(base64.b64decode(v), '<f4').astype(np.float32).reshape(-1, 3)
    if len(hashes) != len(values):
        raise ValueError(f'{len(hashes)} hashes and {len(values)} value rows')
    return hashes, values, bool(stopped)


def is_stopped(record):
    return len(record) > 2 and bool(record[2])


def combine(vectors):
    """One record from the records of a token's tables, one per assignment: the least of the leasts, the mean of the means and the greatest of the mosts. A hash that an
    assignment's record lacks counts as 0 there. A NaN stays NaN: where any assignment's value is NaN, so is the combined one. A stopped table (the engine's walk stopped at its
    cell bound) is NaN in every shape, the ones it lists and the ones it lacks, so any stopped table makes the combined record stopped: NaN in every shape, with the hashes of all the
    tables listed (they say which shapes exist). The hashes come out sorted."""
    vectors = list(vectors)
    if not vectors:
        return np.zeros(0, np.uint64), np.zeros((0, 3), np.float32), False
    u = np.unique(np.concatenate([r[0] for r in vectors]))
    if any(is_stopped(r) for r in vectors):
        return u, np.full((len(u), 3), np.nan, np.float32), True
    dense = np.zeros((len(vectors), len(u), 3), np.float32)
    for a, r in enumerate(vectors):
        dense[a, np.searchsorted(u, r[0])] = r[1]
    out = np.empty((len(u), 3), np.float32)
    out[:, 0] = dense[:, :, 0].min(axis=0)
    out[:, 1] = dense[:, :, 1].astype(np.float64).mean(axis=0)
    out[:, 2] = dense[:, :, 2].max(axis=0)
    return u, out, False


class Spec:
    """The columns of a model, by name: each is the rank or the median difference form of one number of one shape."""

    def __init__(self, names):
        self.names = list(names)
        parsed = []
        for n in self.names:
            m = NAME.fullmatch(n)
            if not m:
                raise ValueError(f'{n!r} is not a shape column name')
            parsed.append((m.group(1), int(m.group(2), 16), NUMBERS.index(m.group(3))))
        self.hashes = np.array(sorted({h for _, h, _ in parsed}), np.uint64)
        pairs = {}  # (shape's index in self.hashes, number) -> index in the pairs
        self.is_rank = np.array([f == 'rank' for f, _, _ in parsed], bool)
        self.pair_of = np.zeros(len(parsed), np.int64)
        for j, (_, h, number) in enumerate(parsed):
            self.pair_of[j] = pairs.setdefault((int(np.searchsorted(self.hashes, np.uint64(h))), number), len(pairs))
        self.pair_cols = np.array([s * 3 + number for s, number in pairs], np.int64)

    @staticmethod
    def of_names(names):
        """The Spec of the names among `names` that are shape columns, or None where there are none."""
        got = [n for n in names if NAME.fullmatch(n)]
        return Spec(got) if got else None


def columns(point_tables, spec):
    """The columns of one point. `point_tables` is the point's table tokens in order, each as its record `(hashes, values)`. Returns a float32 matrix (table tokens, len(spec.names)):
    the rank or mdiff form (`relative`) of the number that each name gives, over the table tokens. With fewer than 2 table tokens every value is NaN."""
    k, c = len(point_tables), len(spec.names)
    out = np.full((k, c), np.nan, np.float32)
    s = len(spec.hashes)
    if k < 2 or c == 0:
        return out
    v = np.zeros((k, s, 3), np.float32)
    for t, rec in enumerate(point_tables):
        h, vals = rec[0], rec[1]
        if is_stopped(rec):
            v[t] = np.nan
            continue
        if len(h) == 0:
            continue
        at = np.minimum(np.searchsorted(spec.hashes, h), s - 1)
        ok = spec.hashes[at] == h
        v[t, at[ok]] = vals[ok]
    x = v.reshape(k, s * 3)[:, spec.pair_cols]
    flat = (x == x[0]).all(axis=0) & ~np.isnan(x).any(axis=0)  # equal and defined at every token: rank 0.5 and mdiff 0, as `relative` gives
    rank = np.full(x.shape, 0.5, np.float32)
    mdiff = np.zeros(x.shape, np.float32)
    if not flat.all():
        rank[:, ~flat], mdiff[:, ~flat] = relative(x[:, ~flat])
    return np.where(spec.is_rank, rank[:, spec.pair_of], mdiff[:, spec.pair_of])


def _equal(a, b):
    return (a == b) | (np.isnan(a) & np.isnan(b))


def unequal_hashes(point_tables):
    """(hashes, every): the hashes whose value (least, mean, most) is not equal across a point's table tokens, a token without the hash counting as 0. NaN equals NaN. A stopped
    token is NaN in every shape: where all the tokens are stopped, no shape is unequal; where only some are, every shape is, and `every` is True (the hashes then are empty)."""
    k = len(point_tables)
    stopped = sum(is_stopped(t) for t in point_tables)
    if stopped:
        return np.zeros(0, np.uint64), 0 < stopped < k
    h = np.concatenate([t[0] for t in point_tables])
    if len(h) == 0:
        return np.zeros(0, np.uint64), False
    v = np.concatenate([t[1] for t in point_tables])
    u, inv = np.unique(h, return_inverse=True)
    order = np.argsort(inv, kind='stable')
    vs = v[order]
    starts = np.flatnonzero(np.r_[True, inv[order][1:] != inv[order][:-1]])
    present = np.diff(np.r_[starts, len(h)])
    absent = k - present
    bad = np.zeros(len(u), bool)
    for c in range(3):
        x = vs[:, c]
        nan = np.isnan(x)
        nan_n = np.add.reduceat(nan.astype(np.int64), starts)
        lo = np.minimum.reduceat(np.where(nan, np.inf, x), starts)
        hi = np.maximum.reduceat(np.where(nan, -np.inf, x), starts)
        lo, hi = np.where(absent > 0, np.minimum(lo, 0), lo), np.where(absent > 0, np.maximum(hi, 0), hi)
        defined = present - nan_n + absent  # values that are not NaN, the missing ones counting as 0
        bad |= (defined > 0) & ((nan_n > 0) | (lo != hi))
    return u[bad], False


def unstable_hashes(record):
    """The hashes of one table record whose least, mean and most are not all equal (a stopped record is NaN throughout, which is equal)."""
    if is_stopped(record):
        return np.zeros(0, np.uint64)
    h, v = record[0], record[1]
    return h[~(_equal(v[:, 0], v[:, 1]) & _equal(v[:, 1], v[:, 2]))]


class ShapeCounts:
    """What the choice of shapes reads from the training points: per hash, the count of training points (with 2 or more table tokens) where its value is not equal across
    the table tokens, and whether it is stable (least, mean and most equal on every training table token). `every` counts the points where every shape is unequal (some table tokens stopped,
    some not); `universe` holds the hashes of all the records seen."""
    FLUSH = 8_000_000  # pending entries that trigger a merge

    def __init__(self):
        self.keys = np.zeros(0, np.uint64)
        self.counts = np.zeros(0, np.int64)
        self.unstable = np.zeros(0, np.uint64)
        self.universe = np.zeros(0, np.uint64)
        self.every = 0
        self.points = 0  # training points with 2 or more table tokens
        self.tokens = 0
        self._pending: list[tuple[np.ndarray, np.ndarray]] = []
        self._unstable_pending: list[np.ndarray] = []
        self._universe_pending: list[np.ndarray] = []
        self._size = 0

    def add_file(self, points):
        """`points`: for each kept training point of a file that has table tokens, its table tokens' records."""
        seen = {}
        chunks = []
        for tables in points:
            for r in tables:
                seen[id(r)] = r
            if len(tables) >= 2:
                self.points += 1
                got, every = unequal_hashes(tables)
                chunks.append(got)
                self.every += every
        self.tokens += len(seen)
        if chunks:
            k, c = np.unique(np.concatenate(chunks), return_counts=True)
            self._pending.append((k, c.astype(np.int64)))
            self._size += len(k)
        if seen:
            self._universe_pending.append(np.unique(np.concatenate([r[0] for r in seen.values()])))
            self._unstable_pending.append(np.unique(np.concatenate([unstable_hashes(r) for r in seen.values()])))
        if self._size > self.FLUSH:
            self.flush()

    def flush(self):
        if self._pending:
            keys = np.concatenate([self.keys, *(k for k, _ in self._pending)])
            counts = np.concatenate([self.counts, *(c for _, c in self._pending)])
            self.keys, inv = np.unique(keys, return_inverse=True)
            self.counts = np.bincount(inv, weights=counts, minlength=len(self.keys)).astype(np.int64)
            self._pending, self._size = [], 0
        if self._unstable_pending:
            self.unstable = np.unique(np.concatenate([self.unstable, *self._unstable_pending]))
            self._unstable_pending = []
        if self._universe_pending:
            self.universe = np.unique(np.concatenate([self.universe, *self._universe_pending]))
            self._universe_pending = []


def kept_spec(counts, budget):
    """(Spec or None, info): the shapes in the order of their count (most first; equal counts by hash), each with 6 columns (rank and mdiff of least, mean and most), or with 2
    (of the mean) where it is stable, until the next shape no longer fits in `budget` columns. A shape that no training point shows unequal has no column."""
    counts.flush()
    keys = counts.universe
    score = np.full(len(keys), counts.every, np.int64)
    score[np.searchsorted(keys, counts.keys)] += counts.counts
    order = np.lexsort((keys, -score))
    unstable = np.isin(keys, counts.unstable)
    names, stable_kept, kept = [], 0, 0
    for i in order:
        if score[i] <= 0:
            break
        stable = not unstable[i]
        if len(names) + (2 if stable else 6) > budget:
            break
        for number in ((1,) if stable else (0, 1, 2)):
            names += [name_of(form, keys[i], number) for form in FORMS]
        kept += 1
        stable_kept += stable
    info = dict(budget=budget, training_points=counts.points, training_tokens=counts.tokens, shapes_unequal_somewhere=int((score > 0).sum()), points_with_some_stopped=int(counts.every), shapes_kept=kept,
                stable_kept=stable_kept, columns=len(names))
    return (Spec(names) if names else None), info


class ColumnHash:
    """A hash of each column of a spec over the table-token rows of the training points (those with 2 or more table tokens), in the order added: columns with equal hashes are
    equal on every row, NaN equal to NaN. Two 64-bit sums, each over the rows' bits weighed by a pseudo-random number of the row's index."""
    MIX = (np.uint64(0x9E3779B97F4A7C15), np.uint64(0xC2B2AE3D27D4EB4F))

    def __init__(self, width):
        self.sums = np.zeros((2, width), np.uint64)
        self.rows = 0

    @staticmethod
    def _weights(index, seed):
        z = (index + np.uint64(1)) * seed
        z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        return z ^ (z >> np.uint64(31))

    def add(self, matrix):
        """`matrix`: one point's `columns` (table tokens, width)."""
        m = np.asarray(matrix, np.float32)
        bits = np.where(np.isnan(m), np.float32(np.nan), m + np.float32(0)).view(np.uint32).astype(np.uint64) + np.uint64(1)
        index = np.arange(self.rows, self.rows + len(m), dtype=np.uint64)
        with np.errstate(over='ignore'):
            for s, seed in enumerate(self.MIX):
                self.sums[s] += (bits * self._weights(index, seed)[:, None]).sum(axis=0, dtype=np.uint64)
        self.rows += len(m)

    def merged(self, spec):
        """(a Spec of the first column of each group of equal columns, {dropped name: the name kept})."""
        _, first, group = np.unique(self.sums.T, axis=0, return_index=True, return_inverse=True)
        group = group.reshape(-1)
        keep = np.sort(first)
        names = spec.names
        return Spec([names[i] for i in keep]), {names[i]: names[first[group[i]]] for i in range(len(names)) if first[group[i]] != i}


def relative(values):
    """(rank, mdiff) of `values`, a float array (table tokens, columns), each the same shape, float32."""
    v = np.asarray(values, np.float64)
    n, m = v.shape
    rank = np.full((n, m), np.nan)
    mdiff = np.full((n, m), np.nan)
    for j in range(m):
        col = v[:, j]
        ok = ~np.isnan(col)
        k = int(ok.sum())
        if k == 0:
            continue
        x = col[ok]
        if k == 1:
            rank[ok, j] = 0.5
            mdiff[ok, j] = 0.0
            continue
        order = np.argsort(x, kind='stable')
        r = np.empty(k)
        r[order] = np.arange(k, dtype=np.float64)
        for value in np.unique(x):  # ties take their mean rank
            tie = x == value
            if tie.sum() > 1:
                r[tie] = r[tie].mean()
        rank[ok, j] = r / (k - 1)
        lo, hi = x.min(), x.max()
        mdiff[ok, j] = 0.0 if hi == lo else (x - np.median(x)) / (hi - lo)
    return rank.astype(np.float32), mdiff.astype(np.float32)


if __name__ == '__main__':  # a check of the definition on a small case
    rk, md = relative([[1.0, 0.0, np.nan], [3.0, 0.0, 2.0], [3.0, 0.0, np.nan], [2.0, 0.0, np.nan]])
    assert np.allclose(rk[:, 0], [0.0, 2.5 / 3, 2.5 / 3, 1 / 3]), rk[:, 0]
    assert np.allclose(rk[:, 1], 0.5) and np.allclose(md[:, 1], 0.0)
    assert np.isnan(rk[0, 2]) and rk[1, 2] == 0.5 and md[1, 2] == 0.0
    assert np.allclose(md[:, 0], [(1 - 2.5) / 2, (3 - 2.5) / 2, (3 - 2.5) / 2, (2 - 2.5) / 2]), md[:, 0]
    # combine: a hash that one table lacks counts 0 there; a NaN stays NaN
    a = (np.array([5, 9], np.uint64), np.array([[1, 2, 3], [4, 4, 4]], np.float32))
    b = (np.array([5], np.uint64), np.array([[3, 4, np.nan]], np.float32))
    h, v = combine([a, b])[:2]
    assert list(h) == [5, 9] and np.allclose(v[0], [1, 3, np.nan], equal_nan=True) and np.allclose(v[1], [0, 2, 4]), v
    spec = Spec([name_of('rank', 5, 1), name_of('mdiff', 5, 1)])
    t = [(np.array([5], np.uint64), np.array([[0, x, 0]], np.float32)) for x in (1.0, 3.0, 2.0)]
    got = columns(t, spec)
    assert np.allclose(got[:, 0], [0, 1, 0.5]) and np.allclose(got[:, 1], [-0.5, 0.5, 0]), got
    assert np.isnan(columns(t[:1], spec)).all()
    # a stopped table is NaN in every shape, the ones it lists and the ones it lacks
    st = (np.array([5], np.uint64), np.array([[1, 1, 1]], np.float32), True)
    h, v = combine([a, st])[:2]
    assert list(h) == [5, 9] and np.isnan(v).all() and combine([a, st])[2] and is_stopped(st) and not is_stopped(a), v
    assert not is_stopped(combine([a, b]))
    ok_rec = (np.array([5], np.uint64), np.array([[0, 2.0, 0]], np.float32), False)
    stopped_rec = combine([(np.array([7], np.uint64), np.array([[1, 1, 1]], np.float32), True)])
    got = columns([ok_rec, ok_rec, stopped_rec], Spec([name_of('rank', 5, 1), name_of('mdiff', 5, 1), name_of('rank', 8, 1)]))
    assert np.isnan(got[2]).all() and np.allclose(got[:2], [[0.5, 0.0, 0.5]] * 2), got
    c, every = unequal_hashes([ok_rec, ok_rec, stopped_rec])
    assert every and len(c) == 0 and unequal_hashes([stopped_rec, stopped_rec])[1] is False
    print('ok')
