"""Checks of the invariants that the layout of a tables export states (see `tables_export.py`).

    python engine/arclog-py/export_checks.py <export dir> [--sample N | --all] [--seed S] [--streams <dir>] [--jobs N]

It needs numpy and pandas (and pyarrow for the command), and no `arclog`. `tables_export` calls `check_part` on each part
it writes, which checks every case, the copy flows' values included. The command checks an existing export: the files of every case, and the
values of a sample of N cases (100 by default; `--all` takes every case; `--seed` picks the sample). It prints
one line per violated invariant, with the count of its violations, the number of its cases and three examples,
then a total, and exits with status 1 where any violation stands. `--jobs N` sets the number of worker processes that check the cases (every core by default; 1 runs in the one process); the report is the same at every N. A change to this module, or to the engine code that writes the export's files (`engine/arclog/src/eval/flows.rs`, `engine/arclog/src/decode/`), runs `engine/arclog-py/roundtrip_check.py` with an `arclog` built from its tree before its merge.

`--streams <dir>` also reads `cases.npz` of the streams export (`lm/export.py`) in that directory and checks
that each table of the export other than an evidence table has a token inside its case's stream at a step the
model writes, that the stream's mask admits each model-written token, and that each case of the streams export
has tables. The number of cases with tables and no stream is printed and is no violation.
"""
import collections, concurrent.futures, heapq, json, multiprocessing, os, random, sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__)) + "/../.."
TASKS = f"{ROOT}/data/tasks"
ROWS, COUNT = 0, 1      # the `kind` of an entry
COPY, COMPUTED, CONSTANT, LIB_NAME = 0, 1, 2, 3     # the `kind` of a flow
EVIDENCE = 2            # the `point` of an evidence table


def width_of(ty):
    return 4 if ty == "Box" else 1


def orientation_sets(types):
    """{type name: set of cells} from `arclog.orientation_types()`, a Pose type taking D4's set."""
    return {name: set(cells) for name, cells in types}


def cells_of(ty, types):
    """The cells that orientation type `ty` admits, a Pose type taking D4's, or None where `ty` is no orientation type or `types` is None."""
    if types is None:
        return None
    if ty.startswith("Pose"):
        return types.get("D4")
    return types.get(ty)


def copy_keeps_type(ty, source, types):
    """Whether a column of type `ty` may copy a column of type `source`: equal types, or orientation types whose cells of either lie within the other's."""
    if ty == source:
        return True
    mine, theirs = cells_of(ty, types), cells_of(source, types)
    return mine is not None and theirs is not None and (mine <= theirs or theirs <= mine)


def rows_of(df):
    return df.itertuples() if df is not None and len(df) else ()


def _faulted(t):
    return isinstance(t.fault, str)


_wants = (None, {})


def _evidence_cells(task, fact):
    """The sorted distinct rows (example, top, bottom, left, right, color) of the cells of `fact` in the task file."""
    global _wants
    if _wants[0] is not task:
        _wants = (task, {})
    cache = _wants[1]
    if fact not in cache:
        ntrain = len(task["train"])
        want = []
        for k, ex in enumerate(task["train"] + task["test"]):
            if fact not in ex or fact == "output" and k >= ntrain:
                continue
            grid = np.array(ex[fact], dtype=np.int64)
            H, W = grid.shape
            y, x = np.mgrid[0:H, 0:W]
            want.append(np.stack([np.full(H * W, k), y.ravel(), (H - 1 - y).ravel(), x.ravel(), (W - 1 - x).ravel(), grid.ravel()], 1))
        cache[fact] = np.unique(np.concatenate(want), axis=0) if want else np.zeros((0, 6), np.int64)
    return cache[fact]


def check_case(frames, values, task, orientation_types, size=None):
    """The violations of one case, one line `<invariant>: <detail>` each.

    `frames` is {part: DataFrame} of the case in the layout `tables_export.write_part` builds with `frame(case, part)`
    (a table's index is its row, an entry's index is its row), `values` the case's int32 array or None, which skips
    the value checks, `task` the task's JSON, `orientation_types` {type name: set of cells} or None, which skips the
    orientation part of the domain check, and `size` the length of `values` where `values` is None and the runs are
    to be checked against it. A copy from a source table whose entries at an example are not all `Rows` entries is
    not checked at that example.
    """
    out = []
    bad = lambda inv, detail: out.append(f"{inv}: {detail}")
    ntrain, ntest = len(task["train"]), len(task["test"])
    if values is not None:
        size = len(values)
    tabs = frames["tables"].reset_index(drop=True)
    tl = list(rows_of(tabs))
    n = len(tl)
    # tables
    if n < 2 or tl[0].fact != "ex_input" or tl[1].fact != "ex_output" or any(t.point != EVIDENCE or t.token != 0 for t in tl[:2]):
        bad("tables-evidence", "tables 0 and 1 are not ex_input and ex_output at token 0")
    tokens = tabs.token.to_numpy().astype(np.int64)
    for i in np.flatnonzero(np.diff(tokens) < 0):
        bad("tables-token-order", f"table {i + 1} has token {tokens[i + 1]} after {tokens[i]}")
    for t in tl:
        i = t.Index
        if _faulted(t):
            if len(t.column_types):
                bad("tables-faulted-empty", f"table {i} has fault and columns")
            continue
        if t.width != sum(width_of(x) for x in t.column_types):
            bad("tables-width", f"table {i} has width {t.width} for types {list(t.column_types)}")
        nc = len(t.column_types)
        if any(not 0 <= c < nc for k in t.keys for c in k):
            bad("tables-key-columns", f"table {i} has keys {[list(k) for k in t.keys]} for {nc} columns")
        for column, ty, name in ((t.output_position, "Box", "output_position"), (t.output_color, "Color", "output_color")):
            if column >= 0 and not (column < nc and t.column_types[column] == ty):
                bad("tables-output-columns", f"table {i} gives {name} {column}, not a {ty} column of {nc}")
    if (tabs.output_position >= 0).sum() > 1:
        bad("tables-output-columns", f"tables {list(np.flatnonzero(tabs.output_position >= 0))} give output_position")
    # flows
    flows = frames.get("flows")
    has_flow = set()
    for r in rows_of(flows):
        t = tl[r.table] if r.table < n else None
        if t is None or _faulted(t) or t.point == EVIDENCE or not 0 <= r.column < len(t.column_types):
            bad("flows-relation-table", f"flow of table {r.table} column {r.column} names no column of a relation table that has not faulted")
            continue
        has_flow.add((r.table, r.column))
        where = f"flow of table {r.table} column {r.column}"
        if r.kind in (CONSTANT, LIB_NAME):
            if r.source_table != -1 or r.source_column != -1 or r.det != -1:
                bad("flows-no-source", f"{where} of kind {r.kind} has source table {r.source_table}, column {r.source_column}, det {r.det}")
            continue
        rels = list(t.det_relations)
        if r.det < 0 and r.source_relation in rels or r.det >= 0 and not (r.det < len(rels) and rels[r.det] == r.source_relation):
            bad("flows-det", f"{where} has det {r.det} for source relation {r.source_relation!r} of {rels}")
        st = r.source_table
        if st < 0:
            sr = r.source_relation
            if sr.startswith("slot ") or sr in ("ex_input", "ex_output"):
                bad("flows-source-table", f"{where}, kind {r.kind}, from {sr!r} names no source table")
            continue
        if st >= n or st > r.table:
            bad("flows-earlier-table", f"{where} names table {st}")
            continue
        s = tl[st]
        held = list(t.det_types[r.det]) if 0 <= r.det < len(t.det_types) else list(s.column_types)
        if not (r.source_column == -2 or 0 <= r.source_column < len(held)):
            bad("flows-source-column", f"{where} names column {r.source_column} of table {st} with {len(held)}")
            continue
        if st != r.table and not t.depth > s.depth:
            bad("flows-depth", f"{where} has depth {t.depth} and its source table {st} depth {s.depth}")
        if r.kind == COPY:
            sty = "Example" if r.source_column == -2 else held[r.source_column]
            if not copy_keeps_type(t.column_types[r.column], sty, orientation_types):
                bad("flows-copy-type", f"{where} of type {t.column_types[r.column]} copies column {r.source_column} of table {st} of type {sty}")
    for t in tl:
        if t.point != EVIDENCE and not _faulted(t):
            for c in range(len(t.column_types)):
                if (t.Index, c) not in has_flow:
                    bad("flows-every-column", f"table {t.Index} column {c} has no flow")
    # entries and runs
    entries = frames.get("entries")
    en = list(rows_of(entries))
    runs = {}     # (offset, length) -> what: each distinct run once, whatever number of rows point at it
    widths = [t.width for t in tl]
    for r in en:
        t = tl[r.table] if r.table < n else None
        if t is None or _faulted(t):
            bad("entries-table", f"entry {r.Index} names table {r.table}, absent or faulted")
            continue
        if r.example_kind == 0 and r.example_index != 0 or r.example_kind == 1 and r.example_index >= ntrain or \
                r.example_kind == 2 and r.example_index >= ntest or r.example_kind > 2:
            bad("entries-example", f"entry {r.Index} of table {r.table} has example {r.example_kind}/{r.example_index} for {ntrain} train and {ntest} test")
        if r.kind == ROWS:
            if t.projections != 0:
                bad("entries-kind", f"entry {r.Index} is a Rows entry of table {r.table}, which has projections")
            if r.rows:
                runs.setdefault((int(r.offset), int(r.rows) * widths[r.table]), "entry")
        elif r.kind == COUNT:
            if t.projections == 0:
                bad("entries-kind", f"entry {r.Index} is a Count entry of table {r.table}, which has no projections")
            if r.offset != 0:
                bad("entries-offset", f"entry {r.Index} is a Count entry with offset {r.offset}")
        elif r.rows or r.offset:
            bad("entries-offset", f"entry {r.Index} of kind {r.kind} has rows {r.rows} and offset {r.offset}")
    for t in tl:
        if _faulted(t) and any(r.table == t.Index for r in en):
            bad("tables-faulted-empty", f"table {t.Index} has fault and entries")
    for r in rows_of(frames.get("assigned")):
        t = tl[en[r.entry].table] if r.entry < len(en) and en[r.entry].table < n else None
        if t is None or not r.det < len(t.det_widths):
            bad("entries-assigned-det", f"assigned of entry {r.entry} names det {r.det}")
        elif r.rows:
            runs.setdefault((int(r.offset), int(r.rows) * int(t.det_widths[r.det])), "assigned")
    projections = frames.get("projections")
    pwidth = list(projections.width) if projections is not None and len(projections) else []
    for r in rows_of(frames.get("projection_rows")):
        if r.projection >= len(pwidth):
            bad("entries-projection", f"projection row of projection {r.projection} of {len(pwidth)}")
        elif r.defined and r.rows:
            runs.setdefault((int(r.offset), int(r.rows) * int(pwidth[r.projection])), "projection")
    pos = 0
    for (off, length), what in sorted(runs.items()):
        if off != pos:
            bad("runs-tile", f"a {what} run at {off} follows an end at {pos}: " + ("an overlap" if off < pos else "a gap"))
            break
        pos += length
    else:
        if size is not None and pos != size:
            bad("runs-tile", f"the runs end at {pos}, the values at {size}")
    if values is None or any(l.startswith("runs-tile") for l in out):
        return out
    _check_values(frames, values, task, orientation_types, tl, en, ntrain, ntest, bad)
    return out


def _check_values(frames, values, task, orientation_types, tl, en, ntrain, ntest, bad):
    blocks = collections.defaultdict(list)       # table -> [(entry, example, block)] of its Rows entries, each distinct run at an example once, at the first entry that has it
    block_entries = collections.defaultdict(list)    # table -> [(entry, example)] of its Rows entries that hold rows
    seen_blocks = set()                          # (table, example, offset, rows)
    held_none = collections.defaultdict(set)     # table -> the examples of its Rows entries that hold no row
    unseen = collections.defaultdict(set)        # table -> the examples of its entries other than Rows entries
    for r in en:
        if r.kind != ROWS:
            unseen[r.table].add((r.example_kind, r.example_index))
        if r.kind == ROWS and r.table < len(tl) and not _faulted(tl[r.table]):
            w = tl[r.table].width
            if r.rows and w:
                ex = (r.example_kind, r.example_index)
                block_entries[r.table].append((r.Index, ex))
                if (r.table, ex, int(r.offset), int(r.rows)) not in seen_blocks:
                    seen_blocks.add((r.table, ex, int(r.offset), int(r.rows)))
                    blocks[r.table].append((r.Index, ex, values[int(r.offset):int(r.offset) + int(r.rows) * w].reshape(int(r.rows), w)))
            elif not r.rows and w:
                held_none[r.table].add((r.example_kind, r.example_index))
            elif r.rows > 1:
                for k in tl[r.table].keys:
                    if not len(k):
                        bad("values-key", f"table {r.table} entry {r.Index} has {r.rows} rows and a key with no columns")
    # column -> its flows, for each column whose every flow is a copy of a column of an earlier table or of the example
    flows_of = collections.defaultdict(list)
    for f in rows_of(frames.get("flows")):
        flows_of[(f.table, f.column)].append(f)
    def source_type(f):
        """The type of the column flow `f` copies, or None where the flow names none."""
        if f.source_column == -2:
            return "Example"
        held = tl[f.table].det_types[f.det] if 0 <= f.det < len(tl[f.table].det_types) else tl[f.source_table].column_types
        return held[f.source_column] if f.source_column < len(held) else None

    copies = {key: fs for key, fs in flows_of.items() if key[0] < len(tl) and all(
        f.kind == COPY and (f.source_column == -2 or f.source_column >= 0 and 0 <= f.source_table < min(f.table, len(tl)))
        and source_type(f) is not None and copy_keeps_type(tl[f.table].column_types[f.column], source_type(f), orientation_types) for f in fs)}
    needed = {(f.source_table, f.source_column) for fs in copies.values() for f in fs if f.det < 0 and f.source_column >= 0} | set(copies)
    column_values = {}           # (table, column) -> {example: rows}
    for ti in sorted(set(blocks) | set(held_none)):
        bl, t = blocks[ti], tl[ti]
        if not bl:
            # every Rows entry holds no row: each column holds none at each example
            for c, ty in enumerate(t.column_types):
                if (ti, c) in needed:
                    column_values[(ti, c)] = {ex: np.zeros((0, width_of(ty)), np.int32) for ex in held_none[ti]}
            continue
        stack = np.concatenate([b for _, _, b in bl])
        entry = np.repeat([e for e, _, _ in bl], [len(b) for _, _, b in bl])
        if len(stack) > 1:
            a, b = stack[1:], stack[:-1]
            neq = a != b
            first = neq.argmax(1)
            idx = np.arange(len(a))
            same = entry[1:] == entry[:-1]
            distinct = neq.any(1)
            for name, mask in (("values-distinct", same & ~distinct), ("values-sorted", same & distinct & (a[idx, first] < b[idx, first]))):
                if mask.any():
                    bad(name, f"table {ti} entry {entry[1:][mask][0]}: {int(mask.sum())} adjacent rows")
        offs = np.cumsum([0] + [width_of(x) for x in t.column_types])
        for c, ty in enumerate(t.column_types):
            col = stack[:, offs[c]:offs[c + 1]]
            dom = None
            if ty == "Color":
                invalid = (col < 0) | (col > 9)
            elif ty == "Unit":
                invalid = col != 0
            elif ty == "Example":
                invalid = (col < 0) | (col >= ntrain + ntest)
            elif orientation_types is not None and (ty in orientation_types or ty.startswith("Pose")):
                dom = np.array(sorted(orientation_types["D4" if ty.startswith("Pose") else ty]), dtype=np.int32)
                invalid = ~np.isin(col, dom)
            else:
                invalid = None
            if invalid is not None and invalid.any():
                bad("values-domain", f"table {ti} column {c} of type {ty} holds {sorted(set(col[invalid].tolist()))[:5]}")
            if (ti, c) in needed:
                bounds = np.cumsum([0] + [len(b) for _, _, b in bl])
                by_example = collections.defaultdict(list)
                for (_, ex, _), lo, hi in zip(bl, bounds, bounds[1:]):
                    by_example[ex].append(col[lo:hi])
                column_values[(ti, c)] = {ex: np.concatenate(v) for ex, v in by_example.items()}
                for ex in held_none[ti] - set(by_example):
                    column_values[(ti, c)][ex] = col[:0]
        for k in t.keys:
            cells = [i for c in k if 0 <= c < len(t.column_types) for i in range(offs[c], offs[c + 1])]
            if not cells:
                continue
            sub = stack[:, cells]
            order = np.lexsort([sub[:, j] for j in reversed(range(len(cells)))] + [entry])
            s, e = sub[order], entry[order]
            dup = (e[1:] == e[:-1]) & (s[1:] == s[:-1]).all(1)
            if dup.any():
                bad("values-key", f"table {ti} key {[int(c) for c in k]}: {int(dup.sum())} repeated rows, first in entry {e[1:][dup][0]}")
    # the evidence tables
    for g, fact in ((0, "input"), (1, "output")):
        if len(tl) > g and tl[g].fact == f"ex_{fact}" and list(tl[g].column_types) == ["Example", "Box", "Color"]:
            got = np.concatenate([b for _, _, b in blocks[g]]).astype(np.int64) if blocks[g] else np.zeros((0, 6), np.int64)
            got, want = np.unique(got, axis=0), _evidence_cells(task, fact)
            if got.shape != want.shape or (got != want).any():
                diff = sorted(set(map(tuple, got.tolist())) ^ set(map(tuple, want.tolist())))
                bad("values-evidence", f"ex_{fact} has {len(got)} distinct rows, the task file {len(want)}; differing: {diff[:3]}")
    # copy flows
    assigned = collections.defaultdict(list)       # entry -> [(det, rows, offset)]
    for r in rows_of(frames.get("assigned")):
        assigned[r.entry].append((int(r.det), int(r.rows), int(r.offset)))

    def det_values(ti, det, sc):
        """{example: rows} of column `sc` of `det`'s assigned rows at the entries of table `ti`."""
        t = tl[ti]
        if not 0 <= det < len(t.det_types) or not 0 <= sc < len(t.det_types[det]):
            return None
        offs = np.cumsum([0] + [width_of(x) for x in t.det_types[det]])
        found = collections.defaultdict(list)
        read = set()         # (example, rows, offset) of the runs read
        for entry, ex in block_entries[ti]:
            for d, rows, offset in assigned[entry]:
                if d == det and rows and (ex, rows, offset) not in read:
                    read.add((ex, rows, offset))
                    block = values[offset:offset + rows * int(offs[-1])].reshape(rows, int(offs[-1]))
                    found[ex].append(block[:, offs[sc]:offs[sc + 1]])
        return {ex: np.concatenate(v) for ex, v in found.items()}

    for (ti, c), fs in copies.items():
        mine_by = column_values.get((ti, c))
        if mine_by is None:
            continue
        width = width_of(tl[ti].column_types[c])
        parts = []         # per flow: (label, a function from an example to its source rows or None)
        for f in fs:
            if f.source_column == -2:
                parts.append((f, {ex: np.arange(ntrain + ntest, dtype=np.int32)[:, None] if ex == (0, 0) else np.array([[ex[1] if ex[0] == 1 else ntrain + ex[1]]], np.int32) for ex in mine_by}, None))
            elif f.det >= 0:
                parts.append((f, det_values(ti, int(f.det), int(f.source_column)), None))
            else:
                parts.append((f, column_values.get((f.source_table, f.source_column)), (0, 0)))
        if any(p[1] is None for p in parts):
            continue
        for ex, mine in mine_by.items():
            pool = []
            for f, by, shared in parts:
                if f.source_column == -2:
                    pool.append(by[ex])
                elif f.det >= 0:
                    pool.extend([by[ex]] if ex in by else [])
                else:
                    if unseen[f.source_table] and (ex == (0, 0) or unseen[f.source_table] & {ex, shared}):
                        pool = None
                        break
                    pool.extend(by.values() if ex == (0, 0) else [x for x in (by.get(ex), by.get(shared)) if x is not None])
            if pool is None:
                continue
            src = np.concatenate(pool) if pool else mine[:0]
            if src.shape[1:] != mine.shape[1:]:
                continue
            if mine.shape[1] == 1:
                missing = mine[~np.isin(mine[:, 0], src[:, 0])]
            else:
                _, inverse = np.unique(np.concatenate([mine, src]), axis=0, return_inverse=True)
                inverse = inverse.ravel()
                missing = mine[~np.isin(inverse[:len(mine)], inverse[len(mine):])]
            if len(missing):
                sources = ", ".join(f"column {f.source_column} of table {f.source_table}" + (f" det {f.det}" if f.det >= 0 else "") for f in fs)
                bad("values-copy", f"table {ti} column {c} copies {sources}: at example {ex}, {len(missing)} of {len(mine)} rows absent from the sources, e.g. {missing[:2].tolist()}")
                break


def number_rows(tables, entries):
    """Sets the `table` column of `tables` and the `entry` column of `entries`: each row's place among its case's rows, in the frames' order."""
    tables["table"] = tables.groupby(["task", "case"]).cumcount()
    entries["entry"] = entries.groupby(["task", "case"]).cumcount()


def _by_case(df, order):
    """{(task, case): the case's rows sorted by `order`, with a fresh index}."""
    df = df.sort_values(["task", "case", order], kind="stable") if order else df
    return {k: g.reset_index(drop=True) for k, g in df.groupby(["task", "case"], sort=False)}


def check_streams(dir, tables):
    """The violations of the tables export whose `tables` frame is given against `cases.npz` in `dir`, as (case, detail) lines per invariant,
    and the number of cases that have tables and no stream."""
    z = np.load(f"{dir}/cases.npz")
    ids, model, off = z["ids"].astype(np.int64), z["model"].astype(bool), z["offsets"]
    keys = pd.MultiIndex.from_arrays([z["task"].astype(str), z["case"].astype(str)])
    found = collections.defaultdict(list)
    lengths = np.diff(off)
    # steps the mask table covers: model-written tokens, in order
    steps = np.flatnonzero(model)
    byte = z["mask_table"][z["mask_index"], ids[steps] >> 3]
    refused = ((byte >> (ids[steps] & 7)) & 1) == 0
    for step in steps[refused][:1000]:
        c = np.searchsorted(off, step, side="right") - 1
        found["streams-mask"].append((f"{keys[c][0]} {keys[c][1]}", f"the mask refuses model-written token {ids[step]} at {step - off[c]}"))
    rel = tables[tables.point != EVIDENCE]
    at = keys.get_indexer(pd.MultiIndex.from_arrays([rel.task, rel.case]))
    for r, c in zip(rel.itertuples(), at):
        if c < 0:
            continue
        if r.token >= lengths[c]:
            found["streams-token"].append((f"{r.task} {r.case}", f"table {r.table} has token {r.token} past the stream of {lengths[c]}"))
        elif not model[off[c] + r.token]:
            found["streams-token"].append((f"{r.task} {r.case}", f"table {r.table} has token {r.token}, which the model did not write"))
    have = pd.MultiIndex.from_frame(tables[["task", "case"]].drop_duplicates())
    for k in keys[have.get_indexer(keys) < 0]:
        found["streams-tables"].append((f"{k[0]} {k[1]}", "a stream with no tables"))
    return found, int((keys.get_indexer(have) < 0).sum())


def _check_cases(dir, cases, chosen, orientation, part=None):
    """[(case, invariant, detail)] of the violations of the cases in the list `cases` of (task, case) pairs, in the order of `cases`.
    It reads the whole files of the export for the tasks of `cases` alone, or the files of part `part` where that is given, and the values of the cases in the set `chosen`."""
    tasks = sorted({t for t, _ in cases})
    wanted = set(cases)
    def read(name, columns=None):
        path = f"{dir}/{name}.parquet" if part is None else f"{dir}/parts/{part:05d}.{name}.parquet"
        if part is None:
            df = pd.read_parquet(path, columns=columns, filters=[("task", "in", tasks)])
        else:       # a part file is small, and a filter on the `task` of an empty one, whatever its type, can fail
            df = pd.read_parquet(path, columns=columns)
            df = df[df.task.isin(tasks)] if len(df) else df
        return df[pd.MultiIndex.from_frame(df[["task", "case"]]).isin(wanted)] if len(df) else df
    if part is None:
        tables = read("tables")
        entries = read("index", ["task", "case", "entry", "table", "example_kind", "example_index", "kind", "rows", "offset"])
    else:
        tables, entries = read("tables"), read("entries")
        number_rows(tables, entries)
    split = {"tables": _by_case(tables, "table"), "entries": _by_case(entries, "entry")}
    for name in ("flows", "assigned", "projections", "projection_rows"):
        split[name] = _by_case(read(name), None)
    task_json, found = {}, []
    for key in cases:
        task, case = key
        if task not in task_json:
            task_json[task] = json.load(open(f"{TASKS}/{task}.json"))
        path = f"{dir}/values/{task}/{case}.i32"
        frames = {p: split[p][key] for p in split if key in split[p]}
        frames.setdefault("entries", pd.DataFrame())
        size = os.path.getsize(path) // 4 if os.path.exists(path) else None
        if size is None:
            found.append((key, "values-file", "no values file"))
        values = np.fromfile(path, np.int32) if key in chosen and size is not None else None
        for line in check_case(frames, values, task_json[task], orientation, size=size):
            inv, detail = line.split(": ", 1)
            found.append((key, inv, detail))
    return found


def shares(dir, cases, chosen, jobs):
    """`cases` cut into at most `jobs` lists of whole cases, each in the order of `cases`, by greedy longest-processing-time assignment.
    A case weighs the size of its values file, a tenth of it where its values are not checked."""
    def weight(key):
        path = f"{dir}/values/{key[0]}/{key[1]}.i32"
        size = os.path.getsize(path) if os.path.exists(path) else 0
        return size if key in chosen else size / 10
    heap = [(0, i) for i in range(min(jobs, len(cases)))]
    shares = [[] for _ in heap]
    for pos, key in sorted(enumerate(cases), key=lambda pk: -weight(pk[1])):
        load, i = heapq.heappop(heap)
        shares[i].append(pos)
        heapq.heappush(heap, (load + weight(key), i))
    return [[cases[pos] for pos in sorted(share)] for share in shares if share]


def check_part(out, k, cases):
    """The violations of the cases in the list `cases` of (task, case) pairs, all in part `k` of the export in `out`, with every case's values checked:
    one line `<task> <case>: <invariant>: <detail>` each, in the order of `cases`. It reads `orientation_types.json` of `out` where it stands,
    and `arclog.orientation_types()` otherwise."""
    if os.path.exists(f"{out}/orientation_types.json"):
        types = json.load(open(f"{out}/orientation_types.json"))
    else:
        import arclog
        types = arclog.orientation_types()
    found = _check_cases(out, cases, set(cases), orientation_sets(types), part=k)
    return [f"{task} {case}: {inv}: {detail}" for (task, case), inv, detail in found]


def check_export(dir, sample=100, seed=0, streams=None, out=sys.stdout, jobs=None):
    """Checks the export in `dir` and prints a report; `sample` is the number of cases whose values are checked, None for every case.
    `jobs` is the number of worker processes, `os.cpu_count()` where it is None; the report does not depend on it.
    Returns the Counter of violations by invariant."""
    keys = pd.read_parquet(f"{dir}/tables.parquet", columns=["task", "case"]).drop_duplicates().sort_values(["task", "case"])
    cases = list(zip(keys.task, keys.case))
    chosen = cases[:]
    random.Random(seed).shuffle(chosen)
    chosen = set(chosen if sample is None else chosen[:sample])
    orientation = None
    if os.path.exists(f"{dir}/orientation_types.json"):
        orientation = orientation_sets(json.load(open(f"{dir}/orientation_types.json")))
    else:
        try:
            import arclog
            orientation = orientation_sets(arclog.orientation_types())
        except ImportError:
            print(f"{dir} holds no orientation_types.json and arclog is not installed: the orientation domains are not checked", file=sys.stderr)
    jobs = jobs or os.cpu_count() or 1
    if jobs == 1 or len(cases) < 2:
        results = [_check_cases(dir, cases, chosen, orientation)]
    else:
        cut = shares(dir, cases, chosen, jobs)
        with concurrent.futures.ProcessPoolExecutor(len(cut), mp_context=multiprocessing.get_context("spawn")) as pool:
            futures = [pool.submit(_check_cases, dir, share, chosen & set(share), orientation) for share in cut]
            results = [f.result() for f in futures]
    position = {key: i for i, key in enumerate(cases)}
    found = collections.defaultdict(list)
    for key, inv, detail in sorted((item for r in results for item in r), key=lambda item: position[item[0]]):
        found[inv].append((f"{key[0]} {key[1]}", detail))
    unmatched = None
    if streams:
        more, unmatched = check_streams(streams, pd.read_parquet(f"{dir}/tables.parquet"))
        for inv, items in more.items():
            found[inv] += items
    counts = collections.Counter({inv: len(items) for inv, items in found.items()})
    for inv in sorted(found):
        items = found[inv]
        print(f"{inv}: {len(items)} in {len({c for c, _ in items})} cases; e.g. " + " | ".join(f"{c}: {d}" for c, d in items[:3]), file=out)
    if unmatched is not None:
        print(f"{unmatched} cases with tables have no stream (no violation)", file=out)
    print(f"checked {len(cases)} cases ({len(chosen)} with values): {sum(counts.values())} violations", file=out)
    return counts


if __name__ == "__main__":
    args, dir, sample, seed, streams, jobs = sys.argv[1:], None, 100, 0, None, None
    while args:
        a = args.pop(0)
        if a == "--sample": sample = int(args.pop(0))
        elif a == "--all": sample = None
        elif a == "--seed": seed = int(args.pop(0))
        elif a == "--streams": streams = args.pop(0)
        elif a == "--jobs": jobs = int(args.pop(0))
        else: dir = a
    if dir is None:
        sys.exit(__doc__)
    sys.exit(1 if check_export(dir, sample, seed, streams, jobs=jobs) else 0)
