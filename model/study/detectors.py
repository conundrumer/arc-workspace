"""Compute the marks of work/lm/data-study/marks.md as detectors of the first table after the branch, and measure how each ranks the
gold continuation's table against the sampled ones.

    work/lm/.venv/bin/python work/lm/data-study/detectors.py cache [<export>] [--export DIR] [--seconds S] [--workers N] [--tasks T ...]
    work/lm/.venv/bin/python work/lm/data-study/detectors.py compute [<export>] [--export DIR] [--parquet FILE]
        [--workers N] [--tasks T ...]
    work/lm/.venv/bin/python work/lm/data-study/detectors.py measure <data> [--export DIR] [--parquet FILE] [--out FILE]
        [--quick [--show DETECTOR ...]]

The rollout export (`--export`, or the positional argument of `cache` and `compute`) defaults to
work/lm/rollouts-s2/export and the parquet (`--parquet`) to work/lm/data-study/detectors.parquet; `measure` reads
`--parquet` with the marks of `--export` joined (`read_marked`) and names `--export` in its output.

`cache` loads the rollout export one task at a time through `encoder.load_rollouts` (strict=False,
allow_violations=True) on a copy of the task's rows that holds no flows.parquet, so the loader knows no table's
parents; the cache reads the task's rows of flows.parquet itself and keeps the sources of each column of each Table
at position 0 (`task_snapshot`). The copy holds the task's rows of bases.parquet (engine/arclog-py/tables_export.py),
and a case that it cuts takes the rows of tables.parquet and flows.parquet of its base's tables numbered below the
cut as its own (`encoder.with_base_rows`), so the snapshot is the one an export without bases gives. A Table's earlier tables are the tables of the same case with a smaller token (export table < prefix_tables, and the
grid tables ex_input and ex_output). The loader's guard against more than half of the relation tables unseen is
lifted for a task whose own tables are so, since it holds over the whole export. Of each task it keeps what the
detectors read (`task_snapshot`), one pickle per task under work/lm/detector-cache/<name>/ (`cache_path` gives
<name>), skips a task whose pickle has the task's stamp (`task_stamps`), stops starting tasks after --seconds, and,
once every task is written, joins them into work/lm/detector-cache/<name>.pkl with the join's stamp (`join_stamp`),
where that file is missing or its stamp differs. It keeps the per-task pickles. `compute` reads the per-task pickles of
a cache whose join holds the join's stamp of the export, refusing one whose stamp is not the task's, computes the detectors
in --workers processes and writes --parquet. A row of that parquet is one Table
(one DET assignment of an export table) at positions 0 to 3 after the branch: its member and label, its flags as
model/value_eval.py reads them (after the budgets of the value run: an entry over 10000 rows, a table over 4000 rows),
the inputs of value_eval.features, and, at position 0, the detector values below, computed on the Table's rows
before the budgets, and `rows_hash`, a hash of its column types and its rows at each train example (null where the
Table is unseen or its rows come from projections), by which two members' tables after the branch compare. The rows of a Table at a train example are its rows whose entry is that example, as a set; a
task-wide entry's row counts at the example that its first Example column gives, or at every train example where the
Table has no Example column. A Table whose rows come from a Count entry's projections is
marked `partial` and gets no row detectors.

Filters (0/1), each marking a degenerate Table:
- f_empty: seen, with 0 rows in every train example;
- f_unseen: faulted or unseen (value_eval's flags, after the budgets), or seen with an entry at a train example, or a
  task-wide entry, stopped at the work cap (`capped` in the cache);
- f_factors: seen, with rows, and every factor degenerate (`factor_values`). Under deferred projection a clause's
  relation holds every binding of its body; a factor is a part of the Table's columns (Example columns left out)
  that the where-provenance (flows.parquet, kept in the cache) derives from one source (`factorize`): the columns
  copied from one earlier table (`copy`), or one column that is constant, a duplicate of another, computed, or from
  a lib relation, a lib name or a constant. Two copy factors that share a column are joined; factors that share
  none are a product. A factor is degenerate (`factor_test`) where it is constant, a duplicate or from the lib; where
  its projection's rows equal its named source's projection by the flows' column map (fewer rows are a selection,
  which survives), or `restates` matches it to its named source or, for a copy factor, to another earlier Table;
  where it equals an earlier Table of its type multiset, or is the union, intersection or difference of two (at most
  FACTOR_SHAPES Tables and FACTOR_MAPPINGS column mappings each); where its rows are pairs of one type that an
  earlier Table derives (`pair_test`: the pairs of an earlier class membership, the order an earlier Number
  column induces, or the closure of an earlier pair relation) or a lib cell relation restricted to the cells of an
  earlier Table (`lib_pair_test`); or where the Table as a whole is f_redundant. A copy factor whose rows are not within its
  source's projection (a relation of several branches) is `partial`: left out where other factors hold its columns,
  surviving otherwise. A Table of Example columns alone has no factor and is degenerate. The earlier Tables these
  tests compare against leave out ex_output: a Table equal to the train output is the solution, not a restatement
  (f_output marks it). Where every factor is degenerate on its own and two or more are copy, computed or unsourced
  factors, the Table still adds signal unless its rows are the Cartesian product of those factors' projections at
  every train example (a constant, duplicate or lib column is determined by the others): otherwise the test `joint`
  is added to factor_tests and the whole of those factors' columns survives as one factor.
- f_independent: the member's first table keeps its rows at every train example when the task's inputs and outputs,
  train and test, are replaced by blank grids (every cell 0, at each grid's size): the member's `f_independent` in
  the marks file work/lm/detector-cache/<name>.independent.parquet (`marks_path`, written by `independent.py mark`
  or by the independence stage of allpoints.py). `compute` does not write it: a measurement reads the parquet
  through `read_marked`, which joins the marks file (`join_marks`) to the Tables at position 0. A member that the
  marks file gives as untested gets 0, with `independent_untested` 1; a member that it does not give gets neither
  value (missing), which fires no filter.

Columns of the parquet in no score (PLAIN, FACTOR_COLUMNS and the aggregates):
- f_output: the Table is f_redundant against the earlier Tables, and not against them less ex_output: it equals
  the train output up to isomorphism.
- f_redundant: the Table equals an earlier Table up to isomorphism: at every train example its rows equal those of
  an earlier Table, or their projection onto columns of the same types (viability.py's `restates`, which ignores
  the order of the columns within a type), the Table's columns mapped to distinct columns except two columns equal
  in every row, which may map to one column; as given or with both Tables in canonical form. The canonical
  form of a Table's rows:
  - a one-cell Box is the margins (r, h-1-r, c, w-1-c) of the cell at row r and column c of the example's h x w
    grid, the form of the input evidence table's cell column (a Position, which the engine types as a Box); every
    Box of the export is already written so, so a grid copy's rows and the input evidence table's compare equal as
    given;
  - where the rows at every example are closed under the swap of two columns of one type (Example columns left out)
    and some row differs between the two, the two columns' values are sorted within each row and the duplicate rows
    dropped, so the relation is on unordered pairs; columns joined by such swaps are sorted together. A folded Table
    that matches no earlier Table is not redundant;
- f_product: at every train example its rows equal the product of their projections onto the two sides of a split of
  its columns (Example columns left out), with both sides of 2 or more values at some example; tested where no
  example has over PRODUCT_ROWS rows and the Table has at most PRODUCT_COLUMNS such columns.
  f_redundant and one_row_diff are tested where no example has over SET_ROWS (20000) rows, and an earlier Table
  over that bound is not compared.
- lineage_independent: `lineage_independent` of the Table's `roots`: no column reaches by its flows a grid's colors
  or a source column with no flows. It misses a selection by color, so it is no degeneracy test;
- f_restate: f_redundant with both Tables as given;
- f_symmetric: the Table's rows have a swap of the canonical form;
- f_grid: at every train example one row per input cell, with a Box column and a Color column whose pairs are the
  input's cells and colors;
- the factor structure: n_factors, n_surviving, n_joins (pairs of copy factors sharing a column), n_shared (the
  columns so shared), n_self_join (columns copied from two columns of one source), factor_width (the surviving
  factors' columns), factor_untested (a bound cut a factor test), factor_kinds and factor_tests (per factor, in
  `factorize`'s order: its kind, and the test that decides it, `survives`, `selection` or `partial` where none
  makes it degenerate), factor_classes (classify.py's classes of each surviving factor, keys derived from the
  rows) and table_classes (of the Table, so);
- `<detector>@max`, `@min` and `@big` for each graded and added signal: its value on each surviving factor's
  projection, aggregated as the max, the min and the value on the factor of the most columns (then rows); the
  Table's own value where no factor survives. `measure`, `headline` and detectors_mut.py take the aggregate
  AGGREGATE as the signal, and the surviving factors' total width as the column count (None: the Table's own
  values and its count of column types).

Graded signals (a number each), over the train examples (e):
- log_rows: log(1 + rows summed over e);
- rows_per_cell: mean of rows_e / input cells_e;
- rows_vs_parent: min of rows_e / rows_e of the earlier relation Table with the most rows (none: missing);
- rows_cv: coefficient of variation of rows_e;
- const_share: share of the columns (Example columns left out) of one value at every e with rows;
- fd_pairs: ordered column pairs (a, b) where a's value gives b's at every e with rows, and at some e a is not a key
  and b has 2 or more values; one_to_one: whether some pair of distinct columns gives each other so, with 2 or more
  values at some e;
- fill: mean over e with rows of rows_e / the product of the columns' distinct counts; lack: the mean over the same e (those
  with rows) of that product less rows_e where fill_e is above 0.8 and below 1, else 0;
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
  sizes differ); out_color: of the rows that name such a cell in some Box column, the share in which some Color
  column holds the output's color at a cell that some Box column names.

Signals added from work/lm/data-study/marks.md:
- off_grid: share of rows with some Box column that is one cell in the input grid's terms and lies off the grid
  (b5bb5719 &r16);
- one_row_diff: an earlier Table of the same column types differs from it by one row over all e (9565186b &r7);
- asg_n, asg_empty, asg_equal: the DET assignments of the Table's export table: log of their count, the share empty
  in every e, the share of those with rows whose rows at every e equal another assignment's (22425bda &r24, 8e5a5113 &r6);
- splits_like_outputs: the examples grouped by equal rows (Example columns left out) are grouped as the outputs are
  by equal grids, where the outputs fall in 2 or more groups and two outputs are equal (44f52bb0 &r0);
- number_out_size: a Number column whose greatest value at every e is the output's height, or its width, where that
  size varies over e (22425bda &r20);
- cell_count_cv: mean over e of the coefficient of variation of the rows per value of the first Box column
  (2c608aff &r14; a product has the same count at every cell);
- untested: 1 where a bound skipped f_product, f_redundant or one_row_diff, or skipped an earlier Table that
  f_redundant did not match, so a 0 of those filters is not a clean pass.

Signals that read the Table against the train outputs (RELEVANCE). A row's cell is the value of a Box column that
is one cell of the output grid; the row's other columns, Example columns left out, are its key. Each is 0 where no
Box column names an output cell:
- out_fd (relevance): for some Box column, at every e with such rows, the key gives one output color at the row's
  cell, and at some e a key has two or more rows;
- changed_share (relevance): mean over e of the share of the cells the Table names that differ between input and
  output (every cell where the sizes differ); out_cover is the other share, of the differing cells that it names;
- out_consistent (relevance): for some Box column, the key gives one output color at the row's cell over the rows
  of every e pooled, and some key is at two or more e: the same map from the Table's values to output colors at
  every example.

Signals of a regularity across the train examples, from the rows alone (INFORMATIVE); none where fewer than two
train examples are or no e has rows:
- cross_example_shape (informativeness): 1 where rows_e is the same at every e, and not 0; 0.5 where else some
  column gives each of its distinct values one count of rows, the same at every e; else 0;
- value_reuse (informativeness): share of the (column, value) pairs of the rows (Example columns left out) at some e
  that are at every e;
- new_values (informativeness): mean over e with rows of the share of the (type, value) pairs of the rows at e
  (Example columns left out) that no earlier Table holds at e, ex_output left out; 0 is a Table that only
  recombines earlier values.
- obj_whole4, obj_whole8 (informativeness): the objects of a train input are its connected components of one color
  (4- or 8-connected), the background included, so each cell lies in one object. A cell column is a Box column
  whose every value is one cell of the example's input grid; its cell sets at an example are the cells of each
  group of rows that agree on the other columns (one set where there is no other column). The value is the
  mean over e with rows of the share of the cell sets that are one object or a union of whole objects, the
  greatest over the cell columns; none where the Table has no cell column;
- obj_cover4, obj_cover8 (informativeness): mean over the same e of the share of the cells the cell columns name
  that lie in objects whose every cell they name.
- mdl_gain, mdl_share (informativeness): the minimum description length gain of the rows given the earlier
  Tables, ex_output left out: bits per row, and the share of the raw bits; `description_gain` states the code.

Signals of a Table against the other candidates of its branch point (SIBLING), from the candidates' first tables
alone, as at decode time; a member's siblings are the other members of its list that have a Table at position 0
(in the all-boundaries sets: the gold and the mutants, or the gold and the foreign clauses). Both are invariant to
which member is the gold: a member's value reads the multiset of its siblings' tables, and the gold is one sibling
of each negative as each negative is of the gold. They are not aggregated over factors:
- sib_same (relevance to the search): share of the siblings with a Table at position 0 whose `rows_hash` equals the
  Table's;
- sib_unique (relevance to the search): share of the Table's rows, each with its train example, that no sibling's
  Table at position 0 of the same column types holds at that example.

`measure` reads detectors.parquet and splits the branch points as model/value_eval.py does, by the held-out tasks of
<data> (its cases.npz). The lists are those of encoder.value_lists at position 0 (positions=1) with the label
`solving`, in two variants: "graded", the Tables value_excluded leaves out left out, as value_eval does; and "all",
every Table at position 0 kept. Each score is measured with encoder.value_draw_metrics. A filter alone scores
-filter; the filters summed score minus their sum; a graded signal alone takes the sign that ranks better on the
training branch points, a missing value taking the training median. The logistic regression on every detector is
trained as value_eval.logistic is (full-batch Adam, 300 steps, lr 0.05, standardized, seed 0), a missing value
taking the training mean; it is measured on the held-out branch points and in 5-fold cross-validation by task over
every task. value_eval.logistic on value_eval.features is measured at positions 1 and 4 in the variant "graded"; in
the variant "all", the same features are fit as the detectors are, over every Table at position 0. Beside them:
the logistic on every detector over its pairs whose position-0 Tables have one column count (held out, and pooled
over the folds), the logistic on the column count alone, and the logistic on every detector less COLUMN_STRUCTURE.
--out (default
work/lm/data-study/detectors.out) gets the tables. With --quick, `measure` prints only the rows of HEADLINE
(`headline`), with the same numbers, and those of the detectors of --show, and writes no file.
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[0]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse, itertools, json, math, os, random, sys, tempfile, time
from types import SimpleNamespace
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = MAIN_ROOT
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pinned   # noqa: E402
pinned.use()   # the pinned model/ modules (pinned.py)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import encoder as E   # noqa: E402
import viability as V   # noqa: E402

PARTS = ("tables", "index", "assigned", "projections", "projection_rows")   # no flows
BUDGET, MAX_ROWS = 10000, 4000   # the value run's --enc-budget and --enc-max-rows
POSITIONS = 4                    # positions written, for the trivial baseline at the value run's --value-positions
PRODUCT_ROWS, PRODUCT_COLUMNS = 3000, 8
SET_ROWS = 20000                 # the most rows at an example for the tests that build row sets
FILTERS = ["f_empty", "f_unseen", "f_factors", "f_independent"]
PLAIN = ["f_redundant", "f_product", "f_restate", "f_symmetric", "f_grid", "f_output"]   # computed and written, in no score
GRADED = ["log_rows", "rows_per_cell", "rows_vs_parent", "rows_cv", "const_share", "fd_pairs", "one_to_one", "fill",
          "lack", "same_rows", "same_all", "jaccard", "n_zero", "zero_identity", "eq_in_cells", "eq_out_cells",
          "eq_out_h", "eq_out_w", "eq_earlier", "out_cover", "out_color"]
ADDED = ["off_grid", "one_row_diff", "asg_n", "asg_empty", "asg_equal", "splits_like_outputs", "number_out_size",
         "cell_count_cv", "untested"]
RELEVANCE = ["out_fd", "changed_share", "out_consistent"]
INFORMATIVE = ["cross_example_shape", "value_reuse", "new_values", "obj_whole4", "obj_cover4", "obj_whole8",
               "obj_cover8", "mdl_gain", "mdl_share"]
ADDED += RELEVANCE + INFORMATIVE
SIBLING = ["sib_same", "sib_unique"]   # per member, against its branch point's other members; no factor aggregate
FEATURE_ROWS = RELEVANCE + INFORMATIVE + SIBLING   # the detectors whose own rows loop.py prints in the variant viable
DETECTORS = FILTERS + GRADED + ADDED + SIBLING
SCORED = FILTERS + GRADED + ADDED   # the detectors the fits read; SIBLING is left out: in the all-boundaries sets it reads the empty and equal negatives of a list


COLUMN_STRUCTURE = ["fd_pairs", "one_to_one", "const_share", "fill", "lack", "jaccard"]
NOT_COMPUTED = [
    "A rank or order equal to its score: it needs the score's table, which only the flows give; f_redundant covers the "
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


_KEY_LIMIT = 2 ** 62


def row_keys(a):
    """One int64 key per row of the 2-D integer array a, in the order of the rows' lexicographic order (each column
    shifted to start at 0 and weighted by the product of the later columns' value ranges), so that equal rows and
    only they have equal keys; None where a has no row or no column, is not an integer array, has a value outside
    the int32 range, or the product of its columns' value ranges passes _KEY_LIMIT."""
    if a.ndim != 2 or not len(a) or not a.shape[1] or a.dtype.kind not in "biu":
        return None
    if a.shape[1] == 1:
        if a.dtype.itemsize > 4 and (a.dtype.kind == "u" or a.min() < -2 ** 31 or a.max() >= 2 ** 31):
            return None
        return a[:, 0]
    lo, hi = a.min(0), a.max(0)
    if a.dtype.itemsize > 4 and (a.dtype.kind == "u" or lo.min() < -2 ** 31 or hi.max() >= 2 ** 31):
        return None
    lo = lo.astype(np.int64)
    span = (hi.astype(np.int64) - lo + 1).tolist()
    total = 1
    for x in span:
        total *= x
    if total > _KEY_LIMIT:
        return None
    key = a[:, 0] - lo[0]
    for j in range(1, a.shape[1]):
        key = key * span[j] + (a[:, j] - lo[j])
    return key


def unique_axis0(a, return_inverse=False, return_counts=False):
    """np.unique(a, axis=0, ...) of a 2-D integer array: the distinct rows in lexicographic order, with the inverse
    (1-D) and the counts where asked; by a sort of `row_keys` where it gives keys, which order the rows as
    np.unique does."""
    k = row_keys(a)
    if k is None:
        got = np.unique(a, axis=0, return_inverse=return_inverse, return_counts=return_counts)
        if return_inverse:
            got = list(got)
            got[1] = got[1].reshape(-1)
            got = tuple(got)
        return got
    order = np.argsort(k, kind="stable")
    ks = k[order]
    first = np.empty(len(ks), bool)
    first[0] = True
    np.not_equal(ks[1:], ks[:-1], out=first[1:])
    out = [a[order[first]]]
    if return_inverse:
        inv = np.empty(len(ks), np.intp)
        inv[order] = np.cumsum(first) - 1
        out.append(inv)
    if return_counts:
        out.append(np.diff(np.append(np.flatnonzero(first), len(ks))))
    return tuple(out) if len(out) > 1 else out[0]


def n_distinct_rows(a):
    """len(np.unique(a, axis=0)) of a 2-D integer array."""
    k = row_keys(a)
    if k is None:
        return len(np.unique(a, axis=0))
    if len(k) < 2:
        return len(k)
    ks = np.sort(k)
    return int(np.count_nonzero(ks[1:] != ks[:-1])) + 1


def unique_rows(a):
    if a.shape[1] == 0:
        return a[:1]
    return unique_axis0(a) if len(a) else a


def table_content(t):
    """A digest of what `train_rows` reads of Table t: its types, evidence flag and cell, marker, presence and
    example arrays."""
    import hashlib
    h = hashlib.sha1(repr((list(t.types), bool(t.evidence))).encode())
    for a in (t.cells, t.marker, t.present, t.example_kind, t.example):
        a = np.asarray(a)
        h.update(b"|%s|%s|" % (str(a.dtype).encode(), repr(a.shape).encode()))
        h.update(np.ascontiguousarray(a).tobytes())
    return h.digest()


def train_rows(t, n_train):
    """[unique rows [n, w]] per train example, or None where the Table's rows come from projections. A task-wide
    entry's row counts at the example its first Example column gives, where the Table has an Example column, and
    at every example where it has none."""
    if t.evidence:
        keep = t.cells[:, 0] < n_train
        c = t.cells[keep]
        return [unique_rows(c[c[:, 0] == e]) for e in range(n_train)]
    live = ~t.marker
    if live.any() and not t.present[live].all():
        return None
    out = []
    wide = live & (t.example_kind == 0)
    ex = [a for (a, _), ty in zip(spans(t.types), t.types) if ty == "Example"]
    for e in range(n_train):
        w = wide & (t.cells[:, ex[0]] == e) if ex and wide.any() else wide
        sel = live & (((t.example_kind == 1) & (t.example == e)) | w)
        out.append(unique_rows(t.cells[sel]))
    return out


_COLSETS = {}   # id of a keyed_rows dict -> (the dict, its column value sets); emptied per task


def colsets(types, k):
    """[{example: frozenset of the column's values}] per column of keyed rows k, kept in _COLSETS."""
    got = _COLSETS.get(id(k))
    if got is None or got[0] is not k:
        sp = V.spans(types)
        got = (k, [{ex: frozenset(r[a:b] for r in rs) for ex, rs in k.items()} for a, b in sp])
        _COLSETS[id(k)] = got
    return got[1]


def equal_columns(types, k):
    """The pairs (i, j), i < j, of columns of keyed rows k whose values are equal in every row, kept in _COLSETS."""
    key = ("eq", id(k))
    got = _COLSETS.get(key)
    if got is None or got[0] is not k:
        sp = V.spans(types)
        got = (k, {(i, j) for i, j in itertools.combinations(range(len(types)), 2) if types[i] == types[j] and all(
            r[sp[i][0]:sp[i][1]] == r[sp[j][0]:sp[j][1]] for rs in k.values() for r in rs)})
        _COLSETS[key] = got
    return got[1]


def restates(x_types, x_rows, y_types, y_rows):
    """viability.restates, with each Table's column value sets built once, and with two columns of x mapped to one
    column of y where those two columns are equal in every row of x."""
    if set(x_rows) != set(y_rows):
        return False
    xc, yc = colsets(x_types, x_rows), colsets(y_types, y_rows)
    cands = []
    for i, ti in enumerate(x_types):
        c = [j for j, tj in enumerate(y_types) if ti == tj and xc[i] == yc[j]]
        if not c:
            return False
        cands.append(c)
    ys = V.spans(y_types)
    for k, m in enumerate(itertools.product(*cands)):
        if k >= V.MAX_MAPPINGS:
            return False
        if len(set(m)) < len(m) and any(m[i] == m[j] and (i, j) not in equal_columns(x_types, x_rows)
                                        for i, j in itertools.combinations(range(len(m)), 2)):
            continue
        if all(x_rows[ex] == {tuple(v for j in m for v in r[ys[j][0]:ys[j][1]]) for r in y_rows[ex]} for ex in x_rows):
            return True
    return False


_CANON = {}   # id of a keyed_rows dict -> (the dict, its canonical form); emptied per task


def canonical(types, rows, k):
    """The canonical form of keyed rows k (`keyed_rows(rows)`, rows one array per train example): for each set of
    columns of one type (Example columns left out) joined by swaps under which the rows at every example are closed,
    with some row differing between the two columns, those columns' values sorted within each row, as a keyed_rows
    dict; k itself where no such swap is. Kept in _CANON."""
    got = _CANON.get(id(k))
    if got is not None and got[0] is k:
        return got[1]
    sp = spans(types)
    cols = [j for j, ty in enumerate(types) if ty != "Example"]
    ex_nz = [e for e, r in enumerate(rows) if len(r)]
    parent = {j: j for j in cols}
    def root(j):
        while parent[j] != j:
            j = parent[j]
        return j
    cs = colsets(types, k) if ex_nz else None
    for a, b in itertools.combinations(cols, 2):
        if types[a] != types[b] or not ex_nz or root(a) == root(b) or any(cs[a][e] != cs[b][e] for e in ex_nz):
            continue
        perm = list(range(rows[ex_nz[0]].shape[1]))
        (sa, ea), (sb, eb) = sp[a], sp[b]
        perm[sa:ea], perm[sb:eb] = perm[sb:eb], perm[sa:ea]
        differ = any((rows[e][:, sa:ea] != rows[e][:, sb:eb]).any() for e in ex_nz)
        if differ and all(frozenset(map(tuple, rows[e][:, perm].tolist())) == k[e] for e in ex_nz):
            parent[root(b)] = root(a)
    groups = defaultdict(list)
    for j in cols:
        groups[root(j)].append(j)
    groups = [g for g in groups.values() if len(g) > 1]
    out = k
    if groups:
        out = {}
        for e, r in enumerate(rows):
            r = r.copy()
            for g in groups:
                w = sp[g[0]][1] - sp[g[0]][0]
                block = np.stack([r[:, sp[j][0]:sp[j][1]] for j in g], 1)   # [n, len(g), w]
                order = np.lexsort(block.transpose(2, 0, 1)[::-1], axis=-1) if w > 1 else np.argsort(block[..., 0], 1)
                block = np.take_along_axis(block, order[..., None], 1)
                for i, j in enumerate(g):
                    r[:, sp[j][0]:sp[j][1]] = block[:, i]
            out[e] = frozenset(map(tuple, r.tolist()))
    _CANON[id(k)] = (k, out)
    return out


def canonical_earlier(earlier):
    """[(types, canonical form, keyed rows)] of the earlier Tables [(types, rows, is_grid, keyed rows or None, rows
    per example)] that have keyed rows, kept in _CANON by the list's id."""
    got = _CANON.get(id(earlier))
    if got is None or got[0] is not earlier:
        got = (earlier, [(ty, canonical(ty, r, k), k) for ty, r, _, k, _ in earlier if k is not None])
        _CANON[id(earlier)] = got
    return got[1]


def keyed_rows(rows):
    """{example: frozenset of row tuples} for viability.restates."""
    return {e: frozenset(map(tuple, r.tolist())) for e, r in enumerate(rows)}


def col_ids(r, sp):
    """The id of each row's value in each column ([n] per column) and each column's distinct count."""
    ids, d = [], []
    for s, e in sp:
        if len(r):
            _, inv = unique_axis0(r[:, s:e], return_inverse=True)
            ids.append(inv); d.append(int(inv.max()) + 1)
        else:
            ids.append(np.zeros(0, np.int64)); d.append(0)
    return ids, d


def n_unique(ids_list):
    """The count of distinct tuples of the id arrays ids_list (`col_ids`' ids: from 0, dense), by one packed key."""
    if not ids_list or len(ids_list[0]) == 0:
        return 0
    key, total = ids_list[0].astype(np.int64), int(ids_list[0].max()) + 1
    for x in ids_list[1:]:
        m = int(x.max()) + 1
        total *= m
        if total > _KEY_LIMIT:
            return n_distinct_rows(np.stack(ids_list, 1))
        key = key * m + x
    if len(key) < 2:
        return len(key)
    key.sort()
    return int(np.count_nonzero(key[1:] != key[:-1])) + 1


def grid_of(g):
    return np.array(g, np.int32)


def cell_boxes(h, w):
    r, c = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
    return np.stack([r, h - 1 - r, c, w - 1 - c], -1).reshape(-1, 4)


# ------------------------------------------------------------------ detectors

def detectors(t, flags, earlier, asg, pairs, n_train, rows_of, filters=True):
    """The detector values of Table t (DETECTORS), given its flags, the earlier Tables [(types, rows, is_grid, keyed
    rows or None, rows per example)], the values of `assignments` for its export table, and the task's train pairs.
    With `filters` False, the tests of f_redundant, f_restate and f_symmetric are left out (for a factor's
    projection)."""
    v = {k: np.nan for k in DETECTORS}
    for k in FILTERS + PLAIN:
        v[k] = 0.0
    v["f_unseen"] = float(flags["unseen"] or flags["faulted"] or bool(getattr(t, "capped", False)))
    v["untested"] = 0.0
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
        if len(cols) > PRODUCT_COLUMNS or n.max() > PRODUCT_ROWS:
            v["untested"] = 1.0
        elif len(cols) >= 2:
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
    if big_set:
        v["untested"] = 1.0
    else:
        noex = [frozenset(map(tuple, (np.concatenate([r[:, sp[j][0]:sp[j][1]] for j in cols], 1) if cols
                                     else r[:, :0]).tolist())) if len(r) else frozenset() for r in rows]
        same = [nz[e] and any(noex[e] == noex[f] for f in range(n_train) if f != e) for e in range(n_train)]
        v["same_rows"] = float(np.mean(same))
        v["same_all"] = float(nz.all() and len(set(noex)) == 1)
        groups = lambda keys: sorted(sorted(i for i, k in enumerate(keys) if k == x) for x in set(keys))
        out_keys = [(g.shape, g.tobytes()) for g in outs]
        v["splits_like_outputs"] = float(2 <= len(set(out_keys)) < n_train and groups(noex) == groups(out_keys))
        kx = keyed_rows(rows)
    if not big_set and filters:
        # symmetric under a swap of two same-typed columns
        fx = canonical(types, rows, kx)
        v["f_symmetric"] = float(fx is not kx)
        # equal to an earlier Table, or a projection of one, as given and in canonical form
        v["f_restate"] = float(any(restates(types, kx, ty, k) for ty, _, _, k, _ in earlier if k is not None))
        if not v["f_restate"]:
            v["f_redundant"] = float(any(restates(types, fx, ty, fy) for ty, fy, k in canonical_earlier(earlier)
                                         if fx is not kx or fy is not k))
        else:
            v["f_redundant"] = 1.0
        if not v["f_redundant"] and any(k is None for _, _, _, k, _ in earlier):
            v["untested"] = 1.0
    if not big_set:
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
        row_hit, row_match, row_off = (np.zeros(len(r), bool) for _ in range(3))
        for b in boxes:
            x = r[:, sp[b][0]:sp[b][1]]
            if len(x) == 0:
                continue
            cell = (x >= 0).all(1) & (x[:, 0] + x[:, 1] == ho - 1) & (x[:, 2] + x[:, 3] == wo - 1)
            rr, cc = np.where(cell, x[:, 0], 0), np.where(cell, x[:, 2], 0)
            named[rr[cell], cc[cell]] = True
            hit = cell & diff[rr, cc]
            row_hit |= hit
            for c in colors:
                row_match |= hit & (r[:, sp[c][0]] == o[rr, cc])
            one = (h - x[:, 0] - x[:, 1] == 1) & (w - x[:, 2] - x[:, 3] == 1)
            row_off |= one & (x < 0).any(1)
        hits += int(row_hit.sum()); matches += int(row_match.sum()); off += int(row_off.sum())
        nrows += len(r)
        if diff.any() and boxes:
            covers.append(float((named & diff).sum() / diff.sum()))
    v["f_grid"] = float(grid_hit)
    v.update(relevance(types, sp, rows, ins, outs, boxes, n_train))
    v.update(regularity(types, sp, rows, n_train))
    for conn in (4, 8):
        v[f"obj_whole{conn}"], v[f"obj_cover{conn}"] = object_alignment(types, sp, rows, ins, conn)
    if not filters:   # the Table's own value is snapshot_frame's, against the earlier Tables less ex_output
        v["new_values"] = new_values(types, sp, rows, earlier, n_train)
        v["mdl_gain"], v["mdl_share"] = description_gain(types, sp, rows, earlier, n_train)
    if boxes:
        v["out_cover"] = float(np.mean(covers)) if covers else 0.0
        v["out_color"] = matches / hits if hits and colors else 0.0
        v["off_grid"] = off / max(nrows, 1)
        cvs = []
        for e in ex_nz:
            _, cnt = unique_axis0(rows[e][:, sp[boxes[0]][0]:sp[boxes[0]][1]], return_counts=True)
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


def regularity(types, sp, rows, n_train):
    """cross_example_shape and value_reuse (INFORMATIVE) of rows (one array per train example)."""
    cols = [j for j, ty in enumerate(types) if ty != "Example"]
    n = [len(r) for r in rows]
    if n_train < 2 or not cols or not any(n):
        return dict(cross_example_shape=np.nan, value_reuse=np.nan)
    if all(n) and len(set(n)) == 1:
        shape = 1.0
    else:
        shape = 0.0
        for j in cols if all(n) else []:
            sizes = set()
            for r in rows:
                _, cnt = unique_axis0(r[:, sp[j][0]:sp[j][1]], return_counts=True)
                sizes |= set(cnt.tolist())
            if len(sizes) == 1:
                shape = 0.5
                break
    vals = [{(j, tuple(x)) for j in cols for x in unique_axis0(r[:, sp[j][0]:sp[j][1]]).tolist()} if len(r) else set()
            for r in rows]
    union = set().union(*vals)
    every = set.intersection(*vals) if all(vals) else set()
    return dict(cross_example_shape=shape, value_reuse=len(every) / len(union))


_OBJECTS = {}   # (grid bytes, shape, connectivity) -> (label per cell, size per label); emptied per task

_N4 = ((0, 1), (1, 0))
_N8 = ((0, 1), (1, 0), (1, 1), (1, -1))


def objects(g, conn):
    """The objects of grid g: its connected components of one color, 4- or 8-connected (conn), every color
    included (the background too, so every cell lies in one object). Gives the label of each cell, flat by
    r * w + c, and the size of each label."""
    key = (g.tobytes(), g.shape, conn)
    got = _OBJECTS.get(key)
    if got is not None:
        return got
    h, w = g.shape
    parent = list(range(h * w))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for r in range(h):
        for c in range(w):
            for dr, dc in (_N4 if conn == 4 else _N8):
                r2, c2 = r + dr, c + dc
                if 0 <= r2 < h and 0 <= c2 < w and g[r, c] == g[r2, c2]:
                    a, b = find(r * w + c), find(r2 * w + c2)
                    if a != b:
                        parent[a] = b
    roots = np.array([find(x) for x in range(h * w)])
    _, lab = np.unique(roots, return_inverse=True)
    lab = lab.reshape(-1)
    got = (lab, np.bincount(lab))
    _OBJECTS[key] = got
    return got


def _cell_columns(types, sp, rows, ins):
    """The Box columns whose every value at every train example is one cell of that example's input grid, with
    rows at some example."""
    out = []
    for j, ty in enumerate(types):
        if ty != "Box":
            continue
        a, b = sp[j]
        ok, some = True, False
        for e, r in enumerate(rows):
            if not len(r):
                continue
            h, w = ins[e].shape
            x = r[:, a:b]
            if not ((x >= 0).all() and (x[:, 0] + x[:, 1] == h - 1).all() and (x[:, 2] + x[:, 3] == w - 1).all()):
                ok = False
                break
            some = True
        if ok and some:
            out.append(j)
    return out


def object_alignment(types, sp, rows, ins, conn):
    """obj_whole and obj_cover (informativeness) of the Table at connectivity conn, from the train inputs only;
    None where the Table has no cell column or no example has rows. A cell column is a Box column whose every value
    is one cell of the example's input grid. Its cell sets at an example are the cells of each group of rows that
    agree on the other columns (Example columns left out); one set where there is no other column. obj_whole: the
    mean over the examples with rows of the share of those cell sets that are one object or a union of whole
    objects, the greatest over the cell columns. obj_cover: the mean over the same examples of the share of the
    cells the cell columns name that lie in objects whose every cell they name."""
    cells = _cell_columns(types, sp, rows, ins)
    if not cells:
        return np.nan, np.nan
    whole_by_col = {j: [] for j in cells}
    covers = []
    for e, r in enumerate(rows):
        if not len(r):
            continue
        h, w = ins[e].shape
        lab, size = objects(ins[e], conn)
        named = set()
        for j in cells:
            a, b = sp[j]
            flat = r[:, a] * w + r[:, a + 2]
            named.update(flat.tolist())
            others = [k for k, ty in enumerate(types) if ty != "Example" and k != j]
            if others:
                key = np.concatenate([r[:, sp[k][0]:sp[k][1]] for k in others], 1)
                _, gid = unique_axis0(key, return_inverse=True)
            else:
                gid = np.zeros(len(r), np.int64)
            ok = 0
            groups = defaultdict(set)
            for g_, f_ in zip(gid.tolist(), flat.tolist()):
                groups[g_].add(f_)
            for s in groups.values():
                ls = lab[list(s)]
                u = np.unique(ls)
                ok += int(size[u].sum() == len(s))
            whole_by_col[j].append(ok / len(groups))
        nm = np.fromiter(named, np.int64)
        ls = lab[nm]
        u, cnt = np.unique(ls, return_counts=True)
        full = cnt == size[u]
        covers.append(float(cnt[full].sum() / len(nm)))
    return max(float(np.mean(v)) for v in whole_by_col.values()), float(np.mean(covers))


C0 = math.log2(2.865064)   # Rissanen's constant of the universal code for the positive integers


def log_star(n):
    """Bits of Rissanen's universal code for the integer n >= 1: log2(c0) + log2 n + log2 log2 n + ..., the
    positive terms."""
    bits, x = C0, float(n)
    while True:
        x = math.log2(x)
        if x <= 0:
            return bits
        bits += x


def bits_count(n):
    """Bits of the count n >= 0, by the universal code of n + 1."""
    return log_star(n + 1)


def log2_choose(log2_u, n):
    """log2 of (U choose n), U = 2 ** log2_u, the bits of a uniform code over the sets of n distinct items of U."""
    if n == 0:
        return 0.0
    if log2_u > 50:
        return n * log2_u - math.lgamma(n + 1) / math.log(2)
    u = 2.0 ** log2_u
    if n > u + 1e-6:
        return float("inf")
    return float((math.lgamma(u + 1) - math.lgamma(n + 1) - math.lgamma(max(u - n, 0) + 1)) / math.log(2))


MDL_ROWS = 5000       # the most rows at an example for the description length (else missing)
MDL_MAPPINGS = 64     # the most column tuples taken from one earlier Table
_W = np.random.default_rng(12345).integers(1, 2**63, 64, dtype=np.uint64) | np.uint64(1)


def _keys(a):
    """One 64-bit hash per row of the int array a, from its values in order (a wrapping weighted sum)."""
    if a.shape[1] > len(_W):
        raise ValueError("too wide")
    return (a.astype(np.int64).astype(np.uint64) * _W[:a.shape[1]]).sum(1, dtype=np.uint64)


def _cols(r, sp, ks):
    return np.concatenate([r[:, sp[k][0]:sp[k][1]] for k in ks], 1)


def description_gain(types, sp, rows, earlier, n_train):
    """mdl_gain and mdl_share (informativeness): the minimum description length gain of the Table's rows given its
    earlier Tables (ex_output left out by the caller), as means over the train examples with rows; None where no
    example has rows, no column is left once Example columns are out, or an example has over MDL_ROWS rows.

    The code, at each train example e, with the Example columns left out:
    - the alphabet of a column is the distinct values of its type at e, over the earlier Tables and the Table;
    - raw: the count n_e of rows by Rissanen's universal code (of n_e + 1), then the set of rows as one of the
      (U_e choose n_e) sets of n_e distinct tuples of the product U_e of the columns' alphabets;
    - given the earlier Tables: a model is a set of disjoint blocks of the Table's columns, each block with one
      predictor, the distinct rows of one earlier Table's projection onto columns of the same types at e (a single
      column, or a tuple of columns of one earlier Table). A row is predicted where every block's values are in its
      predictor. The predicted rows are coded as a count and one set of the product of the predictors' sizes and
      the alphabets of the columns in no block; the other rows as a count and one set raw;
    - the model is one for every example: the count of blocks by the universal code and log2 of the count of
      candidate predictors per block, once, shared equally among the examples with rows. One bit says whether a
      model is used; the code is the shorter of the two. The model is chosen greedily, adding the block that
      shortens the code most until none does. Candidates: every column of an earlier Table of the column's type,
      and the tuples of two or more of the Table's columns mapped injectively to columns of one earlier Table where
      each single mapping predicts at least half of the rows (at most MDL_MAPPINGS per earlier Table).
    gain_e = raw bits - given bits; mdl_gain is the mean of gain_e / n_e, mdl_share the mean of gain_e / raw bits
    (where the raw bits are above 0). A share near 1 is a Table the earlier Tables give; near 0, one they do not."""
    cols = [j for j, ty in enumerate(types) if ty != "Example"]
    n = [len(r) for r in rows]
    if not cols or not any(n) or max(n) > MDL_ROWS:
        return np.nan, np.nan
    ex = [e for e in range(n_train) if n[e]]
    tset = {types[j] for j in cols}
    pre = _mdl_earlier(earlier, n_train)
    esp = pre["esp"]
    # the alphabets: distinct values of each type at each example; the earlier Tables' part is one sorted array
    alpha = {ty: [[pre["alpha"](ty, e)] for e in range(n_train)] for ty in tset}
    mine = {}
    def keys_of(bj, e):
        if (bj, e) not in mine:
            mine[(bj, e)] = _keys(_cols(rows[e], sp, bj))
        return mine[(bj, e)]
    for j in cols:
        for e in ex:
            alpha[types[j]][e].append(keys_of((j,), e))
    size = {ty: [len(np.unique(np.concatenate(alpha[ty][e]))) if e in ex else 1 for e in range(n_train)] for ty in tset}
    la = {j: np.array([math.log2(max(size[types[j]][e], 1)) for e in range(n_train)]) for j in cols}
    all_bits = [sum(la[j][e] for j in cols) for e in range(n_train)]
    raw = np.zeros(n_train)
    for e in ex:
        raw[e] = bits_count(n[e]) + log2_choose(all_bits[e], n[e])
    # candidate blocks: (columns, log2 size per example, predicted mask per example); one per distinct predictor
    cands, seen = [], {}
    def add(bj, sets, hashes=None):
        key = (bj, tuple(hash(sets[e].tobytes()) for e in ex) if hashes is None else tuple(hashes[e] for e in ex))
        if key in seen:
            return seen[key]
        sizes, masks, hit = np.zeros(n_train), [None] * n_train, 0
        for e in ex:
            sizes[e] = math.log2(max(len(sets[e]), 1))
            p, k = sets[e], keys_of(bj, e)
            if len(p):
                i = np.searchsorted(p, k)
                i[i == len(p)] = 0
                masks[e] = p[i] == k
            else:
                masks[e] = np.zeros(n[e], bool)
            hit += int(masks[e].sum())
        cands.append((bj, sizes, masks))
        seen[key] = hit
        return hit
    total_rows = sum(n)
    for xi, (x, xsp) in enumerate(zip(earlier, esp)):
        singles = {}
        for j in cols:
            for k, ty in enumerate(x[0]):
                if ty != types[j]:
                    continue
                sets, hashes = pre["single"](xi, k)
                hit = add((j,), sets, hashes)
                if hit * 2 >= total_rows:
                    singles.setdefault(j, []).append(k)
        if len(singles) < 2:
            continue
        js = sorted(singles)
        made = 0
        for combo in itertools.product(*[singles[j] + [None] for j in js]):
            m = [(j, k) for j, k in zip(js, combo) if k is not None]
            if len(m) < 2 or len({k for _, k in m}) < len(m):
                continue
            bj, bk = tuple(j for j, _ in m), tuple(k for _, k in m)
            add(bj, [_projection(x, xsp, bk, e) if e in ex else None for e in range(n_train)])
            made += 1
            if made >= MDL_MAPPINGS:
                break
    if not cands:
        return 0.0, 0.0
    name_bits = math.log2(len(cands))
    def given(model):
        """Bits per example of the rows given the model (without the model's own bits)."""
        used = {j for c in model for j in c[0]}
        out = np.zeros(n_train)
        for e in ex:
            mask = model[0][2][e]
            lu = sum(la[j][e] for j in cols if j not in used) + model[0][1][e]
            for c in model[1:]:
                mask = mask & c[2][e]
                lu += c[1][e]
            k = int(mask.sum())
            out[e] = bits_count(k) + log2_choose(lu, k) + bits_count(n[e] - k) + log2_choose(all_bits[e], n[e] - k)
        return out
    model, best = [], None
    while True:
        used = {j for c in model for j in c[0]}
        step = None
        for c in cands:
            if used & set(c[0]):
                continue
            g = given(model + [c])
            total = g.sum() + bits_count(len(model) + 1) + name_bits * (len(model) + 1)
            if step is None or total < step[0]:
                step = (total, c, g)
        if step is None or (best is not None and step[0] >= best[0]):
            break
        model.append(step[1])
        best = (step[0], step[2])
    if model and best[0] < raw.sum():
        cond = best[1].copy()
        for e in ex:
            cond[e] += (bits_count(len(model)) + name_bits * len(model)) / len(ex)
    else:
        cond = raw.copy()
    for e in ex:
        cond[e] += 1.0 / len(ex)
    gain = raw - cond
    per_row = [gain[e] / n[e] for e in ex]
    shares = [gain[e] / raw[e] for e in ex if raw[e] > 0]
    return float(np.mean(per_row)), (float(np.mean(shares)) if shares else np.nan)


_PROJ = {}   # (id of an earlier Table's rows, columns, example) -> (the rows, the projection's keys); emptied per task
_MDL = {}    # the ids of a list of earlier Tables -> (the list, `_mdl_earlier`'s constants); emptied per task


def _mdl_earlier(earlier, n_train):
    """What `description_gain` takes of a list of earlier Tables alone, kept in _MDL by the ids of its entries:
    "esp", the spans of each; "alpha"(type, example), the sorted distinct `_keys` of the columns of that type at
    that example over the list; "single"(index in the list, column), the projection onto that column at each
    example (`_projection`) and the hash of each projection's bytes."""
    key = tuple(id(x) for x in earlier)
    got = _MDL.get(key)
    if got is not None and len(got[0]) == len(earlier) and all(a is b for a, b in zip(got[0], earlier)):
        return got[1]
    esp = [spans(x[0]) for x in earlier]
    alphas, singles = {}, {}
    def alpha(ty, e):
        if (ty, e) not in alphas:
            parts = [_projection(x, xsp, (k,), e) for x, xsp in zip(earlier, esp) for k, t in enumerate(x[0]) if t == ty]
            alphas[(ty, e)] = np.unique(np.concatenate(parts)) if parts else np.zeros(0, np.uint64)
        return alphas[(ty, e)]
    def single(xi, k):
        if (xi, k) not in singles:
            x = earlier[xi]
            sets = [_projection(x, esp[xi], (k,), e) for e in range(n_train)]
            singles[(xi, k)] = (sets, [hash(p.tobytes()) for p in sets])
        return singles[(xi, k)]
    got = (list(earlier), dict(esp=esp, alpha=alpha, single=single))
    _MDL[key] = got
    return got[1]


def _projection(x, xsp, ks, e):
    """The distinct rows of earlier Table x at example e projected onto its columns ks, as sorted unique `_keys`."""
    key = (id(x[1]), ks, e)
    got = _PROJ.get(key)
    if got is None or got[0] is not x[1]:
        r = x[1][e]
        got = (x[1], np.unique(_keys(_cols(r, xsp, ks))) if len(r) else np.zeros(0, np.uint64))
        _PROJ[key] = got
    return got[1]


_EARLIER_VALUES = {}   # the ids of a list of earlier Tables -> (the list, its value sets per example); emptied per task
_VALUE_SETS = {}       # id of an earlier Table's entry -> (the entry, its value sets per example); emptied per task


def value_set(types, sp, r):
    """The distinct (type, value) pairs of rows r, Example columns left out."""
    return {(ty, tuple(x)) for j, ty in enumerate(types) if ty != "Example"
            for x in unique_axis0(r[:, sp[j][0]:sp[j][1]]).tolist()} if len(r) else set()


def new_values(types, sp, rows, earlier, n_train):
    """new_values (INFORMATIVE): the mean over the train examples with rows of the share of the (type, value) pairs
    of the rows (Example columns left out) that no earlier Table of `earlier` holds at that example; None where no
    example has rows."""
    key = tuple(id(x) for x in earlier)
    if key not in _EARLIER_VALUES:
        held = [set() for _ in range(n_train)]
        for x in earlier:
            if id(x) not in _VALUE_SETS:
                esp = spans(x[0])
                _VALUE_SETS[id(x)] = (x, [value_set(x[0], esp, x[1][e]) for e in range(n_train)])
            for e, vs in enumerate(_VALUE_SETS[id(x)][1]):
                held[e] |= vs
        _EARLIER_VALUES[key] = (earlier, held)
    held = _EARLIER_VALUES[key][1]
    shares = []
    for e in range(n_train):
        vs = value_set(types, sp, rows[e])
        if vs:
            shares.append(len(vs - held[e]) / len(vs))
    return float(np.mean(shares)) if shares else np.nan


def relevance(types, sp, rows, ins, outs, boxes, n_train):
    """out_fd, changed_share and out_consistent (RELEVANCE) of rows (one array per train example)."""
    fd = cons = False
    shares = []
    named = [set() for _ in range(n_train)]
    for b in boxes:
        others = [j for j, ty in enumerate(types) if ty != "Example" and j != b]
        fd_b, fd_wide, seen_e = True, False, 0
        pooled = {}
        for e in range(n_train):
            o, r = outs[e], rows[e]
            ho, wo = o.shape
            x = r[:, sp[b][0]:sp[b][1]]
            if len(x) == 0:
                continue
            cell = (x >= 0).all(1) & (x[:, 0] + x[:, 1] == ho - 1) & (x[:, 2] + x[:, 3] == wo - 1)
            if not cell.any():
                continue
            seen_e += 1
            rr, cc = x[cell, 0], x[cell, 2]
            named[e] |= set(zip(rr.tolist(), cc.tolist()))
            color = o[rr, cc]
            key = (np.concatenate([r[cell][:, sp[j][0]:sp[j][1]] for j in others], 1) if others
                   else np.zeros((int(cell.sum()), 0), np.int32))
            _, kid = unique_axis0(key, return_inverse=True) if key.shape[1] else (None, np.zeros(len(key), np.int64))
            kid = kid.reshape(-1)
            n_keys = int(kid.max()) + 1
            n_pairs = n_distinct_rows(np.stack([kid, color.astype(np.int64)], 1))
            fd_b &= n_pairs == n_keys
            fd_wide |= n_keys < len(kid)
            for k_, c_ in zip(map(tuple, key.tolist()), color.tolist()):
                pooled.setdefault(k_, {}).setdefault(c_, set()).add(e)
        if seen_e:
            fd |= fd_b and fd_wide
            cons |= (all(len(cs) == 1 for cs in pooled.values())
                     and any(len(next(iter(cs.values()))) >= 2 for cs in pooled.values()))
    for e in range(n_train):
        if named[e]:
            g, o = ins[e], outs[e]
            diff = np.ones(o.shape, bool) if g.shape != o.shape else (g != o)
            shares.append(float(np.mean([diff[r_, c_] for r_, c_ in named[e]])))
    return dict(out_fd=float(fd), changed_share=float(np.mean(shares)) if shares else 0.0, out_consistent=float(cons))


def sibling_contrast(snap, hashes):
    """{Table index of snap["tables"]: (sib_same, sib_unique)} for every Table at position 0 (relevance to the
    search, from the candidates alone). The siblings of a member are the other members of its branch point (its
    case name less the last `__` part) that have a Table at position 0. sib_same: the share of the siblings with
    some Table at position 0 whose rows_hash equals this Table's. sib_unique: the share of this Table's rows, each
    with its train example, that no sibling's Table at position 0 of the same column types holds at that example.
    Both are None where the Table is unseen, its rows come from projections, or the member has no sibling; sib_unique
    is None where the Table has no row."""
    tables = snap["tables"]
    point = lambda c: c.rsplit("__", 1)[0]
    by_point = defaultdict(list)
    for case, m in snap["members"].items():
        by_point[point(case)].append(case)
    rowsets = {}
    def rowset(i):
        if i not in rowsets:
            t = tables[i]
            rowsets[i] = (None if t["unseen"] is not None or t["rows"] is None else
                          {(e, tuple(x)) for e, r in enumerate(t["rows"]) for x in r.tolist()})
        return rowsets[i]
    out = {}
    for case, m in snap["members"].items():
        sibs = [c for c in by_point[point(case)] if c != case]
        for i in m["p0"]:
            t = tables[i]
            if not sibs or hashes.get(i) is None:
                out[i] = (np.nan, np.nan)
                continue
            same = sum(any(hashes.get(k) == hashes[i] for k in snap["members"][c]["p0"]) for c in sibs)
            mine = rowset(i)
            held = set()
            for c in sibs:
                for k in snap["members"][c]["p0"]:
                    if tables[k]["types"] == t["types"] and rowset(k):
                        held |= rowset(k)
            out[i] = (same / len(sibs), len(mine - held) / len(mine) if mine else np.nan)
    return out


def rows_hash(t, rows_of):
    """A hash of Table t's column types and its unique rows at each train example; None where it is unseen or its
    rows come from projections."""
    import hashlib
    if t.unseen is not None:
        return None
    rows = rows_of(t)
    if rows is None:
        return None
    h = hashlib.sha1(",".join(t.types).encode())
    for r in rows:
        h.update(np.ascontiguousarray(r, np.int32).tobytes()); h.update(b"|%d|" % len(r))
    return h.hexdigest()


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


# ------------------------------------------------------------------ factors

FACTOR_MAPPINGS = 16     # the most column mappings of a factor onto one source Table, or onto one Table of its shape
FACTOR_SHAPES = 40       # the most earlier Tables of a factor's shape compared for a union, intersection or difference
GRADED_FACTOR = GRADED + ADDED
AGGREGATES = ("max", "min", "big")
FACTOR_COLUMNS = ["f_factors", "n_factors", "n_surviving", "n_joins", "n_shared", "n_self_join", "factor_width",
                  "factor_untested", "factor_kinds", "factor_tests", "factor_classes", "table_classes"]


def factorize(t, rows):
    """The factors of Table t (rows: one array per train example) by its where-provenance (`t.flows`): [{"kind",
    "columns", "source", "map"}]. Example columns belong to no factor. In order: where the Table has two or more
    columns and more than one row at some example, a column of one value in every row of every example is a factor
    `constant` (a Table of one row at every example, such as a DET's one chosen value, has no constant factor: its
    value depends on the task); a column equal in every row to an earlier column of its type is a
    factor `duplicate`; each earlier table that some column's copy flows name (a source in another table of the
    case) is a factor `copy` of every such column, with `map` giving each column's source columns; a column with no
    such copy flow is a factor of its own: `computed` where some flow computes it (`source`: the tables those flows
    name), `lib` where every flow is a lib relation, a lib name or a constant, and `unsourced` where it has no
    flows."""
    types = list(t.types)
    sp = spans(types)
    cols = [j for j, ty in enumerate(types) if ty != "Example"]
    ex_nz = [e for e, r in enumerate(rows) if len(r)]
    out, const, dup = [], set(), set()
    may_be_constant = len(cols) > 1 and any(len(rows[e]) > 1 for e in ex_nz)
    for j in cols if may_be_constant else []:
        a, b = sp[j]
        vals = set()
        for e in ex_nz:
            vals |= set(map(tuple, unique_axis0(rows[e][:, a:b]).tolist()))
            if len(vals) > 1:
                break
        if len(vals) == 1:
            const.add(j)
            out.append(dict(kind="constant", columns=[j], source=None, map=None))
    for i, j in itertools.combinations(cols, 2):
        if j in const or j in dup or i in dup or types[i] != types[j]:
            continue
        if ex_nz and all((rows[e][:, sp[i][0]:sp[i][1]] == rows[e][:, sp[j][0]:sp[j][1]]).all() for e in ex_nz):
            dup.add(j)
            out.append(dict(kind="duplicate", columns=[j], source=None, map=None))
    copies = defaultdict(lambda: defaultdict(set))
    flows = getattr(t, "flows", None) or [[] for _ in types]
    for j in cols:
        if j in const or j in dup:
            continue
        fl = flows[j]
        named = [(st, sc) for kind, st, sc, det, rel in fl if kind == 0 and st >= 0 and st != t.export_table]
        if named:
            for st, sc in named:
                copies[st][j].add(sc)
        elif any(kind == 1 for kind, *_ in fl):
            src = sorted({st for kind, st, sc, det, rel in fl if st >= 0 and st != t.export_table})
            out.append(dict(kind="computed", columns=[j], source=src, map=None))
        elif fl:
            out.append(dict(kind="lib", columns=[j], source=None, map=None))
        else:
            out.append(dict(kind="unsourced", columns=[j], source=None, map=None))
    for st in sorted(copies):
        m = copies[st]
        out.append(dict(kind="copy", columns=sorted(m), source=st, map={j: sorted(s) for j, s in m.items()}))
    return out


def factor_rows(rows, sp, columns):
    """The unique rows of the projection onto `columns`, one array per example."""
    return [unique_rows(np.concatenate([r[:, sp[j][0]:sp[j][1]] for j in columns], 1)) if len(r) else
            np.zeros((0, sum(sp[j][1] - sp[j][0] for j in columns)), np.int32) for r in rows]


def remapped(types, k, ftypes, rows, limit):
    """The keyed rows of an earlier Table (types, keyed rows k, rows) remapped onto a factor's column types: one per
    mapping of the factor's columns to distinct columns of the Table of the same types, at most `limit`; with
    whether the limit cut it."""
    sp = spans(types)
    opts = [[c for c, ty in enumerate(types) if ty == ft] for ft in ftypes]
    out, cut = [], False
    for m in itertools.product(*opts):
        if len(set(m)) < len(m):
            continue
        if len(out) >= limit:
            cut = True
            break
        idx = [i for c in m for i in range(sp[c][0], sp[c][1])]
        out.append({e: frozenset(map(tuple, r[:, idx].tolist())) for e, r in enumerate(rows)})
    return out, cut


def factor_test(f, ftypes, fk, frows, t, by_table, shaped, n_train, sizes=None):
    """(degenerate, the test that decides, untested) of factor f of Table t, its projection's column types, keyed rows
    fk and rows; by_table: {case table: [(types, rows, keyed rows or None, positions)]} of the member's earlier
    Tables; shaped: [(types, rows, keyed rows)] of the earlier Tables with keyed rows; sizes: the input grid's
    (height, width) at each train example, for `lib_pair_test`."""
    kind = f["kind"]
    if kind in ("constant", "duplicate", "lib"):
        return True, kind, False
    if max(len(r) for r in frows) > SET_ROWS:
        return False, "over bound", True
    untested, selection, mapped = False, False, False
    # an `unsourced` factor names no source: no table of the case derives it
    srcs = by_table.get(f["source"], []) if kind == "copy" else [s for st in f["source"] or [] for s in by_table.get(st, [])]
    if kind == "copy" and not srcs:
        untested = True
    for ty, rr, k, pos in srcs:
        if kind == "copy" and pos is not None:
            opts = [[pos.index(sc) for sc in f["map"][j] if sc in pos] for j in f["columns"]]
            if all(opts):
                sp = spans(ty)
                for n_m, m in enumerate(itertools.product(*opts)):
                    if n_m >= FACTOR_MAPPINGS:
                        untested = True
                        break
                    if any(ty[c] != ft for c, ft in zip(m, ftypes)):
                        continue
                    idx = [i for c in m for i in range(sp[c][0], sp[c][1])]
                    proj = [frozenset(map(tuple, r[:, idx].tolist())) for r in rr]
                    mapped = True
                    if all(fk[e] == proj[e] for e in range(n_train)):
                        return True, "redundant", False
                    selection |= all(fk[e] <= proj[e] for e in range(n_train))
        if k is not None and restates(ftypes, fk, ty, k):
            return True, "redundant", False
    named = {id(s[2]) for s in srcs}
    for ty, rr, k in shaped if kind == "copy" else []:
        if id(k) not in named and restates(ftypes, fk, ty, k):
            return True, "restates", False
    want = sorted(ftypes)
    cands = [(ty, rr, k) for ty, rr, k in shaped if sorted(x for x in ty if x != "Example") == want]
    if len(cands) > FACTOR_SHAPES:
        cands, untested = cands[:FACTOR_SHAPES], True
    maps = []
    for ty, rr, k in cands:
        ms, cut = remapped(ty, k, ftypes, rr, FACTOR_MAPPINGS)
        maps += ms
        untested |= cut
    ex = range(n_train)
    if any(all(m[e] == fk[e] for e in ex) for m in maps):
        return True, "equal", False
    subs = [m for m in maps if all(m[e] <= fk[e] for e in ex)]
    sups = [m for m in maps if all(m[e] >= fk[e] for e in ex)]
    for a, b in itertools.combinations(subs, 2):
        if all(a[e] | b[e] == fk[e] for e in ex):
            return True, "union", False
    for a, b in itertools.combinations(sups, 2):
        if all(a[e] & b[e] == fk[e] for e in ex):
            return True, "intersection", False
    for a in sups:
        for b in maps:
            if b is not a and all(a[e] - b[e] == fk[e] for e in ex):
                return True, "difference", False
    how, cut = pair_test(ftypes, fk, shaped, n_train)
    if how is None and sizes is not None:
        how = lib_pair_test(ftypes, fk, shaped, n_train, sizes)
    if how is not None:
        return True, how, False
    untested |= cut
    return False, "selection" if selection else "partial" if mapped else "survives", untested


PAIR_CANDIDATES = 400   # the most column choices of the earlier Tables that pair_test tries for one factor
_PAIR_SETS = {}   # (id of an earlier Table's keyed rows, the two column spans, kind) -> (the keyed rows, the
                  # per-example pairs or maps that pair_test and member_pairs build of them); emptied per task


def _pair_sets(k, sa, sb, ex):
    """[frozenset of the rows of keyed rows k at each example of ex, cut to the columns of spans sa then sb], kept in
    _PAIR_SETS."""
    key = (id(k), sa, sb, "pairs")
    got = _PAIR_SETS.get(key)
    if got is None or got[0] is not k:
        got = (k, [frozenset(r[sa[0]:sa[1]] + r[sb[0]:sb[1]] for r in k[e]) for e in ex])
        _PAIR_SETS[key] = got
    return got[1]


def _member_maps(k, ka, ca, ex):
    """[{value of column span ka: value of column span ca} of keyed rows k at each example of ex], or None where
    some value of ka has two values of ca at some example; kept in _PAIR_SETS."""
    key = (id(k), ka, ca, "maps")
    got = _PAIR_SETS.get(key)
    if got is None or got[0] is not k:
        maps = []
        for e in ex:
            m = {}
            for r in k[e]:
                x, v = r[ka[0]:ka[1]], r[ca[0]:ca[1]]
                if m.setdefault(x, v) != v:
                    maps = None
                    break
            if maps is None:
                break
            maps.append(m)
        got = (k, maps)
        _PAIR_SETS[key] = got
    return got[1]


def pair_test(ftypes, fk, shaped, n_train):
    """(the test that makes a factor of two columns of one type degenerate, or None; whether PAIR_CANDIDATES or an
    earlier Table without keyed rows cut the tests), the lint's tests of src/study/table_lint.py against the
    earlier Tables [(types, rows, keyed rows)], each at every train example:
    - `class`: the pairs (x, y) of members of one class, x = y kept or left out, where some earlier Table gives each
      member of one of its columns one value of another column (a class membership);
    - `order`: the pairs (x, y) with score(x) < score(y), or <=, x = y kept or left out, in either column order,
      where some earlier Table gives each member of one of its columns one value of a Number column (a score);
    - `closure`: the transitive closure of the pairs of two columns of an earlier Table, or that closure with the
      pairs (x, x) of its members added, where those pairs are within the factor's and not equal to them."""
    if len(ftypes) != 2 or ftypes[0] != ftypes[1] or ftypes[0] == "Example":
        return None, False
    w = E.width(ftypes[0])
    ex = range(n_train)
    if not any(fk[e] for e in ex):
        return None, False
    want = [fk[e] for e in ex]
    swap = [frozenset(r[w:] + r[:w] for r in fk[e]) for e in ex]
    tried, cut = 0, False
    for ty, _, k in shaped:
        if k is None:
            cut = True
            continue
        sp = spans(ty)
        mine = [j for j, t in enumerate(ty) if t == ftypes[0]]
        other = [j for j, t in enumerate(ty) if t != "Example"]
        for a in mine:
            for c in other:
                if c == a:
                    continue
                tried += 1
                if tried > PAIR_CANDIDATES:
                    return None, True
                got = member_pairs(k, sp[a], sp[c], ty[c] == "Number", want, swap, ex)
                if got:
                    return got, cut
        for a, b in itertools.permutations(mine, 2):
            tried += 1
            if tried > PAIR_CANDIDATES:
                return None, True
            proj = _pair_sets(k, sp[a], sp[b], ex)
            if not all(proj[e] <= want[e] for e in ex) or proj == want:
                continue
            if all(closure_equal(proj[e], want[e], w) for e in ex):
                return "closure", cut
    return None, cut


def _group_pairs(S, key, ordered):
    """The pairs of distinct cells of S with equal key(cell): both orders, or one where `ordered`."""
    n = sum(k * (k - 1) for k in Counter(map(key, S)).values())
    return n // 2 if ordered else n


_OFFSETS4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
_DIAG = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
_ROW, _COL = (lambda s: s[0]), (lambda s: s[1])
_D1, _D2 = (lambda s: s[0] - s[1]), (lambda s: s[0] + s[1])
# (name, whether a pair (dr, dc) of distinct cells is in the relation, the relation's pairs within a cell set S)
LIB_PAIRS = [("neighbor", lambda dr, dc: abs(dr) + abs(dc) == 1, lambda S: sum((r + a, c + b) in S for r, c in S for a, b in _OFFSETS4)),
             ("neighbor8", lambda dr, dc: max(abs(dr), abs(dc)) == 1,
              lambda S: sum((r + a, c + b) in S for r, c in S for a, b in _OFFSETS4 + _DIAG)),
             ("diag neighbor", lambda dr, dc: abs(dr) == abs(dc) == 1, lambda S: sum((r + a, c + b) in S for r, c in S for a, b in _DIAG)),
             ("same row", lambda dr, dc: dr == 0, lambda S: _group_pairs(S, _ROW, False)),
             ("same column", lambda dr, dc: dc == 0, lambda S: _group_pairs(S, _COL, False)),
             ("same line", lambda dr, dc: dr == 0 or dc == 0, lambda S: _group_pairs(S, _ROW, False) + _group_pairs(S, _COL, False)),
             ("same diagonal", lambda dr, dc: abs(dr) == abs(dc),
              lambda S: _group_pairs(S, _D1, False) + _group_pairs(S, _D2, False))]
LIB_PAIRS += [(f"step {a},{b}", lambda dr, dc, a=a, b=b: (dr, dc) == (a, b),
               lambda S, a=a, b=b: sum((r + a, c + b) in S for r, c in S)) for a, b in _OFFSETS4 + _DIAG]
LIB_PAIRS += [(f"ray {a},{b}", lambda dr, dc, a=a, b=b: (dr == 0 if a == 0 else dr * a > 0) and (dc == 0 if b == 0 else dc * b > 0)
               and (a == 0 or b == 0 or abs(dr) == abs(dc)),
               lambda S, a=a, b=b: _group_pairs(S, _ROW if a == 0 else _COL if b == 0 else _D1 if a == b else _D2, True))
              for a, b in _OFFSETS4 + _DIAG]


def lib_pair_test(ftypes, fk, shaped, n_train, sizes):
    """`lib pair` where a factor of two Box columns, its pairs of distinct cells, equals a cell relation of the lib
    (LIB_PAIRS: adjacency, a line, a step or a ray) restricted to the cells of one Box column of an earlier Table,
    at every train example; the pairs (x, x), where the factor has them, are then those of every such cell. Else
    None."""
    if ftypes != ["Box", "Box"]:
        return None
    ex = range(n_train)
    cells, diag = [], []
    for e in ex:
        h, w = sizes[e]
        got, same = [], set()
        for r in fk[e]:
            x, y = r[:4], r[4:]
            for t_, b_, l_, r_ in (x, y):
                if min(t_, b_, l_, r_) < 0 or t_ + b_ != h - 1 or l_ + r_ != w - 1:
                    return None
            if x == y:
                same.add((x[0], x[2]))
            else:
                got.append(((x[0], x[2]), (y[0], y[2])))
        cells.append(got); diag.append(same)
    if not any(cells):
        return None
    rels = [(name, count) for name, pred, count in LIB_PAIRS
            if all(pred(b[0] - a[0], b[1] - a[1]) for e in ex for a, b in cells[e])]
    if not rels:
        return None
    nodes = [{c for p in cells[e] for c in p} | diag[e] for e in ex]
    for ty, rr, _ in shaped:
        for j, t_ in enumerate(ty):
            if t_ != "Box":
                continue
            o = spans(ty)[j][0]
            S = []
            for e in ex:
                h, w = sizes[e]
                x = rr[e][:, o:o + 4]
                ok = (x >= 0).all(1) & (x[:, 0] + x[:, 1] == h - 1) & (x[:, 2] + x[:, 3] == w - 1)
                S.append(set(zip(x[ok, 0].tolist(), x[ok, 2].tolist())))
            if not all(nodes[e] <= S[e] for e in ex) or any(diag[e] and diag[e] != S[e] for e in ex):
                continue
            for name, count in rels:
                if all(count(S[e]) == len(cells[e]) for e in ex):
                    return "lib pair"
    return None


def member_pairs(k, ka, ca, score, want, swap, ex):
    """`class` or `order` where the pairs `want` (per example) are the pairs that keyed rows k's column ka gives by
    its column ca as a class or, where `score`, as an order; else None."""
    maps = _member_maps(k, ka, ca, ex)
    if maps is None:
        return None
    for e, m in zip(ex, maps):
        nodes = {r[:len(r) // 2] for r in want[e]} | {r[len(r) // 2:] for r in want[e]}
        if not nodes <= m.keys() or len(m) < 2:
            return None
    # class: the count of pairs before the pairs themselves
    ok_class = []
    for diag in (True, False):
        if all(sum(n * n - (0 if diag else n) for n in Counter(maps[e].values()).values()) == len(want[e]) for e in ex):
            ok_class.append(diag)
    for diag in ok_class:
        if all(frozenset(x + y for x in maps[e] for y in maps[e] if maps[e][x] == maps[e][y] and (diag or x != y))
               == want[e] for e in ex):
            return "class"
    if not score:
        return None
    for strict in (True, False):
        for diag in ((False,) if strict else (True, False)):
            def holds(e, x, y):
                return (maps[e][x] < maps[e][y] if strict else maps[e][x] <= maps[e][y]) and (diag or x != y)
            if not all(order_count(maps[e], strict, diag) == len(want[e]) for e in ex):
                continue
            got = [frozenset(x + y for x in maps[e] for y in maps[e] if holds(e, x, y)) for e in ex]
            if got == want or got == swap:
                return "order"
    return None


def order_count(m, strict, diag):
    """The count of pairs (x, y) of the keys of m with m[x] < m[y], or m[x] <= m[y] with x = y kept or left out."""
    n, ties = len(m), sum(c * c for c in Counter(m.values()).values())
    less = (n * n - ties) // 2
    return less if strict else less + ties - (0 if diag else n)


def closure_equal(step, want, w):
    """Whether the transitive closure of the pairs `step` (flat tuples of two values of width w), or that closure
    with (x, x) for each member, is the pairs `want`; the walk stops once it passes `want`'s size."""
    nxt = defaultdict(set)
    for r in step:
        nxt[r[:w]].add(r[w:])
    got = set()
    for x in list(nxt):
        seen, todo = set(), list(nxt[x])
        while todo:
            y = todo.pop()
            if y in seen:
                continue
            seen.add(y)
            got.add(x + y)
            if len(got) > len(want):
                return False
            todo += nxt.get(y, ())
    if got == want:
        return True
    nodes = {r[:w] for r in step} | {r[w:] for r in step}
    return got | {x + x for x in nodes} == want


GEOMETRY_ROOTS = {("in", 0), ("in", 1), ("const",), ("example",)}   # with every ("lib", relation)


def all_cells(t, rows, pairs, n_train):
    """Whether Table t (rows: one array per train example) is every cell of the input grid with fixed decorations:
    some Box column's distinct values at every train example are every cell of that example's input grid, and each
    other column (Example columns left out) is one of: of one value at each train example (a constant, or a DET's
    chosen value); a Color column that holds the input's color at that Box column's cell in every row; or a lib
    function of the cell, a column whose flows (`roots`, the cache's `lineage`) reach only ex_input's Example and
    cell columns, constants and lib relations, and no recursive relation."""
    roots = getattr(t, "roots", None)
    if not roots or not all(len(r) for r in rows):
        return False
    types = list(t.types)
    sp = spans(types)
    ins = [np.array(pairs[e]["input"]) for e in range(n_train)]
    cells = [{(r, g.shape[0] - 1 - r, c, g.shape[1] - 1 - c) for r in range(g.shape[0]) for c in range(g.shape[1])}
             for g in ins]
    def one_value(k):
        a, b = sp[k]
        return all(n_distinct_rows(rows[e][:, a:b]) == 1 for e in range(n_train))
    def input_color(k, j):
        a = sp[j][0]
        for e in range(n_train):
            r, c = rows[e][:, a], rows[e][:, a + 2]
            if not (rows[e][:, sp[k][0]] == ins[e][r, c]).all():
                return False
        return True
    def geometry(k):
        rs = roots[k]
        return bool(rs) and all(x in GEOMETRY_ROOTS or x[0] == "lib" for x in rs)
    for j, ty in enumerate(types):
        if ty != "Box":
            continue
        a, b = sp[j]
        if all(set(map(tuple, rows[e][:, a:b].tolist())) == cells[e] for e in range(n_train)):
            if all(one_value(k) or (tk == "Color" and input_color(k, j)) or geometry(k)
                   for k, tk in enumerate(types) if k != j and tk != "Example"):
                return True
    return False


def factor_values(t, rows, flags, earlier, at, asg, pairs, n_train, whole=False):
    """The factor structure of Table t, its test per factor, f_factors, and the graded detectors and classify.py's
    classes on each surviving factor's projection, aggregated over the surviving factors as `<detector>@max`,
    `@min` and `@big` (the factor of the most columns, then of the most rows); where no factor survives, each
    aggregate is the Table's own value. earlier: the member's earlier Tables as `detectors` takes them; at: their
    "earlier_at" entries; whole: the Table as a whole is redundant
    (f_redundant), which makes every factor degenerate."""
    import classify as CL
    v = {k: np.nan for k in FACTOR_COLUMNS}
    v["f_factors"] = 0.0
    grids = [(p["input"], p["output"]) for p in pairs]
    if rows is None or not any(len(r) for r in rows):
        return v, []
    types = list(t.types)
    sp = spans(types)
    by_table, shaped = defaultdict(list), []
    for (ty, rr, _, k, _), a in zip(earlier, at):
        by_table[a.get("table")].append((ty, rr, k, a.get("positions")))
    seen = set()
    for ty, rr, _, k, _ in earlier:
        if k is not None and id(k) not in seen:
            seen.add(id(k))
            shaped.append((ty, rr, k))
    fs = factorize(t, rows)
    tests, surviving, untested, partial = [], [], False, []
    every_cell = not whole and all_cells(t, rows, pairs, n_train)
    for f in fs:
        ftypes = [types[j] for j in f["columns"]]
        frows = factor_rows(rows, sp, f["columns"])
        fk = keyed_rows(frows) if max(len(r) for r in frows) <= SET_ROWS else None
        if whole:
            deg, how, unt = True, "whole", False
        elif fk is None and f["kind"] not in ("constant", "duplicate", "lib"):
            deg, how, unt = False, "over bound", True
        else:
            deg, how, unt = factor_test(f, ftypes, fk, frows, t, by_table, shaped, n_train,
                                        [np.array(p["input"]).shape for p in pairs])
        if every_cell and (not deg or how == "partial"):
            deg, how = True, "all_cells"
        untested |= unt
        tests.append(how)
        if how == "partial":
            partial.append((f, ftypes, frows))
        elif not deg:
            surviving.append((f, ftypes, frows))
    covered = {j for f, how in zip(fs, tests) if how != "partial" for j in f["columns"]}
    surviving += [p for p in partial if not set(p[0]["columns"]) <= covered]
    if not surviving and not whole and not every_cell:
        # every factor is degenerate on its own; the table still adds signal unless its rows are the Cartesian
        # product of the factors' projections (a constant, duplicate or lib column is determined by the others)
        free = [(f, ft, fr) for f, ft, fr in zip(fs, (
            [types[j] for j in f["columns"]] for f in fs), (factor_rows(rows, sp, f["columns"]) for f in fs))
            if f["kind"] in ("copy", "computed", "unsourced")]
        if len(free) >= 2:
            cols = sorted(j for f, _, _ in free for j in f["columns"])
            joint = factor_rows(rows, sp, cols)
            product = all(len(joint[e]) == int(np.prod([len(fr[e]) for _, _, fr in free]))
                          for e in range(n_train) if len(rows[e]))
            if not product:
                tests.append("joint")
                surviving.append((dict(kind="joint", columns=cols, source=None, map=None), [types[j] for j in cols], joint))
    copies = [set(f["columns"]) for f in fs if f["kind"] == "copy"]
    v["n_factors"] = float(len(fs))
    v["n_surviving"] = float(len(surviving))
    v["n_joins"] = float(sum(bool(a & b) for a, b in itertools.combinations(copies, 2)))
    v["n_shared"] = float(len({j for a, b in itertools.combinations(copies, 2) for j in a & b}))
    v["n_self_join"] = float(sum(len(s) > 1 for f in fs if f["kind"] == "copy" for s in f["map"].values()))
    v["factor_width"] = float(sum(len(f["columns"]) for f, _, _ in surviving))
    v["factor_untested"] = float(untested)
    v["factor_kinds"] = ",".join(f["kind"] for f in fs)
    v["factor_tests"] = ",".join(tests)
    v["f_factors"] = float(not surviving)
    table_cls, _ = CL.classify(types, None, rows, grids)
    v["table_classes"] = "|".join(sorted(table_cls))
    per = []
    classes = []
    for f, ftypes, frows in surviving:
        ns = SimpleNamespace(types=ftypes, unseen=None)
        d = detectors(ns, flags, earlier, asg, pairs, n_train, lambda _x, r=frows: r, filters=False)
        per.append((len(ftypes), sum(len(r) for r in frows), d))
        classes.append("|".join(sorted(CL.classify(ftypes, None, frows, grids)[0])))
    v["factor_classes"] = ";".join(classes)
    return v, per


def aggregate(v, own, per):
    """The `<detector>@<aggregate>` columns from the per-factor values `per` [(width, rows, values)], or from the
    Table's own values where `per` is empty."""
    out = {}
    big = max(per, key=lambda p: (p[0], p[1]))[2] if per else None
    for g in GRADED_FACTOR:
        xs = [p[2][g] for p in per if p[2][g] is not None and not np.isnan(p[2][g])]
        if not per:
            out[f"{g}@max"] = out[f"{g}@min"] = out[f"{g}@big"] = own.get(g, np.nan)
        else:
            out[f"{g}@max"] = max(xs) if xs else np.nan
            out[f"{g}@min"] = min(xs) if xs else np.nan
            out[f"{g}@big"] = big[g]
    return out


# ------------------------------------------------------------------ compute

def load_task(export, frames, empty, task, labs):
    """`encoder.load_rollouts` of the task on a copy of its rows: the task's frame of each part of `frames` ({part:
    {task: frame}}, `bases` among them; the frame of `empty` where the task has none), its values and the label lines
    `labs`."""
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
            # the guard holds over the whole export, which loads as one; one task's tables may be mostly unseen.
            # The loader sums what `reconcile_unseen` returns for the guard, after that function has checked the
            # loader's counts against the export's, so the check stays and the guard sees no unseen table.
            real = E.reconcile_unseen
            def reconcile(*args, **kw):
                real(*args, **kw)
                return {}
            E.reconcile_unseen = reconcile
            try:
                return E.load_rollouts(tmp, strict=False, allow_violations=True)
            finally:
                E.reconcile_unseen = real


CACHE_BATCH = 100   # tasks whose frames one cache process holds at a time
CACHE_VERSION = 6   # raise on any change to task_snapshot or to what the cache holds
CACHE_DIR = ROOT / "work/lm/detector-cache"


def cache_path(export):
    """The cache of a rollout export: work/lm/detector-cache/<name>.pkl, <name> the export's parent directory, or,
    where that directory is `mut`, `foreign` or `writer` (a set of allpoints.py), `<its parent>-<it>`."""
    d = Path(export).resolve().parent
    return CACHE_DIR / (f"{d.parent.name}-{d.name}.pkl" if d.name in ("mut", "foreign", "writer", "ready") else f"{d.name}.pkl")


def export_stamp(export):
    """The cache's version, the export's path, encoder.table_stamp (the loader's version and the export's mtimes),
    and the whole-second mtimes of labels.jsonl and tables.parquet."""
    d = Path(export).resolve()
    return (CACHE_VERSION, str(d), E.table_stamp(d), int(os.path.getmtime(d / "labels.jsonl")),
            int(os.path.getmtime(d / "tables.parquet")))


def marks_path(export):
    """The marks file of the export's input-independence test: cache_path(export) with the suffix
    `.independent.parquet`."""
    return cache_path(export).with_suffix(".independent.parquet")


def join_marks(df, export):
    """df with the columns `f_independent` and `independent_untested` from the export's marks file (`marks_path`;
    its `f_independent` and `independent_untested_both`) on the Tables at position 0, by member case. A member that
    the marks file does not give, a Table at another position, and every Table where there is no marks file get
    neither value (missing)."""
    p = marks_path(export)
    m = (pd.read_parquet(p, columns=["case", "f_independent", "independent_untested_both"]).set_index("case")
         if p.exists() else pd.DataFrame(columns=["f_independent", "independent_untested_both"], dtype=float))
    p0 = df["position"] == 0
    for col, src in (("f_independent", "f_independent"), ("independent_untested", "independent_untested_both")):
        df[col] = df["case"].map(m[src].astype(float)).where(p0).astype(float)
    return df


def read_compute(parquet):
    """The parquet of `compute`, less the `<detector>@<aggregate>` columns of the aggregates other than AGGREGATE
    (where AGGREGATE is not None), which `with_factors` does not read."""
    import pyarrow.parquet as pq
    if AGGREGATE is None:
        return pd.read_parquet(parquet)
    other = {f"{g}@{x}" for g in GRADED_FACTOR for x in AGGREGATES if x != AGGREGATE}
    names = [c for c in pq.ParquetFile(parquet).schema_arrow.names if not c.startswith("__index_level_")]
    return pd.read_parquet(parquet, columns=[c for c in names if c not in other])


def read_marked(parquet, export):
    """The parquet of `compute` as `read_compute` gives it, with the export's marks joined (`join_marks`)."""
    return join_marks(read_compute(parquet), export)


def task_keys(export):
    """{task: the reuse key and the checks digest, as one text, of its line of the export's `parts/*.tasks.txt`}, for
    each line that gives a reuse key: the last two words of a line `<task> <seconds> <units> <key> <checks digest>`
    or `<task> <seconds> <key> <checks digest>`."""
    out = {}
    for f in (Path(export) / "parts").glob("*.tasks.txt"):
        for w in map(str.split, open(f)):
            if len(w) >= 4:
                out[w[0]] = " ".join(w[-2:])
    return out


def labels_by_task(export):
    """{task: [label lines]} of the export's labels.jsonl, as text, in file order."""
    out = defaultdict(list)
    for line in open(Path(export) / "labels.jsonl"):
        if line.strip():
            out[json.loads(line)["task"]].append(line)
    return out


def task_stamps(export, labels):
    """{task: stamp} for each task of `labels` ({task: label lines}). Where the export's `tasks.txt` gives the task a
    reuse key, the stamp is the cache's version, the loader's version, that key and the sha256 of the task's label
    lines; else it is `export_stamp`."""
    import hashlib
    keys, whole = task_keys(export), None
    out = {}
    for t, lines in labels.items():
        if t in keys:
            out[t] = (CACHE_VERSION, E.LOADER_VERSION, keys[t], hashlib.sha256("".join(lines).encode()).hexdigest())
        else:
            whole = whole or export_stamp(export)
            out[t] = whole
    return out


def join_stamp(export, stamps):
    """The stamp of the joined cache: `export_stamp` where no task has a reuse key, else the sha256 of the sorted
    (task, stamp) pairs `stamps`."""
    import hashlib
    if not any(len(s) == 4 for s in stamps.values()):
        return export_stamp(export)
    return hashlib.sha256(repr(sorted(stamps.items())).encode()).hexdigest()


def stamp_path(export):
    """The file beside the joined cache that holds the repr of its stamp, so the stamp is read without the cache."""
    return cache_path(export).with_suffix(".stamp")


def join_current(export, joined):
    """Whether cache_path(export) holds the stamp `joined`. A cache with no stamp file beside it is loaded once to
    read its stamp, and the file is written where the stamp is equal."""
    import pickle
    path = cache_path(export)
    if not path.exists():
        return False
    if not stamp_path(export).exists():
        with open(path, "rb") as f:
            if pickle.load(f)["stamp"] != joined:
                return False
        stamp_path(export).write_text(repr(joined))
    return stamp_path(export).read_text() == repr(joined)


def cache_stale(export):
    """Whether cache_path(export) is missing or does not hold the export's join stamp. It writes nothing."""
    import pickle
    path = cache_path(export)
    if not path.exists():
        return True
    joined = join_stamp(export, task_stamps(export, labels_by_task(export)))
    if stamp_path(export).exists():
        return stamp_path(export).read_text() != repr(joined)
    with open(path, "rb") as f:
        return pickle.load(f)["stamp"] != joined


def part_stamp(p):
    """The stamp of a per-task pickle, its first object, or None where there is no such file."""
    import pickle
    if not p.exists():
        return None
    with open(p, "rb") as f:
        return pickle.load(f)


def case_flows(fl):
    """{(case table, column): [(kind, source table, source column, det, source relation)]} of one case's rows of
    flows.parquet, in the export's column indexes."""
    out = defaultdict(list)
    if fl is None:
        return out
    for tab, col, kind, st, sc, det, rel in zip(fl["table"], fl["column"], fl["kind"], fl["source_table"],
                                                 fl["source_column"], fl["det"], fl["source_relation"]):
        out[(int(tab), int(col))].append((int(kind), int(st), int(sc), int(det), str(rel)))
    return out


def input_only(flows):
    """{(case table, column): whether every source the column reaches through the flows is ex_input, a constant, a lib
    name or a lib relation, and it reaches one}. A DET source, an ex_output source, or a source column with no flows
    makes it 0; a source in a cycle adds nothing."""
    memo = {}
    def reach(key, stack):
        if key in memo:
            return memo[key]
        if key in stack:
            return None
        stack.add(key)
        got = None
        for kind, st, sc, det, rel in flows.get(key, []):
            if det >= 0 or st == E.GRID_TABLES["ex_output"]:
                got = False
                break
            if st < 0 or st == E.GRID_TABLES["ex_input"] or sc < 0:
                got = True if got is None else got
                continue
            if (st, sc) not in flows:
                got = False
                break
            sub = reach((st, sc), stack)
            if sub is False:
                got = False
                break
            if sub:
                got = True
        stack.discard(key)
        memo[key] = got
        return got
    return {k: bool(reach(k, set())) for k in flows}


LINEAGE_OK = {("in", 0), ("in", 1), ("in", 2), ("const",), ("lib name",)}   # with every ("lib", relation)


def lineage(flows):
    """{(case table, column): the roots its where-provenance reaches through the flows}, a root being ("in", c) or
    ("out", c) for column c of ex_input or ex_output, ("const",), ("lib name",), ("lib", relation) for a lib
    relation's column, ("example",) for the example of a source's entry, ("none",) for a source column with no
    flows, and ("cycle",) where the column reaches itself (a recursive relation). A flow from a DET reaches the
    DET's relation's column."""
    keys = list(flows)
    direct, edges = {}, {}
    for k in keys:
        d, ed = set(), set()
        for kind, st, sc, det, rel in flows[k]:
            if kind == 2:
                d.add(("const",))
            elif kind == 3:
                d.add(("lib name",))
            elif st == E.GRID_TABLES["ex_input"]:
                d.add(("in", sc))
            elif st == E.GRID_TABLES["ex_output"]:
                d.add(("out", sc))
            elif st < 0:
                d.add(("lib", rel))
            elif sc < 0:
                d.add(("example",))
            elif (st, sc) in flows:
                ed.add((st, sc))
            else:
                d.add(("none",))
        direct[k], edges[k] = d, ed
    # the keys each key reaches, then its roots, by a fixpoint
    reach = {k: set(edges[k]) for k in keys}
    changed = True
    while changed:
        changed = False
        for k in keys:
            add = set().union(*(reach[j] for j in reach[k])) - reach[k] if reach[k] else set()
            if add:
                reach[k] |= add
                changed = True
    out = {}
    for k in keys:
        r = set(direct[k]).union(*(direct[j] for j in reach[k])) if reach[k] else set(direct[k])
        if k in reach[k] or any(j in reach[j] for j in reach[k]):
            r.add(("cycle",))
        out[k] = frozenset(r)
    return out


def lineage_independent(roots, colors=(("in", 2), ("out", 2))):
    """Whether a Table whose columns have `lineage`'s `roots` is a function of the grid sizes by its flows: every
    column has roots, none of them the Color column of a grid of `colors` or a source column with no flows. The
    flows give where a value comes from, not the tests that select rows, so a selection by color passes."""
    return bool(roots) and all(rs and not any(x in colors or x == ("none",) for x in rs) for rs in roots)


def task_snapshot(export, frames, empty, task, labs, flows=None):
    """What the detectors read of one task, loaded through `load_task`: {"pairs", "n_train", "rows", "tables",
    "earlier", "members", "skipped"}. "rows" is one dict per Table at positions 0 to POSITIONS - 1, in the order
    the parquet gives them, with its member, label and flags (after the budgets) and "det", the index in "tables"
    of the Table at position 0 (None at other positions). A "tables" entry is that Table before the budgets: its
    member, `types`, column `names`, `positions`, `unseen` (the reason, or None), `rows` (`train_rows`: the unique
    rows at each train example, as `train_rows` gives them; None where unseen or from projections), `wide` (the
    unique task-wide rows; None for an evidence table or where unseen), `keys` and `export_depth` (as
    tables.parquet gives them, in its column indexes), `det_relations`, `assignment` (the unique rows of its
    assignment indexes), `export_table`, `relation`, `evidence`, and the where-provenance of each of its columns from
    flows.parquet: `flows`, per column, [(kind, source table, source column, det, source relation)] as `case_flows`
    gives them (none where the export has no flows.parquet), `input_only`, per column, `input_only`'s flag,
    `roots`, per column, `lineage`'s roots, and `capped`, whether an entry of the seen Table at a train example or
    a task-wide entry stopped at the work cap.
    "earlier" holds the earlier Tables of the members
    (seen, before position 0, with rows at some train example) as dicts of `types`, `rows`, `evidence`, `position`,
    `export_table`, `relation`, `table` (its table in the case: the export table, or the grid table's) and
    `positions`; "members" maps each member case with a Table at position 0 to {"p0": its
    "tables" indexes, "earlier": its "earlier" indexes, "label": its labels.jsonl line}. The joined cache holds
    each snapshot as `shared_earlier` gives it. For a case that the `bases` frame cuts, the rows of tables.parquet
    (`names`, `keys`, `export_depth`) and of flows.parquet of the tables numbered below the cut are its base's
    (`encoder.with_base_rows`)."""
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        members, skipped = load_task(export, frames, empty, task, labs)
    pairs = json.load(open(ROOT / "data/tasks" / f"{task}.json"))["train"]
    n_train = len(pairs)
    meta = frames["tables"].get(task, empty["tables"])
    cut = frames["bases"].get(task, empty["bases"]) if "bases" in frames else None
    if cut is not None and len(cut):
        meta = E.with_base_rows(meta, cut)
        flows = None if flows is None else E.with_base_rows(flows, cut)
    meta = {(c, int(t)): (n, k, d) for c, t, n, k, d in
            zip(meta["case"], meta["table"], meta["column_names"], meta["keys"], meta["depth"])}
    labels = {(l["task"], l["case"]): l for l in labs}
    flows_of = {c: g for c, g in flows.groupby("case", sort=False)} if flows is not None else {}
    cache, by_content = {}, {}
    def rows_of(t):
        # a member's copy of a prefix Table shared with other members is another object of equal content: its
        # rows are computed once per content and the one list is given to each copy
        if id(t) not in cache:
            k = table_content(t)
            if k not in by_content:
                by_content[k] = train_rows(t, n_train)
            cache[id(t)] = by_content[k]
        return cache[id(t)]
    tables, earlier_all, mems, det = [], [], {}, {}
    for key, m in members.items():
        ts, recs = m["tables"], m["records"]
        p0 = [i for i, r in enumerate(recs) if r["position"] == 0]
        if not p0:
            continue
        earlier = []
        cf = case_flows(flows_of.get(key[1]))
        only = input_only(cf)
        roots = lineage(cf)
        for t, r in zip(ts, recs):
            if r["position"] < 0 and t.unseen is None:
                rr = rows_of(t)
                if rr is None or not any(len(x) for x in rr):
                    continue
                earlier.append(len(earlier_all))
                earlier_all.append(dict(types=list(t.types), rows=rr, evidence=bool(t.evidence),
                                        position=int(r["position"]), export_table=getattr(t, "export_table", None),
                                        relation=t.relation, positions=list(map(int, t.positions)),
                                        table=E.GRID_TABLES.get(t.relation) if t.evidence else int(t.export_table)))
        idx = []
        for i in p0:
            t = ts[i]
            names, keys, depth = meta.get((key[1], int(t.export_table)), (None, None, None))
            seen = t.unseen is None
            live = ~t.marker
            wide = (unique_rows(t.cells[live & (t.example_kind == 0)])
                    if seen and not t.evidence and t.present[live].all() else None)
            det[(key, i)] = len(tables)
            idx.append(len(tables))
            tables.append(dict(member=key[1], types=list(t.types),
                               names=None if names is None else [str(names[p]) for p in t.positions],
                               positions=list(map(int, t.positions)), unseen=t.unseen,
                               rows=rows_of(t) if seen else None, wide=wide,
                               keys=None if keys is None else [list(map(int, k)) for k in keys],
                               export_depth=None if depth is None else int(depth),
                               det_relations=list(t.det_relations),
                               assignment=np.unique(t.assignment, axis=0) if len(t.assignment) else t.assignment,
                               export_table=int(t.export_table), relation=t.relation, evidence=bool(t.evidence),
                               flows=[cf.get((int(t.export_table), int(p)), []) for p in t.positions],
                               input_only=[only.get((int(t.export_table), int(p)), False) for p in t.positions],
                               roots=[roots.get((int(t.export_table), int(p)), frozenset()) for p in t.positions],
                               capped=bool(seen and (t.unseen_entries or {}).get("an entry stopped") and (
                                   t.marker & ((t.example_kind == 0) | ((t.example_kind == 1) & (t.example < n_train)))).any())))
        mems[key[1]] = dict(p0=idx, earlier=earlier, label=labels[key])
    # the budgets of the value run, then the flags and value_eval.features' inputs
    tabs = {k: m["tables"] for k, m in members.items()}
    E.mark_over_budget(tabs, BUDGET)
    E.mark_over_rows(tabs, MAX_ROWS)
    records = E.value_records(tabs, labels)
    rows = []
    for key, m in members.items():
        for i, (t, r) in enumerate(zip(tabs[key], records[key])):
            if not 0 <= r["position"] < POSITIONS:
                continue
            rows.append(dict(task=key[0], case=key[1], corpus_case=r["group"][1], prefix_tokens=r["group"][2],
                             member=str(r["member"]), gold=r["member"] == "gold", solving=bool(r["solving"]),
                             position=int(r["position"]), index=i, export_table=t.export_table,
                             empty=r["empty"], unseen=r["unseen"], faulted=r["faulted"],
                             n_rows=int((~t.marker).sum()), depth=float(t.depth or 0), step=int(t.step),
                             types=",".join(t.types), det=det.get((key, i))))
    return dict(pairs=pairs, n_train=n_train, rows=rows, tables=tables, earlier=earlier_all, members=mems,
                skipped=skipped)


def shared_earlier(snap):
    """The snapshot with each set of equal earlier Tables (equal types, evidence and rows) held once: "earlier" then
    holds dicts of `types`, `rows` and `evidence`, and each member's "earlier_at" gives, beside its "earlier"
    indexes, the `position`, `export_table` and `relation` of each. A snapshot already shared is given as it is."""
    import hashlib
    if all("earlier_at" in m for m in snap["members"].values()):
        return snap
    seen, shared, by_id = {}, [], {}
    for m in snap["members"].values():
        idx, at = [], []
        for i in m["earlier"]:
            d = snap["earlier"][i]
            got = by_id.get(id(d["rows"]))   # task_snapshot gives equal rows of equal Tables as one list
            if got is not None and got[0] is d["rows"] and got[1] == (d["types"], d["evidence"]):
                k = got[2]
            else:
                h = hashlib.sha1(repr((d["types"], d["evidence"])).encode())
                for r in d["rows"]:
                    h.update(np.ascontiguousarray(r).tobytes()); h.update(b"|%d,%d|" % r.shape)
                k = h.digest()
                by_id[id(d["rows"])] = (d["rows"], (d["types"], d["evidence"]), k)
            if k not in seen:
                seen[k] = len(shared)
                shared.append(dict(types=d["types"], rows=d["rows"], evidence=d["evidence"]))
            idx.append(seen[k])
            at.append(dict(position=d["position"], export_table=d["export_table"], relation=d["relation"],
                           table=d.get("table"), positions=d.get("positions")))
        m["earlier"], m["earlier_at"] = idx, at
    snap["earlier"] = shared
    return snap


def cache_mode(export, seconds, only, workers=1):
    """Writes the snapshot of each task under work/lm/detector-cache/<name>/ (skipping a task whose pickle has the
    task's stamp), stops starting tasks after `seconds`, and, once every task is written, joins them into
    cache_path(export) where it is missing or its stamp is not the join's stamp."""
    import pickle
    start = time.time()
    path = cache_path(export)
    parts_dir = path.with_suffix("")
    parts_dir.mkdir(parents=True, exist_ok=True)
    lines = labels_by_task(export)
    by_task = {t: [json.loads(l) for l in ls] for t, ls in lines.items()}
    stamps = task_stamps(export, lines)
    joined = join_stamp(export, stamps)
    tasks = sorted(only or by_task)
    if not only and join_current(export, joined):
        print(f"{path} holds the join's stamp", flush=True)
        return
    fresh = lambda task: part_stamp(parts_dir / f"{task}.pkl") == stamps[task]
    todo = [t for t in tasks if not fresh(t)]
    print(f"{len(tasks)} tasks, {len(todo)} to cache", flush=True)
    done = 0
    for b in range(0, len(todo), CACHE_BATCH):
        batch = todo[b:b + CACHE_BATCH]
        # the frames hold one batch of tasks: a whole export's index frame alone takes gigabytes in pandas
        frames, empty = {}, {}
        for part in PARTS:
            df = pd.read_parquet(Path(export) / f"{part}.parquet", filters=[("task", "in", batch)])
            empty[part] = df.iloc[:0]
            frames[part] = {k: g for k, g in df.groupby("task", sort=False)}
            del df
        bp = Path(export) / "bases.parquet"
        df = pd.read_parquet(bp, filters=[("task", "in", batch)]) if bp.exists() else E.read_bases(export)
        empty["bases"] = df.iloc[:0]
        frames["bases"] = {k: g for k, g in df.groupby("task", sort=False)}
        del df
        fp = Path(export) / "flows.parquet"
        flows = {k: g for k, g in pd.read_parquet(fp, filters=[("task", "in", batch)]).groupby("task", sort=False)} if fp.exists() else {}
        print(f"batch of {len(batch)} tasks loaded at {time.time() - start:.0f} s", flush=True)
        def one(task):
            t0 = time.time()
            snap = task_snapshot(export, frames, empty, task, by_task[task], flows.get(task))
            snap = shared_earlier(snap)   # each distinct earlier Table once in the task's pickle
            with open(parts_dir / f"{task}.pkl", "wb") as f:
                pickle.dump(stamps[task], f, protocol=5)   # first, so that part_stamp reads it alone
                pickle.dump(snap, f, protocol=5)
            return (f"{task}: {len(snap['rows'])} Tables, {time.time() - t0:.1f} s" +
                    (f"; left out {snap['skipped']}" if snap["skipped"] else ""))
        if workers > 1:
            # forked workers read the frames from this process's memory; a task is written by one of them
            import multiprocessing as mp
            global _CACHE_ONE
            _CACHE_ONE = one
            with mp.get_context("fork").Pool(workers) as pool:
                for line in pool.imap_unordered(_cache_one, batch):
                    print(line, flush=True)
                    done += 1
                    if time.time() - start > seconds:
                        pool.terminate()
                        print(f"stopped after {time.time() - start:.0f} s with {len(todo) - done} tasks to go", flush=True)
                        return
        else:
            for task in batch:
                if time.time() - start > seconds:
                    print(f"stopped after {time.time() - start:.0f} s with {len(todo) - done} tasks to go", flush=True)
                    return
                print(one(task), flush=True)
                done += 1
    if not only and all(fresh(t) for t in by_task):
        snaps = {}
        for t in sorted(by_task):
            with open(parts_dir / f"{t}.pkl", "rb") as f:
                pickle.load(f)
                snaps[t] = shared_earlier(pickle.load(f))
        stamp_path(export).unlink(missing_ok=True)
        with open(path, "wb") as f:
            pickle.dump(dict(stamp=joined, tasks=snaps), f, protocol=5)
        stamp_path(export).write_text(repr(joined))
        print(f"wrote {path}: {len(snaps)} tasks, {path.stat().st_size / 2**20:.0f} MiB", flush=True)
    print(f"{time.time() - start:.0f} s", flush=True)


_CACHE_ONE = None


def _cache_one(task):
    return _CACHE_ONE(task)


def cached_table(d):
    """A Table of the cache as an object with the fields of `detectors` and `rows_hash`."""
    return SimpleNamespace(**d)


def cached_rows(t):
    return t.rows


PER_TABLE = ("rows_hash", "sib_same", "sib_unique")   # the columns of snapshot_frame not given by `input_key`'s inputs


def _feed(h, o):
    """Feeds a digest of o (arrays, dicts, lists, tuples, sets and plain values) to the hash h."""
    if isinstance(o, np.ndarray):
        h.update(b"A%s%s" % (str(o.dtype).encode(), repr(o.shape).encode()))
        h.update(np.ascontiguousarray(o).tobytes())
    elif isinstance(o, dict):
        h.update(b"D%d" % len(o))
        for k in sorted(o, key=repr):
            _feed(h, k); _feed(h, o[k])
    elif isinstance(o, (list, tuple)):
        h.update(b"L%d" % len(o) if isinstance(o, list) else b"T%d" % len(o))
        for x in o:
            _feed(h, x)
    elif isinstance(o, (set, frozenset)):
        h.update(b"S%d" % len(o))
        for x in sorted(map(repr, o)):
            h.update(b"%d:%s" % (len(x), x.encode()))
    else:
        x = repr(o)
        h.update(b"V%d:%s" % (len(x), x.encode()))


def input_key(t, m, asg, r):
    """A digest of all that snapshot_frame reads to compute the columns of Table t (a "tables" entry) other than
    PER_TABLE: t's types, unseen, rows, capped, flows, export_table and roots; its member m's earlier Tables (their
    indexes in the shared "earlier") and "earlier_at" entries; the member's `assignments` asg; and the flags unseen
    and faulted of its row r."""
    import hashlib
    h = hashlib.sha1()
    for f in ("types", "unseen", "rows", "capped", "flows", "export_table", "roots"):
        _feed(h, t.get(f))
    _feed(h, list(m["earlier"])); _feed(h, m.get("earlier_at"))
    _feed(h, asg); _feed(h, (r["unseen"], r["faulted"]))
    return h.digest()


def snapshot_frame(snap):
    """The rows of one task's parquet from its snapshot: the detectors of each Table at position 0. A Table whose
    `input_key` is that of a Table computed before in the task takes that Table's columns, less PER_TABLE."""
    pairs, n_train, tables = snap["pairs"], snap["n_train"], snap["tables"]
    _COLSETS.clear(); _CANON.clear(); _EARLIER_VALUES.clear(); _VALUE_SETS.clear(); _OBJECTS.clear(); _PROJ.clear()
    _MDL.clear(); _PAIR_SETS.clear()
    earlier_of, asg_of, earlier_at = {}, {}, {}
    def earlier(i):
        if i not in earlier_of:
            d = snap["earlier"][i]
            rr = d["rows"]
            earlier_of[i] = (d["types"], rr, d["evidence"],
                             keyed_rows(rr) if max(len(x) for x in rr) <= SET_ROWS else None,
                             np.array([len(x) for x in rr], float))
        return earlier_of[i]
    hashes = {i: rows_hash(cached_table(d), cached_rows) for i, d in enumerate(tables)}
    sib = sibling_contrast(snap, hashes)
    out, done = [], {}
    for r in snap["rows"]:
        row = {k: v for k, v in r.items() if k != "det"}
        if r["det"] is not None:
            t = cached_table(tables[r["det"]])
            m = snap["members"][t.member]
            if t.member not in asg_of:
                asg_of[t.member] = assignments([tables[i]["rows"] if tables[i]["unseen"] is None else None
                                                for i in m["p0"]])
            key = input_key(tables[r["det"]], m, asg_of[t.member], r)
            first = done.get(key)
            if first is not None:
                written, got = first
                row = {k: got[k] if k in written else row[k] for k in got}
                row["rows_hash"] = hashes[r["det"]]
                row["sib_same"], row["sib_unique"] = sib[r["det"]]
                out.append(row)
                continue
            before = dict(row)
            if t.member not in earlier_at:
                earlier_at[t.member] = [earlier(i) for i in m["earlier"]]
            own = detectors(t, row, earlier_at[t.member], asg_of[t.member], pairs, n_train, cached_rows)
            row.update(own)
            row["rows_hash"] = rows_hash(t, cached_rows)
            row["sib_same"], row["sib_unique"] = sib[r["det"]]
            rows = cached_rows(t) if t.unseen is None else None
            # the degeneracy tests compare against the earlier tables less ex_output: a table equal to the train
            # output is the solution, not a restatement; f_output marks it
            at_all = m.get("earlier_at", [{}] * len(m["earlier"]))
            keep = [i for i, a in enumerate(at_all) if a.get("relation") != "ex_output"]
            earlier_src = [earlier_at[t.member][i] for i in keep]
            at_src = [at_all[i] for i in keep]
            whole = bool(own.get("f_redundant"))
            if whole and len(keep) < len(at_all):
                whole = bool(detectors(t, dict(row), earlier_src, asg_of[t.member], pairs, n_train, cached_rows).get("f_redundant"))
            row["f_output"] = float(bool(own.get("f_redundant")) and not whole)
            row["lineage_independent"] = float(lineage_independent(getattr(t, "roots", None) or []))
            # new_values leaves out ex_output, as the degeneracy tests do
            if rows is not None and any(len(x) for x in rows):
                row["new_values"] = own["new_values"] = new_values(list(t.types), spans(list(t.types)), rows, earlier_src, n_train)
                row["mdl_gain"], row["mdl_share"] = own["mdl_gain"], own["mdl_share"] = description_gain(
                    list(t.types), spans(list(t.types)), rows, earlier_src, n_train)
            row.pop("f_independent", None)   # joined from the marks file at measure (`join_marks`)
            fv, per = factor_values(t, rows, row, earlier_src, at_src, asg_of[t.member], pairs, n_train, whole)
            row.update(fv)
            row.update(aggregate(fv, own, per))
            done[key] = ({k for k in row if k not in before or row[k] is not before[k]}, row)
        out.append(row)
    _COLSETS.clear(); _CANON.clear(); _EARLIER_VALUES.clear(); _VALUE_SETS.clear(); _OBJECTS.clear(); _PROJ.clear()
    _MDL.clear(); _PAIR_SETS.clear()
    return out


_STAMPS = None


def task_columns(task):
    """The rows of the task's parquet (`snapshot_frame`) from its per-task pickle of the cache, refusing one whose
    stamp is not the task's: the row count, the columns in the order the rows first give them, and, per column, a
    pickle of its values (NaN where a row does not give the column)."""
    import pickle
    with open(cache_path(_STAMPS["export"]).with_suffix("") / f"{task}.pkl", "rb") as f:
        if pickle.load(f) != _STAMPS["tasks"][task]:
            raise RuntimeError(f"stale cache pickle of {task}: run `detectors.py cache --export {_STAMPS['export']}` again")
        rows = snapshot_frame(pickle.load(f))
    names = list(dict.fromkeys(k for r in rows for k in r))
    return len(rows), names, {c: pickle.dumps([r.get(c, np.nan) for r in rows], protocol=5) for c in names}


def compute_mode(export, only, parquet, workers=1):
    """The detectors of every task of the export's cache, into `parquet`. Each task is read from its per-task pickle
    and its rows kept as pickled columns: the whole cache, or every row as a dict, takes gigabytes, and a forked
    worker copies the pages of this process's objects that it touches."""
    import gc, pickle
    global _STAMPS
    start = time.time()
    stamps = task_stamps(export, labels_by_task(export))
    want = join_stamp(export, stamps)
    if not join_current(export, want):
        sys.exit(f"no cache at {cache_path(export)} with the export's stamp {want}; "
                 f"run `detectors.py cache --export {export}`")
    tasks = sorted(only or stamps)
    _STAMPS = dict(export=export, tasks=stamps)
    # the larger tasks first
    parts_dir = cache_path(export).with_suffix("")
    order = sorted(tasks, key=lambda t: -os.path.getsize(parts_dir / f"{t}.pkl"))
    if workers > 1:
        import multiprocessing as mp
        gc.freeze()   # a worker's collections then leave this process's objects, and their pages, unwritten
        with mp.get_context("fork").Pool(workers) as pool:
            got = dict(zip(order, pool.map(task_columns, order, chunksize=1)))
        gc.unfreeze()
    else:
        got = {t: task_columns(t) for t in order}
    parts = [got[t] for t in tasks]
    # pd.DataFrame of the rows as dicts infers each column's dtype from that column alone: the same call, one
    # column at a time, gives the frame of all the rows at once
    names = list(dict.fromkeys(c for _, ns, _ in parts for c in ns))
    cols = {}
    for c in names:
        values = [v for n, _, cs in parts for v in (pickle.loads(cs[c]) if c in cs else [np.nan] * n)]
        cols[c] = pd.DataFrame([{c: v} for v in values])[c]
    df = pd.DataFrame(cols)
    df.to_parquet(parquet)
    print(f"wrote {parquet}: {len(df)} Tables of {len(tasks)} tasks, {time.time() - start:.1f} s", flush=True)
    return df


# ------------------------------------------------------------------ measure

STUB_COLUMNS = ["types", "n_rows", "depth", "step", "empty", "unseen", "position"]   # what Stub and value_eval.features read of a row


class Stub:
    """The fields of a Table that value_eval.features reads."""
    def __init__(self, r):
        self.types = r["types"].split(",") if r["types"] else []
        self.marker = np.zeros(int(r["n_rows"]), bool)
        self.depth, self.step = r["depth"], int(r["step"])


def members_of(df, keep_all=False, stubs=False):
    """[{"group", "records", "solving", "tables"?, "rows", "task"}] per member case, in the order of the cases' first
    Tables in df: "records" and "rows" (df index labels) list its Tables in df's order."""
    codes, _ = pd.factorize(df["case"], sort=False)
    order = np.argsort(codes, kind="stable")
    bounds = np.flatnonzero(np.diff(codes[order])) + 1
    col = lambda c: df[c].tolist()
    pos, gold, member, solving = col("position"), col("gold"), col("member"), col("solving")
    empty, unseen, faulted = col("empty"), col("unseen"), col("faulted")
    task, corpus, prefix, index = col("task"), col("corpus_case"), col("prefix_tokens"), df.index.to_numpy()
    if stubs:
        types, n_rows, depth, step = col("types"), col("n_rows"), col("depth"), col("step")
    out = []
    for g in np.split(order, bounds) if len(order) else []:
        g = g.tolist()
        recs = [dict(position=int(pos[i]), member="gold" if gold[i] else member[i], solving=bool(solving[i]),
                     consistent=None, unjudged=True,
                     empty=False if keep_all else bool(empty[i]), unseen=False if keep_all else bool(unseen[i]),
                     faulted=False if keep_all else bool(faulted[i])) for i in g]
        i0 = g[0]
        m = dict(group=(task[i0], corpus[i0], int(prefix[i0])), records=recs, solving=bool(solving[i0]),
                 rows=index[g], task=task[i0])
        if stubs:
            m["tables"] = [Stub(dict(types=types[i], n_rows=n_rows[i], depth=depth[i], step=step[i])) for i in g]
        out.append(m)
    return out


def listed_at(m):
    """The places in member m's records of the Tables its list reads (position 0, not excluded), kept in m."""
    if "_listed" not in m:
        m["_listed"] = [k for k, r in enumerate(m["records"]) if r["position"] == 0 and not E.value_excluded(r)]
    return m["_listed"]


def member_scores(members, score):
    """Per member, the float32 values of `score` (a Series on df's index) at its Tables."""
    rows = [m["rows"] for m in members]
    if not rows:
        return []
    v = score.to_numpy(np.float64)[score.index.get_indexer(np.concatenate(rows))].astype(np.float32)
    return np.split(v, np.cumsum([len(r) for r in rows])[:-1])


def metrics(members, score):
    """encoder.value_draw_metrics at position 0 of the per-Table `score` (a Series on df's index), of one draw:
    the same lists, member means (torch's float32 mean), pairs and AUCs, without building a tensor per member."""
    import torch
    by = {}
    for m, z in zip(members, member_scores(members, score)):
        sel = listed_at(m)
        if sel:
            s = z[sel[0]] if len(sel) == 1 else torch.from_numpy(np.ascontiguousarray(z[sel])).mean().item()
            by.setdefault(m["group"], []).append((bool(m["records"][sel[0]]["solving"]), np.float32(s),
                                                  m["records"][0]["member"] == "gold"))
    lists = []
    for xs in by.values():
        y = np.array([x[0] for x in xs]); sc = np.array([x[1] for x in xs], np.float32)
        lists.append((y, sc, np.array([x[2] for x in xs]), bool(y.any() and not y.all())))
    def pairs(sampled):
        right, n = 0.0, 0
        for y, sc, g, ranked in lists:
            if ranked:
                if sampled:
                    sc, y = sc[~g], y[~g]
                d = sc[y][:, None] - sc[~y][None, :]
                right += float((d > 0).sum() + 0.5 * (d == 0).sum())
                n += d.size
        return right, n
    def auc(sampled):
        aucs = []
        for y, sc, g, _ in lists:
            if sampled:
                sc, y = sc[~g], y[~g]
            a = E.auc(sc, y)
            if a is not None:
                aucs.append(a)
        return float(np.mean(aucs)) if aucs else None
    right, n = pairs(False)
    right_s, n_s = pairs(True)
    out = dict(pair_acc=right / n if n else None, pair_acc_sampled=right_s / n_s if n_s else None, auc=auc(False),
               auc_sampled=auc(True), lists=len(lists), ranked_lists=sum(l[3] for l in lists), pairs=n,
               pairs_sampled=n_s, draws=1)
    for k in E.VALUE_DRAW_METRICS:
        out[f"{k}_min"] = out[f"{k}_max"] = out[k]
    return out


def listed(df, members):
    """The df index of the Tables the lists read (position 0, not excluded under the members' flags)."""
    idx = []
    for m in members:
        idx += m["rows"][listed_at(m)].tolist()
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


def fit_score(df, X, train_members):
    """The scores of every Table of df from fit_logistic on the rows X, trained on the listed Tables of
    `train_members`, a missing value taking the training mean; with the training loss, weights and Table count."""
    ti = tr_idx_pos(df, listed(df, train_members))
    mu = np.nanmean(X[ti], 0)
    mu = np.where(np.isnan(mu), 0.0, mu)
    Xf = np.where(np.isnan(X), mu, X)
    pred, loss, w = fit_logistic(Xf[ti], df["solving"].to_numpy(float)[ti])
    return pd.Series(pred(Xf), index=df.index), loss, w, len(ti)


def same_key_pairs(df, score, members, key):
    """Over the lists of `members`, the pairs of a solving and a non-solving member whose position-0 Tables have the
    same value of the column `key`: (the pairs in which the solving one scores higher, a tie one half; the pairs)."""
    by = {}
    rows = [m["rows"] for m in members]
    if not rows:
        return 0.0, 0
    at = np.concatenate(rows)
    sv = np.split(score.to_numpy(np.float64)[score.index.get_indexer(at)], np.cumsum([len(r) for r in rows])[:-1])
    kv = np.split(df[key].to_numpy()[df.index.get_indexer(at)], np.cumsum([len(r) for r in rows])[:-1])
    for m, z, kz in zip(members, sv, kv):
        sel = listed_at(m)
        if sel:
            mean = float(z[sel[0]]) if len(sel) == 1 else float(pd.Series(z[sel]).mean())
            by.setdefault(m["group"], []).append((m["solving"], mean, kz[sel[0]]))
    right, n = 0.0, 0
    for xs in by.values():
        for a in xs:
            for b in xs:
                if a[0] and not b[0] and a[2] == b[2]:
                    n += 1
                    right += (a[1] > b[1]) + 0.5 * (a[1] == b[1])
    return right, n


def show(x):
    return "   -" if x is None else f"{x:.3f}"


def row_line(name, r):
    return (f"{name:<28}{show(r['pair_acc']):>8}{show(r['auc']):>8}{show(r['pair_acc_sampled']):>9}"
            f"{show(r['auc_sampled']):>9}{r['pairs']:>7}{r['ranked_lists']:>7}{r['lists']:>7}")


HEAD = f"{'score':<28}{'pairs':>8}{'AUC':>8}{'pairs s':>9}{'AUC s':>9}{'n pair':>7}{'ranked':>7}{'lists':>7}"


def split_of(data):
    """The held-out and the training tasks of the data export `data` (its cases.npz)."""
    z = np.load(Path(data) / "cases.npz")
    held_tasks = {t for t, h in zip(z["task"].tolist(), z["heldout"].tolist()) if h}
    train_tasks = {t for t, h in zip(z["task"].tolist(), z["heldout"].tolist()) if not h}
    return held_tasks, train_tasks


AGGREGATE = "max"   # the aggregate over the surviving factors that the graded detectors take; None: the Table's own


def with_factors(df):
    """df with each graded detector taken from its AGGREGATE column where the frame has one, and `n_columns`, the
    surviving factors' total width (`factor_width`) where the frame gives it, else the count of column types."""
    if AGGREGATE is not None:
        for g in GRADED_FACTOR:
            c = f"{g}@{AGGREGATE}"
            if c in df:
                df[g] = df[c].astype(float)
    n = df["types"].map(lambda t: len(t.split(",")) if t else 0).astype(float)
    if "factor_width" in df and AGGREGATE is not None:
        n = df["factor_width"].astype(float).fillna(n)
    df["n_columns"] = n
    return df


def measure_frame(df, held_tasks, train_tasks):
    """df's Tables of the split's tasks, with the detectors as floats (missing where df has no column for one) and
    `n_columns` (`with_factors`)."""
    df = df[df["task"].isin(held_tasks | train_tasks)].copy()
    df = with_factors(df)
    for col in DETECTORS:
        df[col] = df[col].astype(float) if col in df else np.nan   # a parquet older than the detector lacks it
    return df


def table_degenerate(p0):
    """Per Table of the position-0 frame p0: whether it fires one of FILTERS."""
    return p0[FILTERS].fillna(0).astype(bool).any(axis=1)


def member_degenerate(p0):
    """{case: whether its first table is degenerate}: every Table of the member at position 0 (one per DET
    assignment) fires one of FILTERS."""
    return table_degenerate(p0).groupby(p0["case"]).all()


def viable(df):
    """The variant `viable`: df less every member whose first table is degenerate (`member_degenerate`: every Table
    of it at position 0 fires one of FILTERS), the gold continuation included, less every member of a branch point
    whose gold is so dropped, so its list is not ranked, and less the Tables at position 0 that fire a filter in the
    members kept, so a member's score is over its surviving assignments' Tables. Gives the frame and the counts:
    {filter: (gold members, other members) dropped with some Table firing it}, the members dropped (gold, other) and
    the branch points whose gold is dropped."""
    p0 = df[df["position"] == 0]
    deg = member_degenerate(p0)
    out = set(deg.index[deg])
    fires = p0[p0["case"].isin(out)].groupby("case")[FILTERS].max().fillna(0).astype(bool)
    gold = fires.index.str.endswith("__gold")
    counts = {f: (int(fires.loc[gold, f].sum()), int(fires.loc[~gold, f].sum())) for f in FILTERS}
    point = lambda c: c.rsplit("__", 1)[0]
    lost = {point(c) for c in out if c.endswith("__gold")}
    keep = ~df["case"].isin(out) & ~df["case"].map(point).isin(lost)
    bad = pd.Series(False, index=df.index)
    bad.loc[p0.index] = table_degenerate(p0)
    keep &= ~bad
    n_gold = sum(c.endswith("__gold") for c in out)
    return df[keep], dict(filters=counts, dropped=(n_gold, len(out) - n_gold), lost_gold=len(lost))


HEADLINE = ["-(sum of filters)", "trivial features", "column count", "logistic, fit on LM", "logistic, 5-fold"]


def headline(df, held_tasks, train_tasks, extra=()):
    """The rows of `measure` that the loop reports, variant graded: {name: metrics} for HEADLINE and each detector of
    `extra` (its sign learned on the training branch points), with the same numbers as the full table; the 5-fold
    row holds the means over the folds of pair_acc and auc."""
    import contextlib, io
    import value_eval as VE
    df = measure_frame(df, held_tasks, train_tasks)
    ms = members_of(df[df["position"] == 0])
    train = [m for m in ms if m["task"] in train_tasks]
    held = [m for m in ms if m["task"] in held_tasks]
    tr_idx = listed(df, train)
    res = {"-(sum of filters)": metrics(held, -df[FILTERS].sum(axis=1))}
    for g in extra:
        med = float(np.nanmedian(df.loc[tr_idx, g])) if df.loc[tr_idx, g].notna().any() else 0.0
        sc = df[g].fillna(med)
        tr = metrics(train, sc)["pair_acc"]
        sign = -1.0 if tr is not None and tr < 0.5 else 1.0
        res[("-" if sign < 0 else "+") + g] = metrics(held, sign * sc)
    sm = members_of(df, keep_all=False, stubs=True)
    with contextlib.redirect_stdout(io.StringIO()):
        sc = VE.logistic([m for m in sm if m["task"] in train_tasks], [m for m in sm if m["task"] in held_tasks],
                         1, 300, 0, "solving")
    res["trivial features"] = E.value_draw_metrics([m for m in sm if m["task"] in held_tasks], [sc], 1,
                                                   label="solving")
    X = df[SCORED].to_numpy(float)
    res["column count"] = metrics(held, fit_score(df, df[["n_columns"]].to_numpy(float), train)[0])
    res["logistic, fit on LM"] = metrics(held, fit_score(df, X, train)[0])
    tasks = sorted(set(df["task"]))
    random.Random(0).shuffle(tasks)
    accs = defaultdict(list)
    for fold in [set(tasks[k::5]) for k in range(5)]:
        r = metrics([m for m in ms if m["task"] in fold], fit_score(df, X, [m for m in ms if m["task"] not in fold])[0])
        for k in ("pair_acc", "auc"):
            if r[k] is not None:
                accs[k].append(r[k])
    res["logistic, 5-fold"] = {k: float(np.mean(accs[k])) if accs[k] else None for k in ("pair_acc", "auc")}
    return res


def measure_mode(data, out, parquet, export, quick=False, extra=()):
    start = time.time()
    import contextlib, io
    import value_eval as VE
    df = read_marked(parquet, export)
    held_tasks, train_tasks = split_of(data)
    if quick:
        res = headline(df, held_tasks, train_tasks, extra)
        print(f"{'score':<28}{'pairs':>8}{'AUC':>8}")
        for k, r in res.items():
            print(f"{k:<28}{show(r['pair_acc']):>8}{show(r['auc']):>8}")
        print(f"{time.time() - start:.0f} s", file=sys.stderr)
        return res
    df = df[df["task"].isin(held_tasks | train_tasks)].copy()
    p0 = df["position"] == 0
    lines = ["# Detectors of the first table after the branch", "",
             f"Rollout export {export}; split by {data}: {len(held_tasks & set(df['task']))} held-out "
             f"tasks, {len(train_tasks & set(df['task']))} training tasks.",
             "Columns: pairwise ranking accuracy and AUC within a list (encoder.value_draw_metrics), the same over "
             "sampled continuations alone (\"s\", none where no sampled continuation of a list solves), and the counts "
             "of pairs, ranked lists and lists.", ""]
    df = with_factors(df)
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
    TF = np.array([VE.features(Stub(r), r) for r in df[STUB_COLUMNS].to_dict("records")], float)
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
        # the logistic on every detector, on the column count alone, and on every detector less COLUMN_STRUCTURE
        feats = SCORED
        X = df[feats].to_numpy(float)
        Xc = df[["n_columns"]].to_numpy(float)
        Xs = df[[f for f in feats if f not in COLUMN_STRUCTURE]].to_numpy(float)
        score, loss, w, n_tr = fit_score(df, X, v["train"])
        res["logistic"] = metrics(v["held"], score)
        lines.append(row_line("logistic on every detector", res["logistic"]) +
                     f"  ({n_tr} training Tables, final training loss {loss:.3f})")
        right, n = same_key_pairs(df, score, v["held"], "n_columns")
        res["same columns"] = (right / n if n else None, n)
        lines.append(f"{'  its pairs of one column count':<28}{show(res['same columns'][0]):>8}{'':>33}{n:>7}")
        res["columns"] = metrics(v["held"], fit_score(df, Xc, v["train"])[0])
        lines.append(row_line("logistic on column count", res["columns"]))
        res["less structure"] = metrics(v["held"], fit_score(df, Xs, v["train"])[0])
        lines.append(row_line("logistic, less col. structure", res["less structure"]))
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
        same_r, same_n = 0.0, 0
        for k, fold in enumerate(folds):
            trm = [m for m in v["all"] if m["task"] not in fold]
            tem = [m for m in v["all"] if m["task"] in fold]
            ti = listed(df, trm)
            score = fit_score(df, X, trm)[0]
            r = metrics(tem, score)
            sr, sn = same_key_pairs(df, score, tem, "n_columns")
            same_r += sr; same_n += sn
            for key, Xo in (("columns", Xc), ("less structure", Xs)):
                ro = metrics(tem, fit_score(df, Xo, trm)[0])
                for m_ in ("pair_acc", "auc"):
                    if ro[m_] is not None:
                        accs[f"{key} {m_}"].append(ro[m_])
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
        lines.append(f"{'mean, column count alone':<28}{mean('columns pair_acc'):>8}{mean('columns auc'):>8}")
        lines.append(f"{'mean, less col. structure':<28}{mean('less structure pair_acc'):>8}{mean('less structure auc'):>8}")
        res["cv same columns"] = (same_r / same_n if same_n else None, same_n)
        res["cv"] = {k: float(np.mean(x)) for k, x in accs.items() if x}
        lines.append(f"{'pooled, one column count':<28}{show(res['cv same columns'][0]):>8}{'':>33}{same_n:>7}")
        lines.append("")
        results[name] = res
    gl = df.loc[listed(df, variants["graded"]["all"])]
    g = results["graded"]
    qual = ["## Qualifications", "",
            "- No sampled continuation of a held-out task solves, so every held-out pair is the gold continuation's "
            "table against a sampled one's: the metric measures how well a score tells the gold writer's table from "
            "the LM's, not a solving step from a failing one.",
            f"- Gold tables have more columns than sampled ones ({gl[gl['gold']]['n_columns'].mean():.2f} against "
            f"{gl[~gl['gold']]['n_columns'].mean():.2f}, variant graded, every task). The column count alone scores "
            f"{show(g['columns']['pair_acc'])} held out and {show(g['cv'].get('columns pair_acc'))} in the 5-fold run; "
            f"the logistic on every detector scores {show(g['cv same columns'][0])} in the 5-fold run over its "
            f"{g['cv same columns'][1]} pairs of one column count. Without the column-structure detectors "
            f"({', '.join(COLUMN_STRUCTURE)}) it scores {show(g['less structure']['pair_acc'])} held out and "
            f"{show(g['cv'].get('less structure pair_acc'))} in the 5-fold run.",
            f"- The trivial baseline at positions 4 scores {show(g['trivial@4']['pair_acc'])} over "
            f"{g['trivial@4']['pairs']} pairs, the lists of the value run's 0.651; every depth is 0 here, since no "
            f"flows are read, which accounts for the difference. At positions 1, the lists the detectors are measured "
            f"on, it scores {show(g['trivial@1']['pair_acc'])}.", ""]
    lines[5:5] = qual
    lines.append("A signal marked * is one of the signals added from work/lm/data-study/marks.md (detectors.py's docstring). A graded signal's sign (+ or -) "
                 "is the one that ranks better on the training branch points. f_product is tested on Tables of at "
                 f"most {PRODUCT_ROWS} rows at each train example and {PRODUCT_COLUMNS} columns other than Example.")
    lines += ["", "## Marks of work/lm/data-study/marks.md with no detector", ""] + [f"- {x}" for x in NOT_COMPUTED]
    Path(out).write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"{time.time() - start:.0f} s", file=sys.stderr)


def tr_idx_pos(df, idx):
    return df.index.get_indexer(idx)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", choices=["cache", "compute", "measure"])
    ap.add_argument("path", nargs="?", help="cache, compute: the rollout export (or --export); measure: the data export of the split")
    ap.add_argument("--export", help="the rollout export (default work/lm/rollouts-s2/export)")
    ap.add_argument("--parquet", default=str(ROOT / "work/lm/data-study/detectors.parquet"))
    ap.add_argument("--seconds", type=float, default=840)
    ap.add_argument("--tasks", nargs="*")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--quick", action="store_true", help="measure: print only the headline rows (HEADLINE)")
    ap.add_argument("--show", nargs="*", default=[], help="measure --quick: detectors whose own rows to print too")
    ap.add_argument("--out", default=str(ROOT / "work/lm/data-study/detectors.out"))
    a = ap.parse_args()
    export = a.export or (a.path if a.mode != "measure" else None) or "work/lm/rollouts-s2/export"
    if a.mode == "cache":
        cache_mode(export, a.seconds, a.tasks, a.workers)
    elif a.mode == "compute":
        compute_mode(export, a.tasks, a.parquet, a.workers)
    else:
        if a.path is None:
            ap.error("measure: the data export of the split")
        measure_mode(a.path, a.out, a.parquet, export, a.quick, a.show)


if __name__ == "__main__":
    main()
