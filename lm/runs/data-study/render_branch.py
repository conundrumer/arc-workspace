"""Render one branch point of a rollout export as Markdown, or list the branch points of a task.

    work/lm/.venv/bin/python lm/runs/data-study/render_branch.py list <export> <data> [<task>]
    work/lm/.venv/bin/python lm/runs/data-study/render_branch.py render <export> <data> <task> <prefix_tokens>
        [--out FILE] [--samples 6] [--tables 2] [--tasks-dir data/tasks]

<export> is a rollout export (lm/export_rollouts.py) with its labels.jsonl and samples.jsonl; <data> is the data
export whose vocab.json maps token ids to names and whose cases.npz the labels' `heldout` flag comes from.
`list` prints one line per branch point (of <task>, or of every held-out task where no task is given): task, corpus
case, prefix_tokens, gold length, prefix_tokens over gold length, sampled continuations, those with at least one
table after the branch, and the gold's tables after the branch. `render` writes the Markdown of README.md to --out
(default lm/runs/data-study/<task>-<prefix_tokens>.md); a "## What I see" section of an existing file is kept.
"""
import argparse, json, os, sys, tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "lm"))
import encoder as E   # noqa: E402

PARTS = ("tables", "index", "assigned", "projections", "projection_rows")   # no flows: the rows give the features
SEE = "## What I see"
MAX_ROWS = 30


# ------------------------------------------------------------------ reading

def read_labels(export, task=None):
    out = []
    for line in open(Path(export) / "labels.jsonl"):
        if line.strip():
            lab = json.loads(line)
            if task is None or lab["task"] == task:
                out.append(lab)
    return out


def read_samples(export, task=None):
    """The sampler lines of `task` (every task where None), keyed by (task, corpus case, branch, rollout)."""
    out = {}
    with open(Path(export) / "samples.jsonl") as f:
        f.readline()
        for line in f:
            if task is not None and f'"task": "{task}"' not in line[:200]:
                continue
            s = json.loads(line)
            if task is None or s["task"] == task:
                out[(s["task"], s["case"], s["branch"], str(s["rollout"]))] = s
    return out


def branch_points(labels):
    """{(task, corpus case, prefix_tokens): [label]} in the file's order."""
    g = defaultdict(list)
    for lab in labels:
        g[(lab["task"], lab["corpus_case"], int(lab["prefix_tokens"]))].append(lab)
    return g


def tables_after(tables, lab):
    """The count of the case's relation tables at or after the branch."""
    if lab["prefix_tables"] is None:
        return 0
    t = tables.get(lab["case"])
    return 0 if t is None else int((t >= lab["prefix_tables"]).sum())


def list_points(export, task):
    labels = read_labels(export, task)
    samples = read_samples(export, task)
    filt = [("task", "==", task)] if task else None
    t = pd.read_parquet(Path(export) / "tables.parquet", columns=["task", "case", "table", "point"], filters=filt)
    t = t[t["point"] == E.POINT_RELATION]
    tables = {c: g["table"].to_numpy() for c, g in t.groupby("case")}
    print("task case prefix_tokens gold_length fraction sampled with_table gold_tables_after")
    for (tk, case, p), labs in sorted(branch_points(labels).items(), key=lambda kv: (kv[0][0], kv[0][2])):
        if task is None and not labs[0]["heldout"]:
            continue
        gold = [lab for lab in labs if lab["rollout"] == "gold"]
        gs = samples.get((tk, case, labs[0]["branch"], "gold"))
        n = len(gs["ids"]) if gs else None
        sampled = [lab for lab in labs if lab["rollout"] != "gold"]
        print(tk, json.dumps(case), p, n, f"{p / n:.2f}" if n else "-", len(sampled),
              sum(tables_after(tables, lab) > 0 for lab in sampled),
              tables_after(tables, gold[0]) if gold else "-")


def load_members(export, task, labs, tasks_dir):
    """encoder.load_rollouts on a copy of the export that holds only the cases of `labs`, with strict=False and
    allow_violations=True: {(task, case): member}, and the cases it left out with their faults."""
    cases = [lab["case"] for lab in labs]
    export = Path(export)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for part in PARTS:
            df = pd.read_parquet(export / f"{part}.parquet", filters=[("task", "==", task), ("case", "in", cases)])
            df.to_parquet(tmp / f"{part}.parquet")
        (tmp / "values").mkdir()
        os.symlink((export / "values" / task).resolve(), tmp / "values" / task)
        for name in ("orientations.json", "orientation_types.json"):
            if (export / name).exists():
                (tmp / name).write_text((export / name).read_text())
        with open(tmp / "labels.jsonl", "w") as f:
            f.write("".join(json.dumps(lab) + "\n" for lab in labs))
        return E.load_rollouts(tmp, tasks_dir=tasks_dir, strict=False, allow_violations=True)


# ------------------------------------------------------------------ text

def grid_text(g):
    return [" ".join(str(c) for c in row) for row in g]


def pair_text(inp, out):
    a, b = grid_text(inp), grid_text(out)
    wa = max(len(x) for x in a)
    lines = [f"{'input':<{wa}}    output"]
    for i in range(max(len(a), len(b))):
        lines.append(f"{a[i] if i < len(a) else '':<{wa}}    {b[i] if i < len(b) else ''}".rstrip())
    return "\n".join(lines)


def stream_text(ids, model, names, kinds, start, end):
    """The tokens of [start, end) by name, engine-written ones in [brackets], a line ending after each run of
    relation declarations that the engine writes (the end of a clause)."""
    out, line = [], []
    for j in range(start, end):
        engine_rel = not model[j] and kinds[ids[j]] == "relation"
        line.append(names[ids[j]] if model[j] else f"[{names[ids[j]]}]")
        nxt = j + 1 < end and not model[j + 1] and kinds[ids[j + 1]] == "relation"
        if engine_rel and not nxt:
            out.append(" ".join(line)); line = []
    if line:
        out.append(" ".join(line))
    return "\n".join(out)


def clause_end(ids, model, kinds, j):
    """The index after the end of the clause that holds index j: after the run of engine-written relation
    declarations at or after j, or the stream's end."""
    n = len(ids)
    while j < n and (model[j] or kinds[ids[j]] != "relation"):
        j += 1
    while j < n and not model[j] and kinds[ids[j]] == "relation":
        j += 1
    return j


class Cells:
    """Renders a row's cells by column type, with the grid sizes of each example."""

    def __init__(self, task_json, orientations):
        pairs = task_json["train"] + task_json["test"]
        self.inp = [(len(p["input"]), len(p["input"][0])) for p in pairs]
        self.out = [(len(p["output"]), len(p["output"][0])) for p in task_json["train"]]
        self.orient = {int(k): v for k, v in orientations}

    def cell_grid(self, t, idx, offs, ex):
        """The rows idx of example ex drawn on a grid, where every row's first Box column is a cell of one grid
        size (the margins t + b and l + r the same in every row): each cell gives the row's Color where the table has one Color column and the
        cell has one row, else the count of rows at the cell ('+' past 9); '.' marks a cell with no row."""
        boxes = [k for k, ty in enumerate(t.types) if ty == "Box"]
        if not boxes or not len(idx):
            return None
        k = boxes[0]
        m = t.cells[idx, offs[k]:offs[k + 1]]
        if not t.present[idx, k].all():
            return None
        hs, ws = set((m[:, 0] + m[:, 1] + 1).tolist()), set((m[:, 2] + m[:, 3] + 1).tolist())
        if len(hs) != 1 or len(ws) != 1 or (m < 0).any():
            return None
        h, w = hs.pop(), ws.pop()
        name = ("the input" if ex < len(self.inp) and self.inp[ex] == (h, w) else
                "the output" if ex < len(self.out) and self.out[ex] == (h, w) else "neither the input nor the output")
        colors = [c for c, ty in enumerate(t.types) if ty == "Color"]
        count = np.zeros((h, w), int)
        color = np.full((h, w), -1)
        for i, (r, c) in zip(idx, m[:, [0, 2]]):
            count[r, c] += 1
            if len(colors) == 1:
                color[r, c] = t.cells[i, offs[colors[0]]]
        by_color = len(colors) == 1 and count.max() == 1
        what = "the row's Color" if by_color else "the count of rows at the cell"
        g = [" ".join("." if not count[r, c] else str(color[r, c]) if by_color else
                      (str(count[r, c]) if count[r, c] < 10 else "+") for c in range(w)) for r in range(h)]
        return (f"The rows drawn on a {h}x{w} grid, the size of {name} grid, by the first Box column, each cell showing {what}, "
                f"'.' where no row is:\n```\n" + "\n".join(g) + "\n```")

    def box(self, m, ex):
        t, b, l, r = (int(x) for x in m)
        sizes = []
        if 0 <= ex < len(self.inp):
            sizes.append(self.inp[ex])
        if 0 <= ex < len(self.out) and self.out[ex] != self.inp[ex]:
            sizes.append(self.out[ex])
        for k, (h, w) in enumerate(sizes):
            if t + b == h - 1 and l + r == w - 1 and t >= 0 and l >= 0 and b >= 0 and r >= 0:
                return f"({t},{l})" + ("" if k == 0 else "out")
        if t == -b and l == -r:
            return f"+({t},{l})"
        if sizes:
            h, w = sizes[0]
            if t >= 0 and b >= 0 and l >= 0 and r >= 0 and t <= h - 1 - b and l <= w - 1 - r:
                return f"r{t}-{h - 1 - b} c{l}-{w - 1 - r}"
        return f"[{t} {b} {l} {r}]"

    def cell(self, ty, v, ex):
        if ty == "Box":
            return self.box(v, ex)
        v = int(v[0])
        if ty in ("Number", "Color"):
            return str(v)
        if ty == "Example":
            return f"e{v}"
        if ty == "Ident":
            return f"id{v}"
        return self.orient.get(v, f"?{v}")


def table_text(t, row, cells, n_train, rec):
    """The Markdown of one Table: its header lines, then its rows per train example."""
    names = list(row["column_names"])
    all_types = [E.type_name(x) for x in row["column_types"]]
    cols = ", ".join(f"{names[p]}: {all_types[p]}" for p in t.positions)
    dropped = [f"{names[i]}: Unit" for i, x in enumerate(all_types) if x == "Unit"]
    keys = [[names[c] for c in k] for k in row["keys"]]
    lines = [f"- relation: &r{t.relation}",
             f"- columns: {cols}" + (f" (Unit columns dropped: {', '.join(dropped)})" if dropped else ""),
             f"- depth {row['depth']}, step {t.step} (stream token {t.step - 1}), export table {t.export_table}, "
             f"candidate keys {keys if keys else 'none'}",
             f"- labels: position {rec['position']}, solving {rec['solving']}, consistent {rec['consistent']}, "
             f"empty {rec['empty']}, unseen {rec['unseen']}, faulted {rec['faulted']}"]
    if t.det_relations:
        lines.append(f"- DETs assigned: {list(t.det_relations)}; this Table's assignment (index of each DET's value): "
                     f"{t.assignment[0].tolist() if len(t.assignment) else []}")
    note = row.get("note")
    if t.unseen is not None:
        lines.append(f"- unseen: {t.unseen} {t.unseen_entries or ''}")
        if note:
            lines.append(f"- the export's first fault or stop of the table or its entries: {note}")
        return "\n".join(lines)
    if t.unseen_entries:
        lines.append(f"- unseen entries: {t.unseen_entries}" + (f"; the export's first fault or stop: {note}" if note else ""))
    seen = ~t.marker
    per = [int(((t.example == e) & seen).sum()) for e in range(n_train)]
    other = int(seen.sum()) - sum(per)
    lines.append(f"- rows per train example: {per}" + (f"; {other} rows of test or task-wide entries" if other else ""))
    widths = [E.width(x) for x in t.types]
    offs = np.cumsum([0] + widths)
    for e in range(n_train):
        idx = np.nonzero((t.example == e) & seen)[0]
        lines.append(f"\nTrain example {e}: {len(idx)} row{'' if len(idx) == 1 else 's'}" + (f", the first {MAX_ROWS} shown" if len(idx) > MAX_ROWS else ""))
        if not len(idx):
            continue
        if not t.types:
            lines.append("The relation has no columns: its one row says the relation holds.")
            continue
        body = []
        for i in idx[:MAX_ROWS]:
            parts = []
            for k, ty in enumerate(t.types):
                parts.append(cells.cell(ty, t.cells[i, offs[k]:offs[k + 1]], e) if t.present[i, k] else "-")
            body.append(" | ".join(parts) + (f"   (projection {int(t.part[i])})" if t.part[i] else ""))
        header = " | ".join(names[p] for p in t.positions)
        drawn = cells.cell_grid(t, idx, offs, e)
        if drawn:
            lines.append(drawn)
        lines.append("```\n" + header + "\n" + "\n".join(body) + "\n```")
    return "\n".join(lines)


def continuation_text(member, lab, s, rows_of, names, kinds, cells, n_train, n_tables):
    """The Markdown of one continuation: its labels, its text up to the clause of its last shown table, those
    tables, and a list of every table after the branch."""
    ids, model, p = s["ids"], s["model"], int(lab["prefix_tokens"])
    out = [f"- case: `{lab['case']}`",
           f"- sampler labels: ended {lab['ended']}, consistency {lab['consistency']}, solved_test {lab['solved_test']}, "
           f"fault {lab['fault']}, verdicts of the RULE clauses after the branch {lab['rules']}",
           f"- tokens after the branch: {len(ids) - p}"]
    if member is None:
        out.append("- the loader left this case out")
        return "\n".join(out), []
    tabs = [(t, r) for t, r in zip(member["tables"], member["records"]) if not t.evidence and r["position"] >= 0]
    out.append(f"- solving (value label): {member['solving']}")
    positions = sorted({r["position"] for _, r in tabs})
    shown = [(t, r) for t, r in tabs if r["position"] < n_tables]
    end = clause_end(ids, model, kinds, max(t.step - 1 for t, _ in shown)) if shown else len(ids)
    out.append(f"\nText after the branch, tokens {p} to {end}" + (f" of {len(ids)}" if end < len(ids) else "") + ":")
    out.append("```\n" + stream_text(ids, model, names, kinds, p, end) + "\n```")
    if not tabs:
        out.append("\nNo table after the branch.")
    for t, r in shown:
        out.append(f"\n#### Table at position {r['position']}: &r{t.relation}\n")
        out.append(table_text(t, rows_of[t.export_table], cells, n_train, r))
    if positions:
        out.append(f"\nEvery table after the branch ({len(positions)} export tables):\n")
        out.append("| position | relation | token | depth | columns | rows per train example | consistent | empty | unseen | faulted |")
        out.append("|---|---|---|---|---|---|---|---|---|---|")
        for t, r in tabs:
            per = [int(((t.example == e) & ~t.marker).sum()) for e in range(n_train)] if t.unseen is None else "-"
            out.append(f"| {r['position']} | &r{t.relation} | {t.step - 1} | {rows_of[t.export_table]['depth']} | {' '.join(t.types)} | {per} | "
                       f"{r['consistent']} | {r['empty']} | {r['unseen']} | {r['faulted']} |")
    return "\n".join(out), tabs


def render(export, data, task, prefix, out_path, n_samples, n_tables, tasks_dir):
    labels = read_labels(export, task)
    group = [lab for (tk, _, p), ls in branch_points(labels).items() if p == prefix for lab in ls]
    if not group:
        sys.exit(f"no branch point of {task} at prefix_tokens {prefix}")
    gold = [lab for lab in group if lab["rollout"] == "gold"]
    sampled = [lab for lab in group if lab["rollout"] != "gold"]
    keep = gold + sampled[:n_samples]
    samples = read_samples(export, task)
    vocab = json.load(open(Path(data) / "vocab.json"))
    names, kinds = vocab["names"], vocab["kinds"]
    task_json = json.load(open(Path(tasks_dir) / f"{task}.json"))
    n_train = len(task_json["train"])
    cells = Cells(task_json, json.load(open(Path(export) / "orientations.json")))
    members, skipped = load_members(export, task, keep, tasks_dir)
    rows = pd.read_parquet(Path(export) / "tables.parquet", filters=[("task", "==", task),
                                                                     ("case", "in", [lab["case"] for lab in keep])])
    rows_by = {c: {int(r["table"]): r for r in g.to_dict("records")} for c, g in rows.groupby("case")}
    index = pd.read_parquet(Path(export) / "index.parquet", filters=[("task", "==", task),
                            ("case", "in", [lab["case"] for lab in keep])],
                            columns=["case", "table", "fault", "stop_bound", "stop_form", "value_stop_bound",
                                     "value_stop_form"])
    for c, tabs in rows_by.items():
        for k, r in tabs.items():
            notes = [r["fault"]] if isinstance(r["fault"], str) else []
            for e in index[(index["case"] == c) & (index["table"] == k)].to_dict("records"):
                if isinstance(e["fault"], str):
                    notes.append(e["fault"])
                for b, f in (("stop_bound", "stop_form"), ("value_stop_bound", "value_stop_form")):
                    if isinstance(e[b], str):
                        notes.append(f"stopped at {e[b]}" + (f" in {e[f]}" if isinstance(e[f], str) else ""))
            r["note"] = notes[0] if notes else None
    g0 = gold[0] if gold else sampled[0]
    gs = samples[(task, g0["corpus_case"], g0["branch"], "gold")] if gold else None
    any_s = samples[(task, g0["corpus_case"], g0["branch"], str(g0["rollout"]))]
    n_gold = len(gs["ids"]) if gs else None

    md = [f"# {task} at prefix_tokens {prefix}", "",
          f"- corpus case: `{g0['corpus_case']}`, branch (rule index) {g0['branch']}, prefix rules {g0['prefix_rules']}",
          f"- prefix_tokens {prefix} of the gold's {n_gold} tokens ({prefix / n_gold:.2f})" if n_gold else "",
          f"- prefix tables (evidence tables included): {g0['prefix_tables']}",
          f"- sampled continuations: {len(sampled)}, of which {len(keep) - len(gold)} are shown, in the export's order",
          f"- held out: {g0['heldout']}; sampler: {sampled[0]['sampler_run'] if sampled else None} "
          f"(fold {sampled[0]['sampler_fold'] if sampled else None})",
          "- cells: a Position is `(row,col)` of the example's input grid (`(row,col)out` where it fits only the "
          "output grid), an Offset `+(drow,dcol)`, another Box `rR0-R1 cC0-C1` over the input grid or `[t b l r]` "
          "margins; an Ident is `id<n>`, equal only within one case; see README.md", ""]
    md.append("## Train pairs\n")
    for i, pr in enumerate(task_json["train"]):
        hi, wi, ho, wo = len(pr["input"]), len(pr["input"][0]), len(pr["output"]), len(pr["output"][0])
        md.append(f"### Train example {i}: input {hi}x{wi}, output {ho}x{wo}\n")
        md.append("```\n" + pair_text(pr["input"], pr["output"]) + "\n```\n")
    md.append("## Prefix program\n")
    md.append("Model-written tokens plain, engine-written ones in [brackets]; a line ends with each clause's relation "
              "declarations.\n")
    md.append("```\n" + stream_text(any_s["ids"], any_s["model"], names, kinds, 0, prefix) + "\n```\n")
    for lab in keep:
        s = samples[(task, lab["corpus_case"], lab["branch"], str(lab["rollout"]))]
        title = "Gold continuation" if lab["rollout"] == "gold" else f"Sampled continuation r{lab['rollout']}"
        md.append(f"## {title}\n")
        text, _ = continuation_text(members.get((task, lab["case"])), lab, s, rows_by.get(lab["case"], {}), names,
                                    kinds, cells, n_train, n_tables)
        md.append(text + "\n")
    if skipped:
        md.append(f"Cases the loader left out: {skipped}\n")
    see = f"{SEE}\n\n(not written yet)\n"
    if out_path.exists():
        old = out_path.read_text()
        if SEE in old:
            see = old[old.index(SEE):]
    out_path.write_text("\n".join(x for x in md if x is not None) + "\n" + see)
    print(f"wrote {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["list", "render"])
    ap.add_argument("export")
    ap.add_argument("data")
    ap.add_argument("task", nargs="?")
    ap.add_argument("prefix_tokens", nargs="?", type=int)
    ap.add_argument("--out")
    ap.add_argument("--samples", type=int, default=6)
    ap.add_argument("--tables", type=int, default=2)
    ap.add_argument("--tasks-dir", default=str(ROOT / "data/tasks"))
    a = ap.parse_args()
    if a.mode == "list":
        list_points(a.export, a.task)
        return
    if a.task is None or a.prefix_tokens is None:
        ap.error("render takes a task and a prefix_tokens")
    out = Path(a.out) if a.out else Path(__file__).resolve().parent / f"{a.task}-{a.prefix_tokens}.md"
    render(a.export, a.data, a.task, a.prefix_tokens, out, a.samples, a.tables, a.tasks_dir)


if __name__ == "__main__":
    main()
