"""Views of arclog tables: the rows of a table at each example, in a layout of tables and grids (views.py), with
each Box column drawn by its type and frame.

    load_case(export, task, case)              the case's Tables, each with `frames` and `names`, read from an
                                               export directory
    case_table_lines(c, table, assignment=0)   the view of one table of a loaded case
    table_lines(export, task, case, table, assignment=0)   the same, loading the case
    case_lines(export, task, case)             {export table: [the view at each assignment]}

The Tables are model/encoder.py's, from the `encoder` module that the caller has imported, or that an import of
`encoder` finds on the caller's sys.path. Importing this module reads no file and changes no path.
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[2]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import copy, importlib, importlib.util, itertools, json, os, re, sys, tempfile
from pathlib import Path
from typing import NamedTuple

import numpy as np

_spec = importlib.util.spec_from_file_location("haiku_views", Path(__file__).with_name("views.py"))
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)

TASKS = MAIN_ROOT / 'data/tasks'
BOX_TYPES = ("Box", "Position", "Offset")
PARTS = ("tables", "index", "assigned", "projections", "projection_rows", "flows")
LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


class Cells:
    """The grid sizes of each example, train then test, and the text of a value that is not a Box."""

    def __init__(self, task_json, orientations):
        pairs = task_json["train"] + task_json["test"]
        self.inp = [(len(p["input"]), len(p["input"][0])) for p in pairs]
        self.out = [(len(p["output"]), len(p["output"][0])) for p in task_json["train"]]
        self.orient = {int(k): v for k, v in orientations}

    def cell(self, ty, v, ex):
        v = int(v[0])
        if ty in ("Number", "Color"):
            return str(v)
        if ty == "Example":
            return f"e{v}"
        if ty == "Ident":
            return f"id{v}"
        return self.orient.get(v, f"?{v}")


# ------------------------------------------------------------------ loading

class Case(NamedTuple):
    tables: list    # the encoder Tables, each with `frames`, `names` and `relation_name`
    frames: dict    # {part: the case's rows of <part>.parquet}
    cells: Cells
    n_train: int
    n_test: int
    letters: dict   # {(example, Ident value): its letter, the same in every table of the case}


def encoder_module():
    return sys.modules.get("encoder") or importlib.import_module("encoder")


def unique_names(names):
    """The names with each repeat of a name marked by its count: `Key`, `Key#2`, `Key#3`, so that a view keeps
    every column."""
    seen, out = {}, []
    for n in names:
        seen[n] = seen.get(n, 0) + 1
        out.append(n if seen[n] == 1 else f"{n}#{seen[n]}")
    return out


def export_root(export):
    """The directory that holds the values and the orientation files of `export`: the export itself, or, for a task's
    directory `<out>/tasks/<task>/` of an export, `<out>`. Raises ValueError for a task's directory that holds no
    `DONE`, since its files may not be whole."""
    export = Path(export)
    if (export / "orientations.json").exists() or export.parent.name != "tasks":
        return export
    if not (export / "DONE").exists():
        reason = (export / "FAILED").read_text().strip() if (export / "FAILED").exists() else "no DONE marker yet"
        raise ValueError(f"{export}: the task's directory is not whole: {reason}")
    return export.parent.parent


def read_case(export, task, case, tasks_dir=TASKS, encoder=None):
    """(the Tables of the case, {part: its rows}) from an export directory, or from the task's directory
    `<out>/tasks/<task>/` of one (`export_root`), through `encoder.parse_tables`. A case
    that the export's bases.parquet cuts is read with its base, and the base's with its own, so its tables below the
    cut are the base's. Each Table gets, for its kept columns in `positions` order: `frames`, the export's
    `column_frames`; `names`, the export's `column_labels` where it gives them and its `column_names` elsewhere;
    `source_names`, the same from `column_source_labels`, the labels the case's own text writes; each with a
    repeated name marked by its count (`unique_names`); and `relation_name`. A table below the cut takes these from the base's row of tables.parquet."""
    import pandas as pd
    enc = encoder or encoder_module()
    export, root = Path(export), export_root(export)
    chain, bases = [case], None
    if (export / "bases.parquet").exists():
        bases = pd.read_parquet(export / "bases.parquet", filters=[("task", "==", task)])
        base_of = dict(zip(bases["case"], bases["base"]))
        while chain[-1] in base_of and base_of[chain[-1]] not in chain:
            chain.append(base_of[chain[-1]])
        bases = bases[bases["case"].isin(chain)]
    frames = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for part in PARTS:
            if not (export / f"{part}.parquet").exists():
                continue
            df = pd.read_parquet(export / f"{part}.parquet", filters=[("task", "==", task), ("case", "in", chain)])
            df.to_parquet(tmp / f"{part}.parquet")
            frames[part] = df
        if bases is not None:
            bases.to_parquet(tmp / "bases.parquet")
            frames["bases"] = bases
        (tmp / "values").mkdir()
        os.symlink((root / "values" / task).resolve(), tmp / "values" / task)
        for name in ("orientations.json", "orientation_types.json"):
            (tmp / name).write_text((root / name).read_text())
        tables, faults, _ = enc.parse_tables(tmp, tasks_dir)
    if (task, case) not in tables:
        raise ValueError(f"the loader left {task} {case!r} out: {faults}")
    rows = {}
    for k in reversed(chain):   # the base's rows first, each case's own over them
        rows.update({int(r["table"]): r for r in frames["tables"].to_dict("records") if r["case"] == k})
    attach_extents(tables[(task, case)], frames, root / "values" / task, chain, bases)
    for part, df in frames.items():
        if "case" in df.columns:
            frames[part] = df[df["case"] == case]
    for t in tables[(task, case)]:
        r = rows.get(t.export_table, {})
        cf = list(r.get("column_frames", []))
        names = list(r.get("column_names", []))
        labels = list(r["column_labels"]) if r.get("column_labels") is not None else []
        t.frames = [cf[p] if p < len(cf) else "" for p in t.positions]
        t.names = unique_names([(labels[p] if p < len(labels) and labels[p] else names[p] if p < len(names) else f"c{p}")
                                for p in t.positions])
        src = list(r["column_source_labels"]) if r.get("column_source_labels") is not None else []
        t.source_names = unique_names([(src[p] if p < len(src) and src[p] else names[p] if p < len(names) else f"c{p}")
                                       for p in t.positions])
        t.relation_name = r.get("relation_name")
    return tables[(task, case)], frames


def attach_extents(tables, frames, values_dir, chain, bases):
    """Give each Table `extents`, int [rows, kept columns, 2]: the (V, H) extent of the frame of each row's value
    in each column of the export table's `extent_columns`, from the extent runs of the entries and of the
    projection rows; -1 where the export gives none. A table below a cut is the base's, with the base's entries;
    a cut case's own entries stand in its Tables after the base's entries below the cut, as the encoder numbers
    them."""
    cut = {} if bases is None else {r["case"]: (r["base"], int(r["tables"])) for r in bases.to_dict("records")}
    by_case = {k: {part: df[df["case"] == k] for part, df in frames.items() if "case" in df.columns} for k in chain}
    values, offset = {}, {}
    for k in chain:
        if k in cut:
            base, below = cut[k]
            idx = by_case.get(base, {}).get("index")
            offset[k] = 0 if idx is None else int((idx["table"] < below).sum())
        else:
            offset[k] = 0

    def owner(table):
        k = chain[0]
        while k in cut and table < cut[k][1] and cut[k][0] in by_case:
            k = cut[k][0]
        return k

    for t in tables:
        t.extents = np.full((len(t.example), len(getattr(t, "positions", [])), 2), -1, np.int32)
        if t.evidence or t.unseen is not None or not len(t.example):
            continue
        k = owner(t.export_table)
        parts = by_case[k]
        tr = parts["tables"][parts["tables"]["table"] == t.export_table]
        if not len(tr) or tr.iloc[0].get("extent_columns") is None:
            continue
        ext_cols = [int(x) for x in tr.iloc[0]["extent_columns"]]
        kept = {p: j for j, p in enumerate(t.positions)}
        if not ext_cols or not any(p in kept for p in ext_cols):
            continue
        if k not in values:
            values[k] = np.fromfile(values_dir / f"{k}.i32", np.int32)
        vals = values[k]
        idx = parts["index"]
        ents = {int(r["entry"]): r for r in idx[idx["table"] == t.export_table].to_dict("records")}
        projs = parts.get("projections")
        prows = parts.get("projection_rows")
        pcols = {}
        if projs is not None and len(projs):
            p = projs.reset_index(drop=True)
            p = p.assign(_pid=range(len(p)))
            pcols = {int(r["_pid"]): [int(c) for c in r["columns"]] for r in p.to_dict("records") if int(r["table"]) == t.export_table}
        prow = {} if prows is None else {(int(r["projection"]), int(r["entry"])): r for r in prows.to_dict("records")}
        groups = {}
        for i in np.flatnonzero(~t.marker):
            groups.setdefault((int(t.entry[i]) - offset[k], int(t.part[i])), []).append(int(i))
        for (e, part), rows_i in groups.items():
            ent = ents.get(e)
            if ent is None:
                continue
            if int(ent["kind"]) == 0:   # a Rows entry: its own extent run over the table's extent columns
                cols, off, n = ext_cols, int(ent.get("extent_offset", -1)), int(ent["rows"])
            else:   # a Count entry: the run of its projection's rows, over the projection's extent columns
                pid = sorted(pcols)[part] if part < len(pcols) else None
                pr = prow.get((pid, e)) if pid is not None else None
                if pr is None:
                    continue
                cols, off, n = [c for c in ext_cols if c in pcols[pid]], int(pr.get("extent_offset", -1)), int(pr["rows"])
            if off < 0 or not cols or n != len(rows_i):
                continue
            run = vals[off:off + len(rows_i) * len(cols) * 2].reshape(len(rows_i), len(cols), 2)
            for j, c in enumerate(cols):
                if c in kept:
                    t.extents[rows_i, kept[c]] = run[:, j]


def ident_letters(tables):
    """{(example, Ident value): letter}: at each example, the Ident values of every table of the case in their
    order, one letter each, and past the 52 letters a letter with a count (`a1`, `b1`, ...). A task-wide row takes
    the example its Example column gives, as `view_lines` groups it."""
    seen = {}
    for t in tables:
        if t.evidence or t.unseen is not None or "Ident" not in t.types:
            continue
        offs = col_vals(t)
        ex = t.example
        if "Example" in t.types:
            ex = np.where(ex == -1, t.cells[:, offs[t.types.index("Example")]], ex)
        for c, ty in enumerate(t.types):
            if ty == "Ident":
                for e, v, m in zip(ex.tolist(), t.cells[:, offs[c]].tolist(), t.marker.tolist()):
                    if e >= 0 and not m:
                        seen.setdefault(e, set()).add(int(v))
    return {(e, v): LETTERS[r % len(LETTERS)] + (str(r // len(LETTERS)) if r >= len(LETTERS) else "")
            for e, vs in seen.items() for r, v in enumerate(sorted(vs))}


def load_case(export, task, case, tasks_dir=TASKS, encoder=None):
    tables, frames = read_case(export, task, case, tasks_dir, encoder)
    tj = json.load(open(Path(tasks_dir) / f"{task}.json"))
    cells = Cells(tj, json.load(open(export_root(export) / "orientations.json")))
    return Case(tables, frames, cells, len(tj["train"]), len(tj["test"]), ident_letters(tables))


def case_table_lines(c, table, assignment=0, layout=None, header=True):
    """The view of the export table `table` of the loaded case c at its assignment `assignment` (the order of the
    encoder's Tables of that export table): with `header`, the line of its columns, row counts and flags first."""
    group = [t for t in c.tables if t.export_table == table]
    t = group[assignment]
    name = t.relation_name if isinstance(t.relation_name, str) else f"table {table}"
    if header:
        return table_view(name, t, t.names, c.cells, c.n_train, c.n_test, len(group), [], layout=layout, letters=c.letters,
                          assignment=assignment + 1)
    if t.unseen is not None:
        return [f"no rows to show ({t.unseen})"]
    order = [k for k, ty in enumerate(t.types) if ty != "Unit"]
    return view_lines(t, t.names, c.cells, c.n_train, c.n_test, order, {}, layout, c.letters)


def table_lines(export, task, case, table, assignment=0, layout=None, header=True, tasks_dir=TASKS, encoder=None):
    return case_table_lines(load_case(export, task, case, tasks_dir, encoder), table, assignment, layout, header)


def case_lines(export, task, case, layout=None, header=True, tasks_dir=TASKS, encoder=None):
    """{export table: [the view at each of its assignments]} for every relation table of the case."""
    c = load_case(export, task, case, tasks_dir, encoder)
    out = {}
    for t in c.tables:
        if not t.evidence and t.export_table not in out:
            n = sum(1 for x in c.tables if x.export_table == t.export_table)
            out[t.export_table] = [case_table_lines(c, t.export_table, a, layout, header) for a in range(n)]
    return out


# ------------------------------------------------------------------ rendering a table

def short_orient(s):
    return re.sub(r"^(DIR|DIAG|AXIS|DAXIS|D4|SYM|SENSE)_", "", s)


def col_vals(t):
    """The offset of each column's first cell in a row of t.cells, and the row's width last."""
    widths = [sys.modules[type(t).__module__].width(x) for x in t.types]
    offs = np.cumsum([0] + widths)
    return offs


def value_text(cells, ty, v, ex, idents, letters=None):
    """The text of one value: an Ident by `letters` ({(example, value): letter}) where it has one; else `id<n>`,
    by its number, where `letters` is given, so that it shares no letter with another Ident; else by a letter of its
    own in `idents`; a Box value by its type."""
    if ty in BOX_TYPES:
        return box_text(v, ex, cells, "offset" if ty == "Offset" else "cell" if ty == "Position" else "box")
    if ty == "Ident":
        n = int(v[0])
        if letters and (ex, n) in letters:
            return letters[(ex, n)]
        if letters:
            return f"id{n}"
        if n not in idents:
            r = len(idents)
            idents[n] = LETTERS[r % len(LETTERS)] + (str(r // len(LETTERS)) if r >= len(LETTERS) else "")
        return idents[n]
    s = cells.cell(ty, v, ex)
    return short_orient(s) if ty not in BOX_TYPES + ("Number", "Color", "Example") else s


def grid_size(cells, ex):
    return cells.inp[ex] if 0 <= ex < len(cells.inp) else None


def out_size(cells, ex):
    return cells.out[ex] if 0 <= ex < len(cells.out) else None


def box_forms(t, offs, idx, order, cells):
    """{column: form} for the Box columns, from each column's type and frame: "zero" where every value of a Box or
    an Offset is the zero box; "cell" for a Position, a cell of its own frame; "offset" for an Offset; for a Box in
    the frame of the input or the output, "cell-input" or "cell-output" where every value is one cell of that frame,
    and "box-input" or "box-output" where some value is not; "offset" for a Box in another frame whose every value
    has margin sums of 0, a translation; "box" for any other Box."""
    forms = {}
    for c in order:
        ty = t.types[c]
        if ty not in BOX_TYPES:
            continue
        rows = [(int(t.example[i]), tuple(int(x) for x in t.cells[i, offs[c]:offs[c + 1]])) for i in idx
                if t.present[i, c]]
        frame = t.frames[c]
        if ty != "Position" and all(v == (0, 0, 0, 0) for _, v in rows):
            forms[c] = "zero"
        elif ty == "Position":
            forms[c] = "cell"
        elif ty == "Offset":
            forms[c] = "offset"
        elif frame in ("input", "output"):
            size = grid_size if frame == "input" else out_size
            known = [(size(cells, ex), v) for ex, v in rows if size(cells, ex)]
            one = known and all(g[0] - v[0] - v[1] == 1 and g[1] - v[2] - v[3] == 1 for g, v in known)
            forms[c] = ("cell-" if one else "box-") + frame
        elif all(v[0] + v[1] == 0 and v[2] + v[3] == 0 for _, v in rows):
            forms[c] = "offset"
        else:
            forms[c] = "box"
    return forms


def box_text(v, ex, cells, form):
    t, b, l, r = (int(x) for x in v)
    g = grid_size(cells, ex) if form == "box-input" else out_size(cells, ex) if form == "box-output" else None
    if form == "zero" or not g and not any((t, b, l, r)):
        return "ZERO"
    if form == "offset":
        return f"+({t},{l})"
    if form == "cell" and min(t, b, l, r) >= 0:
        return f"({t},{l})/{t + b + 1}x{l + r + 1}"   # no frame is known to be the input
    if g and min(t, b, l, r) >= 0 and t <= g[0] - 1 - b and l <= g[1] - 1 - r:   # inside the grid
        return f"r{t}-{g[0] - 1 - b} c{l}-{g[1] - 1 - r}" + (f"/{g[0]}x{g[1]}" if form == "box-output" else "")
    return f"[{t} {b} {l} {r}]"


def made_extent(t, i, c):
    """The (V, H) extent of the made frame of row i's value in column c, or None where the export gives none."""
    ext = getattr(t, "extents", None)
    if ext is None or i >= len(ext) or c >= ext.shape[1] or "@" not in t.frames[c]:
        return None
    v, h = (int(x) for x in ext[i, c])
    return (v, h) if v >= 1 and h >= 1 else None


def framed_box_text(v, ext, cells, ex):
    """A Box that is not one cell of its made frame of extent ext: the rows and columns it covers, with the frame's
    size; `[t b l r]` where it reaches past the frame or covers no cell."""
    t, b, l, r = (int(x) for x in v)
    if min(t, b, l, r) >= 0 and t <= ext[0] - 1 - b and l <= ext[1] - 1 - r:
        return f"r{t}-{ext[0] - 1 - b} c{l}-{ext[1] - 1 - r}/{ext[0]}x{ext[1]}"
    return f"[{t} {b} {l} {r}]"


def layout_rows(t, names, cells, idx, order, idents, forms, letters=None):
    """The rows idx as views.Rows over the columns order. A Position is a cell of its own frame, and a Box whose
    form is a cell of a grid, or one cell of the made frame the export gives its row, is a cell of that grid or
    frame: `(r,c)`, with `/HxW` where the frame is not the input. Another Box in a made frame is the rows and columns
    it covers, with `/HxW`. A row's extent comes before its column's form, and a value with a negative margin, which
    reaches past its frame, is `[t b l r]`."""
    offs = col_vals(t)
    rows = []
    for i in idx:
        ex = int(t.example[i])
        text, key, cell = {}, {}, {}
        for c in order:
            if not t.present[i, c]:
                continue
            v = t.cells[i, offs[c]:offs[c + 1]]
            key[names[c]] = tuple(int(x) for x in v)
            form, f = forms.get(c), None
            ext = made_extent(t, i, c) if t.types[c] == "Box" else None   # a row's own extent comes before its column's form
            inside = min(int(x) for x in v) >= 0
            if ext is not None:
                if inside and (ext[0] - int(v[0]) - int(v[1]), ext[1] - int(v[2]) - int(v[3])) == (1, 1):
                    f = ext
            elif form == "cell" and inside:
                f = (int(v[0]) + int(v[1]) + 1, int(v[2]) + int(v[3]) + 1)
            elif form in ("cell-input", "cell-output") and inside:
                f = grid_size(cells, ex) if form == "cell-input" else out_size(cells, ex)
            if ext is not None and f is None:
                text[names[c]] = framed_box_text(v, ext, cells, ex)
            elif f is not None:
                r_, c_ = int(v[0]), int(v[2])
                text[names[c]] = f"({r_},{c_})" + ("" if t.frames[c] == "input" else f"/{f[0]}x{f[1]}")
                cell[names[c]] = (r_, c_, f[0], f[1])
            elif t.types[c] in BOX_TYPES:
                text[names[c]] = box_text(v, ex, cells, form)
            else:
                text[names[c]] = value_text(cells, t.types[c], v, ex, idents, letters)
        rows.append(V.Row(text, key, cell))
    return rows


def default_layout(rows, names, types, order):
    """A grid on the first Box column whose values are cells of one frame at every row, with the other columns as
    one table entry in each grid cell; else each column its own table entry."""
    cols = [names[c] for c in order]
    for c in order:
        n = names[c]
        if types[c] in BOX_TYPES and rows and all(n in r.cell for r in rows) and len({r.cell[n][2:] for r in rows}) == 1:
            rest = [x for x in cols if x != n]
            return [V.Grid(n)] + ([V.Table(tuple(rest))] if rest else [])
    return [V.Table((x,)) for x in cols]


def view_lines(t, names, cells, n_train, n_test, order, idents, layout=None, letters=None):
    """The rows of t in a layout (the default where none is given), one block per example, train then test, and
    the task-wide rows in one block. A projection's rows, where an entry has no rows of its own, render in a block
    of their own under the columns they hold."""
    names = unique_names(names)
    offs = col_vals(t)
    t_ = t
    e_col = t.types.index("Example") if "Example" in t.types else None
    if e_col is not None and ((t.example == -1) & ~t.marker).any():   # task-wide rows by their Example column
        t_ = copy.copy(t)
        t_.example = np.where(t.example == -1, t.cells[:, offs[e_col]], t.example)
        order = [c for c in order if c != e_col]
    seen = np.nonzero(~t_.marker)[0]
    whole = {int(t_.entry[i]) for i in seen if t_.present[i, order].all()}
    forms = box_forms(t_, offs, seen, order, cells)
    exs = sorted({int(x) for x in t_.example[seen]})
    blocks = [(f"ex{e}" if e < n_train else f"test{e - n_train}", e) for e in range(n_train + n_test)]
    if exs == [-1]:      # task-wide rows alone: one block
        blocks = [("task", -1)]
    elif -1 in exs:
        blocks = [("task", -1)] + blocks
    all_models = bool(layout) and "M" in layout.split()
    lines, shown = [], None
    split = []
    for label, e in blocks:
        at = [i for i in seen if int(t_.example[i]) == e]
        ms = sorted({int(t_.model[i]) for i in at})
        if len(ms) < 2:
            split.append((label, e, at))
            continue
        for j, m in enumerate(ms if all_models else ms[:2]):
            split.append((f"{label} model {j + 1} of {len(ms)}", e, [i for i in at if int(t_.model[i]) == m]))
        if not all_models and len(ms) > 2:
            split.append((f"{label}: {len(ms) - 2} more models (a layout with M shows each)", e, None))
    for label, e, idx in split:
        if idx is None:
            lines.append(label)
            continue
        mine = [i for i in idx if t_.present[i, order].all()]
        proj = [i for i in idx if int(t_.entry[i]) not in whole]
        if not mine and not proj:
            lines.append(f"{label}  (no rows)")
            continue
        parts = ([(None, mine)] if mine else [])
        for k in sorted({int(t_.part[i]) for i in proj}):
            parts.append((k, [i for i in proj if int(t_.part[i]) == k]))
        for k, ii in parts:
            cols = [c for c in order if t_.present[ii, c].all()] if k is not None else order
            rows = layout_rows(t_, names, cells, ii, cols, idents, forms, letters)
            ent = V.parse(layout) if layout else default_layout(rows, names, t_.types, cols)
            if V.show(ent) != shown:
                shown = V.show(ent)
                lines.append("? " + ("E " if e >= 0 else "") + ("M " if " model " in label else "") + shown)
            head = label + (f"  (too many rows; their projection on {', '.join(names[c] for c in cols)})"
                            if k is not None else "")
            body = V.render(rows, ent) or (["(one row, no columns)"] if ii else [])
            if V.isgrid(ent):
                fs = {r.cell[ent[0].col][2:] for r in rows if ent[0].col in r.cell}
                frame = t_.frames[names.index(ent[0].col)] if ent[0].col in names else ""
                if len(fs) == 1 and frame != "input":
                    f = fs.pop()
                    head += "  (on the output grid)" if frame == "output" else f"  (cells of a {f[0]}x{f[1]} frame)"
            if head and body and len(head) + 2 + len(body[0]) < 200 and not V.isgrid(ent):
                lines.append(f"{head}  {body[0]}")
                lines += [" " * (len(head) + 2) + x for x in body[1:]]
            else:
                if head:
                    lines.append(head)
                lines += ["  " + x for x in body]
    return lines


def row_texts(t, idx, offs, ex, cells, names, order, idents, letters=None):
    return ["  " + " ".join(f"{names[c]}={value_text(cells, t.types[c], t.cells[i, offs[c]:offs[c + 1]], ex, idents, letters)}"
                            for c in order) for i in idx]


def signature_cols(t, offs, ex, order):
    seen = ~t.marker
    idx = np.nonzero((t.example == ex) & seen)[0]
    return sorted(tuple(tuple(int(v) for v in t.cells[i, offs[c]:offs[c + 1]]) for c in order) for i in idx)


def by_example(t, n_train, order):
    offs = col_vals(t)
    return [signature_cols(t, offs, e, order) for e in range(n_train)]


def restates(t, order, sig, earlier):
    """(an earlier relation, its columns) whose rows, projected onto those columns, are this table's rows at
    every train example, or None."""
    tys = type_key(t, order)
    for en, (ety, esig, enames) in earlier:
        if len(ety) <= len(tys) or len(ety) > 7:
            continue
        for pick in itertools.permutations(range(len(ety)), len(tys)):
            if any(ety[p] != ty for p, ty in zip(pick, tys)):
                continue
            if all(sorted(set(tuple(r[p] for p in pick) for r in es)) == sorted(set(s)) for es, s in zip(esig, sig)):
                return en, [enames[p] for p in pick]
    return None


def type_key(t, order):
    return tuple(t.types[c] for c in order)


def table_view(name, t, names, cells, n_train, n_test, assignments, earlier, limit=None, made=(), read=(), closest=False,
               layout=None, letters=None, assignment=None):
    """The view of one table: the header with row counts and flags, then its rows at each example in the layout
    (the default where none is given). With limit 0, the header alone. `assignment` is the place of t among the
    table's assignments, counted from 1, where the caller gives it."""
    lines = []
    shown = [c for c, ty in enumerate(t.types) if ty not in ("Unit",)]
    made = list(made)
    order = sorted(shown, key=lambda c: (made.index(names[c]) if names[c] in made else len(made), c))
    cols = ", ".join(f"{names[c]}:{t.types[c]}" for c in order)
    if t.unseen is not None:
        return [f"{name}({cols}): no rows to show ({t.unseen})"]
    t_all = t
    seen = ~t.marker
    by_e = False
    if "Example" in t.types and ((t.example == -1) & seen).any():
        o = col_vals(t)[t.types.index("Example")]
        t = copy.copy(t)
        t.example = np.where(t.example == -1, t.cells[:, o], t.example)
        by_e = True
    n_models = [len({int(m) for m in t.model[(t.example == e) & seen]}) for e in range(n_train + n_test)]
    if max(n_models, default=0) > 1:   # the counts and flags read the first model
        t_all = t
        t = copy.copy(t)
        t.marker = t.marker | (t.model != 0)
        seen = ~t.marker
    per = [int(((t.example == e) & seen).sum()) for e in range(n_train)]
    test = int(((t.example >= n_train) & seen).sum())
    wide = int(((t.example == -1) & seen).sum())
    flags = ["task-wide, its rows grouped by E"] if by_e else []
    sig = by_example(t, n_train, order) if not wide else None
    if wide and not sum(per):
        counts = f"task-wide rows: {wide}"
    elif by_e:
        counts = f"rows per train example: {per}"
    else:
        counts = f"rows per train example: {per}; test: {test}"
    if not sum(per) and not wide:
        flags.append("EMPTY at every train example")
    elif sum(per) and 0 in per:
        flags.append("empty at ex" + ",".join(str(e) for e, n in enumerate(per) if n == 0))
    if not order:
        flags.append("NO COLUMNS")
    elif sig and all(len(s) == 1 for s in sig) and len({tuple(s) for s in sig}) == 1:
        flags.append("CONSTANT: one row, the same at every example")
    elif sig and sum(per) and len({tuple(s) for s in sig}) == 1:
        flags.append("same rows at every train example")
    if sig is not None and sum(per) and order:
        for en, (ty, esig, _) in earlier:
            if ty == type_key(t, order) and esig == sig:
                flags.append(f"EQUAL to {en}")
                break
        else:
            r = restates(t, order, sig, read)
            if r:
                flags.append(f"RESTATES {r[0]}: its rows are {r[0]}'s columns {', '.join(r[1])}")
    head = f"{name}({cols})  {counts}"
    if max(n_models, default=0) > 1:
        head += (f"; models per train example: {n_models[:n_train]}"
                 + (f"; test: {n_models[n_train:]}" if n_test else "") + "; the counts are at the first model")
    if assignments > 1 and assignment is not None:
        head += f"; {assignments} DET assignments, assignment {assignment} shown"
    elif assignments > 1:
        head += f"; {assignments} DET assignments, " + (
            "the one closest to the train outputs shown" if closest
            else "assignment 1 shown; `done` shows the one closest to the train outputs")
    lines.append(head)
    if flags:
        lines.append("flags: " + "; ".join(flags))
    if not t.types or limit == 0:
        return lines
    return lines + view_lines(t_all, names, cells, n_train, n_test, order, {}, layout, letters)
