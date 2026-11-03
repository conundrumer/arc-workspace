"""Normal form of a table: worlds of examples of typed rows. See design.md, "Normal form of a table".

  read_table(types, x_rows, n_train, n_test) -> Table

`types` are the column types in column order (record field table_types). `x_rows` is the record's list of
[[kind, index], rows, row count, {DET slot: rows}, model, extents]. Nothing here reads order of entries, columns or rows,
Ident values as values, or test outputs (the task loader drops them).
"""
import zlib

import numpy as np

WIDE = {'Position': 4, 'Box': 4, 'Offset': 4}
MAX_WORLDS = 8


class Table:
    """types0: all column types, as given. cols: [(type, start, width)] of the columns the rows keep (no Example column).
    worlds: list of {example: int32 array (n, width)}. An example with no entry in a world is absent from its dict.
    boxdims: per world, {example: (n, boxes, 2) array of box height and width, NaN where unknown}, one per Box column."""

    def __init__(self):
        self.types0 = []
        self.cols = []
        self.width = 0
        self.worlds = []
        self.boxdims = []
        self.n_worlds = 0
        self.capped = False
        self.n_train = 0
        self.n_test = 0
        self.has_example = False
        self.ident = []

    def col_idx(self, typ):
        return [i for i, c in enumerate(self.cols) if c[0] == typ]


def _world_key(e3):
    return tuple(sorted((len(v), tuple(sorted(map(tuple, v)))) for v in (e3 or {}).values()))


def _content_hash(world, ident_cols):
    h = 0
    for ex in sorted(world):
        a = world[ex]
        if ident_cols:
            keep = [i for i in range(a.shape[1]) if i not in ident_cols]
            a = a[:, keep]
        if len(a) and a.shape[1]:
            a = a[np.lexsort(a.T[::-1])]
        h = zlib.crc32(a.tobytes(), zlib.crc32(np.int64(ex).tobytes(), h))
    return h


def read_table(types, x_rows, n_train, n_test):
    t = Table()
    t.n_train, t.n_test = n_train, n_test
    t.types0 = list(types)
    nex = n_train + n_test
    w = [WIDE.get(x, 1) for x in types]
    off = [sum(w[:i]) for i in range(len(w))]
    ex_col = types.index('Example') if 'Example' in types else None
    t.has_example = ex_col is not None
    cols, at = [], 0
    for i, x in enumerate(types):
        if i == ex_col:
            continue
        cols.append((x, at, w[i]))
        at += w[i]
    t.cols, t.width = cols, at
    keep = [off[i] + k for i in range(len(types)) if i != ex_col for k in range(w[i])]
    wide_seen, boxes = 0, []
    for x in types:
        if x in WIDE:
            if x == 'Box':
                boxes.append(wide_seen)
            wide_seen += 1
    t.ident = [c[1] for c in cols if c[0] == 'Ident']
    worlds = {}
    for e in x_rows or []:
        kind, idx = e[0]
        rows, nrows, slots = e[1], e[2], e[3]
        if len(rows) < nrows:
            t.capped = True
        a = np.asarray(rows, dtype=np.int32).reshape(len(rows), sum(w))
        ext = e[5] if len(e) > 5 else None
        key = _world_key(slots)
        wd = worlds.setdefault(key, ({}, {}))
        if boxes and ext is not None and len(ext) == len(rows):
            bd = np.full((len(rows), len(boxes), 2), np.nan)
            for r, xs in enumerate(ext):
                for q, slot in enumerate(boxes):
                    if xs is not None and len(xs) > slot and xs[slot] is not None:
                        bd[r, q] = xs[slot]
        else:
            bd = None
        if ex_col is not None and kind == 0:
            exv = a[:, off[ex_col]]
            body = a[:, keep]
            for v in np.unique(exv):
                ex = int(v) if v < n_train else int(v)  # value under n_train is a train example, past it test example value - n_train
                m = exv == v
                wd[0][ex] = np.concatenate([wd[0][ex], body[m]]) if ex in wd[0] else body[m]
                if bd is not None:
                    wd[1][ex] = bd[m]
        else:
            body = a[:, keep]
            exs = range(nex) if kind == 0 else [idx if kind == 1 else n_train + idx]
            for ex in exs:
                wd[0][ex] = np.concatenate([wd[0][ex], body]) if ex in wd[0] else body
                if bd is not None:
                    wd[1][ex] = bd
    t.n_worlds = len(worlds)
    items = list(worlds.values())
    if len(items) > MAX_WORLDS:
        ic = set(t.ident)
        items.sort(key=lambda wb: _content_hash(wb[0], ic))
        items = items[:MAX_WORLDS]
    t.worlds = [wb[0] for wb in items]
    t.boxdims = [wb[1] for wb in items]
    return t


def ident_classes(a, start):
    """Sizes of the groups of rows that share one Ident value in column `start`. Values themselves are not read."""
    if len(a) == 0:
        return np.zeros(0, np.int64)
    return np.unique(a[:, start], return_counts=True)[1]
