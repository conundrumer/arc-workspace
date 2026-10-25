"""The feature encoder of docs/feature-encoder.md, first version: it turns the relation tables of a decode into
K feature vectors per table, which enter the program language model's sequence after the token whose step gives
the table.

Positions. A row token, and each pooled vector, is an array [21, c]: position 0 holds the invariant channels,
positions 1..4 the edge channels (edges top, bottom, left, right, the order of a Box's margins), and positions
5 + 4i + j the pairwise channel of the edge pair (i, j). A D4 element g, as the edge each edge goes to, moves
position 1 + e to 1 + g(e) and position (i, j) to (g(i), g(j)); on a 4 x 4 matrix M[i, j] that is P_g M P_g^T.
Every linear map is a sum over the orbits of D4 on pairs of positions (68 orbits), so it commutes with that
action; norms and nonlinearities act per position.

Tables. `load_tables` reads a tables export (engine/arclog-py/tables_export.py) into per-case lists of `Table`, the relation
tables in stream order, and caches them in a pickle. The evidence tables `ex_input` and `ex_output` are built from
the task file where the export holds none, and stand first, after the start token.
"""
import bisect, json, math, os, pickle, re
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.checkpoint import checkpoint

# ---------------------------------------------------------------- D4

T, B, L, R = 0, 1, 2, 3
CLOCKWISE = {T: R, R: B, B: L, L: T}
ELEMENTS = {   # the edge each edge (t, b, l, r) goes to, as engine/arclog/src/algebra/geometry.rs gives
    "D4_ID": (T, B, L, R), "D4_CW": (R, L, T, B), "D4_HT": (B, T, R, L), "D4_CC": (L, R, B, T),
    "D4_LR": (T, B, R, L), "D4_TB": (B, T, L, R), "D4_DG": (L, R, T, B), "D4_AD": (R, L, B, T)}
DIRECTIONS = {"DIR_T": {T}, "DIR_B": {B}, "DIR_L": {L}, "DIR_R": {R},
              "DIAG_TL": {T, L}, "DIAG_TR": {T, R}, "DIAG_BL": {B, L}, "DIAG_BR": {B, R}}
AXES = {"AXIS_V": ("DIR_T", "DIR_B"), "AXIS_H": ("DIR_L", "DIR_R"),
        "DAXIS_DG": ("DIAG_TL", "DIAG_BR"), "DAXIS_AD": ("DIAG_TR", "DIAG_BL")}
SENSES = {"SENSE_CW": True, "SENSE_CC": False}
SUBGROUPS = {"SYM_1": [], "SYM_LR": ["D4_LR"], "SYM_TB": ["D4_TB"], "SYM_HT": ["D4_HT"], "SYM_DG": ["D4_DG"],
             "SYM_AD": ["D4_AD"], "SYM_BOX": ["D4_LR", "D4_TB"], "SYM_X": ["D4_DG", "D4_AD"], "SYM_C4": ["D4_CW"],
             "SYM_D4": ["D4_CW", "D4_LR"]}


def after(g, f):
    """The element that applies f, then g."""
    return tuple(g[f[e]] for e in range(4))


def inverse(g):
    inv = [0] * 4
    for e in range(4):
        inv[g[e]] = e
    return tuple(inv)


def is_rotation(g):
    return g[CLOCKWISE[T]] == CLOCKWISE[g[T]]


def subgroup(gens):
    members = {ELEMENTS["D4_ID"]}
    grown = True
    while grown:
        grown = False
        for x in list(members):
            for name in gens:
                y = after(ELEMENTS[name], x)
                if y not in members:
                    members.add(y); grown = True
    return frozenset(members)


def meaning(name):
    """What an orientation constant stands for, in a form that D4 acts on: ("dir", edges), ("axis", the two
    directions' edge sets), ("elem", element), ("sense", clockwise) or ("sub", members)."""
    if name in DIRECTIONS:
        return ("dir", frozenset(DIRECTIONS[name]))
    if name in AXES:
        return ("axis", frozenset(frozenset(DIRECTIONS[d]) for d in AXES[name]))
    if name in ELEMENTS:
        return ("elem", ELEMENTS[name])
    if name in SENSES:
        return ("sense", SENSES[name])
    return ("sub", subgroup(SUBGROUPS[name]))


def meaning_under(m, g):
    """The image of the meaning m under the D4 element g, as geometry.rs's `Meaning::under` gives."""
    conj = lambda x: after(after(g, x), inverse(g))
    kind, v = m
    if kind == "dir":
        return ("dir", frozenset(g[e] for e in v))
    if kind == "axis":
        return ("axis", frozenset(frozenset(g[e] for e in d) for d in v))
    if kind == "elem":
        return ("elem", conj(v))
    if kind == "sense":
        return ("sense", v == is_rotation(g))
    return ("sub", frozenset(conj(x) for x in v))


def perm_matrix(x):
    """M[i, j] = 1 where x takes edge j to edge i."""
    m = np.zeros((4, 4), np.float32)
    for j in range(4):
        m[x[j], j] = 1.0
    return m


def orientation_features(name):
    """The edge indicator (4) and two pairwise matrices (4 x 4) of an orientation constant: a Dir or DiagDir and
    an Axis as an indicator on their edges, a DiagAxis as the matrix of its reflection, a D4 element (and a Pose)
    as its matrix, a Sense as the matrix of the quarter turn in that sense, each in the first matrix; a subgroup
    as the sum of its rotations' matrices in the first and of its reflections' in the second, which conjugation
    keeps apart."""
    edge, pair, ref = np.zeros(4, np.float32), np.zeros((4, 4), np.float32), np.zeros((4, 4), np.float32)
    kind, v = meaning(name)
    if kind == "dir":
        edge[list(v)] = 1.0
    elif kind == "axis" and all(len(d) == 1 for d in v):
        edge[[e for d in v for e in d]] = 1.0
    elif kind == "axis":   # a DiagAxis: the reflection that fixes each of its directions
        (r,) = [x for x in ELEMENTS.values() if x != ELEMENTS["D4_ID"]
                and all(frozenset(x[e] for e in d) == d for d in v)]
        pair = perm_matrix(r)
    elif kind == "elem":
        pair = perm_matrix(v)
    elif kind == "sense":
        pair = perm_matrix(ELEMENTS["D4_CW" if v else "D4_CC"])
    else:
        pair = sum((perm_matrix(x) for x in v if is_rotation(x)), np.zeros((4, 4), np.float32))
        ref = sum((perm_matrix(x) for x in v if not is_rotation(x)), np.zeros((4, 4), np.float32))
    return edge, pair, ref


NPOS = 21


def act_position(g, p):
    if p == 0:
        return 0
    if p < 5:
        return 1 + g[p - 1]
    i, j = divmod(p - 5, 4)
    return 5 + 4 * g[i] + g[j]


def orbits(points, act):
    """The orbit index of each point under the eight elements, by first appearance."""
    index = {}
    for x in points:
        if x in index:
            continue
        k = len(set(index.values()))
        for g in ELEMENTS.values():
            index.setdefault(act(g, x), k)
    return index


POSITION_ORBIT = orbits(range(NPOS), act_position)                      # 5 orbits
PAIR_ORBIT = orbits([(p, q) for p in range(NPOS) for q in range(NPOS)],
                    lambda g, pq: (act_position(g, pq[0]), act_position(g, pq[1])))   # 68 orbits
N_POS_ORBITS, N_PAIR_ORBITS = len(set(POSITION_ORBIT.values())), len(set(PAIR_ORBIT.values()))


def position_permutation(g):
    """perm[p] = the position p goes to under g."""
    return [act_position(g, p) for p in range(NPOS)]


# ---------------------------------------------------------------- tables

ORIENTATION_TYPES = {"Dir", "DiagDir", "Dir8", "Axis", "DiagAxis", "Axis4", "D4", "C4", "Sym", "Sense", "Pose"}
TYPE_NAMES = ["Number", "Color", "Example", "Ident", "Box"] + sorted(ORIENTATION_TYPES)


def type_name(t):
    return "Pose" if t.startswith("Pose") else t


def width(t):
    return 4 if t == "Box" else 1


class Table:
    """A relation table of a case: `step`, the index in the encoded sequence of the step after which its vectors
    enter (stream token index + 1, and 0 for the evidence tables); `relation`, its slot, or the fact relation's
    name; `positions`, the column position of each column it keeps (Unit columns dropped); `types`; and its rows:
    `cells` [n, width] int32, `present` [n, columns] bool (a projection row holds a subset of the columns),
    `example` [n] (the example's index, train then test, or -1 for a task-wide entry), `example_kind` [n]
    (0 task, 1 train, 2 test), `assignment` [n, dets] (the index of each DET's value at the entry's assignment
    among the case's DET values, or -1), `model` [n] and `entry` [n] (the row's entry, one example at one
    assignment and model; for an evidence table, its example), `part` [n] (the row's projection among those of its
    entry, 0 for an entry's own rows) and `marker` [n] bool. An entry the encoder cannot see (undefined, a fault,
    no entries, stopped, a projection with no rows, or over the budget) holds one marker row: no columns, its
    example, kind, assignment and model, and the unseen vector. `unseen_entries` counts those entries by reason.
    `unseen` gives the reason the encoder cannot see the whole table (its projection search stopped, it faults, or
    every entry is unseen), which then has no rows; `largest` is the most rows of one entry, or of one projection
    at an entry. `det_relations` gives the relation of each DET that the table's entries are assigned, as the
    export spells it ("slot <relation>"), and is empty for an evidence table. An export table whose entries hold
    several assignments gives one Table per assignment, each with that assignment's entries over every example and
    model; the Tables of one export table share `step`, `relation` and `export_table`, and stand next to each other
    (`table_groups`).

    From an export that gives the column-level provenance (`flows.parquet`), a relation table also holds `depth`, its
    stratum; `keys`, its candidate keys as lists of column indexes; `output_position` and `output_color`, the columns
    that map to Position and Color of ex_output on the program's output relation, -1 elsewhere; and `flows`, one row
    per source of a column, [m, 5] int32: column, kind (`FLOW_KINDS`), source table (the export table, 0 for ex_input
    and 1 for ex_output, -1 where the case holds none), source column (-1 where none, -2 for the example of the
    source's entry) and DET (the place in `det_relations`, -1 where none). Every column index is one of this loader's
    columns (Unit columns dropped), and a flow of a dropped column is left out. The Tables of one export table share
    these. ex_output holds `color_dependent`: whether the output relation's Color column reaches a DET or ex_output
    through the flows (`color_dependence`), None where the case gives no output relation. Without the export's
    provenance, each of these holds its class default."""
    depth, keys, flows, output_position, output_color, color_dependent = None, None, None, -1, -1, None

    def __init__(self, **kw):
        kw.pop("_unique", None)   # what `unique` keeps, which a copy builds again
        self.__dict__.update(kw)

    def __getstate__(self):
        return {k: v for k, v in self.__dict__.items() if k != "_unique"}

    @property
    def n(self):
        return len(self.cells)


ROW_FIELDS = ("cells", "present", "example", "example_kind", "assignment", "model", "entry", "part", "marker")


def grid_rows(grids):
    """The rows (example, Position as four margins, color) of each (example, grid)."""
    rows = []
    for e, grid in grids:
        h, w = len(grid), len(grid[0])
        for r in range(h):
            for c in range(w):
                rows.append([e, r, h - 1 - r, c, w - 1 - c, grid[r][c]])
    return np.array(rows, np.int32).reshape(-1, 6)


def evidence_tables(task_json):
    train, test = task_json["train"], task_json["test"]
    out = []
    for name, grids in (("ex_input", [(i, p["input"]) for i, p in enumerate(train + test)]),
                        ("ex_output", [(i, p["output"]) for i, p in enumerate(train)])):
        cells = grid_rows(grids)
        n = len(cells)
        # the cell column is a Position, which the engine types as a Box
        out.append(Table(step=0, relation=name, evidence=True, positions=[0, 1, 2], types=["Example", "Box", "Color"],
                         cells=cells, present=np.ones((n, 3), bool), example=np.full(n, -1, np.int16),
                         example_kind=np.zeros(n, np.int8), assignment=np.full((n, 0), -1, np.int32),
                         model=np.zeros(n, np.int32), entry=cells[:, 0].astype(np.int32), part=np.zeros(n, np.int32),
                         marker=np.zeros(n, bool), unseen_entries={}, det_relations=[],
                         largest=max(len(g) * len(g[0]) for _, g in grids), export_table=None, unseen=None))
    return out


# The engine's projections of a table, as the export names them: the files, the column of tables.parquet that holds
# the projections' kind code, and the column of the projection rows that gives the projection's row in its case.
# An export made before the engine named them projections names them views; the loader reads those names too, and
# spells them here alone.
PROJECTIONS_FILE, PROJECTION_ROWS_FILE = "projections.parquet", "projection_rows.parquet"
TABLE_PROJECTIONS, PROJECTION_ID = "projections", "projection"
OLD_NAMES = {PROJECTIONS_FILE: "views.parquet", PROJECTION_ROWS_FILE: "view_rows.parquet",
             TABLE_PROJECTIONS: "views", PROJECTION_ID: "view"}


def read_part(d, name):
    """An export's part file, under its name or its name in an older export."""
    return pd.read_parquet(d / name if (d / name).exists() else d / OLD_NAMES[name])


def with_names(df, *columns):
    """df with each column given renamed from its name in an older export, where it holds that name."""
    return df.rename(columns={OLD_NAMES[c]: c for c in columns if c not in df.columns and OLD_NAMES[c] in df.columns})
PROJECTIONS_STOPPED, PROJECTIONS_FOUND = 1, 2
POINT_RELATION = 0            # the point code of a relation table; a body is 1


def read_projections(d):
    """The projections of every table, each with its id in its case, and the rows of each at each entry."""
    projections = read_part(d, PROJECTIONS_FILE).reset_index(drop=True)
    projections[PROJECTION_ID] = projections.groupby(["task", "case"]).cumcount()
    return projections, with_names(read_part(d, PROJECTION_ROWS_FILE), PROJECTION_ID)


def entry_projection_rows(projections, projection_rows, table, entry):
    """The rows of every projection of `table` at `entry`, as [(columns, width, count, offset)], or the reason
    that the table is unseen. `projections` gives each table's projections ({table: [row]}), and
    `projection_rows` the first row of each projection at each entry ({(projection, entry): row}), of one case."""
    tp = projections.get(table, [])
    if not len(tp):
        return "a count with no projections"
    out = []
    for v in tp:
        pr = projection_rows.get((v[PROJECTION_ID], entry))
        if pr is None or not pr["defined"]:
            return "a projection with no rows at an entry"
        out.append((list(v["columns"]), int(v["width"]), int(pr["rows"]), int(pr["offset"])))
    return out


def evidence_for(task_json, case_tables):
    """The evidence tables of a case, which stand first. This is the one place that decides where they come
    from: today, the task file."""
    return evidence_tables(task_json)


UNSEEN_KINDS = {2: "an entry is undefined", 3: "an entry stopped", 4: "an example's fault", 5: "an example has no entries"}


def unseen_table(t, reason, unseen_entries=None, prov=None):
    """A table the encoder cannot see: no rows, and the reason. It keeps the columns of the export table t (Unit
    columns dropped), as a Table with rows does, so that the column indexes of the flows hold on every Table of
    one export table."""
    types = [type_name(x) for x in t["column_types"]]
    keep = [i for i, x in enumerate(types) if x != "Unit"]
    return Table(**(prov or {}), step=int(t["token"]) + 1, relation=int(t["relation"]), evidence=False, unseen=reason,
                 positions=keep, types=[types[i] for i in keep],
                 cells=np.zeros((0, sum(width(types[i]) for i in keep)), np.int32),
                 present=np.zeros((0, len(keep)), bool), example=np.zeros(0, np.int16),
                 example_kind=np.zeros(0, np.int8), assignment=np.zeros((0, 0), np.int32), model=np.zeros(0, np.int32),
                 entry=np.zeros(0, np.int32), part=np.zeros(0, np.int32), marker=np.zeros(0, bool),
                 unseen_entries=unseen_entries or {}, largest=0, export_table=int(t["table"]),
                 det_relations=list(t["det_relations"]))


def wholly_unseen_reason(unseen_entries):
    """The reason a table whose every entry is unseen is unseen: the entries' reason, where they share one."""
    return next(iter(unseen_entries)) if len(unseen_entries) == 1 else "every entry is unseen"


class DataFault(Exception):
    pass


FLOW_KINDS = ("copy", "computed", "constant", "lib name")   # a flow's kind, by its code
FLOW_CONSTANT, FLOW_LIB_NAME = 2, 3
FLOW_COLUMNS = ["table", "column", "kind", "source_table", "source_column", "det"]
GRID_TABLES = {"ex_input": 0, "ex_output": 1}   # the export table of each grid table, in every case


def kept_columns(column_types):
    """The loader's index of each of an export table's columns, -1 for a dropped (Unit) column."""
    out, k = [], 0
    for x in column_types:
        if type_name(x) == "Unit":
            out.append(-1)
        else:
            out.append(k); k += 1
    return out


def case_flows(fl, kept, where=""):
    """{export table: flows [m, 5] int32} of one case, from its rows of flows.parquet, with every column index
    mapped to the loader's (`kept`, {export table: `kept_columns`}); a flow of a dropped column is left out, and a
    dropped source column reads as -1. Raises DataFault where a flow names a table the case does not hold, or a
    column, or a source column, past its table's columns."""
    a = fl[FLOW_COLUMNS].to_numpy(np.int64)
    out = {}
    for tab in np.unique(a[:, 0]):
        rows = a[a[:, 0] == tab]
        res = []
        for row in rows.tolist():
            _, col, kind, st, sc, det = row
            km, skm = kept.get(int(tab)), kept.get(st) if st >= 0 else []
            if km is None or not 0 <= col < len(km) or skm is None or (st >= 0 and sc >= len(skm)):
                raise DataFault(f"{where}: flow {row} (table, column, kind, source table, source column, det) names "
                                f"a table or a column the export's tables.parquet does not give")
            c = km[col]
            if c < 0:
                continue
            if st >= 0 and sc >= 0:
                sc = skm[sc]
            res.append((c, kind, st, sc, det))
        out[int(tab)] = np.array(res, np.int32).reshape(-1, 5)
    return out


def check_provenance(task, case, tables):
    """Raises DataFault, with the table, its relation and the flow row, where a Table of a case's `tables` names a
    column it does not hold: a flow's column, a key column, `output_position` or `output_color` outside its
    columns, or a flow's source column outside the columns of a Table of its source; or where the Tables of one
    export table hold different columns, which the flows of that export table need to be the same."""
    of = {}
    for i, t in enumerate(tables):
        e = GRID_TABLES.get(t.relation) if t.evidence else t.export_table
        if e is not None:
            of.setdefault(e, []).append(i)
    for e, ix in of.items():
        if any(tables[i].types != tables[ix[0]].types for i in ix):
            raise DataFault(f"{task} {case} export table {e}: its Tables hold different columns "
                            f"{[tables[i].types for i in ix]}")
    for t in tables:
        if t.evidence or t.flows is None:
            continue
        nc, where = len(t.types), f"{task} {case} export table {t.export_table} relation {t.relation} types {t.types}"
        named = [c for k in t.keys for c in k] + [c for c in (t.output_position, t.output_color) if c != -1]
        if any(not 0 <= c < nc for c in named):
            raise DataFault(f"{where}: keys {t.keys}, output columns {t.output_position} {t.output_color}")
        for row in t.flows.tolist():
            c, _, st, sc, _ = row
            if not 0 <= c < nc:
                raise DataFault(f"{where}: flow {row} names column {c}")
            for i in of.get(st, []) if sc >= 0 else []:
                if sc >= len(tables[i].types):
                    raise DataFault(f"{where}: flow {row} names column {sc} of the source table {i}, relation "
                                    f"{tables[i].relation}, types {tables[i].types}")


def color_dependence(flows, output_table, output_color):
    """Whether the column `output_color` of `output_table` reaches, through the flows ({export table: flows}) at
    any depth, a DET or ex_output: then ex_output's Color is computed from the train outputs. Elsewhere it reaches
    only ex_input, constants, lib names, lib relations and relations with no table, and is computed from the
    input."""
    seen, stack = set(), [(output_table, output_color)]
    while stack:
        tc = stack.pop()
        if tc in seen:
            continue
        seen.add(tc)
        f = flows.get(tc[0])
        if f is None:
            continue
        f = f[f[:, 0] == tc[1]]
        if (f[:, 4] >= 0).any() or (f[:, 2] == GRID_TABLES["ex_output"]).any():
            return True
        stack += [(s, c) for s, c in f[(f[:, 2] > GRID_TABLES["ex_output"]) & (f[:, 3] >= 0)][:, 2:4].tolist()]
    return False


def parse_tables(tables_dir, tasks_dir=Path(__file__).resolve().parents[1] / "data/tasks"):
    """{(task, case): [Table]} for every case of the export, and {(task, case): fault} for each case whose export
    cannot be read (no values file, rows past its end), which is left out. A relation table the encoder cannot see
    (it faults, the search for its projections stopped, or an entry is not rows) stays, as an unseen table. A
    relation table whose entries hold several assignments gives one Table per assignment (`parse_table`)."""
    d = Path(tables_dir)
    tables = with_names(pd.read_parquet(d / "tables.parquet"), TABLE_PROJECTIONS)
    index = pd.read_parquet(d / "index.parquet")
    assigned = pd.read_parquet(d / "assigned.parquet")
    projections, projection_rows = read_projections(d)
    by = lambda df: {k: g for k, g in df.groupby(["task", "case"], sort=False)} if len(df) else {}
    idx_by, asg_by, proj_by, prows_by = by(index), by(assigned), by(projections), by(projection_rows)
    # the column-level provenance, where the export gives it; else the masked loss takes the table-level sources
    # and the identifiability test (`field_labels`, `draw_masks`)
    provenance = (d / "flows.parquet").exists() and "depth" in tables.columns
    flows_by = by(pd.read_parquet(d / "flows.parquet", columns=["task", "case"] + FLOW_COLUMNS)) if provenance else {}
    out, faults = {}, {}
    stats = {"body tables": 0, "provenance": "column flows of the export" if provenance else
             "table-level: the export gives no flows, keys or depths"}
    for (task, case), tabs in tables.groupby(["task", "case"], sort=False):
        task_json = json.load(open(f"{tasks_dir}/{task}.json"))
        n_train = len(task_json["train"])
        path = d / "values" / task / f"{case}.i32"
        if not path.exists():
            faults[(task, case)] = "no values file"; continue
        values = np.fromfile(path, np.int32)
        entries = idx_by.get((task, case))
        ents_of = {} if entries is None else records_by(entries, "table")
        asg = asg_by.get((task, case))
        asg_of = {} if asg is None else records_by(asg, "entry")
        projs, prows = proj_by.get((task, case)), prows_by.get((task, case))
        projs = {} if projs is None else records_by(projs, "table")
        # the first row of each projection at each entry
        prows = {} if prows is None else {k: rs[0] for k, rs in records_by(prows, [PROJECTION_ID, "entry"]).items()}
        det_values = {}   # (det relation, cells) -> index
        result = evidence_for(task_json, tabs)
        records = tabs.sort_values("table").to_dict("records")
        if provenance:
            kept = {int(t["table"]): kept_columns(t["column_types"]) for t in records}
            fl = flows_by.get((task, case))
            flows = {} if fl is None else case_flows(fl, kept, f"{task} {case}")
            ex_output = result[1]
            for t in records:
                k = kept[int(t["table"])]
                if t["point"] == POINT_RELATION and t["output_color"] >= 0 and k[t["output_color"]] >= 0:
                    ex_output.color_dependent = color_dependence(flows, int(t["table"]), k[t["output_color"]])
        try:
            for t in records:
                if t["point"] != POINT_RELATION:
                    stats["body tables"] += t["point"] == 1
                    continue
                prov = None
                if provenance:
                    k = kept[int(t["table"])]
                    at = lambda c: k[c] if c >= 0 else -1
                    prov = dict(depth=int(t["depth"]), keys=[[k[c] for c in key if k[c] >= 0] for key in t["keys"]],
                                output_position=at(int(t["output_position"])), output_color=at(int(t["output_color"])),
                                flows=flows.get(int(t["table"]), np.zeros((0, 5), np.int32)))
                result += parse_table(t, ents_of.get(t["table"], []), values, asg_of, projs, prows, det_values,
                                      n_train, prov)
        except DataFault as f:
            faults[(task, case)] = str(f); continue
        if provenance:
            check_provenance(task, case, result)   # a fault of the export's provenance fails the whole build
        out[(task, case)] = result
    relation_tables = [t for ts in out.values() for t in ts if not t.evidence]
    unseen, _ = unseen_counts(out)
    if sum(unseen.values()) * 2 > len(relation_tables):
        raise DataFault(f"more than half of the {len(relation_tables)} relation tables are unseen, which means a bug "
                        f"in the loader or in the export: {sum(unseen.values())} unseen, by reason {unseen}")
    return out, faults, stats


def records_by(df, key):
    """{key value: [row as a dict]}, the rows in the frame's order; a key of several columns gives tuples."""
    out = {}
    for r in df.to_dict("records"):
        out.setdefault(tuple(r[k] for k in key) if isinstance(key, list) else r[key], []).append(r)
    return out


def parse_table(t, ents, values, asg_of, projs, prows, det_values, n_train, prov=None):
    """The Tables of the export's table t, from its entries `ents` (rows of the index, as dicts): one per
    assignment that its entries hold, in the order of each assignment's first entry, or one where they hold one
    assignment or none; or its unseen table. Raises DataFault where the values cannot be read. An entry the
    encoder cannot see gives one marker row; a Table whose every entry is unseen is unseen. `prov` gives the
    table's provenance attributes (`Table`), which every Table of t shares, or None."""
    prov = prov or {}
    if not pd.isna(t["fault"]):   # a null reads as None or as nan, by the column's dtype
        return [unseen_table(t, "the table faults", prov=prov)]
    if t[TABLE_PROJECTIONS] == PROJECTIONS_STOPPED:
        return [unseen_table(t, "the search for its projections stopped", prov=prov)]
    types = [type_name(x) for x in t["column_types"]]
    keep = [i for i, x in enumerate(types) if x != "Unit"]
    kept_width = sum(width(types[i]) for i in keep)
    det_rel, det_w = list(t["det_relations"]), list(t["det_widths"])
    # per assignment: its rows' groups (cells over kept columns, present, example, kind, assignment, model, entry,
    # part, marker), the most rows of one entry or of one projection at an entry, and its unseen entries by reason
    splits = {}
    assignment = {}   # entry -> the index of each DET's value at the entry's assignment

    def assignment_of(e):
        if e["entry"] not in assignment:
            a = np.full(len(det_rel), -1, np.int32)
            for r in asg_of.get(e["entry"], []):
                run = rows_at(int(r["offset"]), int(r["rows"]), det_w[r["det"]])
                a[r["det"]] = det_values.setdefault((det_rel[r["det"]], run.tobytes()), len(det_values))
            assignment[e["entry"]] = a
        return assignment[e["entry"]]

    def split_of(e):
        return splits.setdefault(assignment_of(e).tobytes(), {"groups": [], "largest": 0, "unseen": {}})

    def rows_at(off, n, w):
        if off + n * w > len(values):
            raise DataFault(f"table {t['table']}: rows past the end of the values file")
        return values[off:off + n * w].reshape(n, w)

    def add(rows_cells, cols, e, part=0, marker=False):
        n = len(rows_cells)
        full = np.zeros((n, kept_width), np.int32)
        present = np.zeros((n, len(keep)), bool)
        src = 0
        for c in cols:
            w = width(types[c])
            if c in keep:
                k = keep.index(c)
                o = sum(width(types[keep[i]]) for i in range(k))
                full[:, o:o + w] = rows_cells[:, src:src + w]
                present[:, k] = True
            src += w
        kind = int(e["example_kind"])
        ex = -1 if kind == 0 else int(e["example_index"]) + (n_train if kind == 2 else 0)
        a = assignment_of(e)
        split_of(e)["groups"].append((full, present, np.full(n, ex, np.int16), np.full(n, kind, np.int8),
                                      np.tile(a, (n, 1)), np.full(n, int(e["model"]), np.int32),
                                      np.full(n, int(e["entry"]), np.int32), np.full(n, part, np.int32),
                                      np.full(n, marker, bool)))

    def unseen_entry(e, reason):
        u = split_of(e)["unseen"]
        u[reason] = u.get(reason, 0) + 1
        add(np.zeros((1, 0), np.int32), [], e, marker=True)

    def note_largest(e, n):
        sp = split_of(e)
        sp["largest"] = max(sp["largest"], n)

    for e in ents:
        k = int(e["kind"])
        if k in UNSEEN_KINDS:
            unseen_entry(e, UNSEEN_KINDS[k]); continue
        if k == 0:
            n = int(e["rows"])
            add(rows_at(int(e["offset"]), n, int(t["width"])), range(len(types)), e)
            note_largest(e, n)
            continue
        # Count: the table gives its projections, and each projection's rows at this entry are rows of the table
        parts = entry_projection_rows(projs, prows, t["table"], e["entry"])
        if isinstance(parts, str):
            unseen_entry(e, parts); continue
        for j, (cols, w, n, off) in enumerate(parts):
            note_largest(e, n)
            add(rows_at(off, n, w), cols, e, part=j)

    def table(groups, largest, unseen_entries):
        if unseen_entries and all(g[8].all() for g in groups):
            return unseen_table(t, wholly_unseen_reason(unseen_entries), unseen_entries, prov)
        cat = lambda i, empty: np.concatenate([g[i] for g in groups]) if groups else empty
        return Table(**prov, step=int(t["token"]) + 1, relation=int(t["relation"]), evidence=False, unseen=None,
                     positions=keep, types=[types[i] for i in keep],
                     cells=cat(0, np.zeros((0, kept_width), np.int32)), present=cat(1, np.zeros((0, len(keep)), bool)),
                     example=cat(2, np.zeros(0, np.int16)), example_kind=cat(3, np.zeros(0, np.int8)),
                     assignment=cat(4, np.zeros((0, len(det_rel)), np.int32)), model=cat(5, np.zeros(0, np.int32)),
                     entry=cat(6, np.zeros(0, np.int32)), part=cat(7, np.zeros(0, np.int32)),
                     marker=cat(8, np.zeros(0, bool)), unseen_entries=unseen_entries, largest=largest,
                     export_table=int(t["table"]), det_relations=det_rel)
    return [table(sp["groups"], sp["largest"], sp["unseen"]) for sp in splits.values()] or [table([], 0, {})]


def table_groups(tables):
    """The group of each table of a program, numbered from 0 in order: the Tables of one export table share a
    group, and every other table has its own."""
    out, g, prev = [], -1, None
    for t in tables:
        key = None if t.evidence or t.export_table is None else t.export_table
        if key is None or key != prev:
            g += 1
        out.append(g)
        prev = key
    return out


LOADER_VERSION = 14  # raise on any change to parse_tables or Table


def table_stamp(tables_dir):
    """The stamp of an export: the loader version, the export's directory name and the whole-second mtimes of its
    index and of the task files, so a cache built on one machine holds on another."""
    tasks = Path(__file__).resolve().parents[1] / "data/tasks"
    return (LOADER_VERSION, Path(tables_dir).resolve().name, int(os.path.getmtime(Path(tables_dir) / "index.parquet")),
            int(max(os.path.getmtime(f) for f in tasks.glob("*.json"))))


def load_tables(tables_dir, cache):
    """parse_tables, through a pickle at `cache` keyed by the export, the task files and the loader version. The
    stamp is also in the file `<cache>.stamp.json`, which is read first, so that a stale pickle is not loaded."""
    tasks = Path(__file__).resolve().parents[1] / "data/tasks"
    stamp = table_stamp(tables_dir)
    sidecar = f"{cache}.stamp.json"
    cached, cached_stamp = None, None
    if os.path.exists(cache):
        cached_stamp = read_sidecar(sidecar)
        if cached_stamp is None:   # no sidecar: the stamp inside the pickle
            cached = pickle.load(open(cache, "rb"))
            cached_stamp = list_or_tuple(cached.get("stamp"))
            if cached_stamp == list_or_tuple(stamp):
                write_sidecar(sidecar, stamp)
        if cached_stamp == list_or_tuple(stamp):
            if cached is None:
                cached = pickle.load(open(cache, "rb"))
            return cached["tables"], cached["skipped"], cached["stats"]
        print(f"cache rebuilt: {stamp_difference(cached_stamp, stamp)}", flush=True)
    else:
        print(f"building cache for {tables_dir}", flush=True)
    cached = None   # frees a stale pickle before the rebuild
    tables, skipped, stats = parse_tables(tables_dir, tasks)
    if os.path.exists(sidecar):
        os.remove(sidecar)   # the sidecar stays only beside a pickle that was written whole
    pickle.dump({"stamp": stamp, "tables": tables, "skipped": skipped,
                 "stats": stats}, open(cache, "wb"))
    write_sidecar(sidecar, stamp)
    return tables, skipped, stats


STAMP_PARTS = ("loader version", "export", "index mtime", "tasks mtime")


def list_or_tuple(stamp):
    return list(stamp) if isinstance(stamp, (list, tuple)) else stamp


def read_sidecar(path):
    """The stamp in the sidecar file at `path` (a list), or None where there is no readable sidecar."""
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_sidecar(path, stamp):
    try:
        with open(path, "w") as f:
            json.dump(list(stamp), f)
    except OSError as e:
        print(f"no stamp sidecar written at {path}: {e}", flush=True)


def stamp_difference(cached, current):
    """The parts of two stamps that differ, each with its cached and its current value."""
    if not isinstance(cached, (list, tuple)) or len(cached) != len(current):
        return f"stamp {cached} is not of the current form, now {list(current)}"
    return "; ".join(f"{name} {old} -> {new}" for name, old, new in zip(STAMP_PARTS, cached, current) if old != new)


def mark_over_budget(tables, budget):
    """Replaces with a marker row each entry of a table of `tables` ({(task, case): [Table]}) that holds, on itself
    or on one of its projections, more rows than `budget`, the encoder's context length; a table whose every entry
    is then unseen becomes unseen. Gives the entries replaced: [(task, case, export table, relation, entry, rows)].
    The evidence tables, one entry over every example, are exempt."""
    over = []
    for (task, case), ts in tables.items():
        for i, t in enumerate(ts):
            if t.evidence or t.unseen is not None or t.largest <= budget:
                continue
            key = t.entry.astype(np.int64) * (1 << 20) + t.part
            u_key, inv, counts = np.unique(key, return_inverse=True, return_counts=True)
            big = {int(k >> 20): int(n) for k, n in zip(u_key, counts) if n > budget}
            for e in sorted(big):
                over.append((task, case, t.export_table, t.relation, e, big[e]))
            drop = np.isin(t.entry, list(big))
            first = [int(np.flatnonzero(t.entry == e)[0]) for e in sorted(big)]   # the marker row takes this row's entry fields
            u = Table(**t.__dict__)
            u.unseen_entries = {**t.unseen_entries, "an entry over the budget": len(big)}
            keep = np.flatnonzero(~drop)
            for f in ROW_FIELDS:
                v = getattr(t, f)
                marker_rows = v[first].copy()
                if f in ("cells", "present"):
                    marker_rows[:] = 0
                elif f == "part":
                    marker_rows[:] = 0
                elif f == "marker":
                    marker_rows[:] = True
                setattr(u, f, np.concatenate([v[keep], marker_rows]))
            u.largest = max([int(n) for k, n in zip(u_key, counts) if int(k >> 20) not in big], default=0)
            if u.marker.all():
                u = Table(**{**u.__dict__, "unseen": wholly_unseen_reason(u.unseen_entries), "largest": 0,
                             **{f: getattr(u, f)[:0] for f in ROW_FIELDS}})
            ts[i] = u
    return over


def mark_over_rows(tables, max_rows):
    """Makes unseen each table of `tables` that holds more rows than `max_rows`, summed over its entries, a guard
    on the device's memory; gives them: [(task, case, export table, relation, rows)]. The evidence tables are
    exempt."""
    over = []
    for (task, case), ts in tables.items():
        for i, t in enumerate(ts):
            if not t.evidence and t.unseen is None and t.n > max_rows:
                over.append((task, case, t.export_table, t.relation, t.n))
                ts[i] = Table(**{**t.__dict__, "unseen": "more rows than --enc-max-rows", "largest": 0,
                                 **{f: getattr(t, f)[:0] for f in ROW_FIELDS}})
    return over


def unseen_counts(tables):
    """The count of unseen tables by reason, and of unseen entries by reason (those of the unseen tables included)."""
    counts, entries = {}, {}
    for ts in tables.values():
        for t in ts:
            if t.unseen is not None:
                counts[t.unseen] = counts.get(t.unseen, 0) + 1
            for r, n in getattr(t, "unseen_entries", {}).items():
                entries[r] = entries.get(r, 0) + n
    return counts, entries


def max_example(tables):
    """The largest example index of any row or Example field."""
    m = 0
    for ts in tables.values():
        for t in ts:
            if t.n:
                m = max(m, int(t.example.max()))
                o = 0
                for ty in t.types:
                    if ty == "Example":
                        m = max(m, int(t.cells[:, o].max()))
                    o += width(ty)
    return m


# ---------------------------------------------------------------- layers

class EqLinear(nn.Module):
    """A linear map of [.., 21, c_in] to [.., 21, c_out] that commutes with D4: one c_out x c_in weight per orbit
    of D4 on pairs of positions, and one bias per orbit of positions."""
    def __init__(self, c_in, c_out, bias=True):
        super().__init__()
        self.c_in, self.c_out = c_in, c_out
        orb = torch.zeros(NPOS, NPOS, dtype=torch.long)
        for (p, q), k in PAIR_ORBIT.items():
            orb[p, q] = k
        self.register_buffer("orb", orb, persistent=False)
        self.register_buffer("porb", torch.tensor([POSITION_ORBIT[p] for p in range(NPOS)]), persistent=False)
        self.weight = nn.Parameter(torch.randn(N_PAIR_ORBITS, c_out, c_in) / math.sqrt(NPOS * c_in))
        self.bias = nn.Parameter(torch.zeros(N_POS_ORBITS, c_out)) if bias else None
        self.M = self.b = None   # the matrix and the bias vector, while `FeatureEncoder.prepare` holds them

    def matrix(self):
        return self.weight[self.orb].permute(0, 2, 1, 3).reshape(NPOS * self.c_out, NPOS * self.c_in)

    def bias_vector(self):
        """The bias at every position, [21 c_out], or None."""
        return None if self.bias is None else self.bias[self.porb].reshape(-1)

    def forward(self, x):
        M, b = (self.M, self.b) if self.M is not None else (self.matrix(), self.bias_vector())
        return F.linear(x.reshape(*x.shape[:-2], NPOS * self.c_in), M, b).reshape(*x.shape[:-2], NPOS, self.c_out)


EQUALITY_MODES = ("codes", "random", "flex")
RANDOM_CODE_WIDTH = 32   # the width of a sign code of the "random" equality term, per value


def flex_scores(groups, n_rows):
    """The score_mod of flex_attention that adds the equality term to the scores of the first n_rows keys: for each
    group (values [B, n, m, S], present [B, n, m], weights [B, H, m, m]) and each pair of its columns, the weight
    times the count of the S places where the two rows' values are equal, where both are present."""
    def score_mod(score, b, h, qi, kv):
        kk = torch.clamp(kv, max=n_rows - 1)
        add = torch.zeros_like(score)
        for vals, pres, w in groups:
            m, S = vals.shape[2], vals.shape[3]
            for i in range(m):
                for j in range(m):
                    same = sum((vals[b, qi, i, s] == vals[b, kk, j, s]).to(score.dtype) for s in range(S))
                    add = add + w[b, h, i, j].to(score.dtype) * same * (pres[b, qi, i] & pres[b, kk, j]).to(score.dtype)
        return score + torch.where(kv < n_rows, add, torch.zeros_like(add))
    return score_mod


FLEX = {}   # flex_attention, compiled on cuda


def flex_attention(device_type):
    from torch.nn.attention.flex_attention import flex_attention as fa
    if device_type != "cuda":
        return fa   # eager: it gives the scores of every query and key at once, and has no backward pass on the CPU
    if "cuda" not in FLEX:
        FLEX["cuda"] = torch.compile(fa)
    return FLEX["cuda"]


def up8(w):
    return -(-w // 8) * 8


def head_index(c, heads, width):
    """The head layout of a map's output: per head, that head's channels at each of the 21 positions, then zeros up to
    `width`. Gives the place of each among the 21 c places of the position layout, or 21 c for a zero."""
    dh = c // heads
    out = []
    for h in range(heads):
        out += [p * c + h * dh + e for p in range(NPOS) for e in range(dh)] + [NPOS * c] * (width - NPOS * dh)
    return torch.tensor(out)


def head_rows(lin, index, scale=1.0):
    """The matrix and bias vector of the EqLinear `lin` (as `prepare` holds them) with their rows in the head layout
    `index` of head_index, times scale: their output is the map's, in head layout."""
    M = F.pad(lin.M, (0, 0, 0, 1)).index_select(0, index)
    b = F.pad(lin.b, (0, 1)).index_select(0, index)
    return (M * scale, b * scale) if scale != 1 else (M, b)


def head_cols(lin, index):
    """The matrix of `lin` that takes its input in the head layout `index`, and its bias vector."""
    return F.pad(lin.M, (0, 1)).index_select(1, index), lin.b


def attend(q, k, v, mask, flex=None):
    """Attention in head layout: q [B, nq, H, wq], k [B, nk, H, wq], v [B, nk, H, wv], mask [B, 1, nq or 1, nk] bool
    (keys where it is False take no weight) -> [B, nq, H wv]. The scores are the inner products, unscaled. With
    `flex` (groups, n_rows), the equality term of `flex_scores` is added through flex_attention."""
    B, nq, nk = q.shape[0], q.shape[1], k.shape[1]
    if flex is not None:
        from torch.nn.attention.flex_attention import create_block_mask
        km = mask[:, 0, 0]
        block_mask = create_block_mask(lambda b_, h_, qi, kv: km[b_, kv], B, None, nq, nk, device=q.device)
        o = flex_attention(q.device.type)(q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2),
                                          score_mod=flex_scores(*flex), block_mask=block_mask, scale=1.0)
    else:
        o = F.scaled_dot_product_attention(q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2), attn_mask=mask,
                                           scale=1.0)
    return o.transpose(1, 2).reshape(B, nq, -1)


def placed(src, at, n):
    """n rows of zeros with the rows of src [k, ...] at the distinct places at [k]: a copy, whose backward pass is a
    gather."""
    return src.new_zeros(n, *src.shape[1:]).index_copy(0, at, src)


def leading(t, dim, perm, width):
    """The places of t whose permutation perm (along `dim`) takes to the first `width`, in that order."""
    return torch.zeros_like(t).index_copy(dim, perm, t).narrow(dim, 0, width)


def equality_keys(eq, pos, item, codes, scale=1):
    """The equality term's key channels of each row, [R, L, H, m D], from the weights eq [L, H, slots, slots] of each
    layer, the column positions pos [I, m] of each table, the table of each row item [R] and the rows' codes
    [R, m, D] of one group: for column i, the codes of the columns j mixed by the weight of the pair (i, j), times
    `scale`. The query channels are the codes; their inner product is the term."""
    R, m, D = codes.shape
    L, H = eq.shape[:2]
    w = eq[:, :, pos[:, :, None], pos[:, None, :]].permute(2, 0, 1, 3, 4)                     # [I, L, H, m, m]
    if scale != 1:
        w = w * scale
    w = F.embedding(item, w.reshape(len(w), -1)).reshape(R, L * H * m, m)
    return torch.bmm(w.to(codes.dtype), codes).view(R, L, H, m * D)


class Block(nn.Module):
    """A pre-norm transformer block over the rows of a batch of tables [B, N, 21, c]. A score is the sum over
    positions of the inner products of a head's channels, scaled, plus the equality term within the table. The keys
    and values also hold each table's earlier pooled vectors and the rows of its program's earlier evidence tables
    after this layer, and, with `source_rows`, the rows of each derived table's source tables after this layer, whose
    equality term compares each column with the source columns its flows name, under the weights `src_eq`. `ctx` (a
    `Batch`) holds those, the key mask and the equality term's query and key channels; `mats` the maps that
    `FeatureEncoder.prepare` gives in head layout."""
    def __init__(self, c, heads, slots, mlp, source_rows=False):
        super().__init__()
        self.heads = heads
        self.n1, self.n2 = nn.LayerNorm(c), nn.LayerNorm(c)
        self.q, self.k, self.v, self.o = (EqLinear(c, c) for _ in range(4))
        self.f1, self.f2 = EqLinear(c, mlp * c), EqLinear(mlp * c, c)
        self.eq = nn.Parameter(torch.zeros(heads, slots, slots))   # per head and column-position pair
        if source_rows:   # per head, and per pair of a column's position and its source column's position
            self.src_eq = nn.Parameter(torch.zeros(heads, slots, slots))

    def weights(self, pos):
        """The learned weight of each pair of the columns at positions pos [B, m], per head: [B, H, m, m]."""
        return self.eq[:, pos[:, :, None], pos[:, None, :]].transpose(0, 1)

    def forward(self, x, ctx, l, mats):
        B, N, H = x.shape[0], x.shape[1], self.heads
        W, Wv = mats["W"], mats["Wv"]
        # the rows and the pooled vectors through one norm and one map, which gives q, k and v of both
        h = self.n1(x if ctx.prev is None else torch.cat([x, ctx.prev], 1))
        qkv = F.linear(h.reshape(B, h.shape[1], -1), mats["qkv"], mats["bqkv"])
        q, k, v = qkv.split([H * W, H * W, H * Wv], -1)   # one split, whose backward pass is one cat
        q, k, v = q[:, :N].view(B, N, H, W), k.view(B, -1, H, W), v.view(B, -1, H, Wv)
        if ctx.eq_q is not None:   # the equality term's channels, and the zeros that pad q and k to a multiple of 8
            q = torch.cat([q, ctx.eq_q.expand(-1, -1, H, -1)], -1)
            k = torch.cat([k, ctx.eq_k[l]], -1)
        if ctx.ev is not None:
            ek, evl = ctx.ev.layer(l)
            k, v = torch.cat([k, ek], 1), torch.cat([v, evl], 1)
        if ctx.src is not None:
            sk, sv = ctx.src.layer(l)
            k, v = torch.cat([k, sk], 1), torch.cat([v, sv], 1)
        flex = None
        if ctx.flex is not None:   # each group's values, presence and weights, for the rows, the first N keys
            flex = ([(vals, pres, self.weights(pos)) for vals, pres, pos in ctx.flex], N)
        acc = None
        if ctx.code_v is not None and l == ctx.code_layer:   # the source keys' codes as extra value channels
            cv = F.pad(ctx.code_v, (0, 0, v.shape[1] - ctx.code_v.shape[1], 0)).to(v.dtype)
            Wv = v.shape[-1]
            v = torch.cat([v, cv[:, :, None].expand(-1, -1, H, -1)], -1)
            o = attend(q, k, v, ctx.mask, flex).view(B, N, H, -1)
            o, acc = o[..., :Wv].reshape(B, N, H * Wv), o[..., Wv:]
        else:
            o = attend(q, k, v, ctx.mask, flex)
        x = x + F.linear(o, mats["o"], mats["bo"]).view(x.shape)
        f = F.gelu(F.linear(self.n2(x).reshape(B, N, -1), mats["f1"], mats["bf1"]))
        x = x + F.linear(f, mats["f2"], mats["bf2"]).view(x.shape)
        return x if acc is None else (x, acc)


class Pool(nn.Module):
    """K learned seeds, each fixed by D4 (the same edge vector on every edge, one pair vector per orbit of edge
    pairs), attend to the rows."""
    def __init__(self, c, heads, K, mlp):
        super().__init__()
        self.heads, self.K = heads, K
        self.seed = nn.Parameter(torch.randn(K, N_POS_ORBITS, c) * 0.5)
        self.register_buffer("porb", torch.tensor([POSITION_ORBIT[p] for p in range(NPOS)]), persistent=False)
        self.n0, self.n1, self.n2 = nn.LayerNorm(c), nn.LayerNorm(c), nn.LayerNorm(c)
        self.q, self.k, self.v, self.o = (EqLinear(c, c) for _ in range(4))
        self.f1, self.f2 = EqLinear(c, mlp * c), EqLinear(mlp * c, c)

    def seeds(self):
        return self.seed[:, self.porb]                   # [K, 21, c]

    def forward(self, x, mask, mats):
        """x [B, N, 21, c] and mask [B, 1, J K, N]: J poolings of the same rows, each over the rows its K rows of the
        mask keep, in one attention call -> [B, J K, 21, c]. `mats` as `FeatureEncoder.prepare` gives them."""
        B, N, H, JK = x.shape[0], x.shape[1], self.heads, mask.shape[2]
        Wq, Wv = mats["Wq"], mats["Wv"]
        kv = F.linear(self.n1(x).reshape(B, N, -1), mats["kv"], mats["bkv"])
        k, v = kv.split([H * Wq, H * Wv], -1)
        k, v = k.view(B, N, H, Wq), v.view(B, N, H, Wv)
        q = mats["q"].repeat(JK // self.K, 1, 1)[None].expand(B, -1, -1, -1)       # [B, J K, H, Wq]
        s = mats["seeds"].repeat(JK // self.K, 1, 1)                               # [J K, 21, c]
        s = s + F.linear(attend(q, k, v, mask), mats["o"], mats["bo"]).view(B, JK, NPOS, -1)
        f = F.gelu(F.linear(self.n2(s).reshape(B, JK, -1), mats["f1"], mats["bf1"]))
        return s + F.linear(f, mats["f2"], mats["bf2"]).view(s.shape)


PAIR_ORBITS = [[p for p in range(5, NPOS) if POSITION_ORBIT[p] == o]
               for o in sorted({POSITION_ORBIT[p] for p in range(5, NPOS)})]   # same edge, opposite, adjacent


PAIR_ORBIT_OF = [next(k for k, idx in enumerate(PAIR_ORBITS) if p in idx) for p in range(5, NPOS)]   # 0 same edge, ...


def readout_width(c, r):
    return 5 * c + 4 * r * r


class Readout(nn.Module):
    """Frame-free quantities of pooled vectors [n, 21, c]: the invariant channels; over the edges, the sum of the
    channels and the Gram matrix of their projection to r channels (the inner products of each projected channel
    pair over the four edges); and the same over each orbit of edge pairs: [n, 5c + 4r^2]. A projection mixes
    channels alone, the same at every position, so it commutes with D4."""
    def __init__(self, c, r):
        super().__init__()
        self.proj = nn.ModuleList(nn.Linear(c, r, bias=False) for _ in range(1 + len(PAIR_ORBITS)))

    def forward(self, s):
        inv, edge = s[:, 0], s[:, 1:5]
        gram = lambda x: torch.einsum("npi,npj->nij", x, x).flatten(1)
        parts = [inv, edge.sum(1), gram(self.proj[0](edge))]
        for k, idx in enumerate(PAIR_ORBITS):
            parts += [s[:, idx].sum(1), gram(self.proj[1 + k](s[:, idx]))]
        return torch.cat(parts, -1)


# ---------------------------------------------------------------- masked table loss

CANDIDATES = {   # the constants of each orientation type, which the masked loss scores
    "Dir": ["DIR_T", "DIR_B", "DIR_L", "DIR_R"], "DiagDir": ["DIAG_TL", "DIAG_TR", "DIAG_BL", "DIAG_BR"],
    "Axis": ["AXIS_V", "AXIS_H"], "DiagAxis": ["DAXIS_DG", "DAXIS_AD"], "D4": list(ELEMENTS), "Pose": list(ELEMENTS),
    "C4": ["D4_ID", "D4_CW", "D4_HT", "D4_CC"], "Sym": list(SUBGROUPS), "Sense": list(SENSES)}
CANDIDATES["Dir8"] = CANDIDATES["Dir"] + CANDIDATES["DiagDir"]
CANDIDATES["Axis4"] = CANDIDATES["Axis"] + CANDIDATES["DiagAxis"]
# the type whose candidates a field of each orientation type is scored over when its value is no constant of its
# column's type: the export can type a column C4 whose values include D4's reflections
WIDER = {"C4": "D4", "Dir": "Dir8", "DiagDir": "Dir8", "Axis": "Axis4", "DiagAxis": "Axis4"}


def scored_type(ty, name):
    """The orientation type whose candidates a field of column type ty with the constant `name` is scored over: ty
    where `name` is one of its candidates, else the wider type of ty that holds it."""
    for t in (ty, WIDER.get(ty)):
        if t is not None and name in CANDIDATES[t]:
            return t
    raise ValueError(f"the orientation constant {name} is no candidate of the column type {ty} or a wider type")
POINTER_TYPES = ("Color", "Example", "Ident")


class MaskedHeads(nn.Module):
    """The prediction heads of the masked table loss. Each reads a row's token after the encoder's layers, bound
    to the masked field's column slot by a channel-wise product (the slot's invariant, edge and pairwise bindings at
    their positions), through two equivariant maps, z [21, c]:

    - a Number: a class over the number embedding's range, from z's invariant channels against that embedding;
    - a Box: per edge, a class over the margin embedding's range, from z's channels at that edge;
    - an orientation: per candidate constant of the column's type, the inner product of its edge indicator and
      its two pairwise matrices with scores read from z's edge and pairwise positions, so a D4 element permutes
      the candidates' scores as it moves the constants;
    - a Color, Example or Ident: a pointer to a row of the same table that holds the same value in that column
      (other than the row, with that field present and not masked), scored by the inner product over every
      position of the bound query with each row's key, or the class "no row holds it" from z's invariant channels.
    """
    def __init__(self, c, slots=0, heads=0, ptr_equality=False, source_rows=False):
        super().__init__()
        self.norm = nn.LayerNorm(c)
        self.h1, self.h2 = EqLinear(c, c), EqLinear(c, c)
        self.number = nn.Linear(c, c)
        self.margin = nn.Linear(c, c)
        self.o_edge, self.o_pair, self.o_ref = (nn.Linear(c, 1, bias=False) for _ in range(3))
        self.ptr_q, self.ptr_k = EqLinear(c, c), EqLinear(c, c)
        self.none = nn.Linear(c, 1)
        if ptr_equality:   # the pointer's equality terms: per pair of the hidden column's and a visible column's position
            self.ptr_eq = nn.Parameter(torch.zeros(slots, slots))
            if source_rows:   # and per head and hidden column position, on the codes the last layer's attention gathers
                self.ptr_src = nn.Parameter(torch.zeros(heads, slots))


def bound_slots(S):
    """The binding of each column slot at every position: [slots, 21, c] from S [slots, 3, c]."""
    return torch.cat([S[:, :1], S[:, 1:2].expand(-1, 4, -1), S[:, 2:3].expand(-1, 16, -1)], 1)


# ---------------------------------------------------------------- encoder

class Identifiers:
    """The random identifiers and equality codes of one decode, drawn on first use and reused after: per kind, a
    matrix of the vectors drawn, in the order drawn, and the row of each key. The matrices stay on the host; the
    encoder gathers the vectors it needs there and moves them to the device once per level."""
    def __init__(self, c, code_dim, gen, device, dtype=None):
        self.c, self.code_dim, self.gen, self.device = c, code_dim, gen, device
        self.dtype = dtype or torch.get_default_dtype()
        self.mats, self.rows = {}, {}

    def get(self, kind, keys, dim=None):
        """The row of each key in mats[kind], the vectors of keys not seen before drawn in the order given."""
        dim = dim or self.c
        rows = self.rows.setdefault(kind, {})
        new = [k for k in keys if k not in rows]
        if new:
            if kind.startswith("sign"):   # a vector of signs
                v = torch.randint(0, 2, (len(new), dim), generator=self.gen).to(self.dtype) * 2 - 1
            else:
                v = torch.randn(len(new), dim, generator=self.gen)
            if kind.endswith("code"):
                v = v / v.norm(dim=1, keepdim=True)
            v = v.to(self.dtype)
            start = len(self.mats[kind]) if kind in self.mats else 0
            self.mats[kind] = torch.cat([self.mats[kind], v]) if start else v
            for j, k in enumerate(new):
                rows[k] = start + j
        return [rows[k] for k in keys]

    def put(self, kind, key, vec):
        """Sets the vector of a key."""
        rows = self.rows.setdefault(kind, {})
        vec = vec.to("cpu", self.dtype)
        start = len(self.mats[kind]) if kind in self.mats else 0
        self.mats[kind] = torch.cat([self.mats[kind], vec[None]]) if start else vec[None]
        rows[key] = start

    @property
    def vecs(self):
        """{(kind, key): vector}."""
        return {(kind, k): self.mats[kind][r] for kind, rows in self.rows.items() for k, r in rows.items()}

    def host(self, kind, values, dim=None, unique=None):
        """The vector of each value of the integer array `values`, [n, dim] on the host; `unique` is
        np.unique(values, return_inverse=True), where the caller has it."""
        dim = dim or self.c
        u, inv = unique if unique is not None else np.unique(values, return_inverse=True)
        rows = self.get(kind, u.tolist(), dim)
        if not rows:
            return torch.zeros(0, dim, dtype=self.dtype)
        return self.mats[kind][torch.tensor(rows)[torch.from_numpy(inv.reshape(-1))]]

    def lookup(self, kind, values, dim=None, unique=None):
        """`host`, on the device."""
        return self.host(kind, values, dim, unique).to(self.device)


def unique(table, field, col=None):
    """np.unique(values, return_inverse=True) of a table's field, or of its column `col`, computed once and kept
    on the table while the field is the same array."""
    arr = getattr(table, field)
    memo = table.__dict__.setdefault("_unique", {})
    hit = memo.get((field, col))
    if hit is None or hit[0] is not arr:
        hit = memo[(field, col)] = (arr, *np.unique(arr if col is None else arr[:, col], return_inverse=True))
    return hit[1], hit[2]


def joint_table(a, b):
    """The two evidence tables a and b as one table, a's rows then b's, kept on a while the two are the same."""
    memo = a.__dict__.setdefault("_unique", {})
    arrays = tuple(getattr(x, f) for x in (a, b) for f in ROW_FIELDS)
    hit = memo.get(("joint",))
    if hit is None or len(hit[0]) != len(arrays) or any(x is not y for x, y in zip(hit[0], arrays)):
        jt = Table(**{**a.__dict__, "relation": "evidence", "largest": max(a.largest, b.largest),
                      **{f: np.concatenate([getattr(a, f), getattr(b, f)]) for f in ROW_FIELDS}})
        hit = memo[("joint",)] = (arrays, jt)
    return hit[1]


# ---------------------------------------------------------------- field labels and sources, for the masked loss

COMPUTED, INFERRABLE, SOLE, REMOTE = 0, 1, 2, 3   # a field's label: computed from its sources; inferrable as a
# distribution; neither; computed with no source in its own table or a grid table
FIELD_LABELS = ("computed", "inferrable", "sole", "remote")
STEP_KINDS = ("program", "output", "prior")   # the order in which "alternate" cycles them
LOSS_PART = {"program": "program", "output": "program", "prior": "prior"}   # an output step hides computed fields
EVIDENCE_COLOR = 5                     # the Color field of an evidence row, after Example (1) and Position (4)


def evidence_input(tables):
    """The program's ex_input table, or None."""
    return next((t for t in tables if t.relation == "ex_input"), None)


def output_labels(ex_input, ex_output):
    """The label of each ex_output row's Color field, [n], and whether it is dependent, [n] bool. A field is
    computed where its value occurs among the colors of the same example's input or in another train example's
    output, and sole elsewhere. Where the export gives the provenance (`color_dependent` not None), the column
    decides which computed fields are dependent: none where the output relation's Color column reaches only the
    input, and each whose value another train example's output shows where it reaches a DET or ex_output. Without
    it, a computed field is dependent where its value occurs in another train example's output and not in its own
    input. A dependent field's sources are the fields of the other train outputs that hold its value. The column
    level cannot say which values of one column come from which source, so the sole test stays by occurrence per
    row. Kept on ex_output while both tables' cells are the same arrays."""
    memo = ex_output.__dict__.setdefault("_unique", {})
    in_cells = None if ex_input is None else ex_input.cells
    hit = memo.get(("output labels",))
    if hit is None or hit[0] is not ex_output.cells or hit[1] is not in_cells:
        pair = lambda cells: cells[:, 0].astype(np.int64) * 1024 + cells[:, EVIDENCE_COLOR]
        u, inv = np.unique(pair(ex_output.cells), return_inverse=True)
        ex, color = u // 1024, u % 1024
        free = np.isin(u, pair(in_cells)) if in_cells is not None else np.zeros(len(u), bool)
        shown = np.array([(color == v).sum() > 1 for v in color], bool)   # (example, color) pairs are distinct
        labels = np.where(free | shown, COMPUTED, SOLE).astype(np.int8)[inv.reshape(-1)]
        dep = {None: ~free & shown, True: shown, False: np.zeros(len(u), bool)}[ex_output.color_dependent]
        hit = memo[("output labels",)] = (ex_output.cells, in_cells, labels, dep[inv.reshape(-1)])
    return hit[2], hit[3]


def provenance(tables):
    """Whether the derived tables of a program hold the export's column-level provenance (`Table`)."""
    return any(t.flows is not None for t in tables if not t.evidence)


def column_labels(tables, j):
    """The label of each column of derived table j of a program, from the export's provenance: inferrable in a
    candidate key (`keys`), and where every flow of the column is a constant or a lib name, or the column has none;
    remote where the column is computed and none of the (table, column) pairs of `column_sources` is in table j or
    in an evidence table: its sources are all in derived tables other than j, which j's rows see only as those
    tables' K pooled vectors, or it has no source pair (its flows name no table, or only j's own export table);
    computed elsewhere."""
    t, src = tables[j], column_sources(tables)[j]
    memo = t.__dict__.setdefault("_unique", {})
    hit = memo.get(("column labels",))
    if hit is None or hit[0] is not t.flows or hit[1] is not src:
        lab = np.full(len(t.types), COMPUTED, np.int8)
        for key in t.keys:
            lab[key] = INFERRABLE
        # a column whose flows are all constants or lib names, or that has none
        sourced = np.zeros(len(t.types), bool)
        sourced[t.flows[(t.flows[:, 1] != FLOW_CONSTANT) & (t.flows[:, 1] != FLOW_LIB_NAME), 0]] = True
        lab[~sourced] = INFERRABLE
        for c, s in enumerate(src):
            if lab[c] == COMPUTED and not any(i == j or tables[i].evidence for i, _ in s):
                lab[c] = REMOTE
        hit = memo[("column labels",)] = (t.flows, src, lab)
    return hit[2]


def field_labels(tables):
    """The label of each field of each table of a program, [n, columns] int8, read-only (None for a table without
    rows). In
    the evidence tables, Example and Position fields and ex_input's Color fields are inferrable, and ex_output's
    Color fields are labelled by `output_labels`. In a derived table that holds the export's provenance, a field
    takes its column's label (`column_labels`: computed where a source is in its own table or in a grid table,
    remote where it has no such source); in one that does not, a field is computed where it
    is `identifiable`, and inferrable elsewhere, as a key-like field whose target is a set. A program step hides
    remote fields only with `mask_remote` (`draw_masks`)."""
    out = []
    for j, t in enumerate(tables):
        if not t.n or not len(t.types):
            out.append(None)
        elif t.evidence:
            # Position of ex_output is a key field. The output relation's `output_position` column, whose flows
            # reach ex_input or a DET, would let the Position fields be labelled computed, free or dependent, as
            # the Color fields are, once a hidden Position has a head that can predict it from those sources.
            lab = np.full((t.n, len(t.types)), INFERRABLE, np.int8)
            if t.relation == "ex_output":
                lab[:, t.types.index("Color")] = output_labels(evidence_input(tables), t)[0]
            out.append(lab)
        elif t.flows is not None:
            out.append(np.broadcast_to(column_labels(tables, j), (t.n, len(t.types))))   # a read-only view
        else:
            out.append(np.where(FeatureEncoder.identifiable(t), COMPUTED, INFERRABLE).astype(np.int8))
    return out


def table_sources(tables):
    """The indices of each table's source tables in its program, as sets. ex_input has none, and ex_output's is
    ex_input. A derived table's are the evidence tables, and the tables of the relations of its DETs
    (`det_relations`), each relation's latest group of `table_groups` (every assignment's table), other than its own
    group. `draw_masks` takes these sources for a program whose tables do not hold the export's column-level
    provenance, and `column_sources` for one whose tables do."""
    evidence = {i for i, t in enumerate(tables) if t.evidence}
    group = table_groups(tables)
    members = {}
    for i, g in enumerate(group):
        members.setdefault(g, set()).add(i)
    by_relation = {t.relation: members[group[i]] for i, t in enumerate(tables) if not t.evidence}
    out = []
    for i, t in enumerate(tables):
        if t.evidence:
            out.append({j for j in evidence if tables[j].relation == "ex_input"} if t.relation == "ex_output" else set())
            continue
        dets = {int(m.group(1)) for d in getattr(t, "det_relations", []) if (m := re.fullmatch(r"slot (\d+)", d))}
        out.append(evidence | (set().union(*(by_relation[r] for r in dets if r in by_relation)) - members[group[i]]))
    return out


def column_sources(tables):
    """The sources of each column of each table of a program, from the export's column-level provenance: per
    table, per column, the set of (table index, column) pairs of the program that its flows name, one level of
    sources and not their sources. A flow names every Table of its source's export table (`table_groups`); a source
    in the column's own export table, a source the case holds no table for, and the example of a derived source's
    entry are left out, and the example of an evidence entry is its Example column. An evidence table's columns
    have none: the dependent fields of ex_output keep their sources by `keep_occurrence`. A table without columns
    gives []. The Tables of one export table share one list, which a caller does not change. Kept on the first
    table while the program holds the same Tables."""
    memo = tables[0].__dict__.setdefault("_unique", {}) if tables else {}
    hit = memo.get(("column sources",))
    if hit is not None and len(hit[0]) == len(tables) and all(x is y for x, y in zip(hit[0], tables)):
        return hit[1]
    of = {}
    for i, t in enumerate(tables):
        e = GRID_TABLES.get(t.relation) if t.evidence else t.export_table
        if e is not None:
            of.setdefault(e, []).append(i)
    out, by_export = [], {}
    for t in tables:
        if t.evidence or t.flows is None:
            out.append([set() for _ in t.types]); continue
        if t.export_table not in by_export:
            cols = [set() for _ in t.types]
            for c, st, sc in set(map(tuple, t.flows[:, [0, 2, 3]].tolist())):
                if st < 0 or st == t.export_table:
                    continue
                for j in of.get(st, []):
                    if sc >= 0:
                        cols[c].add((j, sc))
                    elif sc == -2 and tables[j].evidence:
                        cols[c].add((j, 0))
            by_export[t.export_table] = cols
        out.append(by_export[t.export_table])
    if tables:
        memo[("column sources",)] = (list(tables), out)
    return out


def source_tables(tables):
    """The source tables whose rows each derived table of a program attends to with `--enc-source-rows`: per table,
    per column, the (table index, column) pairs of `column_sources` whose table is a derived table with rows that
    stands earlier in the program; [] per column for an evidence table and for a program without the export's
    column-level provenance. The evidence tables are keys of every table already. Gives (per table, its source
    tables' indices in order; per table, per column, its pairs)."""
    if not provenance(tables):
        return [[] for _ in tables], [[[] for _ in t.types] for t in tables]
    cs = column_sources(tables)
    tabs, pairs = [], []
    for t, (tb, cols) in enumerate(zip(tables, cs)):
        keep = lambda j: j < t and not tables[j].evidence and tables[j].n > 0
        pc = [[] if tb.evidence else sorted((j, sc) for j, sc in col if keep(j)) for col in cols]
        pairs.append(pc)
        tabs.append(sorted({j for col in pc for j, _ in col}))
    return tabs, pairs


def keep_occurrence(ex_output, mask, dependent):
    """Makes visible, in place, each hidden dependent Color field of ex_output (`dependent` [n]) whose value no
    other example's output shows in a visible field, one field at a time in row order, so that each hidden
    dependent field keeps a visible source."""
    col = ex_output.types.index("Color")
    ex, color = ex_output.cells[:, 0], ex_output.cells[:, EVIDENCE_COLOR]
    for r in np.flatnonzero(mask[:, col] & dependent):
        if not (~mask[:, col] & (color == color[r]) & (ex != ex[r])).any():
            mask[r, col] = False


def preflight(programs, frac, cap, seed=0, mask_remote=False):
    """Runs the masked loss's data path on each program of `programs` ([(name, tables)]) with no model, and raises
    DataFault on the first offender, with the program, the table, its relation and types: `field_labels` gives
    one label per field, every source of `column_sources` is a column of its table, and `draw_masks` at `frac` and
    `cap` and with `mask_remote`, once per step kind, gives each table a mask of its shape that hides only present
    fields of rows that are not markers and of the step kind's label (a program step also hides remote fields
    with `mask_remote`), hides ex_output fields alone in an output step, and in a program step hides no field
    whose source (column-level with the export's provenance, table-level without) hides fields and, without
    `mask_remote`, hides no field whose column has sources, all in other derived tables. Gives the number of fields of each label, by label name, over the programs."""
    gen = torch.Generator().manual_seed(seed)
    count = {x: 0 for x in FIELD_LABELS}
    for name, ts in programs:
        fail = lambda j, what: DataFault(f"preflight: {name} table {j} relation {ts[j].relation} export table "
                                         f"{ts[j].export_table} types {ts[j].types}: {what}")
        labs, prov = field_labels(ts), provenance(ts)
        sources = column_sources(ts) if prov else table_sources(ts)
        seen = set()   # the source lists checked: the Tables of one export table share one
        for j, (t, lab) in enumerate(zip(ts, labs)):
            if lab is not None and lab.shape != (t.n, len(t.types)):
                raise fail(j, f"labels of shape {lab.shape}")
            if lab is not None:
                for x, n in zip(*np.unique(lab, return_counts=True)):
                    count[FIELD_LABELS[x]] += int(n)
            if prov and id(sources[j]) not in seen:
                seen.add(id(sources[j]))
                for c, src in enumerate(sources[j]):
                    if any(not 0 <= d < len(ts[i].types) for i, d in src):
                        raise fail(j, f"column {c} has sources {sorted(src)} outside their tables' columns")
        for kind in STEP_KINDS:
            ms = FeatureEncoder.draw_masks(None, ts, frac, cap, gen, kind, mask_remote)
            want = INFERRABLE if kind == "prior" else COMPUTED
            allowed = (want, REMOTE) if mask_remote and kind == "program" else (want,)
            hidden = {(j, c) for j, m in enumerate(ms) if m is not None for c in np.flatnonzero(m.any(0)).tolist()}
            held = {j for j, _ in hidden}
            for j, (t, m, lab) in enumerate(zip(ts, ms, labs)):
                if m is None or not m.any():
                    continue
                if m.shape != (t.n, len(t.types)):
                    raise fail(j, f"{kind} mask of shape {m.shape}")
                if (m & ~(t.present & ~t.marker[:, None])).any() or not np.isin(lab[m], allowed).all():
                    raise fail(j, f"a {kind} step hides a field it may not")
                if kind == "program" and prov and not t.evidence and not mask_remote and any(
                        sources[j][c] and not any(i == j or ts[i].evidence for i, _ in sources[j][c])
                        for c in np.flatnonzero(m.any(0))):
                    raise fail(j, "a program step hides a field whose sources are all in other derived tables")
                if kind == "output" and t.relation != "ex_output":
                    raise fail(j, "an output step hides a field outside ex_output")
                if kind == "program" and (any(sources[j][c] & hidden for c in np.flatnonzero(m.any(0))) if prov
                                          else sources[j] & held):
                    raise fail(j, "a program step hides a field whose source hides fields")
    return count


GROUPS = {"Number": "number", "Color": "color", "Example": "example", "Ident": "ident", "Box": "box"}


def to_device(t, device):
    """A host tensor on the device, without a wait on the copy."""
    device = torch.device(device)
    if device.type == "cuda":
        return t.pin_memory().to(device, non_blocking=True)
    return t.to(device)


class Pack:
    """Host arrays bound for the device, which `load` moves there in one copy per dtype; an array's handle then
    gives its view on the device."""
    def __init__(self):
        self.parts, self.size, self.flat = {}, {}, None

    def add(self, a, dtype):
        t = torch.as_tensor(a).to(dtype).reshape(-1)
        off = self.size.get(dtype, 0)
        self.parts.setdefault(dtype, []).append(t)
        self.size[dtype] = off + t.numel()
        return dtype, off, tuple(np.shape(a))

    def load(self, device):
        self.flat = {d: to_device(torch.cat(ts) if len(ts) > 1 else ts[0], device) for d, ts in self.parts.items()}
        self.parts = {}

    def __getitem__(self, handle):
        d, off, shape = handle
        return self.flat[d][off:off + math.prod(shape)].view(shape)


# The cost of one more batch of a level, against the attention scores and rows that padding adds; a level's tables are
# split into the batches of least total cost (`batches`).
BATCH_COST = 2_000_000   # in attention scores
ROW_COST = 100           # a row's maps, in attention scores
# The equality weights of the source keys and of the pointer heads (`--enc-source-rows`, `--enc-ptr-equality`) enter
# times these gains, so that a step of the optimizer moves the term by that many times the learning rate.
SOURCE_EQ_GAIN, POINTER_EQ_GAIN = 30.0, 30.0
# A batch of fewer keys B (N + P + E) skips the checkpoint, and keeps at most 0.1 GB more at c 32, 2 layers, bf16.
CHECKPOINT_MIN = 2048


def batches(rows, keys):
    """The tables of a level as batches: rows [n] the row count of each and keys [n] the keys each row attends to
    beside the table's rows. A batch pads its tables to the most rows of any, rounded up to a multiple of 8, and its
    keys to the most of any; it costs BATCH_COST plus its padded scores and rows. Gives the partition of least cost
    among those that cut the tables in order of their row count, as lists of indices in the given order."""
    order = sorted(range(len(rows)), key=lambda i: (rows[i], i))
    best, cut = [0.0], [0]
    for e in range(1, len(order) + 1):
        n_pad, top, cost = up8(rows[order[e - 1]]), 0, None
        for s in range(e - 1, -1, -1):
            top = max(top, keys[order[s]])
            c = best[s] + BATCH_COST + (e - s) * n_pad * (n_pad + top + ROW_COST)
            if cost is None or c < cost:
                cost, at = c, s
        best.append(cost); cut.append(at)
    out, e = [], len(order)
    while e:
        out.append(sorted(order[cut[e]:e]))
        e = cut[e]
    return out[::-1]


class Batch:
    """What each Block of one batch of a level's tables reads beside the rows: `level`; `mask` [B, 1, 1, keys], the
    keys each table's rows attend to (its rows, its pooled vectors, its evidence rows); `prev` [B, P, 21, c], the
    earlier pooled vectors with their recency; `eq_q` [B, N, 1, D] and `eq_k` (per layer, [B, N + P, H, D]), the
    equality term's query and key channels with the zeros that pad q and k; `ev`, the `EvidenceKeys` of the batch's
    evidence rows; `flex`, the groups of the flex equality term. The per-layer
    parts are views that `unbind` gives of one tensor of every layer, whose backward pass builds that tensor's
    gradient once, where a view per layer by indexing builds a gradient of every layer's size at each layer."""
    def __init__(self, level, mask, prev):
        self.level, self.mask, self.prev = level, mask, prev
        self.eq_q = self.eq_k = self.ev = self.flex = self.src = self.code_v = self.code_layer = None


class Evidence:
    """The rows of each program's evidence tables after each layer, kept for the later tables of the program, and
    their keys and values at each layer, computed once for every program each time evidence is added. The places of
    the rows in the store are planned on the host for every level first (`plan`, `close_level`, `load`); the rows
    themselves join it as each level's batches run (`add`, `join_level`)."""
    def __init__(self, n_programs, layers):
        self.layers = [[] for _ in range(layers)]   # per layer, each batch's rows after it that hold evidence
        self.size = 0                                # the rows of the store, those batches' rows flat
        self.of = [[] for _ in range(n_programs)]    # per program, its evidence rows' places in the store
        self.pending, self.version, self.done = [], 0, 0
        self.ran, self.kv = [], None

    def rows(self, p):
        return sum(len(r) for r in self.of[p])

    def plan(self, members, B, N):
        """A batch of B tables of N rows, with its evidence tables (program, batch index, rows); they join the store
        when the level closes, so that no table of the level sees them."""
        self.pending.append((members, B, N))

    def close_level(self):
        for members, B, N in self.pending:
            for p, b, n in members:
                self.of[p].append(self.size + b * N + np.arange(n))
            self.size += B * N
            self.version += 1
        self.pending = []

    def stale(self):
        return self.done != self.version

    def load(self):
        """The rows that `compute` takes at this point of the plan (`all_rows`)."""
        self.done = self.version
        return self.all_rows()

    def add(self, layers):
        """A planned batch's rows after each layer [B, N, 21, c], in the order of `plan`; they join the store when
        the level's batches have run (`join_level`)."""
        self.ran.append(layers)

    def join_level(self):
        for layers in self.ran:
            for l, x in enumerate(layers):
                self.layers[l].append(x.reshape(-1, *x.shape[2:]))
        self.ran = []

    def all_rows(self):
        return np.concatenate([r for rs in self.of for r in rs])

    def key_index(self, programs, E):
        """The places in `kv` of the evidence rows of each of `programs`, in `all_rows` order, each padded to E
        with the place of kv's zero row: [len(programs), E]."""
        sizes = [self.rows(p) for p in range(len(self.of))]
        start = np.cumsum([0] + sizes)
        idx = np.full((len(programs), E), start[-1], np.int64)
        for b, p in enumerate(programs):
            idx[b, :sizes[p]] = start[p] + np.arange(sizes[p])
        return idx

    def compute(self, enc, sel):
        """The keys and values of the rows `sel` (`load`) at each layer, then one row of zeros, `kv`, and
        `layer_kv`: per layer, the view of kv [rows + 1, H (w + wv)]."""
        kv = []
        for l, (blk, mats) in enumerate(zip(enc.blocks, enc.mats)):
            rows = torch.cat(self.layers[l]) if len(self.layers[l]) > 1 else self.layers[l][0]
            h = blk.n1(rows.index_select(0, sel))
            kv.append(F.linear(h.reshape(len(h), -1), mats["kv"], mats["bkv"]))
        self.kv = F.pad(torch.stack(kv, 1), (0, 0, 0, 0, 0, 1))                       # [rows + 1, L, H (w + wv)]
        self.layer_kv = self.kv.unbind(1)
        self.H, self.W, self.Wv = enc.blocks[0].heads, enc.mats[0]["W"], enc.mats[0]["Wv"]


class EvidenceKeys:
    """A batch's evidence keys and values, built at each layer, inside the Block call, by one index_select of
    `Evidence.layer_kv` at `index` [B E] (`Evidence.key_index`), whose padding places take kv's zero row. A
    checkpointed Block call thus keeps the index and the shared keys and values of `Evidence.kv` for its backward
    pass, and builds the batch's padded copy again there."""
    def __init__(self, ev, index, B, E, pad):
        self.layer_kv, self.index, self.B, self.E, self.pad = ev.layer_kv, index, B, E, pad
        self.H, self.W, self.Wv = ev.H, ev.W, ev.Wv

    def layer(self, l):
        """The keys [B, E, H, w] with `pad` zero channels and the values [B, E, H, wv] at layer l."""
        H, W, Wv, B, E = self.H, self.W, self.Wv, self.B, self.E
        k, v = self.layer_kv[l].index_select(0, self.index).split([H * W, H * Wv], -1)
        k = k.reshape(B, E, H, W)
        return (F.pad(k, (0, self.pad)) if self.pad else k), v.reshape(B, E, H, Wv)


class SourceRows:
    """With `--enc-source-rows`, the rows of the derived tables that are sources of a later table of their program
    (`source_tables`), after each layer, as their keys and values at each layer: one chunk [rows, L, H (w + wv)] per
    level that holds such tables, computed once when that level's batches have run. `place` gives each source table's
    (chunk, first row, rows), planned on the host for every level first; `sizes` each chunk's rows."""
    def __init__(self):
        self.place, self.sizes, self.chunks, self.ran, self.codes = {}, [], [], [], {}

    def plan_level(self, tables):
        """The level's source tables, [(program, table, rows)] in the order their batches run, as one chunk."""
        if not tables:
            return
        o = 0
        for p, t, n in tables:
            self.place[(p, t)] = (len(self.sizes), o, n)
            o += n
        self.sizes.append(o)

    def add(self, layers, sel):
        """A batch's rows after each layer [B, N, 21, c], of which the rows `sel` [r] of B N are of source tables."""
        self.ran.append([x.reshape(-1, *x.shape[2:]).index_select(0, sel) for x in layers])

    def join_level(self, enc):
        if not self.ran:
            return
        kv = []
        for l, (blk, mats) in enumerate(zip(enc.blocks, enc.mats)):
            rows = torch.cat([r[l] for r in self.ran]) if len(self.ran) > 1 else self.ran[0][l]
            h = blk.n1(rows)
            kv.append(F.linear(h.reshape(len(h), -1), mats["kv"], mats["bkv"]))
        self.chunks.append(torch.stack(kv, 1))
        self.ran = []

    def key_index(self, sources, Es):
        """The chunks a batch's source keys come from, and the place of each key in their concatenation, then a zero
        row: per table of the batch, its source tables' rows in order, padded to Es with the zero row's place."""
        involved = sorted({self.place[s][0] for src in sources for s in src})
        base = dict(zip(involved, np.cumsum([0] + [self.sizes[k] for k in involved])))
        zero = sum(self.sizes[k] for k in involved)
        idx = np.full((len(sources), Es), zero, np.int64)
        for b, src in enumerate(sources):
            o = 0
            for s in src:
                k, first, n = self.place[s]
                idx[b, o:o + n] = base[k] + first + np.arange(n)
                o += n
        return involved, idx


class SourceKeys:
    """A batch's source keys and values at each layer, built inside the Block call, as `EvidenceKeys` builds the
    evidence keys: by one index_select of the involved chunks of `SourceRows` and a zero row, at `index` [B Es]. The
    equality channels of the keys are built there too, from `eq` (the places in [B, Es, F] of the codes, the place of
    each one's weight among the slot pairs, and its value; or None) under the weights `w` [L, H, slots, slots], F the
    batch's equality places, then `pad` zeros."""
    def __init__(self, store, involved, index, B, Es, eq, F_, pad, w, H, W, Wv):
        self.chunks = [store.chunks[k] for k in involved]
        self.index, self.B, self.Es, self.eq, self.F, self.pad, self.w = index, B, Es, eq, F_, pad, w
        self.H, self.W, self.Wv = H, W, Wv

    def layer(self, l):
        H, W, Wv, B, Es = self.H, self.W, self.Wv, self.B, self.Es
        kv = torch.cat([c[:, l] for c in self.chunks] + [self.chunks[0].new_zeros(1, H * (W + Wv))])
        k, v = kv.index_select(0, self.index).split([H * W, H * Wv], -1)
        k, v = k.reshape(B, Es, H, W), v.reshape(B, Es, H, Wv)
        if self.F:
            place, widx, val = self.eq
            contrib = self.w[l].reshape(H, -1).index_select(1, widx) * val                     # [H, entries]
            eqk = contrib.new_zeros(H, B * Es * self.F).index_add_(1, place, contrib)
            k = torch.cat([k, eqk.view(H, B, Es, self.F).permute(1, 2, 0, 3).to(k.dtype)], -1)
        return (F.pad(k, (0, self.pad)) if self.pad else k), v


class FeatureEncoder(nn.Module):
    def __init__(self, embed, in_index, id_dim, orientations, K=4, layers=2, c=32, heads=4, mlp=2, examples=16,
                 code_dim=32, number_range=(-64, 1023), margin_range=(-64, 255), recency=16, gram=16, equality="codes", source_rows=False, ptr_equality=False):
        """`examples` is the width of an Example's one-hot equality code, more than any example index; `mlp` the
        width of the feed-forward layers, in multiples of c; `gram` the channels each Gram matrix of the readout
        projects to; `equality` the means of the equality term, one of EQUALITY_MODES; `source_rows`, whether each
        derived table's rows attend also to the rows of its source tables (`source_tables`); `ptr_equality`, whether the
        pointer heads take equality terms (`masked_fields`)."""
        super().__init__()
        assert equality in EQUALITY_MODES, equality
        assert not (source_rows and equality == "flex"), "the source rows' equality term takes codes or random"
        self.equality, self.source_rows, self.ptr_equality = equality, source_rows, ptr_equality
        # the width of a row's pointer codes: a Color's one-hot, an Example's, an Ident's random code, padded to 8
        self.ptr_codes = up8(10 + examples + code_dim) if ptr_equality and source_rows else 0
        hidden = embed.weight.shape[1]
        self.embed, self.in_index = embed, in_index   # the LM's embedding, shared, and its index
        self.K, self.c, self.code_dim, self.examples = K, c, code_dim, examples
        self.slot_names = sorted((n for n in in_index if re.fullmatch(r":\d+", n)), key=lambda n: int(n[1:]))
        self.slots = len(self.slot_names)
        self.number_range, self.margin_range, self.max_recency = number_range, margin_range, recency
        self.slot_proj = nn.Linear(hidden, 3 * c)                 # column slot: invariant, edge and pair bindings
        self.slot_norm = nn.LayerNorm(c)
        self.rel_id = nn.Linear(id_dim, c, bias=False)            # a declared relation: its identifier
        self.rel_tok = nn.Linear(hidden, c, bias=False)           # a fact relation: its token's embedding
        self.rel_table = nn.Embedding(1024, c)                    # a slot with neither
        self.type_emb = nn.Embedding(len(TYPE_NAMES), c)
        self.number = nn.Embedding(number_range[1] - number_range[0] + 1, c)
        self.margin = nn.Embedding(margin_range[1] - margin_range[0] + 1, c)
        self.type_edge = nn.Parameter(torch.randn(len(TYPE_NAMES), c))   # an orientation's edge indicator vector
        self.type_pair = nn.Parameter(torch.randn(len(TYPE_NAMES), c))   # its first pairwise matrix's vector
        self.type_pair_ref = nn.Parameter(torch.randn(len(TYPE_NAMES), c))   # its second's (a subgroup's reflections)
        self.example_kind = nn.Embedding(3, c)
        self.bind_example, self.bind_assignment, self.bind_model = (nn.Parameter(torch.randn(c)) for _ in range(3))
        self.recency = nn.Embedding(recency + 1, c)              # an earlier table's distance back, on its invariant channels
        self.blocks = nn.ModuleList(Block(c, heads, self.slots, mlp, source_rows) for _ in range(layers))
        self.pool = Pool(c, heads, K, mlp)
        # an unseen entry's marker row, or a table the encoder cannot see, on its invariant channels: a fixed vector,
        # not learned, drawn from its own generator
        self.register_buffer("unseen", torch.randn(c, generator=torch.Generator().manual_seed(7)) / math.sqrt(c))
        self.readout = Readout(c, gram)
        self.cross_norm = nn.LayerNorm(readout_width(c, gram))
        self.cross = nn.Linear(readout_width(c, gram), hidden)
        std = embed.weight.detach().float().std().item()
        nn.init.normal_(self.cross.weight, std=std / math.sqrt(readout_width(c, gram))); nn.init.zeros_(self.cross.bias)
        codes = sorted(orientations)
        self.orient_index = {code: i for i, (code, _) in enumerate(codes)}
        # the index of each code, by code, and 0 for any other value, as orient_index.get(code, 0)
        assert all(code >= 0 for code, _ in codes)
        self.orient_lut = np.zeros(max((code for code, _ in codes), default=0) + 1, np.int64)
        for code, i in self.orient_index.items():
            self.orient_lut[code] = i
        feats = [orientation_features(name) for _, name in codes]
        self.register_buffer("orient_edge", torch.tensor(np.stack([f[0] for f in feats])), persistent=False)
        self.register_buffer("orient_pair", torch.tensor(np.stack([f[1] for f in feats])), persistent=False)
        self.register_buffer("orient_ref", torch.tensor(np.stack([f[2] for f in feats])), persistent=False)
        self.orient_np = tuple(np.stack([f[i] for f in feats]) for i in range(3))   # the same, on the host
        self.S = None
        self.orient_name = {code: name for code, name in codes}
        with torch.random.fork_rng(devices=[]):   # so that the language model's draws stay as without these parameters
            torch.manual_seed(1)
            self.mask_inv = nn.Parameter(torch.randn(len(TYPE_NAMES), c))   # a masked value, on the invariant channels
            self.mask_edge = nn.Parameter(torch.randn(c))                   # on every edge
            self.mask_pair = nn.Parameter(torch.randn(len(PAIR_ORBITS), c))  # per orbit of edge pairs
            self.heads = MaskedHeads(c, self.slots, heads, ptr_equality, source_rows)
        self.cand_feats = {}
        # with gradients on, recompute each Block's activations in the backward pass rather than keep them, in a batch
        # of at least CHECKPOINT_MIN keys: the Block draws no random numbers, so the recomputation gives the same values
        self.checkpoint = False
        self.group = 0   # the programs each encoder call takes, all where 0 (see `chunks`)

    def candidate_features(self, ty):
        """The candidates of an orientation type, and their edge indicators [C, 4] and pairwise matrices [C, 16]."""
        dev, dt = self.cross.weight.device, self.cross.weight.dtype
        key = (ty, dev, dt)   # kept per device and dtype, so that a copy of the encoder in another builds its own
        if key not in self.cand_feats:
            names = CANDIDATES[ty]
            f = [orientation_features(n) for n in names]
            t = lambda i: torch.tensor(np.stack([x[i].reshape(-1) for x in f]), device=dev, dtype=dt)
            self.cand_feats[key] = (names, t(0), t(1), t(2))
        return self.cand_feats[key]

    def eq_linears(self):
        return [m for m in self.modules() if isinstance(m, EqLinear)]

    def prepare(self):
        """Builds, once per call, every equivariant map's matrix, the attention maps of the Blocks and the pooling in
        head layout (`mats`), the pooling's queries and the bindings of every column slot."""
        # under autocast, each matrix is cast once here: autocast caches the casts of leaf tensors alone, so it would
        # otherwise cast, and save for the backward pass, a new copy at every call
        dev = self.cross.weight.device
        cast = torch.get_autocast_dtype(dev.type) if torch.is_autocast_enabled(dev.type) else None
        for m in self.eq_linears():
            m.M, m.b = m.matrix(), m.bias_vector()
        H, c = self.blocks[0].heads if len(self.blocks) else self.pool.heads, self.c
        W = NPOS * (c // H)
        Wv = W if self.equality == "flex" else up8(W)
        index = lambda width: head_index(c, H, width).to(dev)
        iq, iv, i8 = index(W), index(Wv), index(up8(W))
        heads = []   # the attention maps in head layout, from the matrices before any cast
        for blk in self.blocks:
            q, bq = head_rows(blk.q, iq, 1 / math.sqrt(W))
            (k, bk), (v, bv) = head_rows(blk.k, iq), head_rows(blk.v, iv)
            o, bo = head_cols(blk.o, iv)
            heads.append(dict(qkv=torch.cat([q, k, v]), bqkv=torch.cat([bq, bk, bv]), kv=torch.cat([k, v]),
                              bkv=torch.cat([bk, bv]), o=o, bo=bo))
        p = self.pool
        q, bq = head_rows(p.q, i8, 1 / math.sqrt(W))
        (k, bk), (v, bv) = head_rows(p.k, i8), head_rows(p.v, i8)
        o, bo = head_cols(p.o, i8)
        heads.append(dict(q=q, bq=bq, kv=torch.cat([k, v]), bkv=torch.cat([bk, bv]), o=o, bo=bo))
        if cast is not None:
            for m in self.eq_linears():
                m.M, m.b = m.M.to(cast), None if m.b is None else m.b.to(cast)
            heads = [{k: v.to(cast) for k, v in d.items()} for d in heads]
        ff = lambda m: dict(f1=m.f1.M, bf1=m.f1.b, f2=m.f2.M, bf2=m.f2.b)
        self.mats = [dict(**d, **ff(blk), W=W, Wv=Wv) for d, blk in zip(heads, self.blocks)]
        d = heads[-1]
        seeds = p.seeds()
        self.pool_mats = dict(kv=d["kv"], bkv=d["bkv"], o=d["o"], bo=d["bo"], **ff(p), Wq=up8(W), Wv=up8(W), seeds=seeds,
                              q=F.linear(p.n0(seeds).reshape(self.K, -1), d["q"], d["bq"]).view(self.K, H, -1))
        ids = torch.tensor([self.in_index[n] for n in self.slot_names], device=dev)
        self.S = self.slot_norm(self.slot_proj(self.embed(ids)).reshape(self.slots, 3, self.c))
        self.eq_all = torch.stack([blk.eq for blk in self.blocks]) if len(self.blocks) else None   # [L, H, slots, slots]
        if self.source_rows:
            self.src_eq_all = torch.stack([blk.src_eq for blk in self.blocks]) * SOURCE_EQ_GAIN

    def prepared(self):
        """The matrices `prepare` built: each equivariant map's and the head layout maps."""
        mats = [m.M for m in self.eq_linears()]
        mats += [v for d in self.mats + [self.pool_mats] for k, v in d.items() if torch.is_tensor(v) and v.dim() == 2
                 and k in ("q", "qkv", "kv", "o")]
        return mats

    def release(self):
        for m in self.eq_linears():
            m.M = m.b = None
        self.S = self.eq_all = self.src_eq_all = None
        self.mats, self.pool_mats = [], {}

    def plan(self, tb, ids, field_mask, rel_index):
        """The host side of the row tokens of a table's rows, and of its equality groups, for `row_tokens` and the equality term: the
        identifiers its values take, drawn from `ids` in a fixed order, and the indices that place each part. A field
        that `field_mask` [n, columns] marks is hidden: its features are the learned mask vector of its channel group,
        bound to its column slot, and its equality code is zero. `rel_index` [n] is each row's relation vector."""
        n, c = tb.n, self.c
        ty_n, num_lo, mar_lo = len(TYPE_NAMES), self.number_range[0], self.margin_range[0]
        n_num, n_mar = self.number.num_embeddings, self.margin.num_embeddings
        one_hot = self.equality == "codes"
        cells, present = tb.cells, tb.present
        hidden = np.zeros_like(present) if field_mask is None else field_mask
        code_present = present & ~hidden
        hv = torch.zeros(n, 4, c, dtype=ids.dtype)   # an example's, the assignment's, the model's identifier; marker
        ex = tb.example
        hv[:, 0] = ids.host("example", ex, unique=unique(tb, "example")) * torch.from_numpy(ex >= 0)[:, None]
        a = tb.assignment
        for d in range(a.shape[1]):
            hv[:, 1] += ids.host("det value", a[:, d], unique=unique(tb, "assignment", d)) * torch.from_numpy(a[:, d] >= 0)[:, None]
        if (tb.model != 0).any():
            hv[:, 2] = ids.host("model", tb.model, unique=unique(tb, "model"))
        hv[:, 3] = torch.from_numpy(tb.marker)[:, None]
        A, Bc, Ed, Pr = [], [], [], []   # cells: invariant; identifier values; edge; pairwise
        groups = {}
        o = 0
        for i, ty in enumerate(tb.types):
            w = width(ty)
            v = cells[:, o:o + w]; col = o; o += w
            rows = np.flatnonzero(present[:, i])
            hid = hidden[rows, i]
            ty_i = TYPE_NAMES.index(ty)
            pos = tb.positions[i]
            pidx = np.full(len(rows), n_num + ty_n)                       # the zero row of the value table
            code = None
            if ty == "Number":
                pidx = np.where(hid, n_num + ty_i, np.clip(v[rows, 0], *self.number_range) - num_lo)
                if one_hot:
                    code = ("dense", ids.host("number code", v[:, 0], self.code_dim, unique(tb, "cells", col)))
            elif ty in ("Color", "Example", "Ident"):
                pidx = np.where(hid, n_num + ty_i, pidx)
                vec = ids.host(ty.lower(), v[:, 0], unique=unique(tb, "cells", col))
                keep = rows[~hid]
                Bc.append((keep, pos, vec[torch.from_numpy(keep)]))
                if not one_hot:
                    pass
                elif ty == "Ident":
                    code = ("dense", ids.host("ident code", v[:, 0], self.code_dim, unique(tb, "cells", col)))
                else:
                    width_ = 10 if ty == "Color" else self.examples
                    assert 0 <= v[:, 0].min() and v[:, 0].max() < width_, f"a {ty} value outside its code's {width_} places"
                    code = ("hot", v[:, :1].astype(np.int64), width_)
            elif ty == "Box":
                m = np.clip(v[rows], *self.margin_range) - mar_lo
                Ed.append((rows, pos, np.where(hid[:, None], n_mar + ty_n, m)))
                code = ("box", v)
            else:
                x_ = v[:, 0].astype(np.int64)
                known = (x_ >= 0) & (x_ < len(self.orient_lut))
                oi = np.where(known, self.orient_lut[np.where(known, x_, 0)], 0)   # a marker row's cell is 0 and absent
                f_edge, f_pair, f_ref = self.orient_np
                e = np.where(f_edge[oi[rows]] > 0, n_mar + ty_i, n_mar + ty_n + 1)
                Ed.append((rows, pos, np.where(hid[:, None], n_mar + ty_n, e)))
                keep = ~hid[:, None]
                Pr.append((rows, pos, ty_i, f_pair[oi[rows]].reshape(-1, 16) * keep, f_ref[oi[rows]].reshape(-1, 16) * keep,
                           hid.astype(np.float64)))
                if one_hot:
                    code = ("hot", oi[:, None], len(self.orient_index))
            g = GROUPS.get(ty, "orientation")
            if self.equality == "random":   # a sign code per value, of each of a Box's margins
                vals = v if ty == "Box" else v[:, :1]
                code = ("dense", torch.cat([ids.host("sign " + g, vals[:, j], RANDOM_CODE_WIDTH)
                                            for j in range(vals.shape[1])], 1))
            elif self.equality == "flex":   # the values themselves, of each of a Box's margins
                code = ("flex", (v if ty == "Box" else v[:, :1]).astype(np.int64))
            A.append((rows, pos, ty_i, pidx))
            groups.setdefault(g, []).append((i, code))
        eq, eq_cols, box_u = {}, {g: [i for i, _ in cols] for g, cols in groups.items()}, None
        for g, cols in groups.items():
            out = []
            if g == "box" and one_hot:   # a one-hot per margin over the margin values the table holds
                u, inv_ = np.unique(np.stack([cd[1] for _, cd in cols]), return_inverse=True)
                box_u = u
                inv_ = inv_.reshape(len(cols), n, 4)
                cols = [(i, ("hot", inv_[k] + np.arange(4) * len(u), 4 * len(u))) for k, (i, _) in enumerate(cols)]
            for i, cd in cols:
                rows = np.flatnonzero(code_present[:, i])
                if cd[0] == "hot":
                    out.append((tb.positions[i], "hot", cd[2], rows, cd[1][rows]))
                elif cd[0] == "dense":
                    out.append((tb.positions[i], "dense", cd[1].shape[1], rows, cd[1][torch.from_numpy(rows)]))
                else:
                    out.append((tb.positions[i], "flex", cd[1].shape[1], code_present[:, i], cd[1]))
            eq[g] = out
        return dict(n=n, rel=rel_index, ek=tb.example_kind.astype(np.int64), hv=hv, A=A, B=Bc, E=Ed, P=Pr, eq=eq,
                    eq_cols=eq_cols, box_u=box_u)

    def row_tokens(self, plans, pack, rel_all):
        """The row tokens of tables, [R, 21, c] for the R rows of `plans` in order. Host arrays go through `pack`,
        which the caller loads before the second call of the generator: it yields once, with the arrays added, then
        gives the tensor."""
        dev, dt, c = self.cross.weight.device, self.cross.weight.dtype, self.c
        starts = np.cumsum([0] + [p["n"] for p in plans])
        R = int(starts[-1])
        cat = lambda xs, empty: np.concatenate(xs) if xs else empty
        i64 = lambda a: np.asarray(a, np.int64)
        # each part: per column, its rows, what the device computes there, and the column's place j among the
        # table's columns of the part; the device puts each row's value at (row, j) of a [R, M] grid, M the most
        # columns of the part of any table, and sums over j
        A = [(starts[k] + r, pos, ty, pidx, j) for k, p in enumerate(plans) for j, (r, pos, ty, pidx) in enumerate(p["A"])]
        Bc = [(starts[k] + r, pos, vec, j) for k, p in enumerate(plans) for j, (r, pos, vec) in enumerate(p["B"])]
        Ed = [(starts[k] + r, pos, e, j) for k, p in enumerate(plans) for j, (r, pos, e) in enumerate(p["E"])]
        Pr = [(starts[k] + r, pos, ty, fa, fb, fh, j) for k, p in enumerate(plans)
              for j, (r, pos, ty, fa, fb, fh) in enumerate(p["P"])]
        M = {part: max(len(p[part]) for p in plans) for part in "ABEP"}
        at = lambda parts, m: cat([x[0] * m + x[-1] for x in parts], i64([]))
        rep = lambda parts, j: cat([np.full(len(x[0]), x[j]) for x in parts], i64([]))
        h = dict(
            rel=pack.add(cat([p["rel"] for p in plans], i64([])), torch.long),
            ek=pack.add(cat([p["ek"] for p in plans], i64([])), torch.long),
            hv=pack.add(torch.cat([p["hv"] for p in plans]), dt),
            a_ty=pack.add(rep(A, 2), torch.long), a_pos=pack.add(rep(A, 1), torch.long),
            a_val=pack.add(cat([x[3] for x in A], i64([])), torch.long),
            b_pos=pack.add(rep(Bc, 1), torch.long),
            b_vec=pack.add(torch.cat([x[2] for x in Bc]) if Bc else torch.zeros(0, c), dt),
            e_pos=pack.add(rep(Ed, 1), torch.long),
            e_val=pack.add(cat([x[2] for x in Ed], np.zeros((0, 4), np.int64)), torch.long),
            p_pos=pack.add(rep(Pr, 1), torch.long), p_ty=pack.add(rep(Pr, 2), torch.long),
            p_a=pack.add(cat([x[3] for x in Pr], np.zeros((0, 16))), dt), p_b=pack.add(cat([x[4] for x in Pr], np.zeros((0, 16))), dt),
            p_h=pack.add(cat([x[5] for x in Pr], np.zeros(0)), dt))
        for part, parts in zip("ABEP", (A, Bc, Ed, Pr)):
            h["at " + part] = pack.add(at(parts, M[part]), torch.long)
        yield
        # the device side
        g_ = lambda k: pack[h[k]]
        zero = self.mask_inv.new_zeros(1, c)
        values = torch.cat([self.number.weight, self.mask_inv, zero])              # a Number's, a hidden value's, none
        edges = torch.cat([self.margin.weight, self.type_edge, self.mask_edge[None], zero])
        S0, S1, S2 = self.S[:, 0], self.S[:, 1], self.S[:, 2]
        bind = torch.stack([self.bind_example, self.bind_assignment, self.bind_model, self.unseen.to(dt)])
        # the lookups in small tables by F.embedding, whose backward pass sums each table row's gradient without
        # atomic adds
        base = F.embedding(g_("rel"), rel_all) + self.example_kind(g_("ek")) + (g_("hv") * bind).sum(1)
        inv_a = (self.type_emb(g_("a_ty")) + F.embedding(g_("a_val"), values)) * F.embedding(g_("a_pos"), S0)
        inv_b = g_("b_vec") * F.embedding(g_("b_pos"), S0)
        edge = F.embedding(g_("e_val"), edges) * F.embedding(g_("e_pos"), S1)[:, None]
        p_ty, mask16 = g_("p_ty"), self.mask_pair[PAIR_ORBIT_OF]
        pair = (g_("p_a")[..., None] * F.embedding(p_ty, self.type_pair)[:, None]
                + g_("p_b")[..., None] * F.embedding(p_ty, self.type_pair_ref)[:, None]
                + g_("p_h")[:, None, None] * mask16) * F.embedding(g_("p_pos"), S2)[:, None]
        summed = lambda src, part: placed(src, g_("at " + part), R * M[part]).view(R, M[part], *src.shape[1:]).sum(1)
        yield torch.cat([(base + summed(inv_a, "A") + summed(inv_b, "B"))[:, None], summed(edge, "E"), summed(pair, "P")], 1)

    @staticmethod
    def equality_layout(plans):
        """The places of the equality term of a level's tables `plans`: {group: (offset, columns, code places)}, the
        groups in a fixed order, each with the most columns and code places of any of the tables."""
        layout, F_ = {}, 0
        for g in sorted({g for p in plans for g in p["eq"]}):
            m = max(len(p["eq"].get(g, [])) for p in plans)
            D = max(col[2] for p in plans for col in p["eq"].get(g, []))
            layout[g] = (F_, m, D)
            F_ += m * D
        return layout

    @staticmethod
    def equality_codes(plans, layout, at, base):
        """The codes of the equality term of a level's tables `plans` under `layout`, for a flat buffer that holds a
        [rows, F] grid from place `base`, F the places of the layout, where row r of table k is grid row at[k] + r:
        the places and the values of the codes that are not zero."""
        F_ = sum(m * D for _, m, D in layout.values())
        idx, val = [], []
        for k, p in enumerate(plans):
            for g, cols in p["eq"].items():
                off, m, D = layout[g]
                for s, (_, kind, _, rows, x) in enumerate(cols):
                    first = base + (at[k] + rows) * F_ + off + s * D
                    if kind == "hot":
                        idx.append((first[:, None] + x).reshape(-1)); val.append(np.ones(x.size))
                    else:
                        idx.append((first[:, None] + np.arange(x.shape[1])).reshape(-1)); val.append(x.reshape(-1).numpy())
        return idx, val

    @staticmethod
    def equality_flex(plans, layout, pack):
        """The equality term of a level's tables `plans` with `equality` "flex", per group of `layout`: the handles in
        `pack` of the values [R, m, S], the presence [R, m] and the column positions [I, m], for the R rows of `plans`
        in order."""
        starts = np.cumsum([0] + [p["n"] for p in plans])
        R, fl = int(starts[-1]), {}
        for g, (_, m, S) in layout.items():
            vals, pres = np.zeros((R, m, S), np.int64), np.zeros((R, m), bool)
            for k, p in enumerate(plans):
                for s, (_, _, _, pr, x) in enumerate(p["eq"].get(g, [])):
                    vals[starts[k]:starts[k + 1], s] = x
                    pres[starts[k]:starts[k + 1], s] = pr
            pos = np.asarray([[col[0] for col in p["eq"].get(g, [])] + [0] * (m - len(p["eq"].get(g, []))) for p in plans],
                             np.int64)
            fl[g] = (pack.add(vals, torch.long), pack.add(pres, torch.bool), pack.add(pos, torch.long))
        return fl

    @staticmethod
    def batch_places(layout, plans):
        """The level's places of `layout` that a batch of `plans` holds, in the batch's order, or None where no table
        of the batch has a column (`batch_layout`)."""
        idx = []
        for g, (off, m, D) in layout.items():
            cols = [p["eq"].get(g, []) for p in plans]
            mb = max(len(cs) for cs in cols)
            if mb:
                Db = max(col[2] for cs in cols for col in cs)
                idx.append((off + np.arange(mb)[:, None] * D + np.arange(Db)).reshape(-1))
        return np.concatenate(idx) if idx else None

    def pointer_codes(self, tb, mask, ids, rows=None):
        """The pointer codes of a table's rows (all, or `rows`), [r, ptr_codes] on the host: per row, the sum over its
        visible Color, Example and Ident fields of the field's code, a one-hot of 10 places for a Color, of `examples`
        for an Example, and the Ident's random code ("ident code"), each in its own places."""
        rows = np.arange(tb.n) if rows is None else rows
        out = torch.zeros(len(rows), self.ptr_codes, dtype=ids.dtype)
        o = 0
        for i, ty in enumerate(tb.types):
            v = tb.cells[rows, o]; o += width(ty)
            if ty not in POINTER_TYPES:
                continue
            vis = torch.from_numpy(tb.present[rows, i] & ~mask[rows, i] if mask is not None else tb.present[rows, i])
            if ty == "Ident":
                out[:, 10 + self.examples:10 + self.examples + self.code_dim] += (
                    ids.host("ident code", v, self.code_dim) * vis[:, None] if len(rows) else 0)
            else:
                at = torch.from_numpy(v.astype(np.int64)) + (0 if ty == "Color" else 10)
                out[torch.arange(len(rows))[vis], at[vis]] += 1
        return out

    def source_codes(self, src, sc, rows, ids, g, plan):
        """The equality codes of column sc of the source table `src` at its rows `rows`, in the code places of the
        derived table whose `plan` reads it, for the group g: (places [r, k], values [r, k]). A Box margin value that
        the derived table does not hold has no place there, and no code."""
        o = int(np.sum([width(x) for x in src.types[:sc]]))
        ty = src.types[sc]
        v = src.cells[rows, o:o + width(ty)]
        r = len(rows)
        dense = lambda vec: (np.broadcast_to(np.arange(vec.shape[1]), vec.shape), vec.numpy())
        if self.equality == "random":
            return dense(torch.cat([ids.host("sign " + g, v[:, j], RANDOM_CODE_WIDTH) for j in range(v.shape[1])], 1)
                         if r else torch.zeros(0, RANDOM_CODE_WIDTH * v.shape[1]))
        if ty in ("Number", "Ident"):
            return dense(ids.host(ty.lower() + " code", v[:, 0], self.code_dim) if r else torch.zeros(0, self.code_dim))
        if ty in ("Color", "Example"):
            return v[:, :1].astype(np.int64), np.ones((r, 1))
        if ty == "Box":
            u = plan["box_u"]
            at = np.minimum(np.searchsorted(u, v), len(u) - 1)
            ok = u[at] == v
            return np.where(ok, at + np.arange(4) * len(u), -1), ok.astype(np.float64)
        x_ = v[:, 0].astype(np.int64)
        known = (x_ >= 0) & (x_ < len(self.orient_lut))
        return np.where(known, self.orient_lut[np.where(known, x_, 0)], 0)[:, None], np.ones((r, 1))

    def source_entries(self, its, tables_of, ids_of, masks, layout, places, F_b, Es, slots):
        """The codes of a batch's source keys in the batch's equality places `places` (the level's places of the
        batch, in order; None where they are all the level's places), as entries of a [B, Es, F_b] grid: the place
        of each, the place of its weight among the [slots, slots] slot pairs, and its value. For each column of a
        table of the batch and each source column of its flows of the same equality group, the source rows' codes
        at the column's places, under the weight of the two columns' positions."""
        at = None
        if places is not None:
            at = np.full(sum(m * D for _, m, D in layout.values()), -1, np.int64)
            at[places] = np.arange(len(places))
        place, widx, val = [], [], []
        scale = 1 / RANDOM_CODE_WIDTH if self.equality == "random" else 1
        for b, it in enumerate(its):
            if not it["src"]:
                continue
            p, plan = it["p"], it["plan"]
            tables, tb = tables_of[p], tables_of[p][it["t"]]
            first = dict(zip(it["src"], np.cumsum([0] + [tables[j].n for j in it["src"]])))
            for g, (off, m, D) in layout.items():
                for s, c in enumerate(plan["eq_cols"].get(g, [])):
                    for j, sc in it["pairs"][c]:
                        src = tables[j]
                        if GROUPS.get(src.types[sc], "orientation") != g:
                            continue
                        hidden = masks[p][j][:, sc] if masks is not None and masks[p][j] is not None else False
                        rows = np.flatnonzero(src.present[:, sc] & ~hidden)
                        d, x = self.source_codes(src, sc, rows, ids_of[p], g, plan)
                        keep = (d >= 0) & (x != 0)
                        f = off + s * D + d
                        if at is not None:
                            f = at[np.where(keep, f, 0)]
                            keep &= f >= 0
                        cell = (b * Es + first[j] + rows)[:, None] * F_b + f
                        place.append(cell[keep]); val.append(x[keep] * scale)
                        widx.append(np.full(int(keep.sum()), tb.positions[c] * slots + src.positions[sc]))
        cat = lambda xs, dt: np.concatenate(xs).astype(dt) if xs else np.zeros(0, dt)
        return cat(place, np.int64), cat(widx, np.int64), cat(val, np.float64)

    def batch_layout(self, layout, plans, pack):
        """The places of a batch's equality term among those of its level's `layout` (`equality_layout`): each
        group's columns at the most columns and code places of any of the batch's tables. Gives (a permutation of the
        level's places that takes them to the first, in order, added to `pack`, and their count, or None where they
        are all the level's places in order; the zeros that pad q and k to a multiple of 8), or None where no table of
        the batch has a column."""
        idx, F_ = self.batch_places(layout, plans), sum(m * D for _, m, D in layout.values())
        if idx is None:
            return None
        W = self.mats[0]["W"]
        pad = up8(W + len(idx)) - W - len(idx)
        if len(idx) == F_:
            return None, pad
        perm = np.empty(F_, np.int64)
        perm[idx] = np.arange(len(idx))
        perm[np.setdiff1d(np.arange(F_), idx)] = np.arange(len(idx), F_)
        return (pack.add(perm, torch.long), len(idx)), pad

    def empty_vectors(self, rel, unseen):
        """The vectors of tables with no rows, [E, K, 21, c] from their relation vectors rel [E, c] and unseen [E]
        (1 where the encoder cannot see the table): the seeds, with the relation's vector on the invariant channels,
        and the unseen vector where the encoder cannot see the table."""
        s = self.pool.seeds()
        inv = s[None, :, 0] + (rel + unseen[:, None] * self.unseen)[:, None]
        return torch.cat([inv[:, :, None], s[None, :, 1:].expand(len(rel), -1, -1, -1)], 2)

    def encode_programs(self, programs, gen, masks=None, detail=False):
        """programs: [(tables, relation vectors [n, c] or a list of them, Identifiers)] -> the pooled vectors
        [n, K, 21, c] of each program's tables. Level t holds the t-th table of every program, whose rows attend to
        that program's pooled vectors of levels 0..t-1 outside its own group of `table_groups` (the tables of the
        other assignments of its export table), each with the embedding of its distance back in groups, and, at each
        layer, to the rows of the program's earlier evidence tables after that layer, which stay in row form. The host
        plans every level first: each level's batches of `batches`, each padded to its most rows. The row tokens of
        every level's tables are then built together and placed in the batches' rows by one copy, and the equality
        codes of every level by one write, each level's in its own layout. The two evidence tables, where a program
        starts with both, are encoded jointly at level 0, as one block of rows that attend to each other with the
        equality term across the block, and each is pooled on its own rows. With `source_rows`, a derived table's
        rows also attend, at each layer, to the rows of its source tables (`source_tables`) after that layer, kept by
        `SourceRows` from their own level, with the equality term of each column against the source columns its flows
        name; and with `ptr_equality` too, the last layer's attention also gathers the source keys' pointer codes for
        the masked heads. Call `prepare` first. With `masks` (per
        program, per table, a field mask [n, columns] or None), the masked fields are hidden and the result is (pooled
        vectors, records): a record (program, table index, masked_fields' result) per table with a masked field."""
        dev, dt, c, K = self.cross.weight.device, self.cross.weight.dtype, self.c, self.K
        act = torch.get_autocast_dtype(dev.type) if torch.is_autocast_enabled(dev.type) else dt
        L, flex = len(self.blocks), self.equality == "flex"
        if not programs:
            return [] if masks is None else ([], [])
        rels = [r if torch.is_tensor(r) else torch.stack(r) if len(r) else torch.zeros(0, c, device=dev, dtype=dt)
                for _, r, _ in programs]
        rel_start = np.cumsum([0] + [len(r) for r in rels])
        rel_all = torch.cat(rels) if len(rels) > 1 else rels[0]
        records = []
        pool_row, n_pooled = {}, 0   # the row of (program, table) among every pooled vector
        ev = Evidence(len(programs), L)
        joint = {p for p, (tables, _, _) in enumerate(programs) if len(tables) > 1 and tables[0].evidence
                 and tables[1].evidence and tables[0].n and tables[1].n}
        group = [np.array(table_groups(tables)) for tables, _, _ in programs]
        srcs = [source_tables(tables) if self.source_rows else None for tables, _, _ in programs]
        is_source = [{j for src in s[0] for j in src} if s is not None else set() for s in srcs]
        store = SourceRows()
        pack = Pack()
        levels, row_plans = [], []
        to_batch, n_placed = [], 0   # each row's place in the rows of every level's batches, one batch after another
        eq_idx, eq_val, eq_size = [], [], 0   # the equality codes of every level, flat
        with torch.profiler.record_function("encoder.host"):
            for t in range(max((len(p[0]) for p in programs), default=0)):
                items, empties = [], []
                for p, (tables, _, ids) in enumerate(programs):
                    if t >= len(tables) or (t == 1 and p in joint):
                        continue
                    if t == 0 and p in joint:   # the evidence tables as one block of rows
                        a, b = tables[0], tables[1]
                        assert a.types == b.types and a.positions == b.positions
                        cm = None if masks is None else (masks[p][0], masks[p][1])
                        cmj = None if masks is None else np.concatenate(cm)
                        rel = np.repeat([rel_start[p], rel_start[p] + 1], [a.n, b.n])
                        items.append(dict(p=p, parts=[(a, cm and cm[0], 0, a.n), (b, cm and cm[1], a.n, a.n + b.n)],
                                          evidence=True, plan=self.plan(joint_table(a, b), ids, cmj, rel)))
                    elif not tables[t].n:
                        empties.append((p, t))
                    else:
                        tb, cm = tables[t], masks[p][t] if masks is not None else None
                        items.append(dict(p=p, parts=[(tb, cm, 0, tb.n)], evidence=tb.evidence,
                                          plan=self.plan(tb, ids, cm, np.full(tb.n, rel_start[p] + t))))
                for it in items:
                    it["n"], it["E"], it["t"] = it["plan"]["n"], ev.rows(it["p"]), t
                    it["src"] = [] if srcs[it["p"]] is None or it["evidence"] else srcs[it["p"]][0][t]
                    it["pairs"] = None if not it["src"] else srcs[it["p"]][1][t]
                    it["Es"] = sum(programs[it["p"]][0][j].n for j in it["src"])
                row_plans += [it["plan"] for it in items]
                layout = self.equality_layout([it["plan"] for it in items])
                starts = np.cumsum([0] + [it["n"] for it in items])
                lv = dict(t=t, empties=empties, eq=None, flex=None, ev_sel=None)
                if empties:
                    lv["e_rel"] = pack.add(np.array([rel_start[p] + i for p, i in empties]), torch.long)
                    lv["e_unseen"] = pack.add(np.array([programs[p][0][i].unseen is not None for p, i in empties]), dt)
                P = t * K
                groups = batches([it["n"] for it in items], [P + it["E"] + it["Es"] for it in items])
                plans = []
                for grp in groups:
                    its = [items[i] for i in grp]
                    B, N, E = len(its), up8(max(it["n"] for it in its)), max(it["E"] for it in its)
                    J = 2 if any(len(it["parts"]) == 2 for it in its) else 1
                    Es = max(it["Es"] for it in its)
                    rows = np.stack([np.r_[starts[i] + np.arange(items[i]["n"]), np.full(N - items[i]["n"], starts[i])]
                                     for i in grp])
                    km = np.zeros((B, N + P + E + Es), bool)
                    pm = np.zeros((B, J, N), bool)
                    for b, it in enumerate(its):
                        km[b, :it["n"]] = True
                        km[b, N:N + P] = np.repeat(group[it["p"]][:t] != group[it["p"]][t], K)   # not its own group
                        km[b, N + P:N + P + it["E"]] = True
                        km[b, N + P + E:N + P + E + it["Es"]] = True
                        for j in range(J):
                            lo, hi = it["parts"][j][2:] if len(it["parts"]) == 2 else (0, it["n"])
                            pm[b, j, lo:hi] = True
                    plan = dict(grp=grp, its=its, B=B, N=N, E=E, J=J, Es=Es, rows=pack.add(rows.reshape(-1), torch.long),
                                key_mask=pack.add(km[:, None, None], torch.bool),
                                pool_mask=pack.add(np.repeat(pm, K, 1)[:, None], torch.bool),
                                item=pack.add(np.array(grp), torch.long),
                                its_ev=[b for b, it in enumerate(its) if it["evidence"]])
                    if E:
                        plan["ev_index"] = pack.add(ev.key_index([it["p"] for it in its], E).reshape(-1), torch.long)
                    if t:
                        plan["prev"] = pack.add(np.array([[pool_row[(it["p"], i)] * K + k for i in range(t) for k in range(K)]
                                                          for it in its]).reshape(-1), torch.long)
                        # each earlier table's distance back in groups, clipped
                        plan["back"] = pack.add(np.stack([np.repeat(np.minimum(group[it["p"]][t] - group[it["p"]][:t],
                                                                               self.max_recency), K) for it in its]).reshape(-1),
                                                torch.long)
                    if layout and not flex:   # the batch's own layout, with the zeros that pad q and k to a multiple of 8
                        plan["eq"] = self.batch_layout(layout, [it["plan"] for it in its], pack)
                    # the rows of the batch's tables that are sources of a later table, and the batch's source keys
                    src_b = [b for b, it in enumerate(its) if it["t"] in is_source[it["p"]] and not it["evidence"]]
                    plan["src_sel"] = None if not src_b else pack.add(
                        np.concatenate([b * N + np.arange(its[b]["n"]) for b in src_b]), torch.long)
                    plan["src_of"] = [(its[b]["p"], its[b]["t"], its[b]["n"]) for b in src_b]
                    if Es:
                        involved, sidx = store.key_index([[(it["p"], j) for j in it["src"]] for it in its], Es)
                        plan["src"] = dict(involved=involved, index=pack.add(sidx.reshape(-1), torch.long), F=0, eq=None)
                        if self.ptr_codes:
                            cv = torch.zeros(B, Es, self.ptr_codes, dtype=dt)
                            for b, it in enumerate(its):
                                if it["src"]:
                                    cat_ = torch.cat([store.codes[(it["p"], j)] for j in it["src"]])
                                    cv[b, :len(cat_)] = cat_
                            plan["src"]["codes"] = pack.add(cv, act)
                        if layout and not flex and plan["eq"] is not None:
                            places = self.batch_places(layout, [it["plan"] for it in its])
                            F_ = sum(m * D for _, m, D in layout.values())
                            F_b = F_ if plan["eq"][0] is None else plan["eq"][0][1]
                            ent = self.source_entries(its, [w[0] for w in programs], [w[2] for w in programs], masks,
                                                      layout, None if plan["eq"][0] is None else places, F_b, Es,
                                                      self.slots)
                            plan["src"].update(F=F_b, eq=(pack.add(ent[0], torch.long), pack.add(ent[1], torch.long),
                                                          pack.add(ent[2], act)))
                    plans.append(plan)
                # each row's place in the rows of the level's batches, one batch after another, each [B N], and the
                # place of each table's first row
                lv["plans"], lv["sizes"] = plans, [pl["B"] * pl["N"] for pl in plans]
                S = sum(lv["sizes"])
                level_at, first, item, o = np.empty(int(starts[-1]), np.int64), np.empty(len(items), np.int64), np.empty(S, np.int64), 0
                for pl, size in zip(plans, lv["sizes"]):
                    for b, i in enumerate(pl["grp"]):
                        first[i] = o + b * pl["N"]
                        level_at[starts[i]:starts[i + 1]] = first[i] + np.arange(items[i]["n"])
                        item[first[i]:first[i] + pl["N"]] = i
                    o += size
                to_batch.append(n_placed + level_at)
                n_placed += S
                if layout and not flex:   # the level's codes in the batches' rows, padded with zeros
                    F_ = sum(m * D for _, m, D in layout.values())
                    idx, val = self.equality_codes([it["plan"] for it in items], layout, first, eq_size)
                    eq_idx += idx; eq_val += val
                    lv["eq"] = dict(layout=layout, base=eq_size, F=F_, item=pack.add(item, torch.long), pos={
                        g: pack.add(np.asarray([[col[0] for col in it["plan"]["eq"].get(g, [])] + [0] * (m - len(it["plan"]["eq"].get(g, [])))
                                                for it in items], np.int64), torch.long) for g, (_, m, _) in layout.items()})
                    eq_size += S * F_
                elif layout:
                    lv["flex"] = self.equality_flex([it["plan"] for it in items], layout, pack)
                if ev.stale() and any(it["E"] for it in items):
                    lv["ev_sel"] = pack.add(ev.load(), torch.long)
                # the level's pooled vectors and evidence rows, in the order its batches run
                store.plan_level([s for pl in plans for s in pl["src_of"]])
                if self.ptr_codes:   # the pointer codes of the level's source tables, for the later tables' values
                    for pl in plans:
                        for p_, t_, _ in pl["src_of"]:
                            store.codes[(p_, t_)] = self.pointer_codes(
                                programs[p_][0][t_], masks[p_][t_] if masks is not None else None, programs[p_][2])
                for pl in plans:
                    if pl["its_ev"]:
                        ev.plan([(pl["its"][b]["p"], b, pl["its"][b]["n"]) for b in pl["its_ev"]], pl["B"], pl["N"])
                    for b, it in enumerate(pl["its"]):
                        for j in range(len(it["parts"])):
                            pool_row[(it["p"], t + j)] = n_pooled + b * pl["J"] + j
                    n_pooled += pl["B"] * pl["J"]
                for k, key in enumerate(empties):
                    pool_row[key] = n_pooled + k
                n_pooled += len(empties)
                ev.close_level()
                levels.append(lv)
            feats = self.row_tokens(row_plans, pack, rel_all) if row_plans else None
            if feats is not None:
                next(feats)
                batch_at = pack.add(np.concatenate(to_batch), torch.long)
            if eq_idx:
                c_idx, c_val = pack.add(np.concatenate(eq_idx), torch.long), pack.add(np.concatenate(eq_val), act)
        pack.load(dev)
        # every level's rows in the batches' row order, padded with zeros, by one copy, and its codes by one write
        if feats is not None:
            xs_all = placed(next(feats), pack[batch_at], n_placed).split([s for lv in levels for s in lv["sizes"]])
        codes_all = torch.zeros(eq_size, dtype=act, device=dev).index_put_((pack[c_idx],), pack[c_val]) if eq_idx else None
        # a sign code's key is scaled so that an equal pair scores the weight
        scale = 1 / RANDOM_CODE_WIDTH if self.equality == "random" else 1
        pooled, n_batches = None, 0
        for lv in levels:
            t, plans, empties = lv["t"], lv["plans"], lv["empties"]
            xs = xs_all[n_batches:n_batches + len(plans)] if plans else ()
            n_batches += len(plans)
            if lv["ev_sel"] is not None:
                ev.compute(self, pack[lv["ev_sel"]])
            eq = lv["eq"]
            if eq is not None:
                S, F_ = sum(lv["sizes"]), eq["F"]
                codes, item = codes_all[eq["base"]:eq["base"] + S * F_].view(S, F_), pack[eq["item"]]
                keys = [equality_keys(self.eq_all, pack[eq["pos"][g]], item, codes[:, off:off + m * D].view(S, m, D), scale)
                        for g, (off, m, D) in eq["layout"].items()]
                qs, ks = codes.split(lv["sizes"]), (torch.cat(keys, -1) if len(keys) > 1 else keys[0]).split(lv["sizes"])
            if lv["flex"] is not None:
                eq_flex = [(pack[v], pack[p], pack[pos]) for v, p, pos in lv["flex"].values()]
            outs = []
            for j_, plan in enumerate(plans):
                B, N, E, J = plan["B"], plan["N"], plan["E"], plan["J"]
                x = xs[j_].view(B, N, NPOS, c)
                prev = None
                if t:   # with the recency embedding on the invariant channels
                    rec = F.pad(self.recency(pack[plan["back"]])[:, None], (0, 0, 0, NPOS - 1)).view(B, t * K, NPOS, c)
                    prev = pooled.view(-1, NPOS, c).index_select(0, pack[plan["prev"]]).view(B, t * K, NPOS, c) + rec
                ctx = Batch(level=t, mask=pack[plan["key_mask"]], prev=prev)
                if eq is not None and plan["eq"] is not None:
                    q_, k_, (sel, pad) = qs[j_], ks[j_], plan["eq"]
                    if sel is not None:
                        perm, width = pack[sel[0]], sel[1]
                        q_, k_ = leading(q_, 1, perm, width), leading(k_, 3, perm, width)
                    ctx.eq_q = (F.pad(q_, (0, pad)) if pad else q_).view(B, N, 1, -1)
                    k_ = k_.view(B, N, L, k_.shape[2], -1)
                    ctx.eq_k = (F.pad(k_, (0, pad, 0, 0, 0, 0, 0, t * K)) if t or pad else k_).unbind(2)
                elif lv["flex"] is not None:
                    rows, item = pack[plan["rows"]], pack[plan["item"]]
                    ctx.flex = [(v.index_select(0, rows).view(B, N, *v.shape[1:]), pr.index_select(0, rows).view(B, N, -1),
                                 pos.index_select(0, item)) for v, pr, pos in eq_flex]
                elif self.mats[0]["W"] % 8 and not flex:   # q and k padded to a multiple of 8, which the kernel needs
                    pad = up8(self.mats[0]["W"]) - self.mats[0]["W"]
                    ctx.eq_q = x.new_zeros(B, N, 1, pad).to(self.mats[0]["qkv"].dtype)
                    ctx.eq_k = x.new_zeros(B, N + t * K, L, self.blocks[0].heads, pad).to(self.mats[0]["qkv"].dtype).unbind(2)
                if E:
                    ctx.ev = EvidenceKeys(ev, pack[plan["ev_index"]], B, E,
                                          ctx.eq_q.shape[-1] if ctx.eq_q is not None else 0)
                Es = plan.get("Es", 0)
                if Es:
                    sp, mats0 = plan["src"], self.mats[0]
                    eq_w = ctx.eq_q.shape[-1] if ctx.eq_q is not None else 0
                    ctx.src = SourceKeys(store, sp["involved"], pack[sp["index"]], B, Es,
                                         None if sp["eq"] is None else tuple(pack[h] for h in sp["eq"]), sp["F"],
                                         eq_w - sp["F"], self.src_eq_all, self.blocks[0].heads, mats0["W"], mats0["Wv"])
                    if self.ptr_codes:
                        ctx.code_v, ctx.code_layer = pack[sp["codes"]], L - 1
                keep_layers = plan["its_ev"] or plan.get("src_sel") is not None
                layers, acc = [], None
                for l, blk in enumerate(self.blocks):
                    if self.checkpoint and torch.is_grad_enabled() and B * (N + t * K + E + Es) >= CHECKPOINT_MIN:
                        x = checkpoint(blk, x, ctx, l, self.mats[l], use_reentrant=False)
                    else:
                        x = blk(x, ctx, l, self.mats[l])
                    if isinstance(x, tuple):
                        x, acc = x
                    if keep_layers:
                        layers.append(x)
                if plan["its_ev"]:
                    ev.add(layers)
                if plan.get("src_sel") is not None:
                    store.add(layers, pack[plan["src_sel"]])
                outs.append(self.pool(x, pack[plan["pool_mask"]], self.pool_mats).view(B * J, K, NPOS, c))
                for b, it in enumerate(plan["its"]):
                    for j, (tbj, cmj, lo, hi) in enumerate(it["parts"]):
                        if cmj is not None and cmj.any():
                            records.append((it["p"], t + j, self.masked_fields(
                                tbj, x[b, lo:hi], cmj, detail, None if acc is None else acc[b, lo:hi],
                                programs[it["p"]][2])))
            if empties:
                outs.append(self.empty_vectors(rel_all.index_select(0, pack[lv["e_rel"]]), pack[lv["e_unseen"]]))
            ev.join_level()
            store.join_level(self)
            parts = ([pooled] if pooled is not None else []) + outs
            if parts:
                pooled = torch.cat(parts) if len(parts) > 1 else parts[0]
        counts = [len(tables) for tables, _, _ in programs]
        if pooled is None:
            out = [torch.zeros(0, K, NPOS, c, device=dev, dtype=dt) for _ in programs]
        else:
            order = to_device(torch.tensor([pool_row[(p, i)] for p, n in enumerate(counts) for i in range(n)], dtype=torch.long), dev)
            out = list(pooled.index_select(0, order).split(counts))
        return out if masks is None else (out, records)

    def masked_fields(self, table, x, field_mask, detail=False, acc=None, ids=None):
        """The masked loss of a table's masked fields, from its row tokens after the layers x [n, 21, c]: a dict of
        "loss" [m] (a field's cross-entropy; a Box's, the mean over its edges), "label" (the column type, under
        "ex_output/" for the evidence output), "correct" [m] bool on the device (a Box: all four margins) and
        "edges" [m] on the device (a Box: its margins right, 0 to 4; any other type: -1), which a
        caller reads after the backward pass, so that the forward pass waits on no copy to the host, and with `detail`,
        "out": {head: (field indices, outputs)} for the symmetry check (the pointer's over the rows some masked field
        may point to, then "no row holds it"). "chance_loss" [m] is the loss of the field's head when all its scores
        are equal: ln of the head's class count, and for a pointer, -log(targets / (candidates + 1)), where targets
        are the candidate rows that hold the field's value (one, "no row holds it", where none does) and candidates
        are the candidate rows.

        With `ptr_equality`, a pointer's score of a candidate row adds, for each visible field of the hidden field's row
        whose column has the hidden column's type, the weight of the two columns' positions (`ptr_eq`) where the
        candidate's value in the hidden column equals that field's value; and with `source_rows`, per head, the weight
        of the hidden column's position (`ptr_src`) times the inner product of the candidate's code in the hidden
        column (`pointer_codes`) with the codes `acc` [n, H, ptr_codes] that the row's last-layer attention gathered
        from its source keys. Both weights enter times POINTER_EQ_GAIN."""
        hd, dev, dt = self.heads, x.device, x.dtype
        up = lambda v: v.float() if v.dtype in (torch.float16, torch.bfloat16) else v   # the loss in at least float32
        rr, ii = np.nonzero(field_mask)
        offsets = np.cumsum([0] + [width(ty) for ty in table.types])
        bind = bound_slots(self.S)[torch.tensor(table.positions, device=dev)[torch.from_numpy(ii).to(dev)]]   # [m, 21, c]
        hx = hd.norm(x)
        z = hd.h2(F.gelu(hd.h1(hx[torch.from_numpy(rr).to(dev)] * bind)))                                    # [m, 21, c]
        types = [table.types[i] for i in ii]
        losses, chances, correct, edges, order, out = [], [], [], [], [], {}
        sel = lambda pred: np.array([k for k, ty in enumerate(types) if pred(ty)], np.int64)
        value = lambda k, j=0: int(table.cells[rr[k], offsets[ii[k]] + j])
        idx = sel(lambda ty: ty == "Number")
        if len(idx):
            lo, hi = self.number_range
            tgt = torch.tensor([min(max(value(k), lo), hi) - lo for k in idx], device=dev)
            logits = hd.number(z[idx, 0]) @ self.number.weight.T
            losses.append(F.cross_entropy(up(logits), tgt, reduction="none")); correct.append(logits.argmax(1) == tgt)
            chances.append(torch.full_like(losses[-1], math.log(logits.shape[1])))
            order.append(idx); out["number"] = (idx, logits)
        idx = sel(lambda ty: ty == "Box")
        if len(idx):
            lo, hi = self.margin_range
            tgt = torch.tensor([[min(max(value(k, j), lo), hi) - lo for j in range(4)] for k in idx], device=dev)
            logits = hd.margin(z[idx, 1:5]) @ self.margin.weight.T                                            # [m, 4, V]
            ce = F.cross_entropy(up(logits).reshape(-1, logits.shape[-1]), tgt.reshape(-1), reduction="none")
            right = logits.argmax(-1) == tgt
            losses.append(ce.reshape(-1, 4).mean(1)); correct.append(right.all(1)); edges.append(right.sum(1))
            chances.append(torch.full_like(losses[-1], math.log(logits.shape[-1])))
            order.append(idx); out["box"] = (idx, logits)
        # each orientation field is scored over the candidates of its column's type, or of the wider type that holds
        # its value (`scored_type`)
        scored = {k: (ty, scored_type(ty, self.orient_name[value(k)])) for k, ty in enumerate(types) if ty in CANDIDATES}
        for ty, st in sorted(set(scored.values())):
            idx = np.array([k for k, v in scored.items() if v == (ty, st)], np.int64)
            names, f_edge, f_pair, f_ref = self.candidate_features(st)
            tgt = torch.tensor([names.index(self.orient_name[value(k)]) for k in idx], device=dev)
            zz = z[idx]
            scores = (hd.o_edge(zz[:, 1:5])[..., 0] @ f_edge.T + hd.o_pair(zz[:, 5:])[..., 0] @ f_pair.T
                      + hd.o_ref(zz[:, 5:])[..., 0] @ f_ref.T)                                               # [m, C]
            losses.append(F.cross_entropy(up(scores), tgt, reduction="none")); correct.append(scores.argmax(1) == tgt)
            chances.append(torch.full_like(losses[-1], math.log(scores.shape[1])))
            order.append(idx); out["orientation " + ty + ("" if st == ty else " as " + st)] = (idx, scores)
        idx = sel(lambda ty: ty in POINTER_TYPES)
        if len(idx):
            # the rows some masked field may point to: a row present, not masked and not a marker in one of the
            # masked fields' columns; the other rows' logits would be -inf for every field, and add nothing to the
            # softmax. A masked field's own row is not present-and-unmasked in its column, so no field points to itself.
            avail = table.present & ~field_mask & ~table.marker[:, None]                                       # [n, columns]
            ucols, which = np.unique(ii[idx], return_inverse=True)
            kept = np.flatnonzero(avail[:, ucols].any(1))
            which = torch.from_numpy(which.reshape(-1)).to(dev)
            A = torch.from_numpy(avail[kept][:, ucols]).to(dev)                                               # [n', u]
            C = torch.from_numpy(table.cells[kept][:, offsets[ucols]]).to(dev)                                # [n', u]
            vals = torch.from_numpy(table.cells[rr[idx], offsets[ii[idx]]]).to(dev)                          # [m]
            cand = A[:, which].T                                                                              # [m, n']
            target = cand & (C[:, which].T == vals[:, None])
            none = ~target.any(1)
            q = hd.ptr_q(z[idx]) * bind[idx]
            y = hd.ptr_k(hx[torch.from_numpy(kept).to(dev)])
            scores = q.flatten(1) @ y.flatten(1).T / math.sqrt(NPOS * self.c)                                   # [m, n']
            if self.ptr_equality:
                scores = scores + self.pointer_equality(table, field_mask, rr[idx], ii[idx], kept, acc, ids, dev)
            logits = torch.cat([scores.masked_fill(~cand, float("-inf")), hd.none(z[idx, 0])], 1)
            logits = up(logits)
            lp = F.log_softmax(logits, 1)
            right = torch.cat([target, none[:, None]], 1)
            losses.append(-torch.logsumexp(lp.masked_fill(~right, float("-inf")), 1))
            correct.append(right.gather(1, lp.argmax(1, keepdim=True))[:, 0])
            chances.append(torch.log((cand.sum(1) + 1).to(losses[-1].dtype) / right.sum(1)))
            order.append(idx); out["pointer"] = (idx, logits)
        perm = torch.from_numpy(np.argsort(np.concatenate(order), kind="stable")).to(dev)
        prefix = "ex_output/" if table.relation == "ex_output" else ""
        # the engine types a Position as a Box, and encodes and predicts it as one; the evidence tables' cell
        # column is a Position, so its fields are labelled so
        label = lambda ty: "Position" if table.evidence and ty == "Box" else ty
        n_edges = torch.full((len(types),), -1, dtype=torch.long, device=dev)
        if "box" in out:
            n_edges[torch.from_numpy(out["box"][0]).to(dev)] = edges[0]
        rec = {"loss": torch.cat(losses)[perm], "correct": torch.cat(correct)[perm], "edges": n_edges,
               "chance_loss": torch.cat(chances)[perm],
               "label": [prefix + label(ty) for ty in types]}
        if detail:
            rec["out"] = out
        return rec

    def pointer_equality(self, table, field_mask, rows, cols, kept, acc, ids, dev):
        """The equality terms of the pointer scores (`masked_fields`) of the hidden fields at (rows, cols) against the
        candidate rows `kept`: [m, n']."""
        hd = self.heads
        offsets = np.cumsum([0] + [width(ty) for ty in table.types])
        vis = table.present & ~field_mask
        m, C = len(rows), len(table.types)
        same = np.zeros((m, len(kept), C), bool)   # the candidate's value in the hidden column equals the row's in c
        wi = np.zeros((m, C), np.int64)            # the place of the pair's weight
        on = np.zeros((m, C), bool)
        for f, (r, i) in enumerate(zip(rows, cols)):
            for c in range(C):
                if c != i and table.types[c] == table.types[i] and vis[r, c]:
                    on[f, c] = True
                    wi[f, c] = table.positions[i] * self.slots + table.positions[c]
                    same[f, :, c] = table.cells[kept, offsets[i]] == table.cells[r, offsets[c]]
        w = hd.ptr_eq.reshape(-1)[torch.from_numpy(wi).to(dev)] * POINTER_EQ_GAIN * torch.from_numpy(on).to(dev)
        out = (torch.from_numpy(same).to(dev, w.dtype) * w[:, None]).sum(-1)
        if acc is not None:
            pos = torch.tensor([table.positions[i] for i in cols], device=dev)
            u = hd.ptr_src[:, pos].T * POINTER_EQ_GAIN                                           # [m, H]
            gathered = (acc[torch.from_numpy(rows).to(dev)].to(u.dtype) * u[:, :, None]).sum(1)  # [m, D]
            parts = []
            for i in np.unique(cols):
                at = torch.from_numpy(np.flatnonzero(cols == i)).to(dev)
                one = Table(**{**table.__dict__, "types": [table.types[i]], "positions": [table.positions[i]],
                               "cells": table.cells[:, offsets[i]:offsets[i] + 1], "present": table.present[:, i:i + 1]})
                code = self.pointer_codes(one, None, ids, kept).to(dev, u.dtype)                 # [n', D]
                parts.append((at, gathered.index_select(0, at) @ code.T))
            out = out + torch.cat([v for _, v in parts]).index_select(
                0, torch.argsort(torch.cat([a for a, _ in parts])))
        return out

    @staticmethod
    def identifiable(table):
        """[n, columns] bool: whether a field's row differs from every other row of the table outside that field's
        column, in the row's example, example kind, assignment and model, or in another column's presence or value.
        Where it does, the other columns hold a candidate key, and the functional dependency of the field's column
        on them holds. Computed once and kept on the table while its cells are the same array."""
        memo = table.__dict__.setdefault("_unique", {})
        hit = memo.get(("identifiable",))
        if hit is None or hit[0] is not table.cells:
            offsets = np.cumsum([0] + [width(ty) for ty in table.types])
            parts = [np.concatenate([table.present[:, i:i + 1], table.cells[:, offsets[i]:offsets[i + 1]]
                                     * table.present[:, i:i + 1]], 1).astype(np.int64)
                     for i in range(len(table.types))]
            row = np.concatenate([table.example[:, None], table.example_kind[:, None], table.assignment,
                                  table.model[:, None]], 1).astype(np.int64)
            ok = np.zeros((table.n, len(table.types)), bool)
            for i in range(len(table.types)):
                key = np.concatenate([row] + parts[:i] + parts[i + 1:], 1)
                _, inv, counts = np.unique(key, axis=0, return_inverse=True, return_counts=True)
                ok[:, i] = counts[inv.reshape(-1)] == 1
            hit = memo[("identifiable",)] = (table.cells, ok)
        return hit[1]

    def draw_masks(self, tables, frac, cap, gen, kind, mask_remote=False):
        """A field mask [n, columns] per table of one program, for a step of `kind` ("program", "output" or
        "prior"), drawn from `gen`; None for a table without rows. A field is a candidate with probability `frac`
        where it is present, its row is not a marker, and its label (`field_labels`) is `computed` in a program
        step, `computed` in ex_output alone in an output step, or `inferrable` in a prior step; a table keeps at
        most `cap` candidates. A `remote` field, which has no source in its own table or in a grid table, is a candidate in a
        program step only with `mask_remote`. In a program step whose tables hold the export's provenance (`provenance`), the
        (table, column) pairs that hold candidates are then visited in an order drawn from `gen`, and a column keeps
        its candidates only where none of its sources (`column_sources`) holds hidden fields already, and it is a
        source of no column that holds hidden fields already; so ex_output's computed fields can be hidden beside
        derived fields that do not flow from its Color column. Without the provenance, the tables are visited in
        an order drawn from `gen`, and a table keeps its candidates only where no table among its sources
        (`table_sources`) and no table that it is a source of holds hidden fields already. Last, in a program step
        and in an output step, each hidden dependent field of ex_output stays visible where no other train
        example's output shows its value in a visible field (`keep_occurrence`)."""
        assert kind in STEP_KINDS, kind
        want = INFERRABLE if kind == "prior" else COMPUTED
        out = []
        for t, lab in zip(tables, field_labels(tables)):
            if not t.n or not len(t.types):
                out.append(None); continue
            m = (torch.rand(t.n, len(t.types), generator=gen).numpy() < frac) & t.present & ~t.marker[:, None]
            m &= (lab == want) | ((lab == REMOTE) & (mask_remote and kind == "program"))
            if kind == "output" and t.relation != "ex_output":
                m[:] = False
            r, i = np.nonzero(m)
            if len(r) > cap:
                drop = torch.randperm(len(r), generator=gen).numpy()[cap:]
                m[r[drop], i[drop]] = False
            out.append(m)
        if kind == "program" and provenance(tables):
            sources, held, blocked = column_sources(tables), set(), set()   # blocked: the sources of held columns
            pairs = [(j, c) for j, m in enumerate(out) if m is not None for c in np.flatnonzero(m.any(0)).tolist()]
            for p in torch.randperm(len(pairs), generator=gen).tolist():
                j, c = pairs[p]
                if sources[j][c] & held or (j, c) in blocked:
                    out[j][:, c] = False
                else:
                    held.add((j, c)); blocked |= sources[j][c]
        elif kind == "program":
            sources, held = table_sources(tables), set()
            for j in torch.randperm(len(tables), generator=gen).tolist():
                if out[j] is None or not out[j].any():
                    continue
                if sources[j] & held or any(j in sources[k] for k in held):
                    out[j][:] = False
                else:
                    held.add(j)
        if kind in ("program", "output"):
            for j, t in enumerate(tables):
                if t.relation == "ex_output" and out[j] is not None:
                    keep_occurrence(t, out[j], output_labels(evidence_input(tables), t)[1])
        return out

    def chunks(self, n):
        """The programs 0..n-1 in groups of `self.group` (all in one where it is 0), each encoded by its own call."""
        g = self.group
        return [range(i, min(i + g, n)) for i in range(0, n, g)] if g else [range(n)]

    def masked_loss(self, programs, gen=None, frac=0.15, cap=512, mask_gen=None, detail=False, backward=None,
                    kind="alternate", step=0, prior_weight=1.0, mask_remote=False):
        """programs: [(tables, declaration identifiers)] -> the masked loss, and the records of encode_programs, each
        with "kind", its program's step kind, "part", the part of the loss it falls in, and "depth", its table's
        `depth`. The step kind of program
        p is `kind` ("program", "output" or "prior"), or with "alternate", STEP_KINDS[(step + p) % 3]. The loss is
        the program part, the mean loss over the hidden fields of the program and output steps, which are computed
        fields, plus `prior_weight` times the prior part, the mean over those of the prior steps; a part without
        fields is 0. A program step hides remote fields too with `mask_remote` (`draw_masks`). The masks are drawn
        from `mask_gen`, all before
        any encoding, and the identifiers from `gen`. The programs are encoded in the groups of `chunks`. With
        `backward`, a weight, where gradients are on, the backward pass of the weight times the loss runs group by
        group, so that each group's graph is freed before the next is built, and the loss and the records' losses
        come detached."""
        assert kind == "alternate" or kind in STEP_KINDS, kind
        dev, dt = self.cross.weight.device, self.cross.weight.dtype
        kinds = [kind if kind != "alternate" else STEP_KINDS[(step + p) % 3] for p in range(len(programs))]
        masks = [self.draw_masks(tables, frac, cap, mask_gen, k, mask_remote) for (tables, _), k in zip(programs, kinds)]
        n_fields = {part: sum(int(m.sum()) for ms, k in zip(masks, kinds) if LOSS_PART[k] == part for m in ms
                              if m is not None) for part in ("program", "prior")}
        scale = {k: w / n_fields[k] if n_fields[k] else 0.0 for k, w in (("program", 1.0), ("prior", prior_weight))}
        weighted = lambda recs: sum(r["loss"].sum() * scale[r["part"]] for _, _, r in recs)
        run_backward = backward is not None and torch.is_grad_enabled()
        records, total = [], None
        for ch in self.chunks(len(programs)):
            self.prepare()
            try:
                rels = self.relation_vectors([t for p in ch for t in programs[p][0]], [d for p in ch for d in programs[p][1]])
                rels = rels.split([len(programs[p][0]) for p in ch])
                work = [(programs[p][0], r, Identifiers(self.c, self.code_dim, gen, dev, dt)) for p, r in zip(ch, rels)]
                _, recs = self.encode_programs(work, gen, [masks[p] for p in ch], detail)
            finally:
                self.release()
            recs = [(ch[0] + p, t, r) for p, t, r in recs]
            for p, t, r in recs:
                r["kind"], r["part"], r["depth"] = kinds[p], LOSS_PART[kinds[p]], programs[p][0][t].depth
            records += recs
            if not recs:
                continue
            s = weighted(recs)
            if run_backward:
                with torch.autocast(dev.type, enabled=False):   # the backward pass outside autocast
                    (backward * s).backward()
                s = s.detach()
                for _, _, r in recs:
                    r["loss"] = r["loss"].detach()
            total = s if total is None else total + s
        assert sum(len(r["loss"]) for _, _, r in records) == sum(n_fields.values())
        if total is None:
            total = (self.mask_edge.detach() if run_backward else self.mask_edge).sum() * 0.0
        return total, records

    def relation_vector(self, table, decl_vec):
        dev = self.cross.weight.device
        if isinstance(table.relation, str):
            return self.rel_tok(self.embed(torch.tensor(self.in_index[table.relation], device=dev)))
        if decl_vec is not None:
            return self.rel_id(decl_vec.to(dev, self.rel_id.weight.dtype))
        return self.rel_table(torch.tensor(table.relation % 1024, device=dev))

    def relation_vectors(self, tables, decls):
        """The relation vector of each table, [n, c], as relation_vector gives them, in one call per kind."""
        dev = self.cross.weight.device
        kind = [0 if isinstance(t.relation, str) else 1 if d is not None else 2 for t, d in zip(tables, decls)]
        at = lambda k: [i for i, x in enumerate(kind) if x == k]
        parts, order = [], []
        if at(0):
            ids = to_device(torch.tensor([self.in_index[tables[i].relation] for i in at(0)]), dev)
            parts.append(self.rel_tok(self.embed(ids))); order += at(0)
        if at(1):
            parts.append(self.rel_id(to_device(torch.stack([decls[i].cpu() for i in at(1)]), dev).to(self.rel_id.weight.dtype)))
            order += at(1)
        if at(2):
            parts.append(self.rel_table(to_device(torch.tensor([tables[i].relation % 1024 for i in at(2)]), dev))); order += at(2)
        if not parts:
            return self.rel_table.weight.new_zeros(0, self.c)
        out = torch.cat(parts) if len(parts) > 1 else parts[0]
        if order == sorted(order):
            return out
        return out.index_select(0, to_device(torch.from_numpy(np.argsort(order)), dev))

    def cross_out(self, s):
        """[n, K, 21, c] -> [n, K, hidden]."""
        return self.cross(self.cross_norm(self.readout(s.reshape(-1, NPOS, self.c)))).reshape(len(s), self.K, -1)

    def forward(self, programs, gen=None):
        """programs: [(tables, declaration identifiers)] -> one [n_tables, K, hidden] tensor per program, or None
        for a program without tables. The programs are encoded in the groups of `chunks`."""
        self.prepare()
        try:
            dev, dt = self.cross.weight.device, self.cross.weight.dtype
            rels = self.relation_vectors([t for tables, _ in programs for t in tables], [d for _, decls in programs for d in decls])
            rels = rels.split([len(tables) for tables, _ in programs])
            work = [(tables, r, Identifiers(self.c, self.code_dim, gen, dev, dt)) for (tables, _), r in zip(programs, rels)]
            pooled = [s for ch in self.chunks(len(work)) for s in self.encode_programs([work[p] for p in ch], gen)]
            counts = [len(s) for s in pooled]
            if not sum(counts):
                return [None for _ in pooled]
            out = self.cross_out(torch.cat(pooled)).split(counts)
            return [o if n else None for o, n in zip(out, counts)]
        finally:
            self.release()


# ---------------------------------------------------------------- value head

# A rollout export holds, per branch point of a gold program, the gold continuation and the continuations that the
# baseline language model samples from the gold prefix; its `labels.jsonl` (lm/rollout_labels.py) gives each case's
# branch point, continuation and outcome. The value head scores a table by one logit, trained to rank, among one
# branch point's continuations, the tables after the branch whose label is 1 above those whose label is 0. A table
# has two labels: `solving`, the continuation's solving (`value_solving`), and `consistent`, the verdict of the
# RULE clause whose evaluation gave the table: 1 where the relation that its END finishes, read as the output, solves
# every train pair. The second label is given per rule.

VALUE_LABELS = ("solving", "consistent")

def read_value_labels(path):
    """{(task, case): label} from a labels.jsonl, one JSON object per line (lm/rollout_labels.py)."""
    out = {}
    with open(path) as f:
        for line in f:
            if line.strip():
                lab = json.loads(line)
                out[(lab["task"], lab["case"])] = lab
    return out


def value_solving(label):
    """Whether a case's continuation is solving: one without a fault line in the export's report that is the gold
    continuation or ends consistent with the train pairs and solves the test pairs."""
    return label["fault"] is None and (label["rollout"] == "gold" or (label["solved_test"] is True
                                                                       and label["consistency"] == "Consistent"))


def value_flags(t):
    """The flags that exclude a table from the value targets: `faulted` (the table or an example of it faults),
    `unseen` (any other reason the encoder cannot see it) and `empty` (seen, with no rows)."""
    faulted = t.unseen == "the table faults" or "an example's fault" in (t.unseen_entries or {})
    return dict(empty=bool(t.unseen is None and not (~t.marker).any()),
                unseen=bool(t.unseen is not None and not faulted), faulted=bool(faulted))


def value_excluded(r):
    return r["empty"] or r["unseen"] or r["faulted"]


def value_consistent(token, lab):
    """The consistent label of a table after the branch whose step is at stream index `token`: 1 where the verdict of
    its rule is Consistent, 0 where it is another verdict, None where no verdict gives one. Rule k covers the tokens
    from the end of rule k-1 (`rule_ends`, lm/rollout_labels.py) to its own end, and has the verdict `rules[k]`."""
    rules = lab.get("rules")
    if rules is None:
        return None
    k = bisect.bisect_right(lab["rule_ends"], token)
    return int(rules[k] == "Consistent") if k < len(rules) else None


def value_records(tables, labels):
    """{(task, case): [record per table]} for each case of `tables` ({(task, case): [Table]}, after `mark_over_budget`
    and `mark_over_rows`) that `labels` gives with its prefix's table count. A record holds `group` (task, corpus
    case, prefix_tokens), `member` (the rollout index or "gold"), `solving` (`value_solving`), `consistent`
    (`value_consistent`, None for a table of the prefix), `unjudged` (whether `consistent` is None), `position` and the
    flags of `value_flags`. The position counts the export tables from the first after the branch, export table
    `prefix_tables`, at 0; the Tables of one export table share it; the prefix's tables, the evidence tables first,
    take the positions before 0, the last of them -1."""
    out = {}
    for key, ts in tables.items():
        lab = labels.get(key)
        if lab is None or lab.get("prefix_tables") is None:
            continue
        p = int(lab["prefix_tables"])
        exported = [t.export_table for t in ts if not t.evidence]
        after = sorted({x for x in exported if x >= p})
        before = sorted({x for x in exported if x < p})
        n_ev = sum(t.evidence for t in ts)
        group, solving = (lab["task"], lab["corpus_case"], int(lab["prefix_tokens"])), value_solving(lab)
        recs, ev_i = [], 0
        for t in ts:
            consistent = None
            if t.evidence:
                pos, ev_i = ev_i - n_ev - len(before), ev_i + 1
            elif t.export_table >= p:
                pos = after.index(t.export_table)
                consistent = value_consistent(t.step - 1, lab)
            else:
                pos = before.index(t.export_table) - len(before)
            recs.append(dict(group=group, member=lab["rollout"], solving=solving, consistent=consistent,
                             unjudged=consistent is None, position=pos, **value_flags(t)))
        out[key] = recs
    return out


def value_groups(records):
    """{group: {"members": [(task, case)], "rate": the share of solving members}} of `value_records`' result, the
    members in the order of the records."""
    out = {}
    for key, recs in records.items():
        g = out.setdefault(recs[0]["group"], {"members": [], "solving": 0})
        g["members"].append(key)
        g["solving"] += recs[0]["solving"]
    return {g: {"members": v["members"], "rate": v["solving"] / len(v["members"])} for g, v in out.items()}


def load_rollouts(rollout_dir, cache=None, budget=None, max_rows=None, tasks_dir=None):
    """A rollout export and the labels.jsonl in its directory, as {(task, case): member}, a member a dict of
    "tables", "records" (`value_records`), "group", "solving" and "rate" (its group's share of solving members),
    and the faults of the cases left out. The tables come through `load_tables` and its cache at `cache`, or, where
    `cache` is None, from `parse_tables` with `tasks_dir`; `budget` and `max_rows` mark tables as
    `mark_over_budget` and `mark_over_rows` do, before the flags are read. A case that the labels do not give is
    left out. Raises DataFault, naming the task, where a sampled continuation's LM was trained on its task's fold
    (`sampler_fold` k/n with `train.fold_of(task, n) == k`) and the labels do not mark the task held out (`heldout`):
    a fold LM trains on its fold's tasks less the held-out ones."""
    labels = read_value_labels(Path(rollout_dir) / "labels.jsonl")
    for (task, case), lab in labels.items():
        if lab.get("sampler_fold") and not lab.get("heldout"):
            from train import fold_of
            k, n = map(int, lab["sampler_fold"].split("/"))
            if fold_of(task, n) == k:
                raise DataFault(f"{task} {case}: sampled by {lab['sampler_run']}, an LM trained on fold {k}/{n}, "
                                f"which holds the task")
    if cache is None:
        tables, skipped, _ = parse_tables(rollout_dir, *([tasks_dir] if tasks_dir else []))
    else:
        tables, skipped, _ = load_tables(rollout_dir, cache)
    if budget:
        mark_over_budget(tables, budget)
    if max_rows:
        mark_over_rows(tables, max_rows)
    records = value_records(tables, labels)
    groups = value_groups(records)
    members = {}
    for g, v in groups.items():
        for key in v["members"]:
            members[key] = dict(key=key, tables=tables[key], records=records[key], group=g,
                                solving=records[key][0]["solving"], rate=v["rate"])
    return members, skipped


def value_relations(tables, id_dim, gen):
    """The identifier of each table's relation for a program without its stream: one random identifier per relation
    slot, drawn from `gen` as a declaration's is, and None for a fact relation."""
    ids = {}
    return [None if isinstance(t.relation, str) else
            ids.setdefault(t.relation, torch.randn(id_dim, generator=gen) / math.sqrt(id_dim)) for t in tables]


def pooled_vectors(enc, programs, gen=None):
    """programs: [(tables, declaration identifiers)] -> the pooled vectors [n_tables, K, 21, c] of each program, which
    `FeatureEncoder.forward` passes to the crossing, encoded in the groups of `chunks`."""
    enc.prepare()
    try:
        dev, dt = enc.cross.weight.device, enc.cross.weight.dtype
        rels = enc.relation_vectors([t for tables, _ in programs for t in tables], [d for _, ds in programs for d in ds])
        rels = rels.split([len(tables) for tables, _ in programs])
        work = [(tables, r, Identifiers(enc.c, enc.code_dim, gen, dev, dt)) for (tables, _), r in zip(programs, rels)]
        return [s for ch in enc.chunks(len(work)) for s in enc.encode_programs([work[p] for p in ch], gen)]
    finally:
        enc.release()


def value_input(readout, s):
    """The value head's input: the frame-free readout (the encoder's `Readout`, before `cross_norm` and `cross`) of
    each table's K pooled vectors s [n, K, 21, c], flattened over K: [n, K (5c + 4 gram^2)]."""
    return readout(s.reshape(-1, NPOS, s.shape[-1])).reshape(len(s), -1)


class ValueHead(nn.Module):
    """One logit per table: a linear map of its `value_input` after a LayerNorm."""
    def __init__(self, c, gram, K):
        super().__init__()
        w = K * readout_width(c, gram)
        self.norm, self.out = nn.LayerNorm(w), nn.Linear(w, 1)

    def forward(self, readout, s):
        """readout: the encoder's `Readout`; s [n, K, 21, c] -> [n]."""
        return self.score(value_input(readout, s))

    def score(self, x):
        """x: `value_input` [n, w] -> [n]."""
        return self.out(self.norm(x)).squeeze(-1)


VALUE_MODES = ("off", "ranking", "binary")


def value_lists(members, logits, positions=1, *, label):
    """The lists of the value loss under the label `label` (`VALUE_LABELS`). `members`: [{"group", "records",
    "solving"}]; `logits`: [tensor [n_tables]] per member. For each group and each position below `positions`, one
    list over the members that hold a table at that position that no flag excludes (`value_excluded`) and, under
    `consistent`, that is not unjudged: "labels" (bool [m], the member's `solving` or its table's `consistent`; the
    gold continuation takes its own), "scores" (each member's mean logit over its Tables at that position, [m]),
    "gold" (bool [m], whether it is the gold continuation) and "ranked" (whether the labels of the list differ)."""
    assert label in VALUE_LABELS, label
    by = {}
    for m, z in zip(members, logits):
        for p in range(positions):
            sel = [i for i, r in enumerate(m["records"]) if r["position"] == p and not value_excluded(r)
                   and (label == "solving" or not r["unjudged"])]
            if sel:
                ys = {bool(m["records"][i][label]) for i in sel}
                assert len(ys) == 1, f"{m['records'][0]['member']}: the Tables of position {p} differ in {label}"
                zs = z[torch.tensor(sel, device=z.device)]
                by.setdefault((m["group"], p), []).append((ys.pop(), zs, m["records"][0]["member"] == "gold"))
    out = []
    for (g, p), xs in by.items():
        labels = torch.tensor([x[0] for x in xs])
        out.append(dict(group=g, position=p, labels=labels, gold=torch.tensor([x[2] for x in xs]),
                        scores=torch.stack([x[1].mean() for x in xs]),
                        ranked=bool(labels.any() and not labels.all())))
    return out


def value_loss(mode, lists):
    """The value loss over the lists of `value_lists`, or None where no list counts. `ranking`: the mean over the
    ranked lists of a listwise softmax cross-entropy, whose soft target puts weight 1 on each member of label 1 and 0
    on each of label 0, normalized over the list. `binary`: the mean over every list's members of a sigmoid
    cross-entropy of the member's score with its own label as the target."""
    if mode == "ranking":
        terms = []
        for l in lists:
            if l["ranked"]:
                s = l["scores"].float()
                q = l["labels"].to(s.device, s.dtype)
                terms.append(-(q / q.sum() * F.log_softmax(s, 0)).sum())
        return torch.stack(terms).mean() if terms else None
    if mode == "binary":
        if not lists:
            return None
        z = torch.cat([l["scores"] for l in lists]).float()
        return F.binary_cross_entropy_with_logits(z, torch.cat([l["labels"] for l in lists]).to(z.device, z.dtype))
    raise ValueError(mode)


def value_pairs(lists, sampled=False):
    """Over each ranked list, the pairs of a member of label 1 and one of label 0, and with `sampled` those of sampled
    continuations alone: (the pairs in which the member of label 1 scores higher, a tie counting one half; the
    pairs)."""
    right, n = 0.0, 0
    for l in lists:
        if l["ranked"]:
            s, y = l["scores"].detach().float().cpu(), l["labels"]
            if sampled:
                s, y = s[~l["gold"]], y[~l["gold"]]
            d = s[y][:, None] - s[~y][None, :]
            right += float((d > 0).sum() + 0.5 * (d == 0).sum())
            n += d.numel()
    return right, n


def auc(scores, labels):
    """The area under the ROC curve of `scores` for the bool `labels`, a tie counting one half; None without both
    classes."""
    s, y = np.asarray(scores, float), np.asarray(labels, bool)
    if y.all() or not y.any():
        return None
    d = s[y][:, None] - s[~y][None, :]
    return float(((d > 0).sum() + 0.5 * (d == 0).sum()) / d.size)


def value_auc(lists, sampled=False):
    """The mean, over the lists that hold members of both labels, of the AUC (`auc`) of the list's
    scores, and with `sampled` over those of sampled continuations alone, without the gold one; None without such a
    list."""
    aucs = []
    for l in lists:
        s, y = l["scores"].detach().float().cpu().numpy(), l["labels"].numpy()
        if sampled:
            s, y = s[~l["gold"].numpy()], y[~l["gold"].numpy()]
        a = auc(s, y)
        if a is not None:
            aucs.append(a)
    return float(np.mean(aucs)) if aucs else None


def value_metrics(lists):
    """The metrics of the lists of `value_lists`: `pair_acc` (the share of the pairs of `value_pairs` in which the
    member of label 1 scores higher, a tie one half), `pair_acc_sampled` (the same over the pairs of sampled
    continuations alone, without the gold one), `auc` and `auc_sampled` (`value_auc`), and the counts `lists`,
    `ranked_lists`, `pairs` and `pairs_sampled`. A metric without a pair or a list to take it over is None."""
    right, pairs = value_pairs(lists)
    right_s, pairs_s = value_pairs(lists, sampled=True)
    return dict(pair_acc=right / pairs if pairs else None, pair_acc_sampled=right_s / pairs_s if pairs_s else None,
                auc=value_auc(lists), auc_sampled=value_auc(lists, sampled=True), lists=len(lists),
                ranked_lists=sum(l["ranked"] for l in lists), pairs=pairs, pairs_sampled=pairs_s)


VALUE_DRAW_METRICS = ("pair_acc", "pair_acc_sampled", "auc", "auc_sampled")


def value_inputs(enc, members, gen, id_dim):
    """The value head's input (`value_input`), [n_tables, w] per member of `members` (`load_rollouts`), each member
    encoded whole as a program with no field hidden, under one draw of identifiers from `gen` (`value_relations`,
    `pooled_vectors`)."""
    pooled = pooled_vectors(enc, [(m["tables"], value_relations(m["tables"], id_dim, gen)) for m in members], gen)
    return list(value_input(enc.readout, torch.cat(pooled)).split([len(s) for s in pooled]))


def value_scores(enc, head, members, gen, id_dim):
    """The value head's logits, [n_tables] per member of `members`, from `value_inputs`."""
    xs = value_inputs(enc, members, gen, id_dim)
    return list(head.score(torch.cat(xs)).float().split([len(x) for x in xs]))


def value_draw_metrics(members, draws, positions, *, label):
    """The metrics of a score that depends on the draw of identifiers. `draws`: per draw, a score per table of each
    member of `members` ([tensor or array [n_tables]] per member). `value_metrics` of the lists of `value_lists` over
    each table's mean score over the draws, beside "draws" (their count) and, for each metric of
    `VALUE_DRAW_METRICS`, "<metric>_min" and "<metric>_max", over the draws taken one at a time (None where no draw
    gives the metric)."""
    lists = lambda scores: value_lists(members, [torch.as_tensor(s, dtype=torch.float32) for s in scores], positions,
                                       label=label)
    mean = [torch.stack([torch.as_tensor(d[i], dtype=torch.float32).cpu() for d in draws]).mean(0)
            for i in range(len(members))]
    out = dict(value_metrics(lists(mean)), draws=len(draws))
    each = [value_metrics(lists(d)) for d in draws]
    for k in VALUE_DRAW_METRICS:
        xs = [e[k] for e in each if e[k] is not None]
        out[f"{k}_min"], out[f"{k}_max"] = (min(xs), max(xs)) if xs else (None, None)
    return out
