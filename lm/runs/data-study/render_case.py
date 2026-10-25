"""Render one corpus case whole as Markdown: its task's grids, then every table of the case in token order.

    work/lm/.venv/bin/python lm/runs/data-study/render_case.py <tables> <streams> <task> <case>
        [--out FILE] [--tasks-dir data/tasks]

<tables> is a tables export (engine/arclog-py/tables_export.py) and <streams> the streams export of the same master
(lm/export.py), whose cases.npz holds the case's token stream and whose vocab.json names its tokens. The script reads
only the rows of the one case: it copies them out of the export's parquet files into a temporary directory, with a
link to the task's values, and parses them with `encoder.parse_tables`, which reads no checks.txt.

The file (default lm/runs/data-study/case-<task>.md) gives the train and test grids, then each clause of the stream,
followed by the tables of the relations it declares: the relation, column names and types, depth, candidate keys,
the DETs its entries are assigned, and, for each assignment, the rows of each train example and of task-wide entries
(those with an Example column grouped by it), drawn on the grid where the rows are cells of the example's input or
output grid or of a task-wide frame. Where a table has several assignments, each is marked with the values of the
DETs whose value differs between them, a DET's value being the rows of its own table at that assignment, and where
an assignment's rows equal those of an earlier assignment of the same table at every example, the file says so in
place of the rows. A "## What I see" section of an existing file is kept.
"""
import argparse, json, os, sys, tempfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "lm"))
sys.path.insert(0, str(HERE))
import encoder as E   # noqa: E402
from render_branch import Cells, pair_text, stream_text, clause_end, SEE, MAX_ROWS   # noqa: E402

PARTS = ("tables", "index", "assigned", "projections", "projection_rows", "flows")
MAX_DET_ROWS = 12


def case_stream(streams, task, case):
    z = np.load(Path(streams) / "cases.npz")
    hit = [i for i in range(len(z["task"])) if z["task"][i] == task and z["case"][i] == case]
    if not hit:
        sys.exit(f"no stream of {task} {case!r} in {streams}")
    o = z["offsets"]
    i = hit[0]
    return z["ids"][o[i]:o[i + 1]], z["model"][o[i]:o[i + 1]], bool(z["concept"][i])


def read_case(export, task, case, tasks_dir):
    """The Tables of the case through `encoder.parse_tables`, and the case's rows of tables.parquet, index.parquet
    and assigned.parquet, and its values."""
    export = Path(export)
    frames = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for part in PARTS:
            df = pd.read_parquet(export / f"{part}.parquet", filters=[("task", "==", task), ("case", "==", case)])
            df.to_parquet(tmp / f"{part}.parquet")
            frames[part] = df
        (tmp / "values").mkdir()
        os.symlink((export / "values" / task).resolve(), tmp / "values" / task)
        for name in ("orientations.json", "orientation_types.json"):
            (tmp / name).write_text((export / name).read_text())
        tables, faults, _ = E.parse_tables(tmp, tasks_dir)
    if (task, case) not in tables:
        sys.exit(f"the loader left {task} {case!r} out: {faults}")
    values = np.fromfile(export / "values" / task / f"{case}.i32", np.int32)
    return tables[(task, case)], frames, values


def assignments(frames, values):
    """{export table: [assignment]} in the order `encoder.parse_table` gives its Tables (each assignment's first
    entry), each assignment a tuple of DET value indexes; and {index: (det relation, rows [n, width])}, the indexes
    numbered as `encoder.parse_tables` numbers them."""
    asg_of = E.records_by(frames["assigned"], "entry")
    det_values, out = {}, {}
    for t in frames["tables"].sort_values("table").to_dict("records"):
        if t["point"] != E.POINT_RELATION:
            continue
        rel, w = list(t["det_relations"]), list(t["det_widths"])
        order = []
        for e in frames["index"][frames["index"]["table"] == t["table"]].to_dict("records"):
            a = [-1] * len(rel)
            for r in asg_of.get(e["entry"], []):
                run = values[int(r["offset"]):int(r["offset"]) + int(r["rows"]) * w[r["det"]]].reshape(-1, w[r["det"]])
                a[r["det"]] = det_values.setdefault((rel[r["det"]], run.tobytes()), (len(det_values), run))[0]
            if tuple(a) not in order:
                order.append(tuple(a))
        out[int(t["table"])] = order
    return out, {i: (rel, run) for (rel, _), (i, run) in det_values.items()}


def rows_text(cells, types, row_cells, present, ex):
    widths = [E.width(x) for x in types]
    offs = np.cumsum([0] + widths)
    return " | ".join(cells.cell(ty, row_cells[offs[k]:offs[k + 1]], ex) if present[k] else "-"
                      for k, ty in enumerate(types))


def det_value_text(cells, det_types, run, slot):
    types = [E.type_name(x) for x in det_types]
    keep = [i for i, x in enumerate(types) if x != "Unit"]
    widths = [E.width(x) for x in types]
    offs = np.cumsum([0] + widths)
    rows = []
    ex_col = types.index("Example") if "Example" in types else None
    for r in run[:MAX_DET_ROWS]:
        ex = int(r[offs[ex_col]]) if ex_col is not None else -1
        rows.append("(" + ", ".join(cells.cell(types[k], r[offs[k]:offs[k + 1]], ex) for k in keep) + ")")
    more = f" ... {len(run)} rows" if len(run) > MAX_DET_ROWS else ""
    return f"&r{slot} = {{{' '.join(rows)}{more}}}" if keep else f"&r{slot} = {'holds' if len(run) else 'empty'}"


LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def draw(t, idx, offs, ex, cells):
    """The rows idx drawn on a grid where every row's first Box column is a cell of one grid size, and that size is
    the example's input or output grid size, or the rows are task-wide and the grid has more than one cell. Each
    cell shows the row's value where the cell has one row and the table has one Color column (its value), else one
    Ident column (a letter, by the Ident's first row in the drawing's raster order), else one Number column (the
    number, '+' past 9); else the count of rows at the cell ('+' past 9). '.' marks a cell with no row."""
    boxes = [k for k, ty in enumerate(t.types) if ty == "Box"]
    if not boxes or not len(idx) or not t.present[idx, boxes[0]].all():
        return None
    k = boxes[0]
    m = t.cells[idx, offs[k]:offs[k + 1]]
    hs, ws = set((m[:, 0] + m[:, 1] + 1).tolist()), set((m[:, 2] + m[:, 3] + 1).tolist())
    if len(hs) != 1 or len(ws) != 1 or (m < 0).any():
        return None
    h, w = hs.pop(), ws.pop()
    if ex >= 0:
        name = ("the input" if ex < len(cells.inp) and cells.inp[ex] == (h, w) else
                "the output" if ex < len(cells.out) and cells.out[ex] == (h, w) else None)
        if name is None:
            return None
        name = f"the size of {name} grid"
    else:
        if h * w == 1:
            return None
        name = "a task-wide frame"
    count = np.zeros((h, w), int)
    for r, c in m[:, [0, 2]]:
        count[r, c] += 1
    what, value = "the count of rows at the cell", None
    if count.max() == 1:
        for ty, label in (("Color", "the row's Color"), ("Ident", "the row's Ident, as a letter by first appearance"),
                          ("Number", "the row's Number")):
            cols = [c for c, x in enumerate(t.types) if x == ty]
            if len(cols) == 1:
                what, value = label, (ty, cols[0])
                break
    pic = np.full((h, w), ".", object)
    letters = {}
    order = sorted(range(len(idx)), key=lambda j: (m[j, 0], m[j, 2]))
    for j in order:
        r, c = m[j, 0], m[j, 2]
        if value is None:
            pic[r, c] = str(count[r, c]) if count[r, c] < 10 else "+"
            continue
        v = int(t.cells[idx[j], offs[value[1]]])
        if value[0] == "Ident":
            pic[r, c] = letters.setdefault(v, LETTERS[len(letters) % len(LETTERS)])
        else:
            pic[r, c] = str(v) if 0 <= v < 10 else "+"
    return (f"Drawn on a {h}x{w} grid, {name}, by the first Box column; each cell shows {what}, '.' where no row "
            f"is:\n```\n" + "\n".join(" ".join(row) for row in pic) + "\n```")


def signature(t):
    """The rows of a Table, by example, as a comparable value."""
    seen = ~t.marker
    out = []
    for e in sorted(set(t.example[seen].tolist())):
        idx = np.nonzero((t.example == e) & seen)[0]
        out.append((e, sorted(map(bytes, (np.ascontiguousarray(t.cells[idx]).view(np.uint8).reshape(len(idx), -1))))))
    return tuple((e, tuple(r)) for e, r in out)


def table_body(t, cells, n_train, n_test):
    lines = []
    if t.unseen is not None:
        lines.append(f"- unseen: {t.unseen} {t.unseen_entries or ''}")
        return lines
    if t.unseen_entries:
        lines.append(f"- unseen entries: {t.unseen_entries}")
    seen = ~t.marker
    per = [int(((t.example == e) & seen).sum()) for e in range(n_train)]
    test = int(((t.example >= n_train) & seen).sum())
    wide = int(((t.example == -1) & seen).sum())
    lines.append(f"- rows per train example: {per}; test: {test}" + (f"; task-wide: {wide}" if wide else ""))
    if wide and not sum(per):
        lines.append("- every row is of a task-wide entry")
    widths = [E.width(x) for x in t.types]
    offs = np.cumsum([0] + widths)
    header = " | ".join(t.names) if t.types else ""
    groups = []
    wide_idx = np.nonzero((t.example == -1) & seen)[0]
    if "Example" in t.types and len(wide_idx):
        # task-wide rows with an Example column: grouped by it, each Box decoded against that example's grids
        o = offs[t.types.index("Example")]
        for v in sorted(set(t.cells[wide_idx, o].tolist())):
            groups.append((int(v), f"Task-wide, rows whose Example column is e{v}", wide_idx[t.cells[wide_idx, o] == v]))
    elif len(wide_idx):
        groups.append((-1, "Task-wide", wide_idx))
    if sum(per):
        groups += [(e, f"Train example {e}", np.nonzero((t.example == e) & seen)[0]) for e in range(n_train)]
    for e, label, idx in groups:
        lines.append(f"\n{label}: {len(idx)} row{'' if len(idx) == 1 else 's'}"
                     + (f", the first {MAX_ROWS} shown" if len(idx) > MAX_ROWS else ""))
        if not len(idx):
            continue
        if not t.types:
            lines.append("The relation has no columns: its one row says the relation holds.")
            continue
        drawn = draw(t, idx, offs, e, cells)
        if drawn:
            lines.append(drawn)
        body = [rows_text(cells, t.types, t.cells[i], t.present[i], e)
                + (f"   (projection {int(t.part[i])})" if t.part[i] else "") for i in idx[:MAX_ROWS]]
        lines.append("```\n" + header + "\n" + "\n".join(body) + "\n```")
    return lines


def render(tables_dir, streams, task, case, out_path, tasks_dir):
    ids, model, concept = case_stream(streams, task, case)
    vocab = json.load(open(Path(streams) / "vocab.json"))
    names, kinds = vocab["names"], vocab["kinds"]
    task_json = json.load(open(Path(tasks_dir) / f"{task}.json"))
    n_train, n_test = len(task_json["train"]), len(task_json["test"])
    cells = Cells(task_json, json.load(open(Path(tables_dir) / "orientations.json")))
    tabs, frames, values = read_case(tables_dir, task, case, tasks_dir)
    order, det_values = assignments(frames, values)
    rows_of = {int(r["table"]): r for r in frames["tables"].to_dict("records")}
    rel = [t for t in tabs if not t.evidence]
    by_table = {}
    for t in rel:
        by_table.setdefault(t.export_table, []).append(t)

    md = [f"# {task}, case `{case}`", "",
          f"- concept case: {concept}; tokens: {len(ids)}; tables: {len(by_table)} relations, {len(rel)} per assignment",
          "- cells: a Position is `(row,col)` of the example's input grid (`(row,col)out` where it fits only the "
          "output grid), an Offset `+(drow,dcol)`, another Box `rR0-R1 cC0-C1` over the input grid or `[t b l r]` "
          "margins; an Ident is `id<n>`, equal only within one case; see README.md", ""]
    md.append("## Grids\n")
    for i, pr in enumerate(task_json["train"]):
        hi, wi, ho, wo = len(pr["input"]), len(pr["input"][0]), len(pr["output"]), len(pr["output"][0])
        md.append(f"### Train example {i}: input {hi}x{wi}, output {ho}x{wo}\n")
        md.append("```\n" + pair_text(pr["input"], pr["output"]) + "\n```\n")
    for i, pr in enumerate(task_json["test"]):
        md.append(f"### Test example {i}: input {len(pr['input'])}x{len(pr['input'][0])}\n")
        md.append("```\n" + "\n".join(" ".join(map(str, r)) for r in pr["input"]) + "\n```\n")
    md.append("## Program and tables\n")
    md.append("Model-written tokens plain, engine-written ones in [brackets]. Each clause is followed by the tables "
              "of the relations it declares. A table whose entries hold several DET assignments is given once per "
              "assignment, each marked with the values, at that assignment, of the DETs whose value differs between "
              "them; a DET's value is the rows of its own table at that assignment.\n")
    start = 0
    keys = sorted(by_table, key=lambda k: (by_table[k][0].step, k))
    i = 0
    while start < len(ids):
        end = clause_end(ids, model, kinds, start)
        md.append("```\n" + stream_text(ids, model, names, kinds, start, end) + "\n```\n")
        while i < len(keys) and by_table[keys[i]][0].step - 1 < end:
            k = keys[i]; i += 1
            row = rows_of[k]
            ts = by_table[k]
            col_names = list(row["column_names"])
            for t in ts:
                t.names = [col_names[p] for p in t.positions]
            all_types = [E.type_name(x) for x in row["column_types"]]
            cols = ", ".join(f"{col_names[p]}: {all_types[p]}" for p in ts[0].positions) or "none"
            key_names = [[col_names[c] for c in kk] for kk in row["keys"]]
            md.append(f"### &r{ts[0].relation} (export table {k})\n")
            md.append(f"- columns: {cols}")
            md.append(f"- depth {row['depth']}, candidate keys {key_names if key_names else 'none'}")
            dets = list(row["det_relations"])
            if dets:
                md.append(f"- DETs its entries are assigned: {', '.join('&r' + d.split()[-1] for d in dets)}; "
                          f"assignments: {len(order[k]) if ts[0].unseen is None else 'unseen'}")
            # the DETs whose value differs between the assignments of this table
            varies = [d for d in range(len(dets)) if len({a[d] for a in order[k]}) > 1] if ts[0].unseen is None else []
            sigs = []
            for j, t in enumerate(ts):
                if len(ts) > 1:
                    a = order[k][j] if t.unseen is None and j < len(order[k]) else None
                    head = f"\n#### &r{t.relation}, assignment {j + 1} of {len(ts)}"
                    md.append(head + "\n")
                    if a is not None:
                        md.append("- DET values that differ between the assignments: " + "; ".join(
                            det_value_text(cells, row["det_types"][d], det_values[a[d]][1], dets[d].split()[-1])
                            if a[d] >= 0 else f"&r{dets[d].split()[-1]} unassigned" for d in varies))
                    if t.unseen is None and t.n:
                        assert not len(t.assignment) or tuple(t.assignment[0].tolist()) == a, (k, j)
                s = signature(t) if t.unseen is None else None
                same = next((jj for jj, ss in enumerate(sigs) if s is not None and ss == s), None)
                sigs.append(s)
                if same is not None:
                    md.append("- empty at every example" if not s else
                              f"- rows equal to those of assignment {same + 1} at every example")
                    continue
                md.extend(table_body(t, cells, n_train, n_test))
                md.append("")
        start = end
    see = f"{SEE}\n\n(not written yet)\n"
    if out_path.exists():
        old = out_path.read_text()
        if SEE in old:
            see = old[old.index(SEE):]
    out_path.write_text("\n".join(md) + "\n" + see)
    print(f"wrote {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tables")
    ap.add_argument("streams")
    ap.add_argument("task")
    ap.add_argument("case")
    ap.add_argument("--out")
    ap.add_argument("--tasks-dir", default=str(ROOT / "data/tasks"))
    a = ap.parse_args()
    out = Path(a.out) if a.out else HERE / f"case-{a.task}.md"
    render(a.tables, a.streams, a.task, a.case, out, a.tasks_dir)


if __name__ == "__main__":
    main()
