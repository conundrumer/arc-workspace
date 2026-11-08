"""A stored table at one assignment as the feature code reads it: the column types, the cells, the rows grouped on the Example column, and
the task's train grids. No engine object.

  table_at(stored, n_train, n_test) -> TableAt
  TaskCtx(task_json)                -> the train pairs and the test inputs; a test output is dropped here, so no feature can receive one
"""
import hashlib
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy import ndimage  # pyright: ignore[reportMissingImports]

import row_store as RS
import table_hash as TH

EIGHT = np.ones((3, 3), int)


@dataclass
class Rw:
    """One Rows: the rows of one example under one constraint model, without the Example column."""
    n: int  # row count
    body: np.ndarray  # int32 (n, cells), in the order of the cells
    boxes: np.ndarray | None  # float32 (n, Box columns, 2)
    key: bytes  # a digest of the content: the order of Rows within an example


@dataclass
class TableAt:
    types: list[str]  # the column types without Example, in the order of the cells
    cols: list[tuple[str, int, int]]  # (type, first cell, cells)
    width: int
    per_example: dict[int, list[Rw]]  # example index (train 0 .. n_train - 1, then the test inputs) -> its distinct Rows, sorted by key
    counts_only: bool
    hash: str | None  # None: the table has no TableHash
    n_train: int
    n_test: int
    task_level: bool = False  # the engine evaluated the table once for the task: its example keys have an item of kind 0
    native: bool = False  # the table's own Type has an Example column (the store adds one to a Type that has none)
    empty: Rw = field(default_factory=lambda: Rw(0, np.zeros((0, 0), np.int32), None, b''))

    def rows_of(self, e: int) -> list[Rw]:
        """The Rows of example e; one empty Rows where the table has none there."""
        return self.per_example.get(e) or [self.empty]


def example_index(code: int, n_train: int) -> int:
    kind, idx = divmod(code, RS.EX_BASE)
    return idx if kind == 1 else n_train + idx


def table_at(t: RS.StoredTable, n_train: int, n_test: int, native: bool = False) -> TableAt:
    ex_pos = t.types.index('Example')
    spans = TH.spans(t.types)
    a, b = spans[ex_pos]
    types = [x for x in t.types if x != 'Example']
    cols, at = [], 0
    for x in types:
        w = TH.WIDE.get(x, 1)
        cols.append((x, at, w))
        at += w
    per: dict[int, dict[bytes, Rw]] = {}
    for r in t.rows:
        body = np.delete(r.cells, np.s_[a:b], axis=1) if r.cells.shape[1] else r.cells
        if body.shape[1] != at:
            body = np.zeros((len(r.cells), at), np.int32)
        key = hashlib.blake2b(body.tobytes() + r.n.to_bytes(8, 'little'), digest_size=8).digest()
        rw = Rw(r.n, body, r.boxes, key)
        exs = range(n_train + n_test) if r.ex == RS.NO_EXAMPLE else [example_index(r.ex, n_train)]
        for e in exs:
            per.setdefault(e, {})[key] = rw
    tab = TableAt(types, cols, at, {e: [d[k] for k in sorted(d)] for e, d in per.items()}, t.counts_only, t.hash, n_train, n_test,
                   task_level=any(k[0] == 0 for k in t.examples), native=native)
    tab.empty = Rw(0, np.zeros((0, at), np.int32), None, b'')
    return tab


# ---------------------------------------------------------------------- the task's grids


def obj_shapes(mask: np.ndarray, area: int, lo: int = 3, hi: float = .6) -> set:
    """Set of shapes (height, width, packed cells) of the 8-connected parts of mask with 3 or more cells and at most hi of the area."""
    if not mask.any():
        return set()
    lab, _ = ndimage.label(mask, EIGHT)
    out = set()
    for i, sl in enumerate(ndimage.find_objects(lab)):
        m = lab[sl] == i + 1
        c = int(m.sum())
        if lo <= c <= hi * area:
            out.add((m.shape[0], m.shape[1], np.packbits(m).tobytes()))
    return out


class Ex:
    """One grid pair (train) or one test input."""

    def __init__(self, a, b=None):
        self.a = np.asarray(a, np.int16)
        self.h, self.w = self.a.shape
        self.area = self.h * self.w
        cnt = np.bincount(self.a.ravel(), minlength=10)
        self.bg = int(cnt.argmax())
        self.fg = self.a != self.bg
        self.colors = frozenset(int(c) for c in np.nonzero(cnt)[0])
        self.cmasks = [self.a == c for c in self.colors]
        self.incls = {m.tobytes() + bytes(m.shape) for m in self.cmasks}
        self.fgshare = float(self.fg.mean())
        self.iobj: set | None = None
        self.b: Any = None
        if b is not None:
            self.b = np.asarray(b, np.int16)
            self.ho, self.wo = self.b.shape
            self.oarea = self.ho * self.wo
            oc = np.bincount(self.b.ravel(), minlength=10)
            self.obg = int(oc.argmax())
            self.ofg = self.b != self.obg
            self.ocolors = frozenset(int(c) for c in np.nonzero(oc)[0])
            self.ohist = oc / oc.sum()
            self.same = (self.ho, self.wo) == (self.h, self.w)
            self.changed = (self.a != self.b) if self.same else None
            self.nchanged = int(self.changed.sum()) if self.changed is not None else 0
            self.nofg = int(self.ofg.sum())
            self.ocmasks = [self.b == c for c in self.ocolors]
            self.oincls = {m.tobytes() + bytes(m.shape) for m in self.ocmasks}
            self.newcolors = self.ocolors - self.colors
            self.base = self.a if self.same else np.full((self.ho, self.wo), self.obg, np.int16)
            self.base_err = self.nchanged if self.same else self.nofg
            self.chist = None
            if self.changed is not None and self.nchanged:
                ch = np.bincount(self.b[self.changed], minlength=10)
                self.chist = ch / ch.sum()
            self.oobj: set | None = None

    def in_objs(self) -> set:
        if self.iobj is None:
            s: set = set()
            for c in self.colors:
                s |= obj_shapes((self.a == c) & self.fg, self.area)
            self.iobj = s
        return self.iobj

    def out_objs(self) -> set:
        if self.oobj is None:
            s: set = set()
            for c in self.ocolors:
                s |= obj_shapes((self.b == c) & self.ofg, self.oarea)
            self.oobj = s
        return self.oobj


class TaskCtx:
    """The train pairs and the test inputs. A test item's output is dropped here, so no feature code can receive it."""

    def __init__(self, task: dict):
        self.train = [Ex(p['input'], p['output']) for p in task['train']]
        self.test = [Ex(x['input']) for x in task['test']]
        self.n_train, self.n_test = len(self.train), len(self.test)
        self.grids = [(p['input'], p['output']) for p in task['train']]


def fsum(v) -> float:
    return math.fsum(sorted(v))
