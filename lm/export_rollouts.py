"""Write the rollout export of sampler lines: the tables export of their streams, one part per task.

    work/lm/.venv/bin/python lm/export_rollouts.py <sampler lines> [<sampler lines> ...] <out dir> [--step-cap N]

Each sampler lines file is the `--out` of lm/sample.py: a settings line, then one line per continuation. Every file
must give the same `settings` and the world `Closed`, the world in which the replay judges the train pairs. The
streams of each task are replayed by `arclog.stream_tables` under those settings, with the case names of
lm/rollout_labels.py (`case_name`), and written as engine/arclog-py/tables_export.py writes a part; the whole files
and `report.txt` follow, as that script's `merge` writes them. `<out dir>` must not exist or be empty. Where more than
one file is given, `<out dir>/samples.jsonl` gets the first settings line and every continuation line, for
lm/rollout_labels.py.

Each case holds the tables of its stream's steps; a stream cut at the sampler's step cap or at an empty mask holds
the tables up to its cut, and one that faults those up to the fault. Where the replay of a task panics,
`arclog.stream_tables` gives no tables of any of its streams; the run then replays each stream alone, and a stream
whose replay panics gives no tables and a fault line. For each branch point whose gold line is given,
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
from rollout_labels import POINT_EVIDENCE, case_name

TABLE_FIELDS = ["form", "point", "relation", "fact", "column_names", "column_types", "width", "det_relations", "depth",
                "keys", "fault"]   # the tables.parquet columns compared across a branch point's cases


def read_lines(paths):
    """The settings line of the files (which must agree) and every continuation line."""
    head, lines = None, []
    for p in paths:
        rows = [json.loads(l) for l in open(p) if l.strip()]
        h = {k: rows[0][k] for k in ("settings", "world")}
        if head is None:
            head, first = h, rows[0]
        elif h != head:
            raise ValueError(f"{p}: settings {h} differ from {paths[0]}'s {head}")
        lines += rows[1:]
    if head["world"] != "Closed":
        raise ValueError(f"world {head['world']}: the replay judges the train pairs in the closed world")
    return first, lines


def prefix_values(out, index, task, case, n):
    """The entries of the case's tables before token n, each as (table, example kind, example index, rows, values);
    `index` is {case: its index.parquet rows}."""
    v = np.fromfile(f"{out}/values/{task}/{case}.i32", np.int32)
    e = index[case][index[case]["token"] < n]
    return [(int(r.table), int(r.example_kind), int(r.example_index), int(r.rows),
             v[int(r.offset):int(r.offset) + int(r.rows) * int(r.width)].tobytes()) for r in e.itertuples()]


def check_prefix(out, tables, index, lines):
    """The checks of the module docstring on the export's tables.parquet frame and the sampler lines."""
    names = {case_name(s["task"], s["case"], s["branch"], s["rollout"]): s for s in lines}
    for (task, case), t in tables.groupby(["task", "case"], sort=False):
        s = names[case]
        model = s["model"]
        bad = [int(i) for i in t[t["point"] != POINT_EVIDENCE]["token"] if not model[i]]
        assert not bad, f"{case}: tables at tokens {bad[:5]} that index an id the engine emitted"
    fields = [c for c in TABLE_FIELDS if c in tables.columns]
    index = {c: e for (_, c), e in index.groupby(["task", "case"], sort=False)}
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
                    assert prefix_values(out, index, s["task"], c, n) == prefix_values(out, index, gold["task"], g, n), \
                        f"{c}: the rows of its tables before token {n} differ from {g}'s"


def replay(task, streams, names, settings, step_cap):
    """`arclog.stream_tables` of the task's streams. Where a unit panics, the call gives no tables of any stream;
    then each stream is replayed alone, and a stream whose replay panics gives no tables and the fault line
    `<task> <case>: <the panic's line>`."""
    cases, report = arclog.stream_tables(task, X.TASKS, streams, names=names, settings=settings, step_cap=step_cap)
    if not (len(report) == 1 and report[0].startswith(f"{task}: ")):
        return cases, report
    cases, verdicts, faults = [], [], []
    for stream, name in zip(streams, names):
        c, r = arclog.stream_tables(task, X.TASKS, [stream], names=[name], settings=settings, step_cap=step_cap)
        if len(r) == 1 and r[0].startswith(f"{task}: "):
            faults.append(f"{task} {name}: {r[0][len(task) + 2:]}")
            continue
        cases += c
        verdicts += [l for l in r if ": ended " in l]
        faults += [l for l in r if ": ended " not in l]
    print(f"{report[0]}; replayed each stream alone, {len(faults)} fault lines", flush=True)
    return cases, verdicts + faults


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
            f.write("".join(json.dumps(r) + "\n" for r in [first] + lines))
    if os.path.exists(f"{out}/tables.parquet"):
        check_prefix(out, pd.read_parquet(f"{out}/tables.parquet"), pd.read_parquet(f"{out}/index.parquet"), lines)
        print("prefix check: passed")


if __name__ == "__main__":
    main()
