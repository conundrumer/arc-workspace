"""The only reader of the engine's export in the sample build.

`arclog.step_tables(..., by_assignment=True, rows=True)` writes a row of `tables` for each table at each of its assignments: `query` (the
engine's QueryHash, `StudyProgram.query_hash`; `has_query` tells whether the row has one), `name` (the output Name), `hash` (the
TableHash), `hashed`, `capped` and `features` (the engine's features); the part `assignments` (for each such row, each DET it depends on, by relation
name, with the value hash of its value, and, where the export gives `det_query`, the DET's QueryHash); the part `example_keys`; and `entries`, the TableRows of the row of `tables`, one entry for each example and
constraint model, with the full rows. If the export changes,
only `read_export` changes: it must give the same `ExportTable`s.

  read_export(M, ct) -> list[ExportTable]     M: the kit's `mmod`; ct: a `step_tables` result by assignment, with rows
"""
from dataclasses import dataclass, field
from typing import Any

import numpy as np

EXAMPLE_TASK, EXAMPLE_TRAIN, EXAMPLE_TEST = 0, 1, 2


class ExportError(Exception):
    """The export gives no table here."""


@dataclass
class Entry:
    kind: int  # example kind: 0 task, 1 train, 2 test
    index: int  # example index within its kind
    model: int  # the engine's number of the constraint model; local to the entry's table and example
    complete: bool  # False: the engine gives no rows for the entry
    n: int  # row count
    rows: np.ndarray | None  # int32, shape (n, cells), in the engine's order of columns
    boxes: np.ndarray | None  # float32, shape (n, Box columns, 2): extents (height, width), NaN where unknown


@dataclass
class At:
    """A table at one assignment."""
    query: str | None  # the engine's QueryHash, 32 hex digits; None for a body table
    hash: str | None  # the TableHash, 32 hex digits; None where the engine gives none
    capped: bool  # the engine stopped the table's walk at the cap of assignments
    features: list[float]  # the engine's features, in the order of `arclog.table_feature_names()` (82; the first 12 are `table_vec.ENGINE_NAMES`)
    dets: list[tuple[str, str]]  # (the DET's relation name, the value hash of its value)
    entries: list[Entry]
    keys: list[tuple[int, int, int, int, int]]  # (kind, index, distinct, rows, hash) of each example
    det_queries: list[str | None] = field(default_factory=list)  # the QueryHash of each DET of `dets`, 32 hex digits, None for a base DET; empty where the export gives no `det_query`


@dataclass
class ExportTable:
    slot: int  # the relation slot
    name: str  # the output Name; empty for a RULE or a DET
    labels: list[str]
    types: list[str]
    at: list[At] = field(default_factory=list)  # in the engine's order of assignments


def hex_of(raw: bytes) -> str:
    """The 32 hex digits of a 16-byte little-endian value (`format(query_hash, '032x')`)."""
    return format(int.from_bytes(raw, 'little'), '032x')


def read_export(M: Any, ct: Any) -> list[ExportTable]:
    T = ct.tables
    n = len(T['form'])
    if n and not hasattr(ct, 'example_keys'):
        raise ExportError('not an export by assignment')
    rel = M.col(ct, 'tables', 'relation')
    tnum = M.col(ct, 'tables', 'table')
    df, hs = bytes(memoryview(T['query']).cast('B')), bytes(memoryview(T['hash']).cast('B'))
    has_def, hashed, capped = (np.frombuffer(memoryview(T[k]).cast('B'), dtype=np.uint8) for k in ('has_query', 'hashed', 'capped'))
    feats = np.frombuffer(memoryview(T['features']).cast('B'), dtype=np.float32).reshape(n, -1) if n else np.zeros((0, 0), np.float32)
    V = np.frombuffer(memoryview(ct.values).cast('B'), dtype=np.int32)
    et, ex, ei = M.col(ct, 'entries', 'table'), M.col(ct, 'entries', 'example_kind'), M.col(ct, 'entries', 'example_index')
    ek, er, eo = M.col(ct, 'entries', 'kind'), M.col(ct, 'entries', 'rows'), M.col(ct, 'entries', 'offset')
    xo, em = M.col(ct, 'entries', 'extent_offset'), M.col(ct, 'entries', 'model')
    xst = ct.entries['extent_status']
    stop, vstop, efault = ct.entries['stop_bound'], ct.entries['value_stop_bound'], ct.entries['fault']
    at_t, at_d = M.col(ct, 'assignments', 'table'), ct.assignments['det']
    at_v = bytes(memoryview(ct.assignments['value']).cast('B'))
    kt = M.col(ct, 'example_keys', 'table')
    kk, ki, kd = (M.col(ct, 'example_keys', k) for k in ('kind', 'index', 'distinct'))
    kr, kh = M.col(ct, 'example_keys', 'rows'), M.col(ct, 'example_keys', 'hash')
    by_row: dict[int, list[int]] = {}
    for e in range(len(et)):
        by_row.setdefault(int(et[e]), []).append(e)
    dets: dict[int, list[tuple[str, str]]] = {}
    for q in range(len(at_t)):
        dets.setdefault(int(at_t[q]), []).append((str(at_d[q]), at_v[q * 16:q * 16 + 16].hex()))
    det_queries: dict[int, list[str | None]] = {}
    if 'det_query' in ct.assignments:
        at_q, at_has = bytes(memoryview(ct.assignments['det_query']).cast('B')), M.col(ct, 'assignments', 'has_det_query')
        for q in range(len(at_t)):
            det_queries.setdefault(int(at_t[q]), []).append(hex_of(at_q[q * 16:q * 16 + 16]) if at_has[q] else None)
    keys: dict[int, list[tuple[int, int, int, int, int]]] = {}
    for q in range(len(kt)):
        keys.setdefault(int(kt[q]), []).append((int(kk[q]), int(ki[q]), int(kd[q]), int(kr[q]), int(kh[q])))
    tables: dict[int, ExportTable] = {}
    for r in range(n):
        if rel[r] < 0:
            continue
        types = [str(t) for t in T['column_types'][r]]
        boxcols = {i: q for q, i in enumerate(i for i, t in enumerate(types) if t == 'Box')}
        xcols = list(T['extent_columns'][r])
        tw = sum(4 if str(t) in M.WIDE else 1 for t in types)
        entries = []
        for e in by_row.get(r, ()):
            cnt = int(er[e])
            complete = not (ek[e] != 0 or stop[e] or vstop[e] or efault[e])
            rows = boxes = None
            if complete:
                rows = V[eo[e]:eo[e] + cnt * tw].reshape(cnt, tw).copy()
                if boxcols and xcols and xo[e] >= 0:
                    boxes = np.full((cnt, len(boxcols), 2), np.nan, np.float32)
                    for i in range(cnt):
                        for j, c in enumerate(xcols):
                            st_ = xst[e][i][j] if e < len(xst) and i < len(xst[e]) and j < len(xst[e][i]) else 0
                            if st_ == 1 and c in boxcols:
                                k = xo[e] + (i * len(xcols) + j) * 2
                                boxes[i, boxcols[c]] = (V[k], V[k + 1])
            entries.append(Entry(int(ex[e]), int(ei[e]), int(em[e]), complete, cnt, rows, boxes))
        at = At(hex_of(df[r * 16:r * 16 + 16]) if has_def[r] else None, hex_of(hs[r * 16:r * 16 + 16]) if hashed[r] else None, bool(capped[r]),
                [float(x) for x in feats[r]], dets.get(r, []), entries, keys.get(r, []), det_queries.get(r, []))
        t = tables.setdefault(int(tnum[r]), ExportTable(int(rel[r]), str(T['name'][r]), [str(x) for x in T['column_labels'][r]], types))
        t.at.append(at)
    return list(tables.values())
