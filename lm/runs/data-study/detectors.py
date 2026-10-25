"""Compute the marks of marks.md as detectors of the first table after the branch, and measure how each ranks the
gold continuation's table against the sampled ones.

    work/lm/.venv/bin/python lm/runs/data-study/detectors.py compute <export> [--parts DIR] [--seconds S] [--tasks T ...]
    work/lm/.venv/bin/python lm/runs/data-study/detectors.py measure <data> [--out FILE]

`compute` loads the rollout export one task at a time through `encoder.load_rollouts` (strict=False,
allow_violations=True) on a copy of the task's rows that holds no flows.parquet, so a table's parents are unknown
and its earlier tables are the tables of the same case with a smaller token (export table < prefix_tables, and the
grid tables ex_input and ex_output). The loader's guard against more than half of the relation tables unseen is
lifted for a task whose own tables are so, since it holds over the whole export. It writes one parquet per task under --parts (default
work/lm/data-study-detectors), skips a task whose parquet is there, stops starting tasks after --seconds, and, once
every task is done, joins the parts into lm/runs/data-study/detectors.parquet. A row of that parquet is one Table
(one DET assignment of an export table) at positions 0 to 3 after the branch: its member and label, its flags as
lm/value_eval.py reads them (after the budgets of the value run: an entry over 10000 rows, a table over 4000 rows),
the inputs of value_eval.features, and, at position 0, the detector values below, computed on the Table's rows
before the budgets. The rows of a Table at a train example are its rows whose entry is that example, as a set; a
task-wide entry's rows count at every train example. A Table whose rows come from a Count entry's projections is
marked `partial` and gets no row detectors.

Filters (0/1):
- f_empty: seen, with 0 rows in every train example;
- f_unseen: faulted or unseen (value_eval's flags, after the budgets);
- f_restate: at every train example, its rows equal those of an earlier Table, or their projection onto distinct
  columns of the same types (viability.py's `restates`);
- f_product: at every train example its rows equal the product of their projections onto the two sides of a split of
  its columns (Example columns left out), with both sides of 2 or more values at some example; tested where no
  example has over PRODUCT_ROWS rows and the Table has at most PRODUCT_COLUMNS such columns;
- f_symmetric: the rows at every example are closed under the swap of two columns of one type, and some row differs
  between the two;
- f_grid: at every train example one row per input cell, with a Box column and a Color column whose pairs are the
  input's cells and colors.

Graded signals (a number each), over the train examples (e):
- log_rows: log(1 + rows summed over e);
- rows_per_cell: mean of rows_e / input cells_e;
- rows_vs_parent: min of rows_e / rows_e of the earlier relation Table with the most rows (none: missing);
- rows_cv: coefficient of variation of rows_e;
- const_share: share of the columns (Example columns left out) of one value at every e with rows;
- fd_pairs: ordered column pairs (a, b) where a's value gives b's at every e with rows, and at some e a is not a key
  and b has 2 or more values; one_to_one: whether some pair of distinct columns gives each other so, with 2 or more
  values at some e;
- fill: mean over e with rows of rows_e / the product of the columns' distinct counts; lack: the mean over e of that
  product less rows_e where fill_e is above 0.8 and below 1, else 0;
- same_rows: share of e whose rows (Example columns left out) equal another e's, beside same_all (every e the same
  rows, not empty);
- jaccard: mean over columns and pairs of e with rows of the Jaccard index of the column's value sets;
- n_zero: e with 0 rows; zero_identity: some e has 0 rows and those e are exactly the ones whose output equals the
  input;
- eq_in_cells, eq_out_cells, eq_out_h, eq_out_w: rows_e equals the input's cells, the output's cells, height or width
  at every e, and some rows_e is above 1;
- eq_earlier: rows_e equals an earlier relation Table's at every e, and some rows_e is above 1;
- out_cover: mean over e where the output differs from the input of the share of those differing output cells that
  a Box column of the Table names (a box of one cell of the output grid; every output cell differs where the
  sizes differ); out_color: of the rows that name such a cell, the share whose Color column (any) holds the output's
  color there.

Signals added from marks.md:
- off_grid: share of rows with a Box of one cell in the input grid's terms that lies off the grid (b5bb5719 &r16);
- one_row_diff: an earlier Table of the same column types differs from it by one row over all e (9565186b &r7);
- asg_n, asg_empty, asg_equal: the DET assignments of the Table's export table: log of their count, the share empty
  in every e, the share of those with rows whose rows at every e equal another assignment's (22425bda &r24, 8e5a5113 &r6);
- splits_like_outputs: the examples grouped by equal rows (Example columns left out) are grouped as the outputs are
  by equal grids, where the outputs fall in 2 or more groups and two outputs are equal (44f52bb0 &r0);
- number_out_size: a Number column whose greatest value at every e is the output's height, or its width, where that
  size varies over e (22425bda &r20);
- cell_count_cv: mean over e of the coefficient of variation of the rows per value of the first Box column
  (2c608aff &r14; a product has the same count at every cell).

`measure` reads detectors.parquet and splits the branch points as lm/value_eval.py does, by the held-out tasks of
<data> (its cases.npz). The lists are those of encoder.value_lists at position 0 (positions=1) with the label
`solving`, in two variants: "graded", the Tables value_excluded leaves out left out, as value_eval does; and "all",
every Table at position 0 kept. Each score is measured with encoder.value_draw_metrics. A filter alone scores
-filter; the filters summed score minus their sum; a graded signal alone takes the sign that ranks better on the
training branch points, a missing value taking the training median. The logistic regression on every detector is
trained as value_eval.logistic is (full-batch Adam, 300 steps, lr 0.05, standardized, seed 0), a missing value
taking the training mean; it is measured on the held-out branch points and in 5-fold cross-validation by task over
every task. value_eval.logistic on value_eval.features is measured at positions 1 and 4 in the variant "graded"; in
the variant "all", the same features are fit as the detectors are, over every Table at position 0. --out (default
lm/runs/data-study/detectors.out) gets the tables.
"""
import argparse, itertools, json, math, os, random, sys, tempfile, time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "lm"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import encoder as E   # noqa: E402
import viability as V   # noqa: E402

PARTS = ("tables", "index", "assigned", "projections", "projection_rows")   # no flows
BUDGET, MAX_ROWS = 10000, 4000   # the value run's --enc-budget and --enc-max-rows
POSITIONS = 4                    # positions written, for the trivial baseline at the value run's --value-positions
PRODUCT_ROWS, PRODUCT_COLUMNS = 3000, 8
SET_ROWS = 20000                 # the most rows at an example for the tests that build row sets
FILTERS = ["f_empty", "f_unseen", "f_restate", "f_product", "f_symmetric", "f_grid"]
GRADED = ["log_rows", "rows_per_cell", "rows_vs_parent", "rows_cv", "const_share", "fd_pairs", "one_to_one", "fill",
          "lack", "same_rows", "same_all", "jaccard", "n_zero", "zero_identity", "eq_in_cells", "eq_out_cells",
          "eq_out_h", "eq_out_w", "eq_earlier", "out_cover", "out_color"]
ADDED = ["off_grid", "one_row_diff", "asg_n", "asg_empty", "asg_equal", "splits_like_outputs", "number_out_size",
         "cell_count_cv"]
DETECTORS = FILTERS + GRADED + ADDED


NOT_COMPUTED = [
    "A rank or order equal to its score: it needs the score's table, which only the flows give; f_restate covers the "
    "case where the rows equal the score's rows.",
    "A lib fact restated, the same in every task: it needs the tables of other tasks.",
    "A complement inside a product; rows that follow from a smaller table and the grid size; an intersection over the "
    "examples of a mostly-chance table; one assignment at which a table differs from its source: each needs the "
    "table's parents, which only the flows give.",
    "A closure walked to a bound read at its last step; a table empty in every example read under NOT; a table equal "
    "to its domain after a NOT of an empty table: each needs how a later clause reads the table.",
    "A second chain that finds a fact already found in other terms; a table built from the inputs that matches one "
    "built from the outputs; the inputs alone killing assignments before an output is read; assignments that agree "
    "though their sources differ: each needs which tables read the outputs, which only the flows give (out_cover, "
    "out_color and asg_empty are the nearest detectors).",
    "A class or an order written as pairs; the same values under other keys in each example; a Number column that "
    "varies where the count drawing is flat; a row count that encodes a value; a row count equal to an earlier "
    "table's at one assignment only; an assignment whose Boxes fit the output grid: computable, but not in a few "
    "lines, and left out.",
    "The section \"Not told by the table, with the earlier tables in view\": by its definition each needs the clause "
    "or the later program.",
]


# ------------------------------------------------------------------ rows

def spans(types):
    o, out = 0, []
    for ty in types:
        w = E.width(ty)
        out.append((o, o + w))
        o += w
    return out


def unique_rows(a):
    if a.shape[1] == 0:
        return a[:1]
    return np.unique(a, axis=0) if len(a) else a


def train_rows(t, n_train):
    """[unique rows [n, w]] per train example, or None where the Table's rows come from projections."""
    if t.evidence:
        keep = t.cells[:, 0] < n_train
        c = t.cells[keep]
        return [unique_rows(c[c[:, 0] == e]) for e in range(n_train)]
    live = ~t.marker
    if live.any() and not t.present[live].all():
        return None
    out = []
    wide = live & (t.example_kind == 0)
    for e in range(n_train):
        sel = live & (((t.example_kind == 1) & (t.example == e)) | wide)
        out.append(unique_rows(t.cells[sel]))
    return out


def keyed_rows(rows):
    """{example: frozenset of row tuples} for viability.restates."""
    return {e: frozenset(map(tuple, r.tolist())) for e, r in enumerate(rows)}


def col_ids(r, sp):
    """The id of each row's value in each column ([n] per column) and each column's distinct count."""
    ids, d = [], []
    for s, e in sp:
        if len(r):
            _, inv = np.unique(r[:, s:e], axis=0, return_inverse=True)
            inv = inv.reshape(-1)
            ids.append(inv); d.append(int(inv.max()) + 1)
        else:
            ids.append(np.zeros(0, np.int64)); d.append(0)
    return ids, d


def n_unique(ids_list):
    if not ids_list or len(ids_list[0]) == 0:
        return 0
    return len(np.unique(np.stack(ids_list, 1), axis=0))


def grid_of(g):
    return np.array(g, np.int32)


def cell_boxes(h, w):
    r, c = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
    return np.stack([r, h - 1 - r, c, w - 1 - c], -1).reshape(-1, 4)


# ------------------------------------------------------------------ detectors

def detectors(t, flags, earlier, asg, pairs, n_train, rows_of):
    """The detector values of Table t (DETECTORS), given its flags, the earlier Tables [(types, rows, is_grid, keyed
    rows or None, rows per example)], the values of `assignments` for its export table, and the task's train pairs."""
    v = {k: np.nan for k in DETECTORS}
    for k in FILTERS:
        v[k] = 0.0
    v["f_unseen"] = float(flags["unseen"] or flags["faulted"])
    if t.unseen is not None:
        return v
    rows = rows_of(t)
    v["partial"] = rows is None
    if rows is None:
        return v
    types = list(t.types)
    sp = spans(types)
    cols = [j for j, ty in enumerate(types) if ty != "Example"]
    n = np.array([len(r) for r in rows], float)
    ins = [grid_of(p["input"]) for p in pairs]
    outs = [grid_of(p["output"]) for p in pairs]
    in_cells = np.array([g.size for g in ins], float)
    out_cells = np.array([g.size for g in outs], float)
    out_h = np.array([g.shape[0] for g in outs], float)
    out_w = np.array([g.shape[1] for g in outs], float)
    nz = n > 0
    v["f_empty"] = float(not nz.any())
    v["log_rows"] = math.log1p(n.sum())
    v["rows_per_cell"] = float((n / in_cells).mean())
    parents = [r for ty, r, g, _, _ in earlier if not g]
    if parents:
        big = max(parents, key=lambda r: sum(len(x) for x in r))
        v["rows_vs_parent"] = float(min(n[e] / max(len(big[e]), 1) for e in range(n_train)))
    v["rows_cv"] = float(n.std() / n.mean()) if n.mean() > 0 else 0.0
    v["n_zero"] = float((~nz).sum())
    same_io = [a.shape == b.shape and (a == b).all() for a, b in zip(ins, outs)]
    v["zero_identity"] = float((~nz).any() and list(~nz) == same_io)
    big1 = (n > 1).any()
    for k, x in (("eq_in_cells", in_cells), ("eq_out_cells", out_cells), ("eq_out_h", out_h), ("eq_out_w", out_w)):
        v[k] = float(big1 and (n == x).all())
    v["eq_earlier"] = float(big1 and any((c == n).all() for _, _, g, _, c in earlier if not g))
    v.update(asg)
    if not nz.any():
        return v
    big_set = max(len(r) for r in rows) > SET_ROWS
    ids = [col_ids(r, sp) for r in rows]
    ex_nz = [e for e in range(n_train) if nz[e]]
    # columns
    if cols:
        v["const_share"] = float(np.mean([all(ids[e][1][j] == 1 for e in ex_nz) for j in cols]))
        fd, one = 0, False
        for a, b in itertools.permutations(cols, 2):
            holds = all(n_unique([ids[e][0][a], ids[e][0][b]]) == ids[e][1][a] for e in ex_nz)
            if not holds:
                continue
            if any(ids[e][1][a] < n[e] and ids[e][1][b] > 1 for e in ex_nz):
                fd += 1
            if a < b and not one and all(n_unique([ids[e][0][a], ids[e][0][b]]) == ids[e][1][b] for e in ex_nz):
                same = types[a] == types[b] and all(
                    (rows[e][:, sp[a][0]:sp[a][1]] == rows[e][:, sp[b][0]:sp[b][1]]).all() for e in ex_nz)
                one = not same and any(ids[e][1][a] >= 2 for e in ex_nz)
        v["fd_pairs"], v["one_to_one"] = float(fd), float(one)
        logprod = [sum(math.log(ids[e][1][j]) for j in cols) for e in ex_nz]
        fills = [n[e] / math.exp(lp) for e, lp in zip(ex_nz, logprod)]
        v["fill"] = float(np.mean(fills))
        v["lack"] = float(np.mean([math.exp(lp) - n[e] if 0.8 < f < 1 else 0.0
                                   for e, lp, f in zip(ex_nz, logprod, fills)]))
        # product of the two sides of a split
        if len(cols) >= 2 and len(cols) <= PRODUCT_COLUMNS and n.max() <= PRODUCT_ROWS:
            for mask in range(1, 2 ** (len(cols) - 1)):
                A = [cols[i] for i in range(len(cols)) if mask >> i & 1]
                B = [c for c in cols if c not in A]
                ok, wide = True, False
                for e in ex_nz:
                    ua, ub = n_unique([ids[e][0][j] for j in A]), n_unique([ids[e][0][j] for j in B])
                    if ua * ub != n[e]:
                        ok = False
                        break
                    wide |= ua >= 2 and ub >= 2
                if ok and wide:
                    v["f_product"] = 1.0
                    break
        # jaccard of the column value sets
        if len(ex_nz) >= 2:
            js = []
            for j in cols:
                s, e_ = sp[j]
                sets = {e: set(map(tuple, rows[e][:, s:e_].tolist())) for e in ex_nz}
                for a, b in itertools.combinations(ex_nz, 2):
                    js.append(len(sets[a] & sets[b]) / len(sets[a] | sets[b]))
            v["jaccard"] = float(np.mean(js))
    # rows with the Example columns left out, per example
    if not big_set:
        noex = [frozenset(map(tuple, (np.concatenate([r[:, sp[j][0]:sp[j][1]] for j in cols], 1) if cols
                                     else r[:, :0]).tolist())) if len(r) else frozenset() for r in rows]
        same = [nz[e] and any(noex[e] == noex[f] for f in range(n_train) if f != e) for e in range(n_train)]
        v["same_rows"] = float(np.mean(same))
        v["same_all"] = float(nz.all() and len(set(noex)) == 1)
        groups = lambda keys: sorted(sorted(i for i, k in enumerate(keys) if k == x) for x in set(keys))
        out_keys = [(g.shape, g.tobytes()) for g in outs]
        v["splits_like_outputs"] = float(2 <= len(set(out_keys)) < n_train and groups(noex) == groups(out_keys))
        # symmetric under a swap of two same-typed columns
        sets = [set(map(tuple, r.tolist())) for r in rows]
        for a, b in itertools.combinations(cols, 2):
            if types[a] != types[b]:
                continue
            perm = list(range(rows[ex_nz[0]].shape[1]))
            (sa, ea), (sb, eb) = sp[a], sp[b]
            perm[sa:ea], perm[sb:eb] = perm[sb:eb], perm[sa:ea]
            differ = any((rows[e][:, sa:ea] != rows[e][:, sb:eb]).any() for e in ex_nz)
            if differ and all(set(map(tuple, rows[e][:, perm].tolist())) == sets[e] for e in ex_nz):
                v["f_symmetric"] = 1.0
                break
        # restatement of an earlier Table
        kx = keyed_rows(rows)
        v["f_restate"] = float(any(V.restates(types, kx, ty, k) for ty, _, _, k, _ in earlier if k is not None))
        # one row from an earlier Table of the same column types
        v["one_row_diff"] = float(any(
            ty == types and k is not None and sum(len(kx[e] ^ k[e]) for e in range(n_train)) == 1
            for ty, _, _, k, _ in earlier))
    # the grid and its cells
    boxes = [j for j, ty in enumerate(types) if ty == "Box"]
    colors = [j for j, ty in enumerate(types) if ty == "Color"]
    numbers = [j for j, ty in enumerate(types) if ty == "Number"]
    grid_hit = bool(boxes and colors)
    covers, matches, hits, off, nrows = [], 0, 0, 0, 0
    for e in range(n_train):
        g, o, r = ins[e], outs[e], rows[e]
        h, w = g.shape
        ho, wo = o.shape
        if grid_hit:
            want = np.concatenate([cell_boxes(h, w), g.reshape(-1, 1)], 1)
            want_set = set(map(tuple, want.tolist()))
            grid_hit = n[e] == h * w and any(
                set(map(tuple, np.concatenate([r[:, sp[b][0]:sp[b][1]], r[:, sp[c][0]:sp[c][1]]], 1).tolist())) == want_set
                for b in boxes for c in colors)
        diff = np.ones((ho, wo), bool) if g.shape != o.shape else (g != o)
        named = np.zeros((ho, wo), bool)
        for b in boxes:
            x = r[:, sp[b][0]:sp[b][1]]
            if len(x) == 0:
                continue
            cell = (x >= 0).all(1) & (x[:, 0] + x[:, 1] == ho - 1) & (x[:, 2] + x[:, 3] == wo - 1)
            rr, cc = x[cell, 0], x[cell, 2]
            named[rr, cc] = True
            dmask = diff[rr, cc]
            hits += int(dmask.sum())
            if colors:
                oc = o[rr[dmask], cc[dmask]]
                matches += int(np.any([r[cell][dmask][:, sp[c][0]] == oc for c in colors], 0).sum())
            one = (h - x[:, 0] - x[:, 1] == 1) & (w - x[:, 2] - x[:, 3] == 1)
            off += int((one & (x < 0).any(1)).sum())
        nrows += len(r)
        if diff.any() and boxes:
            covers.append(float((named & diff).sum() / diff.sum()))
    v["f_grid"] = float(grid_hit)
    if boxes:
        v["out_cover"] = float(np.mean(covers)) if covers else 0.0
        v["out_color"] = matches / hits if hits and colors else 0.0
        v["off_grid"] = off / max(nrows, 1)
        cvs = []
        for e in ex_nz:
            _, cnt = np.unique(rows[e][:, sp[boxes[0]][0]:sp[boxes[0]][1]], axis=0, return_counts=True)
            cvs.append(float(cnt.std() / cnt.mean()))
        v["cell_count_cv"] = float(np.mean(cvs))
    else:
        v["out_cover"] = v["out_color"] = v["off_grid"] = 0.0
    if numbers and len(set(out_h)) > 1 or numbers and len(set(out_w)) > 1:
        hit = False
        for j in numbers:
            if all(nz):
                top = np.array([rows[e][:, sp[j][0]].max() for e in range(n_train)], float)
                hit |= (len(set(out_h)) > 1 and (top == out_h).all()) or (len(set(out_w)) > 1 and (top == out_w).all())
        v["number_out_size"] = float(hit)
    else:
        v["number_out_size"] = 0.0
    return v


def assignments(siblings):
    """asg_n, asg_empty and asg_equal of the Tables of one export table, given each one's rows (None where unseen)."""
    if len(siblings) <= 1:
        return dict(asg_n=0.0, asg_empty=0.0, asg_equal=0.0)
    sib = [s for s in siblings if s is not None]
    keys = [tuple(frozenset(map(tuple, x.tolist())) for x in s) for s in sib if 0 < max(len(x) for x in s) <= SET_ROWS]
    count = Counter(keys)
    return dict(asg_n=math.log(len(siblings)),
                asg_empty=float(np.mean([not any(len(x) for x in s) for s in sib])) if sib else np.nan,
                asg_equal=float(np.mean([count[k] > 1 for k in keys])) if keys else np.nan)


# ------------------------------------------------------------------ compute

def load_task(export, frames, empty, task, labs):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for part, by in frames.items():
            df = by.get(task)
            (df if df is not None else empty[part]).to_parquet(tmp / f"{part}.parquet")
        (tmp / "values").mkdir()
        os.symlink((Path(export) / "values" / task).resolve(), tmp / "values" / task)
        (tmp / "orientations.json").write_text((Path(export) / "orientations.json").read_text())
        with open(tmp / "labels.jsonl", "w") as f:
            f.write("".join(json.dumps(lab) + "\n" for lab in labs))
        try:
            return E.load_rollouts(tmp, strict=False, allow_violations=True)
        except E.DataFault as f:
            if "more than half of the" not in str(f):
                raise
            # the guard holds over the whole export, which loads as one; one task's tables may be mostly unseen
            real, calls = E.unseen_counts, [0]
            def counts(tables):
                calls[0] += 1
                u, e = real(tables)
                return (u, e) if calls[0] % 2 else ({}, e)
            E.unseen_counts = counts
            try:
                return E.load_rollouts(tmp, strict=False, allow_violations=True)
            finally:
                E.unseen_counts = real


def task_frame(export, frames, empty, task, labs):
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        members, skipped = load_task(export, frames, empty, task, labs)
    pairs = json.load(open(ROOT / "data/tasks" / f"{task}.json"))["train"]
    n_train = len(pairs)
    cache, earlier_of = {}, {}
    def rows_of(t):
        if id(t) not in cache:
            cache[id(t)] = train_rows(t, n_train)
        return cache[id(t)]
    out = []
    # the detectors on the rows before the budgets
    det = {}
    for key, m in members.items():
        ts, recs = m["tables"], m["records"]
        flags0 = [r for r in recs]
        p0 = [i for i, r in enumerate(recs) if r["position"] == 0]
        if not p0:
            continue
        earlier = []
        for t, r in zip(ts, recs):
            if r["position"] < 0 and t.unseen is None:
                if id(t) not in earlier_of:
                    rr = rows_of(t)
                    earlier_of[id(t)] = None if rr is None or not any(len(x) for x in rr) else (
                        list(t.types), rr, t.evidence,
                        keyed_rows(rr) if max(len(x) for x in rr) <= SET_ROWS else None,
                        np.array([len(x) for x in rr], float))
                if earlier_of[id(t)] is not None:
                    earlier.append(earlier_of[id(t)])
        asg = assignments([rows_of(ts[i]) if ts[i].unseen is None else None for i in p0])
        for i in p0:
            det[(key, i)] = (ts[i], flags0[i], earlier, asg)
    # the budgets of the value run, then the flags and value_eval.features' inputs
    tabs = {k: m["tables"] for k, m in members.items()}
    E.mark_over_budget(tabs, BUDGET)
    E.mark_over_rows(tabs, MAX_ROWS)
    labels = {(l["task"], l["case"]): l for l in labs}
    records = E.value_records(tabs, labels)
    for key, m in members.items():
        for i, (t, r) in enumerate(zip(tabs[key], records[key])):
            if not 0 <= r["position"] < POSITIONS:
                continue
            row = dict(task=key[0], case=key[1], corpus_case=r["group"][1], prefix_tokens=r["group"][2],
                       member=str(r["member"]), gold=r["member"] == "gold", solving=bool(r["solving"]),
                       position=int(r["position"]), index=i, export_table=t.export_table,
                       empty=r["empty"], unseen=r["unseen"], faulted=r["faulted"],
                       n_rows=int((~t.marker).sum()), depth=float(t.depth or 0), step=int(t.step),
                       types=",".join(t.types))
            if (key, i) in det:
                t0, _, earlier, asg = det[(key, i)]
                row.update(detectors(t0, r, earlier, asg, pairs, n_train, rows_of))
            out.append(row)
    return pd.DataFrame(out), skipped


def compute_mode(export, parts_dir, seconds, only):
    start = time.time()
    parts_dir = Path(parts_dir)
    parts_dir.mkdir(parents=True, exist_ok=True)
    labs = [json.loads(l) for l in open(Path(export) / "labels.jsonl") if l.strip()]
    by_task = defaultdict(list)
    for lab in labs:
        by_task[lab["task"]].append(lab)
    tasks = sorted(only or by_task)
    todo = [t for t in tasks if not (parts_dir / f"{t}.parquet").exists()]
    print(f"{len(tasks)} tasks, {len(todo)} to compute", flush=True)
    if todo:
        frames = {}
        empty = {}
        for part in PARTS:
            df = pd.read_parquet(Path(export) / f"{part}.parquet")
            empty[part] = df.iloc[:0]
            frames[part] = {k: g for k, g in df.groupby("task", sort=False)}
        for k, task in enumerate(todo):
            if time.time() - start > seconds:
                print(f"stopped after {time.time() - start:.0f} s with {len(todo) - k} tasks to go", flush=True)
                return
            t0 = time.time()
            df, skipped = task_frame(export, frames, empty, task, by_task[task])
            df.to_parquet(parts_dir / f"{task}.parquet")
            print(f"{task}: {len(df)} Tables, {time.time() - t0:.1f} s" + (f"; left out {skipped}" if skipped else ""),
                  flush=True)
    done = [parts_dir / f"{t}.parquet" for t in tasks if (parts_dir / f"{t}.parquet").exists()]
    if len(done) == len(by_task):
        all_ = pd.concat([pd.read_parquet(p) for p in done], ignore_index=True)
        all_.to_parquet(ROOT / "lm/runs/data-study/detectors.parquet")
        print(f"wrote lm/runs/data-study/detectors.parquet: {len(all_)} Tables", flush=True)
    print(f"{time.time() - start:.0f} s", flush=True)


# ------------------------------------------------------------------ measure

class Stub:
    """The fields of a Table that value_eval.features reads."""
    def __init__(self, r):
        self.types = r["types"].split(",") if r["types"] else []
        self.marker = np.zeros(int(r["n_rows"]), bool)
        self.depth, self.step = r["depth"], int(r["step"])


def members_of(df, keep_all=False, stubs=False):
    """[{"group", "records", "solving", "tables"?, "rows"}] per member: each a list of its Tables in df's order."""
    out = []
    for case, g in df.groupby("case", sort=False):
        recs = [dict(position=int(r.position), member="gold" if r.gold else r.member, solving=bool(r.solving),
                     consistent=None, unjudged=True,
                     empty=False if keep_all else bool(r.empty), unseen=False if keep_all else bool(r.unseen),
                     faulted=False if keep_all else bool(r.faulted)) for r in g.itertuples()]
        m = dict(group=(g["task"].iat[0], g["corpus_case"].iat[0], int(g["prefix_tokens"].iat[0])), records=recs,
                 solving=bool(g["solving"].iat[0]), rows=g.index.to_numpy(), task=g["task"].iat[0])
        if stubs:
            m["tables"] = [Stub(r) for r in g.to_dict("records")]
        out.append(m)
    return out


def metrics(members, score):
    """encoder.value_draw_metrics at position 0 of the per-Table `score` (a Series on df's index)."""
    return E.value_draw_metrics(members, [[score.loc[m["rows"]].to_numpy(np.float32) for m in members]], 1,
                                label="solving")


def listed(df, members):
    """The df index of the Tables the lists read (position 0, not excluded under the members' flags)."""
    idx = []
    for m in members:
        idx += [i for i, r in zip(m["rows"], m["records"]) if r["position"] == 0 and not E.value_excluded(r)]
    return idx


def fit_logistic(x, y, steps=300, seed=0):
    """value_eval.logistic's training on a feature matrix: standardized, full-batch Adam, lr 0.05."""
    import torch, torch.nn as nn
    x, y = torch.tensor(x, dtype=torch.float32), torch.tensor(y, dtype=torch.float32)
    mu, sd = x.mean(0), x.std(0).clamp_min(1e-6)
    torch.manual_seed(seed)
    lin = nn.Linear(x.shape[1], 1)
    opt = torch.optim.Adam(lin.parameters(), lr=0.05)
    for _ in range(steps):
        loss = nn.functional.binary_cross_entropy_with_logits(lin((x - mu) / sd).squeeze(-1), y)
        opt.zero_grad(); loss.backward(); opt.step()
    def predict(z):
        with torch.no_grad():
            return lin((torch.tensor(z, dtype=torch.float32) - mu) / sd).squeeze(-1).numpy()
    w = lin.weight.detach().numpy().ravel()
    return predict, float(loss.item()), np.where(sd.numpy() > 1e-6, w, np.nan)


def show(x):
    return "   -" if x is None else f"{x:.3f}"


def row_line(name, r):
    return (f"{name:<28}{show(r['pair_acc']):>8}{show(r['auc']):>8}{show(r['pair_acc_sampled']):>9}"
            f"{show(r['auc_sampled']):>9}{r['pairs']:>7}{r['ranked_lists']:>7}{r['lists']:>7}")


HEAD = f"{'score':<28}{'pairs':>8}{'AUC':>8}{'pairs s':>9}{'AUC s':>9}{'n pair':>7}{'ranked':>7}{'lists':>7}"


def measure_mode(data, out):
    start = time.time()
    import contextlib, io
    import value_eval as VE
    df = pd.read_parquet(ROOT / "lm/runs/data-study/detectors.parquet")
    z = np.load(Path(data) / "cases.npz")
    held_tasks = {t for t, h in zip(z["task"].tolist(), z["heldout"].tolist()) if h}
    train_tasks = {t for t, h in zip(z["task"].tolist(), z["heldout"].tolist()) if not h}
    df = df[df["task"].isin(held_tasks | train_tasks)].copy()
    p0 = df["position"] == 0
    lines = ["# Detectors of the first table after the branch", "",
             f"Rollout export work/lm/rollouts-s2/export; split by {data}: {len(held_tasks & set(df['task']))} held-out "
             f"tasks, {len(train_tasks & set(df['task']))} training tasks.",
             "Columns: pairwise ranking accuracy and AUC within a list (encoder.value_draw_metrics), the same over "
             "sampled continuations alone (\"s\", none where no sampled continuation of a list solves), and the counts "
             "of pairs, ranked lists and lists.", ""]
    for col in DETECTORS:
        df[col] = df[col].astype(float)
    partial = int(df.loc[p0, "partial"].fillna(False).astype(bool).sum()) if "partial" in df else 0
    variants = {}
    for name, keep_all in (("graded", False), ("all", True)):
        ms = members_of(df[p0], keep_all)
        variants[name] = dict(train=[m for m in ms if m["task"] in train_tasks],
                              held=[m for m in ms if m["task"] in held_tasks], all=ms)
    lines.append("## Counts at position 0")
    sol = df[p0].drop_duplicates("case")
    lines.append(f"members with a Table at position 0: {len(sol)}; solving sampled continuations among them: "
                 f"{int((sol['solving'] & ~sol['gold']).sum())}, of held-out tasks "
                 f"{int((sol['solving'] & ~sol['gold'] & sol['task'].isin(held_tasks)).sum())}")
    lines.append(f"Tables whose rows come from a Count entry's projections, with no row detectors: {partial}")
    for name, v in variants.items():
        for part in ("held", "train"):
            ms = v[part]
            idx = listed(df, ms)
            r = metrics(ms, pd.Series(0.0, index=df.index))
            lines.append(f"{name}, {part}: {r['lists']} lists, {r['ranked_lists']} ranked, {r['pairs']} pairs, "
                         f"{len(idx)} Tables ({int(df.loc[idx, 'gold'].sum())} gold, {int((~df.loc[idx, 'gold']).sum())} sampled)")
    lines.append("")
    lines.append("### Tables each filter fires on, all Tables at position 0 (held-out and training)")
    lines.append(f"{'filter':<14}{'gold':>14}{'sampled':>16}")
    x = df[p0]
    for f in FILTERS:
        g, s = x[x["gold"]], x[~x["gold"]]
        lines.append(f"{f:<14}{int(g[f].sum()):>6} of {len(g):<6}{int(s[f].sum()):>7} of {len(s):<6}")
    lines.append("")

    def fill_median(col, train_idx):
        med = float(np.nanmedian(df.loc[train_idx, col])) if df.loc[train_idx, col].notna().any() else 0.0
        return df[col].fillna(med)

    sm = members_of(df, keep_all=False, stubs=True)
    TF = np.array([VE.features(Stub(r), r) for r in df.to_dict("records")], float)
    results = {}
    for name, v in variants.items():
        tr_idx = listed(df, v["train"])
        lines.append(f"## Held-out branch points, variant {name}")
        lines.append(HEAD)
        res = {}
        for f in FILTERS:
            res[f] = metrics(v["held"], -df[f])
            lines.append(row_line(f"-{f}", res[f]))
        res["filters"] = metrics(v["held"], -df[FILTERS].sum(axis=1))
        lines.append(row_line("-(sum of filters)", res["filters"]))
        for g in GRADED + ADDED:
            s = fill_median(g, tr_idx)
            tr = metrics(v["train"], s)["pair_acc"]
            sign = -1.0 if tr is not None and tr < 0.5 else 1.0
            res[g] = metrics(v["held"], sign * s)
            lines.append(row_line(("-" if sign < 0 else "+") + g + (" *" if g in ADDED else ""), res[g]))
        # value_eval.logistic on value_eval.features; in the variant "all", the same features and training on
        # every Table at position 0 (value_eval.logistic lists only the Tables value_excluded keeps)
        if name == "graded":
            for positions in (1, 4):
                trm = [m for m in sm if m["task"] in train_tasks]
                hm = [m for m in sm if m["task"] in held_tasks]
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    sc = VE.logistic(trm, hm, positions, 300, 0, "solving")
                r = E.value_draw_metrics(hm, [sc], positions, label="solving")
                res[f"trivial@{positions}"] = r
                lines.append(row_line(f"trivial features, positions {positions}", r) + "  " + buf.getvalue().strip())
        else:
            pred, loss, _ = fit_logistic(TF[tr_idx_pos(df, tr_idx)], df.loc[tr_idx, "solving"].to_numpy(float))
            res["trivial@1"] = metrics(v["held"], pd.Series(pred(TF), index=df.index))
            lines.append(row_line("trivial features, positions 1", res["trivial@1"]) +
                         f"  ({len(tr_idx)} training Tables, final training loss {loss:.3f})")
        # the logistic on every detector
        feats = FILTERS + GRADED + ADDED
        X = df[feats].to_numpy(float)
        mu = np.nanmean(X[tr_idx_pos(df, tr_idx)], 0)
        mu = np.where(np.isnan(mu), 0.0, mu)
        Xf = np.where(np.isnan(X), mu, X)
        pred, loss, w = fit_logistic(Xf[tr_idx_pos(df, tr_idx)], df.loc[tr_idx, "solving"].to_numpy(float))
        res["logistic"] = metrics(v["held"], pd.Series(pred(Xf), index=df.index))
        lines.append(row_line("logistic on every detector", res["logistic"]) +
                     f"  ({len(tr_idx)} training Tables, final training loss {loss:.3f})")
        lines.append("")
        lines.append("the 12 largest weights of the logistic on every detector, per standard deviation of the detector "
                     "on the training Tables (a detector constant there has none): " +
                     ", ".join(f"{f} {x:+.2f}" for f, x in sorted([(f, x) for f, x in zip(feats, w) if not np.isnan(x)],
                                                                  key=lambda p: -abs(p[1]))[:12]))
        lines.append("")
        # 5-fold cross-validation by task
        tasks = sorted(set(df["task"]))
        random.Random(0).shuffle(tasks)
        folds = [set(tasks[k::5]) for k in range(5)]
        lines.append(f"### 5-fold cross-validation by task over {len(tasks)} tasks, variant {name}")
        lines.append(f"{'fold':<28}{'pairs':>8}{'AUC':>8}{'pairs s':>9}{'AUC s':>9}{'n pair':>7}{'ranked':>7}{'lists':>7}"
                     f"{'trivial pairs':>15}{'trivial AUC':>13}")
        accs = defaultdict(list)
        for k, fold in enumerate(folds):
            trm = [m for m in v["all"] if m["task"] not in fold]
            tem = [m for m in v["all"] if m["task"] in fold]
            ti = listed(df, trm)
            mu = np.nanmean(X[tr_idx_pos(df, ti)], 0)
            mu = np.where(np.isnan(mu), 0.0, mu)
            Xk = np.where(np.isnan(X), mu, X)
            pred, _, _ = fit_logistic(Xk[tr_idx_pos(df, ti)], df.loc[ti, "solving"].to_numpy(float))
            r = metrics(tem, pd.Series(pred(Xk), index=df.index))
            if name == "graded":
                smk = [m for m in sm if m["task"] not in fold], [m for m in sm if m["task"] in fold]
                with contextlib.redirect_stdout(io.StringIO()):
                    sc = VE.logistic(smk[0], smk[1], 1, 300, 0, "solving")
                rt = E.value_draw_metrics(smk[1], [sc], 1, label="solving")
            else:
                pt, _, _ = fit_logistic(TF[tr_idx_pos(df, ti)], df.loc[ti, "solving"].to_numpy(float))
                rt = metrics(tem, pd.Series(pt(TF), index=df.index))
            for key, rr in (("pair_acc", r), ("auc", r), ("pair_acc_sampled", r), ("auc_sampled", r)):
                if rr[key] is not None:
                    accs[key].append(rr[key])
            for key in ("pair_acc", "auc"):
                if rt[key] is not None:
                    accs["trivial " + key].append(rt[key])
            lines.append(row_line(f"fold {k} ({len(fold)} tasks)", r) + f"{show(rt['pair_acc']):>15}{show(rt['auc']):>13}")
        mean = lambda k: show(float(np.mean(accs[k])) if accs[k] else None)
        lines.append(f"{'mean over folds':<28}{mean('pair_acc'):>8}{mean('auc'):>8}{mean('pair_acc_sampled'):>9}"
                     f"{mean('auc_sampled'):>9}{'':>21}{mean('trivial pair_acc'):>15}{mean('trivial auc'):>13}")
        lines.append("")
        results[name] = res
    lines.append("A signal marked * is one of the signals added from marks.md (detectors.py's docstring). A graded signal's sign (+ or -) "
                 "is the one that ranks better on the training branch points. f_product is tested on Tables of at "
                 f"most {PRODUCT_ROWS} rows at each train example and {PRODUCT_COLUMNS} columns other than Example.")
    lines += ["", "## Marks of marks.md with no detector", ""] + [f"- {x}" for x in NOT_COMPUTED]
    Path(out).write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"{time.time() - start:.0f} s", file=sys.stderr)


def tr_idx_pos(df, idx):
    return df.index.get_indexer(idx)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", choices=["compute", "measure"])
    ap.add_argument("path", help="compute: the rollout export; measure: the data export of the split")
    ap.add_argument("--parts", default=str(ROOT / "work/lm/data-study-detectors"))
    ap.add_argument("--seconds", type=float, default=600)
    ap.add_argument("--tasks", nargs="*")
    ap.add_argument("--out", default=str(ROOT / "lm/runs/data-study/detectors.out"))
    a = ap.parse_args()
    if a.mode == "compute":
        compute_mode(a.path, a.parts, a.seconds, a.tasks)
    else:
        measure_mode(a.path, a.out)


if __name__ == "__main__":
    main()
