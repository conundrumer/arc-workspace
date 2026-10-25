"""Write the rollout export of sampler lines: the tables export of their streams, one part per task.

    work/lm/.venv/bin/python lm/export_rollouts.py <sampler lines> [<sampler lines> ...] <out dir> [--step-cap N]

Each sampler lines file is the `--out` of lm/sample.py: a settings line, then one line per continuation. Every file
must give the same `settings` and the world `Closed`, the world in which the replay judges the train pairs. The
streams of each task are replayed by `arclog.stream_tables` under those settings, with the case names of
lm/rollout_labels.py (`case_name`), and written as engine/arclog-py/tables_export.py writes a part; the whole files
and `report.txt` follow, as that script's `merge` writes them. `<out dir>` must not exist or be empty. Where more than
one file is given, `<out dir>/samples.jsonl` gets the first file's settings line and every continuation line, for
lm/rollout_labels.py; each continuation line gets the fields of `rollout_labels.sampler_meta` of its own file's
settings line: the prefix mode, the sampling LM's run and fold, and the data export of the prefixes.

Each case holds the tables of its stream's steps; a stream cut at the sampler's step cap or at an empty mask holds
the tables up to its cut, and one that faults those up to the fault. For each branch point whose gold line is given,
the run checks that the export's `token` of a table is an index into the stream as the sampler writes it (the
engine's emitted ids included), the index that `prefix_tokens` counts: each table's token indexes an id that the
model wrote (an evidence table's token is 0), the tables before `prefix_tokens`, with their entries' rows, are the same in the gold case and in each continuation of the branch
point, and the first table of the gold case at or after `prefix_tokens`, if any, has its token at or after it.
"""
import argparse, json, os, sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine" / "arclog-py"))
import arclog
import tables_export as X
from rollout_labels import POINT_EVIDENCE, case_name, sampler_meta

TABLE_FIELDS = ["form", "point", "relation", "fact", "column_names", "column_types", "width", "det_relations", "depth",
                "keys", "fault"]   # the tables.parquet columns compared across a branch point's cases


def read_lines(paths):
    """The settings line of the first file (the files must agree in `settings` and `world`) and every continuation line,
    each with the `sampler_meta` of its own file."""
    head, lines = None, []
    for p in paths:
        rows = [json.loads(l) for l in open(p) if l.strip()]
        h = {k: rows[0][k] for k in ("settings", "world")}
        if head is None:
            head, first = h, rows[0]
        elif h != head:
            raise ValueError(f"{p}: settings {h} differ from {paths[0]}'s {head}")
        meta = sampler_meta(rows[0])
        lines += [dict(r, **meta) for r in rows[1:]]
    if head["world"] != "Closed":
        raise ValueError(f"world {head['world']}: the replay judges the train pairs in the closed world")
    return first, lines


def merged_text(first, lines):
    """The text of `<out dir>/samples.jsonl`: the first file's settings line, then every continuation line."""
    return "".join(json.dumps(r) + "\n" for r in [first] + lines)


def prefix_values(out, index, parts, task, case, n):
    """What the entries of the case's tables before token n hold, each as (table, example kind, example index, kind,
    rows, content); `index` is {case: its index.parquet rows}, and `parts` is {case: (the width of each table's
    projections, in order, the first row of each projection at each entry)} as `projection_parts` gives. The content
    of a Rows entry (kind 0) is its values; of a Count entry (kind 1), which has no values of its own, it is the
    projections' rows at that entry, each as (projection, defined, rows, values); of any other kind, nothing."""
    v = np.fromfile(f"{out}/values/{task}/{case}.i32", np.int32)
    widths, at = parts.get(case, ({}, {}))
    e = index[case][index[case]["token"] < n]
    res = []
    for r in e.itertuples():
        kind, rows = int(r.kind), int(r.rows)
        if kind == 0:
            content = v[int(r.offset):int(r.offset) + rows * int(r.width)].tobytes()
        elif kind == 1:
            content = []
            for j, w in widths.get(int(r.table), []):
                defined, k, off = at.get((j, int(r.entry)), (0, 0, 0))
                content.append((j, defined, k, v[off:off + k * w].tobytes() if defined else b""))
        else:
            content = None
        res.append((int(r.table), int(r.example_kind), int(r.example_index), kind, rows, content))
    return res


def projection_parts(projections, projection_rows):
    """{case: ({table: [(projection, width)]}, {(projection, entry): (defined, rows, offset)})} from the frames of
    projections.parquet and projection_rows.parquet; a projection is numbered by its order among its case's."""
    projections = projections.reset_index(drop=True)
    projections["projection"] = projections.groupby(["task", "case"]).cumcount()
    parts = {}
    for (_, c), p in projections.groupby(["task", "case"], sort=False):
        widths = {}
        for r in p.itertuples():
            widths.setdefault(int(r.table), []).append((int(r.projection), int(r.width)))
        parts[c] = (widths, {})
    for r in projection_rows.itertuples():
        if r.case in parts:
            parts[r.case][1][(int(r.projection), int(r.entry))] = (int(r.defined), int(r.rows), int(r.offset))
    return parts


def check_prefix(out, tables, index, projections, projection_rows, lines):
    """The checks of the module docstring on the export's tables.parquet frame and the sampler lines."""
    names = {case_name(s["task"], s["case"], s["branch"], s["rollout"]): s for s in lines}
    for (task, case), t in tables.groupby(["task", "case"], sort=False):
        s = names[case]
        model = s["model"]
        bad = [int(i) for i in t[t["point"] != POINT_EVIDENCE]["token"] if not model[i]]
        assert not bad, f"{case}: tables at tokens {bad[:5]} that index an id the engine emitted"
    fields = [c for c in TABLE_FIELDS if c in tables.columns]
    index = {c: e for (_, c), e in index.groupby(["task", "case"], sort=False)}
    parts = projection_parts(projections, projection_rows)
    by_case = {c: t.sort_values("table") for (_, c), t in tables.groupby(["task", "case"], sort=False)}
    for gold in (s for s in lines if s["rollout"] == "gold"):
        g = case_name(gold["task"], gold["case"], gold["branch"], "gold")
        if g not in by_case:
            continue
        n = int(gold["prefix_tokens"])
        gt = by_case[g]
        after = gt[gt["token"] >= n]
        if len(after):
            first = int(after["table"].iloc[0])
            assert (gt[gt["table"] < first]["token"] < n).all(), f"{g}: a table before table {first} lies after token {n}"
        pre = gt[gt["token"] < n][["token"] + fields].reset_index(drop=True)
        for s in lines:
            if (s["task"], s["case"], s["branch"]) == (gold["task"], gold["case"], gold["branch"]) and s["rollout"] != "gold":
                assert s["ids"][:n] == gold["ids"][:n], f"{s['task']} {s['case']} b{s['branch']} r{s['rollout']}: another prefix than the gold's"
                c = case_name(s["task"], s["case"], s["branch"], s["rollout"])
                if c in by_case:
                    rt = by_case[c]
                    rpre = rt[rt["token"] < n][["token"] + fields].reset_index(drop=True)
                    assert pre.astype(str).equals(rpre.astype(str)), f"{c}: its tables before token {n} differ from {g}'s"
                    assert prefix_values(out, index, parts, s["task"], c, n) == prefix_values(out, index, parts, gold["task"], g, n), \
                        f"{c}: the rows of its tables before token {n} differ from {g}'s"


def replay(task, streams, names, settings, step_cap):
    """`arclog.stream_tables` of the task's streams."""
    return arclog.stream_tables(task, X.TASKS, streams, names=names, settings=settings, step_cap=step_cap)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="+", help="the sampler lines files, then the out dir")
    ap.add_argument("--step-cap", type=int, default=10000, help="the replay's step cap, as in the corpus export")
    a = ap.parse_args()
    *paths, out = a.paths
    if not paths:
        ap.error("no sampler lines file")
    if os.path.exists(out) and os.listdir(out):
        raise FileExistsError(f"{out} exists and is not empty")
    first, lines = read_lines(paths)
    settings = arclog.DecodeSettings(**first["settings"])
    os.makedirs(f"{out}/parts", exist_ok=True)
    tasks = sorted({s["task"] for s in lines})
    for k, task in enumerate(tasks):
        mine = [s for s in lines if s["task"] == task]
        streams = [(s["ids"], s["model"]) for s in mine]
        names = [case_name(s["task"], s["case"], s["branch"], s["rollout"]) for s in mine]
        twice = sorted({n for n in names if names.count(n) > 1})
        if twice:
            raise ValueError(f"{task}: case names that stand twice, such as rollout indexes that two sampler files "
                             f"both give: {twice[:5]}")
        cases, report = replay(task, streams, names, settings, a.step_cap)
        X.write_part(out, k, [(task, cases, report)])
        print(f"{task}: {len(mine)} streams, {len(cases)} cases, {len(report)} report lines", flush=True)
    X.merge(out)
    if len(paths) > 1:
        with open(f"{out}/samples.jsonl", "w") as f:
            f.write(merged_text(first, lines))
    if os.path.exists(f"{out}/tables.parquet"):
        check_prefix(out, pd.read_parquet(f"{out}/tables.parquet"), pd.read_parquet(f"{out}/index.parquet"),
                     pd.read_parquet(f"{out}/projections.parquet"), pd.read_parquet(f"{out}/projection_rows.parquet"),
                     lines)
        print("prefix check: passed")


if __name__ == "__main__":
    main()
